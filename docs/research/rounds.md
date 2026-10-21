# Improvement rounds, 2026-09-26 to 2026-09-28: the record

- **Date:** 2026-10-03, when the rounds' working data left the repository.
- **The owner:** "I don't believe we need benchmark rounds, for example, though having a historical record of what was tested and the outcomes could be useful under `docs/research/rounds.md` or similar."
- **Where the data is:** every round's folder (`benchmarks/rounds/<round>/`), the spot check sc01 (`benchmarks/spotchecks/sc01/`), the evaluation batches s01 and s02 (`benchmarks/batches/`), the rounds' history (`benchmarks/history.jsonl`) and the spend ledgers are in git history up to commit `d0a5e43` (2026-10-03).
  - A shallow clone leaves them out.
  - The five round batches the tests replay stay, under `tests/fixtures/rounds/`.

## What a round was

The [query improvement plan](../plans/query-improvement-2026-09-26.md) tried levers on how documents are read, one per variant.

- **Method:**
  - Each variant was read against the same baseline on the development slices.
  - The units whose claims changed were judged pairwise by a panel of hosted models, in both orders.
  - A variant was accepted only without a loss in any stratum (text, table, visual).
- **Held-out rounds** (`h`) checked accepted levers on slices never used to design them.
- **The levers accepted became the defaults on 2026-09-28** (`benchmarks/champion.json`).
- **The details:** each lever's story in the [lever index](../reviews/levers.md); the method, its rubrics and each round's cost in the plan; the rules since in [decision 0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md).
  - Each round's review, and the audits of 2026-09-28, were retired on 2026-10-21 (the [plans index](../plans/README.md#retired) says how to read one from git). What they held that's kept nowhere else is below: *Corrections*, *What the method's numbers were* and *What the audits found*.

## Decisions

