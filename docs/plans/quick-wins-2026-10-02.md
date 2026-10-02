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

None yet.

## Progress

- **Item 1, a quick test run (2026-10-02): done.**
  - `QUICK=1` skips 12 tests marked `@slow` (`tests/stubs.py`): slice replays, the settings-class sweep, every lever off, six fixture tests, the controlled corpus's byte test, concurrent determinism.
  - A quick run took 199 s; the full suite takes about 536 s.
