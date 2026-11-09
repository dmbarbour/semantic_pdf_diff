# Changelog

Versions are `0.MINOR.PATCH`, raised at each checkpoint that changes the product, and tagged `vX.Y.Z` ([decision 0040](docs/decisions/0040-versions-raised-at-checkpoints.md)). The lab shares the product's version. Each entry says what a user would notice.

## 0.51.0 (2026-11-09)

- **A link's level from numbers** (`link_levels: weights`, off; tentative matches, milestone 6): comparing proposals, each candidate pair's features banded and weighed (Fellegi-Sunter weights fitted on the controlled proposals pairs, `link_weights.json`), its score against thresholds giving its level, the model's read raising a link it picks; each link says its score and the share of matches it says. Held out (fresh seeds): right plausible links 48 → 62, 95.4% right (the rubric 96.0%). Revisions keep the rubric.
- `links.candidates`: each pair's features apart from its leveling (behaviour preserved).

## 0.50.0 (2026-11-09)

- **`link_tests` and `link_read` on by default** (the owner: "Yes, turn both on by default."), after passing their held-out rule (seeds 2 and 3 of the three controlled proposals pairs, every format): wrong plausible links 55 → 0 with the tests; right plausible links 32 → 57 with the reads, 95% of plausible links right. The reads ask a request a link, comparing proposals only (as held out). Round 0's settings keep both off.
- `controlled.py heldout`: held-out proposals pairs generated, compared and scored by role, apart from development's.

## 0.49.0 (2026-11-08)

- **A link's evidence tested by code** (`link_tests`, off; tentative matches, milestone 4): properties in common count only where they set a pair apart from its siblings; between proposals, values that don't fit (another kind of unit, more than ten times apart) leave a link possible at most. On the controlled proposals pairs, plausible links 16 of 16 right (25 of 43 without).
- **A link read by the model against a decoy** (`link_read`, off): the linked subject and the other source's next likeliest, values hidden between proposals; picked, evidence; the decoy or neither, possible at most. With the tests, plausible links 24 of 25 right.
- A model's readings of a pair (the reranker's, `match_subjects`', the read) count as one kind of evidence toward a link's level.

## 0.48.0 (2026-11-08)

- **Links by the reranker's likest** (`link_rerank`, off; with a reranker, `rerank_model`): each subject left alone ranked against the other source's, told the task (the same item, or one playing the same part); its likest, scoring 0.8 or more, a link's evidence of its own (tentative matches, milestone 3). The reranker scores relevance more than identity: alone it makes a link possible at most.

## 0.47.0 (2026-11-08)

