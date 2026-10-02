# Quick wins after the clean-up

- **Status:** Active (2026-10-02). The owner: "Please start with the quick wins. Create a small plan to control drift risk. Well, item 1 is fine, too, finishing control documents where natural."
- **From:** the [code review](../reviews/code-review-2026-10-01.md)'s leftovers, after the [architecture clean-up](architecture-cleanup-2026-10-02.md).
- **Then:** [controlled documents](controlled-documents-2026-10-01.md) milestone 4 (revision pairs), and its later milestones where they follow naturally. Tracked in that plan, not here.

## Rules against drift

- **Only the items below, within their bounds.** Anything found along the way that's outside them goes into *Found along the way* (or a tentative index row, if it's a new direction), not done now.
- **Requests stay byte-identical** where product code changes: golden requests, and a query snapshot of every slice.
- **One commit per item,** after the full suite passes. A quick run is for iterating only.

## Items

1. **A quick test run.**
   - A `slow` marker in `tests/stubs.py`; `QUICK=1` skips the marked tests.
   - Marked: the tests over about 10 seconds (on 2026-10-02 the suite took 536 s; five tests took 280 s).
   - Not in scope: rewriting tests to be faster.
2. **Dead code** (the review's "Unused code" list):
   - `SectionIndex.boundaries`
   - the `situate.native_rect` alias
   - `review.image_data`
   - `fixtures.NotRecorded`, which shadows `llm.NotRecorded`
   - `judgements.QUESTIONS` and `KINDS`
   - `schematics.build`'s `intro` parameter
   - `eyetest._axes`'s `card` and `rng`
   - the client's byte cache in a folder, which only tests use: they move to a store, or no cache

   **Not in scope,** each kept for a reason:
   - **Test-only code** (`QuoteCheck`, `claim_shares`, the spot-check page's verdict twin): a test is a use.
   - **The early-stop path:** rounds 1 to 8's records use it.
   - **Old-format fallbacks:** they read committed rounds.
   - **`Fact.basis`:** scoring it is a scorer change.
3. **Generated pages on the shared palette:** the insights, post-mortem, query dump, eye test, page test and rounds report pages.
   - Their heads come from `html_pages.page()`, and their colours from its tokens, so each gains a dark mode.
   - Not in scope: layout or content changes, and the three interactive templates (review, questions, spot check), which carry their own styles.
4. **The plans index:** statuses brought in line with the plans' own Status lines. No plan rewritten.

## Found along the way

- **Three dead imports**, found by the check that confirmed item 2's list was unused, and removed with it: `relations` in `schematics.py`, a second `pymupdf` import in `sections.py` (left by milestone 7's split), and `base64` in `review.py` once `image_data` went.
- **The page test's answers fixture gained three recipe rows** when its report was regenerated.
  - These are crops of different regions that render the same image, so they make one query; the replay noted the other ways it was built.
  - No answer changed. The rows are diagnostic labels.
  - The old packing counted rows, so it never wrote such additions; since milestone 2b's fix (packing by bytes) the zip catches up. Committed as it came.

## Progress

- **Item 1, a quick test run (2026-10-02): done.**
  - `QUICK=1` skips 12 tests marked `@slow` (`tests/stubs.py`): slice replays, the settings-class sweep, every lever off, six fixture tests, the controlled corpus's byte test, concurrent determinism.
  - A quick run took 199 s; the full suite takes about 536 s.
- **Item 2, dead code (2026-10-02): done.**
  - Removed: `SectionIndex.boundaries`, the `situate.native_rect` alias, `review.image_data`, `fixtures.NotRecorded`, `schematics.build`'s `intro` and `eyetest._axes`'s `card` and `rng`.
  - `judgements.QUESTIONS` and `KINDS` documented each question's answer; that text is now the `Record`'s comments.
  - **The client's folder cache is gone.** `Client` takes a store or nothing, and a folder is refused with a message. Its key (`request_hash`) went with it. Tests moved to no cache, and the caching test to a store. The streaming test now checks the query hash, what answers are cached and recorded by.
- **Item 3, generated pages on the shared palette (2026-10-02): done.**
  - The insights, post-mortem, query dump, eye test, page test and rounds report pages are built with `html_pages.page()`. Each keeps only its layout rules.
  - Colours come from the shared tokens. The palette gained good, mid and bad (results) and add and del (diff lines), so every page follows the system's dark mode, or `data-theme`, like the report.
  - The committed eye test, page test and r09b post-mortem pages were regenerated offline. Their bodies are byte for byte as before; only the head changed.
