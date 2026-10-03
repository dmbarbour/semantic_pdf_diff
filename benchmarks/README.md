# Benchmarks

What's measured, and what the measurements rest on. Only what tests replay or a reader needs is committed. Working data (rounds, review batches, spot checks, runs, the spend ledgers) stays local; what it showed is written up in docs. The owner, 2026-10-03: "I don't believe we need benchmark rounds, for example, though having a historical record of what was tested and the outcomes could be useful". The record is [docs/research/rounds.md](../docs/research/rounds.md).

Nobody is ground truth here. Each rater (people, model judges, exact keys, mechanical checks) is one estimate among others, and disagreement is kept as information.

## Layout

| Path | In git | Contents |
|---|---|---|
| `controlled/` | yes (not `fixture.sqlite`) | Controlled documents: PDFs, Markdown and Word versions with their answer keys, the recorded answers (`replay.zip`), and the scores (`results.json` for extraction, `comparisons.json` for revision pairs). Plan: [controlled documents](../docs/plans/controlled-documents-2026-10-01.md) |
| `eyetest/` | yes (not `images/`, not `report.html`) | Eye tests for vision models (`scripts/eye_test.py`): `results.json` compares the models; `replay.zip` holds their answers, which a test replays; the images and the report are drawn again on demand |
| `real-pairs/` | yes (not `fixture.sqlite`) | Real revision pairs (`scripts/real_pairs.py`): the settings, the recorded answers and the raters' results. Plan: [comparing revisions](../docs/plans/revision-comparison-2026-10-02.md) |
| `champion.json`, `round0.json` | yes | The defaults since the improvement rounds, and the settings before them (tests pin both) |
| `rounds/<name>/` | no | Improvement rounds (`scripts/run_round.py`): their specs, pairs, verdicts and decisions. Five batches that tests judge again offline are in `tests/fixtures/rounds/` |
| `batches/<name>/` | no | Review batches (`pdf-semantic-diff review sample`) and their labels |
| `spotchecks/<name>/` | no | Spot checks: a person judges the same pairs as the panel (`scripts/spotcheck.py`) |
| `pagetest/` | no | Page tests (`scripts/page_test.py`); the findings are in [page tests](../docs/research/page-tests-2026-10-01.md) |
| `runs/` | no | Stores replayed or recorded by the scripts above |
| `ledger.jsonl`, `history.jsonl` | no | Every model call's reported cost (the budget caps read it), and the rounds' figures; spend by month is in the rounds record |

## Reviewing a batch (for people)

Each batch has two pages. Do them in this order:

1. **`questions.html`: judge the questions, blind.** Each item shows only what the model was asked: a one-line summary of the kind of request, the section heading it was given, the exact input (text and images), and the full instructions, folded. Judge whether a careful reader could answer well from that input alone (enough, partly, not enough), what was missing, and whether it was worth asking. Optionally, write what you would extract. You never see the model's answer here.
2. **`review.html`: judge the answers.** The same input is shown with the model's answer. Judge each part of the answer against that input, and whether the claim is usable as evidence with its section attached.

Separating the two tells apart faults in what we ask (our chunking, headings, crops, context) from faults in how the model answers.

For each page:

1. Open it in a browser (double-click it; it works offline).
2. Type your name at the top. Work through the items, one per screen: pick a verdict, tick any flags that apply, say how clear the item was and how confident you are, and optionally leave a note. Click any image to zoom. `←` and `→` move between items.
3. Progress is saved in the browser as you go, so you can stop and come back (same browser, same file).
4. When done (or at any point), click **Download labels**. That saves `questions-<batch>-<name>.json` or `labels-<batch>-<name>.json`, usually to your Downloads folder. Then either:
   - run `pdf-semantic-diff review import benchmarks/batches/<name> <file>` (it tells the two kinds apart), or
   - tell Claude where the file is, or click **Copy labels** and paste the text into the conversation.

Batches are kept small (about 15–20 items, 10–20 minutes) so a session fits comfortably; more batches can follow.

### What to judge

- **Verdict first**, a coarse call: for a claim, *correct*, *usable but flawed*, *wrong* or *not a claim*.
- **Then flags**: every specific problem that applies (grouped: what is claimed, value and unit, conditions and basis, provenance, tables/charts/drawings, form). Each flag has an example on the page.
- **Clarity**: was the item judgeable? *Context insufficient*, *source illegible* and *item or question ambiguous* mark items where the fault may lie with the question, not the answer.
- **Confidence**: how sure you are of your own verdict.

