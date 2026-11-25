---
name: power-bi-table-naming-convention
description: Apply the in2Facts Power BI table naming convention for semantic models — plain, unprefixed business names for every table, with fact tables doubling as their own measure containers. Use when creating, reviewing, or renaming tables in a Power BI semantic model, or when designing star-schema structure.
---

# Power BI Table Naming Convention

## Purpose

Use this skill to name every table in a Power BI semantic model for the business content it holds, not for its modeling role. A table's role — dimension, fact, bridge, or disconnected — is conveyed by its relationships and icon in Model view, not by a mechanical name prefix. This keeps table names readable for business users browsing the Fields list, Excel, or Analyze in Excel, where a `Dim_`/`Fact_` prefix is an implementation detail with no business meaning.

This convention is designed to be applied together with `power-bi-measure-naming-convention` (measure names) and `power-bi-folder-naming-convention` (measure display folders).

## Core Pattern

```text
<Entity>
<Business Process>
<Entity A> <Entity B>
<Purpose>
```

No table takes a role prefix (no `Dim`, `Fact`, `Bridge`, `Parameter`, `Selector`, or similar). Every table is named in Title Case for what it represents in business terms.

## Naming Rules

1. **Do not prefix any table** with a role label. Name it for its business content: `Customer`, `Sales`, `Customer Account`, `Discount Rate`.
2. Write the table name in **Title Case**, matching the measure-naming convention's business-name casing.
3. Name a dimension for the singular business entity it describes (`Customer`, not `Customers`), matching its one-row-per-entity grain. Do not use Power BI reserved words (e.g., `Date`, `User`, `Group`) as table names.
4. Name a fact table for the business process or event it measures, at the grain it's loaded at (`Sales`, `Inventory Movement`) — never for the source-system table it was extracted from (`FactInternetSales`, `tbl_orders_2024`).
5. Name a bridge table for both entities it connects, using one ordering rule throughout the model (e.g., always alphabetical, or always the same fixed entity sequence) — `Customer Account`, not `Account Customer`, once that rule says `Customer` leads. Default to alphabetical order if the model has no bridge table yet to set a precedent.
6. Name a disconnected table (a What-if parameter, a Field Parameters table, a manual `SWITCH`/`SELECTEDVALUE` selector) for what it lets the user pick, adding a plain descriptive word only where it aids clarity (`Discount Rate`, `Time Granularity`, `Measure Selector`) — this is a business-clarity choice, not a mechanical prefix grammar.
7. Use the same entity term consistently across a dimension's table name, its fact-table foreign key column name, and any bridge table that references it (`Customer` everywhere, not `Customer` in one place and `Client` in another).
8. Role is discoverable in Model view (relationships, cardinality, table icon) and, where the tool supports it, in the table description — not in the name.

## Dimension Tables

Holds one row per instance of a business entity, used to slice and filter fact tables.

```text
Customer
Product
Employee
Date
```

> [!NOTE]
> The date dimension is a plain-named table (`Date` or `Calendar`) like any other — but it must additionally be marked as the model's official Date Table (Power BI Desktop: Table tools → Mark as date table) so time-intelligence DAX functions resolve correctly. Naming it clearly does not substitute for marking it.

A dimension table never carries a measure or a display folder — see Never Place Measures on a Dimension Table below for where a calculation that concerns a dimension actually belongs.

## Fact Tables Are Measure Tables

Do not create a separate, dedicated `_Measures` table. Instead, every fact table doubles as the home for its own measures:

- Hide every physical column of the fact table from report view — keys, degenerate dimensions, and any raw numeric column that a measure wraps. Users browse measures, never raw fact columns.
- Build and organize the table's measures directly on it, using display folders (`power-bi-folder-naming-convention`) to keep them navigable.
- A factless fact table (one that records an event with no numeric column at all, e.g. an attendance log) is the clearest case with no natural business measure — but any fact table can end up there once its columns are hidden. Add one minimal placeholder measure so the table still exposes at least one visible object; a table with every column hidden and zero measures can become unselectable in the Fields pane and report authoring UI:

  ```dax
  Dummy = BLANK()
  ```

  Keep this placeholder visible (do not hide it) precisely so the table remains reachable; replace or supplement it the moment the table gains a real measure.

This means a model typically has no table dedicated solely to holding measures — each fact table is self-sufficient. Bridge tables are handled differently — see Bridge Tables below.

## Never Place Measures on a Dimension Table

A dimension table stays a pure browsing/filtering surface: no measures, and no display folders — a display folder exists to organize measures, so a dimension with no measures needs none. A calculation that concerns a dimension still belongs on a fact table, resolved in this order:

