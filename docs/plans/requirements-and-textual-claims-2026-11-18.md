# Requirements and textual claims: read whole, matched across proposals, compared by role

- **Status:** Draft for the owner's review (2026-11-18).
- **The owner, 2026-11-18:** "Do we have anything on the docket useful for comparing requirements and capturing more textual claims? I have a LOT of claims in the form of requirements tables that aren't numerical in nature in my actual corpus, and I feel we've a long way to go to properly extract and compare such claims."
- **The owner, the same day:** "Please write up the plan." With the columns of one sample table exported from a Cameo model: Provider (the Cameo model's name), Requirement table name, ID ("FOO-REQ-112"), Name ("FOO Handling Temperature"), Text ("usually one sentence containing 'shall', sometimes blank"), Rationale ("up to a few sentences"), Verification Method ("Test, Inspection, Analysis, Demonstration, or a combo"), Requirement Status ("all blanks at the moment"), Compliance ("all blanks"), Derived From ("a list of other requirement names"), Classified ("true, false, blank"), Refined By ("e.g. Command BIT Test, often blank"), Refines, Owner, Satisfied By, Comment, Stakeholder Requirement, Verification Event. And: "These will be compared across proposals, and the columns will certainly NOT match exactly."
- **Takes over** the tentative row *Requirements and textual claims* (2026-11-18) and its nine lever rows.
- **Builds on:**
  - every format through one task core, Cameo's exports read as Markdown and CSV ([0020](../decisions/0020-formats-share-one-task-core.md)); CSV read as a one-sheet workbook (`xlsxdocs.read_csv`), cells as Excel shows them ([0022](../decisions/0022-spreadsheet-cells-as-excel-shows-them.md))
  - tables read by rules a model writes ([0023](../decisions/0023-tables-read-by-rules-a-model-writes.md)), a PDF table's structure ([0024](../decisions/0024-pdf-table-structure.md))
  - subjects and the merged index ([0046](../decisions/0046-one-source-analyzed-with-indexes-of-what-was-read.md)); links between proposals by evidence, never by numbering ([0041](../decisions/0041-evidence-combined-numerically.md), [0042](../decisions/0042-counterparts-only-where-differentiated.md), [0045](../decisions/0045-possible-matches-are-links-kept-apart.md)); gaps weak ([0048](../decisions/0048-gaps-are-weak-evidence-looked-for-where-theyd-be.md)); tensions, on in analyses since 0.72.0
  - [the design apart from its documents and their makers](design-documents-parties-2026-11-17.md) (draft): the Provider, the table's name and the Owner are document and party claims there
  - later served by [criteria-first comparison](n-way-comparison-2026-09-23.md): requirements as criteria

## Why

What happens today to a row such as "FOO-REQ-112 | FOO Handling Temperature | The FOO shall ... | Rationale ... | Test, Analysis | ... " (read in the code, 2026-11-18):

- **Read as loose claims.** A table's rules say a value is "a cell's own value (a number, a name, a short code), never a sentence" (`tablerules.py`), so a row of sentences is sent alone with its header to the general reader, which has no field for an identifier, a modality, a verification method or a trace; the model decides how the row splits into claims.
- **Lost without a word:** a claim whose value passes 300 characters or whose quote passes 400 fails validation and is dropped (`schema.py`; a rationale of a few sentences); a row of two columns over 1,800 bytes isn't sent at all (`tasks.py`).
- **Identity:** an item is keyed by a tag of one shape (one to four capitals, one to four digits: `align.TAG`) or by its entity's words; "SYS_001", "R-1.2.3", "3.2.1.4" or five digits aren't tags, and rows read with a generic entity ("the system") collapse into one subject.
- **Modality:** `basis` (required, targeted, measured) is asked of no reader and stays unknown; "shall" against "should" is nowhere compared.
- **Comparing text:** two text values match by their folded words exactly, or go to the model; nothing tells a rewording from a changed obligation, there's no "tightened" or "loosened", and the report marks no words.
- **Columns taken for something else:** "Source" or "Author" headers make a column a holder of views (`stance.HOLDER_HEADER`), and claims of different holders never pair.
- **Nothing to measure it on:** the controlled corpus scores no text value (`score.py`: "not scored yet"), its requirements are numeric limits, and no recorded slice holds a requirements table.

## Concepts

Code names each with a constant.

- **A requirement:** a statement that obliges the design, with what identifies and qualifies it: a requirements table's row, or a "shall" sentence in prose.
  - "FOO-REQ-112 FOO Handling Temperature: The FOO shall withstand handling temperatures from -40 °C to +70 °C."
  - *Contrast:* does it oblige the design, or describe it? "The pump shall deliver 500 gpm" is a requirement; "the pump delivers 500 gpm" a design claim.
- **A role:** what a requirements table's column holds, whatever its header says: identifier, name, statement, rationale, verification method, verification event, status, compliance, classification, owner, comment, and the traces below. "Verification Method", "Verif. Method" and "V&V" are one role; "Text", "Requirement" and "Statement" another.
  - *Contrast:* a role names what a column means; a header is how one table prints it.
- **Traces:** the relations a requirement states to others and to the design: derived from, refines, refined by, satisfied by, stakeholder requirement. Within one source they're explicit relations, the kind real drawings rarely state (the review of open items' R3, 2026-11-18).
- **Modality:** shall or must (mandatory), should (recommended), may (permitted), will (declared).
  - *Contrast:* "shall not exceed 70 °C" and "should not exceed 70 °C" state one bound and differ in obligation.
