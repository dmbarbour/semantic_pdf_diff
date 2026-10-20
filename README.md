# Semantic PDF Diff

A Python CLI for evidence-first comparison of competing engineering proposals or revisions of one design. It extracts atomic claims from text, tables, charts and diagrams with a small vision model behind an OpenAI-compatible endpoint, pairs related claims, and reports differences with provenance back to the page and region each claim came from. It never ranks proposals, and it never treats a missing counterpart as proof of absence.

## Status

**v0.2.0** (tagged) compares two PDFs. The main branch has since gained:

- **Sources** as files, folders and zip archives, declared in a persistent, resumable store
- **Replay fixtures:** recorded model answers, so runs replay offline
- **Levers:** how documents are read, composed as mixins (`levers.py`)
- **The lab** (`lab/`, its own distribution): improvement rounds judged by model panels and people, controlled documents with known facts, eye and page tests
- **Plain text, Markdown, Word, PowerPoint, Excel, CSV and images** (`.png`, `.jpg`, `.tif` and others; read by vision, as a scanned page is) read as well as PDF: sections from headings (a slide's title, a sheet's name), paragraphs, tables, charts from their data, pictures and speaker notes, claims located by line, paragraph, slide or sheet and cells (Office formats need `pip install 'semantic-pdf-diff[office]'`). Each table in Excel, CSV, Word, PowerPoint or PDF is read as a model, asked once per table, says it should be: by rules applied to every row, row by row, or as a summary (a series, a log, a list) computed from all of them
- **Revisions aligned before they're judged:** items matched across revisions by their values, equal values settled without a model, and the report showing how it grouped them
- **Differences explained:** in revisions, each difference named by kind (a value or its conditions changed, renamed, restated, misread, not the same item), value changes listed first

**Status:**
- Extraction has been measured with one real model (gemma-4-31B, through DeepInfra) on public sample documents and the controlled corpus.
- It isn't a validated engineering sign-off tool; see [limitations](docs/limitations.md).
- **Still planned:** more formats (images), criteria-first comparison of two or more sources, consistency checks and RAG export. See [docs/plans/](docs/plans/README.md).

## Quick start

Python 3.10+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY='your-serving-provider-key'
export OPENAI_BASE_URL='https://your-provider.example/v1'
semantic-pdf-diff config set --user model your-vision-model-id
semantic-pdf-diff config test        # the endpoint, the key and the model checked, for a fraction of a cent
semantic-pdf-diff compare team-a.pdf team-b.pdf --store result
```

The model, like the endpoint's other settings (context, concurrency, timeout), is the user's: kept once for every store. A store keeps its own settings: `semantic-pdf-diff config show --store result` lists them by group, `config set NAME VALUE` sets one for every run in the store, and `config help NAME` says what it does and what changing it redoes. `semantic-pdf-diff --help` lists every command, the environment it needs and examples; `semantic-pdf-diff COMMAND --help` (or `semantic-pdf-diff help COMMAND`) gives a command's options, and `semantic-pdf-diff settings` prints every setting a run would use (with `--changed`, those differing from the defaults: a starting `--config` file).

Open `result/report.html`: it's one file, which can be moved or sent on its own. Its crops are embedded in order of value (the findings to check, and claims read from charts, diagrams and tables, first) until the file reaches `--report-budget` (20 MB by default); `semantic-pdf-diff report --store result --dry-run` says what a budget leaves out. For comparisons too large for one file, `--split` writes a file per pair of files and an index, in a folder to zip and send. The page shows the findings, or every claim of both sources, by topic, file and relation; its search takes words in any order, `"phrases"`, `-exclusions`, `a OR b` and a claim's parts (`entity:pump`, `page:10-20`), finds the most relevant first, compares values across units (`>50kW` finds 0.075 MW), and keeps the search in the page's address, to bookmark or send. Each card's *Claims like this* finds the other source's claims most like it (by meaning too, with an embedding model configured: `config set embed_model Qwen/Qwen3-Embedding-8B`); in the claims view, a search also shows the found claims' counterparts, and offers the other source's names for what was searched. Machine-readable results are in `report.json`; the extracted evidence, its provenance and coverage are in `evidence.json`.

Either source can also be a folder or a zip archive. For revisions, supply the old version first:

```bash
semantic-pdf-diff compare old.pdf new.pdf --mode revisions --store revision-diff
semantic-pdf-diff compare team-a/ team-b.zip --store team-diff
```

For repeated work, declare **sources** in a store, each with a name, provenance metadata and one or more roots, and compare them by name (`compare` takes names and paths alike, a declared name first). Sources are rescanned on every run, so edited, added or deleted files are picked up:

```bash
semantic-pdf-diff source add team-a --store work --path team-a/ --path addendum.pdf --meta organization="Team A" --meta revision=C
semantic-pdf-diff source add team-b --store work --path team-b.zip
semantic-pdf-diff compare --store work team-a team-b
semantic-pdf-diff source export team-a --store work --output team-a.source.json --with-hashes
```

Model requests run in parallel (`concurrency`, default 4, adapting down when the server throttles) within optional time-of-day rate limits, e.g. in a `--config` file:

```json
{"concurrency": 6, "rate_limits": [{"days": "mon-fri", "hours": "08:00-18:00", "tokens_per_minute": 300000},
                                   {"tokens_per_minute": 500000}]}
