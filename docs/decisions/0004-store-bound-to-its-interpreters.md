# 0004. A store is bound to its interpreters, with a selective reset

- **Status:** Accepted (2026-09-23); amended 2026-10-04 (changes that can't cost a model call, and the refusal's content)
- **Source:** [evidence store plan](../plans/sources-and-evidence-store-2026-09-23.md): [concepts](../plans/sources-and-evidence-store-2026-09-23.md#concepts) (interpreter, binding, `--reset`), [decisions](../plans/sources-and-evidence-store-2026-09-23.md#decisions-2026-09-23); [content-addressed queries: progress](../plans/content-addressed-queries-2026-09-28.md#progress), milestones 2 and 5 (cached answers kept through resets); [architecture clean-up: progress](../plans/architecture-cleanup-2026-10-02.md#progress), milestone 3 (every resolved setting bound); [code review 2026-10-01](../reviews/code-review-2026-10-01.md), item 4

## Context

Mixing models, prompts or reading settings in one store gives evidence of mixed origin, broken in unpredictable ways. But most changes affect only part of a store, and discarding everything after, say, a tile-size change would waste paid work.

## Decision

- **The store records each bound role's interpreter** (`interpreter` table, built by `provenance.interpreter`): `extract`, and `triage` (situating) when situating runs.
- **An interpreter holds:**
  - the model
  - a hash of the prompts and the prompt version
  - every setting declared for that role, resolved ([0011](0011-settings-classified-by-effect.md))
  - for extraction, the order of the levers acting on it ([0013](0013-levers-as-mixins.md))
  - library versions: this tool, PyMuPDF, pydantic
- **Left out:** endpoint settings other than the model (timeouts, retries, call limits, concurrency, rate limits, cost caps, credentials, the URL).
- **A run with a different interpreter is refused** (`store.InterpreterMismatch`). The user passes `--reset` or uses a new store; `--reset --dry-run` shows what would be cleared.
- **The refusal is friendly** (2026-10-04). The owner, choosing between keeping the guard, recording instead of guarding, and a middle way: "I lean towards 3 with a friendly refusal." It says:
  - each difference and its effect ("claims_per_request: 20 -> 25 (shapes what's asked)")
  - what going ahead clears (regions, tasks, claim sightings, saved comparisons)
  - at most how many requests would be asked again, with their text and images (`Store.rerun_estimate`, from the store's query log); unchanged queries replay free
- **A change that can't cost a model call isn't refused** (the middle way): when every difference is a setting that only post-processes answers (`quote_match`), it's applied and what it affects is recomputed from cached answers, with a note in the log. Reader changes aren't refused either ([0016](0016-content-reread-when-its-reader-changes.md)).
- **`--reset` is selective:**
  - A setting's change clears the extraction regions it declares (a tile size: the visual regions only), plus situating results and all comparisons.
  - A change not tied to one setting (model, prompts, library versions) clears all extraction.
  - A triage change clears situating results only.
  - Sources, content and cached answers are always kept.
- **Comparison settings are recorded per comparison,** not bound. Rerunning a comparison with another `top_k` needs no reset.
- **A role bound for the first time** (situating turned on later) needs no reset.

## Consequences

- **When a store refuses after a setting, prompt or PyMuPDF change:** rerun with `--reset`. Cached answers survive, keyed by query and model ([0009](0009-content-addressed-queries.md)): unchanged queries replay for free, and only changed ones are paid for.
- **A reader's change isn't a binding change:** the content it reads is read again instead, the rest of the store untouched ([0016](0016-content-reread-when-its-reader-changes.md)).
- The guard stays even though cached answers no longer need it. It decides which derived results (tasks, evidence, situating, comparisons) a change clears.
- Stores made before 2026-10-02 bound only levers changed from that day's defaults. Each asks for `--reset` once.
- What the store can't see is the user's responsibility: a server swapping weights under one model name, or an external converter's own configuration. Keep model identifiers versioned.
