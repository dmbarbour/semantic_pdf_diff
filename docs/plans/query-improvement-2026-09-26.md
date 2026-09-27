# Query improvement in rounds

- **Status:** Active (2026-09-26).
- **Depends on:** [test-models-and-record-replay](test-models-and-record-replay-2026-09-24.md) (fixtures, recording by responder); [evaluation-benchmarks](evaluation-benchmarks-2026-09-23.md) (review pages, panel, consensus).
- **Feeds:** every prompt and context change in [scheduling-and-triage](scheduling-and-triage-2026-09-23.md) (e.g. epistemic status) and later plans.

## Goal

Improve the queries we send the model (context, chunking, crops, instructions) in repeated rounds. Each round tries a few changes, measures them on the same inputs as the current best, and keeps a change only if it helps overall without a real loss in any kind of input. The history is graphed, so progress (and cost) is visible.

What we've learned so far shapes this:
- **Most bad claims trace to thin input, not the model.** In s02, the panel judged 9 of 12 claim questions only partly answerable, most often for lack of surrounding text or something on another page.
- **Batches of different claims can't show a difference.** s01 and s02 each had 12 claims; the change between them was noise.
- **A panel of hosted models is cheap and roughly reliable,** but each member has biases (leniency, verbosity, answering instead of judging), and none is ground truth. People have to anchor it, sparingly.

## The loop

0. **Research and hypotheses.** Each round opens with a short research pass on its top failure mode, run by Claude with subagents at no provider cost. Examples:
   - cropping images that contain text
   - classifying page regions without a model (layout analysis, XY-cuts, whitespace, PyMuPDF's layout tools)
   - table structure, and associating captions with figures

   The findings go in `docs/research/`, and each round's review (`docs/reviews/round-NN-<date>.md`) states hypotheses ("adding the neighbouring paragraph will cut 'surrounding text missing' by half on text tasks") that the round then tests. This keeps changes grounded in evidence rather than guesses.
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

   Claims identical in both outputs (same claim ID) keep their labels and aren't re-judged. Claude labels a small anchor subset each round, answering blind where the stage calls for it. The owner spot-checks when results stabilise or before a top-up, not every round (see *Decisions*).
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

## Restarting when the budget runs out

The provider balance will run out mid-round; a round must pause cleanly and resume later without repeating paid work.

- **Every step is a checkpoint.** A round is a sequence of steps: research, variants, record, sample, judge questions, judge pairs, decide, report. Each step's state is in `benchmarks/rounds/rNN/state.json`: done, in progress with its position, or paused and why.
- **Nothing paid for is repeated.**
  - Recording goes into the fixture (`replay-or-record`), so a resumed recording replays what's recorded and asks only the rest.
  - Panel answers are cached by request in the batch folder, so a resumed judging step pays only for what's missing.
- **Out-of-balance errors stop the round.** An HTTP 402 or a provider billing error isn't retried; the step is marked "paused: budget" and the runner exits. `review rounds resume` continues from the checkpoint after a top-up.
- **A spending ledger.** Every model response's reported cost (DeepInfra returns `estimated_cost`) goes into `benchmarks/ledger.jsonl`, with round, step, model and tokens. The runner stops before a step whose estimate would pass the round's cap (default $15), or the known balance, which is set by hand after a top-up.

## Figures at every step

Every step appends its figures to `benchmarks/history.jsonl`, one record per measurement:
- round, step, variant, stratum
- metric, value, interval, sample size
- the cost of producing it, and a timestamp

That includes the mechanical metrics after recording, adequacy after question judging, win rates and absolute rates after answer judging, the decision, and the ledger totals. The report page draws every graph from this file, so a partial or paused round still shows what it measured.

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

## Future lever: repeated readings and agreement

Round 1 showed that asking the same question again often gets a different answer: a misread dimension here, a dropped minus sign there. That is a quality problem in itself, and a lever to try once the single-query levers settle.

- **Ask several times; keep what agrees.** Ask the same question k times (e.g. k = 3) and keep claims that most readings agree on, flagging the rest as uncertain. This is self-consistency voting, and the "mixed mode" idea in [scheduling-and-triage](scheduling-and-triage-2026-09-23.md): spend it only where doubt is high (low confidence, a failed quote check, a quality flag), not everywhere.
- **Vary the query, not only the sample.** Ask the final top variants (different context or crop choices) and combine their answers. Agreement across differently framed questions is stronger evidence than agreement across repeats of one question, and it may cancel each framing's blind spots.
- **Measure it like any other lever:** pairwise against a single reading, with its extra cost as a guard.

**Record/replay stays deterministic: one recorded response per request.**
- Each repeat is a separate request. Its key carries a reading index (reading 1, 2, 3…), so each has its own recorded answer, and a replay serves exactly those.
- Nothing relies on temperature 0 for repeatability. Caching, batching, GPU partitioning and floating-point order make hosted inference non-deterministic regardless.

## Decisions (2026-09-26)

- **Budget:** $10–15 per round, capped. About $50 is left after $9.99 spent so far; the owner tops up by hand and decides whether to continue based on the improvements shown.
- **Restarts:** rounds must pause cleanly when the balance runs out and resume without repeating paid work (see *Restarting*).
- **Owner's time:** no spot checks every round (reviewing low-quality questions is draining). The owner reviews when results stabilise, or before a top-up, and may bring ideas then. Claude fills the anchor role in between.
- **Research every round,** including heuristics that don't need a model (cropping text-bearing images, classifying page regions, table structure), and a proper per-round review with hypotheses, so changes aren't made blind.
- **Figures at every step** go into the history file, so every stage can be graphed.
- **Acceptance is automatic** when the rules pass, with a round summary for the owner. Assumed from "halt or continue based on improvements"; to be confirmed.

## Progress

| Round | What | Result | Cost |
|---|---|---|---|
| r01 | Four levers, one per variant | Confounded: every variant re-asked every request, so run-to-run variation dominated; paused | $10.03 |
| r01b | The same, re-asking only changed requests | Text layer 0.72, table lead-in 0.71, neighbouring text 0.68 accepted; table filter inconclusive (12 pages) | $3.40 |
| r02 / r02h | The three together, development / held-out | 0.68 (0.54–0.81) / 0.71 (0.56–0.86): accepted | $2.04 |

**Champion (2026-09-26):** `benchmarks/champion.json` (neighbouring text 400 + 400 characters, table lead-in 400, text layer 1,500 with images). Later rounds compare against it.

**Levers built, not yet judged:**

| Lever | Hypothesis | Measured without the model |
|---|---|---|
| `stem_context` | 2: numbered items and headings as parents | (round 3) |
| `tiling: bands` | 3: full-width bands cut at whitespace | NREL: 12 bands cutting 5 lines, against 72 tiles cutting 1,027 |
| `grow_tiles` | extra: tiles grown to whole lines | Drawing sheets: lines cut 137→35, 139→50 |
| `sheet_details` | 5: a drawing sheet's details, titled from the sheet | 16–25 images per sheet instead of 35; 0–10 lines cut instead of 23–79 |
| `references` | 8: abbreviations defined elsewhere, cited captions | 3–15 of 8–17 chunks per report slice gain a line |

**The tool's defaults** stay at the v6 queries for now, so the recorded fixture keeps replaying. The champion becomes the default at a milestone, after a few rounds, with one full re-recording (about $1).

## Open questions

1. **Model fixed per cycle?** Proposed: keep the responder (gemma-4-31B) fixed while improving queries, and compare models separately, so effects don't mix.
