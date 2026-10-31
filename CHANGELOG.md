# Changelog

Versions are `0.MINOR.PATCH`, raised at each checkpoint that changes the product, and tagged `vX.Y.Z` ([decision 0040](docs/decisions/0040-versions-raised-at-checkpoints.md)). The lab shares the product's version. Each entry says what a user would notice.

## 0.19.0 (2026-10-31)

- **The second pass (`second_pass`, still off) is scored on planted reports.** Pump station design reports, each written twice, planted and clean. The planted copy holds values said otherwise in another section, blank schedule cells, "TBD"s and references to a figure and a table it lacks; both copies hold values restated under another condition.
  - It finds 5 of 6 planted contradictions and calls nothing else a contradiction.
  - The gaps found by code (siblings, placeholders, references) are all found, and none in the clean copies.
- **Fewer false gaps from the second pass.** Its "likely missing" now asks only about the subject's own properties. A PDF without an outline no longer hands every subject the whole document's summary. On the planted reports, gaps that weren't planted fell from 27 to none.
- **Doubted claims are read again from their place** (with `second_pass`): each claim the second pass suspects misread, and both claims of each contradiction, are rendered closer from the PDF and asked again. Each card says what its place gives ("as read", "it gives 16D"), and so does the Inconsistencies view (also index.md and the workbook), so a reader's error is told from the document's own. On the planted reports 31 of 33 re-reads are right; on 9 drawing sheets they catch the sheet index's merged rows. A re-read can err too, so it's shown beside the claim, never instead of it.
- **`export` chunks per topic and per finding:**
  - one chunk per topic the report is browsed by, each claim naming its file and place; a claim said alike in several places (two revisions) is one line naming each place;
  - a comparison's findings by what was found (they differ, uncertain, they complement each other, they agree), each with both claims, the judge's reason and the explanation;
  - each source's claims with no counterpart in the other;
  - agreements whose two claims say the same word for word are left out and counted in index.md.
- **Fixed:** Ctrl+C landing while PyMuPDF's C code ran printed a traceback and exited 1. It now ends as an interrupt, with the resume note and exit 130.

## 0.18.0 (2026-10-31)

- **`second_pass`** (off by default): an analysis reads each subject's claims together, one request per subject of two claims or more. Each request is shown the subject's claims, the passages they came from, their sections and what the subject's siblings give. What it finds is kept as notes beside the claims, never changing them: context a claim lacks, what restates, refines or contradicts what, suspected misreads, inferences, and what's likely missing.
  - The notes appear on each claim's card, as likely gaps in "What it doesn't give", and as an Inconsistencies view (also in index.md, the workbook and `index/inconsistencies.csv`).
  - On 9 drawing sheets it cost $0.085 and found 16 contradictions, including the document's own ("WP" defined as both water pump and waterproof) and the reader's (a "6D" where the passage says 16D), along with some that weren't real.
- **`semantic-pdf-diff export`**: a store's report as Markdown chunks for a RAG system's ingest, with no model calls:
  - One chunk per section, or per part of a section (about 400 tokens). Each says where it came from and lists its claims by subject, with their conditions, places and short excerpts.
  - Chunks for finding things: subjects A to Z, figures and tables, the glossary, gaps and inconsistencies.
  - An index.md. Each chunk file is named by its text's hash, so an unchanged chunk keeps its name from one export to the next.

## 0.17.0 (2026-10-31)

- **Each claim's card shows the source's text around its quote:** the sentences holding it, up to about 600 characters, or a table row under its header, with the quote underlined. It's shown in full where the card has no crop or the size budget left its crop out, and folded to two lines below a crop that's shown (a click unfolds it). It isn't searched, and the judge never sees it.
- **Stores are read again once,** with their answers from the answers cache, so their claims get their snippets. No model requests are needed for that.

## 0.16.0 (2026-10-31)

