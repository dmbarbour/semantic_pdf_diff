# Semantic PDF Diff

A Python CLI for evidence-first comparison of competing engineering proposals or revisions of one design. It extracts atomic claims from text, tables, charts and diagrams with a small vision model behind an OpenAI-compatible endpoint, pairs related claims, and reports differences with provenance back to the page and region each claim came from. It never ranks proposals, and it never treats a missing counterpart as proof of absence.

## Status

**v0.2.0** (tagged) compares two PDFs. The main branch has since gained:

- **Sources** as files, folders and zip archives, declared in a persistent, resumable store
- **Replay fixtures:** recorded model answers, so runs replay offline
- **Levers:** how documents are read, composed as mixins (`levers.py`)
- **The lab** (`lab/`, its own distribution): improvement rounds judged by model panels and people, controlled documents with known facts, eye and page tests
- **Plain text, Markdown and Word** read as well as PDF: sections from headings, paragraphs and tables, claims located by line or paragraph (Word needs `pip install 'semantic-pdf-diff[office]'`)
- **Revisions aligned before they're judged:** items matched across revisions by their values, equal values settled without a model, and the report showing how it grouped them
- **Differences explained:** in revisions, each difference named by kind (a value or its conditions changed, renamed, restated, misread, not the same item), value changes listed first

**Status:**
- Extraction has been measured with one real model (gemma-4-31B, through DeepInfra) on public sample documents and the controlled corpus.
- It isn't a validated engineering sign-off tool; see [limitations](docs/limitations.md).
- **Still planned:** more formats (`.pptx`, spreadsheets, images), criteria-first comparison of two or more sources, consistency checks and RAG export. See [docs/plans/](docs/plans/README.md).

## Quick start

Python 3.10+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY='your-serving-provider-key'
export OPENAI_BASE_URL='https://your-provider.example/v1'
export OPENAI_MODEL='your-vision-model-id'
pdf-semantic-diff team-a.pdf team-b.pdf --out result
```

Open `result/report.html`, keeping its `assets/` folder alongside it. Machine-readable results are in `report.json`; the extracted evidence, its provenance and coverage are in `evidence.json`.

Either argument can also be a folder or a zip archive. For revisions, supply the old version first. `--plan` estimates the work without calling the model:

```bash
pdf-semantic-diff old.pdf new.pdf --mode revisions --out revision-diff
pdf-semantic-diff team-a/ team-b.zip --plan
```

For repeated work, declare **sources** in a store, each with a name, provenance metadata and one or more roots, and compare them by name. Sources are rescanned on every run, so edited, added or deleted files are picked up:

```bash
pdf-semantic-diff source add team-a --store work --path team-a/ --path addendum.pdf --meta organization="Team A" --meta revision=C
pdf-semantic-diff source add team-b --store work --path team-b.zip
pdf-semantic-diff compare --store work team-a team-b
pdf-semantic-diff source export team-a --store work --output team-a.source.json --with-hashes
```

Model requests run in parallel (`concurrency`, default 4, adapting down when the server throttles) within optional time-of-day rate limits, e.g. in a `--config` file:

```json
{"concurrency": 6, "rate_limits": [{"days": "mon-fri", "hours": "08:00-18:00", "tokens_per_minute": 300000},
                                   {"tokens_per_minute": 500000}]}
```

Runs show progress bars on a terminal and heartbeat lines otherwise; `-q`, `-v`, `-vv` and `--log-file` control the detail. `--plan` estimates calls, tokens and time under the current limit.

Inspect and maintain a store with `show` (views as Markdown, CSV or JSON Lines), `report` (regenerate a report without model calls) and `gc` (delete content no source references any more):

```bash
pdf-semantic-diff show evidence_occurrences --store work --format csv
pdf-semantic-diff report --store work --out reports/latest
pdf-semantic-diff gc --store work --dry-run
```

A revision is just another source (e.g. `team-a-rev1` vs `team-a-rev2`). Manifests (`source export` / `source import`, or `compare --manifest FILE` for a live link) carry source definitions between stores and users. PDF, `.txt`, `.md` and `.docx` files are extracted so far, a Word document's pictures (EMF, WMF and images) included; other files are listed as skipped.

Exit codes: `0` complete (uncertainty may remain); `2` incomplete coverage or processing failures; `1` fatal input or configuration error.

The `--out` folder is an evidence **store** (`store.sqlite` plus rendered crops): rerunning into it reuses extracted evidence and cached model responses, and an interrupted run resumes where it stopped. A store is bound to the model and extraction settings it was built with; a run with different ones is refused unless you pass `--reset` (preview with `--reset --dry-run`) or use a new folder.

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
