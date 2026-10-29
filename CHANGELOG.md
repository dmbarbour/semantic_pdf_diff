# Changelog

Versions are `0.MINOR.PATCH`, raised at each checkpoint that changes the product, and tagged `vX.Y.Z` ([decision 0040](docs/decisions/0040-versions-raised-at-checkpoints.md)). The lab shares the product's version. Each entry says what a user would notice.

## 0.7.0 (2026-10-29)

- **`semantic-pdf-diff analyze SOURCE`** reads one source and reports its claims without comparing. The source can be a file, a folder or zip of documents, or a declared source. Its report opens on every claim, with topics, a file filter and the same search (other names and vectors too). It takes `compare`'s options except the comparing ones, and uses the same store, settings and answers cache. `report`, `search` and `debug` read an analysis as they read a comparison.
- **Indexes beside every report** (`analyze`'s and `compare`'s), built from what was read with no model requests:
  - `index.md`: subjects A to Z, each with its properties and every value with where it's said; then properties, and figures and tables.
  - `index.xlsx`: a sheet per index. Subjects is an outline: each subject's row with its values beneath, collapsing to the subjects. Plain numbers are stored as numbers.
  - `index/*.csv`: subjects, properties, claims, and figures.
  - `report.json`'s `index`.
  - In a comparison, one merged index: the sources' subjects are matched where the findings pair their claims (else by name), and each source's values sit side by side, "—" where one gives none. A subject's properties are one row where they're named alike or the findings pair their claims ("seating capacity" and "rider capacity").
- **Subjects and Figures views** in report.html. Each value links to its claim's card, and the search box filters them.

## 0.6.1 (2026-10-29)

