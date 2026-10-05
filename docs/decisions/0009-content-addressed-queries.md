# 0009. Queries are content-addressed: keyed by what reaches the model

- **Status:** Accepted (2026-09-28)
- **Source:** [test models plan: decisions 2026-09-28](../plans/test-models-and-record-replay-2026-09-24.md#decisions-2026-09-28); [content-addressed queries plan](../plans/content-addressed-queries-2026-09-28.md): [goal](../plans/content-addressed-queries-2026-09-28.md#goal), [design](../plans/content-addressed-queries-2026-09-28.md#design-proposed-for-review) items 1–3, [migration](../plans/content-addressed-queries-2026-09-28.md#migration-without-paying), [progress](../plans/content-addressed-queries-2026-09-28.md#progress) milestones 2 and 5, [decisions](../plans/content-addressed-queries-2026-09-28.md#decisions-2026-09-28); [meta-audit](../reviews/meta-audit-2026-09-28.md)

## Context

Answers were keyed by request meaning plus a fingerprint of settings ([0007](0007-semantic-request-keys.md)), kept in step with prompts by hand. The meta-audit found that no test had caught any of 21 flaws, several of them keying flaws, and that some answers had been served for queries that had since changed.

## Decision

- **The owner (2026-09-28):** "it roughly allows us to treat queries as content-addressed, and essentially build triples of 'how model M responded to query HASH' for replay, albeit with some extra accounting for failures".
- **A query's name is `llm.query_hash`:** the SHA-256 of a canonical JSON of what reaches the model:
  - the system and user text
  - each image's hash, by its bytes, in order
  - the response format as sent, and the generation settings (output tokens, temperature, seed)
- **Left out:** the model (the M of the triple), the role, image paths, and transport (URL, streaming, timeouts, retries).
- **Images by bytes,** not by crop recipe: fixtures pin PyMuPDF, and replay tests skip under another version ([0006](0006-replay-fixtures.md)).
- **A recording is (query hash, responder, sample) with an outcome:**
  - `ok`: the answer
  - `invalid`: the model's failure, replayed as a failure
  - `transient`: timeouts and server errors, asked again when recording
- **Samples:** replay uses sample 0. The A/A control (`--fresh-regions`) asks for sample 1.
- **The store's response cache uses the same name:** the query hash and the model (`Client._cache_key`).
- **Identical queries share one answer,** such as the same page in both documents. The dispatcher asks each only once, even while both are in flight.
- **Levers are for diagnostics only** (the owner's decision, as the plans record it): they never enter the hash, and needn't be in the fixture record. The owner's reason, as recorded: keying by the query is robust not only to whether a lever applies to a query, but to how it applies.

## Consequences

- A changed query is a miss, never a stale answer. Nothing kept in step by hand decides whether a recorded answer still applies.
- Any byte change in a query re-pays it. Refactors keep requests byte-identical, checked by the golden requests (`tests/test_golden_requests.py`), the golden judge prompts (`tests/golden/`) and `scripts/query_snapshot.py`; otherwise the changed queries are re-recorded.
- Recorded `invalid` answers replay, so a variant's run differs from its baseline only where the variant changes queries.
- Replays are deterministic: two replays of the same runs give byte-identical evidence and reports (a test), with `SOURCE_DATE_EPOCH` fixing reports' timestamps.
- Endpoint settings must never change a hash, so every setting is classified ([0011](0011-settings-classified-by-effect.md)).
- Answers whose rebuilt query didn't match were let go when re-keying. The owner: "Let go of stale answers that don't have an obvious transition via replay".
