# Endpoint setup: choosing a model, trying it, and seeing what's remembered

- **Status:** Planned (2026-10-28). [Design question](#design-questions) 1 answered the same day (the environment and the user's settings); 2 and 3 open.
- **The owner, 2026-10-28, from trials:** "better configuration setup, support for browsing available models at the endpoint and validating the endpoint, running a few checks if not calibrated. This could be somewhat interactive, or just supported through config ops."
- **On the key sent to other models' URLs, the same day** (the deferred decision *A key for a model served elsewhere*): "I'll look into the `OPENAI_API_KEY` thing later. For now, it's the same, but we might want to modularize things and simplify user overrides by a user."
- **The owner, answering design question 1 (2026-10-28):** "Endpoint URL in environment and user settings is sufficient. I'd hate to complicate things too much on the user's end."
- **Builds on:** [an endpoint checked and calibrated on first use](endpoint-first-use-2026-10-20.md) ([0034](../decisions/0034-endpoint-checked-and-calibrated-on-first-use.md)), settings in layers ([0032](../decisions/0032-settings-in-layers-and-one-answers-cache.md)).

## What exists (built 2026-10-20)

- **`config models [WORDS] [--json]`:** the endpoint's models, each with its context window, price and tags where the host gives them. `config models vision` lists those reading images (DeepInfra: 53 of 177).
- **`config test`:** asks the endpoint, never the cache, and exits 5 if a check fails. Its checks:
  - the models listing, with the model among them
  - a JSON answer
  - an image read back exactly, and an image's tokens measured
  - the reranker and the embedding model, where set
- **On first use:** before a run's first request, each model is checked unless `endpoints.json` (beside the answers cache) remembers it passing.
  - `context_tokens` and `image_tokens` are calibrated there, used where no layer sets them.
  - A failed check stops the run before anything is asked.
- **No default model:** a run without one stops, listing up to 15 of the endpoint's vision models.
- **`config show`, `find`, `help`, `set`, `unset`, `export`, `import`:** every setting explained. A measured value is marked "(measured)".

## What's missing

- **No guided path.** A first user has to know four steps:
  1. export `OPENAI_BASE_URL` and `OPENAI_API_KEY`
  2. run `config models vision`
  3. run `config set --user model NAME`
  4. run `config test`
- **Candidates can't be tried.** `config test` takes no `--model` or `--base-url`, so a model is tried only after it's set.
- **`config set model` doesn't check the name** against the endpoint's listing, nor whether it reads images.
- **Checks can't be run selectively.** `config test` runs every check, though `checkup.run` can run some of them.
- **Remembered checks can't be seen.** Nothing says which checks passed, when, what was measured, or where `endpoints.json` is.
- **Remembered checks can't be forgotten.** `checkup.forget` exists but no command reaches it; deleting the file is the only way.
- **The first-run error names only the model.** When the endpoint can't be reached it says so, but not `OPENAI_BASE_URL`, the key, or `config test`.
- **The key check never fails.** A wrong key shows only as an HTTP error in the listing's or the answer's line.
- **The lab's probes aren't the product's:**
  - The eye test's quick suite, the page test and the vision profiles need the repository.
  - The product borrows one eye-test card, and gemma-4's legible size as a constant (`tilechoice.LEGIBLE_PX`).
- **A bug, found writing this plan:** `config set base_url URL` in a store is accepted, and the store's URL then beats `$OPENAI_BASE_URL`.
  - The setting's help says the URL is "Set by $OPENAI_BASE_URL (or --base-url), not kept in a store: the endpoint is the user's."
  - A user's `base_url` loses to the variable, so the two layers disagree.
  - Checked 2026-10-28: a scratch store set to `https://store.example/v1`, with the variable set to another URL, ran with the store's.

## Milestones

### 1. The bug, and the first-run error (bugs first, [0027](../decisions/0027-behaviour-changes-apart-from-refactors.md))

- **`base_url` kept by the environment and the user's settings only** ([design question 1](#design-questions), answered), as its help says:
  - `config set base_url` and `config import` refuse it for a store.
  - A store that holds one is read without it, with a warning naming the store.
  - The user's URL is used where `$OPENAI_BASE_URL` is unset; `--base-url` beats both.
- **The first-run error** says what to set when the endpoint can't be reached (`OPENAI_BASE_URL`, `OPENAI_API_KEY`) and names `config test`.
- **The key check fails** when the endpoint answers 401 or 403, saying the key was refused.

### 2. Trying, seeing and forgetting checks

- **`config test --model NAME`** (and `--base-url`) tries a candidate without setting it; its results are remembered like any check.
- **`config test --only` check names,** and `--new` for only what isn't remembered.
- **`config checks`** lists what `endpoints.json` remembers: each check, its endpoint and model, when it passed, and what it measured. The file's path is shown too.
- **`config checks --forget [MODEL]`** forgets them, so the next run checks and calibrates again.

### 3. Choosing a model

- **`config set model NAME` checks the name** against the endpoint's listing where it can be asked.
  - It warns, without refusing, when the name isn't listed or isn't tagged as reading images.
  - It offers `config test --model NAME`.
- **`config models` marks the models already checked,** with what was measured.

### 4. A guided setup

- **`config setup` walks the steps** in a terminal:
  - the endpoint, and whether a key is set
  - the vision models, narrowed by words typed
  - the candidate tried with `config test`
  - the choice written to the user's settings
- **Every step has a command of its own** (milestones 2 and 3), so a script or a person without a terminal reaches the same state.
- **Whether to build it:** [design question 2](#design-questions).

### 5. A few probes beyond the checks

- **`config test --probes`:** a short suite run in the product, costing about a cent:
  - the eye test's quick cards: random codes at known sizes, so a model without vision scores about 0
  - the smallest legible text measured, in place of gemma-4's constant (`tilechoice.LEGIBLE_PX`)
  - a controlled document's page read against its key
- **Remembered like the checks,** shown by `config checks`.
- **Then:** the vision profile, recommending a model per task ([*Model discovery and per-task selection*](README.md#tentative), [*Vision profiles and adaptive slicing*](README.md#tentative)), and keeping only the models a user's globs allow.

### Later: endpoints as named parts

- **The owner's "modularize things and simplify user overrides by a user":** named endpoints, each with:
  - its URL
  - the name of the variable holding its key
  - the models it serves by role: chat, reranker, embedding
- **A role names its endpoint,** and a user overrides one part without restating the rest.
- **This answers the deferred key question** when the owner takes it up. Until then, every URL is sent `OPENAI_API_KEY`.

## Design questions

1. **Where the endpoint's URL lives:** answered 2026-10-28 (quoted at the top): the environment and the user's settings, never a store ([milestone 1](#1-the-bug-and-the-first-run-error-bugs-first-0027)).
2. **Interactive or config ops only:** you said either would do.
   - **I'd build milestones 2 and 3 first** (commands only), then `config setup` as a thin walk through them, if those still leave the first run awkward.
3. **The probes' cost and when they run:** only on `config test --probes`, or also on a model's first use?
   - **I'd run them on request only.** The first-use checks stay what they are: cheap, and needed before anything is asked.
