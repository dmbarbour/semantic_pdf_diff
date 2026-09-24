# Retrieval benchmark

- **Status:** Planned. Claude will build most of this with you. Your main job is checking labels. Embedding models run locally (see [retrieval-recall](retrieval-recall-2026-09-23.md)), so this no longer waits on in-house access.
- **Depends on:** nothing strictly. It is easier after [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) produces evidence stores to sample from.
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
5. **Score (tool).** A script that reports recall@k and precision for each method and setting, as a table and chart, split by claim kind (text/table/chart/diagram) and by within-source vs between-source pairs. It also measures each in-house embedding model's throughput on our hardware.
6. **Keep it.** Answer keys for the public corpus are committed to the repo as annotation export files (the same format as any exported reviewer decisions; see *Annotations* in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md)), editable by hand, and rerun whenever retrieval or comparison changes, as a regression check. Labels for real documents stay inside the sandbox.
7. **Spot-check on real documents** inside the sandbox, to confirm that public-corpus results carry over to real documents.

## Methods to compare (first round)

- TF-IDF (current), with and without the current aliases
- each available in-house embedding model, embedding claim topics without values
- hybrid: TF-IDF ∪ embedding
- with model-generated section keywords added (once that exists)

## Deliverables

- `benchmarks/retrieval/` with the labelling page, the scoring script, and the public-corpus answer keys as annotation export files
- **reviewer-decision variants:** deliberately "good" and "bad" sets of reviewer decisions (aliases, criteria, forced table strategies) as export files, to measure how much those decisions move results, and to check that a bad set degrades them visibly rather than silently
- a short results write-up recommending default retrieval settings
- first real accuracy numbers for the project (the README currently has none)

## Decisions (2026-09-24)

- **Public-corpus labels live in the repo,** as annotation export files that can be edited by hand. Real-document labels stay in the sandbox.
- **Reviewer-decision variants:** keep "good" and "bad" decision sets as export files to test that lever.
- **Relation labels:** the labelling page also records how a same-topic pair relates (equivalent / different / complementary / unrelated), so the comparison step's judgments can be measured, not just whether retrieval found the pair.
- **Claim-to-criterion labels:** once criteria exist, the benchmark also labels "does this claim address this criterion?", measuring the second retrieval task.
- Anything else that makes testing and benchmarking convenient is welcome.

## Open questions

None currently.
