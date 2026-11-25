# Ultimate Formula 1 Dashboard

A single self-contained `f1-dashboard.html` covering an F1 season across six sections —
Schedule, Results, Driver Standings, Constructor Standings, Drivers, Teams —
with a sidebar for navigation and filters for season and round.

Data comes from the [Jolpica API](https://jolpi.ca) (Ergast-compatible).
See [SPEC.md](SPEC.md) for the original brief.

## Rebuilding

```bash
python fetch.py 2026 2025    # pull raw season data into data/raw-<season>.json
python build.py              # render f1-dashboard.html from data/ + f1-dashboard-template.html
```

`fetch.py` needs network access; `build.py` does not. Open `f1-dashboard.html` directly
in a browser — no server required.

## How it is put together

| File            | Role                                                              |
| --------------- | ----------------------------------------------------------------- |
| `fetch.py`      | Pages through the API and caches raw JSON per season in `data/`    |
| `f1-dashboard-template.html` | The dashboard: markup, CSS, and all view logic                    |
| `build.py`      | Compacts the raw data and injects it into the template            |
| `f1-dashboard.html`    | Generated output — the shareable artefact                         |

### Snapshot, not live fetch

The season data is baked into `f1-dashboard.html` at build time rather than fetched
from the browser. The brief asks for one file you can open locally and share; a
shared file that calls a third-party API breaks the moment that API rate-limits,
moves, or goes down. The trade-off is that new results need a `fetch` + `build`.

Re-run both after each Grand Prix to bring the snapshot up to date.

### Facts baked in, views computed in the browser

`build.py` writes per-race facts only (results, qualifying, sprint). Standings,
season highlights, and the points grid are computed client-side from those facts
for whichever round you select, so the round filter genuinely re-derives the
championship "as of" that round instead of switching between pre-baked tables.

### Correctness check

`build.py` sums race and sprint points per driver and compares the totals with
the standings the API reports itself. Any post-race adjustment that the per-race
points do not explain gets printed as a warning at build time. Both 2025 and
2026 currently reconcile exactly.

## Power BI version

The same dashboard as a Power BI Project under `powerbi/`, with the semantic
model and the report as two separate, independently versioned items:

```
powerbi/
  Ultimate F1 Dashboard.pbip                 project entry point
  Ultimate F1 Dashboard.SemanticModel/       the model (TMDL)
  Ultimate F1 Dashboard.Report/              the report (PBIR) - holds no data
  data/*.csv                                 what the model imports
```

The report references the model by relative path (`definition.pbir`), so either
side can be replaced without touching the other.

### Rebuilding

```bash
python fetch.py 2026 2025    # pull raw season data (shared with the HTML build)
python export_csv.py         # flatten data/raw-*.json into powerbi/data/*.csv
python powerbi/build_report.py   # regenerate the six report pages (Desktop must be CLOSED)
```

Then open `powerbi/Ultimate F1 Dashboard.pbip` and hit **Refresh**. Set the
`Parameter_DataFolder` parameter to your own clone path — it is the only
machine-specific value in the model.

`export_csv.py` re-runs the same points reconciliation `build.py` does, and
refuses to write CSVs that disagree with the API's own standings.

### Model shape

A star schema at two fact grains. Race and sprint results are field-identical in
the API, so they share one fact table and the `Session` dimension separates them
— which makes championship points a single `SUM` rather than an addition across
tables. Qualifying has a different shape (segment times, no points) and stays
separate rather than leaving both halves sparse.

| Table | Role | Grain |
| --- | --- | --- |
| `Race` | dimension | one row per season + round |
| `Driver` | dimension | one row per driver, conformed across seasons |
| `Team` | dimension | one row per constructor |
| `Session` | dimension | two rows — Race, Sprint |
| `Calendar` | dimension | contiguous days, marked as the date table |
| `Session Result` | fact | one row per driver per points-scoring session |
| `Qualifying Result` | fact | one row per driver per qualifying |

Naming follows the in2Facts conventions: plain Title Case tables with no role
prefixes, measures on fact tables only, every physical fact column hidden, and
IBCS-style measure names with numbered display folders.

Two convention extensions were needed and are deliberate: `pts` as the unit for
championship points (they are a dimensionless score, not a count, so `#` would
be wrong), and `RoR` for round-over-round variance (the convention covers
`WoW`/`MoM`/`QoQ`/`YoY` only, and the championship's period is the round).

The Season slicer **preselects the newest season in the data**, read from
`Race.csv` at build time, so the report opens on the current championship the way
the HTML dashboard does and adding 2027 needs no code change.

Clearing that selection shows both seasons at once, which is legitimate but makes
round numbers appear twice — 2025 round 1 and 2026 round 1 are different races.
Every affected visual therefore names the season regardless: the winners and pole
tables carry a Season column, the points grid nests Round under Season, and the
schedule cards are keyed by `Race Key` (`2026-01`), which encodes it.

Both slicers live in the left rail under a `FILTERS` eyebrow, so navigation and
filtering read as two labelled zones rather than one stack.

### Gotchas worth knowing

- **`Calendar` derives its span from `Race`.** Opening the project before any
  refresh evaluates it against an empty model and yields a nonsense one-year
  range. A full refresh fixes it — refresh the whole model, not single tables.
- **`Session` and `Calendar` need quoting in DAX** (`'Session'`), as both
  collide with DAX keywords.
- **A `VAR` may not share a name with a column on the measure's host table.**
  A variable named `Status` in a `Session Result` measure compiles to
  `SYNTAXERROR`, because that table has a `Status` column.
- **`Wins (#)` respects the `Session` filter**, so it means sprint wins under
  `Session = Sprint`. Pages that want Grand Prix wins pin `Session = Race` in
  the visual filter. Unfiltered it counts both, which is why it reads higher
  than the API's `wins` field.
- **PBIR has no master page**, so the sidebar is emitted onto every page by
  `build_report.py`. Change it there, not in the JSON.
- **SVG measures must be left unencoded.** `data:image/svg+xml;utf8,` followed
  by raw markup with plain `#` hex colours is what renders; percent-encoding
  `<`, `>` and spaces produces blank cells even though the SVG is valid XML.
  The measure also needs `dataCategory: ImageUrl`.
- **`imageHeight`/`imageWidth` belong on the table's `grid` object**, not
  `values`. Under `values` they are silently ignored. Table totals are
  `total.totals`, not `total.show`.
- **A table of dimension columns with no measure returns the full cross join.**
  The race-winners table projects Round, Race Name, Driver and Team — three
  different tables — filtered to `Position = 1`. Without a measure that filter
  does not constrain the result at all: 552 rows (every driver against every
  round) instead of 12. Adding one measure forces the fact-table join and the
  row count collapses to the truth. The measure must come from the *same* fact
  the filter is on: the poles table filters `Qualifying Result`, so it needs
  `Poles (#)`; adding `Average Finish (pos)` from `Session Result` re-expands it
  to 233. The measure columns in those two tables are load-bearing — do not
  remove them for looking redundant.
- **Show a driver's team via the `Team (txt)` measure, not the `Team` column.**
  Liam Lawson changed team mid-2026, so grouping by Driver × Team gives him two
  rows of the championship — 24 rows for 23 drivers. The measure collapses that
  back to one row per driver.
- **A slicer over a numeric column needs `data.mode = 'Basic'`.** `Season` and
  `Round` are `int64`, and Power BI defaults a slicer on a numeric column to the
  range slider. In a short box that shows no items at all, so the slicer reads as
  broken rather than misconfigured. Also: `general.orientation` is `0` for a
  vertical list — there is no orientation `2`. And give it room; a list needs
  roughly 40px of chrome plus a row per item.
- **A slicer's selection lives on `general.filter`, not in `filterConfig`.**
  The property nests twice — `general.properties.filter.filter` holds the
  `Version`/`From`/`Where` object. One level less and Desktop ignores it in
  silence, which looks identical to no selection. A categorical filter in
  `filterConfig` is the *Filters on this visual* well: it restricts which values
  the slicer lists and selects nothing, so no filter ever reaches the page.
- **Small rail text fails on contrast, not size.** Measuring inked pixels in a
  screenshot settled this: the `FILTERS` eyebrow at 7pt/`#8A93A2` put 29 ink over
  3 pixel rows, and going to 9pt only reached 46 over 5 - still unreadable.
  Recolouring to `#5A6472` at the same 9pt gave 100 over 9, against 152 over 11
  for an 11pt nav label. Hierarchy in the rail therefore comes from size, with
  every label sharing one ink. A textbox run also needs ~26px of box height, and
  a slicer draws its title hard against its own top edge, so an eyebrow above one
  needs a real gap or the two title-weight rows collide.
- **Slicers opt out of the theme's border and background.** The theme rounds and
  outlines every visual, which boxed each slicer in against the white rail for no
  reason. `visualContainerObjects.border.show = false` on the slicer clears it.
- **A seamless canvas needs two changes together, and neither works alone.**
  Set the page background to **100% transparency** - that removes the drop
  shadow, because an opaque canvas is drawn as a page floating on the wallpaper
  and keeps its shadow however well the colours match. On its own that makes
  Desktop draw a dashed page outline instead, so also set *Second-level
  elements* (`foregroundNeutralSecondary` in the legacy theme schema,
  `secondLevelElements` in the modern one) to the wallpaper's hex, which
  suppresses the outline. Measured before: a 1px line plus a ~15px `#DFE0E2`
  gradient down the whole edge. After: nothing.

  Consequence: with the canvas transparent the ground renders white and the
  wallpaper colour no longer shows, so anything relying on a tinted ground needs
  rethinking - the rail carries its own colour for this reason.

  That token is otherwise a text colour, so anything inheriting it turns
  invisible. Only two places in this report did: slicer `items`, and matrix
  `values`. Both now pin `fontColor` explicitly. Check for new inheritors before
  adding visuals - a visual that sets only `fontSize` on a text object is one.
- **Content runs to the canvas edges.** With no page boundary there is nothing
  for a margin to sit against, so tables and matrices extend to x=1920 and
  y=1080 rather than stopping 24-32px short.
- **Visual titles carry a background from the theme.** The `*`/`*` title style
  set `background: #FFFFFF`, which put a white block behind every title -
  invisible on a table, obvious behind a slicer title on the rail. Dropping the
  property leaves titles transparent.
- **`shape` visuals paint nothing here.** Neither the shape's own `fill` (with
  or without the `{"id": "default"}` state selector) nor its container
  background reaches the screen; a whole-image colour search finds the requested
  tint nowhere. This hid for a long time because the rail was white, and a shape
  that renders nothing looks exactly like a white one. The sidebar ground and
  its hairline rule are built on textboxes with a container background instead -
  textboxes render reliably, as every label in the rail proves.
- **There is no `columnHeaders.show` for `tableEx`.** A table always shows its
  headers; Desktop strips the property on save. A blank `displayName` on the
  projection is what keeps a card table's header quiet.
- **Desktop rewrites `visualContainer` to its own schema version on save**
  (2.11.0 here) and normalises `z`/`tabOrder`. If a diff shows that version
  changing, update `V_SCHEMA` in `build_report.py` rather than reverting it —
  and note that a version detected from an older project in the same repo can be
  stale.
- **Group the schedule cards by `Race Key`, never by `Round`.** Round repeats
  across seasons, so with two seasons in context `SELECTEDVALUE` inside the card
  measure goes blank for every round whose race name differs between them —
  which looks like half the cards silently failing to render. Rounds 1-3 hid the
  bug because Australia, China and Japan open both the 2025 and 2026 calendars.
- **Shape `fillColor` is state-scoped** and needs `selector: {id: "default"}`.
  Without it Power BI silently falls back to theme data colour 0.
- **If a double-click on a `.pbip` opens a blank *Untitled* report**, close it
  and use File → Open inside Desktop, or pass the path to `pbidesktop.exe`.
  Desktop 2.159 (Store) declares `.pbip` and a double-click normally works;
  `check_setup.py` reads the package manifest and says which you have. Either
  way the Store build is slow to cold-start — give it a minute before assuming
  it failed.

## Known gaps

- **No driver photos or livery images.** The API carries no images, and
  embedding remote ones would break both the single-file promise and offline
  use. Driver cards use a team-coloured code badge; team cards use a livery band
  drawn from the team colour.
- **Team colours are hand-maintained** in `TEAM_COLOURS` at the top of
  `build.py`, since the API does not supply them. The 2026 values are
  best-guess brand colours — correct any hex there and re-run `build.py`.
- **Country is shown as an ISO code badge, not a flag emoji.** Windows Chromium
  renders regional-indicator pairs as bare letters, which reads as a bug.
- **Sprint pole is derived** from grid position 1 in the sprint result, as the
  API exposes no separate sprint-qualifying classification.
- **Upstream data oddity:** the 2026 calendar lists round 16 as "Bahrain Grand
  Prix in Malaysia" at Sepang. That is what the API returns; it is rendered
  as-is rather than silently corrected.
