"""Fetch a season of F1 data from the Jolpica API into data/raw-<season>.json.

The API silently clamps ?limit= to 100, so every list endpoint has to be paged
with ?offset= until MRData.total is covered.

    python fetch.py 2026 2025
"""
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = "https://api.jolpi.ca/ergast/f1"
PAGE = 100
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# endpoint -> (table key, row-list key inside each table entry)
# A None row key means the table's own list is the payload and needs no merging.
ENDPOINTS = {
    "results": ("RaceTable", "Results"),
    "qualifying": ("RaceTable", "QualifyingResults"),
    "sprint": ("RaceTable", "SprintResults"),
    "driverStandings": ("StandingsTable", None),
    "constructorStandings": ("StandingsTable", None),
    "drivers": ("DriverTable", None),
    "constructors": ("ConstructorTable", None),
    "": ("RaceTable", None),  # the season's race schedule
}


def get(url, attempts=4):
    for n in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ultimate-f1-dashboard/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            if n == attempts - 1:
                raise
            wait = 2 ** n
            print("    retry in %ds (%s)" % (wait, exc))
            time.sleep(wait)


def list_key(table):
    """The one list inside a *Table payload (Races, StandingsLists, Drivers, ...)."""
    return next(k for k, v in table.items() if isinstance(v, list))


def fetch_all(season, endpoint):
    """Page through an endpoint and return the fully merged *Table payload."""
    table_key, row_key = ENDPOINTS[endpoint]
    path = "%s/%s" % (season, endpoint) if endpoint else str(season)
    merged, offset, total = None, 0, None

    while total is None or offset < total:
        url = "%s/%s.json?limit=%d&offset=%d" % (BASE, path, PAGE, offset)
        data = get(url)["MRData"]
        total = int(data["total"])
        table = data[table_key]

        if merged is None:
            merged = table
        else:
            key = list_key(table)
            existing = merged[key]
            for entry in table[key]:
                # Race-scoped endpoints split one round across pages: merge the
                # inner row list instead of appending a duplicate round.
                prev = existing[-1] if existing else None
                if row_key and prev and prev.get("round") == entry.get("round"):
                    prev[row_key].extend(entry.get(row_key, []))
                else:
                    existing.append(entry)

        offset += PAGE

    print("    %-22s %s rows" % (endpoint or "(schedule)", total))
    return merged


def fetch_season(season):
    print("season %s" % season)
    raw = {"season": str(season), "tables": {}}
    for endpoint in ENDPOINTS:
        raw["tables"][endpoint or "schedule"] = fetch_all(season, endpoint)
    return raw


def main(seasons):
    os.makedirs(DATA_DIR, exist_ok=True)
    for season in seasons:
        raw = fetch_season(season)
        out = os.path.join(DATA_DIR, "raw-%s.json" % season)
        with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(raw, fh, indent=1, sort_keys=True)
        print("  -> %s (%.0f KB)" % (out, os.path.getsize(out) / 1024.0))


if __name__ == "__main__":
    main(sys.argv[1:] or ["2026"])