## Spot checks (for people)

A spot check puts you in a judge's place. The items are the same page regions the panel compares. Two sets of claims read from one region are shown as A and B, in random order: one from round 0's queries, the other from the current champion. You aren't told which is which.

1. Open `spotchecks/<name>/spotcheck.html` in a browser and type your name.
2. For each item:
   - **Mark the claims one by one** if that helps: ✓ right, ✗ wrong, ? unsure; click again to clear.
     - Each claim can also carry its own problems.
     - Each set's header keeps a tally and a colour bar, so you can judge from the columns rather than holding 10–20 claims in your head.
   - **Below the claims, each set's totals are computed from your marks.** That covers ✓/✗/? and each problem's count. The only thing to tick for a whole set is whether important facts are missing from it, since no single claim shows that.
   - **Then say which set is better** and how sure you are. A note is optional. Folds you open stay open while you answer.
   - The picture is the part of the page that was read; click it to enlarge.
   - The page's text layer and the text just before it are folded under the picture.
3. Answer as many or as few as you like: nothing is preset, and your answers are saved in the browser.
4. **Download answers** and put the file in the spot check's folder.

Then `python scripts/spotcheck.py import <folder> <answers file>`, and `compare` shows:
- where you and the panel agree and differ
- the share of each side's claims you marked wrong: a measure of each set on its own, which a preference between two sets isn't. Like every rater's, your marks are weighed as evidence, not taken as ground truth.
- claim by claim, how often you and the judges agree, when the judges also mark claims (rubric v5 or v6)

`judge --rubric v6` asks the panel again with what the page shows you: the whole page with the part outlined, the whole page's text, and every claim, those in both sets listed once. Its verdicts go to `verdicts-v6/`, beside the first ones; `compare --rubric v6` compares against them.

Your verdicts are the anchor for the panel's: they say whether the round decisions track what a person would decide.

## Query checks (before judging)

Before a round spends money judging answers, it looks at the queries themselves. Obvious errors are cheaper to catch there: junk context, a wrong heading, cut-off text, a bad crop.

- **What each variant changed:** `queries-<variant>/index.html` in the round folder. It samples queries whose text or images differ from the baseline's, as diffs, spread over documents and kinds of region. Each shows the lines each lever added ("lever notes": the text before and after, the lead-in, the "Within:" path, the text layer, and so on) and the images sent.
- **Who looks:**
  - Claude, reading the page.
  - Two strong models from other families, Gemini 3.1 Pro and MiMo-V2.6-Pro. They check each query against a short list of problems, capped per round (`query_checks` in `round.json`).
  - Anyone else who wants to.
- **A flag on what a variant changed holds the round** before sampling and judging (exit 4): fix the lever, or accept with `run_round.py <round> --accept-checks`.
  - Problems that were there before the change are shown greyed. They don't hold the round, but they're leads for other levers.
- **Outside rounds,** for a lever being built:

```bash
pdf-semantic-diff queries dump benchmarks/runs/<round>/<variant> --out /tmp/stems --lever stem_context --sample 40
pdf-semantic-diff queries dump benchmarks/runs/<round>/<variant> --against benchmarks/runs/<round>/baseline --out /tmp/diff
pdf-semantic-diff queries check /tmp/diff --model google/gemini-3.1-pro --max-cost 0.5
```

## Panels of people (and sensitive documents)

The same method works with no model and nobody as referee:

