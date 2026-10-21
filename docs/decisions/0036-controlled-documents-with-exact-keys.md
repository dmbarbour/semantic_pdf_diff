# 0036. Controlled documents: generated from a fact sheet and a seed, scored exactly by their keys, their knobs the situations met

- **Status:** Accepted (2026-10-21)
- **Source:** the [controlled documents plan](../plans/controlled-documents-2026-10-01.md) (its design, progress and decisions of 2026-10-01); the [revision comparison plan](../plans/revision-comparison-2026-10-02.md)'s decision 5 (2026-10-02); [0018](0018-several-raters-none-ground-truth.md)

## Context

Judged quality rests on raters with biases of their own, and on people's time. The owner, 2026-10-01: "similar to the eye test as a controlled test, we could have controlled PDF tests, i.e. where you generate a few PDFs with known facts to extract for fictional projects. This might provide a more robust control without relying on yours or my ability to extract facts." And: "pseudo-random so we can still leverage caching and fast testing. We can include things like the stacked tables as another difficulty knob, and generally build a list of troublesome and messy scenarios we've already encountered, mitigating some weaknesses of this approach."

Built 2026-10-01 to 04: fictional projects (a water treatment plant, a roller coaster, a convention centre, a link protocol's specification) as prose, tables, charts, scans, schematics, drawing sheets and a procedure diagram, each under its knobs; revision pairs with known changes; the corpus also as Markdown, Word, slide decks and workbooks. The claim context and tile selection plans have since added documents and knobs of their own.

What was found:
- **Knobs show what clean documents don't.** gemma-4 found every fact of the clean corpus; the table reader misbound only under a knob (spot check sc01's stacked table, reproduced and scored exactly), rotation cost binding but not reading, and figures cost relations.
- **The scorer erred too.** Reading the claims it marked wrong found its flaws (conditions outweighing attributes, ranges bound to one bound, repeated values counted once), each fixed before figures were quoted.
- **One seed, one sample per query:** counts to compare between knobs, not rates to quote.

## Decision

- **Generated, byte for byte:** a document is made by code from a fact sheet and a seed, values drawn within plausible ranges so they can't be guessed. The same seed gives the same bytes, so the pipeline asks the same queries and recorded answers replay (`benchmarks/controlled/replay.zip`). A test generates every committed document again and compares bytes; replays skip under a PyMuPDF other than the fixture's.
- **Fictional projects in real documents' conventions,** in domains new to the model, with backups logged.
- **A key knows every fact's form and place, and every printed number's role** (a fact, a distractor such as a superseded value, a section or page number, a tick label). So claims are classed exactly:
  - right, loose, misbound, misread, wrong unit, inexact (a bar read against its axis), hallucinated, and facts missed; conditions kept
  - relations: right, implied, reversed, wrong, invented
  - revision pairs: changes, additions and removals found, unchanged facts confirmed, and the share of "different" findings that are changes
- **A value printed nowhere is a hallucination, whether it conflicts or not** (the owner: "You should probably also account for hallucinated but viable claims that do not conflict?").
- **Keys stay honest by construction,** each rule tested: every fact placed; a revision changes a value wherever it's printed, as a whole token; a revision prints no number its base doesn't, but facts, added items' names and page numbers.
- **Knobs are the situations met:** each a difficulty from a review, round, spot check or trial, drawn under one knob at a time with the same facts as the clean drawing, and every failure met later gets one. The owner, 2026-10-02: "I'm hoping these fictional controlled tests with known difficulty knobs will greatly mitigate need for spot checks, so I can focus on findings from actual trials later; those findings become new difficulty knobs." The catalogue and its backlog are in [samples and testing](../samples-and-testing.md#controlled-documents).
- **Representations as controls.** The owner, 2026-10-02: "When we do add the alternative readers, we'll implicitly get a new form of control tests: same facts across two or more representations, within constraints of being unable to effectively represent all media (I'm not inclined to even try to interpret ASCII art as figures, for example.)" Each reader's format gets the corpus, scored by the same key; what a format can't carry (a chart in Markdown) is marked absent, not missed.
- **Exact for these documents only** ([0018](0018-several-raters-none-ground-truth.md)): one strong rater among others, never the measure of real documents.

## Consequences

- **Standing test infrastructure:** replay tests run free; the refactor check replays the corpus ([0027](0027-behaviour-changes-apart-from-refactors.md)); levers are judged on it by paired documents ([0037](0037-levers-judged-paired-and-promoted-held-out.md)).
- **Generation must stay byte-identical,** or answers stop replaying: a drawing change that moved a chart's bytes was once caught by hand, and the test catches it now.
- **A lever can fit the generator.** The controlled stratum's part in accepting levers is a proposal the owner answered conditionally (2026-10-01: "We can try this rule, though it may be a bit rigid"); it waits in the plans index's *Resumed query rounds*.
- **Not covered yet:** the backlog in [samples and testing](../samples-and-testing.md#controlled-documents); measured accuracy in the user docs is the tentative *Measured accuracy in the docs*.
