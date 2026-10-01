# Page tests: slicing, shrinking and close-ups

- **Date:** 2026-09-30 to 2026-10-01
- **Asked by:** the owner.
  - "we should be looking at visual acuity within this sort of slicing vs. shrinking tradeoff frame"
  - "how good vision models are at asking for close-up views of a regions (and identifying those regions) when (a) prompted to do so as needed, and (b) we know when it's needed based on prior test results. Sort of an investigative test."
  - "ensure at least one such eye test has tiny illegible text across multiple cells in the range. Perhaps stick it on a four corners."
- **Code:** `src/semantic_pdf_diff/pagetest.py`; run with `scripts/page_test.py`.
- **Results:** `benchmarks/pagetest/results.json` and `report.html`. Answers are in `replay.zip`, and the report is rebuilt offline.
- **Spend:** $0.72 (gemma-4 $0.15 over 2,195 queries, Qwen3-VL $0.56 over 1,383). It includes $0.12 of Qwen answers lost in a crash, before folder fixtures kept their working copy beside the zip.
- **Follows:** the card [eye tests](eye-tests-2026-09-30.md), which measure what a model reads in an image of a given size.

## Method

- **Sheets:** synthetic pages at real sizes, with random codes at known positions and font sizes, checked against the text layer. Two seeds of each.

| Kind | Size | Text |
|---|---|---|
| letter | 612 × 792 pt | 40 items, 4–14 pt, scattered |
| archd | 2592 × 1728 pt (36 × 24 in) | 96 items, 4–14 pt, with line work and a title block |
| letter-detail, archd-detail | as above | Body text readable in an overview (10–14 pt; 24–48 pt on ARCH D), and 2–3 clusters of small text (4–5 pt; 5–8 pt) |
| letter-corner, archd-corner | as above | One small-text cluster centred where four cells of the overview's grid meet, one inside a single cell (close-ups only) |

