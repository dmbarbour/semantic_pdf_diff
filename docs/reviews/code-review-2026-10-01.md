# Code review: architecture, separation of concerns, redundancy

- **Date:** 2026-10-01
- **Asked by:** the owner. "a general code review with attention to architecture, separation of concerns, and redundancy or refactoring opportunities. It's been a while since we did a full review."
- **Scope:**
  - all of `src/` (13,069 lines, 34 modules), `scripts/` (1,621 lines) and `tests/` (5,761 lines)
  - the status of the [overall review](overall-review-2026-09-28.md) and [meta-audit](meta-audit-2026-09-28.md) of 2026-09-28
  - the code has grown from about 7,600 to 14,700 lines since then
- **Method:**
  - Five read-only reviews ran in parallel: extraction; store, CLI and outputs; evaluation tooling; measurement benches; cross-cutting (the import graph, scripts, tests, docs, and the earlier items).
  - The reviewers ran local checks only: AST import scans, the test suite with timings, and small offline reproductions against stub models.
  - **I verified the consequential findings myself:**
    - **by running them:** items 1, 2 and 10 in the table below
    - **by reading the code:** items 3, 5, 6a, 7, 8 and 9
  - Items marked "reviewer" rest on a reviewer's reproduction, which I didn't repeat.
- **Changed nothing; no model was called.**

## Summary

- **The foundations held.**
  - Requests are named by their content, so a refactor can't silently replay a stale answer.
  - `scripts/query_snapshot.py`, the golden judge prompts and the committed replays prove refactors byte-identical offline. That makes most of the changes below cost nothing to re-record.
  - Items 1–9 of the last review's priority fixes are fixed, with tests, as are most of the meta-audit's.
