# Text cut by tiles: counted, then given whole and with its surroundings

- **Status:** Active (2026-10-31: milestone 2's 16:9 pages begun, the owner: "Next, try for the 16:9 tiling."); [milestone 1](#1-count-it-on-noisy-pages-and-on-the-owners) done 2026-10-28 (the owner: "Please proceed with report bookmarks and tiling counts with noisy pages."). [Design question](#design-questions) 1 answered (report pages); 2 and 3 open.
- **The owner, 2026-10-28, from trials:** "we're still clipping a lot vertically across text in ways that make the text useless for claims. I wonder if techniques like fish-eye lenses would help, or if we need to include multiple clips in a query with some overlap in these cases, or similar strategies. We have a lot more context than we're using."
- **The owner, answering design question 1 (2026-10-28):** "I'm getting most from ordinary report pages. Often with a border decoration, page numbers (and footnotes cut vertically, too), but not always, so I'm not sure whether that's the cause. It's as if our heuristics decided to zoom in, so now we just have three parts of a paragraph or bullet point (or multiple paragraphs) across three tiles, sliced vertically. The left part, middle part, right part. Basically useless, and it's unclear if the broken text is what our heuristics wanted to focus on at all (perhaps it's trying to focus on some small diagram in a corner? invisitext?). It might be useful to fog out parts of a tile that shouldn't receive model attention, then drop the tiles that would be mostly fog, or zoom in on the bits that aren't. We can probably create test cases that force zooming or that have light background decorations, complex border decorations, illuminated initials, and so on, i.e. test cases for tiling with more noise."
- **Earlier, 2026-10-14,** on samples too sensitive to share (the tentative row *PyMuPDF's layout analysis*, moved in here):
  - "Many of those are generic: \"Text is heavily clipped and contains no ngineering claims.\" for tile:p3:1, \"Text is clipped on the right side; No engineering claims found in the visible text.\" for tile:p3:0, \"The provided text is highly fragmented and contains no extractable engineering claims\" for tile:p4:5. [...] we'll focus on the current path and get back to slicing and tiling again at some point in the future."
- **Takes over** two tentative rows, kept whole below: [*Tile selection, further*](#moved-in-tile-selection-further) and [*PyMuPDF's layout analysis*](#moved-in-pymupdfs-layout-analysis).
- **Builds on:** [0029](../decisions/0029-tiles-chosen-by-measures.md) (tiles chosen by measures) and its measurements in [tilings](../research/tilings-2026-10-12.md).

## Why: where text is still cut

Checked in the code and the tilings note, 2026-10-28.

### Report pages: what the owner sees, and what was checked

- **The owner sees it on ordinary report pages** (the answer above): a paragraph, a bullet or several paragraphs in three tiles side by side, often on pages with a border decoration, page numbers and footnotes.
- **The tilings note found no sideways cuts there.** Report pages are cut in full-width bands: none of 3,607 development pages had a line cut sideways, and 1,280 lines were cut across. So the owner's pages differ from the samples in something the measures don't see.
- **Checked 2026-10-28 on 17 synthetic pages** (letter, A4, tabloid; no model calls), made by a scratch script that will seed milestone 1's noisy pages.
  - **Reproduced: a page without a text layer.**
    - A scan, or a page whose text is drawn as outlines, is cut in full-width bands.
    - A band answered partial is halved at the middle of its longer side (`segmentation._middle`), so the cut runs down every line in it: at 306 pt on a letter page, the halves sharing 24 pt.
    - With outlined text the page is also taken for a drawing sheet (2,292 drawings, no characters: `figures.is_sheet`), so tile choice isn't asked.
    - The same scan with an invisible text layer (OCR) is halved between lines.
  - **Not reproduced, with a text layer:**
    - **The pages:** a double-rule border, an ornate border, page numbers, 7 pt footnotes, a light diagonal watermark, a logo in a corner, a drop cap, invisible text over the page, all of these together, an A4 page and a tabloid page.
    - **First-pass tiles:** no line cut sideways; one cut across, under the watermark.
    - **Halves:** cut between lines.
  - **Why a tile holds paragraphs at all:**
    - Where text tasks read a page, a band holding only text isn't sent.
    - A tile holding paragraphs is one that also holds a graphic, such as the corner logo (sent with the paragraphs beside it), or a page without a text layer.
- **Reproduced 2026-10-28, at the owner's suggestion ("also try a PDF with text as image"): a scan written at its pixel size.**
  - **The case:** some scanners and image-to-PDF converters make each page as many points as the image has pixels. A letter page scanned at 100 dpi becomes 850 × 1100 pt, and at 150 dpi 1275 × 1650 pt. It looks like any report page on screen.
  - **What the defaults do:** past 672 pt wide there are no bands. Two sample report slices (Solar Decathlon rules, NREL 5 MW), scanned at 100 dpi and written so, get a grid of 9 tiles a page, 3 columns by 3 rows. Every paragraph and bullet is cut into a left, a middle and a right part, the owner's three slices. At 150 dpi it's 20 tiles, 4 columns by 5 rows.
  - **The measures don't see it.** Without a text layer they count no lines, so no cut looks worse than another; tile choice keeps the grid. With an OCR layer over the same scans they count 77 to 136 lines cut sideways a page.
  - **Nothing is gained:** a 420 pt tile drawn at 1,000 px enlarges each of the scan's pixels about 2.4 times, showing nothing a full-width band doesn't.
  - **Not it:** the same pages scanned at letter size (612 × 792 pt) get bands. Read with the model ($0.036), their 48 band tiles were answered complete, none halved and none saying its text was cut.
- **The owner's document, 2026-10-28:** "One document is 13.33 x 7.50 inches, as if for powerpoint presentations. The text is selectable, and highlights properly. But the selection cursor shows up sideways compared to normal. There is also a banner on the left side of each page that is written such that the text would be upright if the page was rotated 90 degrees. That text highlights in a sensible manner for the sideways cursor."
  - **Rebuilt (synthetic, no model):** a 16:9 page, 960 × 540 pt as displayed, stored portrait with its content turned and `/Rotate` 90 or 270 turning it upright, and a banner horizontal in the stored page, displayed on the left. A title, five bullets about 720 pt long and a note.
  - **Reproduced: the three slices.** Wider than 672 pt, the page gets no bands. Tile choice takes the snapped grid, 3 columns by 2 rows, cutting every bullet into a left, middle and right part: 6 tiles, 22 lines cut sideways.
    - XY-cut cuts 10, but in 13 tiles, so it doesn't beat the grid on every measure and isn't chosen.
    - The tiles hold only text, which the text tasks read whole anyway. On a letter page the bands holding only text aren't sent.
  - **Not the rotation:** the same page stored upright tiles alike (lines are placed as displayed: `pages.shown`), and the banner changes nothing.
  - **What would send no slices here** (measured without the model): bands up to 960 pt (`band_width` 2.3), or text-only tiles not sent (`skip_text_only`). Each sends this page no tile at all.
    - On 2026-10-12, `skip_text_only: except_sheets` saved 34 corpus tiles and cost 4 facts, on charts whose text went into a larger tile ([tilings](../research/tilings-2026-10-12.md), milestone 8).
    - Wide pages' bands were dropped for their lower detail (milestone 3 there).
  - **The corpus has no 16:9 page:** its slide is 720 × 540, where XY-cut's one tile wins. Milestone 2 adds one.
- **Still to confirm on the owner's documents:** their runs' tile paths (milestone 1). Grid or snapped tiles on portrait report pages, or a page size far beyond letter or A4 in a viewer's document properties, would mean this case; "halves, down the middle" would mean the halving case above.

### Wide pages and drawing sheets

- A page wider than 672 pt (1.6 tiles of 420 pt) gets grid, snapped or XY-cut tiles, and a drawing sheet always keeps the grid.
- A grid tile is grown by at most 25% a side to hold the lines it cuts, so long lines stay cut.
- Lines cut sideways under the defaults, the samples' development pages:

  | Pages | Lines cut sideways |
  |---|---|
  | Slides and landscape, 435 | 2,813 (7,092 before 0029) |
  | Drawings and posters, 663 | 16,996 (17,842 before) |
  | Report pages, 3,607 | none; band edges still cut 1,280 lines across |

### Elsewhere

- **Scans.** With no text layer the measures see no lines, so every cut is blind; a refined band is cut down its lines (above).
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
  - **Greying out:** tile choice's sketches already grey what no tile holds (`tilechoice.sketch`, `dimmed`). Tiles sent for reading are never greyed.
  - **Fish-eye or foveated rendering:** never proposed before.

## Milestones

### 1. Count it, on noisy pages and on the owner's

- **Tiles complaining of cut text, counted per kind of page:**
  - how they were answered (complete, partial, failed)
  - whether they hold claims
  - whether their page has a text layer
- **Each tile's path recorded:**
  - the cut it came from (bands, grid, snapped, XY-cut, another cut, halves)
  - its depth
  - whether it was halved without a text layer, down its middle
- **On the recorded runs:** the controlled corpus and the slices, from answers already recorded, at no cost. The lab's pattern gains "clip".
- **In the product:** the run's summary and the report's coverage say:
  - how many tiles complained of cut text
  - how many tiles each path gave

  The owner can then count both on documents that can't be shared. This is the first of the *Runtime quality spot checks* (tentative).
- **Pages with noise (the owner's test cases),** generated with keys as the controlled corpus is:
  - light background decorations: a watermark, a tinted panel, a background picture
  - border decorations, simple and complex, and a frame taken for a table
  - illuminated and drop initials
  - page numbers, running heads and footnotes
  - a small diagram or logo in a corner
  - invisible text (an OCR layer over a scan), and text drawn as outlines
  - small text, so the measures choose smaller tiles ("force zooming")

  Measured without the model first (`scripts/tiling.py`), then read against their keys, for cents.
- **The baseline every later milestone is measured against.**
- **Done 2026-10-28:**
  - **In the product** (`311dc03`): each image tile's coverage row records its path (`tiling`: the page's cut, halves and whether down the middle, the region again, or another cut; its depth; whether its page has a text layer). The report's coverage ledger shows each tile's path and counts them with the tiles that said their text was cut (`retiling.tile_lines`); a run logs the same lines as it ends.
  - **In the lab** (`b2dd2a0`):
    - `scripts/tiling.py complaints RUNS...` counts recorded runs' tiles the same way.
    - The lab's complaint pattern gains "clip".
  - **Nine noisy layouts** of the convention centre's design basis, keyed as the corpus is: `lcc-s1-watermark`, `-tinted`, `-ornate`, `-initials`, `-footnotes`, `-small-print`, `-scanned-ocr`, `-outlined`, and `-noisy` (the first five together).
    - Their answers are in the corpus's archive (the variant `noise-2026-10-28`).
    - They join `replay.zip` and `results.json` at the next refresh.
  - **Baseline, from answers already recorded (no cost):**

    | Runs | Tiles | Said their text was cut | Of them, no claims |
    |---|---|---|---|
    | The corpus's recorded runs (278) | 543 | 29 (5%) | 2 |
    | The slices' latest round (r09, baseline arm) | 972 | 37 (4%) | 25 |

    - **Slices by kind:** 36 of the 37 are on construction drawing sets (ken-cd 17, dc-cd 12, calg-cd 7), and 1 is on a report page (lcit-report).
    - **No paths in these counts:** the runs predate the paths, so they count complaints only.
  - **The noisy layouts read with the model** ($0.044), with the clean layout and the scanned frame for reference:
    - **Tiles:** 26, all bands. None was halved and none said its text was cut.
    - **Without a text layer:** 11 of the tiles, on the outlined layout and the two scans.
    - **Recall:** every layout scored 1.00 (23 of 23 facts right).
  - **What it says:**
    - The noise the owner listed doesn't cut text on its own. Neither do pages without a text layer, unless a band is answered partial and halved.
    - The slicing the owner sees on report pages isn't in our documents. Their counts will name its path: the run's last lines and the report's coverage ledger give each tile's path. "halves, down the middle, no text layer" would confirm the cause reproduced above; another path would point elsewhere.

### 2. Whole lines, and complaints acted on

Each item is a lever, judged against null arms on the controlled corpus ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)), report pages first.

- **First, the owner's 16:9 pages (960 × 540 pt)** (the owner, 2026-10-31: "Nice work. Next, try for the 16:9 tiling."):
  - A corpus layout of that size, with the owner's banner.
  - Two candidates against today's cut, read with the model and scored by the keys (a few cents):
    - bands on pages up to 960 pt wide, lower so their area stays 1.6 tiles (`band_width` 2.3)
    - text-only tiles not sent but on drawing sheets (`skip_text_only: except_sheets`)
  - The better made the default if it loses no facts on the corpus's charts and sheets.
  - **Tried 2026-10-31** ($1.10 in all, most of it one read of a long deck; `scripts/tiling.py`):
    - **Two corpus layouts** of the convention centre's design basis, 960 × 540 pt: `lcc-s1-widescreen`, upright, and `lcc-s1-widescreen-turned`, stored portrait with its content turned and `/Rotate 90`, a banner running up the left edge. Today's defaults cut them as the owner sees: snapped or grid tiles, six a page, 16 to 37 lines cut sideways a page.
    - **Without the model, the corpus** (191 pages): bands to 960 pt and text-only tiles not sent (except sheets) each leave the 16:9 pages no line cut sideways. But text-only tiles not sent changes 59 pages, tables' among them, where tile choice, counting fewer images, takes one larger XY-cut tile for two bands: the effect that lost 4 chart facts on 2026-10-12.
    - **So a narrower value, `skip_text_only: wide_pages`:** text-only tiles not sent only on pages too wide for bands (not drawing sheets). First applied before the choice, then after it (below).
    - **The corpus's wide pages read** (its five: 16:9 upright and turned, the 720-pt slide, landscape, the 690-pt page): every fact found under every arm (23 of 23); today's tiles 35, `wide_pages` 5 to 10; today's 16:9 tiles gave a misread and loose claims, none under `wide_pages`. Bands gave six misbound claims on the turned page.
    - **Two real 16:9 decks read** (no key: distinct values found, as the tilings note measured real pages; h2-amr-2023, cowe2024; 1,849 distinct values today):
      | Arm | Tiles | Distinct values | Numbers only today | Only the arm's |
      |---|---|---|---|---|
      | Today | 589 | 1,849 | | |
      | Bands to 960 pt | 216 | 1,633 | 166 | 86 |
      | `wide_pages`, before the choice | 362 | 1,740 | 102 | 37 |
      | `wide_pages`, after the choice | 435 | 1,795 | 32 | 0 |
    - **Where the arms lost values:** before the choice, 122 of the 128 claims lost were on pages whose cut changed (grid or snapped to fewer, larger XY-cut tiles). After it, the 32 are on six pages; on two of them (cowe pages 43 and 49) every claim the text task gave was rejected, its quotes not found in the text layer (a slide's table), and the tiles were all that read them.
    - **Built:** `skip_text_only: wide_pages`, after the choice (`levers.SkipTextOnly.sent_tiles`), off. Text-only 16:9 pages send no tiles; pages with charts keep their cut and send their tiles holding a graphic.
    - **Not made the default:** it loses no facts on the corpus, as this milestone's rule asks, but loses 32 of 1,849 values on real decks where text tasks failed. Asked of the owner (2026-10-31); a fallback would close it: a wide page's held-back tiles sent where its text tasks come back with no claims.
    - **Answered 2026-10-31** (the owner: "I think we should turn it on. We should also do the fallback. Order is up to you."): the fallback first, then `wide_pages` the default.
    - **The fallback, built 2026-10-31:** a wide page's tiles of text alone are held back (`Context.held_tiles`), and sent once the page's text tasks, their refinements too, end having kept no claim (`tasks.Watch`, counting the claims each task kept, a quote not found in the text not one). Each tile sent so says so on its coverage row (`tiling.held`).
      - **Measured** ($0.004; the same two decks and the corpus's five wide pages): the decks keep 1,828 of 1,849 distinct values (14 numbers lost, 0 gained; 32 without the fallback), with 535 tiles (589 today, 435 without it); the corpus's wide pages every fact. The 14 are on pages whose text gave claims but missed a table's (cowe page 69): the text tasks' gap, not the tiles'.
    - **The default since 2026-10-31,** with the fallback. The corpus's and the slices' recordings refreshed.
- **Then, tiles no finer than the page's own pixels:**
  - On a page that is one image (a scan), a tile's detail is capped at the image's: its side in points is at least what the image shows in `image_side` pixels.
  - So a scan written at its pixel size is cut as a page of its physical size would be: full-width bands on a report page.
  - **Measured** on the sample slices scanned at pixel size (100 and 150 dpi, with and without an OCR layer), and on the corpus's scans, against the grid they get now.

- **Whole lines in every tile's text layer:** each line the tile touches in full, as refined halves get them, with line breaks kept.
- **A tile that says its text is cut** is read again under another cut, as a partial one is, even when it's answered complete.
- **Halves of a tile without a text layer** cut between the image's own lines, not down the middle.
  - The lines are found as dark rows in the tile's horizontal projection.
  - Where none are found, the cut goes across the tile's shorter side, crossing at most a line, not every line.
  - This is the cause reproduced above.
- **Measured:**
  - the noisy pages, the controlled corpus's wide pages and sheets, against their keys
  - milestone 1's count
  - lines cut per tile, before and after
- **Cost:** the replays are re-recorded, estimated first.

### 3. Fog

- **The owner's idea:** "fog out parts of a tile that shouldn't receive model attention, then drop the tiles that would be mostly fog, or zoom in on the bits that aren't."
- **First fogged, greyed and lightened:**
  - decoration, as the decoration finder marks it (`segmentation.decoration`): rules, frames, margin bars, a picture behind the text
  - page furniture: running heads and page numbers (`Context.furniture`)
  - the parts of lines the tile cuts, whose words its text layer gives whole (milestone 2) or a neighbouring tile holds whole
- **Tiles mostly fog are dropped,** as blank and decoration-only tiles are now. The rest are cropped to what isn't fog, for more detail where it counts.
- **The prompt says what the fog is,** as the page tests taught for marks drawn on an image.
- **First, a page test:**
  - Does gemma-4 leave fogged text alone?
  - Does it complain of clipped text less?
- **Then a lever** on the noisy pages and the corpus, measured as above.

### 4. Several images in one query

- **The owner's "multiple clips in a query with some overlap":** a tile sent with the strips its cut lines run into, or with its neighbours, as further images.
- **First, a page test** on known pages, with the [page tests](../research/page-tests-2026-10-01.md)' harness, for cents:
  - Does gemma-4 join a line across two images?
  - Does it say which image a claim came from?
- **Then a lever,** on pages where milestone 1 finds lines cut. Its measures:
  - the controlled keys
  - the count
  - claims read twice: a value seen in two images must not become two claims

### 5. Fish-eye and foveated tiles

- **Foveated:** the tile at full detail, with its surroundings at reduced scale in a frame around it. The cut lines run on into the frame, readable or not, and their words come from the text layer.
- **Fish-eye:** a radial lens, detail falling off smoothly from the middle.
  - Text lines bend under it, so it's tried after the frame.
- **First, eye-test cards** ([eye tests](../research/eye-tests-2026-09-30.md)): random codes placed at the centre and in the margins, scored by size and place. They show where text stops being legible, for cents.
- **Then a lever** on wide pages and sheets, measured as above.

### 6. Sheets and scans

What 0029 left unsettled, with the rest of [*Tile selection, further*](#moved-in-tile-selection-further):

- **Drawing sheets:** XY-cut blocks no larger than a tile, in place of the grid (a lever row).
- **Scans:** the image's own lines (milestone 2's) used for the first cut too, so cuts avoid them where there's no text layer.
- **Text drawn as outlines** told apart from a drawing (rows of glyph-sized paths), so its page is read as a scan, not a sheet.

## Design questions

1. **Which pages:** answered 2026-10-28: ordinary report pages ([above](#report-pages-what-the-owner-sees-and-what-was-checked)). Milestone 1's noisy pages and tile paths measure them first, and milestone 2's levers are judged on report pages first.
2. **Fish-eye or foveated:** I'd try the foveated frame first: a radial lens bends lines, and the model reads straight text best. Does "fish-eye" mean something more specific to you?
3. **Whether to pull in [*Progressive disclosure*](README.md#tentative)** (the model asking for close-ups) once milestones 2 and 4 report, or keep it apart.
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
