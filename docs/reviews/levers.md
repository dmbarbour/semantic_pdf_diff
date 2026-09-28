# Lever index

Every query lever tried in the [improvement rounds](../plans/query-improvement-2026-09-26.md): what it does, what we expected, what happened, why we think it happened, and what to try next.

- **Detail:** each round's review in this folder.
- **Per-unit clues:** `benchmarks/rounds/<round>/pairs-<variant>/analysis.json`, browsable as `insights.html` in the round folder (regenerate with `scripts/run_round.py <round> --only report`).
- **Win rates:** the variant's share of pairwise preferences against the baseline, judged in both orders, with a 90% bootstrap interval.

## Status at a glance

| Lever | Setting | Status | Best evidence |
|---|---|---|---|
| Neighbouring text | `context_before/after: 400` | In the champion | r01b 0.68 (0.56–0.80); with the others r02 0.68, r02h 0.71 |
| Text layer with images | `visual_text_layer: 1500` | In the champion | r01b 0.72 (0.56–0.88) |
| Table lead-in | `table_context: 400` | In the champion | r01b 0.71 (0.56–0.85), 15 units |
| Numbered-item stems | `stem_context` | In the champion | r03 0.63 (0.51–0.75); r04 combined 0.64 / r04h 0.69 |
| Whitespace bands | `tiling: bands` | In the champion | r03 0.83 (0.70–0.94) |
| Grown tiles | `grow_tiles` | In the champion | r03 0.80 (0.70–0.89) |
| Skip empty tiles | `skip_empty` | In the champion (cost only) | 43 of 963 tiles (4.5%) skipped on the development slices, 0 claims lost |
| Table filter | `table_filter` | Not accepted | r01b 0.41 (0.23–0.57), 12 pages |
| References | `references` | Not accepted | r05 0.50 (0.35–0.66), 17 units |
| Sheet details | `sheet_details` | Parked | r05–r05d: 0.64 → 0.50 → 0.48 → 0.42 |
| Merged readings | `reconcile` | In the champion (2026-09-27) | r08 0.56 (0.45–0.67) no worse, with 13.5% fewer claims; the owner's design decision |
| Fragment quotes | `quote_match: fragments` | In the champion (2026-09-28) | r09b 0.66 (0.53–0.77); held-out r09h 0.66 (0.50–0.81), text 0.89; visual weaker in both (0.44, 0.40) |
| Excerpt quotes (with an in-order window) | `quote_match: excerpts` | Not accepted | r09 0.51 (0.39–0.63); the window let chart-axis labels through as values |
| Chart-reading rule | `visual_rules` | Not accepted | r08 0.59 (0.47–0.71); vaguer readings, out-of-range ones remain |
| Tile locator | `tile_locator` | Parked | r06 0.49 (flawed sampling), r07 0.58 (0.47–0.68): no worse; wins on IEA and LCIT in both rounds |

## Levers

### Neighbouring text (`context_before`, `context_after`)
- **Mechanism:** 400 characters before and after each text chunk, marked as context not to extract from.
- **Expected:** fewer vague entities, better conditions. **Got:** a win.
- **Why (judges):** it captured values the baseline missed and avoided duplicate claims.
- **Next:** size by paragraph rather than characters, and try the preceding heading paragraph only.

### Text layer with images (`visual_text_layer`)
- **Mechanism:** up to 1,500 characters of the crop's PDF text layer with each image.
- **Expected:** fewer misread labels. **Got:** a win.
- **Why:** it fixed misread units (N·m² vs N·m³), properties (shear modulus vs yield strength) and names ("HARVEST HOME").
- **Watch:** one loss was a title-block tile yielding no claims.

### Table lead-in (`table_context`)
- **Mechanism:** 400 characters of text above a table, with each row.
- **Got:** a win on 15 units.
- **Why:** rows were bound to their table's subject ("Module A", "NREL 5-MW baseline").

### Numbered-item stems (`stem_context`)
- **Mechanism:** "Within: Contest 9 > 9-2. Cooking > c. …" on text and table tasks, carried across pages.
- **Got:** text 0.69, tables neutral. **Loses on IEA-15** in r03 and r04 (0.31): judges said entities and attributes were built from the path.
- **Next:** give the stem as the parent only, not a full path, where the path is long or not numbered.

### Whitespace bands (`tiling: bands`)
- **Mechanism:** on report-sized pages, full-width bands cut at whitespace gaps, skipping bands with no graphics.
- **Got:** the largest single win.
- **Why:** chart readings consistent with their axes, legends kept with charts, fewer near-duplicate claims.
- **Watch:** one band read only part of an IEA page.

### Grown tiles (`grow_tiles`)
- **Mechanism:** grid tiles grown to include every text line they cut.
- **Got:** a win on sheets and reports.
- **Why:** cut notes read whole ("2x4 cedar handrail"), values bound to named parts.

### Skip empty tiles (`skip_empty`)
- **Mechanism:** tiles with no text line, drawing or image aren't sent; the rest keep their numbers, so recorded answers still replay.
- **Found:** in round 5d's analysis, the model's issue notes kept saying "the image is blank".
- **Measured without the model:** 43 of 963 champion tiles skipped on the development slices, and none of them had yielded a claim.
- **Accepted into the champion as a pure cost saving** (2026-09-27). There are no changed answers to judge.

