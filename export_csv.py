"""Flatten data/raw-<season>.json into tidy CSVs for the Power BI semantic model.

The semantic model imports these CSVs rather than parsing the Ergast-shaped
JSON in Power Query: the nested payload needs a wall of Table.ExpandRecordColumn
per table, and the flattening logic already lives here in reviewable Python that
self-checks its own output.

    python fetch.py 2026 2025     # refresh the API snapshot
    python export_csv.py          # rebuild the CSVs
                                  # then Refresh in Power BI Desktop

One CSV per model table, each carrying every season it found, so adding a season
means re-running this script and refreshing - the model itself never changes.

Written as plain UTF-8 with no BOM and \\n line endings: every Csv.Document call
in the model passes Encoding=65001, and a BOM would otherwise end up glued to
the first column name.
"""
import csv
import glob
import io
import json
import os
import re
import sys

import build  # reuse the verified helpers rather than re-deriving them

OUT_DIR = os.path.join(build.HERE, "powerbi", "data")

# Race and Sprint results are field-identical in the API, so they load into one
# fact table and this dimension is what tells them apart.
SESSIONS = [
    {"Session Key": "RACE", "Session": "Race", "Session Order": 1},
    {"Session Key": "SPRINT", "Session": "Sprint", "Session Order": 2},
]


def race_key(season, rnd):
    """Stable surrogate key. Round alone is not unique across seasons."""
    return "%s-%02d" % (season, int(rnd))


def lap_time_ms(text):
    """'1:29.525' or '29.525' -> milliseconds. Blank/absent -> None."""
    if not text:
        return None
    m = re.match(r"^(?:(\d+):)?(\d+)\.(\d+)$", text.strip())
    if not m:
        print("    ! unparsed lap time '%s'" % text)
        return None
    minutes, seconds, frac = m.group(1) or "0", m.group(2), m.group(3)
    return int(minutes) * 60000 + int(seconds) * 1000 + int(frac.ljust(3, "0")[:3])


def write_csv(name, fieldnames, rows):
    path = os.path.join(OUT_DIR, name)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("    %-24s %5d rows" % (name, len(rows)))
    return len(rows)


def collect(raws):
    """Build every table's rows from all season payloads at once."""
    races, results, quali = [], [], []
    drivers, teams = {}, {}
    seen_drivers, seen_teams = set(), set()

    for raw in raws:
        season = raw["season"]
        tables = raw["tables"]
        by_round = {
            "results": {r["round"]: r for r in tables["results"]["Races"]},
            "sprint": {r["round"]: r for r in tables["sprint"]["Races"]},
            "qualifying": {r["round"]: r for r in tables["qualifying"]["Races"]},
        }

        # Dimension rows. A driver or team recurs across seasons; the later
        # season wins so a renamed team keeps its current name.
        for d in tables["drivers"]["Drivers"]:
            drivers[d["driverId"]] = {
                "Driver Key": d["driverId"],
                "Driver Code": d.get("code") or d["familyName"][:3].upper(),
                "Given Name": d["givenName"],
                "Family Name": d["familyName"],
                "Driver Name": "%s %s" % (d["givenName"], d["familyName"]),
                "Permanent Number": d.get("permanentNumber", ""),
                "Nationality": d.get("nationality", ""),
                "Date Of Birth": d.get("dateOfBirth", ""),
            }
        for c in tables["constructors"]["Constructors"]:
            cid = c["constructorId"]
            if cid not in build.TEAM_COLOURS:
                print("    ! no colour for constructor '%s' - using fallback" % cid)
            teams[cid] = {
                "Team Key": cid,
                "Team Name": c["name"],
                "Nationality": c.get("nationality", ""),
                "Team Colour": build.TEAM_COLOURS.get(cid, build.FALLBACK_COLOUR),
            }

        for r in tables["schedule"]["Races"]:
            rnd = r["round"]
            key = race_key(season, rnd)
            res = by_round["results"].get(rnd, {}).get("Results", [])
            spr = by_round["sprint"].get(rnd, {}).get("SprintResults", [])
            qua = by_round["qualifying"].get(rnd, {}).get("QualifyingResults", [])
            loc = r["Circuit"]["Location"]

            races.append({
                "Race Key": key,
                "Season": int(season),
                "Round": int(rnd),
                "Race Name": r["raceName"],
                "Circuit": r["Circuit"]["circuitName"],
                "Circuit Key": r["Circuit"]["circuitId"],
                "Locality": loc["locality"],
                "Country": loc["country"],
                "ISO Code": build.iso(loc["country"]),
                "Latitude": loc.get("lat", ""),
                "Longitude": loc.get("long", ""),
                "Race Date": r["date"],
                "Weekend Start": build.weekend_start(r),
                "Has Sprint": "TRUE" if "Sprint" in r else "FALSE",
                "Is Completed": "TRUE" if res else "FALSE",
            })

            for session_key, rows in (("RACE", res), ("SPRINT", spr)):
                for row in rows:
                    pos_text = row["positionText"]
                    millis = row.get("Time", {}).get("millis")
                    seen_drivers.add(row["Driver"]["driverId"])
                    seen_teams.add(row["Constructor"]["constructorId"])
                    results.append({
                        "Race Key": key,
                        "Session Key": session_key,
                        "Driver Key": row["Driver"]["driverId"],
                        "Team Key": row["Constructor"]["constructorId"],
                        "Position": int(pos_text) if pos_text.isdigit() else "",
                        "Position Text": pos_text,
                        "Grid Position": int(row.get("grid", 0) or 0),
                        "Points": build.num(row["points"]),
                        "Status": row.get("status", ""),
                        "Race Time": int(millis) if millis else "",
                        "Laps": int(row.get("laps", 0) or 0),
                    })

            for row in qua:
                seen_drivers.add(row["Driver"]["driverId"])
                seen_teams.add(row["Constructor"]["constructorId"])
                quali.append({
                    "Race Key": key,
                    "Driver Key": row["Driver"]["driverId"],
                    "Team Key": row["Constructor"]["constructorId"],
                    "Qualifying Position": int(row["position"]),
                    "Q1": lap_time_ms(row.get("Q1")),
                    "Q2": lap_time_ms(row.get("Q2")),
                    "Q3": lap_time_ms(row.get("Q3")),
                })

    # The API's season driver list includes entrants who never started, and its
    # constructor list can carry a team with no classified result yet.
    dropped = sorted(set(drivers) - seen_drivers)
    if dropped:
        print("    dropped %d driver(s) with no appearance: %s"
              % (len(dropped), ", ".join(dropped)))
    drivers = {k: v for k, v in drivers.items() if k in seen_drivers}
    teams = {k: v for k, v in teams.items() if k in seen_teams}

    races.sort(key=lambda r: (r["Season"], r["Round"]))
    return races, drivers, teams, results, quali


