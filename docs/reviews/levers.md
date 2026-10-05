# Lever index

Every query lever tried in the [improvement rounds](../plans/query-improvement-2026-09-26.md): what it does, what we expected, what happened, why we think it happened, and what to try next.

- **Detail:** each round's review in this folder.
- **Per-unit clues:** `benchmarks/rounds/<round>/pairs-<variant>/analysis.json`, browsable as `insights.html` in the round folder (regenerate with `scripts/run_round.py <round> --only report`).
- **Win rates:** the variant's share of pairwise preferences against the baseline, judged in both orders, with a 90% interval (a bootstrap until 2026-09-28; since then cluster-robust, by page region).
- **This index is the lever catalogue** (the owner, 2026-09-28): every lever idea gets a row when it's raised, built or not. Levers not accepted or parked are tried again against later champions, and other ways of doing one idea are tried as its variants.

## Status at a glance

| Lever | Setting | Status | Best evidence |
|---|---|---|---|
| Neighbouring text | `context_before/after: 400` | Default (2026-09-28) | r01b 0.68 (0.56–0.80); with the others r02 0.68, r02h 0.71 |
| Text layer with images | `visual_text_layer: 1500` | Default (2026-09-28) | r01b 0.72 (0.56–0.88) |
| Table lead-in | `table_context: 400` | Default (2026-09-28) | r01b 0.71 (0.56–0.85), 15 units |
| Numbered-item stems | `stem_context` | Default (2026-09-28) | r03 0.63 (0.51–0.75), borderline; r04 combined 0.64 / r04h 0.69. Measured with table values taken for numbered items (fixed 2026-09-28); the fixed version is unmeasured |
| Whitespace bands | `tiling: bands` | Default (2026-09-28) | r03 0.83 (0.70–0.94) |
| Grown tiles | `grow_tiles` | Default (2026-09-28) | r03 0.80 (0.70–0.89) |
| Skip empty tiles | `skip_empty` | Default (2026-09-28; cost only) | 43 of 963 tiles (4.5%) skipped on the development slices, 0 claims lost |
| Table filter | `table_filter` | Not accepted | r01b 0.41 (0.23–0.57), 12 pages |
| References | `references` | Not accepted | r05 0.50 (0.35–0.66), 17 units |
| Sheet details | `sheet_details` | Parked | r05–r05d: 0.64 → 0.50 → 0.48 → 0.42 |
| Merged readings | `reconcile` | Default (2026-09-28) | r08 0.56 (0.45–0.67) no worse, with 13.5% fewer claims; the owner's design decision |
| Fragment quotes | `quote_match: fragments` | Default (2026-09-28) | r09b 0.66 (0.53–0.77); held-out r09h 0.66 (0.50–0.81), borderline, text 0.89; visual weaker in both (0.44, 0.40), mostly from merged claims' wording shown in visual units (the statistics audit) |
| Excerpt quotes (with an in-order window) | `quote_match: excerpts` | Not accepted | r09 0.51 (0.39–0.63); the window let chart-axis labels through as values |
| Chart-reading rule | `visual_rules` | Not accepted | r08 0.59 (0.47–0.71); vaguer readings, out-of-range ones remain |
| Tile locator | `tile_locator` | Parked | r06 0.49 (flawed sampling), r07 0.58 (0.47–0.68): no worse; wins on IEA and LCIT in both rounds |
| Table rules | `table_rules: 0` | Default for Excel's tables: every table asked how it's read (2026-10-05; the owner's design, not a round) | see the lever's section |

## Levers

### Table rules (`table_rules`)
- **Mechanism:** every table (a table of more body rows than the setting; 0, the default, every one) is read as a model says (`tablerules.py`; the owner's decision, the adapters plan's "Excel, in detail"): one query shows the columns analysed, sample rows, the text above the table and our opinion (a summary weighed by size, without a cut-off); the answer is templates applied to every row, rows read by themselves, or a summary (series, log, list). Excel's tables only, for now. `none` reads every table row by row, the baseline (`scripts/controlled.py run --rows`).
- **The owner (2026-10-05):** "I was under the impression we'd also ask how to translate rows to claims even for short tables"; "stats might be the more useful view even for tables of 30 items, it's difficult to set a hard boundary"; and, on going ahead, "I'm sure that we can also extract some levers to improve table handling experimentally. But let's see where we're at with our original vision of this."
- **Expected:** one query a table, not one a row, with claims as good. **Got** (not a round): see the adapters plan's progress; on the IEA workbook 68 queries against 510 row by row.
- **Binding (2026-10-05; the owner: "Yes, please work on improving binding a bit. You can run several experiments at that cost if needed"):** four variants of the rules prompt on the 26 controlled workbooks, by facts read right of 1,015 (row by row: 959, 10 misbound; the rules before: 943, 20 misbound):

  | Variant | Right | Misbound | Conditions kept |
  |---|---|---|---|
  | binding conventions (attribute, entity, conditions, columns as alternatives) | 933 | 36 | 198/198 |
  | conventions and a worked example ("Monthly cooling energy": entity the option, attribute written out, month a condition) | 954 | 15 | 219/219 |
  | conventions and a sentence the model writes first (what the values measure, what has them, under what) | 933 | 36 | 198/198 |
  | **all three (adopted)** | **959** | **10** | **224/224** |

  - The conventions alone made the model take the whole caption ("Figure 1. Monthly cooling energy, May to October") as the attribute; the example shows it written out.
  - The gains are in the chart studies' data tables; the other workbooks read alike under every variant. A one-series table ("Option 1, chilled beams (tons)") flips between its series name and "peak cooling load" as the attribute with small changes to the prompt: the binding is still fragile there.
  - By eye on the samples: the IEA overview's entity became the turbine, the tower's properties "tower | fore-aft inertia | at height 28 m", the synthetic commissioning table "Pump system | Flow at duty point | 118 L/s | Measured", the superseded sheet's swap fixed (its "superseded" mark lost).
  - Cost: $0.12.
- **Next:** the remaining candidate levers in *Ideas not built yet* (table handling); judge rules against rows in a round on real tables; Word, PowerPoint and PDF tables onto the same grid (the one table model).

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
- **Found since:**
  - Table values were taken for numbered items (fixed 2026-09-28).
  - Query checks (2026-09-28) found two more problems:
    - figure panel labels ("(a) Mass density", "(e) Chordwise offset") taken for numbered items, so charts parsed as tables get "Within: (e) ..."
    - a text chunk's "Section:" and "Within:" disagreeing (IEA-15: 3.2 Steady-State Performance against 3.1.1 Controller Methodology)
- **Next:** give the stem as the parent only, not a full path, where the path is long or not numbered; skip parenthesised letters inside figures.

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
- **Post-mortem (2026-09-30, Gemini reading r09b's samples):** "…" may join distant fragments (separate axis labels, far-apart table cells), so it can verify a misbound claim. That fits misbound rising.
  - **Next:** cap how far "…" may reach (no crossing a blank line or another block), or accept "|" joins only in tables and "…" only in prose.
  - The weak visual partition in that batch (0.44) was mostly merged-claim wording shown in visual units (a bug since fixed), which the analyst couldn't know.
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

## Ideas not built yet

Every lever idea gets a row here when it's raised (the owner, 2026-09-28), so none is forgotten.

| Idea | Raised by | Evidence |
|---|---|---|
| Leave page furniture (running headers, footers, page numbers) out of neighbouring text and text layers | Query checks, 2026-09-28 | Gemini flagged it in 5 of 8 sampled queries (DC manual, NREL, HabEx) |
| Cut text chunks at sentence ends, and text layers at word ends | Query checks, 2026-09-28 | "This focus is" ending a HabEx chunk; "defined in the W" ending an IEA-22 text layer |
| Send a one-row table's row without repeating it as its header | Query checks, 2026-09-28 | Ken manual "AC Rating ... 6.4 kW", and an NREL "table" made of equation debris |
| Drop text tasks that hold only a watermark or title-block boilerplate | Query checks, 2026-09-28 | A ken-cd text task holding only "PRODUCED BY AN AUTODESK STUDENT PRODUCT" |
| Recognise charts and diagrams parsed as tables (axis labels, legends, empty cells; a sequence diagram's lifelines taken for column rules) | Query checks, 2026-09-28; the table filter lever (r01b); [controlled documents](../plans/controlled-documents-2026-10-01.md), the procedure diagram (2026-10-04) | IEA-15 airfoil polar legends sent as tables; the table filter was inconclusive in r01b. The controlled sequence chart's labels were cut at its lifelines into cells: of the table reader's 7 claims, 2 hallucinated ("5\|72 s" read as 72 s), 2 misread (step numbers as values), 1 loose |
| Render every image at gemma-4's budget size (about 645,000 px, sides in multiples of 48): 768 × 768 tiles, 1584 × 396 for 4:1 bands | [How gemma-4 sees images](../research/gemma4-images-2026-09-30.md) | Bands rendered at 1000 px wide are enlarged to 1584 px: ~250,000 real pixels against ~590,000 for a tile Measured by the [eye tests](../research/eye-tests-2026-09-30.md): 4:1 bands read 1.3 × finer at 1584 × 384 than at 1000 × 250; tiles read the same at 768² as at 1000². |
| Smaller tiles on drawings (e.g. 280 points) | The same note | 1.5 × the linear detail at 2.25 × the tiles; small dimension text misread on sheets |
| Images before the text in each query | Google's guidance for gemma-4 | Not yet measured |
| Repeat the request after long inputs (a "sandwich"): short headers and the query again at the end. Variants: a brief reminder of the task and output format after the data; the whole prompt twice; headings repeated beside the data | The owner, 2026-09-30: gemma-4's long context may not hold equal quality at start and end | Models use the start and end of long inputs best ([Liu et al., "Lost in the Middle", TACL 2024](https://arxiv.org/abs/2307.03172)). Repeating the whole prompt won 47 of 70 tests with no losses for models not reasoning ([Leviathan et al., Google, 2025](https://arxiv.org/abs/2512.14982)); it lets early tokens attend to what comes later, and costs only input tokens. Our longest prompts are situating's (median 1,400 tokens, up to 14,000), the judges' v6 and future summaries; extraction prompts are short (median ~750 tokens), where repeating costs about $0.0001 a query. Whether gemma-4 reasons by default on DeepInfra is unchecked |
| Fewer rows per table query: cut dense tables into bands of about 8 rows (with the header repeated), since binding fails before reading does | [Eye tests](../research/eye-tests-2026-09-30.md), 2026-09-30 | gemma-4 got 3 of 8 cells right in 20-row tables at 1024² and 8 px, though it reads 96% of items at that size; 19 of 20 misbound values were from the same row or column |
| Ask for arrow direction explicitly (which end has the head) in flow diagrams | Eye tests, 2026-09-30 | gemma-4's only arrow errors were reversals: 15 of 118 |
| A model per task: Mistral-Small-3.2 for tables | Eye tests, 2026-09-30; the owner's model discovery idea (plans index) | Tables: 0.81 against gemma-4's 0.58; arrows and pairs worse. Needs a round on real tables |
| Repair table structure before extraction: merge a row with an empty first cell into the row above (wrapped cells), keep header cells' whole text, and find section header rows inside a table (filled or bold rows, rows repeating the column labels), sending them as each row's context (folded into [one table model](../plans/one-table-model-2026-09-30.md)) | [Spot check sc01](spotcheck-sc01-2026-09-30.md), item 1 (the owner: "the table parser not handling what is clearly two tables aligned into one, separated by a header layer") | HabEx p4: the spectrometers' rows sent under the cameras' header; "Detector / CCD201" and "Spectrometer resolution" split into rows |
| Send tables in bands of rows (about 8) with the full header block and any section header, instead of one row per query (folded into [one table model](../plans/one-table-model-2026-09-30.md)) | Spot check sc01, item 1; [eye tests](../research/eye-tests-2026-09-30.md) | One row per query hides section rows; the eye test found gemma-4 misbinds in dense tables (20 rows), so not whole tables either |
| The table's image with its parsed text, so the model sees its structure (folded into [one table model](../plans/one-table-model-2026-09-30.md)) | Spot check sc01, item 1 | Borders, fills and wrapped cells show what the parsed text loses |
| Show the model the table clearly, with its hazards named, when it builds the table's rules (the row-to-claims mapping planned for spreadsheets); a step toward one table model for every source (plans index) (folded into [one table model](../plans/one-table-model-2026-09-30.md)) | The owner, sc01 item 1: "Perhaps we need clear visualization of tables when building rules in cases like this? Clear identification of hazards, too."; clarified: "that's based on our prior discussion of how to process tables, e.g. for CSV or .xlsx files. We ask a model how to turn table rows into claims, and we might look for exceptions to this" | PDF tables are read one row per query instead; parser faults (stacked tables, wrapped cells) were found only by a person reading the page |
| Entity against conditions in the instructions: conditions are the circumstances a value holds under (operating point, load case, location, time); an alternative being compared (a unit size, a design option) or a part of a component (a camera's detector) is named in the entity | The owner, sc01 item 2: "I wonder if this is a matter of instructions" | The conditions hint says "load, scenario, time, tolerances, scope"; "2 ton unit" and "across the four mission concepts" became conditions (items 1–3) |
| Captions of the page's figures and tables as context for its text | Spot check sc01, item 2 | The text's "baseline unit size" is named only in Figure 13's caption ("2.5 ton unit"), which the chart's own reader used. The reverse in [controlled documents](../plans/controlled-documents-2026-10-01.md) milestone 2b: with a table's hall named only in its caption, the table reader kept it for 0 of 8 room values ("Room 101"), the text and image readers for all |
| Repeat a table's header block in every tile or band that cuts the table, or leave tables to the table reader where it has them | [Controlled documents](../plans/controlled-documents-2026-10-01.md), milestone 2b | gemma-4's image reader gave 15–45 vague claims per schedule document under every knob ("V-319 \| column 2 value \| 4,274"), rows read without their header |
| Name a column by its whole header path under grouped headers ("Dynamics > Entry speed"), not by the group (folded into [one table model](../plans/one-table-model-2026-09-30.md)) | Controlled documents, milestone 2b; spot check sc01 ("Cameras > UV Channel" cut to "UV") | The table reader named only the group ("E3 \| Dynamics \| 57.5") for 14 values under grouped headers and 22 with every knob on, and never on the other schedules |
| Leave a detected table's text out of the page's text chunks (the table reader reads it) | [Controlled documents](../plans/controlled-documents-2026-10-01.md), milestone 2a | On the coaster's schedules gemma-4's text reader misbound 18 values in the clean table and 10 under grouped headers (32 before tables were kept whole on one page), shifting columns in the linearised table text, while the table reader misbound none in the clean table |
| Leave a figure's text (a chart's values and tick labels) out of the page's text chunks; the image reader reads the chart | [Controlled documents](../plans/controlled-documents-2026-10-01.md), milestone 3a | On a vector bar chart, gemma-4's text reader paired 7 printed values with the wrong months and took a tick label for a value; the image reader read every bar right |
| Ask the image reader to read unlabelled bars against the axis, bar by bar, to the nearest half step, and to name series by their legend, not their colour | Controlled documents, milestone 3a; the [eye tests](../research/eye-tests-2026-09-30.md)' axis cards | In extraction, 9 of gemma-4's readings, of 8 of the 12 monthly bars, were off by more than a quarter step (up to 125 MWh), though another reading of each bar was right; it named series by colour on a scanned page. Asked bar by bar on the eye test's cards, it read 100% |
| Ask the image reader to read a figure's legend before its lines (naming each line's kind), to name each note's part from its leader, and to treat only what's inside an outline as part of it | [Controlled documents](../plans/controlled-documents-2026-10-01.md), milestone 3b | On schematics whose link kinds were told only by line style, gemma-4 mostly wrote "connected to" (11 relations implied, not stated); with leader labels it attached notes to neighbouring parts ("EMCCD | plane | pupil plane"; 11 wrong relations on the UV channel, with outline errors); parts drawn outside an outline were credited to it |
| Turn rotated sheets upright before reading, and order a sheet's text as it's viewed | [Controlled documents](../plans/controlled-documents-2026-10-01.md), milestone 3c | On a floor plan stored rotated 90°, gemma-4 read every value, but facts read right fell from 43 to 31 and misbound claims rose from 6 to 17; the text reader's went from none to 5–7 |
| In revisions mode, a change needs the same item: tell the comparison that two items of one kind (two track elements, two revisions' dates, two design options) aren't one item changed, and that an item only in the later revision is new, not its neighbour changed | [Controlled documents](../plans/controlled-documents-2026-10-01.md), milestone 4; built as the `align` lever (2026-10-02; [comparing revisions](../plans/revision-comparison-2026-10-02.md), milestone 2), and each difference left named by kind by the `explain_differences` lever (2026-10-03, milestone 4: two items of one kind are "not the same item") | Across six revision pairs, gemma-4 called 17 pairs of different items "different" as if one had changed: track elements against each other and the new helix against older ones, revision D's date against A, B and C's, and the two cooling options (sc01 item 2's alternatives trap). The prompt says corresponding claims describe the same object |
| Names that carry identity: ask readers to name a row by its tag and a dimension by what it measures, not by position ("blower 5", "dimension 2"); or have the comparison treat a positional name as naming nothing | Controlled documents, milestone 4; the comparison side built in the `align` lever (2026-10-02: names by position follow their values); identity at extraction is planned in [comparing revisions](../plans/revision-comparison-2026-10-02.md) | 59 of 120 "different" findings on the revision pairs came from positional names. Inserting a pump moved every blower down a row, so "blower 5" named B-402 in one revision and B-401 in the other (11); a floor plan's unlabelled dimensions were compared across widths and depths (48). Every real change was still found |
| Keep thousands separators as printed: ask the image reader to copy a number's digits and separators exactly, or check a reading with a decimal point against the text layer's number with a comma | [Controlled documents](../plans/controlled-documents-2026-10-01.md), the procedure diagram (2026-10-04) | On the raster sequence chart, all 5 values with a thousands separator were read with a decimal point ("13,097 kbit/s" as 13.097); the image reader made none on the vector page or in Word, where the text layer holds the label (the table reader, cutting labels into cells, made 1) |
| Word tables' heuristics as levers: the nested-table size written into its cell (`NESTED_INLINE_ROWS`, 6), how a small nested table is written ("Flow: 450 gpm; Head: 85 ft"), and the layout-table signals (one row or column; a heading or long cells without a header row; borders, not used yet) | [Multi-format adapters](../plans/multi-format-adapters-2026-09-23.md), "Merged and nested cells" (2026-10-04; the owner: "we'll get plenty of levers to explore here, and difficulty knobs to test them") | Built as constants first. The first layout rule took 3GPP's tables of companies' comments for layout (long cells, a pasted heading); a header row now keeps a table data |
| Read drawings made of Word shapes as drawings: their text boxes are read as text (2026-10-04), but not their arrangement (which box an arrow joins, what a group frames). Render DrawingML shapes to a picture for the image reader, or describe their geometry (boxes, connectors and their ends) as a schematic's relations | [Multi-format adapters](../plans/multi-format-adapters-2026-09-23.md), "Text boxes" | A Qualcomm RAN1 contribution draws its figures with shapes: 64 shapes without text remain unread, its labels read as separate lines; Ericsson's two grouped drawings likewise |
| Table handling (the owner, 2026-10-05: "we can also extract some levers to improve table handling experimentally"): our opinion's size grading (`FEW_ROWS` 20, `MANY_ROWS` 100) and its wording, or no opinion at all | Excel, every table asked, 2026-10-05 | The model summarised the IEA blade geometry (60 rows) it had read by rules when only long tables were asked |
| Table handling: an uncertainty template, so a value and its ± column ("118 ± 3") make one claim with its uncertainty, not two | The synthetic workbook's commissioning table, 2026-10-05 | Its key names the two columns composite; the rules made "measured value" and "measured tolerance" |
| Table handling: guidance on the entity (the table's subject or an item, not a parameter's name) and on document details (a revision line isn't a condition) | The synthetic workbook, 2026-10-05 | "Design flow \| Parameter \| 110 L/s"; every design basis row conditioned "Design Summary Rev C, 2026-08-14" |
| Table handling: leave bookkeeping columns (contact IDs, reservation times) out of rules, or prefer the list summary for registers | The RAN1 document list, 2026-10-05 | 30,177 claims by rules over every column, before the list summary was suggested |
| Table handling: the examples check (strict values and units, any row shown) and the second asking's wording | The controlled workbooks, 2026-10-05 | A unit outside brackets ("Vertical g") failed twice before the problem said how to mend it |
| Table handling: an uncalculated formula as a claim's value ("[formula =C6+C7, not calculated]") or only as a coverage note | The synthetic workbook, 2026-10-05 | The rules made it a claim with unit m |
| A higher image budget (560 or 1120 tokens) | The same note | Document reading improves markedly at 1120 in Google's report. DeepInfra ignores the setting (measured), so this needs a host that sets it, e.g. the in-house deployment |

## Measurement notes (affect how to read the table)

- **A/A noise:** two readings of the same pages score about 0.5 ± 0.08 over 48 units (r01), so single units mean little.
- **Early stopping at 16–24 units inflates wins;** the combination rounds (r02, r04) at 40–48 units are more honest.
- **Before round 7,** units with more than 25 claims showed judges separately drawn samples, which added noise to visual units in every round. This was fixed in `5850dfd`.
- **Rubric v2 from round 7:** document administration is neutral; judges tag each side's problems and may leave remarks.
- **Free cost saving noticed in r05d's analysis:** the model kept reporting blank tiles. Built as `skip_empty` (see above).
