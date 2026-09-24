# Single-source outputs: consistency check, RAG export, overviews

- **Status:** Planned (consistency check and export); Tentative (model-written summaries)
- **Depends on:** [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md); uses section "about" statements from [scheduling-and-triage](scheduling-and-triage-2026-09-23.md) for per-section export chunks and fact-sheet context

## Goal

Much of the pipeline is useful for **one source** on its own: extracted, provenance-tracked claims plus a coverage record. Expose that directly.

## Features

### 1. `check`: internal consistency

Run claim-level comparison with A = B = one source, excluding pairs of a claim with itself. It surfaces contradictions inside a source, such as:

- pump power 10 kW in §2 but 12 kW in Appendix C
- a spreadsheet total that disagrees with the narrative
- a diagram connection that contradicts the text

It reuses retrieval, the numeric check and the uncertainty rules. Recognized disagreements are recorded as derived claims with their severity and the model's handling decision (e.g. an errata document supersedes the original), which may lower confidence in the claims involved; see *Disagreements are claims* in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md). For a single-team review this is arguably more useful than comparing two teams. Duplicate claims (the same fact from the native and visual passes, or repeated across files) should show as *equivalent* support, not noise.

### 2. `export`: RAG ingestion as Markdown chunks

The target RAG system is not ours to change. Its ingest tool accepts PDF, Markdown, text, `.docx`, `.pptx`, `.xlsx`, CSV and JSON (not JSONL). It preserves provenance poorly, ignores its `--metadata` argument in practice, handles spreadsheets badly and loses the meaning of diagrams. So the export is **a folder of explicit, self-contained Markdown chunk files**, one per chunk, designed so each survives ingestion on its own:

