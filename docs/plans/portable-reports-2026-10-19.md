# Portable reports: one file, crops chosen under a budget

- **Status:** Active (2026-10-19)
- **The owner (2026-10-19):** "I've been trying this out a bit and will be shifting gears to work on the HCI aspects for a while, i.e. the report. For example, right now the report is tied to its origin by image refs and such, but I need a report that is easily migrated. The report is full of 'unrelated' claims, which is a weird way to present unrelated things. We might need to look into use of rerankers to tighten the comparisons further? Might look into compressing the data for the report and having JavaScript unzip, or distribution with a zip folder, or similar. Topic-based browsing, search, presentation of reports, etc.."
- **Then, on the file format:** "Portable file format is where I'm looking first. The all-in-one HTML has the advantage of being portable, but we probably cannot afford tens of megabytes more on crops. I already have 21MB of text with crop links in a two-proposal comparison. Unless we can filter the crops based on where they'll provide the best value to a reader (e.g. figures and charts, small tables), I fear we'll swiftly blow past any reasonable budgets."
- **And on the budget:** "20MB or even a fair bit more is acceptable, but I'm hoping to compare a lot more than two files. If you're looking for a heuristic guiding prioritization, consider providing a command-line option and a mode that provides some feedback about some items that will be cut under that budget. I cannot provide the report, it's sensitive stuff, but I can say one PDF was 32MB and 561 pages, the other 18MB and 99 pages."

## Why

`report.html` links each crop into the store's `assets/` folder by a relative path, so it works only beside that folder. Measured on local reports (2026-10-19):

- **The page is mostly repetition.**
  - Each claim's card is written out again for every finding it's in. The TS 38.300 real pair's page is 14.2 MB for 6,808 findings, with 3,054 image references to 331 crops.
  - Its data, stored once, is 21 MB of JSON, or 2.0 MB gzipped and in base64. In proposals mode, 7,410 of the ten local reports' 10,000 findings are "unrelated".
- **Crops are the cost.**
  - The same report's crops are 15.9 MB of PNG. Only claims read from an image carry one (a tile, a figure, a page overview); claims from text and tables read by rules don't, their verified quote being the evidence.
  - Re-encoded as WebP at quality 60 they're 3 to 4 times smaller, at the resolution the model read them, with small text still legible. JPEG is about twice WebP's size.
- **Few crops serve the findings a reader checks.** Crops for claims in different, uncertain or complementary findings come to 0.4 to 1.3 MB (WebP at 800 px, in base64) in the four reports measured. Crops for every card come to 1.4 to 6.5 MB.

## Design

- **One file.**
  - `report.html` holds everything: no links to `assets/`.
  - The report's parts are written in Python as now (escaping, wording, tested), each claim's card once. They're stored as JSON, gzipped and in base64, inside the page.
  - A short script inflates the JSON with the browser's own `DecompressionStream` (no library; it works from a file). It then puts each finding's cards in place and renders findings in pages, so a report of tens of thousands of findings opens. The relation and kind filters and the search work as now.
  - Byte for byte the same for the same data (gzip without a time; WebP's encoder is deterministic).
- **Crops under a budget.**
  - The report file has a byte budget, 20 MB by default (`--report-budget`, on `compare` and `report`). Crops fill what the page without them leaves.
  - A crop is re-encoded as WebP at the model's resolution, or as JPEG through PyMuPDF where Pillow, an optional dependency, isn't installed.
  - Crops go in in order of value. First by what the claim is in:
    1. different or uncertain findings;
    2. complementary findings, and claims possibly added or removed;
    3. equivalent findings, other unmatched claims, and shared evidence;
    4. unrelated findings.

    Within each, claims read from a chart, diagram or table, or whose quote wasn't found in the text, come first, then the report's order.
  - A crop that doesn't fit is skipped, and smaller ones after it may still fit. A crop several claims share is paid for once, at its best claim's place.
  - A card whose crop was cut says so, with where it is (file, page, task), so the reader can look in the source. The report lists the cut crops in a folded section.
- **Feedback before writing.** `report --dry-run` writes nothing. It prints what the budget includes and cuts in each group, the budget that would include each group in full, and the first cut crops with their findings. `compare` says how many crops its report cut.

## Milestones

1. **One file under a budget:** the payload, the script, crops by priority, `--report-budget`, `report --dry-run`, the report's own list of cut crops; tests, and a headless browser's check that a report opens, filters and shows its crops.
2. **At scale:** the largest local reports opened and timed; a report of many files when comparisons take more than two (the owner: "I'm hoping to compare a lot more than two files"); the owner's 32 MB, 561-page and 18 MB, 99-page pair estimated from the measures.
3. **More value per byte:** crops for tables read by rules (rendered already, not attached to their claims; the owner: "small tables"); tighter crops where an image claim's quote is found in the page's text layer, its box marked on the tile.

## Proposed, awaiting the owner

Raised by the owner on 2026-10-19 (the first quote above). Each was offered with a recommendation, and none is answered yet:

- **Unrelated pairs out of the findings:** counted in the header, and listed on a claim that has no counterpart with what it was compared with.
- **Topic browsing:** by each document's sections, by the items claims are about, or by shared topics a model writes over both sources.
- **Search** across claims and findings beyond today's text filter.
- **A reranker before the judge:** a lever, measured on proposals runs (the [lever index](../reviews/levers.md) row; [retrieval recall](retrieval-recall-2026-09-23.md) lists rerankers already).
