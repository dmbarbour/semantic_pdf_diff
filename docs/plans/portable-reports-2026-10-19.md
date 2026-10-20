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

5. **Unrelated pairs, a claims view and topic coverage** (the owner, 2026-10-20: "As a user of the report, it would be convenient to have an easily searchable database of claims even without the comparisons, so we shouldn't discard unrelated claims, but perhaps we should seek better ways to group them and understand them for a comparison."; then, on the proposal below: "This seems like a good start. Please proceed.").
   - **What unrelated pairs are** (2026-10-20, three local proposals reports): candidates from TF-IDF word overlap (no embedder), 74–87% of the pairs judged. Few share words in conditions alone (44 of 867 in turbines, 52 of 868 in drawings); most are the same property of another item ("height" of a base block and of the finished floor) or the same item's other property (tower steel's density and its Young's modulus).
   - **Word rules can't sort them:** a pair sharing words in both entity and attribute would keep 119 of turbines' 867 unrelated pairs, and also only 8 of its 32 related ones (drawings: 20 of 868, and 28 of 97), since two designs name things differently. That takes meaning: the reranker, or embeddings.
   - **Unrelated pairs leave the findings,** kept in `report.json` and on their claims.
   - **A claims view:** every claim of both sources, searchable and filtered by topic, file, side and kind, each saying how it fared: in findings, compared without a counterpart (with what it was compared with and why not), possibly added or removed, not compared, or shared.
   - **Topic coverage:** each topic's claims on each side, and how many are in findings: where the two documents overlap, and where one is silent.
   - **Built** (44cfac9): unrelated pairs out of the findings, the Claims view (`#claims` opens on it) and topic coverage. Turbines: 1,000 findings → 133, its 867 unrelated pairs on their 239 claims; by topic, the tower is NREL's (149 claims against IEA's 26), thickness IEA's (129 against 4).
   - **The reranker, measured** (2026-10-20, $0.095): DeepInfra's Qwen3-Reranker scored every judged pair of six recorded proposals runs (6,000 pairs), each claim's candidates in one request (the API scores its first query against every document).
     - **As a search engine's reranker** (claims as "entity — attribute [conditions]", no instruction), no model separated related from unrelated pairs better than TF-IDF's own score; the 4B and 8B were no better than the 0.6B, and the IEA report against its workbook was at chance.
     - **Told the task** (the instruction "Given a claim from one engineering design document, retrieve claims from another design that state the same property of the same kind of component, so that their values can be compared", claims as sentences: "The rated power of the rotor, for 10 m/s."), the 8B separated them far better on the turbines runs (0.92–0.94 against TF-IDF's 0.64–0.82, the chance a related pair outscores an unrelated one), as well on the drawings (0.89–0.95 against 0.93), and no better on the IEA pair (0.71 against 0.70).
     - **One threshold, 0.02:** every equivalent and different pair kept in all six runs; 26–64% of the unrelated pairs left unjudged in five (4% in the IEA pair, which loses 57 of its 86 complementary pairs: the same item's other property, which the instruction asks to leave out). About 39% of the 4,482 unrelated pairs, for some $0.006 a thousand pairs against the judge's $0.19.
   - **Built** (74c0dd2; the owner: "Yes, please."): the `rerank` lever, on DeepInfra's inference API or text-embeddings-inference's `/rerank`; its requests recorded and replayed like the judge's. On only where a reranker is configured, its threshold in hundredths (the owner, 2026-10-20: "Let's enable the reranker if the user configures it, no default. We should make the threshold configurable, too, perhaps 1-10 corresponding to 0.01-0.10. It can be disabled by default in the configuration. Default 3?"): `rerank_threshold` 1–10, 3 by default, `--rerank-threshold` overriding the environment or a `--config` file.
   - **End to end** (2026-10-20, the slices' two proposals runs from their archive, $0.12; 0.05 and 0.1 replayed for $0.0007):

     | Run | Arm | Pairs judged | Related (lost, gained) | Uncertain | Unrelated |
     |---|---|---|---|---|---|
     | turbines | defaults | 1,000 (932 left by the cap) | 16 | 106 | 878 |
     | turbines | reranker, 0.02 | 787 (none left) | 19 (0, +3) | 109 | 659 |
     | turbines | reranker, 0.05 | 626 | 19 (0, +3) | 105 | 502 |
     | turbines | reranker, 0.1 | 478 | 19 (0, +3) | 97 | 362 |
     | drawings | defaults | 1,000 (598 left by the cap) | 132 | 190 | 678 |
     | drawings | reranker, 0.02 | 1,000 (26 left) | 132 (0, 0) | 200 | 668 |
     | drawings | reranker, 0.05 | 876 | 132 (0, 0) | 197 | 547 |
     | drawings | reranker, 0.1 | 783 | 132 (0, 0) | 195 | 456 |

     No related finding was lost at any threshold; turbines, which the cap had cut, gained three. Offline, 0.1 lost related pairs in two runs (19% of an older turbines run's; the IEA pair's complementary ones); the default is the owner's 3 (0.03).

6. **Search** (done 2026-10-20; the owner, 2026-10-20: "Broader search is good.").
   - **Today:** the box keeps the items whose text holds what's typed as one string.
     - "feed pump" misses "pump, feed" and "the feed water pumps"; "75 kW" misses "75kW".
     - Items stay in their listed order however weakly they match.
     - A claim is also found by the words of the claims it was compared with (its "compared with" list).
   - **Words, not strings:**
     - Each word must appear, in any order, as the start of a word ("pump" finds "pumps"). Case and accents are ignored.
     - Numbers match whole: "75" doesn't find "750"; "1,000" is "1000", "15.00" is "15", "75kW" is "75 kW".
     - `"feed pump"` is a phrase, `-gearbox` excludes, `blade OR rotor` takes either.
   - **Fields:** a card's parts searched alone: `entity:`, `attribute:`, `value:` (with its unit), `conditions:`, `quote:`, `section:`, `file:`, `page:` (`page:12`, `page:10-20`). They're read off the card's markup, which report.py writes; nothing is added to the data.
   - **Most relevant first:**
     - With words, items are ordered by BM25 over the fields, weighted by what a claim is about: entity and attribute 3, value 2, conditions and section 1.5, quote and context 1, the rest 0.5.
     - A finding is scored by its two claims and its own text.
     - "As listed" is one click away.
   - **Claims like this one:** each card's button searches `like:ID`, the other source's claims by default. It's the reader's own retrieval, for a claim the comparison found no counterpart for.
     - Its words are what the claim is about (entity, attribute, conditions) and its value's words, numbers left out. Each weighs as its field does.
     - A claim is found when it scores at least 30% of the claim's own score: "UE — performs = resuming from RRC_INACTIVE" finds 189 claims, not the 1,021 that share "UE" or "performs".
   - **What each source says:** while searching, the count says how many of each source's claims match, and each view's button how many of its items do (topic coverage, for any words).
   - **Shown:** the matched words are marked in the cards.
   - **An address:** the view and the search are kept in the page's address (`#claims&q=feed%20pump`), so a search can be bookmarked, or sent with the file, and opens as it was.
   - **Built in the page:**
     - An index of the cards' words is built just after the page opens, in slices that keep it responsive; no library, and nothing added to the file.
     - A search then intersects a few lists.
   - **Measured** (2026-10-20) in headless Chromium on a real clock (DevTools protocol), on the largest local report and 10× it. Times are after the box's 0.2 s pause:

     | Report | Claims | Building the index | A search at once | Later searches | Heap |
     |---|---|---|---|---|---|
     | TS 38.300 | 13,309 | about 0.4 s of work, after opening | 0.44 s | 0.05–0.16 s | 28 MB opened, 41–59 MB searched |
     | 10× it | 133,090 | about 5 s of work | 5.0 s (the index finished first) | 0.13–0.37 s | 322 MB indexed (285 MB before) |

   - **Found, against the old search** (TS 38.300, claims; the old search's findings in brackets):

     | Search | Old | New |
     |---|---|---|
     | harq timer | 0 (0) | 24, 12 in each revision (13 findings) |
     | timer harq | 0 (0) | 24 |
     | rrc inactive | 6 (3): the documents write "RRC_INACTIVE" | 546 |
     | pdcch monitoring | 71 (39) | 78 |
     | monitoring pdcch | 8 (4) | 78 |
     | capability ue | 0 (0) | 365 |

     Ordered by relevance, the first claims found are those about the words: "harq timer" opens on SL HARQ RTT and retransmission timers.

## Proposed, awaiting the owner

Raised by the owner on 2026-10-19 (the first quote above). Each was offered with a recommendation:

- **More search** (2026-10-20, beyond milestone 6): the owner, on the four ideas: "I like all the ideas for search. So, lowest hanging fruit first, I guess." They're the [search](search-2026-10-20.md) plan's.
- **More than two sources:** premature (the owner, 2026-10-19). It would belong to [criteria-first comparison](n-way-comparison-2026-09-23.md) and claim clustering: claims of every source grouped into topics, shown as a matrix of topics by sources.
