# Review: first review batch (s01) and what it found

- **Date:** 2026-09-25
- **Plan:** [evaluation-benchmarks](../plans/evaluation-benchmarks-2026-09-23.md), with [test-models-and-record-replay](../plans/test-models-and-record-replay-2026-09-24.md)
- **Batch:** `benchmarks/batches/s01`: 17 items (12 claims, 3 about statements, 2 claim pairs) sampled from gemma-4-31B's recorded answers on the turbine, drawing and rules slices
- **Reviewers so far:** Claude (Opus 5.5, in session), and a panel of google/gemini-3.1-pro, Qwen/Qwen3.5-397B-A17B and moonshotai/Kimi-K3 (about $0.70 per full panel pass on this batch). The owner's labels are pending.

## Agreement

After one rubric clarification (below), across the four reviewers:

| Item type | Items | Verdict α | Usable-or-not α | Notes |
|---|---|---|---|---|
| Claims | 12 | 0.75 | 0.89 | Usable gate reliable (≥ 0.80); four-way verdict tentative |
| About statements | 3 | 0.27 | 0.27 | Too few items to mean much |
| Claim pairs | 2 | −0.17 | −0.17 | Split on what relations mean across proposals (below) |

Flags with full or strong agreement: `condition_misattached` and `region_wrong` (α 1.0), `value_misread` (0.84), `quote_not_verbatim` (0.75).

**Rubric clarifications** (from the disagreements):
- "Correct" judges faithfulness only; usefulness is a flag. All three models called a title-block address "correct"; I had called it flawed.
- A partial truth stated as the whole is "flawed" (`attribute_misassigned`), e.g. "material composition: glass_triax" for one layer of several. The reviewers split 2–2 on two such claims.
- Pair items now state that A and B come from different sources, and give the relation definitions.

## What gemma-4-31B got wrong, and why

Among the 12 claims, the consensus is about 4 correct, 4 flawed and 4 wrong. That's far too small a sample for a rate, but the causes are specific, and most are ours rather than the model's:

1. **Section attribution by page (3 claims).** Rules for the Cooking subcontest (9-2) were attributed to 9-3 Dinner Party. Pages belong to the last outline entry starting on or before them, and 9-3 starts lower on the same page, so every task on that page got 9-3's heading. **Fix:** place outline entries by their position on the page, so a region gets the heading above it.
2. **Figure detection on boxed headings.** "Contest 10. Energy Balance" (a heading drawn in a box) became a figure. The model then described Figure 10 from the surrounding text: correct content, wrong region. **Fix:** skip drawing clusters that are only frames around text.
3. **Caption pattern.** "Table 5-1 summarizes…" was read as a caption labelled "table 5": the number `5-1` backtracked to `5` plus a separator. **Fix:** a separator mustn't be followed by a digit.
4. **Overview resolution (1 claim).** "FINISHED FLOOR 2' - 9 1/2"" was read as 2'-3" from a page overview of a large sheet. gemma resizes every image to a fixed budget (about 284 tokens), so whole-sheet overviews lose small labels. **Lever:** treat overviews as context only, or down-weight values read from them when tiles cover the same area.
5. **Partial or vague attributes (2 claims).** "material composition = X" was used for one material of several. **Lever:** a prompt rule to say what the value is part of (e.g. spar cap, outer skin).
6. **Cross-proposal comparisons (2 pairs).** The comparison prompt doesn't say that A and B come from different sources. One rationale treated two teams' houses as one building (team B's floor height "relative to" team A's datum). **Fix:** tell the model which mode it's in: different designs (proposals) or versions of one document (revisions).
7. **Quotes composed from chart labels** rather than quoted (2 claims). A prompt lever: for charts, quote the visible labels used and say so.

## Open design question

**What the relations mean across proposals.** The owner's call, since it shapes criteria-first comparison.