| Round | Set | Variant | Units judged | Win rate (90% interval) | By stratum | Decision |
|---|---|---|---|---|---|---|
| r01 | dev | lead-in | – | – | – | – |
| r01 | dev | neighbours | – | – | – | – |
| r01 | dev | table-filter | 48 | 0.43 (0.35–0.51) | page 0.43 | inconclusive: judge more units |
| r01 | dev | text-layer | – | – | – | – |
| r01b | dev | lead-in | 15 | 0.71 (0.56–0.85) | table 0.71 | accepted: wins |
| r01b | dev | neighbours | 24 | 0.68 (0.56–0.80) | text 0.68 | accepted: wins |
| r01b | dev | table-filter | 12 | 0.41 (0.23–0.57) | page 0.41 | inconclusive: judge more units |
| r01b | dev | text-layer | 16 | 0.72 (0.56–0.88) | visual 0.72 | accepted: wins |
| r02 | dev | combined | 24 | 0.68 (0.54–0.81) | table 0.75; text 0.72; visual 0.56 | accepted: wins |
| r02h | heldout | combined | 16 | 0.71 (0.56–0.86) | table 0.81; text 0.55; visual 0.75 | accepted: wins |
| r03 | dev | bands | 16 | 0.83 (0.70–0.94) | visual 0.83 | accepted: wins |
| r03 | dev | grow | 16 | 0.80 (0.70–0.89) | visual 0.80 | accepted: wins |
| r03 | dev | stem | 24 | 0.63 (0.51–0.75) | table 0.51; text 0.69 | accepted: wins |
| r04 | dev | combined | 40 | 0.64 (0.54–0.73) | table 0.42; text 0.67; visual 0.71 | accepted: wins |
| r04h | heldout | combined | 24 | 0.69 (0.57–0.82) | table 0.71; text 0.68; visual 0.69 | accepted: wins |
| r05 | dev | details | 8 | 0.64 (0.41–0.86) | visual 0.64 | inconclusive: judge more units |
| r05 | dev | references | 17 | 0.50 (0.35–0.66) | table 1.00; text 0.47 | inconclusive: judge more units |
| r05b | dev | details | 20 | 0.50 (0.38–0.64) | visual 0.50 | inconclusive: judge more units |
| r05c | dev | details | 20 | 0.47 (0.34–0.61) | visual 0.47 | inconclusive: judge more units |
| r05d | dev | details | 21 | 0.42 (0.28–0.56) | visual 0.42 | inconclusive: judge more units |
| r06 | dev | locator | 32 | 0.49 (0.37–0.61) | visual 0.49 | inconclusive: judge more units |
| r06 | dev | reconcile | 32 | 0.58 (0.47–0.69) | table 0.59; text 0.72; visual 0.42 | no worse: accept only with another gain (e.g. cost) |
| r07 | dev | locator | 32 | 0.58 (0.47–0.68) | visual 0.58 | no worse: accept only with another gain (e.g. cost) |
| r07 | dev | reconcile | 32 | 0.54 (0.43–0.65) | table 0.47; text 0.61; visual 0.54 | inconclusive: judge more units |
| r08 | dev | charts | 32 | 0.59 (0.47–0.71) | visual 0.59 | no worse: accept only with another gain (e.g. cost) |
| r08 | dev | reconcile | 32 | 0.56 (0.45–0.67) | table 0.50; text 0.65; visual 0.54 | no worse: accept only with another gain (e.g. cost) |
| r09 | dev | aa | 32 | 0.48 (0.37–0.61) | table 0.67; text 0.40; visual 0.48 | inconclusive |
| r09 | dev | excerpts | 31 | 0.51 (0.39–0.63) | table 0.25; text 0.62; visual 0.44 | inconclusive (re-decided 2026-10-02; see *Corrections*) |
| r09b | dev | fragments | 32 | 0.66 (0.53–0.77) | table 0.00; text 0.77; visual 0.44 | accepted: wins (re-decided 2026-10-02; see *Corrections*) |
| r09h | heldout | fragments | 21 | 0.66 (0.50–0.81) | text 0.89; visual 0.40 | no worse: accept only with another gain (e.g. cost) (re-decided 2026-10-02; see *Corrections*) |

