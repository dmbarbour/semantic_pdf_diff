# Multi-format source adapters

- **Status:** Active (2026-10-04): milestones 1 (`.txt`/`.md` and a shared task core), 2 (`.docx`) and 3 (`.pptx`) done; next, `.csv`/`.xlsx`. Format priority (2026-09-23): PDF, then `.docx` and `.pptx`; Cameo models via a separate project.
- **Depends on:** [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (locators, sections, store)

## Goal

Accept common report formats beyond PDF: `.txt`, `.md`, `.csv`, `.xlsx`, `.docx`, `.pptx`, images, and possibly legacy Office formats. Every claim keeps fine-grained provenance.

## Key idea

Most of these formats are **better sources than PDF**, because their structure is explicit rather than guessed. Each adapter produces the same intermediate units:

- **text segments** with a heading path
- **structured tables** (header plus rows, with a known cell locator)
- **renderable visual regions** (embedded images, figures)

Only content that is truly unstructured goes to the model claim by claim. For structured data, the model decides *how* rows become claims, and that decision is then applied mechanically wherever possible (see *Tables and spreadsheets* below).

## Per-format approach

| Format | Approach | Notes |
|---|---|---|
| `.txt`, `.md` | Text segments. Markdown headings give the heading path and sections; recognized front matter keys become provenance annotations, and the rest is content. | Cheap; do first. |
| `.csv`, `.xlsx` | **Model-guided table interpretation**, applied mechanically to rows (see below). | A model call per row doesn't scale to a 10k-row sheet, and it adds error to exact data. Handle merged and multi-row headers. Formulas: use cached values; if a formula has none, record the value as unknown with the formula text as an issue, never evaluate it. Hidden sheets are extracted but marked hidden, never silently merged with visible data. Never follow external links. |
| `.docx` | Real paragraphs, heading styles and real tables via `python-docx`. Embedded images go to the visual pipeline. Read as currently written, with tracked changes applied. Comments are content, with a provenance annotation saying what they comment on. | No table detection needed; quote checks become exact. |
| `.pptx` | Text per shape, tables, speaker notes (content, with "slide N speaker notes" as provenance), and **chart XML, which holds the actual series data**. Embedded images go to vision. | Chart XML beats estimating values from pixels. SmartArt and grouped shapes are the awkward cases. |
| Images (`.png`, `.jpg`, scans) | Straight into the existing visual pipeline. | Nearly free. |
| Legacy `.doc`/`.ppt`/`.xls`, or visual fidelity for Office files | Recorded as unsupported. Optional headless LibreOffice conversion to PDF is a tentative, very low priority extra dependency, never assumed (milestone 4). | Provenance would map only to the converted PDF's pages, so it could only ever be a fallback. |

Candidates for later: HTML, and email exports.

### Samples

The public corpus (`scripts/fetch_samples.py`) covers the priority formats, all from 3GPP and kept as the original zips:

- `.docx` revisions: `3gpp-ts38300-revisions` (TS 38.300 across releases, including a small-difference pair and one legacy `.doc`)
- `.docx` competing proposals: `3gpp-ran1-beam-management` (four companies, plus moderator summaries)
- `.pptx` competing proposals in a mixed-format set: `3gpp-rel19-aiml-views` (four `.pptx`, one `.docx`, four PDF on the same topic)
- `.xlsx`: the two meetings' document lists, plus the wind-turbine spreadsheets. These are all tidy single tables.
- **Messy spreadsheets:** `scripts/make_synthetic_samples.py` generates `samples/synthetic/messy-workbook.xlsx` and `messy-export.csv`, each with an `.expected.json` answer key (true table regions, header rows, composite columns, expected strategy, hidden sheet, the ambiguous layout that should be skipped). The table detection and interpretation work should be tested against these keys.

### Cameo models (decided 2026-09-23)

Cameo `.mdzip` models are digested by a separate project whose output is a large folder of Markdown and some CSV, including its own model-written summaries, aimed mainly at RAG ingestion elsewhere. This project consumes that folder **as an ordinary source** through the `.md` and `.csv` adapters; no converter or importer is needed.

This project **does not judge content produced by external tools**, including the Cameo project's model-written summaries. Whether such content is weaker evidence is the provider's call: a provider may mark content with confidence levels or similar metadata, and this project passes that through to evidence and reports. Provider markings use Markdown front matter and become provider-declared provenance annotations (see [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (*Annotations*)).

### Tables and spreadsheets

Tables from every source now go through [one table model](one-table-model-2026-09-30.md) (2026-09-30): the interpretation below becomes its rules, applied to PDF tables too. What follows stays for what is specific to spreadsheets (regions and sheet maps, formulas, hidden sheets).

One claim per cell is not right in general: adjacent cells often compose into one claim (value and uncertainty, value and unit, min/nominal/max, a condition column). And a very large sheet can't simply be sampled: if one column lists requirement names, every row matters. So each table gets a **model interpretation step**:

0. **Find the tables first.** A sheet may hold several tables plopped down in different places, plus notes, titles and stray cells, and a CSV may carry preamble lines or blank-line-separated blocks. Detect candidate regions heuristically:
   - use explicit structure when present: Excel defined tables and named ranges, merged header cells
   - otherwise find blocks of non-empty cells separated by blank rows and columns, and look for header-like rows (text above numbers, or distinct styling)
   - build a compact **sheet map** (each region's bounds, first rows and apparent header) to show the model

   If a sheet has more than one region, or regions that are irregular or overlapping, the interpretation prompt **warns the model** that the sheet may contain several tables and includes the map. Confident regions are interpreted separately. Ambiguous layouts may be skipped for now, but never silently: the coverage record marks them as `skipped: ambiguous sheet layout` with the region map, so a reviewer can see what was left out. Better heuristics can come later without changing that contract.
1. **Show the model enough of the table to judge:** headers, notes, and a spread of rows (first rows, some from the middle and end, and rows that look different, such as blank, merged or text-heavy ones), within the context budget.
2. **The model returns a row-to-claims mapping:** which columns give the entity, attribute, value, unit, uncertainty, conditions and basis; which columns combine into one claim; and one or several claims per row.
3. **And a processing strategy for the table:**
   - **iterate:** every row is a distinct item (requirements, equipment lists), so the mapping is applied to all rows mechanically. This costs no model calls per row, even for 100k rows.
   - **per-row extraction:** cells need interpretation (free-text descriptions), so rows go to the model individually or in small batches.
   - **summarize:** rows are samples of one quantity (time series, logs), so statistics are computed mechanically over the columns the model identified, marked as derived.
4. **Check the mapping mechanically** against more rows (does the value column parse as numbers? is the unit column constant?). Rows the mapping doesn't fit fall back to per-row extraction, and a high failure rate sends the table back for re-interpretation.
5. **Record everything:** the mapping and strategy are stored with the table and appear in its derivation ("mechanical read under a model interpretation of the headers"). The coverage record states what happened ("summarized 50,000 rows; statistics over columns C–F"), so nothing is silently dismissed. Reviewers can confirm or correct a mapping as reusable QA data, and a configuration can force a strategy for a given table.

### Extension policy

Adapters are chosen **only by normalized extension**, consistent with the store's content model (content = bytes + interpretation, identified by SHA-256 + extension). Known aliases collapse (`.jpeg` → `.jpg` and so on). Files with no extension, or an extension no adapter or converter handles, are listed as skipped and contribute no evidence. No content sniffing.

### External converters (future)

Some formats need proprietary or heavyweight tools, e.g. Cameo/MagicDraw `.mdzip` models. Allow configuring **external converters as executables**, keyed by extension:

- A converter "opens" content into formats we already handle (XMI/XML, CSV, HTML, PDF, PNG diagrams…). Its outputs become **derived content** in the store, with provenance back to the original file.
- The converter's identity (executable path and hash, declared version, arguments) is part of the extraction interpreter, so changing it falls under the store's interpreter-binding rule (reject, or `--reset`). This is best effort only: a converter's own configuration files and dependencies can't be tracked, and the documentation must say clearly that **users are responsible** for resetting a store when they change them.
- Converters run inside the sandbox with no network, a timeout and output size limits (generous backstops), and write only to a scratch directory the tool provides.
- The LibreOffice fallback for legacy Office formats would be just one configured converter, never assumed. The owner (2026-10-04): "We won't have LibreOffice, and let's not assume it, but it could be a tentative extra-dependency eventually (very low priority)."

## Locators

Each adapter defines its locator shape (see the store plan):

- DOCX / MD / TXT: heading path plus paragraph or line range
- XLSX / CSV: sheet plus cell range
- PPTX: slide plus shape ID, or chart plus series/point
- Image: image plus bounding box

The report must render a suitable preview for each format: a text excerpt with its heading path, a small HTML table for a cell range, a slide thumbnail, and so on.

## Packaging and safety

- Adapters go behind optional extras, e.g. `pip install semantic-pdf-diff[office]`. `python-docx`, `python-pptx` and `openpyxl` are MIT/BSD licensed, unlike PyMuPDF's AGPL.
- Treat every input as hostile: size limits, zip-bomb guards on Office files (they are zip archives), no macro evaluation, no external links followed.
- `--plan` estimates model calls per format; spreadsheets can skew the numbers dramatically.

## Milestones

Ordered by what users submit: PDF first (already supported), then `.docx` and `.pptx`, then the rest.

1. Adapter interface and intermediate units; refactor the PDF path to use it. Include `.txt` / `.md` here as the simplest adapters: they are nearly free and exercise the interface (and the `ietf-quic-transport` samples).
2. `.docx`.
3. `.pptx`, including chart XML. *From the closed [evaluation benchmarks](evaluation-benchmarks-2026-09-23.md) plan (2026-10-04):* the controlled corpus written as slides too, scored by the same keys (its representations, as Markdown and Word are).
4. External converter interface. *Tentative, very low priority (the owner, 2026-10-04, above):* LibreOffice an optional extra dependency at most, never assumed; legacy `.doc`/`.ppt`/`.xls` are recorded as unsupported meanwhile.
5. `.csv` / `.xlsx`: table region detection and sheet maps, then model-guided table interpretation. *From the closed [evaluation benchmarks](evaluation-benchmarks-2026-09-23.md) plan (2026-10-04):* extraction scored against the synthetic spreadsheets' answer keys (`scripts/make_synthetic_samples.py`), with claim matching and adjudication of the leftovers.
6. Images.

## Milestone 1 in detail (2026-10-03), for the owner's review

Written when the work began. The owner (2026-10-02), on the readers' value beyond formats: "When we do add the alternative readers, we'll implicitly get a new form of control tests: same facts across two or more representations" (the [controlled documents](controlled-documents-2026-10-01.md) plan's decision 4).

**Today:**
- Extraction is one PDF job (`extract._pdf_job`): a generator fed a page at a time for fair share, whose closures build text, table and image tasks, check quotes, write coverage rows and evidence.
- Context reaches prompts only through levers' hooks given a reader (`extract.Context`), whose methods answer in pages and boxes (blocks on a page, the text above a table, a numbered item's stems, citations).
- Locators are PDF's (`models.PdfLocator`), and `models.Locator` is already meant to become a union discriminated by `format`.
- Any other extension is recorded as unsupported.

**Proposed:**
1. **A shared task core.**
   - What every reader does with a task moves out of the PDF job into one small class: queue the request, check quotes, make evidence and coverage rows, follow repeated blocks, refine on a partial answer.
   - The PDF job keeps only what is PDF's: pages, text blocks, table detection, crops.
   - PDF requests stay byte for byte, checked as in the clean-up by the golden requests and a query snapshot of every slice.
2. **Readers chosen by extension** (the extension policy above): PDF as today, and `.txt` and `.md` by one text reader.
   - Each yields parts as the PDF job yields pages, so fair share across sources holds.
3. **The text reader:**
   - **Sections:**
     - Markdown headings
     - in plain text, numbered headings in the RFC style ("7.2.  Stream Concurrency")
     - else fixed line ranges
   - **Text tasks:** paragraphs (blank-line separated) grouped up to `text_bytes`, as PDF blocks are.
   - **Table tasks:** Markdown pipe tables, as PDF table rows are (header and row).
   - **Quotes:** checked against the source text exactly.
   - **No image tasks.** An image a Markdown file links is recorded as not read.
   - **Text laid out for a monospace font:**
     - **Kept as text, its spacing intact:** code blocks, and blocks indented as RFC figures are. Arrows ("A -> B") and simple structures reach the model as written.
     - **No reader for drawings made of characters.** The owner may lift that restriction later (Decisions).
   - **Context levers through a text reader** with the same methods as `extract.Context`, answering in lines rather than boxes:
     - neighbouring text
     - the text above a table
     - a numbered item's stems ("7.2." > "a.")
     - citations
     - The levers apply unchanged.
4. **Locators:**
   - A `TextLocator` (format `text`): first and last line, region, task. `Locator` becomes the union the model anticipates.
   - Reports show a text excerpt under its heading path where a PDF claim shows a crop.
   - An addition to `evidence.json` and `report.json`, not a change to PDF claims.
5. **Prompts name the region as today** ("Source type: text", "table"): a Markdown paragraph is text to the model. The locator's format says where it came from.
6. **Situating** (figures, "about" statements) stays PDF's in this milestone. Text documents get sections, not "about" statements.
7. **Measured on the controlled corpus written as Markdown** (decision 4 there):
   - prose and tables as Markdown, charts, schematics and sheets left out and their facts marked absent
   - scored by the same keys, so the reader is exact-scored before any real document is read
   - then the revision pairs in Markdown, and the QUIC drafts as a first real revision series

**Questions for the owner** (answered 2026-10-03; see Decisions):
1. **Locators:** a `TextLocator` beside `PdfLocator`, and text excerpts in reports. (Proposed: yes.)
2. **Regions and prompts:** text formats' tasks named "text" and "table" as PDF's are, so a paragraph asks what a PDF paragraph asks. The alternative is new region names per format, which would make every format's prompts different. (Proposed: the same names.)
3. **The shared task core:** a refactor of the PDF job, kept byte-identical, rather than a text reader that copies its task handling. (Proposed: the shared core.)

## Pictures in Word documents, in detail (2026-10-03), for the owner's review

The owner (2026-10-03), after the revision comparison's milestone 4: "Then we'll work on reading pictures." The per-format table already says a `.docx`'s embedded images go to the visual pipeline; this is how, ahead of milestone 6 (images on their own).

**What the samples hold** (Word and PowerPoint files in `samples/`):

| Where | Pictures | Notes |
|---|---|---|
| TS 38.300 (three versions) | 270 EMF, 115 WMF, 19 PNG | Almost all are previews of embedded Visio drawings (176 `.vsd`, 92 `.vsdx`, 109 OLE `.bin` beside them): sequence diagrams, protocol stacks, architectures |
| RAN1 contributions and summaries (5) | 13 PNG, 2 JPEG | Plots and tables as pictures |
| Rel-19 views (`.pptx`, 3) | PNG, JPEG, TIFF, one embedded workbook | For milestone 3 |

**Found by trying:**
- LibreOffice (installed here: `soffice --headless --convert-to`) renders EMF and WMF faithfully, about 1.5 s for five pictures in one call.
- Converted to PDF, a drawing stays vector, and its labels stay text. A sequence diagram's "UE", "gNB", "1. UECapabilityEnquiry" and the stack's "PHY", "MAC", "RLC" are in its text layer.
- Each picture lands on a page with a white background, so it's cropped to what's drawn.
- Pillow reads WMF only on Windows; PyMuPDF opens PNG, JPEG and TIFF but not EMF. (The research below found one pure-Python renderer, first released in September 2026.)

**Proposed (Claude's):**
1. **Pictures become pages:**
   - A raster picture (PNG, JPEG, GIF, BMP, TIFF) is wrapped in a page by PyMuPDF.
   - An EMF or WMF picture is converted to PDF by LibreOffice, keeping its vector drawing and text, then cropped to its drawing.
   - The PDF job's visual tasks then read these pages unchanged: a figure read whole, tiles for a large one, the text layer as context (`visual_text_layer`), and crops for comparisons (`verify_visuals`).
2. **Read in their document, not apart:** each picture's tasks are part of its Word document's job.
   - Its context is its caption (the paragraph naming "Figure …", or one in a caption style), its section heading, and the paragraphs around it, as a PDF figure's are.
   - Its claims are located at the picture's paragraph (`DocxLocator`, region figure or tile) with their crop.
   - A picture's tasks are keyed by its bytes. An unchanged picture in two revisions asks the same queries and gets the same claims, which alignment then settles.
3. **LibreOffice as an optional converter:**
   - It's found on the path, or named by a setting: the first piece of milestone 4's converter interface, pulled forward.
   - Without it, EMF and WMF pictures stay recorded as not read, with the install hint; raster pictures are read regardless.
   - Its version is recorded with the run, as PyMuPDF's is, since it shapes the crops.
4. **Every picture is read,** a tiny one (under about half an inch drawn) excepted. A cover logo costs one request; captions don't decide, since many real figures have none.
5. **Measured:**
   - **The controlled Word documents gain their figures** as pictures (the PDF's chart and drawing regions, rendered). The Word representation then carries chart and schematic facts too, scored exactly beside the PDF's readings.
   - **TS 38.300's figures** are read by eye, and the v19.2 → v19.3 pair compared again with pictures.
6. **Later, as tentative index rows:**
   - the Visio sources' shape text (`.vsdx` XML), as `.pptx` chart XML is read
   - a Markdown file's linked local images
   - `.pptx` pictures, by the same path

**For the owner:**
- **A. LibreOffice as an optional external converter for EMF and WMF now.** Recommended: it's the only renderer here that draws 3GPP's figures, and it's already the plan's first converter. The alternative is leaving TS 38.300's figures unread until milestone 4.
- **B. Pictures read within their document,** with captions and neighbouring text as context and claims located at their paragraph. Recommended over reading each picture as a separate file, which loses the caption and section.
- **C. Every picture read** (a size floor aside), rather than only captioned ones.

**Cost:** about 150 pictures in each TS 38.300 version, about one request each, with tiles for large ones: roughly $0.10–0.25 a version. The controlled Word figures cost cents.

**The owner's answers (2026-10-03):**
- **A:** "I wouldn't count on LibreOffice being available in most environments, among them my intended usage environment. It's also outside our control and difficult to make reproducible. My intuition is that it isn't the right move. Perhaps do a bit more research. If there is an un-maintained python lib with a suitable license, consider grabbing a copy and extracting what is needed? Do a bit more research on this and our options, in any case."
- **B:** "Yes, we'll want similar context as what PDF pics get."
- **C:** "Every pic."

**The research (2026-10-03).** A survey of renderers was run, and the candidates were tried on TS 38.300 v19.3's 143 metafiles. Renders were made in the scratchpad only.

- **What the figures are:**
  - 103 EMF, every one EMF+ "dual" (an EMF+ stream with a plain GDI fallback). 101 preview Visio objects: 65 binary `.vsd`, 36 `.vsdx`.
  - 40 WMF, 37 of them previews of Msc-generator charts, whose OLE object holds the chart's source as text.
  - Labels are text records: EMF+ DrawDriverString in 53 EMFs, GDI ExtTextOutW in 49, WMF ExtTextOut. A few store glyph indices instead of characters (4 seen).
  - Visio's gradient boxes are drawn in the GDI fallback by an XOR trick: pattern blits (PATINVERT) over DIB pattern brushes.

| Route | License | On our figures |
|---|---|---|
| **metafile-render** 0.3.0 (Python; Pillow, pyclipper; ~7,100 lines; first released 2026-09, one author) | MIT | Every EMF renders. Sequence diagrams and stacks are good, and its SVG, drawn by PyMuPDF, keeps labels as text. Visio's gradient boxes become black stripes over their labels. 36 of 103 SVGs are a raster wrapped in SVG. 38 of 40 WMFs fail or render blank (Msc-generator's clipping). |
| Apache POI HEMF/HWMF (Java, ~16,000 lines of logic) | Apache-2.0 | All 143 render, the best seen: gradients, boxes and labels right. A port needs Java2D's clipping areas, transforms and raster operations rebuilt. |
| wmf2svg (Java, ~28,000 lines) | Apache-2.0 | All convert. Draws both streams of dual files (labels doubled); misplaced labels. |
| metafile-rs, emf-rs, emfsdk (Rust) | Apache-2.0 / MIT | A native build to maintain. metafile-rs drops all EMF+ text. |
| pyemf, pyemf3; libwmf | LGPL | Write or parse only; none renders what we need |
| libUEMF, libemf2svg, pymfvu, UniConvertor, libvisio-ng | GPL or AGPL | Ruled out for an MIT project |
| Pillow's WMF plugin | MIT-CMU | Renders only on Windows |

- **The specifications** ([MS-EMF], [MS-EMFPLUS], [MS-WMF]) allow copying them "in order to develop implementations". Microsoft's patent map lists no patents for any of them. An implementation of our own, or our own fixes, may follow them.
- **Text without rendering:**
  - the metafiles' own text records (a record walker of about 300 lines)
  - `.vsdx` shape text (the `vsdx` package, BSD-3; text found in 35 of 36)
  - Msc-generator chart sources (`olefile`, BSD; 35 of 37 read)
  - Binary `.vsd` would need a port of POI's HDGF (text only, ~1,700 lines).
- **Checked here:** metafile-render's vector SVG, opened by PyMuPDF, gives a crisp page whose text layer reads "UE gNB AMF NAS RRC PDCP…". MuPDF's own fonts draw it, so the same picture gives the same pixels on every machine.

**Revised proposal (Claude's), for the owner:**
1. **Render with a vendored copy of metafile-render** (MIT, kept with its license notice), its SVG output drawn by PyMuPDF. Our fixes:
   - Visio's gradient fills: the XOR pattern blits and pattern brushes, or the EMF+ stream with its text placed right
   - WMF clipping as real regions (pyclipper), for Msc-generator's charts
   - no whole-picture raster fallback
   - one text element per run
   - its safety limits made settings
2. **The picture's text from its own records,** as a PDF figure's text layer is given (`visual_text_layer`). Its labels reach the model as text even where the drawing is imperfect. An Msc-generator chart's source is given too.
3. **Raster pictures** (PNG, JPEG) as they are; Pillow and pyclipper join the `office` extra.
4. **Later:** Visio sources (`.vsdx` with the BSD `vsdx` package; `.vsd` through an HDGF port).

**The owner's decision (2026-10-03):** "Let's go with 1 for now, but hold 2/3 as fallback options if we struggle with fixes or quality." Route 1 is the vendored copy of metafile-render; the POI port and a renderer of our own stay fallbacks.

**The alternatives:**
- port Apache POI (the best quality, a much larger job)
- write our own renderer from the specifications for the record types our figures use, borrowing from metafile-render and POI with attribution
- text first only, deferring pixels (days, not weeks, but arrows and layout are lost)

## Excel, in detail (2026-10-04), for the owner's review

The owner (2026-10-04): "Let's do Excel next. 99% of my spreadsheets are Excel." So milestone 5 is Excel first (`.xlsx`, and `.xlsm` read the same, macros ignored); CSV can follow cheaply; legacy `.xls` stays unsupported (recorded as such).

**The design is already set** by the [one table model](one-table-model-2026-09-30.md) and *Tables and spreadsheets* above: a model writes each table's rules once (which cells give each claim's entity, attribute, value, unit and conditions), and they're applied to every row mechanically, checked, with the rows they don't fit read one by one. A 10,000-row sheet costs one model query, not 10,000.

**Proposed order** (Claude's): Excel goes through the rules path first, before the one table model's PDF repair milestones. A spreadsheet's cells are native (no parser, no repair), so it's the cleanest place to build and measure the rules; PDF and Word tables move onto them afterwards.

**Steps:**
1. **The reader** (`xlsxdocs.py`, with openpyxl added to the `office` extra):
   - each sheet a page and a section, titled by its name, in the workbook's order
   - cells as Excel shows them: the cached value in its number format; a formula without a cached value is recorded as unknown, its formula text as an issue, never evaluated
   - hidden sheets, rows and columns read, but marked hidden
   - merged cells, Excel's defined tables and named ranges used as structure
   - cell comments as content, as in Word
   - charts read from their data (`chartxml.py`); pictures as in Word
   - external links never followed
2. **Regions and the sheet map:** defined tables first; then blocks of filled cells parted by blank rows and columns, with header-like rows; titles and notes as text. A sheet with several regions gets a map (each region's range, first rows and apparent header).
3. **The table representation** (the one table model's item 1, filled from native cells): a grid with spans, header levels (labels by path), section rows, the row-label column, and hazards named.
4. **First reading, before the rules exist:** a small region is read row by row, as Word's tables are now. A large one (over a row limit) is recorded "not read yet: N rows, awaiting rules", never silently. This gives a working reader early and a baseline the rules must beat.
5. **The rules query and their mechanical application** (the one table model's item 4), with its checks and row-by-row fallback.
6. **Measured:**
   - the synthetic workbook's answer key: regions, header rows, composite columns, strategies
   - the controlled corpus written as workbooks, scored by the same keys (the medium test: the same facts from PDF, Word, slides and Excel)
   - the IEA 15 MW workbook against the tables in its own PDF report (a real medium test)

**Decision 1, how a table is handled (the owner, 2026-10-04):** "I believe our decision previously was: ask a model how to handle the table. We should give the model the headers and samples of the rows, report number of claims and our own heuristic opinion (summary vs. point per claim) based on size and a short analysis of rows (whether they're mostly text, numbers, etc..), then ask the model how to handle it, i.e. whether how to produce claims from rows or how to summarize things within a few known templates."

So the rules query (step 5) is one "how should this table be read?" query per table:
- **What it's shown:**
  - the table's place (sheet, range, caption or title), its full header block, and sample rows (the first, some from the middle and end, any unusual ones)
  - its size: rows, and the claims a point per cell would give
  - **a short analysis of its rows,** mechanical: each column's kind (numbers, text, dates, empty, and in what shares), its distinct values, whether it steps evenly (a hint of an input, as the one table model's decision 2 says), long text
  - **our heuristic opinion,** from size and that analysis, labelled as such: "a series: 330 rows of numbers, column A stepping evenly: summarise?" or "150 rows of mostly text, each a distinct item: claims per row?"
- **What it answers,** one of:
  - **claims from rows:** the row-to-claims mapping (roles, composites), applied to every row mechanically; or rows read one by one where cells need reading
  - **a summary, within a few known templates,** naming the template and its columns. The statistics are computed mechanically and marked derived. Proposed templates (Claude's):
    - **series:** a curve of one or more quantities against an input (the airfoil polars): the input's range and step; each quantity's extremes and where they fall; the values at points the model names
    - **log:** samples of quantities over time (the flow log): the span and count; each quantity's minimum, maximum, mean and last value
    - **list:** many records of one kind (the RAN1 document list): the count, and counts by the categories the model names
- **Checked, recorded, replayable** as the one table model says: a mapping's claims for the sample rows must match the model's examples; values must parse; rows the mapping doesn't fit are read one by one.

**Decision 2, the library (2026-10-04):** openpyxl, in the `office` extra (MIT; already in the `dev` extra): it reads number formats, merged cells, defined tables and cached values. The owner left it to Claude: "I cannot offer informed opinions on openpyxl or any alternatives. I'll leave it to you. You can review the decision if there are any quality or integration concerns."

## Decisions (2026-09-23)

- **Milestone 1's design (2026-10-03).** The owner: "I agree with all three recommendations": a `TextLocator` beside `PdfLocator` with text excerpts in reports; text formats' tasks named "text" and "table" as PDF's are; a shared task core, the PDF job refactored byte-identically.
- **Text laid out for a monospace font (2026-10-03).** The owner: "I would add caution on recognizing ASCII art. We should still recognize simple arrows and such. And it may be we want to recognize some graph-like structures written with the expectation of monospace. I might end up rolling back the restriction on recognizing ASCII art, but I won't prioritize it." Claude's reading:
  - such text is sent as text with its spacing kept, so arrows and simple structures are read
  - no dedicated reader for drawings made of characters for now
- **Spreadsheet claims are marked by provenance, not trust.** A claim read directly from cells is *more direct* than one a model extracted from prose or a chart, and its derivation says so (see *Derivation* in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md)). Directness is not reliability. A spreadsheet still raises questions: is our interpretation of the columns right (and if a model interpreted the headers, that is itself a model step in the derivation)? Is a value a measurement, a projection, a requirement or wishful thinking? Are uncertainties given? Those are judged like any other claim (see *Epistemic status* in [scheduling-and-triage](scheduling-and-triage-2026-09-23.md)), not assumed away.

## Progress

- **Milestone 1, a shared task core and `.txt`/`.md` (2026-10-03): done.**
  - **The task core** (`tasks.py`) does what every reader does with a task:
    - the request, quote checks, evidence and coverage rows
    - repeated blocks
    - text and table tasks with their refinement
  - **The PDF job** (`extract.py`) keeps pages, blocks, table detection and image tasks.
  - **Byte for byte:** a query snapshot of every slice under three profiles matched before and after, 10,208 queries, none changed.
  - **The text reader** (`textdocs.py`), chosen by extension:
    - pages by form feed
    - sections from Markdown or RFC-style numbered headings
    - paragraphs kept as laid out, pipe tables row by row
    - page furniture (a line repeated near the edges of three or more pages) left out
    - linked images recorded as not read
    - context levers through a line-based reader, claims located by `TextLocator` (page and lines)
    - The report shows "lines 5–5" where a PDF claim shows its box.
  - **Measured on the controlled corpus written as Markdown** (17 documents: the clean and trap documents and their revisions; charts, schematics and sheets left out, their facts marked absent):

    | | Markdown | PDF |
    |---|---|---|
    | Recall, every document | 1.000 | 1.000 |
    | Misbound claims, `wtp-tables-s1-clean` | 0 | 6 |
    | Misbound claims, `coaster-tables-s1-clean` | 0 | 18 |
    | Misbound claims, the energy studies | 0 | 5–9 |

    - The schedules' misbinding in PDF came from layout (the text layer's column shifts, the image reader's row names), not from the tables' content.
  - **The Markdown revision pairs** (9) found every change, addition and removal with no false change, and judged 0–6 pairs each. The PDF pairs judged 4–24.
  - **Alignment fixes Markdown found** (the revision comparison plan):
    - a condition moved between attribute and conditions ("95th percentile")
    - "number of inversions" against "inversion count"
    - a new value beside a superseded one ("raised from 178 ft to 230 ft")
  - **Cost:** $0.066 to read the Markdown corpus and compare its pairs.
  - **Not yet:** situating (figures and "about" statements) for text files; RFC furniture other than repeated lines; the QUIC drafts (the revision comparison plan's milestone 3).

- **Milestone 2, `.docx` (2026-10-03): done.** The owner: "I agree with the recommended order. No issues with spending a few dollars to get both of these done."
  - **The reader** (`docxdocs.py`, with python-docx, MIT, in the `office` extra) reads a Word document into the text reader's form, so the task core, sections and context levers work unchanged:
    - each paragraph and table row a line
    - headings by style ("Heading N"); a title is text
    - tracked insertions in, deletions out
    - the table of contents left out
    - tables row by row
    - Claims are located by paragraphs (`DocxLocator`); reports show "paragraphs 12–14".
    - Without python-docx, a `.docx` is skipped with the install command in its coverage note.
  - **Not read yet:** embedded pictures and objects (each recorded as not read: 294 in the two TS 38.300 versions, mostly 3GPP's figures), and comments.
  - **Long documents keep fair share:** a page as long as a whole Word document yields to other sources every 20 tasks.
  - **The controlled corpus written as Word documents** (17, from the Markdown, byte for byte the same each time):
    - full recall
    - no misbinding where the PDF schedules had 6–18
    - its nine revision pairs found every change, addition and removal with no false change
    - $0.058
  - **A real document:** 3GPP TS 38.300 v19.2.0 and v19.3.0, about 800 KB of text each, read for $0.52: 10,649 claims, 1,283 table rows (the revision comparison plan's milestone 3).
  - **A fault found and fixed:** cells were skipped when Python reused an lxml element's id; each `w:tc` is one cell.

- **Pictures in Word documents, steps 1–3 (2026-10-03): metafiles drawn.** The owner: "Let's go with 1 for now, but hold 2/3 as fallback options if we struggle with fixes or quality."
  - **The vendored copy:** metafile-render 0.3.0 from PyPI, every file checked against the wheel's record, in `src/semantic_pdf_diff/vendor/metafile_render` with its MIT license. Our changes are listed in `vendor/README.md`.
  - **Our PDF backend** (`metafiles.py`) draws the vendored playback's commands into a one-page PDF:
    - vector paths
    - clips computed with pyclipper (GDI's replace, intersect, union, exclude and xor), once per distinct clip stack
    - text as text in PDF's built-in fonts, measured with their metrics; a run tighter than the font is narrowed to its advances
    - bitmaps in drawing order, mask operations drawn with the masked colour transparent
    - The vendored SVG and Pillow backends aren't used. The page draws alike on every machine, and its labels are the text layer the visual tasks read.
  - **Fixed in the vendored copy** (found on TS 38.300's figures):
    - dual files play their EMF+ stream, falling back to the EMF records
    - GetDC windows draw in GDI's own coordinates
    - placeable WMFs map onto their bounding box
    - EMF+ regions are read
    - a text record fills its rectangle only with ETO_OPAQUE
    - the clip-operation limit is raised from 64 to 100,000

    | TS 38.300, three versions | Before the fixes (v19.3) | After (all three) |
    |---|---|---|
    | Distinct metafiles drawn | 106 of 143 (37 WMF over the clip limit) | 163 of 163 |
    | With text, words in all | 104, 3,939 | 155, 6,256 |
    | Compared by eye with Apache POI's renders (v19.3's 143) | Visio's gradient boxes black over their labels; GetDC labels scattered; Msc-generator charts blank | close throughout |

  - **Known differences:**
    - EMF+ gradients drawn as one representative colour (the vendored brush approximation)
    - translucent fills drawn opaque in a few figures
    - the 3GPP cover logo's EMF+ image not decoded: its fallback bitmap is drawn, cropped
    - 2 characters the built-in fonts can't show (counted)
    - one path drawn with an AND operation skipped
  - **Tests** (`tests/test_metafiles.py`) build small WMF and EMF+ files record by record:
    - a window mapped onto its box
    - text placed as text
    - an excluded rectangle
    - GetDC text in GDI's coordinates
    - an EMF+ stream without drawing
    - a region's hole
    - Each fix's test fails with that fix reverted.
  - **`scripts/metafiles.py render`** draws every distinct metafile in the samples' Word documents into `benchmarks/metafiles` (git-ignored), optionally beside reference renders.
  - **Next:** step 4, pictures read in their Word document with a PDF figure's context.
- **Pictures in Word documents, steps 4–5 (2026-10-03): read and measured.**
  - **The reader** (`docxdocs.py`) keeps each picture with:
    - its paragraph
    - its bytes and format: a drawing's image, or an embedded object's preview
    - its displayed size: a drawing's extent, an object's VML style
    - its caption: the next paragraph in a caption style (Word's Caption, 3GPP's TF) or starting "Figure …", else the one before
  - **Pictures** (`pictures.py`) become pages at their displayed size:
    - metafiles drawn by `metafiles.py`; images placed as they are
    - every picture drawn before any task is fed, since adding a page invalidates earlier ones and a refined tile renders from its page
    - Each page gets a PDF page's image tasks (`extract.Visuals`, shared with the PDF job, its PDF requests byte for byte as before): the caption as source text, the text layer as context and check, the section's headings.
    - Claims are located at the picture's paragraph (`DocxLocator`, now with the image regions) with their crops.
    - A picture that can't be drawn is recorded, with its reason.
  - **The controlled corpus's Word documents carry their charts as pictures,** cropped from the PDF's drawing with their captions. The charts' facts are placed at the pictures ("docx-figure") and scored.

    | | PDF | Word, charts as pictures |
    |---|---|---|
    | Energy study: recall; claims misbound | 21 of 21; 7 | 21 of 21; 0 |
    | End-use study: recall; claims misbound | 33 of 33; 5 | 33 of 33; 0 |
    | Energy revision pair | every change, no false change | every change (the charts' bars too), no false change, each named "changed" |

  - **TS 38.300 v19.2 → v19.3, pictures read** (the revision comparison plan's real pair), $0.142 for both versions' pictures and the comparisons they added:
    - claims from pictures: 2,706 of 13,355
    - quotes found in the picture's own text layer: 2,428 (90%)
    - picture tasks: 354 of 358 complete (4 long procedure diagrams hit the claim limit)
    - The rater (`bench/real_pairs.py`) now counts a picture changed when its bytes differ from its counterpart's (by caption): four procedure diagrams changed and one was renamed.
    - Differences on pictures fell mostly on those diagrams. Inserted messages shifted their steps, and the pairings across steps were named "not the same item".
  - **Stores made before this read no pictures** until `--reset` (no users yet; noted, not migrated).

- **Diagrams with many claims: the owner's decisions (2026-10-03).** Measured on TS 38.300's pictures: 8 of 338 picture reads hit the 20-claim limit; a median picture has 95% of its label words in some claim, the largest procedure diagrams 76–100%. Claude's five ideas, and the owner's answers:
  - **1. Continue when the model asks for more:** "I think enabling 'continue' based on a request from the model is straightforward." Now.
  - **2. Labels no claim covers:** "Analysis of labels unused is probably better applied as a quality and confidence check." Now, as a check, not a trigger.
  - **3. Split a picture in halves:** "I think splitting halves will be very confusing in some cases; the purpose of the vision model is to see and report things as a human might, and visual context is a big part of that." Not done.
  - **4. The model proposes the partition:** "Support for interactive analysis of images (4) would be somewhat analogous to progressive disclosure, but I agree it should be secondary." Later.
  - **5. Read a picture's source** (Msc-generator's chart text, Visio's shape text): "Reading source for pictures is very nice to have as a fallback for attempting to understand claims." Later, "when we'd get to it normally."
  - The owner: "We'll need to ensure some claim-heavy diagrams and charts are in our control docs."
- **Continued reading and the label check (2026-10-04): built.**
  - **Continuation** (the `continue_reading` lever, `continuations`, default 3):
    - The trigger is an image task's answer that's incomplete with its claims at the limit, or that says the claim limit stopped it ("more steps (17–22) than the 20 claim limit allowed"). That's the model asking for more; clipping or illegibility isn't.
    - The same task is asked again ("<task>-c<n>") with the claims it returned listed by entity, attribute and value, not to be repeated.
    - A first request's bytes are as before, so recorded answers replay.
  - **Image tasks only.** Continued, a page's text task read the tables on the page too, copying a header's condition ("rated point") onto every row. The other revision's reading lacked it, so alignment couldn't settle them. Listing the claims without conditions didn't stop it. Text and table tasks keep refinement by splitting their text.

    | Controlled corpus (116 runs) | Before | Continued, all tasks | Conditions not listed | Image tasks only |
    |---|---|---|---|---|
    | Facts read right | 4,607 | 4,611 | 4,606 | 4,606 |
    | Misbound claims | 281 | 243 | 242 | 226 |
    | Claims | 6,106 | 5,707 | 5,712 | 5,681 |
    | Revision pairs with fewer unchanged facts confirmed | – | 3 | 3 | 0 |

    - The gain is in tiles: a capped tile is continued, not halved. The equipment schedules' halves had read rows twice; they went from 6–8 misbound to 0.
    - Slightly worse: the floor plan's clean run reads 5 facts loosely rather than right; the scanned end-use study has 2 misbound where it had none.
    - On TS 38.300: 3 capped picture reads continued, all complete, 17 more claims.
    - Cost: $0.34 on the controlled corpus (three versions), $0.012 on TS 38.300.
  - **The label check** (`pictures.Reading.labels`): a coverage row for each picture with a text layer (`labels:p1:pic<line>`, status complete). It gives the share of the picture's own words (three letters or more, function words left out) that some claim from it mentions, and lists the words none does. It's a quality measure, never applied.
    - On TS 38.300's 267 pictures (two versions): median 100%, 16 under 80%, none under half.
    - The uncovered words are mostly axis titles and sentences in figures.
- **Word's own difficulties as knobs (2026-10-03).** The owner: "I do want Word-specific knobs; we should definitely include some footnotes etc, speaker notes in pptx later, etc.. For tracked changes, we'll generally process the changes-applied version, but that must be tested if not already." (The reader applies tracked changes; a unit test covers it, no controlled document does yet.)
- **Word knobs, a first set (2026-10-04): built.**
  - **The reader** (`docxdocs.py`) now reads:
    - **footnotes:** each placed as a line ("Footnote 1: …") after the paragraph or table citing it, marked "[1]" where cited
    - **numbered lists:** written from Word's numbering definitions (levels, formats, label text, a style's own numbering): "Condition 3:", "a)", "iv.", "•"
  - **The knobs** (`bench/controlled/word.py`): Word-only documents beside the corpus, scored by the same facts.

    | Knob | Document | Result |
    |---|---|---|
    | Tracked changes | the treatment plant's revision as unaccepted insertions and deletions to the earlier document (values, a row added, a sentence dropped) | scored exactly as the clean revision: 4 of 4 changes, 3 of 3 additions, 1 of 1 removal, 28 of 28 unchanged, no false change |
    | Footnotes | three sentences, four facts, moved into footnotes | 33 of 33 facts found, all read right |
    | Numbered lists | the specification's conditions as a Word list labelled "Condition %1:", and its renumbered revision | the reader writes the same text as the plain document, so the queries are byte for byte the plain document's: the same answers and scores |

  - **Not yet:** merged and nested table cells, text boxes, Word charts (chart XML), equations, comments.
  - Cost: $0.004.
- **Claim-heavy diagrams and charts in the controlled corpus (2026-10-04): built.** The owner: "We'll need to ensure some claim-heavy diagrams and charts are in our control docs."
  - **Dense charts** (`lcc-metered`, under the six chart knobs): a year of a convention center's metered electricity.
    - two substations' monthly use as grouped bars: 24 values
    - their monthly peak demand as lines: 24 more
    - the year's totals and the contract demand in the text: 51 facts in all
    - Values repeat within a substation (the month tells them apart); the two substations' ranges never meet.
  - **A procedure diagram** (`procedures.py`, `attach`, under the clean and raster knobs): a message sequence chart with four lifelines and 24 numbered messages.
    - Each message carries one parameter and its value ("7. Admission Grant (granted rate 13,097 kbit/s)").
    - Attributes of one shape recur: four lifetimes, three intervals, two timeouts.
    - **One layout, two drawers:** the PDF draws it as vector shapes or, under the raster knob, as an image. The Word document carries the same shapes as a WMF. Our metafile renderer draws that WMF back with nothing skipped and every label as text.
    - Markdown marks it as not shown, and lists its facts as absent.
  - **A revision pair on the diagram,** after TS 38.300's procedure diagrams (above):
    - a Key Challenge message inserted at step 10, so steps 10–24 become 11–25
    - one parameter revised before the insertion, one after it (renumbered as well)
    - The Markdown pair is skipped: its two files are byte for byte the same, since Markdown can't carry the diagram. The run and the scorer now skip any pair whose two documents are identical.
  - **gemma-4 read them for $0.076.** No existing run or pair scored differently.

    | Dense charts (51 facts) | Recall | Facts read right | Loose | Misbound | Inexact | Claims |
    |---|---|---|---|---|---|---|
    | clean | 1.00 | 51 | 24 | 14 | 0 | 91 |
    | axis | 0.84 | 28 | 19 | 0 | 31 | 91 |
    | raster | 1.00 | 51 | 0 | 0 | 0 | 53 |
    | legend-caption | 1.00 | 51 | 24 | 0 | 0 | 77 |
    | scan | 1.00 | 51 | 0 | 0 | 0 | 51 |
    | all | 0.69 | 35 | 0 | 0 | 36 | 72 |
    | Word, charts as pictures | 1.00 | 51 | 0 | 0 | 0 | 51 |

    | Procedure diagram (26 facts) | Recall | Facts read right | Loose | Misread | Hallucinated | Claims |
    |---|---|---|---|---|---|---|
    | clean | 1.00 | 26 | 1 | 2 | 2 | 34 |
    | raster | 1.00 | 26 | 0 | 0 | 5 | 33 |
    | Word, a WMF picture | 1.00 | 26 | 0 | 0 | 0 | 26 |

    | Diagram pair | Changes | Additions | Unchanged confirmed | "Different" findings that are changes |
    |---|---|---|---|---|
    | PDF | 2 / 2 | 1 / 1 | 22 / 24 (2 uncertain) | 2 of 5 |
    | Word | 2 / 2 | 1 / 1 | 24 / 24 | 2 of 2 |

  - **Continuation fired as built:** 40 capped reads, from PDF figure, overview and tile tasks and from Word pictures' overview and tile tasks. Each was continued once, and every one was complete after it.
  - **The renumbering didn't confuse the comparison.** Messages kept their names across revisions, so no step was paired with another by its number.
  - **Faults these documents expose** (two new rows in the [lever index](../reviews/levers.md)):
    - **The PDF table reader took the diagram for a table:** the lifelines read as column rules, and labels were cut into cells.
      - Of its 7 claims, 2 were hallucinated ("5|72 s" read as 72 s) and 2 misread (step numbers as values).
      - All 3 of the PDF pair's "different" findings that aren't changes, and both of its uncertain ones, involve these claims.
    - **Thousands separators read as decimal points:** on the raster diagram, all 5 values with a comma were read with a point ("13,097 kbit/s" as 13.097). The image reader made none on the vector page or in Word, where a text layer holds the labels.
    - **The text reader misbinds a chart's printed values:** 14 on the clean dense charts, as on the other charts (milestone 3a's known flaw).
    - **The PDF's image reader named the peak demand line chart's values "power"** (the axis is in kW): 24 loose. In Word, with the caption beside the picture, all were named "peak demand".
    - **Against the axis,** 31–36 readings were off by more than a quarter step: 24 bars and 24 points at 50 and 100 steps.
  - **A layout fault fixed on the way:** a figure 0.7 pt past the page body silently lost the section after it, since the overflow check allowed 1 pt. It now allows 0.01 pt. No committed document fell in that slack, so none changed.
- **Merged and nested cells, and layout tables (2026-10-04): built.** The owner, on Claude's proposal: "Okay, seems we'll get plenty of levers to explore here, and difficulty knobs to test them. Go ahead with the initial design based on your recommendations, heuristic for layout tables. This will provide a foundation for improving things later."
  - **What the Word reader did before** (checked on a small document):
    - **a nested table was read three times:** squashed into its cell, added as extra columns, and read as rows of the outer table under its header ("Flow | 450 gpm" asked as Pump = Flow, Duty = 450 gpm)
    - **a cell merged down** left the rows below it without their subject
    - **a cell merged across** shifted the cells after it under the wrong headers
    - **a table of one row** (a boxed note or proposal) was taken for a header with no rows: never read
  - **The design** (`docxdocs.py`):
    - **the grid:** each row's cells placed on the table's columns. A cell merged down repeats its text in each row it covers; a cell merged across is one value, asked under its columns' labels joined ("Stroke time (s) > Open / Close"). Each row is asked under its own labels.
    - **headers:** the rows Word marks to repeat as a header; else the first row, and the next too when the first has a merged cell and the next holds no number. Under two header rows a column's label is its path ("Hydraulics > Capacity (gpm)").
    - **nested tables:** up to 6 rows, written into the cell ("Capacity (gpm): 7,824; TDH (ft): 134.8"); larger, read on their own after the outer table, under a line naming where they sit ("Table in Raw water intake, Valves:")
    - **layout tables,** read as the document's own paragraphs and tables:
      - not marked with a header row, and
      - of one row or one column, or with no header-like first row and either a heading in a cell or long cells (200 characters on average)
    - Content controls around rows, cells and paragraphs are read through.
    - **One departure from the recommendation:** the 6-row limit is a named constant, not a setting. A setting joins every store's binding, so every store would need rebuilding for no change in behaviour. It becomes a setting when it's tried as a lever (the [lever index](../reviews/levers.md) has a row for these heuristics).
  - **Measured on the real Word samples before recording,** the old reader against the new, offline:
    - **The first layout rule misfired:** long cells or a pasted heading made 3GPP's tables of companies' comments (a "Company | Comments" header, then long views) into layout, half the tables of two RAN1 feature-lead summaries. A short, filled first row now keeps a table data. The summaries then changed in 1–2 of 590–733 rows.
    - **Boxes are now read:** one-row and one-column tables, never read before, are read as text. One Ericsson contribution had 13, its work item's objectives among them.
    - **TS 38.300 changed in one table, the change history.** A title row merged across all its columns ("Change history") had been read as the header and the real header row as data; the columns are now labelled ("Change history > Date", "> Meeting", …). About 600 row queries changed in each version.
  - **Three Word knobs** (`word.py`), on the equipment schedules:

    | Knob | What it holds | Facts | Read right | Claims |
    |---|---|---|---|---|
    | merged | two-row headers made of merged cells (one table's found, one's marked to repeat); each pump's tag and motor merged down over its rated and runout rows; valves' stroke times as Open and Close, merged across where equal | 105 (84, 6 runout points, 15 closing times) | 105 | 105 |
    | nested | each pump's rated point and motor as small nested tables; the valves as two large tables nested in an area table | 84 | 84 | 84 |
    | layout | the plain document inside a borderless one-row, two-column table | 84 | 84 | 84 |

    - The layout document asks byte for byte the plain document's queries: it was read from recorded answers, at no cost.
    - **A key fix, from reading the claims:** the merged knob's opening stroke times were first scored loose (15). The claims were right ("Stroke time Open: 45.4 s"), but the key lacked the column's own word, so the opening and closing times tied. "Open time" is now among those facts' names.
  - **TS 38.300 re-read,** its revision pair compared again, $0.083:
    - The model mostly declines the change history either way ("a change history log rather than engineering specifications"): 39 claims from its 1,187 rows before, 10 now.
    - The pair's rating barely moved: 13–20 fewer claims per version, 11 fewer settled in changed text. One more numeric change went unseen: the history's rows added in v19.3.0, document administration.
    - **A gap met on the way:** a store re-run after a reader change keeps the tasks the old reader made. The first re-run asked nothing new ($0.002). The pair was re-read into a fresh store, the old one set aside. A reader version in the store's binding would close this gap; until then, a reader change means fresh stores.
  - **The real-pair replay names the model as recorded,** as the controlled corpus's does: it works without `.env`.
  - Cost: $0.015 for the knobs.
- **Text boxes (2026-10-04): built.** The owner, on text boxes as the next Word knob: "Please proceed."
  - **What the reader did before:**
    - **a modern text box was read twice,** once from its shape and once from the VML copy Word keeps for older readers, both glued into the middle of the sentence anchoring it
    - **a table in a text box** was never read as a table: its cells were glued, twice, into the paragraph before it
    - **every text box was reported as an unread object**
  - **The design** (`docxdocs.py`):
    - **out of the anchor:** a paragraph's own text leaves its text boxes out
    - **after the anchor:** each box's paragraphs and tables follow the paragraph anchoring it, read as the document's own (headings, numbering, footnotes, nested boxes alike), as footnotes follow theirs
    - **in a table cell,** a box's text joins the cell's
    - **no copies:** Word's copy for older readers (`mc:Fallback`) is never read, so text, pictures and footnote marks aren't repeated
    - **not a picture:** a plain text box is no longer reported unread. A drawing of grouped shapes or a drawing canvas is recorded as "a drawing of shapes (its text read, not its arrangement)".
  - **Measured on the real Word samples first,** the old reader against the new:
    - **TS 38.300** reads exactly as before.
    - **A Qualcomm RAN1 contribution** draws its figures with Word shapes. Before, all their labels were glued twice into one paragraph ("AI/ML Model(ID#X)AI/ML Model(ID#X)Output features…"); now each label is read once, on its own line. Unread objects fell from 166 to 64, the rest shapes without text.
    - **An Ericsson contribution's** body sentences no longer carry its diagrams' labels glued in. Its two grouped drawings are recorded as drawings of shapes.
  - **The knob** (`word.py`, `wtp-s1-textbox`), the treatment plant's document with:
    - a sentence in a modern text box (a shape with Word's VML copy)
    - the pump table and its caption in another
    - a sentence in a VML text box alone, as older Word wrote them
    - **Result:** 33 of 33 facts read right, conditions kept 11 of 11, the same claims as the plain document, for $0.001. Most of its queries were the plain document's.
  - **Not yet:** a drawing of shapes is read as its text only. The [lever index](../reviews/levers.md) has a row for reading their arrangement.
- **Word charts (2026-10-04): built.** The owner: "Please proceed with Word charts next." The plan's approach (Per-format approach, `.pptx`): "chart XML, which holds the actual series data ... Chart XML beats estimating values from pixels."
  - **Before:** a Word chart was recorded as "a chart or drawing without a picture" and not read.
  - **The design** (`chartxml.py`, shared with PowerPoint later; `docxdocs.py`):
    - **from its cache:** each chart is read from the values it caches beside its drawing, not from its workbook
    - **as tables:** a row per category and a column per series (column, bar, line, area, pie, doughnut, radar, stock, surface; a combination's groups side by side); for scatter and bubble charts, a row per point ("Series | X | Y")
    - **values as shown:** each in its series' number format ("#,##0" 1,750; "0.0%" 12.5%; dates as ISO dates; rounded half away from zero, as Office rounds), "General" as the shortest exact form
    - **a label first:** the table follows a line naming the chart: "Chart: Readiness for a WI (%) (clustered column chart); values: MWh; caption: Figure 1 …". It gives the title (a lone series' name when untitled, as Word shows it), the kind, the axes' titles and the nearest caption paragraph.
    - **placement:** after the paragraph anchoring the chart, or after its table when the chart sits in a cell
    - **provenance:** the rows are read as table rows, their claims' derivation "docx-chart"
    - **not read:** the newer chart kinds (chartex: waterfall, histogram, treemap) are recorded as not read, as is a chart whose part can't be parsed
  - **On the real samples:** only the Ericsson Rel-19 views paper has a Word chart (TS 38.300 has none). It's now read: three categories by four series, with its caption.
  - **The knob** (`word.py`, `-charts`): the three chart studies with each chart a Word chart rather than a picture. Values are cached as numbers shown "#,##0", the value axis titled with the unit, the caption after the chart.

    | Study | Facts read right | Claims, charts as data | Claims, charts as pictures |
    |---|---|---|---|
    | cooling energy | 21 of 21 | 23 (the 2 loose are prose, as with pictures) | 23 |
    | energy by end use | 33 of 33 | 33 | 51 |
    | metered electricity (dense) | 51 of 51 | 51 | 51 |

    - Read as data, the charts' values are read right, kept to their month (conditions 19 of 19, 33 of 33, 50 of 50), and read once: a picture's overview and tiles had read the end-use chart's values twice.
    - Cost: $0.014.
- **Equations and comments, and readers versioned (2026-10-04): built.** The owner, on the plans review's cheap wins: "Go for the cheap wins!"
  - **Equations (Office Math) were dropped:** only Word's text runs were read, so TS 38.300's inline symbols vanished from their sentences ("K_offset and K_mac:" read " and :"; "Common TA is a configured timing offset…" read " is a configured…"), along with values (the R2D transmission's subcarrier spacing, Δf=15∙10^3 Hz).
  - **Now written as linear text where they stand:** K_offset, (a+b)/c, x^2, √(x+1), ∑_(i=1)^N x, sin(θ), [a b; c d]. Nine lines of each TS 38.300 version change.
  - **Comments,** as the per-format table always said ("Comments are content, with a provenance annotation saying what they comment on"):
    - each a line after the paragraph (or table) holding its reference: 'Comment by Ana on "the design flow": Check against the 2025 census.'
    - its anchored text cut at 100 characters
    - The RAN1 feature-lead summaries hold two each ('Comment by 作者 on "[Note:": To align with proposal 3.1.1').
  - **A knob,** `wtp-s1-comments`: two sentences moved into reviewers' comments on the sentences before them. 33 of 33 facts read right, conditions kept 11 of 11, $0.002.
  - **Readers versioned** ([decision 0016](../decisions/0016-content-reread-when-its-reader-changes.md)):
    - The gap met with merged cells is closed. Each content item records the version of the reader that extracted it (`extract.READERS`: `pdf/1`, `text/1`, `docx/2`), and a run reads again any item whose reader has changed since, or that has gained a reader.
    - Unchanged queries replay from the cache.
    - Every controlled store was read again this way. No score changed, and nothing new was asked but the new knob's queries.
- **Milestone 3, slide decks (2026-10-04): done.** The owner, choosing between reading slides as Word documents and drawing each slide from its shapes: "This looks good to me, including the recommendation to read slides like Word docs."
  - **No slide is drawn,** since no renderer is assumed. Drawing a slide from its shapes stays a possible later lever, as for Word's shape drawings ([lever index](../reviews/levers.md)).
  - **The reader** (`pptxdocs.py`, with the `office` extra; no new dependency: a deck's parts are read with lxml):
    - each slide a page and a section, titled by its title, or failing one its subtitle or a short text box at its top
      - The Huawei deck titles every slide with a subtitle; others with text boxes. "Slide 3" when none.
    - shapes' paragraphs in reading order (top to bottom in bands, left to right), a group's together, a placeholder placed by its layout or master, automatic numbers written ("2.", "b)")
    - tables on the Word reader's grid (merges: gridSpan, rowSpan, hMerge, vMerge)
    - charts from their data (`chartxml.py`)
    - pictures with the slide's title as caption (pictures are now page-aware; a Word document's tasks are unchanged)
    - speaker notes after the slide's content ("Speaker notes: ...")
    - a hidden slide read, marked "(Hidden slide)"
    - recorded as not read: a slide drawn with shapes joined by connectors (its text read, not its arrangement), SmartArt, media, objects without a preview
    - claims located by slide and line (`PptxLocator`)
  - **On the four sample decks** (Rel-19 AI/ML views): every slide headed by its title but three (a cover and two closing slides, "Slide N"); 7 tables, 1 chart and 7 pictures read; two Huawei slides recorded as shape diagrams (21 and 123 connectors). None has speaker notes.
  - **The controlled corpus as decks** (`slides.py`; from the closed evaluation benchmarks plan): 26 decks of the corpus's representations (a slide per section, tables, charts as charts, the procedure diagram as its WMF), and a **notes knob** (two sentences moved into speaker notes). The decks are minimal (no masters, layouts or theme), enough for any reader of the format.

    | | Decks | Their Word versions |
    |---|---|---|
    | Facts read right | as Word, fact for fact; the specification slightly better (13 against 10 on the renumbered revision) | |
    | Revision pairs (15) | every change, addition and removal found, no false change | the same |
    | End-use study's claims | 33 (its chart read as data) | 51 (as a picture) |
    | Notes knob | 33 of 33 right | |

    - Cost: $0.059.
  - **Fixed on the way:** the lab's run collector listed the formats it reads, without `.pptx`.
- **Milestone 5, Excel, steps 1–4 (2026-10-04): built.** The owner: "Let's do Excel next. 99% of my spreadsheets are Excel."
  - **The reader** (`xlsxdocs.py`, openpyxl in the `office` extra):
    - each sheet a page and a section named by the sheet, in the workbook's order; a hidden sheet read, marked "(Hidden sheet)"
    - cells as Excel shows them: the cached value in its number format (shared with charts: `chartxml.format_number`), dates as ISO dates
    - a formula without a cached value marked "[formula =B6+B7, not calculated]", never evaluated
    - cell comments as lines after their region ("Comment by Ana on A6: ..."); charts from their data; pictures as Word's
    - not read, and recorded: chart sheets; never followed: external links, pivot caches, macros
  - **Regions and the sheet map** (`TextDocument.regions`):
    - Excel's defined tables first, then blocks of filled cells joined through shared edges (two tables touching only at a corner stay two), overlapping blocks merged
    - a lone cell over a wider block split off as its title; narrow label-and-value rows over a table split off as pairs ("Reynolds: 8100000")
    - a region of one row or one column is text; the rest are tables on the Word reader's grid (merges span, header rows labelled by path)
    - **an ambiguous region is skipped, never silently:** a column past the first holding values under no header (tables pressed together) is recorded "skipped: ambiguous sheet layout (Sheet!A8:E11)"
  - **First reading:** tables of up to 50 rows read row by row, as Word's; a longer one recorded "not read yet: it awaits the rules query".
  - **Claims located by sheet and cells** (`XlsxLocator`: "sheet Summary, cells A6:D6"); reader version `xlsx/1`.
  - **On the samples:**
    - the synthetic workbook: regions as its key gives them; the Scratch sheet's two tables touching diagonally skipped as ambiguous, as the key expects
    - the IEA 15 MW and 22 MW workbooks: label-and-value pairs and tables; their long airfoil polars and series await the rules
    - the RAN1 document list: one table, A1:AJ1931, read in about 12 s
  - **The controlled corpus as workbooks** (`workbooks.py`): 26 workbooks, a sheet per section, numbers stored as numbers in their printed formats, a chart's data as a table (its series headed with the axis's unit), the procedure diagram a note.

    | | Workbooks | Their decks |
    |---|---|---|
    | Facts read right | as the decks, fact for fact, in 19 of 26 runs | |
    | The specification (5 runs) | one fact fewer: "per channel group" put in the attribute rather than the conditions | |
    | Revision pairs (14) | every change, addition and removal found, no false change | the same |

    - The attachment study's figures aren't carried into its workbooks (its key holds their 2 prose facts), so its revision, in a figure, leaves its two workbooks the same: no pair.
    - **Fixed on the way:** the first workbooks' chart tables had no unit, and 5 of the energy study's values were read without one. Real workbooks head a series with its unit; so do these now.
    - **Workbooks generated byte for byte the same:** openpyxl stamps the save time into each; it's pinned, as the synthetic samples' is.
    - Cost: $0.045.
- **Milestone 5, Excel, step 5: tables read by rules (2026-10-05): built.** The owner's decision 1 (above): "ask a model how to handle the table ... then ask the model how to handle it, i.e. whether how to produce claims from rows or how to summarize things within a few known templates."
  - **When** (the `table_rules` setting, default 50): a table of more body rows than this is read by rules; 0 sends every table through them, none none. Excel's tables only for now: other formats' tables have no grid for the rules yet.
  - **What the model is shown** (`tablerules.py`, one query per table):
    - the table's place and title
    - each column's header and a mechanical analysis: numbers, dates, text and empty cells counted; distinct values and the most common; the range; an order and an even step ("rising; in steps of 5 min"); prose (by words or characters)
    - sample rows: the first five, three from the middle, the last two, and up to three rows unlike the rest
    - the size and the claims a point per value cell would give
    - **our heuristic opinion,** labelled a guess: a series, a log, points (numbers with no column in order), rows of prose, a list, or claims from rows by rules
  - **What it answers,** one reading:
    - **rules:** templates of a row's cells ("{B}", "{C.name}", "{C.unit}", "{section}"; one template over columns "C:I" with "{*}"), applied to every row mechanically; each claim quotes its cells and its derivation names its template (`table-rules`)
    - **rows:** each row read by itself, as without rules
    - **summary,** within three templates (Claude's): **series** (an input's range and step; each quantity's extremes and where they fall; values at points the model names), **log** (the span and count; each quantity's minimum, maximum, mean and last), **list** (the count; counts by each category's values). Statistics are computed; a mean or a count is marked computed (`table-summary`), a mean approximate.
  - **Checked:**
    - the templates must give the model's own example claims (values and units) for a row it was shown
      - a row named by its place among those shown still counts: the RAN1 list's example "row 6" was the sixth row shown
    - a value marked a number must be one; a row that isn't is read by itself
    - an answer with problems, or rules failing a fifth of the rows, is asked once more with the problems listed; failing again, every row is read by itself
  - **Reader version** `xlsx/2`.
  - **On the samples** (cost $0.68 in all, most of it the IEA workbook's 475 small-table rows, read one by one, and a first RAN1 reading row by row):

    | Workbook | Table | Reading | Claims |
    |---|---|---|---|
    | synthetic | requirements register, 150 rows | rows, each read by itself (the key: each row a requirement) | 144 atomic ("pumping station \| delivery rate \| 10 L/s \| at the design head") |
    | synthetic | flow log, 2,000 rows | summary, log (the key: summarise) | 13 |
    | IEA 15 MW | blade geometry, 60 rows | rules: columns C:I by span position | 420 |
    | IEA 15 MW | 7 airfoil shapes, 101–257 rows | summary, series: x range, y extremes (thickness), y at x = 0 and 1 | 5–6 each |
    | IEA 15 MW | 7 airfoil polars, 120–199 rows | summary, series: alpha range; c_l, c_d, c_m extremes (stall) and their values at 0 or ±180 | 7–13 each |
    | RAN1 #116 document list | 1,930 rows by 36 columns | rules: every column a claim about its document | 30,177, in 90 s, one query |

  - **Fixed on the way, by eye:**
    - **Sentences taken as values:** first reading, the register's requirements became claims whose value was the whole sentence, with three bookkeeping claims a row. Requirements average 11 words but under 60 characters, so they weren't marked prose. Prose is now marked by words too, our opinion says to read such rows by themselves, and the prompt says a value is never a sentence.
    - **Points:** the model named the sample rows it was shown as a series' points (alpha = -175.43…). It's now asked for values that matter on their own (zero, a design point).
    - **A midnight sample** read "2026-07-01" among "2026-07-01 00:05:00": a date and time shows its time when its format does.
  - **The controlled corpus with every table read by rules** (`scripts/controlled.py run --rules`: the 26 workbooks and 14 pairs, `table_rules` 0, scored by the same keys; packed with the standard runs):
    - all 44 tables read by rules on the first answer
    - facts read right, claims and conditions: as row by row in every workbook, but the treatment plant's four, which lose the two claims row-by-row reading made outside the key
    - the 14 revision pairs: as row by row, every change found, no false change
    - on the first prompt, 10 tables were asked again; the fixes below came from them
    - the traps study kept 12 of 12 conditions under the first prompt's rules, 4 of 12 under the final one's (as row by row): the conditions are named only in the text before the table, which the rules query isn't shown (a lever: show it, as `table_context` does for rows)
    - cost: $0.051 (the rules queries); rebuilding the local unaligned pair stores asked $0.091 of comparisons again
  - **Fixed on the corpus:**
    - **units outside brackets:** the coaster's "Vertical g" gave no unit to `{*.unit}`, against the model's example "2.58 g"; asked again, it repeated itself. The problem now says how to mend it (a template of its own for such columns, the unit written out).
    - **a table turned sideways:** the treatment plant's options table holds its units in its row labels ("Capital cost ($M)"); `{A.cell_name}` and `{A.cell_unit}` split a cell as `.name` and `.unit` split a header
    - **n/a** gives no claim, as an empty cell doesn't; an example naming a row read by itself anyway (its value not a number) is no problem
    - `{*.value}`, as the model wrote it, is the cell
    - the rules query's log entry now names its region and content in their places
  - **Findings, not acted on:**
    - **The RAN1 list's 30,177 claims** include bookkeeping (contact IDs, reservation times). The model chose them over the list summary we suggested as an alternative. Whether such columns should be left out is a question for a round.
    - **The IEA polars' header says "alpha [rad]"** over values from −180 to 180: degrees. Claims carry the header's unit, as written.
    - **Full-precision values:** the IEA cells hold 15 significant digits in General format ("3.78071922309736 m"), read as stored. Excel would show fewer in a narrow column.
- **Every Excel table asked how it's read (2026-10-05).** The owner, on step 5's 50-row cut-off: "I was under the impression we'd also ask how to translate rows to claims even for short tables; is this just adding the statistics option for longer ones, because stats might be the more useful view even for tables of 30 items, it's difficult to set a hard boundary." And, going ahead: "I'm sure that we can also extract some levers to improve table handling experimentally. But let's see where we're at with our original vision of this."
  - **The cut-off was Claude's,** from step 4's plan (a row-by-row baseline the rules must beat), not the owner's decision 1, which had size as an input to our opinion.
  - **Changed:**
    - `table_rules` 0 by default: every Excel table is asked; none reads every table row by row, the baseline (`scripts/controlled.py run --rows`, replacing `--rules`)
    - **our opinion without a cut-off:** it names the table's shape (a series, a log, a set of points, a list) and weighs a summary by size, graded: an aside under 20 rows ("with 10 rows a summary would save little"), one of two readings from 20, the likelier from 100
      - prose decides the reading where it's a third of the table's text, else it's an aside; a list needs records mostly of text
    - **the context a row would be given** (the text above the table, its headings) is shown with the table, and the prompt says a condition it names for every row belongs in the templates
    - reader version `xlsx/3`
  - **The controlled workbooks,** every table asked against every row by itself:

    | | Every table asked | Row by row |
    |---|---|---|
    | Queries for tables | 44 (all read by rules on the first answer) and 10 rows read by themselves | 288 |
    | Facts read right, of 1,034 | 943 | 959 |
    | Traps study, conditions kept (2 runs) | 12 of 12 | 4 of 12 |
    | Treatment plant (4 runs) | the same facts, without 2 claims outside the key (n/a cells) | |
    | Cooling energy study (2 runs) | 14 of 21 right, 5 misbound | 19 of 21 |
    | End use study | 27 of 33 right, 6 loose | 33 of 33 |
    | Revision pairs (14) | as row by row but the energy study's: 4 of 5 changes, 12 of 16 unchanged confirmed | every change found |

    - **The misbinding:** in the charts' data tables, the rules made each month the entity and each series ("Option 1, chilled beams") the attribute. Row by row, the quantity comes from the caption ("cooling energy"), the option is the entity and the month a condition. The rules query has none of the extraction instructions' guidance on alternatives, entities and conditions.
  - **The samples** ($0.04):
    - **IEA 15 MW:** 43 tables, 24 by rules and 19 summarised, none failing twice; 68 queries ($0.04) against 510 ($0.29) when the short tables were read row by row. With size graded, the model now summarises mid-sized distributions it read by rules before: blade geometry (60 rows), structural properties (25), tower (40), rotor performance (50).
    - **The synthetic workbook's short tables, by eye against its key:**
      - design basis: a claim a row; its uncalculated formula a claim valued "[formula =C6+C7, not calculated]"
      - pump schedule: right, units from the headers, with a Duty or Standby claim a row beside the key's 3
      - commissioning results: the value and ± columns made two claims ("measured value", "measured tolerance"), where the key has one composite
      - the superseded sheet: entity and attribute swapped ("Design flow | Parameter | 110 L/s"), marked "Rev B (superseded)"
      - every design basis row conditioned on the document's revision line
    - **RAN1 document list:** a list summary (69 claims) rather than 30,177 claims by rules over every column: prose is now an aside where it's a small part of the text
  - **Candidate levers** (the owner: "extract some levers to improve table handling experimentally"), in the [lever index](../reviews/levers.md)'s ideas:
    - the extraction instructions' guidance on entities, conditions and alternatives in the rules query
    - an uncertainty template for value and ± columns
    - our opinion's grading, its wording, or none
    - bookkeeping columns, the examples check, uncalculated formulas
- **Binding in the rules query (2026-10-05).** The owner: "Yes, please work on improving binding a bit. You can run several experiments at that cost if needed."
  - **Four prompt variants** on the 26 controlled workbooks: binding conventions, a worked example, a sentence the model writes first, and all three. The [lever index](../reviews/levers.md) has the table; all three together read best.
  - **Adopted** (`tablerules.py`, reader version `xlsx/4`):
    - **how a claim is bound,** as in any extraction:
      - the attribute is the property measured, never an option's or a series' name
      - the entity is the thing with the value: an item, or an alternative being compared
      - conditions are the circumstances, never the document's own details
      - columns that are alternatives of one quantity name the entity, the quantity is the attribute, and the row's label is a condition
    - **a worked example:** "Monthly cooling energy", columns Option 1 and Option 2: entity the option, attribute "cooling energy" written out, the month a condition
    - **"binding":** the model first writes what the values measure, what has them and under what; kept in the coverage record
  - **The controlled workbooks,** every table asked against row by row:

    | | Every table asked | Row by row |
    |---|---|---|
    | Facts read right, of 1,015 scored | 959 | 959 |
    | Misbound | 10 | 10 |
    | Traps study, conditions kept (2 runs) | 12 of 12 | 4 of 12 |
    | Claims outside the key (treatment plant, n/a cells) | none | 8 |
    | Revision pairs (14) | the same in every pair: every change found, no false change | |
    | Queries for tables | 44, and 10 rows read by themselves | 288 |

  - **Still fragile:** a one-series table ("Option 1, chilled beams (tons)") flipped between its series name and "peak cooling load" as the attribute under small changes to the prompt.
  - **By eye on the samples:** the IEA overview's entity became the turbine; the synthetic workbook's commissioning table reads "Pump system | Flow at duty point | 118 L/s | Measured"; its superseded sheet's swap is fixed but its "superseded" mark is lost.
  - Cost: $0.12 for the experiments, $0.003 for the pairs.
- **Worked examples in the rules query (2026-10-05).** The owner: "If one worked example helped, would two or three diverse examples help more? Seems a lever worthy of a check."
  - **Leakage:** the first example mirrored a corpus table. The fresh ones (heating demand by design, rotor performance by wind speed, motor options with units in the row labels, settlement by pier) come from outside the corpus.
  - **Measured** on the 26 workbooks and on 26 from the corpus's second seed:

    | Examples | Facts right, both seeds | Misbound | Conditions kept |
    |---|---|---|---|
    | none | 1,863 of 2,030 | 71 | all |
    | one, corpus-like (shipped before) | 1,910 | 24 | all |
    | one, fresh | 1,905 | 29 | all |
    | two, fresh | 1,915 | 19 | 438 of 446 |
    | **three, fresh (adopted)** | **1,915** | **19** | **all** |
    | four, fresh | 1,915 | 19 | all |
    | row by row | 1,915 | 19 | 414 of 446 |

  - **Adopted:** three fresh examples (`tablerules.py`, reader `xlsx/5`). The [lever index](../reviews/levers.md) has the details.
  - **On the committed corpus with pairs:** facts as row by row, every condition kept. One pair is worse: the specification's Session ID change is judged uncertain, because its two revisions' rules bound the length differently. That adds a lever idea: the same rules for a table in both revisions.
  - Cost: $0.35.

## Open questions

None currently.
