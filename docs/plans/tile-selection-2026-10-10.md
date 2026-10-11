# Tile selection for vision tasks

- **Status:** Active (2026-10-10). Written, and its design questions answered the same day (see [the end](#design-questions-answered-2026-10-10)). The owner, 2026-10-10: "Alright, please begin developing the plan."
- **The owner, 2026-10-08:** "We probably need a whole plan just to improve tile selection and find/create examples that lead to such perverse outcomes." Then, 2026-10-09: "I'm tempted to push on tile selection a bit".
- **The model choosing, the owner, 2026-10-10:** "send the vision model itself a small version of the image, perhaps one to three small sketches of heuristic tile selection (the most promising), and asking which tiling is the best, e.g. with labeled translucent overlays. The model cannot easily read the shrunk down page, but can probably identify areas of interest from a zoomed out view. We can also measure the quality of those answers by injecting some known-bad tiling test cases." Then: "one shrunk-down image without tiling, plus one per candidate with that candidate's tiling. We could also include a calibration step that tests if a model is any good at this sort of question, tuned with known-bad cuts and pseudo-random candidate ordering. Your variant seems useful, too, but could include a mixed or nonsense option for classifying bad tiles."
- **From:** the [trials review](../reviews/trials-2026-10-08.md), finding 5, and what the [bug plan](review-bugs-2026-10-09.md)'s item 6 left open.

## Scope

- **In:** which parts of a page are sent to the vision model, in what shapes, and how much they overlap. That is the first cut: tiles, bands, which tiles are kept. Also refinement's open questions: the second cut, made when a tile's answer is partial.
- **Out, with their own rows in the plans index:**
  - **How small text may get:** tile size and render size from a model's eye-test profile (*Vision profiles and adaptive slicing*). This plan keeps `tile_points` 420 and decides where the cuts go.
  - **Close-ups a model asks for while reading** (*Progressive disclosure*). Here the model chooses among tilings, labels regions, or asks for another of the candidate tilings; it never draws its own boxes.
  - **Tiles the model draws itself.** The owner, 2026-10-10: "Eventually, maybe, but that would require some difficult measurement and calibration so I wouldn't be confident in the quality."
  - **Figure detection and the table reader's regions.** They're inputs here: a figure split by a tile is a measure, and figure tasks stay as they are.
- **Formats:** PDF pages and images. Word and deck pictures go through the same page code (`pictures.py`), so they follow.

## Where things stand

- **A page's image tasks** (`Platform.visual_regions`, `levers.py`):
  1. **Tiles:**
     - Pages up to 1.6 × 420 = 672 pt wide get full-width bands, cut at whitespace (`Tiling`, `segmentation.bands`). Bands no graphic touches are skipped, since the text tasks read them.
     - Wider pages get an overlapping grid of 420 pt tiles, 18% overlap, each grown to whole lines by at most 25% per side (`GrowTiles`).
     - A drawing sheet can be cut into its details first (`SheetDetails`, parked).
  2. **Kept tiles:** blank tiles are dropped (`SkipEmpty`); text-only grid tiles are kept.
  3. **Figures** are read whole besides the tiles (`FigureTasks`), unless one tile holds them or they fill the page.
  4. **The overview:** the whole page in one image.
- **What counts as a graphic** (`segmentation._graphics`): any drawing less than half the page's height, and any image whatever its size. A frame drawn as one path is left out; drawn as four lines it counts, as do rules, logos and side bars.
- **Refinement** (fixed 2026-10-09): a partial tile is halved at whitespace nearest the middle of what it holds, each half holding at least 25% (`segmentation.halves`, `LEAST_HALF`).
- **Measured in the trials review** (the samples' first 40 pages each, 803 pages):
  - bands: 559 pages, 822 tiles, no line cut sideways
  - grid: 244 pages, 6,582 tiles, 6,400 lines cut sideways, on 236 pages
  - 25 pages have an image over half the page, so every band there is sent
  - 217 of 822 bands are under 5% graphics
- **Model answers** (slices fixture): 401 of 964 tile answers (42%) hold no claims; 23 describe the image as fragments or a cropped border.
- **Related evidence:**
  - **The page tests** ([research](../research/page-tests-2026-10-01.md)):
    - From a 1024 px overview, told small text is there and given a labelled grid, gemma-4 found every small-text cluster.
    - The boxes it gave were precise.
    - Grid labels drawn on images were read as page text until the prompt said they aren't part of the page.
  - **The parked `tile_locator` lever:** a 384 px thumbnail with the tile outlined. No worse overall; it won on IEA and LCIT.
- **The measures used so far** (lines cut, graphics share) were scratch scripts. Only the refinement bench (`bench/refinement.py`, `scripts/refinement.py`) is committed.

## Rules against drift

- **Every change in behaviour is a lever, off by default** until measured, and listed in the [lever index](../reviews/levers.md). Defaults change only on measured evidence, judged by eye this early.
- **Refactors needed on the way are separate steps,** proven by replay ([0027](../decisions/0027-behaviour-changes-apart-from-refactors.md)). One is likely: the tilers become candidates the platform can rank.
- **New directions found on the way** become tentative rows in the plans index, not milestones here.
- **Each milestone ends with a commit after the full suite passes,** and reports what it spent.

## Milestones

### 1. Measures without the model

- **Product:** a module of pure geometry, `tiling.py`, with a measure of any tiling of a page. It belongs in the product, not the lab, because milestones 3 and 5 rank candidates at run time, and the *Runtime quality spot checks* row wants the same signals. Per tile and per page:
  - **lines cut** sideways and across, and words cut
  - **figures split:** a detected figure crossing a tile's edge, unless a figure task reads it whole
  - **text only:** a tile with no graphic after decoration is set aside (milestone 3), which only repeats the text tasks
  - **graphics share** of the tile, and decoration only
  - **blank**
  - **read twice:** lines held by more than one tile, and the area overlapped
  - **missed:** text or graphics in no tile and no figure task
  - **images sent,** and their tokens at the model's profile
- **Lab:** `bench/tiling.py` and `scripts/tiling.py`, which measure every page of a folder under any settings, and compare two settings.
- **Run on:**
  - the trials' 803 pages, which should reproduce the trials review's figures
  - every page of the samples: the header-join scan read 4,187
  - the controlled corpus
- **Measures with the model,** for the later milestones, from a run's store:
  - empty answers
  - complaints (`refinement.COMPLAINT`)
  - claims per tile and per dollar
  - against a controlled key: right, loose and misbound claims
- **Tests:** synthetic pages with known cuts.

### 2. A gallery and the knobs

- **A gallery of the worst pages:**
  - Found by milestone 1's measures across the samples, a few per failure: most lines cut, most text-only tiles, most read twice, decoration-heavy, figures split.
  - An offline page ([0019](../decisions/0019-offline-review-pages.md)) shows each page with its tiles outlined, under the current settings and any candidate, beside their measures.
  - It's how the owner first saw the problem (the assets folder) and how candidates are judged by eye. HabEx's page 4, LCIT's slide 27, the jury sheets and the old cut's wins (HabEx, calg) are in it from the start.
- **New controlled knobs,** each a cause of a failure:
  - a text-only slide (a PDF page 720 × 540)
  - a page slightly larger than Letter (690 pt wide)
  - a border frame drawn as one path, and as four lines
  - a full-page background image behind text
  - a scan inside a frame
  - Already there: `decorated` (side bars, logo, rule), `two-column`, `decorated+two-column`, `landscape`.
  - New knobs join `ALONE`, so the existing documents regenerate byte for byte.
- **Recorded once** under today's settings: the controlled corpus (about $0.02), as the baseline the candidates are measured against.

### 3. Heuristic candidates

Each is a lever, measured first by milestone 1's measures and the gallery, then with the model on the knobs, the gallery's pages and the controlled corpus.

- **Decoration set aside:** what doesn't count as a graphic, for keeping or skipping tiles.
  - graphics repeated in the same place across a document's pages (headers, footers, logos)
  - thin rules
  - frames, as one path or as lines along the page's edges
  - an image behind most of a page's text layer. A scan has no text layer, or a hidden one, so it still counts.
- **Text-only tiles skipped on every page,** as bands already are.
- **Bands on wide pages** whose bands fit the image budget (the eye tests: gemma-4 reads 4:1 bands 1.3 × finer rendered at 1584 × 384 than at 1000 × 250), instead of the grid.
- **Cuts by columns as well as rows** (XY-cut): blocks found by whitespace both ways, merged into tiles of up to the tile size.
- **Less overlap on grids:**
  - Overlap kept only where a cut crosses content.
  - Growing a tile limited where its neighbour already holds the line.
  - The landscape knob read the same lines in several tiles: 81 claims, 26 distinct readings.

### 4. Calibration: can a model judge tilings?

The owner's step, built before either model query below is trusted.

- **The cases:** pages with a known-good tiling among known-bad ones:
  - the old midline cut
  - a plain grid on a text page
  - tiles shifted to cut every line
  - a tile holding only decoration
  - a figure split in two
  - a tile of border alone
  - Built from the controlled corpus, the new knobs and synthetic pages, so every case has an exact key.
- **Candidate order pseudo-random,** seeded by the page's content and the case, so a run replays. Each case is asked in two orders, so position bias and consistency can be measured.
- **Scored:**
  - the known-good chosen
  - each position's share of choices against its expected share (position bias)
  - the same choice in both orders
  - for labelling (milestone 6), a confusion matrix by label: the known-bad tiles' "nonsense" and "mixed" above all
  - for extraction of a known-bad tile, whether the answer asks for another tiling (milestone 7)
- **The result is a profile per model,** like the eye test's. A model under its threshold doesn't get the levers below. The threshold is set by judgement first.
- **Reused by *Model discovery and per-task selection*** as a probe.
- **Cost:** about 1,300 input tokens per question (four images at about 260 tokens each, and the prompt), about $0.0002 with gemma-4. 400 cases in two orders cost about $0.16.

### 5. The model chooses a tiling

The owner's idea, as a lever.

- **When** (the owner, 2026-10-10: "I'd suggest two options. First, heuristics determine the best tiling is ambiguous. Second, models could feasibly request an alternative tiling as a refinement option."):
  - **Before reading, where the heuristics can't tell:** milestone 1's measures leave no candidate at least as good as the others on every measure, or the best are within a margin. Most report pages won't be asked.
  - **After reading, as a refinement option:** see milestone 7.
- **Candidates:** the best one to three heuristic tilings by milestone 1's measures. A known-bad candidate is never sent outside calibration.
- **The question:** one shrunk image of the page without tiles, then one per candidate with its tiles outlined and labelled.
  - Labels sit in the margin or at a tile's corner, and the prompt says they aren't part of the page (the page tests' lesson).
  - Candidate order is pseudo-random, as in calibration.
- **The answer:**
  - the chosen label
  - for each candidate, any problems from a closed list: cuts text, splits a figure, misses content, decoration only, repeats text
  - The problems are checked against milestone 1's measures, as a check on the answer and a diagnostic.
- **Fallback:** an invalid answer, a failed question or a failed calibration falls back to the heuristic default.
- **Recorded like every query** ([0009](../decisions/0009-content-addressed-queries.md)). The tile queries that follow depend on its answer, so a replay replays the choice first.

### 6. The model labels regions

Claude's variant, with the owner's addition: a mixed and a nonsense label.

- **The regions:** the chosen tiling's tiles, or the XY-cut blocks, numbered on the page (one clean image beside it).
- **The labels:**
  - text
  - table
  - chart
  - drawing
  - photo or scan
  - decoration
  - blank
  - mixed: several of these
  - nonsense: the owner, 2026-10-10: "A tiling that does not make sense, e.g. cut lines or part of a figure."
  - other: the owner: "another distinct label for items of interest that aren't in the expected type list", with a few words naming what it is
- **What follows by rule:**
  - text: skipped, since the text tasks read it
  - decoration and blank: skipped
  - nonsense: the tile is re-cut, or joined to its neighbour
  - mixed: kept, or cut along the parts
  - other: kept, its words noted with the tile; the words are collected across the samples, as candidates for new labels
  - the rest: kept
- **One answer serves every candidate tiling, and refinement.** The labels and the measures are checked against each other where the measures can see (text only, blank).
- **A lever of its own,** measured against milestone 5's choice and the heuristic best, with milestone 4's calibration covering it.

### 7. Refinement's open questions

Each is a lever, measured with the forced-refinement bench on the gallery's pages and the knobs:

- **Another tiling as a refinement option** (the owner, 2026-10-10, above).
  - A tile's answer that marks itself partial may ask for its halves, as now, or for the page under another tiling. The other tiling is the next candidate, or milestone 5's question among the rest.
  - **Claims from both tilings are kept.** The owner: "It isn't necessarily a problem to combine claims from two different tilings of the same page." The same claim from both is one piece of evidence with two occurrences already ([how it works](../how-it-works.md)).
  - **Measured:**
    - claims both tilings found, and those only one found
    - different values for one entity and attribute
    - how often the model asks
  - **The page tests' warning:** prompted only to zoom "as needed", neither model did, because a model doesn't know what it can't read. So calibration includes extraction of known-bad tiles, scored on whether the answer asks for another tiling.

- **A refined chart or drawing kept whole, zoomed into, or cut.** With the image budget fixed, kept whole means one more look at the same size, with a note of what was missed.
- **The least share of a half** (`LEAST_HALF`, 25%): the owner, 2026-10-09: "a tuning lever ... start with 25%".
- **Refinement guided by milestone 6's labels:** the cut follows the parts.
- **The old cut's wins** (HabEx's paragraphs, a calg table) are cases in the measure.

### 8. Measured with the model, and defaults

- **The candidates that hold up** on the knobs and the gallery are measured together:
  - the slices' development runs (re-recorded for each lever that becomes a default, about $0.02 each)
  - the controlled corpus
- **Compared with the current defaults:**
  - facts found right, loose and misbound claims
  - empty answers and complaints
  - lines cut and lines read twice
  - images sent, and claims per dollar
- **Defaults change by judgement** on that evidence, and through the rounds when they resume.
- **Cost** for milestones 2 to 8: a few dollars, mostly calibration and the gallery's pages read under each candidate. Anything over $5 is estimated for the owner first.

### 9. Closing

- A decision record for how tiles are chosen.
- The lever index brought current.
- What the measures found, in *how it works*.
- Leftovers moved to rows, as usual.

## Design questions, answered 2026-10-10

1. **When the model chooses.** The owner: "I'd suggest two options. First, heuristics determine the best tiling is ambiguous. Second, models could feasibly request an alternative tiling as a refinement option. It isn't necessarily a problem to combine claims from two different tilings of the same page." Milestones 5 and 7.
2. **The model proposing its own tiles.** The owner: "Eventually, maybe, but that would require some difficult measurement and calibration so I wouldn't be confident in the quality." Out of this plan (see Scope).
3. **"Nonsense".** The owner: "A tiling that does not make sense, e.g. cut lines or part of a figure. We could have another distinct label for items of interest that aren't in the expected type list, though." Milestone 6, with an "other" label.
