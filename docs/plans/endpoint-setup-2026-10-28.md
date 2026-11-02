# Endpoint setup: choosing a model, trying it, and seeing what's remembered

- **Status:** Planned (2026-10-28); [milestone 1](#1-the-bug-and-the-first-run-error-bugs-first-0027) done the same day, [2](#2-trying-seeing-and-forgetting-checks) and [3](#3-choosing-a-model) 2026-11-01 (the owner, on the review of open items: "Please go ahead."), [4](#4-guidance-before-each-run-in-place-of-a-guided-setup) and [5](#5-failing-fast-a-ping-each-run-and-probes-on-first-use)'s ping and acuity 2026-11-02 (one eye chart tried first and not built; a card a size built: the owner, "Go ahead with the per-size probe cards."). [Design questions](#design-questions) 1 to 3 answered; a controlled page as a probe left.
- **The owner, 2026-10-28, from trials:** "better configuration setup, support for browsing available models at the endpoint and validating the endpoint, running a few checks if not calibrated. This could be somewhat interactive, or just supported through config ops."
- **On the key sent to other models' URLs, the same day** (the deferred decision *A key for a model served elsewhere*): "I'll look into the `OPENAI_API_KEY` thing later. For now, it's the same, but we might want to modularize things and simplify user overrides by a user."
- **The owner, answering design question 1 (2026-10-28):** "Endpoint URL in environment and user settings is sufficient. I'd hate to complicate things too much on the user's end."
- **Builds on:** [an endpoint checked and calibrated on first use](endpoint-first-use-2026-10-20.md) ([0034](../decisions/0034-endpoint-checked-and-calibrated-on-first-use.md)), settings in layers ([0032](../decisions/0032-settings-in-layers-and-one-answers-cache.md)).

- **The owner, 2026-11-01, on milestones 2 and 3:** "When trying, seeing, and forgetting model checks, how do we distinguish checking a rerank or embedding model? Or can you list mode and other relevant stats (context size, etc.) upon for `config models`?" Both built the same day ([milestone 2](#2-trying-seeing-and-forgetting-checks), [3](#3-choosing-a-model)).

- **The owner, 2026-11-02, answering design questions 2 and 3:**
  - "Q2. Interactive mode would be more convenient for someone new to the tool, but I'm not sure it's what we need. More important is guidance: always do a quick check on settings before starting, always let users know if they've missed an important one. Perhaps we should distinguish 'no model' from 'unconfigured' for things like embedding and reranking, so users don't default to missing out on a feature they didn't know needed to be configured to use it."
  - "Q3. Always test a model that hasn't been tested. If there are calibrations, run those up front. Even if the endpoints are tested in cache, do a lightweight ping to ensure the endpoints are up. This tool takes many hours to run, so it's something that is left to run overnight. Better to fail fast up front even if it costs a little. The engineer's time is measured in tens of dollars per hour. The endpoint is tenths of pennies for a liveness check, or perhaps less."

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
- **Done 2026-10-28** (`3e4dacd`):
  - **Every command takes the URL in one order:** `--base-url` (or a `--config` file) for the run, then `$OPENAI_BASE_URL`, then the user's `base_url`.
    - Found while fixing it: a run merged the user's settings over the variable (`cli.compare_command`), so the user's URL beat `$OPENAI_BASE_URL` in runs but not in `config test`.
  - **A store keeps none:**
    - `config set` and `config import` refuse it (`store.USERS_ONLY`).
    - One kept before is read without it, with a warning naming `config unset base_url`.
  - **`config show` and `config help base_url`** mark the variable's URL "(environment)".
  - **The key check fails on 401 or 403.** A listing refused that way stays a failure, where it had read as "lists no models".
  - **The first-use checks, `config test` and the no-model error** say which variable names the endpoint when it can't be reached, and which holds the key when it's refused.

### 2. Trying, seeing and forgetting checks

- **`config test --model NAME`** (and `--base-url`) tries a candidate without setting it; its results are remembered like any check.
- **`config test --only` check names,** and `--new` for only what isn't remembered.
- **`config checks`** lists what `endpoints.json` remembers: each check, its endpoint and model, when it passed, and what it measured. The file's path is shown too.
- **`config checks --forget [MODEL]`** forgets them, so the next run checks and calibrates again.
- **Done 2026-11-01:**
  - **`config test --model NAME`** checks a candidate as the chat model: the endpoint's listing, the JSON answer and the card, not the reranker's or the embedding model's checks unless `--only` names them. `--base-url URL` checks at another endpoint for this command. The results are remembered under that model and URL, as any check's.
  - **`--only json,image,reranker,embedding`**, comma-separated or repeated; a name it doesn't know is refused, naming the checks. **`--new`** runs those of the checks asked for that aren't remembered passing, and asks nothing when every one is.
  - **`config checks`** prints the record's path, then each model at each endpoint, marked with the settings naming it where its checks are the ones they call for; each check, when it passed (UTC) and what it measured (the context the endpoint lists; an image's tokens at its `image_side`).
  - **`config checks --forget`** forgets every check; `--forget MODEL` a model's at any endpoint, saying how many.
  - **Tried at DeepInfra** (a scratch cache; $0.0002): `--model google/gemma-4-26B-A4B-it` passed its three checks (258 tokens an image) without changing the model set; `--new` then asked nothing; `--forget` of it left the 31B's.
  - **A reranker or an embedding model tried as one** (2026-11-01, the owner's question above): `--model` had tried a candidate as the chat model only, and `--only reranker` checked the reranker set, not a candidate.
    - **`config test --rerank NAME`, `--embed NAME`** (the run's `--rerank` flag's name): a candidate tried in its role, its role's check alone unless `--only` says; with `--model` too, each in its own. The first line names each model and its role: `checking bge-reranker (reranker), bge-m3 (embedding model) at URL`.
    - **Remembered under its role:** `config checks` already listed each check by its name (`reranker`, `embedding`) and the URL it was asked at (`.../v1/rerank`, `.../v1/embeddings`), and `config models` marks it `checked: reranker`.
    - **A chat candidate the endpoint lists as serving otherwise** says so on the listing's line, offering the flag that tries it as one: `listed as an embedding model, not a chat model (`config test --embed NAME` tries it as one)`. Not failed: its checks say whether it chats all the same.
    - **Tried through a LiteLLM proxy** (a local one, as the owner's, in front of DeepInfra; a scratch cache; under $0.0001): `--rerank dev/rerank-tagged --embed Qwen/Qwen3-Embedding-8B` passed both (4,096 dimensions); `--model Qwen/Qwen3-Embedding-8B --only json` failed its JSON check (the proxy: "does not exist"), its listing's line saying it's an embedding model.

### 3. Choosing a model

- **`config set model NAME` checks the name** against the endpoint's listing where it can be asked.
  - It warns, without refusing, when the name isn't listed or isn't tagged as reading images.
  - It offers `config test --model NAME`.
- **`config models` marks the models already checked,** with what was measured.
- **Done 2026-11-01:**
  - **`config set model NAME`** (a store's or the user's, and `config import`) asks the endpoint's listing, at most 10 s, once the model is set. It warns where the name isn't listed, naming up to three like it (`google/gemma-4-31b-it` offers `google/gemma-4-31B-it` at DeepInfra), and where it's listed untagged as reading images while others are tagged (`meta-llama/Llama-3.3-70B-Instruct-Turbo`). Each warning offers `config test --model NAME`; a name listed and tagged says so. Where the listing can't be had, it says the name wasn't checked, and why.
  - **`config models`** marks each model whose checks are remembered passing at its endpoint: `checked: json, image (an image 258 tokens)`. `--json` gives each model's `checked`, with when and what was measured.
  - **Modes and stats in `config models`** (2026-11-01, the owner's question above):
    - **A mode column:** what the model serves, in LiteLLM's words (`chat`, `embedding`, `rerank`, `image_generation`, `audio_speech`...), from LiteLLM's `mode` or DeepInfra's tags (chat, embed, image-gen, tts...); the tag saying it isn't repeated among the others. `config models embedding` and `config models rerank` find them, the mode searched with the name and tags.
    - **The context column** adds the most a model answers with where it's less than its context (OpenRouter's `max_completion_tokens`, LiteLLM's `max_output_tokens`; DeepInfra's equals its context for all 173). `--json` gives `mode` and `output`.
    - **A LiteLLM proxy's listing** (`/v1/models`) gives names alone, so where no model listed says anything more, its `/model/info` is asked too (not tried with a key of limited rights: the local proxy has no keys): each model group's mode, `max_input_tokens`, `max_output_tokens`, costs a token and `supports_vision`, from the proxy's configuration or LiteLLM's price map, the first deployment saying each. A price of 0 is taken as unknown (the map's default for a model it lacks). Another server, or a key refused it, leaves the names alone.
    - **Seen on a local proxy** (LiteLLM 1.102.4): six model groups, those whose configuration sets `mode` listed `chat`, `embedding` or `rerank`; `deepinfra/google/gemma-4-26B-A4B-it` given context, prices and vision by the price map; a group neither configured nor in the map (`openai/google/gemma-4-31B-it`) says nothing but its name. So what the owner's proxy shows depends on its configuration.
    - **`config set rerank_model` and `embed_model`** are checked as `model` is: listed, and listed in their mode (`warning: the endpoint lists google/gemma-4-31B-it as a chat model, not an embedding model (embed_model)`). One served apart (`rerank_url`, `embed_url`, DeepInfra's rerank API, which its `/models` doesn't list) says it isn't checked.

### 4. Guidance before each run, in place of a guided setup

- **Planned as `config setup`,** walking the steps in a terminal: the endpoint and key, the vision models narrowed by words typed, the candidate tried, the choice written to the user's settings.
- **Not built:** [design question 2](#design-questions)'s answer puts guidance first ("I'm not sure it's what we need. More important is guidance"). Every step has a command of its own (milestones 2 and 3).
- **Done 2026-11-02:**
  - **A run's settings checked before it starts** (`checkup.guidance`; compare and analyze, a dry run too; not a fixture's replay): one line naming the models it asks and where, then two for each feature off for want of a model no layer names:
    - `Models: google/gemma-4-31B-it at https://api.deepinfra.com/v1/openai; no reranker (none chosen); no embedding model (not configured)`
    - `Search by meaning is off: no embed_model is configured. An embedding model finds the claims most like a claim or a phrase (near:ID, meaning:"...").`
    - `` `semantic-pdf-diff config set --user embed_model NAME` names one (`config models embedding` lists the endpoint's), `none` goes without and stops this.``
    - Logged as progress is: `-q` quiets them. Each line fits 160 columns, so a terminal doesn't wrap it.
    - The reranker is named in proposals mode alone, where it's asked.
  - **"none" kept apart from unset** for `rerank_model` and `embed_model` (`configuration.OPTIONAL_MODELS`, `levers.declined`):
    - `config set [--user] rerank_model none` keeps an explicit none in the layer (JSON `null`), where `none` had unset it; `config unset` leaves it not configured. `config export` writes it `"none"`, which `config import` reads back as none; `null` still unsets.
    - The setting's value is none either way, so nothing is redone or checked. A run tells the two apart by whether a layer gives it (`model_fields_set`): a `--config` file's `"none"`, a flag's (`--rerank none`), the user's or a store's.
    - `config show` says `not set` for one no layer gives, `none (user)` for one gone without; `config test`'s reranker and embedding lines say `not configured, so reranking is off: ...` or `none: rerank_model is none, so reranking is off`.
  - **Other settings looked at, and left out:** the endpoint and the key are checked on first use already, and a run without a model stops; the context and an image's tokens are measured; nothing else turns a feature off for want of a value.
  - **Seen live** (DeepInfra, a scratch cache and stores; $0.0002 with the runs): an analysis named the models and warned of search by meaning; a comparison with `--rerank none` said `no reranker (none chosen)`.

### 5. Failing fast: a ping each run, and probes on first use

- **Planned as `config test --probes`,** a short suite run on request, costing about a cent:
  - the eye test's quick cards: random codes at known sizes, so a model without vision scores about 0
  - the smallest legible text measured, in place of gemma-4's constant (`tilechoice.LEGIBLE_PX`)
  - a controlled document's page read against its key
- **Run on a model's first use too,** up front, by [design question 3](#design-questions)'s answer ("Always test a model that hasn't been tested. If there are calibrations, run those up front."). Remembered like the checks, shown by `config checks`.
- **The ping, done 2026-11-02** (the answer's "Even if the endpoints are tested in cache, do a lightweight ping to ensure the endpoints are up"):
  - **Each run asks every model a small request before anything else,** remembered or not (`checkup.PING`): the chat model's JSON check (a sum, about 95 tokens), the reranker's and the embedding model's checks (two short documents, three sentences). The image check, which measures, runs on first use alone.
  - **Passing, it's one line:** `The endpoint answers: json in 4.1 s ($0.00002; asked each run, the first-use checks remembered in .../endpoints.json)`.
  - **Failing, the run stops at once** with the check's lines, exit 5, as a first-use check failing does, and every check of the run's models is forgotten, so the next run checks and calibrates again.
  - **Tested on a stub refusing every request:** one request sent (the ping's sum), the run stopped before scanning, nothing remembered. On a stub answering the ping and refusing the run's requests, the run stops after 25 in a row, as before.
  - **Already up front, unchanged:** an untested model is checked on first use in every role (chat, reranker, embedding model), and the context window and an image's tokens are calibrated there. No other calibration runs in the product: the tiling calibrations (`scripts/calibration.py`, `labelling.py`, `asking.py`) are the lab's, for levers off by default (`tile_choice model`, `region_labels model`, `another_tiling asked`).
- **The probes, a first one tried 2026-11-02 and not built: acuity, the smallest capitals a model reads** (Claude's design):
  - **The idea:** an eye chart on a square `image_side` pixels a side (as large as an image is sent), lines of five random codes (`HXR-4027`) at several capitals' heights; a height is read where 90% of its codes are found in the answer (the eye tests' pass mark), and the measure is the smallest height from which every larger one is read. On first use with the image check, remembered and shown; said against what tiling assumes (`tilechoice.LEGIBLE_PX`, 7 px); not used for tiling, which is the lever *Vision profiles and adaptive slicing* plans.
  - **Tried on gemma-4 at DeepInfra, one chart a request** (four charts each; $0.0042):

| Chart | Measured (px, capitals) |
|---|---|
| 14 lines: 2 a size at 5, 6, 7, 8, 10, 12, 14 px, smallest first | 8, 8, 10, 8 |
| The same, shuffled | 7, 7, 8, 7 (the eye tests: 7.0 at 1024 px) |
| 24 lines: 3 a size, 16 px added, shuffled | 10, none, 10, none |

  - **So one crowded chart isn't a probe:** with 24 lines, gemma-4 missed some 16 px lines too, and two charts of four measured nothing, which would have stopped the run. A long transcription measures attention as much as sight.
  - **Next, built below:** a card a size, five lines each, as the lab's eye test draws them (`lab/src/semantic_pdf_diff_lab/bench/eyetest.py`, family `read`), at 5 to 16 px: eight requests, about $0.002 and a minute on first use, sent together. The lab's cards gave gemma-4 7.0 px at 1024 px over two seeds, on a monotone fit. It would warn where a model reads coarser than tiling assumes, and stop a run only where it reads no size at all.
- **Acuity, a card a size, done 2026-11-02** (the owner: "Go ahead with the per-size probe cards."; `acuity.py`, the check `acuity`):
  - **The cards:** eight, one for each capitals' height of 5, 6, 7, 8, 10, 12, 14 and 16 px, each a square `image_side` pixels a side (as large as an image is sent) holding five lines of up to eight random codes and numbers (`HX-402`, `0.075`, `2'-9 1/2"`), placed as a block at a random spot. The eye test's read family: its items, prompt, pass mark (90% of a card's items, read exactly and in order) and fit (the height where reading reaches 90%, interpolated on a monotone fit). Sent together; a card not answered reads nothing, as in the eye test.
  - **When:** on a model's first use, with the image check, and in `config test` (`--only acuity`; `--model NAME` runs it with the chat model's checks). Not in the ping. Remembered by endpoint, model and `image_side`, with each card's share read; shown by `config checks` (`acuity passed ...; capitals 7 px tall and up read at 1000 px square`) and `config models` (`checked: json, image, acuity (an image 258 tokens; capitals 7 px read)`).
  - **What it does with the measure:** says it against what tiling assumes (`tilechoice.LEGIBLE_PX`, 7 px): `capitals 7 px tall and up read at 1000 px square (pages are tiled for text 7 px and up)`. Above 7.7 px (1.1 times), the line adds `smaller text on pages may be misread`. Reading no card at 90%, or no card answered, fails the check, and a run stops before anything is asked. Not used for tiling: that's the lever *Vision profiles and adaptive slicing* plans.
  - **Measured at DeepInfra** (scratch cache; $0.0058 in all):

| Model | Measured, 1000 px square | The eye test, 1024 px | Cost a check |
|---|---|---|---|
| gemma-4-31B-it, three checks | 7.0, 7.4, 7.0 px | 7.0 | $0.0013 |
| gemma-3-27b-it, two | 8.2, 8.0 | 9.1 | $0.0005 |
| Mistral-Small-3.2-24B | 8.3 | 9.1 | $0.0013 |
| Llama-4-Scout-17B-16E | failed: every card refused, HTTP 429 "Model busy, retry later" | 7.2 | $0 |

  - **So the measure orders models as the eye test did,** a little finer for the two weaker ones, and repeats on gemma-4 to within 0.4 px. The warning's 7.7 px sits between gemma-4's checks and the others'.
  - **A busy model fails the check,** as it would the JSON check: eight requests at once met Llama-4-Scout's 429s, which the retries didn't outlast. Run again, it's asked again.
  - **Two cards at a time since** (2026-11-02, with the low-hanging fruit: the owner, "Let's go with your recommendations on the low-hanging fruit."; `checkup.CARDS_AT_ONCE`), gentler on an endpoint of a few servers. It didn't save Llama-4-Scout: refused every card again, and its JSON check alone too, DeepInfra's model busy whatever is asked. gemma-4 at two at a time: 6.9 px ($0.0014).
  - **Scored a little apart from the lab:** text is folded (dashes, primes, quotes) before NFKC as well as after. NFKC makes a double prime (″) two primes, so the lab's scoring counts an inch mark written so as misread.
  - **Left too:** a controlled document's page read against its key, which needs a pass mark measured across models.
- **Then:** the vision profile, recommending a model per task ([*Model discovery and per-task selection*](README.md#tentative), [*Vision profiles and adaptive slicing*](README.md#tentative)), and keeping only the models a user's globs allow.

### Later: endpoints as named parts

- **The owner's "modularize things and simplify user overrides by a user":** named endpoints, each with:
  - its URL
  - the name of the variable holding its key
  - the models it serves by role: chat, reranker, embedding
- **A role names its endpoint,** and a user overrides one part without restating the rest.
- **This answers the deferred key question** when the owner takes it up. Until then, every URL is sent `OPENAI_API_KEY`.
- **A key of their own, built 2026-11-02** (the owner: "We could enable users to assign reranker and embedding model their own key, but the key must never be stored; they could specify environment variables where to find the key, though."): `rerank_key_env` and `embed_key_env`, each a variable's name, the key read from it as each request is made (`llm.key_named`, `Request.api_key`) and cut from what a server says back. A name not in capitals, digits and `_` is refused without being said back. Named endpoints stay for later.

## Design questions

1. **Where the endpoint's URL lives:** answered 2026-10-28 (quoted at the top): the environment and the user's settings, never a store ([milestone 1](#1-the-bug-and-the-first-run-error-bugs-first-0027)).
2. **Interactive or config ops only:** you said either would do.
   - **I'd build milestones 2 and 3 first** (commands only), then `config setup` as a thin walk through them, if those still leave the first run awkward.
   - **Answered 2026-11-02** (quoted at the top): guidance before each run, and "no model" kept apart from "unconfigured"; no guided setup for now ([milestone 4](#4-guidance-before-each-run-in-place-of-a-guided-setup)).
3. **The probes' cost and when they run:** only on `config test --probes`, or also on a model's first use?
   - **I'd run them on request only.** The first-use checks stay what they are: cheap, and needed before anything is asked.
   - **Answered 2026-11-02** (quoted at the top): on a model's first use, up front, and a ping each run even where the checks are remembered ([milestone 5](#5-failing-fast-a-ping-each-run-and-probes-on-first-use)).
