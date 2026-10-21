# Criteria-first comparison of sources

- **Status:** Planned (design settled 2026-09-24). Next after scheduling-and-triage: this is the main use case, since two-way proposal comparison goes criteria first too.
- **Since written (reviewed 2026-10-21):** the claim model this plan assumes (§1, "claims carry context") is now [claim context](claim-context-2026-10-14.md)'s: subject, scope, frame, provenance and stance kept apart. Revisions are no longer compared pairwise from the content difference: they're aligned items-first ([revision comparison](revision-comparison-2026-10-02.md)). Situating's "about" statements exist (PDFs only). Criteria built on reviewers' annotations need an annotation mechanism, which doesn't exist yet; its design is [Annotations](#annotations), from the retired store plan. `compare` takes exactly two sources. The portable report (gzipped parts, search, topics) is the base a matrix view would extend.
- **Proposals mode, from the closed [comparing revisions](revision-comparison-2026-10-02.md) plan (2026-10-21; its decision 9):** the owner, 2026-10-02: "Let's defer proposals comparison mode for a little bit longer, but it is an important use case that we shouldn't defer too much longer, so we should seek opportunities where it begins to make sense to pursue it." Its openings, as Claude read them:
  - alignment's signals scoring counterparts across two designs, with structure and kind standing in for anchors ([0038](../decisions/0038-revisions-aligned-then-differences-explained.md))
  - the entity register ([claim context](claim-context-2026-10-14.md))
  - the fetched competing sets: `3gpp-ran1-beam-management` (four companies' contributions on one agenda item) and `3gpp-rel19-aiml-views` (nine companies' views, in `.pptx`, `.docx` and PDF), readable since the adapters
  - controlled proposals: two fictional designs of one system from one fact sheet's kinds, counterparts known
