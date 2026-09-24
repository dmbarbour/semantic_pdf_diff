# Better retrieval recall: model keywords, alias consolidation, embeddings

- **Status:** Tentative. Decide what to build from [retrieval-benchmark](retrieval-benchmark-2026-09-23.md) results.
- **Depends on:** [projects-and-evidence-store](projects-and-evidence-store-2026-09-23.md) (sections), [retrieval-benchmark](retrieval-benchmark-2026-09-23.md) (to measure)

## Problem

Before the model compares anything, a cheap step decides **which pairs of claims are worth comparing**. That step is called retrieval. Today it uses TF-IDF, which scores two claims as related when they share words, giving more weight to rare words ("chiller") than common ones ("system"). It is fast and transparent, but it **misses related claims that share no words**, e.g. "CHW supply temperature" vs "chilled water flow temp". Manual `aliases` help but don't scale. A missed pair is never compared, and never shows up in the report except as "unmatched".

This gets worse with more files, more projects (the [n-way-comparison](n-way-comparison-2026-09-23.md) plan) and more drift in vocabulary between teams.

## Candidate improvements

### 1. Model-generated keywords per section

Ask the model for relevant keywords as one extra output field while it reads a section. It already knows many synonyms and abbreviations. Pitfalls and how to avoid them:

- **Order dependence and caching.** Passing a running "previously used keywords" list into each prompt makes results depend on processing order. It also changes the prompt as the list grows, so editing one early file re-keys every later cached request. Instead:
  - **Pass 1:** free keywords per section, with no running list. This is order-independent and caches cleanly.
  - **Consolidation:** cluster the keywords into a canonical vocabulary (embedding similarity, plus small model batches to confirm merges). The output is a **reviewable alias map** that feeds the existing `aliases` mechanism.
- **Context budget.** If vocabulary is ever put into a prompt (e.g. consolidating one project against another), include only the top-k prior keywords that match the current section, never the full list.
- **Symmetry in proposal mode.** Build each project's vocabulary independently, then merge in a step that treats all projects equally. Otherwise team B's keywords are steered by team A's.
- Section-level keywords cost less than per-claim keywords. Claims inherit their section's keywords plus their own entity and attribute.

### 2. Embeddings

Several in-house embedding models are available behind (or easily put behind) an OpenAI-compatible `/v1/embeddings` endpoint, which fits the existing adapter, with a cache keyed on text hash. Likely uses, in order of expected payoff:

1. **Hybrid candidate retrieval:** the union of TF-IDF and embedding candidates. Embed a claim's *topic* (`entity | attribute | conditions`), **not its value**: we want "both are about pump power at design load", and numbers make embeddings noisy. Lexical retrieval stays in the mix because embeddings are often weak on tags like `P-101`.
2. **Keyword and entity clustering** for the consolidation step above.
3. **Topic clusters** for N-way comparison.
4. **Section alignment** between projects, to narrow the candidate space before claim-level matching.

## Milestones (after the benchmark exists)

1. Embedding client plus cache; hybrid retrieval behind a setting.
2. Keyword field in extraction; per-project consolidation into an alias map.
3. Cross-project vocabulary merge.
4. Choose defaults from benchmark results; document the tradeoffs.

## Open questions

- Which in-house embedding models are available, and what are their context limits and throughput?
- Should alias maps be committed alongside a project so reviewers can edit them?
