# 0012. Every request at temperature 0, with model-neutral defaults

- **Status:** Accepted (2026-10-02); amended 2026-10-21 (the context window and an image's tokens measured on first use; no default model)
- **Amended 2026-10-21** ([endpoint first use](../plans/endpoint-first-use-2026-10-20.md), milestones 2 and 5; [decision 0034](0034-endpoint-checked-and-calibrated-on-first-use.md)):
  - `context_tokens` and `image_tokens` are no longer calibrated by hand only. Where no layer sets them, a run uses what its first-use checks measured: the model's context window as the endpoint lists it, and an image's tokens at `image_side` with a tenth added. The defaults below (32,768 and 1,200) stay where nothing was measured; the other budgets are still set by hand.
  - There is no default model. The owner (2026-10-20): "remove the "gemma-4" default model, just error if one isn't configured."
  - The last consequence below, a user calibrating `image_tokens` by hand, now applies where the endpoint gives no measure, or counts a long image by more than its area.
- **Source:** [code review 2026-10-01: decisions](../plans/README.md#retired) items 1 and 5, and findings 1, 2 and 12; [architecture clean-up: decisions](../plans/README.md#retired) (commit `7ccccf1`)

## Context

`temperature` was a setting (default 0, since `v0.2.0`). The code review found that an exported `PDF_DIFF_TEMPERATURE` changed every judge query, so all verdicts would have been paid for again. It also found that the shipped defaults, after the measured champion was promoted, didn't fit their own context budget: with plain defaults, 172 of 178 comparisons were refused before being sent.

## Decision

- **The owner (2026-10-02):** "we don't really need `PDF_DIFF_TEMPERATURE` - just fixing temp at 0 for all the things is fine."
- **`llm.TEMPERATURE = 0.0`** for every request of every role, judges included. It isn't a setting.
  - It's still sent as a float, as before, so request bytes and query hashes didn't change.
- **The owner (2026-10-02):** "model-neutral, but example settings could essentially be gemma-4."
- **Defaults target a 32,768-token context,** with a 1,200-token bound per image.
- **`config.example.json` holds gemma-4's measured profile** on DeepInfra: 262,144 context tokens, 300 per image, 20 claims with 4,000 output tokens.
- **A test runs a plain comparison under the shipped defaults** and requires no budget refusals.

## Consequences

- Answers are as repeatable as the server allows. Servers and weights still drift, so recordings are dated snapshots.
- A truncated answer isn't retried: at temperature 0 it would stop at the same place.
- `seed` remains a setting, sent when set.
- Stores bound before the change asked for `--reset` once; answers replayed.
- A user with another model starts from the neutral defaults and calibrates `image_tokens` and the other budgets to their backend (`docs/configuration.md`, context budget).
