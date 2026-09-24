# Sources, content and a SQLite evidence store

- **Status:** Active (next up)
- **Depends on:** [robustness-baseline](robustness-baseline-2026-09-23.md) (completed)
- **Enables:** every other plan in this folder

## Goal

Make extraction write to a **persistent, resumable SQLite evidence store**, and make comparison one of several operations over it. Support **folders and zip archives** as comparison objects, with fine-grained provenance. Stay PDF-only in this plan; other formats plug in later via [multi-format-adapters](multi-format-adapters-2026-09-23.md).

## Why

Most of the pipeline is already independent of "two PDFs": `extract_pdf` never sees the other document, and `compare` only needs two lists of `Evidence`. What ties the code to two PDFs is:

- `Evidence.document: Literal["A", "B"]`
- page and bounding box as the only way to locate a claim
- a CLI that extracts, compares and reports in one run

Teams may partition one report into many files, so a folder or archive is the natural thing to compare. A persistent store also makes single-source uses cheap ([single-source-outputs](single-source-outputs-2026-09-23.md)), and is the prerequisite for comparing N sources ([n-way-comparison](n-way-comparison-2026-09-23.md)).

## Concepts

Plans use **source** for a comparison object. "Project" means a real-world project (or this software), never a comparison object.

- **Content:** bytes plus the interpretation they are given. Approximated by a **content ID = SHA-256 of the bytes + normalized file extension** (lowercase, e.g. `sha256:…​.pdf`). The same bytes named `.txt` and `.md` are different content, because they are interpreted differently. Evidence attaches to content, never to paths.
  - **Normalization** collapses only aliases known to share an interpretation (`.jpeg` → `.jpg`, `.tif` → `.tiff`, `.htm` → `.html`, `.yml` → `.yaml`, `.markdown` → `.md`), from a maintained table.
  - **Files without an extension, or with one no adapter handles, are not interpreted** and contribute no evidence. They are still listed as files, with a `skipped` task outcome, so nothing disappears silently.
- **File:** a path within a source that refers to content. Archive members are files too, with paths like `a.zip!/b.zip!/c.pdf`. An archive is itself content whose interpretation yields more files.
- **Source:** a comparison object: a folder, a zip, a single file, or a manifest listing any of these. A source *has content via its files*.
- **Source metadata (provenance *of* sources):** this project treats sources as the provenance of evidence, but downstream consumers (RAG especially) also need to know where a source itself came from. When a source is registered, the user may attach free-form metadata, e.g. title, organization or team, author, revision label, date, description, handling or classification notes. A manifest can also attach metadata to individual files or path globs. Native document properties (PDF and `.docx` title and author, and similar) are read and kept as file-level metadata. Metadata is **human-supplied and not interpreted**. It appears in reports and is written into exports, and is not sent to extraction prompts, so editing it never needs a reset.
- **Duplicate content within a source** (the same PDF in two folders, a file both loose and inside a zip) is extracted once and contributes no new evidence. Every occurrence is still recorded, so provenance can say "also at …".
- **Revisions are content differences, not timestamps.** Going from source A to source B means some content was removed (in A, not B), some added (in B, not A) and the rest is shared. A rename is shared content under a new path, so it changes only provenance. File times may be recorded for humans but carry no meaning in comparisons. This answers the earlier question of how manifests express revision metadata: they don't need to.
- **Section:** a logical part of one piece of content, and the unit of scheduling, caching and triage. For PDFs it comes from the outline/bookmarks, falling back to headings guessed from font size, then to fixed page ranges. See [scheduling-and-triage](scheduling-and-triage-2026-09-23.md).
- **Locator:** where a claim sits *within content*, never including the path: for PDF, page plus bounding box plus pass (text / table / tile / overview). Other formats add their own shapes later.
- **Interpreter:** everything besides the bytes that shapes derived data. There are separate interpreters for extraction, embeddings and summaries. An interpreter includes:
  - **everything sent to a model:** model identifier, prompt templates (tracked by an internal prompt version plus hash), sampling and output options (temperature, seed, response format, token limits) and image rendering (resolution, tile size)
  - **everything that shapes chunking or sections:** text budget, tile overlap, refinement depth, section heuristics
  - **tool and library versions** that affect parsing or rendering (this tool, PyMuPDF, adapter libraries)
  - **configured external converters:** executable path, SHA-256, declared version and arguments. This is best effort only: a converter's own configuration files and dependencies can't be tracked, and **users are responsible** for resetting a store when they change them.

  Not included: timeouts, retries, call limits, concurrency and rate limits, credentials, and the endpoint URL. The model identifier must identify the weights; if a server swaps weights under the same name, that is also the user's responsibility (the README already advises versioned model names).
