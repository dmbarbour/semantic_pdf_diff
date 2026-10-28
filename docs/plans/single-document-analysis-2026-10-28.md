# Single-document analysis: claims situated among their subject's claims, inconsistencies and gaps

- **Status:** Planned (2026-10-28); [design questions](#design-questions) open.
- **The owner, 2026-10-28, from trials:**
  - "we probably need to prioritize development of a second pass (or an entire refinement, situating, contextualizing strategy) where claims are analyzed in context, not just the provenance of where the claim is located but also situating it with other claims about the subject and distinguishing it with more nuance. A lot of comparisons don't make sense because they're compared without enough context. Context can help mitigate drift from heuristics (I hope!)."
  - "prioritize single-document analysis for a while, extracting and situating claims, perhaps analysis for gaps alongside inconsistencies in what is provided. Gaps in claims seems like a difficult target because we don't know where we should be looking for what we don't know without sufficient context."
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

- **Subject:** what a set of claims is about, however the document names it: an item (`P-101B`, MEETING 101), a procedure, a system.
  - Found mechanically first: tags, names as printed, row labels, headings, records, and alignment's items within one document.
  - Then by similar names (`search_names`, embeddings).
  - Then the model, only for what's left: "the feed pump" is `P-101`; "Pump" names two pumps in two systems.
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
  - **what the document points to about the subject but doesn't give**
- **Annotations, never edits** ([design question 1](#design-questions)):
  - The second pass's results are the pipeline's own statements, held as ours (claim context's stance).
  - They sit beside claims and are checked mechanically: the quotes cited are found in the document, the claims cited exist, a scope added names words the document prints.
  - Situating's rule holds: claims are never changed.
- **Inconsistency:** two claims about one subject, of one attribute, with compatible scope and frame, whose values differ after units.
  - The relation must be confirmed in the second pass, with the dossier, not judged from the pair alone.
  - "Differs by condition" and "restates with rounding" aren't inconsistencies.

## Gaps: where to look for what isn't there

Gaps are the hard part, as the owner says: without context there's nowhere to look. So this plan looks only where a document points at itself. A checklist from outside the document is [criteria-first comparison](n-way-comparison-2026-09-23.md)'s work ([design question 3](#design-questions)).

| Kind | Examples | Found by | Where |
|---|---|---|---|
| **Declared, not given** | "see Table 5" with no Table 5; a contents entry with no section; "TBD", "to be confirmed", "later"; empty cells in a table otherwise filled; "see attached" with nothing attached | Code: situating's unresolved references (measured on every run already), placeholders by pattern, a table's empty cells | Here, first |
| **Missing among siblings** | P-101 and P-102 give head and flow, P-103 flow only; a value for phases 1 and 2, not 3; a requirement without its verification; a room without its area | Siblings' attributes compared by code; the second pass asked about the sibling table | Here |
| **Expected of a document of its kind** | a design basis without design life, codes or loads | A checklist: the user's criteria, or criteria a model proposes and a person reviews | [Criteria-first comparison](n-way-comparison-2026-09-23.md), one source against criteria |
| **Expected by another document** | a requirement no claim answers | Criteria drawn from the requirements | The same |

- **A gap is weak evidence.** The criteria-first plan's rule holds here: "No evidence found" stays weak. Each gap says where it was expected and why, and is never counted as a finding against the document.

## Measurement

- **Controlled documents (exact keys):**
  - **Subjects:** the fact sheet knows each fact's item, so grouping scores precision and recall.
  - **New knobs:**
    - a value restated differently in another section (an inconsistency)
    - a value restated under another condition (not an inconsistency)
    - a sibling missing an attribute
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
  - **Rated** by model panels ([0018](../decisions/0018-several-raters-none-ground-truth.md)): dossiers, relations, flags and gaps.
  - **Counted:**
    - claims per subject, and subjects of one claim
    - flags per 1,000 claims
    - the share of cited quotes found in the document
- **The owner's documents:** feedback from use. The report shows each flag and gap so it can be called useful or wrong ([*Reviewer feedback*](README.md#tentative)).
- **Cost:** about one request per subject of two or more claims. Estimated on TS 38.300 before it runs, and asked first above $5.

## Milestones

### 1. A one-source report

- **What:** `report` and a run of one source give the Claims view, topics and search, built from the portable report's parts, with no new model requests (the suggested order's first item).
- **With it, from the trials:** the text a claim came from ([report snippets](report-snippets-and-bookmarks-2026-10-28.md)).

### 2. Subjects, mechanically

- **The index:** a per-document subject index from tags, names as printed, row labels, headings and records, with alignment's items (`align.Side`) used within one document.
- **Measured** against the controlled keys.
- **Shown** as a Subjects view in the one-source report.
- **Then names merged** by other names and embeddings, and the model asked only for what's left.
- **Claim context's entity register:** this index is the register, built here; that plan's item points here.

### 3. Dossiers and the second pass

- **One request per subject**, its results stored as annotations and checked mechanically.
- **A lever, off until measured** against null arms on the controlled corpus.
- **Shown beside each claim:** "design point, at 60 Hz (p. 12); restated on p. 30; shutoff head on p. 40".
- **Suspected misreads** asked again from their crops: the follow-up *Comparing revisions, further* names ("a misread value read again from its crop").

### 4. Inconsistencies (`check`)

- **Candidates:** within a subject, claims of one attribute whose values differ, confirmed by the second pass's relations.
- **Reported** in a view of their own, each with both claims and the dossier's reason.
- **The knobs** of an inconsistency and of a restatement under another condition.
- **Replaces** single-source outputs' design, which compared a source with itself claim by claim.

### 5. Gaps a document declares

- **Declared, not given:** by code first.
- **Missing among siblings:** then.
- **Reported** in a view, "What it doesn't give", each gap with where it was expected and why, labelled weak.

### 6. Context for comparisons

- **The judge** (and alignment's near-ties) shown each claim's subject context from the second pass.
- **A lever**, measured on the controlled pairs and the real ones (RAN1, TS 38.300, QUIC).

## Design questions

1. **Annotations, not edits:** the second pass records context and relations beside claims, and never changes a claim. Reports and comparisons use them where a lever says so.
   - **I'd keep it so.** A reading stays checkable against its quote.
   - **The alternative:** a confirmed scope or frame replaces the claim's own for everything after it.
2. **The unit of the second pass:** one subject's dossier per request, or a section's claims, or a document's?
   - **I'd use the subject's dossier.** It's small and cached, and a changed claim re-asks only its subject.
   - **A section** keeps the document's order but splits subjects across requests.
   - **A large specification's claims** don't fit one request.
3. **Gaps' reach:** declared and sibling gaps here; gaps from a checklist (a document's kind, another document) left to criteria-first comparison, as one source against criteria. Agreed?
4. **Where it runs:** a stage after situating, in comparisons too, or one-source runs only until it's measured?
   - **I'd make it a stage, as situating is,** and turn it on in comparisons once milestone 6 measures it.
5. **Images in the second pass:** text only (claims, quotes, records, abouts), with a suspected misread re-read from its crop as a follow-up? Or crops in the dossier from the start?
   - **I'd start with text.** A dossier of a busy subject would otherwise carry dozens of images.
6. **The command:** one source given to `compare`, a new command (`analyze SOURCE`), or both? `check` then names the report's inconsistencies view, not a command.
   - **I'd add `analyze`,** since "compare" with one source reads oddly.