1. If the calculation depends on an existing measure (for example, `RANKX(ALL('Product'), [Sales ($)], ...)`, ranking by an already-placed `[Sales ($)]` measure), place it on the same table that hosts the measure it depends on.
2. Otherwise, if it's a plain aggregate of the dimension itself (for example, `Customer Rowcount (#) = COUNTROWS(Customer)`), place it on the fact table connected to that dimension by a relationship.
3. If the dimension is related to more than one fact table (for example, `Customer` related to both `Sales` and `Reseller Sales`) and step 1 doesn't already resolve the choice, do not guess — ask the developer which fact table should host it before creating the measure.

## Bridge Tables

Resolves a many-to-many relationship between two dimensions, or connects a shared dimension to fact tables at different grains.

```text
Customer Account
Product Category
```

A bridge table can be hidden from report view entirely (`isHidden` on the table itself, not just its columns) — self-service users never need to browse a bridge table's rows or columns directly, only benefit from the relationship it resolves. Unlike a fact table, a bridge table does not need a `Dummy = BLANK()` placeholder measure: a fully hidden table has no reason to remain reachable in the Fields pane.

## Disconnected Tables

A disconnected table has no relationships to the rest of the model; it exists only so DAX can read a value the user picked. Two constructions are common, and the plain business name should reflect which one it is when that isn't obvious from context alone:

| Construction | Built from | Read via | Example name |
| --- | --- | --- | --- |
| Numeric What-if parameter | `GENERATESERIES` calculated table with a slider | `SELECTEDVALUE` feeding an arithmetic formula | `Discount Rate`, `Growth Rate %` |
| Field Parameters / manual switch | Power BI's Field Parameters feature, or a manual DAX/enter-data table listing options | `SELECTEDVALUE` feeding `SWITCH` to swap a measure, dimension, or granularity | `Measure Selector`, `Row Selector`, `Column Selector`, `Time Granularity` |

Power BI's Field Parameters feature auto-names the table after the fields you select when you create it — rename it to a clear business name before shipping the model; the default name doesn't describe what the selector controls.

## Validation Checklist

When reviewing a proposed or existing table, verify that:

- No table carries a mechanical role prefix (`Dim`, `Fact`, `Bridge`, `Parameter`, `Selector`, `_`, or similar).
- Dimension names are singular business entities in Title Case.
- Fact table names describe the business process/grain, not the source-system table.
- Bridge table names include both connected entities, in a consistent order used throughout the model.
- Every disconnected table has a clear business name — none is left with Power BI's auto-generated default name.
- Every fact table has all physical columns hidden from report view and exposes at least one visible measure — a real one where possible, otherwise a `Dummy = BLANK()` placeholder.
- Every bridge table is hidden from report view entirely (table-level `isHidden`), with no placeholder measure needed.
- No separate table exists solely to hold measures.
- No dimension table carries a measure or a display folder — every measure lives on a fact table, chosen by measure dependency or by the relevant relationship path.
- The date dimension is marked as the model's official Date Table, not just clearly named.
- The same entity term is used consistently across the table name, its FK columns elsewhere, and any bridge table referencing it.

## Output Behavior

When asked to propose or review tables:

1. Return the recommended table names in a code block.
2. Flag any table name that encodes a role prefix instead of business content.
3. Flag any fact table with visible physical columns, or with zero visible measures and no `Dummy = BLANK()` placeholder. Flag any bridge table that isn't hidden entirely at the table level.
4. Flag a dedicated measure-only table if one exists — its measures should be redistributed onto the fact table(s) they describe, or left on a single fact table if the model has only one.
5. Flag any measure or display folder found on a dimension table. Recommend the fact table that hosts the measure it depends on, or the fact table it's related to when there's no such dependency — and if more than one fact table is related with no dependency to disambiguate, ask the developer instead of picking one.
6. Flag a date table that isn't marked as the model's official Date Table.
7. If a table doesn't fit any category in this taxonomy (for example, a disconnected legend or free-text annotation table), propose the closest analogous plain business name and explicitly flag that the case isn't covered by an approved example.

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

This convention governs table names, column visibility, and measure placement only. It does not govern measure names (`power-bi-measure-naming-convention`), measure display folders (`power-bi-folder-naming-convention`), column naming, or relationship cardinality. Those fall outside this convention's scope.

Apply all of them together: a plainly-named fact table with unnamed measures, or a correctly-hidden fact table with a many-to-many relationship left unresolved, is still an incomplete model.

Apply a rename with `pbi table rename <old-name> "<New Name>"`, and mark the date table with `pbi table mark-date "<Table>" --date-column <column>`. pbi-cli only exposes `--hidden` at creation time (`pbi table create`/`pbi column create`) — it has no live command to hide a table or column that already exists, so apply that part of this convention by editing the `isHidden` line directly in the table's TMDL definition and reloading in Power BI Desktop.
