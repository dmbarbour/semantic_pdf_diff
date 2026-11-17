# The design apart from its documents and their makers

- **Status:** Draft for the owner's review (2026-11-17).
- **The owner, 2026-11-17,** on the review of open items' R1 (claims about the documents and their parties kept apart from the design): "Yes, write the plan for R1."; and "We'll stick to comparing pairs of sources for now".
- **Takes over** the tentative row *Subject, parties and provenance* (raised by the owner, round 5's title-block metadata, 2026-09-27), its notes carried below.
- **Its other half is built:** who asserts a claim (the document's authors, or a party it reports: a jury, a company in a feature lead's table) is [claim context](claim-context-2026-10-14.md)'s stance, milestone 5 (holders from tables and from reading, views' yes or no; RAN1's findings pairing two companies' views 14 → 0). This plan is what a claim describes.
- **Builds on:**
  - a document's numbering identifies nothing between designs ([0042](../decisions/0042-counterparts-only-where-differentiated.md); `align.generic`, `align.placeholder`, `DOCUMENT_PARTS`)
  - a sheet's title block read and kept as a context record (`figures.title_block`, `records.py`, `sheet_records`)
  - repeated blocks read where first said (`repeated_text`)
  - claims never change; what's learnt is a view or a log beside them ([0047](../decisions/0047-commentary-logged-beside-claims-that-never-change.md))
  - gaps weak, never findings ([0048](../decisions/0048-gaps-are-weak-evidence-looked-for-where-theyd-be.md)); one merged index ([0046](../decisions/0046-one-source-analyzed-with-indexes-of-what-was-read.md))
  - `debug`'s count of subjects named only as a document's parts (0.71.0), which this plan's classes replace, so the two stay one count

## Why

Two designs' drawing sets differ in their sheets, dates, scales, revisions and makers by construction. Today those differences are reported as the design's.

