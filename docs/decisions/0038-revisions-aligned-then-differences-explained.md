# 0038. Revisions are aligned item by item before they're judged, and each difference is named by kind

- **Status:** Accepted (2026-10-21)
- **Source:** the [revision comparison plan](../plans/revision-comparison-2026-10-02.md) (decisions 1, 2, 6, 7 and 10 to 12; milestones 1, 2 and 4), from [controlled documents](../plans/controlled-documents-2026-10-01.md) milestone 4; the research note [correspondence without a model](../research/correspondence-without-a-model-2026-10-02.md)

## Context

Pairs were chosen by text similarity (each claim's top 4 by TF-IDF), and a judge decided correspondence and difference at once, from two claims. On six controlled revision pairs gemma-4 found all 22 changes, but only 41 of 120 "different" findings were changes:
- 59 came from names by position ("blower 5"), which shift when a row is inserted
- 17 took two items of a kind for one item changed
- 3 of 13 additions were paired with a neighbour and called changes

The six small pairs took 1,798 judged pairs ($0.247). The owner, 2026-10-02: "establish candidate differences then analyze them by some means for 'why different' with attention to known issues like renamings or context shifts." On correspondence: "making it more soft/probabilistic/heuristic in nature without fully intelligent [...] a weighted mixture of techniques that each can output confidence between 0 and 1. Pairwise analyses of all pairs of things is super-expensive, so if we can use other means and filter it down that's good."

## Decision

- **Alignment first** (`align`, a default; revisions mode only, proposals keep retrieval): which items correspond is decided across the whole document before any value is judged (the `correspondence` hook, `align.py`).
  - **Items:** a revision's claims grouped by a tag in the entity (`P-101B`), else the entity's words. A claim named by position joins the tagged item whose values it clearly repeats.
  - **Scored from cheap signals, no model:** shared values (rare ones counting more) 0.6, names whose identifiers agree 0.3 ("Room 104" isn't "Room 105"), attributes 0.1. No new dependency.
  - **Best first, with a floor and a margin** (decision 10): below 0.3 there's no counterpart; a counterpart not 0.15 ahead of the next candidate is ambiguous and goes to the judge, never aligned mechanically.
  - **One counterpart favoured, not assumed** (decision 11): a leftover item attaches to the item, or group of items, uniquely holding most of its values.
  - **Within matched items:** a value whose readings agree on conditions across the revisions is settled as equivalent without a model, unless identifiers, stated frames or holders conflict. The rest pair by attribute, then by wording, for the judge.
  - **Unaligned items** are listed as possibly added or removed, and not compared.
- **Groupings shown as the tool sees them** (decision 12; the owner: "It's best that the report is honest about how the pdf_semantic_diff is viewing the groupings in these cases."): a report section (`groupings` in `report.json`) with every group (matched, renamed, attached, ambiguous, unaligned, split or merge candidates), its evidence and its outcome. Split and merge candidates (names sharing a stem, values that add up) are labelled candidates: not compared claim by claim, not confirmed.
- **Differences named in a second pass** (`explain_differences`, a default; revisions only):
  - each "different" or "uncertain" finding gets one more call, shown both claims, the judgment, each claim's item and the other revision's claims stating each value
  - it names a kind: changed, conditions, renamed, moved, restated, split_or_merge, misread, not_same_item or unclear, recorded as the finding's `explanation`; the judge's relation stands
  - the report groups value changes, editorial changes and not changes, value changes first
- **Accepted risks** (the owner):
  - items with nothing to anchor them may be misaligned: "even a human would definitely get that wrong or just consider it a wholesale replacement of a component"
  - repeated values make weak identity: "fungible things naturally have weak identity even to the human eye"
- **Set by inspection** (decision 7; the owner: "For early development, we shouldn't consider any levers defaults like a null hypothesis"): the weights, floor and margin were set by eye on the controlled pairs, and both levers are defaults by judgement.

## Consequences

- **The six controlled pairs:** "different" findings that are changes 41/120 → 31/33; pairs judged 1,798 → 58, 336 settled without a model; every change still found, additions 10/13 → 13/13.
- **Real pairs:** TS 38.300 v19.2 → v19.3 settled 4,845 pairs and judged 501; QUIC draft-34 → RFC 9000, mostly editorial, 1,042 and 998. The suspect differences left (list members, positional attributes, two of a kind) are named "not the same item".
- **Explanations** (prompt version 4): kinds right 100 of 108 on the aligned controlled pairs, 189 of 216 with alignment off.
- **"Why" is scored as well as "whether":** each controlled revision's key logs its edits by kind (changed, added, removed, renamed, moved, conditions, split).
- **Extended since** by [claim context](../plans/claim-context-2026-10-14.md): holders and hedges in alignment (`align_hedges`, a default), names as printed (`align_printed`, off).
- **Not settled:** a model confirming splits and merges (open), positional pairings, calibrated confidences, real series and raters beyond the text diff: the plans index's *Comparing revisions, further*. Identity at extraction is claim context's; proposals mode is [criteria-first comparison](../plans/n-way-comparison-2026-09-23.md)'s.
