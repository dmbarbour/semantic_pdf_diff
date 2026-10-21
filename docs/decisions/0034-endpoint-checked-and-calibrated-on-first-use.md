# 0034. An endpoint is checked and calibrated on first use, and no model is assumed

- **Status:** Accepted (2026-10-21)
- **Source:** [an endpoint checked and calibrated on first use](../plans/endpoint-first-use-2026-10-20.md), milestones 1 to 5

## Context

A request that failed was retried, recorded as failed and counted in the coverage, and the run went on to the next. Without `-v` the only signs were a failed count in the progress line and exit 2, which an ordinary run with one unread table also gets. A reranker asked where none was served failed every request, and a wrong model name, an expired key or a server down still could.

- `config test` checked an endpoint only when asked.
- The default model was "gemma-4", a name no provider serves.
- Nothing was calibrated: the configuration guide said to set `image_tokens` against the backend by hand, and `context_tokens` was 32,768 whatever the model's window ([0012](0012-temperature-zero-and-model-neutral-defaults.md)).
- An endpoint's `/models` gives more than names at some hosts: DeepInfra's each model's context window, price and tags; vLLM's `max_model_len`. `config models` showed only the names.

The owner (2026-10-20): "Yes, we should always auto-test the model endpoint if it isn't tested in memory. Without verbose mode, we can get 13k bad requests without noticing. (guess how I know!) Also, remove the "gemma-4" default model, just error if one isn't configured." Then: "It isn't clear that we run any calibration on first use of an endpoint. I think we should." On the listing: "IIRC there is also a 'models' endpoint for the OpenAI API. We could let people know what's available." Then: "Also provide that list on request."

## Decision

- **No default model:** `model` is unset until the user sets it.
  - A command that would ask the model without one stops before anything changes, naming `config set --user model NAME`.
  - It lists the endpoint's models that read images (all its models where none says what it reads): 15 by name, then how many more and `config models vision`.
  - A replay needs none; `config test` fails a `model` check.
- **Requests failing in a row stop sending** (`stop_after_failures`, default 25, an endpoint setting): when that many in a row fail at one URL, each after its retries.
  - Sending stops as the cost cap stops it: the run is paused, what was read is kept and the report written ([0030](0030-only-answers-decide-what-a-run-writes.md)). The pause names the URL, the error and `config test`; the run exits 5.
  - Requests not yet sent aren't attempted and aren't recorded as failed, so the next run asks them.
  - The record of checks passed is forgotten for the run's models, so the next run checks again.
- **Each model checked before a run's first request,** as `config test` checks it, unless remembered as passing:
  - **The record** is `endpoints.json` beside the answers cache's `answers.sqlite`, owner-only, its URLs without credentials. A project with a cache of its own keeps its own record; nothing about its endpoint reaches the home cache.
  - **Each check is remembered by what it depends on:** the chat check by the endpoint and model; the image check by those and `image_side`; the reranker's and the embedding model's by their URL, model and API.
  - **A failed check stops the run** before anything is asked, its lines printed as `config test` prints them, exit 5, and its pass forgotten.
  - `config test` records its results in the same record (the cache the store uses).
  - A run replaying a fixture (`--fixture`: the tests, the lab) is never checked.
  - Checks are said in the run's log, not counted under its cost cap.
- **Calibrated from what the checks measure:**
  - `context_tokens`: the model's context window, where the listing gives it (DeepInfra's metadata, vLLM's `max_model_len`, OpenRouter's `context_length`).
  - `image_tokens`: the image check's card on a square canvas `image_side` pixels a side; its tokens are the prompt tokens reported, less the same prompt's without the image, with a tenth added (`checkup.MARGIN`, 1.1).
  - **Used only where no layer sets the setting:** a measured layer between the defaults and the user's settings ([0032](0032-settings-in-layers-and-one-answers-cache.md), amended 2026-10-21).
  - **A set value the measure says is unsafe is kept, and warned of:** a `context_tokens` above the window, an `image_tokens` below the measured. The warning names the `config unset` that uses the measure.
  - A measure that doesn't fit the other settings is dropped, with a warning, and the defaults kept.
  - `config show` marks measured values `(measured)`; a dry run uses what was measured, without checking.
- **`config models [WORDS] [--json]` says what each model is,** where the endpoint says: its context window, its price a million tokens in and out, and its tags (reading images, embedding). Words filter by name or tag; the models the settings name are marked; `--json` gives every field.

## Consequences

- A wrong model name, key or endpoint stops a run at its first check, or after 25 failures in a row, instead of failing every request.
- **Tested on a stub refusing every request** (HTTP 404): of 80 pages, 25 to 39 requests were sent (those in flight when the 25th failed among them), the run exited 5 saying why, and run again against a working endpoint it read every page.
- **On DeepInfra** (2026-10-20):
  - 177 models listed, 53 tagged as reading images, 25 as embedding; its rerankers aren't listed.
  - Checks cost about $0.0002; gemma-4-31B's cost $0.0001.
  - gemma-4-31B's window is listed as 262,144 tokens; an image 1,000 px square was 258 tokens, so `image_tokens` would be 284. The owner's settings, 262,144 and 300, are both safe, so neither is warned of.
- Measured values are part of the interpreter a store is bound to, as set ones are ([0004](0004-store-bound-to-its-interpreters.md)): a measure that changes redoes what it shapes.
- The check measures a square image, the largest sent. A backend counting a long image by more than its area needs `image_tokens` set by hand (the configuration guide).
- The tests name a model as a user does, `gemma-4` in their own user settings, and their stand-in skips the first-use check everywhere but its own tests (tests/stubs.py, tests/test_first_use.py).
