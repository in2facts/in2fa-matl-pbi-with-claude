---
name: power-bi-measure-naming-convention
description: Apply the in2Facts Power BI DAX measure naming convention, aligned with IBCS 2.0 and ISO 24896:2026 notation principles. Use when creating, reviewing, renaming, or documenting Power BI measures, including aggregation type, units of measure (currency, percentages, hexadecimal color codes, free text, and HTML markup), time intelligence, scenarios, variances (including period-over-period comparisons such as MoM, QoQ, and YoY), ratios, ranks, and boolean flags.
---

# Power BI Measure Naming Convention

## Purpose

Use this skill to create consistent, readable, and sortable DAX measure names for Power BI semantic models.

The convention translates the reporting principles of **IBCS 2.0**, whose notation component is aligned with **ISO 24896:2026, Notation for business reporting**, into a practical Power BI naming pattern.

IBCS requires consistent terminology, abbreviations, number formats, units, scenarios, and time periods. This skill defines the concrete semantic-model naming convention used by in2Facts.

## Core Pattern

```text
[<Aggregation Type>] <Measure Name> (<UoM>) [(<Time Intelligence>)]
[<Aggregation Type>] <Measure Name> <Scenario> (<UoM>) [(<Time Intelligence>)]
```

For variances, use:

```text
[<Aggregation Type>] <Measure Name> Δ <Scenario A> vs <Scenario B> (<UoM>) [(<Time Intelligence>)]
[<Aggregation Type>] <Measure Name> Δ <Scenario A> vs <Scenario B> (%) [(<Time Intelligence>)]
```

The brackets in these patterns indicate optional components. Do not include square brackets in the actual measure name.

## Naming Rules

1. Write the business measure name in **Title Case**.
2. Include `<Aggregation Type>` as a leading term before the business measure name only when the aggregation deviates from the default for that unit of measure (typically SUM for additive quantities, COUNT for `#`), and never use `Total` for the default.
3. When the measure represents a non-Actual scenario outside a variance comparison, add the uppercase scenario abbreviation directly after the measure name, before any parentheses.
4. Put the unit of measure in the first pair of parentheses, immediately after the measure name (or after the scenario abbreviation, when present).
5. Write all descriptive qualifiers inside parentheses in **lower-case**.
6. Use one qualifier per pair of parentheses.
7. Keep the parenthetical qualifier order consistent:
   1. Unit of measure
   2. Time intelligence
8. Use the same term and abbreviation consistently throughout the semantic model.
9. Do not repeat the unit in the business measure name if it is already shown as the UoM qualifier.

## Aggregation Type

Use the following statistical terms as a leading qualifier for a non-default aggregation:

| Aggregation | Term |
| --- | ---: |
| Average | `Average` |
| Median | `Median` |
| Minimum | `Min` |
| Maximum | `Max` |
| Distinct count | `Distinct` |
| Rank | `Rank` |

> [!NOTE]
> Leave `<Aggregation Type>` out for the default aggregation for that unit of measure — typically SUM for additive quantities (`€`, `kg`, `y`, …) and COUNT for `#`. Never use `Total` — it collides with the "Grand Total" label Power BI generates in matrix and table visuals.

Examples:

```text
Average Order Value (€)
Median Resolution Time (d)
Min Downtime (h)
Max Downtime (h)
Distinct Customers (#)
Rank Customers (pos)
```

`<Aggregation Type>` applies to quantitative measures. Free text (`txt`), HTML markup (`html`), SVG markup (`svg`), hexadecimal color (`hex`), and boolean flag (`flag`) measures have no applicable aggregation and never take an `<Aggregation Type>` prefix.

## Units of Measure

Use the clearest recognized symbol or abbreviation for the reported quantity.

Use the recognized symbol for the reporting currency (for example `€`, `$`, or `£`), never a three-letter ISO code such as `EUR` or `USD`, to keep the measure name short and readable. Use one currency symbol consistently throughout a given semantic model, matching its actual reporting currency.

