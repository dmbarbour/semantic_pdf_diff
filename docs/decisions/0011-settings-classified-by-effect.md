# 0011. Every setting is declared once, classified by what it can affect

- **Status:** Accepted (2026-09-28)
- **Source:** [content-addressed queries plan](../plans/content-addressed-queries-2026-09-28.md): [design](../plans/content-addressed-queries-2026-09-28.md#design-proposed-for-review) item 4, [progress](../plans/content-addressed-queries-2026-09-28.md#progress) milestone 1; [architecture clean-up](../plans/architecture-cleanup-2026-10-02.md): [design](../plans/architecture-cleanup-2026-10-02.md#levers-as-mixins-on-a-platform-class), [progress](../plans/architecture-cleanup-2026-10-02.md#progress) milestones 2b, 3 and 9; [meta-audit](../reviews/meta-audit-2026-09-28.md)

## Context

Five hand-kept lists (`LEVERS`, `EXTRACTION_SETTINGS`, `SETTING_REGIONS`, `TRIAGE_SETTINGS`, `COMPARISON_SETTINGS`) decided what keys, bindings and resets covered, and they disagreed: `quote_match` was misfiled, so a reset re-paid text answers. Nothing checked that a setting did only what its listing claimed.

## Decision

- **Each setting is a field annotated with its declaration** (`levers.Declared`):
  - its class
  - the roles whose store binding it joins ([0004](0004-store-bound-to-its-interpreters.md))
  - the extraction regions a change clears
- **Four classes:**
  - **endpoint:** how requests travel, budgets and limits. Never changes a query's hash.
  - **shaping:** the content of queries (text, images, generation settings). Toggling it changes some hash.
  - **selecting:** which queries are made, and which sources are read. Queries it doesn't touch keep their hashes.
  - **post:** what is done with answers. Every query hash is identical with it on and off.
- **`tests/test_settings.py`** toggles each setting through the whole pipeline (extraction, situating, comparison) against a stub model, and checks it keeps to its class. An undeclared setting fails.
- **Bindings follow the roles declared,** whatever the class. Endpoint settings never join one, except the model.
- **The tables once kept by hand are read off the declarations:** `SETTING_CLASSES`, the role tuples, `LEVERS`, `SETTING_REGIONS`, `LEVER_MARKS`.
- **`docs/configuration.md`'s settings table is generated** (`levers.settings_table`), and a test keeps it current.
- **Endpoint settings are a plain object beside the platform** (`settings.Endpoint`): not bound, hashed or searched. Evaluator clients take only endpoint settings from the environment (the lab's `eval.clients.evaluator_settings`).

## Consequences

- Changing an endpoint setting (timeouts, retries, concurrency, rate limits, cost caps, the URL) never needs `--reset` and never re-pays answers.
- Changing a bound setting needs `--reset`; cached answers replay for every query it didn't change.
- A new setting must be declared before tests pass. A misfiled one shows up as a hash change its class forbids.
- Some settings that look like budgets shape queries: `image_tokens`, `context_tokens` and `safety_tokens`, since situating fits its text to what's left after each image's allowance.
- An exported `PDF_DIFF_*` shaping setting doesn't reach a judge, so it can't silently re-pay judging.
