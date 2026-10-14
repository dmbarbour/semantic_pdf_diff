# Claim context: where a claim was made, how it was named, under what conventions

- **Status:** Active (2026-10-14): written; milestone 1 begun.
- **The owner, 2026-10-14:** "Ideally, we'd avoid list positions as conditions of a claim, treating them as provenance instead (where a claim was made, how it was named). I feel there's a lot to improve in this domain of tracking the context of a claim. For A, we should consider what the model has access to as part of its query, and what a comparison of claims would have access to - was there enough information in the query to call it the non-conventional 'depth' instead of 'length'? If not, what sort of structure would provide the context for that info? Perhaps we should be examining how we'd approach different naming conventions for dimensions between papers, too."
- **Then:** "Write the plan, then start with list positions as provenance. Turn it into a full plan unless it proves very short; I expect there's a lot you can think up for how to handle provenance and contexts with a little brainstorming."
- **From:** the 2026-10-14 looks at the controlled corpus's drawing sheets and at the spec's revision pairs after `text_spans: page` became a default ([lever index](../reviews/levers.md)).

## Why

A claim today is five words the reader chose (entity, attribute, value, unit, conditions), a quote, and a locator. Everything else a reader or a comparison might need is either folded into those words or lost.

- **Positions read as conditions.** The spec prints "Condition 1: no acknowledgement is received within 856 ms." Its claims come back as "Link failure | acknowledgement timeout | 856 ms | conditions: Condition 1". A revision inserts a condition and renumbers the rest, so the same timeout is "Condition 2" in one and "Condition 3" in the other.
  - The judge sees different conditions and returns uncertain.
  - The explanation calls them different items, against its own checklist.
  - Alignment's identifier check calls "condition 2" against "condition 3" a conflict, so the pair never settles without a model.
  - The numbered and renumbered spec pairs in Word: 3 unchanged facts each uncertain (2026-10-14).
  - Across the corpus's runs: 96 claims hold a position in their conditions (81 of them "Condition N"), 152 in their attribute ("dimension 1"), and many in their entity ("Option 2", "column 3"), not all of which are positions.
- **Names the source never gives.** The drawing sheets miss only room dimensions, and every one is named by the reader:
  - The sheet prints "24'-6"" on a dimension line beside MEETING 101. It prints no word for either room dimension and has no north arrow. The key calls it "depth" ("north-south dimension"), a name the generator chose.
  - The tile's query held the image and a text layer ("MEETING 101 564 SF 23'-0" 24'-6" D101"), so which way each dimension runs was in the image only. The model called it "length"; "depth" couldn't be derived.
  - A comparison sees less still: entity, attribute, value, unit, conditions and quote, no geometry. Two proposals that call one dimension "depth" and "length", or draw the room turned 90°, have only the value to match on.
- **Conventions that scope many claims are read once, if at all.** The same sheet's general notes say "ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE" and "ROOM AREAS ARE NET". Two proposals measuring to different faces would show equal rooms as different, or different rooms as equal, and nothing would say why.
- **Who says it, and to whom it applies,** is the [subject, parties and provenance](README.md) row's: the RAN1 summaries' companies' views compared as one item changed.

## Scope

- **In:** the context of a claim: where it was made (structure and position, not only page and box), how it was named (as printed, and as the reader named it), what scopes it (headings, lead-ins, notes, legends, captions, declared units and conventions), and for drawings what it spans. Captured mechanically where the source's structure gives it, by the reader where only reading can, and used by alignment, comparison, explanations, reports and the scorer.
- **Shared with other plans:**
  - [Comparing revisions](revision-comparison-2026-10-02.md), design item 4 (identity at extraction, an entity register): the register names *things*; this plan records *where and how* each claim named them. Its cheap partial steps (names by what a value measures, row labels and column headers kept) are built here or there, whichever comes first, not twice.
  - *Subject, parties and provenance* (plans index): who asserts a claim and what it's about. This plan's record has a place for it; the row's work stays there.
  - [Units and normalization](units-and-normalization-2026-09-24.md): a document's declared units ("all dimensions in mm") are conventions here, applied there.
  - *Evidence webs* (plans index): links between claims. A claim's context points at other claims (a lead-in, a note) but isn't a web.
