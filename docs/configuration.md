# Configuration (v0.2.0)

## Endpoint

When no environment variable or override is supplied, the default endpoint is `http://localhost:8000/v1`. `gemma-4` is only a configurable model identifier, not a claim that OpenAI hosts that model. The server must support Chat Completions with base64 PNG `image_url` inputs and JSON text responses. Use your provider's actual model identifier. API credentials come only from `OPENAI_API_KEY` and are not written to output. A warning is printed if the key would be sent over plain HTTP to a non-local host, and credentials embedded in `base_url` are redacted from reports.

## Precedence and environment variables

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

## Settings

Settings are in `config.example.json`; all omitted settings have defaults in `models.py`.

- `response_format` is `none` by default because some compatible servers do not support it; `json_object` requests JSON mode and `json_schema` sends the response schema for guided decoding (vLLM, llama.cpp, and similar), which is strongly recommended for small models where supported. The 0.1 `json_mode: true` setting still maps to `json_object`.
- `temperature` defaults to `0` for reproducibility (set `null` to use the server default), and `seed` is sent when set.
- Set `max_token_field` to `max_completion_tokens` if your server requires it.
- `section_depth` (default 2) sets how many outline levels become sections; `section_pages` (default 20) sets the page-range size for PDFs without an outline. Both affect prompts, so changing them needs `--reset` on an existing store.
- `--no-vision` is a deliberately incomplete text-only run, recorded as such.

## Context budget

Defaults target an 8,192-token context. No request contains a whole PDF; even a native text block is split. The adapter budgets UTF-8 text bytes conservatively, adds configurable image-token estimates, reserves output and safety capacity, then refuses an oversized request. If your server offers a larger window, raise `context_tokens` to match; chunk sizes (`text_bytes`, tile size) are separate settings.

**Image token accounting is backend-specific.** `image_tokens` must be a conservative upper bound for one image at `image_side`. It is not an exact tokenizer. Calibrate against your serving backend before large runs. For a smaller context, reduce `output_tokens`, `text_bytes`, `image_side` and tile size together, and adjust image-token estimates according to the actual backend. Two-image comparison requests may still exceed budget and will be reported as uncertain; `verify_visuals: false` allows text-claim comparison at the cost of skipping direct visual reinspection.

## Calls, caching and exit codes

A typical page needs multiple calls, so large PDFs can require hundreds or thousands. Calls are sequential to avoid overwhelming a small-model server; `Retry-After` on 429/503 responses is honoured (capped at 60 s). `--plan` makes no API calls and counts initial visual tasks; text, table, comparison, retries and refinement calls are additional. `--max-calls` caps actual HTTP attempts for one invocation, including retries.

The `--out` folder is an evidence store: `store.sqlite` (sources, files, content, evidence, coverage, cached model responses, comparisons) plus `assets/` for rendered crops. Stores are created with owner-only permissions and are as sensitive as the documents they were built from.

- **Reuse and resume:** content already extracted is loaded from the store. Evidence and coverage are written task by task, and model responses are cached by the meaning of each request (content, task, input), so an interrupted run resumes by replaying cached answers. Tasks that failed (e.g. hitting `--max-calls`) are retried on the next run.
- **One writer:** a second process writing to the same store gets a "store is in use" error.
- **Binding:** the store records its extraction interpreter (model, prompts, output-affecting settings, library versions). A run with a different one is refused with the differences listed. `--reset` clears only the affected derived data (for example, a changed tile size clears only image-based evidence) and all comparisons; `--reset --dry-run` shows what would be cleared. Timeouts, retries, call limits, credentials and the endpoint URL don't count. Keep model identifiers versioned when deployed weights change; the store can't detect a silent weight swap.
- **Schema changes** during development aren't migrated: an older store refuses to open; use a new folder.
- **`cache_check`** (off by default) is a debugging aid: a cache hit whose stored request bytes differ from the current request raises an error instead of being served.

Exit codes: `0` processing complete (semantic uncertainty may remain); `2` incomplete source coverage, a comparison processing failure, no extracted claims on either side, or pair-limit truncation; `1` fatal input/configuration error. Inspect the JSON and coverage ledger regardless of exit code.
