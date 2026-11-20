# Requirements and textual claims: tables of statements read whole, compared across proposals

- **Status:** Active (2026-11-18; the owner: "Proceed."); its design questions answered the same day (below), the plan revised for them. Milestone 0's counts in `debug` built the same day (0.73.0); milestone 1's silent losses fixed (0.73.1, 0.73.2); milestone 2's reading built, off (0.74.0: `statement_tables`).
- **The owner, 2026-11-18:** "Do we have anything on the docket useful for comparing requirements and capturing more textual claims? I have a LOT of claims in the form of requirements tables that aren't numerical in nature in my actual corpus, and I feel we've a long way to go to properly extract and compare such claims."
- **The owner, the same day:** "Please write up the plan." Two sample tables, both to be "compared across proposals, and the columns will certainly NOT match exactly":
  - **One copied from a Cameo model to Excel:** Provider, Requirement table name, ID ("FOO-REQ-112"), Name, Text ("usually one sentence containing 'shall', sometimes blank"), Rationale, Verification Method ("Test, Inspection, Analysis, Demonstration, or a combo"), Requirement Status and Compliance ("all blanks"), Derived From ("a list of other requirement names"), Classified, Refined By, Refines, Owner, Satisfied By, Comment, Stakeholder Requirement, Verification Event.
  - **One from outside Cameo:** Temporary UID ("FOOv0.0-001"), Condition ("In event of X"), Subject ("the X"), Verb ("SHALL"), Clause(s)/Content ("continues sentence, sometimes adds more sentences"), REQUIREMENTS NOTE ("discussion of recommended changes to requirement"), "Several miscellaneous columns".
  - "Anyhow, we'll certainly need a model to make sense of how to read these tables."
- **The owner's answers to the first draft's questions (2026-11-18):**
  - **Reading rows:** "I suspect you're assuming too much stability if you want any built-in rule on how to read table rows. We'll either need a model's help to understand how to read a row in a given table, or we'll need a generic approach that works across many tables."
  - **"Will":** "I'd count 'will' as a claim or intention. We're ultimately using requirements to understand what a document is claiming about a system."
  - **Which columns are compared:** "You're overly specializing again. Don't count on that one table example as being canonical. It's just one example."
  - **The form:** "The table I mentioned prior was a copy-paste from one Cameo model to Excel. The table above was requirements from outside Cameo."
  - **Other columns:** "In the one sample, I mentioned all the columns, but I wouldn't assume that's all columns we might use in a requirements table."
- **Takes over** the tentative row *Requirements and textual claims* (2026-11-18) and its nine lever rows.
- **Builds on:**
  - tables read by rules a model writes for each table, applied by code ([0023](../decisions/0023-tables-read-by-rules-a-model-writes.md)); a PDF table's structure ([0024](../decisions/0024-pdf-table-structure.md)); workbooks' cells as Excel shows them, CSV as a one-sheet workbook ([0022](../decisions/0022-spreadsheet-cells-as-excel-shows-them.md)); every format through one task core ([0020](../decisions/0020-formats-share-one-task-core.md))
  - subjects and the merged index ([0046](../decisions/0046-one-source-analyzed-with-indexes-of-what-was-read.md)); links between proposals by evidence, never by numbering ([0041](../decisions/0041-evidence-combined-numerically.md), [0042](../decisions/0042-counterparts-only-where-differentiated.md), [0045](../decisions/0045-possible-matches-are-links-kept-apart.md)); gaps weak ([0048](../decisions/0048-gaps-are-weak-evidence-looked-for-where-theyd-be.md)); commentary beside claims that never change ([0047](../decisions/0047-commentary-logged-beside-claims-that-never-change.md)); stance: who holds a claim ([claim context](claim-context-2026-10-14.md), milestone 5)
  - [the design apart from its documents and their makers](design-documents-parties-2026-11-17.md) (draft): a table's provider, its name and an owner column are document and party claims there
  - later served by [criteria-first comparison](n-way-comparison-2026-09-23.md)

## Why

What happens today to a table of statements (read in the code, 2026-11-18):

