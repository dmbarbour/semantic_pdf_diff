# Criteria-first comparison of sources

- **Status:** Planned (design settled 2026-09-24). Next after scheduling-and-triage: this is the main use case, since two-way proposal comparison goes criteria first too.
- **Depends on:** [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (claim context fields, store); uses section "about" statements from [scheduling-and-triage](scheduling-and-triage-2026-09-23.md) to recommend criteria; benefits from [retrieval-recall](retrieval-recall-2026-09-23.md)

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

Every claim, for every source and regardless of comparison, records its topic and "aboutness", basis, context (initial or final, scenario, phase) and role in the design. This lands with schema v2 in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md).

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
- **Entered or edited by users.** Every criterion can be added, merged, split, reworded or dropped. Changes are stored as reusable annotations that can be exported, imported and kept as configuration (see [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (*Annotations*)).

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

## Milestones

1. **Criteria:** records built on annotations (provenance, review state, export and re-import for editing); extraction from reference documents and the user's rubrics; model recommendation from "about" statements.
2. **Mapping** sources to criteria, with applicability outcomes.
3. **Per-source synthesis:** context selection, derived implications, model-judged statistics.
4. **Cross-source description** within each criterion: mechanical statistics plus one model request per criterion describing agreement, spread, outliers and incomparable positions.
5. **Matrix report** with source picking and pinning; two-way proposals switch over from claim-level comparison here.
6. **Ordered revision series** (claim-level, content-difference first).

## Decisions (2026-09-24)

- **Context:** the gemma-4 deployment serves 262,144 tokens. Criterion-level requests hold all positions with generous context; splitting into groups is a rare fallback.
- **Scale of N:** 4 or fewer is typical, 8 is large, and there is no artificial limit.
- **Report legibility at any N:** one general matrix renderer. Self-contained inline JavaScript (no external resources; data embedded as escaped JSON and never evaluated or inserted as raw HTML, as for all reports) lets the reader choose which sources are shown as columns, pin one for side-by-side reading, and filter criteria. All sources are shown by default up to about five; beyond that the report opens on a subset with a source picker. The per-criterion distribution description always covers *all* sources, so a subset view never hides the overall picture.
- **Two- and three-way cases** use the same pipeline and renderer (N = 2 is just two columns). Presentation conveniences for small N (e.g. side-by-side evidence cards, as today) are tweaks within that renderer, not separate code paths, to keep implementation simple.
- **Two-way proposals** therefore also go criteria first. Today's claim-level pairwise comparison remains the method for revisions.

## Open questions

None currently. Units, normalization and money are planned in [units-and-normalization](units-and-normalization-2026-09-24.md).
