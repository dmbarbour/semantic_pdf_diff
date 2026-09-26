# Query improvement in rounds

- **Status:** Planned (2026-09-26). Draft for discussion.
- **Depends on:** [test-models-and-record-replay](test-models-and-record-replay-2026-09-24.md) (fixtures, recording by responder); [evaluation-benchmarks](evaluation-benchmarks-2026-09-23.md) (review pages, panel, consensus).
- **Feeds:** every prompt and context change in [scheduling-and-triage](scheduling-and-triage-2026-09-23.md) (e.g. epistemic status) and later plans.

## Goal

Improve the queries we send the model (context, chunking, crops, instructions) in repeated rounds. Each round tries a few changes, measures them on the same inputs as the current best, and keeps a change only if it helps overall without a real loss in any kind of input. The history is graphed, so progress (and cost) is visible.

What we've learned so far shapes this:
- **Most bad claims trace to thin input, not the model.** In s02, the panel judged 9 of 12 claim questions only partly answerable, most often for lack of surrounding text or something on another page.
- **Batches of different claims can't show a difference.** s01 and s02 each had 12 claims; the change between them was noise.
- **A panel of hosted models is cheap and roughly reliable,** but each member has biases (leniency, verbosity, answering instead of judging), and none is ground truth. People have to anchor it, sparingly.

## The loop

1. **Diagnose.** Aggregate the latest panel and human labels:
   - what questions were missing ("surrounding text", "legend", "heading"...)
   - which answer fields fail (entity, conditions, quote...)
   - which flags recur
   - the notes, clustered by a model into a short list of failure modes with example items
2. **Propose variants.** One lever per variant, so a result can be attributed, for example:
   - add the neighbouring paragraph as labelled context
   - send the table header with every row
   - add the caption and legend to figure tasks
   - quote-verbatim rules
   - smaller tiles on drawing sheets

   Claude and the owner design the first rounds. Later, a model can propose variants from the failure clusters (automatic prompt optimisation), but the owner approves what runs.
3. **Record.** Run each variant on the evaluation inputs through the live pipeline with the fixture attached (a new interpreter fingerprint, the same responder). Unchanged requests replay for free.
4. **Judge.** The panel judges, per sampled input:
   - **Pairwise:** the baseline's answer against the variant's, in both orders (to cancel position bias): which is better, or equal, and why.
   - **Absolute checks:** the per-field right/wrong/unsure on each output's claims.
   - **The question itself, blind,** when the variant changed the input.

   A person spot-checks a small subset. Claims identical in both outputs (same claim ID) keep their labels and aren't re-judged.
5. **Decide** by the acceptance rules below. An accepted variant becomes the new baseline.
6. **Graph and log** the round.

## Measuring on the same inputs (paired)

The unit of evaluation is an **input** (an extraction task, a situating request, a comparison), not a claim. Both variants answer the same inputs, so differences come from the variant, not from sampling. This is far more sensitive than comparing batches of different claims. Pairwise preferences are also judged more consistently than absolute scores (the research on LLM judges and human raters agrees on this).

Inputs are sampled **stratified**:
- by request kind (text, table row, tile, figure, overview, figure about, section about, comparison)
- by document family (reports, drawing sets, rules)

Every stratum gets enough items to show a regression.

## Evaluation sets

- **Development set:** the inputs rounds are judged on. It grows past today's five slices to about 10–15 slices across more families: LCIT and HabEx reports, team project manuals, IEA 22 MW, more drawing sheets, the 2013 rules. Cut at section boundaries (fixing the missing-heading artefact).
- **Held-out set:** other documents, never looked at while designing variants, judged only at milestones (every 3–4 rounds). It catches changes that only fit the development set.
- **Regression set:** inputs whose answers earlier rounds confirmed with high consensus. They're cheap to recheck, because identical claims keep their labels.

The split is by document, not by page, so nothing leaks between sets.

## Metrics, cheapest first

| Layer | Metrics | Cost |
|---|---|---|
| Mechanical (every run, free) | Failed or unparseable answers; partial rate; refinement depth; claims per task; quote found in the page's text layer; section attribution rate; values in "abouts"; tokens and latency per page | None |
| Questions (when inputs change) | Share of inputs judged enough / partly / not enough; what's missing | About $0.03 per input across 4–6 judges |
| Answers, pairwise | Variant's win rate against the baseline, overall and per stratum, with bootstrap confidence intervals | About $0.03–0.06 per input |
| Answers, absolute | Usable-claim rate (Dawid–Skene consensus); per-field correctness; hallucination rate (value not in source) | Included in the pairwise judging |
| Recall | Claims a careful reader would extract but the model didn't: blind answers from the question stage (people and panel), matched mechanically, with leftovers adjudicated | People's time; a few inputs per round |
| Human anchor | Panel-vs-person agreement on a spot-check subset; panel weights re-estimated if they drift | About 15 items per round |