- **What it doesn't give.** Every report's index now lists gaps found by code, with no model requests. Each is labelled weak, with where it was expected and why:
  - a property most of an item's siblings give that it doesn't (on TS 38.300, PUCCH formats 0 and 1 give no "UCI payload" where formats 2 to 4 do);
  - a figure, table or sheet cited and not found in the document;
  - a value given as a placeholder ("TBD", "to be confirmed").

  They appear in a view of the page, a section of index.md, a Gaps sheet in the workbook and `index/gaps.csv`.
- **Fixed:** the progress line could read "0 in flight" while a page waited minutes on a request it had sent itself (the tiling question, its tiles' labels). It now counts every request at the endpoint.
- **Fixed:** a glossary entry read across a drawing's column gap (a fan schedule's row taken as "EF" meaning "GREENHECK | SP-B90") is now dropped.
- The `glossary` setting's default is confirmed (the owner: "Confirm glossary on by default.").

## 0.15.0 (2026-10-30)

- **`retrieve_glossary` and `topic_glossary` are on by default** (the owner: "Yes, turn on the recommended items."). Comparing proposals, a meaning written out pairs with its term among the pairs judged. The topics count a meaning written out as its term, so "SWD" in one source and "side water depth" in the other make one topic. Where a source defines no terms, nothing changes.

## 0.14.0 (2026-10-30)

- **Search finds a term's meaning anywhere in a claim.** A term the documents' glossaries define finds its meaning's claims, and the meaning finds the term's, wherever their words are in a claim. The model's other names still match only a claim's whole name. They're offered as "The glossary's other names for it" on the page and by `semantic-pdf-diff search` (`--json`: `glossary_names`). They were listed as the model's other names before.
- **`retrieve_glossary`** (off by default; on recommended): comparing proposals, retrieval takes a meaning written out as its term, so one team's "air handling unit" meets the other's "AHU" among the pairs judged. On a controlled pair where one side abbreviates, one or two more of its 32 or 33 shared facts had their claims paired, in every format, and none were lost.
- **`topic_glossary`** (off by default; on recommended): the topics count a meaning written out as its term, so "SWD" in one source and "side water depth" in the other make one topic. On the abbreviated pair, the share of claims placed in a topic went from 74% to 97%.
- **`explain_glossary`** (off by default): the explainer is shown the terms each claim uses. Measured no different.

## 0.13.0 (2026-10-30)

- **A discipline's abbreviations hold for its sheets.** Where a drawing set has abbreviation lists on sheets of two disciplines or more, each discipline's list (on S-001, E-001, and so on) holds for that discipline's sheets. A general sheet's list (G) still holds for the whole set, as do a set's lists that all belong to one discipline. Where a term is used, the nearest definition holds: the sheet's own, then its discipline's, then the document's. dc's "EF" now means each face on its structural sheets and exhaust fan on its electrical ones. The index says where each meaning holds ("S sheets only"; "page 23; S sheets"), and only flags a term as defined differently where two sources disagree about the same sheets.
- **A common word that a list defines** ("OF" for outside face, "IF", "NO.") counts as the term only where it's printed in capitals and the words beside it aren't, so "TOP OF STEEL" keeps its word. This narrows what `judge_glossary` and `reader_glossary` (both off) are shown.

## 0.12.0 (2026-10-30)

- **`align_glossary` is on by default** (the owner: "Yes, let's add align_glossary as a default"): comparing revisions, a meaning written out pairs with its term, so a revision that abbreviates still has its values compared with the other's.
- **The glossary is read before the claims** (it was read before they were compared), so the reader can use it too. The same requests and the same report.
- **`reader_glossary`** (off by default): each request reading claims is shown the terms its words use, as its document defines them ("Defined in this document: SWD = side water depth"). Measured against a null arm on the controlled corpus, TS 38.300 and a drawing set: no different.
- **Fixed:** a list that prints each meaning before its abbreviation ("ADDITIONAL", then "ADD.") was read reversed, so the index showed it backwards. Such an entry is now turned round where the meaning is one word abbreviating the term.
- **Fixed:** with `judge_glossary` or `reader_glossary` on, a defined term of several words printed across a line break ("parent node") stopped the run.

