# Lessons learned

Thirty-four findings from building this project: a PBIP semantic model plus a
hand-authored PBIR report. Each is written as a rule, so it can be lifted into a
`SKILL.md` without re-deriving it.

Everything here was confirmed against a rendering Power BI Desktop or a live DAX
query. None of it is inferred from documentation.

**Scope:** Power BI Desktop 2.156 (Microsoft Store build), `visualContainer`
schema 2.11.0. Some findings may be build-specific — the shape-visual one in
particular.

**Re-confirmed on 2.157.1354.0** (Store build) by a full run of the course on
that version: the model loaded, all six pages rendered, the card grid behaved as
described, and no finding here contradicted what the build did. The shape-visual
caveat above is untested on 2.157 and stays as written. A build newer than this
is unverified — if something here disagrees with what you see, believe the
screen and say so, because that is how this file gets its next entry.

Two findings came from Alain rather than from inspection, and are marked.

---

## The rule that would have saved the most time

**When hand-authored PBIR JSON does not render, stop guessing and get one working
example built in Desktop's UI.**

PBIR fails silently. A wrong property name produces a blank visual, never an
error, so every failure below presented identically. Four consecutive blank card
visuals turned out to be two independent problems masking each other, and neither
was findable by inspection.

It got worse before it got better: a card was copied from another project in this
repo as a reference — and **that card bound its image to a measure that no longer
existed in its own model**. It had never rendered either. Hours went into tuning
property values borrowed from something broken.

- Verify a reference's own dependencies resolve before trusting it.
- Commit the hand-built example verbatim as its own commit *before* regenerating
  over it, so the working shape stays in history and can be diffed.

---

## Report JSON — field wells, selectors, objects

> Target: `pbir-report-builder`

### Field well names are not the format-pane labels
A card visual with a category renders nothing when the well is called
`Categories`. The well is **`Rows`**; "Categories" is only the UI label.

**Rule:** never infer a `queryState` well name from the format pane. Read it from
a visual built in Desktop.

### The presence or absence of a selector is semantic
`label.show = false` works. The identical `value.show = false` is ignored.

- `label` needs `selector: {id: "default"}`
- `value` must have **no selector at all**

**Rule:** copy the selector shape per property. Do not apply one helper uniformly
across an objects block.

### A per-item binding needs the dataViewWildcard selector
An image bound to a measure lands on one tile, or none.

**Rule:** any measure-driven per-item property (image, colour) needs

```json
"selector": {
  "data": [{ "dataViewWildcard": { "matchingOption": 1 } }],
  "id": "default",
  "hierarchyMatching": 1
}
```

### Only the Button Slicer renders an SVG measure as the tile
*(Found by Alain.)* The new Card visual will not display an SVG measure as its
image under any property combination — its image binding expects a static
resource.

**Rule:** for a grid of SVG cards use `advancedSlicerVisual`, binding
`objects.image.image` straight to the measure. Side effect: it is a slicer, so
clicking a tile filters the page.

### A slicer's selection is not in filterConfig
`filterConfig` is the "Filters on this visual" well — it restricts what the
slicer lists and selects nothing, so no filter reaches the page.

**Rule:** selection goes in `objects.general.properties.filter.filter`. The
doubled `filter` key is required; one level less is ignored in silence.

### A slicer over a numeric column defaults to the range slider
`int64` columns get the between-slider, which in a short box shows no items and
no handles — so it reads as broken rather than misconfigured.

**Rule:** set `objects.data.mode = 'Basic'` for a list. `general.orientation` is
`0` for vertical; there is no orientation `2`.

### Slicer height is arithmetic
**Rule:** `height >= 36px title block + 23px per item + 10px padding`. Undershoot
and Power BI silently adds a scrollbar.

### A visual only sorts by something it queries
`sortDefinition` naming a measure that is in no well is ignored.

**Rule:** project the sort measure into `Tooltips` purely to make it sortable,
then reference it from `sortDefinition`.

### Without sortDefinition a table falls back to its first column
A standings table showed positions reading 15, 1, 11, 16.

**Rule:** give every table an explicit `sortDefinition`. Nothing sensible is
inferred from a rank column being present.

### Properties that do not exist on tableEx
- There is no `columnHeaders.show` — a table always shows headers. Use a blank
  `displayName` on the projection instead.
- Totals are `total.totals`, not `total.show`.
- Image sizing is `grid.imageHeight` / `grid.imageWidth`, never under `values`.

### Shape visuals paint nothing
Neither a shape's `fill` nor its container background reached the screen in this
build. A whole-image colour search found the requested tint nowhere. It hid for
days because the rail was white — a shape that renders nothing looks exactly like
a white one.

**Rule:** build grounds and rules from **textboxes with a container background**.
If a shape is unavoidable, `fillColor` is state-scoped and needs
`selector: {id: "default"}` or it falls back to theme data colour 0.