- **The case:** NREL 5 MW's pitch angle at 25 m/s, against IEA 15 MW's pitch controller objective.
- **The reviewers split:** the three panel models said "unrelated" (different turbines), and I said "complementary" (compatible facts about corresponding subsystems).
- **In proposal mode, the interesting relation is "same attribute, different value across designs".** Today's labels mix that with contradiction ("different: incompatible values under the same conditions"), which only makes sense for revisions.

## Update: a larger panel and consensus without a referee

Four more hosted models joined the panel: ByteDance/Seed-2.0-pro, thinkingmachines/Inkling, deepseek-ai/DeepSeek-V4-Flash-Vision-Exp and XiaomiMiMo/MiMo-V2.6-Pro. NVIDIA Nemotron-3-Ultra rejected the image requests (HTTP 400). DeepSeek's reasoning ran past the 16,000-token output cap on 2 items.

With eight reviewers, raw agreement on claims fell (verdict α 0.59, usable gate 0.68), because some reviewers are much more lenient. `review consensus` (Dawid–Skene) estimates each reviewer's reliability from the labels alone.

| Reviewer | Claims: agrees with the others' majority | Estimated accuracy |
|---|---|---|
| claude-opus-5.5 | 11/11 | 1.00 |
| MiMo-V2.6-Pro | 11/12 | 0.92 |
| gemini-3.1-pro | 10/11 | 0.92 |
| Kimi-K3 | 10/11 | 0.92 |
| DeepSeek-V4-Flash-Vision | 10/11 | 0.91 |
| Qwen3.5-397B | 10/12 | 0.83 |
| Inkling | 8/11 | 0.75 |
| Seed-2.0-pro | 7/12 | 0.58 (most lenient: e.g. missed the misattached condition) |

- **Consensus is confident:** no claim is contested (every consensus is above 0.8 probability).
- **The sample is small:** 12 claims make these estimates rough.
- **The same procedure works for a panel of people with no referee** (see `benchmarks/README.md`).

## Update: the owner's review, and what changed because of it

The owner labelled all 17 items (`labels/David.json`). They found it slow: flags were far from the fields they concerned, and there was no quick way to say which part of a claim was wrong.

**Where the owner differed from the other reviewers' majority** (rubric-level disagreements):
- **Stricter on two claims:** glass_triax (wrong, not flawed), and K_I, which should be separated from its condition.
- **More lenient on one:** a quote composed from chart labels.
- **The boxed-heading "about":** the owner, Gemini and Claude said wrong; the majority didn't.

Consensus estimates put the owner at 9/12 agreement with the others on claims.

**What the notes led to:**

| Note | Change |
|---|---|
| Answers should sit next to each part of a claim; "contested" per field | Per-field ✓ / ✗ / ? next to entity, attribute, value, unit, conditions, basis, approximate, quote and section; pairs get four questions (A read right, B read right, same subject, relation right); "about" statements get about, role, keywords, type. The verdict follows the field answers unless chosen; flags moved under "More detail". Panel models answer per field too, and agreement is reported per field. |
| No way to say "wrong section" | The section is one of the fields. |
| "Bad cropping" (6 items) | Review: tile crops now show the model's image outlined within its surroundings. Extraction: each detected figure (with caption and legend) is now read whole, besides the tile grid that cut through them (`figure_tasks`, about 10% more visual tasks). |
| Not knowing how to read a chart, for reviewers and models alike | Clarity option "not sure how to read the source". An extraction prompt rule: say so, lower confidence, mark readings approximate, and don't guess unexplained conventions. |
| K_I should be separated from its condition; "composition" for one layer | Prompt rules: the attribute names the property only; say what a part belongs to. |
| "Would be complementary if about the same subject" | A pair flag for exactly that; the relation vocabulary itself is still open (see the [research note](../research/comparing-designs-2026-09-25.md)). |
| Let models zoom interactively, within a quota | Tentative plan row: interactive zoom for models. |
| Try DeepInfra embedding models | Noted in the retrieval plan. |
| Young's modulus is a weak test item: general knowledge corroborates it | To be addressed in sampling: prefer items not answerable from general knowledge. |

