# 0023. Every table is read by rules a model writes for it, per document

- **Status:** Accepted (2026-10-04 to 2026-10-07)
- **Source:** [one table model](../plans/one-table-model-2026-09-30.md) (its decisions of 2026-09-30); [multi-format adapters](../plans/multi-format-adapters-2026-09-23.md), "Excel, in detail" (decision 1), its progress and open question 1

## Context

Table rows were sent to the model one at a time with their header: one query per row, each binding values afresh, and long tables (polars, logs, registers) costing hundreds of queries for claims nobody checks one by one.

## Decision

- **One query per table asks how it's read** (`tablerules.py`): it shows the columns analysed mechanically, sample rows, the text above, the claims a point per cell would give and our heuristic opinion. The owner (2026-10-04): "ask a model how to handle the table ... then ask the model how to handle it, i.e. whether how to produce claims from rows or how to summarize things within a few known templates."
- **The answer is a reading:**
  - rules: templates of a row's cells, applied to every row mechanically and checked against the model's own example claims, a row they don't fit read by itself
  - rows: every row read by itself
  - a summary by a known template (series, log, list), computed and marked derived
- **Every table is asked, whatever its size** (`table_rules: 0`). The owner (2026-10-05): "I was under the impression we'd also ask how to translate rows to claims even for short tables"; "it's difficult to set a hard boundary."
- **Rules failing their checks are asked for once more,** then the rows are read one by one.
- **The outcome is reviewed:** the model is shown what its rules gave and keeps or revises them, up to `table_review` times (10), the last rules passing the checks used. The owner (2026-10-07): "a cap of e.g. 10 will surely be safe yet more than cover the use cases ... just keeping the last revision."
- **Rules are asked per document, never shared between revisions.** The owner (2026-10-05): "I think we cannot effectively identify the 'same table' between revisions in the general case. Each document's claims are processed in any order, and there may be more than two revisions. Trying to avoid vague conditions, and tracing/reporting how a table was read, might be useful."
- **How a table was read is traced** in each claim's derivation, and a finding between claims whose tables were read differently is flagged.
- **Every format's tables take this path:** Excel, CSV, Word, PowerPoint and PDF (PDF's structure: [0024](0024-pdf-table-structure.md)).

## Consequences

- One query per table instead of one per row, with facts as good as row by row on the controlled corpus and conditions kept better.
- Two revisions of one table can be bound differently; the trace flags such findings rather than hiding them.
- Binding guidance (conventions, three worked examples) lives in one prompt and is tuned there.
