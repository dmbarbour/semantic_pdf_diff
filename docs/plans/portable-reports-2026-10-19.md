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

1. **One file under a budget** (done 2026-10-19, 3e0f457): the payload, the script, crops by priority, `--report-budget`, `report --dry-run`, the report's own list of cut crops; tests, and a headless browser's check that a report opens and shows its findings, cards and crops.
   - The largest local report (TS 38.300, 6,808 findings): a 14.2 MB page beside 16.3 MB of assets became one 10.1 MB file with every crop (2.1 MB without them).
2. **Many files on each side** (done 2026-10-20). Two sources, each a folder or zip of many documents, which the pipeline compares today. The owner, on more than two sources: "I agree that comparisons of more than two sources is premature."
   - **How far one file went** (2026-10-19, before this milestone): the TS 38.300 report's data copied 4 and 10 times, timed in headless Chromium on a real clock (DevTools protocol):

     | Copies | Claims | Findings | Data without crops | Written in | Opened in | Heap | First search |
     |---|---|---|---|---|---|---|---|
     | 1× | 13,309 | 6,808 | 2.1 MB | 7 s | 1.1 s | 66 MB | 0.2 s |
     | 4× | 53,236 | 27,232 | 6.9 MB | 26 s | 2.0 s | 165 MB | — |
     | 10× | 133,090 | 68,080 | 16.4 MB | 48 s | 2.8 s | 369 MB (535 MB after a search) | 1.5 s |

     The budget ran out first: at 10×, the data alone left the crops 3.6 MB of 20. The heap came next. The owner's 660-page pair is about 1.5× by its page's size.
   - **A comparison to try it on:** the controlled corpus's 25 revision pairs as two folders (each pair's earlier PDF and its later one, under the pair's name): 50 files, 2,210 claims, 1,356 findings; $0.056, situating included.
   - **The pair cap** (aabd446; the owner: "That 1000 item cap seems arbitrary, it should be configurable at least."): `--max-pairs`, beside `--top-k`; the report's header and the run's last lines say how many candidate pairs went unjudged.
   - **Browsing by file** (628f0a0): with more than one pair of files, the files' difference is a table of pairs (findings by relation, those reaching another pair's files counted apart; claims without a counterpart; crops embedded), each row a button filtering the findings, and a file filter. In headless Chromium, the 25-pair report's first row showed 33 of 1,356 findings.
   - **Crops shared between files** (628f0a0): within each group, files take turns; the dry run says what each file got.
   - **Shared structure for identical claims** (2aabd95; the owner: "For version comparisons, or the 4x one file, I expect you could squeeze things down further via shared structure for subsets of identical claims. Might be a lever worth exploring.").
     - What a claim says (its statement and quote) is written once however many claims say it, and cards refer to it. Equivalent findings whose two claims say the same are folded, a checkbox showing them.
     - The TS 38.300 pair opens on 1,119 of its 6,808 findings (5,689 folded). The data at 1× and 10× includes the trims below (4× doesn't); the heap and drawing times were measured before them:

       | Copies | Data, before → after | Heap | Drawn in |
       |---|---|---|---|
       | 1× | 2.1 → 1.6 MB | 66 → 48 MB | 1.1 → 0.6 s |
       | 4× | 6.9 → 4.5 MB | 165 → 135 MB | 2.0 → 1.1 s |
       | 10× | 16.4 → 9.5 MB | 369 → 285 MB | 2.8 → 2.0 s |

       Most of the gain is in repeats farther apart than gzip's window, as the owner expected; side by side, gzip had found them already (about 14%).
   - **Less of what grows with files** (cc4f1ca): the run's metadata leaves out what the page shows elsewhere (groupings, sections, situating, files: 208 KB of TS 38.300's 1.4 MB was the groupings, gzipped), and a PDF box is printed to a tenth of a point. The 25-pair report's data: 292 → 204 KB.
   - **Split when one file can't hold it** (2263a97): `--split` writes `report-split/`, a file per pair of files (its findings, those reaching other pairs' files, its claims without a counterpart) within the budget, and an index. The 25 pairs: 25 parts and an index, 8.9 MB (crops of content several pairs share repeat; one file was 4.6 MB).
   - **Not done: parts inflated on demand.** At 10× the largest local report, the data is 9.5 MB and the heap 285 MB, so one inflation still serves; it waits for larger reports.
   - **Not the report, but limiting it:** proposals mode judges at most `max_pairs` candidates. With many files most go unjudged (the IEA report against its workbook left out 9,899); the reranker is the cheaper way.
