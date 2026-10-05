# 0015. The repository holds code, docs and the answers tests replay

- **Status:** Accepted (2026-10-03)
- **Source:** [code review 2026-10-01: decisions](../reviews/code-review-2026-10-01.md#decisions-2026-10-02) item 6; [architecture clean-up](../plans/architecture-cleanup-2026-10-02.md): [decisions](../plans/architecture-cleanup-2026-10-02.md#decisions-2026-10-02), [progress](../plans/architecture-cleanup-2026-10-02.md#progress) milestone 9; [the rounds' record](../research/rounds.md) (2026-10-03); commit `715925a`

## Context

Development rounds committed their page images, judge caches with page text, round folders, spot checks, review batches and spend ledgers. Most of it could be regenerated from the public samples or mattered only as history, and every clone carried it.

## Decision

- **The owner (2026-10-02):** "Ideally, we should not be committing images and images for development rounds. The fixture for CI testing answers is probably the exception."
- **The owner (2026-10-03):** "I don't believe we need benchmark rounds, for example, though having a historical record of what was tested and the outcomes could be useful under `docs/research/rounds.md` or similar."
- **The owner (2026-10-03):** "Skip updating history for now, it's sufficient that a shallow clone can be thin."
- **Committed:** code, docs, and the answers tests replay:
  - `tests/fixtures/replay-slices.zip`
  - the five round batches tests replay (`tests/fixtures/rounds/`), without their crops and page text
- **Local and git-ignored:** run stores, working fixtures (`tests/fixtures/*.sqlite`), rounds, spot checks, review batches, page tests, spend ledgers and the rounds' history (`.gitignore`).
- **Findings go into docs:** `docs/research/rounds.md` records every round's decisions and spend.
- **Git history isn't rewritten:** the removed data stays in history up to `d0a5e43`.

## Consequences

- A shallow clone is thin. A full clone still holds the old run data.
- Crops and page text are rebuilt byte for byte from the public slices (`scripts/rerender_rounds.py`). Judging a batch without its page text stops and says how to restore it.
- On a fresh clone, tests that need the samples skip until they're fetched and sliced.
- Spend checks and budget caps read the local ledgers, which a fresh clone doesn't have.
