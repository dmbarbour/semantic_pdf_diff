# Statistics and review audit

- **Date:** 2026-09-28
- **Asked by:** the owner: "We should aim to improve known flaws in our statistics and review to find more of them." The spot check had just shown a junk "Within:" line (a table value taken for a numbered item) and claims about table rows the band's crop didn't show.
- **Method:**
  - A read-only audit of the round statistics, judging and spot checks against rounds r06–r09h.
  - Its figures come from the rounds' files and copies of the r09* run stores, with no model calls.
  - I re-checked items 1, 4, 6, 8 and 10 in code and on the rounds' data before changing anything. Items 2, 3, 5 and 7 rest on the audit's simulations, not mine.
- **Already known, fixed alongside:**
  - bands of one region counted as independent
  - judges without the whole page or the full claim sets (rubric v6)
  - stems taken from table values

## Findings, ranked by how likely each was to change a decision

| # | Finding | Checked | Done |
|---|---|---|---|
| 1 | **Decisions sat on their thresholds.** Several wins' lower bounds were within 0.01 of 0.50: r01 neighbours (0.501), r02 (0.503), r09h (0.503). Clustering by region moved r09h's low bound from 0.500 to 0.529 only because its 3 multi-band regions happened to split. | Yes: every round re-decided, 3 ways | Cluster-robust t intervals; borderline calls flagged |
| 2 | **"No worse, with another gain" names no gain.** A lever with no effect lands on "no worse" 8–12% of the time (simulated). r08's merged readings entered on fewer claims, and r09h on "missing" tags from the same verdicts. | Code read; simulation not rerun | Proposal A |
| 3 | **Levers that re-ask every image are diluted by re-asking noise.** The A/A control changed 132 of 270 units just by re-asking image tasks, so a chart rule's effect on chart tiles is averaged with noise on every other tile. At risk: r08 charts (0.59) and r07 locator (0.58), both "no worse". | A/A figures read; the dilution is inferred | Proposal B |
| 4 | **Merged readings carried text wording into visual units.** A unit showed each merged claim in its representative's words, usually a text reading's. A text lever then changed visual units whose own readings hadn't changed, and one change counted in two units. | Yes: see below | Units show each reading in its own words |
| 5 | **Several variants per round.** With 3–6 variants, the chance of accepting some lever with no effect is 14–26% per round. A lever with a true rate of 0.60 is accepted 37% of the time, and then reports about 0.67. | Simulation not rerun | Proposal A |
| 6 | **Strata are weak and incomplete.** A stratum at 0.35–0.40 blocks only 14–25% of the time at 6–13 units. The plan stratifies by document family too, but the code didn't. | Yes: code; strata recomputed | Document-family strata; a watch list |
| 7 | **The sample over-represents small kinds.** Sampling is round-robin over text, table and visual, and a region cut into 4 bands is 4 times as likely to be picked. r09 excerpts: 0.508 as sampled, 0.538 weighted by changed units. | Code read | Weighted mean reported alongside |
| 8 | **Escalation judges' failures were lost.** Qwen's failed verdicts were never retried, and each call overwrote the failure count, so Qwen showed 0. r09 excerpts decided on 31 of 32 units, and the dropped units are the longest. | Yes: code | Retried once at the end; counted over the round |
| 9 | **The spot-check anchor measures easy pairs.** sc01 compares round 0 with the whole champion, not a round's close single-lever calls. At 16 units, agreement is uncertain by about ±0.2. | Yes | Proposal C |
| 10 | **Minor:** rubric v4 says hidden claims are identical, but units over 100 claims still hide unique ones (1 unit in r09 aa); an empty baseline was cut into bands but an empty variant wasn't. | Yes | v6 shows every claim; banding made symmetric |

**Minor, not acted on:**
- Qwen leans 0.055 toward the smaller set, against MiMo's 0.003 (490 units both judged). It moves an overall rate by at most 0.02.
- In the A/A, 9 of 32 units were scored by Qwen alone, after MiMo timed out at 450 s. Streaming should make that rarer.
- r09b's development win was measured after choosing fragments from r09's per-unit results.