| Measure type | UoM | Example |
| --- | ---: | --- |
| Count | `#` | `Customers (#)` |
| Currency | `€`/`$`/`£`, `k€`/`k$`/`k£`, `m€`/`m$`/`m£` | `Revenue (€)`, `Revenue ($)` |
| Percentage or share | `%` | `Gross Margin (%)` |
| Percentage-point difference | `pp` | `Gross Margin Δ ACT vs BDG (pp)` |
| Years | `y` | `Life Expectancy (y)` |
| Days | `d` | `Average Resolution Time (d)` |
| Hours | `h` | `Downtime (h)` |
| Minutes | `min` | `Average Wait Time (min)` |
| Seconds | `s` | `Response Time (s)` |
| Kilograms | `kg` | `Shipment Weight (kg)` |
| Tonnes | `t` | `Shipment Volume (t)` |
| Full-time equivalents | `fte` | `Workforce (fte)` |
| Free text | `txt` | `Customer Segment (txt)` |
| HTML markup | `html` | `ABC Analysis (html)` |
| SVG markup | `svg` | `Trend Sparkline (svg)` |
| Hexadecimal color code | `hex` | `Title Color (hex)` |
| Rank position | `pos` | `Rank Customers (pos)` |
| Boolean | `flag` | `Is Key Account (flag)` |

### Currency Scaling

If values are scaled, make the scaling explicit in the UoM. This applies regardless of which currency symbol the model uses:

```text
Revenue (€)
Revenue (k€)
Revenue (m€)

Revenue ($)
Revenue (k$)
Revenue (m$)
```

Do not use the same name for measures with different scaling.

## Time Intelligence

Use lower-case abbreviations:

| Meaning | Abbreviation |
| --- | ---: |
| Month to date | `mtd` |
| Week to date | `wtd` |
| Quarter to date | `qtd` |
| Year to date | `ytd` |
| Rolling N months, zero-padded (also known as trailing N months; `r12m` = TTM) | `rXXm` |
| Previous month | `pm` |
| Previous quarter | `pq` |
| Previous year | `py` |
| Same period last year | `sply` |

> [!NOTE]
> Use `py` for a fixed prior full year, and `sply` for the same period last year at the current granularity, matching the current period's length and offsetting it by one year (equivalent to DAX `SAMEPERIODLASTYEAR`).

Examples:

```text
Customers (#) (mtd)
Customers (#) (qtd)
Customers (#) (ytd)
Customers (#) (r12m)
Customers (#) (r06m)
Revenue (€) (ytd)
Life Expectancy (y) (ytd)
```

> [!NOTE]
> Only add a time-intelligence qualifier when the calculation itself applies that time transformation. Do not add `(ytd)` merely because a visual is filtered to the current year.

A measure with no time-intelligence qualifier is a basic aggregation measure or a `CALCULATE` measure with no time-period transformation.

## Scenarios

Use the following uppercase scenario abbreviations:

| Scenario | Abbreviation |
| --- | ---: |
| Actual | `ACT` |
| Budget | `BDG` |
| Target | `TGT` |
| Forecast | `FCST` |

> [!NOTE]
> Actual is the default scenario and is implicit: omit the scenario abbreviation for Actual, and add it only for Budget, Target, or Forecast.

Examples:

```text
Revenue (€)
Revenue BDG (€)
Revenue TGT (€)
Revenue (€) (ytd)
```

When a scenario is part of a variance comparison, include it in the comparison expression rather than as a final qualifier:

```text
Revenue Δ ACT vs BDG (€)
Revenue Δ ACT vs BDG (%)
```

## Variances

Use `Δ` for the arithmetic as well as relative difference between scenarios:

```text
<Measure Name> Δ <Scenario A> vs <Scenario B> (<UoM>)
```

Examples:

```text
Revenue Δ ACT vs BDG (€)
Customers Δ ACT vs TGT (#)
Life Expectancy Δ ACT vs BDG (y)

Revenue Δ ACT vs BDG (%)
Customers Δ ACT vs TGT (%)
Life Expectancy Δ ACT vs BDG (%)

Gross Margin Δ ACT vs BDG (pp)
Gross Margin Δ ACT vs BDG (%)
```

### Period-over-Period Variances

Use the following abbreviations for a variance against the immediately preceding period of the same length, instead of a `<Scenario A> vs <Scenario B>` comparison:

| Comparison | Abbreviation |
| --- | ---: |
| Week-over-week | `WoW` |
| Month-over-month | `MoM` |
| Quarter-over-quarter | `QoQ` |
| Year-over-year | `YoY` |

```text
<Measure Name> Δ <Comparison> (<UoM>)
<Measure Name> Δ <Comparison> (%)
```

Examples:

```text
Revenue Δ MoM (€)
Revenue Δ MoM (%)
Revenue Δ QoQ (€)
Revenue Δ QoQ (%)
Revenue Δ YoY (€)
Revenue Δ YoY (%)
```

## Ratios

Combine two recognized unit symbols with `/` to express a rate or ratio, using the standard `<Measure Name> (<UoM>)` pattern:

```text
<Measure Name> (<UoM A>/<UoM B>)
```

Examples:

```text
Speed (km/h)
Burn Rate (€/y)
Revenue per Employee (€/fte)
```

## Ranks

Rank measures use `Rank` as the aggregation type (see Aggregation Type) together with the `pos` unit of measure:

```text
Rank <Measure Name> (pos)
```

Examples:

```text
Rank Customers (pos)
Rank Revenue (pos)
```

> [!NOTE]
> When more than one ranking criterion could apply to the same entity, disambiguate with `by <Criterion>`, for example `Rank Products by Sales (pos)` versus `Rank Products by Quantity (pos)`.

## Boolean Flags

Use `Is` or `Has` as the leading word of the Title Case business name, paired with the `flag` unit of measure:

```text
Is <Attribute> (flag)
Has <Attribute> (flag)
```

Examples:

```text
Is Key Account (flag)
Has Delete Permission (flag)
```

## Approved Examples

```text
Customers (#)
Customers (#) (mtd)
Customers (#) (qtd)
Customers (#) (ytd)
Customers (#) (r12m)

Revenue (€)
Revenue (€) (mtd)
Revenue (€) (ytd)
Revenue Δ ACT vs BDG (€)
Revenue Δ ACT vs BDG (%)
Revenue Δ YoY (€)
Revenue Δ YoY (%)

Life Expectancy (y)
Life Expectancy (y) (ytd)
Life Expectancy Δ ACT vs BDG (y)
Life Expectancy Δ ACT vs BDG (%)

Child Mortality Rate (%)
Gross Margin (%)
Gross Margin Δ ACT vs BDG (pp)
Gross Margin Δ ACT vs BDG (%)

Average Order Value (€)
Title Color (hex)

Speed (km/h)
Rank Customers (pos)
Is Key Account (flag)

Revenue ($)
Rank Products by Sales (pos)
```

## Validation Checklist

When reviewing a proposed measure name, verify that:

- The business name is clear and uses Title Case.
- No business name uses a `Total` prefix; non-default aggregations are named with their statistical term instead.
- The UoM is present and unambiguous.
- Counts use `(#)`.
- Percentage measures use `(%)`.
- Absolute differences between percentages use `(pp)`.
- Relative variances use `(%)`.
- Time-intelligence abbreviations are lower-case.
- Scenario abbreviations are uppercase.
- `rXXm` uses a zero-padded month count for a rolling window (e.g. `r06m`, `r12m`).
- Period-over-period variances use `MoM`, `QoQ`, or `YoY`.
- Ratio measures use a compound UoM combining two recognized units with `/`.
- Rank measures use the `Rank` aggregation type with the `pos` UoM, disambiguated with `by <Criterion>` when more than one ranking basis exists.
- Boolean flag measures start with `Is`/`Has` in Title Case, with the `flag` UoM.
- Qualifiers appear in the defined order.
- The exact same concept uses the exact same term everywhere.
- No symbol or qualifier is duplicated.

