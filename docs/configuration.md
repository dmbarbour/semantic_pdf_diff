# Configuration (v0.2.0)

## Endpoint

When no environment variable or override is supplied, the default endpoint is `http://localhost:8000/v1`. `gemma-4` is only a configurable model identifier, not a claim that OpenAI hosts that model. The server must support Chat Completions with base64 PNG `image_url` inputs and JSON text responses. Use your provider's actual model identifier. API credentials come only from `OPENAI_API_KEY` and are not written to output. A warning is printed if the key would be sent over plain HTTP to a non-local host, and credentials embedded in `base_url` are redacted from reports.

## Precedence and environment variables

Configuration precedence, highest first: **CLI flags > JSON config file > the store's own settings > the user's settings > built-in defaults**. The user's settings (`config set --user`, kept in `$XDG_CONFIG_HOME/semantic-pdf-diff/settings.json`, else `~/.config/...`) belong to an endpoint and a machine: the model and its context, image tokens, concurrency, timeout, a reranker. Every store shares them. A store keeps its own settings for its comparison, set with `semantic-pdf-diff config` (below). A run's flags and a `--config` file override them for that run only. After naming the endpoint and the model once, you can normally run just `semantic-pdf-diff compare a.pdf b.pdf`. A config file only overrides fields it contains.

Four environment variables, as the owner listed them ([the plan](plans/configuration-in-the-store-2026-10-20.md)):

| Environment variable | What it is |
| --- | --- |
| `OPENAI_API_KEY` | API authentication (never included in settings/reports, never written anywhere) |
| `OPENAI_BASE_URL` | Chat Completions API base URL, including `/v1` when required |
| `SEMANTIC_PDF_DIFF_STORE` | The store a command works on without `--store` (unset: `./diff-output`) |
| `SEMANTIC_PDF_DIFF_CACHE` | The answers cache's folder: every answer the user's runs were given, in `answers.sqlite`, shared by every store (unset: `$XDG_CACHE_HOME/semantic-pdf-diff`, else `~/.cache/semantic-pdf-diff`) |

Two more variables aren't settings:

| Variable | What it is |
| --- | --- |
| `SEMANTIC_PDF_DIFF_ANSWER_ORDER` | Tests only: a seed; cached and replayed answers are handled in an order drawn from it, as a live run's might arrive, rather than as they were asked. What a run writes must not change (`dispatch.py`) |
| `SOURCE_DATE_EPOCH` | The time reports and review batches say they were made, in seconds since 1970 (UTC). The reproducible-builds convention; with it, replays form byte-identical reports |

`OPENAI_MODEL` and `PDF_DIFF_<NAME>` (one for every setting until 2026-10-20) are no longer read. A run that finds one set says, once, which `config set --user` keeps it instead: `OPENAI_MODEL` is `config set --user model NAME`, `PDF_DIFF_CONCURRENCY` is `config set --user concurrency 32`. `PDF_DIFF_STORE` and `PDF_DIFF_CACHE` are now `SEMANTIC_PDF_DIFF_STORE` and `SEMANTIC_PDF_DIFF_CACHE`, named as the command is; the old names are ignored, with a warning. Export the two endpoint variables through your shell or process manager; `.env` files are not loaded automatically.

`semantic-pdf-diff settings [--config FILE] [--store DIR]` prints every setting as a run would resolve them, the API key never; `--changed` prints only those differing from the defaults.

## The user's and a store's settings: `semantic-pdf-diff config`

A store keeps its own settings, set once for every run in it; the user's are shared by every store ([the plan](plans/configuration-in-the-store-2026-10-20.md)). Names are the settings' own, in snake case, everywhere (flags keep their dashes). Each command takes `--store DIR` (default: `$SEMANTIC_PDF_DIFF_STORE`, else `./diff-output`). `set`, `unset`, `export` and `import` take `--user` for the user's settings instead of the store's.

