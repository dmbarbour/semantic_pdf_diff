# Limits and engineering review (v0.2.0)

- This is a runnable baseline, not a validated engineering sign-off system. No real VLM was available during development; evaluate against labeled representative PDFs before relying on findings. Measuring accuracy is planned in [plans/evaluation-benchmarks-2026-09-23.md](plans/evaluation-benchmarks-2026-09-23.md).
- Small models may misread dense diagrams, arrow direction, legends, log axes and merged table headers. Overview context can help but does not solve arbitrary cross-page relationships. No local OCR engine, engineering solver, graph-isomorphism engine or full table reconstruction is included.
- Table extraction treats the first row as a provisional header; repeated/multilevel headers and continued tables need review. Tiling may separate legends or labels; partial findings remain visible.
- Sparse retrieval can miss semantic equivalents with no shared terms. Domain aliases help; candidate recall is not guaranteed. Increase `top_k` / lower `min_score` for recall, and inspect unmatched evidence. Very generic claims can make retrieval expensive.
- Only a small explicit set of units is normalized, case-sensitively (`mW` ≠ `MW`); case variants are accepted only where unambiguous (e.g. `KW`). Ranges, inequalities, currencies, affine temperatures, ambiguous units and approximate readings abstain from deterministic numeric comparison. Numerical equality does not prove semantic equivalence.
- Model confidence is uncalibrated. Reinspection by the same model is not independent verification. No automatic importance ranking or inferred project impact is presented.
- Evidence from native and visual passes may duplicate or disagree. IDs and source kinds preserve those observations; they are not silently fused into one authoritative fact.
- PDF bytes are processed locally; source text and rendered crops are sent to the configured endpoint. The generated report has no external resources. PDF contents are treated as data, and the model has no execution tools.
- Output folders (evidence, cache, crops, reports) are as sensitive as the input PDFs.
- PyMuPDF has its own licensing terms; review the dependency's AGPL/commercial licensing for your distribution model.
