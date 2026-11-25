---
name: power-bi-dax-pitfalls
description: in2Facts field notes on DAX and semantic model traps that fail silently rather than erroring. Use this skill EVERY TIME you write or debug a DAX measure that returns an unexpected BLANK, a table visual returning far more rows than expected, a measure reading a dimension attribute from a fact context, an SVG or HTML measure, or a model whose grain repeats across seasons, years or partitions. Trigger phrases include 'measure returns blank', 'SELECTEDVALUE blank', 'wrong row count', 'cross join', 'too many rows', 'SYNTAXERROR', 'VAR error', 'svg measure', 'image measure', 'dataCategory ImageUrl', 'card shows nothing', 'filter direction', 'RELATED', 'LOOKUPVALUE', 'composite key', or any measure that works for one entity but not another. Every rule was confirmed against a live model, not inferred from documentation.
---

# DAX and Model Pitfalls

Findings from building the in2Facts F1 dashboard. Each of these produced a
**silent wrong answer** — a blank, or a plausible-looking number — never an
error. That is what makes them expensive.

Confirmed against a live Power BI Desktop model and DAX queries.

---

## Filters never flow from a fact back to a dimension

**Three separate bugs in one build shared this root cause.** It is the single
most common source of an unexplained blank.

### Symptom

A measure returns its fallback for every row, or blank:

```dax
Team Colour (hex) = SELECTEDVALUE('Team'[Team Colour], "#6B7280")
```

On a page grouped by `Driver`, this returns `#6B7280` for every driver.

### Cause

With only `Driver` in filter context, `Team` is **not filtered**. All twelve
teams are visible, so `SELECTEDVALUE` has more than one value and returns blank.
Filters propagate dimension → fact, never fact → dimension.

The same mistake dressed differently: reading a dimension attribute inside a
`CALCULATE` that filters the fact.

```dax
-- WRONG: Driver is untouched by filtering Session Result, so this is blank
VAR Winner = CALCULATE(SELECTEDVALUE('Driver'[Driver Code]), 'Session Result'[Position] = 1)
```

### Three working shapes

```dax
-- 1. Pass the fact table in, to force the cross-filter through it
CALCULATETABLE(VALUES('Team'[Team Colour]), 'Session Result')

-- 2. Iterate the fact and reach across with RELATED
MAXX(FILTER('Session Result', 'Session Result'[Position] = 1), RELATED('Driver'[Driver Code]))

-- 3. Resolve the key on the fact, then look the attribute up directly
VAR TeamKey = CALCULATE(SELECTEDVALUE('Session Result'[Team Key]), 'Session Result'[Race Key] = LastKey)
RETURN LOOKUPVALUE('Team'[Team Name], 'Team'[Team Key], TeamKey)
```

### Prefer shape 3 for a "latest value" fallback

A fallback branch that relied on table-filter propagation returned blank even
with provably correct inputs — `N = 2`, `LastKey = "2026-12"`, result blank.
Reading the foreign key off the fact and using `LOOKUPVALUE` is unambiguous and
does not depend on propagation.

Note that such a branch may be reached by **only one entity in the whole model**
(here: a driver who changed team mid-season), so it can stay broken indefinitely
without anyone noticing. Test the fallback deliberately.

---

## A table of dimension columns with no measure returns the full cross join

### Symptom

A table filtered to `Position = 1` returns **552 rows instead of 12** — every
driver against every round.

### Cause

The table projected Round, Race Name, Driver and Team — columns from three
different tables. With no measure, nothing forces the fact-table join, so the
filter does not constrain the result at all.

### Rule

Add a measure **from the same fact the filter is on**.

A measure from a *different* fact re-expands it: a poles table filtering
`Qualifying Result` needs `Poles (#)`. Adding `Average Finish (pos)` from
`Session Result` instead took it back to 233 rows.

Those measure columns are load-bearing. Do not remove them for looking redundant
next to the dimension columns.

---

## A VAR may not share a name with a column on the host table

```dax
-- Session Result has a [Status] column, so this is SYNTAXERROR
VAR Status = SELECTEDVALUE('Session Result'[Position Text])
```

The error does not point at the collision. Prefix or rename variables —
`StatusLabel`, `_Status`.

---

## SVG and image measures

- The payload must be **left unencoded**: `data:image/svg+xml;utf8,` followed by
  raw markup with plain `#` hex colours. Percent-encoding `<`, `>` and spaces
  produces blank cells even though the SVG is valid XML.
- The measure needs **`dataCategory: ImageUrl`**.
- Escape `&` in any data interpolated into the markup (`SUBSTITUTE(x, "&", "and")`)
  or the SVG is malformed.
- **Guard the measure on having data in context**, or entities that exist in the
  dimension but have no rows this period render as empty tiles:

```dax
IF(NOT ISBLANK(Code) && [Distinct Races (#)] > 0, "data:image/svg+xml;utf8," & ...)
```

A blank measure drops the tile entirely, which is what you want.

---

## Group by a composite key, never by a repeating natural key

### Symptom

Half a card grid silently blank.

### Cause

Grouping by `Round`, which repeats across seasons. `SELECTEDVALUE` inside the
card measure goes blank wherever two seasons disagree about that round.

Rounds 1–3 masked the bug entirely, because the same three countries opened both
the 2025 and 2026 calendars.

### Rule

Group by the surrogate that encodes the partition — `Race Key` = `2026-01`.
Build the key in the source data, not in DAX.

**Test with more than one partition loaded.** A single season, year or company
will hide this class of bug completely.

---

## Table names that collide with DAX keywords need quoting everywhere

`Date` is the one that actually bites, because almost every model has a Date table
and `DATE` is a DAX function. Unquoted, the parser has to choose between your table
and the function:

```dax
CALCULATE([Points (pts)], DATESYTD(Date[Date]))     -- ambiguous
CALCULATE([Points (pts)], DATESYTD('Date'[Date]))   -- correct
```

The quotes are what say "this is my table, not the function". The same applies to
`'Calendar'`, `'Time'`, `'Value'`, `'Filter'`, `'Format'`, `'Rank'`, `'Year'`,
`'Month'`, `'Day'` and any other table sharing a name with a function — and to
`'Session'`, which is a reserved word rather than a function.

Always write the quotes. Do not rely on the expression happening to compile, because
when it does not, the error names no cause. `tmdl_lint` reports this as
`dax.unquotedtable`.

---

## A calculated table deriving its span from another table is empty before first refresh

A calendar built from `MIN`/`MAX` of a fact date shows a nonsense one-year range
when the project is opened before any refresh.

**Refresh the whole model, not single tables**, before judging a derived
calculated table.

---

## Related skills

- `power-bi-measure-naming-convention` — how to name what you build here
- `power-bi-pbip-pitfalls` — TMDL syntax, PBIP projects, and the Desktop loop
- `pbi-report-builder` — the report-side equivalent of these notes
