# Samples and testing

## Tests and demo

The product is `src/semantic_pdf_diff`. The lab, how it's measured and improved (rounds, judges, review panels, spot checks, controlled documents, eye and page tests), is its own distribution in `lab/` (`semantic_pdf_diff_lab`), installed beside it. It adds its commands to `pdf-semantic-diff` through entry points. `tests/test_boundaries.py` keeps the product from importing it.

```bash
pip install -e '.[dev]' -e lab
python -m unittest discover -s tests -v
QUICK=1 python -m unittest discover -s tests    # skips the slowest tests (marked @slow): for iterating, not for commits
python scripts/run_tests.py                     # the same suite, one module per process on every CPU: about 2.5 minutes
python examples/demo.py
```

Tests use a local HTTP stub, temporary PDFs and controlled evidence. They exercise cross-format and many-to-one retrieval, case-sensitive unit conversion, uncertainty gates, UTF-8 chunking, text grouping and refinement, table column splitting, tile spacing and coverage, rotated pages, visual quote checks, malformed/truncated/null API output, `Retry-After`, claim salvage, caching, budgets, quote validation and HTML escaping. Synthetic spreadsheet tests check that the generated messy samples match their answer keys; they need the `dev` extra and are skipped without it. None of this establishes real-model extraction accuracy; see [VALIDATION.md](VALIDATION.md) and the [evaluation plan](plans/evaluation-benchmarks-2026-09-23.md).

`examples/demo-output/report.html` is an explicitly hand-authored fixture report; it makes no API calls.

## Public sample corpus

A public test corpus of competing proposals and design revisions can be downloaded into the git-ignored `samples/` folder. Every file is checked against a pinned SHA-256 hash, and TLS is always verified:

```bash
python scripts/fetch_samples.py --list      # sets, sizes, sources and terms
python scripts/fetch_samples.py             # default sets (~150 MB)
python scripts/fetch_samples.py --all --make-zips
```

| Set | Contents |
| --- | --- |
| `solar-decathlon-2013` | Four competing house designs, one folder per team (drawings, project manual, jury score sheets), plus shared rules |
| `wind-reference-turbines` | Three reference turbine designs with PDF reports and `.xlsx` data, plus an older spreadsheet revision |
| `ietf-quic-transport` | Plain-text draft revisions through RFC 9000 |
| `3gpp-ts38300-revisions` | Zipped `.docx` revisions of a 5G specification (one legacy `.doc`) |
| `3gpp-ran1-beam-management` | Four companies' competing `.docx` proposals plus moderator summaries |
| `3gpp-rel19-aiml-views` | Nine companies' competing views in `.pptx`, `.docx` and PDF |
| `archive-edge-cases` | Nested zips |
| `nasa-flagship-concepts` (optional, ~320 MB) | Competing mission-concept reports, interim and final |

The 3GPP files are kept as downloaded zips, since zips are meant to be read as folders. Sources and terms are in `scripts/samples.json`. For example:

```bash
pdf-semantic-diff samples/wind-reference-turbines/nrel-5mw/NREL-5MW-reference-turbine.pdf \
  samples/wind-reference-turbines/iea-15mw/IEA-15MW-reference-turbine.pdf --plan
```

## Recorded answers (replay fixtures)

Recorded model answers let the real pipeline run offline. A query is named by the hash of what reaches the model, so a changed query is a miss, never a stale answer. The design is in [decisions 0006 to 0010](decisions/README.md).

- **The committed fixture:** `tests/fixtures/replay-slices.zip`, answers from `google/gemma-4-31B-it` (DeepInfra) for the development runs in `scripts/slices.json`.
- **Slices:** page ranges cut from the public samples, byte-identical for the PyMuPDF version pinned in `slices.json`. `make_slices.py` says so when bytes differ.
- **What a fixture holds:** `pdf-semantic-diff fixtures summary FILE` lists answers per responder, role and outcome, tokens, and the PyMuPDF version it was recorded with.

```bash
python scripts/fetch_samples.py --set wind-reference-turbines --set solar-decathlon-2013 --set nasa-flagship-concepts
python scripts/make_slices.py                                  # writes samples/slices/
python -m unittest discover -s tests -p test_replay_slices.py  # the first three development runs, about 100 s
```

The replay test skips without the slices, when the fixture was recorded from other slices, or under a PyMuPDF version other than the fixture's, since text and renderings may differ. `REPLAY_ALL=1` replays every run the fixture holds rather than the first three: the committed fixture holds the development runs, and held-out runs are recorded into local fixtures only.

**Recording** calls the model configured through `OPENAI_*` and costs money. `scripts/record_runs.py` runs the slice runs live with a fixture attached:

```bash
python scripts/record_runs.py --fixture tests/fixtures/slices.sqlite --set dev \
    --ledger benchmarks/ledger.jsonl --tag step=record --max-cost 1
python scripts/record_runs.py --replay --fixture tests/fixtures/replay-slices.zip --out benchmarks/runs/baseline
```

- **Into a working `.sqlite`** (git-ignored under `tests/fixtures/`). A `.zip` is for replay only.
- **Modes:** by default `record-new`, which asks only what was never asked: the model's failures replay as failures, and transient ones (timeouts, server errors) are asked again. `--retry-failures` uses `replay-or-record`, which asks recorded failures again too. `--replay` asks nothing and fails on anything unrecorded.
- **Resumable:** a rerun replays what's recorded. At `--max-cost` it stops with exit code 3.
- **Variants:** `--variant FILE` merges a settings JSON over the base settings. Every setting that can change a query is saved, resolved, in `<out>/settings.json`.

**After a prompt or lever change, top up, prune and pack:**

1. **Start from a working copy.** A packed zip holds one SQLite file: `unzip tests/fixtures/replay-slices.zip -d tests/fixtures` gives `tests/fixtures/ci2.sqlite`. Keep its name, since the zip records it.
2. **Note the time,** then record the runs it serves into the working copy: `python scripts/record_runs.py --fixture tests/fixtures/ci2.sqlite --set dev`. Only changed queries are asked.
3. **Prune:** `pdf-semantic-diff fixtures prune tests/fixtures/ci2.sqlite --unused-since TIME` drops answers no run used since then (`--dry-run` previews). Unless `--force` is given, it refuses when no run used the fixture since then, when a run missed requests, or when more than half the answers would go.
4. **Pack:** `pdf-semantic-diff fixtures pack tests/fixtures/ci2.sqlite tests/fixtures/replay-slices.zip`. Packing is reproducible: last-use times aren't packed, so the zip's bytes change only when answers do.

## Synthetic samples

Deliberately messy synthetic spreadsheets (several tables on one sheet, multi-row headers, value/uncertainty pairs, a formula without a cached value, a hidden superseded sheet, a long list that must not be sampled), each with an answer key describing its true layout:

```bash
pip install -e '.[dev]'
python scripts/make_synthetic_samples.py    # writes samples/synthetic/
```

## Local embedding server

For retrieval development, `scripts/embedding_server.sh` runs any of the in-house embedding models locally on CPU (Hugging Face text-embeddings-inference in Docker), bound to localhost, with an OpenAI-compatible `/v1/embeddings` endpoint:

```bash
scripts/embedding_server.sh start                                   # all-MiniLM-L6-v2 on port 8081
scripts/embedding_server.sh start intfloat/multilingual-e5-small 8082
scripts/embedding_server.sh stop
```

The current release doesn't use embeddings yet; see the [retrieval plan](plans/retrieval-recall-2026-09-23.md).
