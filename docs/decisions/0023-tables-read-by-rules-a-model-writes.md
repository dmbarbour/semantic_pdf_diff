# 0023. Every table is read by rules a model writes for it, per document

- **Status:** Accepted (2026-10-04 to 2026-10-07; amended 2026-10-09 and 2026-10-10)
- **Source:** [one table model](../plans/README.md#retired) (its decisions of 2026-09-30); [multi-format adapters](../plans/README.md#retired), "Excel, in detail" (decision 1), its progress and open question 1

## Context

Table rows were sent to the model one at a time with their header: one query per row, each binding values afresh, and long tables (polars, logs, registers) costing hundreds of queries for claims nobody checks one by one.

## Decision

- **One query per table asks how it's read** (`tablerules.py`): it shows the columns analysed mechanically, sample rows, the text above, the claims a point per cell would give and our heuristic opinion. The owner (2026-10-04): "ask a model how to handle the table ... then ask the model how to handle it, i.e. whether how to produce claims from rows or how to summarize things within a few known templates."
- **The answer is a reading:**
  - rules: templates of a row's cells, applied to every row mechanically and checked against the model's own example claims, a row they don't fit read by itself
  - rows: every row read by itself
  - a summary by a known template (series, log, list), computed and marked derived
- **Every table is asked, whatever its size** (`table_rules: 0`). The owner (2026-10-05): "I was under the impression we'd also ask how to translate rows to claims even for short tables"; "it's difficult to set a hard boundary."
- **A column's role is the model's to name** (2026-09-30): which columns are inputs, outputs or entities can't be told without a model. A column stepping evenly (wind speed 14, 15, 16…) is shown in the column analysis as a hint, never deciding alone; a case table's claims are one per output cell, the row's inputs their conditions, as the worked example "Rotor performance" shows (`tablerules.py`). The owner: "default claims seem fine, esp. if we can recognize the "input" conditions, but I'm not sure how we'd recognize which columns represent entites or input conditions without already asking a model for a claims rule."
- **Rules failing their checks are asked for once more,** then the rows are read one by one.
- **The outcome is reviewed:** the model is shown what its rules gave and keeps or revises them, up to `table_review` times (10), the last rules passing the checks used. The owner (2026-10-07): "a cap of e.g. 10 will surely be safe yet more than cover the use cases ... just keeping the last revision."
- **Rules are asked per document, never shared between revisions.** The owner (2026-10-05): "I think we cannot effectively identify the 'same table' between revisions in the general case. Each document's claims are processed in any order, and there may be more than two revisions. Trying to avoid vague conditions, and tracing/reporting how a table was read, might be useful."
- **How a table was read is traced** in each claim's derivation, and a finding between claims whose tables were read differently is flagged.
- **Every format's tables take this path:** Excel, CSV, Word, PowerPoint and PDF (PDF's structure: [0024](0024-pdf-table-structure.md)). The owner (2026-09-30): "I don't believe medium should be a severe differentiater here. A viable approach might be to logically turn our tables into CSV or XLSX or a shared intermediate representation with some model support (it seems PDF text extraction is doing a bad job of preserving table structure in many cases) then ensure we have a consistent processing model for tables from any source."
- **A row read by itself is read as the grid the rules saw holds it** (amended 2026-10-09; the [2026-10-08 review](../plans/README.md#retired), B2): wrapped lines joined, a one-cell row holding a number proposed as a note, confirmed by the rules query and read by itself. A confirmed note labels nothing: the rows below it take the section above. Unconfirmed, it stays a label; with no answer (the query failed or wasn't reached), it's read by itself.
- **A block of two columns may be a key-value list** (amended 2026-10-09 and 2026-10-10; the review's B5): a form's or data sheet's "Pump | P-2", "Flow | 95 L/s", not a table headed by its first pair.
  - **Our heuristic proposes:** two columns, the left one holding no number or date, the header not marked as one.
  - **The model confirms** (`keyvalue.py`), with the table's crop where there is one (PDF). The owner (2026-10-09): "you should still be asking a model (likely vision) to confirm the proposed 'rule' for reading a table."
  - Confirmed, its rows are read as "key: value" lines; else it's a table, as before.
  - A failed check uses our proposal, recorded partial; one not reached (the call limit, an answer a replay lacks) is asked on the next run, the block unread.
  - Sheets, CSV and Word, which nothing lays out, are checked by text alone; a PDF's with its crop (the owner, 2026-10-09, on both: "We can go with 1 and 2 decisions for now").
  - Named as document AI names the layout ("key-value pairs", as in forms extraction), at the owner's question (2026-10-09): "I'm not sure "pairs" is the best word here, it doesn't seem conventional and might confuse a model about what you're pairing, is there a more common naming for this layout?"
  - Asked of sheets, CSV, Word, PDF and, since 2026-10-10, decks.

## Consequences

- One query per table instead of one per row, with facts as good as row by row on the controlled corpus and conditions kept better.
- Two revisions of one table can be bound differently; the trace flags such findings rather than hiding them.
- Binding guidance (conventions, three worked examples) lives in one prompt and is tuned there.
- **Measured on the controlled corpus (2026-10-09):** rows from the grid changed only PDFs' claims (right 3287 → 3295, loose 426 → 416, misbound 203 → 205, hallucinated 6 → 8, on pseudo-tables). The key-value check's 35 answers on real tables and data sheets were all right, and Word and workbook data sheets' recall rose 0.947 → 1.0. Of 178 PDF candidates, 169 were phantoms, most a header cell PyMuPDF detects as a tiny table of its own ("Rating | (psi)"), so a block whose rows all repeat its header isn't one.
