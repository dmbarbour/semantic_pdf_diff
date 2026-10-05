# One table model for every source

- **Status:** Planned (2026-09-30), for the owner's review.
- **Depends on:** [multi-format adapters](multi-format-adapters-2026-09-23.md), whose *Tables and spreadsheets* design this generalises; [query improvement](query-improvement-2026-09-26.md), whose rounds measure it; [content-addressed queries](content-addressed-queries-2026-09-28.md) (recorded, replayable queries).
- **Feeds:** the multi-format plan's `.csv`/`.xlsx` milestone (and later `.docx`/`.pptx` tables); the [lever index](../reviews/levers.md) (its table rows fold into this plan).
- **Why:**
  - **The owner (2026-09-30):** "I don't believe medium should be a severe differentiater here. A viable approach might be to logically turn our tables into CSV or XLSX or a shared intermediate representation with some model support (it seems PDF text extraction is doing a bad job of preserving table structure in many cases) then ensure we have a consistent processing model for tables from any source."
  - **And on building the rules:** "that's based on our prior discussion of how to process tables, e.g. for CSV or .xlsx files. We ask a model how to turn table rows into claims, and we might look for exceptions to this"; "Perhaps we need clear visualization of tables when building rules in cases like this? Clear identification of hazards, too."
  - **The evidence:**
    - [Spot check sc01](../reviews/spotcheck-sc01-2026-09-30.md), item 1: a stacked table's second header row was lost, header cells were cut short, and wrapped cells arrived as unlabelled rows, so values were bound to the wrong table.
    - The [eye tests](../research/eye-tests-2026-09-30.md): gemma-4 misbound values in dense tables it could read.

## Goal

- **One representation of a table, whatever its source:** a grid of cells with spans, header levels, section rows, notes and units, where every cell keeps its place in the source.
- **One way of turning it into claims:** a model looks at the whole table, clearly shown with its hazards named, and writes the rules: which cells give each claim's entity, attribute, value, unit and conditions. The rules are applied mechanically, checked, and the rows they don't fit are read one by one.
- **The medium doesn't change the answer:** the same table as a PDF, a CSV file or a spreadsheet gives the same claims.

## Today

| | PDF (built) | Spreadsheets and CSV (planned, not built) |
|---|---|---|
| Structure | PyMuPDF's `find_tables`: rows as extracted, the first row as the header, continuation across pages, a filter for real tables | Explicit cells; regions found heuristically, with a sheet map and warnings when a sheet may hold several tables |
| Interpretation | None at table level | A model writes a row-to-claims mapping and picks a strategy: iterate, per-row, or summarise |
| Claims | One query per row (split by columns when too wide), with one header row, the lead-in text and stems as context | The mapping, applied mechanically; rows it doesn't fit are read one by one |
| Failures seen | Stacked tables merged; wrapped cells split into rows; header text cut; misbinding in dense tables | — |

## Design

**1. The table representation** (`tables.py`; a strict model in `models.py`):
- **Grid:** rows of cells, each with its text, its row and column span, and its locator:
  - a PDF cell's page and box
  - a spreadsheet's sheet and cell
  - a CSV file's line and field
