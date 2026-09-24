# Projects, sections and a persistent evidence store

- **Status:** Active (next up)
- **Depends on:** [robustness-baseline](robustness-baseline-2026-09-23.md) (completed)
- **Enables:** every other plan in this folder

## Goal

Make extraction produce a **persistent, per-project evidence store**, and make comparison one of several operations over stores. Support **folders** (a project split across many files) with fine-grained provenance. Stay PDF-only in this plan; other formats plug in later via [multi-format-adapters](multi-format-adapters-2026-09-23.md).

## Why

Most of the pipeline is already independent of "two PDFs": `extract_pdf` never sees the other document, and `compare` only needs two lists of `Evidence`. What ties the code to two PDFs is:

- `Evidence.document: Literal["A", "B"]`
- page and bounding box as the only way to locate a claim
- a CLI that extracts, compares and reports in one run

Teams may partition one report into many files, so a *project* (a set of files) is the natural thing to compare. Per-project stores also make single-project uses cheap ([single-project-outputs](single-project-outputs-2026-09-23.md)) and are the prerequisite for comparing N projects ([n-way-comparison](n-way-comparison-2026-09-23.md)).

## Design

### Concepts

- **Project:** a named set of sources, given as a folder, a list of files, or a manifest with include/exclude globs.
- **Source:** one file, identified by its path relative to the project root plus its sha256.
- **Section:** a logical part of a source, and the unit of scheduling, caching and triage. For PDFs it comes from the outline/bookmarks, falling back to headings guessed from font size, then to fixed page ranges. See [scheduling-and-triage](scheduling-and-triage-2026-09-23.md).
- **Locator:** where a claim sits inside a source. It is a tagged union per format; for PDF that is page, bounding box and source kind (text / table / tile / overview). Other formats add their own shapes later: slide/shape, sheet/cell range, heading path/line range.
- **Evidence (schema v2):** replace `document` with `project`, `source` (relative path plus hash), `section` and `locator`. Keep stable, content-addressed IDs.

### Store

A per-project store directory containing:

- evidence as JSONL
- the coverage record
- rendered assets
- a manifest of sources with hashes, sections and extraction settings

Extraction is **incremental**: an unchanged source (same hash, same settings) is not re-extracted. The model-response cache already does most of this at request level; the store makes it explicit and cheap to check. A run can stop at any time and resume.

### CLI

Staged subcommands. The current two-file form stays as a shortcut that runs all three stages.

```
extract <project> --store <dir>
compare <store> <store> [--mode proposals|revisions]
report <result>
```

(`check`, `export` and N-way `compare` arrive with later plans.)

### Folder-specific concerns

- **Duplicate and superseded files:** detect identical hashes, and flag near-duplicates such as `report_v2_final_FINAL.pdf`, instead of double-counting claims.
- **Heading-path context:** send the section heading path with each text group, so the model can tell which component a sentence is about. This helps PDFs and folders alike.
- **Provenance in reports:** show `project / relative/path.pdf / section / p.12`.
- **Names across files** ("P-101" in an equipment list vs "primary pump" in the narrative) get more common in folders. That is handled by alias consolidation in [retrieval-recall](retrieval-recall-2026-09-23.md), not here.

## Milestones

1. Evidence schema v2 and locator types; migrate `compare` and `report` to use `project`/`source` instead of A/B.
2. Store layout plus manifest; incremental extraction keyed on source hash and settings.
3. PDF section detection (outline → font-size headings → page ranges); heading path in prompts.
4. Folder and manifest projects; duplicate-file detection.
5. Staged CLI with the current two-file command kept working; tests and docs.

## Open questions

- **What structure do real documents have?** Before choosing section heuristics, look at a few representative PDFs: do they have outlines, consistent heading fonts, or neither?
- Store format: JSONL files are simple and diffable; SQLite would make queries easier later. Start with JSONL unless queries force the issue.
- How should manifests express file order or revision metadata, if at all?

## Out of scope

Non-PDF formats, rate-aware scheduling, N-way comparison, summaries and export. Each has its own plan.