## 0.11.0 (2026-10-30)

- **The glossary is read before claims are compared** (it was read after), so a comparison can use it. The same requests and the same report.
- **`align_glossary`** (off by default; revisions, with `align` and `glossary`): alignment takes a meaning written out as its term, so a revision that abbreviates ("an SWD of", "SBs") still pairs its values with the other's "side water depth" and "sedimentation basins". A long meaning's last words count too where no other meaning ends so ("detention time" for "hydraulic detention time"). On a controlled pair abbreviating what its earlier revision spells out, both changed values are now found in every format, where they were listed as unmatched.
- **`judge_glossary`** (off by default): the judge is shown the terms each claim uses, as its document defines them. Measured no different: the model already reads common abbreviations.

## 0.10.0 (2026-10-30)

- **A glossary entry's reach.** A symbol on a drawing sheet, drawn or lettered, holds for that sheet ("sheet E-001", from its title block). Everything else holds for its document: abbreviation lists, definitions, prose, and a drawing set's abbreviations, terms and conventions. The index says when a term is one sheet's ("sheet E-201 only"), or that it's consistent where it means the same on two sheets or more ("alike on 3 sheets"). Only terms holding for their documents, and consistent symbols, are taken as other names by the search.
- **Other names join the index's subjects.** A glossary term and its meaning ("AHU" and "air handling unit"), or names the model grouped as one thing's, now act as one name:
  - one source's subjects under such names are joined;
  - subjects of two sources that the findings left apart are matched by them ("matched by other names");
  - a subject's properties under such names become one row ("NPSH" and "net positive suction head").

## 0.9.0 (2026-10-30)

- **Kinds of items in the index.** Tagged items group by their tag's letters (P-101, P-102 and P-103 as "pump (P)"), and items named with a number by the name without it ("Room 104", "Room 105" as "Room"). Each kind is a table of its items by property, the properties most of them give first, with "—" where an item gives none its siblings do. It appears in index.md, the workbook's Kinds sheet (an outline collapsing to the kinds), `index/kinds.csv` and the page's Kinds view.
- **A glossary list that runs past its page** in a PDF without an outline is read on over the next pages, up to the next heading. The calg manual's DEFINITIONS are read over four pages.
- **A drawn legend's symbols:** a drawing's Symbols or Legend block is read from its words as before, and its picture is asked for its symbols (with vision on). A drawn symbol is described in square brackets, such as "[circle with M] = MOTOR". On calg's legend this took the glossary from 25 terms to 49.
- **Indexes are built whenever a report is written,** so `semantic-pdf-diff report` brings an older comparison's index up to date.

## 0.8.0 (2026-10-30)

- **Glossaries.** After a comparison or analysis, each source's abbreviations, defined terms, symbols and conventions are read (the `glossary` setting, on by default):
  - from the parts headed Abbreviations, Definitions, Symbols, Legend and the like. The model reads them a part at a time, and a term is kept only where the text holds both it and its meaning. A Word or Markdown table there, or a list of tabbed lines, is taken as it is, with no request.
  - from definitions in prose, such as "net positive suction head (NPSH)".
  - A drawing sheet's abbreviations are read as rows of words by position, so each term stays beside its meaning even where the text layer lists the columns apart.
- **The glossary in the index:** a Glossary section in index.md, `index/glossary.csv`, a Glossary sheet in the workbook, and a Glossary view in the page. In a comparison each term is listed once with each source's meanings, and a term the sources define differently is marked. A search for a term also finds the claims under its meaning.

## 0.7.0 (2026-10-29)

