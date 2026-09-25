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
