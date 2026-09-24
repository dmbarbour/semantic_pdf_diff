# Single-project outputs: consistency check, RAG export, overviews

- **Status:** Planned (consistency check and export); Tentative (model-written summaries)
- **Depends on:** [projects-and-evidence-store](projects-and-evidence-store-2026-09-23.md)

## Goal

Much of the pipeline is useful for **one project** on its own: extracted, provenance-tracked claims plus a coverage record. Expose that directly.

## Features

### 1. `check`: internal consistency

Run the existing comparison with A = B = one project, excluding pairs of a claim with itself. It surfaces contradictions inside a project, such as:

- pump power 10 kW in §2 but 12 kW in Appendix C
- a spreadsheet total that disagrees with the narrative
- a diagram connection that contradicts the text

It reuses retrieval, the numeric check and the uncertainty rules unchanged. For a single-team review this is arguably more useful than comparing two teams. Duplicate claims (the same fact from the native and visual passes, or repeated across files) should show as *equivalent* support, not noise.

### 2. `export`: RAG ingestion as Markdown chunks

The target RAG system is not ours to change. Its ingest tool accepts PDF, Markdown, text, `.docx`, `.pptx`, `.xlsx`, CSV and JSON (not JSONL). It preserves provenance poorly, ignores its `--metadata` argument in practice, handles spreadsheets badly and loses the meaning of diagrams. So the export is **a folder of explicit, self-contained Markdown chunk files**, one per chunk, designed so each survives ingestion on its own:

- **Provenance in the text, not in metadata.** Each chunk states in prose where it came from: source, file path, page or slide or cell range, section heading path, and a short content ID for exact tracing. A human-readable citation line ("PS-3 design summary.pdf, p. 12, Table 3") is included so RAG answers can quote it.
- **Small and self-contained.** Chunks are kept below a configurable size so the ingest tool is unlikely to split them. If it splits anyway, a compact provenance line is repeated before each subsection, so no fragment loses its origin.
- **Tables inline, as small Markdown tables** with their headers and units, instead of separate CSV or `.xlsx` files the ingest tool would mangle. Large tables are split into chunks that each repeat the header and table identity.
- **Diagrams and charts as text.** Claims from visual extraction (connections, operating points, axis readings, flagged approximations) are written out in words. That preserves exactly what the ingest tool would lose.
- **Qualifiers kept with the facts:** conditions, basis (measured, projected, required…), stated uncertainty, derivation (direct read, model extraction, summary of summaries), quote-verification status and any issues or suspicions. Confidence appears as the qualifier it is, not as a bare number presented as truth.
- **Stable file names** derived from content and section IDs, so re-exporting after a change replaces the same files and adds or removes only what changed.
- **An `index.md`** listing every chunk with its citation, plus a note on how the export was produced (tool version, interpreters, coverage summary including what wasn't reached or was skipped).

Chunk granularity is selectable:

- **per section** (the default): the section's "about" statement, its claims with qualifiers, and short verbatim excerpts supporting them
- **per topic or entity:** fact-sheet style, gathering claims about one subject across files, each with its own citation
- **per finding:** for `check` and comparison results, one finding per chunk with both sides' evidence

An example chunk:

```markdown
# Pump schedule — PS-3 design summary.pdf, p. 12

Source: PS-3 (folder) / design/PS-3 design summary.pdf, page 12, Table 3 "Pump schedule".
Section: 4 Mechanical > 4.2 Pumps. Content sha256:3f7ffce6….pdf.

| Tag | Duty | Flow (L/s) | Head (m) | Motor power (kW) |
|---|---|---|---|---|
| P-301 | Duty | 60 | 25.5 | 22 |
| P-303 | Standby | 60 | 25.5 | 22 |

- P-301 rated flow: 60 L/s at 25.5 m head. Basis: specified. Uncertainty: none given.
  Derivation: model reading of a native PDF table; quote verified in text layer.

Cite as: PS-3 design summary.pdf, p. 12, Table 3.
```

A JSON rendering of the same records (an array, since JSONL isn't accepted) is a cheap secondary option for tools that want structure, but Markdown is the primary target.

### 3. Fact sheet, built without the model (first-tier overview)

Claims grouped by entity and topic, showing values, conditions and provenance links. Nothing is generated, so there is nothing to hallucinate, which fits the project's evidence-first approach. Rendered as HTML alongside the existing report.

### 4. Cited summaries (second tier, tentative)

A model-written overview for humans, produced by map-reduce within the small context window: section summaries, then topic summaries.

- **Every sentence cites evidence IDs.** Citations are checked mechanically: the cited claims must exist, and any values stated must appear in them.
- It is clearly labelled as generated and optional. It is the project's first *global* generated text, which the README currently avoids on purpose.
- Build it only after the fact sheet shows what readers actually want.

## Milestones

1. `check` subcommand and report view.
2. `export` as Markdown chunks (per section first, then per topic and per finding), with `index.md`; optional JSON array.
3. HTML fact sheet.
4. (Tentative) cited summaries with citation verification.

## Decisions (2026-09-23)

- **RAG target:** an external system with a fixed ingest tool (PDF, Markdown, text, `.docx`, `.pptx`, `.xlsx`, CSV, JSON; no JSONL; metadata ignored). Export explicit, self-contained Markdown chunks with provenance, tables, qualifiers and notes written into the text.

## Open questions

- **How does the ingest tool chunk and update?** Its splitting size and whether re-ingesting a file with the same name replaces the old one are unknown. Measure both with a small trial export, then set default chunk sizes and naming accordingly.
- **Do RAG answers actually surface the in-text citation?** Check with a few queries after a trial ingestion; adjust citation wording and placement if not.
- Is a structured fact sheet enough for human readers, or is prose needed?
