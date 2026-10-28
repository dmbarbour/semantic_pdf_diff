# Text cut by tiles: counted, then given whole and with its surroundings

- **Status:** Planned (2026-10-28); [design questions](#design-questions) open.
- **The owner, 2026-10-28, from trials:** "we're still clipping a lot vertically across text in ways that make the text useless for claims. I wonder if techniques like fish-eye lenses would help, or if we need to include multiple clips in a query with some overlap in these cases, or similar strategies. We have a lot more context than we're using."
- **Earlier, 2026-10-14,** on samples too sensitive to share (the tentative row *PyMuPDF's layout analysis*, moved in here):
  - "Many of those are generic: \"Text is heavily clipped and contains no ngineering claims.\" for tile:p3:1, \"Text is clipped on the right side; No engineering claims found in the visible text.\" for tile:p3:0, \"The provided text is highly fragmented and contains no extractable engineering claims\" for tile:p4:5. [...] we'll focus on the current path and get back to slicing and tiling again at some point in the future."
- **Takes over** two tentative rows, kept whole below: [*Tile selection, further*](#moved-in-tile-selection-further) and [*PyMuPDF's layout analysis*](#moved-in-pymupdfs-layout-analysis).
- **Builds on:** [0029](../decisions/0029-tiles-chosen-by-measures.md) (tiles chosen by measures) and its measurements in [tilings](../research/tilings-2026-10-12.md).

## Why: where text is still cut

Checked in the code and the tilings note, 2026-10-28.

- **Wide pages and drawing sheets.** A page wider than 672 pt (1.6 tiles of 420 pt) gets grid, snapped or XY-cut tiles, and a drawing sheet always keeps the grid.
  - A grid tile is grown by at most 25% a side to hold the lines it cuts, so long lines stay cut.
  - Lines cut sideways under the defaults, the samples' development pages:

    | Pages | Lines cut sideways |
    |---|---|
    | Slides and landscape, 435 | 2,813 (7,092 before 0029) |
    | Drawings and posters, 663 | 16,996 (17,842 before) |
    | Report pages, 3,607 | none; band edges still cut 1,280 lines across |
- **Scans.** With no text layer the measures see no lines, so every cut is blind.
- **The text a tile is sent is cut too.**
  - A first-pass tile's text layer is clipped at the tile's edge, character by character (`get_textpage(clip=...)` in `visuals.py`). Checked 2026-10-28: a 12 pt line "ALL DIMENSIONS ARE TO FACE OF FINISH" in a region ending at 200 pt comes back as "ALL DIMENSIONS ARE TO FACE".
  - It's then joined into one run of words, its line breaks dropped, and cut to 1,500 characters (`visual_text_layer`).
  - Only a refined half is given whole lines.
- **Answers saying so aren't refined.**
  - Only a tile answered `partial` or `failed` is read again.
  - A tile answered complete, with no claims and "Text is heavily clipped" among its issues, is left as it is.
- **Nothing counts them.**
  - The *PyMuPDF* row asked for a count of tiles answered "clipped" or "fragmented" with no claims, and it was never taken.
  - The lab's complaint pattern (`bench/refinement.py`, `COMPLAINT`) lacks "clip", though the product's (`retiling.CUT_SAID`) has it.
- **"A lot more context than we're using":**
  - **What a tile's query holds:** one image, the headings it spans, a note, and its text layer.
  - **What fits:** gemma-4's window is 262,144 tokens. An image costs about 258 tokens on DeepInfra, whatever its size.
  - **More images are cheap; more pixels aren't.** Each image is shrunk to 768 px a side, so detail can't be raised, but a query can hold several images. Tile choice's calibration sent four in one question (about 1,300 input tokens).
- **What was tried, nearest to the owner's ideas:**
  - **The tile locator** (`tile_locator`): a page thumbnail with the tile outlined, sent as a second image. Parked: r07 0.58 (0.47–0.68), no worse, and the model never mentioned it.
  - **`complete_by_image`**: telling the model the layer is cut at its edges. Off; it lost facts.
  - **Neighbouring text for image tiles:** never built (`context_before`/`after` reach text tasks only).
  - **Fish-eye or foveated rendering:** never proposed before.

## Milestones

### 1. Count it, on our pages and on the owner's

- **Tiles complaining of cut text, counted per kind of page:**
  - how they were answered (complete, partial, failed)
  - whether they hold claims
  - whether their page has a text layer
- **On the recorded runs:** the controlled corpus and the slices, from answers already recorded, at no cost. The lab's pattern gains "clip".
- **In the product:** the run's summary, and the report's coverage, say how many tiles complained of cut text. The owner can then count it on documents that can't be shared.
  - This is the first of the *Runtime quality spot checks* (tentative).
- **The baseline every later milestone is measured against.**

### 2. Whole lines, and complaints acted on

Each item is a lever, judged against null arms on the controlled corpus ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)).

- **Whole lines in every tile's text layer:** each line the tile touches in full, as refined halves get them, with line breaks kept.
- **A tile that says its text is cut** is read again under another cut, as a partial one is, even when it's answered complete.
- **Measured:**
  - the controlled corpus's wide pages and sheets, against their keys
  - milestone 1's count
  - lines cut per tile, before and after
- **Cost:** the replays are re-recorded, estimated first.

### 3. Several images in one query

- **The owner's "multiple clips in a query with some overlap":** a tile sent with the strips its cut lines run into, or with its neighbours, as further images.
- **First, a page test:** does gemma-4 join a line across two images, and does it say which image a claim came from? This uses known pages and the [page tests](../research/page-tests-2026-10-01.md)' harness, for cents.
- **Then a lever,** on pages where milestone 1 finds lines cut. Its measures:
  - the controlled keys
  - the count
  - claims read twice: a value seen in two images must not become two claims

### 4. Fish-eye and foveated tiles

- **Foveated:** the tile at full detail, with its surroundings at reduced scale in a frame around it. The cut lines run on into the frame, readable or not, and their words come from the text layer.
- **Fish-eye:** a radial lens, detail falling off smoothly from the middle.
  - Text lines bend under it, so it's tried after the frame.
- **First, eye-test cards** ([eye tests](../research/eye-tests-2026-09-30.md)): random codes placed at the centre and in the margins, scored by size and place. They show where text stops being legible, for cents.
- **Then a lever** on wide pages and sheets, measured as above.

### 5. Sheets and scans

What 0029 left unsettled, with the rest of [*Tile selection, further*](#moved-in-tile-selection-further):

- **Drawing sheets:** XY-cut blocks no larger than a tile, in place of the grid (a lever row).
- **Scans:** text lines found from the image itself (dark rows in a horizontal projection), so cuts can avoid them where there's no text layer.

## Design questions

1. **Which pages do you see it on?** Wide pages and slides, drawing sheets, scans, or report pages?
   - Each has its own cause above.
   - Until milestone 1 can count it on your documents, your answer sets where milestone 2 is measured first.
2. **Fish-eye or foveated:** I'd try the foveated frame first: a radial lens bends lines, and the model reads straight text best. Does "fish-eye" mean something more specific to you?
3. **Whether to pull in [*Progressive disclosure*](README.md#tentative)** (the model asking for close-ups) once milestones 2 and 3 report, or keep it apart.
   - Its page test found gemma-4 finds small text when told it's there, but rarely asks for a close-up on its own.

## Moved in: *Tile selection, further*

The tentative row, moved whole (2026-10-28):

- **What [tile selection](README.md#retired) left open:**
  - Its measurements are in [tilings](../research/tilings-2026-10-12.md), its lever ideas in the [lever index](../reviews/levers.md).
  - **Calibration on drawing sheets and scans,** which have no known-good tiling by its rules.
  - **A lone page number left out of calibration's known-good tilings.** gemma-4's complaints about known-good tilings were mostly "decoration or blank" (38 of 46, dimmed). In 37 of those 38 asks the tiling had a tile holding one short line, the page number: page furniture, though the measures count it as text.
  - **A measure that weighs small text against fewer cuts.** XY-cut's larger tiles lose facts on sheets, which the small-text count doesn't see.
  - **The old cut's wins not won back:** HabEx p4's band halves find nothing.
  - **A chart and its text in one larger tile,** with `skip_text_only` on, losing two readings (lcc-enduse).
  - **Figures not held whole on report pages, rising with decoration** (105 → 176): tables the figure finder takes for figures.
  - **Real pages measured by distinct values only,** without a key.
- **Was waiting on:** real pages with keys, or more drawing sheets and scans in the controlled corpus.

## Moved in: *PyMuPDF's layout analysis*

The tentative row, moved whole (2026-10-28):

- **The owner, 2026-10-14:** "I keep getting a notice \"Consider using the pymupdf_layout package for a greatly improved page layout analysis\" message on the CLI with the current product. Might be something to look into later, especially given the number of complaints about slicing text that I'm still receiving."
- **The notice:**
  - PyMuPDF 1.28 prints it once per process when a page's text is read without its optional `pymupdf_layout` package.
  - `pymupdf.no_recommend_layout()` or `PYMUPDF_SUGGEST_LAYOUT_ANALYZER=0` silences it. It's silenced since 2026-10-21 (`progress.setup_logging`), which leaves the choice open.
- **To weigh:**
  - whether its layout analysis orders and groups text blocks better than our reading order (`pages.reading_blocks`, text spans and cuts) on the pages where people see text sliced
  - its licence and its dependencies
  - a lever choosing it, measured on the corpus and the slices
- **Measured for tables only** (2026-10-07; [decision 0024](../decisions/0024-pdf-table-structure.md)):
  - Its own table detection found 0.057 of the corpus's true cells.
  - Its union with line detection found 0.963, against the heuristics' 0.966.
  - It brings 261 MB of dependencies (onnxruntime and others).
- **The measure without the owner's samples:** the owner's words of the same day are quoted at the top. Image tasks whose issues say clipped or fragmented text and whose answer holds no claims, counted on the corpus and the slices (the reader's `issues`, stored per task). That's milestone 1.
- **Was waiting on:** the tiling work resumed, and a baseline count of tiles answered "clipped" or "fragmented" with no claims.
