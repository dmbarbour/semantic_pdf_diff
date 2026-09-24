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

#### Available in-house models (as of 2026-09-23)

| Model | Max input tokens | Dimensions | Notes |
|---|---|---|---|
| `llmrails/ember-v1` | 512 | 1024 | English |
| `sentence-transformers/all-MiniLM-L6-v2` | 256 | 384 | Smallest and fastest; a good baseline |
| `sentence-transformers/all-mpnet-base-v2` | 384 | 768 | English |
| `intfloat/multilingual-e5-small` | 512 | 384 | Multilingual |
| `intfloat/multilingual-e5-large` | 512 | 1024 | Multilingual; largest, likely slowest |

Implications:

- **Input limits don't constrain claims.** A claim topic (`entity | attribute | conditions`) is typically tens of tokens, well under every limit. They do constrain **sections**, which exceed all of them. The preferred approach is an **"about" statement**: a short model-written description of what the section is about (subject, scope, components and kinds of information covered) that deliberately omits its specific values and decisions. This mirrors embedding a claim's topic rather than its value: sections on chilled-water plant sizing should match even when one team chooses 2 × 500 kW chillers and the other 3 × 350 kW. It is produced by the section triage call ([scheduling-and-triage](scheduling-and-triage-2026-09-23.md)), which can read the whole section given the deployment's 262,144-token context. It is kept to a few sentences so it fits every embedding model's input limit, and built from subsections' statements only for sections too large for one request. Embedding chunks and pooling the vectors is the fallback to compare against in the benchmark.
- **Prefixes are part of the interpreter.** E5 models expect `query: ` / `passage: ` prefixes (use `query: ` on both sides for symmetric claim-to-claim similarity). Check each model card for similar conventions. Whatever prefix is used gets recorded with the embedding interpreter, since changing it changes the vectors.
- **Throughput isn't known yet;** measure it in the benchmark. Model size suggests MiniLM is several times faster than the others and e5-large the slowest. At our scale (thousands of short claim strings per store) even the slowest is probably fine, but section chunks could be much more numerous.
- **All five are benchmark candidates.** Dimensions matter little for storage at this scale.

## Milestones (after the benchmark exists)

1. Embedding client plus cache; hybrid retrieval behind a setting.
2. Keyword field in extraction; per-project consolidation into an alias map.
3. Cross-project vocabulary merge.
4. Choose defaults from benchmark results; document the tradeoffs.

## Open questions

- Measured throughput of each in-house model on our hardware (to be measured in the benchmark).

## Decisions (2026-09-23)

- **Available models:** listed above.
- **Language:** current sources are English, so English models are the default candidates. Keep the multilingual E5 models in the benchmark and as a configurable option, since future users may have other languages; don't assume English anywhere it is cheap not to (e.g. tokenization already uses Unicode word rules).
- **Alias maps and other reviewer decisions:** every human QA judgment is **reusable data**. Accepting or rejecting a proposed alias, confirming a keyword merge, correcting an extraction or labelling a benchmark pair are all stored as annotations keyed by stable IDs. They survive report regeneration and store resets, can be exported as their own report and imported into another store, and, for alias decisions, can be exported as a configuration fragment (the `aliases` mapping). Aliases shape retrieval, which is recorded per comparison, so applying an updated alias map never needs a store reset. The annotation mechanism itself (storage, capture from reports, import and export) is shared with other plans and will be designed where it is first needed.
