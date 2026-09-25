# Evaluation benchmarks: extraction and retrieval

- **Status:** Active (2026-09-25): review tooling and the first batch done. Claude will build most of this with you. Your main job is checking labels. Embedding models run locally (see [retrieval-recall](retrieval-recall-2026-09-23.md)), so this no longer waits on in-house access.
- **Depends on:** [test-models-and-record-replay](test-models-and-record-replay-2026-09-24.md) for responder tables (Claude, weak local VLM, in-house gemma-4); easier once [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) produces evidence stores to sample from.
- **Informs:** [retrieval-recall](retrieval-recall-2026-09-23.md), prompt and extraction work in [scheduling-and-triage](scheduling-and-triage-2026-09-23.md) and [multi-format-adapters](multi-format-adapters-2026-09-23.md), and [n-way-comparison](n-way-comparison-2026-09-23.md)

## What this is, in plain terms

The project has no accuracy numbers yet. The README has always said that extraction recall, retrieval recall and the precision of reported differences must be measured on labelled examples (especially dense charts, table continuations and diagram topology) before relying on findings. This plan turns that into benchmarks:

- **Extraction:** did we get the right claims out of each page, table, chart and diagram, with the right values, qualifiers and provenance?
- **Retrieval:** does the cheap pairing step find the claims worth comparing?
- **Comparison:** are the relations it reports (equivalent, different…) right?

A **benchmark** is a fixed answer key plus a scoring script, rerun whenever the pipeline changes.

Glossary:

- **Recall:** of everything that should have been found, the fraction that was found.
- **Precision:** of everything that was found, the fraction that is right.
- **Retrieval:** the cheap step that picks candidate claim pairs (or claim-to-criterion matches) for the model to judge.
- **TF-IDF:** the current retrieval method. Two claims are related if they share words, with rare words counting more.
- **Embedding:** a model that turns text into a list of numbers so that texts with similar meanings end up close together, even without shared words.
- **Recall@k:** retrieval recall when each claim keeps its top *k* candidates; `top_k` in settings is this *k*.

## Extraction quality

Retrieval and comparison can only be as good as the claims extracted, and extraction is where a small model most often goes wrong.

### What is measured

| Measure | Question |
|---|---|
| **Claim recall** | Of the claims a careful reader would extract, how many did we get? |
| **Claim precision** | Of the claims we extracted, how many are real and correctly stated? |
| **Hallucination rate** | How many extracted claims have no support in the source at all? (The worst kind of precision error, counted separately.) |
| **Value accuracy** | For matched claims: is the value exactly right, or within tolerance for readings flagged approximate (e.g. chart estimates)? Are units right? |
| **Qualifier accuracy** | Are conditions, basis (measured, projected, required…), stated uncertainty and context captured, or silently dropped? |
| **Provenance accuracy** | Does the claim point to the right file, page or slide or cell range, and region? Is `quote_verified` right? |
| **Coverage honesty** | When claims were missed, did the task report itself *partial* rather than *complete*? A miss the coverage record admits is far less harmful than a silent one. |

Everything is reported per responder, per claim kind (text, table, chart, diagram) and per format, because the failure modes differ.

### Test material

- **Curated slice of the public corpus:** the same pages and tables as the replay fixtures, chosen to include the hard cases: dense tables and table continuations, charts with log or truncated axes, diagrams with directed connections, scanned pages, and multi-table spreadsheets. For each item, a hand-checked **expected-claim list**. Claude drafts it; the owner checks it.
- **Synthetic documents with known contents:** generated like the messy spreadsheet, so the ground truth is exact by construction and needs no labelling: PDFs, `.docx` and `.pptx` containing tables with known values, charts drawn from known data (with log axes, missing error bars, and deliberate traps), diagrams with known connections and arrow directions, and text with known qualifiers (requirements vs projections, stated tolerances). `scripts/make_synthetic_samples.py` grows to produce these, each with an answer key.
- **Real documents:** a spot check inside the sandbox confirms that public-corpus results carry over. Those labels never leave it.

### Matching extracted claims to expected ones

Claims are never phrased identically, so scoring needs a matching step:

1. **Automatic match** on normalized entity and attribute (with aliases), value and unit (unit-aware, see [units-and-normalization](units-and-normalization-2026-09-24.md)) and locator overlap.
2. **Adjudication** of the leftovers: unmatched expected claims and unmatched extracted claims are shown side by side, and the labeller decides "same claim", "wrong value", "missing" or "hallucinated". Claude drafts; the owner checks.
3. Adjudications are stored as labels too, so reruns only need adjudicating what changed.

### Responders

Extraction is scored for every responder table from [test-models-and-record-replay](test-models-and-record-replay-2026-09-24.md): Claude (a strong reference, roughly the ceiling), the weak local VLM (the floor), and in-house gemma-4 (the number that matters). Differences between prompt versions are measured by re-recording the slice under the new prompt.

## Situating quality

For the situating stage ([scheduling-and-triage](scheduling-and-triage-2026-09-23.md)):

