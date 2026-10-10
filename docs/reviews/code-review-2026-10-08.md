# Code review: architecture, separation of concerns, simplification, complexity

- **Date:** 2026-10-08
- **Asked by:** the owner. "I think it's time for a big code review. This review should focus on architecture, separation of concerns, refactoring and simplification opportunities, code quality and discovery of messy or complex code. Download some python tools to make measurements, e.g. complexity metrics, where appropriate. Of course, any bugs or performance concerns, etc. discovered should also be opportunistically captured in the review findings."
- **Scope:**
  - the product: `src/semantic_pdf_diff` (12,450 lines in 42 modules, the vendored metafile renderer left out)
  - the lab: `lab/src` (10,677 lines)
  - `scripts/` (2,326 lines) and `tests/` (9,834 lines)
  - the status of the [2026-10-01 review](code-review-2026-10-01.md)'s items
- **Method:**
  - **Measurements** with tools installed in a scratch folder, not the project's environment (a library choice, Claude's; none becomes a dependency):

    | Tool | What it measured |
    |---|---|
    | radon | cyclomatic complexity, maintainability |
    | lizard | function length, parameter counts |
    | vulture | possibly dead code |
    | ruff | lint: late-binding closures, blind excepts, unused code and more |
    | pylint | duplicated code |
    | an AST scan of our own | the import graph, lazy imports, cycles |
    | cProfile | a no-model replay of the drawing-sheet slice |

  - **Five read-only reviews in parallel:** the PDF extraction core (A); tables and the other formats' readers (B); the platform: settings, levers, the model client, fixtures, store, pipeline, CLI (C); comparison and reports (D); the lab, scripts and tests (E). Their reproductions ran offline against stub clients.
  - **Checked by me:**
    - **by running them:** A1, B1, D1, and the commit costs (C2)
    - **by reading the code:** C1, C10
  - Other findings rest on the reviewer's reproduction or reading, marked as such.
- **Changed nothing; no model was called.** Fixes followed (see *Fixes so far*, at the end).

## Summary

- **The foundations held again.**
  - Content-addressed queries, the golden requests and the committed replays still make refactors provable offline.
  - Items 1–9 and 12 of the last review are fixed. Its architecture items are mostly fixed: settings declared once, the replay policy split out, the report document owned, HTML writers on one page builder.
  - The product imports nothing from the lab.
- **Three high-severity bugs, all found by the reviews and all cheap to fix:**
  - **B1. A late table answer in a workbook or deck reads the next sheet's rows.** The same late-binding bug I fixed in the PDF path two days ago, left in the text formats' path (`textdocs.py:389`, `page` unbound). Rows are filed under the wrong sheet and their task tags collide, so the store keeps one table's claims in place of three. Reproduced: 60 rows of one sheet filed under the next.
  - **A1. Word pictures that share a line share a task tag** (two pictures in one paragraph; every picture in one table row). The store deletes the first picture's claims when the second's are recorded. Reproduced.
  - **D1. A limit's direction is dropped when values are aligned:** "≤ 5 NTU" and "≥ 5 NTU" (also "<"/">", "±0.5"/"0.5", "$5"/"5") get one value key, so a revision flipping a requirement is settled "equivalent" without a model. Reproduced.
- **Performance: about 40% of a no-model replay is avoidable, with requests byte-identical.**
  - commits waiting on the disk: 9.5 s of 57 s (C2)
  - pages' text, drawings and display lists rebuilt by every consumer: about 15 s (A5–A8)
  - The lab's controlled scorer takes about 19 minutes under the profiler, from facts' vocabularies rebuilt per claim (E1).
- **Architecture: the layering is inverted at the bottom, and three big orchestrators carry too much.**
  - **A 21-module import cycle** exists only through 31 imports placed inside functions. Its root: the schema module (`models`) imports the levers at load, and the levers reach into seven implementation modules (C4).
  - **`extract._pdf_job`** (218 lines, complexity 61, five nested closures bound by default arguments), **`pipeline.run`** (complexity 49) and **`compare.compare`** (complexity 57, five jobs).
  - **The ask, check, ask again and review state machine is written twice** (`tablerules.read`, `tablestructure.read`) and has already drifted (B: A1).
  - **"Grid" has no single owner;** rows read by themselves come from the raw rows, not the grid the rules saw (B2).
- **Complexity is concentrated.** 84% of 1,468 functions have complexity 10 or less. 49 have more than 30: 23 in the product, 21 in the lab, 5 in scripts.
- **Dead code is modest** (about 30 product names). Textual duplication is low (two 6-line copies); the redundancy is semantic: normalisers, number parsers, letter helpers, box unions, test stubs.

## Measurements

| Measure | Product | Lab | Scripts | Notes |
|---|---|---|---|---|
| Lines | 12,450 | 10,677 | 2,326 | tests 9,834 |
| Functions measured (radon) | 848 | 536 | 84 | 1,468 in all; 84% at complexity 10 or less |
| Mean cyclomatic complexity | 6.0 | | | grade B |
| Functions over 30 / over 40 | 23 / 15 | 21 / 15 | 5 / 2 | |
| Lint findings (ruff, bug-prone rules) | 244 | | | 448 in all; 71 late-binding closures, of which 1 a real bug (B1) |
| Possibly dead names (vulture ≥ 60%) | 35 | | | many are pydantic fields or library attributes |
| Duplicated blocks of 6+ lines (pylint) | 1 | 1 | 0 | `_joined` in tables and tablestructure |
| Import cycles | 1 of 21 modules | 2 (5 and 8 modules) | | only through function-level imports |

**The product's most complex functions** (cyclomatic complexity, lines):

| Function | CC | Lines |
|---|---|---|
| `extract._pdf_job` | 61 | 218 |
| `segmentation.sheet_details` (parked lever) | 60 | 61 |
| `compare.compare` | 57 | 128 |
| `textdocs.text_job` | 55 | 104 |
| `align.align`, `align._within` | 55, 55 | 58, 72 |
| `tablestructure.apply` | 53 | 124 |
| `llm.Transport.send` | 50 | 92 |
| `pipeline.run` | 49 | 78 |
| `report.write_report` | 47 | 110 |
| `xlsxdocs.regions` | 45 | 56 |
| `tablestructure.signals` | 43 | 37 |
| `tablerules.summarise`, `analyse` | 41, 40 | 67, 35 |