- **Links by names alike in meaning** (`link_meaning`, off; with an embedding model, `embed_model`): each claim's name embedded once, two subjects whose names are each other's likest (cosine 0.8 or more) a link's evidence and candidates (tentative matches, milestone 3; the owner: "Match candidates by meaning might help").
- Names spelled alike (letters' trigrams) are a link's candidates and names' evidence; the names' words, spelling and meaning count as one kind of evidence toward a link's level.
- Comparing proposals, numbers that differ in two names no longer rule a link out (NREL's 5 MW turbine and IEA's 15 MW); comparing revisions they still do (Room 104 isn't Room 105).

## 0.46.0 (2026-11-07)

- **Links: subjects possibly one, kept apart** (tentative matches, milestone 2; the owner: "Three levels is a start"; plausible matches "should feed links and topics for now"): in a comparison, two sources' subjects linked by weaker evidence, never merged, each with its level (plausible: two signals; possible: one) and its signals (names, properties or values in common, the judge's pairings, alignment's groupings, the model's answers). Shown in the Subjects view and index.md ("possibly the counterpart of …"), found by a search for either; a plausible link's claims share a topic. Revisions' and proposals' evidence weighed apart.
- `match_subjects` keeps an answer whose candidate another took, as a link.

## 0.45.0 (2026-11-07)

- **`look_gaps` on by default** (the owner: "Go ahead and turn on `look_gaps`."): each gap another source fills is looked for where it'd be, a request a gap (about $0.0002 each; the 8 development slice comparisons asked 110, $0.016). Round 0's settings keep it off.

## 0.44.0 (2026-11-07)

- **Subjects across documents, and the gaps another source fills** (single-document analysis, milestone 7; the owner, answering its design: "All four recommendations look good as a start."):
  - Comparing proposals, subjects are matched by name or other names, no longer by the judge's verdicts alone (they compare values, not items). Revisions as before.
  - `match_subjects` (off): the model matches what names leave alone to the same item, the corresponding element (each design's tower) or a state of it, kept apart; "matched by model" in the index.
  - A gap kind, **Another source gives it**: a matched subject's property one source gives and another describing it doesn't, in the gaps view, index.md, the workbook and gaps.csv.
  - `look_gaps` (off): each such gap looked for where it'd be (given under another name, not given, no place for it, not shown), beside the gap, in the subjects' blank cell and on the other source's card.
- The slice runs' replay fixture re-recorded: it had gone stale.

## 0.43.0 (2026-11-07)

- **The second pass in comparisons, its notes shown the judge, as a setting** (`judge_notes`, off): each source's subjects read together before judging (as an analysis's second pass), the judge shown what that noted of each claim, and the notes kept as the comparison's commentary, on its cards. Measured: the controlled revision pairs within noise; a proposals pair (two reference turbines) 27 of 1,000 verdicts changed, most more decisive and right. Left off: a run costs the second pass's requests besides the judge's.

## 0.42.0 (2026-11-07)

- **Summaries of sections, files and the source by default in analyses** (the owner: "Go ahead and turn on summaries."): each sentence citing the claims it rests on and checked against them, in the Summaries view and the export. Subjects' and topics', a request an item or topic, are asked for with `summaries`; `summaries: []` writes none. A store analyzed before writes them on its next run, its claims from the store.

## 0.41.0 (2026-11-07)

- **Summaries, each sentence citing its claims, as a setting** (`summaries`, none by default; analyses; the owner: "This seems like a good design for milestone 4."). The kinds named are written by the model from the claims alone: a section's (a drawing set's sheets, page by page), a file's from its sections', a folder's from its files', a subject's, a topic's. Each sentence cites the claims it rests on and is checked by code: it cites claims it was given, and states no number they don't give; one failing is kept and marked. In a Summaries view, each citation a link to its claim, and in `export` as chunks labelled as written by the model, with the claims they cite. On two real analyses, 694 sentences, every one citing its claims, none stating a number they don't give.
- **Fixed: tensions raised two values of one property, and two items sharing a name as conflicts.** A tension whose claims all give one property is dropped (the second pass's contradictions), and a "can't both hold" whose claims stand on different pages is taken as "needs a reason", saying they may be two items. On scical's sheets, 14 tensions became 10, none "can't both hold"; on the IEA report, 2, both worth it (a drag coefficient of 0, a misread; plywood as an exterior deck).

## 0.40.0 (2026-11-06)

- **An analysis's later steps shown as bars of their own** (the owner: "it seems the second pass doesn't have its own progress bar? Mine's been on `embed` with 10,296/10,296 sentences but has been doing reread steps for hours now."): the second pass's subjects and kinds, the claims it doubts read again, the gaps looked for, the kinds named, the tensions' subjects. Before, they were counted only in the status line, under the last bar drawn.

## 0.39.0 (2026-11-06)

- **Tensions: claims hard to hold together on engineering grounds, with levels of suspicion, as a setting** (`tensions`, off, analyses; the owner: "We'll need to also look for qualitative inconsistencies, with levels of suspicion. E.g. claiming low-alloy steel combined with a claim of corrosion resistance without a clear mitigating factor."). Each subject (with its parts) holding a word value is asked which of its claims are hard to hold together (a material and a service it doesn't suit, a rating and where it's used), at a level (can't both hold; needs a reason; worth a look), why, and what would reconcile them. Those words are then looked for in what the source's claims say: found, the tension is shown reconciled, citing where; not found, it stands. On both claims' cards, and in a new Suspects view, those standing first by level ("worth a look" marked low priority). `reviewer_concerns` adds a reviewer's own things to watch for; it works without them. On planted reports: all 6 planted tensions found, none standing where the document reconciles them, each reconciled by the right statement.

## 0.38.0 (2026-11-06)

- **A tile's text layer by whole lines, by default** (`whole_lines: true`; the owner: "Let's go with your recommendations."). Checked on held-out drawing sheets and posters first: as much read (651 numbers against 641, within the model's own variation), for 9% fewer requests; tiles complain of cut text far less. A store read before reads its image regions again on its next run, unchanged requests answered from the cache.
- **Claims whose quote isn't found kept, marked, as a setting** (`unquoted: kept`, off; the owner: "Filtering the claims before they reach the database seems like a way to lose useful information."). Such a claim is kept with its quote unverified, its card warning that it's in the model's words; the Reading view counts it, the export says so. On the controlled corpus it finds 14 more facts among 712 more claims, 62 more of them misbound.
- **Fixed: a quote missed a word broken at a line end, or spacing an OCR layer lost** ("con-\nditions" quoted "conditions"; "59,045cfm" quoted "59,045 cfm"), so such claims were dropped. Stores check their quotes again, from the answers cache. Why quotes fail was investigated on the corpus's recorded answers: mostly words that are there but not as one run, not paraphrase; dropped claims are 64% right and 16% misbound, against kept ones' 77% and 5%.

## 0.37.0 (2026-11-06)

- **A tile's text layer by whole lines, as a setting** (`whole_lines`, off): an image region's text layer holds every line it touches whole, not the words it clips. On 11 pages where tiles cut lines it read as many numbers (within the model's own variation), with the same keyed facts, for 7% fewer requests: tiles complained of cut text far less (a poster's 65 to 8), so fewer were read again.
- **A tile answered complete that says its text was cut, read again, as a setting** (`said_cut: read again`, off): as a partial one is, under the page's next cut. On the same pages it changed one, gaining a poster's colour-bar ticks: most such tiles are already answered partial and read again.

## 0.36.0 (2026-11-06)

- **How well each page was read, in the report's Reading view** (the owner, 2026-10-09: "some sort of quality heuristics spot-check for runtime behavior would be useful for both confidence decisions and part of the report"). What a run recorded of its own reading, counted by file and page, each kind apart and with what it's counted of: requests that failed, weren't sent or came back incomplete; claims dropped because their quote isn't in their text; a picture's claims whose quote isn't in the text layer; image tiles that said their text was cut; tables read without their rules; claims the second pass doubted or read again otherwise. No model is asked and no score made of them. Each page's claims are a link away, and the search finds pages by `file:` and `page:`. A run ends with one line of the totals ("Read with problems: 9 of 9 pages (cut short 48, …)").

## 0.35.0 (2026-11-06)

- **`SEMANTIC_PDF_DIFF_USER`: a folder for what's the user's** (the owner: "I open a fresh container every day, so the user is lost unless I make a heroic effort to save and restore the user. Perhaps enable a `SEMANTIC_PDF_DIFF_USER` environment variable to act as an alternative HOME for this role?"). Set, it holds the user's settings (`settings.json`, `config set --user`) and the user's answers cache (`cache/`, with its record of checks passed), in place of `~/.config` and `~/.cache`. `SEMANTIC_PDF_DIFF_CACHE` still names the cache where set, and a store already bound to a cache keeps it (`config set answers_cache` binds it to another). `config show` lists it.

## 0.34.0 (2026-11-06)

- **A run checking its models again says why** (the owner: "It seems the initial calibration queries aren't cached?"). Checks are remembered in `endpoints.json` beside the answers cache, so with one cache a second run asks only the ping ($0.00002 at DeepInfra; the first use took 41 s, acuity's eight cards 37.5 s of it). Where a run checks again, its `First use:` line now says why: no record there yet (each answers cache keeps its own), forgotten (when, and why: a check failed, a run's requests failed in a row, `config checks --forget`), remembered at another `image_side`, or never passed there; and where the user's cache's record remembers them all, that it does, though a run reads only its own.
- **Fixed: a run said "Calibrated from what was measured: context_tokens …, image_tokens …" each time,** though only its first use measured. A remembered run says what was measured on the ping's line, as remembered.
- **The search helps show a file's name with spaces quoted** (the owner: "Most filenames have spaces, so we should support quotes there perhaps."): `file:"pump spec sheet"`, a whole name or a part of it, already worked; on the command line, quote the query whole for the shell: `semantic-pdf-diff search 'file:"Pump Spec Sheet.pdf" page:3-5'`.

## 0.33.1 (2026-11-06)

- **Fixed: the report's other views took the search's language as plain text.** The Subjects, Kinds, Figures and tables, Glossary, Gaps and Inconsistencies views filtered their rows by the search's text as typed, so `file:`, `page:`, phrases, `-word`, `OR` and values compared found nothing there (the owner: "the search doesn't work properly for things like `file:` or `page:` as described in the search help"). They now read it as the Claims view does: a row's own words for the words, and its claims for the rest, one claim all of it (`file:a.pdf page:12` finds the subjects with a claim on that page of that file); a figure's and a glossary term's own file and page too.
- **Fixed: a part named with a space after its colon was searched as a word** (`file: a.pdf`, `page: 12`, finding nothing or the wrong claims): it's now read as `file:a.pdf`, in the report's search box and `semantic-pdf-diff search`.

## 0.33.0 (2026-11-03)

- **Progress while the endpoint is checked:** a run's first-use checks and `config test` show a bar for each check, of what it asks: the endpoint's listing, the JSON answer, the image check's two answers, the acuity test's eight cards, the reranker's ranking and the embedding model's request, with the requests' status below (the owner: "it's unclear whether my system is frozen or just moving slowly."). Before, one line said the checks had begun, then nothing until they ended; the acuity test alone takes about 30 s at DeepInfra.
- **A wait shows as one:** once no answer has come for 10 s, the status says how long ("no answer in 45 s", "last answer 1 min 05 s ago"), drawn again each second. Without a terminal, a heartbeat line comes every `heartbeat_seconds` whether or not anything changed.
- **Fixed: a terminal of no size set drew the bars 10 columns wide** (a bare pseudo-terminal's, `script`'s): it takes the default width now, `COLUMNS` or 80.
- **Fixed: Ctrl+C sometimes ended a run with "Error: release unlocked lock" and exit 1,** not the note on resuming and 130: an interrupt arriving while a wait took its lock back came out as that error. It now ends the run as Ctrl+C does.

## 0.32.0 (2026-11-02)

- **A ruled table's lines of two labels joined shown to the model by default** (`labels_joined: true`; the owner: "Yes, let's turn that on by default."). A store read before reads its tables again on its next run, each unchanged request answered from the cache; only a table part with such a join asks the structure query anew.

## 0.31.0 (2026-11-02)

- **A ruled table's lines of two labels joined, shown to the model** (`labels_joined`, off; the owner: "Yes, please develop that check for suspect joins."). Our table mending joins lines across the unruled boundaries of a mostly ruled table, and can't tell two labels made one row ("ADDRESS:" and "DRAWN BY:" in a title block, "AH ALUM" in an abbreviation list) from one label over two lines. With it, such a part goes to the structure query with those lines apart, each tagged "read with the line above": the model's "keep" makes a line a row of its own, and otherwise it stays joined. On the corpus's pages with such a join, parts read by the model's rules 29 → 64 (development's pages) and 65 → 89 (held-out's), nearly every part read otherwise better by eye; 13 title blocks' answers failed twice where they had passed, read as the mending left them. It asks once more for a part with such a join that wasn't asked already.
- **Fixed: a lone value a model gave for a list failed the whole answer** (a structure rule's `"into": "B"` for `["B"]`): it's now a list of that one value. It had failed structure answers wherever a join named one column.

## 0.30.1 (2026-11-02)

- **Fixed: a ruled table's rows each starting with their own tag were joined into one** ("A-102 A-201" | both titles). Our table mending took a table ruled at most of its boundaries for one whose unruled boundaries are a row's wrapped lines; scical's sheet index (61 of 95 ruled) lost 21 rows that way, each sheet's claims counted for none. Two lines each starting with a tag of their own, of one shape, now stay apart; a line whose tag and title PyMuPDF merged across the columns is parted where its words are, where that fits neatly. Of the corpus's 6,028 tables, 3 read otherwise, each by eye right; none in the controlled corpus. PDF tables are read again (reader pdf/14), unchanged requests from the cache. On scical's 9 sheets: rows read as one 21 → 0, its gaps and contradictions as before, 15 fewer doubted claims ($0.023).
- **Fixed: a value cut short in a word kept a kind's two properties apart** (a title cut at a tile's edge, "HARDWIRED EQUIPMENT ELECTRICA", against the whole title): such a value, two words or more, is now alike.

## 0.30.0 (2026-11-02)

- **The endpoint's key from a variable of its choosing:** `model_key_env` names the environment variable the endpoint's key is read from (default `OPENAI_API_KEY`). The reranker and the embedding model are sent it too, unless `rerank_key_env` or `embed_key_env` name their own. Only the name is kept; a value not shaped as a variable's name is refused without being said back. `config test`, `config show`, `debug` and a run's first line name the variable.
- **A scan's tiles halved between their lines by default** (`scan_halves: lines`; the owner: "I agree `scan_halves` defaults to `lines`."). A store read before re-reads its image regions on its next run, each unchanged request answered from the cache; only a scan's tiles read again in halves ask anything new.

## 0.29.0 (2026-11-02)

- **A scan's tiles halved between their lines** (`scan_halves: lines`, off): a tile of a page without a text layer that's read again in halves was cut down the middle of its longer side, through every line of a band. With it, the cut goes between the lines the tile's own image shows (rows of ink, parted at gutters), and where none are found, across the tile's shorter side. A drawing sheet with a text layer keeps its cut. It changes nothing the controlled corpus recorded.

## 0.28.0 (2026-11-02)

- **Fixed: one thing's name holding two tags was counted as naming several items.** TS 38.300 names things so ("L2 U2N Relay UE", "L1/L2 Triggered Mobility"): 477 of its claims were counted for none of their subjects, kinds and gaps. Now several items are rows read as one (tags of one shape, apart by spaces or titles: "A-102 A-201") or a list (apart by commas, "and", "or"). TS 38.300: 477 → 10; scical's merged rows as before.
- **A list's claims count for each item it names** ("SRB0, SRB1, SRB3 and other MAC CEs", "Pumps P-101 and P-102"): the value is under each, marked "[said of ...]", and an item named only in a list is a subject of its own, so its siblings' gaps show what it lacks. Rows read as one still count for none.
- **`export --json`:** `chunks.json` beside the Markdown chunks, every chunk as an object (name, title, front matter's fields, text), for a system ingesting JSON.
- **`export --since FOLDER`:** a delta against an earlier export, written to the store's `export-delta/`: only the chunks the earlier one doesn't hold, and in index.md the names of its chunks to remove.
- **A reranker's or an embedding model's own key:** `rerank_key_env` and `embed_key_env` name the environment variable its key is read from (unset: `OPENAI_API_KEY`). Only the name is kept; a value not shaped as a variable's name is refused without being said back. A run's first line names the variable, and says when it isn't set.
- **The acuity check sends its cards two at a time,** gentler on an endpoint of a few servers.

## 0.27.0 (2026-11-02)

- **How small a model reads, measured on its first use** (`acuity`, among the checks): eight cards of random codes and numbers, one for each capitals' height from 5 to 16 px, as large as an image is sent, give the smallest height the model reads 90% of. It's said against the 7 px pages are tiled for, with a warning where it's above 7.7 px. A model reading no card stops the run. `config test` runs it (`--only acuity`), `config checks` and `config models` show it. At DeepInfra: gemma-4 7.0 to 7.4 px, about $0.0013 a check; gemma-3-27b 8.0 to 8.2; Mistral-Small-3.2 8.3.

## 0.26.0 (2026-11-02)

- **A run's settings said before it starts:** the models it asks and where, and each feature off for want of a model no layer names: reranking (comparisons in proposals mode) and search by meaning, with how to name one or go without.
- **`none` kept apart from not configured** for `rerank_model` and `embed_model`: `config set --user rerank_model none` goes without, and runs stop saying so; `config unset` leaves it not configured again. `config show` says `not set` or `none (user)`, and `config test` says which.
- **Every run pings its models first,** even those whose checks are remembered: a small request to the chat model, the reranker and the embedding model, about $0.00002 at DeepInfra, said in one line. A model not answering stops the run before anything else is done (exit 5), and its checks are forgotten, so the next run checks and calibrates again.

## 0.25.0 (2026-11-01)

- **A reranker or an embedding model tried as one:** `config test --rerank NAME` and `--embed NAME` try a candidate in its role, with its role's check alone (scores, or vectors), without setting it; remembered under its role, as `config checks` shows. A chat candidate the endpoint lists as an embedding model or a reranker is said to be one, with the flag that tries it as one.
- **`config models` says what each model serves:** a mode column (`chat`, `embedding`, `rerank`, `image_generation`...), its context, the most it answers with where that's less, its price. `config models embedding` and `config models rerank` find them. A LiteLLM proxy lists its models' names alone, so its `/model/info` is asked too, for what its configuration or price map says.
- **`config set rerank_model` and `embed_model`** are checked against the endpoint's listing as `model` is: a warning where the endpoint doesn't list the name, or lists it as serving otherwise.
- **Kinds grouped by what their items are** (the index's Kinds, its siblings' gaps, and the second pass's hints):
  - **A drawing set's sheets are one kind, "sheet",** whatever their letters, recognized by the shape its title blocks print their numbers in (G-001). On 9 of scical's sheets, 15 kinds by letter became one of 84 sheets.
  - **A property named two ways is one** where three items or more give both, alike each time ("drawing title" and "sheet name"), headed "drawing title (also sheet name)".
  - **A claim naming several items** ("A-401 A-402": rows read as one) counts for none of them; a subject is named by a name naming it alone, and one whose every name names several is marked and left out of kinds.
  - On 9 of scical's sheets, gaps 152 → 48 with the second pass read again, the 3 confirmed missing still found. On the planted reports, false gaps from a table read without its header 12 → 6, with every planted contradiction and gap still found.
- **The model can name the kinds** (`confirm_kinds`, off): one request a source, which names each kind by what its items are, merges kinds of one thing and moves items not of a kind. Tried on scical and TS 38.300: better names, no fewer gaps than the rules, and one item moved wrongly, so it's off.

## 0.24.0 (2026-11-01)

- **A model tried before it's set:** `config test --model NAME` checks a candidate as the chat model (the endpoint lists it, it answers in JSON, it reads a card), without changing the model set. `--base-url URL` checks at another endpoint. What passes is remembered, so a first run with that model needn't check again.
- **Checks run selectively:** `config test --only json,image` (or `reranker`, `embedding`), and `--new` for only those not remembered passing.
- **Remembered checks shown and forgotten:** `config checks` lists each model and endpoint checked, when, and what was measured (its context, an image's tokens), and where the record is kept. `config checks --forget [MODEL]` forgets them, so the next run checks again.
- **A model's name checked when it's set:** `config set model NAME` asks the endpoint's listing. It warns, without refusing, where the endpoint doesn't list the name (naming those like it: `google/gemma-4-31b-it` offers `google/gemma-4-31B-it`) or doesn't tag it as reading images, and offers `config test --model NAME`.
- **`config models` marks the models already checked**, with an image's tokens where measured.
- **Snippets stay out of search.** Measured on the 17 queries that hold the page's and the command line's search alike: searched, a claim's snippet reordered 12 of them and added mostly claims beside a sentence or table header holding the words.

## 0.23.0 (2026-10-31)

- **Fixed: the index joined opposite properties.** The model's other names for a property (asked for search) are joined into one property only where they can be one: written in other words ("rated output", "nominal power"), or the same words spelled otherwise ("SIZE W", "size width"). Not a name and a more general one, nor "Maximum transient pressure" and "Minimum transient pressure", which the index had joined on a planted report. On 9 of scical's sheets, one right join is lost ("drawing title", "sheet title").
- **Contradiction candidates found by code.** The second pass is shown pairs of a subject's claims that give one property two values differing in common units, their conditions alike or one stating none, and asked to settle each. On the planted reports, contradictions found went from 5 of 6 to 6 of 6, with none false and no trap taken.
- **A gap's look tells more apart.** Besides given and not given, it now says "no place for it there" (the item is shown, with nowhere it would give the property) or "not shown there" (the item isn't). A value under another name for the same property counts as given. Gaps the reader missed come first in each kind.
  - On 9 of scical's sheets, 150 gaps: 55 given, 3 not given, 77 no place, 15 not shown. Before: 15 given, 26 not given, 85 not shown of 126. Two earlier answers were wrong against the sheet index.
- **A document's own tables.** A table read by rules keeps its cells as read, so:
  - **`export`** writes each table as a Markdown table, a long one in parts under its header again.
  - **A cell left blank** in a column most of the table's rows fill is a gap of its own, "Left blank in a table".
  - Every reader's version is raised: a store is read again from the answers cache, with no requests.

## 0.22.1 (2026-10-31)

- **Exports and reports are made fresh** (the owner: "Each export or report should be logically fresh from the sources, not history-dependent.").
  - **`export`** left an earlier export's chunks in its folder beside its own, so ingesting the folder took both. The folder now holds one export alone. An earlier export's chunks it doesn't hold are removed, and the command says how many. A folder holding a file no export writes is refused, and nothing is written. Hidden files are left alone.
  - **A report's index files:** `index/inconsistencies.csv` from an earlier report is removed when this one finds none.
  - **A report's pages:** a split report no longer leaves an earlier `report.html` beside it. An unsplit report, or one split into fewer parts, no longer leaves an earlier split's parts in `report-split/`.

## 0.22.0 (2026-10-31)

- **The second pass is on by default** in `analyze` (`second_pass`; the owner: "Yes, turn `second_pass` on."). Comparisons don't run it yet. To turn it off: `semantic-pdf-diff config set second_pass false`.
- **Gaps are looked for before they're reported.** In a PDF, each gap among siblings, and each the second pass says is likely, is looked for on the page that best names its subject and property. That place is rendered closer and asked whether it gives a value. The answer is shown beside the gap: "looked for on a.pdf, page 2: not given", "it gives 6.2 ft" or "not shown there".
  - On the planted reports, every planted blank cell came back "not given". On 9 of scical's sheets, 15 of 126 gaps turned out to be given (mostly under another property name), and 26 not given.
- **A kind's items are read together**: one request a kind, such as all the pumps. It looks for items said to be alike whose values differ, a value unlike its siblings', and what the items give together, such as a firm capacity.
  - Where an inference cites plain numbers in one unit, their sum is worked out by code and shown beside it when its words don't give it (the model once summed 1,318 + 1,898 + 1,449 as 4,663).
  - The planted reports' firm capacity, never found before, is now found in every one.
- **Export** adds a chunk a subject (everything said about it, and what it doesn't give), a chunk a kind (its items as a Markdown table), and the second pass's notes under the claims they're about.
- **Corrected:** 0.21.0's "14 values still lost" on two 16:9 decks were the same numbers read with other units. Counted by number alone, none is lost. A rule sending held tiles for numbers no claim gives was tried and not built: there was nothing for it to recover.

## 0.21.0 (2026-10-31)

- **Wide pages are no longer sliced by default** (`skip_text_only: wide_pages`, now the default; the owner: "I think we should turn it on. We should also do the fallback."). On a page too wide for bands, such as a 16:9 slide, image tiles holding only text aren't sent; the text tasks read that text whole. Tiles holding a chart or picture are still sent.
- **The fallback:** those tiles are held back, not dropped. If the page's text tasks end without a single claim kept (on two slides of tables every quote was rejected), the held tiles are sent as before, and their coverage rows say so (`held`).
  - On two real 16:9 decks, 1,828 of 1,849 distinct values are kept, with 535 tiles instead of 589. The 14 values first counted as lost are the same numbers read with other units or none (corrected in 0.22.0): by number alone, none is lost.
- To go back to sending every tile: `semantic-pdf-diff config set skip_text_only false`.
- Stores read before read their documents' image tasks again once, with no new requests: every answer comes from the answers cache.

## 0.20.0 (2026-10-31)

- **`skip_text_only: wide_pages`** (off by default): on a page too wide for bands, such as a 16:9 slide, image tiles holding only text aren't sent; the text tasks read that text whole. The cut is chosen first, as without it, so pages with charts keep their tiles that hold a graphic.
  - A 16:9 page of text no longer goes out as a left, a middle and a right slice of every line.
  - The controlled corpus's five wide documents keep every fact, with 10 tiles instead of 35.
  - On two real 16:9 decks it keeps 1,795 of 1,849 distinct values with a quarter fewer tiles. The 32 numbers lost are on pages whose text task failed, where the tiles were all that read them.
- The controlled corpus gains two 16:9 layouts (960 × 540 pt): one upright, one stored on its side and turned by `/Rotate`, with a banner up the left edge.

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