### Quote matching (`quote_match`)
- **Found in the overall review:** the verbatim quote check dropped a third of all text claims (2,826 of 8,661 in recorded answers). They were mostly elided quotes, line-end hyphenation, Unicode variants, and table cells joined with "|".
- **`fragments`:**
  - normalizes Unicode, case, dashes, quote marks and line-end hyphens
  - accepts quotes whose "…" or "|" parts each appear, contiguous and in order
  - recovers about 1,070 claims
  - **Accepted in r09b:** 0.66, text 0.77. Missing fell sharply; misbound rose.
- **`excerpts`:** also accepts words read in order across a pseudo-table. It recovers about 1,700 claims, but let chart-axis labels through as values (r09: 0.51). Not accepted.
- **Measurement notes:**
  - No requests change, so testing costs judging only.
  - An A/A control in the same round (r09: 0.48 ± 0.12) gives the noise floor.

### Table filter (`table_filter`)
- **Mechanism:** drops detected "tables" that are chart gridlines or drawing grids.
- **Got:** changed 12 pages, inconclusive; not re-tested.
- **Next:** measure on pages with false tables only.

### References (`references`)
- **Mechanism:** abbreviations defined elsewhere ("PI = proportional-integral"), and captions of cited figures and tables.
- **Got:** neutral; rarely active (17 of 137 units).
- **Why:** most differences were run-to-run variation. One clear win: a filter bound to the cited figure's name. One loss: an empty answer.
- **Next:** only revisit if citations become a complaint.

### Sheet details (`sheet_details`)
- **Mechanism:** a drawing sheet cut into its numbered details, each crop titled with the sheet and detail; side columns (title block, notes) read separately.
- **Got:** it won where designed (dc p39–42 0.75), and lost elsewhere.
- **Why, in three layers:**
  1. **Crops too large:** oversized crops lost small print (fixed).
  2. **A note switched extraction off:** "Title block" in the note made gemma skip a legible revision table as "not engineering".
  3. **An isolated crop reads as out of scope:** even untitled, a crop holding only a title block reads as administrative. Grid tiles mixing drawing and title block read it.

  Also: wrong detail titles where detail numbers sit close together.
- **Lessons:**
  - Crops change what the model considers in scope.
  - Context notes should say where, not what to expect.
  - A wrong title is worse than none.
- **Next ideas:**
  - Keep grid tiles, and add each tile's detail title as context only where one detail covers the whole tile.
  - Treat provenance separately (plans index: subject, parties and provenance).

### Merged readings (`reconcile`)
- **Mechanism:** readings of one fact by different tasks become one claim, keeping every wording.
- **Got:** no worse overall; a text win (0.72) with a visual weakness (0.43).
- **Why (from the round's analysis), two causes:**
  1. **Measurement:** on large units, judges saw different samples of each side (fixed: every difference plus one shared sample).
  2. **Lever:** the representative wording was chosen by region and dropped conditions another reading had (fixed: the most informative reading represents).
- **r07 (with the most informative reading representing):** 0.54. The judges tagged 31 variant claims invented against 11, because wide regions attach context from elsewhere ("Structure South Elevation - Main"). Reverted to the most local reading.
- **r08 (the most local reading representing, rubric v3):** 0.56 (0.45–0.67). Duplicates 87 → 63, invented 10 → 7, conditions 16 → 11, but missing 51 → 65.
- **The missing facts, traced:** "Module A" merged with "Module B" because "a" was a stopword (fixed, `e7ea841`).
- **Accepted into the champion:** no worse, with a gain (13.5% fewer claims) and the owner's decision.

### Chart-reading rule (`visual_rules`)
- **Mechanism:** image tasks only: values only where labelled or marked, otherwise trend and range; series from the legend.
- **Source:** round 7's remarks.
- **Got:** 0.59, no worse. The out-of-range readings survived (NREL: 23° and 25° on a 0–20° axis), and IEA lost specific readings to vague and sometimes wrong trends.
- **Next:** a mechanical range check instead of a prohibition.

### Tile locator (`tile_locator`)
- **Mechanism:** a 384 px page thumbnail with the tile outlined in red, as a second image with each tile. The owner's suggestion.
- **r06:** 0.49, with flawed sampling. **r07:** 0.58 (0.47–0.68), no worse.
- **By document, the same direction in both rounds:** IEA-15 0.82 / 0.80 and LCIT 1.00 / 0.92 won; dc-manual 0.00 / 0.08 lost.
- **Tags:** fewer missing facts, invented claims and quote problems; slightly more duplicates. The model's issue notes never mention the thumbnail.
- **Parked:** a small cost with no established gain.
- **Next ideas:**
  - a larger sample on report pages only
  - a larger thumbnail on sheets
  - the thumbnail only for tiles that cut a figure

## Measurement notes (affect how to read the table)

- **A/A noise:** two readings of the same pages score about 0.5 ± 0.08 over 48 units (r01), so single units mean little.
- **Early stopping at 16–24 units inflates wins;** the combination rounds (r02, r04) at 40–48 units are more honest.
- **Before round 7,** units with more than 25 claims showed judges separately drawn samples, which added noise to visual units in every round. This was fixed in `5850dfd`.
- **Rubric v2 from round 7:** document administration is neutral; judges tag each side's problems and may leave remarks.
- **Free cost saving noticed in r05d's analysis:** the model kept reporting blank tiles. Built as `skip_empty` (see above).
