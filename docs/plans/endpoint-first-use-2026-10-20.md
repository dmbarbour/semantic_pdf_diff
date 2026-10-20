# An endpoint checked and calibrated on first use

- **Status:** Active (2026-10-20)
- **The owner (2026-10-20):** "Yes, we should always auto-test the model endpoint if it isn't tested in memory. Without verbose mode, we can get 13k bad requests without noticing. (guess how I know!) Also, remove the "gemma-4" default model, just error if one isn't configured." Then: "It isn't clear that we run any calibration on first use of an endpoint. I think we should."
- **On the models listing (2026-10-20):** "IIRC there is also a 'models' endpoint for the OpenAI API. We could let people know what's available." Then: "Also provide that list on request."

## Why

- **A run can fail every request quietly:**
  - A request that fails is retried, recorded as failed and counted in the coverage; the run goes on to the next request.
  - Without `-v`, the only signs are a failed count in the progress line and exit 2 at the end. Exit 2 is also what an ordinary run with one unread table gets.
  - A reranker asked where none is served failed every request, until warnings were added (2026-10-20). A wrong model name, an expired key or a server down still fails every chat request the same way.
- **`config test` checks an endpoint only when it's asked.** Nothing runs it before a first run.
- **The default model is "gemma-4",** a name no provider serves. A user who sets no model gets HTTP errors on every request.
- **Nothing is calibrated.** The configuration guide says to calibrate `image_tokens` against the backend by hand, and `context_tokens` defaults to 32,768 whatever the model's window is.
- **The endpoint lists its models,** with more than names at some providers. DeepInfra's `/models` gives each model's context window, price per million tokens and tags (`vision`, `chat`, `embeddings`); vLLM gives `max_model_len`. `config models` shows only the names.

## Milestones

1. **Requests failing in a row stop the run** (done 2026-10-20; a bug: the failures went unnoticed):
   - When `stop_after_failures` requests in a row fail at one URL (default 25; any failure, after its retries), the run stops sending.
   - The requests not yet sent aren't attempted and aren't recorded as failed: the next run asks them again.
   - The run pauses as the cost cap pauses it: what was read is kept and the report written. The pause names the URL, the error and `config test`, and the run exits 5.
   - **Tested** on a stub refusing every request (HTTP 404): of 80 pages, 25 to 39 requests are sent (those in flight when the 25th fails are sent too), the run exits 5 saying why, and run again against a working endpoint it reads every page.
2. **No default model** (done 2026-10-20): `model` is unset until the user sets it.
   - A command that would ask the model without one stops before anything is changed.
   - The error names `config set --user model NAME` and lists the endpoint's vision models (from `/models`), or all its models where none says what it reads.
   - It lists 15, by name, then how many more and `config models vision`: on DeepInfra, 53 of its 177 models read images. A replay (`--fixture` in `replay` mode) needs none; `config test` fails a `model` check.
   - The tests name a model as a user names one: `gemma-4` in their own user settings (tests/stubs.py).
3. **`config models` says what each model is** (done 2026-10-20), where the endpoint says: its context window, its price, and whether it reads images or embeds.
   - `config models WORDS` filters the list by name or tag (`config models vision`); `--json` gives every field for tools.
   - Read from DeepInfra's `metadata` (context, price a million tokens, tags), vLLM's `max_model_len`, and OpenRouter's fields (price a token, images among the inputs).
   - On DeepInfra: 177 models, 53 tagged as reading images, 25 as embedding. Its listing doesn't include its rerankers.
4. **Checked on first use** (done 2026-10-20): before a run's first request, each model the settings name is checked, as `config test` checks it, unless it's remembered as passing.
   - **Remembered** in `endpoints.json`, beside the answers cache's `answers.sqlite`: a project with a cache of its own keeps its own record, and nothing about its endpoint is written to the home cache.
   - **Each check is remembered by what it depends on:** the chat check by the endpoint and model; the image check by those and `image_side`; the reranker's and the embedding model's by their URL, model and API.
   - **A failed check stops the run** before anything is asked (exit 5), its lines printed as `config test` prints them.
   - **A pass is forgotten** when a check of it fails, or when its URL trips milestone 1's stop.
   - **When nothing is checked:** runs replaying a fixture (`--fixture`, tests and the lab) are never checked; a run whose answers all come from the cache sends nothing, so it isn't either.
   - Checks cost about $0.0002 on DeepInfra. They're said in the run's log, not counted under its cost cap.
   - `config test` records its results too, in the record beside the cache the store uses.
   - **Tested** with a stub endpoint: a first run checks (a sum, the card, the card's prompt alone) and the next doesn't; a wrong sum stops the run with nothing asked; a run whose requests fail in a row empties the record. The tests' stand-in skips the check everywhere else (tests/stubs.py).
5. **Calibrated on first use** (done 2026-10-20), from what the checks measure:
   - **`context_tokens`:** the model's context window, where the endpoint's listing gives it.
   - **`image_tokens`:** an image's tokens at `image_side`. The image check sends its card on a square canvas of that size, and the image's tokens are the prompt tokens reported, less the same prompt's without the image. Used with a margin of 10%.
   - **Precedence:** calibrated values sit between the defaults and the user's settings. A value the user or the store sets wins, but a set value the measurement says is unsafe is warned of: an `image_tokens` below the measured, or a `context_tokens` above the window.
   - `config show` marks calibrated values `(measured)`; the record says when.
   - A dry run uses what was measured, without checking.
   - **On DeepInfra** (2026-10-20, $0.0001 for the checks): gemma-4-31B's window is listed as 262,144 tokens; an image 1,000 px square is 258 tokens, so `image_tokens` would be 284. The owner's 262,144 and 300 are both safe, so neither is warned of.
