# Remediating the review's larger bugs

- **Status:** Active (2026-10-09). The order is agreed. Items 1–4 (the review's) are done; the trials' two bugs joined as items 5 and 6 (the owner, 2026-10-09). Item 5 is designed and next; item 6's design waits on the owner's answers.
- **The owner, 2026-10-09:** "We'll focus on bugfixes, then architecture, then new features, except in cases where a bugfix would be much easier after an architecture fix (if you recommend them). To explain this order: I'm not fond of mixing bugfixes (behavior modifying) with architecture updates (behavior preserving), nor of trying to preserve known bugs. For the larger bugs, please develop a remediation plan."
- **From:** the [code review of 2026-10-08](../reviews/code-review-2026-10-08.md), "Still open". Its small fixes are done; its "Fixes so far" section lists them.
- **Then:** the behaviour-preserving phase: performance with requests byte-identical, then the architecture moves (see [After the bugs](#after-the-bugs)).

## Rules against drift

- **Only the items below.** Anything else found on the way is listed under *Found along the way* and not fixed now: a bug goes to the end of this plan, a new direction to a tentative index row.
- **No refactoring mixed in.** A fix changes only what its behaviour needs. Moves and clean-ups wait for the architecture phase, even where they would be natural.
- **Each fix has a test that fails without it.** Commit after the full suite passes.
- **Reader versions are bumped** wherever a reader's output changes, so stores re-read.
- **Requests that change are named in the commit.** They're re-recorded once, at the end (see [Re-recording and measuring](#re-recording-and-measuring)).

## Architecture first? No, for all four

- None of the four is much easier after an architecture move. Each fix is local.
- **B2 is the nearest case.**
  - Its root is a table block carrying two forms of its rows: the raw rows and the grid, joined by keys (the review's architecture item 6).
  - The fix makes the grid the only form that's read. That takes three call sites, and the keys still link the two forms.
  - Item 6 then removes the raw rows from the block, as a pure move.
- **D2 could later become one three-way alignment.** The `Alignment` object (item 11) would make that easier. That's a design change to measure, not a bug fix, so it's listed as an option below.

## Items, in order

### 1. E3: lab scoring sees every format

**Done (2026-10-09).** The owner: "Please proceed with E3." What was built:
- **`eval/documents.py`**, the lab's one view of a stored document:
  - `contents(store)`: every content whose extension has a reader
  - `Document`: a PDF's pages; an image's pages as its reader laid them out, under the store's bound `tile_points` and `image_side`; a text format's lines, with the headings above a line
- **Rounds:**
  - units and mechanical measures read every format
  - a text format's unit has no image; its page text is its lines, cut into bands by line
  - judges are told a text unit has no page image (`judging.TEXT_FORMAT`); image units keep their layout for `rerender`, which restores every format from the slices
- **Review batches:**
  - every format's claims are sampled
  - a text format's claim is shown as its lines, the claim's own marked, in `texts` (on the review page and in the panel's prompt)
  - a Word picture's crop is the run's own image, found by its hash
- **Product (behaviour-preserving, for the lab):** `textdocs.read_text` (the readers' parsing, which `text_job` now calls) and `Store.interpreter(role)`.
- **Found while fixing:** the units already collected text formats, but a batch with one would have failed: every document was opened as a PDF.
- **Unchanged:** PDF batches and prompts, byte for byte (the rounds tests rerender and compare them).
- **Test:** `tests/test_lab_documents.py`: a PDF, a Markdown file and an image through units, measures, batches, context, rerender and review samples.

- **The bug** (lab only):
  - The rounds' units (`eval/rounds/units.py:62-63`) read PDFs and text formats, but not images.
  - The mechanical measures (`eval/rounds/measures.py:55`) read PDFs only.
  - Review batches (`eval/review.py:95,103`) sample PDF claims only, and render every view from a PDF page.
  - Levers that act on other formats are therefore measured on PDFs alone.
- **Fix:**
  - **One lab helper** for "every content a reader reads", keyed by `extract.READERS`. Units, measures and review sources all use it.
  - **Review views by format:**
    - PDF: as now.
    - An image: rendered through `extract.image_pdf`, so it's the same page the reader saw.
    - A text format (Word, decks, sheets, plain text): the claim's source lines, shown as text in place of a page image. Text locators are lines, not boxes.
- **Effects:**
  - No product change and no requests.
  - Rounds gain units from images and text formats. Past rounds' recorded numbers stay as recorded. A round compares variants on the same units, so its baseline and variants both include the new units.
- **First** because the later fixes (B5 especially) act on sheets and Word, and the rounds should see them.

### 2. D2: revisions with unchanged files

**Done (2026-10-09).** The owner: "Okay. Record the option as a lever, then fix D2." What was built (`compare.py`):
- A claim aligned in any pass is "not compared" (or its pairs' outcome), never "possibly added or removed".
- `_combined` merges the passes' groupings: unaligned groups keep only the claims no pass aligned, groups of shared claims alone are dropped, and a group both passes formed is listed once.
- Each alignment summary names its pass; they stay two, since their counts can't be added (an item can be in both).
- **Test:** `test_align.Report`: the reproduction below, whose statuses, groupings and pairs are now the same with the unchanged file as without it.
- **Measured:** no corpus run. No requests change, the committed comparisons hold no alignment summaries, and the controlled revision pairs have no unchanged files.
- **The three-way alignment:** recorded as a lever idea in the [lever index](../reviews/levers.md).

- **The bug:** `compare` aligns in two passes, so that shared (unchanged) content is never compared with itself:
  - pass 1: earlier unique against later unique plus shared
  - pass 2: shared against later unique

  The passes' outcomes are then combined wrongly:
  - **Statuses are unioned.** A later claim aligned in pass 1 but lone in pass 2 is reported "possibly added or removed", not "not compared".
  - **Groupings contradict.** The same claim sits in an aligned group from one pass and an unaligned group from the other.
  - **The report shows two alignment summaries,** unlabelled.
- **The review's proposed fix, not taken:** one alignment over (earlier + shared, later + shared).
  - Shared claims would align with their own twins, competing for the counterpart role. A changed file's claim that is restated in an unchanged file could then show as removed, where today it's matched; `compare`'s docstring calls that match intended.
  - It would also realign all the shared content, and alignment is quadratic in places (D3, D4).
- **Fix, keeping the two passes:**
  - **A claim's status comes from every pass it took part in.** It's "possibly added or removed" only if no pass aligned it; aligned in any pass, its status is "not compared" or the outcome of its pairs.
  - **Groupings are merged.** A claim's "unaligned" group is dropped where another pass aligned it.
  - **The alignment summaries labelled** by pass.
  - **Groupings of shared claims only are dropped.** Unchanged content listed as "unaligned" says nothing.
- **Reproduced (2026-10-09):**
  - **Setup:** a changed file plus one unchanged file (a fan, F-1).
  - **The later pump P-1** gains a new attribute (NPSH, claim Y-3), in an item that pass 1 aligned with the earlier pump.
  - **Without the unchanged file:**
    - Y-3 is "not compared".
    - The groupings are: P-1 matched, M-7 unaligned (removed), V-9 unaligned (added).
  - **With it:**
    - The same pairs are judged. The alignment isn't hindered.
    - Y-3 becomes "possibly added or removed".
    - The later pump's claims are listed as matched and as unaligned.
    - V-9 is listed unaligned twice.
    - The unchanged fan is listed unaligned in both directions.
    - The report shows two alignment summaries.
- **Effects:** no requests change (the pairs judged are the same). Only the reports' statuses, groupings and summary change. Saved comparisons keep what they said.
- **Test:** the reviewer's reproduction: a revision with one unchanged file, and a later claim aligned in pass 1 but lone in pass 2.
- **Later option:** a three-way alignment (earlier against later, with shared content open to both sides, never paired with itself), measured on revision pairs after the `Alignment` object exists. Recorded as a lever idea in the [lever index](../reviews/levers.md) (the owner, 2026-10-09).

### 3. B2 (with B10's wording): table rows read by themselves come from the grid

**Done (2026-10-09)** as designed below:
- **What was built:**
  - `tablerules`: `SectionRow`, `possible_notes`, `noted`, the POSSIBLE NOTES line, `Rules.notes`.
  - `tables.pdf_grid`: `joined`.
  - The PDF and text table paths read the grid's rows and notes.
  - The structure prompt's union is said.
  - Readers: pdf/7, docx/7, pptx/6, xlsx/11, csv/7.
- **Tests:** `tests/test_table_rows.py`. The misfit path isn't tested apart: it calls the same `by_itself` as the "rows" path.
- **Re-recorded** (2026-10-09, the dev runs only), here and not once after B5: the owner asked for B2 to be fixed now, and a commit needs the replay to pass. B5 will re-record its own blocks.
  - 563 calls, $0.174, most of them the structure queries' new wording.
  - 489 unused answers pruned.
- **Measured on the controlled corpus** ($0.035):
  - **Only PDFs changed.** The other formats' tables have no wrapped rows or one-cell notes with numbers.
  - **Standard runs:** claims 4100 to 4103; right 3287 to 3295; loose 426 to 416; misbound 203 to 205; misread 24 to 25; hallucinated 6 to 8.
  - **Tables read row by row:** right 3395 to 3398; loose 418 to 406; misread 28 to 25; misbound 195 to 196; hallucinated 6 to 8.
  - **Revision pairs:** changes found 119 to 120 of 120; unchanged confirmed 2839 to 2841 (row by row: 100 to 101 of 101).
  - **Where:**
    - The sequence diagram that table detection takes for a table (attach-s1): the table reader's right claims went from 2 to 17, its rows now read with their lines joined. One join of cut labels ("cache lifetime 5" + "s) 72 s)") was read as 72 s, hallucinated; the fact is 572 s.
    - Room labels on the rotated floor plan, detected as small tables: three dimensions once loose are now misbound (a width read as a height).
    - Both are pseudo-tables: the lever idea "recognise charts and diagrams parsed as tables" in the [lever index](../reviews/levers.md).

- **The bug:** a table's rules see its grid, but rows read by themselves come from the raw rows (`tables.py:57-76`, `tablerules.py:140-158,844-847`, `extract.py:527-553`, `textdocs.py:392-407`). Reproduced (2026-10-09) on a PDF table with a "Pumps" section row, P-2's service wrapped onto a second line, a one-cell note "Note: P-2 is rated 95 L/s at 28 m ..." and P-3 below it.
- **Part 1, wrapped rows (a consistency bug):**
  - **The problem:**
    - The grid joins P-2's continuation line ("Condenser water, standby duty"), but a row read by itself is the raw first line ("Condenser water,").
    - This happens on every path that reads rows by themselves: a "rows" answer, rows that misfit the rules, rules failing twice or failing outright, an image mismatch.
    - On the path without rules, the continuation line is also read alone, as a fragment.
  - **Fix:**
    - Every path reads the grid's rows.
    - A row the grid joined is read whole: its lines' cells joined, and its box the union of theirs. Any other row is read exactly as now, so its request doesn't change.
    - Tags keep the raw index of the row's first line.
    - A PDF table whose rows lack boxes has no grid and is read as now.
- **Part 2, one-cell rows (a heuristic misfiring on a hazard):**
  - **The problem:** a row holding only its first cell (in tables of three columns or more) is a section label for the rows below. A note is classed the same way:
    - **Its facts are never read:** labels aren't rows, so no path reads it (only the path without rules, which reads every raw row).
    - **It labels the rows below:** the reproduction files P-3 under the section "Note: P-2 is rated 95 L/s ...", which the rules query is told labels P-3. P-3's claims can carry it, e.g. as a condition.
  - **Design** (as in B5 and decision 0023: our heuristics propose, the model decides), in the owner's words of 2026-10-09: "Yes, update the plan that way, then fix B2.":
    - **The proposal:** a section row holding a number is a possible note. The rules query lists such rows in a "POSSIBLE NOTES" line, only when a table has them, and asks for any that are notes by row number in a new `notes` field.
    - **Confirmed notes:**
      - Each is read by itself.
      - It labels nothing: the rows below it take the section above it.
    - **No answer** (the rules query failed or wasn't reached): the proposal stands, and the possible notes are read by themselves.
    - **The path without rules:** possible notes are read by themselves; digitless section rows are no longer asked alone.
    - **Unconfirmed rows** stay labels.
  - **Requests:** the rules query changes only for tables with possible notes. The answer has no JSON schema in the request (`response_format` is "none" by default), so the new field changes nothing else.
- **B10's wording, folded in:** the structure prompt's "and/or" (read as an intersection; the code takes the union) says union. It changes only the structure query, and it's re-recorded with B2's changes.
- **Effects:**
  - Row prompts change for wrapped PDF rows.
  - Confirmed notes (or, without an answer, possible notes) are new row tasks.
  - The rules query changes for tables with possible notes.
  - On the path without rules, continuation lines and digitless section rows are no longer asked alone (fewer calls).
  - Reader versions: every format whose tables reach the grid (pdf, docx, pptx, xlsx, csv).
- **Tests:**
  - a wrapped row read whole on the "rows" path and on the misfit path
  - unwrapped rows' requests and tags unchanged
  - a confirmed note read by itself, labelling nothing
  - an unconfirmed possible note left a label
  - possible notes read when the rules query fails
  - the path without rules reading grid rows and possible notes
  - a Word or sheet table's note

### 4. B5: label and value blocks

**Done (2026-10-09)** as designed below. The owner: "Please proceed with B5." What was built:
- **`keyvalue.py`:** `candidate` (the heuristic), the key-value check (`question`, `Check`), and `read`, which asks and then reads the block as a table or as "key: value" lines.
- **Readers mark candidates:** sheets and CSV (not a defined table, one header row), Word (one header row, not marked to repeat). PDFs are checked in `proceed`, before the rules query, with the table's crop.
- **A key-value list is read by a text task** (`text:p<n>:kv<table>`), each line placed on its row. It's given the context a table row gets ("Above the table", the headings), since a text block's context leaves out the block's caption: without it, the clearwell was read as "tank/basin".
- **Traced:** a `key-value-check` step in every claim's derivation, on both readings (`tablerules.read` takes a list of source steps).
- **A guard found by measuring:** a PDF table of one row is read with its header as its body. 169 of the corpus's 178 PDF candidates were such phantoms, most of them a header cell PyMuPDF detects as a tiny table of its own ("Rating | (psi)"). A block whose rows all repeat its header isn't a candidate.
- **Readers:** pdf/8, docx/8, xlsx/12, csv/8. Decks aren't marked (not in the design; see *Found along the way*).
- **Tests:** `tests/test_key_value.py`, 12 tests. Eight fail without the fix; one guards a slip of mine on the way (refined text parts were given their parent's context).
- **The measuring knob:** the corpus had no key-value list (its two-column blocks are real tables: Field / Length (bits), a one-series chart's data, Area / Valves). So a new clean project was added, `wtp-datasheets-s1`, in every format:
  - Three pump data sheets, each headed by the pair "Pump | P-201A".
  - A clearwell data sheet whose first row is a fact ("Volume (MG) | 4.2").
  - A real two-column table with a header (chemical storage).
  - No header styling on the data sheets in any format.
- **The model's checks, 2026-10-09:** 36 a run, the 35 on real tables and data sheets all right.
  - Every real table was read as a table: Field / Length in 17 documents, Peak Loads ×2, Area / Valves, chemical storage ×3.
  - Every data sheet was read as a key-value list, in PDF, Word and the workbook.
  - The drawing pseudo-table (lcc-plan-s1-clean) was read as a key-value list (its title block's labels and values).
- **Measured on the controlled corpus** (before: the committed code on the new corpus):
  - **Word and workbook data sheets** (the bug): 18 right of 21 claims, recall 0.947 (the clearwell's volume lost as a header), became 19 right of 19, recall 1.0. Read row by row: the workbook went from 19 of 22 to 19 of 19; Word's was unchanged at 18 right, one misbound, 3 fewer claims.
  - **PDF data sheets:** every fact found before and after; 4 fewer duplicate claims.
  - **The pseudo-table:** one claim more, misbound.
  - **Totals:** PDF right 3330 to 3326 (the duplicates), misbound 208 to 209; docx right 1572 to 1573; xlsx 979 to 980; Markdown and decks unchanged.
  - **Revision pairs:** changes found 120 of 120 both; unchanged confirmed 2841 to 2843 (lcc-plan, 33 to 35 of 35).
- **Spent:** $0.26 in all.
  - Corpus: $0.036 for the before run and $0.026 for the after runs.
  - Slices re-record: $0.20. Of that, $0.164 was wasted on the refinement-context slip above, its answers pruned. About $0.03 went on phantom checks in a recording stopped to add the guard.

- **The bug** (`xlsxdocs.py:176-186`, `docxdocs.py:381-400`):
  - A sheet splits narrow pairs off only when a wider table follows them.
  - A two-column block standing alone becomes a table, headed by its first row. Word does the same with any two-column table.
  - So in "Pump | P-2", "Flow | 95 L/s", "Head | 30 m", the first pair is the header. "P-2" is never read as a value, and the other rows are read under the labels "Pump" and "P-2".
- **Choices offered:** (a) a two-column block whose left column holds no numbers, and whose header isn't marked, read as pairs (recommended); (b) keep the table and also read its first row as a pair when it holds a digit or its label ends with ":".
- **The owner, 2026-10-09:** "Regarding the B5 choice, I think that you recommendation is a good heuristic to start, but you should still be asking a model (likely vision) to confirm the proposed 'rule' for reading a table."
- **Design** (as decision 0023: our heuristics propose, the model decides):
  - **Candidates:** (a)'s heuristic marks them.
    - The block has two columns, its left column holds no numbers, and no header is marked. A sheet's defined table and Word's repeated header rows are marked headers.
    - Only candidates are asked, so no other table's requests change.
  - **One small query per candidate: the key-value check.**
    - It shows the block's rows as lines and the text just above it, and states the proposal: "a key-value list, as on a form or data sheet: each row is a key (column A) and its value (column B), the first row included".
    - It asks which reading holds: `{"reading": "key-value" | "table", "why": "..."}`. "table" means the first row is a header naming the columns below.
    - **Naming:** the owner, 2026-10-09: "I'm not sure "pairs" is the best word here, it doesn't seem conventional and might confuse a model about what you're pairing, is there a more common naming for this layout?" "Key-value pairs" is document AI's usual term for this layout (forms extraction, e.g. AWS Textract, Azure Document Intelligence). The sheets' internal "pairs" region kind keeps its name until the architecture phase (a rename is behaviour-preserving).
  - **Vision where there's an image** (both points agreed by the owner, 2026-10-09: "We can go with 1 and 2 decisions for now"):
    - Sheets, CSV and Word have no page image; nothing lays them out. Their check is text alone. Rendering them, styles included, would be a feature of its own.
    - PDFs are included: a two-column PDF table is headed by its first row too (`extract.py:478`). There the check is sent the table's crop, already rendered for the rules query.
  - **The outcome:**
    - **"key-value":** the rows are read as "key: value" lines by a text task, as sheets already read the label-and-value rows above a table.
    - **"table":** the block is read as a table, as now (the rules query).
    - **A failed check:** the heuristic's proposal is used (key-value), and the task is recorded as partial with the error.
    - **Not reached** (a call limit, an answer not recorded): recorded as not reached, and asked on the next run.
  - **Traced:** a `key-value-check` step in each claim's derivation says what the model answered, or that it wasn't confirmed.
  - **Where:**
    - Readers mark candidates on their table blocks; the check is asked when the job reaches the block (`text_job`).
    - For PDFs, the check is asked before the rules query.
- **Measured:**
  - A knob in the controlled workbooks and Word documents: a label and value block standing alone, with a pair as its first row and with a real header. Added only if the corpus has none.
  - Scored before and after on the controlled corpus, with the checks' answers and cost counted.
- **Effects:**
  - Reader versions xlsx, csv, docx and pdf.
  - Requests change for candidate blocks only: one check each, then their reading.

### 5. Trials finding 1: `--fixture` with a new file

- **The owner, 2026-10-09:** "Let's go ahead and add those to pre-architecture. Fixing fixture should be a relatively simple fix, but the slicing seems a bigger task that needs careful design, an approach to measuring improvements, etc.."
- **The bug** ([trials](../reviews/trials-2026-10-08.md), finding 1): `--fixture new.sqlite` fails with "no such fixture", because the default mode, `replay`, never creates a file. The error comes after the sources are scanned and the store bound.
- **Fix** (the trials' proposal):
  - **A fixture named without a mode** records and replays (`replay-or-record`), creating a `.sqlite` file. A `.zip` (or a folder) is replayed, as a `.zip` can't be recorded into.
  - **Strict replay stays explicit,** `--fixture-mode replay`, for tests and CI. The scripts pass their modes already. `test_fixtures`' replay tests now say `replay`.
  - **Checked first:** a fixture that can't be opened as asked fails the run before the store is bound or a source scanned.
  - The help text says what each mode does and that a new file is created.
- **Later:** this folds into finding 2's per-user cache (the cache becomes the fixture format), a design for the architecture phase's configuration work.
- **Tests:** a new `.sqlite` named alone is created and recorded into; a missing fixture under `replay` fails before scanning, the store left as it was; a `.zip` named alone replays.
- **No requests change;** nothing to re-record.

### 6. Trials finding 5, cause 1: refinement cuts a tile through its text

- **The owner, 2026-10-09** (above): "the slicing seems a bigger task that needs careful design, an approach to measuring improvements, etc.."
- **The bug** (`extract.py`, `Visuals.refine`): a tile answered partial or failed is halved at its midpoint along its longer side, with 12 pt of overlap.
  - The halves aren't grown to whole lines, and each half's text layer is clipped to the half-lines (`get_text(clip=…)`). So the model gets fragments in both the image and the text.
  - Bands are wider than tall, so every refined band is cut vertically, down every line. On the public samples: 5.7 lines cut on average, and 336 of 822 bands have 5 or more lines cut.
  - In the slices fixture, 28 of 36 refined halves answered with no claims.
- **Scope:** refinement only. Where tiles are first cut (grid tiles on wide pages, decoration counted as graphics, text-only grid tiles) stays with the tentative tile-selection plan.

**Design (proposed):**
- **Where to cut:** in whitespace, not at the middle.
  - **Candidates:**
    - Horizontal gaps between text lines.
    - Vertical gaps between columns: x-ranges no line and no graphic crosses.
    - Both are taken from the page's lines (`pages.lines`) and graphics (`segmentation._graphics`) inside the tile.
  - **Choice:** the candidate crossing no line, nearest the middle, with each half at least 25% of the tile.
    - Ties go to the cut along the shorter side, so a band is cut between lines, not down them.
    - If no candidate crosses no line, the one crossing the fewest is taken, then the middle as today. A drawing with no text keeps today's cut.
- **The halves:**
  - Each half is grown to the whole lines it touches (`segmentation.grown`), so a line cut by an overlap is read whole in one of them.
  - Its text layer is taken by whole lines (lines whose centre lies in the half), not clipped.
- **Unchanged:**
  - Refinement still happens only on partial or failed tiles, with the same depth and minimum size.
  - Overviews and figures still aren't refined.
  - Word pictures (no text lines) keep the middle cut.
- **Version:** the PDF reader's (refined tiles' requests change); nothing else.

**Measuring (proposed):**
1. **Without the model, on the public samples' first 40 pages each** (the trials' 803 pages): every band and grid tile refined once, as if partial. Counted, before and after:
   - lines cut by each half
   - halves holding no text and no graphic
   - each half's share of its parent
   - Today's figures: 5.7 lines cut per refined band on average, and 336 bands with 5 or more.
2. **With the model, on the halves themselves:** refinement is rare in a run (36 refined tiles in the slices fixture), too few to judge.
   - So the measure forces it: a lab-only switch refines every tile of chosen pages once, whatever its answer, both ways.
   - Pages: the trials' worst bands (HabEx p4, the cut-lines leaders) and the controlled corpus's tiled pages.
   - Compared per parent tile:
     - empty answers among the halves (today 28 of 36)
     - claims per half, and right claims where a key exists (the controlled corpus)
     - the halves' claims judged against the parent tile's (the rounds' pairwise judge, both orders)
     - cost per right claim
   - About 200 parent tiles, so about 800 half requests over both cuts: under $0.50.
3. **The usual runs after:** slices re-recorded (dev only), the controlled corpus run and scored.

**Questions for the owner:**
1. **A fix, or a lever?** The bug phase replaces behaviour, measured before and after (as B2 and B5). A lever choosing the cut would be a feature (the owner's order, 2026-10-09). I'd make it a fix: the middle cut has no case where it's the better choice by design, and the measure above compares both anyway.
2. **The forced-refinement switch:** a lab-only setting, not a product setting. Is that acceptable for measuring, or should the measure use only refinements that happen naturally (fewer cases, longer to gather)?
3. **The 25% minimum share for a half:** a guess. With it, a band with one long paragraph at its top and a figure below cuts between them, not in the paragraph. Without a whitespace cut that meets it, today's middle cut stands. Should a smaller share be allowed before falling back?

## Re-recording and measuring

- **Once, after items 3 and 4** (in the event: after item 3, and again for item 4's blocks; see item 3):
  1. The slices fixture: the dev runs only. Unpack the zip, note the time, run `record_runs.py --set dev`, prune answers unused since then, and pack.
  2. The controlled corpus re-run, then scored and compared with the committed results.
- **Expected cost:** cents. The changed requests are a small share; the earlier re-record cost $0.25 only because it recorded the held-out runs.
- **Reported in the review's "Fixes so far":** per format, what changed (claims, misbound, missed), and the requests added and removed.

## After the bugs

The owner's answers of 2026-10-09, placed in the agreed order. Each phase is another plan or the review's own order; they're listed here so nothing is dropped.

- **Behaviour-preserving, next:**
  1. **Performance, requests byte-identical** (the review's C2, A5–A8, P1, D3–D5, E1).
     - C2's durability, the owner's answer: "I think it's safe to reduce durability of commits. This system is designed to resume from what is known to be committed, IIRC. The main exceptions should be the things humans manipulate manually, e.g. adding/removing items to project, updating configurations, etc."
       - Checked: a task's row and claims commit in one transaction (`Store.record_task`). A transaction lost to a power cut is a task asked again, its answer usually still in the fixture.
       - The store: WAL with `synchronous=NORMAL`.
       - The fixture: WAL with NORMAL too, checkpointed before packing. It uses the default rollback journal today, and NORMAL without WAL can corrupt a file on a power cut.
       - The writes people make are committed at FULL: sources added or removed, binding and resets, the reconcile setting, `gc`, and configuration once it's in the store.
       - The diagnostic writes are batched into the next task's transaction.
       - A decision record when it lands.
  2. **The architecture moves,** in the review's order (items 1–13).
- **Features, after:**
  - **A20 as a lever.** The owner: "We can add skipping table detection as a lever, np." It skips table detection on pages recognised as drawing sheets, and is measured like other levers.
  - **The trials' plans:** configuration in the store, the progress display, tile selection.

## For the owner

- **B5, answered 2026-10-09** (above): PDFs included with their crop; sheets, CSV and Word checked by text alone; "key-value" proposed in place of "pairs".
- **The trials' bugs, answered 2026-10-09:** both join, as items 5 and 6. The rest of finding 5, and findings 2–4, stay with their plans.
- **Item 6's three questions** (above): a fix or a lever; the forced-refinement switch for measuring; the minimum share of a half.

## Found along the way

- **Decks' two-column tables aren't checked** (B5, 2026-10-09): B5's design named sheets, CSV, Word and PDFs. A deck's table of two columns is headed by its first row as Word's was. Decks would need only their reader to mark candidates (`pptxdocs.py`'s table), a reader version and a measure; the corpus's decks have none.
- **A section row right under a PDF table's header is taken for the header's second line** (B2's tests, 2026-10-09): `pdf_parts` merged "Pumps" into "Tag" ("Tag Pumps"), so the rows below it lose their section label and the first column's header is wrong. Not fixed here; a bug for after this plan's items, to be confirmed on real tables first.