- **Out:** model-chosen names judged by a rater (the panel's business); a document's own revision marks (the revision comparison plan).

## Concepts

A claim keeps what it asserts apart from its context. The judge compares assertions; context explains, scopes and identifies.

| Part | What it holds | How it's found | Today |
|---|---|---|---|
| **Place** | page, box, region, task; section path | the reader's layout | kept (locator, section) |
| **Position** | the label the source gives an item in a sequence ("Condition 2", "step 3", "(b)", "4.2.1"), its list and the list's lead-in ("A link failure is declared when any of the following conditions holds.") | the parse: Word's numbering, Markdown's ordered lists, labels repeated in sequence by sibling blocks; clause numbers from headings | folded into conditions, attribute or entity |
| **Name as printed** | the words the source puts beside the value: row label and column header, the label before a value in a sentence, a dimension's own label, a legend entry | tables: the grid; text: the quote; drawings: the text nearest the value | only the reader's name |
| **Name as read** | the reader's entity and attribute | the reader | kept (the claim) |
| **Scope** | what the source says applies: heading path, lead-in, table caption and notes, footnote markers, "unless noted otherwise", "typical", a sheet's general notes | the parse and situating | heading path only (`Section: ...` in prompts) |
| **Conventions** | how the document writes things: units, north arrow and orientation, dimension references (face of finish, centreline), datums, sign conventions, defined terms and abbreviations, naming pairs (W × D) | situating, per document, sheet or section | read as ordinary claims, if at all |
| **Geometry** (drawings, charts) | what a value spans or marks: a dimension's direction as displayed, its ends, the room or element it bounds; a gridline reference; a chart reading's series and axis | the vector drawing first, the reader where it can't | the image only |
| **Assertion** | who says it and on what basis | the *subject, parties and provenance* row; `basis` | `basis` (rarely filled) |

**Rules for using context:**
- **A position is weak identity.** The same label on both sides supports a match; a different label with the same name and value suggests renumbering, a common edit, not a different item. Positions never block a match.
- **A name as printed outranks a name as read.** Two readers naming one printed label differently aren't a rename.
- **Scope and conventions are shown to the judge as such,** apart from conditions: "conventions differ (face of finish vs centreline)" is a finding about context, not a changed value.
- **What isn't knowable stays unnamed.** A dimension whose direction can't be tied to a convention is recorded by its geometry ("vertical as drawn, along MEETING 101's west wall"), never given a conventional name the page doesn't print.

## Naming conventions across documents

Dimensions are the sharpest case, and the pattern carries over to other named quantities (a tower's fore-aft and side-to-side, a pump's rated and design points).

- **Match on structure before words:** the entity, the kind of quantity (a length), its role relative to the entity (one of a room's two plan dimensions; an opening's width or height), then the value. "Width", "depth" and "length" become the reader's labels, weak evidence.
- **Where direction is established** (a north arrow, a schedule's columns, both drawn the same way up), compare by direction.
- **Where it isn't, compare a room's plan dimensions as an unordered pair:** {23'-0", 24'-6"} matches {24'-6", 23'-0"} whatever each is called, and the report says "the dimensions agree as a pair". A room drawn turned 90° in another proposal is the same room.
- **A document's own vocabulary is recorded once:** a schedule headed "W × D", a glossary, defined terms. Claims named in it are tied to its terms, and two documents' vocabularies are compared as conventions.
- **Abstain rather than guess:** "length" in one document and "depth" in another is "named differently", not a match or a change, unless geometry or a convention ties them.

## Measurement

- **Counts without the model, per document** (a new lab measure):
  - claims holding a position in their conditions, attribute or entity
  - claims named by position ("dimension 1")
  - claims carrying a position, a printed name, scope, conventions or geometry in their context
- **The controlled corpus's keys gain context:** each listed fact's printed label; room dimensions by room and direction as drawn; the conventions a document declares. Scoring then accepts a reading that names what's knowable ("Meeting 101, vertical dimension") and stops requiring a convention the page doesn't print. A scorer change is announced with before and after numbers, not folded into a lever's measure.
- **New controlled scenarios,** each a knob on an existing family:
  - a list item inserted (the spec has it), steps renumbered, nested lists, a list continued across a page
  - a sheet with and without a north arrow; a room drawn turned 90° between proposals; a schedule headed W × D against one headed W × L; dimensions to centreline against face of finish
  - a note's scope ("unless noted otherwise") with an exception, a footnote marker on a table value, a "typical" marker
- **Comparisons:** the spec pairs' uncertain and false findings; renumbering named as such; the real pairs read by eye (3GPP revisions renumber clauses often).
- **Judged** as levers are ([judging a lever](../samples-and-testing.md#judging-a-lever)): document by document, target and guard named first, null arms for anything that rewords a prompt.

## Rules against drift

- **Every change in behaviour is a lever, off by default** until measured, and listed in the [lever index](../reviews/levers.md). Defaults change only on measured evidence and the owner's word.
- **Refactors needed on the way are separate steps,** proven by replay ([0027](../decisions/0027-behaviour-changes-apart-from-refactors.md)). Likely: a context record on evidence, and the store's schema version.
- **Mechanical before model:** context is taken from the source's structure wherever the parse has it. The reader is asked only for what reading alone can give, and each such prompt change is judged against null arms.
- **New directions found on the way** become tentative rows in the plans index, not milestones here.
- **Each milestone ends with a commit after the full suite passes,** and reports what it spent.

## Milestones

### 1. List positions as provenance

The first step, and the cheapest: no extraction query changes.

- **Find positions mechanically.** A text block opening with a label is a list item when sibling blocks (the same page and section) open with labels of the same form in sequence:
  - a word and a number ("Condition 1:", "Step 2.", "Item 3 -"); a number ("1.", "2)"); a letter or roman numeral ("(a)", "iv.")
  - Word writes its numbering's labels into the text (`docxdocs.Numbering`), and Markdown's ordered lists keep theirs, so one rule covers PDF, Word and Markdown text.
  - A lone "Option B:" or "Load Case 3" isn't a sequence and stays a name.
- **A claim takes its block's position** (claims are placed by their quote's block). When its conditions are only that label, or the label and other words, the label leaves the conditions and goes to the claim's position, with the list's lead-in.
- **The lever:** `positions: "conditions" | "provenance"`, off ("conditions") until measured.
- **Comparison:** the position is provenance, so the judge doesn't see it. Alignment counts a shared label as weak support, never as a conflict.
- **Measured:**
  - the count of conditions holding a position, before and after (96 in the corpus's runs)
  - the spec pairs: the 6 uncertain facts, kinds named right
  - facts right on the corpus, paired by document (the guard)
- **Cost:** extraction replays; comparisons re-asked where claims changed: cents.
- **Then, if positions stay in attributes and entities** ("condition 1" as an attribute, 40 claims): the same label moved from those, or a prompt field for it (judged against null arms).

### 2. A context record on evidence

- **The record:** position, name as printed, scope, conventions, geometry, each optional, on evidence beside the locator. The store's schema version bumped, with old stores read as having none.
- **Name as printed, mechanically:**
  - table claims: the parse's row label and column header (the [one table model](one-table-model-2026-09-30.md) has them)
  - text claims: the label before the value in its sentence ("timeout of 856 ms")
- **Shown in the report:** "as printed: Condition 2 of 'A link failure is declared when…'"; a renumbering shown as such.
- **Explanations** get both claims' positions and printed names, so "renumbered" is named from evidence rather than inferred from numbers in the conditions.

### 3. Scope and conventions

- **Situating finds conventions** per document, sheet and section: general notes, legends, abbreviation lists, declared units, north arrows and scales, "unless noted otherwise", "typical".
- **Claims take the conventions in their scope** (a sheet's notes apply to its sheet; a table's notes to its table; a footnote marker to its cell).
- **The judge sees conventions apart from conditions,** and a difference in conventions is reported as context, with the claims it covers.
- **The scorer** checks a claim's conventions where the key declares them.

### 4. Drawing geometry

- **First, a look without the model:** can dimension strings (a dimension line, extension lines, ticks or arrows, a label along the line) be found in the vector drawing of the corpus's sheets and the slices' real drawing sets? Real sets are stored turned 90° (25 of the slices' 103 pages), so directions are taken as displayed.
- **If they can:** each dimension's direction, extent and what it bounds go into the tile's text layer ("24'-6" — vertical dimension, beside MEETING 101") and into the claim's context. Gridline references (A–F, 1–4) give places as a drawing's own coordinates.
- **If they can't:** the reader is asked for direction as drawn, judged against null arms.

### 5. Naming across documents

- **Room dimensions as pairs** where direction isn't established; by direction where it is.
- **A document's vocabulary** (schedule headers, defined terms) recorded and compared as a convention.
- **Keys and scorer:** room dimensions keyed by room and direction as drawn; "named differently" scored as a comparison outcome.
- **Other paired quantities** (fore-aft and side-to-side, rated and design points) checked for the same pattern in the corpus and the samples.

### 6. Further contexts (to be ordered as earlier milestones report)

- **Clause and section numbers as positions:** 3GPP revisions renumber clauses; a claim's clause is provenance, and a moved clause is "moved", not removed and added.
- **Tables:** units rows, merged header spans, footnote markers, "typical" columns.
- **Charts:** series, axis and operating point as context, not attribute words.
- **Time and place in scope:** phase, year, level, zone, option or alternate ("base bid", "alternate 2"); options are names with identity, not positions.
- **Quoted sources:** a value given "per ASHRAE 90.1" or from another document is the cited source's claim.
- **Repetition:** the same value stated in many places, its occurrences as context for confidence ([evidence webs](README.md)).

## Design questions

1. **Renumbering in reports:** shown as a finding of its own ("renumbered: Condition 2 → 3"), or only in the claim's detail? I'd show it among editorial changes.
2. **Unordered pairs:** may room dimensions whose direction isn't established be compared as a pair and reported "agree as a pair", rather than left uncompared?
3. **The scorer's room dimensions:** keyed by direction as drawn, accepting any name, instead of the generator's width and depth?
4. **Conventions to the judge:** shown as their own field (my preference), or folded into conditions?