- **`semantic-pdf-diff analyze SOURCE`** reads one source and reports its claims without comparing. The source can be a file, a folder or zip of documents, or a declared source. Its report opens on every claim, with topics, a file filter and the same search (other names and vectors too). It takes `compare`'s options except the comparing ones, and uses the same store, settings and answers cache. `report`, `search` and `debug` read an analysis as they read a comparison.
- **Indexes beside every report** (`analyze`'s and `compare`'s), built from what was read with no model requests:
  - `index.md`: subjects A to Z, each with its properties and every value with where it's said; then properties, and figures and tables.
  - `index.xlsx`: a sheet per index. Subjects is an outline: each subject's row with its values beneath, collapsing to the subjects. Plain numbers are stored as numbers.
  - `index/*.csv`: subjects, properties, claims, and figures.
  - `report.json`'s `index`.
  - In a comparison, one merged index: the sources' subjects are matched where the findings pair their claims (else by name), and each source's values sit side by side, "—" where one gives none. A subject's properties are one row where they're named alike or the findings pair their claims ("seating capacity" and "rider capacity").
- **Subjects and Figures views** in report.html. Each value links to its claim's card, and the search box filters them.

## 0.6.1 (2026-10-29)

- **A rate limit that resets later pauses the run at once, saying when.** A 429 that says when its limit resets (`Retry-After`, or a LiteLLM proxy's `reset_at` header and "Limit resets at:" message) is waited for when that's within 10 minutes. Later than that, sending stops at the first such refusal, and the run pauses (exit 3) with "rate limit reached at URL until TIME (in 3 h 5 min)". Before, each request was retried a minute apart, and the run paused only once 25 in a row had failed, without saying when the limit resets.
- The reranker's warning for requests not sent no longer says their pairs were judged: once sending has stopped, the judge isn't asked either.

## 0.6.0 (2026-10-29)

- **Answers cut short no longer stop a run.** An answer that's cut short, or isn't the JSON asked for, shows the endpoint working, so it doesn't count toward `stop_after_failures`. Before, 25 dense pages in a row stopped a whole run before its reranker, judge, names and topics were asked, even though those pages are asked again in smaller pieces anyway.
- **Requests not sent are counted apart from failures.** The reranker's and the embedding model's summaries and warnings say how many weren't sent (because sending had stopped, or a cap was reached) and how many failed. `debug` says so too.
- **`embed_dimensions` is unset by default.** No size is asked for, and the model answers at its own. Set it for a model trained to be cut: 256 was measured best for Qwen3-Embedding-8B. A store embedded at 256 embeds its claims again on its next comparison, for a fraction of a cent.
- **`debug`** names the region of each extraction error (text, table, tile, overview, figure), and fits its step column to the longest step's name.

## 0.5.0 (2026-10-29)

- **`semantic-pdf-diff debug`** says what a store's runs asked and what failed, in a few lines to read off a screen. It shows:
  - the endpoint and models the last comparison used;
  - the requests by step (extract, compare, rerank, embed, ...): asked, answered, failed, and never answered (not sent, as after sending stopped);
  - the last comparison's counts;
  - the errors the answers cache recorded, the most frequent first.

  It asks no model, and prints nothing of the documents but what a server's error quotes. `--errors N` shows more errors; `--json` prints everything as JSON.

## 0.4.0 (2026-10-29)

- **Embedding models that can't be cut work.** Every embedding request asked for `embed_dimensions` (256). Five of DeepInfra's 25 embedding models refuse any size with HTTP 400: BAAI/bge-base-en-v1.5, bge-en-icl and bge-large-en-v1.5, intfloat/e5-large-v2, thenlper/gte-large. A refused request is now asked again once with the model and the input alone, and the model answers at its own size. `config test` names the vectors' size, and says when it's the model's own.
- **A refusal says why.** A failed request said only its status (`HTTP 400: Bad Request`). It now adds what the server said: a JSON error's message, or plain text, on one line.
- **`-vv` shows what a refused request sent** (images and long texts shortened) and what the server answered. `config test` takes `-q`, `-v`, `-vv` and `--log-file`, as a comparison does.

## 0.3.0 (2026-10-28)

Everything since 0.2.0 (2026-09-24, about 630 commits), in brief. Each item's decision record has the detail.

- **Sources and stores:**
  - Files, folders, zip archives and manifests are declared as sources in a resumable store, a local folder ([0002](docs/decisions/0002-evidence-attaches-to-content.md), [0003](docs/decisions/0003-sqlite-evidence-store.md)).
  - A claim is kept once per piece of content, with every place it was read ([0005](docs/decisions/0005-union-provenance.md)).
  - A store reads again what a changed setting or reader affects ([0004](docs/decisions/0004-store-bound-to-its-interpreters.md), [0016](docs/decisions/0016-content-reread-when-its-reader-changes.md)).
- **Formats:** plain text, Markdown, Word, PowerPoint, Excel, CSV and images besides PDF, through one task core ([0020](docs/decisions/0020-formats-share-one-task-core.md)).
  - Office drawings are rendered ([0021](docs/decisions/0021-metafiles-drawn-by-vendored-renderer.md)).
  - Spreadsheet cells are read as Excel shows them ([0022](docs/decisions/0022-spreadsheet-cells-as-excel-shows-them.md)).
  - Every table is read by rules a model writes for it ([0023](docs/decisions/0023-tables-read-by-rules-a-model-writes.md), [0024](docs/decisions/0024-pdf-table-structure.md)).
- **PDF pages:**
  - Tiles are chosen by measures of each candidate cut ([0029](docs/decisions/0029-tiles-chosen-by-measures.md)).
  - Figures are linked to the prose citing them, and figures and sections are given what they're about ([0039](docs/decisions/0039-runs-paced-by-throughput-and-situated-after-extraction.md)).
- **Claims in context:** each claim carries its headings, lead-ins, notes and title blocks, and who holds it (a company's view, a hedge).
- **Comparing:**
  - Proposals' claims are paired by retrieval and a reranker, then judged.
  - Revisions are aligned item by item, equal values settled without a model, and each difference named by kind ([0038](docs/decisions/0038-revisions-aligned-then-differences-explained.md)).
- **The report:** `report.html` is one self-contained file ([0033](docs/decisions/0033-self-contained-reports-and-their-search.md)):
  - crops under a size budget
  - topics, and every claim of both sources
  - a search the command line shares (`semantic-pdf-diff search`)
  - views, filters and items kept in the page's address
  - `--split` for comparisons too large for one file
- **Setup:** settings in layers, set with `semantic-pdf-diff config`; four environment variables; one answers cache per user ([0032](docs/decisions/0032-settings-in-layers-and-one-answers-cache.md)).
  - There's no default model.
  - The endpoint is checked and calibrated on first use ([0034](docs/decisions/0034-endpoint-checked-and-calibrated-on-first-use.md)).
  - The endpoint's URL comes from `$OPENAI_BASE_URL` or the user's settings, never a store's.
- **Runs:**
  - Requests are paced by the server's throughput ([0039](docs/decisions/0039-runs-paced-by-throughput-and-situated-after-extraction.md)).
  - Progress is shown in bars ([0035](docs/decisions/0035-progress-drawn-by-the-product.md)).
  - Ctrl+C stops cleanly; the same command resumes.
  - Every request is at temperature 0 ([0012](docs/decisions/0012-temperature-zero-and-model-neutral-defaults.md)).
- **Diagnostics:** each image tile's path is recorded and counted, with the tiles whose answers say their text was cut.
- **Incompatible with 0.2.0:**
  - `OPENAI_MODEL` and `PDF_DIFF_<NAME>` aren't read; a run that finds one set says which `config set --user` replaces it.
  - The output folder is now a store.
- **The lab** is its own distribution, `semantic-pdf-diff[lab]` ([0014](docs/decisions/0014-lab-as-its-own-distribution.md)): improvement rounds, controlled documents with known facts ([0036](docs/decisions/0036-controlled-documents-with-exact-keys.md)), and levers judged against their baselines ([0037](docs/decisions/0037-levers-judged-paired-and-promoted-held-out.md)).
