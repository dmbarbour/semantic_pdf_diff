# Robustness baseline (0.2.0)

- **Status:** Completed 2026-09-23 (commit `50e74cb`). The stable baseline is tagged `v0.2.0`.
- **Scope:** Fix correctness and robustness problems found in a review of 0.1.1 before generalizing the project.

## Why

The 0.1.1 code was a sound evidence-first design, but a review found bugs that could abort real runs or silently corrupt evidence, plus avoidable cost. We wanted a solid baseline before the generalization plans in this folder.

## What changed

Bugs fixed:

- **API response shapes.** `usage: null`, `content: null`, missing `choices`, or a reply that isn't a JSON object raised an uncaught `AttributeError` that crashed the whole run. These are now retryable model failures. Fenced or prose-wrapped JSON is accepted.
- **Table refinement.** Retrying a partial table row byte-split the serialized `Header/Row` text, separating the header from its values. Rows are now split by column, repeating the header and column 0 (a provisional row label). Oversized rows are split instead of skipped.
- **Table quote check.** Quotes spanning adjacent cells (`Pump 10 kW`) were rejected because they were checked against JSON text. They are now accepted.
- **Unit case folding.** `mW` was read as megawatts, `mPa` as megapascals, `S` as seconds and `M` as metres. Unit matching is now case-sensitive, with case variants accepted only where unambiguous.
- **De-duplication.** Refined tile sources escaped de-duplication. Claims are now de-duplicated per page within two families, *native* (text and tables) and *visual* (tiles and overview).
- A non-object config file is now a clean error, and the broad `except` covers only table detection.

Cost and quality:

- Consecutive text blocks are grouped up to `text_bytes`, keeping per-block bounding boxes; retries split on block boundaries.
- Tiles are evenly spaced (same count at default settings, but no near-duplicate rows). Tiles run before the overview, so higher-resolution crops win de-duplication.
- Visual quotes are checked against the PDF text layer and recorded as `quote_verified` (flagged in the report, not rejected).
- Partially malformed extractions keep their valid claims; the task is marked partial.
- New settings: `response_format` (`none` / `json_object` / `json_schema`), `temperature` (default 0) and `seed`. The legacy `json_mode` still works.
- `Retry-After` is honoured. There is a warning when an API key would be sent over plain HTTP to a remote host, and `base_url` credentials are redacted in reports.

Housekeeping: `import pymupdf` (PyMuPDF ≥ 1.24.3), 25 new regression tests (38 total), and updated docs. Prompt changes invalidate 0.1 caches.

## Known limits carried forward

- Nothing here measures real-model extraction accuracy; see [evaluation-benchmarks](evaluation-benchmarks-2026-09-23.md).
- At default `tile_points` (420), a US Letter page still needs 6 tiles; about 440 would give 4.
