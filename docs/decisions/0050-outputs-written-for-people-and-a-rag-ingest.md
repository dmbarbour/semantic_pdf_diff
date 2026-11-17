# 0050. Outputs are written for people, and for a RAG ingest as self-contained chunks, fresh from their sources

- **Status:** Accepted (2026-11-17, retiring the plan it was made in)
- **Source:** the plan's decisions of 2026-09-23 (the RAG target as described then); the owner, 2026-10-31: "Each export or report should be logically fresh from the sources, not history-dependent."
- **Builds on:** [0033](0033-self-contained-reports-and-their-search.md), [0030](0030-only-answers-decide-what-a-run-writes.md); made in [single-source outputs](../research/single-source-outputs-measured-2026-11-17.md)

## Decision

- **Writing for people** (reports, summaries, export chunks):
  - just enough prose to situate the facts: one to three sentences saying what this is, its scope, whose source and what basis;
  - facts as terse bullets, each leading with its subject and value with its unit, then conditions, basis, uncertainty and citation;
  - tables where values are comparable across rows, options or sources;
  - qualifiers attached to the facts they qualify, never collected in a caveats paragraph.
- **The RAG target is fixed:** an external system whose ingest takes PDF, Markdown, text, Office files, CSV and JSON (not JSONL), ignores metadata, and cuts text into 512-token chunks overlapping by 128.
- **So the export is self-contained chunks** (`export`): provenance, tables, qualifiers and notes written into each chunk's text, a chunk under one ingest chunk; Markdown with YAML front matter (a JSON file too); each named by its text's hash, so an unchanged chunk keeps its name; the user manages corpora (new, reset, or the delta written apart); chunks for finding things (subjects A to Z, figures and tables, the glossary, gaps, `index.md`) beside those of detail.
- **Fresh:** an export's folder holds that export alone, an earlier one's chunks removed; a folder holding a file no export writes is refused, nothing written.

## Consequences

- `export.py`; the README's export section.
