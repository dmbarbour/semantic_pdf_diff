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
