# 0032. Settings in layers, four environment variables, and one answers cache per user

- **Status:** Accepted (2026-10-20); amended 2026-10-20 (one name)
- **Amended 2026-10-20:** one name for the command, the package, the folders and the variables (the owner: "We also should unify naming a bit. Right now, iirc, it's PDF_DIFF, pdf-semantic-diff, and semantic-pdf-diff. I'm fine with any one name, but three is a bit awkward."). The command `pdf-semantic-diff` is now `semantic-pdf-diff`, as the distribution, the package (`semantic_pdf_diff`), the user's folders and the files' formats were named already. The variables follow: `PDF_DIFF_STORE` and `PDF_DIFF_CACHE` are `SEMANTIC_PDF_DIFF_STORE` and `SEMANTIC_PDF_DIFF_CACHE`, the old names ignored with a warning (`settings.variable`); the owner's quote below keeps the names as said.
- **Source:** [configuration in the store](../plans/configuration-in-the-store-2026-10-20.md), milestones 1 to 5; the [trials review](../reviews/trials-2026-10-08.md), finding 2

## Context

Settings came in four ways, highest first: about 25 flags per command, a `--config` JSON file, a `PDF_DIFF_<NAME>` variable for every one of 107 settings (plus `OPENAI_MODEL`), and the defaults. Nothing kept a store's own choices, so a store was configured again on every run. Answers were cached inside each store, cleared with it, and shared with no other. A run with other settings than its store's was refused until `--reset`.

- **The owner (2026-10-08):** "I think we need to greatly clean up and simplify configuration. We should keep just a few environment variables, perhaps four: OPENAI_BASE_URL, OPENAI_API_KEY, PDF_DIFF_STORE, PDF_DIFF_CACHE. [...] Other configuration items should be adjusted in the store via the CLI, e.g. `pdf-semantic-diff config (set|unset|import|export|show|test)...` with import/export using JSON. Use of `show` should describe options, defaults, examples where feasible."
- **On the cache (2026-10-08):** "The per-user default is tempting. Let's go with that instead."
- **On the design (2026-10-20):** "User layer is fine. Snake case or kebab case is fine, if consistent. Definitely will need navigation of settings and adequate help for each. Redo instead of refusing, yes." And earlier that day: "A flag as override is okay." cameo_ingest's `config` was the model to align with: "I have similar for the cameo_ingest product, including import and export via json files."

## Decision

- **Four environment variables:**
  - `OPENAI_BASE_URL` and `OPENAI_API_KEY`: the endpoint, and its key, never written anywhere.
  - `SEMANTIC_PDF_DIFF_STORE`: the store a command works on without `--store`.
  - `SEMANTIC_PDF_DIFF_CACHE`: the answers cache's folder.
  - `PDF_DIFF_<NAME>` and `OPENAI_MODEL` are no longer read. A run that finds one set warns once, naming the `config set --user` that replaces it.
- **Settings in layers,** each above the last:
  - the defaults;
  - the user's (`config set --user`, `$XDG_CONFIG_HOME/semantic-pdf-diff/settings.json`): what belongs to an endpoint and a machine, shared by every store;
  - the store's (`config set`, its `meta` table): the comparison's own, run options (`mode`, `report_budget`, `split`) among them;
  - a `--config` file, then a run's flags: one run's overrides, never saved.
- **Names are the settings' own, in snake case, everywhere:** `config`, exported files, `--config` files, report.json. Flags keep their dashes; a dashed name is answered with "did you mean max_cost?".
- **`semantic-pdf-diff config`:**
  - `show [GROUP] [--all]`, `find WORDS` and `help NAME` navigate the settings by group; every setting has its help (settinghelp.py, tested), and says what changing it redoes.
  - `set`, `unset`, `export` and `import`, the last two in cameo_ingest's format (`{"format": 1, "settings": {...}}`), all or nothing.
  - `test` checks the endpoint, the key and each model by asking, for a fraction of a cent, and exits 5 on a failure; `models` lists the endpoint's.
- **One answers cache per user:** `$SEMANTIC_PDF_DIFF_CACHE/answers.sqlite` (else `$XDG_CACHE_HOME/semantic-pdf-diff`, else `~/.cache/semantic-pdf-diff`).
  - It's a fixture ([0006](0006-replay-fixtures.md)), used as one is in `replay-or-record` mode under the model's name: the model's failures are asked again.
  - It's owner-only, as a store is.
  - Stores no longer cache answers. A store's own cached answers move into the cache as they're asked for.
  - `--fixture` replaces the cache for a run (tests and the lab).
- **A changed setting redoes what it changes,** instead of refusing the run ([0004](0004-store-bound-to-its-interpreters.md), amended). `--reset` starts a store over.

## Consequences

- A setting is set once, where it belongs; a run's command line names only what differs for that run.
- What one store asked, another is answered from: comparing a document again in a new store costs time, not money.
- **Removing a store leaves its answers in the cache,** and they quote its documents. Until a `cache` command exists (*Answers cache maintenance*, Tentative), the cache is cleared by removing `answers.sqlite`.
- The tests keep a cache in each store (tests/stubs.py) and read an empty folder's user settings, so a developer's own settings and answers never reach them.
- The lab's `.env` holds only the key and the endpoint; its other values are the user's settings. Scripts name fixtures, as before.
- Judges and checkers still take only endpoint settings from the user's settings ([0011](0011-settings-classified-by-effect.md)).
