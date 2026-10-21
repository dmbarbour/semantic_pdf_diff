# 0020. Every format is read through one task core into the PDF's evidence units

- **Status:** Accepted (2026-10-03; images 2026-10-07)
- **Source:** [multi-format adapters](../plans/README.md#retired), milestone 1 in detail and its decisions; milestone 6 (images); the [evidence store plan](../plans/README.md#retired)'s decisions of 2026-09-24 (content against annotation, document versions); its measurements in [formats beyond PDF](../research/formats-beyond-pdf-2026-10-07.md)

## Context

Sources arrive as PDF, plain text, Markdown, Word, PowerPoint, Excel, CSV and images. Each format could have had its own prompts, task names and handling, which would make every format's claims differ for reasons other than their content, and make one format's lessons useless to the others.

## Decision

- **One task core** (`tasks.py`): the PDF job was refactored into it byte-identically, and every reader feeds it text blocks, tables and pictures. The owner (2026-10-03): "I agree with all three recommendations."
- **The same region names and prompts:** a text format's paragraph is a "text" task and its table a "table" task, asking what a PDF's would.
- **Locators by format** (`PdfLocator`, `TextLocator`, `DocxLocator`, `PptxLocator`, `XlsxLocator`, `CsvLocator`), with excerpts in reports where there's no page to show.
- **Images are read by the PDF reader** as one-page documents made in memory (`extract.image_pdf`): their overview and tiles read them, as a scanned page is. A scan recording 150 dpi or more keeps its paper size; any other image is laid out so a tile shows its pixels one to one.
- **No external converter is assumed.** The owner (2026-10-04): LibreOffice an optional extra dependency at most, a very low priority; legacy `.doc`, `.ppt` and `.xls` are recorded as unsupported.
- **Content made by other tools is read as any source is** (decided 2026-09-23): Cameo `.mdzip` models arrive as a separate project's folders of Markdown and CSV, read by the text and CSV readers, no converter needed. Content made by external tools, model-written summaries included, isn't judged here: whether it's weaker evidence is its provider's call, passed through to evidence and reports (the front matter carrying it is unbuilt: *More formats* in the [plans index](../plans/README.md#tentative)).
- **Inputs are treated as hostile:** no macro runs, no external link or pivot cache is followed (an Office part's external relationships are dropped), and no formula is evaluated ([0022](0022-spreadsheet-cells-as-excel-shows-them.md)).
- **Text laid out for a monospace font is sent as text, its spacing kept,** so arrows and simple structures are read; there's no dedicated reader for drawings made of characters. The owner (2026-10-03): "I would add caution on recognizing ASCII art. We should still recognize simple arrows and such."
- **What a reader doesn't know the purpose of is content,** its place its provenance (the evidence store plan's decisions, 2026-09-24): speaker notes after the slide's content ("Speaker notes: ..."), a comment after the paragraph it's on, naming its author and the text it's about.
- **A document is read as it currently is,** never an earlier version within one file (the same decisions): Word's tracked changes applied. The owner (2026-10-03): "For tracked changes, we'll generally process the changes-applied version, but that must be tested if not already."

## Consequences

- A prompt or lever change applies to every format at once, and the same facts written in several formats are a control: the controlled corpus is scored as PDF, Markdown, Word, slides and workbooks by the same keys (the owner, 2026-10-02: "we'll implicitly get a new form of control tests: same facts across two or more representations").
- Each reader carries a version ([0016](0016-content-reread-when-its-reader-changes.md)).
- On the controlled corpus, Markdown and Word read every fact the PDFs did (recall 1.000), decks as Word and workbooks as the decks in 19 of 26 runs; the PDF schedules' misbinding (6 and 18 claims) was none in Markdown and Word: it came from the PDF's layout (the text layer's column shifts, the image reader's row names), not from the tables' content ([formats beyond PDF](../research/formats-beyond-pdf-2026-10-07.md)).
- An image in a folder source costs vision tasks like a scanned page.
