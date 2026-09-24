# Semantic PDF Diff

A Python CLI for evidence-first comparison of competing engineering proposals or revisions of one design. It uses an OpenAI-compatible vision model endpoint, with no frontier model, embedding API, or whole-document model call.

## Run

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

Open `result/report.html`. Keep its `assets/` folder alongside it. Machine-readable results are in `report.json`; independently extracted evidence and coverage are in `evidence-A.json` and `evidence-B.json`.

When no environment variable or override is supplied, the default endpoint is `http://localhost:8000/v1`. `gemma-4` is only a configurable model identifier, not a claim that OpenAI hosts that model. The server must support Chat Completions with base64 PNG `image_url` inputs and JSON text responses. Use your provider's actual model identifier. API credentials come only from `OPENAI_API_KEY` and are not written to output.

For revisions, supply the old PDF first:

```bash
pdf-semantic-diff old.pdf new.pdf --mode revisions --config config.example.json --out revision-diff
pdf-semantic-diff old.pdf new.pdf --config config.example.json --plan
```

`--plan` makes no API calls and counts initial visual tasks; text, table, comparison, retries and refinement calls are additional. `--max-calls` caps actual HTTP attempts for one invocation, including retries. Rerun using the same output directory to reuse successful cached responses. Do not run concurrent processes into the same output directory.

## Environment configuration

Configuration precedence, highest first: **CLI flags > JSON config file > environment variables > built-in defaults**. You can normally run just `pdf-semantic-diff a.pdf b.pdf` after setting your environment. A config file only overrides fields it contains; the example config intentionally omits model and endpoint so it works with your environment.

| Environment variable | Setting |
| --- | --- |
| `OPENAI_API_KEY` | API authentication (never included in settings/reports) |
| `OPENAI_BASE_URL` | Chat Completions API base URL, including `/v1` when required |
| `OPENAI_MODEL` | Your provider's vision model identifier |
| `PDF_DIFF_CONTEXT_TOKENS` | Context budget |
| `PDF_DIFF_OUTPUT_TOKENS` | Output reserve |
| `PDF_DIFF_IMAGE_TOKENS` | Per-image budget estimate |
| `PDF_DIFF_MAX_CALLS` | HTTP attempt limit |
| `PDF_DIFF_TIMEOUT` | HTTP timeout in seconds |
| `PDF_DIFF_TOP_K` | Retrieval candidates per direction |
| `PDF_DIFF_VISION` | Enable visual extraction (`true` or `false`) |
| `PDF_DIFF_VERIFY_VISUALS` | Reinspect source images in comparisons |
| `PDF_DIFF_ALIASES` | JSON object mapping domain aliases to canonical names |

Every other field in `Settings` follows `PDF_DIFF_<UPPERCASE_FIELD_NAME>` (for example `PDF_DIFF_TEXT_BYTES`, `PDF_DIFF_RETRIES`, `PDF_DIFF_RESPONSE_FORMAT`). Model and base URL use only the `OPENAI_*` names above. `OPENAI_MODEL` and the `PDF_DIFF_*` names are application conventions. Empty or whitespace-only setting variables are treated as unset; invalid active values fail validation. Explicit overrides take precedence even over invalid environment values. Export variables through your shell or process manager; `.env` files are not loaded automatically.

For Python callers, use `Settings.from_env(...)` to get the same environment defaults with explicit keyword overrides. Plain `Settings(...)` remains deterministic and does not consult the environment. Output paths, comparison mode and planning remain CLI options.

## What it compares

All modalities become atomic claims with `entity`, `attribute`, `value`, `unit`, `conditions`, `kind`, `quote`, `confidence` and `approximate`. Every claim receives a stable evidence ID, document label, one-based page and source bounding box in unrotated PDF points. Visual claims retain the exact PNG the model saw. A chart operating point can therefore match a table row, and a diagram connection can match a sentence.

