"""Turn data/raw-<season>.json into a single self-contained f1-dashboard.html.

The dashboard bakes in a season snapshot rather than calling the API from the
browser: the brief asks for one file you can open locally and share, and a
shared file that fetches from a third party breaks the moment that third party
rate-limits, moves, or goes down.

    python fetch.py 2026 2025     # refresh the snapshot
    python build.py               # rebuild f1-dashboard.html

Row layouts written into the payload (kept as arrays to hold the file size down):
    res / spr : [driverId, teamId, pos|null, posText, grid, points, status, millis|null]
    qual      : [driverId, pos]
"""
import datetime
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

# --------------------------------------------------------------------------
# Team colours. The API carries no colours, so these are maintained by hand.
# 2026 liveries in particular are best-guess brand colours - correct any hex
# here and re-run build.py; nothing else needs touching.
# --------------------------------------------------------------------------
TEAM_COLOURS = {
    "alpine":       "#0093CC",
    "aston_martin": "#229971",
    "audi":         "#F50537",
    "cadillac":     "#C6A15B",
    "ferrari":      "#E8002D",
    "haas":         "#B6BABD",
    "mclaren":      "#FF8000",
    "mercedes":     "#00D7B6",
    "rb":           "#6692FF",
    "red_bull":     "#3671C6",
    "sauber":       "#52E252",
    "williams":     "#64C4FF",
}
FALLBACK_COLOUR = "#6B7280"

# Country as the API spells it -> ISO 3166-1 alpha-2, shown as the flag badge.
ISO2 = {
    "Australia": "AU", "Austria": "AT", "Azerbaijan": "AZ", "Bahrain": "BH",
    "Belgium": "BE", "Brazil": "BR", "Canada": "CA", "China": "CN",
    "France": "FR", "Germany": "DE", "Hungary": "HU", "India": "IN",
    "Italy": "IT", "Japan": "JP", "Korea": "KR", "Malaysia": "MY",
    "Mexico": "MX", "Monaco": "MC", "Netherlands": "NL", "Portugal": "PT",
    "Qatar": "QA", "Russia": "RU", "Saudi Arabia": "SA", "Singapore": "SG",
    "South Korea": "KR", "Spain": "ES", "Turkey": "TR", "UAE": "AE",
    "UK": "GB", "United Kingdom": "GB", "USA": "US", "Vietnam": "VN",
}


def iso(country):
    """Two-letter code used as the flag badge. Windows Chromium does not render
    regional-indicator flag emoji, so the dashboard shows the code instead."""
    code = ISO2.get(country)
    if not code:
        print("    ! no ISO code for country '%s'" % country)
    return code or "??"


def num(value):
    """Ergast points come through as strings; keep ints as ints."""
    f = float(value)
    return int(f) if f == int(f) else f


def weekend_start(race):
    """Earliest dated session of the weekend, so cards can show a range."""
    dates = [race[k]["date"] for k in
             ("FirstPractice", "SecondPractice", "ThirdPractice",
              "SprintQualifying", "Sprint", "Qualifying")
             if isinstance(race.get(k), dict) and race[k].get("date")]
    return min(dates) if dates else race["date"]


def result_row(row):
    pos_text = row["positionText"]
    pos = int(pos_text) if pos_text.isdigit() else None
    millis = row.get("Time", {}).get("millis")
    return [
        row["Driver"]["driverId"],
        row["Constructor"]["constructorId"],
        pos,
        pos_text,
        int(row.get("grid", 0) or 0),
        num(row["points"]),
        row.get("status", ""),
        int(millis) if millis else None,
    ]


def build_season(raw):
    tables = raw["tables"]
    season = raw["season"]

    results = {r["round"]: r for r in tables["results"]["Races"]}
    quali = {r["round"]: r for r in tables["qualifying"]["Races"]}
    sprint = {r["round"]: r for r in tables["sprint"]["Races"]}

    teams = {}
    for c in tables["constructors"]["Constructors"]:
        teams[c["constructorId"]] = {
            "n": c["name"],
            "c": TEAM_COLOURS.get(c["constructorId"], FALLBACK_COLOUR),
            "nat": c.get("nationality", ""),
        }
        if c["constructorId"] not in TEAM_COLOURS:
            print("    ! no colour for constructor '%s' - using fallback" % c["constructorId"])

    drivers = {}
    for d in tables["drivers"]["Drivers"]:
        drivers[d["driverId"]] = {
            "c": d.get("code") or d["familyName"][:3].upper(),
            "g": d["givenName"],
            "f": d["familyName"],
            "n": d.get("permanentNumber", ""),
            "nat": d.get("nationality", ""),
            "t": None,  # filled from the driver's latest appearance
        }

    races, last_done = [], 0
    for r in tables["schedule"]["Races"]:
        rnd = r["round"]
        res = results.get(rnd)
        done = bool(res and res.get("Results"))
        loc = r["Circuit"]["Location"]
        entry = {
            "r": int(rnd),
            "name": r["raceName"],
            "cc": loc["country"],
            "iso": iso(loc["country"]),
            "circuit": r["Circuit"]["circuitName"],
            "loc": loc["locality"],
            "date": r["date"],
            "start": weekend_start(r),
            "sprint": "Sprint" in r,
            "done": done,
            "res": [result_row(x) for x in (res or {}).get("Results", [])],
            "qual": [[x["Driver"]["driverId"], int(x["position"])]
                     for x in quali.get(rnd, {}).get("QualifyingResults", [])],
            "spr": [result_row(x) for x in sprint.get(rnd, {}).get("SprintResults", [])],
        }
        if done:
            last_done = int(rnd)
            for row in entry["res"]:
                if row[0] in drivers:
                    drivers[row[0]]["t"] = row[1]
        races.append(entry)

    upcoming = [r["r"] for r in races if not r["done"]]

    # Drop drivers who never appeared - the season driver list includes
    # entrants who ended up not racing.
    seen = {row[0] for r in races for row in r["res"] + r["spr"]}
    seen |= {q[0] for r in races for q in r["qual"]}
    drivers = {k: v for k, v in drivers.items() if k in seen}

    payload = {
        "season": season,
        "teams": teams,
        "drivers": drivers,
        "races": races,
        "last": last_done,
        "next": upcoming[0] if upcoming else None,
    }
    verify(payload, tables)
    return payload


