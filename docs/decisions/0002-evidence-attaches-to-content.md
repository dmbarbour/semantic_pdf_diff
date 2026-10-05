# 0002. Evidence attaches to content, and sources are declared in the store

- **Status:** Accepted (2026-09-23)
- **Source:** [evidence store plan](../plans/sources-and-evidence-store-2026-09-23.md): [concepts](../plans/sources-and-evidence-store-2026-09-23.md#concepts), [decisions](../plans/sources-and-evidence-store-2026-09-23.md#decisions-2026-09-23), [comparison consequences](../plans/sources-and-evidence-store-2026-09-23.md#comparison-consequences), [folder and archive concerns](../plans/sources-and-evidence-store-2026-09-23.md#folder-and-archive-concerns); [store review](../reviews/store-complete-2026-09-24.md)

## Context

0.1 tied evidence to "document A or B" and located claims only by page and box. Teams split one report into many files, revisions share most of their content, and one file may sit in two folders, or both loose and inside a zip. Comparing folders and archives, and reusing work across them, needs evidence that doesn't depend on where a file sits.

## Decision

- **Content** is bytes plus the interpretation they're given. Its ID is `sha256:<hex>.<ext>`: the SHA-256 of the bytes and the lowercase, normalized extension (`provenance.content_id`).
  - The same bytes as `.txt` and `.md` are different content.
  - Extension aliases collapse only where they share an interpretation (`provenance.EXTENSION_ALIASES`: `.jpeg`, `.tif`, `.htm`, `.yml`, `.markdown`).
  - Files without an extension, or with one no reader handles, aren't interpreted. They're listed with a `skipped` outcome.
- **Evidence attaches to content, never to paths.** A locator places a claim within content: page and box for PDF, lines or paragraphs for text and Word.
- **A file** is a path within a source that refers to content. Archive members are files: `a.zip!/b.zip!/c.pdf`.
- **A source** is declared in the store: a name, metadata and roots (files, folders, zip archives).
  - Roots are rescanned on each run by default; `rescan: "manual"` leaves it to `source update`.
  - Metadata is supplied by people, shown in reports, and never sent to prompts.
  - Revisions are separate sources. A source has no history of its own.
  - Manifests (`source export`, `source import`, `--manifest`) transfer definitions. Nobody maintains them by hand.
- **Content is extracted once per store,** whichever sources and paths hold it. Every occurrence is recorded for provenance ("also at …").
- **Revisions are content differences,** not timestamps. A comparison starts from shared, removed and added content.

## Consequences

- Shared content costs no model calls. Its evidence is identical by construction, listed as unchanged (renames and moves included), and used as a retrieval target.
- Renames, moves and re-packaging change only provenance. Evidence IDs stay stable.
- Near-duplicate files (different bytes, mostly the same claims) are separate content.
- Hidden files (names starting with `.`) and OS clutter are skipped and listed.
- Zip limits are generous, configurable backstops (`max_zip_depth` 8, `max_source_bytes` 50 GB, `zip_ratio_limit` 1000 on large members). Anything over a limit is a recorded outcome, never a silent drop.
- Content no source references is orphaned, and `gc` collects it.
- New formats plug in as readers of content by extension (`.txt`, `.md` and `.docx` so far).
