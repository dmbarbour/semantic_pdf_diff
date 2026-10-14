# Claim context: what a claim is about, how to read it, where it came from and who holds it

- **Status:** Active (2026-10-14): written; milestone 1 built, its lever a default; Concepts rewritten (subject, scope, frame, provenance, stance); design questions answered.
- **The owner, 2026-10-14:** "Ideally, we'd avoid list positions as conditions of a claim, treating them as provenance instead (where a claim was made, how it was named). I feel there's a lot to improve in this domain of tracking the context of a claim. For A, we should consider what the model has access to as part of its query, and what a comparison of claims would have access to - was there enough information in the query to call it the non-conventional 'depth' instead of 'length'? If not, what sort of structure would provide the context for that info? Perhaps we should be examining how we'd approach different naming conventions for dimensions between papers, too."
- **Then:** "Write the plan, then start with list positions as provenance. Turn it into a full plan unless it proves very short; I expect there's a lot you can think up for how to handle provenance and contexts with a little brainstorming."
- **On the kinds of context (2026-10-14),** after I proposed subject, scope, frame, provenance and stance: "The names work; rewrite the plan's Concepts section. We can keep 'context' as the umbrella term. I expect we'll spend a fair bit of time on this, trying to improve capture of context per claim." Further words on stance and on context's size are quoted in Concepts.
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
- **Conventions that frame many claims are read once, if at all.** The same sheet's general notes say "ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE" and "ROOM AREAS ARE NET". Two proposals measuring to different faces would show equal rooms as different, or different rooms as equal, and nothing would say why.
- **Who holds a claim is lost.** The RAN1 summaries tabulate companies' proposals; their claims named the subject but not the company, so Spreadtrum's "not needed" and ZTE's "support" were compared as one item changed ([comparing revisions](revision-comparison-2026-10-02.md)).

## Scope

- **In:** the context of a claim: where it was made (structure and position, not only page and box), how it was named (as printed, and as the reader named it), what scopes it (headings, lead-ins, notes, legends, captions), how its value is to be read (declared units and conventions: its frame), who holds it and through whom (stance), and for drawings what it spans. Captured mechanically where the source's structure gives it, by the reader where only reading can, and used by alignment, comparison, explanations, reports and the scorer.
- **Shared with other plans:**
  - [Comparing revisions](revision-comparison-2026-10-02.md), design item 4 (identity at extraction, an entity register): the register names *things*; this plan records *where and how* each claim named them. Its cheap partial steps (names by what a value measures, row labels and column headers kept) are built here or there, whichever comes first, not twice.
  - *Subject, parties and provenance* (plans index): the parties around a project and the document's own provenance (title blocks, front matter, issue status), and claims about parties told from claims about the subject. That work stays there; the attribution chain on each claim (stance) is this plan's, and takes the document's link from it.
  - [Scheduling and triage](scheduling-and-triage-2026-09-23.md), milestone 5 (epistemic status): asks readers for basis and uncertainty. Here those are the innermost link's attitude; the prompt work stays there.
  - [Units and normalization](units-and-normalization-2026-09-24.md): a document's declared units ("all dimensions in mm") are frame here, applied there.
  - *Evidence webs* (plans index): links between claims. A claim's context points at other claims (a lead-in, a note) but isn't a web.
