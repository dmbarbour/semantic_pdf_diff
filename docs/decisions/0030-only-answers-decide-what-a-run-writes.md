# 0030. Only answers decide what a run writes; how the run went is recorded apart

- **Status:** Accepted (2026-10-13)
- **Source:** the [determinism review](../reviews/determinism-2026-10-12.md), found by the controlled corpus re-recorded under `leave_text: tables`

## Context

A live run handles answers in the order they arrive; a replay or a cache hit handles them in the order they were asked. One controlled run scored 3 claims more misbound replayed than recorded, from the same evidence. The review found 15 places where order, threads, the clock or the hash seed reached the output: first-wins choices in callbacks, unsorted store reads, a shared answer object edited by one waiter, budget caps checked per attempt on worker threads, telemetry in the report. No test exercised arrival order, since a replay answers synchronously.

The owner, 2026-10-12: "We definitely need to fix things so race conditions aren't observed. Not just for replay, either. Only the content (or absence, e.g. for timeouts) of answers should impact reports or metrics (discounting the log)."

## Decision

- **What a run writes depends only on:** its inputs, its settings, and each answer's content or absence. That covers evidence.json, report.json and report.html, coverage, the store as later stages read it, and every lab metric.
- **It must not depend on:** the order answers arrive in, thread scheduling, the wall clock, or PYTHONHASHSEED.
- **Tested by shuffling:** with `PDF_DIFF_ANSWER_ORDER` (tests only), the dispatcher holds cached and replayed answers, failures too, and releases them in a seeded order. A whole run replayed under several seeds must write the same evidence and report.
- **Answers are never shared or edited:**
  - A query's outcome, answer or failure, is kept for the run, so a duplicate gets the same outcome whenever it's asked.
  - Each waiter gets its own copy.
- **Order-free choices:** anything chosen among several is chosen by content (rank, page, task, id), never by which came first. Store and lab reads are ordered; float sums use `math.fsum`.
- **How the run went is in `run.json`** beside the report, as the log is: calls, tokens, cost, cache hits, the fixture's counts, `created_at`, the fixture's path as given. The owner: "Separate run.json."
- **Budget caps pause a run, they don't end it:**
  - Requests are admitted on the calling thread as they're asked; `max_calls` counts requests, not attempts.
  - Which work a cap cuts still follows the order earlier answers came in. So a report a cap cut says `paused`, and the lab refuses to score it; the run is resumed instead. The owner: "Paused, not a result."
- **A repeated table row's lead is its first sighting by page:** rows that may repeat are held until the document's pages are read and its requests answered, then read in (page, tag) order. The owner: "Hold until the document is fed."
- **Left as is:** a failure's text says how the answer came to be absent (HTTP 503 or a timeout), and may differ between runs that both lack it.

## Consequences

- **Recorded and replayed agree:** on all 210 controlled runs, and on the slices' runs at any concurrency.
- **Scores moved once, with the lab's fixes:** each reading is counted once per outcome. Standard runs: misbound 165 → 170, right 7,973 → 7,976. Row-by-row runs, re-recorded: misbound 242 → 146, loose 571 → 468.
- **Rows that may repeat are sent at the document's end,** a small loss of overlap.
- **`max_calls` counts fewer:** retries no longer count against it.
- **New order-dependent code needs a seed test:** `stubs.answers_shuffled(seed)` and `stubs.AtHand` serve a fake client's answers as cached, so they're shuffled too.
- **Judged lab answers recorded before the fixes** may be keyed by prompts that listed claims in another order (the refinement bench's unique claims), so a later judged run may ask some again.
- **Timing checks in tests** measure CPU time (`time.process_time()`), except where waiting is the thing measured.
