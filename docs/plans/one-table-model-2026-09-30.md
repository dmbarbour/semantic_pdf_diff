# One table model for every source

- **Status:** Completed (2026-10-08): one way into claims for every format's tables (rules a model writes, applied mechanically, checked and reviewed), and PDF tables' structure from heuristics and structure rules. Decisions in force: [0023](../decisions/0023-tables-read-by-rules-a-model-writes.md), [0024](../decisions/0024-pdf-table-structure.md). Milestone 3's round against row queries waits with the [query rounds](query-improvement-2026-09-26.md); the remaining table levers are in the [lever index](../reviews/levers.md).
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

## PDF tables onto the rules path, in detail (2026-10-06), for the owner's review

**Where things stand:**
- Milestones 3 and 4 are built for every format with native cells: Excel, CSV, Word and slide decks (the [adapters plan](multi-format-adapters-2026-09-23.md), milestone 5 and after).
- Each table is asked how it's read (rules, rows, or a summary), and the rules are applied mechanically and checked.
- On the controlled corpus: one query per table instead of one per row, the same facts, conditions kept better.
- PDF tables are still read one row per query.

**What's different for PDF:** its cells come from a parser, and structure is where PDF tables fail:
- stacked tables merged
- wrapped cells split into rows
- header text cut
- misbinding in dense tables (sc01, the eye tests, the controlled tables' knobs)

**Proposed steps** (Claude's):
1. **PDF tables on the grid, no model:**
   - PyMuPDF's cells (each with its box, spans from merged cells) placed on the same grid Word and decks use
   - its header rows: PyMuPDF's detected header and today's same-form test
   - a table continued over pages joined into one grid (today's continuation logic), each row keeping its page and box
   - heuristic repairs:
     - a row with an empty first cell and text continuing the row above is a wrapped cell, merged up
     - a row with only its first cell is a section row
     - header cells keep their whole text
   - Claims made by rules are located by their page and row's box, as row claims are now.
2. **The rules query for PDF tables, with the table's image** (the owner's "clear visualization of tables when building rules"), and the vision check folded in (decision 1):
   - the query also transcribes one sample row from the image
   - a mismatch with the text layer is a hazard: that table's rows are read one by one, with the image
3. **Measured before going further:**
   - **The controlled PDF tables** (the treatment plant's and the coaster's schedules, with their knobs: stacked, multilevel, multi-value, dense, continued): rules against `--rows`, by the same keys. Their misbinding today is the target (the coaster's knobs: 9–20 misbound).
   - **A round on the development slices' real tables** (rubric v6), rules against row queries, with cost per table. The regressions to watch: sc01 items 1 and 4.
4. **Model repair of structure** (the plan's milestone 2) only where step 3 shows the heuristics and the image leave hazards: a query proposing restructuring edits (merge rows, mark headers and sections, split tables), checked so no text is added or lost.

**This reorders the plan:** repair was to come before the rules. Proposed: rules first, on heuristic grids with the image, because the rules query may absorb much of what repair was for, and the measurement says what's left.

**For the owner's review:**
1. **Repair after rules, and only where measured** (above), rather than a repair query for every table first. Proposed: yes.
2. **The table's image in every PDF rules query** (one image, about 260 tokens), rather than only for tables with hazards found. Proposed: always.
3. **The vision check folded into the rules query** (one transcribed row), rather than in a separate repair query. Proposed: folded in.

**Decided (the owner, 2026-10-07):** "The recommendations look good." Repair after rules, only where measured; the image in every PDF rules query; the vision check folded into the rules query. And a new lever, asked in the same breath: "is there a good way to show the model a few sample outcomes? Sort of an 'is this your final answer' opportunity? For tables, which are super-efficient due to rules-driven processing, this seems a cheap lever to add." (The adapters plan has its design and measurement.)

## Structure rules, in detail (2026-10-07), for the owner's review

**Where it comes from:**
- The image check (one row copied from the image) failed on 254 of 394 controlled PDF tables, almost all on structure: two-line headers split by the parser, not wrong cell text.
- On HabEx p4 (sc01 item 1), every row boundary the parser drew without a drawn rule under it is a false split: header lines, "µm" under "Wavelength bands", "CCD201" under "Detector", "resolution" under "Spectrometer". The table shades each text line with its own box, and the parser takes the boxes' edges as row lines.
- Rules drawn under row boundaries: corpus tables 108 all ruled, 17 mostly, 16 few or none; dev slices 10 all, 12 mostly, 140 few or none.
- **The owner (2026-10-07):** "this is closer to what I was imagining with regards to aiming image checks at suspects. The ability to get a 'pretty good' merge heuristically based on our samples is good. Ideally, we'd not provide the full table in bands for processing via vision, instead getting some comprehensible suggestions/rules about how to work around confusing formatting, with feedback similar to how we approach claims rules."

**Proposed** (Claude's):
1. **Heuristics, no model:** two-line headers merged and stacked tables split (`pdf_parts`); where most row boundaries are ruled, rows merged across the unruled ones.
2. **Suspects:** each remaining row boundary is scored by named signals:
   - no drawn rule under it, in a mostly ruled table
   - a text gap no wider than the line spacing inside cells
   - one cell's shading spanning both rows
   - the lower row's first cell empty, or only its first cell filled
   - the lower row holding only units, or only words under rows of numbers
   - a row half the usual height
3. **A structure rules query, only for tables with suspects,** before the claims rules query:
   - shown: the parsed lines, numbered, each with its signals as short tags (`12 | | CCD201 | CCD201 | LMAPD  [first cell empty; no rule above]`), the heuristics' proposal, and the image (the whole table, plus a crop around the worst suspects when the table is too large to read at the endpoint's fixed image size)
   - answered with rules from a closed vocabulary: a condition built from the signals ("first cell empty", "no rule above"...), or rows named as exceptions, and an action:
     - join the row above, cell by cell
     - join the header, as its next line or level
     - a section row over the rows below
     - a new table with its own header
     - a column holding two values split in two
     - not part of the table (read as text)
   - with two or three example rows as the model reads them in the image, one of them the worst suspect named in the question: the image check, aimed
4. **Applied mechanically and checked**, as claims rules are:
   - restructuring only, so no text added or lost (a split column checked to keep every character)
   - the examples compared with the rules' outcome; a mismatch is shown back once ("your rules give row 11 as ..., your example ..."); failing twice, the heuristic grid is kept and the table is marked
   - the review: the changed rows shown before and after, with the suspects no rule touched ("is this your final answer"), up to `table_review` times, ending when nothing changes
5. **Reported in how the table was read:** the rules in words, with the rows each changed.
6. **Measured:** the structure benchmark for the heuristics; a corpus run and HabEx p4 by eye for the query; the image check's failures before and after.

**For the owner's review:**
1. **A separate structure query before the claims rules,** rather than one query doing both. Proposed: separate; both are cheap, and each is checked on its own.
2. **Rules from a closed vocabulary, with named rows as exceptions,** rather than edits by row index (the design above, section 2). Proposed: rules, which read as reasons and apply to rows the model didn't single out.
3. **Only tables with suspects asked,** rather than every PDF table. Proposed: only with suspects.

**Decided (the owner, 2026-10-07):** "The recommendations look good, please proceed." A separate structure query before the claims rules; rules from a closed vocabulary with named rows as exceptions; only tables with suspects asked.

## Progress

- **PDF tables asked how they're read (2026-10-07): steps 1 and 2 built.** The owner approved the design above: "The recommendations look good."
  - **The build** (`tables.pdf_grid`; `extract.py`):
    - a detected table's cells placed on the grid, merged header cells spanning
    - **repairs:** a wrapped cell (a row with an empty first cell and no number) joins the row above; a section row labels the rows below
    - rows keep their boxes, and claims are located by them
    - **the rules query gets the table's crop** and copies one row from it; a disagreement with the text layer sends the table's rows to be read one by one, as before
    - a table continued over pages is read part by part, each part with the carried header, as before
    - reader version `pdf/2`; round 0's named configuration pinned to row by row (`table_rules: null`)
  - **The controlled PDFs (79 runs), asked against row by row:** facts read right the same (3,207 of 3,355), conditions the same (746 of 756), misbound 229 against 226.
    - **Better:** the multilevel tables (3 misbound to none), fewer stray claims in the attachment study
    - **Worse:** the energy study's revision (16 misbound against 9) and one plan pair (2 of 3 changes)
    - The coaster knobs' misbinding is unchanged, because most of their tables never reached the rules (next point).
  - **The vision check's finding.** Of the corpus's 394 PDF tables, 254 failed it and were read row by row:

    | | Same text, other cell boundaries | Text differs |
    |---|---|---|
    | Controlled PDFs | 204 | 40 |
    | Development slices (real) | 19 | 43 |

    - **Same text, other boundaries:** a word or header split across cells ("Entry | speed", "p | owers"), a two-line header parsed as a header and a first body row. Structure, not cell text: what step 4's repair is for. The heuristics merge wrapped body rows, not a wrapped header.
    - **Text differs:** mostly drawings and charts the parser took for tables (the real drawing sheets: dimension strings), and a few cells really misread.
  - **The development slices,** recorded for their replay fixture (repacked): 118 tables; 15 read by rules, 28 row by row by the model's choice, 67 failing the vision check, 2 answers malformed JSON (inch marks; read row by row).
  - Cost: $0.39 (the corpus $0.21 and its unaligned pairs $0.18), the slices $0.19.
  - **Next (step 4, "only where measured"; measured):** repair of cell boundaries. A table whose copied row has the same text in other cells gets its structure mended (cells joined, a wrapped header merged) from the image before the rules apply. A table whose text differs stays row by row.

- **PDF table structure (2026-10-07): steps 1 to 4 of the image-check follow-up, then structure rules.** The owner: "Please do. The cost is also negligible, so 1-4 is go."; then the structure rules above ("The recommendations look good, please proceed.").
  - **Offline benchmark** (Claude's; not committed): the corpus's true cells (row label, column label, value), 1,688 of them, found in the parsed grids:

    | Parser and repairs | Found |
    |---|---|
    | PyMuPDF as is | 0.907 |
    | a two-line header merged | 0.937 |
    | **parts: header merged, stacked tables split (`pdf_parts`; adopted)** | **0.966** |
    | parts, strategy `lines_strict` | 0.961 |
    | parts, PyMuPDF's `refine` | 0.951 |
    | parts, strategy `text` | 0.212 |
    | the layout add-on (`pymupdf-layout`), its own table detection | 0.057 |
    | the layout add-on's union with line detection | 0.963 |
    | parts and rows joined across unruled boundaries (adopted) | 0.966 |

    - PyMuPDF's detected header (`TableHeader`) gains nothing over the first row.
    - **The layout add-on isn't adopted** (a library choice, Claude's): its own detection misses nearly every generated table, its union with line detection is no better than the heuristics, and it brings 261 MB of dependencies (onnxruntime and others).
    - The remaining misses: cells holding two values ("2.58 0.69" under "g (vertical / lateral)") and the dense "all" knob.
  - **The heuristics** (`tables.py`; reader `pdf/3`):
    - `pdf_parts`: rows of labels (no digit) above rows of numbers join the header, as a second level under merged cells ("Rated point > Capacity (gpm)") or as its next line; a row of labels styled as the header (fill or bold) starts a stacked table; empty rows between header lines dropped, others kept in place
    - `ruled_rows`: where 3 or more, and 40% or more, of a table's row boundaries have a rule drawn under them, rows are joined across the others; two rows both labelled with a digit in one column stay apart. **HabEx p4 (sc01 item 1) now reads as printed:** two tables (cameras, spectrometers), "Detector | 1×1 CCD201", "Spectrometer resolution | 7". On the development slices it joined rows in HabEx p4 and p8 only, both right; every other table it changed is a chart or drawing that `real_table` rejects (the table filter, off by default, would drop them; with it off they're read as before, joined).
    - `Marks`: a page's rules, fills and text styles, read once (pages without rotation)
  - **The image check copies a row of values** (a number in it), not a header line.
  - **The controlled PDFs, measured after the header merge and the aimed check** (before the structure query):

    | | Before | After |
    |---|---|---|
    | tables failing the image check | 254 of 394 | 111 of 409 |
    | misbound, read by rules | 229 | 203 |
    | misbound, row by row | 226 | 199 |
    | facts read right | 3,207 | 3,207 |

    - Of the 111 left: 68 the same text in other cells (columns cutting through words: "7. | 4", "speed ( | mph)"), 37 other text (mostly floor plans and chart legends taken for tables), 6 a row that isn't the table's.
  - **The structure query** (`tablestructure.py`, `table_structure`; the design above):
    - **The development slices:** 96 table parts asked, most on drawing sheets' title blocks. 15 rules used, 42 answered "not a table", 19 failing twice (the heuristics kept). On the real reports every "not a table" answer is a chart the parser took for a table (the turbine plots, a scoring figure).
    - **HabEx p7, by eye:** the two-line header joined, a spacer line dropped, each "(science)" or "(guide)" line joined to its row; the rules then read all 9 values right ("UV Science | IR bandpass | 1.6–1.8 μm | mode guide").
    - **Mended after the first recording:** H named among a rule's lines is ignored (it failed 25 parts); rules leaving no rows keep the heuristics without asking again (the model reads no table there); examples are compared by each row's whole text, cells parted otherwise in the image noted, not failed (row grouping is what's checked).
    - **Bugs found on real pages:** line numbers given as numbers; a late answer read by the next page's table (its continuation looked up by name when it came; now bound when asked; a test holds it).
  - **Claims rules' checks, from the same pages:** an example parting value and unit otherwise than its cell (10.2 and ″ against 10.2″) passes; `{B.cell_value}` names the cell.
  - **The controlled PDFs with everything** (fresh stores; against the last commit):

    | | Last commit | Now |
    |---|---|---|
    | misbound, read by rules | 229 | 209 |
    | misbound, row by row | 226 | 199 |
    | loose (rules) | 472 | 434 |
    | facts read right | 3,207 | 3,207 |
    | conditions kept | 746 of 756 | 746 of 756 |
    | tables failing the image check | 254 of 394 | 114 of 408 |

    - The PDF revision pairs are found exactly as before (changes 26 of 27 by rules, 27 of 27 row by row; additions, removals and unchanged facts alike; no false changes).
    - 209 against step 4's 203: the joined rows (6 tables), the styled stacked-table test and the answers asked again; not traced further.
    - **The structure query on the corpus:** 40 parts asked, nearly all floor plans, charts and diagrams taken for tables; 20 answered "not a table", 5 restructured, the rest failing twice (dimension strings and legends that no row grouping makes a table). The one real table asked (the attachment study's sequence) fails on columns cutting through words ("1. P | robe Request").
  - **Cost:** the corpus $0.23 (step 4) and $0.04 (the final run); the slices $0.29 and $0.08; the HabEx trials a few cents.
  - **Next** (candidates, in the lever index):
    - a part the model calls "not a table" read as a figure instead (the turbine plots)
    - a "join columns" action (the model asked for one) and columns cutting through words, the corpus's remaining image-check failures
    - title blocks on drawing sheets kept out of the table path

- **Table levers from the plans review (2026-10-07 and 08).** The owner, on the next steps: "Okay, please proceed with the recommended direction. 2 is OK, IMO. So just pursue 1-5 in whatever order makes the best sense." Each measured on the controlled corpus against the run before it (facts read right 3,207 throughout):
  - **A part the model reads as no table, read as a figure** (reader `pdf/4`): its lines aren't read as a table; a figure task reads it, unless the overview, a figure task or one tile already sees it whole. Of 20 such parts, 8 went to a figure task, 10 were seen whole by a tile, 2 by a figure task. Misbound 209 to 207, loose claims 434 to 421 (rules); a floor-plan pair's changes 2 of 3 to 3 of 3.
  - **Columns cutting through words** (reader `pdf/5`):
    - **First version, the model's:** a signal for a word a column line cuts and a "join columns" action. The model often joined the wrong columns ("360" and "738.9" for a cut between their neighbours), and the signal sent floor plans to the query; whole-text examples couldn't see a join in the wrong place. A guard (two of a row's values joined only across a cut) didn't rescue it.
    - **Adopted, mechanical first:** columns are joined at detection where every row with text on both sides has a word cut at that boundary (`tables.cut_columns`: "7. | 4" is "7.4", "Base elev. (" and "ft)" one header); a cut counts as a suspect only where it parts text across two filled cells (`split_cuts`); the model's "join columns", with the guard, sees only what's left.
    - Measured: image-check failures 114 to 96 (same text in other cells 68 to 64), hallucinated claims 7 to 6 (rules) and 11 to 6 (row by row); misbound and misread unchanged; true cells found offline 0.966 to 0.967. One floor-plan pair back to 2 of 3 changes; one attachment pair better and worse by one.
    - **A misreading of mine, corrected:** fewer "right" claims on some documents (coaster 125 to 111) are fewer duplicate claims; facts found right were unchanged on every one.
  - **Three binding levers in the rules query** (the lever index's table-handling rows):
    - a heading's or slide's title the table sits under isn't a condition: the treatment plant's deck pair now confirms every unchanged fact (30 of 31 to 31 of 31)
    - a tolerance or uncertainty column becomes its value's `uncertainty` (a template field): the synthetic commissioning table's "118 L/s" carries "± 3 L/s", where the column was left out before
    - columns keeping the document's own records (who submitted a row, their ID, when it was entered, a sort order) give no claims: the RAN1 document list reads as a list summary, 113 claims where there were 30,121
    - The other formats' scores unchanged; PDF misbound 207 to 205, loose 418 to 426.
    - **The image check's failures rose with it, 96 to 121,** every new one on a lone header cell the parser took for a table of its own ("Raw | water | pumps"), whose header text the model now copied. **The check now compares a row of values only** (a digit in it; what it asks for): failures 24 of 399, two of them the same text in other cells. Scores unchanged. So most "same text in other cells" failures all along were such header cells, not real tables.
  - **Cost:** the corpus $0.01, $0.05, $0.03 and $0.30 (the prompt change re-asks every rules query); the workbooks' checks a few cents.

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
