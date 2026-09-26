# Research, round 1: context, layout, cropping and resolution without a model

- **Date:** 2026-09-26
- **For:** [query improvement in rounds](../plans/query-improvement-2026-09-26.md), round 1
- **Prompted by:** the panel's blind judgments of s02's questions. 9 of 12 claim inputs were only partly enough; the most-marked gaps were surrounding text (68), another page (36), legend or key (20), table header (16), resolution (16), section heading (15) and caption (13). The owner's review also complained repeatedly of bad cropping.
- **Method:** literature and documentation, plus measurements on the five sample slices with PyMuPDF 1.28.2. The prototype scripts are in [round-01-prototypes/](round-01-prototypes/); they are research code, not part of the tool.

## Findings

### The model's image budget

- **Gemma 4 at about 280 image tokens sees at most about 645,000 pixels.** That's 2,520 patches of 16 px. It keeps the aspect ratio with sides in multiples of 48, so the largest square is 768 × 768.
- **Pixels per point = √(645,120 ÷ crop area in points²).**
- **What current crops give:**

  | Crop | px/pt | Smallest text |
  |---|---|---|
  | Letter-page overview | 1.03 | 7 pt → 7 px |
  | Drawing-sheet overview (2448 × 1584 pt) | 0.41 | 9.3 pt → 3.8 px: illegible |
  | Large detail viewport | 0.73–1.06 | 7–10 px |

- **We also render at 1,000 px, then the model resamples.** Rendering directly at the model's size avoids blurring twice.

