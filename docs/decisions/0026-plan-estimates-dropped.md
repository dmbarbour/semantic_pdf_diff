# 0026. `--plan` is dropped until estimates can come from the reading itself

- **Status:** Accepted (2026-10-10)
- **Source:** the [code review of 2026-10-08](../reviews/code-review-2026-10-08.md), C7, and the owner's answer

## Context

`--plan` came with the first commit: it counted a PDF's image tasks without calling the model. Scheduling milestone 1 added tokens, minutes at the rate limit and a warning when `max_calls` would stop the run; situating added its requests. It shaped two early decisions: the `max_calls` default (500 to 100,000) and the size of the DC team's drawing set (9,698 image tasks). Nothing has used it since 2026-09-25.

It counted tasks with its own code, sharing only the image levers' regions, the text grouping and the situating counts with extraction. Every format and query added since was missing:

- On the controlled corpus's 204 recorded runs it predicted 760 tasks of 3,135 (24%).
- It skipped every format but PDF (1,187 tasks) and every table query (835 in the PDFs alone).
- Its tests checked its output's fields, not its counts against extraction, so drift failed nothing. Three reviews flagged it.

Meanwhile the run guards itself: `max_cost` and `max_calls` cap it, an interrupted run resumes paying only for what's missing, and the ledger records what was spent.

The owner, 2026-10-10: "Yes, drop --plan. I think there is merit in a `--dry-run`, but it's difficult to judge details for interactive queries (where the model is permitted to ask questions, specify boxes, etc..)"

## Decision

- **`--plan` is removed:** the flag, `cli.plan`, its test and its documentation. Tests that ran a command through it now test what they meant to (settings' precedence, a settings file that isn't an object, source names, a blank page's tiles) directly.
- **No hand-written estimate replaces it.** An estimate that copies extraction's enumeration drifts with every reader, lever and query.
- **A dry run is a tentative plan** (the plans index, *Dry runs*): estimates from extraction's own code, the open question being the queries whose follow-ups depend on the model's answers.

## Consequences

- No pre-run estimate of calls, tokens or time; `max_cost`, `max_calls` and resuming bound a run instead.
- The progress display (the trials' findings 3 and 4) can't take its totals from `--plan`; its totals come from the run, as each level opens.
- `--dry-run` today means "with `--reset`, report what would be cleared" (and the same for `gc`). A dry run of the reading would extend that flag or need another name.
