# Review: fair share across sources (scheduling milestone 2, part) and next steps

- **Date:** 2026-09-24
- **Plan:** [scheduling-and-triage](../plans/scheduling-and-triage-2026-09-23.md), milestone 2 (fair share and `not_reached`; the rest waits for triage and preliminary reports)
- **Commits:** `4786aac` (fair share), `fde16d0` (`max_calls` default, previous review)
- **Tests:** 117 passing on Python 3.12; 113 passing and 4 skipped on Python 3.10 with minimum dependency versions

## Delivered

- **Jobs and a fair-share scheduler.**
  - Extracting one PDF is a job: a generator fed one page at a time, which keeps its document open until its own pending requests (and any refinement they queue) finish.
  - `run_jobs` feeds pages round-robin across sources. A source whose job runs out of pages moves straight on to its next job within the same turn.
  - All compared sources' PDFs share one queue, so sources advance together, and a folder of many small PDFs is no longer limited to one file at a time.
- **`not_reached`:** work cut off by `max_calls` (`CallLimitReached`) is recorded as `not_reached`, not `failed`. Its content isn't marked extracted, so the next run completes it.
- **Deterministic coverage order:** sorted by content, page and task.

## Evidence

- **Fair share:** with one worker, two sources' pages alternate strictly while both have work, across job boundaries. The first version lost a source's turn at each job boundary; the test caught it before commit.
- **Determinism:** the concurrent-vs-sequential test still passes with the scheduler in place.

## Next: triage (milestone 3). One design choice, and a proposed reordering

### Repeated boilerplate: skip, or extract once?

The plan says repeated headers, footers, title blocks and legends should be "skipped or de-duplicated". The drawing sets show why it matters: about half the table rows on the first 40 sheets of `dc_cd.pdf` repeat on five or more sheets. Under union provenance, repeats already merge into one claim, but each repeat still costs a model call.

1. **Extract once:** send the first occurrence to the model. Later identical occurrences are recorded as coverage rows that say "same as task X on page N". The claim then gets an occurrence for each page, with no further calls. Nothing is silently dropped, and provenance stays complete. **Recommended.**
2. **Skip entirely:** never send repeated blocks. Cheaper, but a title block's content (project name, sheet index, revision) would never become evidence at all.

A block counts as "repeated" when the same normalized text appears on three or more pages of the same content. For text, that's restricted to the top and bottom bands of the page (headers and footers); for table rows, anywhere (title blocks). Identical *files* are already extracted once, via content IDs.

### Reorder: priority ordering waits for preliminary reports

Triage's other output is a priority order for sections. With no time budgets, a run always completes, so order only matters for what an *interrupted* run, or a *preliminary report*, has covered. Ordering also costs something: feeding pages out of order breaks the page-by-page table-continuation logic, which would need per-page table detection cached ahead of time.

**Proposal:** milestone 3 delivers the de-duplication above plus the cheap per-section signals (density of numbers and units, tables, drawings, text layer, requirement language), stored with sections for later use. Section *ordering* moves to milestone 6, with preliminary reports, where it first has value. Milestone 4 (the model's per-section triage call: type, keywords, "about" statements) stays next after 3.
