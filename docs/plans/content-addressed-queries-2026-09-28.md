# Content-addressed queries, checks and records

- **Status:** Planned (2026-09-28).
- **Depends on:** [test-models-and-record-replay](test-models-and-record-replay-2026-09-24.md), whose keys this replaces; [query improvement](query-improvement-2026-09-26.md), whose rounds get the checks.
- **Feeds:** every later round; the [weighted quality estimates](README.md) (judgement records); a lever search (plans index).
- **Why:**
  - **The owner's question:** better separation of concerns. The [meta-audit](../reviews/meta-audit-2026-09-28.md) found no test had caught any of 21 flaws, about half of them the kind structure and checks catch.
  - **The owner's decision:** requests keyed by what reaches the model (record/replay decisions, 2026-09-28).

## Goal

- **A query is what reaches the model, named by its hash.** A recording is a triple: how model M answered query H (the owner: "essentially build triples of 'how model M responded to query HASH' for replay, albeit with some extra accounting for failures").
- **Nothing kept in step by hand decides whether a recorded answer still applies.** No lever list, no key suffix, no fingerprint of settings.
- **A fixture holds only answers.** Everything else is rebuilt from the sample documents and those answers, deterministically enough to form the same reports (the owner). How a query was built, its recipe and lever notes, lives in the run's store for diagnostics, not in the fixture.
- **Cheap checks come before any money is spent on judging:**
  - settings classified by what they can affect
  - queries dumped for people and strong models to look over
  - batches checked for consistency when built
  - decision rules simulated under the null

## What changes, and why

| Today | Problem (meta-audit) | Planned |
|---|---|---|
| Fixture key: a hand-picked tuple of parts, plus a fingerprint of settings without the levers | Kept in step with the prompt by hand. The chart rules nearly weren't keyed, the locator thumbnail still isn't, and table numbers are keyed without reaching the model | The hash of what reaches the model |
| `LEVERS`, `EXTRACTION_SETTINGS`, `SETTING_REGIONS`, `TRIAGE_SETTINGS`, `COMPARISON_SETTINGS` | Five hand lists; `quote_match` misfiled (a reset re-pays text answers) | One classification of every setting, checked by tests |
| Extraction, situating and comparison keyed three ways; the run cache and judge caches a fourth | Code reads keys by position (`parts[5]` is the crop) | One request object and one hash; labels for everything else |
| The A/A control's answers under a `#fresh` responder | A naming trick | A sample number |
| What a lever added is visible only by reading prompts | Junk stems went unnoticed from r03 to sc01 | Lever notes per query, dumps, and a strong-model check each round |
| Fixtures store each request's prompt text and image hashes | Bulk that replay doesn't need | Answers only, keyed by hash; query text and images stay out, beyond a few samples kept for quality checks |

The run cache (`.cache`) and the committed judge caches (2,646 files) are already content-addressed: they hash the request body with its images. Judge answers move to the same format in files of their own (item 8).

## Design (proposed; for review)

