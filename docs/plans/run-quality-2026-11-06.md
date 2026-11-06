# The run's reading, counted: where the report deserves less trust

- **Status:** Active (2026-11-06): [milestone 1](#1-a-pages-reading-counted) built 2026-11-06; 2 and 3 not begun; [4](#4-claims-whose-quote-isnt-found-why-and-kept) investigated and built 2026-11-06 (the matcher fixed; `unquoted`, off).
- **The owner, 2026-10-09:** "I'm beginning to believe that having some sort of quality heuristics spot-check for runtime behavior would be useful for both confidence decisions and part of the report."
- **Chosen 2026-11-02** from the review of open items, where Claude offered it as "How well the run read, shown in the report": the owner, "cited summaries, quality reports, and cut-text work are probably the most valuable to me in the short term"; then, 2026-11-06, "we should finish the quality reports and cut-text work, too."
- **Takes over** the tentative row *Runtime quality spot checks*, kept whole [below](#moved-in-runtime-quality-spot-checks).
- **Builds on:** the coverage ledger (every task's status and notes), [text cut by tiles](text-cut-by-tiles-2026-10-28.md)' milestone 1 (each tile's path; the tiles that said their text was cut), the second pass's log of commentary ([single-document analysis](single-document-analysis-2026-10-28.md), milestone 3), the report's views and search ([0033](../decisions/0033-self-contained-reports-and-their-search.md)).

## Why

A report shows every claim the same way, however its page was read. A run records where its reading went wrong, but in a ledger of every task nobody reads (the report's *Source coverage ledger*), or not at all past a count: a claim whose quote isn't in its text is dropped, leaving a note.

- **What a reader can't tell today:** that a page's text task failed and its tiles read it alone; that half the claims a page's text gave were dropped; that a table was read row by row because its rules failed; that the second pass doubted a fifth of a sheet's claims.
- **What it's for:** where to look first, and where to trust the report less. Later, the same counts as signals: a claim's reliability (milestone 2), and work a run does again where its reading went wrong (milestone 3; the owner, 2026-11-02, on progressive disclosure: "code-driven based on quality of responses is fine").

## Milestones

### 1. A page's reading counted

- **Counted by file and page,** from what the run recorded, each kind apart (`quality.py`):
  - requests failed after their retries, not sent (the run stopped first), and answered incomplete;
  - claims dropped, their quote not in the text they were read from;
  - a picture's claims kept with their quote not in the page's text layer;
  - image tiles whose answer said text was cut at their edges (said in their notes, or the edges they named);
  - table parts read without the model's structure, and rows without its rules;
  - claims the second pass suspected (misread, about another subject, out of place), and claims whose place, read again, gave something else.
- **Each with what it's counted of:** the page's requests, its image tiles, the claims its text gave (kept or dropped), its pictures' claims checked against the text layer, its claims.
- **Not weighed into a score** ([no rater is absolute](../decisions/0018-several-raters-none-ground-truth.md)): a count is a place to look. Not counted: a contradiction the second pass found (the document's, not the reading's); a table the model said isn't one (a choice, read by a figure task).
- **Shown:**
  - a **Reading** view in the report: each file's pages with a problem and the pages with the most; a row a page, its counts, and its claims a link away (a search by its file and page); the search finds rows by `file:`, `page:` and the kinds' names, as the other views';
  - one line as a run ends: "Read with problems: 9 of 9 pages (cut short 48, quotes not found 25, …)".
- **No model asked, nothing stored:** counted from the report's data each time it's written.
- **Built 2026-11-06.** Counted on two analyses already recorded (no requests):

  | Report | Pages with a problem | What's most counted |
  |---|---|---|
  | scical's 9 sheets (1,289 claims) | 9 of 9 | cut short 48 of 577 requests, text cut 45 of 382 image tiles, doubted 71 and read again otherwise 30 of 1,289 claims, tables as mended 31, quotes not found 25 of 339 claims from text |
  | Two PDFs: IEA 22 MW's pages 12 to 21, a DC drawing set's 39 to 42 (729 claims) | 14 of 14 | quotes unverified 163 of 615 pictures' claims checked, quotes not found 82 of 196 claims from text (71 on one page: a materials table read as text), tables as mended 20, text cut 19 of 213 image tiles, failed 6 of 410 requests |

  - On such pages every page has something; the counts' bases tell a page with one cut tile in 48 from one with half its text's claims dropped.
  - **Approximate:** a request made incomplete by a dropped claim isn't told from one the model said was incomplete; it's counted as its drops.

### 2. Claim quality signals

From the tentative row (below): three axes kept apart, never one opaque score: reliability, specificity, salience. A claim's reliability begins with milestone 1's counts for its page and its own quote, re-read and doubts.

### 3. Reading again where it went wrong

The counts as triggers, code-driven: a page whose text gave claims mostly dropped read again by its tiles; a tile that said its text was cut read under another cut ([text cut by tiles](text-cut-by-tiles-2026-10-28.md), milestone 2). Each a lever, measured.

### 4. Claims whose quote isn't found: why, and kept

The tentative row *Claims kept whose quote isn't found*, moved in 2026-11-06 (the owner, on the recommendation to build it next: "Let's go with your recommendations. We should also investigate to see how we're matching claims, e.g. if it's rejected as paraphrasing, and see if our quote-matching heuristics need work."). The owner, earlier the same day: "I recall that, in several cases, claims were filtered out because of literal quotes. We might want to still record these as claims or evidence with extra provenance where available, reducing to something like 'quoted anonymously', that may weaken claims without corroboration. Filtering the claims before they reach the database seems like a way to lose useful information."

- **Today:** a text or table task's claim whose quote isn't in its text is dropped, a note left on its coverage row ("Rejected claim with unsupported literal quote"); a picture's is kept, marked (`quote_verified`: false). The check: the quote verbatim up to spacing, or a table's words all in its rows, or `quote_match: fragments` (Unicode forms, case, dashes, quote marks, a line-end hyphen kept in a compound; "…" and " | " parts each found, in order).
- **Investigated 2026-11-06** (no requests: every text and table answer recorded, re-checked as the product checks it, each failing quote sorted by why; the 294 recorded runs of the controlled corpus scored against their keys):

  | Why the quote failed | Corpus | Right | Misbound | Two real analyses |
  |---|---|---|---|---|
  | Every word in the text, not as one run: a chart's labels joined by "…", a room's name and its area on two lines | 430 | 276 | 49 | 65 (drawings' labels and values) |
  | Read from somewhere else: a poll's proposal joined to a row; a table read column by column, its rows named from the context | 247 | 134 | 57 | 28 |
  | From the context the prompt gives, not its source | 105 | 100 | 0 | 5 |
  | Three quarters of its words in the text (paraphrase, mostly) | 94 | 47 | 41 | 4 |
  | Only spacing or symbols differ (an OCR layer's "59,045cfm" for "59,045 cfm") | 24 | 19 | 0 | 4 |
  | A line-end hyphen breaking a word ("con-\nditions" quoted "conditions") | 0 | | | 2 |

  - **The check earns its keep:** the 900 claims it dropped are 64% right and 16% misbound; the 1,939 text and table claims it kept on the same documents, 77% and 5%.
  - **Little is lost on the corpus:** 14 of its facts are found by a dropped claim alone; the rest repeat claims other tasks kept (a tile, the neighbouring text's task).
  - **More on real documents:** an IEA report's materials table, its text layer column by column, gave 71 claims, all dropped (its values all in the text, its rows' names from the context).
  - **Paraphrase isn't the main cause:** the model mostly quotes words that are there, but not as one run.
- **What to change:**
  - **The matcher, a fix:** a line-end hyphen breaking a word read both ways ("con-\nditions" as "con-ditions" and "conditions"), and spacing ignored where only spacing differs (OCR layers lose and add spaces). On the corpus, 19 of the 24 such claims are right, none misbound.
  - **Kept, marked, as a setting (`unquoted`, off):** a claim whose quote isn't found kept with its quote unverified, as a picture's is: its card warns, the Reading view counts it, and what reads it (the second pass, the index, comparisons) can weigh it below a verified claim. Not words-in-order as verified: those claims are misbound three times as often as kept ones.
- **Built 2026-11-06, both measured on the corpus's recorded answers replayed (no requests):**
  - **The matcher's fix** (`quotes.excerpted`; every reader's version raised, stores checking their quotes again from the cache): 15 claims more kept (11 on the scanned OCR page), one more right, none misbound or misread.
  - **`unquoted: kept`:** 712 claims more (unverified 405 → 1,117), facts found 10,312 → 10,326 (the 14 the investigation counted); among the claims, right 11,355 → 11,396, misbound 223 → 285, misread 35 → 50, inexact 124 → 138.
    - First built with a kept claim's task answered complete: then its text wasn't read again in parts (bounded refinement), which a dropped claim's partial task had been, and recovered quoted claims; facts found fell to 10,303. Its task stays partial either way now, and is read again in parts as before.
    - Off: the corpus gains 14 facts for some 90 claims more misbound, misread or inexact, each marked. On real documents more may be at stake (the IEA report's materials table, 71 claims).

## Moved in: *Runtime quality spot checks*

The tentative row, as it stood on 2026-11-06:

The owner, 2026-10-09: "I'm beginning to believe that having some sort of quality heuristics spot-check for runtime behavior would be useful for both confidence decisions and part of the report." Cheap checks a run makes on itself, without keys or judges, such as image tiles answered empty, lines cut by a tile, quotes not found in the text layer, tasks failed or cut short, tables whose rules were rejected. Each is a signal for a claim's or a region's confidence, and the report would show the run's own quality summary. The lab already measures some of these offline (lines cut by a tile, `bench/tiling.py`; the refinement bench's checks, `bench/refinement.py`). The first in the product, tiles complaining of cut text, is [text cut by tiles](text-cut-by-tiles-2026-10-28.md)' milestone 1 (2026-10-28). <br>- **Claim quality signals, from the closed [scheduling](scheduling-and-triage-2026-09-23.md) plan (2026-10-21; its milestone 7):** three axes kept apart, never one opaque score: reliability (native or visual, `quote_verified`, passes agreeing, `approximate`, retry depth, model confidence weighted least), specificity (a number with a unit, stated conditions, a specific entity, a requirement against a capability or a hedge) and salience (references to the entity across the source, section type, repetition across files; the riskiest, labelled so). For scheduling, sorting and filtering (filtering once calibrated), each component shown, never hiding evidence; derivation shown beside them, not an axis; weights from reviewers' marks (*Reviewer feedback*). Also situating's reference check telling references to other documents apart (`calg_cd.pdf`'s building-code tables, "Table 26.9-1"), so an unresolved reference still points at a missed figure ([milestone 4's review](README.md#retired)).

**It was waiting on:** [Weighted quality estimates](#tentative) for combining the signals
