# How it works

This describes the current code: comparing two sources (files, folders, zip archives) through a persistent store, with evidence in the content-based schema v2. Criteria-first comparison and more formats are planned in [plans/](plans/README.md).

## Claims and provenance

All modalities become atomic claims with `entity`, `attribute`, `value`, `unit`, `conditions`, `kind`, `quote`, `confidence` and `approximate`, plus context fields (`topic`, `basis`, `uncertainty`, `context`, `role`) that prompts don't request yet and so default to "not stated". A chart operating point can therefore match a table row, and a diagram connection can match a sentence.

Provenance (schema v2):

- Each comparison object is a **source**: a name, provenance metadata and roots (files, folders, zip archives). Scanning its roots yields **files** (archive members as `bundle.zip!/inner.pdf`), each referring to **content**: the SHA-256 of its bytes plus its normalized extension (`sha256:…​.pdf`). Files without an extension get a bare hash and are never interpreted; only `.pdf` content is extracted so far.
- Content present in both sources, or several times within one, is extracted once; reports list every occurrence.
- Evidence attaches to content, never to paths. Each item has a **locator** within the content (one-based page, bounding box in unrotated PDF points, the extraction pass and task) and a **derivation** listing the steps from bytes to claim. Visual claims retain the exact PNG the model saw.
- A piece of evidence is a **claim within one piece of content**. Its ID derives only from the content and the claim's identity (entity, attribute, value, unit, conditions, `approximate`, basis), so it is stable across renames and doesn't depend on the order in which tasks ran. Every sighting of the same claim (by text, table, tile or overview passes, on any page) is kept as an **occurrence**; displays use one representative occurrence (native before visual, tile before overview, then the smallest region), and reports say how many times and by which passes a claim was found. The same PDF supplied as both sources is extracted once; its evidence is listed as *shared* and never sent for comparison.
- `evidence.json` and `report.json` record the **interpreters**: the model, a hash of the prompts, the settings that affect output, and library versions.
- Everything is kept in an evidence **store** (the `--out` folder); see [configuration](configuration.md) for reuse, resume and binding.

## Pipeline

Extraction of all compared sources shares one queue: pages are fed round-robin across sources, so they advance together, and model requests run concurrently (see [configuration](configuration.md)). Work cut off by `max_calls` is recorded as `not_reached` and resumed on the next run.

