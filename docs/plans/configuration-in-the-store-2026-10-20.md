# Configuration in the store: `pdf-semantic-diff config`, four environment variables, one answers cache

- **Status:** Active (2026-10-20). Milestones 1 and 2 done.
- **The owner (2026-10-08, the [trials review](../reviews/trials-2026-10-08.md), finding 2):** "I think we need to greatly clean up and simplify configuration. We should keep just a few environment variables, perhaps four: OPENAI_BASE_URL, OPENAI_API_KEY, PDF_DIFF_STORE, PDF_DIFF_CACHE. The difference between STORE and CACHE is that CACHE becomes our answers fixture, perhaps defaulting to $PDF_DIFF_STORE/cache, while STORE is our workspace for a particular difference task. We can also specify store and cache on the CLI. Other configuration items should be adjusted in the store via the CLI, e.g. `pdf-semantic-diff config (set|unset|import|export|show|test)...` with import/export using JSON. Use of `show` should describe options, defaults, examples where feasible."
- **Decided then (2026-10-08):** the cache is per user by default: "The per-user default is tempting. Let's go with that instead."
- **Then (2026-10-20), on the reranker's settings:** "Do we not have persistent configuration and the rest via 'pdf_semantic_diff config' yet? A flag as override is okay." And, asked for this design: "Please do. I have similar for the cameo_ingest product, including import and export via json files."

- **The owner's review (2026-10-20):** "User layer is fine. Snake case or kebab case is fine, if consistent. Definitely will need navigation of settings and adequate help for each. Redo instead of refusing, yes. Please proceed."
  - **Names:** snake case, the settings' own, everywhere: in `config`, exported files, `--config` files and report.json. Flags keep their dashes. A dashed name is answered with "did you mean max_cost?", not taken silently.
  - **Retiring `PDF_DIFF_<NAME>`** (question 4) wasn't answered. It follows the owner's own four variables (2026-10-08). `--config FILE` stays (question 6, not answered; nothing changes).
  - **Navigation and help:** `config show` by group (`config show GROUP`, `--all`), `config find WORDS`, `config help NAME`; every setting has a line on what it does, more where it helps, and an example where one does (settinghelp.py, checked by tests/test_config_command.py).

## Today

- **107 settings:** 36 of the platform and 71 of 63 levers. By class: 11 endpoint, 44 shaping, 40 selecting, 12 post.
- **Four ways in,** highest first:
  - about 25 flags on each running command;
  - a `--config` JSON file, which can also order the levers;
  - `PDF_DIFF_<NAME>` for every setting, plus `OPENAI_MODEL`, `OPENAI_BASE_URL` and `OPENAI_API_KEY`;
  - the defaults.

  The lab's `.env` sets six of them for DeepInfra (context, image tokens, concurrency, claims a request, output tokens, timeout).
- **The store binds** every setting its results rest on. A run with others is refused, and `--reset` clears what they change.
- **Two answer caches:**
  - the store's `response_cache`, inside the store and cleared with it;
  - the fixture (`--fixture`), shareable and packed, holding samples and failures, several processes at once.
- **Other run options:** the report's `--report-budget`, `--split` and the comparison's `--mode` are run options, not settings.

## What cameo_ingest does (to align with)

- **Environment:** four optional variables, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `CAMEO_INGEST_TREE` (the workspace, `./ingest_tree` unset) and `CAMEO_INGEST_CACHE` (`$XDG_CACHE_HOME/cameo-ingest`, else `~/.cache/cameo-ingest`). Everything else is the tree's.
- **What `config` sets:** a curated list of settings a user can judge (11), each with a key as `config` names it (`text-model`, `max-calls`), a kind (switch, text, models, count, choice), a default as shown, and a line saying what it does. The rest are defaults or calibrated.
- **The commands:**
  - `config [show]`: each setting's value, whether it's the tree's own or the default, and what it does; then the environment variables, the key shown only as set or not.
  - `config set KEY VALUE` and `config unset KEY`: setting one starts a tree.
  - `config export [FILE]` writes `{"format": 1, "settings": {KEY: VALUE}}`, the tree's own only, to the screen without FILE. `config import FILE` reads the same, `null` unsetting one, and changes nothing when any key or value is wrong.
  - `config test` checks the endpoint, the key and each model, and exits 5 on a failure. `config models [TEXT]` lists the endpoint's models.
- **Changes:** a changed setting rewrites what it affects, and stored answers are reused.

## Design

1. **Four environment variables,** as the owner listed them:
   - `OPENAI_BASE_URL` and `OPENAI_API_KEY`: the endpoint, and its key (never written anywhere).
   - `PDF_DIFF_STORE`: the store a command works on without `--store` (unset: `./diff-output`, as today).
   - `PDF_DIFF_CACHE`: the answers cache (unset: `$XDG_CACHE_HOME/semantic-pdf-diff`, else `~/.cache/semantic-pdf-diff`).

   `PDF_DIFF_<NAME>` and `OPENAI_MODEL` are no longer read. A run that finds one set warns once, naming the `config set` that replaces it. Variables that aren't settings stay: `SOURCE_DATE_EPOCH`, and the tests' `PDF_DIFF_ANSWER_ORDER`.
