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

**Done without the model (2026-10-10).** The measures with the model come with milestone 2's baseline, their first use.
- **Built:**
  - `tiling.py` (`measure`, `measure_tile`)
  - `bench/tiling.py` (`run`, `summary`, `compare`, `worst`)
  - `scripts/tiling.py` (`measure`, `report`, `compare`)
  - `tests/test_tiling.py`, seven tests
- **The trials review reproduced exactly** (the first 40 pages of each sample PDF, 803 pages):
  - grid: 244 pages, 6,582 tiles, 6,400 lines cut sideways, on 236 pages
  - bands: 559 pages, 822 tiles, none cut sideways
- **Every page of the samples** (4,157 pages) and the controlled corpus (133 pages):

  | | Samples: bands | Samples: grid | Controlled: bands | Controlled: grid |
  |---|---|---|---|---|
  | Pages | 3,568 | 589 | 125 | 8 |
  | Tiles | 5,006 | 16,235 | 177 | 174 |
  | Lines cut sideways | 0 | 13,320 (on 567 pages) | 0 | 101 (on 6 pages) |
  | Lines cut across | 2,598 | 1,504 | 28 | 5 |
  | Words cut | 12,572 | 17,347 | 74 | 152 |
  | Text-only tiles | 0 | 725 | 0 | 44 |
  | Lines read twice | 4,046 | 53,985 | 70 | 537 |
  | Tiles under 5% graphics | 2,479 | 5,252 | 26 | 45 |
  | Figures not seen whole | 109 | 480 | 10 | 6 |

- **What they show:**
  - **Grid pages are 14% of the samples' pages but 76% of their tiles.** They hold every line cut sideways, and 93% of the lines read twice.
  - **Bands cut no line sideways, but 2,598 across.** Likely where a band's window holds no gap and the band falls back to an overlapping cut, not yet checked; the gallery will show them.
  - **No tile is blank** (`skip_empty` drops them), and none is decoration only, because decoration isn't told apart until milestone 3.
- **Caveats:**
  - **Figures not seen whole** include those the product leaves to the overview: a figure covering 90% of the page, such as a drawing sheet or a cover. The gallery will tell those apart.
  - **Graphics share** is measured on a 2-point raster, so a hairline counts as 2 points wide. A drawing with no height (a rule drawn as one line) meets no tile, as in `segmentation`.
- **Speed:** about 0.2 s a page, mostly PyMuPDF reading the text layer. The product's own segmentation reads a page's lines and graphics again (`bands`, `Tiling.tiles`) instead of taking the reader's: a behaviour-preserving fix for later (*Code health*).

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

### 1b. More wide pages, with a held-out set

**Done (2026-10-10).** The owner: "Look to the internet for a few more PDFs with grid pages. We can obtain more samples for metrics and reserve some as a test set to avoid overfitting. We can begin milestone 2 after we have more than 8 pages for the areas where our heuristics are failing."
- **A new sample set, `wide-pages`** (`scripts/samples.json`, optional, about 145 MB; fetched and verified by `fetch_samples.py`).
  - 31 PDFs, all U.S. government works or government-funded: NREL, NASA (NTRS), DOE, NIST, EIA, NPS, and two 2015 Solar Decathlon drawing sets.
  - Five categories: slide decks 4:3, slide decks 16:9, landscape text pages, construction drawings, conference posters.
- **Split before any comparison,** into `dev/` and `heldout/`:
  - **Families never straddle the two.** A family is one publisher's template (NREL's three decks; NIST's three guides) or one author's posters.
  - **The rule:** within each category, families sorted by the SHA-256 of their first file, every third from the first held out.
  - **`heldout/` is measured only** to check a change already chosen on `dev/`.
