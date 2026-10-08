# 0024. A PDF table's structure: heuristics first, then rules a model writes where lines are suspect

- **Status:** Accepted (2026-10-07)
- **Source:** [one table model](../plans/one-table-model-2026-09-30.md): decision 1 (2026-09-30), "PDF tables onto the rules path, in detail", "Structure rules, in detail" and its progress

## Context

A PDF's tables come from a parser that guesses cells from drawn edges and text: it splits a cell's lines into rows (taking shading boxes' edges for row lines), splits two-line headers, stacks tables into one and draws columns through words. On the controlled PDFs, 254 of 394 tables failed a check against their image, nearly all on structure.

## Decision

- **Cell text comes from the text layer, never retyped by a model; vision checks it.** The owner (2026-09-30): "Perhaps assume it is, but verify at least one row via vision?" The rules query gets the table's image and copies a row of values from it; a disagreement sends the rows to be read one by one.
- **Heuristics first, no model** (`tables.py`): rows joined across boundaries without a drawn rule in a mostly ruled table; two-line headers merged; a stacked table, styled as the header, split off; columns joined where every split word is cut; wrapped cells joined.
- **Then structure rules, only where a line is suspect** (`tablestructure.py`, `table_structure`). The owner (2026-10-07): "Ideally, we'd not provide the full table in bands for processing via vision, instead getting some comprehensible suggestions/rules about how to work around confusing formatting, with feedback similar to how we approach claims rules."; then "The recommendations look good, please proceed":
  - a separate query before the claims rules
  - rules from a closed vocabulary (a condition from the lines' signals, or lines named, and an action), applied mechanically, checked against rows copied from the image, reviewed
  - only for parts with suspect lines
- **A part the model reads as no table** (a chart, a floor plan) is read as a figure instead.
- **Repair comes after rules, where measured,** rather than a repair query for every table (the owner, 2026-10-07: "The recommendations look good.").

## Consequences

- On the controlled PDFs (2026-10-08): image-check failures 254 of 394 to 24 of 399 (the check compares a row of values only: header cells the parser took for tables of their own had made most of the failures), misbound claims 229 to 205, hallucinated 7 to 6, facts as before.
- Columns are joined mechanically only where every split word is cut; a model's column joins in the wrong place weren't caught by whole-text examples, so a body row's separate values are never joined.
- The layout add-on (`pymupdf-layout`) was measured and not adopted: no gain over the heuristics, 261 MB of dependencies.
- New hazards become signals and actions in the vocabulary, each measured on the corpus and the development slices.