Found on the way: overview tasks were refined (split) against the design, because tags had been renamed to `overview:pN`; fixed.

## Batch s02 (after the fixes, prompt v6)

Sampled from the re-recorded answers with the same sizes as s01 (seed 2); reviewed by Claude and the seven-model panel, per field; the owner's labels are pending.

- **Claim consensus** (Dawid–Skene): 6 correct, 3 flawed, 3 wrong. For s01 it was 4, 5 and 3. With 12 different claims per batch, that's no evidence of improvement yet; batches need to be larger or repeated to measure changes.
- **Per-field agreement on claims:**

  | Field | α | Raw pairwise agreement |
  |---|---|---|
  | Entity | 0.73 | 0.94 |
  | Attribute | 0.72 | 0.94 |
  | Unit | 0.44 | 0.96 |
  | Quote | 0.47 | 0.79 |
  | Value | 0.37 | 0.87 |
  | Section | 0.26 | 0.85 |
  | Conditions | 0.28 | 0.83 |
  | Approximate | 0.19 | 0.86 |
  | Basis | 0.20 | 0.57 |

  α understates agreement when nearly all answers are "ok" (a prevalence effect), so reports now show both. Basis is the genuinely ambiguous field: every claim says "unknown", and reviewers split on whether that's acceptable. The field's help now says "unknown" is wrong for a "shall" or "must" requirement or a reported measurement. The real fix is milestone 5 (epistemic status).
- **Verdict agreement was lower than s01** (α 0.34 vs 0.59). DeepSeek-V4-Flash-Vision stood out (estimated accuracy 0.38; its reasoning also ran long enough to truncate). Kimi timed out once.
- **Errors found:**
  - A tile cut "2x4 CEDAR HANDRAILS" to "2x4 CED", bound to "exterior elevation".
  - "30 m of ground (water surface) clearance" was read as a ground depth.
  - An axial stiffness was read off a chart at the wrong span (4e10 vs about 3.4e10).
  - A top-of-steel elevation was called a length.
  - Quotes were composed from axis labels or taken from a caption.
  - A table row key (wind speed 25 m/s) was treated as a property.
- **Slicing artefact:** slices that start mid-section have no heading on their first pages, because only outline entries inside the slice are copied. Fixing it changes the slices' bytes, and therefore every recording; deferred to the next planned re-record.

## s02 questions, judged blind by the panel

Six panel models judged s02's 17 questions from the exact inputs, without seeing the answers. Claude, having seen the answers, sat this stage out.

- **Consensus on the 12 claim questions:** 2 had enough input, 9 partly enough, 1 not enough (a table row read without its context).
- **What was missing, by how often reviewers marked it** (and their pairwise agreement):

  | Missing | Marks | Agreement |
  |---|---|---|
  | Surrounding text | 68 | 0.66 |
  | Something on another page | 36 | 0.56 |
  | Legend or key | 20 | 0.89 |
  | Table header | 16 | 0.92 |
  | Resolution | 16 | 0.82 |
  | Section heading | 15 | 0.81 |
  | Caption | 13 | 0.78 |

- **The pattern supports the next extraction lever.** Most wrong claims so far trace back to thin input rather than a weak model. The planned lever: give each extraction request labelled context (the section heading, the neighbouring paragraph, the figure's caption and legend), clearly separated from the source data to extract from.
- **Adequacy is judged less consistently than answers** (α 0.26, raw agreement 0.58); "partly" is a wide middle. The owner's blind judgments will show whether people split the same way.
- **Two panel fixes:** Gemini first answered the question it was shown instead of reviewing it, so the model's instructions are now fenced off in the judging prompt. Inkling gave its blind answer as a list, so model answers given as lists now become lines.