### Visual titles carry a background from the theme
The `*`/`*` title style set `background: #FFFFFF`, putting a white block behind
every title — invisible on a table, obvious behind a slicer title on a rail.

**Rule:** drop `background` from the global title style.

### Desktop is a free validator
**Rule:** open, save, then `git diff`. Anything Desktop *removed* was invalid. It
also rewrites `$schema` to its own version and normalises `z`/`tabOrder` — follow
its version rather than reverting, and distrust a version detected from an older
project in the same repo.

### cardVisual projections omit "active"
Every other visual type here carries `"active": true` on projections. A
`cardVisual` does not.

**Rule:** do not apply a projection helper uniformly across visual types.

### PBIR has no master page
**Rule:** shared chrome must be emitted onto every page by the generator.

### Grid geometry differs per visual type
An invented `layout` object with `autoGrid`/`maxTiles` renders as a single
column.

- Button Slicer: `objects.layout` with **both** `columnCount` and `rowCount`
- Card: `objects.smallMultiplesLayout` with `orientation` and `rowCount`,
  columns derived

**Rule:** never carry a grid object across visual types.

---

## Theme tokens

> Target: `pbir-report-builder`

### "Second-level elements" decides whether cards render
*(Diagnosed by Alain.)* The token had been set to the wallpaper colour to
suppress a page outline. Every card then painted `#F4F6F9` on a near-white
ground — including a verbatim copy of a card that renders elsewhere.

**Rule:** `foregroundNeutralSecondary` (legacy) / `secondLevelElements` (modern)
must stay dark enough to render. Audit every inheriting visual before pointing it
anywhere near a background colour.

### An inheritor audit goes stale the moment a visual type is added
An audit found exactly two inheritors — slicer `items` and matrix `values` — and
both were pinned. A card visual added later inherited the token afresh and
disappeared.

**Rule:** a visual that sets only `fontSize` on a text object is an inheritor.
Re-audit whenever a new visual type enters the report, or pin `fontColor`
everywhere as policy.

### A seamless canvas needs two changes, and neither works alone
Measured before: a 1px line plus a ~15px `#DFE0E2` shadow gradient down the
canvas edge. Matching canvas colour to wallpaper does not remove it — an opaque
canvas is drawn as a page *floating* on the wallpaper and keeps its shadow
however well the colours match. Transparency alone makes Desktop draw a dashed
outline instead.

**Rule:**
1. Page background → **100% transparency** (removes the shadow)
2. Second-level elements → the wallpaper hex (suppresses the dashed outline)

Consequence: the ground then renders white and the wallpaper colour no longer
shows, so anything relying on a tinted ground must carry its own colour.

### Small text fails on contrast long before it fails on size
Measured inked pixels rather than eyeballing:

| Variant | Ink | Inked rows |
|---|---:|---:|
| 7pt `#8A93A2` | 29 | 3 |
| 9pt `#8A93A2` | 46 | 5 |
| **9pt `#5A6472`** | **100** | **9** |
| 11pt nav label (reference) | 152 | 11 |

**Rule:** fix contrast first. Build hierarchy from size, with one ink.

---

## DAX — filter direction and the blanks it produces

> Target: `power-bi-dax`

### A dimension is not filtered by filtering the fact
Three separate bugs in this build shared this root cause. With only `Driver` in
context, `Team` stays unfiltered — all twelve teams visible, so `SELECTEDVALUE`
returns blank. Filters flow dimension → fact, never back. The symptom is always a
silent blank.

**Rule:** three working shapes —

```dax
CALCULATETABLE(VALUES('Dim'[Col]), 'Fact')       -- pass the fact in
MAXX(FILTER('Fact', ...), RELATED('Dim'[Col]))   -- iterate the fact
-- or: resolve the key on the fact, then LOOKUPVALUE on the dimension
```

### Prefer a key lookup over table-filter propagation
A fallback branch returned blank with provably correct inputs (`N=2`,
`LastKey="2026-12"`). It relied on a table filter reaching the dimension. Only a
mid-season team switcher ever reached that branch, so it went unnoticed for the
whole build.

**Rule:** read the foreign key from the fact, then `LOOKUPVALUE` the attribute.
Unambiguous, and independent of propagation.

### Dimension columns with no measure return the full cross join
A table filtered to `Position = 1` returned **552 rows instead of 12** — every
driver against every round. With only dimension columns projected, nothing forces
the fact-table join, so the filter does not constrain the result at all.

**Rule:** add a measure **from the same fact the filter is on**. A measure from a
different fact re-expands it — the poles table filtered `Qualifying Result` and
needed `Poles (#)`; adding a `Session Result` measure took it back to 233 rows.
Those measure columns are load-bearing, not decorative.