- **Out:** model-chosen names judged by a rater (the panel's business); a document's own revision marks (the revision comparison plan).

## Concepts

A claim is a **proposition** (subject, attribute, value, unit) and its **context**: everything else that says what it means, where it came from and who holds it. "Context" is the umbrella term; the kinds below are its parts.

### Telling the kinds apart

Suppose two claims differ only in X. What X is decides how a comparison treats it.

| The two claims are | X is | A comparison |
|---|---|---|
| different propositions, both of which may be true | **subject** or **scope** | requires them to correspond before comparing values |
| perhaps the same proposition written differently, or different ones written alike (5 m and 5000 mm; 564 SF net and 564 SF gross) | **frame** | reconciles them first: converts, or reports the frames as different |
| the same proposition, held by someone else or held differently | **stance** | compares it as a finding of its own ("now B's proposal, was A's"; "now required, was targeted"), never as a changed value |
| the same proposition, recorded in another place or another way | **provenance** | leaves it out of the verdict; may use it to pair claims and to explain |

### The kinds

| Kind | The question | What it holds | Today |
|---|---|---|---|
| **Subject** | What is it about? | the entity, and what identifies it | `entity`, as the reader named it |
| **Scope** | Under what circumstances does it hold? | operating point, load case, mode; the time it's valid for; where it applies (level, zone); option or alternate; phase | `conditions` (with positions, tolerances and frame words mixed in) |
| **Frame** | How is the value to be read? | units; datums; what a dimension is measured to (face of finish, centreline); orientation and north; sign conventions; defined terms and abbreviations; net or gross; a document's naming pairs (W × D) | not recorded; sometimes in `conditions` or `unit` |
| **Provenance** | Where and how was it recorded? | the document, its revision and date; place (page, box, region, section path); position in a list; the quote; the name as printed; geometry as drawn; the derivation (which reader, which task) | locator, section, position, derivation, occurrences (`PROVENANCE_FIELDS`) |
| **Stance** | Who holds it, through whom, and how firmly? | the attribution chain (below) | `basis`, rarely filled; reported views lost (the RAN1 companies') |

Stance is a form of provenance: the provenance of the proposition, where the rest is the provenance of the record. It has its own rule in comparison, so it's named apart.

**Pairs that look alike and aren't:**
- **When it was said, and when it holds:** a document's date is provenance; "from 2027" or "in phase 2" is scope. (Databases call these record time and valid time.)
- **Where it was said, and where it applies:** "page 4, Condition 2" is provenance; "level 3, zone B" is scope.
- **Who wrote it, and whose view it reports:** the document's authors are its outer stance, usually implicit; "Company A proposes option 2" is a reported stance, and a different claim from B's proposal.
- **The name as printed, and the name as read:** the printed label is provenance, something observed on the page; the reader's entity and attribute are the subject and property it assigned.
- **A scope's source, and the scope:** a heading, a list's lead-in or a sheet's general notes is provenance (where the claim sits); the scope it implies is a reading of it. Both are kept, so a reading can be checked against its source, and a query can be asked whether it held enough to give it (the drawing sheets' "depth" didn't).

**Identity cues:** a position, a name as printed and geometry as drawn are provenance that alignment may use as weak evidence for pairing claims. They never enter the verdict, and never block a match.

### Stance: attribution chains

*The owner, 2026-10-14:* "IIUC, stance is essentially closer to a form of provenance than to a scope, e.g. "Bob said that Alice thinks ...", and should be clearly separated from a model's own stance (e.g. "gemma-4 is confident that Bob is uncertain that Alice believes ..."). I certainly wouldn't place it under scope, but it might need more nuanced attention than the current plan assigns to it."

- **A proposition reaches a report through a chain of holders,** from the outside in: our reader, the document's authors, any parties they report, and the party that holds the proposition. "gemma-4 is confident that Bob is uncertain that Alice believes the timeout is 856 ms" has three links.
- **Each link has a holder and an attitude:** says, proposes, requires, targets, measures, calculates, estimates, believes, doubts, disputes, rejects. It may also have a strength: a hedge ("may", "likely") or a stated uncertainty.
- **The pipeline's link is kept apart from the source's.** The reader's confidence, its quote's verification, agreement among readers (occurrences), the derivation and the judge's confidence are our stance on the record.
  - They weight, order and filter findings.
  - They are never compared as a difference between documents, and never read as the source's uncertainty.
  - Today `confidence` is ours, and `basis` and `uncertainty` are meant to be the source's, but the schema doesn't say so.
- **The document's link is usually implicit:** a spec states its requirements in its authors' voice. That link is recorded once per document or sheet (the *subject, parties and provenance* row's title blocks and front matter), not per claim.
- **Reported links carry the meaning where they occur:** feature-lead summaries (companies' proposals), meeting minutes, reviews and jury findings, cited standards ("per ASHRAE 90.1"), literature reviews, quoted correspondence.
  - Claims held by different parties are different claims for alignment.
  - The same proposition held by another party is reported as its attribution changed.
- **Negation and dispute are attitudes, not values:** "Company A does not support option 2" is A's stance on option 2, not a value "not supported" on the item.
- **Basis** (measured, calculated, simulated, projected, required, targeted, asserted) is the attitude of the innermost link. The [scheduling plan](scheduling-and-triage-2026-09-23.md)'s epistemic-status milestone asks readers for it; this record gives it its place.
- **Chains are usually short** (none to two reported links); the record allows any depth.

### Context outweighs its claims

*The owner, 2026-10-14:* "In practice, context is likely one or two orders of magnitude larger than most claims."

- **Stored once, and referenced by claims.** Context records follow the document's structure: the document, a sheet, a section, a list, a table, a note, a legend, a figure.
  - A claim points to the records that hold it, and to those that reach it by reference: a general note's "unless noted otherwise", a footnote marker, a legend.
  - A claim's context is that path and those references, not a copy. (Milestone 1's position copies its list's lead-in into each item's claims; milestone 2 makes it a reference.)
- **A record's kinds are labels, not columns on claims.** One general note may be frame ("dimensions are to face of finish") and scope ("unless noted otherwise") at once; a heading may give both a subject and a scope.
- **Selected for each use, within a budget:**
  - the reader, what its span needs (today, the heading path);
  - the judge, what bears on the pair, above all where the two sides' contexts differ;
  - the report, all of it, on demand.
- **Measured:** the context each claim has (records and bytes), what each query and judgment was shown, and what it was not.

### Rules for using context

- **A position is weak identity.** The same label on both sides supports a match; a different label with the same name and value suggests renumbering, a common edit, not a different item. Positions never block a match.
- **A name as printed outranks a name as read.** Two readers naming one printed label differently aren't a rename.
- **The judge rules on subject, scope and frame separately,** each shown apart from the others; a difference in frame is a finding about context ("dimensions to face of finish against centreline"), not a changed value (design question 4).
- **Stance is compared as itself:** the source's chain against the source's chain; our own confidence never as a difference.
- **What isn't knowable stays unnamed.** A dimension whose direction can't be tied to a convention is recorded by its geometry ("vertical as drawn, along MEETING 101's west wall"), never given a conventional name the page doesn't print.

### Where the code mixes them today

- **`conditions`** is defined to readers as "load, scenario, time, tolerances, scope" (`tasks.py`): scope, with a tolerance, which belongs to the value.
- **Readers' conditions** hold where a claim sits ("Door Schedule") and frame ("face of finish"), as `align.py` notes, and positions ("Condition 1"; milestone 1).
- **Attributes** hold positions ("dimension 1") and names the page never prints ("depth").
- **The judge** is asked whether "entity, attribute, scope and operating conditions correspond", and answers with one `same_conditions`. The report's "conditions" kind is "conditions or scope".
- **Schema v2's unfilled fields** `context`, `topic` and `role` have no definitions; `context` names a field and the umbrella both.
- **`basis`** is the innermost link's attitude with no holder: nothing says whose requirement or whose measurement it is.

## Naming conventions across documents

Dimensions are the sharpest case, and the pattern carries over to other named quantities (a tower's fore-aft and side-to-side, a pump's rated and design points).

- **Match on structure before words:** the entity, the kind of quantity (a length), its role relative to the entity (one of a room's two plan dimensions; an opening's width or height), then the value. "Width", "depth" and "length" become the reader's labels, weak evidence.
- **Where direction is established** (a north arrow, a schedule's columns, both drawn the same way up), compare by direction.
- **Where it isn't, compare a room's plan dimensions as an unordered pair:** {23'-0", 24'-6"} matches {24'-6", 23'-0"} whatever each is called, and the report says "the dimensions agree as a pair". A room drawn turned 90° in another proposal is the same room.
- **A document's own vocabulary is recorded once:** a schedule headed "W × D", a glossary, defined terms. Claims named in it are tied to its terms, and two documents' vocabularies are compared as frame.
- **Abstain rather than guess:** "length" in one document and "depth" in another is "named differently", not a match or a change, unless geometry or a convention ties them.

## Measurement

- **Counts without the model, per document** (a new lab measure):
  - claims holding a position in their conditions, attribute or entity
  - claims named by position ("dimension 1")
  - claims carrying a position, a printed name, scope, frame, geometry or a reported holder in their context
- **The controlled corpus's keys gain context:** each listed fact's printed label; room dimensions by room and direction as drawn; the frame a document declares (units, what dimensions are measured to). Scoring then accepts a reading that names what's knowable ("Meeting 101, vertical dimension") and stops requiring a convention the page doesn't print. A scorer change is announced with before and after numbers, not folded into a lever's measure.
- **New controlled scenarios,** each a knob on an existing family:
  - a list item inserted (the spec has it), steps renumbered, nested lists, a list continued across a page
  - a sheet with and without a north arrow; a room drawn turned 90° between proposals; a schedule headed W × D against one headed W × L; dimensions to centreline against face of finish
  - a note's scope ("unless noted otherwise") with an exception, a footnote marker on a table value, a "typical" marker
  - a proposal whose holder changes between revisions; a view reported ("Company A proposes") against the same words stated in the authors' voice; a hedge added or removed
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

**Built and measured (2026-10-14):** the `positions` lever (`positions.py`); the [lever index](../reviews/levers.md) has the numbers. A default since 2026-10-14 (the owner: "We can make `positions:provenance` the default, seems mostly positive and it's already committed.").
- On the controlled corpus: conditions holding a position 81 → 0; 138 claims given a position; extraction unchanged; the spec's numbered and renumbered pairs' 9 uncertain facts confirmed, no false change. $0.002.
- A picture's claim quoting a list item takes the item's position too: without that, the PDF spec's overview and text readings of one condition stopped merging.
- **Not yet:** positions in attributes and entities ("condition 1" as an attribute), and alignment using a shared label as weak support.
- **Seen on the slices as the default:** a lead-in taken from a stamp ("PUBLIC DOMAIN", ken-cd), and a figure's panel labels ("(b)", "(d)", turbines) counted as a list with axis ticks for a lead-in. Context records from the page's structure (milestone 2) should tell a list's lead-in, a figure's panels and furniture apart.

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

### 2. Context records

- **Records once per document part** (document, sheet, section, list, table, note, legend, figure), each labelled with the kinds it gives (subject, scope, frame, stance); evidence points to the records that hold or reach it, beside its locator. The store's schema version bumped, with old stores read as having none.
- **Milestone 1's position** refers to its list's record instead of copying the lead-in.
- **Measured:** records and bytes of context per claim, and what each query and judgment was shown.
- **Name as printed, mechanically:**
  - table claims: the parse's row label and column header (the [one table model](one-table-model-2026-09-30.md) has them)
  - text claims: the label before the value in its sentence ("timeout of 856 ms")
- **Shown in the report:** "as printed: Condition 2 of 'A link failure is declared when…'"; a renumbering shown as such.
- **Explanations** get both claims' positions and printed names, so "renumbered" is named from evidence rather than inferred from numbers in the conditions.

### 3. Scope and frame

- **Situating finds scope sources and frames** per document, sheet and section: general notes, legends, abbreviation lists, declared units, north arrows and scales, "unless noted otherwise", "typical".
- **Claims take the frames and scope sources that reach them** (a sheet's notes apply to its sheet; a table's notes to its table; a footnote marker to its cell).
- **The reader's `conditions` split into scope and frame** (a prompt change, judged against null arms); a tolerance goes with the value.
- **The judge rules on subject, scope and frame separately,** and a difference in frame is reported as context, with the claims it covers.
- **The scorer** checks a claim's frame where the key declares it.

### 4. Drawing geometry

- **First, a look without the model:** can dimension strings (a dimension line, extension lines, ticks or arrows, a label along the line) be found in the vector drawing of the corpus's sheets and the slices' real drawing sets? Real sets are stored turned 90° (25 of the slices' 103 pages), so directions are taken as displayed.
- **If they can:** each dimension's direction, extent and what it bounds go into the tile's text layer ("24'-6" — vertical dimension, beside MEETING 101") and into the claim's context. Gridline references (A–F, 1–4) give places as a drawing's own coordinates.
- **If they can't:** the reader is asked for direction as drawn, judged against null arms.

### 5. Naming across documents

- **Room dimensions as pairs** where direction isn't established; by direction where it is.
- **A document's vocabulary** (schedule headers, defined terms) recorded and compared as frame.
- **Keys and scorer:** room dimensions keyed by room and direction as drawn; "named differently" scored as a comparison outcome.
- **Other paired quantities** (fore-aft and side-to-side, rated and design points) checked for the same pattern in the corpus and the samples.

### 6. Stance

- **First, a look at the corpus and the real pairs without the model:** where are views reported (feature-lead summaries' company tables, minutes, reviews, cited standards), and what share of claims sit in them?
- **The attribution chain on evidence:** links of holder, attitude and strength, outermost first; the document's link from its record (the *subject, parties and provenance* row), reported links from tables ("Company | Proposals"), "according to", quotations and citations, mechanically where the parse gives them.
- **The pipeline's link named as such:** the reader's confidence, verification, agreement and derivation grouped as our stance, and the schema's `basis` and `uncertainty` documented as the source's.
- **The reader asked for reported holders and attitudes** where the parse can't give them (a prompt change, judged against null arms; coordinated with the scheduling plan's epistemic status).
- **Alignment and the judge:** claims held by different parties don't pair; the same proposition with a changed holder or attitude is its own finding (design question 5).

### 7. Further contexts (to be ordered as earlier milestones report)

- **Clause and section numbers as positions:** 3GPP revisions renumber clauses; a claim's clause is provenance, and a moved clause is "moved", not removed and added.
- **Tables:** units rows, merged header spans, footnote markers, "typical" columns.
- **Charts:** series, axis and operating point as context, not attribute words.
- **Time and place in scope:** phase, year, level, zone, option or alternate ("base bid", "alternate 2"); options are names with identity, not positions.
- **Repetition:** the same value stated in many places, its occurrences as context for confidence ([evidence webs](README.md)).

## Design questions

Answered by the owner on 2026-10-14.

1. **Renumbering in reports:** shown as a finding of its own ("renumbered: Condition 2 → 3"), or only in the claim's detail? I'd show it among editorial changes.
   - **The owner:** "editorial changes, like a new page number if we added some text or section numbering if we inserted a section."
   - **So:** a changed position, page or clause number is reported among editorial changes, as a move is, never as a changed value.
2. **Unordered pairs:** may room dimensions whose direction isn't established be compared as a pair and reported "agree as a pair", rather than left uncompared?
   - **The owner:** "yes, agree as a pair if we don't have a clear idea on framing."
   - **So:** compared by direction where the frame establishes it (a north arrow, a schedule's columns, both drawn the same way up); as an unordered pair otherwise.
3. **The scorer's room dimensions:** keyed by direction as drawn, accepting any name, instead of the generator's width and depth?
   - **The owner:** "I waffle on this one: we can only score based on what's there, but we should also test under various conditions, and we should look into how data from context might augment framing of reads."
   - **Proposed:** each scenario's key holds what its page makes knowable. A sheet with a north arrow or a schedule headed W × D is keyed by those names; a sheet without them by direction as drawn, accepting any name. The scenarios with and without (Measurement) test both, and the reads with context added (milestones 3 and 4) are scored on the same keys, so a gain from framing shows.
   - **The owner:** "Q3: your proposal looks reasonable as a starting point."
4. **Frame to the judge:** shown as its own field, with its own ruling (my preference), or folded into conditions?
   - **The owner:** "this is clearly a lever, but you can start with your preference."
   - **So:** a lever, off until measured; its first setting shows the frame as its own field with its own ruling.
5. **Stance changes in reports:** a finding kind of its own ("now B's proposal, was A's"; "now required, was targeted"), beside "changed" and "conditions changed"? I'd add it.
   - **The owner:** "I agree this is the sort of change readers would be interested in seeing called out."
   - **So:** a finding kind of its own, in milestone 6.
