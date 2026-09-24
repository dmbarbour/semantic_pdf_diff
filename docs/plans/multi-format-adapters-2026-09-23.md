# Multi-format source adapters

- **Status:** Planned. Format priority (2026-09-23): PDF, then `.docx` and `.pptx`; Cameo models via a separate project.
- **Depends on:** [projects-and-evidence-store](projects-and-evidence-store-2026-09-23.md) (locators, sections, store)

## Goal

Accept common report formats beyond PDF: `.txt`, `.md`, `.csv`, `.xlsx`, `.docx`, `.pptx`, images, and possibly legacy Office formats. Every claim keeps fine-grained provenance.

## Key idea

Most of these formats are **better sources than PDF**, because their structure is explicit rather than guessed. Each adapter produces the same intermediate units:

- **text segments** with a heading path
- **structured tables** (header plus rows, with a known cell locator)
- **renderable visual regions** (embedded images, figures)

Only content that is truly unstructured goes to the model. Structured data should become claims **deterministically** wherever possible.

## Per-format approach

| Format | Approach | Notes |
|---|---|---|
| `.txt`, `.md` | Text segments. Markdown headings give the heading path and sections. | Cheap; do first. |
| `.csv`, `.xlsx` | **Deterministic claims:** entity = row label, attribute = column header, value = cell. Units parsed from headers like `Power (kW)`. At most one model call per table, to interpret ambiguous headers. | A model call per row doesn't scale to a 10k-row sheet, and it adds error to exact data. Handle merged and multi-row headers, formulas (use cached values), hidden sheets. Never follow external links. |
| `.docx` | Real paragraphs, heading styles and real tables via `python-docx`. Embedded images go to the visual pipeline. | No table detection needed; quote checks become exact. |
| `.pptx` | Text per shape, tables, and **chart XML, which holds the actual series data**. Embedded images go to vision. | Chart XML beats estimating values from pixels. SmartArt and grouped shapes are the awkward cases. |
| Images (`.png`, `.jpg`, scans) | Straight into the existing visual pipeline. | Nearly free. |
| Legacy `.doc`/`.ppt`/`.xls`, or visual fidelity for Office files | Optional headless LibreOffice conversion to PDF. | Provenance maps only to the converted PDF's pages, so this is a fallback, not the main path. |

Candidates for later: HTML, and email exports.

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
4. External converter interface, with LibreOffice as the first configured converter. This is also the integration point for Cameo `.mdzip` models, which are being digested in a separate project: its output formats become inputs here.
5. `.csv` / `.xlsx` with deterministic claims.
6. Images.

## Open questions

- **Samples for `.docx` and `.pptx`:** the public corpus has none yet. Find freely available engineering reports and slide decks (ideally competing or revised versions) and add them to `scripts/samples.json` before milestone 2.
- **Cameo integration:** what will the separate Cameo project produce (XMI, CSV, HTML, diagram images, or claims directly)? That decides whether it plugs in as an external converter or as an importer of ready-made evidence.
- How should a deterministic spreadsheet claim be marked (source kind, reliability) relative to model-extracted claims?
- Should very large sheets get per-table sampling or summary statistics instead of one claim per cell?