### A VAR may not share a name with a column on the host table
A variable named `Status` in a measure whose host table has a `Status` column
compiles to `SYNTAXERROR`. The error does not point at the collision.

### SVG measures must be left unencoded
`data:image/svg+xml;utf8,` followed by raw markup with plain `#` hex. Percent-
encoding `<`, `>` and spaces produces blank cells even though the SVG is valid
XML. The measure also needs `dataCategory: ImageUrl`.

### Guard a card measure on having data in context
Otherwise entities that exist in the dimension but have no rows this season
render as empty tiles.

```dax
IF(NOT ISBLANK(Key) && [Distinct Races (#)] > 0, ...)
```

A blank measure drops the tile entirely.

---

## Modelling

> Target: `power-bi-modeling`

### Group by a composite key, never by a repeating natural key
Grouping by `Round`, which repeats across seasons, left half a card grid silently
blank: `SELECTEDVALUE` inside the card measure goes blank wherever two seasons
disagree. Rounds 1–3 masked it, because the same three countries open both
calendars.

**Rule:** group by the surrogate that encodes the partition (`Race Key` =
`2026-01`). Test with more than one partition loaded.

### Table names that collide with DAX keywords need quoting
`'Session'` and `'Calendar'` must always be quoted. Worth weighing at naming
time, not discovery time.

### A calculated table deriving its span from another table is empty before first refresh
A calendar derived from `Race` shows a nonsense one-year range on first open.

**Rule:** refresh the **whole model**, not single tables, before judging it.

---

## TMDL, PBIP and the Desktop loop

> Target: `power-bi-deployment`, `power-bi-diagnostics`

### TMDL comment syntax is narrow
- Object descriptions are `///` comments **above** the object — never a
  `description:` property
- There is no `//` plain comment
- Objects with no Description in the object model (relationships) accept no
  comment at all
- Indentation is tabs

### Connect to a PBIP folder to validate TMDL without Desktop
The Power BI Modeling MCP's `ConnectFolder` parses a `*.SemanticModel` directory
and reports the exact file, line and reason. Far faster than a Desktop round-trip
for syntax work.

Note: `pbi-cli` needs a **running** Desktop and cannot author a project from
nothing.

### A double-click on a .pbip can open a blank Untitled report
On 2.156 (Store), double-clicking a `.pbip`, or passing it to a launcher, opened
a blank Untitled report — silently. On 2.159 (Store) a double-click opens the
project: the package manifest declares `.pbip` as a file type. `assoc .pbip`
proves nothing either way; it is just as blank for `.pbix`, because it cannot
see a packaged app's associations. Read the manifest
(`Get-AppxPackageManifest`), as `check_setup.py` now does.

**Rule:** if it opens blank, pass the path to `pbidesktop.exe` directly, or use
File → Open. Do not tell participants the association is missing without
checking. Cold start is slow; give it a minute before concluding it failed.

### Close Desktop before regenerating, and watch the rmtree
`WinError 32` means the file is locked. A generator that rebuilds pages from
scratch will delete hand-built work — guard it with a clear error, and commit any
hand-built reference before running it.

### Desktop writes UI state back into the report definition
An unexplained `filterConfig` and `general.filter` appeared in a card grid after
merely opening the file: the grid is a slicer, and a click on a tile became a
persisted selection. Desktop also rewrites `activePageName`.

**Rule:** diff **semantically** before committing after a Desktop session —
compare parsed JSON, not text, since key reordering makes almost every file look
changed.

### Gitignore .pbi/ with an unanchored pattern
`*.Report/.pbi/` never matches, because `*` does not cross a path separator. Use
a bare `.pbi/`.

---

## Method — how these were actually found

### Measure pixels instead of trusting your eyes
Two findings came only from counting pixels in a screenshot: the small-text
contrast problem, and confirming the canvas shadow was gone. Screenshots are
downscaled and antialiased — at that scale a 2pt size change and a colour change
look identical.

**Rule:** count inked pixels per row over a fixed region, or search the whole
image for a specific hex, and A/B the same region across two builds. It turns
"looks about the same" into a number.

### Ship two variants when one look settles both
With a slow rebuild-and-reopen loop, put the borrowed values on one page and the
intended values on another. One screenshot answers both.

### Isolate on a scratch page, not on the real pages
Three variants side by side on a throwaway page kept six working pages intact —
and proved the simplest possible case also failed, which is what redirected the
search.

### Verify a reference before copying from it
Every `ImageUrl` object in the reference project was a *column* feeding a table,
never a measure on a card — and the one card that looked authoritative pointed at
a measure that no longer existed.

### Never capture the screen without confirming the foreground window
A screenshot taken while the user had switched applications captured an unrelated
document. Compare `GetForegroundWindow()` against the target handle and abort if
it does not match.