| Command | What it does |
| --- | --- |
| `config show [GROUP] [--all] [--json]` | The settings most runs set, by group, each with its value, `(user)` or `(store)` where one sets it, and what it does; a group's (endpoint, budget, sources, reading, comparing, report, levers); every one; or every value as JSON. Then the environment variables |
| `config find WORDS` | Settings whose name or help holds the words |
| `config help NAME` | One setting: what it does, its value and default, an example, its group and lever, and what changing it redoes |
| `config set NAME VALUE` | Kept in the store (a new store is made for it), and says what the next run redoes. Values as text: `on`/`off`, numbers, sizes (`40MB`), `none`, JSON for lists and objects |
| `config unset NAME` | Back to the default |
| `config export [FILE]` | The store's own settings as `{"format": 1, "settings": {...}}` (cameo_ingest's format), to the screen without a file |
| `config import FILE` | Every setting in the file, or none when any key or value is wrong; `null` unsets one |
| `config test` | The endpoint, the key and each model the settings name, checked by asking, never from the cache, for a fraction of a cent: the model listed at the endpoint (`/models`), a JSON answer (a sum), an eye-test card read (a random code drawn large), the reranker if one is set (a counterpart scored above an unrelated claim); then what the checks cost. Exit 5 when one fails |
| `config models [WORDS]` | The endpoint's models (its `/models`) whose names hold every word, those the settings name marked |

Besides the settings below, a store keeps three run options the same way: `mode` (proposals or revisions), and the report's `report_budget` and `split`.