- **Win rate:** the variant's share of pairwise preferences against the baseline, with a 90% interval (bootstrap until 2026-09-28, then cluster-robust by page region).
- **Rounds r02 and r04** combined the levers accepted before them. Their records are in the plan's progress.
- **The defaults since 2026-09-28** (the champion):
  - neighbouring text, the text layer with images, table lead-ins, numbered-item stems, whitespace bands and grown tiles (rounds 1–4)
  - merged readings (r06–r08, no worse with fewer claims; the owner's design decision)
  - fragment quotes (r09b, held out in r09h)
  - skip empty tiles (cost only)

## Corrections

**Four units judged on the wrong crop (found 2026-10-02):**
- **What happened:** a text unit and a visual unit cut into bands of the same number, on one page, got one image name. The first unit's crop was kept for both, so the second was judged on a crop of another band: 1 unit in r09 (excerpts), 2 in r09b (fragments), 1 in r09h (fragments, held out).
- **Found** while making the rounds' images again from the slices (the [architecture clean-up](../plans/architecture-cleanup-2026-10-02.md), milestone 9). New batches name a band's crop by its kind.
- **Re-decided without them,** as the owner asked ("Go ahead"), offline from the recorded verdicts:

  | Batch | Recorded | Today's rules, all units | Today's rules, without them |
  |---|---|---|---|
  | r09 excerpts | inconclusive, 0.51 (0.39–0.63) | inconclusive, 0.49 (0.37–0.62) | inconclusive, 0.49 (0.36–0.62) |
  | r09b fragments | accepted: wins, 0.66 (0.53–0.77) | accepted: wins, 0.66 (0.53–0.78) | accepted: wins, 0.67 (0.54–0.79) |
  | r09h fragments (held out) | no worse, 0.66 (0.50–0.81) | accepted: wins, 0.66 (0.50–0.81) | no worse, 0.64 (0.48–0.79) |

- **No conclusion changes.** Under the held-out rule (since 2026-09-30), r09h holds out with or without the unit, so fragments stays a default. Its development-rule verdict flips between "wins" and "no worse" on one unit because its lower bound sits at 0.5: the borderline the round reported, not a new result.

## What the method's numbers were

From the overall review's meta-analysis of every round's files (2026-09-28, rounds r01–r08: 26 judged batches, 505 units plus r01's):

| Measure | Value |
|---|---|
| Per-unit score SD | 0.38 (36% of units score 1.0, 18% score 0.0) |
| 90% half-width at 16 / 32 / 48 / 96 units | ±0.16 / ±0.11 / ±0.09 / ±0.06 |
| First chunk (8 units) against the final result | +0.08 on average, up to +0.24 |
| Qwen against MiMo, same unit | sign agreement 68%, opposite 6%; κ 0.49; r 0.69 |
| Order flips (position consistency) | Qwen 19%, MiMo 14%; the first-shown set wins 54–57% of decisive verdicts (cancelled by judging both orders) |
| Judge retest with fixed claims (locator, r06 against r07) | r 0.83, sign agreement 18 of 20 |
| Missing verdicts | Qwen 0.5%, MiMo 9.2% (timeouts on long units) |
| Cost per verdict | Qwen $0.019, MiMo $0.0045 |
| Units over 25 claims | 51% overall, 74% of visual; they score lower (0.54 against 0.59) even after the sampling fix |

- **The judges agree with each other and with themselves.** Most of the noise is re-extraction: every re-asked request is a fresh sample. An A/A control (r09: the champion's image tasks asked afresh) scored 0.48 ± 0.12 at 32 units, so a lever needs a true rate of about 0.62 to be accepted reliably there.
- **Win rates are conditional on changed units:** a lever changing 8 of 176 units and one changing 91 aren't comparable without their coverage.
- **Pairwise preference can't see failures both sides share,** and those dominated: in r07–r08, 70% of verdicts tagged both sides with duplicates. The 375 remarks most often named a fact both sides missed (159), duplicates (147), and text-layer or OCR trouble (131).

## What the audits found

The overall review, the statistics audit and the meta-audit (all 2026-09-28) found the method's flaws; their fixes and rules are in [decision 0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md), [0009](../decisions/0009-content-addressed-queries.md) and [0011](../decisions/0011-settings-classified-by-effect.md), and what was left open in the plans index's *Resumed query rounds*.

- **No test found any of the 21 flaws** traced from the rounds; all were found by looking: agent reviews and audits 8, round analysis 6, while building 3, the owner 2, a research note 1, a review batch 1. Each lived hours to about 2 days, and the method's overhaul of 2026-09-28 brought three new ones.
- **Their root causes:** an invariant nobody stated (5; "a variant differs only where its lever acts"), decision rules never simulated under the null (3), a concept with no single owner (3: display order on rotated pages, request identity), the judged unit not the unit of dependence (3), reviewers lacking context (2), visible only by looking (4).
- **The meta-audit's lessons:**
  1. Check each comparison against its lever's declared scope before judging. The costliest escapes measured something other than the lever, and all were detectable without a model.
  2. Simulate each decision rule under the null when it's written, as a test. The early-stopping warnings of r01b, r03 and r04 had no numbers, and changed nothing for 33 hours.
  3. Give each cross-cutting concept one owner, and fix the class, not the site. The rotation fix of 2026-09-25 went site by site, and the next day's context builders brought the bug back.
  4. Change the method in small steps, each with its invariant.
  5. Treat a stratum anomaly as a bug hunt before blaming the lever: ken-cd's tables at 0.25 were put down to misbinding noise while the rotated-sheet bug was giving them the title block as their lead-in. When a lever is built, dump the context it adds for each document, and get people looking at units early.

## Spend

Every model call's reported cost, from the ledgers, as of 2026-10-03.

- **By month:** September 2026 $43.39; October 2026 (to the 3rd) $2.43.
- **By kind:**
  - judging $37.77
  - extraction $5.25
  - comparison $1.13
  - eye tests $0.84
  - page tests $0.72
  - situating $0.13
- **By round:**

  | Round | USD | Round | USD | Round | USD |
  |---|---|---|---|---|---|
  | r00 | 0.83 | r04 | 1.70 | r06 | 3.38 |
  | r01 | 10.03 | r04h | 1.21 | r07 | 3.38 |
  | r01b | 3.40 | r05 | 1.04 | r08 | 3.55 |
  | r02 | 1.09 | r05b | 1.36 | r09 | 2.18 |
  | r02h | 0.96 | r05c | 0.99 | r09b | 0.55 |
  | r03 | 2.51 | r05d | 1.11 | r09h | 0.14 |

- **Other tags:**

  | Tag | USD |
  |---|---|
  | maintenance | 2.66 |
  | controlled documents | 1.05 |
  | eye tests | 0.84 |
  | page tests | 0.72 |
  | real revision pairs | 0.68 |
  | spot check sc01 | 0.46 |

- **Total:** $45.82.
- **The ledgers now stay local** (`benchmarks/ledger.jsonl`, git-ignored) for the budget caps. A month's spend is added here.

## Also removed, with their records

- **Spot check sc01** (2026-09-30, items 1–5 of 16, round 0 against the champion):
  - **Its findings:** tables lost their structure before the model saw them (a stacked table's second header row, header cells cut short, wrapped cells as unlabelled rows; the [one table model](../plans/one-table-model-2026-09-30.md)); entity against conditions was underspecified ("2 ton unit" given as a condition); a unit held one reader's claims while people and judges saw the whole page. Its lever ideas have rows in the lever index, its situations rows in the [catalogue](../samples-and-testing.md#the-catalogue-of-situations), and its rubric v7 candidate is in *Resumed query rounds*.
  - The owner (2026-10-03): "I won't get back to that spotcheck." So the survey it awaited is dropped, and nothing waits on it.
- **Evaluation batches s01 and s02** (2026-09-25; 17 items each, labelled by the owner, Claude and a panel of up to seven hosted models):
  - **Agreement:** on claims, verdict α 0.75 and the usable-or-not gate 0.89 with four reviewers; 0.59 and 0.68 with eight, some much more lenient. Dawid–Skene estimated the reviewers' accuracy at 0.58–1.00 from the labels alone; the owner agreed with the others' majority on 9 of 12 claims. Per field, entity and attribute reached α 0.72–0.73, basis 0.20; α understates agreement when nearly every answer is "ok", so raw agreement is reported beside it ([decision 0018](../decisions/0018-several-raters-none-ground-truth.md)).
  - **gemma-4's errors were mostly ours:** sections assigned by page, boxed headings taken for figures, a caption pattern, overviews too coarse for small labels, partial attributes, comparisons not told the sides were different designs, quotes composed from chart labels. Each was fixed or has a lever row; the relations across proposals are an open question of [criteria-first comparison](../plans/n-way-comparison-2026-09-23.md).
  - **Judged blind, the panel said most claims had only partly enough input** (2 of 12 enough, 9 partly): surrounding text missing most often (68 marks), then something on another page (36): the case for the context levers tried in round 1.
  - **Weak items:** one answerable from general knowledge (Young's modulus) tests nothing; sample items the document alone can settle.
  - The owner: "I think we won't use those labels again."
- **The eye and page tests' generated pages,** and the page test's recorded answers. The findings are in [eye tests](eye-tests-2026-09-30.md) and [page tests](page-tests-2026-10-01.md). The eye tests' answers stay, as a test replays them.
