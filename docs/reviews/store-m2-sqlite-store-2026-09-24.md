# Review: store milestone 2 (SQLite store) and next steps

- **Date:** 2026-09-24
- **Plan:** [sources-and-evidence-store](../plans/sources-and-evidence-store-2026-09-23.md), milestone 2, with the decisions from the [milestone 1 review](store-m1-schema-v2-2026-09-24.md)
- **Commit:** `e4d76ff`
- **Tests:** 63 passing on Python 3.12; 59 passing and 4 skipped on Python 3.10 with minimum dependency versions

## Delivered

- **`store.py`:** the `--out` folder is a store holding `store.sqlite` (WAL mode, foreign keys, owner-only permissions) and `assets/`. It takes an exclusive lock (a second writer gets "in use") and refuses a store with a different schema version.
- **Per-task records:** extraction reports each task through `on_task`, and the store writes the task's coverage row and evidence in one transaction. Content whose tasks all finished without failure is marked extracted, and later runs load it instead of re-extracting.
- **Semantic response cache:** callers pass keys by meaning: extraction `(extract, region, content, task, input-text hash, crop)`, comparison `(compare, comparison-settings hash, evidence A, evidence B)`. The request-byte hash is stored with each entry; the `cache_check` setting raises on a mismatch. The file-based byte-keyed cache remains for library callers without a store.
- **Binding:** the extraction interpreter is bound to the store. A different one is refused with a flattened list of differences. `--reset` clears only the affected regions (e.g. a changed `tile_points` clears only image-based tasks, evidence and cached responses), plus all comparisons; `--reset --dry-run` previews the counts.
- **Resume by cache replay:** an interrupted run resumes with no repeated model calls and identical findings (tested by raising an interrupt mid-run).

## A bug the new tests caught before commit

**Task tags weren't unique across pages.** Every page's text group was `text:0.0`, and every page's overview was `overview`. In the new task table, page 2 overwrote page 1. Worse, in the semantic cache key, same-sized pages have identical tile rectangles, so page 2's tiles and overview would have been served page 1's answers. Task tags now carry the page (`text:p2:0.0`, `tile:p2:3-r0`, `overview:p2`). Two tests fail on the old tags and pass on the new ones: the resume test, and a dedicated two-page test.

This is evidence for the mitigation agreed for semantic keys: tests that vary each input and assert a miss or a distinct key. Every future key needs the same scrutiny.

## Drift from the plan, with justification

| Drift | Justification |
|---|---|
| No persistent task queue; resume by cache replay. | Decided in the milestone 1 review; the queue moves to scheduling-and-triage. |
| `report.html`, `report.json` and `evidence.json` stay at the top of `--out`, not in `reports/`. | The two-file command's output should be easy to find, given the naming concern you raised. The staged CLI (milestone 7) will separate the store from report locations. |
| Any extraction reset clears **all** comparisons. | Comparisons reference evidence IDs; after a partial reset their inputs may no longer exist. They are cheap to regenerate from the cache, and precise invalidation isn't worth it yet. |
| Coverage-only rows (`vision`, `table-detection`) count as regions for selective reset. | So turning vision on or off clears the "vision skipped" rows too. |
| Only the extraction interpreter is bound. | Embeddings and summaries don't exist yet; comparison settings are recorded per comparison, as decided. |

## Next steps, reordered

**Milestone 3 (annotations core) is split and moved to its consumers.** Its parts need things that don't exist yet: manifests and a staged CLI (to attach source provenance), sections (for extracted provenance), and aliases, criteria or report review controls (to produce reviewer decisions). Building the record format, import and export without any consumer would mean designing in a vacuum. Instead:

- **Native document properties** (PDF title and author) go into file metadata with milestone 4. They're trivial to read, and every sample PDF has a title.
- **Source provenance** at registration arrives with manifests (milestone 5) and the staged CLI (milestone 7).
- **Reviewer decision records** (table, export and import, orphan re-attachment) arrive with their first consumer: report review controls in scheduling-and-triage, or criteria review, whichever is built first.

**Milestone 4 (PDF sections) is next.** A survey of the 33 sample PDFs:

- **Every multi-page PDF has an outline** (bookmarks): reports, project manuals and even construction drawing sets, from 25 to 1,022 entries. Only the 1–2 page jury score sheets have none, and they're too short to need sections.
- **Every PDF has a document title** in its metadata.

So sections come from the **outline first, with fixed page ranges as the fallback**. The font-size heading heuristic in the plan has no demonstrated need in the corpus, so it's deferred until a document needs it. Deep outlines (`ken_manual` has 1,022 entries) need a depth or minimum-size rule, so sections stay useful units.
