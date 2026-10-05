# 0006. Recorded model answers replay as test fixtures

- **Status:** Accepted (2026-09-25)
- **Source:** [test models and record/replay plan](../plans/test-models-and-record-replay-2026-09-24.md): [design](../plans/test-models-and-record-replay-2026-09-24.md#design), [milestones](../plans/test-models-and-record-replay-2026-09-24.md#milestones) 1–4 (`record-new`, 2026-09-27), [decisions 2026-09-25](../plans/test-models-and-record-replay-2026-09-24.md#decisions-2026-09-25); [content-addressed queries: progress](../plans/content-addressed-queries-2026-09-28.md#progress), milestone 1 (the prune guard); [meta-audit](../reviews/meta-audit-2026-09-28.md), flaws 3, 11 and 21

## Context

Integration tests against a real model are slow, cost money and vary from run to run. The stub server gives only canned answers and failures. Model availability was a bottleneck, and prompt work needed realistic answers in seconds, offline.

## Decision

- **Model answers are recorded into SQLite fixtures** and replayed through the real pipeline: `--fixture FILE` with `--fixture-mode` (`fixtures.MODES`):
  - `replay`: serves recorded answers; anything unrecorded fails. Tests use it.
  - `replay-or-record`: asks for whatever is missing, recorded failures included.
  - `record-new`: asks only what was never asked. It replays the model's failures as failures, and asks transient ones (timeouts, server errors) again.
- **Committed zipped:** `tests/fixtures/replay-slices.zip`. A `.zip` is replay-only, served from a temporary copy. Recording goes into a working `.sqlite`, which is git-ignored.
- **Reproducible packing** (`pdf-semantic-diff fixtures pack`): rows in key order, fixed timestamps, last-use times and sessions left out. Unchanged answers give identical bytes, so git history changes only when answers do.
- **`pdf-semantic-diff fixtures summary`** says what a fixture holds (answers per responder, role and outcome; tokens; PyMuPDF version), since a binary diff doesn't.
- **Slices, not whole documents:** recordings use deterministic page slices of the public sample corpus (`scripts/slices.json`, `scripts/make_slices.py`). They're cheaper to record and faster to replay.
- **PyMuPDF pinned:** slices are pinned by SHA-256 and by the PyMuPDF version that cut them. Fixtures record their PyMuPDF version, and replay tests skip under another, since text and renderings may differ.
- **No migrations:** a fixture with another schema version is refused (`fixtures.FixtureError`).
- How answers are keyed: [0009](0009-content-addressed-queries.md). What a fixture holds: [0010](0010-fixtures-hold-answers-only.md).

## Consequences

- `tests/test_replay_slices.py` runs the real pipeline offline on recorded answers (the first three development runs). Outcomes are checked for shape, not exact content.
- A fresh clone skips the replay tests until the samples are fetched and sliced. They also skip under another PyMuPDF version.
- Replay tests the pipeline, not model quality. Answers are one responder's dated snapshot, not ground truth.
- A PyMuPDF upgrade means re-cutting and re-pinning the slices, and re-recording what changed.
- **`fixtures prune` has a guard.** Unless `--force` is given, it refuses when:
  - no run used the fixture since `--unused-since`
  - a run since then missed requests
  - more than half the answers would go

  An unguarded prune once emptied the fixture.
- How to record, top up, prune and pack: [samples and testing](../samples-and-testing.md#recorded-answers-replay-fixtures).
