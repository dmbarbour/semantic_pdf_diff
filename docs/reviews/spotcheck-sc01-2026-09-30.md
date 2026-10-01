# Spot check sc01: the owner's comments, with evidence

- **Date:** 2026-09-30, items 1–5 of 16 (the owner's survey is in progress).
- **Batch:** `benchmarks/spotchecks/sc01`, round 0's output (r02 and r02h baselines) against the champion (r09b and r09h fragments).
- **Evidence:** read from the batch's `pairs.json` (claims, and each table task's input) and from the runs' stores.

## Items

**Item 1: HabEx p4, a table band** (`u-habex-interim-p80-89-52da8af4-p4-table-b2of4`)
- **The owner:** "There is some confusion here between what is an 'Camera' channel vs. corresponding 'Spectrometer' channels. In part, this is due to the table parser not handling what is clearly two tables aligned into one, separated by a header layer. The "IR Guide" vs. "IR" is the only case where I can clearly distinguish these facts, but this feels more like an accident; ideally, the Header rows would better support distinguishing Cameras from Spectrometers. Perhaps we need clear visualization of tables when building rules in cases like this? Clear identification of hazards, too. In both cases, due to formatting, it's assuming spectrometer counts instead of resolution. In the 'Detector' cases, we should be treating the detector as a component of the camera, resulting in many misbindings."
- **What the extractor was sent:** one row per query, each with a single header row:
  - Header: `["", "UV", "Visible", "IR Guide"]`
    - "Cameras" is gone, and "UV Channel" became "UV".
    - The second table's header row ("Spectrometers | UV Channel | Visible Channel | IR Channel") isn't sent at all.
    - So the spectrometers' rows arrive under the cameras' header: `Row: ["FOV", "10.2\"", "1.9\"", "3.8\""]` is the spectrometers' FOV, and both sides bound 1.9" to the visible camera, whose FOV is 11.9".
  - **Wrapped cells become rows of their own:**
    - "Detector / 1×1 / CCD201" arrives as `["Detector", "1×1", ...]` and then `["", "CCD201", "CCD201", "LMAPD"]`, with no label.
    - "Spectrometer resolution" arrives as `["Spectrometer", "7", "140", "40"]`, read as counts.

**Item 2: ken manual p6, text** (`u-ken-manual-p70-79-3b80816c-p6-text`)
- **The owner:** "Sadly, no attempt to read the chart for corroboration or several additional claims, e.g. about month to month usage. It isn't clear to me that some of the mentioned 'conditions' shouldn't be part of an 'entity' instead, e.g. `(baseline unit size)` or `(2 ton unit)` relates to distinct subjects of a claim or comparison instead of the conditions under which it was tested; I wonder if this is a matter of instructions."
- **The charts were read, but in another unit.** Both runs read Figures 13 and 14 month by month:
  - the baseline in 28 claims (`figure:p6:0` and `figure:p6:1`), e.g. "2.5 ton HVAC unit | Space Heat energy usage | 0.55 MWh | January"
  - the champion in 12 (`figure:p6:0`; its tile covered Figure 14)
  - They're in the page's visual unit. A unit holds one kind of reading (text, table or visual), so this text unit shows none of them, although the page shown has both charts.
  - The readings are selective: 4–5 months per chart, and stacked segments approximate.
- **The charts' readers named the entity right; the text's didn't.** They wrote "2 ton HVAC unit" and "2.5 ton HVAC unit". The text claims wrote "HVAC system" with "2 ton unit" or "baseline unit size" as conditions.
  - The text never says the baseline is 2.5 tons; Figure 13's caption does.
- **The instructions invite it:** the schema hint defines conditions as "load, scenario, time, tolerances, scope". Nothing says that an alternative being compared belongs in the entity.

**Item 3: LCIT report p5, visual** (`u-lcit-report-p12-19-bb5dd36f-p5-visual`)
- **The owner:** "Item 3 has similar weirdness with conditions vs. entity as item 1."
- "across the four mission concepts" is given as a condition by both sides.
  - The champion's tile reading also bound the 100 to "mission concepts | quantity | 100", when it counts issues and concerns.

**Item 4: NREL 5 MW p10, a table band** — discussed before: claims about rows the band's crop didn't show. Judges and people now see the whole page (rubric v6).

**Item 5: HabEx p6, a text band** (`u-habex-interim-p80-89-52da8af4-p6-text-b1of2`)
- **The owner:** "Item 5 again ignores the figure as a source."
- **As in item 2:** the champion read the figure inside this band (`figure:p6:1`, 9 claims), but it belongs to the visual unit.

## Common threads

1. **Tables lose their structure before the model sees them** (item 1).
   - Rows go one per query, with only the top header row.
   - Stacked tables' second header rows are lost, header cells are cut short, and wrapped cells become unlabelled rows.
   - The model can't recover what it isn't sent.
   - Item 4's baseline (a claim per cell) against the champion (one claim per row, with conditions) is the same row-at-a-time framing.
2. **Entity against conditions is underspecified** (items 1, 2 and 3).
   - "Scenario" and "scope" in the conditions hint pull alternatives ("2 ton unit") and scopes ("across the four mission concepts") into conditions.
   - Nothing says how to name a component of a component (the camera's detector).
3. **A unit holds one kind of reading, but people and judges see the whole page** (items 2 and 5).
   - A text unit can be faulted for facts its page's figure reader has.
   - Corroboration between text and figures can't be judged.
   - With rubric v6 (the whole page, "missing" against everything), judges will see this too.
4. **The right context is often in another reader's region** (item 2): the caption names what the text calls "baseline unit size".

- **The owner's clarification of "visualization of tables when building rules" (2026-09-30):** "that's based on our prior discussion of how to process tables, e.g. for CSV or .xlsx files. We ask a model how to turn table rows into claims, and we might look for exceptions to this. It seems we're using a different tactic for PDFs, but I don't believe medium should be a severe differentiater here."
  - Claude first read it as a diagnostic view of parsed tables; that reading is withdrawn.

- **The owner on what judges should see (2026-09-30):** unsure, and suggested showing both queries without revealing which answer set came from which. Recorded as an open rubric v7 candidate in the [query-improvement plan](../plans/query-improvement-2026-09-26.md).

## Proposals

- **Lever ideas** (rows in the [lever index](levers.md)):
  - repair table structure before extraction
  - send table bands with the full header block
  - show the table's image with its text
  - showing the model the table clearly, with its hazards named, when it builds the table's rules (the owner's idea)
  - entity against conditions in the instructions
  - captions of the page's figures and tables as context for its text
- **For evaluation, needing the owner's review:** show a unit's claims from the page's other readers (figures, tables, tiles) as context beside its own, marked by reader.
  - Units would stay one reader each, so rounds still compare like with like.
  - "Missing" and corroboration could then be judged against everything the page yielded.
