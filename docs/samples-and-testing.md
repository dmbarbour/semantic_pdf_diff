# Samples and testing

## Tests and demo

```bash
pip install -e '.[dev]'
python -m unittest discover -s tests -v
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
