# Review: union provenance and concurrent extraction (scheduling milestone 1)

- **Date:** 2026-09-24
- **Plan:** [scheduling-and-triage](../plans/scheduling-and-triage-2026-09-23.md): prerequisite (union provenance) and milestone 1, merged with the task queue from milestone 2 as decided in the [store completion review](store-complete-2026-09-24.md)
- **Commits:** `6a2b622` (union provenance), `1a3d460` (throttling, thread-safe client), `456e6a9` (dispatcher, concurrent extraction and comparison), `5a9e0d4` (progress, logging, plan estimates)
- **Tests:** 116 passing on Python 3.12; 112 passing and 4 skipped on Python 3.10 with minimum dependency versions (including tqdm 4.60.0)

## Delivered

- **Union provenance.**
  - A claim's ID derives from its content and identity only.
  - Each task's sightings are stored as occurrences (store schema 6) and merged deterministically, across passes and pages.
  - The representative occurrence follows a fixed rule.
  - Reports say how often, and by which passes, a claim was found.
- **Throughput control.**
  - The client splits into prepare, cached and save, which run on the main thread (it owns the store and the PDF), and send, which is thread-safe.
  - `send` passes through a sliding-window rate limiter with time-of-day rules (`rate_limits`) and an adaptive gate (`concurrency`, default 4). The gate halves on 429/503 or a latency spike and grows back after a run of successes.
- **Concurrent extraction and comparison.**
  - A `Dispatcher` runs only HTTP requests on worker threads.
  - Extraction became a request queue whose refinement runs in callbacks. Pages are fed only while few requests are pending, which bounds memory.
  - Comparisons keep findings in pair order.
- **Progress and logging.**
  - `tqdm` bars on a terminal, heartbeat lines otherwise.
  - `-q`, `-v` (tasks), `-vv` (requests) and `--log-file`.
  - `--plan` estimates calls, tokens and minutes at the limit in force now.

## Evidence

- **Determinism:** concurrent (8 workers) and sequential runs against a stub with random latency produce identical evidence, coverage, findings, unmatched and shared lists. The test confirms requests overlapped, refinement happened and occurrences merged.
- **Concurrency:** 12 requests against a stub that takes 0.2 s each never exceeded 4 in flight and finished in well under half the sequential time. Throttled responses shrank the gate.
- **Estimates:** for the NREL 5 MW and IEA 15 MW reports, 1,143 calls and about 3.9 M tokens, roughly 8 minutes at 500k tokens/min (before table rows, refinement and comparisons).
- **Two bugs caught by the new tests:**
  - Replacing log handlers leaked the previous log file; it's now closed.
  - The resume test's patch on `ask` no longer intercepted anything once extraction used `send`. The test now targets `send`, and states the resume guarantee precisely (below).

## Drift from the plan, with justification

| Drift | Justification |
|---|---|
| Union provenance was built first, as a prerequisite. | Decided with you: first-seen de-duplication made results depend on task order, and concurrency would expose that. |
| The task queue is in memory; persisting it moves to milestone 2 or 6. | Resume already works by cache replay. Persistence adds progress reporting, which preliminary reports need, and nothing needs it yet. |
| **Resume under concurrency:** requests answered by the server but not yet saved when a run is interrupted are asked again (at most one per worker). | Saving happens on the main thread by design (single writer). Sequential runs keep the exact guarantee; the test covers both. |
| Content items are extracted one after another; only the tasks *within* each run concurrently. | Interleaving across files and sources is the fair-share part of milestone 2, next. For folders of many small PDFs, concurrency is currently limited to one file at a time. |
| `max_calls` default raised from 500 to 100,000. | `--plan` showed two ordinary reports need about 1,100 calls, so 500 was a hard cap that stopped real runs partway, not the safety stop the plan describes. |
| `--plan` doesn't count table rows. | Table detection is slow on drawing sets (minutes per document); the estimate says so. |

## Next: milestone 2 (fair share and not-reached), no open questions

- **One queue across all content being compared:** pages from every file of every source are fed round-robin by source, then by section, so compared sources advance together (the "balanced progress" preliminary reports need).
- **`not_reached`:** tasks and sections never started (a run stopped by `max_calls` or an interruption) are recorded as `not_reached`, not `failed`.
- **Persisting the queue** stays with preliminary reports (milestone 6), where it's first needed.
