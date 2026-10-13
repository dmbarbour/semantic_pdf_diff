# Determinism review: only answers decide what a run writes

- **Date:** 2026-10-12
- **Status:** Open. Fixes to follow; three questions for the owner (below).
- **Asked by:** the owner. "We definitely need to fix things so race conditions aren't observed. Not just for replay, either. Only the content (or absence, e.g. for timeouts) of answers should impact reports or metrics (discounting the log). Do a review for this."
- **Found by:** the controlled corpus re-recorded under `leave_text: tables` (commit c6f613a). lcc-enduse-s1-clean scored 3 claims more misbound replayed than recorded, from the same evidence.json.
- **The requirement:**
  - **What a run writes depends only on:** the inputs, the settings, and each answer's content (or its absence: failed, timed out). That covers evidence.json, report.json and report.html, coverage, the store as later stages read it, and every lab metric.
  - **What it must not depend on:** the order answers arrive in, thread scheduling, the wall clock or PYTHONHASHSEED.
  - **Absence:** which answers are absent must not depend on order either (see D6).
- **Method:**
  - **Four read-only reviews in parallel:**
    - extraction scheduling and claim assembly (a)
    - answers after they arrive: readings, store, situating (b)
    - comparison and reports (c)
    - the lab's scoring and benches (d)
  - Their probes ran offline on copies of stores and fixtures (scratch scripts, not committed).
  - **Replays by me:**
    - **The slices' development runs at concurrency 1, 8 (twice) and 16:** evidence.json identical. report.json differs only in `settings.concurrency` and the fixture's unpacked path (D9).
    - **The same with each replayed answer delayed at random:** identical too, and that proves nothing. A replayed answer is served inside the submitting call on the main thread, so a replay always handles answers in submission order. No test or replay exercises arrival order (D15).
  - **Checked by me in the code:** D1, D2, D3, D4. The other findings rest on the reviewers' reading or probes, marked as such.
- **Changed nothing; no model was called.**

## Root mechanism

- **A live run handles answers in arrival order.**
  - `dispatch.py` `wait_one` walks a set of finished futures, so even answers that finish together come out in no fixed order.
  - `jobs.py` `make_room` runs their callbacks between page feeds.
- **A replay or cache hit handles answers in submission order:** they finish synchronously inside `Dispatcher.submit`.
- **The consequence:** anything first-wins in a callback, or kept in arrival order without a sort, can differ between a recording and its replay, and between two live runs.

## Findings, most severe first

