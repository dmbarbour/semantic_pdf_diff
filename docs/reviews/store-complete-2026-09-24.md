# Review: evidence store plan complete; next, scheduling and triage

- **Date:** 2026-09-24
- **Plan:** [sources-and-evidence-store](../plans/sources-and-evidence-store-2026-09-23.md): all milestones done, except reviewer-decision records, which arrive with their first consumer
- **Commits:** milestones 6 (`1034799`) and 7 (`c4a6445`); earlier milestones in their own reviews
- **Tests:** 98 passing on Python 3.12; 94 passing and 4 skipped on Python 3.10 with minimum dependency versions (SQLite's JSON functions work in both)

## Milestones 6 and 7

- **Shared evidence as retrieval targets:** each side's unique claims are compared with the other side's unique claims and with shared evidence.
- **File-level difference summary:** files unchanged, modified, moved, added and removed, compared relative to each source's roots, with zip members compared instead of their archives. Two single-file sources are compared as one file.
- **`show`:** six views as Markdown, CSV or JSON Lines. Five are SQL views in `store.sqlite`, so they can also be queried directly.
- **`report`:** regenerates a report from a saved comparison without model calls.
- **`gc`:** deletes orphaned content with its evidence, tasks, sections, cached extraction responses (now tagged with their content; schema 5) and crops. `--dry-run` previews, and `--orphaned-sources` also removes sources whose linked manifest is gone. A test confirms that after `gc` a rerun makes no model calls, so nothing still referenced was collected.

## Drift, with justification

| Drift | Justification |
|---|---|
| `gc` leaves cached *comparison* responses in place. | Their keys are hashes of evidence IDs, not content, and an orphaned entry is simply never hit again. Tagging them would need an evidence-to-cache index for little benefit; revisit if stores grow large. |
| Saved comparisons are kept by `gc`. | They are self-contained historical records (each embeds its evidence), and `report --comparison ID` can still regenerate them. |
| Crops are matched to content by a 12-hex-digit prefix. | Crop names already use it; a collision between two contents' prefixes is vanishingly unlikely. |

## The store plan overall

What exists now that the original tool didn't have:
- declared, rescanned sources over folders and nested zips, with provenance and manifests
- content-addressed evidence with locators, sections and derivation
- a resumable SQLite store bound to its interpreters, with selective reset
- semantic cache keys (so replay fixtures can be copies of a store's cache)
- shared-content handling and file-level differences
- maintenance commands

Three findings shaped later plans: page-scoped task identity (a bug caught by tests), the continuation false positives in the rules PDF, and the drawing-set table noise.

## Next: scheduling and triage, milestone 1. One architecture point to discuss

Milestone 1 is "concurrent client: rate-limit rules, adaptive backoff, a concurrency cap, `--plan` estimates, progress and logging". Milestone 2 is "persistent task queue: extraction restructured into discrete tasks".

**Finding:** a concurrent client is only useful to a concurrent caller. Extraction today is a set of recursive closures that run tasks one after another; a partial result immediately spawns its refinement children. Running tasks in parallel means restructuring extraction into independent tasks with a queue, which *is* milestone 2. Built in the planned order, milestone 1 would deliver a rate limiter that nothing calls concurrently, and its concurrency tests would exercise an artificial caller.

**Proposal: merge the two milestones' core, in this order:**

1. **Task queue:** extraction becomes a queue of tasks: text group, table row, tile, overview. A partial or failed result enqueues its refinement children. Page and section ownership stay as they are. The queue lives in memory to start with. A persistent queue across runs isn't needed yet, since resume already works by cache replay; persisting tasks adds progress reporting for preliminary reports, which comes later (milestone 6).
2. **Worker threads with one writer:** a small thread pool runs tasks, since the HTTP client is blocking I/O and threads are the simplest fit. Only the main thread writes to SQLite, applying results as tasks finish, which keeps the store's single-writer design.
3. **Rate limiting:**
   - a token budget per minute, with time-of-day rules; requests are estimated before sending and corrected from reported `usage`
   - adaptive concurrency: halve on 429/503 or rising latency, grow by one after a run of successes, up to the configured cap
4. **Progress and logging:** `tqdm` bars on a terminal, heartbeat lines otherwise, and `-q` / `-v` / `-vv` plus `--log-file`. This adds `tqdm` (MPL-2.0/MIT) as a dependency.
5. **`--plan` estimates** of tokens and wall-clock time under the configured limits.

**Determinism is preserved.** Results are keyed by task, not by completion order. Evidence IDs don't depend on order, and a test will compare a concurrent run with a sequential one. The one exception is duplicate claims: de-duplication keeps the first occurrence it sees, so with concurrency the kept copy could come from a different task. That needs a deterministic rule, e.g. keep the claim from the task that sorts first.
