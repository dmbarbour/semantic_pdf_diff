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

### 2. `export`: RAG ingestion

Claims are good retrieval units but lossy, so export both:

- **source chunks** (text groups, table rows, visual region descriptions) with locators
- **claims** linked to their chunks, with locator, quality signals and stable IDs

Stable, content-addressed IDs allow incremental re-ingestion: only changed sources produce new records. JSONL first; target a specific schema only once there is a concrete consumer.

### 3. Fact sheet, built without the model (first-tier overview)

Claims grouped by entity and topic, showing values, conditions and provenance links. Nothing is generated, so there is nothing to hallucinate, which fits the project's evidence-first approach. Rendered as HTML alongside the existing report.

### 4. Cited summaries (second tier, tentative)

A model-written overview for humans, produced by map-reduce within the small context window: section summaries, then topic summaries.

- **Every sentence cites evidence IDs.** Citations are checked mechanically: the cited claims must exist, and any values stated must appear in them.
- It is clearly labelled as generated and optional. It is the project's first *global* generated text, which the README currently avoids on purpose.
- Build it only after the fact sheet shows what readers actually want.

## Milestones

1. `check` subcommand and report view.
2. `export --format jsonl` (chunks plus claims).
3. HTML fact sheet.
4. (Tentative) cited summaries with citation verification.

## Open questions

- Is there a target RAG system or schema?
- Is a structured fact sheet enough for human readers, or is prose needed?
