---
name: power-bi-folder-naming-convention
description: Apply the in2Facts Power BI display-folder organization convention for semantic model measures. Groups measures by calculation type, mirroring the categories defined in the power-bi-measure-naming-convention skill (aggregation type, time intelligence, scenarios, variances, ratios, ranks, boolean flags, technical/presentation measures). Use when creating, reviewing, or reorganizing display folders for measures in Power BI semantic models.
---

# Power BI Display Folder Convention

## Purpose

Use this skill to organize measures into Display Folders so the Fields list stays navigable as a semantic model grows.

This convention groups measures by calculation type, mirroring the categories already defined in the `power-bi-measure-naming-convention` skill, so a measure's name and its folder location reinforce the same classification rather than encoding two independent taxonomies.

## Core Pattern

```text
<NN> <Top-Level Folder>[\<NN> <Subfolder>]
```

Use `\` to nest a subfolder under a top-level folder — Power BI's native display-folder syntax. `<NN>` is the two-digit sort-order prefix defined in the Folder Sort Order section below; every folder and subfolder carries one. Limit nesting to two levels. A deeper hierarchy makes the Fields list harder to scan, which defeats the purpose of folders — if a subfolder still feels too broad, split it into an additional sibling subfolder under the same parent rather than adding a third level.

## Naming Rules

1. Assign every measure to exactly one top-level folder from the Folder Taxonomy table.
2. Write folder names in Title Case, matching the measure-naming convention's business-name casing.
3. Use a subfolder only when a top-level folder would otherwise hold measures spanning genuinely different sub-groupings (for example, Variances split into scenario comparisons vs. period-over-period, or Time Intelligence split by to-date, previous-period, rolling, and same-period shapes).
4. Do not create a subfolder that holds only one measure — fold it back into its parent folder.
5. Keep a measure's folder assignment consistent with its name: a measure named with a `Δ` qualifier belongs in Variances, one with a time-intelligence qualifier belongs in Time Intelligence, and so on.
6. Do not use folders to restate information already visible in the measure name (for example, a one-measure "Revenue" subfolder for `Revenue (€)`). The measure-naming convention already requires every name to stand alone outside its folder.
7. Prefix every folder and subfolder name with its two-digit sort order from the `Order` column of the Folder Taxonomy table (for example, `01 Base Measures`, `01 Base Measures\01 Aggregation Measures`). The prefix is a mechanical sort key, not part of the Title Case business name — write it as `<NN> <Folder Name>`. See Folder Sort Order below for why and how.

## Folder Taxonomy

| Order | Folder | Subfolder | Contains | Example measure |
| --- | --- | --- | --- | --- |
| 01 | Base Measures | — | Default-aggregation, Actual-scenario measures with no time intelligence, variance, or other qualifier | `Revenue (€)` |
| 01.01 | Base Measures | Aggregation Measures | Default-aggregation measures computed with a direct aggregation function (`SUM`, `AVERAGE`, `MIN`, `MAX`, `COUNT`, `DISTINCTCOUNT`, …) | `Revenue (€)` |
| 01.02 | Base Measures | Iteration Measures | Default-aggregation measures computed with a row-context iterator function (`SUMX`, `AVERAGEX`, `MAXX`, `MINX`, `COUNTX`, …) | `Revenue (€)` |
| 01.03 | Base Measures | Calculate Measures | Default-aggregation measures whose defining logic is a `CALCULATE` filter modification, with no other naming qualifier | `Active Customers (#)` |
| 02 | Aggregations | — | Non-default aggregation-type measures (Average, Median, Min, Max, Distinct, Rank) | `Average Order Value (€)` |
| 03 | Time Intelligence | — | Measures with a time-intelligence qualifier | `Revenue (€) (ytd)` |
| 03.01 | Time Intelligence | To-Date | `mtd`/`wtd`/`qtd`/`ytd` measures | `Revenue (€) (ytd)` |
| 03.02 | Time Intelligence | Previous Period | `pm`/`pq`/`py` measures | `Revenue (€) (py)` |
| 03.03 | Time Intelligence | Rolling | `rXXm` measures | `Revenue (€) (r12m)` |
| 03.04 | Time Intelligence | Same-Period | `sply` measures | `Revenue (€) (sply)` |
| 04 | Scenarios | — | Non-Actual scenario measures | `Revenue BDG (€)` |
| 05 | Variances | — | Scenario-comparison `Δ` measures | `Revenue Δ ACT vs BDG (€)` |
| 05.01 | Variances | Period-over-Period | Period-over-period `Δ` measures | `Revenue Δ YoY (€)` |
| 06 | Ratios | — | Compound-UoM rate or ratio measures | `Speed (km/h)` |
| 07 | Ranks | — | Rank measures | `Rank Customers (pos)` |
| 08 | Flags | — | Boolean flag measures | `Is Key Account (flag)` |
| 09 | Technical | — | Free text, HTML, and color measures used for presentation logic rather than analysis | `Title Color (hex)` |

## Folder Sort Order

Power BI's Fields pane has no native "folders above loose fields" setting — folders and unfoldered measures at the same level are sorted alphabetically together, by name. Two-digit numeric prefixes on folder and subfolder names solve both ordering problems at once:

- **Folders always render above unfoldered measures.** Digits sort before letters, so a folder named `01 Base Measures` always precedes a plain-named measure like `Active Customers (#)` sitting at the same level — regardless of what that measure is called.
- **Folders render in a fixed business-priority order**, not alphabetical drift. `01 Base Measures` through `09 Technical` always appear in that sequence in any table that uses them, whether or not every folder is present.

Rules for applying the prefix:

- Use the `Order` value from the Folder Taxonomy table, formatted as `<NN> <Folder Name>` for a top-level folder (e.g. `03 Time Intelligence`) and `<NN> <Folder Name>\<NN> <Subfolder Name>` for a subfolder (e.g. `03 Time Intelligence\01 To-Date`) — reuse only the two digits after the dot for the subfolder's own prefix.
- Zero-pad to two digits even while the taxonomy has fewer than 10 top-level folders. Unpadded prefixes break the trick once a 10th folder is added, because `"10"` sorts before `"2"` as text.
- The prefix is a sort key, not a name — it does not change a folder's classification, and it is not counted against Title Case (rule 2 still governs the text after the prefix).

> [!NOTE]
> Zero-width space (U+200B) prefixes were tried as an invisible alternative to the visible numeric prefix and confirmed **not** to work in Power BI Desktop's Fields pane — do not reintroduce them. This tracks with the theory: U+200B is a Unicode default-ignorable character, so collation-aware comparers can treat it as weightless rather than as a sortable character.

> [!NOTE]
> A measure can only occupy one folder. When a measure could plausibly fit two categories (for example, a scenario-specific ratio), classify it by whichever qualifier is most prominent in its name — usually the last one applied, since qualifier order in the naming convention reflects increasing specificity.
>
> The Base Measures subfolders classify by DAX implementation, not by name, so they can overlap with a named category — a time-intelligence or variance measure is very often `CALCULATE`-based too, and a rank measure is always an iterator (`RANKX`). Regardless of DAX implementation, a named category (Aggregations, Time Intelligence, Scenarios, Variances, Ratios, Ranks, Flags, Technical) always takes precedence over a Base Measures subfolder. The Base Measures subfolders exist only for measures that carry no other naming-convention qualifier at all.

## Validation Checklist

When reviewing a proposed or existing folder assignment, verify that:

- Every measure is assigned to exactly one top-level folder.
- No subfolder is nested more than one level deep.
- No subfolder contains only a single measure.
- The folder matches the measure's naming-convention category (`Δ` → Variances, a time-intelligence qualifier → Time Intelligence, a scenario abbreviation → Scenarios, and so on).
- A Base Measures measure is split into Aggregation Measures, Iteration Measures, or Calculate Measures by its DAX implementation, and only when no more specific top-level folder already applies.
- Folder names use Title Case.
- Every folder and subfolder name carries its two-digit prefix from the Folder Taxonomy table's `Order` column, zero-padded.

## Output Behavior

When asked to assign or review display folders:

1. Return the recommended folder path for each measure in a code block, formatted as `<NN> Folder\<NN> Subfolder — Measure Name`.
2. Flag any measure whose name and folder classification disagree.
3. Flag any subfolder that contains only one measure.
4. Preserve folder names already established elsewhere in the model rather than inventing new synonyms for the same category — reapply the correct numeric prefix if an existing folder is missing one.
5. If a measure does not fit any folder in the taxonomy, propose the closest analogous folder and flag that the case is not covered.

## Execution

This skill defines the target folder path only; it does not move a measure by itself.

**Preferred: `powerbi-modeling-mcp`.** Microsoft's official Power BI Modeling MCP server (public preview, [microsoft/powerbi-modeling-mcp](https://github.com/microsoft/powerbi-modeling-mcp)). Connect with `connection_operations` — to Power BI Desktop, a Fabric workspace, or a `.pbip` project's TMDL — then set the folder with `measure_operations`, `update` action, on the `displayFolder` field:

```text
measure_operations: action=update, table=<Table>, name="<Measure Name>",
                     displayFolder="<NN> Folder\<NN> Subfolder>"
```

The server is still in public preview — confirm the exact field name against its live tool schema rather than assuming it matches verbatim.

**Fallback: pbi-cli.** When the MCP server isn't available, apply the same change via `pbi measure`:

- Connected live to Power BI Desktop:

  ```bash
  pbi measure update "<Measure Name>" -t <Table> --folder "<NN> Folder\<NN> Subfolder>"
  ```

- Not connected live — edit the `displayFolder` line directly in the table's TMDL definition, then reimport:

  ```bash
  pbi database export-tmdl ./model-tmdl/    # or edit an existing export in place
  # edit displayFolder: "<NN> Folder\<NN> Subfolder>" on the measure in the .tmdl file
  pbi database import-tmdl ./model-tmdl/
  ```

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

This convention determines where a measure appears in the Fields list; it does not affect the measure's name, which is governed by the `power-bi-measure-naming-convention` skill. The two conventions are designed to be applied together — the folder taxonomy exists so that a measure's name and its location tell the same story.

This taxonomy is defined for measures only. Columns, hierarchies, and calculation-group items also support a `displayFolder` property in the tabular model, but this skill does not define a taxonomy for them — if asked to organize those object types, say so explicitly rather than silently reusing the measure taxonomy, since their natural groupings (e.g. by source table or business entity, not by calculation type) are usually different.
