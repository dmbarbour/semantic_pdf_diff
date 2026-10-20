# Answers cache maintenance: copy a project's answers, remove them, prune

- **Status:** Active (2026-10-20)
- **The owner (2026-10-20):** "I'm just using project-local cache for sensitive things. Can't even let it mix without marking home cache CUI or higher. Some ability to prune or transfer answers would be convenient, though, e.g. fill this cache by taking answers from that one for a particular project."
- **From:** the Tentative row raised when the answers cache became one per user ([decision 0032](../decisions/0032-settings-in-layers-and-one-answers-cache.md)): removing a store leaves its answers in the cache, and they quote its documents.

## Why

- **One cache per user, by default** (decision 0032): every store's answers are kept in `answers.sqlite`, under `$SEMANTIC_PDF_DIFF_CACHE` or the user's cache folder. A sensitive project gets a cache of its own by pointing the variable at the project.
- **Today the only tools are the whole file and `fixtures`:**
  - `fixtures merge` copies every answer of one fixture into another. No filter keeps another project's answers out.
  - `fixtures prune` drops answers unused since a time. Nothing removes one project's answers and keeps the rest.
- **What a project asked is already known:** each store logs every query its runs asked (the `query` table), whether a cache answered it or the model did. The log uses the same hash the cache keys answers by, so a store's answers can be picked out exactly.

## Design

`semantic-pdf-diff cache ACTION` works on one answers cache: `--cache PATH` (a folder holding `answers.sqlite`, or the file), else the current one, as `config show` lists it.

| Action | What it does |
|---|---|
| `cache show` | Where the cache is, its size, its answers by model and role, and when it was last used |
| `cache copy FROM [--store DIR ...]` | Copies into this cache the answers FROM holds and this cache lacks. FROM is another cache's folder or a fixture (`.sqlite` or `.zip`). With `--store`, only the answers to the queries those stores asked: "fill this cache by taking answers from that one for a particular project" |
| `cache remove --store DIR ... [--keep DIR ...]` | Removes the answers to the queries those stores asked, except those the `--keep` stores asked too: for a store removed, or for answers that belong in another cache |
| `cache prune [--keep DIR ...] [--unused-since TIME]` | Keeps only the answers the named stores asked, or drops those unused since a time (`fixtures prune`'s guards), or both |

- **Every action takes `--dry-run`** and says what it would copy or remove, and from where to where.
- **Both ends are always named:**
  - Nothing copies between caches unless the command names the source.
  - Each action's output names both files, so a copy into the wrong cache can be seen and undone with `cache remove`.
- **Removed means gone from the file:**
  - Removal deletes with SQLite's `secure_delete`, then compacts the file (`VACUUM`) and empties its write-ahead log.
  - So removed answers aren't left in the file's free pages.
  - Copies the filesystem or a backup made earlier are beyond the tool; the output says so.
- **Side rows go with their answers:** a query's description and recipes (its content's hash, its task) are copied with its answers, and removed when it has no answers left.
- **Every model's answers:** a store's queries are copied or removed whichever model answered them. A query's hash includes its model's settings, but not the model's name.
- **A store from before 2026-10-20** kept answers in its own `response_cache`. Those reach a cache as its next run asks them; `cache copy` doesn't read them.

## Milestones

1. **The `cache` command** (done 2026-10-20): the actions above, their help, tests (copy filtered by store, every model's answers, owner-only folders; remove with keep, the removed answers' text gone from the file and its log; prune by stores and by age; dry runs; refusals), and docs (configuration, the README, decision 0032).

2. **A store bound to its cache** (done 2026-10-20; proposed after milestone 1 because a shell without the export sent a sensitive project's answers into the home cache, which then needed marking; the owner: "Supporting a configurable cache makes sense. Please proceed with that").
   - **The store records which cache its runs use** (`answers_cache`, a store's option like `report_budget`):
     - The one its first run used ($SEMANTIC_PDF_DIFF_CACHE's, else the user's), or one named with `config set answers_cache PATH`.
     - It's kept relative to the store where both sit in one project's folder (`../answers`), from `~` in the home folder, else absolute.
   - **Later runs use it whatever the environment says:** a shell without the project's export still keeps the project's answers in the project's cache.
   - **A run whose SEMANTIC_PDF_DIFF_CACHE names another cache is refused,** naming both, before the store changes (before its sources are declared or scanned). A dry run says so too.
   - **`config set answers_cache PATH`** takes the path from the current folder. It says where the answers asked before stay, and the `cache copy` that brings them. `config set --user answers_cache` is refused: the user's cache is the variable's.
   - **Still possible:** a store's first run made in the wrong shell binds the cache it used. `cache copy`, `cache remove` and `config set answers_cache` repair that.
