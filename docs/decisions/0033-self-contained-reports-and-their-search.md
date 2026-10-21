# 0033. A report is one self-contained file, and the page and the command line search its claims alike

- **Status:** Accepted (2026-10-21)
- **Source:** [portable reports](../plans/portable-reports-2026-10-19.md), milestones 1 to 6; [search beyond the words typed](../plans/search-2026-10-20.md), milestones 1 to 5

## Context

`report.html` linked each crop into the store's `assets/` folder, so it worked only beside it, and wrote a claim's card again for every finding it was in. Its search kept the items holding what was typed as one string.

- **The owner (2026-10-19):** "I need a report that is easily migrated. The report is full of 'unrelated' claims, which is a weird way to present unrelated things." On the budget: "If you're looking for a heuristic guiding prioritization, consider providing a command-line option and a mode that provides some feedback about some items that will be cut under that budget."
- **On unrelated claims (2026-10-20):** "we shouldn't discard unrelated claims, but perhaps we should seek better ways to group them and understand them for a comparison."
- **On topics (2026-10-19),** from cameo_ingest: "find candidate cliques of unique words that split the datasets [...] roughly evenly. After finding these, there was a step to let an LLM model select heuristically between candidates based on what would better fit the human intuition, and name the divisions. [...] If LLMs timed out, we'd just use a heuristic choice."
- **On the reranker (2026-10-20):** "Let's enable the reranker if the user configures it, no default. We should make the threshold configurable, too, perhaps 1-10 corresponding to 0.01-0.10. It can be disabled by default in the configuration. Default 3?"
- **On search (2026-10-20):** "Broader search is good." Then: "I like all the ideas for search. So, lowest hanging fruit first, I guess."

What was found:
- **Crops are the cost, and few serve the findings a reader checks.** TS 38.300's real pair was a 14.2 MB page beside 16.3 MB of assets; its data, stored once, is 2.0 MB gzipped. Crops for the findings to check came to 0.4 to 1.3 MB in four reports, against 1.4 to 6.5 MB for every card.
- **Word rules can't sort unrelated pairs** from related ones. Told the task, Qwen3-Reranker-8B separated them far better than retrieval's word score on the turbines runs, as well on the drawings, and no better on the IEA report against its workbook.
- **A claim's mark shown to the judge changed every marked claim's query.**
- **A bare word searched file names too:** "mw" found all 711 of the turbines' claims (`nrel-5mw-p25-36.pdf`).
- **The product's unit table enters comparison prompts.**

## Decision

- **One file:**
  - `report.html` holds everything; nothing links to `assets/`.
  - Its parts are written in Python, each card once and what a claim says once, stored as JSON, gzipped and in base64, inside the page.
  - A short script inflates them with the browser's own `DecompressionStream` (no library; it works from a file) and draws findings in pages.
  - The same bytes for the same data: gzip without a time; WebP's encoder is deterministic.
- **Crops under a byte budget,** in order of value:
  - `--report-budget` (`report_budget`, 20 MB by default) on `compare` and `report`. Crops fill what the page without them leaves, its vectors and values included.
  - WebP at the model's resolution, or JPEG through PyMuPDF where Pillow isn't installed.
  - By what a claim is in: different or uncertain findings; complementary, possibly added or removed; equivalent, other unmatched and shared; unrelated. Within each, claims read from a chart, diagram or table, or whose quote wasn't found in the text, first; files take turns. A shared crop is paid for once.
  - A cut crop's card says where to look (file, page, task); the report lists the cut crops.
  - `report --dry-run` writes nothing, and says what the budget includes and cuts in each group and the budget each group needs.
  - `--split` writes `report-split/`: a file per pair of files within the budget, and an index.
- **Unrelated pairs leave the findings,** kept in `report.json` and on their claims. A Claims view lists every claim of both sources, filtered by topic, file, side and kind, each saying how it fared; topic coverage says what each side says by topic.
- **Topics,** shown as filters with counts:
  - Candidate ways, mechanical: words found on both sides that split the claims about evenly (by subject, by property, by subject coarser). Words of one side alone would make topics of the sources again (cameo_ingest's lesson).
  - The model chooses a way and names its topics (`topic_names`, a default since 2026-10-20; the owner: "Yes, turn `topic_names` on by default."). Without it, or when it fails, the most even way, labelled by its words.
- **Marks on crops are provenance:**
  - A claim's place on its crop is marked (`mark`), not cut tighter, so a crop stays one image and keeps its context.
  - A table claim read by rules shows its table's crop, its row marked; its own `image` stays empty, so `verify_visuals` doesn't send the table to the judge.
  - `mark` is kept from the judge.
- **The reranker** (`rerank`, proposals mode): on only where a reranker model is configured (`rerank_model`). `rerank_threshold` 1 to 10 in hundredths, 3 by default, `--rerank-threshold` overriding. Asked at the chat endpoint's `/rerank` unless `rerank_api` or `rerank_url` says otherwise.
- **Search, one language in two engines:**
  - Words in any order, each the start of a word; numbers whole; phrases, exclusions, `OR`; a card's fields (`entity:`, `value:`, `page:` and the rest); values across units (`>50kW`). The search is kept in the page's address.
  - The most relevant first: BM25 over the cards' fields, what a claim is about weighing most. The page builds its index after it opens, with no library.
  - A file's name is searched only with `file:`.
  - `semantic-pdf-diff search` searches stores' claims, with or without a report: a Python port of `search.js`, held to the page by the same test cases, run by both (`tests/test_search.py`).
  - **The search's unit table is its own** (`values.SEARCH_UNITS`), drawn from the product's, the scorer's and units only it knows; the product's and the scorer's are unchanged.
  - `search_names`, a default since 2026-10-20 (the owner: "Go ahead and make it a default."): the model groups the names both sources give one thing; a query naming one whole name finds the others' claims after its own, marked.
  - `embed`, on only where an embedding model is named (`embed_model`; `embed_dimensions` 256): the claims' vectors in the page, `near:ID`, `like:ID` blending meaning in, `meaning:"..."` from the command line. Measured best: Qwen3-Embedding-8B at 256 dimensions (`config help embed_model`).
- **The models' requests** (topics, other names, reranking, embedding) are recorded and replayed like any query.

## Consequences

- **A report is one file to move or send,** or a folder to zip with `--split`. TS 38.300's pair is one 10.1 MB file with every crop.
- **One inflation serves today:** at 10× TS 38.300 (133,090 claims) the data is 9.5 MB and the heap 285 MB, 322 MB with the search's index. Parts inflated on demand wait for larger reports (*Report parts inflated on demand*, Tentative, in the [plans index](../plans/README.md)).
- **Unrelated pairs aren't lost:** their claims stay in the Claims view and the `search` command.
- **The two engines are kept in step by hand,** a change to one made to the other; on two reports, 17 queries returned the same claims in the same order.
- **The search's units can't change a comparison.**
- **With a reranker,** pairs below the threshold go unjudged: on the slices' two proposals runs, no related finding lost at 0.02, 0.05 or 0.1.
- **The replay fixtures carry `topic_names`' and `search_names`' requests;** round 0 pins `search_names` off.
- **Not settled:**
  - A model panel's judgement of the topics' names and groups (judged by eye so far), and topics from each side's sections or alignment's items (designed, not built): rows in the [lever index](../reviews/levers.md)'s ideas.
  - More than two sources (the owner, 2026-10-19: "I agree that comparisons of more than two sources is premature."): [criteria-first comparison](../plans/n-way-comparison-2026-09-23.md)'s subject.