def verify(payload, tables):
    """Cross-check points summed from race+sprint results against the API's own
    standings. A mismatch means a post-race adjustment we are not modelling."""
    standings = tables["driverStandings"]["StandingsLists"]
    if not standings:
        return
    official_list = standings[-1]
    if int(official_list["round"]) != payload["last"]:
        print("    ! standings are for round %s but last result is round %s"
              % (official_list["round"], payload["last"]))
    official = {e["Driver"]["driverId"]: num(e["points"]) for e in official_list["DriverStandings"]}

    computed = {}
    for r in payload["races"]:
        if not r["done"]:
            continue
        for row in r["res"] + r["spr"]:
            computed[row[0]] = computed.get(row[0], 0) + row[5]

    bad = [(k, official[k], computed.get(k, 0))
           for k in official if abs(official[k] - computed.get(k, 0)) > 1e-6]
    if bad:
        print("    ! points mismatch vs API standings (%d driver(s)):" % len(bad))
        for k, o, c in bad[:8]:
            print("        %-16s official=%-6s computed=%s" % (k, o, c))
    else:
        print("    points reconcile with API standings for all %d drivers" % len(official))


def main():
    raws = sorted(glob.glob(os.path.join(DATA_DIR, "raw-*.json")))
    if not raws:
        # NOT "run fetch.py": the season data is pinned so that everybody's
        # numbers are identical, and re-fetching is the one way to lose that.
        # This only fires when the script is run from the wrong folder, so say
        # that instead of sending the reader off to break the guarantee.
        sys.exit("no data/raw-*.json found - run this from the course folder, "
                 "the one holding data/ (the season data ships with it)")

    seasons = {}
    for path in raws:
        with io.open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        print("building %s" % raw["season"])
        seasons[raw["season"]] = build_season(raw)

    # Say so plainly rather than raising FileNotFoundError. This script ships from
    # the `start` checkpoint while the template is the thing the HTML chapter
    # builds, so running it early is easy to do - and a participant who sees a
    # Python traceback reasonably concludes they have broken something. Every
    # other check in this file already exits with a sentence; this was the one
    # hole.
    template = os.path.join(HERE, "f1-dashboard-template.html")
    if not os.path.isfile(template):
        sys.exit("no f1-dashboard-template.html here yet - that is the file this "
                 "chapter asks you to write, and this script fills it in once it "
                 "exists")
    with io.open(template, encoding="utf-8") as fh:
        html = fh.read()

    data = json.dumps({"seasons": seasons}, separators=(",", ":"), ensure_ascii=False)
    built = datetime.datetime.now().strftime("%d %b %Y %H:%M")

    # str.replace, not re.sub - the payload is full of backslashes that re
    # would read as group references.
    for token, value in (("__SEASON_DATA__", data), ("__BUILT_AT__", built)):
        if token not in html:
            sys.exit("f1-dashboard-template.html is missing the %s placeholder" % token)
        html = html.replace(token, value)

    out = os.path.join(HERE, "f1-dashboard.html")
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    print("-> %s (%.0f KB, seasons: %s)"
          % (out, os.path.getsize(out) / 1024.0, ", ".join(sorted(seasons))))

    frag = os.path.join(HERE, "f1-dashboard-embed.html")
    with io.open(frag, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(fragment(html))
    print("-> %s (%.0f KB, the same page as a body fragment)"
          % (frag, os.path.getsize(frag) / 1024.0))


def fragment(html):
    """Same page as a body fragment, for embedding in another page.

    A host page supplies its own doctype/html/head/body,
    so those tags have to come out; the title, styles and markup carry over
    untouched, which keeps f1-dashboard.html the single source of truth."""
    def grab(tag):
        m = re.search(r"<%s\b[^>]*>.*?</%s>" % (tag, tag), html, re.S)
        if not m:
            sys.exit("f1-dashboard-template.html has no <%s> element" % tag)
        return m.group(0)

    body = re.search(r"<body[^>]*>(.*)</body>", html, re.S)
    if not body:
        sys.exit("f1-dashboard-template.html has no <body> element")
    return "\n".join([grab("title"), grab("style"), body.group(1).strip(), ""])


if __name__ == "__main__":
    main()
