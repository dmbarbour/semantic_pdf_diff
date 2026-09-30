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
   - **Per-output checks:** the per-field right/wrong/unsure on each output's claims, weighed across raters (no rater is ground truth).
   - **The question itself, blind,** when the variant changed the input.

   Claims identical in both outputs (same claim ID) keep their labels and aren't re-judged. Claude labels a small anchor subset each round, answering blind where the stage calls for it. The owner spot-checks when results stabilise or before a top-up, not every round (see *Decisions*).
5. **Decide** by the acceptance rules below. An accepted variant becomes the new baseline.
6. **Graph and log** the round.

## Measuring on the same inputs (paired)

The unit of evaluation is an **input** (an extraction task, a situating request, a comparison), not a claim. Both variants answer the same inputs, so differences come from the variant, not from sampling. This is far more sensitive than comparing batches of different claims. Pairwise preferences are also judged more consistently than scores given to one output at a time (the research on LLM judges and human raters agrees on this).

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
| Answers, pairwise | Variant's win rate against the baseline, overall and per stratum, with confidence intervals clustered by page region | About $0.03–0.06 per input |
| Answers, per set | Usable-claim rate (Dawid–Skene consensus, weighting raters by estimated reliability); per-field correctness; hallucination rate (value not in source) | Included in the pairwise judging |
| Recall | Claims a careful reader would extract but the model didn't: blind answers from the question stage (people and panel), matched mechanically, with leftovers adjudicated | People's time; a few inputs per round |
| Human anchor | Panel-vs-person agreement on a spot-check subset; panel weights re-estimated if they drift | About 15 items per round |

## Acceptance rules (no severe regressions)

