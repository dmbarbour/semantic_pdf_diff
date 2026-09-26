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
| [Evaluation benchmarks](evaluation-benchmarks-2026-09-23.md) | Review batches sampled from recorded answers, labelled by the owner, Claude and a panel of hosted models (verdict, error flags, clarity, confidence), with agreement measured; plus extraction, retrieval and comparison benchmarks on curated public pages and synthetic documents. |
| [Test models and record/replay](test-models-and-record-replay-2026-09-24.md) | Replay recorded model answers offline: requests keyed by meaning (not bytes) plus an interpreter fingerprint, recorded by running the pipeline live against hosted gemma-4 (and other models for comparison) on deterministic slices of the public corpus; stored as zipped SQLite fixtures in the repo. |
| [Scheduling and triage](scheduling-and-triage-2026-09-23.md) | Time-of-day rate limits and adaptive concurrency for the in-house server; fair share across sections and sources; status-stamped preliminary reports; section triage with "about" statements; claim quality signals, epistemic status (basis, uncertainty) and skeptical prompting. |

## Planned

| Plan | Summary | Depends on |
|---|---|---|
| [Query improvement in rounds](query-improvement-2026-09-26.md) | Improve queries (context, chunking, crops, instructions) in repeated rounds: one lever per variant, judged on the same inputs as the current baseline (pairwise, by the panel, anchored by the owner), accepted only without a loss in any stratum; history graphed with cost. | Record/replay; evaluation benchmarks |
| [Units and normalization](units-and-normalization-2026-09-24.md) | Structured quantities (intervals, bounds, tolerances), compound units with explicit ambiguity rules, money compared only in the same currency and price basis, same-source normalization for criteria, statistics in common units. Abstain, never guess. | None strictly |
| [Criteria-first comparison](n-way-comparison-2026-09-23.md) | Criteria first (for two-way proposals too): compare N sources by reviewed, evidence-based criteria (extracted from rules, requirements or the user's rubrics, or recommended), with applicability, per-source synthesis and a criteria × sources matrix. Compares, never judges. Revisions stay claim-level. | Evidence store; triage for "about" statements |
| [Multi-format adapters](multi-format-adapters-2026-09-23.md) | `.txt`/`.md`, then `.docx` and `.pptx` (chart XML), then external converters, then `.csv`/`.xlsx` (table detection plus model-guided interpretation), then images. Cameo output is consumed as an ordinary source. | Evidence store |
| [Single-source outputs](single-source-outputs-2026-09-23.md) | `check` for internal consistency; RAG `export` as self-contained Markdown chunks with provenance; a fact sheet built without the model; a shared writing style for people. (Cited summaries within it are tentative.) | Evidence store; triage for "about" statements |
| [Retrieval recall](retrieval-recall-2026-09-23.md) | Model-generated section keywords, alias consolidation, hybrid lexical + embedding retrieval (claim-to-claim and claim-to-criterion), with the in-house embedding models run locally for development. | Retrieval benchmark (built alongside) |

## Tentative

| Plan | Summary | Waiting on |
|---|---|---|
| Approach-level comparison *(plan not yet written)* | Summarize each source's *approach* to the shared ends, including primary components and processes; group sources that take the same approach, and compare within a group on what only that approach makes comparable (e.g. rotor speed among turbines, not against solar), while criteria compare across groups. Applied recursively to subsystems ("fractally"). Still compares, never judges. | Criteria-first comparison; triage "about" statements |
| Query-driven reports *(plan not yet written)* | When requesting a report, support a query to filter and focus a report |
| Include/exclude patterns for sources *(plan not yet written)* | Glob patterns in a source definition to include or exclude files under its roots (beyond the built-in hidden-file rule), for sources that share a folder tree or carry clutter. | Source registry (store milestone 5) |
| Git revisions as sources *(plan not yet written)* | Stretch goal: declare a source from a git revision (e.g. `team-a@v2` from a repository), so comparing revisions of a versioned document set needs no manual copies. | Source registry (store milestone 5) |
| Minimal-interpretation mode *(plan not yet written)* | A long-term option to limit how much model interpretation stands between a source and its evidence, e.g. favouring literal, verbatim or deterministic extraction. Motivated by layered interpreters, such as model summaries of models. | Evidence store; format adapters |
| Interactive views *(plan not yet written)* | Live views over a store while a run proceeds: status-stamped preliminary reports, criteria review (propose → review → run), pending alias and keyword questions, review annotations. Terminal UI first (usable inside a sandbox), favouring a library that is easy to work with, extend and modify (e.g. Textual); a local web server later for other users. | Evidence store; preliminary reports from scheduling |
| Evidence webs *(plan not yet written)* | Link claims that support, derive from or relate to one another (same quantity stated in text and a table, a value computed from others, a figure explaining a number) into webs that contribute to (or contradict) a claim's confidence and derivation. Situating's figure–prose links and claim quality signals are the first threads. | Situating stage; claim quality signals; units and normalization (for derivations) |
| Interactive zoom for models *(plan not yet written)* | Let a model ask for zoomed-in regions while reading (progressive disclosure within a request quota), since fixed image budgets lose small labels on drawings (e.g. 2'-9 1/2" read as 2'-3"). Possibly limited interaction in general. Raised by the owner in the s01 review. | Evaluation benchmarks (to measure the gain); record/replay of multi-turn requests |
| Automatic source partitioning *(plan not yet written)* | Provide users tools to partition a body of documents and evidence across teams (recognizing multiple components) and timelines (recognizing multiple versions of a file), so users don't need to partition manually. |

## Completed

| Plan | Summary |
|---|---|
| [Sources, content and evidence store](sources-and-evidence-store-2026-09-23.md) | SQLite store (resumable, many views); evidence attached to content (SHA-256 + extension) shared across sources; folders and zips as sources; revisions as content differences; interpreter metadata; staged CLI. Completed 2026-09-24 (reviewer-decision records arrive with their first consumer). |
| [Robustness baseline (0.2.0)](robustness-baseline-2026-09-23.md) | Tagged `v0.2.0` as the stable baseline. Fixed API-shape crashes, table refinement, unit case folding and de-duplication; text grouping, tile spacing, visual quote checks, tolerant parsing. |

## Suggested order

Nobody uses the tool between now and implementation (the stable baseline is tagged `v0.2.0`), so plans and checkpoints can be reordered, split or merged freely.

1. ~~Evidence store~~ (completed)
2. Scheduling and triage (active) (concurrency, progress and logging, sections, "about" statements, epistemic status)
3. Test models and record/replay, then evaluation benchmarks and retrieval recall (criteria-first comparison relies on claim-to-criterion retrieval)
4. Units and normalization, then criteria-first comparison: the main use case, two-way proposals included
5. Adapter interface with `.txt` / `.md`, then `.docx` and `.pptx`
6. Single-source `check` and RAG `export`
7. External converters, `.csv` / `.xlsx`, images

## Deferred decisions

- **Project name:** `semantic_pdf_diff` will become a misnomer as scope grows. The owner will rename it later; it's not blocking.
