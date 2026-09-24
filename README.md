# Semantic PDF Diff

A Python CLI for evidence-first comparison of competing engineering proposals or revisions of one design. It extracts atomic claims from text, tables, charts and diagrams with a small vision model behind an OpenAI-compatible endpoint, pairs related claims, and reports differences with provenance back to the page and region each claim came from. It never ranks proposals, and it never treats a missing counterpart as proof of absence.

## Status

**v0.2.0** (tagged) compares two PDFs. It's a runnable baseline, not yet validated against a real model; see [limitations](docs/limitations.md).

A generalized design is planned and not yet implemented: sources as folders and zip archives, a persistent resumable store, more formats (`.docx`, `.pptx`, spreadsheets), criteria-first comparison of two or more sources, consistency checks and RAG export. See [docs/plans/](docs/plans/README.md).

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

Open `result/report.html`, keeping its `assets/` folder alongside it. Machine-readable results are in `report.json`; each document's extracted evidence and coverage are in `evidence-A.json` and `evidence-B.json`.

For revisions, supply the old PDF first. `--plan` estimates the work without calling the model:

```bash
pdf-semantic-diff old.pdf new.pdf --mode revisions --out revision-diff
pdf-semantic-diff old.pdf new.pdf --plan
```

Exit codes: `0` complete (uncertainty may remain); `2` incomplete coverage or processing failures; `1` fatal input or configuration error. Rerunning into the same output folder reuses cached model responses.

## Documentation

| Document | Contents |
| --- | --- |
| [How it works](docs/how-it-works.md) | Claims, the extraction and comparison pipeline, modes, code map |
| [Configuration](docs/configuration.md) | Endpoint, environment variables, settings, context budget, caching, exit codes |
| [Samples and testing](docs/samples-and-testing.md) | Running tests, the public sample corpus, synthetic samples, local embedding server |
| [Limitations](docs/limitations.md) | What the current release can't do, and what to review before relying on it |
| [Validation](docs/VALIDATION.md) | What has and hasn't been verified |
| [Plans](docs/plans/README.md) | Design plans for the generalized tool, with status |

## Tests

```bash
pip install -e '.[dev]'
python -m unittest discover -s tests -v
```