def verify(raws, results):
    """Re-run build.py's reconciliation against the rows about to be written:
    points summed from race plus sprint results must match the API's own driver
    standings. Runs before anything reaches disk, so a failure costs nothing."""
    ok = True
    for raw in raws:
        season = raw["season"]
        lists = raw["tables"]["driverStandings"]["StandingsLists"]
        if not lists:
            continue
        official = {e["Driver"]["driverId"]: build.num(e["points"])
                    for e in lists[-1]["DriverStandings"]}
        keys = {race_key(season, r) for r in
                [x["round"] for x in raw["tables"]["schedule"]["Races"]]}

        computed = {}
        for row in results:
            if row["Race Key"] in keys:
                computed[row["Driver Key"]] = computed.get(row["Driver Key"], 0) + row["Points"]

        bad = [(k, official[k], computed.get(k, 0)) for k in official
               if abs(official[k] - computed.get(k, 0)) > 1e-6]
        if bad:
            ok = False
            print("    ! %s: points mismatch vs API standings (%d driver(s))"
                  % (season, len(bad)))
            for k, o, c in bad[:8]:
                print("        %-16s official=%-6s csv=%s" % (k, o, c))
        else:
            print("    %s: points reconcile with API standings for all %d drivers"
                  % (season, len(official)))
    return ok


def main():
    paths = sorted(glob.glob(os.path.join(build.DATA_DIR, "raw-*.json")))
    if not paths:
        sys.exit("no data/raw-<season>.json found - run fetch.py first")

    raws = [json.load(io.open(p, encoding="utf-8")) for p in paths]
    seasons = ", ".join(r["season"] for r in raws)
    print("exporting seasons: %s" % seasons)

    races, drivers, teams, results, quali = collect(raws)

    # Verify BEFORE writing anything. The reconciliation runs against the rows
    # held in memory - the same rows that are about to be written - so there is
    # no reason to touch the disk first. Writing first and complaining second
    # meant a failed export replaced good CSVs with bad ones and then told you
    # they were wrong, which is the worst of both: the check caught the problem
    # and the damage was already done.
    print("verifying:")
    if not verify(raws, results):
        sys.exit("export aborted: nothing was written, the CSVs on disk are unchanged")

    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)

    write_csv("Race.csv", list(races[0].keys()), races)
    write_csv("Driver.csv", list(next(iter(drivers.values())).keys()),
              [drivers[k] for k in sorted(drivers)])
    write_csv("Team.csv", list(next(iter(teams.values())).keys()),
              [teams[k] for k in sorted(teams)])
    write_csv("Session.csv", list(SESSIONS[0].keys()), SESSIONS)
    write_csv("Session Result.csv", list(results[0].keys()), results)
    write_csv("Qualifying Result.csv", list(quali[0].keys()), quali)

    print("-> %s" % OUT_DIR)


if __name__ == "__main__":
    main()
