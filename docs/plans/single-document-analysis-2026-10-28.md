# Single-document analysis: claims situated among their subject's claims, inconsistencies and gaps

- **Status:** Active (2026-10-29): milestone 1, `analyze`, built 2026-10-29 (0.7.0); milestone 3, the second pass, 2026-10-31 (0.18.0; on by default in analyses since 0.22.0, with gaps looked for and kinds read together); milestone 4's first form (contradictions in a view) and milestone 5 by code, 2026-10-31; milestone 6 built 2026-11-07 (`judge_notes`, off); milestone 7 built 2026-11-07 (subjects across documents and the gaps another source fills; `match_subjects` off, `look_gaps` on by default). [Design questions](#design-questions) 1 and 3 answered 2026-10-28, 6 on 2026-10-29, 2, 4 and 5 on 2026-10-31. Milestone 2 moved to [indexes and glossaries](indexes-and-glossaries-2026-10-29.md) (2026-10-29).
- **The owner, 2026-10-29, setting the focus:** "We have a lot of open plans. I'd like to focus on two things that will be immediately useful to me: single document outputs, and building indexes and glossaries, e.g. of claims, diagrams, subjects. Even for a single document that would be useful, and it seems deeply related to the problem of comparing things regardless." And: "Well, I say "single document" but I really mean "single source" that might be a folder of docs." The indexes are [their own plan](indexes-and-glossaries-2026-10-29.md).
- **The owner, 2026-10-28, from trials:**
  - "we probably need to prioritize development of a second pass (or an entire refinement, situating, contextualizing strategy) where claims are analyzed in context, not just the provenance of where the claim is located but also situating it with other claims about the subject and distinguishing it with more nuance. A lot of comparisons don't make sense because they're compared without enough context. Context can help mitigate drift from heuristics (I hope!)."
  - "prioritize single-document analysis for a while, extracting and situating claims, perhaps analysis for gaps alongside inconsistencies in what is provided. Gaps in claims seems like a difficult target because we don't know where we should be looking for what we don't know without sufficient context."
