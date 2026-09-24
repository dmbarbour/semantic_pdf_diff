# Test models and record/replay

- **Status:** Planned
- **Depends on:** [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (response cache, interpreter records)
- **Enables:** fast realistic integration tests for every later plan; the [retrieval-benchmark](retrieval-benchmark-2026-09-23.md)

## Goal

Test the pipeline against **realistic model responses without calling a model**, so that most integration tests run in seconds, offline, and deterministically, and model availability stops being a bottleneck for development.

## Idea

1. **Record** the model requests the pipeline makes on a curated slice of the public sample corpus.
2. **Answer** them with several responders, each stored as its own response table:
   - **Claude** (answering in a development session): a strong reference
   - **a weak local VLM** (e.g. a small Gemma via Ollama on CPU): exposes brittleness
   - **gemma-4 in-house:** the owner records the same public slice in an empty, non-sensitive sandbox with access to the in-house server. It's the most realistic table, and shareable because the documents are public.
   - **the existing stub server**: for failures (malformed JSON, truncation, 429s), which real responders rarely produce on demand
3. **Replay:** tests run the real pipeline with a client that answers from a chosen table.

Local embedding servers (`scripts/embedding_server.sh`) cover the embedding side; they're fast and deterministic enough to call live.

## Assessment

It will substantially speed up testing after the first round, and it lets strong and weak responders bracket the behaviour we care about. It also has real weaknesses; the design below is shaped by them.

- **Exact-hash keys are brittle.** The response cache keys on the full request: prompt text, image bytes and settings. Any prompt edit, chunking change or PyMuPDF rendering difference turns every recorded response into a miss. **Mitigation:** key replay on a *semantic* request key: task kind, prompt version, content ID, locator, a hash of the input text, and for images the crop specification (content, page, rectangle, scale) rather than PNG bytes. Real prompt changes still invalidate responses, as they should; incidental byte changes don't.
- **The pipeline is adaptive, so recording takes rounds.** Retries on partial results, comparisons and criteria depend on earlier answers, so a single pass without a model only sees first-stage requests. **Mitigation:** record in rounds. Answer round 1, replay, collect the new misses as round 2, answer those, and repeat until no new requests appear (usually two or three rounds for a small slice).
- **Stale responses can hide regressions.** A response recorded for an old prompt, silently reused for a new one, tests nothing. **Mitigation:** the prompt version in the semantic key makes misses explicit. Each response records its responder and interpreter, and replay reports what it served.
- **Recording by Claude is laborious.** Answering hundreds of extraction requests (reading page images, writing schema-valid JSON) takes a lot of session time. **Mitigation:** keep the slice small and deliberate: a few pages per sample family plus known edge cases (dense tables, charts, diagrams, the messy spreadsheet), tens to low hundreds of requests, not whole documents.
- **Replay tests the pipeline, not model quality.** A weak 4B model is not gemma-4, and Claude is much stronger than either. The tables *bracket* behaviour; they don't predict gemma-4's accuracy. Accuracy belongs to the benchmark, ideally with a gemma-4 table.
- **Responses drift.** Even at temperature 0, servers and weights change. Tables are dated snapshots with interpreter metadata, not ground truth.

## Design

### Fixture format

A **SQLite database per fixture set**, stored zipped in the repo (e.g. `tests/fixtures/replay-<set>.sqlite.zip`) and unpacked to a temporary directory by tests:

| Table | Contents |
|---|---|
| `request` | semantic key; task kind; prompt version; content ID and locator; input text (or its hash plus an excerpt); image crop specifications with image hashes; the round in which it was recorded |
| `response` | semantic key, responder (e.g. `claude-opus-5.5`, `gemma-3-4b-ollama`, `gemma-4-inhouse`), response JSON, interpreter metadata, date, notes |
| `meta` | fixture name, sample-set hashes (from `scripts/samples.json`), tool version, schema version |

- **No images inside.** Crops are regenerated from the pinned samples, and hashes confirm they match. That keeps the zip small (target: a few MB).
- **Same shape as the store.** The `response` table mirrors the store's response cache, so a fixture can also seed a real store for a manual run.
- **Reproducible zips:** rows are written in a sorted order with fixed timestamps, so re-packing unchanged data gives identical bytes and git history stays meaningful. A `fixtures summary` command prints what a fixture contains, since a binary diff doesn't.

### Client modes

| Mode | On a hit | On a miss |
|---|---|---|
| `live` | — | call the configured model (today's behaviour) |
| `replay` (strict) | serve the recorded response | fail, listing the missing request |
| `replay-or-record` | serve the recorded response | call a live responder and append its answer |
| `collect` | serve the recorded response | return a placeholder and log the request as needed for the next round |

Tests use `replay`. Recording rounds use `collect`, answer the collected requests, then repeat. `replay-or-record` is for topping up a table with the weak local model.

### Answering tools

- **Export collected requests** as a work list: prompt text plus the regenerated crop paths, for a responder to answer.
- **Import answers** after validating them against the response schema, rejecting invalid ones, and storing them under the responder's name.
- For Claude, a session reads the work list and images, writes answers in batches, and imports them. For local models, `replay-or-record` does it automatically.

### Recording kit for in-house gemma-4

Recording in the owner's environment should be one command, not a project setup:

- **Self-contained:** the kit holds the work list and the public source files for the curated slice (a few MB), so it needs no internet access or `fetch_samples.py` run. It needs only this tool installed and the in-house endpoint configured through the usual `OPENAI_*` variables.
- **One command,** e.g. `pdf-semantic-diff fixtures record kit.zip --responder gemma-4-inhouse`. It answers every request in the work list, is resumable if interrupted, and respects the configured rate limits.
- **One small output file** holding responses only (no documents, no credentials, endpoint redacted), to copy back and import.
- **Rounds:** because recording happens in rounds, later rounds produce new, smaller kits. Keep the slice small enough that two or three trips cover it.

## Milestones

1. Semantic request keys and the replay client modes, with unit tests against hand-made fixtures.
2. Fixture database, zip packing, `fixtures summary`, and seeding a store from a fixture.
3. Collection rounds on a curated slice of the sample corpus: export work lists, import answers.
4. First tables: Claude on a small slice; the weak local VLM (Ollama, CPU) on the same slice.
5. Integration tests that replay each table, with expected outcomes checked loosely (structure, coverage, provenance), since answers differ across responders.
6. **Recording kit** and a gemma-4 table recorded in-house on the same public slice.

## Decisions (2026-09-24)

- **gemma-4 table:** the owner will record one on the public slice, in an empty non-sensitive sandbox with in-house model access, using the recording kit.

## Open questions

None currently.