- **Structure:**
  - header rows, possibly several levels, so each column has a label path (`["Cameras", "UV Channel"]`)
  - section rows, which label the rows below them until the next section (`Spectrometers`)
  - the row-label column(s)
  - notes and footnote markers
  - a caption or title, and the text just before the table (today's table lead-in)
- **Parts:** a table continued over several pages or sheets, as one table with its parts.
- **Hazards,** named for the model and for people: stacked tables, wrapped cells, empty row labels, merged cells, multi-level headers, units in headers, cells holding several values (`1×1 CCD201`), totals rows, blank separator rows, continuation, and rows of irregular width.
- **Provenance:** how the structure was obtained (native cells, the PDF parser, heuristic repairs, a model's repair), as derivation steps.
- **Renderings:** Markdown or HTML for prompts, with header levels, section rows and hazards marked; and the same beside the source's crop, for query dumps and review pages.

**2. PDF tables into the representation:**
- **Text comes from the text layer, structure from the parser, heuristics and a model.** Cell text is never retyped by a model, so a model can't misread a value into the grid.
- **Heuristics first** (no model call):
  - merge a row with an empty first cell into the row above (wrapped cells)
  - find section rows, which are styled (a fill drawn under them, bold text) and repeat the column labels' form
  - keep whole header text
  - use PyMuPDF's detected header (`TableHeader`) where it differs from the first row
- **Model repair, one query per table:** the model sees the table's image beside the parsed grid, and returns edits by row index:
  - merge row *i* into row *i − 1*
  - row *i* is a header row (level *k*) or a section row
  - split the table before row *i*
  - column *j* labels the rows
- **Mechanical checks:** edits only restructure existing cells, so no text can be added or lost. A repair that leaves hazards unresolved is recorded, and those rows fall back to row-by-row reading.
- **Checking the cell text by vision** (the owner: "Perhaps assume it is, but verify at least one row via vision"):
  - The repair query also transcribes at least one row from the image: the first body row, and a row with symbols, units or the longest cell.
  - Compared with the text layer's cells (folded for case, whitespace and dash and quote forms), a mismatch is a hazard ("text layer and image disagree"). The table's rows are then read one by one with the image, and the case is kept for review.
  - Hazards found this way include missing glyphs (∂, θ, ±), ligatures, text drawn as outlines, overlapping text, and a column read out of place.
- **Scans without a text layer** stay with the vision tiles for now.

**3. Spreadsheets, CSV, and later `.docx` and `.pptx` tables:** their adapters fill the same representation. Cells and spans are native; regions come from the multi-format plan's region detection and sheet maps. Their hazards are the same list.

**4. The table's rules** (the interpretation; one query per table, or per section when sections differ):
- **What the model sees:** the rendered grid with its hazards named, a spread of rows (the first, some from the middle and end, and any that look different), the caption and lead-in, and for PDFs the table's image. This is the owner's "clear visualization of tables when building rules".
- **What it returns:**
  - **A layout:**
    - items in rows (an equipment schedule)
    - items in columns (the HabEx camera table: properties in rows)
    - cases (an operating-point table: inputs and outputs)
    - a two-way matrix
    - free text (a cell needs reading)
  - **Roles:** where the entity, attribute, value, unit and conditions come from: a column, a row label, a header path, a section row, the caption, or a constant.
  - **Composites:** composite columns (value ± uncertainty; min, nominal, max) and cells holding several values.
  - **A strategy:** iterate (apply to every row) or per-row (read each row). Summarise (statistics over columns, marked derived) is deferred.
  - **Example claims** for three sample rows.
- **Applied mechanically:**
  - Each claim's quote is its cells' text, and its locator the cells' boxes or references.
  - Its derivation says "mechanical read under a model's rules for this table", with the rules kept beside the table.
- **Checked:**
  - the rules' claims for the sample rows must match the model's example claims
  - values parse where the rules say numbers
  - units stay constant where the rules say so
  - rows that fail are read one by one, and a high failure rate sends the table back for new rules
- **Recorded:** repair and rules queries are recorded by query hash like every other, so replays are free and rounds can compare them.

**5. Measurement:**
- **Table eye tests:** synthetic tables with random content and known structure, drawn as PDF pages and written as CSV and XLSX, like the [eye test](../research/eye-tests-2026-09-30.md)'s cards. The hazards are the variables: stacked tables, wrapped cells, multi-level headers, transposed layouts, operating-point tables.
  - Scored exactly, with no judge: structure recovered (header rows, section rows, merged rows) and claims against the answer key.
  - **The medium test:** the same table's claims must be the same from every medium.
- **The synthetic workbook and CSV** already have answer keys (regions, header rows, composite columns, strategies).
- **Real documents:** a round with a `table_model` setting (`rows`, today's, against `rules`), judged with rubric v6 and spot-checked.
  - The regressions to watch: sc01 item 1 (HabEx p4) and item 4 (NREL 5 MW p10).
- **Cost:** queries and tokens per table. Two queries per table (repair and rules) against one per row: HabEx p4's two tables cost 20 row queries today.

## Milestones

1. **The representation, the PDF heuristics and the table eye tests.**
   - No model calls yet.
   - The rendering is shown in query dumps beside each table's crop.
   - Measured by structure recovered on the synthetic tables. A query snapshot shows which real row queries change when wrapped rows merge.
2. **Model repair of PDF table structure,** with its mechanical checks and the vision check of cell text. Measured on the synthetic tables and on the real tables of the development slices.
   - **Is cell text adequate?** The owner: "we should generally investigate whether cell text is adequate." Every development-slice table gets its sampled rows transcribed by vision, and the disagreements are counted per document and per kind of hazard. That rate decides whether one checked row per table is enough.
3. **The rules and their mechanical application,** with checks and row-by-row fallback. Behind the `table_model` setting, judged in a round against today's row queries.
4. **Spreadsheets and CSV through the same path** (the multi-format plan's `.csv`/`.xlsx` milestone), with the medium test. `.docx` and `.pptx` tables follow those adapters.

## Relation to other plans and levers

- **The multi-format plan's *Tables and spreadsheets* section** is kept for what is specific to spreadsheets: formulas, hidden sheets, external links, sheet maps. Its model-guided interpretation becomes this plan's rules.
- **Lever index rows that fold in here:**
  - repair table structure (milestones 1–2)
  - bands of rows with the full header block (the per-row fallback reads bands, not single rows)
  - the table's image with its text (milestone 2's repair, and the rules query)
  - showing the model the table clearly, with its hazards, when it builds the rules (milestone 3)
- **Levers that stay as they are:** entity against conditions in the instructions (the rules query gets the same guidance), and captions as context.
- **Today's table levers carry over as context providers:** the lead-in (`table_context`), stems, and the real-table filter.

## Decisions (2026-09-30)

1. **Cell text comes from the text layer, checked by vision.** The owner: "I think we should generally investigate whether cell text is adequate. Perhaps assume it is, but verify at least one row via vision? Something to gain confidence."
   - The repair query transcribes sample rows from the image, and disagreements are hazards (design item 2).
   - Milestone 2 measures how often they occur. Scans stay with the vision tiles for now.
2. **A case table's default claims:** one claim per output cell, with the row's input cells as conditions. The owner: "default claims seem fine, esp. if we can recognize the "input" conditions, but I'm not sure how we'd recognize which columns represent entites or input conditions without already asking a model for a claims rule."
   - **Recognising inputs:** they can't be told apart without a model. The rules query is where the model classifies the layout and each column's role (entity, input, output, unit).
   - **The default** is guidance in that query: for a case table, one claim per output cell with that row's inputs as conditions. It isn't something found before asking.
   - **Heuristics as hints only:** evenly stepped values in the first columns (wind speed 14, 15, 16…) look like inputs. They're shown to the model as hints and never decide alone.
3. **Summarise is deferred.** The owner: "we can defer summary strategies if that's the plan." The plan builds iterate and per-row first. Summarise comes after milestone 4, if long logs turn up.
   - **Revisited (2026-10-04),** when Excel's real tables brought long series (the adapters plan, "Excel, in detail", decision 1). The owner: "ask a model how to handle the table ... report number of claims and our own heuristic opinion (summary vs. point per claim) based on size and a short analysis of rows ... then ask the model how to handle it, i.e. whether how to produce claims from rows or how to summarize things within a few known templates." Summaries come with the rules, chosen by the model among known templates.

## Open questions

None at present.
