# 0008. Fixtures are recorded by running the pipeline live against hosted gemma-4

- **Status:** Accepted (2026-09-25)
- **Source:** [test models plan](../plans/test-models-and-record-replay-2026-09-24.md): [idea](../plans/test-models-and-record-replay-2026-09-24.md#idea), [milestones](../plans/test-models-and-record-replay-2026-09-24.md#milestones) (reordered 2026-09-25), [decisions 2026-09-25](../plans/test-models-and-record-replay-2026-09-24.md#decisions-2026-09-25) and [2026-09-24](../plans/test-models-and-record-replay-2026-09-24.md#decisions-2026-09-24); [content-addressed queries: progress](../plans/content-addressed-queries-2026-09-28.md#progress), milestone 2 (recordings save resolved settings)

## Context

The pipeline is adaptive: refinement, re-asks, situating and comparisons depend on earlier answers, so a pass without a model sees only first-stage requests. The plan first meant to record in collection rounds (collect requests, answer them offline, replay, repeat), with an in-house gemma-4 table recorded by the owner using a self-contained kit. Then a cheap hosted gemma-4 became available.

## Decision

- **The owner bought pay-go access** to `google/gemma-4-31B-it` on DeepInfra (OpenAI-compatible; about $0.13 per million input tokens).
- **Record by running the pipeline live** with a fixture attached: one run records every adaptive round. `scripts/record_runs.py` records the slice runs in `record-new` mode; `--retry-failures` uses `replay-or-record`.
- **Collection rounds** (work lists answered offline, then imported) are only for responders that can't be called, such as Claude in a session or a local VLM. They aren't built.
- **The in-house recording kit is deferred.** Hosted gemma-4 covers realistic answers. The kit returns if the in-house deployment's answers differ enough to matter.
- **Recordings save every setting that can change a query, resolved** (`<out>/settings.json`, from `Settings.configuration()`), so a replay means the same thing after defaults move (2026-09-28).

## Consequences

- Recording is cheap: the first table, 2,906 requests on all slices, cost about $0.48.
- It's slow per request (about 13 generated tokens a second), so recording runs at high concurrency.
- `record_runs.py` resumes (recorded answers replay), stops at `--max-cost` with exit code 3, and tags spend in a ledger (`--ledger`, `--tag`).
- Only one responder is recorded so far, so replay can't yet bracket behaviour between a strong and a weak model.
- Credentials stay in the environment (`OPENAI_*`; a git-ignored `.env` for development). Fixtures hold answers only.
