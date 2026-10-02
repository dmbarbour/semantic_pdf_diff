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
5. **Local comparison:** One claim pair per request, with source images where available. The model distinguishes equivalent, different, complementary, unrelated and uncertain. A deterministic decimal calculator checks supported unit conversions. Unestablished conditions, approximate readings, low confidence or inconsistent arithmetic veto confident difference/equivalence judgments.
6. **Review report:** Filter/search findings, inspect both sources, review numeric checks, unmatched evidence, provenance and task-level coverage. No model-generated global summary is needed.

## Modes

Evidence from content present in both sources is **shared**: listed once, never compared with itself, but used as a retrieval target, so a claim in changed content whose counterpart sits in shared content isn't reported as unmatched. Reports also summarize the **file-level difference**: files unchanged, modified (same relative path, different content), moved or renamed (same content, different path), added and removed, with paths compared relative to each source's roots (so `rev1/x.pdf` lines up with `rev2/x.pdf`).

Proposal mode is symmetric and does not rank teams. Revision mode labels A as earlier and B as later; numeric deltas are B minus A. Neither mode calls unmatched evidence a proven addition/deletion. Absence is harder to establish than a local difference.

## Model output handling

Model output is validated; unknown keys are ignored, individually malformed claims are discarded (the task is then marked partial), and malformed/truncated responses are retried and ultimately recorded as failures. Fenced or prose-wrapped JSON is accepted. Exact duplicate claims within the native or the visual passes on one page are kept once.

## Code map

| Module | Responsibility |
| --- | --- |
| `models.py` | Validated settings and evidence schemas |
| `llm.py` | Compatible API transport, request budgeting, retries and cache |
| `extract.py` | PDF text/tables, page/tile rendering, refinement and provenance |
| `situate.py` | Figures, captions and citing prose; figure and section "about" requests |
| `compare.py` | Retrieval, local reasoning and numeric checks |
| `report.py` | Escaped HTML and JSON reports |
| `provenance.py` | Content IDs, extension normalization, interpreter descriptions |
| `scan.py` | Scanning a source's roots: folders, zip archives, hidden files, safety limits |
| `manifest.py` | Source manifests: export and import |
| `throttle.py` | Rate limits with time-of-day rules; adaptive concurrency |
| `dispatch.py` | Worker threads for model requests; everything else stays on the main thread |
| `progress.py` | Progress bars, heartbeats and logging |
| `store.py` | SQLite evidence store: binding, per-task records, semantic response cache, comparisons |
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
