# Remediating the review's larger bugs

- **Status:** Active (2026-10-09). The order is agreed. Items 1 (E3) and 2 (D2) are done; B2 is being fixed; B5's design is settled (2026-10-09).
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

## Re-recording and measuring

- **Once, after items 3 and 4:**
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
- **The trials' bugs:** they were deferred on 2026-10-08 ("before working on these, we'll focus on the architecture and bugs found in your review"). Should they join this plan's bug phase?
  - **Trials finding 1:** `--fixture` with a file that doesn't exist yet fails; the default mode, `replay`, can't create one. A small fix.
  - **Finding 5's refinement cut:** a failed tile is halved down its middle, through its text. A small fix, measured.
  - The rest of finding 5, and findings 2–4, are design work and stay with their plans.

## Found along the way

(Nothing yet.)