- **Provenance in the text, not in metadata.** Each chunk states in prose where it came from: source, file path, page or slide or cell range, section heading path, and a short content ID for exact tracing. It also carries **provenance of the source itself** from the source and file metadata (title, organization or team, author, revision label, date; see *Source metadata* in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md)), so the RAG system knows whose document and which revision a fact comes from. A human-readable citation line ("PS-3 design summary.pdf, p. 12, Table 3") is included so RAG answers can quote it.
- **Sized to the ingest tool's chunking.** The tool extracts text with `markitdown` and splits into chunks of 512 tokens with 128 tokens of overlap by default (configurable on its command line). Export chunks therefore target roughly 400 tokens by default (configurable), leaving margin for tokenizer differences, so each file normally becomes one RAG chunk. When a chunk must be longer, a compact provenance line is repeated before each subsection, so any 512-token window still names its origin. The provenance header costs roughly 50–80 tokens per chunk; worth it.
- **Tables inline, as small Markdown tables** with their headers and units, instead of separate CSV or `.xlsx` files the ingest tool would mangle. Large tables are split into chunks that each repeat the header and table identity.
- **Diagrams and charts as text.** Claims from visual extraction (connections, operating points, axis readings, flagged approximations) are written out in words. That preserves exactly what the ingest tool would lose.
- **Qualifiers kept with the facts:** conditions, basis (measured, projected, required…), stated uncertainty, derivation (direct read, model extraction, summary of summaries), quote-verification status and any issues or suspicions. Confidence appears as the qualifier it is, not as a bare number presented as truth. Relevant annotations travel too: provider-declared markings, recognized disagreements and their handling, and reviewer decisions such as criteria (see [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (*Annotations*)).
- **Unique file names.** Re-ingesting apparently aggregates rather than replaces, so every chunk file gets a unique name (derived from its content hash plus an export ID) and the user controls the corpus directly: ingest a fresh export into a new or reset corpus, or ingest a **delta export** containing only chunks not present in a named previous export. The delta's `index.md` also lists chunks that disappeared, for the user to act on.
- **Discovery chunks alongside detail chunks.** Besides chunks that explain content (comprehension), the export includes chunks that help find it (discovery): tables of topics, an entity index, an index of diagrams and charts with what each shows, and section maps. Each entry names the detail chunks' citations, so a RAG query about "what covers pump redundancy?" can land on an index and then on the facts.
- **An `index.md`** listing every chunk with its citation, plus a note on how the export was produced (tool version, interpreters, coverage summary including what wasn't reached or was skipped).

Chunk granularity is selectable:

- **per section** (the default): the section's "about" statement, its claims with qualifiers, and short verbatim excerpts supporting them
- **per topic or entity:** fact-sheet style, gathering claims about one subject across files, each with its own citation
- **per finding:** for `check` and comparison results, one finding per chunk with both sides' evidence

An example chunk:

```markdown
---
title: "Pump schedule — PS-3 design summary.pdf, p. 12"
author: "Team A (PS-3 design consultant)"
source: "PS-3"
revision: "Rev C"
---
# Pump schedule — PS-3 design summary.pdf, p. 12

Source: PS-3 (folder) / design/PS-3 design summary.pdf, page 12, Table 3 "Pump schedule".
Section: 4 Mechanical > 4.2 Pumps. Content sha256:3f7ffce6….pdf.

Pump schedule for the PS-3 station design: three identical pumps, two duty and one standby.

| Tag | Duty | Flow (L/s) | Head (m) | Motor power (kW) |
|---|---|---|---|---|
| P-301 | Duty | 60 | 25.5 | 22 |
| P-303 | Standby | 60 | 25.5 | 22 |

- P-301 rated flow: 60 L/s at 25.5 m head. Basis: specified. Uncertainty: none given.
  Derivation: model reading of a native PDF table; quote verified in text layer.

Cite as: PS-3 design summary.pdf, p. 12, Table 3.
```

**Provenance tags.** Full provenance annotations (a source's organization, revision, dates, handling notes, and the extraction's interpreters) can grow large, and repeating them in every chunk would crowd out content in 400-token chunks. So:

- each source, and each file where it matters, gets one **provenance chunk** holding its full provenance annotation, headed by a short, distinctive **tag** (e.g. `SRC-PS3-TEAMA-REVC`)
- detail chunks carry the tag plus a compact citation line, not the full provenance
- the tag is plain text in the body (and in front matter), so the RAG system's own retrieval can connect a detail chunk to its provenance chunk when asked "whose document is this?"

**Title and author.** The ingest tool is good at tracing content to a file's title and author, which it reads from PDF and `.docx` properties. The export format is a configuration choice:

- **Markdown (the default):** the first heading is the citation, and the file opens with YAML front matter (`title`, `author`/organization, `source`, `revision`). `markitdown` passes Markdown through largely as text, so the front matter at least remains readable in the chunk.
- **`.docx` (to try later):** the same body, with the core `title` and `author` properties set from provenance. More work, but it plays to the tool's demonstrated strength.

A JSON rendering of the same records (an array, since JSONL isn't accepted) is a cheap secondary option for tools that want structure, but Markdown is the primary target.

### Writing for people

Applies to reports, fact sheets, summaries and export chunks alike:

- **Just enough prose to situate the facts:** one to three sentences saying what this is, its scope, whose source and what basis. Not more; prose that buries numbers makes readers dig them out of word problems.
- **Facts as terse bullets.** Fragments are fine. Each bullet leads with the subject and the value with its unit, then conditions, basis, uncertainty and citation.
- **Tables when values are comparable** across rows, options or sources.
- Qualifiers stay attached to the facts they qualify, never collected in a separate caveats paragraph.

### 3. Fact sheet, built without the model (first-tier overview)

Claims grouped by entity and topic, showing values, conditions and provenance links, written in the style above; its short situating lines come from section "about" statements and source metadata. Nothing else is generated, so there is nothing to hallucinate, which fits the project's evidence-first approach. Rendered as HTML alongside the existing report.

### 4. Cited summaries (second tier, tentative)

A model-written overview for humans: section summaries, then topic summaries. With the deployment's 262,144-token context, whole sections and large sets of claims fit in one request, so little map-reduce is needed.

- **Written in the style above, and every statement cites evidence IDs.** Citations are checked mechanically: the cited claims must exist, and any values stated must appear in them.
- It is clearly labelled as generated and optional. It is the project's first *global* generated text, which the README currently avoids on purpose.
- Build it only after the fact sheet shows what readers actually want.

## Milestones

1. `check` subcommand and report view.
2. `export` as Markdown chunks with front matter (per section first, then per topic and per finding), discovery chunks, `index.md`, unique file names and delta exports; optional JSON array; `.docx` chunks as a later configuration option.
3. HTML fact sheet.
4. (Tentative) cited summaries with citation verification.

## Decisions (2026-09-23)

- **RAG target:** an external system with a fixed ingest tool (PDF, Markdown, text, `.docx`, `.pptx`, `.xlsx`, CSV, JSON; no JSONL; `--metadata` ignored; `markitdown` extraction; 512-token chunks with 128-token overlap by default; good at tracing file title and author). Export explicit, self-contained chunks with provenance (including provenance of sources), tables, qualifiers and notes written into the text, sized to fit one ingest chunk.

- **Updates:** unique file names per export; the user manages RAG corpora (new, reset, or delta ingestion) rather than relying on replacement.
- **Chunk format:** Markdown with YAML front matter first; `.docx` with title/author properties is a configuration option to try later.
- **Discovery and comprehension:** export index-style chunks (topics, entities, diagrams, section maps) alongside detail chunks.
- **Human readers:** some prose, enough to situate the facts but never burying them; facts as terse bullets and tables (see *Writing for people*).

## Open questions

None currently.
