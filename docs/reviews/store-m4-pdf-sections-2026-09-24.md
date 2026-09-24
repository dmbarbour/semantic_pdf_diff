# Review: store milestone 4 (PDF sections) and next steps

- **Date:** 2026-09-24
- **Plan:** [sources-and-evidence-store](../plans/sources-and-evidence-store-2026-09-23.md), milestone 4 (taken before milestone 3; see the [milestone 2 review](store-m2-sqlite-store-2026-09-24.md))
- **Commit:** `1834619`
- **Tests:** 74 passing on Python 3.12; 70 passing and 4 skipped on Python 3.10 with minimum dependency versions

## Delivered

- **Sections** from the PDF outline down to `section_depth` (default 2), with page ranges of `section_pages` (default 20) as the fallback. Assignment is per page: a page belongs to the last outline entry starting on or before it. Sections are stored per content (schema version 3).
- **Heading path in every prompt** (`Section: Design > Pumps`), in the semantic cache key, and on each claim (`Evidence.section`). Reports show `§ heading path` on evidence cards.
- **Prompt version** in the extraction and comparison interpreters (extraction is now 2). The interpreter's prompt hash covered only template text, not how prompts are assembled, so adding the section line would have gone unnoticed by store binding without it. Bump it whenever prompt assembly or task construction changes.
- **Table continuation across pages**, recorded in the derivation ("row with header continued from page N").
- **Empty table rows skipped** without renumbering the remaining rows' tasks.
- **Native document properties** (PDF title and author) as file metadata. This is the first piece of the split annotations milestone.

## Evidence from the sample corpus

- **Sections:** at depth 2, sections average 1–5 pages in reports and manuals. In drawing sets they're one sheet each, with useful headings (`GENERAL > G-102 - EMERGENCY EGRESS PLAN`).
- **Continuation false positives found and fixed.** The first rule (same width, at the top of the page after a table at the bottom) fired on the Solar Decathlon rules' daily schedules, where Sunday's table followed Saturday's. That would have labelled Sunday's rows with Saturday's header. The rule now treats a first row that is a *header of the same form* (at least half its cells matching the carried header, position by position) as a new table. On the rules PDF only the true continuation remains (pages 57→58, repeated header).
- **Drawing sets defeat table detection.** In `dc_cd.pdf` (143 sheets), PyMuPDF finds over 10,000 table rows. They're mostly drawing geometry: 47% are entirely empty, and about half the rows on the first 40 sheets repeat on five or more sheets. Skipping empty rows removes the worst of it. Recognizing repeated title blocks and legends belongs to boilerplate detection in [scheduling-and-triage](../plans/scheduling-and-triage-2026-09-23.md) (milestone 3), which should use drawing sets as a test case. Continuations found in drawings are junk matching junk. They're harmless to meaning, but they cost calls.

## Drift from the plan, with justification

| Drift | Justification |
|---|---|
| No font-size heading heuristic. | Every multi-page sample PDF has an outline ([milestone 2 review](store-m2-sqlite-store-2026-09-24.md)); no document has shown the need. |
| Section boundaries are per page, not per text block. | Outline destinations give a position on the page, but mid-page boundaries are rarer than whole-page ones and add complexity. Revisit if evidence shows mislabelled content. |
| Explicit prompt version added. | The plan requires prompt versions in the interpreter; this milestone was the first to need one. |
| Empty-row skipping. | Not in the plan. Lossless, and it removes 10–47% of table calls in the samples. |

## Next step: milestone 5 (folders, zips and manifests). One open question

Folders and zip archives are straightforward and fully specified by the plan:
- hidden files ignored
- archives read in memory, with the agreed safety limits
- duplicate content listed as occurrences
- unsupported or extensionless files listed as skipped

**Manifests aren't.** A manifest lists a source's items and attaches **source provenance** (title, organization, revision…), plus metadata for individual files or globs. It's the main way to give source provenance, since two positional CLI arguments leave no good place for per-source flags.

**Question: how does the CLI recognize a manifest?** A plain `.json` argument is ambiguous: it could be content (a JSON document to extract from) or a manifest. Options:

1. **A naming convention**, e.g. `*.source.json`. Visible, needs no extra flag, and doesn't depend on the file's contents.
2. **A flag**, e.g. `--manifest team-a.json` in place of a positional path. Explicit, but awkward with two positional sources.
3. **A marker key** inside the JSON (e.g. `"semantic_pdf_diff_source": 1`). Automatic, but it's content sniffing, which the plan avoids elsewhere.

**Recommendation:** option 1, with JSON as the format (the standard library reads it on Python 3.10, unlike TOML). A manifest can also sit *inside* a folder, e.g. `source.json` at its root, to give the folder its provenance without changing how it's passed.