0. **Sections:** each PDF is divided into sections from its outline (bookmarks) down to `section_depth` levels, or into `section_pages`-page ranges if it has no outline. Every prompt carries the section's heading path (e.g. `Section: Design > Pumps`), and every claim records its section. Sections also collect cheap signals (numbers, units, requirement words, tables, images, vector drawings, characters) for later triage.
1. **Native extraction:** Consecutive PDF text blocks are grouped up to the UTF-8 byte budget (oversized blocks are split), so headings and short labels travel with their context; each claim keeps the bounding box of the block containing its quote. Detected tables are sent row by row with the first row repeated as a provisional header; rows with no content are skipped. A table row repeated exactly (same cells, same table position) on three or more pages, typical of drawing title blocks, is sent only while the repetition is unproven; later repeats reuse the first occurrence's claims and are listed in the coverage record as "identical to … not re-sent" (`dedupe_repeated`). Text is never de-duplicated. A table at the top of a page, as wide as one that ended at the bottom of the previous page, is treated as its continuation and gets that header (unless its own first row is a header of the same form, i.e. a new table); rows over budget are split by column, repeating the header and the first column as a provisional row label. Native claims whose supporting quotes are absent from the input are rejected; table quotes may span adjacent cells.
2. **Visual extraction:** Every page receives evenly spaced overlapping tiles (at least 18% overlap) and an overview. This includes scanned pages and vector diagrams that embedded-image extraction would miss. The same small model reads labels, graph axes and series, table relationships and diagram connections. Approximate graph readings remain explicitly approximate. Where the rendered region has a PDF text layer, each visual quote is checked against it and the result is recorded as `quote_verified` (`false` flags a possible misread or a raster-only label; it does not reject the claim).
3. **Bounded refinement:** Partial/failed text groups are split on block boundaries (single blocks by bytes); partial/failed table rows are split by column, keeping header and row label; partial/failed visual tiles are subdivided. All are bounded by `refinement_depth`. Original failures remain in the coverage ledger even if smaller tasks succeed. Nothing silently declares exhaustive coverage.
3a. **Situating:** after a PDF is fully extracted, a separate stage places its parts in context. Figures and tables are found mechanically (image blocks and dense vector-drawing clusters paired with captions such as "Figure 3:", "Table 2"); a drawing sheet is one figure labelled from its title block (e.g. `S-701`, "PV DETAILS"). The paragraphs that cite each figure are found too, and claims inside a figure's region are attached to it. Every figure then gets one request with its location (page, position, section), caption or title block, the text around it, the paragraphs citing it, its claims and an image, for what it depicts, why it's there and any label printed in it. Labels the model reads resolve outstanding references, and figures that gain citations are asked once more. Each section then gets one request (heading path, text, claims, its figures' "abouts", and up to three page overviews if it is diagram-heavy) for its type, information density, keywords and a value-free "about" statement. Results are stored per content and reused; claims are never changed. Mechanical quality checks run on every run and are reported, never applied: the share of figure references that resolve, values (numbers with units) in an "about", "about" terms not found in the material it was given (possible invention), odd lengths, and sections with claims but no "about". `--no-situate` skips the stage.
4. **Global retrieval:** Sparse TF-IDF over normalized claim entities, attributes, conditions and values generates a bidirectional top-k union. Claims can match across pages, order, layout and modality, with one-to-many matches. User-provided domain aliases improve synonym recall. No model holds the full corpus.
4a. **Alignment (revisions mode):** before any value is judged, each revision's claims are grouped into items (a tag such as `P-101B`, else the entity's words), and items are matched across the revisions by shared values (rare ones counting more), names whose identifiers agree, and attributes: best first, one counterpart favoured, and only with a margin over the next candidate. Near-ties go to the judge; an item with no counterpart is added or removed and isn't compared. Within matched items, equal values whose readings agree on conditions are settled as equivalent without a model, and the rest are paired by attribute for the judge. Leftover items whose names share a stem, one on one side and two or more on the other, are split or merge candidates, with whether their values add up; they're shown, not compared claim by claim. The report's groupings section shows every group alignment formed, with its evidence and outcome, as alignment saw it. Proposal mode keeps retrieval. See [the revision comparison plan](plans/revision-comparison-2026-10-02.md).
5. **Local comparison:** One claim pair per request, with source images where available. The model distinguishes equivalent, different, complementary, unrelated and uncertain. A deterministic decimal calculator checks supported unit conversions. Unestablished conditions, approximate readings, low confidence or inconsistent arithmetic veto confident difference/equivalence judgments.
5a. **Explaining differences (revisions mode):** each "different" or "uncertain" finding gets a second request naming the kind of difference: a value changed, its conditions changed, renamed, moved, restated, split or merged, misread, not the same item, or unclear. It's sent both claims with their sections and crops, the judgment, each claim's item (its other claims in its revision), and the claims of the other revision that still, or already, state each value: members of one list, numbered conditions and two items of one kind show up there. The report counts differences by kind (value changes, editorial changes, not changes) and lists the value changes first. See [the revision comparison plan](plans/revision-comparison-2026-10-02.md), milestone 4.
6. **Review report:** Filter/search findings, inspect both sources, review numeric checks, unmatched evidence, provenance and task-level coverage. No model-generated global summary is needed.

## Text files and Word documents

`.txt` and `.md` files are read by a text reader (`textdocs.py`) through the same task core as PDFs (`tasks.py`): the same prompts, quote checks, context levers and refinement. Word documents (`.docx`, with the `office` extra) are read into the same form by `docxdocs.py`: each paragraph and table row a line, headings by style (`Heading N`), tracked changes applied, the table of contents left out. Tables are read on their grid: a cell merged down repeats in each row it covers, a cell merged across is asked under its columns' labels, a small nested table is written into its cell and a large one read on its own, and a table used for layout is read as paragraphs. A text box's paragraphs follow the paragraph anchoring it. A chart is read from the values it caches (`chartxml.py`), as a table of categories by series after a line naming it. Equations are written as linear text where they stand (K_offset, (a+b)/c), and each comment follows the paragraph it comments on, naming its author and the text it's about.

