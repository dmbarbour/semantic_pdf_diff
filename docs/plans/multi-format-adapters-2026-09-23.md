# Multi-format source adapters

- **Status:** Planned. Format priority (2026-09-23): PDF, then `.docx` and `.pptx`; Cameo models via a separate project.
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

## Decisions (2026-09-23)

- **Spreadsheet claims are marked by provenance, not trust.** A claim read directly from cells is *more direct* than one a model extracted from prose or a chart, and its derivation says so (see *Derivation* in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md)). Directness is not reliability. A spreadsheet still raises questions: is our interpretation of the columns right (and if a model interpreted the headers, that is itself a model step in the derivation)? Is a value a measurement, a projection, a requirement or wishful thinking? Are uncertainties given? Those are judged like any other claim (see *Epistemic status* in [scheduling-and-triage](scheduling-and-triage-2026-09-23.md)), not assumed away.

## Open questions

None currently.