- **A store is bound to its interpreters** (a default guideline, not a hard rule). The first run records each interpreter in the store's manifest. A later run whose interpreter differs is **rejected**, with a message naming what differs and what `--reset` would clear. Mixing models breaks things in unpredictable ways; embeddings especially are only comparable within one model. The user either creates a new store or passes `--reset`. Adding a role that wasn't configured before (e.g. embeddings later) is allowed without a reset.
- **`--reset` is selective.** Interpreters are recorded as components scoped by role and, where it applies, by adapter or extension (PDF rendering settings affect only `.pdf` content; a converter affects only its extension). `--reset` diffs the new configuration against the recorded one and clears only the affected derived data plus everything downstream of it (extraction → evidence → embeddings, summaries, comparisons). Registered sources and content are always kept. Examples:
  - a new embedding model clears embeddings and whatever was built from them, but keeps evidence
  - a new summary model clears summaries only
  - a changed PDF tile size clears visual evidence from PDF content only; text and spreadsheet evidence stay
  - a changed extraction model or prompt version clears all extraction and everything downstream (the full reset)
  - when the scope isn't obvious, clear more rather than less

  `--reset --dry-run` reports what would be cleared, and the rejection message shows the same summary.

- **Derivation:** every evidence row records *how directly* it was obtained from the bytes, as a chain of steps, e.g. a deterministic cell read; a model reading of text, a table or an image; a deterministic read under a model's interpretation of the headers; or a model reading of content that another tool's model wrote (a summary of summaries). The tool and reports use it to show whether a claim is primary, a summary, or a summary of summaries, and comparisons record the derivation of both sides. **Directness is provenance, not reliability**: a direct read of a questionable spreadsheet is still questionable.

Evidence IDs are derived from `content ID + locator + claim`, so they are stable across renames, moves and re-packaging. They don't need an interpreter component, since one store has one extraction interpreter.

## Store

### Layout

A store is a **local folder** that users may copy or share at whatever scope suits them:

```
<store>/
  store.sqlite     # sources, content, evidence, tasks, comparisons, response cache
  assets/          # rendered crops and other auxiliary files, named by SHA-256
  reports/         # generated HTML reports (disposable; regenerated from the database)
```

The expected scale is a few sources per user, typically a few revisions plus a few competing teams, so one store usually holds several sources and shares work among them. One process writes to a store at a time; a second writer gets a clear "store is in use" error. Copying a store folder is fine, but using one live over a network filesystem is not supported (SQLite locking is unreliable there).

### Why SQLite

- **Many views from one store:** evidence with provenance, coverage summaries, per-source diffs and human-readable exports are all queries or views over the same tables.
- **Stop and resume:** each extraction task commits in its own transaction, so a long run can be halted at any point and continued without losing or duplicating work. WAL mode lets reports and queries read while extraction writes.
- **Content-addressed reuse:** one store holds several sources. Revisions and competing proposals share whatever content they have in common, and that content is extracted only once.
- It is part of the Python standard library, so there's no new dependency.

Reports (HTML) remain files generated from the database.

### Tables (sketch)

| Table | Contents |
|---|---|
| `content` | content ID, SHA-256, extension, size, detected media type |
| `source` | source ID, name, how it was given (folder / zip / file / manifest), metadata (JSON) |
| `file` | source ID, path (with `!/` for archive members), content ID, parent archive file if any, metadata (JSON: manifest-supplied and native document properties) |
| `interpreter` | one row per bound role (extract / embed / summarize; comparison settings are recorded per comparison instead): model, endpoint label (credentials redacted), prompt hashes, output-affecting settings JSON, tool and library versions. This is the store's binding checked on every run. |
| `section` | content ID, section ID, locator range, heading path, triage results (type, density, keywords, "about" statement) |
| `table_interpretation` | content ID, table region, sheet map, row-to-claims mapping, strategy, check results (see [multi-format-adapters](multi-format-adapters-2026-09-23.md)) |
| `task` | content ID, section, pass, locator, status (pending / complete / partial / failed / skipped / not_reached), attempts, issues. This is the coverage record and the resume queue. |
| `evidence` | evidence ID, content ID, task ID, locator JSON, claim fields (including topic, basis, uncertainty, context and role), derivation chain, quality signals, issues |
| `embedding` | text hash, embedding interpreter, vector (for claim topics and section "about" statements) |
| `comparison` | comparison ID, mode, the sources compared, comparison settings and model, criteria used, findings or criterion descriptions (so reports can be regenerated without model calls) |
| `criterion` | criterion ID, question, required basis and context, comparison method, provenance (extracted from which documents, recommended, or user-entered), review state |
| `annotation` | see *Annotations* below: source provenance and reviewer decisions (target, kind, value, context snapshot, author, time). Kept across `--reset`. Extracted provenance lives on file, section and evidence rows. |
| `response_cache` | request hash → validated model response (replaces the `cache/` folder) |
| `meta` | schema version, creation and tool info |