## Acceptance rules (no severe regressions)

A variant is accepted when all of these hold:
1. **Overall:** its pairwise win rate's 90% interval lies above 50%, or it's non-inferior (the interval's lower bound is at least 45%) with a mechanical gain such as lower cost.
2. **No stratum loses clearly:** no stratum's win-rate interval lies entirely below 45%. A stratum that loses blocks the variant, or makes it conditional (e.g. applied only to tables).
3. **Guards:** failures and partials don't rise; cost per page rises no more than an agreed cap (e.g. 20%) without a matching quality gain.
4. **Regression set:** no confirmed-good claim is lost without a better one replacing it.

Rounds stop early when the result is already clear (sequential testing), so clear winners and losers don't use the whole budget. Rejected variants are kept in the log with their results, so ideas aren't retried blindly.

## Graphs

A static, self-contained report page (works offline; can also be shared as an artifact for public-corpus results), regenerated after every round:

- **Progress:** usable-claim rate, per-field correctness, "input enough" share and recall per round, on the development set, with the held-out set's milestones marked. Intervals shown as bands.
- **Round decisions:** each variant's win rate against its baseline, with its interval and a 50% line; accepted in colour, rejected in grey.
- **Regression heatmap:** strata (rows) × rounds (columns), coloured by win rate or usable-claim rate. A red cell shows where a round hurt.
- **What's missing, over rounds:** a stacked bar of the panel's "missing" answers; the levers should shrink the bars they target.
- **Quality vs cost:** usable claims per dollar or per page against tokens per page, one point per accepted baseline.

## Budget

Measured so far: recording all five slices costs about $0.50; a panel pass on a 17-item batch costs about $0.70–1.50 (reasoning-heavy judges cost most).

**Per round** (60 inputs, 2–3 variants, 4 judges):

| Item | Cost |
|---|---|
| Recording | ≤ $1 |
| Question judging | ≈ $2 |
| Pairwise judging | ≈ $3–5 per variant |
| **Total** | **≈ $8–15** |

**Levers to spend less:**
- **Choose judges by reliability per dollar** from the consensus estimates. Gemini-3.1-pro, Qwen3.5 and MiMo are cheap and fairly reliable; Kimi is reliable but the costliest; DeepSeek was unreliable.
- **Judge only changed outputs.**
- **Stop early** when the result is clear.
- **Cheaper panels for mechanical-looking checks.**

Every round prints an estimate before spending (tokens × the provider's listed prices) and stops at a set cap.

## What has to be built

1. **Variants as data:** prompt templates and context options selectable by settings (a named "query set"), so two variants can run side by side without code edits. Today, prompts are constants in code.
2. **Context levers** behind settings: surrounding paragraph, caption and legend, table header per row, heading always shown (even "none"), tile size per page type.
3. **Input-level sampling** from fixtures, stratified, with development, held-out and regression sets defined in files.
4. **A pairwise item type** in the review pages and panel: one input, two outputs, randomised order, "which is better, and why", plus per-field checks on each.
5. **Statistics:** bootstrap intervals, stratified win rates, sequential stopping, and the acceptance rules as code.
6. **A round runner:** estimate cost, record variants, sample, judge, decide, log (`benchmarks/rounds/<n>/` with variant definitions, inputs, labels and results; `benchmarks/history.json`).
7. **The report page** with the graphs above.
8. **More slices,** cut at section boundaries, split into development and held-out sets.

## Milestones

1. Query sets and context levers as settings; the missing-heading slicing fix; more slices, split into sets. One re-recording of the baseline.
2. Pairwise items, input-level sampling, statistics and acceptance rules.
3. Round 0: the baseline's absolute metrics on both sets; panel calibration against about 30 of the owner's labels; judges chosen by reliability per dollar.
4. Rounds 1–3: one lever per variant, starting with what the panel said was missing most (surrounding text, then other-page context, then legends).
5. The report page and history.
6. Later: model-proposed variants from failure clusters, with the owner approving what runs.

## Open questions

1. **Budget:** about $10–15 per round, with a hard cap per round? What should the cap be?
2. **Approval:** should accepted variants become the baseline automatically when the rules pass, or wait for the owner's approval each round? I'd suggest automatic, with a summary to review.
3. **Human time per round:** is about 15 spot-check items reasonable, plus a few blind extractions for recall?
4. **Model fixed per cycle?** I'd keep the responder (gemma-4-31B) fixed while improving queries, and compare models separately; otherwise effects mix.
