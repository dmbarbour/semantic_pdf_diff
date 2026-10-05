# 0001. The v0.2.0 robustness baseline is the stable tag

- **Status:** Accepted (2026-09-23)
- **Source:** [robustness baseline plan](../plans/robustness-baseline-2026-09-23.md); [plans index: suggested order](../plans/README.md#suggested-order); [evidence store plan: decisions](../plans/sources-and-evidence-store-2026-09-23.md#decisions-2026-09-23) (no store migrations)

## Context

A review of 0.1.1 found bugs that could abort real runs or silently corrupt evidence: API response shapes, table refinement, unit case folding and de-duplication, plus avoidable cost. The project was about to generalize well beyond comparing two PDFs, and needed a sound version to build on and fall back to.

## Decision

- Fix 0.1.1's correctness and robustness problems before generalizing (the plan was completed at `50e74cb`).
- Tag the result `v0.2.0`. It is the stable baseline; `main` is development.
- Nobody uses the tool between `v0.2.0` and implementation, so:
  - plans and checkpoints are reordered, split or merged freely
  - formats change without migrations: stores ([0003](0003-sqlite-evidence-store.md)) and fixtures ([0006](0006-replay-fixtures.md))

## Consequences

- Anyone who needs a stable tool uses `v0.2.0`. It compares two PDFs only.
- The tag sits on `01cac04`, 25 commits after `50e74cb` (plans, sample scripts and one test). The product code (`src/`) is the same.
- Development breaks compatibility freely: an older store refuses to open, and prompt changes invalidate cached answers.
- Nothing in `v0.2.0` measures real-model extraction accuracy (the plan's known limits).
- Once the tool has users, compatibility (migrations, release versions) needs a decision of its own.