1. **Share the batch folder**, not a URL. Each person opens `review.html` offline, types their name, and sends back their labels file. Progress is saved per name, so several people can share one computer.
2. **Import every file** with `review import`.
3. **Run `review consensus`.** It estimates each reviewer's reliability and each item's most likely verdict from all the labels together, using the Dawid–Skene model (EM over each reviewer's confusion matrix). Nobody's labels count as the answer key.
4. **Discuss the contested items** (those whose consensus is below 0.8 probability). Disagreement there usually means the item or rubric is ambiguous; clarity flags help tell the two apart.
5. **Run `review agreement`** to report Krippendorff's α per item type and per flag: at least 0.80 is reliable, 0.667–0.80 tentative.

For sensitive documents, everything stays local. Use `review judge` only with models you're allowed to send the documents to (e.g. an in-house deployment). A good first session for a new panel is a small practice batch, followed by a short discussion of the contested items before the real batches.

## Commands

```bash
# Replay recorded answers into stores to sample from (offline; no model calls)
pdf-semantic-diff samples/slices/A.pdf samples/slices/B.pdf --out benchmarks/runs/<responder>/<run> \
    --fixture tests/fixtures/replay-slices.zip --responder <responder> --config <recording settings>

# Sample a batch (claims round-robin over kinds; abouts; pairs round-robin over relations)
pdf-semantic-diff review sample benchmarks/batches/s02 --store <label>=benchmarks/runs/... --claims 4 --abouts 1 --pairs 1
    # items show exactly what each model was asked, from the stores' query logs
pdf-semantic-diff review judge benchmarks/batches/s02 --model <m> --stage questions   # the panel judges questions blind
pdf-semantic-diff review question-agreement benchmarks/batches/s02

# Labels from people, a panel of models, and the results
pdf-semantic-diff review import benchmarks/batches/s02 labels.json
pdf-semantic-diff review judge benchmarks/batches/s02 --model google/gemini-3.1-pro --limit 2   # check cost first
pdf-semantic-diff review consensus benchmarks/batches/s02 [--gate]   # reliability and consensus, no referee
pdf-semantic-diff review agreement benchmarks/batches/s02
pdf-semantic-diff review scores benchmarks/batches/s02
```

## Why the taxonomy looks like this

The categories (in `src/semantic_pdf_diff/taxonomy.py`) consolidate error analyses from related work, collected on 2026-09-25:

- **Grounding and entity binding dominate.** Table QA errors are mostly wrong or missing evidence (TAT-QA: 55% wrong evidence, 29% missing; [arXiv 2105.07624](https://arxiv.org/pdf/2105.07624)); in SciTab half the reasoning errors are grounding errors ([arXiv 2305.13186](https://arxiv.org/pdf/2305.13186)). Entity errors are the most frequent factual errors in summaries (FRANK; [NAACL 2021](https://aclanthology.org/2021.naacl-main.383/)). Hence the first flag group: *entity_misbound*, *scope_level_error* (component vs system), *attribute_misassigned*.
- **Distractor numbers hurt.** An irrelevant clause can sharply reduce word-problem accuracy ([GSM-IC](https://arxiv.org/abs/2302.00093), [GSM-Symbolic](https://arxiv.org/abs/2410.05229)); dense engineering tables are full of neighbouring numbers.
- **Hedges and qualifiers matter.** A third of SciTab's refuted claims turn on approximation words; conditions and circumstances are a distinct error class in FRANK. Hence *approximation_misflagged*, *condition_dropped*, *basis_wrong*, *polarity_or_negation_error*.
- **Units and scale.** TAT-QA reports scale errors (thousands, percentages) separately; hence *scale_factor_missed* next to *unit_wrong_or_missing*.
- **Charts and diagrams** fail mostly in perception (axes, legends, overlapping series) and in relations (invented or reversed edges between nearby elements); see [CHOC](https://arxiv.org/html/2312.10160) and [ChartAgent](https://arxiv.org/pdf/2510.04514).

Annotation design follows the same sources:

- **Verdict, then flags.** Agreement on "factual or not" was much higher than on the error category (FRANK: κ 0.58 vs 0.39), and binary checklists agree better than Likert scales ([CheckEval](https://aclanthology.org/2025.emnlp-main.796/)). So agreement is reported on the verdict, on a usable-or-not gate, and per flag.
- **Clarity and confidence are recorded** because disagreement often reflects genuinely ambiguous items, not careless reviewers ([Pavlick & Kwiatkowski 2019](https://aclanthology.org/Q19-1043/)).
- **Agreement:** Krippendorff's α (several reviewers, missing labels, nominal categories): 0.80 and above is reliable, 0.667–0.80 tentative.
- **Model panel:** several models from different families beat one large judge at lower cost ([PoLL](https://arxiv.org/abs/2404.18796)). Judges give their reasoning before the verdict. Models favour their own outputs ([Panickssery 2024](https://arxiv.org/abs/2404.13076)), so the model under test doesn't judge its own work. LLM judges also show position and verbosity biases ([Zheng 2023](https://arxiv.org/pdf/2306.05685)).

Planned: relation categories for [evidence webs](../docs/plans/README.md) (component of, input to, output of, source of, contradicts…) will get their own item type when that work starts.
