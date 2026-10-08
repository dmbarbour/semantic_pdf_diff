# 0022. Spreadsheet cells are read as Excel shows them, never evaluated

- **Status:** Accepted (2026-10-04)
- **Source:** [multi-format adapters](../plans/multi-format-adapters-2026-09-23.md), "Excel, in detail" (decision 2) and the plan's decisions

## Context

A workbook holds values, number formats, formulas with or without cached results, merged cells, defined tables and hidden sheets. A reader could show raw values, evaluate formulas, or show what a person sees.

## Decision

- **Cells as Excel shows them:** cached values in their number formats; a CSV's fields as written.
- **A formula without a cached value is marked, never evaluated** ("[formula =C6+C7, not calculated]").
- **openpyxl** in the `office` extra reads them (MIT; number formats, merged cells, defined tables, cached values). The library choice was left to Claude (the owner: "I'll leave it to you. You can review the decision if there are any quality or integration concerns.").
- **Directness isn't trust:** a claim read from cells says so in its derivation, but whether its columns were interpreted right (a model step, recorded as such) is still open to question.
- Hidden sheets are read and marked.

## Consequences

- Claims match what a reader of the workbook sees, and a workbook saved without recalculation shows its formulas as uncalculated.
- Whether an uncalculated formula should be a claim's value or only a coverage note is an open lever (the [lever index](../reviews/levers.md)).
