# How it works

This describes the current code: comparing two PDFs, with evidence in the content-based schema v2. The generalized design (sources as folders and archives, a persistent store, criteria-first comparison, more formats) is planned in [plans/](plans/README.md) and not yet implemented.

## Claims and provenance

All modalities become atomic claims with `entity`, `attribute`, `value`, `unit`, `conditions`, `kind`, `quote`, `confidence` and `approximate`, plus context fields (`topic`, `basis`, `uncertainty`, `context`, `role`) that prompts don't request yet and so default to "not stated". A chart operating point can therefore match a table row, and a diagram connection can match a sentence.

Provenance (schema v2):

- Each input PDF is a **source** containing one **file**, which refers to **content**: the SHA-256 of its bytes plus its normalized extension (`sha256:…​.pdf`).
- Evidence attaches to content, never to paths. Each item has a **locator** within the content (one-based page, bounding box in unrotated PDF points, the extraction pass and task) and a **derivation** listing the steps from bytes to claim. Visual claims retain the exact PNG the model saw.
- Evidence IDs derive from content, locator and claim, so they are stable across renames. The same PDF supplied as both sources is extracted once; its evidence is listed as *shared* and never sent for comparison.
- `evidence.json` and `report.json` record the **interpreters**: the model, a hash of the prompts, the settings that affect output, and library versions.

## Pipeline

1. **Native extraction:** Consecutive PDF text blocks are grouped up to the UTF-8 byte budget (oversized blocks are split), so headings and short labels travel with their context; each claim keeps the bounding box of the block containing its quote. Detected tables are sent row by row with the first row repeated as a provisional header; rows over budget are split by column, repeating the header and the first column as a provisional row label. Native claims whose supporting quotes are absent from the input are rejected; table quotes may span adjacent cells.
2. **Visual extraction:** Every page receives evenly spaced overlapping tiles (at least 18% overlap) and an overview. This includes scanned pages and vector diagrams that embedded-image extraction would miss. The same small model reads labels, graph axes and series, table relationships and diagram connections. Approximate graph readings remain explicitly approximate. Where the rendered region has a PDF text layer, each visual quote is checked against it and the result is recorded as `quote_verified` (`false` flags a possible misread or a raster-only label; it does not reject the claim).
3. **Bounded refinement:** Partial/failed text groups are split on block boundaries (single blocks by bytes); partial/failed table rows are split by column, keeping header and row label; partial/failed visual tiles are subdivided. All are bounded by `refinement_depth`. Original failures remain in the coverage ledger even if smaller tasks succeed. Nothing silently declares exhaustive coverage.
4. **Global retrieval:** Sparse TF-IDF over normalized claim entities, attributes, conditions and values generates a bidirectional top-k union. Claims can match across pages, order, layout and modality, with one-to-many matches. User-provided domain aliases improve synonym recall. No model holds the full corpus.
5. **Local comparison:** One claim pair per request, with source images where available. The model distinguishes equivalent, different, complementary, unrelated and uncertain. A deterministic decimal calculator checks supported unit conversions. Unestablished conditions, approximate readings, low confidence or inconsistent arithmetic veto confident difference/equivalence judgments.
6. **Review report:** Filter/search findings, inspect both sources, review numeric checks, unmatched evidence, provenance and task-level coverage. No model-generated global summary is needed.

## Modes

Proposal mode is symmetric and does not rank teams. Revision mode labels A as earlier and B as later; numeric deltas are B minus A. Neither mode calls unmatched evidence a proven addition/deletion. Absence is harder to establish than a local difference.

## Model output handling

Model output is validated; unknown keys are ignored, individually malformed claims are discarded (the task is then marked partial), and malformed/truncated responses are retried and ultimately recorded as failures. Fenced or prose-wrapped JSON is accepted. Exact duplicate claims within the native or the visual passes on one page are kept once.

## Code map

| Module | Responsibility |
| --- | --- |
| `models.py` | Validated settings and evidence schemas |
| `llm.py` | Compatible API transport, request budgeting, retries and cache |
| `extract.py` | PDF text/tables, page/tile rendering, refinement and provenance |
| `compare.py` | Retrieval, local reasoning and numeric checks |
| `report.py` | Escaped HTML and JSON reports |
| `cli.py` | Orchestration, planning and exit semantics |

API contracts were checked against the [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) and [PyMuPDF Page documentation](https://pymupdf.readthedocs.io/en/latest/page.html). Provider compatibility still needs a live smoke test.
