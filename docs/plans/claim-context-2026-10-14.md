# Claim context: what a claim is about, how to read it, where it came from and who holds it

- **Status:** Active (2026-10-14): written; milestones 1 to 3 built (positions a default; context measured, order revisited; context records kept, `records` and `editorial` defaults); Concepts rewritten (subject, scope, frame, provenance, stance); reviewed whole against the context model, with measurement rewritten and milestones reordered ([Review](#review-2026-10-14)); design questions 1–9 answered, claim identity to be considered further ([Claim identity](#claim-identity)).
- **The owner, 2026-10-14:** "Ideally, we'd avoid list positions as conditions of a claim, treating them as provenance instead (where a claim was made, how it was named). I feel there's a lot to improve in this domain of tracking the context of a claim. For A, we should consider what the model has access to as part of its query, and what a comparison of claims would have access to - was there enough information in the query to call it the non-conventional 'depth' instead of 'length'? If not, what sort of structure would provide the context for that info? Perhaps we should be examining how we'd approach different naming conventions for dimensions between papers, too."
- **Then:** "Write the plan, then start with list positions as provenance. Turn it into a full plan unless it proves very short; I expect there's a lot you can think up for how to handle provenance and contexts with a little brainstorming."
- **On the kinds of context (2026-10-14),** after I proposed subject, scope, frame, provenance and stance: "The names work; rewrite the plan's Concepts section. We can keep 'context' as the umbrella term. I expect we'll spend a fair bit of time on this, trying to improve capture of context per claim." Further words on stance and on context's size are quoted in Concepts.
- **The review (2026-10-14):** "Please give the plan a full review based on the adjusted context model (you did some of this, but it isn't clear to me that it was holistic), with some attention to how we'll measure outcomes and perhaps verify model quality at providing needed context or applying relevant context when provided."
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
- **Conventions that frame many claims are read once, if at all.** The same sheet's general notes say "ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE" and "ROOM AREAS ARE NET". Two proposals measuring to different faces would show equal rooms as different, or different rooms as equal, and nothing would say why. A revision changing only such a note changes the meaning of every dimension on the sheet, and today nothing reports it.
- **Who holds a claim is lost.** The RAN1 summaries tabulate companies' proposals; their claims named the subject but not the company, so Spreadtrum's "not needed" and ZTE's "support" were compared as one item changed ([comparing revisions](revision-comparison-2026-10-02.md)).
- **No measure says where context is lost.** The scorer counts conditions kept, but not whether a missed scope or frame was ever in the reader's query, whether the model ignored it there, or whether the judge applied it once shown. Without that, a fix can't be aimed: at the parse, at what a query is given, or at the model.

## Scope

- **In:** the context of a claim, every kind (subject, scope, frame, provenance, stance), through every stage: captured mechanically where the source's structure gives it, by the reader where only reading can; stored once and referenced; selected into the reader's and the judge's queries; applied by code or by the model; reported; and keyed, so each stage is measured. For drawings, what a value spans.
- **Shared with other plans:**
  - [Comparing revisions](revision-comparison-2026-10-02.md), design item 4 (identity at extraction, an entity register): the register names *things*; this plan records where a claim's subject came from (a heading, a row label, a title block) and how it was named. Its cheap partial steps (names by what a value measures, row labels and column headers kept) are built here or there, whichever comes first, not twice.
  - *Subject, parties and provenance* (plans index): the parties around a project and the document's own provenance (title blocks, front matter, issue status), and claims about parties told from claims about the subject. That work stays there; the attribution chain on each claim (stance) is this plan's, and takes the document's link from it.
  - [Scheduling and triage](scheduling-and-triage-2026-09-23.md), milestone 5 (epistemic status): asks readers for basis and uncertainty. Here those are the innermost link's attitude; the prompt work stays there. Its situating stage's figure and section "abouts" become context records here (milestone 3).
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

**Identity follows only roughly:** the table says how a comparison treats a difference once claims are paired, not which claims to pair. Which claims are the same is a weighted estimate over proxies from every kind, provenance included ([Claim identity](#claim-identity)).

### The kinds

| Kind | The question | What it holds | Today |
|---|---|---|---|
| **Subject** | What is it about? | the entity, and what identifies it (a tag, a row label, the heading it sits under) | `entity`, as the reader named it |
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
- **A context source, and the context it gives:** a heading, a list's lead-in or a sheet's general notes is provenance (where the claim sits); the scope, frame or subject it implies is a reading of it. Both are kept, so a reading can be checked against its source, and a query can be asked whether it held enough to give it (the drawing sheets' "depth" didn't).

**Identity cues:** a printed identifier, a position, a name as printed and geometry as drawn are provenance that alignment weighs in pairing claims ([Claim identity](#claim-identity)): a requirement's "TFV-45" strongly between versions of one document, a list position weakly and never against a match. None enters the verdict on a value.

**Stated, none, or unknown.** Each kind on a claim is one of three: stated (the source gives it, and the claim has it), none (the source gives none: the value holds unconditionally, the document declares no datum), or unknown (not captured, or not knowable from the page). Only stated against stated can differ; a scope stated on one side and unknown on the other is "not established", as the judge's veto says today, never a difference.

### Stance: attribution chains

*The owner, 2026-10-14:* "IIUC, stance is essentially closer to a form of provenance than to a scope, e.g. "Bob said that Alice thinks ...", and should be clearly separated from a model's own stance (e.g. "gemma-4 is confident that Bob is uncertain that Alice believes ..."). I certainly wouldn't place it under scope, but it might need more nuanced attention than the current plan assigns to it."

- **A proposition reaches a report through a chain of holders,** from the outside in: our reader, the document's authors, any parties they report, and the party that holds the proposition. "gemma-4 is confident that Bob is uncertain that Alice believes the timeout is 856 ms" has three links.
- **Each link has a holder and an attitude:** says, proposes, requires, targets, measures, calculates, estimates, believes, doubts, disputes, rejects. It may also have a strength: a hedge ("may", "likely") or a stated uncertainty.
- **The pipeline's link is kept apart from the source's.** The reader's confidence, its quote's verification, agreement among readers (occurrences), the derivation and the judge's confidence are our stance on the record.
  - They weight, order and filter findings, once measured against keys (calibration, below).
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
  - A claim's context is that path and those references, not a copy. (Milestone 1's position copies its list's lead-in into each item's claims; milestone 3 makes it a reference.)
- **A record's kinds are labels, not columns on claims.** One general note may be frame ("dimensions are to face of finish") and scope ("unless noted otherwise") at once; a heading may give both a subject and a scope.
- **A record has a reach** (the claims it applies to) **and a precedence** (which wins when two disagree): a sheet's general notes reach its sheet; a table's notes its table; a footnote marker its cell; a heading its section; a lead-in its list. The nearer record wins, and an explicit exception ("unless noted otherwise", a local note) beats a general one. Finding a record's reach is capture too, and measured.
- **Records are compared too.** A note, heading or lead-in that changes between revisions changes what every claim it reaches means, whatever their values. It is reported once, with the claims it reaches (design question 6), not as many claim findings or none.
- **Selected for each use, within a budget:**
  - the reader, what its span needs (today: the heading path, neighbouring text, a table's lead-in, numbered-item stems: the `neighbours`, `table_context` and `stem_context` levers);
  - the judge, what bears on the pair, above all where the two sides' contexts differ;
  - the report, all of it, on demand.

### Context through the pipeline

Each kind passes through the same stages. The table says where each is found and who applies it; every cell is a place a measure (below) can find a loss.

| Kind | Captured from | Selected into | Applied by | Reported as |
|---|---|---|---|---|
| **Subject** | headings, row labels, tags, title blocks, situating's abouts; the reader | the reader (heading path, stems); the judge (both claims' subjects and their sources) | alignment (the register, names), then the judge | the claim's entity, with its printed source |
| **Scope** | lead-ins, headings, captions, notes' reach, table columns (load case, month); the reader | the reader (the records reaching its span); the judge | the judge, ruling on scope apart | "conditions changed" (scope), or not established |
| **Frame** | general notes, legends, declared units, north arrows and scales, schedule headers, abbreviation lists | the reader where it changes a reading (bare numbers under "all dimensions in mm"); the judge | code (units, a datum offset, unordered pairs, a note's reach), the model checking it where unclear; the judge otherwise | "frame differs", once per record, with the claims it reaches |
| **Provenance** | the parse: locator, section path, positions, printed names, geometry | the explainer; alignment's identity cues; never the judge's verdict | alignment (weak support), explanations | editorial changes: renumbered, moved, a new page |
| **Stance** | title blocks (the document's link); "Company \| Proposals" tables, "according to", citations; the reader | the reader (who holds what it reads); the judge | alignment (different holders don't pair); the judge | "attribution changed", "now required, was targeted" |

**Who applies context** (design question 7):
- **Code, for mechanical and hierarchical context:** units and datums; unordered pairs; renumbering; a record's reach down the document's structure (sheet, section, table, list) and its precedence.
- **The model checks code's heuristics where they're unclear:** signals flagged, the model asked, its answer applied mechanically and checked, as the table structure query does (a note whose reach the layout leaves open; a lead-in that may be a stamp).
- **The model supplies context buried in images and prose:** a north arrow, a note's reach stated in words, a holder named in a sentence, a scope given only in a paragraph.
- **The probes measure the model's part,** and say where a heuristic needs its check. Our own link's figures (confidence, agreement) are applied only once calibrated.

### Rules for using context

- **A position is weak identity.** The same label on both sides supports a match; a different label with the same name and value suggests renumbering, a common edit, not a different item. Positions never block a match.
- **A name as printed outranks a name as read.** Two readers naming one printed label differently aren't a rename.
- **The judge rules on subject, scope and frame separately,** each shown apart from the others; a difference in frame is a finding about context ("dimensions to face of finish against centreline"), not a changed value (design question 4).
- **Stance is compared as itself:** the source's chain against the source's chain; our own confidence never as a difference.
- **Unknown is never different.** Only stated against stated can differ.
- **What isn't knowable stays unnamed.** A dimension whose direction can't be tied to a convention is recorded by its geometry ("vertical as drawn, along MEETING 101's west wall"), never given a conventional name the page doesn't print.

### Where the code mixes them today

- **`conditions`** is defined to readers as "load, scenario, time, tolerances, scope" (`tasks.py`): scope, with a tolerance, which belongs to the value.
- **Readers' conditions** hold where a claim sits ("Door Schedule") and frame ("face of finish"), as `align.py` notes, and positions ("Condition 1"; milestone 1).
- **Attributes** hold positions ("dimension 1") and names the page never prints ("depth").
- **The judge** is asked whether "entity, attribute, scope and operating conditions correspond", and answers with one `same_conditions`. The report's "conditions" kind is "conditions or scope".
- **`claim_id`** hashes conditions (scope and frame mixed, positions until milestone 1) and basis, but not a holder.
- **Schema v2's unfilled fields** `context`, `topic` and `role` have no definitions; `context` names a field and the umbrella both.
- **`basis`** is the innermost link's attitude with no holder: nothing says whose requirement or whose measurement it is.
- **The controlled keys** hold conditions as one string; the scorer's "conditions kept" can't tell scope from frame, nor a misplaced context word from a missing one.

## Naming conventions across documents

Dimensions are the sharpest case, and the pattern carries over to other named quantities (a tower's fore-aft and side-to-side, a pump's rated and design points).

- **Match on structure before words:** the entity, the kind of quantity (a length), its role relative to the entity (one of a room's two plan dimensions; an opening's width or height), then the value. "Width", "depth" and "length" become the reader's labels, weak evidence.
- **Where direction is established** (a north arrow, a schedule's columns, both drawn the same way up), compare by direction.
- **Where it isn't, compare a room's plan dimensions as an unordered pair:** {23'-0", 24'-6"} matches {24'-6", 23'-0"} whatever each is called, and the report says "the dimensions agree as a pair". A room drawn turned 90° in another proposal is the same room.
- **A document's own vocabulary is recorded once:** a schedule headed "W × D", a glossary, defined terms. Claims named in it are tied to its terms, and two documents' vocabularies are compared as frame.
- **Abstain rather than guess:** "length" in one document and "depth" in another is "named differently", not a match or a change, unless geometry or a convention ties them.

## Claim identity

*The owner, 2026-10-14:* "all of these things are heuristic proxies for claim identity; otoh, philosophically 'identity' itself is a difficult topic. Consider this closer to a weighted analysis. Some parts of provenance do make good claim identities, for example, e.g. in a requirements database a requirement named "TFV-45" is a pretty good identity for comparing versions of a model, less so for comparing across models. Let's consider identity more carefully, but prepare an initial heuristic proxy as a starting point."

Identity is estimated, not defined: every part of a claim is a proxy for it, weighed by what is being compared.

**Three questions, kept apart:**
- **The same reading?** Two readings of one passage in one document (an overview and a text task, two tiles), merged as occurrences. Near exact: the proposition and its context's words, as `claim_id` hashes them; the same quote and place support it strongly.
- **The same item in another version?** Alignment's question in revisions mode. Most of a revision is unchanged, so values and the document's own identifiers count most.
- **The same item in another design?** Proposals mode, or another model of the same system. Each team numbers its own and values differ by design, so identifiers and values count little; what a thing is (its kind, its role, its subject as named) counts most.

**The proxies, and their initial weight** (by eye, as alignment's were: decision 7):

| Proxy | Kind | Between versions | Between designs |
|---|---|---|---|
| A printed identifier that names (requirement "TFV-45", tag "P-101B", room 104, sheet A-101) | provenance | strong | weak |
| Values with their units, rare ones more | proposition | strong (alignment's 0.6 today) | weak |
| The subject, as printed before as read | subject | moderate | strong |
| The attribute: the kind of quantity and its role | proposition | moderate | strong |
| Place: section path as printed, sheet | provenance | moderate | weak |
| The quote's words | provenance | moderate (restated text less) | weak |
| A list position, a clause number | provenance | weak, and only for a match | none |
| Scope | scope | must agree where both stated; unknown never conflicts | the same |
| Holder | stance | different holders are different claims | the same |
| Frame | frame | not weighed: reconciled after pairing | the same |

**The initial proxy:**
- **Alignment's item score extended:** printed identifiers as a feature of their own, beside values, name and attributes; position and place as small positive terms; scope and holder as gates (where both are stated and differ, no pair). Weights per mode, as in the table.
- **Shown with their evidence,** as alignment's groupings are now, so a pairing can be read and questioned.
- **`claim_id` stays the same-reading key:** its conditions split into scope and frame, and the holder added, once they're filled apart. A refactor while nothing fills them, proven by replay.

**Then, more carefully:**
- **A research note on identity** across versions and designs: what a requirements database's IDs promise and don't (an ID reused, retired or split); things that split or merge; identity of items against identity of claims about them.
- **Weights learned, not set:** record linkage weighs each proxy by how often it agrees among true counterparts against among non-counterparts (Fellegi and Sunter's method). The controlled pairs' keys give both rates, per mode and per family; the result is a calibrated score, not a threshold set by eye.

## Measurement

There's no ground truth to measure against ([decision 0018](../decisions/0018-several-raters-none-ground-truth.md)): quality is estimated from keys where documents are generated, mechanical checks everywhere, and raters on real documents. Context adds a question the extraction measures don't ask: when a claim's context is wrong, **where was it lost?** Each layer below answers part of that, and each milestone names its target and guard from them before it's built.

### 1. Inventory (no model, every document)

- **Per document:** context records by kind; claims per kind stated, none and unknown; context bytes per claim; what each query and judgment was shown.
- **Misplacements:** context in the wrong field, found mechanically: positions in conditions, attributes or entities; scope words in attributes; frame words ("face of finish", "net") in conditions.
- **Grounding:** each claim's context words (its scope and frame, its holder) found in what its query held: the page's text, the heading path, the records selected. Context the query didn't hold is **unsupported**: invented, or drawn from the image (counted apart for image tasks). This runs on real documents, with no key; it's the context counterpart of quote verification.

### 2. Capture, against keys (controlled corpus)

- **Keys gain context per kind:** each fact's subject source, scope, frame, holder and attitude, position and printed label, as the generator wrote them; and what the page makes knowable (a room dimension's direction as drawn; a conventional name only where a north arrow or a schedule's header gives it; design question 3).
- **Per kind, stated right, missed, wrong, or invented** (given where the key says none or unknowable); "conditions kept" becomes its scope and frame parts.
- **Placement:** for each keyed context item, the field it landed in (scope, frame, attribute, entity, nowhere): a confusion matrix of kinds. It measures separation, not just presence: a frame read into conditions is captured but misplaced.
- **Knowability:** named where knowable; abstained (geometry, "named differently") where not. A conventional name the page doesn't give counts as invented.

### 3. Sufficiency: was it in the query?

The owner's question about "depth", asked of every miss. For each keyed context item a claim missed, misplaced or got wrong, the query that read it (stored, and dumped by the lab's `queries dump`) is searched for the item's source:

- **not shown:** the source wasn't in the query (the parse missed it, or selection left it out, or the budget cut it): our pipeline's loss, fixed by capture or selection;
- **shown, not used:** the source was there and the claim lacks it: the model's loss, fixed by instruction, by structure (a field for it), or by code applying it;
- **shown, misapplied:** the source was there and the claim reads it wrongly (a note applied beyond its reach).

The same split is made for the judge: was each claim's context in the pair's prompt? This is mechanical over stored queries, so it costs nothing, and its three counts say where a milestone should aim.

### 4. Application: does the model use context it's given?

Small, fixed **probe batteries**, recorded once per model and replayed thereafter, measure the model apart from the pipeline. Each probe varies one kind of context and nothing else, so its expected answer is known.

- **Reader probes:** minimal pages or passages where only context decides the reading: bare numbers under a units note; list items under a scoping lead-in; a "Company | Proposal" table; a note that reaches one table and not the next.
  - **Sensitivity:** with the context and without it, the reading changes as it should.
  - **Specificity:** with context that doesn't reach the claim (another sheet's note, an irrelevant lead-in), the reading doesn't change.
  - **Precedence:** with a general note and a local exception, the exception wins.
  - **Abstention:** with the context a reading needs absent (no north arrow), the reader names geometry, not a convention.
- **Judge probes:** claim pairs built from keyed facts, varied one kind at a time: the same values in different frames; the same proposition held by different parties; a renumbered position; a different scope; scope known on one side only. Expected rulings follow the table in Concepts. Each pair is asked in both orders; irrelevant context added mustn't change the verdict.
- **Counterfactual pairs:** controlled revision pairs that change only a context record (the general note's datum, a lead-in, a table's holder column), with values unchanged. The comparison should report the context change once, with the claims it reaches, and no value change.
- **Scored as accuracy per kind and per property** (sensitivity, specificity, precedence, abstention), with agreement across orders for the judge. Batteries are tens of queries: cents per model.
- **They qualify a model:** the same batteries run against another model or backend before it's used, and after a prompt change to the context instructions, as a regression check beside the null arms.
- **They decide who applies context** (design question 7): a kind the model applies reliably when shown stays the model's; one it doesn't is applied by code, or given a field of its own.

### 5. Outcomes: comparisons and reports

- **On the controlled pairs, per scenario family:** unchanged facts confirmed, false changes, kinds named right (the guard, as now), and the context findings' precision and recall: renumbered, moved, frame differs, attribution changed, named differently, agree as a pair.
- **Reports:** a changed context record reported once, with the claims it reaches; editorial changes apart from value changes; no finding whose only difference is provenance.

### 6. Real documents (no keys)

- **Mechanical:** the inventory and grounding above, on the slices and the real pairs.
- **Eye looks:** the real pairs (3GPP revisions renumber clauses and tabulate companies' views; drawing sets hold general notes), read by me at each milestone and recorded.
- **Raters:** review batches gain a context rubric: is the claim's scope right, is any needed scope or frame missing, is its holder right, is anything invented. The pairwise rubric's "needed conditions kept" splits by kind. Rated by panels of models; agreement measured, as for any rubric (design question 9).
- **People's feedback** comes from using the tool's results at work: generic, about the outcomes they needed. Recorded as it comes, and turned into probes, scenarios or rubric clauses where it points at a context; no rating batches asked of people.

### 7. Our own link: calibration

- The reader's confidence and the judge's confidence, against keyed correctness: a reliability curve per kind of claim. Until calibrated, they order findings but don't filter them.

### Costs and guards

- **Cost per query:** context bytes and tokens added, calls added, output tokens per claim (each new field in an answer costs output, and a small model's accuracy may fall as its schema grows).
- **The guard for every lever:** facts read right on the corpus, paired by document; for prompt changes, against null arms ([judging a lever](../samples-and-testing.md#judging-a-lever)).
- **A scorer change** (new keys, new splits) is announced with before and after numbers, never folded into a lever's measure.

## Rules against drift

- **Measure before building:** each milestone names its target and guard from the measurement layers, and takes a baseline, before its first change.
- **Every change in behaviour is a lever, off by default** until measured, and listed in the [lever index](../reviews/levers.md). Defaults change only on measured evidence and the owner's word.
- **Refactors needed on the way are separate steps,** proven by replay ([0027](../decisions/0027-behaviour-changes-apart-from-refactors.md)). Likely: context records on evidence, the store's schema version, and claim identity.
- **Mechanical before model:** context is taken from the source's structure wherever the parse has it. The reader is asked only for what reading alone can give, and each such prompt change is judged against null arms and the probe batteries.
- **New directions found on the way** become tentative rows in the plans index, not milestones here.
- **Each milestone ends with a commit after the full suite passes,** and reports what it spent.

## Milestones

### 1. List positions as provenance

The first step, and the cheapest: no extraction query changes.

**Built and measured (2026-10-14):** the `positions` lever (`positions.py`); the [lever index](../reviews/levers.md) has the numbers. A default since 2026-10-14 (the owner: "We can make `positions:provenance` the default, seems mostly positive and it's already committed.").
- On the controlled corpus: conditions holding a position 81 → 0; 138 claims given a position; extraction unchanged; the spec's numbered and renumbered pairs' 9 uncertain facts confirmed, no false change. $0.002.
- A picture's claim quoting a list item takes the item's position too: without that, the PDF spec's overview and text readings of one condition stopped merging.
- **Seen on the slices as the default:** a lead-in taken from a stamp ("PUBLIC DOMAIN", ken-cd), and a figure's panel labels ("(b)", "(d)", turbines) counted as a list with axis ticks for a lead-in. Context records from the page's structure (milestone 3) should tell a list's lead-in, a figure's panels and furniture apart.
- **Left:**
  - positions in attributes and entities ("condition 1" as an attribute, about 40 claims): the same label moved from those, or a prompt field for it (judged against null arms);
  - alignment counting a shared label as weak support, never a conflict.

### 2. Measuring context

Before records are built, so each later milestone has a baseline. Almost all of it without the model.

- **The inventory and grounding** (layer 1) as a lab measure, per document, on the controlled corpus, the slices and the real pairs.
- **Keys gain context per kind** (layer 2), from the generator: scope and frame apart, holders where a family has them, positions and printed labels, and what each page makes knowable. The scorer reports per kind, with the placement matrix. Announced as a scorer change, with before and after numbers.
- **The sufficiency audit** (layer 3) over the corpus's stored queries: every context miss classed as not shown, shown not used, or misapplied, for the reader and the judge. The drawing sheets' "depth" is its first case.
- **A first probe battery** (layer 4), reader and judge, a few probes per kind and property, recorded for gemma-4 as its baseline.
- **Calibration** (layer 7) of the reader's confidence on the corpus, as a baseline.
- **Then:** the order of milestones 3 to 8 revisited on what the audit and probes show, and reported.

**Built and measured (2026-10-14):** `scripts/controlled.py context` (context.json), `scripts/context.py` for any runs, `scripts/probes.py` (benchmarks/probes); lab `bench/context.py`, `bench/probes.py`, `bench/controlled/contexts.py`. Spent: under a cent (the probes); the rest replays stored runs.

- **Keys:** every fact's context by kind. Of the 40 conditions the generator writes, 13 aren't scope: frames ("95th percentile", "3-second gust"), bounds ("maximum"), subjects ("Hall C", "across the four halls"), provenance (the lift hill "as revision A" had it) and siblings (a revision row's description given as its date's condition). Declared once and keyed for the facts they reach: the plan sheet's general notes (frame), the coaster schedule's datum (frame), the pump schedule's rated points (scope). Room widths and depths keyed as resting on an unprinted convention. The documents regenerate byte for byte; only keys changed.
- **Inventory and grounding** (layer 1). Conditions grounded in what their request showed, for text and table readers; image readers' conditions are counted apart (the picture isn't text):

  | Runs | Readings | With conditions | Grounded | Partly | Unsupported | Image, unsupported |
  |---|---|---|---|---|---|---|
  | controlled (210) | 11,783 | 4,195 | 3,545 | 95 | 34 | 484 |
  | slices (8) | 5,082 | 1,712 | 1,201 | 127 | 14 | 161 |
  | real pairs (3) | 20,024 | 13,815 | 11,511 | 1,123 | 75 | 50 |

  - Readers rarely invent context in text: unsupported conditions are mostly fair inferences ("in September" under a column "Sep").
  - **Numbered labels where names belong:** "dimension 1/2/3" on drawings (slices 21, controlled 124 in attributes); table rows as conditions ("row 8", the slices' schedules); procedure steps as conditions in TS 38.300 (640: "after step 3", "step 7/8 of transition"), a scope that points at a position.
  - **Frame words in conditions:** "typical" on the slices' drawings (93 in dc-sheets).
- **Capture against keys** (layer 2), for the facts read right or loosely, and **sufficiency** (layer 3) for each lost item:

  | Kind | Facts | In its place | Elsewhere | Nowhere | Not shown | Shown, not used | Misapplied | Image only |
  |---|---|---|---|---|---|---|---|---|
  | scope | 1,810 | 1,775 | 29 (attribute) | 6 | 0 | 29 | 4 | 2 |
  | frame | 239 | 148 | 18 (attribute) | 73 | 30 | 24 | 0 | 37 |
  | subject | 243 | 200 | 0 | 43 | 15 | 27 | 0 | 1 |
  | bound | 81 | 60 | 0 | 21 | 0 | 21 | 0 | 0 |

  - **Scope is captured** (98%); its losses are the reader's: the spec's "When the link is lightly loaded, the following values apply." shown and not used (29).
  - **Frame is where context is lost:** the plan sheet's general notes aren't in a tile's request (30 not shown), and are shown but not used where they are (24).
  - **Names resting on an unprinted convention:** 71 of 82 room dimensions were called width, depth or length, which the sheet doesn't say ("depth" again).
  - Provenance kept out of conditions: the superseded lift hill's "revision A" is in conditions (5), as are revision rows' descriptions (15 of 19).
- **Probes** (layer 4), gemma-4-31B: 25/29 through the product.
  - **The reader applies context it's shown:** a lead-in's scope, a units note, a local exception over a general note; it keeps a scope to its section, and names each company holding a proposal. It doesn't abstain: "12'-6" by 14'-0"" became a length and a width.
  - **The judge doesn't apply stance:** the same timer proposed by Company A and by Company B is "equivalent", in both orders. It calls differing frames and scopes "different", which only the conditions veto turns to uncertain: its own answers pass 11/16; 6 of 8 probes answered alike in both orders.
- **Calibration** (layer 7): table rules give 0.9 to every claim (99.8% right). Text and image readings' confidence rises with accuracy (below 0.9: 11% and 59% right; 0.95 and over: 90% and 92%), but 97% of readings are 0.95 or over: it ranks a few doubtful claims and doesn't separate the rest.
- **The judge's sufficiency** (layer 3's second half): the judge is shown the two claims (and images, where `verify_visuals` sends them), so what it can know is what both readers captured: layer 2 on both sides, with the probes for its use of it. Measured pair by pair in milestone 4, when it rules on scope and frame apart.

**Lever ideas** from these findings are rows in the [lever index](../reviews/levers.md)'s *Ideas not built yet* ("Claim context, …"): 13, for the reader's selection and fields, positions, the judge's rulings and order, alignment's gates and identifiers, explanations and confidence.

**The order revisited:** scope capture is good; frame (not shown, then not used), names by unprinted convention, and the judge's stance are where context is lost. So:
- **Context records stay first** (milestone 3): the sheet's notes' reach is a record and a selection, the cheapest cure for "not shown".
- **Scope and frame next** (milestone 4), with frame's selection into tile requests first.
- **Stance moves up** (now milestone 5): the judge pairs different holders as one claim, the RAN1 pair's real failure; a holder gate in alignment is code (design question 7), cheap, and the reader already names holders when stated.
- **Drawing geometry and naming across documents follow** (6 and 7), then further contexts, with procedure steps, table row numbers and clause numbers as positions from the real documents.

### 3. Context records

- **Records once per document part** (document, sheet, section, list, table, note, legend, figure), each labelled with the kinds it gives (subject, scope, frame, stance) and its reach; evidence points to the records that hold or reach it, beside its locator. The store's schema version bumped, with old stores read as having none.
- **Subject sources:** headings, row labels and title blocks as records; situating's figure and section abouts as subject and scope records.
- **Milestone 1's position** refers to its list's record instead of copying the lead-in; the stamp and figure-panel cases told apart by the record's kind.
- **Name as printed, mechanically:**
  - table claims: the parse's row label and column header (the [one table model](one-table-model-2026-09-30.md) has them)
  - text claims: the label before the value in its sentence ("timeout of 856 ms")
- **Stated, none, unknown** recorded per kind on each claim.
- **Identity, a first proxy** ([Claim identity](#claim-identity)): printed identifiers as alignment's own feature, positions and place as small terms, weights per mode; `claim_id`'s parts named (a refactor, proven by replay).
- **Shown in the report:** "as printed: Condition 2 of 'A link failure is declared when…'"; a renumbering among editorial changes.
- **Explanations** get both claims' positions and printed names, so "renumbered" is named from evidence rather than inferred from numbers in the conditions.
- **Measured:** the inventory per kind; misplacements; grounding; the spec pairs' renumberings named.


**Built and measured (2026-10-14)** (the owner: "Go ahead with milestone 3, context records."); the [lever index](../reviews/levers.md) has the rows. Spent: $0.20 (judge and explainer arms); the rest replays.
- **The store's records** (schema 9: new stores): `ContextRecord` per content, saved with the tasks whose claims reference them; `Evidence.records` and `Evidence.printed`, provenance both (the judge never sees them). Reports and evidence.json carry a content's records once; a claim's card shows its name as printed, its position with its list's lead-in, and the table, notes and legends reaching it.
- **`records`** (a default since 2026-10-14): lists (lead-in and labels), a drawing sheet's notes and legends (reaching every claim on the sheet), tables read by rules (title, headers, the context their rows are given), and names as printed (a rule claim's row label and header; a text claim's words before its value). The controlled corpus: 256 table, 31 list and 6 note records; 4,800 of 9,359 claims reference one; 5,910 have a name as printed. Extraction and comparisons as before. $0.
- **`editorial`** (a default since 2026-10-14): a pair judged or settled equivalent at differently labelled places in its lists is noted "renumbered", an editorial change (design question 1). The controlled pairs: 19 notes, the renumbered spec's three conditions in every format; verdicts unchanged. $0.
- **`align_printed`** (off; the first identity proxy): a table claim's column header stands for its attribute in alignment. No different on the corpus; text claims' names, tried too, lost the coaster's lift hill change in every format ("lift hill rises" for "height"), so only headers count.
- **`explain_context`** (off): positions and names as printed shown to the explainer. No different against a null arm (kinds 150 and 148 of 155, records alone 151).
- **Not done here, moved:**
  - *Stated, none, unknown per kind* and `claim_id`'s parts named: with the scope and frame split (milestone 4) and holders (milestone 5), when there are parts to name.
  - *Records from situating* (a sheet's title block, figures and their abouts, section abouts as subject and scope records) and *a document's glossary*: situating runs after extraction and only for PDFs; they come with milestone 4's selection, where records are given to requests.
- **Defaults** (2026-10-14; the owner: "Move forward with the recommended defaults."): `records` (a post setting, $0, extraction and verdicts unchanged; what reports and the next milestones read) and `editorial` (19 right notes, no verdict changed). `align_printed` and `explain_context` stay off until a corpus pair can move them.

### 4. Scope and frame

- **Situating finds scope sources and frames** per document, sheet and section: general notes, legends, abbreviation lists, declared units, north arrows and scales, "unless noted otherwise", "typical"; each with its reach and precedence.
- **Claims take the frames and scope sources that reach them,** and the reader's query is given those its span needs (selection, measured by the sufficiency audit's "not shown"): first a sheet's notes and legends (milestone 3's records) in its tiles' requests.
- **Records from situating and the glossary** (moved from milestone 3): a sheet's title block, figures and their abouts, section abouts, and a document's defined abbreviations, as records requests and claims can be given.
- **Stated, none, unknown per kind,** and `claim_id`'s parts named, once scope and frame are apart (moved from milestone 3).
- **The reader's `conditions` split into scope and frame** (a prompt change, judged against null arms and the probes); a tolerance goes with the value.
- **Who applies frame:** units and datums by code where the probes say the model doesn't apply them reliably; the rest by the judge.
- **The judge rules on subject, scope and frame separately** (a lever; design question 4), and a difference in frame is reported as context, with the claims it covers.
- **Changed records reported once:** a note, heading or lead-in that changes between revisions, with the claims it reaches (design question 6).
- **The scorer** checks scope and frame per kind where the key declares them; the counterfactual pairs added (layer 4).

**Progress (2026-10-14):**
- **Context held by reference counted** (a scorer change): a keyed scope, frame or subject found in the text of a record the claim references (the `records` lever's lists, sheet notes and tables) is in its place, placed "records". The controlled corpus, before and after:
  - frame: nowhere 73 → 0 (records 73: the plan sheet's general notes, which every claim on the sheet references); lost 91 → 18 (not shown 30 → 0, image only 37 → 0, shown and not used 24 → 18: frames in attributes, wtp's "95th percentile turbidity");
  - scope, subject and bound unchanged: scope's 29 shown and not used are mostly scope in the attribute ("peak flow (maximum day)", "Rated point TDH"), two the spec's lead-in;
  - a revision row's description held by its table's record (1), provenance kept out of the claim's words.
- **So the reader's selection isn't where context is lost** on the corpus: a sheet's notes in its tiles' requests (the first item above) has no target left there, and waits for a document whose notes change a reading (a units note over bare numbers). What's lost is downstream: the judge is shown neither side's records, and a record that changes between revisions isn't reported.
- **The judge shown records, ruling on subject, scope and frame apart** (`judge_context`, off; design question 4): each claim's records as a `context` field, and `same_subject`, `same_scope`, `same_frame` ruled yes, no or unknown; a part ruled "no" makes an equivalent or different relation uncertain.
  - The judge probes gain five that give context in records only, and are asked under the battery's settings and under each judge lever (`JUDGE_ARMS`).
  - Off: the three sensitivity probes (frame in notes, scope in a lead-in, units in headers) all called equivalent (0/6). On: 26/26 of the judge probes, 13/13 alike in both orders (off: 18/26, 11/13).
  - The model itself answers "different" for a frame or scope apart; its rulings make it uncertain.
  - The controlled pairs (against `record_changes` alone, and a null arm asking the same rulings with an empty context): no different from the null, both worse than without. Kinds named right 170 → 161 (null 162); the spec's scope pairs went from uncertain to complementary or unrelated, ruled the same subject in another scope. The datum pair's heights were ruled a different frame, naming the datum. Off; $0.19 the two arms.
  - Tweak direction (the lever index): in revisions mode, the same subject in another scope or frame is a conditions change where the claims' records were restated; the rulings alone also fit siblings (a chart's months).
- **Restated records reported once** (`record_changes`, the default since 2026-10-15; design question 6): each side's records paired by kind and heading or title (an untitled table by its headers), one whose words differ, numbers aside, listed once with the claims it reaches.
  - The counterfactual pairs: restated-context facts reported 0/39 → 34/39 (the plan's notes 14/14; the datum lead-in 5/5 in every format but Markdown, whose tables have no records); verdicts unchanged; replayed, $0.
  - First built on a record's whole text and labels: 48 changes listed, 39 false (an item inserted renumbered a list's labels; a table's text window moved; untitled tables paired by place). Fixed: a list by its lead-in, a table by its headers and the value-free sentences above it; 9 listed, all restatements.
- **Scope and frame apart in the reader** (`split_conditions`, the default since 2026-10-15): conditions hold scope, a `frame` field how a value is read (measured to or from, a datum, net or gross), a tolerance its `uncertainty`; the table rules ask for a frame too. A set frame is part of the claim's identity; readings, alignment, explanations and the report carry it.
  - The controlled corpus's PDFs, against the base and a null arm: of 197 keyed frames, 51 in the frame field (none before), in conditions 104 → 30 (the null 89), none misplaced in attributes (4 before); scope unchanged. Facts right no different (3,587 → 3,591, the null 3,581).
  - The reader rarely fills the field by itself (the plan's "to face of finish"); a frame said in a table's lead-in mostly stays with the table's record, which the claims reference. The reader put some limits in frame ("maximum", "up to"); told a limit isn't a frame, it put none there, and placed 37 frames in the field (51 before), facts right still no different. As the default, every format: frames in their own field 57, in conditions 180 → 80; no false change in the comparisons.
  - Two measure notes: *claims right* counts distinct wordings of a fact (the lever's readers word alike more often: 2,385 → 2,658 facts in one wording), so it fell with nothing lost; a bound written into the value ("<= 39") is placed nowhere, the value not being searched.
  - The units the context measures read (`rounds.collect`) kept no frame: fixed before measuring.
- **Who applies frame** (design question 7), from the probes: the reader applies the frame and scope it's shown (a units note gives "mm"; an exception wins over its general note; a lead-in's scope reaches its items), so selection decides; code applies what changes between revisions (`record_changes`) and keeps stated frames apart (`_frames_differ`, `readings`); the judge isn't shown records (`judge_context`: the probes passed, the corpus did worse). Code takes units next only where a scenario shows the reader missing a declared unit over bare numbers.
- **Stated, none, unknown:** unknown is never different already: readings agree when one side states nothing, alignment keeps apart only frames both state, and the judge's veto leaves a scope on one side "not established" (the scope-unknown probe). A field per claim waits for a consumer; "none" needs the source to say so (a sheet declaring no datum), not an empty field.
- **The scorer per kind:** `scripts/paired.py` measures scope, frame and subject kept (in its place, or by a record the claim references) and frame in its field, so a lever can name them as target or guard. The context measures now read every reading, not a unit's first sighting: frames in their field 57 → 96 on the corpus (the coaster's tiles gave frames its figure task didn't).
- **A units note over bare numbers** (the controlled corpus's units pairs): the coaster schedules' headers lose their units to a note under the lead-in; in one pair nothing else changes, in the other the note gives heights in metres, numbers kept.
  - Read alone, 92/92 facts right in every format: the reader applies a note's units to bare cells, so code needn't (design question 7).
  - Units moved: no false change. Heights in metres: reported 5/5 in PDF and Markdown, 3/5 Word and Excel, 2/5 PowerPoint; the rest uncertain, since one side's heights carried the speeds' "at the element's entry", so matching conditions weren't established.
- **A sibling's context misapplied:** the coaster's speed scope is keyed as a sibling of the schedule's other values, and `paired` counts facts given it in their own words. Of 2,122 keyed siblings, 186 carry it in conditions (PDF 72, Word 51, Excel 44, PowerPoint 19, Markdown 0); the table rules write it into every column's template.
  - `column_conditions` (off) tells the rules a condition named for some columns is theirs alone: 186 → 141, its null arm 146, no different; facts right unchanged. One answer applies it to a whole table or none, and a re-ask flips it whatever the prompt says; the answers still misapplying it write one wildcard template over the columns. Then by structure (`conditions_by_column`, off): a template may give conditions and frames by column, added by code to those columns' claims. With a worked example, 41 of 164 coaster templates used it, mostly for the heights' frame; siblings misapplied 164 → 141, its null arm 124, so no better, and left there. The lead-in gives "design values" to the speeds alone too, and readers stretch the whole phrase over every column; a sibling's scope stays a judge's and alignment's problem ("not established") until a document shows it mattering more than this one sentence.
- **A subject only the sheet gives** (the controlled corpus's `lcc-plans`, PDF only): two sheets alike but for the hall their title blocks name (A-201 Hall C, A-202 Hall D), the same room and door numbers on each, every size different; its pair widens Hall D's room 102. On the corpus nothing else was left for records from situating: the one subject "not shown" elsewhere is a key's wording ("across the four halls" for "the four halls together").
  - Baseline: the hall kept for 2 of 63 facts (in the entity); 36 shown and not used, 19 not shown, 6 in the image only. The comparison: no false change, 1/2 changes found (the area uncertain), 64/71 unchanged facts confirmed (7 not read), and 7 findings pair a claim with another fact than its own ("across facts"): difference precision 0.33. Alignment groups both halls' Meeting 101 as one item, but pairs no differing claims across the sheets: the 7 are Hall D's tiles' generic readings ("dimension line", "MEETING 10"). $0.06.
  - The controlled replays were refreshed from fresh stores: the committed replay scores predated `split_conditions` and `records` (101 of 210 documents differed from the recorded); replayed and recorded now agree on every document and pair.
  - `sheet_records` (a default since 2026-10-15): the title block, as `figures.title_block` reads it, is a record every claim on its sheet references (the report's claim cards show it). The hall kept for 63 of 63 facts (2 before), every other document and pair unchanged; $0. Built first with alignment keeping a sheet's claims together: the set's comparison got worse (findings across facts 5 → 14), since nothing crossed the sheets to begin with; withdrawn. What the record changes downstream waits on the judge being shown records (`judge_context`, measured worse) or a report reader using the cards.
- **Abbreviation lists left as lever ideas** (the owner, 2026-10-15: "If we cannot effectively test abbreviation lists, we should record them as lever ideas for the future and move forward for now."): a glossary record, and abbreviations as names in alignment (milestone 7), are rows in the lever index, and a tentative plan of their own, *Document glossaries* (the owner: "not as a set of claims, but as metadata for reports, comparisons, and comprehending claims in context"), with where to test them (the local drawing sets' ABBREVIATIONS sheets, 38.300's clause) and what blocks it (reading a real legend into pairs). `sheet_records` is a default (the owner: "Go ahead and include `sheet_records` as a default.").

### 5. Stance

- **First, a look at the corpus and the real pairs without the model:** where are views reported (feature-lead summaries' company tables, minutes, reviews, cited standards), and what share of claims sit in them?
- **The attribution chain on evidence:** links of holder, attitude and strength, outermost first; the document's link from its record (the *subject, parties and provenance* row), reported links from tables ("Company | Proposals"), "according to", quotations and citations, mechanically where the parse gives them.
- **The pipeline's link named as such:** the reader's confidence, verification, agreement and derivation grouped as our stance, and the schema's `basis` and `uncertainty` documented as the source's; confidence used to filter only once calibrated.
- **The reader asked for reported holders and attitudes** where the parse can't give them (a prompt change, judged against null arms and stance probes; coordinated with the scheduling plan's epistemic status).
- **Alignment and the judge:** claims held by different parties don't pair; the same proposition with a changed holder or attitude is its own finding (design question 5).
- **Measured:** holders and attitudes against keys (new controlled families: a holder changed between revisions, a view reported against the same words in the authors' voice, a hedge added or removed); the RAN1 pair's companies' views told apart.

**Progress (2026-10-15; the owner: "Please proceed with milestone 5."):**
- **Where views are reported, without the model** (the real pairs' recorded runs, before `records` was a default):
  - The RAN1 feature-lead summaries are almost all reported views: 1,862 of the pair's 2,182 claims sit in companies' tables. "Company | Proposals" (16 tables, 246 rows: each company's proposals, quoted from its contribution) gives 1,151 claims, 110 of them naming a company (10%); "Company | Y/N | Comments" (12 tables and 278 rows, 29 and 387 by summary #3: each company's view on the moderator's proposals) gives 711, 221 naming one (31%, mostly as the entity: "CMCC | support for Proposal 3.2.4 | Y").
  - So the holder is in the table's first column for every claim of its row, and the reader mostly drops it ("UE-side model report | reported beam count | > 4 | BM-Case 1 and BM-Case 2", Spreadtrum's); where it keeps it, a view is bound as a value of the company (entity CMCC, attribute "support for Proposal 3.2.4", value "Y") rather than as CMCC's stance on the proposal.
  - TS 38.300 and QUIC report almost no one's views: a dozen claims in 13,309 and 4,558 name a company, mostly false matches ("New Cell").
  - Counted by company names from the meeting's TDoc list and the tables' own row labels; tasks' row numbers don't count rows as python-docx does, so a claim's own row's company isn't checked, only whether it names one.
- **A controlled family with holders** (`views`): a feature lead's summary, each company's proposals in a "Company | Proposals" table (two companies proposing different values for one parameter) and the moderator's own in the summary's voice; keys give a proposal's holder and attitude ("proposes"), the moderator's none (the document's implicit voice). Its pair credits Estrella's report period to Borealis, words and value kept, and revises Avelin's and the moderator's timeouts; the comparison scorer counts a fact whose holder alone changed (`holders_noticed`: not settled as unchanged). Recorded, $0.023:
  - Readers keep the holder for all 60 keyed facts (40 in conditions, "proposed by Avelin"; 20 as the entity), every fact found in every format: on a clean table, one proposal a row, the reader names whose it is.
  - The comparison finds both changes and confirms the 5 unchanged facts, but settles the credited proposal as unchanged in PDF, Word and Markdown, and leaves it uncertain in PowerPoint and Excel: never reported as another's.
  - So the holder is read but isn't part of the claim: alignment and the judge treat "proposed by Estrella" and "proposed by Borealis" as conditions worded differently.
- **Stance on claims** (`Claim.stance`, the reported links outermost first: holder, attitude, a hedge): a holder is part of a claim's identity; a claim without one keeps its id. Proven by replay (238 documents' and 98 pairs' scores as before).
- **A table's holder column** (`table_holders`, a default since 2026-10-16, the owner: "Yes, make `table_holders` a default."; `stance.py`): a column headed Company, Source, Proponent, Organization (and the like) holds every claim of its row. Alignment never pairs claims naming different holders, but for an attribution changed (the same words, holders aside, each holder without the value on the other side), a finding of its own without a model (design question 5).
  - The controlled corpus: holders in the stance for all 60 keyed facts; the credited proposal reported in every format (before: settled in three, uncertain in two); every other document and pair unchanged.
  - The RAN1 pair: all 1,930 table claims name their company; findings pairing two companies' claims 14 → 0 (5 had settled as one claim), none falsely attributed.
  - Built in steps: every equal value under other holders was first an attribution (RAN1's 9 were two companies' views sharing "Y" or "8"); and readings naming no holder (the PDF's text and tiles) settled the credited value before a value with an attribution stopped settling.
  - Left as lever ideas: the reader asked for holders where no column gives them; a view bound as the holder's stance on the proposition (RAN1's "CMCC | support for Proposal 3.2.4 | Y"); a holder named on a company's first row only.
- **The three ideas built and measured** (the owner, 2026-10-16: "Try and measure the recorded lever ideas."); two controlled documents for them, in every format: `views-grouped` (a company named on its first row only, as a merged cell prints) and `views-prose` (views in sentences: "Avelin [1] proposes", "According to Borealis [2]", "Delmar [4] supports", "Estrella [5] opposes"); the scorer counts a keyed attitude in the stance.
  - **A blank holder cell carried down** (`carried_holders`, a default since 2026-10-16, the owner: "Apply the two recommended defaults."): the 24 grouped rows Word, Markdown, slides and workbooks lost now hold their company (86 → 110 in the stance); the PDF already kept them (its reader joins a company's lines into one row); nothing else changed, $0. No real document has such a table (RAN1's summaries name the company on every row).
  - **A yes or no held, as a view** (`view_attitudes`, a default since 2026-10-16, the same answer): on RAN1 the company is no longer the entity of its views (139 of 148 before, none after; 103 of 121 name the proposal), each with an attitude; unmatched views 40 → 25. No finding paired two proposals' views before or after. The controlled corpus has no such claims, so nothing changes there.
  - **The reader asked for holders** (`read_holders`, off): the sentences' companies move from conditions into the stance (25 of 25), attitudes right for 19; facts right no different from the null arm, nor the comparisons. But it invents holders the null never does (61: the moderator's and the authors' own voice, "Company 1" for a blank cell, proposal labels), and on RAN1 first named rows' companies as printed, reference marks and all, mixing companies (fixed: a holder column's name wins, the reader adds only an attitude). RAN1's text reports no company's view, so the lever has nothing to find there. Tweak directions are in the lever index.
    - **Tweaked by its directions** (2026-10-16): holders and attitudes in the stance up again (+24, p 0.06; +41, p 0.001) with facts and comparisons no different from the null; placeholders and labels gone, but the document's own voice still named 38 times ("moderator", "design team"); on RAN1, views right 184 of 208 (the null 167), unmatched up 84 on the null. Still off; next: the document's voice dropped mechanically. $1.3.
  - **An alignment fix** it led to: a claim's holders count among its words when it pairs by wording (no default comparison changed).
  - $2.2 in all, mostly the prompt arms re-reading every PDF.
- **The pipeline's link named as such** (2026-10-16, the owner: "Continue."): [how it works](../how-it-works.md) says whose each field is: `stance`, `basis` and `uncertainty` the source's; the reader's confidence, quote verification, occurrences, derivation and the judge's and explainer's confidence ours, ordering and weighting a report, filtering nothing (none does today) until calibrated (Measurement, 7).
- **Views keyed, a poll's yes or no** (`views-poll`, in every format, with a revision turning two views round: one supporter now opposes, one opponent accepts and withdraws its counter-proposal): the moderator's two proposals, each followed by a "Company | Y/N | Comments" table as RAN1's. A view is keyed apart from the facts (holder, proposition, yes or no, attitude) and scored by the names a claim gives, wherever it gives them (lab `controlled/views.py`). Recorded under the defaults, $0.039, then the reconcile fix below re-applied ($0.003):
  - Views found 7 and 8 of 10 in the PDFs, 6 to 10 in Word, Markdown, slides and workbooks; none read the other way round or under another company. Every view a table reader found holds its company in the stance with the right attitude (`view_attitudes`); the PDF's text and image readers name it only in the entity.
  - The views lost: an "N | Prefers 171 ms." row gives the counter-proposal only, never the no (lever ideas: the yes-or-no column read without the model, `view_rows`; the reader told a party's yes or no is evidence). First counted, bare "Y" rows seemed lost too: they were read, then merged into a neighbouring company's view (the reconcile fix below).
  - The comparisons: of the two views turned round, one reported in PDF, Word and slides, both in workbooks, none in Markdown; one in every format when tables are read row by row. Kept views confirmed 5 to 8 of 8, no false change. The counter-proposal withdrawn: reported removed in PDF and Word (and in every format row by row), paired as a change with another value in slides and workbooks, and in Markdown read under another proposal's name.
- **Readings of one fact kept apart by holder** (a bug fix): `reconcile` (a default) merged readings with the same value, alike names and overlapping regions, whoever held them, so two companies' views in adjacent rows ("Proposal 2.2 | support | Y", Avelin's and Borealis's) became one claim. A claim's holders now have to match, as its ID's do. The polled summary: views found up 1 to 3 in 8 of its 10 documents, its comparisons' kept views confirmed up 1 to 3, unmatched claims down; every other document and pair unchanged. On RAN1 (b48's stores, reconciled again offline): 27 claims kept apart (11 in summary 0, 16 in summary 3).
- **A holder's yes or no read without the model** (`view_rows`, a default since 2026-10-16, the owner: "Please add `view_rows` as a default then continue milestone 5."): in a table with a holder column and a yes-or-no column, a row's yes or no is its holder's view of the item the text above the table last names, added where the reader gives none. The polled summary: views 10 of 10 in the PDF (7 before), 8 to 10 elsewhere; turned views reported 2 of 2 in four formats (1 of 2 in Markdown), no false change. RAN1: views 148 → 195, the 49 added right for 47 against the summaries' own tables (the reader's own: 119 of 146); views right 119 → 166 of 229 Y/N rows; no finding pairs two companies. $0.006.
- **Hedges keyed** (`hedges`, a link's draft design notes in every format; 2026-10-16, the owner: "Please add `view_rows` as a default then continue milestone 5."): values stated with a hedge in sentences ("is expected to be", "Tentatively,", "Preliminary estimates put") and in a table's Status column ("Working assumption" against "Agreed"); its revision firms two up and hedges two others, every value kept, and revises the preliminary beam count. A fact's hedge is keyed (`strength`); the context measure finds where a reading says it (its link's strength, uncertainty, conditions, attribute, value, entity, or nowhere); the comparison scorer counts a hedge changed with its value kept, reported (`hedges_reported`: in a "different" finding). Recorded under the defaults, $0.027:
  - Every fact found in every format. The hedges: 4 of 5 in conditions ("Tentatively", "preliminary estimate", "working assumption"), "is expected to be" nowhere, as is the revision's "will likely be"; none in a stance or uncertainty (nothing asks for them).
  - The comparisons report no hedge changed, in any format: the two sentence hedges are lost, so their pairs settle as unchanged without a model; the two table hedges are judged equivalent ("180" against "180, working assumption"). And the changed beam count, preliminary in both, is judged uncertain, not different, in every format: the one change missed.
  - Lever ideas ([lever index](../reviews/levers.md)): hedge words in conditions taken out as the link's strength, and a hedge changed reported without a model (as an attribution changed is); the reader asked to keep a sentence's hedge; and the changed beam count: the judge said "different", but a veto made every approximate reading's judgment uncertain, meant for values read off a picture (fixed below).
- **A hedge changed, reported without a model** (`align_hedges`, off; recommended as a default): a value's two readings whose conditions differ only by hedge or status words ("working assumption" against "agreed") are reported as the value firmed up or hedged, without a model. The hedged design notes: the table's two hedge changes reported in every format (none before), no false change; every other pair, and RAN1, unchanged. A hedge the reader drops isn't seen: the sentence hedges need the reader (a lever idea). $0.
- **An estimate's change no longer vetoed** (a bug fix): a judgment of an approximate reading was made uncertain whatever kind it was ("Approximate visual value requires review", from the first commit, meant for a value read off a picture); now only a chart's or a diagram's, or a reading of an image. The hedged design notes' preliminary beam count, 23 then 19: found in every format (none before); every other pair unchanged; $0.001.
- **The document's voice repeating a party's words** (`views-echo`, in every format): the moderator's proposals adopt companies' proposals word for word, the same sentence and value; its revision has the moderator adopt the other company's (the moderator's value changed, every company's kept). Keyed apart (echoes: a label and a value, bound by the label a claim gives). Recorded, $0.013: the moderator's switch reported in PDF, slides and workbooks; in Word and Markdown, its claims (no holder) were judged equivalent to the companies' of the same value (158 ms Avelin's, then 341 ms Borealis's), so the change was lost; the companies' proposals confirmed unchanged in every format, no false change.
- **The document's voice kept apart from a party's equal value** (a bug fix): a claim naming no holder paired with a party's claim of the same value; now only when its own revision has no claim of the party's of that value (else it's another voice repeating the value, not the party's claim read without its holder). The moderator's switch reported in every format (Word and Markdown too); the PDF views pairs lose 1 and 2 redundant "no change" pairs, no outcome moved; every other pair, and RAN1, unchanged; $0.001.
- **First, a look without the model:** can dimension strings (a dimension line, extension lines, ticks or arrows, a label along the line) be found in the vector drawing of the corpus's sheets and the slices' real drawing sets? Real sets are stored turned 90° (25 of the slices' 103 pages), so directions are taken as displayed.
- **If they can:** each dimension's direction, extent and what it bounds go into the tile's text layer ("24'-6" — vertical dimension, beside MEETING 101") and into the claim's context. Gridline references (A–F, 1–4) give places as a drawing's own coordinates.
- **If they can't:** the reader is asked for direction as drawn, judged against null arms and an abstention probe.
- **Measured:** room dimensions by direction as drawn (layer 2's knowability), the sufficiency audit's "not shown" for direction before and after.

### 7. Naming across documents

- **Room dimensions as pairs** where direction isn't established; by direction where it is.
- **A document's vocabulary** (schedule headers, defined terms) recorded and compared as frame.
- **Keys and scorer:** room dimensions keyed by room and direction as drawn; "named differently" and "agree as a pair" scored as comparison outcomes.
- **Other paired quantities** (fore-aft and side-to-side, rated and design points) checked for the same pattern in the corpus and the samples.

### 8. Further contexts (to be ordered as earlier milestones report)

- **Clause and section numbers as positions:** 3GPP revisions renumber clauses; a claim's clause is provenance, and a moved clause is "moved", not removed and added.
- **Procedure steps and table rows as positions:** TS 38.300's "after step 3" and "step 7/8 of transition" (640 conditions), the slices' "row 8": a scope that points at a position keeps its meaning when the steps are renumbered.
- **Tables:** units rows, merged header spans, footnote markers, "typical" columns.
- **Charts:** series, axis and operating point as context, not attribute words.
- **Time and place in scope:** phase, year, level, zone, option or alternate ("base bid", "alternate 2"); options are names with identity, not positions.
- **Repetition:** the same value stated in many places, its occurrences as context for confidence ([evidence webs](README.md)).

## Review (2026-10-14)

The plan read whole against the five kinds and the stages a context passes through. What changed, and why:

- **Measurement was the weakest part:** counts, keys and new scenarios, but nothing to say where a lost context was lost, and nothing measuring the model apart from the pipeline. Now seven layers, of which three are new: the **sufficiency audit** (was it in the query?), the owner's "depth" question asked of every miss; **probe batteries** for the reader and the judge (sensitivity, specificity, precedence, abstention), which also qualify another model; and **counterfactual pairs** that change only a context record. Grounding (context the query didn't hold) gives a measure on real documents without keys.
- **Measurement comes first** (new milestone 2), mostly without the model, so every later milestone has a baseline and the order of the rest can follow what the audit finds.
- **The milestones followed mechanisms; now each kind has a home** and the stages are explicit (Context through the pipeline). Subject had none: its sources (headings, row labels, title blocks, situating's abouts) are now records in milestone 3, the register's identity work staying with the revision comparison plan.
- **Context records have reach and precedence,** and changed records are findings of their own: a revision that changes only a general note was invisible to the plan as written (design question 6).
- **Who applies context** (code or model) was implicit; now decided per kind from the probes (design question 7).
- **Claim identity** was unstated: `claim_id` hashes conditions, positions until milestone 1, and no holder (design question 8).
- **Unknown isn't different:** stated, none and unknown are told apart, so a scope one reader missed can't become a change.
- **Our own link** is measured (calibration) before it filters anything.
- **Kept:** the concepts, the naming conventions, milestone 1 and the answered design questions; milestones 3 to 8 are the old 2 to 7, extended as above.

## Design questions

Answered by the owner on 2026-10-14; 6–9 came from the review.

1. **Renumbering in reports:** shown as a finding of its own ("renumbered: Condition 2 → 3"), or only in the claim's detail? I'd show it among editorial changes.
   - **The owner:** "editorial changes, like a new page number if we added some text or section numbering if we inserted a section."
   - **So:** a changed position, page or clause number is reported among editorial changes, as a move is, never as a changed value.
2. **Unordered pairs:** may room dimensions whose direction isn't established be compared as a pair and reported "agree as a pair", rather than left uncompared?
   - **The owner:** "yes, agree as a pair if we don't have a clear idea on framing."
   - **So:** compared by direction where the frame establishes it (a north arrow, a schedule's columns, both drawn the same way up); as an unordered pair otherwise.
3. **The scorer's room dimensions:** keyed by direction as drawn, accepting any name, instead of the generator's width and depth?
   - **The owner:** "I waffle on this one: we can only score based on what's there, but we should also test under various conditions, and we should look into how data from context might augment framing of reads."
   - **Proposed:** each scenario's key holds what its page makes knowable. A sheet with a north arrow or a schedule headed W × D is keyed by those names; a sheet without them by direction as drawn, accepting any name. The scenarios with and without (Measurement) test both, and the reads with context added (milestones 4 and 6) are scored on the same keys, so a gain from framing shows.
   - **The owner:** "Q3: your proposal looks reasonable as a starting point."
4. **Frame to the judge:** shown as its own field, with its own ruling (my preference), or folded into conditions?
   - **The owner:** "this is clearly a lever, but you can start with your preference."
   - **So:** a lever, off until measured; its first setting shows the frame as its own field with its own ruling.
5. **Stance changes in reports:** a finding kind of its own ("now B's proposal, was A's"; "now required, was targeted"), beside "changed" and "conditions changed"? I'd add it.
   - **The owner:** "I agree this is the sort of change readers would be interested in seeing called out."
   - **So:** a finding kind of its own, in milestone 5 (stance; milestone 7 before the order was revisited).
6. **Changed context records as findings:** a note, heading or lead-in that changes between revisions reported once, as its own finding, with the claims it reaches ("general note 3: dimensions now to centreline; 42 dimensions on A-101")? I'd add it, grouped with the value changes it may explain.
   - **The owner:** "add it."
   - **So:** in milestone 4, grouped with the value changes it may explain.
7. **Who applies context:** code where a rule is mechanical (units, a datum, renumbering, unordered pairs) and the probes show the model unreliable; the model where judgement is needed. Decided per kind from the probes, each as a lever. Agreed?
   - **The owner:** "code is preferable for for mechanical or hierarchical contexts, we may need the rule of "model checks heuristics" here when things are unclear by our heuristics, and we certainly need some extra context from the model where it's buried in images and prose."
   - **So:** code for mechanical and hierarchical context; the model checking heuristics where they're unclear; the model supplying context from images and prose ([Context through the pipeline](#context-through-the-pipeline)).
8. **Claim identity:** subject, attribute, value, unit, scope, frame and holder; never provenance. It changes claim ids (a store schema change, stores read again from cached answers), so I'd make it one refactor step in milestone 3, before anything fills scope, frame or holder apart.
   - **The owner:** "all of these things are heuristic proxies for claim identity; otoh, philosophically 'identity' itself is a difficult topic. Consider this closer to a weighted analysis. Some parts of provenance do make good claim identities, for example, e.g. in a requirements database a requirement named "TFV-45" is a pretty good identity for comparing versions of a model, less so for comparing across models. Let's consider identity more carefully, but prepare an initial heuristic proxy as a starting point."
   - **So:** identity as a weighted estimate over proxies, weights by what's compared, provenance's identifiers among them; an initial proxy in milestone 3, a research note and learned weights after ([Claim identity](#claim-identity)).
9. **Raters for context on real documents:** the context rubric rated by the panel of models first, and people only on samples where the panel disagrees? Or people from the start?
   - **The owner:** "panels of models first; it turns out that I can only motivate myself to look at the final outcomes that are actually needed for work, and even more so my larger team, so it will mostly be generic feedback based on user experiences from me."
   - **So:** panels of models rate; people's input is feedback from use, recorded and turned into probes, scenarios or rubric clauses (Measurement, layer 6).
