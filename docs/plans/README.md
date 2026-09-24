# Plans

Design plans for the project, named `<topic>-<YYYY-MM-DD>.md` by the date each was written. Update a plan's **Status** line and this index together when its state changes.

Statuses:

- **Active:** being worked on now.
- **Planned:** agreed direction, not started.
- **Tentative:** worth doing, but the design or priority depends on earlier results.
- **Completed:** done; kept as a record of what changed and why.

## Active

| Plan | Summary |
|---|---|
| [Sources, content and evidence store](projects-and-evidence-store-2026-09-23.md) | SQLite store (resumable, many views); evidence attached to content (SHA-256 + extension) shared across sources; folders and zips as sources; revisions as content differences; interpreter metadata; staged CLI. The foundation for everything else. |

## Planned

| Plan | Summary | Depends on |
|---|---|---|
| [Scheduling and triage](scheduling-and-triage-2026-09-23.md) | Rate-aware concurrency for the in-house server (tokens/min), fair share across sections, section triage, claim quality signals (reliability / specificity / salience). | Evidence store |
| [Multi-format adapters](multi-format-adapters-2026-09-23.md) | `.txt`, `.md`, `.csv`, `.xlsx` (deterministic claims), `.docx`, `.pptx` (chart XML), images; optional LibreOffice fallback. | Evidence store |
| [Single-project outputs](single-project-outputs-2026-09-23.md) | `check` for internal consistency, `export` for RAG, a fact sheet built without the model. (Cited summaries within it are tentative.) | Evidence store |
| [Retrieval benchmark](retrieval-benchmark-2026-09-23.md) | Future: a labelled answer key of claim pairs, built together with Claude, to measure retrieval methods. | None strictly |

## Tentative

| Plan | Summary | Waiting on |
|---|---|---|
| [Retrieval recall](retrieval-recall-2026-09-23.md) | Model-generated section keywords, alias consolidation, hybrid lexical + embedding retrieval. | Retrieval benchmark results |
| [N-way comparison](n-way-comparison-2026-09-23.md) | Compare N projects via topic clusters and a comparison matrix; ordered revision series. | Evidence store; ideally retrieval recall |
| Interactive views *(plan not yet written)* | Live views over a store while a run proceeds: status-stamped preliminary reports, pending alias and keyword questions, review annotations. Terminal UI first (usable inside a sandbox), favouring a library that is easy to work with, extend and modify (e.g. Textual); a local web server later for other users. | Evidence store; preliminary reports from scheduling |

## Completed

| Plan | Summary |
|---|---|
| [Robustness baseline (0.2.0)](robustness-baseline-2026-09-23.md) | Fixed API-shape crashes, table refinement, unit case folding and de-duplication; text grouping, tile spacing, visual quote checks, tolerant parsing. |

## Suggested order

1. Evidence store (active)
2. Scheduling and triage (needed before large folders are practical)
3. Single-project `check` / `export`, and the `.txt` / `.md` / `.csv` adapters, both cheap once the store exists
4. Retrieval benchmark, which can start any time; then retrieval recall
5. Remaining adapters (`.xlsx`, `.docx`, `.pptx`), in the order users need them
6. N-way comparison

## Deferred decisions

- **Project name:** `semantic_pdf_diff` will become a misnomer as scope grows. The owner will rename it later; it's not blocking.
