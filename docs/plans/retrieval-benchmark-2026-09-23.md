# Retrieval benchmark

- **Status:** Planned (future). Claude will build most of this with you. Your main job is checking labels.
- **Depends on:** nothing strictly. It is easier after [projects-and-evidence-store](projects-and-evidence-store-2026-09-23.md) produces evidence stores to sample from.
- **Informs:** [retrieval-recall](retrieval-recall-2026-09-23.md), and later [n-way-comparison](n-way-comparison-2026-09-23.md)

## What this is, in plain terms

The tool can only compare claims that its **retrieval** step pairs up. If retrieval misses a pair, the comparison never happens, and the report just shows two "unmatched" claims.

We have ideas for better retrieval (model keywords, embeddings), but no way to tell whether they actually help. A **benchmark** is a fixed answer key: a list of claim pairs where a person has decided "these are about the same thing" or "these aren't". Run each retrieval method against it and count how many of the true pairs each one finds.

Glossary:

- **Retrieval:** the cheap step that picks candidate claim pairs for the model to compare.
- **TF-IDF:** the current retrieval method. Two claims are related if they share words, with rare words counting more.
- **Embedding:** a model that turns text into a list of numbers so that texts with similar meanings end up close together, even without shared words.
- **Recall@k:** of all the true pairs in the answer key, the fraction found when each claim keeps its top *k* candidates. Higher is better; `top_k` in settings is this *k*.
- **Precision:** of the candidates retrieved, the fraction that are true pairs. Lower precision means more wasted model calls, not wrong answers.

## How we'd build it

1. **Pick documents.** Real project documents are sensitive and unavailable, so start from the public corpus fetched by `scripts/fetch_samples.py`. It has competing proposals (`solar-decathlon-2013` teams, the `wind-reference-turbines` designs, the 3GPP company contributions, where the moderator summaries give a head start on which positions correspond), revisions (`ietf-quic-transport`, the IEA 15 MW spreadsheets, the NASA interim and final reports) and natural vocabulary drift between authors. Later, the same tooling can be run inside the sandbox on real documents to check that public-corpus results carry over; those labels would never leave it.
2. **Extract claims (tool).** Run extraction to get evidence stores.
3. **Propose candidate pairs (Claude).** Take a generous union of candidates from several methods (TF-IDF at high `k`, embeddings, keyword overlap), plus random pairs as controls. Casting a wide net matters: labelling only what TF-IDF finds would hide exactly the misses we want to measure.
4. **Label (Claude drafts, you check).** A small labelling page shows each pair side by side with its source crops. Choices: *same topic*, *different topic*, *unsure*. Claude can pre-fill suggestions so you mostly confirm; aim for a few hundred pairs. Your judgement is the ground truth.
5. **Score (tool).** A script that reports recall@k and precision for each method and setting, as a table and chart, split by claim kind (text/table/chart/diagram) and by within-project vs between-project pairs.
6. **Keep it.** The answer key is versioned in the repo (or an in-house location) and rerun whenever retrieval changes, as a regression check.

## Methods to compare (first round)

- TF-IDF (current), with and without the current aliases
- each available in-house embedding model, embedding claim topics without values
- hybrid: TF-IDF ∪ embedding
- with model-generated section keywords added (once that exists)

## Deliverables

- `benchmarks/retrieval/` with the answer key format, the labelling page and the scoring script
- a short results write-up recommending default retrieval settings
- first real accuracy numbers for the project (the README currently has none)

## Open questions

- Can labels for the public corpus live in this repo (they describe public documents), with labels for real documents kept only in the sandbox?
- Do results on the public corpus predict results on real documents? A small in-sandbox spot check would tell.
- Should the same labelling page also collect relation labels (equivalent / different / …) so we can later measure the comparison step, not just retrieval?
- Criteria-first comparison adds a second retrieval task, claim to criterion. Should the benchmark also label "does this claim address this criterion?" once criteria exist?