- **Open question (from [review batch s01](README.md#retired), 2026-09-25, the owner's call):** what the relations mean across proposals. The panel called NREL 5 MW's pitch angle at 25 m/s against IEA 15 MW's pitch controller objective "unrelated" (different turbines), Claude "complementary"; in proposals the interesting relation is "same attribute, different value across designs", which today's labels mix with contradiction.
- **Depends on:** the evidence store (built: [0002](../decisions/0002-evidence-attaches-to-content.md), [0003](../decisions/0003-sqlite-evidence-store.md)) and claim context fields ([claim context](claim-context-2026-10-14.md)); uses section "about" statements from [scheduling-and-triage](scheduling-and-triage-2026-09-23.md) to recommend criteria; benefits from [retrieval-recall](retrieval-recall-2026-09-23.md)

## Goal

Compare two or more sources intelligently: competing proposals (two-way included), or an ordered series of revisions. **This project compares; it does not judge.** It produces no scores, rankings or rubric results, but it can organize comparisons around what a user will later judge by.

## Why not compare claims directly

Two claims can share a topic and still not be comparable. They may differ in:

- **role:** the same quantity doing different jobs in different designs (rotor speed of a utility turbine vs a rooftop turbine; irrelevant to a solar panel)
- **basis and context:** projected vs measured, initial vs final
- **implications:** a 22 kW motor means something different in a two-pump design than in a three-pump design

Projects that take different approaches toward the same end share their *ends*, not their mechanisms. So proposals are compared **by criteria**.

## Design

### 1. Claims carry their own context

Every claim, for every source and regardless of comparison, records its topic and "aboutness", basis, context (initial or final, scenario, phase) and role in the design. Schema v2 (2026-09-24) holds the fields (`topic`, `basis`, `uncertainty`, `context`, `role`), which prompts don't request yet ([how it works](../how-it-works.md#claims-and-provenance)); [claim context](claim-context-2026-10-14.md) carries the design now.

### 2. Criteria: an evidence-based QA step

A **criterion** is a question worth asking of every source, e.g. "annual energy delivered under the reference conditions", "how redundancy is provided", "compliance with rule 4.2". It states:

- what is being compared, and the basis and context it requires (e.g. final measured values)
- how to compare: direct values, normalized values (per kW installed, per m²), qualitative positions, or statistics
- that **"not applicable to this approach"** is a legitimate outcome, distinct from "no evidence found"

A criterion is **not a rubric**: it has no weights, scores or pass marks.

Criteria are **records with provenance, reviewed by people**, like other human QA data:

- **Extracted from evidence.** Projects often know what they'll be measured by, and say so: rules, requirements, RFP evaluation sections, agenda items, score sheets. The model extracts comparison criteria from such documents, citing them.
- **Aligned with the user's rubrics.** A user may supply the rubric or score sheet they plan to judge with, as a reference source. The tool derives criteria that will inform that judgment, without applying the rubric.
- **Recommended by the model,** by clustering the sources' "about" statements to find shared ends, clearly marked as proposals.
- **Entered or edited by users.** Every criterion can be added, merged, split, reworded or dropped. Changes are stored as reusable annotations that can be exported, imported and kept as configuration (see [Annotations](#annotations)).

The workflow is **propose → review → run**. Expensive comparison runs only after a person has seen the criteria. Before interactive views exist, review happens by editing an exported criteria file and importing it back.

### 3. Mapping sources to criteria

For each source and criterion, find the claims that address it (retrieval plus a model check). The outcome is *addressed* (with claims), *not applicable* (with the reason, e.g. a different approach), or *no evidence found* (weak, never "absent"). The cost is sources × criteria.

### 4. Per-source synthesis

Within one source, for one criterion:

- select claims matching the criterion's required basis and context (final over initial, measured over projected). The others stay visible.
- compute derived implications where the criterion needs them (e.g. total duty power = 2 × 22 kW), recorded in the derivation
- apply statistics only when the model judges the claims to be samples of one quantity; that judgment is recorded, not assumed

### 5. Cross-source comparison: describe the distribution

Within each criterion, **all sources' positions are compared together in one request**, not pairwise. Nine or even thirty positions with their context fit comfortably in gemma-4's context. The output is **descriptive, not a judgment**:

- **Mechanical statistics first** where values and units allow (normalized if the criterion says so): range, median, spread, and how many sources fall where. These are computed, not generated, and are given to the model as input.
- **The model then describes the distribution:** which sources agree (groups of equivalent positions), where they spread and by how much, outliers, and positions that differ in basis or context and so aren't directly comparable (e.g. three measured values and two projections). Qualitative positions are grouped the same way: which sources take the same approach, and how the others differ.
- Every statement names the sources and cites their evidence. No source is framed as the reference, and nothing is ranked.

Only if one criterion's positions exceed the context budget are they split into groups, described separately, then merged, and the report says so. Pairwise comparison is not the default anywhere in proposal mode.

### 6. Report

A **criteria × sources matrix.** Cells show the position, its evidence, its derivation and its applicability. Filters cover disagreement, "not applicable" and "no evidence found". The report ranks no one.

## Follow-up

**Approach-level comparison** (tentative, plan not yet written; see the [index](README.md)): summarize each source's approach, group sources that share one, and compare within groups on what only that approach makes comparable, recursively for subsystems. Criteria keep comparing across groups.

## Revisions

Revisions of one design are commensurable by default. They use claim-level comparison (today's pairwise approach), starting from the content difference: shared, removed and added content. Deltas run between consecutive versions of an ordered series. Criteria remain available when a user wants revisions viewed through them.

## Semantics to handle honestly

- **Judgments are not transitive.** A≈B and B≈C do not imply A≈C. Each cell carries its own evidence.
- **"No evidence found" stays weak.** The matrix makes gaps look like absences, so the UI must counter that.
- **Symmetry:** in proposal mode, nothing is framed relative to one source; criteria come from shared ends, not from one team's structure.

## Samples

- `solar-decathlon-2013`: shared rules plus per-team **jury score sheets**, ideal for extracting criteria from rubric-like documents without scoring.
- `3gpp-ran1-beam-management`: an agenda item and moderator summaries of each company's position, useful for checking proposed criteria and positions.
- `3gpp-rel19-aiml-views`: nine sources in mixed formats on one topic.
- `wind-reference-turbines`: similar systems at very different scales, a test for "comparable only after normalization" and "not applicable".

## Annotations

The record criteria are built on (milestone 1), designed in the retired [store plan](README.md#retired) (2026-09-23 to 24). Other consumers: aliases ([retrieval recall](retrieval-recall-2026-09-23.md)), *Reviewer feedback* and *Interactive views* ([plans index](README.md#tentative)), and the RAG export ([single-source outputs](single-source-outputs-2026-09-23.md)).

- **Built:** source metadata ([0002](../decisions/0002-evidence-attaches-to-content.md)); extracted provenance as columns on file, section and evidence rows (a PDF's title and author, sections and heading paths, locators, derivation, occurrences: [0005](../decisions/0005-union-provenance.md)); speaker notes and comments read as content ([0020](../decisions/0020-formats-share-one-task-core.md)). **Not built:** the `annotation` table, reviewer decisions, provider markings, disagreements as claims.
- **What they are:** what is provided by or through the tool: provenance supplied when a source is added; titles, authors and sections extracted and traced to files; derivation, confidence and quality signals; reviewers' decisions about how the tool should work (criteria, aliases).
- **Content, not annotation:** anything whose purpose the tool doesn't know, with a provenance annotation saying where it came from ("slide 42 speaker notes", "comment on §3.2").

| Kind | Examples | Lifetime |
|---|---|---|
| **Source provenance (user-supplied)** | title, organization, author, revision, date, whether the source is external, handling notes | kept across `--reset`; edited by the user |
| **Extracted provenance** | native document properties (title, author) traced to files; sections and heading paths; locators with context ("slide 42 speaker notes", "comment by …"); derivation chains; confidence and quality signals | derived, so it follows the extraction interpreter like evidence |
| **Provider-declared** | recognized Markdown front matter keys, such as title, author or a provider's confidence level (e.g. from the Cameo export) | derived from content; passed through without judgment |
| **Reviewer decisions** | criteria added, edited, merged or dropped; aliases accepted or rejected; a table mapping or strategy forced; a finding marked useful or not; benchmark labels | kept across `--reset`; re-attached or orphaned (below) |

- **A record:** a target by stable ID (source, file, content, section, evidence, a pair of evidence IDs, criterion, alias proposal, table interpretation or comparison); a kind and value, with an optional note; for reviewer decisions, a context snapshot of what the reviewer saw (quotes, values, paths), so it reads on its own and can be re-attached; the time, and optionally a reviewer ID.
- **Survives regeneration and resets:** evidence IDs are content-based. After a reset or a model change, a reviewer decision whose target is gone is orphaned, not deleted: the tool re-attaches it by its context snapshot and lists what stays orphaned. Removing a source leaves its decisions orphaned unless they're removed explicitly.
- **Reviewer decisions are configuration:** a change that affects model derivations redoes what it affects (a forced table strategy, that table's evidence; edited criteria or aliases, the comparisons they change); one that affects only reports (a usefulness mark) redoes nothing. Source provenance affects only reports and exports.
- **Disagreements are claims:** when the model recognizes that claims disagree (within one source, such as an errata document against the original, or between documents), the disagreement is recorded as a derived claim with context (which claims, how they differ, subtle or major) and the model's handling decision (the errata supersedes, or it's unresolved). Depending on both, the claims' reliability is lowered, and reports show why. This is what `check` produces ([single-source outputs](single-source-outputs-2026-09-23.md)).
- **Visible, never destructive:** reports show reviewer decisions and model-recognized disagreements beside the evidence they concern; evidence is never replaced or hidden.
- **Capture:** source provenance at registration (`source add --meta`, manifests); a file exported, edited and imported back (the review path before interactive views); report controls kept in the browser's local storage and exported as JSON for `import-reviews`; later, interactive views writing decisions directly.
- **Export and import:** a JSON file plus a readable report grouped by kind, with context snapshots. Import merges into any store, listing conflicts with existing decisions for the user to choose (or a flag preferring incoming or existing ones). Accepted aliases, criteria and forced table strategies export as configuration fragments.
- **Decided 2026-09-24:**
  - **No per-claim corrections:** reviewers use the tool to avoid reading the documents, with provenance as the basis for spot checks. A correction comes in as content, an errata document added to the source (e.g. `errata.md`), extracted like any new file; its conflicts with the original are disagreements, recorded as derived claims.
  - **"External"** is just a field in a source's provenance, for users who want it.
  - **Authorship** isn't required. If wanted, the tool asks once on first use, stores an e-mail address in `$XDG_CONFIG_HOME/<tool>/reviewer_id` (default `~/.config/<tool>/reviewer_id`) and stamps it on reviewer decisions.
  - **Provider markings** are Markdown front matter. Exports relate content to them with short tags (*Provenance tags* in [single-source outputs](single-source-outputs-2026-09-23.md)).

## Milestones

1. **Criteria:** records built on annotations (provenance, review state, export and re-import for editing); extraction from reference documents and the user's rubrics; model recommendation from "about" statements.
2. **Mapping** sources to criteria, with applicability outcomes.
3. **Per-source synthesis:** context selection, derived implications, model-judged statistics.
4. **Cross-source description** within each criterion: mechanical statistics plus one model request per criterion describing agreement, spread, outliers and incomparable positions.
5. **Matrix report** with source picking and pinning; two-way proposals switch over from claim-level comparison here.
6. **Ordered revision series** (claim-level, content-difference first).

*From the closed [evaluation benchmarks](README.md#retired) plan (2026-10-04):*
- **Claim-to-criterion labels:** "does this claim address this criterion?", measuring the second retrieval task, on the retrieval benchmark's review page.
- **Reviewer-decision variants:** deliberately good and bad sets of reviewer decisions (aliases, criteria, forced table strategies) as export files, to measure how much they move results and to check that a bad set degrades them visibly rather than silently.

## Decisions (2026-09-24)

- **Context:** the gemma-4 deployment serves 262,144 tokens. Criterion-level requests hold all positions with generous context; splitting into groups is a rare fallback.
- **Scale of N:** 4 or fewer is typical, 8 is large, and there is no artificial limit.
- **Report legibility at any N:** one general matrix renderer. Self-contained inline JavaScript (no external resources; data embedded as escaped JSON and never evaluated or inserted as raw HTML, as for all reports) lets the reader choose which sources are shown as columns, pin one for side-by-side reading, and filter criteria. All sources are shown by default up to about five; beyond that the report opens on a subset with a source picker. The per-criterion distribution description always covers *all* sources, so a subset view never hides the overall picture.
- **Two- and three-way cases** use the same pipeline and renderer (N = 2 is just two columns). Presentation conveniences for small N (e.g. side-by-side evidence cards, as today) are tweaks within that renderer, not separate code paths, to keep implementation simple.
- **Two-way proposals** therefore also go criteria first. Today's claim-level pairwise comparison remains the method for revisions.

## Open questions

None currently. Units, normalization and money are planned in [units-and-normalization](units-and-normalization-2026-09-24.md).