For Python callers, use `Settings.from_env(...)` to get the user's settings and the endpoint's variable with explicit keyword overrides (a store's settings among them). Plain `Settings(...)` remains deterministic and consults neither. Output paths and comparison mode remain CLI options.

## Settings

Settings are in `config.example.json`; all omitted settings have defaults in `settings.py` and `levers.py`.

- **Levers** are the settings that shape how documents are read (context lines, tiling, quote matching and so on). Each is a mixin in `levers.py` that declares its settings, the stores' bindings it is part of, and the regions a change clears. A settings file may name its levers in order (`"levers": [...]`); without, the default order. `benchmarks/round0.json` and `benchmarks/champion.json` name theirs. A lever left out asks exactly what it asks switched off; a lever's place orders its lines among others' (context lines, for one).
- **A store binds every setting that shapes its results,** resolved, and the levers' order. A store made before 2026-10-02 bound only levers changed from the defaults of its day, so its first run since reads again what they shape; recorded answers replay.


### Every setting

Generated from the settings' declarations (`levers.settings_table`); `tests/test_settings.py` checks it's current. *Class:* endpoint settings never change what's asked; shaping ones change queries' content; selecting ones, which queries are made; post ones, only what's done with answers. *Bound by:* the stores' bindings it is part of (a change reads again what it affects). *Regions:* the extraction regions a change clears.

<!-- settings table: generated, do not edit -->
| Setting | Default | Class | Lever | Bound by | Regions |
|---|---|---|---|---|---|
| `rerank_url` | `null` | endpoint | rerank | - | - |
| `model` | `"gemma-4"` | endpoint |  | extract, triage, compare | all |
| `base_url` | `"http://localhost:8000/v1"` | endpoint |  | - | - |
| `max_calls` | `100000` | endpoint |  | - | - |
| `max_cost` | `null` | endpoint |  | - | - |
| `retries` | `2` | endpoint |  | - | - |
| `timeout` | `120` | endpoint |  | - | - |
| `stream` | `true` | endpoint |  | - | - |
| `concurrency` | `4` | endpoint |  | - | - |
| `heartbeat_seconds` | `30.0` | endpoint |  | - | - |
| `rate_limits` | `[]` | endpoint |  | - | - |
| `context_tokens` | `32768` | shaping |  | extract, triage | all |
| `output_tokens` | `4000` | shaping |  | extract, triage, compare | all |
| `claims_per_request` | `20` | shaping |  | extract | all |
| `image_tokens` | `1200` | shaping |  | extract, triage | all |
| `safety_tokens` | `400` | shaping |  | extract, triage | all |
| `text_bytes` | `1800` | shaping |  | extract | table, text |
| `image_side` | `1000` | shaping |  | extract, triage | figure, overview, tile, vision |
| `tile_points` | `420` | selecting |  | extract | figure, overview, tile, vision |
| `refinement_depth` | `1` | selecting |  | extract | all |
| `least_half` | `0.25` | selecting |  | extract | figure, overview, tile, vision |
| `section_depth` | `2` | shaping |  | extract | all |
| `section_pages` | `20` | shaping |  | extract | all |
| `top_k` | `4` | selecting |  | compare | - |
| `min_score` | `0.1` | selecting |  | compare | - |
| `max_pairs` | `1000` | selecting |  | compare | - |
| `vision` | `true` | selecting |  | extract | figure, overview, tile, vision |
| `situate` | `true` | selecting |  | - | - |
| `response_format` | `"none"` | shaping |  | extract, triage, compare | all |
| `seed` | `null` | shaping |  | extract, triage, compare | all |
| `max_token_field` | `"max_tokens"` | shaping |  | extract, triage, compare | all |
| `aliases` | `{}` | selecting |  | compare | - |
| `rescan` | `"auto"` | selecting |  | - | - |
| `max_zip_depth` | `8` | selecting |  | - | - |
| `max_source_bytes` | `53687091200` | selecting |  | - | - |
| `zip_ratio_limit` | `1000.0` | selecting |  | - | - |
| `zip_ratio_min_bytes` | `104857600` | selecting |  | - | - |
| `extract_prompt` | `null` | shaping | extract_prompt | extract | all |
| `split_conditions` | `true` | shaping | split_conditions | extract | all |
| `read_holders` | `true` | shaping | read_holders | extract | all |
| `hedge_rule` | `true` | shaping | hedge_rule | extract | all |
| `worked_examples` | `false` | shaping | worked_examples | extract | all |
| `column_conditions` | `false` | shaping | column_conditions | extract | table |
| `conditions_by_column` | `false` | shaping | conditions_by_column | extract | table |
| `extract_rules` | `[]` | shaping | extract_rules | extract | all |
| `visual_rules` | `[]` | shaping | visual_rules | extract | figure, overview, tile, vision |
| `images_first` | `true` | shaping | images_first | extract, triage, compare | figure, overview, tile, vision |
| `complete_by_image` | `false` | shaping | complete_by_image | extract | figure, overview, tile, vision |
| `context_before` | `400` | shaping | neighbours | extract | table, text |
| `context_after` | `400` | shaping | neighbours | extract | table, text |
| `leave_furniture` | `false` | shaping | leave_furniture | extract | figure, overview, table, text, tile, vision |
| `table_context` | `400` | shaping | table_context | extract | table |
| `stem_context` | `true` | shaping | stem_context | extract | table, text |
| `references` | `false` | shaping | references | extract | table, text |
| `tile_locator` | `false` | shaping | tile_locator | extract | figure, overview, tile, vision |
| `decoration` | `true` | selecting | decoration | extract | figure, overview, tile, vision |
| `tiling` | `"bands"` | selecting | tiling | extract | figure, overview, tile, vision |
| `band_width` | `1.6` | selecting | tiling | extract | figure, overview, tile, vision |
| `tile_cut` | `"grid"` | selecting | tile_cut | extract | figure, overview, tile, vision |
| `tile_choice` | `"measures"` | selecting | tile_choice | extract | figure, overview, tile, vision |
| `grow_tiles` | `true` | shaping | grow_tiles | extract | figure, overview, tile, vision |
| `sheet_details` | `false` | selecting | sheet_details | extract | figure, overview, tile, vision |
| `skip_empty` | `true` | selecting | skip_empty | extract | figure, overview, tile, vision |
| `skip_text_only` | `false` | selecting | skip_text_only | extract | figure, overview, tile, vision |
| `region_labels` | `"off"` | selecting | region_labels | extract | figure, overview, tile, vision |
| `another_tiling` | `"measures"` | shaping | another_tiling | extract | figure, overview, tile, vision |
| `refine_figures` | `"halves"` | selecting | figure_refinement | extract | figure, overview, tile, vision |
| `halve_parts` | `true` | selecting | halve_parts | extract | figure, overview, tile, vision |
| `render_area` | `false` | shaping | render_area | extract | figure, overview, tile, vision |
| `figure_tasks` | `true` | selecting | figure_tasks | extract | figure |
| `table_rules` | `0` | selecting | table_rules | extract | table |
| `table_review` | `10` | shaping | table_review | extract | table |
| `table_structure` | `true` | selecting | table_structure | extract | table |
| `visual_text_layer` | `1500` | shaping | visual_text_layer | extract | figure, overview, tile, vision |
| `table_cuts` | `false` | shaping | table_cuts | extract | figure, overview, tile, vision |
| `text_cuts` | `"bytes"` | shaping | text_cuts | extract | figure, overview, text, tile, vision |
| `text_spans` | `"page"` | shaping | text_spans | extract | text |
| `repeated_text` | `"first"` | shaping | repeated_text | extract | table, text |
| `lone_rows` | `true` | shaping | lone_rows | extract | table |
| `table_filter` | `false` | selecting | table_filter | extract | table, table-detection |
| `skip_sheet_tables` | `false` | selecting | skip_sheet_tables | extract | figure, table, table-detection |
| `leave_text` | `"tables"` | shaping | leave_text | extract | table, text |
| `quote_match` | `"fragments"` | post | quote_match | extract | table, text |
| `positions` | `"provenance"` | post | positions | extract | table, text |
| `records` | `true` | post | records | extract | all |
| `sheet_records` | `true` | post | sheet_records | extract | all |
| `table_holders` | `true` | post | table_holders | extract | table |
| `carried_holders` | `true` | post | carried_holders | extract | table |
| `view_attitudes` | `true` | post | view_attitudes | extract | all |
| `view_rows` | `true` | post | view_rows | extract | table |
| `hedges_apart` | `true` | post | hedges_apart | extract | all |
| `reconcile` | `true` | post | reconcile | - | - |
| `dedupe_repeated` | `true` | shaping | dedupe_repeated | extract | all |
| `continuations` | `3` | selecting | continue_reading | extract | figure, overview, tile, vision |
| `align` | `true` | selecting | align | compare | - |
| `align_printed` | `false` | selecting | align | compare | - |
| `align_hedges` | `true` | selecting | align | compare | - |
| `verify_visuals` | `true` | selecting | verify_visuals | compare | - |
| `explain_differences` | `true` | selecting | explain_differences | compare | - |
| `explain_context` | `false` | shaping | explain_differences | compare | - |
| `editorial` | `true` | post | editorial | compare | - |
| `record_changes` | `true` | post | record_changes | compare | - |
| `judge_context` | `false` | shaping | judge_context | compare | - |
| `topic_names` | `true` | selecting | topic_names | compare | - |
| `rerank_model` | `null` | selecting | rerank | compare | - |
| `rerank_api` | `"deepinfra"` | selecting | rerank | compare | - |
| `rerank_url` | `null` | endpoint | rerank | - | - |
| `rerank_threshold` | `3` | selecting | rerank | compare | - |
<!-- end of settings table -->

- `response_format` is `none` by default because some compatible servers do not support it; `json_object` requests JSON mode and `json_schema` sends the response schema for guided decoding (vLLM, llama.cpp, and similar), which is strongly recommended for small models where supported. The 0.1 `json_mode: true` setting still maps to `json_object`.
- Every request is sent at temperature 0, for reproducible answers; it isn't a setting. `seed` is sent when set.
- Set `max_token_field` to `max_completion_tokens` if your server requires it.
- `claims_per_request` (default 20) caps the claims asked for in one extraction request. A small cap on a dense page makes the model report "partial", and each partial answer is split and asked again, one round at a time. With a large-context model, raise it together with `output_tokens` (allow about 150 tokens per claim), e.g. 20 claims with 4000 output tokens.
- `section_depth` (default 2) sets how many outline levels become sections; `section_pages` (default 20) sets the page-range size for PDFs without an outline. Both affect prompts, so changing them reads an existing store's documents again.
- `--no-vision` is a deliberately incomplete text-only run, recorded as such.
- `situate` (default `true`; `--no-situate` on the command line) runs the situating stage: one request per labelled figure and per section after extraction. Its model, prompts and output settings are bound to the store as the `triage` role; changing them situates again, clearing only situating results.

## Context budget

Defaults are model-neutral and target a 32,768-token context, with a generous 1,200-token bound per image. `config.example.json` holds the profile measured with gemma-4 on DeepInfra (262,144 context tokens, 300 per image, 20 claims with 4,000 output tokens). No request contains a whole PDF; even a native text block is split. The adapter budgets UTF-8 text bytes conservatively, adds configurable image-token estimates, reserves output and safety capacity, then refuses an oversized request. If your server offers a larger window, raise `context_tokens` to match; chunk sizes (`text_bytes`, tile size) are separate settings.

**Image token accounting is backend-specific.** For example, gemma-4 on DeepInfra charges a flat ~284 prompt tokens per image regardless of size (it resizes internally), so `image_tokens: 300` suffices there. `image_tokens` must be a conservative upper bound for one image at `image_side`. It is not an exact tokenizer. Calibrate against your serving backend before large runs. For a smaller context, reduce `output_tokens`, `text_bytes`, `image_side` and tile size together, and adjust image-token estimates according to the actual backend. Two-image comparison requests may still exceed budget and will be reported as uncertain; `verify_visuals: false` allows text-claim comparison at the cost of skipping direct visual reinspection.

## Throughput and progress

- **`concurrency`** (default 4): the most model requests in flight. An adaptive gate halves it when the server returns 429/503 or latency jumps, and grows it back by one after a run of successes. Results don't depend on it: concurrent and sequential runs produce identical evidence and findings.
- **`rate_limits`**: time-of-day rules, the first matching one applies (local time), each with `tokens_per_minute` and/or `requests_per_minute`, optionally `days` (`"mon-fri"`, `"sat,sun"`) and `hours` (`"08:00-18:00"`, or overnight like `"22:00-06:00"`). Token use is estimated before each request and corrected from the server's reported usage. `config set --user rate_limits '[...]'` takes the same JSON list.
- **Progress:** a `tqdm` bar per stage on a terminal; otherwise a heartbeat line every `heartbeat_seconds` (30) with tasks done, tokens per minute and time remaining. `-q` shows warnings only, `-v` each task, `-vv` each model request; `--log-file` writes a detailed log.

None of these affect output, so changing them never reads anything again.

## Calls, caching and exit codes

A typical page needs multiple calls, so large PDFs can require hundreds or thousands. `Retry-After` on 429/503 responses is honoured (capped at 60 s). `--max-calls` caps the requests sent in one invocation, counted as each is asked; retries don't count. A run a cap cuts (`--max-calls`, `--max-cost`, the provider's balance) says so in its report (`paused`): which work the cap cut followed the order answers came in, so the report isn't reproducible until the run is resumed.