- **Static plans:**
  - the whole page shrunk into one image, or tiles of 864 down to 144 points (the pipeline's own tiling)
  - each rendered at 768 or 1536 px on the long side
  - Qwen was given one seed and plans of up to 40 tiles, as it is slow at 1536 px.
- **Close-up runs:**
  - **From** an overview (1024 px), the model lists what it reads and asks for close-ups (768 px). Each close-up may ask for closer ones, two levels deep, at most 6 per image and 40 queries per run.
  - **Prompted** to zoom as needed (free), or told the page has text below its measured threshold, in pixels, at this scale (informed).
  - **Regions named** by boxes (0–1000 coordinates), by cells of a labelled red grid drawn on the image, or by cells and rectangles of cells (ranges).
- **Scored:**
  - recall per font size, and the smallest font read at 90% (interpolated on a monotone fit)
  - spurious items, queries, prompt tokens
  - for close-ups: whether the small text was inside a requested region, the share of first close-ups holding any, and the share of clusters found
  - every request recorded as given, with requests that gave no close-up and why

## Slicing against shrinking

| Plan | gemma-4: recall | gemma-4: smallest read | gemma-4: queries / tokens | Qwen3-VL: recall | Qwen3-VL: smallest read | Qwen3-VL: queries / tokens |
|---|---|---|---|---|---|---|
| **Letter page,** whole at 768 | 0.81 | 5.9 pt | 1 / 0.4k | 0.65 | 7.8 pt | 1 / 0.6k |
| whole at 1536 | 0.90 | 5.7 pt | 1 / 0.4k | **0.97** | 4.5 pt | 1 / 1.9k |
| 420-pt tiles at 768 | **1.00** | 4 pt | 6 / 2.4k | 0.95 | 5.0 pt | 6 / 4.2k |
| **ARCH D sheet,** whole at 1536 | 0.17 | – | 1 / 0.4k | 0.30 | – | 1 / 1.7k |
| 864-pt tiles at 1536 | 0.80 | 6.5 pt | 12 / 4.8k | **0.96** | 4.7 pt | 12 / 29k |
| 576-pt tiles at 1536 | 0.96 | 4.7 pt | 24 / 9.6k | 0.99 | 4 pt | 24 / 58k |
| 420-pt tiles at 768 (today's tiles) | 0.98 | 4.4 pt | 40 / 16k | 0.99 | 4 pt | 40 / 28k |
| 288-pt tiles at 768 | 1.00 | 4 pt | 88 / 35k | – | – | – |

"4 pt" is the smallest font on the sheets: everything was read.

- **Shrinking a whole ARCH D sheet reads almost nothing,** for either model.
- **A letter page shrinks well for Qwen** (97% in one query at 1536 px), and for gemma-4 down to about 6-point text.
- **gemma-4 needs tiles,** rendered at about its budget:
  - 420-point tiles read 4-point text on both page kinds; 576-point tiles read 5-point text with 40% fewer queries.
  - Rendering at 1536 rather than 768 costs gemma-4 nothing (the host shrinks it to the same tokens), and it reads a little better: a sharp image shrunk beats a small one enlarged.
- **Qwen trades queries for tokens.** It reads an ARCH D sheet in 12 tiles at 1536 px, against gemma-4's 40, but at 29k prompt tokens against 16k, and slowly.
- **Too much magnification breaks Qwen.**
  - With 144-point tiles at 1536 px (14-point capitals about 100 px tall), it read 33% of a letter page, breaking large text into pieces ("MLK-58" as "MLK", "C-1", "A", "G").
  - The eye test's new large-glyph cards put its ceiling between 32 px (read perfectly) and 48 px (not at all). The other five models read 64-px capitals.
  - gemma-4 is protected by its own budget: the host shrinks what we magnify.
- **Too fine a slicing also cuts large text.** On the ARCH D detail sheets, 288-point tiles held only 90% of the 48-point items whole, and recall fell to 0.94.

## The cards predict the pages

- **Prediction:** a profile from the card test (the smallest glyph read per 1000 px of side, at the nearest image size) predicts the smallest font a plan reads.
- **gemma-4 reads pages about 10% smaller than predicted** (calibration 0.90 from 16 plans): isolated items are easier than the cards' dense lines.
- **Qwen matches the prediction** (1.01, from 13 plans).
- **The planner** (`profiles.py`) picks the fewest tiles, then the smallest render, that read a page's smallest text without magnifying its largest past the model's ceiling. Checked against the measured plans:

| Sheet | gemma-4: planned | gemma-4: cheapest that read every size | Qwen3-VL: planned | Qwen3-VL: cheapest that read every size |
|---|---|---|---|---|
| letter | 420 pt (6 tiles) | 420 pt (6) | 288 pt at 768 (12) | 420 pt at 1536 (6) |
| archd | 420 pt (40) | 420 pt (40) | 576 pt at 1536 (24) | 576 pt at 1536 (24) |
| letter-detail | 420 pt (6) | 420 pt (6) | 288 pt at 768 (12) | 288 pt at 768 (12) |
| archd-detail | 420 pt (40) | 576 pt (24) | none | none |

- **The plan matches or is one step cautious** on every sheet, and every plan it chose read at least 97.5% of items.
- **"None" is the right answer** on the ARCH D detail sheets for Qwen: no single tiling reads both its 5-point clusters and its 48-point titles within Qwen's ceiling.
  - Reading such a page in two passes, one per band of text sizes, is the next step for the planner.
  - Cards at 40 px would narrow Qwen's ceiling.

## Close-ups

Results are averaged per sheet over two seeds of each kind. "Clusters" is the share of small-text clusters found by the first close-ups.

| Sheets | Variant | gemma-4: recall / queries / clusters | Qwen3-VL: recall / queries / clusters |
|---|---|---|---|
| archd-detail | free, boxes | 0.52 / 1.5 / 0.17 | 0.43 / 1 / 0 |
| archd-detail | informed, cells | 0.79 / 5 / **1.0** | 0.77 / 17.5 / **1.0** |
| archd-detail | static 576-pt tiles | 1.00 / 24 | 0.95 / 24 (at 768) |
| letter-detail | informed, cells | 0.97 / 5 / **1.0** | 0.88 / 4 / 0.75 |
| letter-corner | informed, boxes | 0.96 / 3 / **1.0** | 0.90 / 1 / 0 |
| archd-corner | informed, cells | 0.90 / 6.5 / **1.0** | 0.96 / 15.5 / **1.0** |

- **Prompted only to zoom "as needed", neither model does.**
  - gemma-4 asked in a handful of runs, Qwen in none.
  - Instead they list what they think they see. From an ARCH D overview, gemma-4 listed 30–55 items while reading 3–17% correctly, and its spurious items ran to 26–37 per sheet.
  - **A model doesn't know what it can't read.**
- **Told that small text is there, and given a labelled grid, both find it.**
  - gemma-4 found every cluster on every detail and corner sheet, in 5–6.5 queries. Qwen found most, and spent more queries going two levels deep.
  - With grid cells it always asks; with boxes it rarely answers.
- **Boxes, when given, are precise.**
  - On the corner sheets gemma-4 gave a single box holding the whole corner cluster twice.
  - On the letter corner sheets it read 96% of items in 3 queries.
- **Ranges went unused at the overview.**
  - Offered "B2:C3", gemma-4 never used one: 0 of 57 requests on the earlier sheets, none on the corner sheets.
  - Qwen used ranges only inside close-ups.
  - With tiny text across four cells, both named the cells around it one by one, which covered 75–100% of the corner cluster.
- **Nothing was dropped:** every request was a usable region.
- **Static tiling still reads more,** at more queries: 24 tiles read the ARCH D detail sheets fully, against gemma-4's 79% from 5 close-ups.
  - Close-ups pay where small text is localised on a large page, and its sizes are unknown (no text layer to plan from).
  - gemma-4 uses its second level of close-ups too little.
- **Grid labels drawn on images were read as page text** in the deepest close-ups, until those carried no grid and the prompt said the grid isn't part of the page.

## What this means

- **Plan per page from its text sizes:** the profile and planner (`profiles.py`), with the text layer giving font sizes, as a lever (`tiling: profile`) for the next round.
  - **For gemma-4,** about 420-point tiles where 4-point text appears and 576 points where the smallest is 5–6 points.
  - Whole-page reading only for letter pages with no text under about 6 points.
  - Render above its budget (1000 px is fine).
- **Two passes for pages with both tiny and huge text,** for a model with a magnification ceiling.
- **Close-ups as a fallback where there's no text layer** (scans, outlined text): an overview, told small text is present, with a labelled grid; gemma-4 finds the regions.
- **Model choice:** Qwen reads drawing sheets with far fewer tiles at full resolution, at more tokens and time, but must not be over-magnified (plans index: model discovery).

## Limits

- Clean synthetic pages: one font, no scans or noise, random codes rather than words.
- Two seeds per kind, and one for Qwen's static plans: single cells are noisy.
- One wording per close-up prompt.
