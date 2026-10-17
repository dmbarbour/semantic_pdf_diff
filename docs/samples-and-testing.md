# Samples and testing

## Tests and demo

The product is `src/semantic_pdf_diff`. The lab, how it's measured and improved (rounds, judges, review panels, spot checks, controlled documents, eye and page tests), is its own distribution in `lab/` (`semantic_pdf_diff_lab`), installed beside it. It adds its commands to `pdf-semantic-diff` through entry points. `tests/test_boundaries.py` keeps the product from importing it.

```bash
pip install -e '.[dev]' -e lab
python -m unittest discover -s tests -v
QUICK=1 python -m unittest discover -s tests    # skips the slowest tests (marked @slow): for iterating
python scripts/run_tests.py                     # the same suite, one module per process on every CPU: about 4.5 minutes
python examples/demo.py
```

**The commit gate** (`scripts/gate.py`; enabled in a checkout by `git config core.hooksPath scripts/hooks`):

- `scripts/run_tests.py` run over every module records a pass for the tree it tested: the working folder as git would commit it, untracked files included. A tree edited during the run gets no pass.
- A pre-commit hook lets a commit through when its staged tree has a recorded pass. Otherwise it checks the staged tree out into a temporary folder (with `samples/` linked in), runs the quick suite there (about 3 minutes), records the pass, and blocks the commit on a failure. A partial commit is tested as committed.
- `python scripts/gate.py status` says whether the working tree and the staged tree have passes.

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
| `wide-pages` (optional, ~145 MB) | Pages wider than bands serve, for tile selection: slide decks, landscape text pages, construction drawings and posters, split into `dev/` and a held-out test set, `heldout/` (measured only to check a change already chosen on `dev/`) |

The 3GPP files are kept as downloaded zips, since zips are meant to be read as folders. Sources and terms are in `scripts/samples.json`. For example:

```bash
pdf-semantic-diff compare samples/wind-reference-turbines/nrel-5mw/NREL-5MW-reference-turbine.pdf \
  samples/wind-reference-turbines/iea-15mw/IEA-15MW-reference-turbine.pdf --store wind-diff
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

1. **Start from a working copy.** A packed zip holds one SQLite file: `unzip tests/fixtures/replay-slices.zip -d tests/fixtures` gives `tests/fixtures/fixture.sqlite`. Keep its name, since the zip records it.
2. **Seed it, if a recording already holds the new answers** (a lever's measured arm, say): `pdf-semantic-diff fixtures merge tests/fixtures/fixture.sqlite ARM.sqlite` copies in the answers the working copy lacks, `.zip` or `.sqlite`, keeping those it holds. A query is named by what reaches the model, so a copied answer is the same model's answer to the same query. Copied answers count as unused until a run replays them.
3. **Note the time,** then record the runs it serves into the working copy: `python scripts/record_runs.py --fixture tests/fixtures/fixture.sqlite --set dev`. Only changed queries are asked.
4. **Prune:** `pdf-semantic-diff fixtures prune tests/fixtures/fixture.sqlite --unused-since TIME` drops answers no run used since then (`--dry-run` previews). Unless `--force` is given, it refuses when no run used the fixture since then, when a run missed requests, or when more than half the answers would go.
5. **Pack:** `pdf-semantic-diff fixtures pack tests/fixtures/fixture.sqlite tests/fixtures/replay-slices.zip`. Packing is reproducible: last-use times aren't packed, so the zip's bytes change only when answers do.

## Proving a refactor changes nothing

A refactor or performance change must leave every output as it was ([decision 0027](decisions/0027-behaviour-changes-apart-from-refactors.md)). Replay before and after the change, offline, and compare:

```bash
python scripts/refactor_check.py                    # the working tree against HEAD (about 5 minutes)
python scripts/refactor_check.py --against main~2   # against another revision; --only slices|controlled
```

- **What it replays:** the slices' development runs and the controlled corpus's standard and row-by-row runs, in the working tree and in the revision (checked out into a temporary git worktree, `samples/` linked in), all four at once. Each tree replays from its own fixtures, and nothing is asked of a model.
- **What it compares:** every report.json, whole, but for `created_at` and the tree's path. How each run went is in `run.json` beside it, not the report, and isn't compared. It exits 1 on any difference, listing each run and the fields that differ.
- **A request that isn't recorded fails the replay.** That alone shows a change reached the model; the check names the replay that failed and its log.
- **What the replays don't cover, compare directly:**
  - a renderer's pages, from the same report documents
  - the lab's outputs, regenerated byte for byte (`scripts/eye_test.py report`)
  - a rewritten pure function, against the old one on random inputs
- **Then the full suite:** `python scripts/run_tests.py`.

A changed output means a behaviour change. It goes in a fix of its own, with its test.

## Judging a lever

A lever changes some queries, and gemma-4 answers a changed query anew. A reworded image prompt moves facts both ways even at temperature 0: on 2026-10-14 a rule meant to do nothing ("Read the image carefully.") moved the corpus's relations read right 416 → 444, as far as the arrow rule it was a control for. Totals can't tell that churn from a gain. Arms on the controlled corpus are compared document by document instead:

```bash
python scripts/paired.py read/arrow --base read/base --null read/null --null read/null2 --target "relations reversed"
python scripts/paired.py read/lone --base read/base --target "claims right" --all
```

- **Arms share answers.** Each reads from a copy of the base's fixture, so a query a lever leaves alone replays its answer and moves nothing. Every compared setting is named in each arm.
- **Null arms for a lever that changes many queries.** A null arm changes the same queries to no purpose (a do-nothing rule of the same kind: `visual_rules` for an image rule, `extract_rules` for an instruction).
- **Target and guards, named first.** The target is the error the lever is for (reversed relations for an arrow rule, not relations right); the guard is facts read right.
- **The test:** each document's change, summed; a 90% interval from resampling documents; a two-sided sign-flip p-value (with no effect, either arm is as likely ahead on any document). Documents are the unit, since one query moves several of a document's facts.
- **The verdict** (`bench/paired.judge`): better when the target improves on the base and on every null arm at p < 0.1 and no guard is worse; worse when the target or a guard is worse on the base and on every null; otherwise no different.
- **What it can't see:** a change confined to one or two documents never reaches p < 0.1 (two documents can't go below 0.5), so a lever reaching few documents is judged by inspecting them.

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