2. **Settings in layers,** each above the last:
   - the built-in defaults;
   - **the user's** (`config set --user`, in `$XDG_CONFIG_HOME/semantic-pdf-diff/settings.json`): what belongs to an endpoint and a machine rather than to a comparison (the model and its context, image tokens, concurrency, timeout, a reranker), shared by every store;
   - **the store's** (`config set`, kept in `store.sqlite`): the comparison's own (its mode, its levers, its budget, the report's);
   - **a run's flags:** one run's overrides, never saved (the owner: "A flag as override is okay").

   `--config FILE` stays as one run's overrides, for the lab's scripts and settings files.
3. **`pdf-semantic-diff config`,** cameo_ingest's commands with our settings:
   - **`config [show] [--all]`:** each setting's value, where it comes from (default, user, store), and a line on what it does, with an example where one helps.
     - **Shown by default,** about 20, grouped: the endpoint and budget (model, context, concurrency, timeout, max cost, max calls), reading (vision, situate), comparing (mode, top k, max pairs, the reranker), and the report (report budget, topic names).
     - **`--all`** adds the levers' 71, each with its class and what it changes, as `docs/configuration.md`'s table has them.
     - Then the four variables.
     - `pdf-semantic-diff settings` folds into it.
   - **`config set KEY VALUE` and `config unset KEY`** (`--user` for the user's layer):
     - Keys are named as their flags are (`max-cost`, `report-budget`, `rerank-threshold`), snake case accepted.
     - Values are parsed by the setting's type: `on`/`off` for switches, numbers, sizes as `20MB`, lists as JSON.
     - Setting one starts a store, so a store can be configured before its first comparison.
     - A setting the store's results rest on says what the next run redoes: "tile and figure regions read again from cached answers; the comparison judged again".
   - **`config export [FILE]` and `config import FILE`:** cameo_ingest's format, `{"format": 1, "settings": {"max-cost": 2, "levers": [...]}}`.
     - Export writes the layer's own settings only (the store's, or the user's with `--user`).
     - Import reads them, `null` unsetting one, and changes nothing when any key or value is wrong.
   - **`config test`** checks, for a few cents at most, and exits 5 on a failure:
     - the endpoint is reachable, and the model listed;
     - a JSON answer parses;
     - an image is read: an eye-test card, whose random code can't be guessed;
     - the reranker answers, if one is set;
     - and it reports what the checks cost.
   - **`config models [TEXT]`:** the endpoint's models, those the configuration uses marked.
4. **One answers cache:** `$PDF_DIFF_CACHE/answers.sqlite`, the fixture format (a query's answers by responder, samples and failures, several runs at once).
   - Every store reads and records into it: failures are asked again, transient ones retried.
   - The store's own `response_cache` is retired; a store keeps only what it derives.
   - `--fixture` stays for tests and the lab: a run's answers from that file instead.
   - A `cache` command (its size; pruned by age) can follow when it grows.
5. **A changed setting redoes what it changes,** instead of refusing the run. The bindings already know what each setting affects; the answers come from the cache, so redoing costs time, not money. `--reset` stays only as "start this store over".
6. **The report's and the comparison's options become settings:** `report-budget` and `split`, and `mode` (a store compares in one mode; `--mode` a run's override).

## Milestones

1. **The store's settings** (done 2026-10-20): `config show`, `find`, `help`, `set`, `unset`, `export` and `import`, with the store's settings under a `--config` file and the flags; `mode`, `report_budget` and `split` kept the same way; `settings` takes `--store` and stays as the JSON view. The store keeps them in its `meta` table, so existing stores open as they are.
2. **The user's layer and the four variables** (done 2026-10-20): `config set|unset|export|import --user`, in `$XDG_CONFIG_HOME/semantic-pdf-diff/settings.json`, under every store's settings and shown as `(user)`; `Settings.from_env` reads it and `OPENAI_BASE_URL`, nothing else. `PDF_DIFF_<NAME>` and `OPENAI_MODEL` warn once a run, naming the `config set --user` that replaces them. The lab's `.env` keeps only the key and the endpoint: its model, context, image tokens, concurrency, claims a request, output tokens and timeout were imported as the user's. The tests read an empty folder's user settings (tests/stubs.py), set for a block with `stubs.user_settings`. `PDF_DIFF_CACHE` comes with milestone 3.
3. **One answers cache,** per user; the store's response cache retired; `--fixture` for tests and the lab.
4. **Redo instead of refuse:** a store's bindings followed on every run.
5. **`config test` and `config models`.**

## Questions for the owner

Each with Claude's recommendation:

1. **A user layer** (the endpoint's settings, shared by every store) besides the store's? *Yes:* concurrency, context and the model belong to the endpoint, not to one comparison; cameo_ingest's trees each set them again.
2. **Keys as their flags name them** (`max-cost`), snake case accepted? *Yes*, as cameo_ingest's.
3. **`config show` curated,** with `--all` for the levers? *Yes:* 107 settings at once hide the twenty a user sets.
4. **`PDF_DIFF_<NAME>` and `OPENAI_MODEL` retired,** with a warning? *Yes*, as the owner's four variables say.
5. **A changed setting redoes rather than refuses?** *Yes*, with the cache making it free of model cost.
6. **`--config FILE` kept** as one run's overrides? *Yes*, for the lab's scripts.
