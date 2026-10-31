# Single-source outputs: consistency check, RAG export, overviews

- **Status:** Active (export per section, per topic and per finding built 2026-10-31); Tentative (model-written summaries). Since 2026-10-28, `check` (feature 1, milestone 1) and the fact sheet (feature 3, milestone 3) are [single-document analysis](single-document-analysis-2026-10-28.md)'s: inconsistencies found within a subject's claims, confirmed by a second pass, and a one-source report with a Subjects view. They're kept below as written.
- **Since written (reviewed 2026-10-21):** the portable report's Claims view, topics and search (`search`, the command too) make a claims browser without the model, but only of a two-source comparison; the owner, 2026-10-20: "As a user of the report, it would be convenient to have an easily searchable database of claims even without the comparisons". Milestone 3 would be that report for one source. `export` is taken (`source export`, `config export`), so the RAG export needs another name. Comparing a source with itself compares nothing (shared evidence is never compared with itself), so `check` needs its own pass. Situating's "about" statements exist for PDFs only.
- **Depends on:** the evidence store (built: [0002](../decisions/0002-evidence-attaches-to-content.md), [0003](../decisions/0003-sqlite-evidence-store.md)); uses section "about" statements from [scheduling-and-triage](scheduling-and-triage-2026-09-23.md) for per-section export chunks and fact-sheet context

## Goal

Much of the pipeline is useful for **one source** on its own: extracted, provenance-tracked claims plus a coverage record. Expose that directly.

## Features

### 1. `check`: internal consistency

Run claim-level comparison with A = B = one source, excluding pairs of a claim with itself. It surfaces contradictions inside a source, such as:

- pump power 10 kW in §2 but 12 kW in Appendix C
- a spreadsheet total that disagrees with the narrative
- a diagram connection that contradicts the text

It reuses retrieval, the numeric check and the uncertainty rules. Recognized disagreements are recorded as derived claims with their severity and the model's handling decision (e.g. an errata document supersedes the original), which may lower confidence in the claims involved; see *Disagreements are claims* in [Annotations](n-way-comparison-2026-09-23.md#annotations). For a single-team review this is arguably more useful than comparing two teams. Duplicate claims (the same fact from the native and visual passes, or repeated across files) should show as *equivalent* support, not noise.

### 2. `export`: RAG ingestion as Markdown chunks

The target RAG system is not ours to change. Its ingest tool accepts PDF, Markdown, text, `.docx`, `.pptx`, `.xlsx`, CSV and JSON (not JSONL). It preserves provenance poorly, ignores its `--metadata` argument in practice, handles spreadsheets badly and loses the meaning of diagrams. So the export is **a folder of explicit, self-contained Markdown chunk files**, one per chunk, designed so each survives ingestion on its own:

- **Provenance in the text, not in metadata.** Each chunk states in prose where it came from: source, file path, page or slide or cell range, section heading path, and a short content ID for exact tracing. It also carries **provenance of the source itself** from the source and file metadata (title, organization or team, author, revision label, date; see source metadata in [0002](../decisions/0002-evidence-attaches-to-content.md)), so the RAG system knows whose document and which revision a fact comes from. A human-readable citation line ("PS-3 design summary.pdf, p. 12, Table 3") is included so RAG answers can quote it.
- **Sized to the ingest tool's chunking.** The tool extracts text with `markitdown` and splits into chunks of 512 tokens with 128 tokens of overlap by default (configurable on its command line). Export chunks therefore target roughly 400 tokens by default (configurable), leaving margin for tokenizer differences, so each file normally becomes one RAG chunk. When a chunk must be longer, a compact provenance line is repeated before each subsection, so any 512-token window still names its origin. The provenance header costs roughly 50–80 tokens per chunk; worth it.
- **Tables inline, as small Markdown tables** with their headers and units, instead of separate CSV or `.xlsx` files the ingest tool would mangle. Large tables are split into chunks that each repeat the header and table identity.
- **Diagrams and charts as text.** Claims from visual extraction (connections, operating points, axis readings, flagged approximations) are written out in words. That preserves exactly what the ingest tool would lose.
- **Qualifiers kept with the facts:** conditions, basis (measured, projected, required…), stated uncertainty, derivation (direct read, model extraction, summary of summaries), quote-verification status and any issues or suspicions. Confidence appears as the qualifier it is, not as a bare number presented as truth. Relevant annotations travel too: provider-declared markings, recognized disagreements and their handling, and reviewer decisions such as criteria (see [Annotations](n-way-comparison-2026-09-23.md#annotations)).
- **Stable file names from content.** Each chunk file is named by its content hash plus extension (e.g. `3f7ffce6….md`), so an unchanged chunk keeps its name across exports and a changed one gets a new name. Re-ingesting apparently aggregates rather than replaces, so the user controls the corpus directly: ingest a full export into a new or reset corpus, or ingest a **delta export** containing only chunk files not present in a named previous export. The delta's `index.md` also lists chunk files that disappeared, for the user to act on.
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

1. `check` subcommand and report view (moved 2026-10-28 to single-document analysis, milestone 4).
2. `export` as Markdown chunks with front matter (per section first, then per topic and per finding), discovery chunks, `index.md`, content-derived file names and delta exports; optional JSON array; `.docx` chunks as a later configuration option.
   - **Built 2026-10-31, per section** (the owner, 2026-10-31: "Please proceed in recommended order"; `export.py`, `semantic-pdf-diff export --store DIR [--out FOLDER] [--chunk-chars N]`, no requests): a chunk a section, or a part of one (about 1,600 characters of claims, some 400 tokens): front matter (title, source, file, pages), a line saying where it came from (source, file, pages or paragraphs or lines, section, a short content id), the section's "about", its claims by subject, each with its conditions, basis, hedges, where it's read and a short excerpt where its quote says more than its value; discovery chunks (subjects A to Z each pointing to the chunks holding its claims, figures and tables, the glossary, what it doesn't give, inconsistencies); `index.md` (every chunk, how the export was made). Each file named by its text's hash: an unchanged chunk keeps its name, nothing is deleted. TS 38.300's v19.3.0, clauses 1 to 8: 253 chunks, a median of 1,765 bytes, 2,198 at most; 9 of scical's sheets: 118.
   - **Built 2026-10-31, per topic and per finding** (the owner, 2026-10-31: "The proposed next steps seem good to me. Please proceed."; no requests):
     - **A chunk a topic** the report is browsed by (the model's names where it chose them), or a part of one: its claims by subject from every file and section, each naming its file and place; a claim said alike in several places (two revisions) one line naming each place.
     - **A comparison's findings** by what was found ("They differ", "Uncertain", "They complement each other", "They agree"), each with both claims and their places, the judge's reason and confidence, and the explanation's kind and reason; then "Only in A" and "Only in B", each source's claims with no counterpart.
     - **Agreements whose two claims say the same word for word left out** (the report folds them too) and counted in index.md: TS 38.300's comparison, 1,354 of them.
     - **Measured** (offline): TS 38.300's v19.2.0 against v19.3.0, clauses 1 to 8: 749 chunks (238 topics', 31 findings', the rest sections' and discovery's), a median of 1,717 characters, 2,119 at most; first tried, 1,508, 620 of them agreements said alike and 387 topics' repeating each claim once a version. 9 of scical's sheets (an analysis): 202 chunks, 87 topics'.
   - **Not yet:** chunks per subject, tables as Markdown tables, a JSON array, `.docx` chunks.
3. HTML fact sheet (moved 2026-10-28 to single-document analysis, milestones 1 and 2; its milestone 2 since 2026-10-29 [indexes and glossaries](indexes-and-glossaries-2026-10-29.md)').
4. (Tentative) cited summaries with citation verification.

## Decisions (2026-09-23)

- **RAG target:** an external system with a fixed ingest tool (PDF, Markdown, text, `.docx`, `.pptx`, `.xlsx`, CSV, JSON; no JSONL; `--metadata` ignored; `markitdown` extraction; 512-token chunks with 128-token overlap by default; good at tracing file title and author). Export explicit, self-contained chunks with provenance (including provenance of sources), tables, qualifiers and notes written into the text, sized to fit one ingest chunk.

- **Updates:** stable file names derived from chunk content (hash plus extension); the user manages RAG corpora (new, reset, or delta ingestion) rather than relying on replacement.
- **Chunk format:** Markdown with YAML front matter first; `.docx` with title/author properties is a configuration option to try later.
- **Discovery and comprehension:** export index-style chunks (topics, entities, diagrams, section maps) alongside detail chunks.
- **Human readers:** some prose, enough to situate the facts but never burying them; facts as terse bullets and tables (see *Writing for people*).

## Open questions

None currently.
