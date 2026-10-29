# Single-document analysis: claims situated among their subject's claims, inconsistencies and gaps

- **Status:** Active (2026-10-29): milestone 1, `analyze`, first; the rest planned. [Design questions](#design-questions) 1 and 3 answered 2026-10-28, 6 on 2026-10-29; 2, 4 and 5 open. Milestone 2 moved to [indexes and glossaries](indexes-and-glossaries-2026-10-29.md) (2026-10-29).
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

### 2. Subjects, mechanically

Moved 2026-10-29 to [indexes and glossaries](indexes-and-glossaries-2026-10-29.md): the subject index is its milestones 1 and 3, and it's claim context's entity register. The milestones below build on it.

### 3. Dossiers and the second pass

- **One request per subject**, its results written to the log and checked mechanically.
- **A lever, off until measured** against null arms on the controlled corpus.
- **Shown beside each claim:** "design point, at 60 Hz (p. 12); restated on p. 30; shutoff head on p. 40".
- **Suspected misreads** asked again from their crops: the follow-up *Comparing revisions, further* names ("a misread value read again from its crop").

### 4. Inconsistencies (`check`)

- **Candidates:** within a subject, claims of one attribute whose values differ, confirmed by the second pass's relations.
- **Reported** in a view of their own, each with both claims and the dossier's reason.
- **The knobs** of an inconsistency and of a restatement under another condition.
- **Replaces** single-source outputs' design, which compared a source with itself claim by claim.

### 5. Gaps within one document

- **By code first:** missing among siblings, and declared but not given.
- **Then the second pass:** what its dossier suggests is missing, and what can be inferred (entries of their own).
- **Reported** in a view, "What it doesn't give", each gap with where it was expected and why, labelled weak.

### 6. Context for comparisons

- **The judge** (and alignment's near-ties) shown each claim's subject context from the second pass.
- **A lever**, measured on the controlled pairs and the real ones (RAN1, TS 38.300, QUIC).

### 7. Subjects across documents, and their gaps

- **Subjects matched across documents:** each document's subjects (milestone 2), matched by alignment's items and names first, the model for what's left.
  - Each match is an entry in the log, with its evidence.
  - A subject's states (as designed, as built; phase 1, phase 2) are kept apart.
- **The owner's clearest gap:** an attribute one source gives for a matched subject, in the same state, that the other doesn't.
- **Reported** in the comparison's report beside its findings, labelled weak, with the claim the other source gives.
- **Measured** by the knob of an attribute one revision or proposal gives and the other doesn't, on the controlled pairs.

## Design questions

1. **Annotations, not edits:** answered 2026-10-28 (quoted at the top): claims are never changed; commentary is a log, traceable, monotonic and reproducible ([Concepts](#concepts)).
2. **The unit of the second pass:** one subject's dossier per request, or a section's claims, or a document's?
   - **I'd use the subject's dossier.** It's small and cached, and a changed claim re-asks only its subject.
   - **A section** keeps the document's order but splits subjects across requests.
   - **A large specification's claims** don't fit one request.
3. **Gaps' reach:** answered 2026-10-28 (quoted at the top): gaps in general, not only those a page points to. The clearest is an attribute another source gives for the same subject ([Gaps](#gaps-what-we-dont-know-about-a-subject); milestones 5 and 7). A checklist for a document's kind stays with criteria-first comparison.
4. **Where it runs:** a stage after situating, in comparisons too, or one-source runs only until it's measured?
   - **I'd make it a stage, as situating is,** and turn it on in comparisons once milestone 6 measures it.
5. **Images in the second pass:** text only (claims, quotes, records, abouts), with a suspected misread re-read from its crop as a follow-up? Or crops in the dossier from the start?
   - **I'd start with text.** A dossier of a busy subject would otherwise carry dozens of images.
6. **The command:** answered 2026-10-29 (chosen from the options I offered): a new command, `analyze`, for one source; `compare` stays for two or more. `check` names the report's inconsistencies view, not a command.
