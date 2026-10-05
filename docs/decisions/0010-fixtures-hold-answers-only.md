# 0010. A fixture holds answers only; evaluation answers have fixtures of their own

- **Status:** Accepted (2026-09-28)
- **Source:** [content-addressed queries plan](../plans/content-addressed-queries-2026-09-28.md): [goal](../plans/content-addressed-queries-2026-09-28.md#goal), [design](../plans/content-addressed-queries-2026-09-28.md#design-proposed-for-review) items 2 and 8, [progress](../plans/content-addressed-queries-2026-09-28.md#progress) milestones 2, 3 and 6, [decisions](../plans/content-addressed-queries-2026-09-28.md#decisions-2026-09-28)

## Context

Under semantic keys ([0007](0007-semantic-request-keys.md)), fixtures stored each request's prompt text and image hashes, which replay doesn't need. Judge answers lived apart, in 2,685 cache files with keys of their own.

## Decision

- **The owner:** "I'm not sure I'd want to store images or query text in test fixtures in the general case... the idea with the test fixture is that everything should be deterministic enough, i.e. based on samples and responses to prior queries, to form the same reports."
- **The owner:** "the main fixture table - the (model, query-hash, repeat-index, response) - should be pretty close to pure. Other tables can hold whatever is convenient, so long as we don't compromise the main lookup."
- **Fixture schema 4** (`fixtures.SCHEMA_VERSION`):
  - `response`, the main table: keyed by (query, responder, sample), with the outcome, answer or error, usage, and when recorded
  - `description`: facts about each query's own content, for summaries
  - `recipe`: partial recipes (role, content, task; no query text), for summaries
  - `meta`: schema version, PyMuPDF version
- **Only `response` is used for lookup.** The side tables serve summaries and nothing else.
- **How each query was built** (its recipe and text) is logged in the run's store (the `query` table), which is git-ignored and rebuilt by replay. Lever notes are computed from it when dumping (`context.lever_notes`, `queries dump` in the lab), never stored or hashed.
- **The owner:** "Storing a few samples for quality judgements is reasonable". Each round's query dumps, with text and images, are kept with that round, which is local working data ([0015](0015-repository-contents.md)).
- **Judge answers use the same format, in separate files.** The owner: "Judge requests can use the same format, though perhaps a separate .db file"; "Batch per round for judge files is good"; "whatever makes the most sense here, just so long as it's kept out of our main test fixture".
  - Each evaluated folder (a round's batch, a spot check, a review batch) keeps every model answer its evaluation asked for in its own `replay.zip` (`fixtures.FOLDER_FIXTURE`), with a git-ignored working `replay.sqlite` beside it.

## Consequences

- The committed fixture stays small: 1.7 MB for 4,190 queries.
- Replay needs the sample documents, since queries are rebuilt from them.
- To see what was asked, replay the runs into a store, then dump its queries (`pdf-semantic-diff queries dump`, with the lab installed). The fixture alone can't show it.
- Rerunning an evaluation pays only for answers its folder fixture lacks. Packing is reproducible, so a replay leaves the zip's bytes alone.
- Verdict files keep their own layout, so rounds can be re-decided offline without any fixture.