- **Figure–reference links:** label which prose cites which figure on curated pages. Score link precision and recall, and figure detection recall (reports' unresolved-reference counts are a label-free proxy).
- **"About" statements:** rate usefulness and correctness (does it say what the section or figure is about, without values?). Also measure whether "about" embeddings align sections across sources better than headings alone.
- **Synthetic diagrams with known structure:** generate block diagrams and flow graphs from known graphs (e.g. via Mermaid or Graphviz) into PDFs, with captions and citing prose. The ground truth (nodes, edges, direction, references) is exact by construction. They test visual extraction, situating, and the structured-text and vector-geometry alternatives alike.

## Retrieval and comparison

1. **Pick documents.** Start from the public corpus fetched by `scripts/fetch_samples.py`. It has competing proposals (`solar-decathlon-2013` teams, the `wind-reference-turbines` designs, the 3GPP company contributions, where the moderator summaries give a head start on which positions correspond), revisions (`ietf-quic-transport`, the IEA 15 MW spreadsheets, the NASA interim and final reports) and natural vocabulary drift between authors.
2. **Extract claims (tool).** Run extraction to get evidence stores (or replay recorded responses).
3. **Propose candidate pairs (Claude).** Take a generous union of candidates from several methods (TF-IDF at high `k`, embeddings, keyword overlap), plus random pairs as controls. Casting a wide net matters: labelling only what TF-IDF finds would hide exactly the misses we want to measure.
4. **Label (Claude drafts, you check).** A small labelling page shows each pair side by side with its source crops. Choices: *same topic*, *different topic*, *unsure*, plus the relation for same-topic pairs (equivalent / different / complementary / unrelated). Once criteria exist, the page also labels "does this claim address this criterion?". Claude can pre-fill suggestions so you mostly confirm; aim for a few hundred pairs.
5. **Score (tool).** Recall@k and precision for each method and setting, as a table and chart, split by claim kind and by within-source vs between-source pairs; accuracy of the comparison step's relations; and each in-house embedding model's throughput on our hardware.
6. **Spot-check on real documents** inside the sandbox.

### Methods to compare (first round)

- TF-IDF (current), with and without the current aliases
- each available in-house embedding model, embedding claim topics without values
- hybrid: TF-IDF ∪ embedding
- with model-generated section keywords added (once that exists)

## Keeping it

All answer keys for the public corpus (expected-claim lists, adjudications, pair and relation labels, claim-to-criterion labels) are committed to the repo as annotation export files (see *Annotations* in [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md)), editable by hand, and rerun whenever extraction, retrieval or comparison changes, as a regression check. Labels for real documents stay inside the sandbox.

## Deliverables

- `benchmarks/` with the labelling page, the scoring scripts, and the public-corpus answer keys as annotation export files
- synthetic documents with known contents (PDF, `.docx`, `.pptx`), generated by script with answer keys
- **reviewer-decision variants:** deliberately "good" and "bad" sets of reviewer decisions (aliases, criteria, forced table strategies) as export files, to measure how much those decisions move results, and to check that a bad set degrades them visibly rather than silently
- a short results write-up per round: extraction scores per responder and kind, recommended retrieval defaults
- first real accuracy numbers for the project, replacing the README's disclaimer with measured ones

## Milestones

1. Scoring for extraction against the existing synthetic spreadsheet keys, and claim matching with adjudication.
2. Synthetic PDF, `.docx` and `.pptx` documents with answer keys.
3. Expected-claim lists for the curated slice; first extraction scores for the Claude and weak-VLM tables.
4. Labelling page and retrieval scoring; first retrieval results with local embeddings.
5. gemma-4 scores once the in-house table is recorded.
6. Relation and claim-to-criterion labels once criteria-first comparison exists.

## Decisions (2026-09-25)

- **Reviewers:** the owner, Claude in a session, and a panel of hosted models from different families (first panel: gemini-3.1-pro, Qwen3.5-397B, Kimi-K3), each labelling independently. Nobody is ground truth; agreement is measured (Krippendorff's α) and disagreement kept. The model under test doesn't judge its own work.
- **Every label records clarity** (clear / context insufficient / source illegible / item ambiguous) **and the reviewer's confidence** (high / medium / low), so faults in the question are told apart from faults in the answer.
- **Verdict, then flags:** a coarse verdict per item and multi-select error flags from a taxonomy consolidated from published error analyses (entity and scope binding first). See `benchmarks/README.md`.
- **Review page:** a local, self-contained HTML page (works offline and in the sandbox for real documents), one item per screen, progress saved in the browser, labels exported as a file and imported with `review import`. Batches of about 15–20 items per session.
- **Evidence-web relations** (component of, input to, output of, source of, contradicts…) get their own item type when that work starts.
- First batch and findings: [evaluation-s01 review](../reviews/evaluation-s01-2026-09-25.md).

## Decisions (2026-09-24)

- **Public-corpus labels live in the repo,** as annotation export files that can be edited by hand. Real-document labels stay in the sandbox.
- **Reviewer-decision variants:** keep "good" and "bad" decision sets as export files to test that lever.
- **Relation labels:** the labelling page also records how a same-topic pair relates, so the comparison step's judgments can be measured, not just whether retrieval found the pair.
- **Claim-to-criterion labels:** once criteria exist, the benchmark also labels "does this claim address this criterion?", measuring the second retrieval task.
- **Extraction quality is measured,** expanding the README's sketch: recall, precision, hallucinations, values, qualifiers, provenance and coverage honesty, on curated public pages and synthetic documents with known contents.
- Anything else that makes testing and benchmarking convenient is welcome.

## Open questions

None currently.
