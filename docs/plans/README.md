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
| [Sources, content and evidence store](sources-and-evidence-store-2026-09-23.md) | SQLite store (resumable, many views); evidence attached to content (SHA-256 + extension) shared across sources; folders and zips as sources; revisions as content differences; interpreter metadata; staged CLI. The foundation for everything else. |

## Planned

| Plan | Summary | Depends on |
|---|---|---|
| [Scheduling and triage](scheduling-and-triage-2026-09-23.md) | Time-of-day rate limits and adaptive concurrency for the in-house server; fair share across sections and sources; status-stamped preliminary reports; section triage with "about" statements; claim quality signals, epistemic status (basis, uncertainty) and skeptical prompting. | Evidence store |
| [Units and normalization](units-and-normalization-2026-09-24.md) | Structured quantities (intervals, bounds, tolerances), compound units with explicit ambiguity rules, money compared only in the same currency and price basis, same-source normalization for criteria, statistics in common units. Abstain, never guess. | None strictly |
| [Criteria-first comparison](n-way-comparison-2026-09-23.md) | Criteria first (for two-way proposals too): compare N sources by reviewed, evidence-based criteria (extracted from rules, requirements or the user's rubrics, or recommended), with applicability, per-source synthesis and a criteria × sources matrix. Compares, never judges. Revisions stay claim-level. | Evidence store; triage for "about" statements |
| [Multi-format adapters](multi-format-adapters-2026-09-23.md) | `.txt`/`.md`, then `.docx` and `.pptx` (chart XML), then external converters, then `.csv`/`.xlsx` (table detection plus model-guided interpretation), then images. Cameo output is consumed as an ordinary source. | Evidence store |
| [Single-source outputs](single-source-outputs-2026-09-23.md) | `check` for internal consistency; RAG `export` as self-contained Markdown chunks with provenance; a fact sheet built without the model; a shared writing style for people. (Cited summaries within it are tentative.) | Evidence store; triage for "about" statements |
| [Evaluation benchmarks](evaluation-benchmarks-2026-09-23.md) | Extraction quality (recall, precision, hallucinations, values, qualifiers, provenance, coverage honesty) on curated public pages and synthetic documents with known contents; retrieval and comparison labels; all answer keys committed as annotation export files, with good and bad reviewer-decision variants. Built together with Claude. | Record/replay responder tables |
| [Retrieval recall](retrieval-recall-2026-09-23.md) | Model-generated section keywords, alias consolidation, hybrid lexical + embedding retrieval (claim-to-claim and claim-to-criterion), with the in-house embedding models run locally for development. | Retrieval benchmark (built alongside) |
| [Test models and record/replay](test-models-and-record-replay-2026-09-24.md) | Replay realistic model responses offline: requests keyed by meaning (not bytes), recorded in rounds on a small curated slice of the public corpus, answered by Claude (strong reference), a weak local VLM, optionally in-house gemma-4, plus the stub for failures; stored as zipped SQLite fixtures in the repo. Local embedding servers cover embeddings. | Evidence store (response cache) |

## Tentative

| Plan | Summary | Waiting on |
|---|---|---|
| Approach-level comparison *(plan not yet written)* | Summarize each source's *approach* to the shared ends, including primary components and processes; group sources that take the same approach, and compare within a group on what only that approach makes comparable (e.g. rotor speed among turbines, not against solar), while criteria compare across groups. Applied recursively to subsystems ("fractally"). Still compares, never judges. | Criteria-first comparison; triage "about" statements |
| Query-driven reports *(plan not yet written)* | When requesting a report, support a query to filter and focus a report |
| Minimal-interpretation mode *(plan not yet written)* | A long-term option to limit how much model interpretation stands between a source and its evidence, e.g. favouring literal, verbatim or deterministic extraction. Motivated by layered interpreters, such as model summaries of models. | Evidence store; format adapters |
| Interactive views *(plan not yet written)* | Live views over a store while a run proceeds: status-stamped preliminary reports, criteria review (propose → review → run), pending alias and keyword questions, review annotations. Terminal UI first (usable inside a sandbox), favouring a library that is easy to work with, extend and modify (e.g. Textual); a local web server later for other users. | Evidence store; preliminary reports from scheduling |
| Automatic source partitioning *(plan not yet written)* | Provide users tools to partition a body of documents and evidence across teams (recognizing multiple components) and timelines (recognizing multiple versions of a file), so users don't need to partition manually. |

## Completed

| Plan | Summary |
|---|---|
| [Robustness baseline (0.2.0)](robustness-baseline-2026-09-23.md) | Tagged `v0.2.0` as the stable baseline. Fixed API-shape crashes, table refinement, unit case folding and de-duplication; text grouping, tile spacing, visual quote checks, tolerant parsing. |

## Suggested order

Nobody uses the tool between now and implementation (the stable baseline is tagged `v0.2.0`), so plans and checkpoints can be reordered, split or merged freely.

1. Evidence store (active)
2. Scheduling and triage (concurrency, progress and logging, sections, "about" statements, epistemic status)
3. Test models and record/replay, then evaluation benchmarks and retrieval recall (criteria-first comparison relies on claim-to-criterion retrieval)
4. Units and normalization, then criteria-first comparison: the main use case, two-way proposals included
5. Adapter interface with `.txt` / `.md`, then `.docx` and `.pptx`
6. Single-source `check` and RAG `export`
7. External converters, `.csv` / `.xlsx`, images

## Deferred decisions

- **Project name:** `semantic_pdf_diff` will become a misnomer as scope grows. The owner will rename it later; it's not blocking.
