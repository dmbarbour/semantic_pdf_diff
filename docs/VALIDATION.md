# Validation

Forty-two automated tests passed on Python 3.12 with PyMuPDF 1.28.2, Pydantic 2.13.5 and openpyxl 3.1.5. The thirty-eight core tests also passed on Python 3.10 with the minimum supported PyMuPDF 1.24.3 and Pydantic 2.7.0; the four synthetic-spreadsheet tests need the `dev` extra and are skipped without it.

The end-to-end test creates temporary PDFs, sends native text and rendered images to a local HTTP stub, generates HTML/JSON, and reruns with zero additional HTTP calls because of caching. Other tests cover retrieval across modalities, many-to-one candidates, unit conversions, uncertainty gates, byte budgets, malformed/truncated responses, call limits, visual refinement, quote rejection and escaped report content.

The bundled demo is hand-authored synthetic evidence with fixture judgments. It is not a VLM accuracy evaluation. No live external model was called. Before deployment, measure extraction recall, candidate retrieval recall and difference precision on domain-specific labeled examples, especially dense charts, table continuations and diagram topology. How that will be measured is planned in [plans/evaluation-benchmarks-2026-09-23.md](plans/evaluation-benchmarks-2026-09-23.md).

Robustness tests cover null/missing/non-object API response fields, fenced or prose-wrapped JSON, `Retry-After`, request sampling and `response_format` options, salvage of partially valid extractions, case-sensitive units, even tile spacing, grouped text blocks with per-block provenance, block-boundary refinement, table column splitting that preserves header and row label, visual de-duplication across refinement, visual quote checks against the text layer, rotated-page coordinates and URL credential redaction.

Environment configuration tests verify typed parsing, API-key exclusion from serialized settings, empty-variable fallback, invalid-value handling and CLI > file > environment precedence.