```

Runs show progress bars on a terminal and heartbeat lines otherwise; `-q`, `-v`, `-vv` and `--log-file` control the detail.

Inspect and maintain a store with `show` (views as Markdown, CSV or JSON Lines), `report` (regenerate a report without model calls) and `gc` (delete content no source references any more); the answers cache with `cache` (show it; copy, remove or prune a project's answers by naming its stores):

```bash
semantic-pdf-diff show evidence_occurrences --store work --format csv
semantic-pdf-diff report --store work --out reports/latest
semantic-pdf-diff gc --store work --dry-run
semantic-pdf-diff cache copy ~/.cache/semantic-pdf-diff --store work   # this project's answers, from another cache
semantic-pdf-diff search 'hub height -tower' --store work               # the store's claims, as the report's search
```

A revision is just another source (e.g. `team-a-rev1` vs `team-a-rev2`). Manifests (`source export` / `source import`, or `compare --manifest FILE` for a live link) carry source definitions between stores and users. Files of the types listed under Status are read; others are listed as skipped (`source show` says which, and why).

Exit codes: `0` complete (uncertainty may remain); `2` incomplete coverage or processing failures; `1` fatal input or configuration error, a mistyped command or option included; `5` a check of `semantic-pdf-diff config test` failed.

The `--store` folder (`diff-output` unless named) is an evidence **store** (`store.sqlite` plus rendered crops): rerunning into it reuses extracted evidence, and an interrupted run resumes where it stopped. Model answers are cached for every store (`$SEMANTIC_PDF_DIFF_CACHE`, else `~/.cache/semantic-pdf-diff`), so what was asked once isn't paid for again. A store is bound to the model and extraction settings it was built with. A run with different ones reads again what they change, saying what differs and at most how much is asked again (preview with `--dry-run`); unchanged queries are answered from the cache. `--reset` starts a store over.

## Documentation

| Document | Contents |
| --- | --- |
| [How it works](docs/how-it-works.md) | Claims, the extraction and comparison pipeline, modes, code map |
| [Configuration](docs/configuration.md) | Endpoint, environment variables, settings, context budget, caching, exit codes |
| [Samples and testing](docs/samples-and-testing.md) | Running tests, the public sample corpus, recorded answers (replay fixtures), synthetic samples, local embedding server |
| [Limitations](docs/limitations.md) | What the current release can't do, and what to review before relying on it |
| [Validation](docs/VALIDATION.md) | What has and hasn't been verified |
| [Plans](docs/plans/README.md) | Design plans for the generalized tool, with status |
| [Decisions](docs/decisions/README.md) | Architecture decisions in force, each with its reasons and consequences |

## Tests

The tests cover the lab too: the evaluation and bench tooling, its own distribution in `lab/` (`semantic-pdf-diff[lab]` once published), which adds the `review` and `queries` commands.

```bash
pip install -e '.[dev]' -e lab
python -m unittest discover -s tests -v
```