| # | Finding | Where | What differs | Verified |
|---|---|---|---|---|
| D1 | The lab's scorer counts whichever duplicate claim comes first | `bench/controlled/score.py` 272–291 | `outcomes` in results.json, `outcomes_by_reader`, relations; tiling and refinement benches (same `score`) | Yes: 4 corpus runs change with claim order; sorted, recorded and replay score alike on all 210 (d) |
| D2 | Coverage and lab reads come back in arrival order | `store.py` `coverage` (`ORDER BY rowid`); lab `rounds/units.py` 60–70; `bench/tiling.py` `answers`; `bench/refinement.py` `_stored`, `halves`, `_unique` | The lab's unit order, so D1's claim order; refinement judges' prompts (`_unique` keeps the first copy) | Yes (b, d) |
| D3 | A repeated table row's lead is the first to arrive | `tasks.py` 234–248 (`repeats.setdefault`, `seen` by arrival) | Which rows are sent, so request keys (a replay can miss a query the recording never asked); `duplicate_of` and issues; derivations; claims | By simulation with the real `TaskCore` (a, b). Default: rows are consumed from rules, structure and key-value answers |
| D4 | Waiters on an in-flight duplicate share one answer object, and compare's veto edits it | `dispatch.py` `_complete`; `compare.py` `finish` | A finding's rationale (the veto's reason prepended twice), so the explain prompt and its key | Yes, with a fake client: concurrency 1 against 4 (c) |
| D5 | A duplicate in flight shares its leader's failure; one sent after is asked again | `dispatch.py` 224–255 | Whether an identical query is answered or absent; `cache_hits`; the fixture's recipe rows | By reading (a, c) |
| D6 | Budget cut-offs depend on order | `llm.py` `_admit` (worker threads, per attempt, retries included); cost accrues on completion; lab caps (`controlled.py`, `tiling.read`, `refinement.py`) | Which tasks or pairs are `not_reached` or `processing_error`; evidence, findings, exit code | By reading (a, c, d). **Question 1** |
| D7 | A retiled tile's depth is its first asker's plus one | `retiling.py` 92–95; `visuals.py` 75–76 | With `refinement_depth` ≥ 2 only: the tile's text layer (so its prompt) and whether it may be refined again | By reading (a, b) |
| D8 | Situating issues are kept in completion order | `situate.py` 285, 290, 333, 339 | `situation[content].issues` order in evidence.json and report.json | By reading (b) |
| D9 | report.json records how the run went, not just answers | `pipeline.py` 224–229; `report.py` 167–170 | `usage` (calls and tokens with retries, cache hits, the fixture's temporary unpacked path), and `created_at` unless SOURCE_DATE_EPOCH is set (`scripts/controlled.py` doesn't set it) | Yes. **Question 2** |
| D10 | Comparison output depends on the order of its input claims | `explain.py` 79–114 (siblings and echoes cut by index); `align.py` 160 (`most_common` ties); `compare.py` 173–174, 240–243; `retrieval.py` 204–208 | Explain prompts, item names, `unmatched` order: today only under shuffled input. The input order is canonical (reconcile sorts), so this is defensive | Yes, by shuffling (c) |
| D11 | Float sums over sets follow PYTHONHASHSEED | `align.py` 195; lab `rounds/decisions.py` 143–144 | 0.9 against 0.8999999999999999; an exact tie at `MARGIN` would flip aligned and ambiguous | Yes, across 8 seeds; no outcome changed (c) |
| D12 | A shared query's cached answer is labelled with the first submitter's content | `llm.py` 493–498; `store.py` 412–415 | Deleting that content's cache can drop an answer another content still uses; it's asked again | By reading (a) |
| D13 | A claim id recorded twice by one task: the store keeps the last, a fresh run both | `store.py` 362–365 (`INSERT OR REPLACE`); `tablerules.py` `use`; `tasks.py` `follow` | A claim's occurrences, representative and confidence between a fresh and a loaded run. Not a race, but not answer-determined either | By reading; not present in the corpus (b) |
| D14 | Minor orders | `Store.view`, `Store.queries`; lab `insights.py` (`most_common` ties); verdict files; a failure's rationale is the last attempt's transport text | Display, file bytes; the failure text in a finding | By reading |
| D15 | No test exercises arrival order | `dispatch.py` (replays answer synchronously); `tests/test_concurrency.py` (no repeated rows, no duplicates in flight) | Every finding above passes the suite | Yes |

### Not a race: the pack's missing explain answers

Packing the corpus reported 3 explain requests without an answer. A reviewer traced them to the `--rows` runs (`table_rules` none). Pack replays these runs but `run --replay` doesn't. They weren't re-recorded after `leave_text: tables` became a default:
- Without the text task's reading, a merged claim's representative changed: `"P-101B 5,590"` became `"P-101B, 5,590"`, and "capacity" became "Capacity".
- The explain prompts changed with it.
- Replayed with `leave_text: none`, nothing is missing. Recording these runs again fixes it.

### Checked and order-safe

- **Merging:**
  - `merge_occurrences`, `store.evidence` and `readings.reconcile` choose the representative by rank, task and id.
  - Shuffling every controlled store's evidence rows (1,050 trials) changed nothing.
- **evidence.json:** coverage, sections and situations are sorted. Recorded and replayed are identical on all 210 controlled runs, and fresh and store-loaded runs are equal.
- **Request keys:**
  - A query's hash covers its prompt, image bytes and parameters; the recipe is a label.
  - Follow-up prompts (text splits, column splits, continuations, figure looks, table rules, structure and review rounds) carry only their own task's answers.
- **Once-a-page caches** (regions, tile choice, labels, retilings) are filled in synchronous page planning, from content. The tile choice's shuffle is seeded from the page's text.
- **Comparison:**
  - Pairs and the `max_pairs` cut are sorted by score and ids.
  - Alignment's assignment steps sort.
  - Explanation starts after every judgment and writes only its own finding.
- **The lab's sampling and statistics:** seeded shuffles, sorted pools, a t-interval with no random draws.

## Questions for the owner

1. **Budget cut-offs (D6).** Admitting each request on the main thread, in submission order, removes the thread race. Submission order still follows earlier answers' arrival (refinements, continuations, table rounds), so which tasks a cap cuts stays order-dependent. Recommendation:
   - Admit in submission order.
   - Mark a run cut by a cap as paused, not reproducible: its report says so.
   - The lab refuses to score cut runs (a bench resumes them instead).
   - A cap is a backstop, so a paused run is meant to be resumed, not read as a result.
2. **Run telemetry in the report (D9).** Recommendation:
   - Move `usage` (calls, tokens, cost, cache hits, fixture counts) out of report.json and report.html into a run record beside them (`run.json`), as the log is.
   - Record the fixture path as given, not where it was unpacked.
   - The report keeps the answer-determined content and `created_at` (SOURCE_DATE_EPOCH for byte-identical replays, as today).
3. **Repeated table rows (D3).** Recommendation: hold rows with a repeat key until the document's pages are all fed and its table answers are in. The lead is then the first by (page, task), the second sighting is sent too, and the rest follow as today. This delays those rows to the document's end, a small cost in overlap. The alternative is to let identical prompts share one query through the cache and set `duplicate_of` afterwards. That changes more: the section heading is in the prompt, so pages' prompts differ.

## Fix order (bugs; no behaviour change intended beyond determinism)

1. **A test that exercises arrival order** (D15):
   - The dispatcher, in a test mode, serves replayed answers through its pool in a seeded shuffled order.
   - Tests compare evidence and reports across seeds on corpus documents with repeated rows, duplicate queries and refinement.
   - It should fail on D3 and D4 before they're fixed.
2. **Mechanical fixes, one commit each:**
   - D4: no mutation of answers; each waiter gets its own copy.
   - D5: a query's outcome memoized per run.
   - D7: retiled tiles at a fixed depth.
   - D8: situating issues sorted.
   - D10: comparison input sorted.
   - D11: `math.fsum`, sorted sets.
   - D12: a shared query's cache kept while any content uses it.
   - D13: duplicates dropped per task.
   - D14: ORDER BY on the store's views.
3. **The store's coverage** in (page, task) order (D2).
4. **The lab, then its numbers re-scored (no model calls):**
   - D1: an order-free choice per reading, by outcome rank.
   - D2's lab reads ordered.
5. **The owner's answers:** D3, D6, D9.
6. **The corpus's `--rows` runs recorded again** (pennies), and the fixtures re-packed.