A variant is accepted when all of these hold:
1. **Overall:** its pairwise win rate's 90% interval lies above 50%, or it's non-inferior (the interval's lower bound is at least 45%) with a mechanical gain such as lower cost.
2. **No stratum loses clearly:** no stratum's win-rate interval lies entirely below 45%. A stratum that loses blocks the variant, or makes it conditional (e.g. applied only to tables).
3. **Guards:** failures and partials don't rise; cost per page rises no more than an agreed cap (e.g. 20%) without a matching quality gain.
4. **Regression set:** no confirmed-good claim is lost without a better one replacing it.

**Decided once, at a fixed sample** (from round 9, 2026-09-28):
- **Every variant is judged to its full sample (32 units) and decided once.** Rounds 1–8 stopped as soon as an interval cleared, looking at 16, 24 and 32 units; simulations on their data put the chance of accepting a lever with no effect at 12–18%, against 6–9% for a single look (see the [overall review](../reviews/overall-review-2026-09-28.md)). Extending an inconclusive round is another look, so it's noted in the review.
- **A stratum needs at least 6 units to block a variant.** Two lost units could otherwise reject it.
- **Win rates are over changed units only.** Decisions report their coverage (the share of units a lever changed) alongside.
- **Units larger than 25 claims are cut into up to 4 bands of the page,** each judged as its own crop.

Rejected variants are kept in the log with their results, so ideas aren't retried blindly.

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

That includes the mechanical metrics after recording, adequacy after question judging, win rates and per-set rates after answer judging, the decision, and the ledger totals. The report page draws every graph from this file, so a partial or paused round still shows what it measured.

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
5. **Statistics:** intervals (clustered by page region since 2026-09-28), stratified win rates, sequential stopping, and the acceptance rules as code.
6. **A round runner:** estimate cost, record variants, sample, judge, decide, log (`benchmarks/rounds/<n>/` with variant definitions, inputs, labels and results; `benchmarks/history.json`).
7. **The report page** with the graphs above.
8. **More slices,** cut at section boundaries, split into development and held-out sets.

## Milestones

1. Query sets and context levers as settings; the missing-heading slicing fix; more slices, split into sets. One re-recording of the baseline.
2. Pairwise items, input-level sampling, statistics and acceptance rules.
3. Round 0: the baseline's per-set metrics on both sets; panel calibration against about 30 of the owner's labels; judges chosen by reliability per dollar.
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

## Decisions (2026-09-28)

- **Extraction first** (the owner): comparisons are deferred until extraction quality is reasonably good, or until it can't easily be improved further.
- **Judges** (the owner):
  - **Normal rounds** use the cheap judge, MiMo-V2.6-Pro, on every unit. Qwen3.5-397B gives second opinions only where MiMo leaves a unit unsettled: a failed verdict, a flip with the order.
  - **The most promising candidates** get a separate confirmation by the expensive judges (Qwen, Gemini): `confirm_judges` in `round.json`, off by default.
- **Round method** (the owner approved the overall review's changes):
  - fixed samples (above)
  - each judge's two orders averaged before judges are combined
  - failed verdicts asked once more at the end, instead of on every chunk
  - rubric v4: judges are told when a set is a sample, and see the text before the unit and the numbered items it sits under
  - an A/A control variant (`"fresh"` regions re-asked) for levers that re-ask everything

**Spend accounting (2026-09-28):**
- **The gap:** the provider's dashboard showed $54.60 spent where the ledger (plus an estimate of early panel work) gave $51.40.
- **Most likely cause:** answers cut off by our timeouts are still billed but were never recorded. Failed judge verdicts were also re-sent on every chunk, and the ledger kept only a request's last attempt.
- **Fixed:** every attempt is now recorded, failed verdicts are asked once more at the end, and answers are streamed, so the timeout applies between chunks and slow answers complete.
- **For estimates:** treat the dashboard as authoritative, and allow for this known undercount in rounds 1–9.

**Statistics and review fixes (the owner, 2026-09-28: "improve known flaws in our statistics and review to find more of them"; details in the [statistics audit](../reviews/statistics-audit-2026-09-28.md)):**
- **Intervals are clustered by page region:** bands cut from one region share a crop, a reading and often a judge's mood, so they aren't independent.
  - **The method:** a cluster-robust t interval replaces the percentile bootstrap. It's deterministic and corrected for small samples.
  - **Past rounds:** no decision in rounds 1–9 changes.
  - **Borderline calls:** decisions list any bound within 0.03 of its threshold. Four wins are borderline: r01 neighbours, r02, r03 stems and r09h, at 0.501–0.512.
- **Units show each reading in its own words:** a merged claim used to appear in its representative's words (often a text reading's), so text levers changed visual units. r09b's changed visual units drop from 9 to 2.
- **Document families are strata** (reports, drawings, manuals, rules, set in `scripts/slices.json`), as this plan always said. A non-blocking **watch** list names strata with a mean below 0.45 on 10 or more units.
- **Escalation judges' failed verdicts are retried once,** and failures are counted over the whole round.
- **Stems from table values (a bug, found in the spot check):** a value such as "3.83" at the start of a table line was taken for a numbered item, so the extractor's "Within:" line and the judges' "It sits under:" named table cells ("3.83 -43.73E+6").
  - **Fixed:** a section number needs a capitalised title, can't start at 0, and must be set as a heading or follow the section numbers before it (3.2.1 → 3.2.2, 3.3, 4.1).
  - **What it touched:** lines whose path lost a table value or regained its real heading: HabEx 719, NREL 613, IEA-15 381, calG sheets 39–42 192, Ken manual 158, IEA-22 52. The rules, LCIT, DC manual and the other drawing slices changed by 2 lines at most.
  - **Stems were accepted in r03 (0.63) as implemented then,** junk included; the fixed version hasn't been measured on its own.
- **Rubric v6:** judges see what a person sees on the spot-check page:
  - the whole page, with the part outlined (a second image, for bands)
  - the whole page's text layer, as well as the part's
  - every claim, with those in both sets listed once (S1, ...) and then each set's own (A1, ..., B1, ...), so "missing" can be judged against everything a set has
  - Shared claims' marks count for both sides. Rounds using v6 run `add_context` on each batch.
- **Unpriced responses:** a streamed answer cut off before its last chunk comes without usage, yet may be billed. The ledger used to drop it; it now records it as "unpriced", and rounds report how many.

**On the audit's proposals (the owner, 2026-09-28):**
- **Promotion (A, approved):**
  - A lever reaches the defaults only after a combination round and a held-out check. The held-out criterion is written into `round.json` before judging (e.g. mean above 0.5 and no stratum loss), and the held-out effect is the one quoted, since development figures of accepted levers are inflated by selection.
  - "No worse" needs a gain named in advance, with its metric and threshold.
  - **Built (2026-09-30):** `criteria` in `round.json` (`models.Criteria`: role, thresholds, named gain, held-out rule), fixed when judging starts. Simulated rates are in the [content-addressed queries plan](content-addressed-queries-2026-09-28.md). The default held-out rule is open.
  - **No lever is forgotten:** the [lever index](../reviews/levers.md) is the catalogue.
    - Every idea gets a row when it's raised, built or not.
    - Levers not accepted or parked are tried again against later champions, since a baseline that moved can change the answer.
    - Other ways of doing one idea are tried as its variants; there may be subtleties a first version misses (quotes: exact, excerpts, fragments; stems: as in r03, as fixed).
  - **Later:** a search closer to genetic programming, combining and mutating levers to get out of the local optima that one lever at a time finds (plans index: *Lever search*).
- **Levers that act on part of a page (B), open:**
  - **The problem:** a rule added to every image prompt (the chart rule) re-asks every image, so the few units it acts on are judged among many that changed only by chance.
  - **Proposed:** a lever adds to a request only where it applies (tiles with charts, say); the rest replay unchanged.
  - **The owner:** agrees that requests should be cached by what reaches the model. If this means updating only a sample of queries, the means must be robust and easy to review.
  - **A separate question the owner raised:** whether to skip re-asking changed requests that no judged unit will use. It depends on how time and money split between extraction and judging: extraction was $3.94 of the ledger's $40.31, judging $35.56.
- **Spot checks (C):** mix close calls and clear ones, drawn from a decided round's batch and stratified by closeness (close, flipped with the order, clear), for more robust quality estimates.
- **Measurements owed (D):** agreed, after the owner's surveys.

**Judging rubric v2 (the owner, 2026-09-27; from round 7):**
- **What changes:** document administration (contacts, addresses, lot or project numbers, revision dates, copyright, logos) is neutral in pairwise judging. Neither side is preferred for including or omitting it; such claims are checked only for correctness.
- **Why:** in round 5, crops that happened to isolate a title block swung results.
- **Where it really belongs:** provenance gets its own layer (plans index: *Subject, parties and provenance*).
- **Setup:** rounds choose a rubric in `round.json` (`"rubric": "v2"`). v1 is the default and leaves earlier prompts unchanged, so their cached verdicts still replay.

## Progress

| Round | What | Result | Cost |
|---|---|---|---|
| r01 | Four levers, one per variant | Confounded: every variant re-asked every request, so run-to-run variation dominated; paused | $10.03 |
| r01b | The same, re-asking only changed requests | Text layer 0.72, table lead-in 0.71, neighbouring text 0.68 accepted; table filter inconclusive (12 pages) | $3.40 |
| r02 / r02h | The three together, development / held-out | 0.68 (0.54–0.81) / 0.71 (0.56–0.86): accepted | $2.04 |
| r03 | Stems, bands, grown tiles, each against the champion | Stems 0.63 (0.51–0.75), bands 0.83 (0.70–0.94), grown tiles 0.80 (0.70–0.89): accepted | $2.51 |
| r04 / r04h | The three together, development / held-out | 0.64 (0.54–0.73) at 40 units / 0.69 (0.57–0.82): accepted | $2.91 |
| r05 | Sheet details, references | Details 0.64 (0.41–0.86) on 8 units, with a resolution flaw since fixed; references 0.50 (0.35–0.66): neither accepted | $1.04 |
| r05b–d | Details with two more sheet slices, and two fixes | 0.50, 0.48, 0.42: parked (isolated title blocks read as out of scope) | $3.46 |
| r06 | Merged readings, tile locator | 0.58 and 0.49: judges saw separately drawn samples (fixed) | $3.38 |
| r07 | The same, re-judged (rubric v2) | 0.54 (representative embellished; reverted) and 0.58 (locator parked) | $3.38 |
| r08 | Merged readings (local representative), chart-reading rule (rubric v3) | 0.56 (accepted with its claim reduction) and 0.59 (not accepted) | $3.55 |
| r09 / r09b | The new method: excerpt quotes, an A/A control; fragment quotes | 0.51 (not accepted), 0.48 (the noise floor, as expected); fragments 0.66 (accepted) | $2.63 |

**Champion (2026-09-27):** `benchmarks/champion.json` (neighbouring text 400 + 400 characters, table lead-in 400, text layer 1,500 with images, numbered-item stems, whitespace bands on report pages, tiles grown to whole lines; since 2026-09-27 also empty tiles skipped and readings of one fact merged; since 2026-09-28 fragment quotes accepted). Later rounds compare against it.

**Levers built, not yet judged:**

| Lever | Hypothesis | Measured without the model |
|---|---|---|
| `sheet_details` | 5: a drawing sheet's details, titled from the sheet | 28–38 images per sheet against 35; 1–23 lines cut instead of 23–79; parked after r05d |
| `references` | 8: abbreviations defined elsewhere, cited captions | 3–15 of 8–17 chunks per report slice gain a line; r05 neutral, not accepted |

**The tool's defaults are the champion** (promoted 2026-09-28, the owner: "promote clear champions to defaults"):
- **Promoted:** neighbouring text, table lead-in, the text layer with images, stems, whitespace bands, grown tiles, skipped empty tiles, merged readings and fragment quotes, with 20 claims and 4,000 output tokens per request (what every recording used).
- **Round 0's settings** are in `benchmarks/round0.json`.
- **Endpoint settings stay out:** context size and image-token cost describe the endpoint, not the queries, so they remain in `.env`.
- **Re-recording:** the replay test's fixture was re-recorded under the new defaults.

## Open questions

1. **Model fixed per cycle?** Proposed: keep the responder (gemma-4-31B) fixed while improving queries, and compare models separately, so effects don't mix.
