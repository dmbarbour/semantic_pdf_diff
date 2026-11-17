# 0024. A PDF table's structure: heuristics first, then rules a model writes where lines are suspect

- **Status:** Accepted (2026-10-07; amended 2026-10-10, 2026-11-17: rows read as one parted, labels joined)
- **Source:** [one table model](../plans/README.md#retired): decision 1 (2026-09-30), "PDF tables onto the rules path, in detail", "Structure rules, in detail" and its progress

## Context

A PDF's tables come from a parser that guesses cells from drawn edges and text: it splits a cell's lines into rows (taking shading boxes' edges for row lines), splits two-line headers, stacks tables into one and draws columns through words. On the controlled PDFs, 254 of 394 tables failed a check against their image, nearly all on structure.

## Decision

- **Cell text comes from the text layer, never retyped by a model; vision checks it.** The owner (2026-09-30): "Perhaps assume it is, but verify at least one row via vision?" The rules query gets the table's image and copies a row of values from it; a disagreement sends the rows to be read one by one.
- **Heuristics first, no model** (`tables.py`): rows joined across boundaries without a drawn rule in a mostly ruled table; two-line headers merged (a row of its first cell alone, under a filled first header cell, kept a section row: amended 2026-10-10, on every table in the samples); a stacked table, styled as the header, split off; columns joined where every split word is cut; wrapped cells joined.
- **Then structure rules, only where a line is suspect** (`tablestructure.py`, `table_structure`). The owner (2026-10-07): "Ideally, we'd not provide the full table in bands for processing via vision, instead getting some comprehensible suggestions/rules about how to work around confusing formatting, with feedback similar to how we approach claims rules."; then "The recommendations look good, please proceed":
  - a separate query before the claims rules
  - rules from a closed vocabulary (a condition from the lines' signals, or lines named, and an action), applied mechanically, checked against rows copied from the image, reviewed
  - only for parts with suspect lines
- **A part the model reads as no table** (a chart, a floor plan) is read as a figure instead.
- **Repair comes after rules, where measured,** rather than a repair query for every table (the owner, 2026-10-07: "The recommendations look good.").

## Consequences

- On the controlled PDFs (2026-10-08): image-check failures 254 of 394 to 24 of 399 (the check compares a row of values only: header cells the parser took for tables of their own had made most of the failures), misbound claims 229 to 205, hallucinated 7 to 6, facts as before.
- Columns are joined mechanically only where every split word is cut; a model's column joins in the wrong place weren't caught by whole-text examples, so a body row's separate values are never joined.
- The layout add-on (`pymupdf-layout`) was measured and not adopted: no gain over the heuristics, 261 MB of dependencies.
- New hazards become signals and actions in the vocabulary, each measured on the corpus and the development slices.
- **The section row under the header (2026-10-10):** every table PyMuPDF detects in the samples and the corpus (4,187 pages), mended as extraction mends it, logged 153 header joins in 18 documents, 29 of a row holding only its first cell. The 14 of those under a filled first header cell were all section or title rows, none a header's second line ("HabEx Coronagraph (HCG) – Channel A" under "Instrument", HabEx p. 182). Under an empty first header cell such a row can be one ("Parameter", HabEx p. 369), so those join as before.

## Amended 2026-11-17: rows read as one parted, labels joined

From [indexes and glossaries](../research/indexes-and-glossaries-measured-2026-11-17.md) (design questions 6 and 8, built 2026-11-02; recorded when that plan was retired). The owner, 2026-11-02: "For the split rows, I agree that we can apply heuristics for reading a table and splitting things. If everything fits together neatly, we can reasonably give that some weight. But we should also be willing to ask a model what the author is trying to say if it's confusing. Perhaps an "is this the correct reading of that" question in some form, not sure. I doubt re-reading each merged row independently would help, but this does fit under doubted reads/claims."; "Nice work! Yes, please develop that check for suspect joins."; "Yes, let's turn that on by default."

- **Where it fits neatly, by code:** two lines each starting with a tag of their own, of one shape, stay apart (`tables.tagged_apart`); a line whose first cell starts with its own tag and spans the columns is parted at the column lines where a line beside it holds a tag of that shape (`tables.parted_across`).
- **Where it's confusing, the model asked:** two lines joined across an unruled boundary, each with its first cell filled, make the table part a structure suspect, shown to the model as the code reads it with its image, to keep or regroup (`labels_joined`, a default since 2026-11-02).
- **No re-read row by row:** claims still naming several items stay counted for none ([0046](0046-one-source-analyzed-with-indexes-of-what-was-read.md)) and among the second pass's doubted claims.