1. **Native extraction:** Consecutive PDF text blocks are grouped up to the UTF-8 byte budget (oversized blocks are split), so headings and short labels travel with their context; each claim keeps the bounding box of the block containing its quote. Detected tables are sent row by row with the first row repeated as a provisional header; rows over budget are split by column, repeating the header and the first column as a provisional row label. Native claims whose supporting quotes are absent from the input are rejected; table quotes may span adjacent cells.
2. **Visual extraction:** Every page receives evenly spaced overlapping tiles (at least 18% overlap) and an overview. This includes scanned pages and vector diagrams that embedded-image extraction would miss. The same small model reads labels, graph axes and series, table relationships and diagram connections. Approximate graph readings remain explicitly approximate. Where the rendered region has a PDF text layer, each visual quote is checked against it and the result is recorded as `quote_verified` (`false` flags a possible misread or a raster-only label; it does not reject the claim).
3. **Bounded refinement:** Partial/failed text groups are split on block boundaries (single blocks by bytes); partial/failed table rows are split by column, keeping header and row label; partial/failed visual tiles are subdivided. All are bounded by `refinement_depth`. Original failures remain in the coverage ledger even if smaller tasks succeed. Nothing silently declares exhaustive coverage.
4. **Global retrieval:** Sparse TF-IDF over normalized claim entities, attributes, conditions and values generates a bidirectional top-k union. Claims can match across pages, order, layout and modality, with one-to-many matches. User-provided domain aliases improve synonym recall. No model holds the full corpus.
5. **Local comparison:** One claim pair per request, with source images where available. The model distinguishes equivalent, different, complementary, unrelated and uncertain. A deterministic decimal calculator checks supported unit conversions. Unestablished conditions, approximate readings, low confidence or inconsistent arithmetic veto confident difference/equivalence judgments.
6. **Review report:** Filter/search findings, inspect both sources, review numeric checks, unmatched evidence, provenance and task-level coverage. No model-generated global summary is needed.

Proposal mode is symmetric and does not rank teams. Revision mode labels A as earlier and B as later; numeric deltas are B minus A. Neither mode calls unmatched evidence a proven addition/deletion. Absence is harder to establish than a local difference.

## Working with a small context window

Defaults target an 8,192-token context. No request contains a whole PDF; even a native text block is split. The adapter budgets UTF-8 text bytes conservatively, adds configurable image-token estimates, reserves output and safety capacity, then refuses an oversized request. Model output is validated; unknown keys are ignored, individually malformed claims are discarded (the task is then marked partial), and malformed/truncated responses are retried and ultimately recorded as failures. Fenced or prose-wrapped JSON is accepted. Exact duplicate claims within the native or the visual passes on one page are kept once.

**Image token accounting is backend-specific.** `image_tokens` must be a conservative upper bound for one image at `image_side`. It is not an exact tokenizer. Calibrate against your serving backend before large runs. For a smaller context, reduce `output_tokens`, `text_bytes`, `image_side` and tile size together, and adjust image-token estimates according to the actual backend. Two-image comparison requests may still exceed budget and will be reported as uncertain; `verify_visuals: false` allows text-claim comparison at the cost of skipping direct visual reinspection.

Settings are in `config.example.json`; all omitted settings have defaults in `models.py`. `response_format` is `none` by default because some compatible servers do not support it; `json_object` requests JSON mode and `json_schema` sends the response schema for guided decoding (vLLM, llama.cpp, and similar), which is strongly recommended for small models where supported. The 0.1 `json_mode: true` setting still maps to `json_object`. `temperature` defaults to `0` for reproducibility (set `null` to use the server default) and `seed` is sent when set. Set `max_token_field` to `max_completion_tokens` if your server requires it. `--no-vision` is a deliberately incomplete text-only run, recorded as such.

A typical page needs multiple calls, so large PDFs can require hundreds or thousands. Calls are sequential to avoid overwhelming a small-model server; `Retry-After` on 429/503 responses is honoured (capped at 60 s). The cache key includes endpoint, model, prompt, image bytes, response schema and output/sampling parameters. Keep endpoint/model identifiers versioned when changing deployed weights; otherwise clear `cache/`. Cache entries contain extracted document information.

Exit codes: `0` processing complete (semantic uncertainty may remain); `2` incomplete source coverage, a comparison processing failure, no extracted claims on either side, or pair-limit truncation; `1` fatal input/configuration error. Inspect the JSON and coverage ledger regardless of exit code.