**The replay profile** (the drawings slice, 10 documents, every answer replayed, 57 s):

| Where | Seconds | Avoidable |
|---|---|---|
| SQLite commits (3,314, each waiting on the disk) | 9.5 | nearly all (C2) |
| Crops rendered (342), PNG encoding | 11.4 | the page interpretation, 4 s (A7); encoding no (image bytes are in queries) |
| Table detection (`find_tables`, 8 drawing sheets) | 11.0 | no, unless skipped on drawing sheets (A20) |
| Text pages built (863 times) | 8.7 | about 3 s (A6) |
| Coordinate mapping (`pages.shown`, 135,000 calls) | 8.2 | about 5 s (A5) |
| Figure detection repeated per consumer | about 3 | most (A8) |
| Request bodies built for replayed answers | 1.2 | all (C19) |

## Bugs and risks, to fix first

| # | Severity | What | Where | Checked | Fix | Cost |
|---|---|---|---|---|---|---|
| B1 | High | **A late table answer in a workbook, CSV, deck or Word file reads its rows under the page the loop has reached:** `by_itself` binds the table but not `page`. Rows go to the wrong sheet or slide and section, tags collide (`table:p3:0:0` from three tables), and the store keeps one table's claims for each tag. Happens on normal runs with concurrency, whenever answers aren't served at once | `textdocs.py:389-397` | Me (the reviewer's reproduction: 60 rows of one sheet filed under the next) | Bind `page`; port the PDF path's late-answer test to sheets and slides | S |
| A1 | High | **Word pictures sharing a line share a task tag:** two pictures in a paragraph, every picture in a table row. The second's crop overwrites the first's, the store deletes the first's claims, the label check reads the wrong words | `pictures.py:74,91,96`; lines from `docxdocs.py:591,640` | Me (reproduced) | An ordinal in the tag after the first picture of a line (`pic2`, `pic2.1`), so existing tags are kept; a test | S |
| D1 | High | **Alignment drops a value's comparator, tolerance and currency:** "≤ 5" and "≥ 5" settle as equivalent without a model | `align.py:99,109-120` | Me (reproduced) | Keep the normalised prefix in the value key; tests | S |
| B2 | Medium–High | **Rows read by themselves come from the raw rows, not the grid the rules saw:** a PDF row's wrapped continuation line (joined in the grid) is never read on the fallback paths (a "rows" answer, misfits, failures, an image mismatch); a row holding only its first cell becomes a section row with no key and is never read ("Note: P-2 ... rated 95 L/s") | `tables.py:57-76`; `tablerules.py:140-158,844-847,953-954`; `extract.py:497-510` | Reviewer (reproduced) | The grid as the one source of rows; a section row holding a digit read as a row | M |
| D2 | Medium | **Revisions with unchanged files are aligned in two passes,** so an unpaired later claim is called "possibly added or removed" instead of "not compared", and groupings contradict each other; two alignment summaries | `compare.py:294-308` | Reviewer (reproduced) | One alignment over (left + shared, right + shared) | M |
| C1 | Medium | **One broken symlink or unreadable file in a source folder aborts the whole scan** (and a file moved since the scan aborts a `manual` rescan run) | `scan.py:98,108`; `extract.py:200` | Me (read); reviewer (reproduced) | Catch `OSError` per file and record an issue; a failed `open` row when loading fails | S |
| A2 | Medium | **PDF table part tags can collide:** a structure answer's "new table" names its inner part 1 as `0.1`, the tag `pdf_parts`' part 1 already has | `extract.py:495,531` | Reviewer (read) | Another separator for inner parts | S |
| B3 | Medium | **A second "split column" rule acts on the wrong column** (the column map isn't shifted after a split); overlapping joins join one column too many | `tablestructure.py:316-374` | Reviewer (reproduced) | Shift the map; `apply` in three phases sharing one column map | S |
| B4 | Medium | **A plain-text paragraph starting "A " or "I " becomes a heading** | `textdocs.py:28,166-171` | Reviewer (reproduced) | A letter heading needs "A." or "Appendix A" | S |
| B5 | Medium | **A label and value block on a sheet becomes a table headed by its first pair,** so that pair's value is never read | `xlsxdocs.py:176-186`; `docxdocs.py:381-400` | Reviewer (reproduced) | Two columns of label and value read as pairs | S–M |
| A3 | Medium | **Table rows are split by column after "not reached"** (a call limit, an answer not recorded), tripling the unreached rows; text and pictures already skip it | `tasks.py:248` | Reviewer (reproduced) | Split only after "partial" or "failed" | S |
| A4 | Medium | **The blanket `except` around table detection also catches our own heuristics' bugs,** dropping the page's earlier tables and calling it a detection failure | `extract.py:422-442` | Reviewer (read) | Narrow it to PyMuPDF's calls | S |
| C10 | Medium (money) | **A schema-invalid answer is retried, and billed, every time:** pydantic's error is a `ValueError`, caught with the transport's errors. All 5 invalid recordings in the slices' fixture failed 3 times | `llm.py:368,386` | Me (read); reviewer (fixture) | An `Invalid` failure, not retried | S |
| E2 | Medium (money) | **The eye and page tests cap cost per model, not per command:** two models with `--max-cost 0.5` can spend $1 | `scripts/eye_test.py:46-53`, `scripts/page_test.py:55-60` | Reviewer (read) | One `llm.Budget` per command | S |
| E3 | Medium | **Claims from images (and, in review batches, every format but PDF) are left out of lab scoring:** `rounds.collect` filters by extension | `eval/rounds/units.py:62-63`; `eval/review.py:95,103` | Reviewer (read) | A store reader without an extension filter, used by the bench and rounds | S–M |
| C8 | Low–Medium | **`show` and `report` take the writer's lock,** so a store can't be inspected during a run | `cli.py:360` | Reviewer (reproduced) | The lock-free read-only `Store.open` | S |
| C9 | Low–Medium | **Judges validate the whole environment,** so a small-context profile's `PDF_DIFF_CONTEXT_TOKENS` makes every judge fail | `llm.py:208` | Reviewer (reproduced) | Read only endpoint settings from the environment | S |
| D9 | Low–Medium | **`reconcile` folds a unit's case** ("5 MW" and "5 mW" become one claim, against decision 0005) and strips every comma ("12,50" merges with "1,250") | `readings.py:33-34` | Reviewer (reproduced) | Fold the value only; strip thousands separators only | S |
| B6, B7 | Low–Medium | **The table queries' progress never completes** (each submit adds, each record finishes once); **the structure query records one tag twice** | `tablerules.py:833,842,907`; `tablestructure.py:474,481,508,554` | Reviewer (reproduced) | Fixed once in the shared state machine | S |
| C12 | Low | **An answer without `complete` is rejected whole,** then retried | `models.py:69` | Reviewer (reproduced) | Missing is `False`, with an issue | S |
| A14 | Low | **Followers of a repeated row copy only the first answer's first turn,** not its continuations | `tasks.py:158-168` | Reviewer (read) | Release followers after the last continuation | S |
| B8, B9 | Low | **A sheet comment outside every region is dropped silently; a defined table with no header row gets one** | `xlsxdocs.py:301-304,139` | Reviewer (reproduced, read) | Emit leftover comments; respect 0 header rows | S |
| B10 | Low | **The structure prompt's "and/or" reads as an intersection; the code takes a union.** "No rows" on the second answer keeps `table`; column letters break past 52 columns | `tablestructure.py:122-123,150,260-271,516` | Reviewer (read) | Say union in the prompt; the shared letter helper | S |
| C23, C24 | Low | **`PDF_DIFF_TABLE_RULES=none` can't be set from the environment; a "free" rebind deletes every saved comparison silently** | `models.py:473-474`; `store.py:231,275` | Reviewer (reproduced, read) | Map "none" to None; keep or warn | S |
| D11, E19 | Low | **Lengths key inconsistently** (`33.5"` against `33.5 in`: missed settlements, extra judge calls); **"½" isn't parsed** | `align.py:109-120`; `values.py:78` | Reviewer (reproduced) | `values.inches` for every length; fold vulgar fractions | S |
| A15 | Low | `image_pdf`'s blind except turns our own errors into "unreadable"; `page_of` leaves its documents open | `extract.py:293`; `pictures.py:32-39` | Reviewer (read) | Catch PyMuPDF's errors only; `with` | S |

**Late-binding closures (ruff B023), 71 sites:** one real bug (B1). The others are called within their own loop iteration, or bind what they use as default arguments; the reviewers read each one.

## Performance

| # | What | Where | Saving | Checked | Fix |
|---|---|---|---|---|---|
| C2 | **Every write commits and waits on the disk:** the store's journal is WAL with `synchronous` at FULL, 2.9 ms a commit; the fixture's journal is the default (8.4 ms). 3,314 commits in the replay, most of them diagnostics (`note_query` 1,435, recipes 1,435) | `store.py:175-178,483-490`; `fixtures.py:80,155-161` | about 9 s of 57 s; `test_replay_slices` 77 s to 60 s | Me (timed: FULL 2.9 ms, NORMAL 0.07 ms per commit) | Buffer the diagnostic writes into the next task's transaction; `synchronous=NORMAL` (a power cut, not a crash, can lose the last transactions); open a zipped fixture's copy read-only (C3) |
| A5 | `pages.shown` builds the page's rotation matrix on every call: 135,000 calls | `pages.py:11`; callers `situate.py:177`, `segmentation.py` | about 5 s | Reviewer (timed: 1.43 s to 0.46 s on one sheet) | The matrix once per page |
| A6 | Each crop builds two text pages | `extract.py:323,326` | about 3 s | Reviewer (timed, output identical) | One text page per task |
| A7 | Each crop re-interprets the whole page | `extract.py:102-105`, `situate.py:461`, `context.py:121` | about 4 s | Reviewer (timed, pixels identical) | A display list per page |
| A8 | The same page facts are rebuilt by every consumer: figures 2–3 times, drawings 4–6 times a page | `context.py:57,93`; `situate.py:159-177`; `segmentation.py:42,136,140,177` | about 3 s | Reviewer (profile callers) | The last review's `PageScan`: one cached scan per page, owned by `Context` |
| P1 | A workbook is loaded twice (values and formulas) to find uncalculated formulas | `xlsxdocs.py:317-318` | half the read time (5.5 of 10.8 s on 30,000 rows) | Reviewer (profiled) | One load; formulas found in the sheet XML |
| D3, D4 | Alignment is quadratic where names share a word ("Room N") and inside a large item | `align.py:184-199,270-303` | 2,000 items 23 s; one 2,000-claim item 4 s | Reviewer (timed) | Features per claim computed once; prune name-only candidates by an upper bound |
| D5, C11 | `reconcile` is still quadratic within one stated value | `readings.py:82-97` | 4,000 claims of one value 33 s | Reviewer (timed) | Bucket by page too; drop the repeated `_stated` |
| E1 | The controlled scorer rebuilds facts' vocabularies and rarity per claim, and scores each run again per reader | `bench/controlled/score.py:21-63,93-169,219`; `scripts/controlled.py:211-216` | about 19 minutes (under the profiler) to a few; 5.8 s to 2.2 s on a sample | Reviewer (profiled, results identical) | A `Scorer(key)` precomputed once; claims classified once, split by reader |
| E9 | The suite takes about 9 minutes, run one module at a time on 8 cores; four modules take 61% | `tests/` | to about 1.5 minutes in parallel | Reviewer (timed per module) | A parallel runner; one class-level recording in `test_fixtures`; `@slow` on two more |
| A20 | Table detection costs 1.4 s a page on drawing sheets | `extract.py:427` | 11 s on the slice | Reviewer (profile) | **For the owner:** a lever skipping table detection on pages recognised as drawing sheets (it changes what's read) |

## Architecture

1. **The bottom layer imports the top (C4).** `models` (claims, locators, settings) imports `levers` at load. The levers lazily import align, compare, pages, quotes, segmentation, situate and tables; 17 modules import `models` for claim types alone. That one edge holds the 21-module cycle together.
   - **Proposed:** `schema.py` (claims, locators, answers) and `settings.py` (Settings, its classes, environment loading); `llm` imports `Settings` for type hints only; lever notes move to their one user. The reviewer's simulation: the cycle falls from 21 modules to groups of 10, 4 and 2, and with the moves below to none outside extraction. Pure moves: requests byte-identical.
2. **`extract.py` holds five jobs (A12):** the job scheduler and reader registry, `image_pdf`, the extraction prompt, `Visuals`, and the PDF job; it re-exports 23 names for callers.
   - **Proposed:** the prompt to `tasks.py`; the scheduler and readers to `jobs.py`; `Visuals` to `visuals.py`; callers import from owners; `situate` imports sections from `sections` (breaking extract ↔ situate).
3. **`_pdf_job` (218 lines) binds callbacks by default arguments (A9).** Any new loop name a callback uses silently captures the last iteration: B1 is that bug in the text formats' path.
   - **Proposed:** a `PdfTable` object per detected table holding its page, index, boxes, crop and derivation, with `image()`, `read_parts()` and `read_row()`; table continuation as a pure, tested `continues()`; the page loop split into text, detection, tables, signals and vision.
4. **Task parameters travel as long argument lists (A10):** `TaskCore.consume` takes 17, re-listed by hand twice (each copy dropping a different subset); `table_task` 10. **Proposed:** a frozen `Task` dataclass, continuations as `replace(task, ...)` (the last review's proposal, still open).
5. **The ask, check, ask again and review machine is written twice (B: A1; A11):** `tablerules.read` and `tablestructure.read` are near-copies that have drifted (B6, B7, the review override, derivation steps, "no rows" handling); the submit protocol (progress, the pending count, the key tuple) is copied four times. **Proposed:** an `asking.py` exchange configured by hooks (check, revise, same, review prompt, use, fallback), testable without a fake core; one `TaskCore.ask(role, name, prompt, schema, images, finish)`.
6. **"Grid" has no single owner (B: A2):** `tablerules` owns `Grid`, `grid`, `from_cells`, `letter`, `number`; Word's private cell helpers are imported by the deck and workbook readers; `pptxdocs.Package` is used by the workbook reader; a table block carries two representations joined by keys (the root of B2). **Proposed:** `tablegrid.py` (the grid, its constructors, cells, header labels, letters, cell values) and `office.py` (package, namespaces, charts and pictures).
7. **`textdocs.py` does three jobs (B: A3):** the plain-text and Markdown parser; the text document model every format shares; and the job runner for every non-PDF format (complexity 55, if-chains over formats). **Proposed:** `textmodel.py` and `textjob.py` with a registry by extension (reader, locator, derivation, picture kind). The office readers share one writer (B: A4).
8. **`situate.py` mixes figure detection (used by extraction) and the model's situating (A13).** **Proposed:** detection to `figures.py`.
9. **`Store` holds binding policy (C5):** about 150 lines (`free`, `describe`, `affected_regions`, the mismatch text, `bind`), plus post-processing (`reconcile` on load), rescans and re-exported region names. **Proposed:** `binding.py` over the store's primitives.
10. **`pipeline.run` does six jobs (C6),** and its client can't be injected (three test files patch it); **`--plan` re-implements task enumeration and has drifted (C7)**: no section split, no formats but PDF, no table queries. **Proposed:** `run(..., client=None)` with its parts extracted; one task enumeration shared by extraction and the plan.
11. **`compare.py` holds retrieval, file differences, comparison and the explain stage (D6);** `compare()` does five jobs; alignment's state travels as loose locals (`_groups` takes 13 parameters) (D7); **`write_report` changes the report document** after it's been saved (D8). **Proposed:** `retrieval.py`, `explain.py`; a pure, testable veto; an `Alignment` object; the report's content settled before it's saved, the writer a pure renderer.
12. **The model client still holds** the query log, the store cache, replay glue and nine forwarding properties; the recipe tuple is read by position in six places with two parsers (C14); evaluation helpers live in product modules (C15). **Proposed:** a `Recipe` named tuple (recipes aren't hashed: no re-recording); evaluators to the lab.
13. **The lab:** scripts hold lab logic and copy each other (E4: the format list in five places, base settings three times, the ledger six); the lab reads product schemas with raw SQL in five places (E5); the rating loop over models is written about eight times (E7); two lab import cycles (E8). **Proposed:** a lab `bench/recording.py` and a `FORMATS` table, scripts reduced to argument parsing; `Fixture.responders()` and `usage()`; one evaluator context manager; a `controlled/model.py`.

## Simplification and duplication

- **Normalisers and number parsers (D10, S1):** word sets in five places (`align.words`, `readings._words`, `compare.words`, `situate.terms`, `pictures.words`), number scanners in five (`tablerules.number`, `align.NUMERIC`, `numeric_check`, `compare.NUMBERS`, `tablestructure._number`) beside `values.parse_number`. One cached tokenizer and one number scanner in `values.py`, leaving the folds that shape requests where they are.
- **Small copies:** `_joined`, `_filled` and `_plain` (tables, tablestructure, tablerules); box unions four times; to-string validators six times (one `Text` type); column-letter helpers three times; crop renderers three times (A16, kept byte-identical); the dispatch back-pressure loop three times (D15); two settings loaders and two error handlers (C16); four identical locator `bbox` properties and two identical `drop_unknown` validators (C18).
- **Long functions to split:** `tablestructure.apply` (three phases; the source of B3), `xlsxdocs.regions`, `tablerules.summarise` (one function per template), `llm.Transport.send` (post, account, classify; 35 tests guard it), `report.write_report` (a view table by format), the lab's `score_comparison` (complexity 101) and `eyetest.score` (71).
- **Fine as they are** (the reviewers' judgement): `docxdocs._math` (a flat dispatch), `chartxml.read`, `tablerules.opinion`, `relations.triples` (dense but commented), the parked `sheet_details`.

## Dead code

- **Product:**
  - unused: `situate.citing`; the shadowed `stems` import of `terms`; `pptxdocs.re`; `tablerules.json`; `Numbering.FORMATS`; `pptxdocs.RELS`; `provenance.LEVERS` and `TRIAGE_SETTINGS`; `compare`'s re-exports of `FOLDED` and `UNITS`; `models.DIFFERENCE_KINDS`, a fourth copy of the difference kinds
  - test-only: `extract_pdf`, `provenance.EXTRACTION_SETTINGS` and `COMPARISON_SETTINGS`, `Platform.digest`
  - broken: `dispatch._same` reads `client._sample`, which no longer exists, so merged in-flight queries always use sample 0
  - unreachable: `align.SAME["no"]`, `compare.py:369`, the non-declared branch in `Composable.explain`, PyMuPDF fallbacks for versions we no longer support (4 places)
  - unused parameters: about a dozen, among them `problems(tags)`, `Marks.styles(bbox)` and `_groups(ambiguous)`
- **Lab and scripts:** `scripts/alignment_sketch.py` (194 lines, superseded by the align lever, by its own docstring "throwaway"); `judgements.QuoteCheck`, `rounds.claim_shares`, `taxonomy.suggested_verdict` (a Python twin of a page's script); private names re-exported by the lab's façades.
- **Not dead** (vulture's false positives): pydantic fields and validators, entry-point commands, attributes set for libraries, `eyetest.perfect` (a documented test helper), the parked levers (kept by the owner's decision of 2026-10-02).

## Tests

- **Gaps for risky code:** each bug above lacks the test that would have caught it, and:
  - late answers in workbooks and decks (B1)
  - table continuation over pages: no test anywhere (A19)
  - the failure paths of both table queries (not reached, failed, review errors)
  - revisions with unchanged files (D2)
  - alignment at scale (reconcile has a timing test; alignment none)
  - the comparison's veto rules, reachable only through `compare()`
  - scans with unreadable entries (C1); `show` during a run (C8)
  - a guard on commits per replay, so C2 doesn't return
- **Speed (E9):** about 9 minutes serial. `test_controlled` 91 s, `test_fixtures` 85 s (ten tests each recording and replaying through an HTTP stub), `test_settings` 83 s (one 72-second sweep), `test_replay_slices` 73 s. Two slow classes lack `@slow`.
- **Helpers (E10):** seven `Recorder` classes, seven HTTP stub servers, about eight PDF builders, "SOURCE DATA" split by hand in eleven files. A `stubs.Recorder` base with answer hooks, `stubs.source_data()`, one model server and one PDF builder.
- **The boundary test doesn't recurse (E6):** five `eval/rounds` modules and `vendor/` are never checked (clean today).
- **Product tests import lab generators (E18):** they fail without the lab rather than skip.

## The 2026-10-01 review: status

| Item | Status |
|---|---|
| 1. Defaults exceed their budget | Fixed |
| 2. Judges take settings from the environment | Fixed; residual C9 |
| 3. Situating not rebound | Fixed |
| 4. Binding against current defaults | Fixed |
| 5. Stale task rows on resume | Fixed; table rows still split after "not reached" (A3) |
| 6. Rotation outside `pages.py` | Fixed |
| 7. One unreadable PDF aborts the run | Fixed for content; the scan still aborts (C1) |
| 8. Folder fixtures repack by row count | Fixed |
| 9. Cost caps per model | Fixed in the product and review commands; open in the eye and page tests (E2) |
| 10. Controlled scorer slips | Fixed, with tests |
| 11. A unit's score two ways | Fixed; claim-identity fallbacks still differ (E17) |
| 12. Truncated answers retried | Fixed; invalid answers still retried (C10) |
| 13. `reconcile` quadratic | Partly: grouped by value, still quadratic within one (D5) |
| 14, 15. Rounds report chart, bands on rotated sheets | Not rechecked (rounds paused) |
| Architecture: settings declared once; replay policy; report ownership; HTML writers | Fixed; residuals C4, C14, D8 |
| `extract.py` split; `llm.Client`'s jobs; the CLI hosting the pipeline | Partly (A9, A10, A12; C14, C15; C6, C7) |
| Hidden cycles | Open and grown: 21 modules (C4) |
| `PageScan`; crop renderers; drawing fetches | Open (A8, A16) |
| Number parsers and normalisers | Partly: `values.py` owns the main ones; copies remain (D10) |
| `controlled.py`'s concerns; `rounds.py`'s jobs | Partly (E4, E8); fixed |
| Evaluator setup; script boilerplate; test helpers | Partly; grown; open (E7, E4, E10) |

## Strengths worth keeping

- **Requests named by their content,** golden requests and committed replays: every refactor below can be proven byte-identical offline.
- **Coordinates have one owner** (`pages.py`), and rotation bugs haven't returned; region names have one (`regions.py`).
- **Settings declared once,** with every derived table generated and a test toggling each setting through the whole pipeline.
- **Workers only send requests;** callbacks run on one thread, identical in-flight queries merge, the scheduler is fair and bounded.
- **The fixture, replay policy and transport split** (`Fixture`, `Replayer`, `Transport`), reproducible packing, a well-tested transport.
- **Pure, fast table functions** (`row_claims`, `problems`, `apply`, `pdf_parts`, `ruled_rows`, `cut_columns`: 47 tests in 0.3 s); cells never retyped; closed vocabularies.
- **Alignment is pure and deterministic,** its thresholds named and documented; findings keep pair order however requests finish.
- **A clean product–lab boundary;** self-checking corpus generators; typed round specifications.
- **Failures are recorded, not fatal:** an unreadable document is one failed row; a metafile reports what it couldn't draw.

## Proposed order

The order is Claude's (the owner leaves order to Claude); the architecture moves are proposals for the owner's review.

1. **The high and medium bugs, each with its test** (B1, A1, D1, B2, D2, C1, A2, B3–B5, A3, A4, C10, E2, E3 and the small ones): about two days. B1, A1 and D1 first. Re-recording: D1 and B2 change some claims (a corpus run, cents).
2. **Performance with requests byte-identical** (C2 with C3, A5–A8, P1, D3–D5, C19), then the lab scorer (E1) and a parallel test runner (E9). Each proven by the golden requests and replays; the replay about 40% faster.
3. **The layering (C4)** and the moves it unlocks (A12, A13, C5, C15, D6's modules): pure moves, cycles checked by a test of the import graph.
4. **The orchestrators:** `PdfTable` and `Task` (A9, A10), the shared asking machine (B: A1, A11), the grid's owner and the text-format split (B: A2–A4), `pipeline.run` and the plan (C6, C7), `compare` and alignment (D6–D8).
5. **Simplification and dead code** alongside the modules each step touches; the lab's recording module, evaluator helper and test stubs (E4, E7, E10).

**For the owner** (answered 2026-10-09):
- **Durability:** `synchronous=NORMAL` trades the last few transactions after a power cut (not a crash) for commits 40 times cheaper. Proposed: yes for the store, with the diagnostic writes batched in any case. Paid answers are also in the fixture.
  - **The owner:** "I think it's safe to reduce durability of commits. This system is designed to resume from what is known to be committed, IIRC. The main exceptions should be the things humans manipulate manually, e.g. adding/removing items to project, updating configurations, etc."
- **Drawing sheets:** skip table detection on pages recognised as drawing sheets (A20; 1.4 s a page). It changes what's read, so it would be a lever, measured.
  - **The owner:** "We can add skipping table detection as a lever, np."
- **The architecture moves (3 and 4)** before the next features, or interleaved with them.
  - **The owner:** "We'll focus on bugfixes, then architecture, then new features, except in cases where a bugfix would be much easier after an architecture fix (if you recommend them). To explain this order: I'm not fond of mixing bugfixes (behavior modifying) with architecture updates (behavior preserving), nor of trying to preserve known bugs. For the larger bugs, please develop a remediation plan."
  - The plan: [remediating the review's larger bugs](../plans/review-bugs-2026-10-09.md). Performance with requests byte-identical (step 2 above) joins the architecture phase, as behaviour-preserving; the A20 lever goes with the features.

## Fixes so far

The owner, 2026-10-08: "before working on these, we'll focus on the architecture and bugs found in your review. Please start with all low-hanging fruit that has obvious fixes and doesn't need my attention." Each fix has a test that fails without it, unless noted.

| Finding | Status | Commit |
|---|---|---|
| E9: the suite one module at a time | `scripts/run_tests.py`, one module per process: about 2.5 minutes instead of 9 | `5a3a0f1` |
| B1, A1, D1 (the high bugs) | Fixed | `f77c56e` |
| C1, A2, A3, A4 | Fixed (A4: a mending bug of ours is named and the table read as detected) | `f77c56e` |
| C10, C12, C9, C8, E2 | Fixed (C10: a stream cut off still retried, as a connection fault; E2 has no test) | `8056c5a` |
| D9, B3, B4, B8, B9, C23, C24, D11, E19, A15 | Fixed (C24: a rebind nobody was asked about keeps saved comparisons; a reset still clears them, as decision 0004 says) | `8056c5a` |
| A14 | Fixed; latent today (only image tasks continue, and only table rows repeat) | `8056c5a` |
| `dispatch._same` reading a gone `Client._sample` | Fixed | `8056c5a` |
| Dead code (product) | Removed: the unused names and imports, PyMuPDF fallbacks, `scripts/alignment_sketch.py`. Kept: test-only helpers, and the lab's `QuoteCheck`, `claim_shares` and `suggested_verdict` (tested parts of paused rating tools) | `8056c5a` |
| B6, B7 | Fixed without the shared asking machine: each review call finishes its progress once; a structure asked again records its outcome under `:again` | `7ab18da` |
| B10 | Column letters past AZ, and a second "no rows" answer read as no table (two parts of the drawing slice, recorded anew). The prompt's "and/or" left as it is: the next sentence states the union, and a wording change needs re-recording and measuring. The slices fixture re-recorded for the two parts ($0.25 spent, nearly all on held-out runs recorded by mistake and pruned) | `7ab18da` |
| E3 | Fixed: the lab's rounds and review batches read every format through one document view; a text format is shown as its lines ([plan](../plans/review-bugs-2026-10-09.md), item 1) | `389a26e` |
| D2 | Fixed: the two alignment passes' outcomes combined, so an unchanged file changes no status or grouping ([plan](../plans/review-bugs-2026-10-09.md), item 2); the three-way alignment recorded as a lever idea | `038e9c7` |
| B2, and B10's wording | Fixed: rows read by themselves as the grid holds them (wrapped lines joined); one-cell rows holding a number proposed as notes, confirmed by the rules query, read by themselves and labelling nothing; the structure prompt says union. Readers pdf/7, docx/7, pptx/6, xlsx/11, csv/7. Slices re-recorded ($0.174); corpus: PDF right 3287 to 3295, loose 426 to 416, misbound 203 to 205, hallucinated 6 to 8 (pseudo-tables), one more change found ([plan](../plans/review-bugs-2026-10-09.md), item 3) | `813c510` |
| B5 | Fixed: a block of two columns, its left column holding no number, is proposed as a key-value list and the model asked (a PDF's with its crop); confirmed, its rows are read as "key: value" lines. On the corpus, the 35 checks of real tables and data sheets were all answered right. Readers pdf/8, docx/8, xlsx/12, csv/8. A data sheets project added to the corpus: Word and workbook recall on it 0.947 to 1.0; elsewhere one misbound claim more (a drawing's pseudo-table). $0.26 ([plan](../plans/review-bugs-2026-10-09.md), item 4) | `af1d6e4` |
| Reader versions | pdf/6, text/2 (.txt), docx/6, pptx/5, xlsx/10, csv/6, for the readers whose output changed | `8056c5a` |

**Measured on the controlled corpus** (`e2a6f67`, $0.001): PDF misbound claims 205 to 203 (2 fewer claims); every other format, and every revision pair, unchanged.

**Also fixed under the remediation plan** (the [trials review](trials-2026-10-08.md)'s two bugs, not this review's): a fixture named alone created and recorded into (`94966c7`); refinement cutting tiles between lines or columns (`6c914e7`, checked further in `992cfef`). The latter added `Context.lines` and `Context.graphics`, page caches that are part of A8.

**The behaviour-preserving phase** (the owner, 2026-10-09: "let's move forward on behavior-preserving improvements first"). Each step is proven offline: the eight development runs of the slices replayed with no model (`samples/slices`, the committed fixture), every report identical to the one before the step, no request unrecorded; the golden requests unchanged; the full suite.

| Finding | Done | Replay of the 8 dev runs | Commit |
|---|---|---|---|
| A5 | A page's rotation matrices built once per page object (`pages._matrices`) | 151.0 s to 127.0 s, with A6 and C19 | `d7c7e71` |
| A6 | One text page for a crop's text layer and its blocks (the same flags) | | |
| C19 | A request's body built only when it's sent (`Request.raw`, on first use) | | |
| E9 | `@slow` on `RecordedJudging` and `UnderTheNull`. `test_fixtures`' recordings left as they are: 4.8 s of a 7.5 s test is commits, which C2 removes | | |
| E6 | The boundary test walks subpackages (`vendor/`, `eval/rounds`) | | |
| E18 | `stubs.needs_lab()`: product tests building input with the lab's generators skip without it (13 tests) | | |
| C14 | `recipes.py`: `Recipe`, its shared slots read by name (role, region, content, task, label), `RECIPES` and `recipe_fields` moved there; stored recipes and fixture labels unchanged | | |
| Small copies | Locators by lines share `InLines.bbox`; `Judgment` and `Explanation` share `DropsUnknown`; schemas unchanged. `_filled`, `_joined` and `_plain` wait for `tablegrid.py` (architecture item 6), their owner | `d7c7e71` |
| E1 | The controlled scorer's words, vocabularies, rarity, units and fact numbers cached on what they're made from; a claim's names weighed once per claim, not per fact. Results identical (every run, by reader too); `controlled.py score` 401 s to 67 s, its scoring 155 s to 22 s | (lab only) | `e696d89` |
| C2 | The store commits at NORMAL and people's changes at FULL; the query log and the fixture's recipes ride in the next transaction; a test bounds commits per replay (65 for 182 answers; 429 before). The fixture keeps its rollback journal at FULL, unlike the plan's WAL: see [decision 0025](../decisions/0025-commits-wait-on-the-disk-only-for-peoples-changes.md). Store tables after a run identical; the suite 136 s to 113 s (`test_fixtures` 161 s to 61 s) | 127.0 s to 97.9 s, with C3 | `f4a2734` |
| C3 | A zipped fixture replayed from a read-only copy | | `f4a2734` |
| A7 | A page's display list built once and every crop rendered from it (`Context.pixmap`, as `Page.get_pixmap` renders): crops byte-identical, as every query's image hash replayed | 97.9 s to 91.9 s, with A8 | `2956969` |
| A8 | A page's drawings fetched once for figures, graphics, the empty-tile check and the page's signals (`Context.drawings`). Both kept for the last two pages only (`context.Recent`): a drawing sheet's are large. Not shared: situating's figures, read from its own copy of the document, and the clipped text pages of crops (PyMuPDF ignores a clip given a text page) | | `2956969` |
| P1 | A workbook's formulas loaded again only where a sheet holds a cell without a value and its part a formula (Excel saves every formula's value). The 35 workbooks in the samples and the corpus, and two made for it, read to identical documents, 14.0 s to 8.9 s | (no workbooks) | `66361b4` |
| D3 | Name words looked up among items with the same identifiers or none: a pair sharing no value whose names hold different identifiers can't reach the floor. 2,000 rooms 18.6 s to 0.5 s | | `25ec3d9` |
| D4 | Within an item, each claim's words computed once; leftover pairs found by a shared attribute word. One item of 2,000 claims sharing no value 96.8 s to 8.6 s (its 133,340 pairs to judge are the rest) | | `25ec3d9` |
| D5 | A claim compared only with its value's clusters seen on one of its pages, in the order they were started. 4,000 claims of one value 50.3 s to 0.5 s. D3–D5: 400 random revision pairs and 300 claim sets identical; the controlled corpus replayed into fresh stores gives all 280 reports as recorded | | `25ec3d9` |
| Test gaps | Table continuation over pages (A19); the rules and structure queries' failure paths (not reached, failed, first or second answer, a failed review); alignment at scale (with D3–D5); the vetoes, lifted into the pure `compare.vetoes` | | `11ea2cb` |
| E10 | `stubs`: a `Recorder` base with stock answers (six extraction fakes now subclass it), `source_data` (14 hand-made splits), `text_pdf` (five builders), `serving`, `request_body` and `chat_answer` (seven stub servers' boilerplate). Left as they are: the judge fake, the workbook tests' scripted model, and the builders that draw | | `6dbcbaa` |
| C4 (architecture 1) | `models` split into `schema.py` (claims, locators, answers, evidence, coverage, the report documents; imports nothing of the product) and `settings.py` (Settings and their loading; the lever marks, moved from `context`, which never used them); every importer imports from the owner; `llm` imports Settings for type checking only. A test pins the import cycle: still 21 modules, now held by edges later items break (`compare` → `provenance`, A12's `extract` ↔ `tasks`, A13's `situate` → `extract`, C14's `llm` ↔ `fixtures`, C15's evaluator settings, item 7's `textdocs` ↔ `docxdocs`). The corpus replayed into fresh stores: 280 of 280 reports as recorded | 8 dev runs identical | `f9b012b` |
| A12 (architecture 2) | `extract.py`'s five jobs apart: the extraction prompt (`ExtractQuery`, the template, the continuation note) to `tasks.py`, its one user; the scheduler, the readers by extension, `image_pdf` and `extract_pdf` to `jobs.py`; `Visuals` and `render` to `visuals.py`; `extract.py` the PDF job. Its 23 re-exports gone: callers import from the owners (`situate` takes sections from `sections`). The cycle: 21 modules to 11 and 4 | 8 dev runs identical; corpus 280 of 280 | `f7df55a` |
| A13 (architecture 8) | Figure detection (captions, drawing clusters, images, drawing sheets, figure labels) to `figures.py`, which imports only `pages` and `schema`; `situate.py` keeps the references, the figure map and the situating requests. `context`, `stems`, `levers` and `cli` take figures from `figures` | 8 dev runs identical; corpus 280 of 280 `ea0d9f5` |
| C5 (architecture 9) | The binding's policy (what differs, whether it's free, the refusal's text, the regions affected, `bind`, the rerun estimate) to `binding.py`, over the store's operations; the store gains `save_interpreter` and `logged_queries`, and no longer imports the levers or the settings, nor re-exports region names. Left in the store: reconcile on load (`Store.evidence`; moving it changes every reader of evidence) and rescans | 8 dev runs identical; corpus 280 of 280 `ffd6956` |
| C15 (part of architecture 12) | The evaluators' helpers (`evaluator_settings`, `EVALUATOR_SETTINGS`, `folder_client`, `Budget`), which the product never used, to the lab's `eval/clients.py`. That cut `llm`'s last edge to the settings: the cycle of 11 broke into `compare`/`levers`/`provenance`/`settings` (D6) and `llm`/`fixtures` (C14), with the text formats' four (item 7) | 8 dev runs identical; corpus 280 of 280 `a5993d3` |
| D6's modules (part of architecture 11) | Retrieval (`words`, `candidates`) to `retrieval.py`, the levers' only use of `compare`; the explain stage (its prompt, `Revisions`, `explain`) to `explain.py`. `compare` no longer imports `provenance`: the pipeline gives it its recipe label (the comparison interpreter's hash, as before; the stores' recipes as recorded). The cycles left: `llm`/`fixtures` (C14) and the text formats' four (item 7) | 8 dev runs identical; corpus 280 of 280 `ee1c5d1` |
| Architecture 6 | `tablegrid.py`, the grid's one owner: `Grid`, its constructors, section rows and possible notes, letters, cell values, header labels and units (from `tablerules`); readers' cells on a grid and their header rows and labels (Word's private helpers the deck and workbook readers borrowed, now public); rows' cells filled, joined and folded (the three copies, deduplicated). `office.py`: the package, the namespaces and EMU the three readers each defined, list-number formats (the deck reader borrowed Word's). Kept: a table block's raw rows beside its grid, which Markdown tables and charts (no grid) and rows read by themselves still use | 8 dev runs identical; corpus 280 of 280 `c7c638e` |
| Architecture 7 | `textdocs.py`'s three jobs apart: the document model every format shares to `textmodel.py`; the job reading any text format to `textjob.py`, its if-chains over formats now `FORMATS`, a registry by extension (reader, derivation, locator, pictures' kind; an office format is one with pictures); `textdocs.py` reads plain text and Markdown. The text formats' cycle broke: one is left, `llm`/`fixtures` (C14). Not done: one writer shared by the office readers (B: A4), more than a move | 8 dev runs identical; corpus 280 of 280 `21a3a38` |
| C14's cycle (part of architecture 12) | The failure classes and `transient` to `failures.py`, which the fixture imports instead of the client: the last import cycle broke. The product has none; `test_boundaries` checks it stays so | 8 dev runs identical; corpus 280 of 280 `1e797eb` |
| A10 (architecture 4) | `tasks.Task`, a frozen dataclass of a request's making, in place of `consume`'s 17 parameters; a continuation and a repeat's follower are `replace(task, ...)`, not two hand-made re-listings | 8 dev runs identical; corpus 280 of 280 `a1ce1fa` |
| A9 (architecture 3) | `_pdf_job` (264 lines with its closures) now 38: `PdfReading` holds what a PDF's pages share and reads a page in steps (text, detection, tables, signals, vision); `PdfTable` reads one table (its crop, parts, rows, key-value check, rules), everything bound when it's made and each part's values with `functools.partial`; continuation is the pure `continues()`, tested. Late-binding findings (ruff B023) in `extract.py`: 8 to 0 | 8 dev runs identical; corpus 280 of 280 `3079df3` |
| Architecture 5 | The exchange both table queries hold (ask, check, ask again once, review until kept or capped, not reached) once, in `asking.Asking`; the rules and structure queries are subclasses giving their checks, texts and outcomes. `TaskCore.ask` is the one way a table query is asked (the rules, structure and key-value queries and their reviews: four copies before) | 8 dev runs identical; corpus 280 of 280 `6e3450f` |
| C6 (architecture 10) | `pipeline.run` split into `prepare` (binding, readings, scans), `read_sources`, `write_evidence` and `compare_and_report`; `run`, `compare_paths` and `cli.main` take a client (the caller's, kept open), so the three tests that patched `pipeline.Client` pass one. evidence.json, too, as recorded for all 280. Not done: `--plan`'s own task enumeration (C7) shared with extraction, which changes what the plan prints (it misses section splits, formats but PDF, table queries): a behaviour change, for the owner to schedule | 8 dev runs identical; corpus 280 of 280 `43d508b` |
| D7 (architecture 11) | `align.Alignment`: alignment's steps (match, compare the matched and the ambiguous, attach, leftovers) as methods, each step's outcome kept for the next; the report's groupings read it (`_groups` took 13 parameters). 400 random revision pairs align identically. Not done: D8, the report's content settled before it's saved: `write_report` adds `tables_read` to findings after the comparison is saved, so settling it first changes what the store keeps (a behaviour change, for the owner) | 8 dev runs identical; corpus 280 of 280 `5a885cf` |
| E8 (architecture 13) | The lab's three import cycles broken: the controlled corpus's model (`Fact`, `Draw`, `Project`, `locate`) to `controlled/model.py`, which its drawers import instead of `corpus`; `corpus()` (every document, knobs and revisions) to `controlled/catalog.py`, above `corpus` and `revisions`; `score` imports `relations` directly, not through the package; the raters (`ModelJudge`, `Person`, `QuoteCheck`) to `eval/raters.py`, above `judgements` and the rounds. `test_boundaries` checks the lab has none | the corpus regenerated byte for byte; scores unchanged `934d663` |
| E4 (architecture 13) | `bench/recording.py`: the base settings every recording shares (three copies, identical) and the ledger's place (seven); the ledger checks' redundant guards dropped (`ledger.spent` is 0 without a ledger); `controlled.py`'s four representations in one `REPRESENTATIONS` table (four hand-made lists). Not done: the scripts reduced to argument parsing | scores unchanged; corpus 280 of 280 `b847a12` |
| E5 (architecture 13) | The lab reads the product's tables through their owners: `Fixture.responders()`, `usage(query)` and `recipe_usage(role, responder)`, and `Store.situation_data(content)`, in place of SQL in the eye and page tests, the rounds' measures, the review batches, `controlled.py` and `real_pairs.py`. Left: the refinement bench's per-task reads of a store (no store method gives a task's own claims) | 8 dev runs identical; corpus 280 of 280 | |

**Status, 2026-10-09:** every finding in *Bugs and risks* is fixed. The [remediation plan](../plans/review-bugs-2026-10-09.md)'s six items are done.

**Still open** (the behaviour-preserving phase, as the owner ordered on 2026-10-09; the steps done are in the table above):
- **Performance:** none left. (Done: A5–A8, C2, C3, C19, D3–D5, E1, P1.)
- **Tests:** none left. (Done: E6, E9, E10, E18, the guard on commits per replay, and the gaps: A19, the table queries' failure paths, alignment at scale, the vetoes.)
- **Architecture:** the rest of 12, and 13. (Done: items 1–11 but D8, C15 and the last import cycle.)
- **Behaviour changes found:** `--plan` enumerates tasks itself and has drifted (C7); sharing extraction's enumeration changes what it prints. A saved comparison lacks the `tables_read` its report shows (D8); settling the report before it's saved changes what the store keeps.
- **Simplification:** normalisers and number parsers (D10, S1), the long functions. (Done: C14, the models' copies, the table helpers' three copies.)
- **Not in this phase:** A20, a lever with the features (the owner's answer, above). Two bugs found under the remediation plan wait on the owner's order: decks' two-column tables aren't checked, and a section row under a PDF table's header is taken for its second line (the plan's *Found along the way*).

