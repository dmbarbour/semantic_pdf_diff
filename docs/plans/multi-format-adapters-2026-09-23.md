# Multi-format source adapters

- **Status:** Active (2026-10-03): milestones 1 (`.txt`/`.md` and a shared task core) and 2 (`.docx`) done; next, `.pptx`. Format priority (2026-09-23): PDF, then `.docx` and `.pptx`; Cameo models via a separate project.
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
| Legacy `.doc`/`.ppt`/`.xls`, or visual fidelity for Office files | Optional headless LibreOffice conversion to PDF. | Provenance maps only to the converted PDF's pages, so this is a fallback, not the main path. |

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
- The LibreOffice fallback for legacy Office formats becomes just one configured converter.

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
3. `.pptx`, including chart XML.
4. External converter interface, with LibreOffice as the first configured converter.
5. `.csv` / `.xlsx`: table region detection and sheet maps, then model-guided table interpretation.
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

## Open questions

None currently.