## Test and demo

```bash
python -m unittest discover -s tests -v
python examples/demo.py
```

Tests use a local HTTP stub, temporary PDFs and controlled evidence. They exercise cross-format and many-to-one retrieval, case-sensitive unit conversion, uncertainty gates, UTF-8 chunking, text grouping and refinement, table column splitting, tile spacing and coverage, rotated pages, visual quote checks, malformed/truncated/null API output, `Retry-After`, claim salvage, caching, budgets, quote validation and HTML escaping. They do not establish real-model extraction accuracy. `examples/demo-output/report.html` is an explicitly hand-authored fixture report; it makes no API calls.

## Sample documents

A public test corpus of competing proposals and design revisions can be downloaded into the git-ignored `samples/` folder. Every file is checked against a pinned SHA-256 hash, and TLS is always verified:

```bash
python scripts/fetch_samples.py --list      # sets, sizes, sources and terms
python scripts/fetch_samples.py             # default sets (~120 MB)
python scripts/fetch_samples.py --all --make-zips
```

Default sets: `solar-decathlon-2013` (four competing house designs, one folder per team), `wind-reference-turbines` (three reference turbine designs with PDF reports and `.xlsx` data) and `ietf-quic-transport` (plain-text draft revisions through RFC 9000). `nasa-flagship-concepts` (~320 MB of competing mission-concept reports) is optional. Sources and terms are in `scripts/samples.json`. For example:

```bash
pdf-semantic-diff samples/wind-reference-turbines/nrel-5mw/NREL-5MW-reference-turbine.pdf \
  samples/wind-reference-turbines/iea-15mw/IEA-15MW-reference-turbine.pdf --plan
```

## Limits and engineering review

- This is a runnable baseline, not a validated engineering sign-off system. No real VLM was available during development; evaluate against labeled representative PDFs before relying on findings.
- Small models may misread dense diagrams, arrow direction, legends, log axes and merged table headers. Overview context can help but does not solve arbitrary cross-page relationships. No local OCR engine, engineering solver, graph-isomorphism engine or full table reconstruction is included.
- Table extraction treats the first row as a provisional header; repeated/multilevel headers and continued tables need review. Tiling may separate legends or labels; partial findings remain visible.
- Sparse retrieval can miss semantic equivalents with no shared terms. Domain aliases help; candidate recall is not guaranteed. Increase `top_k` / lower `min_score` for recall, and inspect unmatched evidence. Very generic claims can make retrieval expensive.
- Only a small explicit set of units is normalized, case-sensitively (`mW` ≠ `MW`); case variants are accepted only where unambiguous (e.g. `KW`). Ranges, inequalities, currencies, affine temperatures, ambiguous units and approximate readings abstain from deterministic numeric comparison. Numerical equality does not prove semantic equivalence.
- Model confidence is uncalibrated. Reinspection by the same model is not independent verification. No automatic importance ranking or inferred project impact is presented.
- Evidence from native and visual passes may duplicate or disagree. IDs and source kinds preserve those observations; they are not silently fused into one authoritative fact.
- PDF bytes are processed locally; source text and rendered crops are sent to the configured endpoint. A warning is printed if an API key would be sent over plain HTTP to a non-local host, and credentials embedded in `base_url` are redacted from reports. The generated report has no external resources. PDF contents are treated as data, and the model has no execution tools.
- PyMuPDF has its own licensing terms; review the dependency's AGPL/commercial licensing for your distribution model.

## Code map

| Module | Responsibility |
| --- | --- |
| `models.py` | Validated settings and evidence schemas |
| `llm.py` | Compatible API transport, request budgeting, retries and cache |
| `extract.py` | PDF text/tables, page/tile rendering, refinement and provenance |
| `compare.py` | Retrieval, local reasoning and numeric checks |
| `report.py` | Escaped HTML and JSON reports |
| `cli.py` | Orchestration, planning and exit semantics |

API contracts were checked against the [OpenAI Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create) and [PyMuPDF Page documentation](https://pymupdf.readthedocs.io/en/latest/page.html). Provider compatibility still needs a live smoke test.