- **Measured** (no model; today's settings):

  | Category | Dev: files | Dev: grid pages | Dev: lines cut sideways | Held out: files | Held out: grid pages | Held out: lines cut sideways |
  |---|---|---|---|---|---|---|
  | Slide decks, 4:3 | 1 | 50 | 1,532 | 1 | 141 | 3,809 |
  | Slide decks, 16:9 | 4 | 264 | 3,133 | 2 | 61 | 1,687 |
  | Landscape text | 1 | 11 | 102 | 3 | 19 | 986 |
  | Drawings | 2 | 174 | 4,516 | 1 | 131 | 2,522 |
  | Posters | 10 | 10 | 2,331 | 6 | 6 | 1,708 |
  | **All** | 18 | 509 | 11,614 | 13 | 358 | 10,712 |

- **What the new pages show:**
  - **Grid pages almost always cut lines:** 800 of the 867 grid pages cut at least one line sideways.
  - **Decks drawn on a template have no text-only tiles:** NASA's 4:3 decks and DOE's hydrogen deck, 0 of 1,274 tiles. Their backgrounds count as graphics, which is cause 4 on slides.
  - **One poster has no text layer** (`poster-sic`, dev): it's read by vision alone.
  - **Posters are the densest:** 35 to 110 tiles each, and up to 1,089 lines read twice on one poster. One poster printed at landscape Letter (`poster-multisorb`) takes 6 tiles, so its text is tiny.
- **Not found:** pages slightly wider than Letter (680 to 712 points), as the jury sheets are. They're rare in published documents, so the controlled knob covers them.
- **Development keeps the existing samples' grid pages** (the 2013 Solar Decathlon drawings, 589 pages) beside `dev/`.

### 2. A gallery and the knobs

**Done (2026-10-10).** The owner: "Thanks. Please proceed with milestone 2."
- **Built:**
  - `bench/gallery.py`, run as `scripts/tiling.py gallery RUN --samples samples --out benchmarks/tiling/gallery --config LABEL[:NAME=VALUE;...]`:
    - each failure's worst development pages, one per document (a `heldout/` path is never picked), and the named cases
    - each page drawn under every configuration given, with its tiles outlined and numbered and its figure tasks dashed, beside its measures
    - the output (`benchmarks/tiling/`) stays local
  - `bench/tiling.answers(store, key)`: a run's image tasks by kind (tasks, empty answers, complaints, claims), and with a key, the tiles' claims scored. The milestone 1 measures with the model.
  - Two tests added to `tests/test_tiling.py`.
- **Six new knobs** in the controlled corpus (`corpus.py`):
  - `slide`
  - `wide-letter`
  - `frame`
  - `frame-lines`
  - `background`
  - `scanned-frame`
  - All are in `ALONE`, so the existing documents regenerated byte for byte.
- **The gallery** (36 pages, under a minute):
  - Counts favour large pages, so slides and landscape pages are also ranked by lines cut per line, among pages up to 1,000 points wide.
  - "Lines cut across" is ranked on band pages only, where it's a separate failure.
- **Seen by eye in the gallery:**
  - ~~**Drawing sheets drawn sideways without a rotation** (`sd15-stevens` p118).~~ **Withdrawn (2026-10-11):** the gallery's mistake, not the page's. The sheet is rotated by `/Rotate` 90, and the product reads and renders it upright; the gallery drew pages unrotated (`show_pdf_page`), under tiles in displayed coordinates. Fixed: the gallery draws the page as rendered. Grid tiles do cut that sheet's lines, as on other sheets.
  - **Band pages cut lines across in dense tables.** A table with no gap between rows (HabEx's target list, p403) makes a band fall back to an overlapping cut. The band's edge runs through a row, and five rows are read twice. The table reader reads those tables anyway.
  - **A landscape schedule chart** (the 2013 rules, p44): a figure task reads it whole, and six grid tiles overlapping 2.3 times read 952 lines twice besides.
  - **Slides:** six tiles on a 960 × 540 slide cut its headings and pictures. The template's banner and footer bar count as graphics.
  - **HabEx p4 today sends one band** (the boxed list), not every band. The trials' description was of refinement's halves.
- **The knobs read with the model** (recorded: $0.030; their row-by-row run, $0.001):

  | Knob | Tiles | Tile answers empty | Tile claims | Right | Loose | Misbound | Facts found right by tiles |
  |---|---|---|---|---|---|---|---|
  | clean | 1 | 0 | 8 | 8 | 0 | 0 | 8 of 23 |
  | slide | 12 | 2 | 49 | 26 | 1 | 11 | 22 of 23 |
  | wide-letter | 12 | 3 | 47 | 30 | 8 | 5 | 22 of 23 |
  | landscape (2026-10-09) | 12 | 1 | 65 | 34 | 17 | 1 | 23 of 23 |
  | background | 6 | 3 | 22 | 23 | 0 | 0 | 23 of 23 |
  | frame, frame-lines | 1 | 0 | 8 | 8 | 0 | 0 | 8 of 23 |
  | scanned-frame | 6 | 3 | 22 | 23 | 0 | 0 | 23 of 23 |

  - **Every knob's document finds all 23 facts:** the text reader 83% of them (landscape 100%), the table reader 35%, the overview all 23.
  - **The grid knobs** (slide, wide-letter, landscape) add loose and misbound claims from cut lines, and no facts. The slide's tiles give 11 misbound claims and the document's one hallucinated claim; the clean page gives 25 right claims and nothing else.
  - **Background:** six tiles where the clean page sends one, half of them empty. The document scores as the clean page does (23 facts, no loose or misbound claims), at five more image queries. That's the cost of cause 4.
  - **The frames change nothing today.** A one-path frame is left out as a frame, and lines with no height meet no tile. They stay as regression cases for decoration filters.
  - **The scanned frame is read by tiles alone,** as it should be: the page has no text layer.
- **Found on the way:** the row-by-row run of a deck (`wtp-datasheets-s1.pptx`) still held its reading from before decks' key-value tables (pptx/8). It caught up when recorded, and now matches the standard run.

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

**Done (2026-10-11).** The owner: "Please proceed with milestone 3." Five levers, all off by default; the lever index has a section on them. Spent $0.307 with the model.
- **Built:**
  - **Levers:**
    - `decoration` (`segmentation.decoration`, `Context.decoration`)
    - `skip_text_only`
    - `band_width` (on `tiling`)
    - `tile_cut`: `snapped` or `xycut` (`segmentation.snapped`, `segmentation.xy_cut`)
    - `render_area`
  - **Platform hooks** (each a no-op by default):
    - `cut_page`, the tiler's cut
    - `content_graphics`, what makes a tile worth sending
    - `render_side`
  - **The measures:**
    - Text-only tiles now count with decoration set aside, so every configuration's run finds decoration.
    - The lab adds each tile's detail: pixels per point as gemma-4 sees it, after the host shrinks the image to its budget.
  - **`scripts/tiling.py`:**
    - `measure --exclude heldout/`
    - `read`: documents read with the model under each configuration, recorded into a fixture of its own (`benchmarks/tiling/`), scored by their keys
  - **Tests:** six added to `tests/test_tiling.py`.
- **Before the candidates, two separate commits:**
  - **A behaviour-preserving step:** segmentation takes the reader's lines and graphics, and finds a page's figures once (the Code health item). The measures of all 5,063 sample pages came out identical.
  - **A gallery bug:** it drew rotated pages unrotated. That withdrew milestone 2's sideways-sheet finding and this milestone's sixth candidate, a tile turned upright.
- **Measured without the model,** on every development page of the samples (held-out pages left out):

  | Pages | Configuration | Tiles | Lines cut sideways | Lines cut across | Lines read twice | Text-only tiles | Detail, 10th percentile (px/pt) |
  |---|---|---|---|---|---|---|---|
  | Report (up to 672 pt wide; 3,607) | today | 5,058 | 0 | 2,603 | 4,059 | 2,602 | 1.72 |
  | | decoration | 2,450 | 0 | 1,776 | 2,858 | 0 | 1.63 |
  | Slides, landscape (672 to 1,000 pt; 435) | today | 1,688 | 7,092 | 390 | 12,782 | 510 | 1.67 |
  | | text-only skipped (with decoration) | 1,178 | 4,305 | 277 | 10,594 | 0 | 1.64 |
  | | wide bands (2.4, by area) | 531 | 0 | 495 | 728 | 0 | 1.51 |
  | | snapped | 1,662 | 5,800 | 300 | 6,830 | 529 | 1.89 |
  | | XY-cut | 1,504 | 768 | 91 | 1,818 | 826 | 1.52 |
  | | XY-cut, by area | 1,015 | 492 | 82 | 1,751 | 473 | 1.55 |
  | | combined | 542 | 490 | 75 | 1,751 | 0 | 1.54 |
  | Drawings, posters (over 1,000 pt; 663) | today | 21,838 | 17,842 | 1,973 | 59,679 | 6,363 | 1.76 |
  | | text-only skipped | 15,475 | 9,241 | 1,162 | 34,435 | 0 | 1.75 |
  | | snapped | 21,243 | 9,741 | 1,361 | 27,588 | 8,108 | 1.92 |
  | | XY-cut | 17,305 | 3,212 | 509 | 9,131 | 7,375 | 1.68 |
  | | XY-cut, by area | 14,133 | 2,635 | 509 | 8,752 | 5,446 | 1.75 |
  | | combined | 8,687 | 2,088 | 402 | 8,739 | 0 | 1.71 |

  - **Combined:** decoration, text-only tiles skipped, XY-cut, rendered by area.
  - **A configuration not shown for some pages** tiles them as the row above it: decoration doesn't change wide pages, and wide bands don't change drawings.
  - **Figures not seen whole on report pages:** 110 rise to 180 with decoration. Most are tables the figure finder calls figures, their fills taken as text panels (LUVOIR's tables), so the table reader reads them.
- **Read with the model:**
  - **The knobs** (one reading each; facts found right of 23 in every configuration):

    | Knob | today: images, misbound, loose | text-only skipped | wide bands | XY-cut, by area | combined |
    |---|---|---|---|---|---|
    | slide | 17, 10, 1 (and 1 hallucinated) | 5, 8, 0 | 5, 0, 0 | 7, 0, 0 | 5, 0, 0 |
    | wide-letter | 14, 4, 5 | 6, 4, 5 | 4, 0, 1 | 7, 0, 1 | 4, 0, 1 |
    | landscape | 14, 1, 17 | 6, 0, 16 | 4, 0, 0 (1 hallucinated) | 7, 0, 0 (1 hallucinated, 1 text) | 4, 0, 0 (1 hallucinated) |
    | background | 8, 0, 0 | 3, 0, 0 | 3, 0, 0 | 3, 0, 0 | 3, 0, 0 |
    | decorated | 6, 0, 0 | 3, 0, 0 | 3, 0, 0 | 3, 0, 0 | 3, 0, 0 |

  - **The controlled corpus** (89 documents):
    - Decoration: 11 tiles fewer, facts right 3,438 as before.
    - Text-only skipped: 73 tiles fewer, facts right 3,419. Every fact lost is on the six plan sheets (`lcc-plan`), 3 or 4 each.
    - Rendered by area (ten documents, one per family): facts right 372 → 366, loose 57 → 48, inexact 62 → 69. No gain on Letter pages.
  - **Six gallery pages** (no key: distinct numeric values found by every task together):

    | Page | today: values, images | XY-cut, by area: values (lost), images | combined: values (lost), images |
    |---|---|---|---|
    | h2-amr p8 (slide) | 7, 7 | 6 (1), 7 | 6 (1), 5 |
    | nesc-thermal p20 (text slide) | 0, 5 | 0, 3 | 0, 1 |
    | 2013 rules p44 (schedule) | 54, 13 | 53 (2), 4 | 53 (2), 4 |
    | poster-radiation | 4, 117 | 7 (1), 82 | 6 (2), 44 |
    | scical p7 (notes sheet) | 88, 37 | 63 (26), 21 | 62 (27), 10 |
    | dc p23 (drawing sheet) | 78, 37 | 60 (20), 24 | 50 (28), 3 |

- **What it shows:**
  - **On slides and landscape pages, XY-cut and skipping text-only tiles hold up.** Combined, they cut the tiles by two thirds (images by 43%), lose no fact on the knobs, and leave almost no misbound claims.
  - **Wide bands** cut no line on slides, but a slide's columns leave no full-width gap. The band then falls back to an overlapping cut through every column (h2-amr p8). XY-cut cuts at the columns.
  - **Decoration** halves the bands sent on report pages at no cost in facts.
  - **Drawing sheets are the exception.** Text-only tiles skipped lose facts there: the corpus's plan sheets, and both gallery sheets. A drawing's labels mean what they sit beside, and its text tasks come back partial (12 of 19 on dc p23). XY-cut's larger tiles also found fewer values there than the overlapping grid, even without skipping. One reading per page and no key, so not every lost value was right.
  - **Snapped** halves the lines read twice but keeps nearly every tile. Paragraphs that run the page's width leave its cuts nowhere to go.
- **Fixed by eye on the way:**
  - Furniture by place alone took a report appendix's picture strips (HabEx p429 to p441), so it now needs the same drawing or image.
  - A chart's lines hold their labels in their boxes (LUVOIR p203), so a text panel must be filled.
  - Underlines, masks behind a drawing's notes, and panels joined the decoration after the gallery showed them keeping text tiles.
  - XY-cut blocks fit by area, longer where rendered by area: a poster's text column, about 680 points wide, fell back to the grid.
- **Directions for milestone 8 (tweaks and partitions):**
  - **Partition:** skip text-only tiles everywhere but drawing sheets.
  - **Tweak:** on drawing sheets, XY-cut blocks no larger than a tile; a block with no gap cut into strips, not the grid.
  - **Tweak:** quotation bars beside text as decoration (HabEx p4 still sends a band).
  - **Wide bands:** dropped in favour of XY-cut.
  - **Rendered by area:** only with long tiles.
  - **Before any default:** the held-out pages measured, and the slices read.

Each is a lever, measured first by milestone 1's measures and the gallery, then with the model on the knobs, the gallery's pages and the controlled corpus.

- **Decoration set aside:** what doesn't count as a graphic, for keeping or skipping tiles.
  - graphics repeated in the same place across a document's pages (headers, footers, logos)
  - thin rules
  - frames, as one path or as lines along the page's edges
  - an image behind most of a page's text layer. A scan has no text layer, or a hidden one, so it still counts.
- **Text-only tiles skipped on every page,** as bands already are.
- **Bands on wide pages** whose bands fit the image budget (the eye tests: gemma-4 reads 4:1 bands 1.3 × finer rendered at 1584 × 384 than at 1000 × 250), instead of the grid.
- **Cuts by columns as well as rows** (XY-cut): blocks found by whitespace both ways, merged into tiles of up to the tile size.
- ~~**A tile turned upright where its text runs vertically.**~~ **Withdrawn (2026-10-11):** its cause was the gallery's mistake (milestone 2). Of 5,063 sample pages, 12 have 30% or more of their text running vertically as displayed, all mixed with horizontal text (schedule charts, vertical table headings). Kept as an idea in the [lever index](../reviews/levers.md).
- **Less overlap on grids:**
  - Overlap kept only where a cut crosses content.
  - Growing a tile limited where its neighbour already holds the line.
  - The landscape knob read the same lines in several tiles: 81 claims, 26 distinct readings.

### 4. Calibration: can a model judge tilings?

The owner's step, built before either model query below is trusted.

**Done for the choice (2026-10-11).** The owner: "Please proceed." The labelling and extraction scores come with milestones 6 and 7, whose questions they test. Spent $0.460 with the model.
- **Built:**
  - **The question** (`tilechoice.py`, in the product for milestone 5; no lever asks it yet):
    - one shrunk page, then one sketch per candidate: tiles outlined, washed and numbered beside their corner, and "Tiling A" in a strip above the page
    - the prompt says the marks aren't part of the page, and gives no example answer
    - the answer: the best letter, and each candidate's problems from a closed list: cuts text, splits a figure, misses content, decoration or blank, repeats text
  - **The cases** (`bench/calibration.py`), from the controlled corpus:
    - **Known-good:** XY-cut over the text and the graphics other than decoration, each detected figure kept as one block. It's accepted only where the measures find no line or word cut, every line and figure held whole, no graphic missed, and no tile of decoration or blank space alone.
    - **Known-good found:** 126 of 146 pages. None on the scans or the plan sheets, whose figure is larger than a tile.
    - **Known-bad, each kept only where the measures find its fault:**

      | Kind | What it is | Pages |
      |---|---|---|
      | midline | refinement's old cut | 126 |
      | grid | the plain grid | 126 |
      | shifted | edges between rows moved into a line | 31 |
      | decoration | a tile of decoration alone | 4 |
      | border | a tile of margin alone | 126 |
      | figure split | a figure cut through its middle | 93 |
      | missing | the tile holding most graphics or lines dropped | 123 |
      | overlap | tiles grown into their neighbours, cutting nothing, so lines are read twice | 38 |

      Overlap was added for the "repeats text" problem, which no listed case tested.
    - **Questions:** each pairs the known-good with two bad kinds; 371 questions in all.
    - **Order:** pseudo-random, seeded by the page's text. Each question is asked twice, every candidate moving one place on.
  - **The profile:** `benchmarks/calibration/results.json`, committed with its answers (`replay.zip`), as the eye test's is. `scripts/calibration.py run`, then `report` offline (`report.html`: the profiles, then every question's pictures, the wrong ones first).
  - **Two arms:**
    - **outlined:** tiles outlined only
    - **dimmed:** also greys out what no tile holds. Added after the first arm's misses.
  - **Tests:** `tests/test_calibration.py`, 8 tests (a simulated judge scores full marks; one always taking the first shows its bias).
- **gemma-4, by arm** (742 asks each):

  | | Outlined | Dimmed |
  |---|---|---|
  | known-good chosen | 90.2% | 95.1% |
  | the same tiling in both orders | 86.8% | 91.4% |
  | the known-good chosen in both orders | 83.6% | 90.8% |
  | known-good tilings given a problem | 12.1% | 6.1% |
  | invalid answers | 0 | 0 |
  | choices by position (A, B, C; the known-good at 33%, 35%, 32%) | 33%, 36%, 31% | 35%, 35%, 31% |

- **Each bad kind chosen over the known-good, and its own fault named** (dimmed arm):

  | Kind | Asks | Chosen | Fault named |
  |---|---|---|---|
  | missing | 270 | 4.4% (outlined: 20.4%) | 69% |
  | overlap | 84 | 6.0% | 1% |
  | midline | 282 | 3.5% | 72% |
  | border | 284 | 1.8% | 97% |
  | shifted | 62 | 1.6% | 94% |
  | figure split | 214 | 1.4% | 52% |
  | grid | 278 | 0% | 92% |
  | decoration | 10 | 0% | 100% |

- **What it shows:**
  - **gemma-4 judges stark tilings well, with no position bias to speak of.**
  - **Outlines alone hide what a tiling misses.** A tiling missing a page's table, keeping only a tile around the page number, looked like the page untouched: chosen over the known-good in both orders on several table pages. Greying out what no tile holds took "missing" from 20% to 4%. Milestone 5 asks with the dimmed sketches.
  - **The problems named are reliable for some faults only:** cut text, decoration and blank tiles (92 to 100%). Figure splits are named half the time; overlap almost never ("repeats text" 1%) though the overlapping tiling is rarely chosen. Milestone 5 checks only the reliable problems against the measures.
  - **Complaints about known-good tilings are mostly "decoration or blank"** (38 of 46 named, dimmed). In 37 of those 38 asks, the tiling has a tile holding one short line, the page number. That's a fair reading: a page number is page furniture, though the measures count it as text. A known-good tiling might leave a lone page number out.
- **Threshold, set by judgement:** the known-good chosen in 90% of asks, and the same tiling in both orders in 85% (`calibration.PASS`). gemma-4 passes under both arms.
- **What it doesn't show yet:**
  - **No drawing sheets or scans:** they have no known-good tiling by these rules.
  - **Stark faults only:** milestone 5's candidates are all heuristic tilings, much closer to each other. Before its lever is trusted, calibration adds near cases: a single line cut, a little overlap, a known-good against today's tiling where today's cuts a few lines.
  - **The corpus is synthetic,** its pages built from a few templates.

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

**Done (2026-10-12).** The owner: "Please proceed with milestone 5." The lever is built, off by default, and the rule it falls back on is measured with it. Spent $0.502 with the model, $0.223 of it re-reading the corpus's today before its recorded answers were found (`fixture-corpus.sqlite`).
- **Built, in three commits:**
  - **A refactor:** the tilers name their cuts.
    - `tiling_of`, a chained hook, names a page's cut: Tiling gives bands, TileCut its cut.
    - `cut_named` makes each cut; `tiles_for` makes the tiles.
    - `cut_page` is gone.
    - Proven unchanged on 5,492 regions of 168 pages under five configurations.
  - **Near cases in calibration**, before the lever is trusted (below).
  - **The lever** (`tile_choice: off, measures, model`; `tilechoice.choose`):
    - **Candidates:** bands where today gives them, the grid, snapped, XY-cut.
    - **Measures**, each fewer is better: lines cut, figures split, lines and graphics missed, tiles of decoration or blank alone, lines read twice, small text, images sent.
    - **Small text:** lines whose capitals no tile shows 7 px tall (gemma-4's eye-test threshold), at the tile's detail as the host shrinks it.
    - **Images sent:** counted after the keep rules (bands skip text-only bands).
    - **The rule:** a cut at least as good as the rest on every measure is taken, today's first among ties. Where there's none, today's is kept unless another beats it; then the first unbeaten cut that beats it is taken.
    - **`model`:** asks the calibrated question (dimmed) among the unbeaten cuts, up to three, in a seeded order. It's asked synchronously while the page is planned (`Context.ask`, the client's), so a replay replays the choice first.
    - **Recorded:** a row `vision:p<n>:tiling` with the cut chosen, and the reliable problems (cut text, decoration or blank) checked against the measures.
    - **Fallback:** a failed question or an answer naming none falls back to the rule.
  - **Tests:** `tests/test_tilechoice.py` (8, one a whole PDF job with a stub model); a near-case test in `test_calibration.py`. The detail measure moved from the lab into `tiling.py`.
- **Near cases** (gemma-4, dimmed, 239 questions in two orders, $0.113):

  | Against the known-good | Asks | Known-good chosen | Fault named |
  |---|---|---|---|
  | one edge moved into a line | 62 | 98% | 97% |
  | one tile grown three lines into the next | 50 | 82% | 22% |
  | today's tiling, where the measures find a fault | 114 | 86% | 31% |
  | the snapped grid, likewise | 252 | 100% | 90% |
  | all | 478 | 94.6% (same in both orders 90.0%) | |

  Today's tiling was never chosen where it cuts text (0 of 36). It was chosen 16 times of 78 where its bands split a detected figure, mostly a group of tables cut between two tables: a defensible cut, so a debatable key.
- **The rule over every development page** (4,705; `scripts/tiling.py measure --set tile_choice=measures`):

  | Pages | Asked if `model` | Cut chosen | Images | Lines cut | Lines read twice | Small text |
  |---|---|---|---|---|---|---|
  | Report (3,607) | 1,125 | bands 3,291, XY-cut 316 | 5,058 → 4,979 | 4,071 → 3,358 | 8,442 → 6,886 | 3,303 → 3,292 |
  | Slides and landscape (435) | 219 | grid 156, snapped 92, XY-cut 187 | 1,688 → 1,459 | 7,482 → 3,699 | 12,782 → 6,903 | 3,576 → 2,651 |
  | Drawings and posters (663) | 616 | grid 341, snapped 295, XY-cut 27 | 21,838 → 21,737 | 19,815 → 14,483 | 59,679 → 45,630 | 13,455 → 10,280 |

  No measure gets worse on any kind of page; figures split fall too (773 → 670 on report pages).
- **With the model** (one reading each):

  | The controlled corpus (89 documents) | Tiles | Facts right (of 3,582) | Misbound | Loose |
  |---|---|---|---|---|
  | today | 450 | 3,438 | 261 | 490 |
  | the rule (`measures`) | 408 | 3,439 | 236 | 426 |
  | the model (`model`; asked on 45 pages) | 334 | 3,415 | 189 | 385 |

  - **The rule:** loses no fact. The knobs' misbound claims go (17 → 0), and the plan sheets keep theirs (231).
  - **The model:** chose XY-cut on all six plan sheets: facts 231 → 207, misbound 79 → 23.
  - **The gallery's six pages** (distinct values against today's):
    - The rule changes the cut on four: scical p7 loses 20 and gains 12 (snapped). The poster (89 → 88) and rules p44 (56 → 59) keep about as many, the poster with 15 lost and 14 new. nesc-thermal p20 has no values either way.
    - The model chose XY-cut on scical p7 (27 lost, 6 new) and on the h2-amr slide (10 of 18 lost).
- **What it shows:**
  - **The rule alone holds up:** fewer tiles, cuts and repeats on every kind of page, and no fact lost on the corpus.
  - **Asked, gemma-4 judges what it's asked:** cuts and coverage. It picks the cleanest-looking cut, usually XY-cut with the fewest tiles. On drawing sheets those tiles are too large for small text, which the question never mentions and calibration never tested.
  - **The model would be asked often:** on 31% of report pages, half the slides and 93% of drawing sheets. Mostly these are trade-offs the measures can't settle, such as fewer cuts against smaller text.
  - **Four faults of the rule, found in earlier runs and fixed:**
    - Ties were asked.
    - Bands were compared before their text-only bands were skipped (492 report pages moved to XY-cut for fewer tiles, sending more).
    - A cut beating today's could lose to one that didn't.
    - Without a measure of detail, XY-cut won the drawing sheets.
- **Directions for milestone 8:**
  - **Tweak:** offer the model only cuts no worse than the rest on small text, or tell it larger tiles show less detail and calibrate that.
  - **Before any default:** the rule measured on the held-out pages, and the slices read.

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