### Views and exports

SQL views cover common questions: evidence with all its file occurrences per source, coverage by source and section, and content shared, added or removed between two sources. A `show` subcommand turns views into human-readable output (Markdown or CSV tables, JSONL for tools) without anyone needing to write SQL.

## Annotations

**Annotations are provided by or through the tool**: provenance metadata supplied when a source is added, titles, authors and sections extracted and traced to files, derivation levels, confidence and quality signals, and reviewers' decisions about how the tool should work (criteria, aliases). **Anything whose purpose the tool doesn't know is content**, and gets a provenance annotation saying where it came from. Speaker notes, document comments and unrecognized front matter are content; "slide 42 speaker notes" or "comment on §3.2" is the provenance annotation that goes with them.

Conceptually these are one kind of record. Physically, much of it (locators, derivation, quality signals) lives as columns on file, section and evidence rows; the `annotation` table holds the rest.

### Kinds

| Kind | Examples | Lifetime |
|---|---|---|
| **Source provenance (user-supplied)** | title, organization, author, revision, date, whether the source is external, handling notes | kept across `--reset`; edited by the user |
| **Extracted provenance** | native document properties (title, author) traced to files; sections and heading paths; locators with context ("slide 42 speaker notes", "comment by …"); derivation chains; confidence and quality signals | derived, so it follows the extraction interpreter like evidence |
| **Provider-declared** | recognized Markdown front matter keys, such as title, author or a provider's confidence level (e.g. from the Cameo export) | derived from content; passed through without judgment |
| **Reviewer decisions** | criteria added, edited, merged or dropped; aliases accepted or rejected; a table mapping or strategy forced; a finding marked useful or not; benchmark labels | kept across `--reset`; re-attached or orphaned (below) |

**No per-claim corrections by reviewers.** Reviewers use the tool to *avoid* reading the pile of source documents, with provenance as the basis for spot validation, so correcting individual values isn't ergonomic or realistic. Corrections come in as content instead: a user **extends the source with an errata document**, e.g. by adding `errata.md` to the source folder. It is ordinary content, so only the new file is extracted, and the model recognizes its intent from what it says. Conflicts between the errata and the original are handled like any other disagreement (below).

### Disagreements are claims

When the model recognizes that claims disagree (within one source, such as an errata document against the original, or between documents), the disagreement is recorded as a **derived claim** with context: which claims, how they differ, and whether the difference is subtle or major. The model also decides how to handle it (e.g. the errata document supersedes, or the disagreement is unresolved), and records that decision. Depending on severity and handling, the involved claims' reliability is lowered, and reports show why. This is what `check` produces for a single source ([single-source-outputs](single-source-outputs-2026-09-23.md)).

### Record (for the `annotation` table)

- **target** by stable ID: source, file, content, section, evidence, a pair of evidence IDs (finding or benchmark pair), criterion, alias proposal, table interpretation, or comparison
- **kind** and **value**, with an optional note
- **context snapshot** for reviewer decisions: what the reviewer saw (quotes, values, paths), so the record reads on its own and can be re-attached
- **time**, and optionally a **reviewer ID** (see *Decisions*)

### Behaviour