- **Findings between proposals** (recorded reports, no requests; a crude word pattern on each claim's entity and attribute), "different" findings about the documents or their makers:

  | Pair (`scripts/slices.json`) | "Different" findings | About documents or makers |
  |---|---|---|
  | `mech-dc-calg` | 53 | 23 (43%) |
  | `mech-nu-uncc` | 38 | 27 (71%) |
  | `mech-scu-usc` | 55 | 42 (76%) |
  | `drawings` | 89 | 60 (67%) |
  | `turbines`, `turbines-nacelles` (reports) | 53 | 0 |

  Examples: "document revision 4 \| date", "drawing \| scale", "document \| drawn by", "Team \| name", "Project \| copyright", "AIR DISTRIBUTION PLAN \| sheet identifier".
- **The index, in both modes:** on the same four drawing pairs, 18% to 35% of the index's subjects are documents or makers ("Sheet M-101", "Revision 4", "Team"), and up to 55% of a pair's gaps ("Sheet M-101 doesn't give its sheet title, as 4 of its 6 sheets do"). On the turbine nacelles pair, 8% (some of them the pattern's false hits).
- **Matching:** the drawing panels' sampled links were mostly such things (0.64.1 to 0.67.3 discount them by name; the lever index's row on drawings' furniture).
- **Met in a real pair (2026-10-04),** from the tentative row: RAN1's feature-lead summaries tabulate companies' views; the companies' "not needed" and "support" were compared as one item changed (fixed by stance, above).

## Concepts

Each claim describes one of three things. The class is a view computed when a report is written, from the claim's words, where it sits and how often it repeats; claims never change. Code names the classes as constants.

- **Design claims:** what's designed, where, and what it does: its components, systems, site and performance.
  - "P-101 \| flow \| 500 gpm"; "Room 104 \| area \| 320 sq ft"; "Project \| site address \| ..." (the site is the design's).
  - *Contrast:* would it still hold if the same design were drawn by another firm, on other sheets, on another date? Then it's the design's.
- **Document claims:** the documents themselves: sheet numbers and titles, scales, revisions and their dates, issue status ("95% CD", "issued for construction"), a document's own numbering and its contents.
  - "Sheet M-101 \| sheet title \| HVAC PLAN"; "Revision 4 \| date \| 2013-06-01"; "drawing \| scale \| 1/4" = 1'-0"".
  - *Contrast:* does it describe the paper rather than what's drawn on it?
  - **By the attribute, whatever the entity:** "HEAT PUMP \| drawing scale" is a document claim; a project's name identifies the documents and is one.
- **Party claims:** the people and organizations around the design: owner, client, designers and engineers of record, drafters, checkers, builders, reviewers, jurors, certifiers, a team.
  - "document \| drawn by \| JS"; "Team \| name \| Santa Clara"; "Engineer of record \| license \| ...".
  - *Contrast:* is it about who made, owns or judged the design rather than the design or the paper?
- **A document's imprint** (a word new to the project, from publishing: a printed work's maker, place and date): the document claims and party claims of one document or drawing set gathered as one, read from its title blocks and front matter: its makers with their roles, its issue status, its date and revision. Shown as context ("as-built set against a 95% set", "another engineer of record").
  - *Contrast:* "provenance" (claim context's kind) is where one claim was read and how it was named; an imprint is who issued the whole document and when.

## Milestones

### 0. Measured before anything changes

- **The recorded count above** as the before figure (no requests).
- **A panel's labels:** the lab's review batches given a field asking what a claim describes (design, documents, parties, unsure), on claims sampled from the four drawing pairs and two report pairs; models of other families than the reader's, Dawid-Skene consensus ([0043](../decisions/0043-matching-measured-on-real-pairs-by-a-model-panel.md)). About $2 to $3.
- **The controlled corpus:** its sheets key their revision table's dates as facts (`sheets.py`: "Revision 1 \| date"), so document claims are scored there for free; it prints no parties, so a knob is needed (a title block naming a firm, drafter and checker, different in two designs).

### 1. What a claim describes, by code (no requests)

- **Words:** an attribute naming a document's part or property (sheet number or title, scale, revision, issue date, issue status, copyright, page) makes a document claim; an entity or attribute naming a party's role (drawn by, checked by, designer, engineer, architect, owner, client, contractor, team, firm) a party claim; a document's part named alone (`align.generic`, `placeholder`) a document claim.
- **Where:** a claim read inside a sheet's title block region (beside the number `figures.title_block` finds), or a report's front matter (its first pages, before the first numbered section).
- **Repetition:** the same claim on most sheets of a set (a title block's firm, project and date).
- **Logged, weighing nothing first:** each claim's class and why, counted against the panel's labels and the controlled keys before any report changes.

### 2. Reported apart

- **Between proposals:** findings whose two claims are document or party claims shown in their own section ("About the documents and their makers"), not among the design's differences, nor counted with them; one claim of each class isn't a finding.
- **Between revisions:** still compared (a revision's date and issue status situate two versions of one thing), in their own section; they're the evidence *Revision cues* and *Recognising versions of one document* (the plans index's tentative rows) want.
- **One source:** the index's document and party subjects listed apart from the design's subjects; the sibling gaps among them not counted (a sheet lacking a title is the drawing's, not the design's).
- **`debug`:** its count of subjects named as a document's parts becomes the classes' counts.

### 3. Matching

- **Between proposals,** a link between two document or party subjects weighs nothing ([0042](../decisions/0042-counterparts-only-where-differentiated.md): a document's numbering identifies nothing); a design subject is never linked to one.

### 4. A document's imprint

- **Gathered from the classes,** no requests: each document's (or drawing set's) makers with roles, issue status, date and revision; shown at the head of the report and of each source in the index, and between proposals as context, never as differences.

### 5. The reader asked, only if code misses much

- **A prompt lever** asking the reader what each claim describes, measured against a null arm ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)); every recording re-made, so last.

### 6. Held out

- **The rule** written and committed before the pairs are recorded: fresh drawing pairs from sets not yet recorded (Solar Decathlon 2015 teams' drawings, `scripts/samples.json`), and one report pair; the panel's labels on a fresh sample; passes if the classes' agreement with the consensus holds and no design claim's finding is lost.
- **Defaults:** each step built off, held out, then the owner's call.

## Measurement

- **Agreement with the panel** per class (precision and recall of document and party claims), on development's pairs, then held out.
- **The guard:** design findings and design subjects lost (a design claim classed otherwise), named first.
- **Reports by eye:** the four drawing pairs and a turbine pair, before and after.
- **Cost:** milestones 1 to 4 no requests; the panel about $2 to $3 a batch; the held-out recording under $1.

## Design questions

1. **Three classes, or a fourth for the process** (codes cited, schedules, submittal rules)?
   - I'd keep three: a code a design follows describes the design ("designed to ASHRAE 90.1"); a construction schedule is a party's.
2. **Between proposals, their own section, or left out?**
   - I'd give them their own section, collapsed, counted apart: a different engineer of record is worth seeing, not worth counting as a difference.
3. **Between revisions, compared as today but in their own section?**
   - I'd say yes: dates and revisions are how two versions are told apart.
4. **In an analysis, the sibling gaps of sheets and revisions not counted?**
   - I'd say yes, listed with the documents' index instead.
5. **The reader asked (milestone 5):** only if milestone 1's code misses much against the panel.