- **The owner, answering design question 1 (2026-10-28):** "I think we shouldn't 'change' claims as in any form of mutability. We could annotate them, have a log or graph of commentary - associations, conflicts, corroborations, re-situation or re-contextualization, etc.. Everything should be traceable, monotonic, and (assuming the answer cache) reproducible."
- **The owner, answering design question 3 (2026-10-28):** "Not gaps that a page points to, just gaps in general. I mentally frame things in terms of constraint models. We have referents, e.g. names of things, subjects, that we don't know much about to start with. It's complicated a bit by claims potentially referring to the same thing at different points in time, different contexts of use, etc.. Trying to figure out when two items name the same target is already difficult. But assuming we are confident that two or three or ten claims are about the same subject, there are still gaps in what we know about it that a different proposal might specify in its claims about the corresponding elements. That's the clearest sort of gap, e.g. Project A tells you a bunch about Bob including his favorite food, while Project B tells you about Bob but did not mention his favorite food. Ideally, when we gather enough context, models themselves can also be smart enough to describe likely gaps in a collection of claims. Anyhow, this is a pretty deep subject, knowing or identifying what we don't know requires reading between the lines and also identifying what can reasonably be inferred from multiple claims in context."
- **Earlier, the same direction:**
  - 2026-10-01, on clustering: "I wonder if we can do a better job at clustering related claims for effective lookup and analysis as part of performing a diff, analyzing a document, or preprocessing a single document for effective ingestion." The tentative row *Claim clustering for lookup and analysis*, moved in here whole (2026-10-28):
    - **Its idea:** group claims about one subject (one quantity across conditions, corroborating or conflicting statements), using the [retrieval plan](retrieval-recall-2026-09-23.md)'s lexical, embedding and reranker scores.
    - **It was waiting on:** extraction quality first (the owner's focus), and that plan's benchmark and hybrid retrieval.
  - 2026-10-20, on reports: "it would be convenient to have an easily searchable database of claims even without the comparisons" (the plans index's suggested order, item 1)
- **Takes over:** from [single-source outputs](single-source-outputs-2026-09-23.md), `check` (its milestone 1) and the fact sheet (its milestone 3); that plan keeps the RAG export and cited summaries.
- **Builds on:**
  - [claim context](claim-context-2026-10-14.md)'s records (subject, scope, frame, provenance, stance), whose entity register is built here (milestone 2)
  - situating's figure and section "abouts" ([0039](../decisions/0039-runs-paced-by-throughput-and-situated-after-extraction.md))
  - alignment's items ([0038](../decisions/0038-revisions-aligned-then-differences-explained.md))
  - the portable report and its search ([0033](../decisions/0033-self-contained-reports-and-their-search.md))

## Why

Every claim is read by one task: a text group, a table row, a tile. A task sees its own span and the records reaching it (headings, lead-ins, notes, a title block). Nothing reads a claim beside the document's other claims about the same thing.

- **Comparisons lack what the document says elsewhere.**
  - A pump's head may be 42 m in one place and 61 m in another: one is the design point, the other shutoff head.
  - The document says so in a table's column header or a later paragraph. Neither claim carries it, and the judge sees only the two claims, their quotes, records and crops.
  - Claim context's records reach down the document's structure (sheet, section, table, list). They don't reach sideways to another section about the same subject.
- **Heuristics' errors look odd in context.**
  - A tile cut through a line, a row label taken from the next row, a holder carried to the wrong company: each makes a claim that disagrees with the document's other statements about its subject.
  - Nothing compares a claim with those statements, so the error reaches the comparison as a "different" finding.
- **One source has its own uses:**
  - a searchable record of what a document claims
  - its contradictions
  - what it leaves out
- **What exists for one document:**
  - **Situating** (PDFs only): figures linked to the prose citing them, and value-free "abouts" for figures and sections. It never changes or relates claims.
  - **Context records** reaching a claim, and its holders and hedges.
  - **Items**, grouped by tag or entity words: built for alignment (`align.Side`), never for one document on its own.
  - **Topics, search and other names** (`topic_names`, `search_names`, `embed`): in the report of a comparison only.

## Concepts

- **The owner's frame: constraint models.** Subjects are referents we know little about at first, and claims constrain them. In that frame (the mapping is mine):
  - an inconsistency is constraints that can't all hold
  - a gap is what one source or sibling constrains and another leaves open
  - an inference is a constraint drawn from others
- **Subject:** what a set of claims is about, however the document names it: an item (`P-101B`, MEETING 101), a procedure, a system.
  - Found mechanically first: tags, names as printed, row labels, headings, records, and alignment's items within one document.
  - Then by similar names (`search_names`, embeddings).
  - Then the model, only for what's left: "the feed pump" is `P-101`; "Pump" names two pumps in two systems.
- **One subject, or two?** The owner: "claims potentially referring to the same thing at different points in time, different contexts of use".
  - A name may hold one subject in several states: as designed and as built, phase 1 and phase 2, before and after a change.
  - Different names may hold one subject.
  - So a match of subjects is commentary like any other, with its evidence and how sure it is. Claims are compared, and gaps found, within one state of a subject, read from their scope and frame (claim context's records).
- **Siblings:** subjects of one kind (the pumps, the rooms, the conditions of one procedure).
  - Siblings' attributes show what one of them lacks.
- **Dossier:** what one request is shown about one subject.
  - its claims, each with its quote, records, section path and holder
  - the "abouts" of the figures and sections the claims come from
  - its siblings' names, and the attributes they have
- **The second pass:** the model reads a dossier and returns:
  - **context a claim lacks that the dossier supplies** (scope, frame, holder), each with the quote that supplies it
  - **relations among the claims:** restates, corroborates, refines, differs by condition, contradicts, derived from
  - **suspicions:** a likely misread, a claim about another subject, a claim that doesn't fit
  - **what can be inferred** from the claims together, citing them
  - **what's likely missing:** what the document points to but doesn't give, and what its siblings or the dossier suggest
- **Commentary, never edits** ([design question 1](#design-questions), answered): claims are never changed. What's learnt about them is a log, a graph of commentary beside them.
  - **Its entries (the owner's list):** associations, conflicts, corroborations, re-situation, re-contextualization. Matches of subjects, inferences and gaps are entries too.
  - **Traceable:** each entry names what made it and what it rests on:
    - the pass and its request's key in the answers cache
    - the claims it's about
    - the quotes it cites
  - **Monotonic:** entries are only added.
    - A later entry may dispute or supersede an earlier one by saying so, as an entry of its own.
    - Nothing is removed or rewritten.
    - What a reader shows (the latest word, or every word) is a view of the log, not a change to it.
  - **Reproducible:** the same claims and the same answers cache give the same log.
  - **Held as ours** (claim context's stance): the pipeline's statements, never the document's.
  - **Checked mechanically** as they're written:
    - the quotes cited are found in the document
    - the claims cited exist
    - a scope added names words the document prints
- **Inconsistency:** two claims about one subject, of one attribute, with compatible scope and frame, whose values differ after units.
  - The relation must be confirmed in the second pass, with the dossier, not judged from the pair alone.
  - "Differs by condition" and "restates with rounding" aren't inconsistencies.

## Gaps: what we don't know about a subject

Gaps in general ([design question 3](#design-questions), answered): what's known of a subject, and what's left open. As the owner says, it needs context to know where to look, "reading between the lines", and what "can reasonably be inferred from multiple claims in context". The kinds, the owner's clearest first:

| Kind | Examples | Found by | Needs |
|---|---|---|---|
| **Another source says it** (the owner's clearest kind) | Project A gives Bob's favorite food, Project B tells about Bob but not his favorite food; one proposal gives P-101's NPSH, the other doesn't | Subjects matched across documents, then their attributes compared: an attribute one source gives, for a subject both describe, in the same state | Subjects in each document (milestone 2), matched across them (milestone 7) |
| **Missing among siblings** | P-101 and P-102 give head and flow, P-103 flow only; a value for phases 1 and 2, not 3; a requirement without its verification; a room without its area | Siblings' attributes compared by code; the second pass asked about the sibling table | Subjects and siblings within one document |
| **Declared, not given** | "see Table 5" with no Table 5; "TBD", "to be confirmed"; empty cells in a table otherwise filled; "see attached" with nothing attached | Code: situating's unresolved references, placeholders by pattern, a table's empty cells | The document alone; cheap, and one kind among the rest |
| **Likely, from the dossier** | a pump with head and flow but no power or efficiency; a schedule with no dates for one phase | The second pass, asked what its dossier suggests is missing, given what siblings and other sources hold | A dossier with enough context |
| **Expected of a document of its kind** | a design basis without design life, codes or loads | A checklist: the user's criteria, or criteria a model proposes and a person reviews | [Criteria-first comparison](n-way-comparison-2026-09-23.md) |

- **What can be inferred isn't a gap.** A value other claims imply (power from head, flow and efficiency; a total from its parts) is an inference: an entry in the log, held as ours, citing the claims it's drawn from.
  - The gap is then that the document doesn't state it, which is weaker.
- **A gap is weak evidence.** The criteria-first plan's rule holds here: "No evidence found" stays weak. Each gap says:
  - where it was expected, and why
  - which state of the subject it's about

  It is never counted as a finding against the document.

## Measurement

- **Controlled documents (exact keys):**
  - **Subjects:** the fact sheet knows each fact's item, so grouping scores precision and recall.
  - **New knobs:**
    - a value restated differently in another section (an inconsistency)
    - a value restated under another condition (not an inconsistency)
    - a sibling missing an attribute
    - an attribute one revision or proposal gives and the other doesn't, for the same item
    - a value the document's other claims imply but don't state
    - one item under two names, and one name for an item in two states
    - a dangling reference
    - a placeholder
  - **Context added:** scored against the keys' scope, frame and holder.
  - **Suspicions:** scored against the scorer's own classes (misread, misbound, hallucinated). A flag's precision is how much drift the second pass catches.
- **Comparisons:** the second pass's context given to the judge is a lever ([milestone 6](#6-context-for-comparisons)), judged against null arms on the controlled revision and proposal pairs ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)). What it should lower:
  - uncertain findings
  - "not the same item" findings
  - wrong verdicts
- **Real documents (no keys):**
  - **Documents:** TS 38.300, the NREL 5 MW report, HabEx, the drawing sets.
  - **Rated** by model panels ([0018](../decisions/0018-several-raters-none-ground-truth.md)): dossiers, the log's entries, flags and gaps.
  - **Counted:**
    - claims per subject, and subjects of one claim
    - flags per 1,000 claims
    - the share of cited quotes found in the document
- **The owner's documents:** feedback from use. The report shows each flag and gap so it can be called useful or wrong ([*Reviewer feedback*](README.md#tentative)).
- **Cost:** about one request per subject of two or more claims. Estimated on TS 38.300 before it runs, and asked first above $5.

## Milestones

### 1. A one-source report: `analyze`

- **The command** ([design question 6](#design-questions), answered): `semantic-pdf-diff analyze SOURCE --store DIR` reads one source and writes its report. A source is what `compare` takes: a file, a folder of documents or a zip archive, or a source declared in the store (the owner: "single source" that might be a folder of docs).
- **What:** the Claims view, topics and search, built from the portable report's parts, with situating, other names and embeddings as a comparison's are; no findings, and no new kind of model request (the suggested order's first item). `report` writes it again.
- **With it:** the [indexes](indexes-and-glossaries-2026-10-29.md) (that plan's milestone 1) and their files; from the trials, the text a claim came from ([report snippets](report-snippets-and-bookmarks-2026-10-28.md)).
- **Built 2026-10-29 (0.7.0):**
  - `analyze` takes `compare`'s options but those of comparing; one source's topics needn't be found on two sides, and its other names are asked of one source (prompts of their own, so a comparison's queries are unchanged).
  - The page opens on its claims, with a filter by file; no findings, sides or "how it fared".
  - Tried live on two sample slices as one folder source (the IEA 22 MW report's pages 12-21 and a Solar Decathlon drawing set's pages 39-42): 729 claims, $0.16.

### 2. Subjects, mechanically

Moved 2026-10-29 to [indexes and glossaries](indexes-and-glossaries-2026-10-29.md): the subject index is its milestones 1 and 3, and it's claim context's entity register. The milestones below build on it.

### 3. Dossiers and the second pass

- **One request per subject**, its results written to the log and checked mechanically.
- **A lever, off until measured** against null arms on the controlled corpus.
- **Shown beside each claim:** "design point, at 60 Hz (p. 12); restated on p. 30; shutoff head on p. 40".
- **Suspected misreads** asked again from their crops: the follow-up *Comparing revisions, further* names ("a misread value read again from its crop").
- **Built 2026-10-31** (`second_pass`, off until measured; the owner, 2026-10-31: "Agree with all second-pass recommendations."; "Please proceed in recommended order"; `dossiers.py`):
  - **A stage of `analyze`,** after its claims, topics and other names: each source's subject of two claims or more (the index's subjects), its dossier its claims named C1, C2, ... (each with its quote, the passage it was read from, its section, its context records), its sections' and figures' abouts, and what its kind's siblings give that it doesn't; one request a subject, text only.
  - **The log** (report.json's `commentary`): context added, relations (restates, corroborates, refines, differs by condition, contradicts, derived from), suspicions (misread, another subject, out of place), inferences, likely missing; each checked as it's written (its claims the dossier's, a context's quote the dossier's words, a kind known), dropped and counted otherwise; a reason's claim names written as a reader finds them (“6D” (page 5)).
  - **Shown** on each claim's card ("Read with its subject's other claims", ours, out of search), likely gaps in "What it doesn't give", contradictions in an Inconsistencies view (milestone 4's first form), index.md, the workbook and `index/inconsistencies.csv`.
  - **Measured by eye** (2026-10-31, $0.15): 9 of scical's sheets, 205 subjects, 718 entries (294 restatements, 77 corroborations, 56 refinements, 16 by condition, 16 contradictions; 69 suspicions, 47 of them misreads; 36 context added, 25 inferences, 128 likely missing), 15 dropped by the checks, $0.085; TS 38.300's v19.3.0, clauses 1 to 8, 183 subjects, 345 entries, no contradictions, 47 claims suspected about another subject, $0.066. The contradictions mix the document's own ("WP" both water pump and waterproof in one list; METAL abbreviated MTL. and MET.), the reader's errors ("6D" sinkers where the passage says 16D, a compressor's width and length swapped, a sheet index's rows merged), and false ones (two "top of steel" elevations of different places). The misreads by eye mostly right; "another subject" mostly the index's grouping (three spans' rows under one subject); likely gaps often its siblings' hint again; inferences often summaries.
  - **Agreed** (the owner, 2026-10-31, on the proposed next steps: "The proposed next steps seem good to me. Please proceed."): the controlled knobs to score it (planted inconsistencies and gaps); suspected misreads asked again from their crops. Both built (below).
  - **Scored on planted reports** (2026-10-31, built as agreed; `consistency.py` in the lab, `scripts/controlled.py analyze`, `benchmarks/controlled/analysis.json`): a pump station's design report (two pages: prose, a pump schedule, datasheets, a valve schedule) written twice from a seed, planted and clean, seeds 1 and 2, analyzed with the second pass on and situated. Planted in each: three values restated otherwise in another section (P-302's motor, P-304's head, the wet well's working volume), two siblings missing a property (a blank cell in each schedule), two placeholders ("TBD"), two references to a figure and a table the report doesn't have. In both twins, never findings: two values restated under another condition (50 Hz on the standby generator, runout), three restated alike (one in miles for feet), and a total the claims imply. Each claim bound to its fact as the corpus's scorer binds it.
    - **First run** ($0.115): contradictions 4 of 6 found (the wet well's volume read as "differs by condition" both times), none false; no trap taken (0 of 4 conditions, 0 of 18 restatements said to contradict); 27 likely gaps not planted, nearly all the station's: its dossier carried the report's one section's about ("it covers pump schedules, valve specifications, ..."), read as a list of what the station lacked.
    - **Two changes, by these knobs:** the "missing" instruction narrowed to this subject's own properties, not other subjects' nor what an "about" says the source covers ($0.022: 5 of 6 found, the likely gaps still the station's); then a headless section's about (the whole document as one section, an outline-less PDF's) left out of dossiers ($0.021).
    - **Now** (planted, both seeds): contradictions 5 of 6, none false; no trap taken; sibling gaps 4 of 4 read together too; no likely gap not planted, in either twin (27 before). The total implied across three pumps 0 of 2: a subject's dossier can't reach claims of other subjects.
    - **Suspicions, unplanted but exact:** the valve schedule breaks across the pages, and its rows on page 2 were read with the first of them as their header (properties named "3,317", "54.6"); the second pass suspected all 22 such claims misread, and nothing else.
  - **Doubted claims read again** (2026-10-31, built as agreed; `dossiers.rereads`, part of `second_pass`): each claim the second pass suspects misread, and both claims of each contradiction (so the reader's errors are told from the document's own), from a PDF: its place rendered closer (its mark's box widened three times across and six down, 240 by 120 points at least, within the tile or page it was read from; else the region it was read from) and asked what the image gives for that item's property: as claimed, otherwise (what), or not shown. An entry of the log of its own; on the claim's card ("Read again from its place: it gives 16D") and beside each side of an inconsistency (the view, index.md, the workbook and CSV).
    - **Planted reports** (scored: a planted contradiction's claims are right "as claimed", the document saying both; a claim whose property was named by a value right "otherwise"): first 10 of 11 and 14 of 22; the model checked only that a value sat in its item's row, so "as claimed" now needs the property as the claim names it: 10 of 11 and 20 of 22; with regions sized in points, 10 of 11 and 21 of 22 ($0.005 a run, less).
    - **scical's 9 sheets** (by eye; $0.092 with dossiers asked again, then $0.005): 64 claims read again, 35 as claimed, 22 otherwise, 7 not shown. The sheet index's merged rows caught ("A-102 A-201": "two rows with their own names"), dimensions bound to a label the drawing doesn't give them, relations between parts the sheet doesn't state. One wrong at first ("6" O/C" read "6' O/C" from a third of the page at about a pixel a point), right once regions were sized in points around the claim's mark.
    - **Ours, not the document's:** a re-read can err as the reading did; it's shown beside the claim, never instead of it.
  - **A kind's items read together** (built 2026-10-31, part of `second_pass`; the owner, 2026-10-31: "Your recommended path seems reasonable"; my recommendation's item 3; `dossiers.kind_dossiers`): one request a kind of two items or more (the index's kinds: the pumps P-301 to P-304), its items' claims (80 at most) and the passages they were read from (8 at most, each once): two items said alike (identical, duty and standby) whose values differ, a claim unlike its siblings' as a misreading would make it, and what the items give together (a total, a firm capacity). A relation within one item is dropped: the model first called an item's restatements "derived" (its subject's dossier relates those).
    - **The sum by code:** an inference citing claims of one number each in one unit shows their sum beside it where its words don't give it ("4,663 gpm (the claims it cites sum to 4,665 gpm)"): a model's arithmetic can slip, and once did on a clean twin.
    - **Planted reports** ($0.008): the firm capacity implied across three pumps found 2 of 2 in each twin (0 of 2 before); contradictions 5 of 6, none false, no trap taken, as before; one more suspicion, a planted contradiction's text value called a misread against its table.
    - **9 of scical's sheets** (by eye; $0.007): 19 kinds; sheet titles cut short suspected ("ELECTRICAL CALCULATIONS & SCHE"), and two sheet-index rows the reader merged ("P-102 P-103") said to contradict P-103's own title; nothing else.
  - **On by default** in analyses since 2026-10-31 (the owner: "Yes, turn `second_pass` on.").
  - **Not yet:** in comparisons (milestone 6).

### 4. Inconsistencies (`check`)

- **Candidates:** within a subject, claims of one attribute whose values differ, confirmed by the second pass's relations.
- **Reported** in a view of their own, each with both claims and the dossier's reason.
- **The knobs** of an inconsistency and of a restatement under another condition.
- **Replaces** single-source outputs' design, which compared a source with itself claim by claim.
- **Built 2026-10-31: candidates found by code, asked about in the dossier** (the owner, 2026-10-31: "Proceed with items 3, 4 and 5"; part of `second_pass`; `dossiers.differing`): pairs of a subject's claims of one property (the index's) giving two values in all, that differ in common units beyond the coarser one's printing (0.62 mi is 3,274 ft), their conditions alike or one stating none; a property of more values lists different things (a detail's dimensions), and a number without a known unit counts only as one number alone (not a tag, 101-004). A dossier holding any (10 at most) is asked to settle each (DIFFER): "contradicts", unless the source gives the values different states or operating points (50 Hz and 60 Hz, at runout and at the design point; words only saying what the property is, a working volume "between the pump-off and start levels", name no other state), or one refines the other. A dossier without asks as before, so only those are asked again.
  - **Found on the way, fixed first:** the index joined a property's other names from the model where they can't be one property ("Maximum transient pressure" and "Minimum transient pressure"), which made pairs of them; [indexes and glossaries](indexes-and-glossaries-2026-10-29.md), milestone 3.
  - **Planted reports** ($0.009): contradictions 6 of 6 (5 before: the wet well's working volume, the table's and the prose's, now said to contradict), none false; no trap taken (0 of 4 conditions, 0 of 6 and 0 of 12 restatements). The traps have the wet well's shape (one claim with a condition, one without), so only the model tells them apart.
  - **9 of scical's sheets** (by eye; $0.024 with what the index's fix asked again): 2 subjects asked; an article's two heights and widths said to contradict, each read again as read (two articles' rows under one subject), and a compressor's length and width, one read again otherwise; 14 contradictions in all (15 before, other subjects' answers moving).

- **Tensions: claims hard to hold together, designed 2026-11-06.** The owner, 2026-11-06: "We'll need to also look for qualitative inconsistencies, with levels of suspicion. E.g. claiming low-alloy steel combined with a claim of corrosion resistance without a clear mitigating factor. Ideas on how to begin approaching this? Simply looking for two numbers attached to a subject won't work, this is where a model with some domain knowledge is likely necessary." Claude's design, its questions answered the same day:
  - **Scope** (within a subject first, then a part with its surroundings) and **levels** (worth a look, needs a reason, can't both hold): "Scope and levels seems reasonable, and 'worth a look' is probably worth adding to a suspects table for the user if not resolved, albeit marked low priority."
  - **A reviewer's concerns:** "Having reviewers able to supply specific concerns to watch for is an excellent feature, but it should work even when not supplied based on limited domain knowledge held by the model."
  - **A request of its own:** "I agree we should start separate; combining with second pass can be an experiment of its own." (A row in the [levers' ideas](../reviews/levers.md#ideas-not-built-yet).)
  - **Asked** (`tensions.py`, a request a subject of two claims or more holding one that isn't a number alone; the second pass's dossier: claims with their passages, sections, context and the sections' abouts): claims hard to hold together on engineering grounds (a material and a property or service it doesn't usually have, a rating and where it's used, a class and its application), each with the claims, its level, why, and what would reconcile it, in words a document would use ("hot-dip galvanized", "cathodic protection"). Not two values of one property (the second pass's). A reviewer's concerns (`reviewer_concerns`), when given, are added as things to watch for.
  - **The reconciling words looked for by code** in the source's claims, the passages they were read from and its context records: found, the tension is reconciled, citing where; not found, it stays, "nothing that reconciles it found" (weak: not saying isn't absence). A model's check of what's found is a later step, where code finds too much.
  - **Kept as commentary,** entries of kind "tension" in the second pass's log, never changing a claim; on both claims' cards, and in a **Suspects** view: those not reconciled first, by level, "worth a look" marked low priority; then those reconciled, with what reconciles them.
  - **Measured on planted tensions:** the planted reports gain three (a low-alloy steel hatch frame said to resist the wet well's hydrogen sulfide; a NEMA 1 control panel outdoors; ductile iron pipe in high-sulfate soil), each printed with what reconciles it in the clean twin (galvanized and coated; in a weatherproof kiosk; polyethylene-encased); then by eye on real documents.
  - **A setting, `tensions`** (off, analyses only), and `reviewer_concerns` (a list, none by default).
  - **Built 2026-11-06, measured on the planted reports** ($0.12):
    - **Planted twins:** each of the three tensions found and standing in both (6 of 6): the NEMA 1 panel outdoors "can't both hold", the steel hatch and the pipe in corrosive soil "need a reason". Found besides, in both: the three duty pumps' capacity short of the peak wet weather flow (the generator's values drawn apart: a real inconsistency of the document, not planted).
    - **Clean twins:** none standing. Each tension raised there reconciled, citing the statement that reconciles it (the hatch by "All metal fabrications in the wet well are hot-dip galvanized...", 2 of 2; the pipe by the polyethylene encasement, 2 of 2; the panel raised once, reconciled by the kiosk).
    - **First built otherwise, fixed before measuring:**
      - The hatch was read as two subjects (the frame's material, the hatch's corrosion resistance): never asked together. A subject is now asked with its parts, the subjects whose names add a word or two to its own.
      - Reconciling words were looked for in the passages claims were read from: a passage holds its neighbours' sentences, so every claim of the "6 Electrical and Materials" paragraph was cited for each. Now in what claims say, and context records (a mitigation the text says that no claim holds isn't found: a [levers' idea](../reviews/levers.md#ideas-not-built-yet)).
      - "NEMA 3R" was looked for as "NEMA" (a word of two characters left out), and found in the NEMA 1 claim: a word with a number now counts, and the words must stand near one another and near something of the tension's claims.
      - A tension whose reason named nothing of its claims (a NEMA 1 enclosure's reason, cited to the wet well's coating) stood in a clean twin: such an entry is now dropped.
    - **Real documents, by eye** (2026-11-07, $0.33 with what `whole_lines` and the readers' versions asked again):
      - **IEA 22 MW's pages and a DC drawing set's** (29 subjects asked): 2 tensions, both worth it: "airfoil drag coefficient 0" can't hold (a misread: the text gives the cylinder's lift coefficient 0.0 and drag coefficient 0.35), and plywood as an exterior deck surface needs a reason.
      - **scical's 9 sheets** (188 subjects asked): at first 6 tensions, then, asked again with the prompt saying a tension is about one item, 14: two items sharing a generic name called "can't both hold" (a "beam" LVL in one detail and a W-beam in another; "horizontal member", "vertical member" plywood and HSS), and two values of one property (the floor sheathing's 1" and 1/2"), which the prompt excludes. Worth a look among them: ASTM A307 all-thread rod "driven into" asphalt; a 10 ft assembly on full-extension drawer slides; 10d and 6d nails for one sheathing.
      - **So, by code** (gemma-4 ignoring the prompt's two rules): a tension whose claims all give one property dropped (the second pass's contradictions); a "can't both hold" whose claims stand on different pages taken as "needs a reason", the level said kept, its why saying they may be two items. scical: 14 → 10, no "can't both hold" left; the planted reports and the IEA report unchanged.

### 5. Gaps within one document

- **By code first:** missing among siblings, and declared but not given.
- **Then the second pass:** what its dossier suggests is missing, and what can be inferred (entries of their own).
- **Reported** in a view, "What it doesn't give", each gap with where it was expected and why, labelled weak.
- **Built 2026-10-31, by code** (the owner: "Please proceed in recommended order"; `indexes.gaps`, no requests):
  - **Missing among siblings:** of a kind's items in one source (three or more), a property more than half of them give and one doesn't; where expected, where its other values are.
  - **Cited, not found:** situating's unresolved references (a figure, table or sheet cited and not in the document).
  - **Placeholders:** a value given as "TBD", "TBC", "to be confirmed" and the like ("N/A" isn't one: it says the value doesn't apply).
  - In the page (a view, "What it doesn't give"), index.md, the workbook's Gaps sheet and `index/gaps.csv`, each source's own in a comparison.
  - **By eye** (offline): 9 of scical's sheets, 19 siblings' gaps and 2 sheets cited and not in the set (it's a subset); TS 38.300's clauses 1 to 8, 10 siblings' gaps, each version's own: PUCCH formats 0 and 1 give no "UCI payload" where 2 to 4 do, 2 and 3 no "UE multiplexing capacity". Several of scical's are sheet-list rows the kinds group loosely ("connection (A)"): weak, as labelled.
  - **Scored on planted reports** (2026-10-31; milestone 3's): by code, sibling gaps 4 of 4 (one under "column 3", its schedule read without its header there), placeholders 4 of 4, references cited and not found 4 of 4, none in the clean twins; 12 not planted, each a property named by a value (the header lost). The second pass's likely gaps: 4 of 4 siblings', none not planted once headless abouts were left out.
  - **Gaps looked for before they're reported** (built 2026-10-31, part of `second_pass`; the owner, 2026-10-31: "Your recommended path seems reasonable"; my recommendation's item 2; `dossiers.looks`): each gap among siblings, and each the second pass says is likely, looked for in a PDF where it would be: of the pages naming its subject (its claims there, or its names in the words), the one naming its property too (in the words, then by the siblings' values of it); there, what names them widened (240 by 120 points at least), rendered closer and asked whether it gives a value of the property for the item: given (the reader missed it, or named it otherwise), not given (a blank cell, "-", "TBD"), or not shown there. An entry of the log of its own ("looked"), shown beside the gap in the view, index.md, the workbook, the CSV and the export. Progressive disclosure led by the pipeline: the gap says where to look, as a doubt says what to read again. Other formats skipped (counted).
    - **Planted reports** ($0.003): the four planted blank cells looked for, found by code and read together alike, each "not given"; the clean twins had no gap to look for. The 12 gaps of the valve table whose header was lost (properties named by values): 6 given, 6 not given.
    - **9 of scical's sheets** (by eye; $0.017 with dossiers asked again, their prompt changed since): 126 gaps looked for (19 siblings', 107 likely): 15 given, 26 not given, 85 not shown there. The given ones are mostly the sheet index's rows, a sheet's name read under another property ("drawing title" where its siblings give "sheet name"), and keynotes the reader skipped; the not given ones blank cells and dashes ("SIZE" "-" for a forklift). "Not shown there" is weaker: some places don't hold the item.
    - **Answers told apart** (2026-10-31; the owner: "Proceed with items 3, 4 and 5", my item 4, "fewer 'not shown there' answers"): what I'd proposed (look only where the page names the subject) wouldn't have helped. Of the 85, 78 were looked for on a page holding the subject's claims and naming it; 66 were the second pass's likely gaps, properties those items don't have (a sheet index's row asked for its "part number" or "detail reference"), hinted by a kind grouped loosely (2 of its 17 items giving them). Five answers contradicted themselves ("The sheet name for item A-402 is explicitly listed in the table", not shown). So the look's answers are four (LOOK): given, under its name or another name for the same property (a sheet index's title is a sheet's name); not given (a blank cell, "-", "TBD"); no place for it there (the item shown, nowhere it would give the property: no such column, field or note); not shown (the item isn't there). In each kind of gap, the reader's misses come first, then what's left blank, then those not looked for, and last those with no place or not shown (`indexes.LOOKED`).
      - **9 of scical's sheets** ($0.022, twice; 150 gaps looked for, 7 more siblings' since the index's fix): 55 given, 3 not given, 77 no place for it there, 15 not shown there. The five that contradicted themselves now given; two answers before, "a blank cell" for S-403's sheet name and XB-001 "not listed", were wrong (the sheet index gives both), now given. Some given are loose: about ten sheet-index rows' "reference" answered with their titles. The not given are a forklift's dimensions printed "-".
      - **Planted reports** ($0.003): the planted blank cells 8 of 8 not given, as before.
  - **A table's cell left blank, built 2026-10-31** (the owner, 2026-10-31: "Proceed with items 3, 4 and 5"; `indexes.blanks`, no requests): from its record's cells (kept since, for the export's tables too: [single-source outputs](single-source-outputs-2026-09-23.md)), of three rows or more, in a named column more than half of them fill, each row leaving it empty, named by its first cell; a row of one cell (a section's label) or without a name (a merged cell's continuation, likely) isn't counted. A gap of its own kind, "Left blank in a table", weak as the rest (a cell merged across reads as blank too).
    - **Planted reports:** the pump schedule's planted blank cell found as one in both twins (the valve schedule's, on the page its header was lost, isn't), with one more each from that headerless part (a property named by a value); the clean twins none. 9 of scical's sheets (3 tables, 71 rows) and TS 38.300's clauses 1 to 8 (2 tables): none.

### 6. Context for comparisons

- **The judge** (and alignment's near-ties) shown each claim's subject context from the second pass.
- **A lever**, measured on the controlled pairs and the real ones (RAN1, TS 38.300, QUIC).
- **Built 2026-11-07, `judge_notes`, off** (the owner, 2026-11-07: "Proceed with the recommended path."): a comparison reads each source's subjects together before judging (the second pass, over the sources' claims as a report holds them), and each claim judged is shown what that noted of it as a "noted" field, in the export's words (context its passage lacks, its relations to its subject's other claims, doubts), the prompt saying they're ours. Its log is the comparison report's commentary: its cards show the notes, its index the inconsistencies, as an analysis's do.
- **Measured on the controlled revision pairs** (the 26 PDF pairs, 1,500 findings; $0.59): today's arm (the standard recordings), `judge_notes`, and a null arm (the same requests, the "noted" field empty: a scratch patch in a frozen worktree).

  | Arm | Changes found | Unchanged confirmed | Kinds named right | False changes |
  |---|---|---|---|---|
  | Today | 39/39 | 1,005/1,023 | 55/64 | 0 |
  | Null | 38/39 | 1,005/1,023 | 55/64 | 0 |
  | `judge_notes` | 38/39 | 1,008/1,023 | 51/60 | 0 |

  - The notes reached 848 of the 1,500 findings (a claim of 1,423 of 2,968 noted: context added 802 times, restatements 391, differs by condition 83, contradictions 46).
  - **Where they moved a verdict:** the units-note pair's 5 restated values, today uncertain and explained "restated", judged equivalent (the values the same; so 4 fewer kinds scored); 3 more unchanged values confirmed; one change missed (coaster's), as the null arm missed another.
  - **So:** on clean revision pairs, where a value matches or changes plainly, the notes change little. The comparisons the owner found lacking context are proposals: measured next on one.
- **A proposals pair, by eye** (the development slices' reference turbines, NREL 5 MW's pages 25 to 36 and IEA 15 MW's 20 to 31; 1,000 pairs judged; $0.41): 309 entries in the log; 27 verdicts changed, most more decisive and right (pitch angles at different wind speeds, a generator's speed and a rotor's, uncertain → unrelated: 17), a few the other way (unrelated → uncertain, "matching conditions were not established": 5); the judge's reasons seldom cite the notes. Uncertain 100 → 88.
  - **The notes' own worth is on the report:** the second pass doubted the IEA turbine's "14 MW" generator power against its 15 MW (a misread), now on its card in a comparison too.
- **Not made a default** (the owner's call): as a judge's input it changes little; the second pass in comparisons is worth more for its notes on the cards and its inconsistencies view than for the verdicts.

### 7. Subjects across documents, and their gaps

- **Subjects matched across documents:** each document's subjects (milestone 2), matched by alignment's items and names first, the model for what's left.
  - Each match is an entry in the log, with its evidence.
  - A subject's states (as designed, as built; phase 1, phase 2) are kept apart.
- **The owner's clearest gap:** an attribute one source gives for a matched subject, in the same state, that the other doesn't.
- **Reported** in the comparison's report beside its findings, labelled weak, with the claim the other source gives.
- **Measured** by the knob of an attribute one revision or proposal gives and the other doesn't, on the controlled pairs.
- **Design, 2026-11-07** (Claude's sketch, for the owner's review; the owner, 2026-11-07: "Please proceed." to a design first). Questions A to D below.
  - **Answered 2026-11-07** (the owner: "All four recommendations look good as a start."): A to D as recommended. With it, for revisions: "I'd want some extra cues about what is claimed to have been revised or why. I don't believe we track that sort of provenance at the moment because it doesn't look enough like a number or engineering claim." A direction of its own: the plans index's tentative row *Revision cues*.
  - **What there is:**
    - A comparison's merged index matches the sources' subjects: where the findings pair their claims (the most pairs first), then keyed alike (a tag, the same words), then other names.
    - Each matched subject's properties are listed with each source's values. A property one source doesn't give is left blank. It isn't listed or looked for anywhere: only each source's own gaps are (milestone 5).
  - **What that gives on a proposals pair** (the turbine pair of milestone 6; by code, no requests):
    - **Matches:** 103 subjects; 16 matched, every one by the findings; 87 alone.
    - **The judge's verdicts aren't evidence of identity across proposals:** they're about values. Of the 1,000 verdicts, 877 are unrelated and 100 uncertain. Subjects were linked mostly by uncertain pairs: "Generator Torque" and the "torque curve" (17), NREL's "tower" (117 claims) and IEA's "first torsional mode" (3).
    - **So the matches go wrong:** that link took NREL's tower, leaving IEA's own "Tower" (8 claims) alone, though both are keyed "tower". NREL's one-claim "tip-speed ratio" took IEA's "blade" (77 claims).
    - **Matched subjects mostly differ:** the rotor gives 16 of its 18 properties in one source only. Much of that is what each slice covers (NREL's pages describe the control system, IEA's the blade structure), not gaps.
  - **Subjects matched (revisions):** as now. Alignment decided the items, and the findings follow it, settled pairs among them.
  - **Subjects matched (proposals), by code first:**
    - Keyed alike, then other names. The findings are no longer a match on their own: they're the model's evidence (question D). On the turbine pair, rotor, tower, generator power and generator torque.
    - **Then the model, for what's left** (`match_subjects`, a lever): a subject alone in one source, shown with up to 8 candidates in the other (by shared name words and property names, and by embedding where the run made vectors). Each side is shown with its name, kind and properties, a value each, and how many of their claims the findings paired.
    - **The model answers:** the same item; the corresponding element (each proposal's tower: the owner's "corresponding elements"); a state of it (as designed and as built; phase 1 and phase 2); or none. Each with why.
    - **Checked mechanically:** the names given, one counterpart each.
    - **Cost:** one request per subject left alone in the smaller source. Pennies on the turbine pair (47 requests).
    - **Kept:** every match is an entry in the log (kind "match": the two subjects, how they were matched and why), and the merged index is built from those entries. A match never changes a claim.
  - **States** (question B):
    - Two subjects the model calls states of one item stay two subjects, linked, with no gaps between them.
    - Within a matched subject, a property is one property whatever its conditions. Each value's conditions are shown beside the gap, not split into states, until trials show they need splitting.
  - **Gaps, "another source gives it"** (a gap kind, first in GAP_KINDS: the owner's clearest kind):
    - **Found:** for a matched subject, a property one source gives that the other doesn't under any of its names, where the other describes the subject (two claims of its own or more).
    - **Each gap gives:**
      - the source lacking it
      - the subject and the property
      - where it'd be expected: the subject's first place in that source
      - why: what the other source gives, and where ("1,250 gpm, b.pdf page 3"), linked to that claim's card
    - **Ordered:** properties the lacking source gives for the subject's siblings first (it gives that kind of property elsewhere), then the rest.
    - **Weak, as every gap:** never a finding, never counted against a document.
  - **Looked for where it'd be** (`look_gaps`, a lever; dossiers.looks, as siblings' gaps are in an analysis):
    - The page of the lacking source that names the subject best is rendered closer and asked: given, not given, no place for it, or not shown.
    - **Given** is the reader's miss. In revisions, it's also a false "possibly added or removed" claim, now said so on its card.
    - **Not shown** is most of what a slice doesn't cover.
    - **Cost:** one image request per gap, about $0.0002 each (milestone 5's 150 looks cost $0.022).
  - **Reported** where gaps are now: the Gaps view (each source's, this kind first), index.md, the workbook's Gaps sheet and gaps.csv. A blank cell of the merged index links to its gap.
  - **In both modes** (question C): in revisions, the gaps restate additions and removals by subject, and the looks catch the reader's misses behind false ones; that's where exact keys can measure it.
  - **Measured:**
    - **Controlled revision pairs, as they are:**
      - Of the keys' 28 added or removed facts, 5 belong to an item both revisions keep: planted gaps, scored for recall.
      - The other 23 are whole items, matched to nothing: no gaps expected.
      - A gap whose fact the keys say both revisions give is a false one, the reader's miss: the looks should say "given".
    - **A knob added** (a lab build): revisions dropping or adding one property of items that are kept: a schedule's column dropped (a gap for each row), a sentence giving one property dropped, a property added. 15 to 20 more planted gaps, with today's pairs as controls.
    - **Matching:** scored against the keys' items, by code and then with the model.
    - **The turbine pair, by eye:** the matches, and a sample of the gaps with their looks.
    - **No controlled proposal pairs exist:** a pair (two projects of one kind, one leaving properties out) is a lab build of its own, proposed if the turbine pair says the gaps are worth it.
    - **Estimated cost:** under $0.50 in all; asked first above $5.
  - **Questions:**
    - **A. Corresponding elements:** in proposals, match the corresponding elements (each proposal's tower, each its rotor), not only the same item? Claude's recommendation: yes, the model saying which it is.
    - **B. States:** kept apart only where the model, matching, says two subjects are states of one item; within a match, conditions shown beside each gap, not split? Claude's recommendation: yes, splitting by conditions later if trials need it.
    - **C. Revisions too?** Claude's recommendation: yes. The looks there catch false additions and removals, and exact keys measure them.
    - **D. Findings in proposals' matching:** no longer a match on their own, shown to the model as evidence? Claude's recommendation: yes. The turbine pair's tower and blade went wrong by them.
- **Built 2026-11-07** (the owner's answers above; 0.44.0):
  - **Matching:** proposals' subjects by name or other names, never by the findings alone (D); revisions as before.
  - **`match_subjects`** (off; `crossmatch.py`): a subject names leave alone in the source with fewer, shown up to 8 subjects of the other sharing a name word or a property, with the judge's verdicts on their claims as evidence. The model names the same item, the corresponding element (A) or a state of it (B, kept apart). One counterpart each. Entries of kind "match"; the index says "matched by model: the corresponding element".
  - **The gap kind "Another source gives it"** (by code, both modes: C): a matched subject's property one source gives and another, giving the subject two claims or more, doesn't. Those its source gives the subject's siblings come first.
  - **`look_gaps`** (off): each looked for where it'd be in the source lacking it (dossiers.looks). The look isn't shown the other source's value, so it can't take a look-alike for it. The answer is shown beside the gap, in the subjects' blank cell, and on the other source's claim's card ("Not given by a.pdf as read; looked for on ...").
- **Measured on the controlled revision pairs** (scored by the lab: comparisons.json's `gaps_found`, `gaps`, `gap_looks`; the refresh $0.075):
  - **Two knob pairs added** (`revisions.py`):
    - `wtp-tables-s1-clean-gaps`: the valve schedule's stroke time column dropped, 20 valves kept. 20 of 20 found in every format, none false.
    - `wtp-s1-gaps`: the design basis's raw water turbidity and filtration rate no longer given, the rapid mix basin's volume and alum's storage given. 1 of 4 found in every format. The misses are the reader's grouping, not the gaps': raw water and filtration read as subjects of their own (gone whole from the later), the alum's storage as "alum day tanks". One false: a property named two ways ("served population", "serving population").
  - **Today's pairs:** 5 planted (of 28 facts added or removed, 23 are whole items). Found in the PDFs 1 (members' 3 and views-poll's 1 missed); in the other formats up to 4. 30 more on the PDFs: 9 of facts both revisions give (the reader's miss, or a property named two ways), 20 of claims bound to no fact (sheets' and abbreviations' claims).
  - **Looked for** (`look_gaps`, the PDF pairs; $0.007):

    | Gaps (by the keys) | Given | Not given | No place for it | Not shown |
    |---|---|---|---|---|
    | Planted (22) | 1 | 0 | 21 | 0 |
    | Both revisions give it (10) | 9 | 0 | 0 | 1 |
    | Bound to no fact (22) | 7 | 4 | 10 | 1 |

    - So the look tells the reader's misses from the revisions' own gaps. The one planted gap said given is a renumbered condition: the look took condition 1's words for the fatal-error condition (a positional property, as alignment's renumbering knob).
- **Measured on the turbine pair** (NREL 5 MW pages 25 to 36, IEA 15 MW pages 20 to 31, proposals; both levers on; 77 requests, $0.009):
  - **Matching:** by name and other names, 7 subjects (the tower now the tower's). The model asked of 21, 4 matched, all plausible: IEA's DTU Basic Controller and NREL's baseline blade-pitch controller, IEA's "tower and monopile" and NREL's integrated tower, each one's aerodynamic power and power coefficient. 4 dropped (a candidate taken, or none of those shown).
  - **Gaps:** 56. Given 4: the NREL tower's steel density and moduli, read under "steel", and the rotor's rated power. No place 34: NREL's controller gains, pitch sensitivities and the tower's distributed properties, which IEA's pages don't tabulate. Not shown 18: the operating points IEA's pages give and NREL's don't.
  - **What remains:** a property named several ways in one source ("Power Coefficient", "Power Coef. (Cp)", "Power Coefficient (CP)") is several gaps; the slices' coverage, not the designs', makes most of them.
- **Defaults** (the owner's call): `look_gaps` on since 2026-11-07, as Claude recommended (the owner: "Go ahead and turn on `look_gaps`."; round 0's settings keep it off); `match_subjects` off, Claude's recommendation being on for proposals once the owner's trials say the matches are right.
- **Weaker matches** (the owner, 2026-11-07, after the build: "I suspect we might want to support weaker, plausible or tentative matches in some way, for our reports, analysis, etc.. Any ideas on that? Match candidates by meaning might help, but I think we probably first need a viable model for "possibly relevant or a match, not sure, investigate further and see if things fit when tied together" instead of all-or-nothing."): a direction of its own, the plans index's tentative row *Tentative matches*.
- **Not built:** candidates found by embeddings (the design's "where the run made vectors"); a property named several ways joined before gaps are counted.

## Design questions

1. **Annotations, not edits:** answered 2026-10-28 (quoted at the top): claims are never changed; commentary is a log, traceable, monotonic and reproducible ([Concepts](#concepts)).
2. **The unit of the second pass:** one subject's dossier per request, or a section's claims, or a document's?
   - **I'd use the subject's dossier.** It's small and cached, and a changed claim re-asks only its subject.
   - **Answered 2026-10-31 (the owner: "Agree with all second-pass recommendations."):** the subject's dossier.
   - **A section** keeps the document's order but splits subjects across requests.
   - **A large specification's claims** don't fit one request.
3. **Gaps' reach:** answered 2026-10-28 (quoted at the top): gaps in general, not only those a page points to. The clearest is an attribute another source gives for the same subject ([Gaps](#gaps-what-we-dont-know-about-a-subject); milestones 5 and 7). A checklist for a document's kind stays with criteria-first comparison.
4. **Where it runs:** a stage after situating, in comparisons too, or one-source runs only until it's measured?
   - **I'd make it a stage, as situating is,** and turn it on in comparisons once milestone 6 measures it.
   - **Answered 2026-10-31 (the owner: "Agree with all second-pass recommendations."):** a stage, in comparisons once measured.
5. **Images in the second pass:** text only (claims, quotes, records, abouts), with a suspected misread re-read from its crop as a follow-up? Or crops in the dossier from the start?
   - **I'd start with text.** A dossier of a busy subject would otherwise carry dozens of images.
   - **Answered 2026-10-31 (the owner: "Agree with all second-pass recommendations."):** text first.
6. **The command:** answered 2026-10-29 (chosen from the options I offered): a new command, `analyze`, for one source; `compare` stays for two or more. `check` names the report's inconsistencies view, not a command.