- **Survives regeneration and resets.** Evidence IDs are content-based, so annotations survive report regeneration, renames and re-packaging. After a reset or model change, a reviewer decision whose target is gone is **orphaned, not deleted**. The tool tries to re-attach it via its context snapshot and lists what stays orphaned.
- **Reviewer decisions are configuration**, and follow the same rule as any other configuration: a change that affects model derivations triggers the selective `--reset` or re-run of just what it affects, and a change that affects only final reports doesn't. For example, a forced table strategy changes that table's extraction (reset that table's evidence); edited criteria or aliases change comparisons (re-run the affected comparisons, which record their own settings); a usefulness mark changes only reports (nothing to re-run). Source provenance annotations affect only reports and exports.
- **Visible, never destructive.** Reports show reviewer decisions and model-recognized disagreements next to the evidence they concern; evidence is never replaced or hidden.

### Capture

- **CLI and manifests:** source provenance at registration.
- **Edit and re-import:** export a file (e.g. proposed criteria or table mappings), edit it, import it back. This is the review path before interactive views exist.
- **Report controls:** review buttons in the static HTML report keep decisions in the browser's local storage, and an *Export reviews* button downloads them as JSON for `import-reviews`.
- **Later:** interactive views write reviewer decisions directly.

### Export and import

- **Export:** a machine-readable JSON file plus a readable report grouped by kind, with context snapshots.
- **Import** merges reviewer decisions into any store. Conflicts with existing decisions are listed, and the user chooses which to keep (or passes a flag preferring incoming or existing ones).
- **Configuration fragments:** accepted aliases, criteria and forced table strategies can be exported as configuration for future runs.

### Decisions (2026-09-24)

- **Reviewer corrections:** none per claim; an errata document added to the source (e.g. `errata.md`) is ordinary content.
- **Content vs annotation:** if the tool doesn't know why something is there, it's content, with a provenance annotation giving its context. Speaker notes, comments and unrecognized front matter are content.
- **Document versions:** always read documents as they currently are (for `.docx`, with tracked changes applied), never earlier versions within one file; anything else confuses people.
- **Disagreements:** recognized by the model and recorded as derived claims with severity and a handling decision, which may lower confidence in the claims involved.
- **External sources:** most sources are external, so nothing special; "external" is just a field in a source's provenance annotation if a user wants it.
- **Authorship:** not required, any more than for the rest of the configuration. If wanted, the tool asks once on first use and stores an e-mail address in `$XDG_CONFIG_HOME/<tool>/reviewer_id` (default `~/.config/<tool>/reviewer_id`), then stamps it on reviewer decisions.
- **Configuration changes and resets:** reviewer decisions and other configuration force a (selective) reset or re-run only when they affect model derivations; changes that affect only final reports never do.
- **Provider markings:** Markdown front matter. Provenance annotations can grow large, so exports relate content to them with short tags instead of repeating them (see *Provenance tags* in [single-source-outputs](single-source-outputs-2026-09-23.md)).

## Comparison consequences

Because evidence belongs to content, comparing two sources starts with a cheap content difference:

- **Shared content** needs no model calls. Its evidence is identical by construction, and the report lists it as unchanged, including renames and moves.
- **Removed vs added content** is where comparison effort goes: retrieval runs over evidence from removed and added content, plus shared content as a target, so facts moved from a changed file into an unchanged one are still found.
- This applies to proposals too: if two teams both include the same rules PDF, it is recognized as common automatically.

For revisions, this can cut model calls dramatically when a new version changes only a few files.

## CLI

Staged subcommands. The current two-file form stays as a shortcut that runs all stages with a temporary store.

```
extract <source> [<source> ...] --store <dir> [--reset]
compare --store <dir> <source> <source> [--mode proposals|revisions]
show --store <dir> <view> [--format md|csv|jsonl]
report --store <dir> <comparison>
```

(`check`, `export` and N-way `compare` arrive with later plans.)

## Folder and archive concerns

- **Hidden files are ignored:** any file or folder whose name starts with `.`, at any depth and inside archives, is skipped (listed in the coverage record as hidden, never read).
- **Near-duplicate files** such as `report_v2_final_FINAL.pdf`: identical content is handled by content IDs. Near-duplicates (different bytes, mostly the same claims) are flagged in reports, not merged.
- **Heading-path context:** send the section heading path with each text group, so the model can tell which component a sentence is about.
- **Provenance in reports:** show `source / relative/path.pdf / section / p.12`, plus "also at …" for duplicate occurrences.
- **Zip archives as folders:** a `.zip`, given as the source or found inside one, is read without extracting to disk. Safety limits are generous backstops against pathological input, not restrictions on normal use; all are configurable:
  - reject absolute paths and `..` members (zip-slip), even though members are never written to disk under their own names
  - nesting depth: at least 4 levels; default 8
  - size backstops, set high: e.g. total uncompressed bytes per source in the tens of GB, and a compression-ratio check only on large members (e.g. over 1000:1 for members above 100 MB). Anything over a limit is recorded as a task outcome, not silently dropped.
  - record encrypted members as `skipped` rather than failing
  - ignore OS clutter (`__MACOSX/`, `.DS_Store`, `Thumbs.db`)

  Other archive formats (`.tar.gz`, `.7z`) can use the same interface later if needed.
- **Names across files** ("P-101" in an equipment list vs "primary pump" in the narrative) get more common in folders. That is handled by alias consolidation in [retrieval-recall](retrieval-recall-2026-09-23.md), not here.

## Milestones

1. **Schema v2:** content, file, source and interpreter model; content-relative locators; derivation chains; claim context fields (topic, basis, uncertainty, context, role) in the schema, filled by the prompt work in [scheduling-and-triage](scheduling-and-triage-2026-09-23.md); migrate `compare` and `report` off A/B.
2. **Store folder and SQLite:** WAL, single-writer lock, task queue with per-task transactions, response cache in the database, interpreter binding with rejection, selective `--reset` and `--dry-run`; resume after interruption (tested by killing a run midway).
3. **Annotations core:** the annotation table and record format; source provenance at registration and in manifests; extracted provenance from PDFs (document properties, sections, comments as content with context); export and import of reviewer decisions; orphan re-attachment. Capture from reports comes with its first consumer (reviewer feedback in scheduling-and-triage); model-recognized disagreements come with `check`.
4. **PDF sections:** outline → font-size headings → page ranges; heading path in prompts. Real documents are sensitive and won't be shared (the tool runs inside a multi-layer sandbox), so heuristics are developed against the public corpus (see [Samples](#samples)) and must fall back gracefully when there's no outline or consistent heading font.
5. **Folder, zip and manifest sources;** duplicate occurrences in provenance.
6. **Content-difference-first comparison** (shared / removed / added).
7. **Views, `show` and the staged CLI,** with the current two-file command kept working; tests and docs.

## Decisions (2026-09-23)

- **Store format:** SQLite inside a store folder, with auxiliary files (crops) beside it and HTML reports generated from it.
- **Revision metadata:** none needed; revisions are content differences.
- **Files without extensions:** not interpreted, no evidence, listed as skipped.
- **Extension aliases:** collapse only those known to share an interpretation.
- **Model or interpreter changes:** rejected; new store or explicit `--reset`.
- **Store scope:** one local folder, shared at any scope the user chooses; typically a few revisions and a few teams per user.
- **What affects output:** anything sent to a model, plus anything that shapes chunking or sections (see *Interpreter* above). External converters are tracked best-effort; their hidden configuration is the user's responsibility.
- **Comparison settings** (retrieval options, aliases, comparison model) are recorded **per comparison**, not bound to the store. Each comparison is a self-contained record, so a user can re-run one with a larger `top_k` without any reset.
- **Binding is a default guideline:** where a change obviously affects only part of the derived data, `--reset` clears just that part (see *Interpreter* above).
- **Upgrades:** internal prompt versions and library versions are tracked and a change is rejected like any other interpreter change. That is acceptable because most users install once, spend a while on configuration, then use the same setup for a long time; upgrades are rare, deliberate events where a `--reset` or new store is expected.
- **Future:** external converters (e.g. opening Cameo `.mdzip` models into recognized formats) are planned in [multi-format-adapters](multi-format-adapters-2026-09-23.md). They fit the content model: the converter and its version are part of the interpretation, and its outputs are derived content with provenance back to the original.

## Open questions

None currently.

## Samples

`python scripts/fetch_samples.py` downloads a public test corpus into the git-ignored `samples/` folder and verifies pinned SHA-256 hashes (sources and terms are in `scripts/samples.json`). Relevant sets:

- `solar-decathlon-2013`: four competing teams, one folder per team (drawings, project manual, jury scoresheets), plus shared rules. `--make-zips` also packs each team folder into a zip, which exercises archive reading and duplicate content (the same bytes loose and zipped).
- `wind-reference-turbines`: three reference designs, each a folder with a PDF report and, for two of them, an `.xlsx` spreadsheet.
- `ietf-quic-transport`: text revisions, useful for testing content-difference comparison once adapters for text exist.
- The 3GPP sets and `archive-edge-cases`: natural zips (one file per company, some with `__MACOSX/` clutter), nested zips, and a legacy `.doc` that should be listed but skipped.

## Out of scope

Non-PDF formats, rate-aware scheduling, N-way comparison, summaries and export. Each has its own plan.