- **Read as loose claims.** A table's rules say a value is "a cell's own value (a number, a name, a short code), never a sentence" (`tablerules.py`), so a row of sentences is sent alone with its header to the general reader, which decides how it splits into claims; a sentence split over cells (condition, subject, verb, content) is read cell by cell, and an identifier or a verification method binds to whatever entity the model chose.
- **Lost without a word:** a claim whose value passes 300 characters or whose quote passes 400 fails validation and is dropped (`schema.py`); a row of two columns over 1,800 bytes isn't sent at all (`tasks.py`).
- **Identity:** an item is keyed by a tag of one shape (`align.TAG`: one to four capitals, one to four digits) or by its entity's words; "FOOv0.0-001", "SYS_001", "3.2.1.4" aren't tags, and rows read with a generic entity ("the system") collapse into one subject.
- **Modality:** `basis` is asked of no reader and stays unknown; "shall", "should" and "will" are nowhere told apart or compared.
- **Comparing text:** two text values match by their folded words exactly, or go to the model; nothing tells a rewording from a changed obligation, and the report marks no words.
- **Columns taken for something else:** "Source" or "Author" headers make a column a holder of views (`stance.HOLDER_HEADER`), and claims of different holders never pair.
- **Nothing to measure it on:** the controlled corpus scores no text value (`score.py`: "not scored yet"), and no recorded slice holds a table of statements.

## Concepts

- **A table of statements:** a table whose rows each say something in sentences, with cells that identify, qualify or discuss what's said: requirements tables, but also risk registers, interface tables, test matrices, compliance matrices. Not a table of values (a schedule of pumps), whose cells are each a value.
  - *Contrast:* is a row's main content a sentence (or a sentence split over cells), or a set of values?
- **A table's reading:** what a model says, once a table, about how its rows read; code applies it to every row (as a table's rules are today). No built-in list of columns: each table is read as its own headers and cells say.
  - **The statement:** the cells that make the row's sentence, in order ("{Condition}, {Subject} {Verb} {Clause(s)/Content}"; or "{Text}" alone).
  - **The identifier:** the cells that tell the row from the others ("FOOv0.0-001", "FOO-REQ-112"), and a name if one is given.
  - **Qualifiers:** cells that say something more of the statement, each by its own header ("Verification Method: Test, Analysis", "Rationale: ...", "Requirement Status", any miscellaneous column).
  - **Notes about the statement:** cells discussing the statement ("REQUIREMENTS NOTE: discussion of recommended changes"), the document's own commentary; a note may still claim something of the system (a "well, actually"), so a note is read by the model with its statement as context.
  - **References:** cells naming other rows or other things ("Derived From", "Satisfied By"), resolved where the source holds what they name.
  - *Contrast:* a reading says how this table's cells make claims; the rules today say which cell holds which value.
- **A statement is a claim about the system, with its modality** (the owner: "We're ultimately using requirements to understand what a document is claiming about a system"): shall or must (an obligation), should (a recommendation), may (a permission), will (a claim or an intention), none (a plain description).
  - *Contrast:* "the pump shall deliver 500 gpm" and "the pump will deliver 500 gpm" claim one capacity, with different force.
- **A statement's counterpart in another proposal:** the statement the other design makes for the same need. An identifier never makes one (each proposal numbers its own: [0042](../decisions/0042-counterparts-only-where-differentiated.md)); what the statements say does (their subject, their bounds), and what qualifies them where both tables give it.
- **How two counterparts differ:** reworded (one claim), tightened or loosened (a bound, a modality, "at least"), scope changed (its condition, what it applies to), other; one-sided (no counterpart: a gap, weak).

## Milestones

### 0. The losses counted, and something to measure on