**1. The request object.**
- `ModelRequest`: the role (extract, triage, compare, judge), the system text, the user text, the images (paths, with each image's SHA-256), the response schema or format, and the generation settings (output tokens, temperature, seed).
- **`hash()`:** SHA-256 of a canonical JSON of everything above but the paths.
  - Left out: the model, since it is the M of the triple, and transport (URL, streaming, timeouts, retries).
  - Images are hashed by their bytes. Fixtures already pin the PDF library's version, and replay tests skip under another, so the old reason for keying crops by recipe falls away.
- **`body(model)`:** builds today's request body, so what is sent doesn't change.
- **One builder per role** makes a `ModelRequest`. Extraction's builder takes a task (page, region, crop, text) and the context providers (item 5).

**2. The fixture holds answers only** (schema version 4):
- **The owner:** "I'm not sure I'd want to store images or query text in test fixtures in the general case... the idea with the test fixture is that everything should be deterministic enough, i.e. based on samples and responses to prior queries, to form the same reports."

| Table | Holds | Key |
|---|---|---|
| `response` | outcome (`ok`, `invalid`, `transient`), answer or error, usage, when recorded, when last used; role and region as labels, for summaries (proposed) | `(query hash, responder, sample)` |
| `meta` | schema version, PDF library version | |

- **Replay:** rebuild the query from the sample documents, hash it, and look up `(responder, hash, sample)`.
  - `ok` returns the answer. `invalid` replays the failure, so variants differ only where they change requests.
  - `transient` (timeouts, 5xx) or nothing: in record modes it is asked; in replay mode it's reported missing.
- **A changed request is a miss, never a stale answer:** its hash differs.
- **Diagnostics live in the run's store, which is git-ignored and rebuilt by replay:**
  - each query's recipe: role, document, kind, page, task, crop and overlays, code version
  - its text
  - the lever notes
  - Recipes get a table of their own there, normalised as the owner suggested for a recipes table.
  - **How a query changed** is a report comparing two runs' recipes and queries, e.g. a variant against its baseline.
- **Samples for quality checks** (the owner: "Storing a few samples for quality judgements is reasonable"): the queries dumped each round (item 6), with text and images, are kept in the round's folder. Rounds run on public slices only.
- **The spot check's "read from"** takes a claim's input from the run's store at build time, instead of from the fixture's stored prompt.
- **A determinism test:** two replays of the same runs give identical evidence and reports. That's the property the fixture exists for, and it catches ordering and timestamp leaks.
- **Prune gets a guard:** it refuses without `--force` when the last replay reported misses, or when it would remove more than half the answers. An unguarded prune once emptied the fixture.

**3. Samples:** `(query, responder, n)`.
- Replay uses sample 0.
- The A/A control asks for sample 1 in its regions, replacing `#fresh`.
- Later, repeated readings for agreement ("future lever" in the query-improvement plan) ask for samples 0..k.

**4. Settings, each classified once** (a table in `models.py`; a test fails on any unclassified field):

| Class | Examples | Rule |
|---|---|---|
| Endpoint | model (as the responder), URL, timeouts, retries, concurrency, streaming, cost caps | Never changes a query's hash |
| Request-shaping | context sizes, text-layer size, stems, rules, claims per request, output tokens, image side | Reaches the model, so the hash covers it. A test checks toggling it changes some hash, or it's dead or misfiled |
| Request-selecting | tiling, grown tiles, skipped empty tiles, figure tasks, table filter, vision | Changes which queries exist. Queries it doesn't touch keep their hashes |
| Post-processing | quote matching, merged readings, de-duplication | Never changes a hash. A test checks every hash is identical with it on and off |

- **Stores:** a changed setting no longer needs a precise reset list. Rerun the affected document: unchanged queries hit the cache, and post-processing is recomputed from cached answers.
  - The store's interpreter binding becomes a record of settings, not a guard.
  - Measure rerun time on the development slices before dropping `SETTING_REGIONS`, since rendering tiles is the main cost.

**5. Levers as diagnostics** (the owner: needed only for diagnostics; they don't affect a query's hash, and needn't be in the fixture record). The notes go into the run store's recipes (item 2):
- **Context providers,** one per lever (neighbouring text, table lead-in, stems, references, the locator, the text layer, rules). Each adds its part to the request and a note to the recipe, e.g. `stem_context: "Within: 7.3 Baseline Blade-Pitch Controller"` or `context_before: 400 characters`.
- **One owner for page coordinates.** Displayed and unrotated boxes become distinct types, and each builder takes a page context. The rotated-sheet bug came back once because it was fixed site by site.
- **Uses:**
  - dumps
  - round reports, e.g. "the variant changed 212 queries; stems gave a different Within line in 180"
  - a soft scope check: a lever's notes appear only in the kinds it declares

**6. Query dumps and checks, every round** (the owner: "Ability to easily dump, view, and validate sample queries by a high-end model or human"; "The strong model pass per round, including yourself and a few others, seems wise"):
- **`queries dump <runs> [--against <baseline runs>] --sample N`:**
  - A page like the spot check. Per document and kind, a sample of queries exactly as sent: text with the context marked, the images, and the lever notes.
  - Against a baseline, it shows only queries whose task changed hash, as a diff, plus queries only one side has.
  - Also written as JSONL for model checkers.
- **The strong-model check:** a short rubric asks, for each query, whether anything is wrong or misleading:
  - context that is junk or from elsewhere on the page
  - wrong headings or stems
  - text cut off
  - images that are empty, unreadable or cut through content
  - rules that don't apply
  - anything contradictory
  - Answers: ok, or problem tags with a note.
  - **Checkers** (chosen by Claude; the owner left the choice to me):
    - Claude in session, reading the dump
    - `google/gemini-3.1-pro`, `Qwen/Qwen3.5-397B-A17B` and `moonshotai/Kimi-K3`, the s01 panel: three different families, all with images, about $0.70 per pass over s01's batch
    - Gemini shares a family with the extractor, gemma. That matters little here: the queries are built by our code, not written by gemma.
    - **Size and cap:** 30 queries per variant (40 for the baseline), and at most $2 per round (`round.json`: `query_check_cap`).
- **When:** after recording and before judging. Judging waits until flagged problems are fixed or accepted, and the results are kept in the round's folder.
- **When a lever is built:** dump what it adds for every development document (the meta-audit's lesson 5).

**7. Evaluation checks and records** (the meta-audit's evaluation side):
- **Checks when a batch is built:**
  - hidden claims are all shared
  - swapping the sides mirrors the units
  - a text-only lever changes no visual units
  - every unit has a document family
  - each claim's reading comes from its unit's kind
- **One claim identity:** each shown claim carries its claim ID and its reading's ID. `_ident` stays for old batches.
- **Decision rules as pure functions,** with tests that simulate them under the null: A/A and permuted scores, 3–6 variants per round, and the "no worse" path, checking false-acceptance rates.
- **A typed round spec** (strict pydantic, like `Settings`), with the criteria set in advance: the round's role (development, combination, held-out), thresholds, strata, and a named gain. They're hashed when judging starts, and `decide` refuses if they change (query-improvement decision A).
- **Judgement records and a rater interface:**
  - Each record: a rater (a model judge, a person, or the quote check), a target (unit, side, claim), a question, an answer, a status and its attempts.
  - Today's verdict files are read through an adapter, with no re-judging.
  - These are what the weighted quality estimates consume. Retry policy and failure counts live in one place.
- **Golden tests for every rubric's prompt (v2–v6)** before any rubric refactor. A byte change in a judge prompt re-pays judging, which was 88% of spend.

**8. Judge answers in the same format** (the owner: "Judge requests can use the same format, though perhaps a separate .db file"):
- **Each batch folder gets its own judge fixture:** `(query hash, judge, sample)`, answers only, packed reproducibly like the replay fixture. It replaces the `.judge-cache` folders. Spot checks likewise.
- **Migration by replay:** rebuild each batch's judge prompts from `pairs.json` and its rubric, find each answer under its old cache hash, and store it under the new hash. Answers with no match are dropped.
- **Verdict files stay as they are:** rounds can still be re-decided offline without any fixture.

## Migration without paying

- **Re-key by replaying.** Only a hash of the old system prompt is stored, so old keys can't be converted directly. Instead `fixtures rekey <old> <new>` replays the recorded runs with today's code:
  1. Each request is looked up under its old key.
  2. Its rebuilt user text and image hashes are compared with those the old fixture recorded.
  3. A match is written under the new hash.
  4. A mismatch is stale and dropped (the owner: "Let go of stale answers that don't have an obvious transition via replay"). The report counts both.
- **The replay fixture** (`replay-slices.zip`, ten runs): expected to match fully, since it was recorded today with the current code.
- **The local master fixture** (`tests/fixtures/slices.sqlite`, 100 MB, git-ignored): re-keyed by replaying the current defaults and the round baselines and variants still worth replaying. What doesn't carry over is let go, along with the older local `slices-v4/v5/v6.sqlite`.
- **Judge caches:** re-keyed per batch by rebuilding their prompts (item 8).
- **If something doesn't match,** re-recording extraction costs about $4 at today's sizes.

## Milestones

1. **Settings classified,** with the four tests; the prune guard. No behaviour changes.
2. **`ModelRequest` and fixture schema 4:** answers only, with outcomes and samples; recipes and lever notes in run stores; `fixtures rekey`; both fixtures re-keyed; the determinism test; replay tests at 0 missing; the old key code, fingerprint lists and `#fresh` removed.
3. **Lever notes, `queries dump` and the strong-model check,** with its rubric and a per-round cap. First used on the next round.
4. **Context providers and one owner for page coordinates.**
   - Replay at 0 missing proves no request changed.
   - Two meta-audit items are fixed by construction: table numbering (task ids are labels now) and the locator thumbnail (its bytes are in the hash).
5. **Evaluation checks:** batch checks, one claim identity, pure decision rules with null simulations, the typed round spec with pre-set criteria.
6. **Judge fixtures per batch** (item 8), with the judge caches re-keyed; judgement records and raters; golden rubric tests; then the rubric object, if still worthwhile.

Milestones 1–3 come before the next round, which waits on the owner's surveys anyway. 4–6 can go around rounds.

## Decisions (2026-09-28)

- **Keyed by what reaches the model;** triples of model, query hash and response, with accounting for failures (the owner; record/replay decisions).
- **Levers only for diagnostics:** recorded per query if useful, never in the hash, and not needed in the fixture record except as a secondary, less reliable identifier (the owner).
- **Fixtures hold no query text or images in the general case;** storing a few samples for quality judgements is reasonable (the owner). Everything should be deterministic enough, from the samples and the responses to prior queries, to form the same reports (the owner).
- **Judge answers use the same format, in separate files** (the owner).
- **Stale answers without an obvious transition via replay are let go** (the owner).
- **Checker models left to Claude** (the owner). Chosen: Claude, Gemini 3.1 Pro, Qwen3.5-397B and Kimi-K3, with 30 queries per variant and at most $2 per round.
- **A strong-model pass on queries each round,** by Claude and a few others (the owner).

## Open questions

- **Labels on answers:** role and region on each response row, for fixture summaries. They aren't query text, but they aren't needed for replay either. Proposed yes.
- **Judge fixtures per batch or per round?** Proposed per batch, as the caches are now.
