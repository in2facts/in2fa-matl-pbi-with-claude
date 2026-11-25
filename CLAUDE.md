# Ultimate F1 Dashboard — training repository

This is the working folder for a one-day in2Facts course. The person at this
prompt is learning to **direct** an agent and to check its work. Producing the
right answer quickly is worth less here than producing an answer they can verify.

## What is in here

- `SPEC.md` — the brief for the HTML dashboard built in chapter 03.
- `data/raw-*.json` — the season data, **pinned**. Do not re-fetch it. Every
  exercise depends on the numbers being identical for everybody, and `fetch.py`
  exists to show how they were obtained, not to be run again.
- `scripts/tmdl_lint.py` and `scripts/pbir_lint.py` — the checks each chapter
  ends at. They are the pass marks, not advisory.
- `.claude/skills/` — seven Power BI skills, including a PBIR report builder with
  JSON templates and the Microsoft schemas. Consult them before authoring TMDL or
  report JSON.

## How to work here

**Run the check; do not predict it.** A clean run is a claim you can stand behind.
Reasoning about whether something will work is not, and this course exists because
the difference is invisible.

Which check depends on what exists yet. Run the one that applies and skip the
others — a checkpoint early in the course has no Power BI project at all, and the
linters correctly answer `no .pbip found` and exit 2 there. That is not a failure
to investigate or fix; it means the thing being checked has not been built.

| Once this exists | The check is | It answers |
| --- | --- | --- |
| `export_csv.py` | `python export_csv.py` | do the totals reconcile |
| a `.pbip` with a semantic model | `python scripts/tmdl_lint.py` | do the names, display folders and measure placement follow the conventions |
| the same `.pbip` | the Modeling MCP's `ConnectFolder` on the `.SemanticModel` folder | would Power BI actually load this |
| a `.pbip` with report pages | `python scripts/pbir_lint.py` | are the field wells real, are the bindings resolvable, and does the page belong to the same report as the others |

The two model checks are not alternatives. `tmdl_lint` reads the TMDL as text and
has no idea whether the model loads — it will report zero errors on a file Desktop
refuses to open. `ConnectFolder` loads it properly and says where it gave up. Run
both; neither substitutes for the other.

Before any of that exists, there is nothing to check, and saying so is the correct
answer. Do not report a gate as passing when it found nothing to look at.

**Build date tables in Power Query, never as a DAX calculated table.** A
calculated table whose span depends on another table is empty until the whole
model refreshes, so it shows a nonsense one-year range on first open and looks
like a modelling error. `CALENDAR`, `CALENDARAUTO` and `ADDCOLUMNS` over either
are the wrong tool here. Read the dates from the data with `LoadCsv` and generate
the range with `List.Dates`. `tmdl_lint` reports a calculated partition, so this
one is checked rather than merely asked for.

**Quote a table whose name is also a DAX function.** A table called `Date` must be
written `'Date'[Date]`, never `Date[Date]` - `DATE` is a function, so unquoted the
parser has to guess. The same goes for `'Calendar'`, `'Time'`, `'Value'`, `'Rank'`
and the rest.

What guessing wrong costs: the measure fails to parse, and the error names the
token rather than the reason, so it reads as a problem with the column. The same
class of trap bites VAR names - `VAR Current` is a syntax error because `CURRENT`
is reserved, and the message blames the variable without saying why. When DAX
rejects something that looks obviously correct, suspect a name collision with the
language before you suspect your logic. `tmdl_lint` reports this as
`dax.unquotedtable`.

**Take the report's colours and geometry from what is already there.** A page
can be correctly wired and still not belong to this report. The palette is the
tokens at the top of `build_report.py` plus white; the canvas is 1920x1080; the
sidebar owns everything left of x=228 and content starts at x=252. Never write a
hex that is not a palette token - anything team-coded gets its colour from a
measure, not from a literal - and never position a visual by eye when the
constant it should derive from is in the generator. `pbir_lint` reports all of
this as `theme.palette`, `layout.*`, `page.canvas` and `page.nav`.

Four colours sit outside the palette because they mean something rather than
decorate something, and a card written in DAX is where you will need them:

| | |
|---|---|
| `#229971` | a completed round |
| `#FF8000` | the next race, and the sprint pill |
| `#FFF3E6` | the sprint pill's fill, tinted from that orange |
| `#6B7280` | no livery known for this team |

The list is closed, and it is closed in both directions. A fifth status needs a
fifth meaning; invent one quietly and the report ends up with two greens that
disagree, which no diff will show you. Equally, none of these may appear in a
visual's properties - they live in measures, because only a measure knows
whether a round is finished. And a palette token must never be pressed into
service as a status: grey chrome that happens to mean "not classified" reads as
chrome to the next person who edits it.

What guessing wrong costs: nothing visible. The colour renders, the report looks
deliberate, and the meaning is wrong only to someone who knows the convention.
This rule was added after the reference itself was found using four colours its
own documentation said did not exist - and passing the check, because the check
read `visual.json` and never read a measure. It reads both now.

**Never invent a PBIR property or field-well name.** They are not discoverable
and not reliably documented, and a wrong one produces a blank visual with no
error anywhere. Copy the shape from a visual that already renders, or from the
report-builder skill's templates. If neither has it, say so rather than guessing.

**Match a card SVG to its tile.** A card grid scales the image to **fill** the
tile and crops the overflow, centred. So a card whose aspect ratio differs from
its tile's loses a band off the top and another off the bottom - and it still
renders: border, headings and labels all present, only whatever sat in the
cropped bands missing. It reads as a styling problem rather than a broken visual,
which is what makes it expensive to find.

Set `width` and `height` on the `<svg>` to the tile's pixel size (content width /
columns, content height / rows) and use **no `viewBox`**. `preserveAspectRatio`
does nothing without one and is ignored with one. Either side may move - size the
card to the tile, or change the grid's `columnCount` / `rowCount` to suit the
card. `pbir_lint` reports the mismatch as `card.aspect`.

**Keep the CSV contract.** UTF-8 with no byte-order mark, `\n` line endings, and
every reader passing `Encoding = 65001`. A byte-order mark lands in the first
column name and matches nothing; the wrong encoding mangles accented driver
names. Neither failure reports itself.

**Verify before writing, not after.** Anything that transforms data should check
its output and refuse rather than leave bad files on disk. When something aborts,
say plainly whether anything was written.

The two orderings are not a style choice. Check first and a failed run leaves the
previous good output untouched. Check second and a failed run has already
overwritten it - so the report is now built on data you know to be wrong, and the
only copy of the right data is gone. Both versions "have a reconciliation check";
only one of them is any use at the moment the check fires.

**Close Power BI Desktop before rewriting the project.** An open `.pbip` holds a
file lock, and refusing is better than half-writing a report.

**Explain what you changed and why, briefly.** The person here is learning to
review agent output. A legible edit they can follow beats a silent correct one.

## What not to do

- Do not run `git commit`, `git checkout`, or anything that moves the checkpoint
  tags unless asked. Resetting to a checkpoint is the participant's decision, and
  getting it wrong is expensive: a `git checkout` with modified tracked files
  refuses outright, and a tag that moves takes somebody's recovery point with it.
  If a checkout looks necessary, say so and let them decide.
- Do not edit files under `powerbi/` while Desktop has the project open.
- Do not add dependencies. Everything needed ships with this repository, and the
  manual promises that every command runs verbatim after `git clone`. An install
  that works here breaks that promise on the next machine - usually on a locked-
  down one, in a room, with no time to fix it.