Slide decks (`.pptx`, with the `office` extra) are read as Word documents are, by `pptxdocs.py` (no slide is drawn: no renderer is assumed): each slide a page and a section, titled by its title (or subtitle, or a short text box at its top); its shapes' paragraphs in reading order, top to bottom and left to right, a group's together; tables on their grid; charts from their data; pictures with the slide's title as caption; speaker notes after the slide's content ("Speaker notes: ..."). A slide drawn with shapes joined by connectors is recorded as read for its text, not its arrangement. Claims are located by slide and line (`PptxLocator`).

Excel workbooks (`.xlsx`, `.xlsm`, with the `office` extra) are read by `xlsxdocs.py`: each sheet a page and a section, named by its sheet; its regions found (Excel's defined tables, then blocks of filled cells parted by blank rows and columns, a title or label-and-value rows over a table split off); cells as Excel shows them (cached values in their number formats; a formula without a cached value is marked, never evaluated); tables on the grid; a block that looks like two tables pressed together recorded as skipped. Each table, whatever its length (`table_rules` 0; a size from which to ask, or none for row by row), is read as a model says it should be (`tablerules.py`): one query shows the model the table's columns with a mechanical analysis of their cells (numbers, dates, text, empty; ranges, an even step, prose), sample rows, the text above the table, the claims a point per cell would give and our heuristic opinion (a summary weighed by size, without a cut-off), and the model answers with a reading: templates of a row's cells applied to every row mechanically, checked against its own example claims (a row they don't fit read by itself); every row read by itself; or a summary by a known template (series: an input's range and step, each quantity's extremes and values at named points; log: span, extremes, mean and last; list: counts by category), computed and marked derived. A tolerance column becomes its value's uncertainty ("± {D} {C.unit}"), columns keeping the document's own records (who submitted a row, when, a sort order) give no claims, and the heading or slide title a table sits under isn't a condition. Rules that fail their checks are asked for once more, then the rows are read one by one. Comments, charts and pictures as in Word; hidden sheets read and marked. Claims are located by sheet and cells (`XlsxLocator`). Their claims are located by paragraphs (`DocxLocator`).

