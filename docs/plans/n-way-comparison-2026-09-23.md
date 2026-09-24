# Comparing more than two projects

- **Status:** Tentative
- **Depends on:** [projects-and-evidence-store](projects-and-evidence-store-2026-09-23.md); benefits from [retrieval-recall](retrieval-recall-2026-09-23.md)

## Goal

Compare N projects at once: several competing proposals, or an ordered series of revisions v1…vN.

## Why not run every pair

Running the two-way comparison on every pair multiplies model calls by roughly N², and produces N² separate reports that nobody can read together.

## Design

1. **Retrieval over all claims** from all projects at once, forming **topic clusters** (entity + attribute + conditions) instead of A→B candidate lists.
2. **Compare within each cluster:** each project's claim against a representative claim for the cluster, giving O(N) model calls per cluster rather than O(N²). The numeric check extends to N values for free.
3. **Comparison matrix report:** rows are topics, columns are projects, cells hold values with provenance and judgments. Filters include "rows where projects disagree" and "rows missing from some projects". For proposal evaluation this is what reviewers actually want.
4. **Revision mode** becomes an ordered series, with deltas between consecutive versions.

## Semantics to handle honestly

- **Judgments are not transitive.** A≈B and B≈C do not imply A≈C, especially with approximate readings. Each cell shows its own evidence and judgment, not an inferred group verdict.
- **"Not found" stays weak.** A topic present in 3 of 5 projects reads "no counterpart retrieved in D, E", never "D and E lack it". The matrix makes gaps look like absences, so the UI must counter that.
- **Symmetry:** proposal mode ranks no one. Cluster representatives must not favour whichever project was processed first.

## Milestones

1. Topic clustering over multiple stores (lexical, then hybrid once retrieval-recall work lands).
2. Comparison within clusters against a representative; N-value numeric checks.
3. Matrix report with disagreement and missing-counterpart filters.
4. Ordered revision series.

## Open questions

- How should a representative claim be chosen: most reliable, most specific, or a medoid in embedding space?
- What is a realistic N? The report design differs between 3 projects and 20.
- Does this replace the two-way comparison internally (N = 2 as a special case), or sit beside it?