A comparison's `--store` folder is an evidence store: `store.sqlite` (sources, files, content, evidence, coverage, the queries asked, comparisons) plus `assets/` for rendered crops. Stores are created with owner-only permissions and are as sensitive as the documents they were built from. So is the answers cache (`$SEMANTIC_PDF_DIFF_CACHE`), owner-only too: its answers quote the documents, and removing a store leaves them there.

- **Reuse and resume:** content already extracted is loaded from the store. Evidence and coverage are written task by task. Model answers are cached in the user's answers cache (`$SEMANTIC_PDF_DIFF_CACHE/answers.sqlite`, a fixture's format, shared by every store) by the query that reached the model (its text, images and generation settings) and the model, so an interrupted run resumes by replaying cached answers, and another store asking the same is answered from it. The model's failures are asked again. Tasks that failed (e.g. hitting `--max-calls`) are retried on the next run. `--fixture` replaces the cache for a run (tests and the lab). Stores cached their own answers until 2026-10-20; those are moved into the cache as they're asked for.
- **The answers cache's maintenance** ([the plan](plans/answers-cache-maintenance-2026-10-20.md)): a project whose documents mustn't mix with others' keeps a cache of its own (`SEMANTIC_PDF_DIFF_CACHE` pointed at it). Each store logs every query its runs asked, however answered, so `cache` picks out a project's answers by naming its stores. Each action works on the current cache, or the one `--cache` names, and takes `--dry-run`:
  - `cache show`: where the cache is, its size, its answers by model and role, when last used.
  - `cache copy FROM [--store DIR ...]`: the answers another cache (its folder) or fixture holds and this one lacks, only the stores' if named: a project's answers taken from another cache.
  - `cache remove --store DIR ... [--keep DIR ...]`: the answers the stores asked, but those the `--keep` stores asked too: a store removed, or answers that belong in another cache.
  - `cache prune --keep DIR ...` keeps only what the stores asked; `cache prune --unused-since TIME` removes what no run used since (with `fixtures prune`'s guards).
  - Removed answers are overwritten in the file (SQLite's `secure_delete`, then the file compacted and its log emptied), not left in its free pages. Copies made before, by backups or snapshots, aren't touched.
- **Sources:** each comparison object is a source declared in the store with a name, metadata and roots (files, folders, zip archives). `compare` declares a path given in place of a name as a `shortcut` source, named after its final component. Roots are rescanned on every run; set `rescan` to `"manual"` to rescan only on `source update`. Unchanged files (same size and modification time) aren't reread. Content no source references any more is orphaned; `gc` removes it.
- **Archives and hidden files:** zip archives are read in memory, including nested ones. Files and folders whose names start with `.`, and OS clutter (`__MACOSX`, `Thumbs.db`), are skipped and listed. Safety limits are generous and configurable: `max_zip_depth` (8), `max_source_bytes` (50 GB), and a compression-ratio check (`zip_ratio_limit` 1000 for members over `zip_ratio_min_bytes`, 100 MB). Unsafe member paths are rejected and encrypted members skipped; all are listed in the report.
- **One writer:** a second process writing to the same store gets a "store is in use" error.
- **Binding:** the store records its extraction interpreter (model, prompts, output-affecting settings, library versions). A run with a different one clears only the derived data the differences affect (for example, a changed tile size clears only image-based evidence) and reads it again, its unchanged queries answered from the cache. The log says each difference and what it affects, what is read again, and at most how many requests are asked again. Until 2026-10-20 such a run was refused (the owner: "Redo instead of refusing, yes."). A setting that only post-processes answers (`quote_match`) is recomputed from cached answers. A reader's change reads again the content it reads ([decision 0016](decisions/0016-content-reread-when-its-reader-changes.md)). Saved comparisons are kept. `--reset` starts the store over: everything read is read again and its saved comparisons cleared (sources, settings and cached answers stay). `--dry-run` shows what a run would clear. Timeouts, retries, call limits, credentials and the endpoint URL don't count. Keep model identifiers versioned when deployed weights change; the store can't detect a silent weight swap.
- **Maintenance:** `show VIEW` prints `sources`, `source_files`, `evidence_occurrences`, `coverage_by_source`, `orphaned_content` or `comparisons` (the same names are SQL views in `store.sqlite`). `report` regenerates a report from a saved comparison (`--comparison ID`, default latest). `gc` deletes orphaned content with its evidence, tasks, sections, cached extraction responses and crops; `--dry-run` previews, and `--orphaned-sources` also removes sources whose linked manifest file is gone.
- **Schema changes** during development aren't migrated: an older store refuses to open; use a new folder.

- **Recorded answers:** `--fixture FILE` keeps the model's answers in a fixture and replays them. A `.sqlite` file is created if missing and records new answers; a `.zip` is replayed only. `--fixture-mode` sets the policy:
  - `replay` (a `.zip`'s default): fail what isn't recorded, as tests and CI want
  - `replay-or-record` (a `.sqlite` file's default): ask the model and record it, recorded failures too
  - `record-new`: record only what was never asked

  A fixture that can't be used as asked (a missing file under `replay`, a `.zip` to record into) fails the run before the store is changed.

  `--responder` names whose answers to use. `--fresh-regions` re-asks extraction for some regions as a second sample (an A/A control).
- **Cost:** `--max-cost` stops sending once the provider-reported cost reaches that many dollars. `--ledger FILE` appends every response's reported cost, tagged with `--ledger-tag KEY=VALUE`.

Exit codes:
- `0` processing complete (semantic uncertainty may remain)
- `2` incomplete source coverage (including tasks `not_reached` because of `max_calls`), a comparison processing failure, no extracted claims on either side, or pair-limit truncation
- `3` paused for budget (the cost cap, or the provider's balance): rerun the same command to resume, keeping finished work
- `1` fatal input or configuration error
- `5` a check of `config test` failed

Inspect the JSON and coverage ledger regardless of exit code.
