# Review: store milestone 5 (source registry) and next steps

- **Date:** 2026-09-24
- **Plan:** [sources-and-evidence-store](../plans/sources-and-evidence-store-2026-09-23.md), milestone 5 as redefined on 2026-09-24 (declared sources, rescans, manifests)
- **Commits:** `7d3d209` (scanning), `2612487` (registry, CLI)
- **Tests:** 90 passing on Python 3.12; 86 passing and 4 skipped on Python 3.10 with minimum dependency versions

## Delivered

- **Scanning (`scan.py`):** roots can be files, folders or zip archives.
  - Archives are read in memory and recursed.
  - Hidden files and folders (dot-names, `__MACOSX`, `Thumbs.db`, …) are reported once and never descended into.
  - The agreed safety limits are configurable: nesting depth 8, 50 GB per source, and a compression-ratio check on large members. Unsafe member paths are rejected and encrypted members skipped. Everything stopped is listed.
  - Extensionless files get a bare content hash and are never interpreted.
- **Registry (store schema 4):** sources have a name, kind (`declared`, `shortcut`, `manifest`), metadata and roots. Rescans update files in place, and unchanged disk files are reused without rereading (a zip's member rows and issues are reused as a unit). Content no file references is reported as orphaned.
- **Commands:**
  - `source add | list | show | update | remove | export | import`
  - `compare --store DIR NAME NAME`, with `--manifest FILE` live links (re-imported when the file's hash changes; `source list` flags a missing manifest as orphaned) and `--report DIR`
  - the two-path shortcut, now accepting folders and zips
- **Extraction** reads PDFs from bytes, so zip members work. Archives are treated as containers, and other types are listed as skipped until their adapters exist. Reports link crops relative to the report folder and list files not scanned.
- **Milestone 3 slice:** source provenance at registration (`--meta`) is done; document properties arrived with milestone 4.

## Evidence

- **On the samples:** `source add` for the Solar Decathlon DC team took 0.36 s to register six PDFs (23 MB) whose content was already in the store. The natural nested zips in `archive-edge-cases` scan correctly, `.DOCX` normalizes to `.docx`, and `__MACOSX` clutter inside the 3GPP zips is reported as hidden.
- **Scale ahead:** `--plan` estimates 9,698 image tasks for the DC team's 793 pages, mostly large drawing sheets. That is scheduling-and-triage's problem, and a concrete target for it.
- **Test fixtures taught two lessons, both written into the tests:** PyMuPDF gives every newly generated PDF a unique ID, so "identical" test PDFs must be generated once and copied. And identical files in two sources are one piece of content with one coverage row, by design.

## Drift from the plan, with justification

| Drift | Justification |
|---|---|
| Scanning and the registry were committed separately, and the registry and CLI checkpoints were merged. | The shortcut depends on the registry; a temporary port would have been thrown away. |
| `Source` has a single `name` (no separate `id`). | Users refer to sources by name; two identifiers invited drift. Names can't contain `@` or `/`, reserving them for future syntax (e.g. git revisions). |
| `source import` declares a copy; only `--manifest` makes a live link. | Importing a colleague's manifest shouldn't tie your store to their file; linking is an explicit choice. |
| The shortcut refuses a path whose name matches a *declared* source. | Silently replacing a declared source's roots would be destructive. |
| Only PDFs are extracted. | Other formats belong to [multi-format-adapters](../plans/multi-format-adapters-2026-09-23.md). They're listed as skipped, which makes runs on mixed folders exit 2 (incomplete) until adapters exist. That is honest, but worth knowing. |

## Next steps

**Milestone 6 (content-difference-first comparison).** Shared evidence is already listed apart and never compared (since milestone 1). What remains:

- **Shared evidence as retrieval targets.** A claim in changed content whose counterpart sits in shared content should match it instead of being reported "unmatched". Retrieval will compare each side's unique evidence against the other side's unique evidence *plus* shared evidence.
- **A file-level difference summary** for reports: files unchanged, modified (same path, different content), added, removed, and moved or renamed (same content, different path). Sources are separate (`team-a-rev1` vs `team-a-rev2`), so paths are compared relative to each source's roots.

**Milestone 7 (views, `show`, `gc`, rest of the CLI):** `gc` deletes orphaned content with its evidence, tasks, sections, cached responses and crops (`--dry-run` to preview). Sources whose linked manifest is missing are removed only with an explicit flag, since deleting a user's source definition is a bigger step than collecting unreferenced content. No open design questions for either milestone.