Sources: [Gemma vision](https://ai.google.dev/gemma/docs/capabilities/vision), [Hugging Face Gemma 4](https://huggingface.co/docs/transformers/model_doc/gemma4).

### Surrounding context

- **A heading and list-stem stack gives each chunk its parents.**
  - Walk the document's lines in reading order, keeping a stack of numbered markers: `Contest 9.`, `9-2.`, `c.`, `(iii)`.
  - Headings are larger or bold lines.
  - On the rules slice this yields "Contest 9. Home Entertainment > 9-3. Dinner Party > k. Teams hosting dinner parties shall comply with the following > (iii)…", across page breaks.
  - Work on lines, not blocks: one PyMuPDF block can hold items a.–h.
- **Neighbouring paragraphs,** marked as context: the previous paragraph's last one or two sentences and the next's first. About 300–400 bytes each, following the chunk-plus-context pattern of [Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval).
- **A table's lead-in:**
  - its full caption (within 40 pt)
  - sentences mentioning its label on the same or previous page ("Table 5-1 summarizes the drivetrain properties…")
  - notes just below it

  All four real tables in the samples have one.
- **Repeated headers and footers:** a line whose text (digits masked) recurs at the same height on at least half the pages is margin text, and should be dropped from text groups.
- **Equations:** their text layer comes out garbled (one character per line). Send them as an image crop, with the following "where …" paragraph as context.

### Layout and region classification

- **`pymupdf_layout` is a machine-learning model,** a small graph network. It's dual-licensed AGPL or commercial. PyMuPDF's "Consider using pymupdf_layout" message is an advertisement.
- **Rotated pages:**
  - text and drawing boxes are unrotated, while `page.rect`, clips and `find_tables` are displayed
  - `get_text("blocks", sort=True)` sorts by unrotated position, so text groups on rotated sheets don't follow displayed reading order
- **Most "tables" aren't tables.** 70 of the 74 regions `find_tables` detects on the samples are chart gridlines, drawing-sheet frames or paragraphs in boxes. A filter keeps all 4 real tables and drops all 70 others:
  - at least half the cells filled
  - no more than 5% of words straddling cell edges
  - at least 2 rows, 2 columns and 6 words
  - under half the page
  - no more than 30% of cells longer than 80 characters

  It misses the borderless "Full points / Reduced points" box in the rules; tiles still cover it. Changing the table strategy doesn't help.
- **Columns:** all the samples are single-column. For multi-column documents, PyMuPDF's non-ML `column_boxes` utility applies.
- **Classic references:** XY-cut (Nagy & Seth 1984), whitespace analysis (Breuel 2002), Docstrum (O'Gorman 1993), and the comparison by Shafait et al. (2008). With a text layer, projection profiles of line, drawing and image boxes suffice.

### Cropping without cutting labels

- **Full-width bands cut at whitespace gutters.** Go down each report page and cut at the widest empty horizontal gap in the second half of each 400-pt band; fall back to a 15% overlap.
  - On the report slices this cut (tile, text line) pairs from 2,126 to 7.
  - It went from 168 images to 65.
  - It kept resolution equal or better (median 2.0–2.3 px/pt).
  - 27 of the 65 bands are text-only, already covered by text tasks, and can be skipped.
- **Grow crops to whole lines:** add any line a crop cuts, while the crop grows no more than 25% per side. On drawing sheets this cut the lines cut by tiles from 137 to 35 (calg) and 139 to 50 (dc), for 2–4% more area. It fixes cases like "2x4 CED|AR".
- **Legends:**
  - A swatch is a small drawing (6–40 pt wide, at most 12 pt high) with a short text line starting just to its right.
  - Entries stack at the same x.
  - A legend should never be split: expand the crop to include it.
  - This found every legend on the sample charts.
- **Drawing-sheet viewports:** detail titles are large spans like `B4` at the bottom-left of each detail (US National CAD Standard). A detail runs up to the next title above, and across to the widest gap before the next detail to its right.
  - On dc S-522 this isolated all 5 details (C1, C3, B1, B4, A6).
  - The title block is the repeated template column.

### Resolution

- **Size crops by font.** Take the crop's 5th-percentile font size f, weighted by characters, and require about 12 px per em. Then the crop may be at most 645,120·(f/12)² pt²:

  | f | Largest square side |
  |---|---|
  | 5.3 pt | 355 pt |
  | 7.4 pt | 495 pt |
  | 9.3 pt (drawing sheets) | 623 pt |
  | 12 pt | 803 pt |

  N = 12 px is a first guess, to be calibrated against the model.
- **Give image tasks the text layer's lines inside the crop** ("read the image; use this to spell labels"). Whole sheets have 800–1,500 characters of labels, about 250–400 tokens.

### Across pages

- **References can be resolved deterministically:** "see Section 9", "Table 7-1", equation "(7-1)", "Contest 8-3h". Add the target's heading and first sentence, or the table's caption and header; say "not in this document" when the target is outside the source.
- **Definitions:** `X (ABBR)`, "X is defined as", "where X is…". Add at most 3 matching the chunk.

## Hypotheses for round 1 (ranked)

1. **Table filter** will cut table-header complaints and nonsense rows on table tasks.
   - Why: 70 of 74 detected "tables" aren't tables.
   - Expected: fewer tokens and a large gain on drawing sheets and chart pages. *Built as `table_filter`.*
2. **Heading and list-stem stack** as context will cut "section heading" and part of "surrounding text" on text and table tasks.
   - Why: list items lose their parents today.
   - Cost: +20–60 tokens.
3. **Gutter-cut bands**, skipping text-only ones, will cut cropping, legend and resolution complaints on tile tasks.
   - Why: tiles cut 2,126 line pairs; bands cut 7.
   - Cost: fewer images.
4. **Table lead-in** (caption, mentioning sentences, notes) will cut "surrounding text" and "caption" on table-row tasks.
   - Cost: +40–120 tokens per row. *A simple version is built as `table_context`.*
5. **Drawing-sheet viewports with title-block context,** sub-tiled by the font rule, will cut resolution, cropping and context complaints on sheet tasks.
   - Cost: +30 tokens per crop; about the same image count.
6. **Text-layer transcript with each image** will cut resolution and legend complaints on tile, overview and figure tasks.
   - Cost: +100–400 tokens per image. *Built as `visual_text_layer`.*
7. **Neighbouring paragraphs** will cut "surrounding text" on text tasks.
   - Cost: +100–200 tokens; watch for claims taken from the context. *Built as `context_before` / `context_after`.*
8. **Cross-page references and definitions** will cut "something on another page" on text and table tasks.
   - Cost: +30–100 tokens, only where a reference exists.

Also cheap: grow crops to whole lines and legends; sort reading order by displayed position on rotated pages.