- **A counterpart requirement:** the requirement another proposal states for the same need. Its identifier never makes it one (each proposal numbers its own: [0042](../decisions/0042-counterparts-only-where-differentiated.md)); its name, its statement's subject and bounds, its verification and its traces do.
- **How two counterparts' statements differ:** reworded (one obligation), tightened or loosened (a bound, a modality, "at least"), scope changed (what it applies to, when), other; and one-sided (no counterpart: a gap, weak).

## Milestones

### 0. The losses counted, and something to measure on

- **`debug` counts what a run lost of text, by why** (too long, quote not found, a row too long to send, a table read twice), naming nothing of the documents: the owner's corpus sized without sharing it (no requests).
- **A controlled requirements pair** (keys exact; the generator's own): two proposals' requirement tables for one kind of system, as workbooks, CSV, Markdown (as Cameo exports them), Word and PDF.
  - Headers differing (synonyms, order, extra and missing columns, Cameo's names in one); identifiers of each proposal's own scheme; blanks as the owner describes (a status and a compliance column all blank, some statements blank).
  - Knobs: a statement reworded; tightened and loosened bounds; a modality changed; a scope changed; verification methods differing (Test against Test, Analysis); a requirement split in two in the other; one-sided requirements; long rationales; traces to parents with counterparts and without.
  - The scorer taught to score text values: a requirement's role and its words, a counterpart, a difference's kind.
- **Public requirement tables** added to the slices: HabEx's science traceability matrices, the 2013 Decathlon rules, and a public SysML model's requirement tables if one can be found.

### 1. Silent losses fixed (bugs first)

- **A long value or quote kept,** never dropped: its whole text kept where it was read verbatim, else cut at a word and marked.
- **A long row read in parts,** never left unsent.
- **"Source" and "Author" columns** taken as holders only where they hold names of parties, not documents cited.

### 2. Requirements tables read as requirements

- **By code where the headers say so:** a table whose headers map to roles (an identifier or name, and a statement, at least) is read row by row into one subject a requirement, each cell a property of its role, its text verbatim (no model reading, no length limit, its quote the cell). Blank cells give no claim; a column blank in every row is said once, not as a gap a row.
- **Headers code can't map** go to the table's rules request, which names each column's role; the rules applied by code as before.
- **Numbers in a statement** ("-40 °C to +70 °C") read by code as the requirement's bounds, so numeric comparison still applies.
- **Prose "shall" sentences** (rules, specifications): each a requirement of the subject it names, read by the reader as today, its modality by code.

### 3. Modality and traces

- **Modality by code** from the statement's words, into `basis`.
- **Traces within a source:** Derived From's names and identifiers resolved to the source's requirements; Satisfied By's to the design's subjects where another document of the proposal names them. Shown in the report and the index.

### 4. Counterparts across proposals

- **Linked by evidence** ([0041](../decisions/0041-evidence-combined-numerically.md)): names and statements' words (the glossary's terms one word), bounds of one quantity, verification methods, traces whose parents are counterparts; identifiers and table names weigh nothing; the model read for contested pairs as for other subjects.
- **Several to one allowed** as links ([0045](../decisions/0045-possible-matches-are-links-kept-apart.md)): one proposal's requirement split into two of the other's, reported as split.
- **One-sided requirements** as gaps, weak: what one proposal requires and the other doesn't state.

### 5. Counterparts compared by role

- **Statements by code first:** modality, bounds with their units, and the words differing; a kind given where code can (reworded when only words move; tightened or loosened when a bound or a modality moves one way); the judge asked only what's left, told the kinds.
- **Verification methods** as sets ("Test" against "Test, Analysis": one added).
- **Rationales and comments** shown side by side, not judged.
- **Status, compliance and classification** as given, blanks said; the Provider, the table's name and the Owner as document and party claims (the draft plan above).
- **Traces:** each parent's and satisfier's counterpart, or none.

### 6. Shown

- **A Requirements view:** counterparts side by side, a row a role, the differing words marked, each difference's kind; one-sided requirements apart; the index's requirements with their traces; the export's chunks a requirement.

### 7. Held out

- **Rules written before** fresh controlled seeds and fresh public tables are read; each lever off until it passes, then the owner's call.

## Measurement

- **Controlled pairs, exactly:** text kept whole (no requirement lost), roles right, counterparts found (precision and recall), kinds right, by format.
- **Public tables:** a model panel rating counterparts and kinds ([0043](../decisions/0043-matching-measured-on-real-pairs-by-a-model-panel.md)).
- **The owner's corpus, by use:** `debug`'s counts before and after; what the owner sees in reports.
- **Cost:** milestones 0 to 3 no requests but the rules request where headers aren't mapped; the judge asked less where code gives a kind.

## Design questions

1. **Requirements tables read by code where their headers map to roles, verbatim, not by the model?**
   - I'd say yes: nothing lost or reworded, no length limit, no requests; the model only names unknown headers' roles.
2. **"Will":** a requirement, or a declaration of intent as in some conventions?
   - I'd record it as said and not count it as an obligation, unless your corpus's convention differs.
3. **Which roles are compared, and which only shown?**
   - I'd compare statements, verification methods and traces; show rationales and comments side by side; give status, compliance and classification as they are.
4. **In what form do Cameo's tables reach you:** CSV, Excel, a generated Word or HTML report, or PDF? The controlled pair is made in each form; the one you use is measured first.
5. **Other columns or tables in the same exports** (a requirement's parent package, a diagram's name, a satisfying block's properties) worth reading as context?