- **`debug` counts what a run lost of text, by why** (too long, quote not found, a row too long to send, a table read twice), naming nothing of the documents: the owner's corpus sized without sharing it (no requests).
  - **Built 2026-11-18** (0.73.0): a claim discarded for a field longer than allowed is said apart from a malformed one ("Discarded N claim(s) too long to keep"); the run's reading counts them ("Too long") and table rows never sent ("Rows not sent"), neither counted as cut short too, in the run's last line, the report's Reading view and `debug`, which also says how many claims are text (no digit in their value). On the held-out tensions' documents (recorded before the change, so their too-long claims still read as malformed): HabEx's 10 pages 676 claims, 235 of them text, 30 quotes not found; Kentucky's manual's 10 pages 452 claims, 23 text, 91 quotes not found. A table read twice isn't counted: both readings are kept, so nothing is lost.
- **Controlled tables of statements, varied on purpose** (keys exact): several shapes, none canonical; each an Excel workbook (as pasted from a modelling tool), CSV, Markdown, Word and PDF:
  - a statement in one cell beside an identifier, a name and qualifiers;
  - a statement split over condition, subject, verb and content cells;
  - statements in prose ("shall" paragraphs);
  - other tables of statements (a risk register, an interface table);
  - headers differing between two proposals, columns added, dropped and reordered, miscellaneous columns, blank columns and blank statements, notes discussing changes, references between rows.
  - Notes of two kinds: some only discussing a statement, some claiming something of the system ("the 70 °C limit is unachievable; 60 °C is expected").
  - Knobs across two proposals: a statement reworded; a bound tightened or loosened; a modality changed (shall to should, shall to will); a condition changed; a qualifier differing; a statement split in two; one-sided statements; long statements and notes.
  - The scorer taught to score text: a statement's words whole, its modality, its identifier, a counterpart, a difference's kind.
  - **Built 2026-11-19, the first shapes** (lab `statements.py`; [samples and testing](../samples-and-testing.md)'s controlled corpus): a harbour monitoring buoy's eight requirements (shall, should, may and will; conditions; bounds; three with no number) in three shapes (`cells`: ID, Name, Text, Rationale, Verification Method and a blank status; `split`: Temporary UID, Condition, Subject, Verb, Clause(s)/Content and a REQUIREMENTS NOTE; `prose`: numbered paragraphs), each as PDF, Markdown, Word, slides and a workbook (15 documents, every existing one byte for byte as before). Each statement and rationale is a text fact (drawn "statement", placed by the words it prints), each number a numeric fact, the modality its basis. The scorer's text branch (`score.classify_statement`, only where a key holds statements: every other score unchanged): right where a claim's value holds a statement's words whole and names it, a fragment where it holds part of one.
  - **Today's reading, the baseline** (recorded $0.03): in every shape and format the six numbers are found, and no statement or rationale is: the reader gives one claim a requirement, its subject, a property it names and the core of what's required ("buoy hull | paint colour | international orange"; "data logger | data retention period | at least 85", the condition kept as such), its modality lost (every basis "unknown"), its rationale, verification method and identifier read as nothing. 8 or 9 claims for 8 requirements from Markdown, Word, slides and workbooks; recall 6 of 22 facts (cells, prose), 6 of 14 (split: no rationales).
  - **Built 2026-11-19, notes and a register:** two of the split shape's notes claim something of the system (a hull rated below the stated limit; another reporting interval in storms), their numbers facts the note holds (`statements.NOTE_HOLDER`); the rest discuss wording. A risk register (`hmbr`: Risk ID, Risk, Likelihood, Consequence, Mitigation, Owner), risks and mitigations text facts. Recorded ($0.02): the split shape finds its two notes' numbers besides the six (8 of 16), still no statement; the register 2 or 3 of 10 (its two numbers, at most one mitigation), most of its claims words the key doesn't state (6 or 7 a document).
  - **Not built yet:** the pair of proposals whose tables differ (headers, identifiers, shapes, the knobs above): built before milestone 4 measures counterparts.
- **Public tables of statements** added to the slices:
  - **Added 2026-11-19:** HabEx's science traceability matrix (`habex-final-p132-135`, a development run `habex-stm`; recorded $0.11). Today's reading: 684 claims on its four pages, 17 of them text and 3 over 60 characters; its objectives and requirements read as bounds ("UVS multi-object spectroscopy | spectral range | 115–320 nm"), their sentences not kept; `debug`: cut short 41, quotes not found 4, too long 3. HabEx's science traceability matrices, the 2013 Decathlon rules; others found as they're looked for.

### 1. Silent losses fixed (bugs first)

- **A long value or quote kept,** never dropped: whole where it was read verbatim, else cut at a word and marked.
- **A long row read in parts,** never left unsent.
- **Fixed 2026-11-18** (0.73.1; every reader's version raised, so stores are read again from the answers cache, only the long rows asked):
  - **Claims' limits raised** to generous backstops (a value or a quote 2,000 characters, conditions 1,000; `schema.LONGEST`); a field longer still is shortened at a word's end and marked ("…"; a quote shortened stays a prefix of what it quoted, so it's still found), the claim kept and counted ("Too long"). Values over 300 characters and quotes over 400 had been dropped.
  - **A row too long to send, of two cells or one,** has its longest cell split at sentence and word ends into parts that fit, each sent with the row's other cells and the header (`tasks.long_row`): an identifier and a long statement keep together. It had been recorded partial and never sent.
  - **Measured on recordings** ($0.05 in all): RAN1's two feature-lead summaries (Word tables of companies' proposals in prose), whose 32 rows had gone unread, now read in 66 parts: 289 claims more (2,182 to 2,470), none left unsent, 2 kept that the old limits had dropped. QUIC's and TS 38.300's pairs unchanged (4,558 and 13,309 claims); the controlled corpus one claim more, right; a development slice's (UNCC's mechanical sheets) one long row read.
  - "Source" and "Author" columns as holders: left for milestone 2, where a table's reading says what each column is.
- **"Source" and "Author" columns** taken as holders only where they hold parties' names, not documents cited.

### 2. Tables of statements read by the table's reading

- **The table's rules request asked one more thing:** whether its rows are statements, and if so its reading (the statement's cells and their order, the identifier, qualifiers, notes, references), each named by the table's own headers. One request a table, as today; the reading applied by code to every row.
- **Checked by code:** a row's statement is its cells' words in the reading's order, so it's verbatim by construction; a reading naming a header the table hasn't is refused, and the table read as today.
- **Each row a subject,** keyed by its identifier within its source (any shape: the reading names it); its statement a claim with its modality, its qualifiers claims of it, by their headers; blank cells give no claim, and a column blank in every row is said once.
- **Notes read by the model with their statement as context** (its row's identifier, statement and qualifiers): kept as the document's commentary on the statement, shown beside it; a claim a note makes of the system (a bound it says is wrong, a value it gives instead) kept as the note's, beside the statement's, never in its place ([0047](../decisions/0047-commentary-logged-beside-claims-that-never-change.md); its stance the note's: [claim context](claim-context-2026-10-14.md)). A request a note that says more than a few words; measured on the controlled notes (some only discussing, some claiming) against reading them as plain text.
- **Numbers in a statement** ("-40 °C to +70 °C") read by code as its bounds, so numeric comparison still applies.
- **Statements in prose** are the reader's, as today, their modality by code.
- **Measured** against a null arm of the same request's length and against today's reading, on the controlled shapes; held out before it's a default.
- **Built 2026-11-19** (0.74.0, `statement_tables`, off; `tablerules.Statements`, `statement_claims`): the rules request offers a fourth reading, "statements", the columns named by letter as the table's headers say what they are (statement, identifier, name, qualifiers, notes, references); checked by code (a column the table lacks refuses it); each row's statement its cells joined word for word, each qualifier, reference and note a claim under its own header, the entity the row's identifier and name; every row still read by itself. A table of values isn't offered anything new to do.
  - **Development** (the controlled corpus's tables of statements, two arms; on $0.19; the scorer's whole statement loosened the same day: a claim holding a statement whole with more beside it, a risk with its consequence, is right):

    | Documents | Statements and rationales or risks found, off → on |
    |---|---|
    | Cells shape: PDF, Word, slides, workbook | 0 → 14, 16, 16, 16 of 16 |
    | Split shape: PDF, Word, slides, workbook | 0 → 8, 7, 8, 8 of 8 |
    | Risk register: PDF, Word, slides, workbook | 1 → 8, 8, 8, 8 of 8 |
    | Markdown (every shape), prose (every format) | unchanged |

    Numbers found as before in every document; the equipment schedules' 39 documents (tables of values) unchanged. Missed: a split row whose condition the model named a qualifier (kept as its own claim; the statement without it); a cells table continued over two PDF pages, its second part reading one row of two (the lever index's row on tables continued over pages).
  - **Held out, 2026-11-20** (the lever index's *Tables of statements*): a fresh template, two shapes of its own, 98% and 91% of its statements found with the lever on (5 of 96 off), numbers alike; the real tables weren't reached (LUVOIR's read as values, HabEx's interim matrix stopped by the PDF image check), so the rule's real half is unmet; the owner's own tables the likeliest real test.
  - **Not reached:** Markdown's pipe tables are read without a grid, so they're never asked the rules request (`textjob`: rows read by themselves), whatever this lever; and statements in prose are the reader's.

### 3. Modality and references

- **Modality by code** from the statement's words (and a verb cell where the reading names one), into `basis`; "will" a claim or an intention.
- **References within a source:** cells naming other rows resolved to them by identifier or name; to the design's subjects where another document of the proposal names them; shown, and available to matching.

### 4. Counterparts across proposals

- **Linked by evidence** ([0041](../decisions/0041-evidence-combined-numerically.md)): what two statements say (their subject's words and meaning, their bounds of one quantity, their condition), their names where given, references whose targets are counterparts; qualifiers of like headers where both tables have them; identifiers and table names weigh nothing; the model read for contested pairs as for other subjects.
- **Several to one allowed** as links ([0045](../decisions/0045-possible-matches-are-links-kept-apart.md)): a statement split into two in the other proposal, reported as split.
- **One-sided statements** as gaps, weak.

### 5. Counterparts compared

- **Statements by code first:** modality, bounds with their units, conditions, and the words differing; a kind given where code can (reworded when only words move; tightened or loosened when a bound or a modality moves one way); the judge asked only what's left, told what code found.
- **Qualifiers by header likeness, not a fixed list:** columns of the two tables paired by their headers' words and meaning and by the values they hold (two columns both holding "Test", "Analysis"); a pair compared as values (a set of methods, a status); a column with no partner said, not counted as a difference.
- **Notes** shown beside their statements; the claims a note makes of the system compared as the note's (a note in one proposal saying a bound should change is reported as that, not as the statement's).

### 6. Shown

- **A Statements view:** counterparts side by side, the differing words marked, each difference's kind and modality; qualifiers by paired columns; one-sided statements apart; references; the export's chunks a statement.

### 7. Held out

- **Rules written before** fresh controlled seeds and fresh public tables are read; each lever off until it passes, then the owner's call.

## Measurement

- **Controlled tables, exactly:** statements kept whole, modality right, rows told apart, counterparts found (precision and recall), kinds right; by shape and by format, so no one shape decides.
- **Public tables:** a model panel rating counterparts and kinds ([0043](../decisions/0043-matching-measured-on-real-pairs-by-a-model-panel.md)).
- **The owner's corpus, by use:** `debug`'s counts before and after; what the owner sees in reports.
- **Cost:** a table's reading rides on its rules request (no request more); the judge asked less where code gives a kind.

## Design questions

Answered 2026-11-18 (quoted at the top), and the plan revised for them: no built-in reading of rows, a model's reading a table instead; "will" a claim or an intention; no table taken as canonical, nor its columns as all there are; Excel pasted from a modelling tool, and tables from elsewhere.

- **Notes discussing a statement,** answered 2026-11-18 (the owner: "Although I'd probably read requirements notes as commentary about a document, I wouldn't necessarily reject the possibility that such commentary makes claims about the product (e.g. a "well, actually" in the comment). It's probably something that needs to be read by a model with sufficient context at some point."): commentary on the statement, read by the model with its statement as context, the claims it makes of the system kept as the note's (milestone 2).

None open.