## What changed

**Intervals (items 1, 7):**
- **The method:** a cluster-robust t interval (CR1, t with G − 1 degrees of freedom), clustered by page region, replaces the percentile bootstrap. It's deterministic, and corrects for small samples.
- **Effect:** intervals are slightly wider. No decision in rounds 1–9 changes against the region-clustered bootstrap.
- **`borderline`** lists any bound within 0.03 of its threshold. Such calls are reported, not trusted on their own. Flagged so far:
  - r01 neighbours, r02, r03 stems and r09h (wins)
  - r06 merged readings, r07 locator and r08 charts ("no worse")
- **`overall_weighted_by_changed`** is reported alongside the sampled mean, for new batches.

**Units (item 4):**
- A unit now shows each merged claim once, as its own tasks read it: the first sighting's words, under that reading's ID. A batch records this as `"unit_claims": "own readings"`.
- `add_context` refuses batches built the old way, since it would recompute different units. sc01 already has its context, so this doesn't affect it.
- **Units changed by a lever, old collect against new:**

  | Batch | Visual, old → new | Text, old → new |
  |---|---|---|
  | r09b fragments | 9 → 2 | 25 → 27 |
  | r09h fragments | 10 → 3 | 11 → 11 |
  | r09 excerpts | 22 → 4 | 38 → 40 |

- **So fragments' weak visual stratum** (0.44 in development, 0.40 held out) was mostly merge wording, not image readings. That answers r09h's open question.

**Strata (item 6):**
- **Document families** (reports, drawings, manuals, rules) are set in `scripts/slices.json` and now block like the kinds of region, at 6 units or more. No past decision changes.
- **`watch`** lists strata with a mean below 0.45 on 10 or more units that don't block. Past rounds' watch entries worth a look:
  - **merged readings on drawings:** 0.39 on 17 units (r08) and 0.41 on 11 (r07), against 0.57 on 17 (r06). r08 accepted merging. Those batches used the old collect, where merge wording leaked into units, so this needs a fresh measurement before any conclusion.
  - **excerpt quotes on drawings:** 0.39 on 18 units (r09); not accepted anyway.

**Judging (items 8, 10):**
- Escalation judges' failed verdicts are asked once more when a variant's sample is done, in rounds and spot checks.
- Failure counts add up over the round.
- Banding treats an empty side the same whichever side it is.

## Proposals for the owner

**A. Multiplicity and "no worse" (items 2, 5):**
- **Promotion needs a combination round plus a held-out check,** with the held-out criterion written into `round.json` before judging (e.g. mean above 0.5 and no stratum loss). This is what r02/r02h and r04/r04h did.
- **Quote the held-out effect, not the development one:** development figures of accepted levers are inflated by selection.
- **"No worse" needs a named gain,** with its metric and threshold in `round.json` before judging (e.g. cost per page down 10%, or claims per page down 15% with no stratum loss). The mechanical figures would then record tokens and cost per page for each variant.
- **Alternative:** a Holm correction within a round. It's cheaper in rounds but weaker than a held-out check.

**B. Levers that act on part of a page (item 3):**
- **Sample only units where the lever acts:** for example, tiles the chart rule applies to, from the variant's own prompts.
- **Size n from the A/A control's share of changed units.** This matters most for rules that re-ask every image.

**C. The next spot check (item 9):**
- about 30 units from a decided round's batch, oversampling close units and ones that flipped with the order
- one person's marks on more units, rather than the same units twice
- a few units seen by several people, if a panel of people forms, so that people's reliability can be estimated too

**D. Measurements owed, after the owner's surveys:**
- **Stems as fixed:** accepted in r03 (0.63) with table values taken for numbered items.
- **Merged readings on drawings, with the new units.**
- **sc01 re-judged with rubric v6** (about $0.40), for the first weighted-quality fit.