Images (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`, `.bmp`, `.gif`; reader `image/1`) are read as one-page documents by the PDF reader (`extract.image_pdf`; a TIFF's frames as pages): with no text layer, its overview and tiles read them, as a scanned page is. A scan recording 150 dpi or more keeps its paper size; any other image (a screenshot, a photo, one without a resolution) is laid out so a tile shows its pixels one to one (`tile_points` against `image_side`), so a large photo gets more tiles rather than less detail. Claims are located by page and box in the page's points. An unreadable image is recorded as failed to open. In a folder source, images are read like any other file.

CSV files (`.csv`, `.tsv`; no extra needed) are read as one-sheet workbooks of text cells (`xlsxdocs.read_csv`): the delimiter sniffed (comma, semicolon, tab or bar), UTF-8 or else Windows-1252, fields as written; preamble lines read as text and blocks parted by blank lines as tables, each table asked how it's read as a workbook's are. Claims are located by the file's lines and fields (`CsvLocator`; a quoted field may span lines).

Word and PowerPoint tables take the same path: their grids (merged cells spanning, header rows labelled by path) are asked how they're read as a workbook's tables are, each named for the query ("table 3", "slide 2, table 1"; a slide's title is its table's title). A chart's data is still read row by row.

PDF tables take the same path, from the parser's cells (`tables.py`, `tablestructure.py`; reader `pdf/3`):
- **Heuristics, no model:**
  - where most of a table's row boundaries have a rule drawn under them, rows are joined across the ones that don't (lines of one row the parser split, e.g. where each text line has its own shading box); two rows both labelled and both with a digit in one column stay apart
  - a header over two lines merged (a second level, "Rated point > Capacity (gpm)", under merged cells)
  - a stacked table split off: a row of labels over rows of numbers, styled as the header is (its fill or bold)
  - columns joined where every row with text on both sides has a word cut at their boundary ("7. | 4" is "7.4")
  - a wrapped cell (an empty first cell, no number) joined to the row above; a lone first cell a section row
- **The structure query** (`table_structure`), only for a part with a suspect line: each line tagged with its signals (no rule above it in a mostly ruled table, an empty first cell with values, a lone label, units alone, fewer words under numbers, half height, a word a column line splits), the table's image attached. The model answers with rules from a closed vocabulary (a condition from the signals, or lines named, and an action: join above, join the header, a section, a new table, not the table, keep, split a column of two values, join columns where a word is cut: a body row's separate values are never joined) and two or three rows copied from the image, one the worst suspect's. The rules are applied mechanically (cells are regrouped, never retyped), the examples checked against what they give (a mismatch shown back once, then the heuristics kept), and the outcome reviewed as claims rules are. The rules, in words, go into each claim's derivation. A part the model reads as no table (a chart, a floor plan) isn't read as a table: a figure task reads it, unless the overview, a figure task or one tile already sees it whole.
- **The rules query** then gets each part with the table's crop, and copies a row of values from the image: a disagreement with the text layer sends the part's rows to be read one by one (a copied row without a value, a lone header cell parsed as a table, checks nothing).

Once a table's rules pass their checks, the model is shown what they gave for three rows (or a summary's claims) and asked whether that's its final answer: it keeps them, or gives corrected rules, which pass the same checks and are shown again, up to `table_review` times (10); a revision changing nothing ends it, and the last rules passing the checks are used. The outcome is recorded with each claim.

How a table was read is traced: each claim from a table says whether its table was read by rules (and the template that made it), by a summary, or row by row, and a comparison between claims whose tables were read differently is flagged (`tables_read` in `report.json`; a warning in the report): a difference there may come from the reading, not the source. A table's rules are asked per document, never shared between revisions.

A Word document's pictures are read as a PDF's figures are (`pictures.py`). Each picture becomes a page at its displayed size:
- **EMF or WMF** (most technical figures: Visio and chart-tool previews) is drawn by `metafiles.py` from the vendored metafile renderer's playback. Paths are vector, clips are computed, and text is set in PDF's built-in fonts, so the page draws alike on every machine and its labels are a text layer.
- **A raster image** is placed as it is.

The page gets a PDF page's image tasks (the whole picture, and tiles when it's large). Each task has the picture's caption as source text, its text layer as context and as a check on quotes, and its section's headings. Its claims are located at the picture's paragraph, with their crops. Drawings without a picture, and charts of the newer kinds, are recorded as not read. Content read by an earlier version of its reader is read again on the next run, unchanged queries replaying from the cache ([decision 0016](decisions/0016-content-reread-when-its-reader-changes.md)).

- **Pages:** a form feed starts one (as in RFCs); otherwise the file is one page.
- **Sections:** from Markdown headings, or numbered headings in the RFC style ("7.2.  Stream Concurrency"); failing those, fixed page ranges.
- **Text tasks:** paragraphs, grouped up to the byte budget, kept as laid out: text written for a monospace font, its arrows and simple structures, reaches the model as written.
- **Table tasks:** Markdown pipe tables, row by row with their header.
- **Page furniture:** a line repeated near the top or bottom of three or more pages is left out.
- **Not read:** linked images (recorded as skipped).
- **Locators:** a claim's locator is its page and line range (`TextLocator`); reports show the lines where a PDF claim shows its box.

## Modes

Evidence from content present in both sources is **shared**: listed once, never compared with itself, but used as a retrieval target, so a claim in changed content whose counterpart sits in shared content isn't reported as unmatched. Reports also summarize the **file-level difference**: files unchanged, modified (same relative path, different content), moved or renamed (same content, different path), added and removed, with paths compared relative to each source's roots (so `rev1/x.pdf` lines up with `rev2/x.pdf`).

Proposal mode is symmetric and does not rank teams. Revision mode labels A as earlier and B as later; numeric deltas are B minus A. Neither mode calls unmatched evidence a proven addition/deletion. Absence is harder to establish than a local difference.

## Model output handling

Model output is validated; unknown keys are ignored, individually malformed claims are discarded (the task is then marked partial), and malformed/truncated responses are retried and ultimately recorded as failures. Fenced or prose-wrapped JSON is accepted. Exact duplicate claims within the native or the visual passes on one page are kept once.

## Code map

| Module | Responsibility |
| --- | --- |
| `schema.py` | What the pipeline reads and writes: claims, locators, model answers, evidence, coverage rows, the report documents (imports no other module) |
| `settings.py` | Settings: the endpoint's beside the platform the levers compose, loaded from the environment, a file and a caller |
| `llm.py` | Compatible API transport, request budgeting, retries and cache |
| `jobs.py` | The extraction scheduler (a page at a time, sources in turn) and the readers by extension, with their versions |
| `extract.py` | The PDF job: a PDF's text, tables, figures and tiles made into tasks |
| `visuals.py` | Image tasks: a region rendered to a crop, its text layer and context, a partial tile refined in halves |
| `figures.py` | Figures found on a page: captions, drawing clusters and images paired with them, drawing sheets; figure labels |
| `situate.py` | The prose citing figures and the claims inside them; figure and section "about" requests |
| `tasks.py` | The task core every reader shares: the extraction prompt, requests, quote checks, evidence, coverage, refinement |
| `textdocs.py` | Plain text and Markdown: pages, sections, paragraphs and pipe tables, line locators |
| `docxdocs.py` | Word documents read into the text reader's form: paragraphs, headings by style, tables, tracked changes, pictures |
| `pptxdocs.py` | Slide decks read into the text reader's form: slides as pages, shapes in reading order, tables, charts, pictures, speaker notes |
| `xlsxdocs.py` | Excel workbooks and CSV files read into the text reader's form: sheets as pages, regions and the sheet map, cells as Excel shows them (a CSV's as written), tables on the grid |
| `tablerules.py` | A table read by rules a model writes for it: the column analysis and our opinion it's shown, the rules applied to every row and checked, the summary templates |
| `tablestructure.py` | A PDF table's lines grouped into rows by rules a model writes where the heuristics leave suspects: the signals, the rules applied and checked against rows copied from the image |
| `chartxml.py` | Charts stored as chart XML (Word's and PowerPoint's): their cached series as tables, values in their number formats |
| `pictures.py` | A Word document's pictures as pages, read with a PDF figure's image tasks and context |
| `metafiles.py` | EMF, EMF+ and WMF pictures drawn into PDF pages (vector, text as text), from the vendored `vendor/metafile_render` |
| `compare.py` | Retrieval, local reasoning, numeric checks, and (revisions) explaining differences |
| `align.py` | Revisions mode: items matched across revisions before judging; equal values settled |
| `report.py` | Escaped HTML and JSON reports |
| `provenance.py` | Content IDs, extension normalization, interpreter descriptions |
| `scan.py` | Scanning a source's roots: folders, zip archives, hidden files, safety limits |
| `manifest.py` | Source manifests: export and import |
| `throttle.py` | Rate limits with time-of-day rules; adaptive concurrency |
| `dispatch.py` | Worker threads for model requests; everything else stays on the main thread |
| `progress.py` | Progress bars, heartbeats and logging |
| `store.py` | SQLite evidence store: binding, per-task records, the response cache keyed by query and model, the reader version each content item was read with, comparisons |
| `cli.py` | Commands: arguments into settings and run options, planning, exit semantics; the lab's commands by entry point |
| `pipeline.py` | A run: bind the store, scan, extract, situate, compare, report |
| `levers.py` | Settings' declarations, levers as mixins on the platform, configurations |
| `context.py`, `quotes.py`, `stems.py`, `sections.py`, `tables.py`, `segmentation.py` | Extraction's pieces: the document reader, quote checks, numbered items, sections, tables, page segmentation |
| `readings.py` | Merging readings of one fact by different tasks |
| `pages.py` | Page coordinates as displayed and as stored |
| `regions.py`, `values.py` | Region names and crop names; numbers, dates, lengths and units as printed |
| `fixtures.py` | Replay fixtures: recorded answers, the replay policy |
| `ledger.py` | Cost ledger and measured figures |
| `html_pages.py` | What every generated page shares: escaping, embedded data, the palette |
| `lab/` (`semantic_pdf_diff_lab`) | The lab, its own distribution: `eval/` (rounds, judges, rubrics, review panels, spot checks, query checks, post-mortems) and `bench/` (controlled documents, eye and page tests) |

API contracts were checked against the [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) and [PyMuPDF Page documentation](https://pymupdf.readthedocs.io/en/latest/page.html). Provider compatibility still needs a live smoke test.