3. **Topic browsing** (the owner, 2026-10-19: "the idea is to let users swiftly filter when the Search box is blank page syndrome").
   - **Built** (2026-10-20): topics by words (27034d2), shown as buttons with live counts filtering the findings; the `topic_names` lever (2dee355), off by default, with the model choosing among the ways and naming the topics.
   - **Measured** on five local reports (by subject, the words' choice): 76–96% of claims placed, evenness 0.92–0.98, 93–100% of topics holding both sources. The model ($0.0013 for five) chose "by subject" each time and named topics a reader would use ("Relay UE Operations", "Internal Blade Structure"); see the [lever index](../reviews/levers.md) row.
   - **A default** (2026-10-20, the owner: "Yes, turn `topic_names` on by default."): the replay fixtures re-recorded with its requests. A way needs two topics or more, so a comparison whose claims don't split asks nothing.
   - **Open:** a model panel's judgement of names and groups, if the owner wants more than eyes.
   - **The owner's approach,** from cameo_ingest: "find candidate cliques of unique words that split the datasets (requirements, in that case, claim cards in this one) roughly evenly. After finding these, there was a step to let an LLM model select heuristically between candidates based on what would better fit the human intuition, and name the divisions. [...] If LLMs timed out, we'd just use a heuristic choice."
   - **What cameo_ingest's code does** (`subjects.py`, `topics.py`, its `docs/design/subjects.md`):
     - The model proposes about three ways to split, each on a principle, and places items 30 to a request. The first way placing 95% is shown first.
     - Without the model, a split comes from Louvain communities of shared words and elements, merged down to about √(n/2) groups (2 to 15) and labelled by distinctive words.
     - Its lesson: topics are joined across models, never within one, or they come out as the models again.
   - **Here,** the cards of both sources:
     - **Candidates, mechanical:** sets of words found on both sides, in claims' entities, attributes and conditions, that split the cards about evenly into about √(n/2) groups. Also each side's sections, and alignment's items in revisions.
     - **The model** chooses among the candidates and names the groups, in a request or two a comparison: recorded and replayed like any query. Placing 13,000 cards 30 to a request would take about 450 requests, so cards are placed by their words.
     - **Without the model, or when it fails:** the most even candidate, labelled by its words.
     - **Shown when the search box is empty,** as topics with counts, each a filter.
   - **Measured** by the share of cards in a topic, how even the topics are, whether each holds both sources, and a model panel's judgement of the names and groups (as cameo_ingest's three judges did).
4. **More value per byte** (done 2026-10-20): crops for tables read by rules (rendered already, not attached to their claims; the owner: "small tables"); tighter crops where an image claim's quote is found in the page's text layer, its box marked on the tile.
   - **Marked, not cut:** a claim's place on its crop is marked (`mark` on the evidence: fractions of the crop, in its orientation), not cropped tighter, so the crop stays one image however many claims it holds and keeps its context. An image claim is marked where the text block quoting it is (the block that already placed it in its section); a table claim read by rules, its row.
   - **Table crops:** a rules task's coverage rows record the crop its rules were written from; a rules-read claim shows it, its row marked. The claim's own `image` stays empty, so `verify_visuals` doesn't send the table to the judge.
   - **Kept from the judge:** `mark` is provenance; shown to the judge it changed every marked claim's query (a strict replay of the 25 pairs missed 86 answers before it was excluded).
   - **Measured** on the 25-pair comparison, extracted again by replay ($0): 1,584 of 2,210 claims marked (every rules-read row; image claims whose quotes are in the text); 252 of 252 rules tasks with their crop; the report 4.4 → 5.5 MB with 66 table crops more (284 crops, all within the default budget).

## Proposed, awaiting the owner

Raised by the owner on 2026-10-19 (the first quote above). Each was offered with a recommendation:

- **Unrelated pairs out of the findings:** counted in the header, and listed on a claim that has no counterpart with what it was compared with.
- **Search** across claims and findings beyond today's text filter.
- **A reranker before the judge:** a lever, measured on proposals runs (the [lever index](../reviews/levers.md) row; [retrieval recall](retrieval-recall-2026-09-23.md) lists rerankers already).
- **More than two sources:** premature (the owner, 2026-10-19). It would belong to [criteria-first comparison](n-way-comparison-2026-09-23.md) and claim clustering: claims of every source grouped into topics, shown as a matrix of topics by sources.