- **One new high-severity bug, mine.** Since the 2026-09-28 promotion of the champion to the defaults (`993635e`), the shipped defaults don't fit their own context budget.
  - `output_tokens` went to 4,000, but `context_tokens` stayed 8,192 and `image_tokens` 1,200.
  - That leaves 3,792 tokens for input, estimated generously as one per byte.
  - With plain defaults, 172 of 178 comparisons were refused before being sent (reviewer's reproduction).
  - Nothing caught it: every recording and test runs with the measured profile (262,144 / 300) or round 0's.
- **Five more correctness gaps, all cheap to fix:**
  - judges take query-shaping settings from the environment (verified: an exported `PDF_DIFF_TEMPERATURE` changes every judge query, so all verdicts would be paid for again)
  - situating isn't rebound when its budget settings change
  - store binding is judged against the current defaults
  - resumed runs leave stale task rows
  - rotation is still mishandled in two places outside `pages.py`
- **Architecture: one package holds three products, and several concepts have no single owner.**
  - The shipped CLI is about 5,650 lines, evaluation tooling about 3,050, and the measurement benches about 4,370.
  - The concepts without an owner: settings, the request's structure, the report document, fixtures, judgement files, unit scores, region names.
  - Each concept's knowledge sits in 3–7 hand-synchronised places, and some already disagree.
- **Large modules do many jobs:**
  - `controlled.py`: 5 concerns, 1,311 lines
  - `extract.py`: a 316-line closure
  - `rounds.py`: 8 jobs
  - `llm.Client`: 8 jobs
  - `cli.py`: hosts the pipeline
  - `run_round.main`: 368 lines, untested
  - Lazy imports hide 5 cycles.
- **Redundancy:**
  - an evaluator-client setup written 7 times
  - 9 HTML writers
  - 4 crop renderers
  - 3 coordinate-unaware drawing fetches
  - 5 number parsers and 3 text normalisers
  - copied script boilerplate
- **Docs describe the tool as of 2026-09-25.** "Store not yet implemented", "123 tests", `claims_per_request` 6, exit code 3 undocumented.

## Bugs and risks, to fix first

| # | Severity | What | Where | Checked | Fix | Cost |
|---|---|---|---|---|---|---|
| 1 | High | **Shipped defaults exceed their context budget.** 3,792 tokens left for input; comparisons and some tile tasks are refused | `models.py:331-336`, `llm.py:254-256`; from `993635e` | Me (arithmetic); reviewer (reproduction) | A coherent default profile; a test that plain `Settings()` through the stub pipeline gets no budget refusals; refresh `config.example.json` (still 1,400 output tokens) | Situating re-asked (cents) |
| 2 | High (money) | **Judges take query-shaping settings from the environment.** Only context, output and image tokens are pinned; temperature, seed, response format and max-token field come from `PDF_DIFF_*` | `Settings.from_env` at `run_round.py:179,288,341`, `spotcheck.py:93`, `cli.py:427,500`; `models.py:539` | Me (0.0 → 0.7) | One evaluator-client helper that reads only endpoint settings from the environment | None |
| 3 | Medium | **Situating isn't rebound when `image_tokens` or `safety_tokens` change**, though it sizes its prompt by them | `situate.py:366` vs `provenance.py:23` | Me (code) | Bind them; derive interpreters from one registry (architecture A1) | One rebind; answers replay |
| 4 | Medium | **Store binding is judged against the current defaults:** a lever whose default moves isn't noticed, and old evidence is served as current | `provenance.py:63-73` | Reviewer (simulation) | Bind every resolved shaping setting | One rebind; answers replay |
| 5 | High | **Resumed runs leave stale task rows:** refinement also runs after "not reached" (budget) and "not recorded", and a document's old rows are never cleared. Later runs then skip situating and report incomplete | `extract.py:1120,1193`; `store.py:343-350` | Me (code); reviewer (reproduction) | Refine only answered tasks; clear a document's rows that aren't in this run's task list | None |
| 6 | High | **Rotation is mishandled outside `pages.py`:**<br>(a) `section_text` clips in displayed coordinates. A whole-page section returned half its lines; this text feeds every situating section prompt<br>(b) figure detection pairs captions and clips drawings in unrotated coordinates, so rotated pages lose figure tasks | (a) `extract.py:880-891`; (b) `situate.py:114-124,167-185` | (a) me (code), reviewer (reproduction); (b) reviewer | Route both through `pages.py`; add a `pages.drawings()` for the four copied fetches; extend the upright-or-rotated test to figures and situating | Rotated pages' requests (cents) |
| 7 | Medium | **One unreadable or encrypted PDF aborts the whole run;** the error doesn't name the file | `extract.py:1206-1211`; `cli.py:51-53` | Me (code); reviewer (reproduction) | A failed coverage row naming the file, and continue | None |
| 8 | Low–medium | **Folder fixtures repack by row count:** an answer that replaced a recorded failure before a crash is never packed | `fixtures.py:271` | Me (code); reviewer (reproduction) | Pack to bytes; write only if they differ | None |
| 9 | Medium | **Cost caps apply per model or per call,** not per command:<br>- `review judge` and `queries check`: per model<br>- spot checks: per call, with no budget pause and no public-slice guard (their images are committed)<br>- `--max-cost 0` means "no cap" in two commands | `cli.py:424-441,499-516`; `spotcheck.py:92-107` | Me (code) | One budget carried across models; spot checks share `run_round`'s judging, pause and guard | None |
| 10 | Medium | **Controlled scorer slips, mine this week:**<br>- units ignored ("5,151 ft" for a flow in gpm is right)<br>- a condition counts as kept on any shared word ("maximum day" for "average day")<br>- "located in" is unscored (two relations claim it)<br>- fractional inches are "misread" | `controlled.py:1147-1212,1289-1292`; `relations.py:64,111`; `sheets.py:16` | Me (all four) | Typed values (kind, magnitude in a base unit via `compare.UNITS`, tolerance); distinctive condition words only; resolve the within/located-at tie by the object's kind; fractions | Offline re-score |
| 11 | Medium | **A unit's score is defined two ways:** `rounds.unit_scores` averages each judge's two orders; `insights` averages all verdicts flat (1.0 against 0.667 in one case). The post-mortem picks samples by one and shows the other | `rounds.py:862-877`; `insights.py:56,77`; `postmortem.py:105,142-156` | Reviewer | One `UnitVerdicts` object | `analysis.json` changes |
| 12 | Low | **A truncated answer is retried at full price**, and truncates again at temperature 0 | `llm.py:403-404,429` | Reviewer | A non-retried `Truncated` failure, still refined | None |
| 13 | Medium | **`reconcile` is quadratic and runs on every load:** 27 s for 4,000 claims | `readings.py:86-97`; `store.py:355` | Reviewer (timing) | Group clusters by stated value; cache words | None |
| 14 | Low | **The rounds report's by-kind chart collapses variants** into one unlabelled point | `rounds.py:1092-1110` | Reviewer | Name series by round, variant and stratum | None |
| 15 | Low | **Unit bands are cut by unrotated y on rotated sheets** (dc, calg, ken); v6's whole-page view mitigates | `rounds.py:117-126` | Reviewer | `pages.display_y` | Rebuilt batches only |

**Measurement validity.**
- **The relation vocabulary was grown from the recorded gemma-4 answers it now scores:**
  - "airflow destination" (8 claims)
  - "optical path sequence" (5)
  - "door identifier" (3)
  - "input beam path" (2)
- The plan records this, but gemma's relation recall is partly measured on wording fitted to gemma.
- **Fix:**
  - score a held-out model or seed before the vocabulary grows again
  - log unscored attribute phrases for each run
  - note each phrase's source

## Architecture

### A1. Concepts without a single owner

| Concept | Where it lives now | Proposed owner |
|---|---|---|
| **Settings and levers** | Five tables:<br>- `SETTING_CLASSES`<br>- `provenance.LEVERS` and the three role tuples<br>- `store.SETTING_REGIONS`<br>- `from_env`'s list fields<br>- `extract.LEVER_MARKS`<br><br>They already disagree (item 3), and only `SETTING_CLASSES` is tested | One registry in field metadata (class, roles, regions, marks, parsing); the tables derived from it; a test that every shaping setting is bound by a role. The meta-audit's item 6, still open |
| **The request's structure** | Prompts assembled inline (`extract.py:1054-1057`), then parsed back at markers by `llm.describe`, `review.py:184` and `rounds.py:613`. The recipe tuple is read by position in 6+ places. One marker already misses ("Drawing sheet. Detail B4") | An `ExtractQuery` whose `prompt()` reproduces today's bytes and whose `parts()` go into the query log; a `Recipe` NamedTuple. Meta-audit item 7 |
| **The report document** | Assembled in `cli.py:291-318`; `schema_version` hard-coded twice; read as dicts by `report.py`, `review.py` and two store SQL views by JSON path | A `Report` model owning the version; `evidence.json` derived from it; `Situation` and `CoverageRow` types |
| **Fixtures** | Five ways to open, three working-file conventions. Read-only queries open a writable fixture and can repack the committed zip. `.zip` given to `prune` crashes | `fixtures.open(path, mode)` for `.sqlite`, `.zip` or a folder, with `responders()` and `usage(role)` |
| **Replay policy** | Split between `llm.Client` (mutates `Fixture` counters, classifies outcomes, picks samples) and `Fixture`. Three caches in three key spaces; one, the byte cache, is used only by tests | A `Replayer` owning mode, sample, outcome and counters; `Client` is transport plus one cache |
| **Judgement files and rubrics** | `judge_pairs` reads and writes verdict files, while `judgements` only parses them. No record carries its rubric, so a mid-round rubric edit mixes rubrics undetected. Rubrics are chains of `str.replace` that fail silently. People's spot-check instructions are still v4's | `judgements` owns the files (header with reviewer, rubric and kind); one rating loop for the three model raters; a `Rubric` value from named clauses, pinned by the goldens |
| **A unit's score, lean and split** | Three definitions (item 11) | `UnitVerdicts` |
| **Region and family names, crop names** | Four region tables; `task.split(":")[0]` open-coded in 5 places; the crop stem written twice and globbed by `gc` | A `regions` module; `crop_name()` and `assets_dir()` |
| **Evaluator client** | Written 7 times (item 2, item 9) | One helper: endpoint settings from the environment, a shared budget, a Paused result |
| **Controlled-document kinds** | `getattr(project, "sheet")` and `getattr(project, "schematic")` attached after construction; a nine-way `if` over tuple-tagged blocks; three knob interpreters; the project registry in two places; "Hall C" hard-coded in the shared renderer | A family registry; block renderers registered by tag (HTML and drawing); knob → style dataclasses |

### A2. One package, three products

- **Sizes:**
  - product: about 5,650 lines (cli, extract, situate, compare, store, llm, models, scan, provenance, readings, pages, dispatch, progress, throttle, report, manifest, fixtures)
  - evaluation: about 3,050 (rounds, review, judgements, insights, postmortem, queries, taxonomy, ledger)
  - benches: about 4,370 (eyetest, pagetest, profiles, controlled, relations, schematics, sheets)
- **The product depends on evaluation code:**
  - `models.py` holds the round specs, verdict and panel types, and imports `rounds` (`models.py:525`). That single edge closes a 13-module cycle once lazy imports are counted.
  - `llm` holds `folder_client` and A/A sampling.
  - The store imports fixtures for recipe labels.
  - The CLI carries the `review`, `queries` and `fixtures` subcommands.
- **The installed package ships all of it,** and `postmortem` reads `docs/reviews/levers.md` through `parents[2]`, so it works only from a checkout.
- **Proposal:**
  - subpackages `eval/` and `bench/`
  - evaluation types out of `models.py`
  - a test that product modules never import them
  - one evaluation CLI
  - mostly moves, proven byte-identical by `query_snapshot` and the goldens

### A3. Orchestration in the CLI and in scripts

- **`cli.py` hosts the pipeline:** planning, binding, the extraction and situating loops, client construction, report assembly.
- **Scripts drive it as an API:**
  - they build argument lists for `cli.main`
  - they capture `--plan`'s printed JSON
  - tests patch `cli.Client` because a client can't be injected
- **`--plan` re-implements task enumeration** and has drifted: it groups text without the section split, so it undercounts.
- **`run_round.main` is a 368-line closure** holding round policy: chunked judging, retries, escalation, resampling, the privacy guard, and the early-stop rule outside `decide_scores`. No test reaches it.
- **Proposal:**
  - a `pipeline.py` (prepare, extract, situate, compare, plan; client injected)
  - one `page_tasks()` used by extraction and `--plan`
  - a tested `RoundRunner` in the library, with a typed `RoundState`
  - scripts reduced to argument parsing and exit codes
  - recording constants (`BASE_SETTINGS`, duplicated today) moved into the library

### A4. Large modules

| Module | Lines | Jobs | Proposed split |
|---|---|---|---|
| `controlled.py` | 1,311 | Fact model; 7 generators; HTML and Story rendering; charts; locating; scoring | A `controlled/` package: model and values, projects, render, charts, score, beside relations, schematics and sheets |
| `extract.py` | 1,297 | Prompt and scheduler; sections; layout and regions; quote matching; context; tables. `_pdf_job` is a 316-line closure whose `consume` takes 15 parameters, 13 of them re-listed by hand in a lambda | `sections`, `regions`, `quotes`, `context`, `tables`; a `Task` dataclass and a `PdfExtraction` class; a pure `table_rows()` |
| `rounds.py` | 1,131 | Units; batches; rubric prompts; judging; spot checks; statistics; decisions; history and report | `units`, `batches`, `rubrics`, `pairwise`, `spotcheck`, `stats` (with `review`'s α and Dawid–Skene), `decisions`, `history`; `rounds` kept as a re-exporting façade |
| `llm.Client` | about 280 | Request building and hashing; query log; replay policy; 2 caches; A/A sampling; HTTP and retries; throttling; budget and ledger. Also knows extraction prompts (`describe`) and recipe positions | A pure request builder; a transport; an answers interface (fixture, store) |
| `review.py` | 796 | Rendering; sampling; labels; prompts; statistics | `render` to `pages`, `reviewer_file` to `judgements`, statistics to `stats` |

### A5. Cycles hidden by lazy imports

- `models` → `rounds`: one edge, which closes a 13-module cycle
- extract ↔ situate
- compare ↔ provenance (provenance, a low-level module, lazily imports extract, situate, compare and llm)
- judgements ↔ rounds
- controlled ↔ schematics ↔ sheets (12 function-level imports; the scorer reaches into the sheet generator for a unit parser)

## Redundancy

| What | Copies | Where | Proposal |
|---|---|---|---|
| Evaluator-client setup (`Settings.from_env` + `folder_client` + ledger + progress + budget exit) | 7 | `cli.py:427,500`; `run_round.py:179,288,341`; `spotcheck.py:93`; `eye_test.py:50`; `page_test.py:57` | One helper (fixes items 2 and 9) |
| HTML pages with their own palette and escaping | 9 | report, insights, eyetest, pagetest, rounds, postmortem, queries, review; `__DATA__` injection twice | `html_page()`, `esc`, `embed_json()`; the product report gains dark mode |
| Crop rendering | 4 | `extract.render`, situate's nested `render`, `review.render`, `pagetest.picture` | One renderer, only with byte-identical parameters (image bytes are hashed) |
| Drawing fetch with the `get_cdrawings` fallback | 4 | `extract.py:309,368,712`; `situate.py:103` | `pages.drawings()`, coordinate-aware (item 6b) |
| Page scans per page | 5× drawings, 4× `get_text("dict")`, 3× image info | `visual_regions`, `bands`, `_empty`, `page_figures`, `page_signals`, `sheet_details` | A cached `PageScan` in `pages.py` |
| Number parsing; text normalising | 5; 3 | `parse_number`, `printed_value`, `sheets.inches`, `eyetest._number`, the RANGE regexes; `eyetest.norm`, `relations.norm`, `controlled.tokens` (also `extract.FOLD`, `readings.QUOTES`) | One `values` module (pairs with item 10) |
| Coverage rows by hand | 6 | `extract.py:1008,1046,1145,1234,1289`; `cli.py:553` | A `CoverageRow` type |
| Reading a task's request input | 3 ways | `rounds.add_context`, `postmortem._unit_queries`, `review.Requests` | From the query log's parts (A1, the request's structure) |
| Model-rater loop | 3 | `rounds.judge_pairs`, `review.judge`, `queries.check` | One rating loop (A1, judgement files) |
| `build_batch` and `add_context` | Collect and split run twice; the unit id, PDF load and band rectangle written twice | `rounds.py:233-262,601-640` | A `UnitKey`; `build_batch(whole=True)` |
| Eye- and page-test plumbing | Shared code lives in `eyetest`; the two scripts' run and replay loops are copies; "not recorded" detected by message prefix | `pagetest.py:28,538`; `eye_test.py`/`page_test.py` | A `bench` module and a scripts helper |
| Reading thresholds and plan names | 2 thresholds; `CAP` twice; plan name format in 4 places | `pagetest.acuity`, `profiles` | `acuity` uses `Profile`; one `plan_name()` |
| Drawing primitives | `_border` twice; text helpers rebuilt in 3 drawers; "first free spot" twice | eyetest, controlled, schematics, sheets | A small `drawing` module for new code; migrate old drawers at the next re-record |
| Prose generators in `controlled.py` | `add = lambda` 5 times; months, season and totals twice; Option names 3 times (drifted) | `controlled.py:121-619` | A fact-sheet builder; templates naming facts by id (milestone 4's revisions need it) |
| Script boilerplate | `sys.path.insert` in 9 scripts; the dead-URL literal in 9 places; `LEDGER` in 6; `BASE_SETTINGS` twice | `scripts/` | The library's recording module |
| Test helpers | 7 HTTP stub servers, about 28 fake clients, about 10 PDF builders; "SOURCE DATA" parsed in 9 test files; `stubs.py` is 23 lines | `tests/` | `stubs.model_server`, `FakeClient`, `pdf()` |

## Dead and parked code

- **Parked or rejected levers** still branch through every extraction request (about 190 lines):
  - `sheet_details`, `references`, `glossary`, `tile_locator`, `real_table`
  - `levers.md` lists them as "Not accepted" or "Parked"
- **Unused code:**
  - `SectionIndex.boundaries`, `situate.native_rect` (an alias), `review.image_data`
  - `fixtures.NotRecorded`, which shadows `llm.NotRecorded`
  - `judgements.QUESTIONS`/`KINDS`
  - `schematics.build`'s `intro` parameter
  - `eyetest._axes`'s `card` and `rng`
  - the byte cache in `llm` (used only by tests)
- **Test-only code:**
  - `taxonomy.suggested_verdict`: the page uses a JavaScript twin, so the test checks a copy
  - `rounds.claim_shares`, `QuoteCheck`
- **Never enabled:** the early-stop path (no round sets it)
- **Old-format fallbacks:**
  - `rounds._reader`, the legacy sources shape
  - two claim-identity fallbacks that differ (`rounds._ident` and `insights._claim_key`)
- **Unscored:** `Fact.basis` is in every controlled key but never scored, and its default "proposed" isn't in the claims' vocabulary.
- **Not checked:** `--only decide` is accepted by `run_round` but no step checks it.

## Tests and docs

- **No always-running test pins situating or comparison requests.**
  - Judge prompts are golden; extraction is pinned only by the controlled replay (with `--no-situate`).
  - The slice replay and `query_snapshot` need git-ignored files and skip on a fresh clone.
  - **Proposal:** golden request hashes for all three roles on a synthetic document, under the defaults and under round 0.
- **CLI-driven tests read `PDF_DIFF_*` from the environment.** A shell where `.env` was sourced, as the scripts' docstrings instruct, changes test settings. Clear the environment for all tests.
- **Two test files define classes after `unittest.main()`:** `test_controlled.py` (Replay, Corpus) and `test_fixtures.py`. They run under discovery, but not when run directly.
- **The controlled corpus test checks only documents that exist,** and not their keys.
- **Three tests take 62% of the suite's time:** `test_replay_slices` 97 s, `test_settings` 62 s, `test_fixtures` 51 s, out of 337 s. A `SLOW` switch would help.
- **Docs drift:**
  - README and `how-it-works.md` call sources, archives and the store "planned".
  - `limitations.md` says no real model was used; `VALIDATION.md` says 123 tests (now 296).
  - `configuration.md`:
    - gives `claims_per_request` as 6
    - misses 26 of 56 settings, including every query lever
    - misses exit code 3 and the fixture, ledger and cost flags
  - The code map in `how-it-works.md` lists 14 of 34 modules.
  - **Proposal:** a settings table generated from the registry (A1), and a test that every field is documented.
- **Repository size:**
  - `.git` is 93 MB in loose objects, and has never been packed.
  - `replay-slices.zip` has 10 versions in history; `ledger.jsonl` is 7.7 MB and re-read on every spend check.
  - 864 round page images are committed.

## The 2026-09-28 reviews: status

| Item | Status |
|---|---|
| Overall review 1–9 (rotation in extraction, early stopping, ledger per attempt, `IncompleteRead`, JSON repair, `reconcile`, judging details, transient failures, lever regions) | **Fixed, with tests.** Rotation still has the leftovers in item 6 |
| 10. Rounds commit document content | **Partly:** non-public slices are refused, but images and page text are still committed |
| 11. Defaults never measured | **Partly, and it caused item 1:** levers, 20 claims and 4,000 output tokens were promoted; context and image tokens weren't |
| Meta-audit: replay drift check, batch checks, pure decisions with null simulation, typed round spec, claim identity, judgement records, goldens | **Done.** `run_round` turns the typed spec back into a dict with 22 restated defaults |
| Meta-audit: lever registry | **Open** (A1) |
| Meta-audit: `ExtractQuery` and the recipe; Rubric object; inclusion probabilities | **Partly** |
| Small items: v6 instructions on the spot-check page; tables numbered after filtering; counting missing verdicts, not attempts | **Open** |

## Strengths worth keeping

- **Content-addressed requests, with byte-identity checks:**
  - `query_hash`
  - recipes as labels only
  - `query_snapshot`
  - golden prompts
  - committed replays

  Together they make most refactors here free and provable.
- **Determinism:** generated documents, packed fixtures and reports reproduce byte for byte, and the 54 controlled documents and keys regenerate identically.
- **A simple, correct threading model.** Workers only send; state stays on the main thread. Identical in-flight queries are merged, and exit codes are consistent (3 means paused for budget, resumable).
- **Store integrity:**
  - per-task transactions
  - a writer lock and WAL
  - binding with a dry run, a targeted reset, and both roles checked before either is cleared
- **Rigorous decisions:** pure rules simulated under the null, criteria locked before judging, and a round spec that rejects typos.
- **Self-checking generators:**
  - eye cards and page sheets check their own text layers
  - `locate` refuses an unplaced fact
  - layout repeats until no table or figure is split
  - a test keeps every schematic line clear of every box
- **Small, focused core modules:** pages 66 lines, dispatch 95, provenance 90, throttle 120, readings 110.

## Proposed order

The order is mine to set. The design questions below are the owner's.

| Phase | What | Cost |
|---|---|---|
| **0. Guards first** | Golden requests for situating and comparison; a default-profile test (item 1); a settings-registry consistency test; the controlled corpus test checking ids and keys; tests with a cleared environment; main guards moved | None |
| **1. Fixes** | Items 1–13 above; the controlled scorer's re-score | Cents (rotated pages' and situating requests); offline re-scores |
| **2. Single owners** | The settings registry; the evaluator-client helper; `fixtures.open` and a `Replayer`; `Recipe` and `ExtractQuery`; `UnitVerdicts`; judgement files and `Rubric`; the `Report` type; a read-only `Store.open`; HTML helpers; a `values` module | None. `query_snapshot` and the goldens prove requests unchanged |
| **3. Splits** | The `controlled/` package (before milestone 4, which adds revision pairs to it); `rounds`, `extract` and `llm.Client` split; `pipeline.py` out of the CLI; a tested `RoundRunner` | None (moves) |
| **4. Packaging and hygiene** | `eval/` and `bench/` subpackages with an import test; the docs pass; `git gc`, ledger rotation | None |

**For the owner to decide:**
- **The package split** (A2): subpackages within one distribution, or the evaluation and bench tooling outside the shipped package.
- **Parked levers:** delete them, or move them to an experimental module.
- **The default profile** (item 1): the measured gemma-4 profile (context 262,144, images 300) as the shipped default, or a smaller, model-neutral profile that fits.
- **Committed round images and fixtures:** keep committing, re-render images from the public slices, or use Git LFS.
