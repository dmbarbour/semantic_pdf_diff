# The run's reading, counted: where the report deserves less trust

- **Status:** Active (2026-11-06): [milestone 1](#1-a-pages-reading-counted) built 2026-11-06; 2 and 3 not begun.
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

## Moved in: *Runtime quality spot checks*

The tentative row, as it stood on 2026-11-06:

The owner, 2026-10-09: "I'm beginning to believe that having some sort of quality heuristics spot-check for runtime behavior would be useful for both confidence decisions and part of the report." Cheap checks a run makes on itself, without keys or judges, such as image tiles answered empty, lines cut by a tile, quotes not found in the text layer, tasks failed or cut short, tables whose rules were rejected. Each is a signal for a claim's or a region's confidence, and the report would show the run's own quality summary. The lab already measures some of these offline (lines cut by a tile, `bench/tiling.py`; the refinement bench's checks, `bench/refinement.py`). The first in the product, tiles complaining of cut text, is [text cut by tiles](text-cut-by-tiles-2026-10-28.md)' milestone 1 (2026-10-28). <br>- **Claim quality signals, from the closed [scheduling](scheduling-and-triage-2026-09-23.md) plan (2026-10-21; its milestone 7):** three axes kept apart, never one opaque score: reliability (native or visual, `quote_verified`, passes agreeing, `approximate`, retry depth, model confidence weighted least), specificity (a number with a unit, stated conditions, a specific entity, a requirement against a capability or a hedge) and salience (references to the entity across the source, section type, repetition across files; the riskiest, labelled so). For scheduling, sorting and filtering (filtering once calibrated), each component shown, never hiding evidence; derivation shown beside them, not an axis; weights from reviewers' marks (*Reviewer feedback*). Also situating's reference check telling references to other documents apart (`calg_cd.pdf`'s building-code tables, "Table 26.9-1"), so an unresolved reference still points at a missed figure ([milestone 4's review](README.md#retired)).

**It was waiting on:** [Weighted quality estimates](#tentative) for combining the signals