## Output Behavior

When asked to propose or review measure names:

1. Return the recommended names in a code block.
2. Flag ambiguous units or scenario meanings.
3. Distinguish absolute, relative, and percentage-point variances.
4. Preserve the organization's approved business terminology.
5. Briefly explain any correction.
6. If the measure does not fit any pattern in this skill (for example a geographic coordinate), apply the closest analogous pattern, and explicitly flag that the case is not covered by an approved example.

## Execution

**Preferred: `powerbi-modeling-mcp`.** Microsoft's official Power BI Modeling MCP server (public preview, [microsoft/powerbi-modeling-mcp](https://github.com/microsoft/powerbi-modeling-mcp)). Connect with `connection_operations` — to Power BI Desktop, a Fabric workspace, or a `.pbip` project's TMDL — then apply the name with `measure_operations`:

```text
measure_operations: action=create, table=<Table>, name="<Measure Name> (<UoM>)",
                     expression="<DAX expression>", displayFolder="<path>"     # new measure
measure_operations: action=rename, table=<Table>, name="<Old Name>", newName="<New Name>"
measure_operations: action=update, table=<Table>, name="<Measure Name>", description="<description>"
```

The server is still in public preview — confirm the exact field names (`expression`, `displayFolder`, `newName`, …) against its live tool schema rather than assuming they match verbatim.

**Fallback: pbi-cli.** When the MCP server isn't available, apply the same change with `pbi measure`:

```bash
pbi measure create "<Measure Name> (<UoM>)" -e "<DAX expression>" -t <Table> --folder "<path>"   # new measure
pbi measure rename "<Old Name>" "<New Name>" -t <Table>                                          # rename only
pbi measure update "<Measure Name>" -t <Table> --description "<description>"                     # other metadata
```

Multi-line DAX (`VAR`/`RETURN`) collapses when passed via `-e` — pipe it from stdin instead:

```bash
echo 'VAR ... RETURN ...' | pbi measure create "<Measure Name> (<UoM>)" -e - -t <Table>
```

Not connected live to Power BI Desktop with either tool: edit the measure's name/expression directly in the table's TMDL definition, then reimport — `pbi database export-tmdl`/`import-tmdl`, or the MCP server's `database_operations` import/export:

```bash
pbi database export-tmdl ./model-tmdl/    # or edit an existing export in place
# edit the measure's name line in the .tmdl file
pbi database import-tmdl ./model-tmdl/
```

## Display Folders

Display folders may group measures by scenario, subject, or purpose. The measure name must remain understandable outside the folder, such as in Excel, Analyze in Excel, external tools, and search results. See the `power-bi-folder-naming-convention` skill for the folder taxonomy itself.

## Standards References

- IBCS Association, **IBCS Standards 2.0**, Notation and Composition: https://www.ibcs.com/
- ISO, **ISO 24896:2026, Notation for business reporting**: https://www.iso.org/standard/88366.html

## Checking a whole model at once

The rules above are also implemented as an offline linter, so a model can be
checked without opening Desktop or refreshing anything:

```bash
python scripts/tmdl_lint.py "C:\path\to\Project.pbip"
```

It reports ERROR for things that break the model or the conventions outright
(a role prefix, a measure on a dimension, a visible fact column, a date table
that is not marked) and WARN for naming and display-folder departures. WARN
never fails the run - a convention is a default, and a model may have a good
reason to depart from one.

This skill remains the specification. Where the linter and this document
disagree, this document wins; the linter is only a reading of it, and covers the
mechanically checkable subset.

## Scope Note

IBCS and ISO 24896 define business-reporting notation and consistency principles.

The exact Power BI measure-name syntax in this skill — including parentheses placement, Title Case, qualifier order, and the `Δ` symbol — is the in2Facts implementation convention designed to operationalize those principles in semantic models.