- **A rate limit that resets later pauses the run at once, saying when.** A 429 that says when its limit resets (`Retry-After`, or a LiteLLM proxy's `reset_at` header and "Limit resets at:" message) is waited for when that's within 10 minutes. Later than that, sending stops at the first such refusal, and the run pauses (exit 3) with "rate limit reached at URL until TIME (in 3 h 5 min)". Before, each request was retried a minute apart, and the run paused only once 25 in a row had failed, without saying when the limit resets.
- The reranker's warning for requests not sent no longer says their pairs were judged: once sending has stopped, the judge isn't asked either.

## 0.6.0 (2026-10-29)

- **Answers cut short no longer stop a run.** An answer that's cut short, or isn't the JSON asked for, shows the endpoint working, so it doesn't count toward `stop_after_failures`. Before, 25 dense pages in a row stopped a whole run before its reranker, judge, names and topics were asked, even though those pages are asked again in smaller pieces anyway.
- **Requests not sent are counted apart from failures.** The reranker's and the embedding model's summaries and warnings say how many weren't sent (because sending had stopped, or a cap was reached) and how many failed. `debug` says so too.
- **`embed_dimensions` is unset by default.** No size is asked for, and the model answers at its own. Set it for a model trained to be cut: 256 was measured best for Qwen3-Embedding-8B. A store embedded at 256 embeds its claims again on its next comparison, for a fraction of a cent.
- **`debug`** names the region of each extraction error (text, table, tile, overview, figure), and fits its step column to the longest step's name.

## 0.5.0 (2026-10-29)

- **`semantic-pdf-diff debug`** says what a store's runs asked and what failed, in a few lines to read off a screen. It shows:
  - the endpoint and models the last comparison used;
  - the requests by step (extract, compare, rerank, embed, ...): asked, answered, failed, and never answered (not sent, as after sending stopped);
  - the last comparison's counts;
  - the errors the answers cache recorded, the most frequent first.

  It asks no model, and prints nothing of the documents but what a server's error quotes. `--errors N` shows more errors; `--json` prints everything as JSON.

## 0.4.0 (2026-10-29)

- **Embedding models that can't be cut work.** Every embedding request asked for `embed_dimensions` (256). Five of DeepInfra's 25 embedding models refuse any size with HTTP 400: BAAI/bge-base-en-v1.5, bge-en-icl and bge-large-en-v1.5, intfloat/e5-large-v2, thenlper/gte-large. A refused request is now asked again once with the model and the input alone, and the model answers at its own size. `config test` names the vectors' size, and says when it's the model's own.
- **A refusal says why.** A failed request said only its status (`HTTP 400: Bad Request`). It now adds what the server said: a JSON error's message, or plain text, on one line.
- **`-vv` shows what a refused request sent** (images and long texts shortened) and what the server answered. `config test` takes `-q`, `-v`, `-vv` and `--log-file`, as a comparison does.

## 0.3.0 (2026-10-28)

Everything since 0.2.0 (2026-09-24, about 630 commits), in brief. Each item's decision record has the detail.

- **Sources and stores:**
  - Files, folders, zip archives and manifests are declared as sources in a resumable store, a local folder ([0002](docs/decisions/0002-evidence-attaches-to-content.md), [0003](docs/decisions/0003-sqlite-evidence-store.md)).
  - A claim is kept once per piece of content, with every place it was read ([0005](docs/decisions/0005-union-provenance.md)).
  - A store reads again what a changed setting or reader affects ([0004](docs/decisions/0004-store-bound-to-its-interpreters.md), [0016](docs/decisions/0016-content-reread-when-its-reader-changes.md)).
- **Formats:** plain text, Markdown, Word, PowerPoint, Excel, CSV and images besides PDF, through one task core ([0020](docs/decisions/0020-formats-share-one-task-core.md)).
  - Office drawings are rendered ([0021](docs/decisions/0021-metafiles-drawn-by-vendored-renderer.md)).
  - Spreadsheet cells are read as Excel shows them ([0022](docs/decisions/0022-spreadsheet-cells-as-excel-shows-them.md)).
  - Every table is read by rules a model writes for it ([0023](docs/decisions/0023-tables-read-by-rules-a-model-writes.md), [0024](docs/decisions/0024-pdf-table-structure.md)).
- **PDF pages:**
  - Tiles are chosen by measures of each candidate cut ([0029](docs/decisions/0029-tiles-chosen-by-measures.md)).
  - Figures are linked to the prose citing them, and figures and sections are given what they're about ([0039](docs/decisions/0039-runs-paced-by-throughput-and-situated-after-extraction.md)).
- **Claims in context:** each claim carries its headings, lead-ins, notes and title blocks, and who holds it (a company's view, a hedge).
- **Comparing:**
  - Proposals' claims are paired by retrieval and a reranker, then judged.
  - Revisions are aligned item by item, equal values settled without a model, and each difference named by kind ([0038](docs/decisions/0038-revisions-aligned-then-differences-explained.md)).
- **The report:** `report.html` is one self-contained file ([0033](docs/decisions/0033-self-contained-reports-and-their-search.md)):
  - crops under a size budget
  - topics, and every claim of both sources
  - a search the command line shares (`semantic-pdf-diff search`)
  - views, filters and items kept in the page's address
  - `--split` for comparisons too large for one file
- **Setup:** settings in layers, set with `semantic-pdf-diff config`; four environment variables; one answers cache per user ([0032](docs/decisions/0032-settings-in-layers-and-one-answers-cache.md)).
  - There's no default model.
  - The endpoint is checked and calibrated on first use ([0034](docs/decisions/0034-endpoint-checked-and-calibrated-on-first-use.md)).
  - The endpoint's URL comes from `$OPENAI_BASE_URL` or the user's settings, never a store's.
- **Runs:**
  - Requests are paced by the server's throughput ([0039](docs/decisions/0039-runs-paced-by-throughput-and-situated-after-extraction.md)).
  - Progress is shown in bars ([0035](docs/decisions/0035-progress-drawn-by-the-product.md)).
  - Ctrl+C stops cleanly; the same command resumes.
  - Every request is at temperature 0 ([0012](docs/decisions/0012-temperature-zero-and-model-neutral-defaults.md)).
- **Diagnostics:** each image tile's path is recorded and counted, with the tiles whose answers say their text was cut.
- **Incompatible with 0.2.0:**
  - `OPENAI_MODEL` and `PDF_DIFF_<NAME>` aren't read; a run that finds one set says which `config set --user` replaces it.
  - The output folder is now a store.
- **The lab** is its own distribution, `semantic-pdf-diff[lab]` ([0014](docs/decisions/0014-lab-as-its-own-distribution.md)): improvement rounds, controlled documents with known facts ([0036](docs/decisions/0036-controlled-documents-with-exact-keys.md)), and levers judged against their baselines ([0037](docs/decisions/0037-levers-judged-paired-and-promoted-held-out.md)).
