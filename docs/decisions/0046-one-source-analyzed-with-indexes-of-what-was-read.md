# 0046. One source is analyzed on its own, and every report carries indexes of what was read

- **Status:** Accepted (2026-11-17, retiring the plans it was made in)
- **Source:** the owner, 2026-10-29: "I'd like to focus on two things that will be immediately useful to me: single document outputs, and building indexes and glossaries, e.g. of claims, diagrams, subjects. Even for a single document that would be useful, and it seems deeply related to the problem of comparing things regardless."; "Well, I say "single document" but I really mean "single source" that might be a folder of docs."; 2026-10-20: "it would be convenient to have an easily searchable database of claims even without the comparisons"; on the files: "An excel file is also a good representation for indices. We already output excel workbooks of claims, but not really designed as an indexing model."; 2026-10-30, on items or kinds: "I think we should have indices for both, where feasible."; on which files: "Keep every run."; 2026-11-01, on kinds by rules or a model: "Let's try your recommendations on the decisions. But test the model on Q7 and see how it works out."
- **Builds on:** [0033](0033-self-contained-reports-and-their-search.md) (the report), [0038](0038-revisions-aligned-then-differences-explained.md) (alignment's items), [0039](0039-runs-paced-by-throughput-and-situated-after-extraction.md) (situating's abouts); made in [single-document analysis](../research/single-document-analysis-measured-2026-11-17.md) (milestone 1, design question 6) and [indexes and glossaries](../research/indexes-and-glossaries-measured-2026-11-17.md)

## Context

- Reports were of comparisons only; a source's claims had no browsable index of what they're about.

## Decision

- **`analyze` for one source** (a file, a folder, a zip or a declared source): `compare`'s options but the comparing ones, the same store and answers cache; `compare` stays for two (chosen 2026-10-29 among options offered). The inconsistencies a source holds are a view of its report, not a command.
- **Indexes from what was read, no new requests:** subjects (alignment's items: a tag, else the entity's words), properties, claims, figures and tables, kinds and the glossary ([0049](0049-a-glossary-is-metadata-beside-the-claims.md)); rebuilt whenever a report is written.
- **Written beside every report, every run:** the page's views, `report.json`'s `index`, `index.md`, `index.xlsx` (our own writer: the same bytes for the same data) and `index/*.csv`.
- **Items and kinds both:** a kind groups items by what they are (a set's sheets one kind; a property named two ways one where three items or more give both alike, never by numbers alone). A name naming several items ("A-102 A-201") counts for none of them, marked; a list's claims ("Pumps P-101 and P-102") are given to each. Rules first; the model naming kinds (`confirm_kinds`) a lever, off.
- **A comparison has one merged index,** each subject once with each source's values side by side; across proposals subjects join by their evidence ([0041](0041-evidence-combined-numerically.md), [0045](0045-possible-matches-are-links-kept-apart.md)), never by findings alone.

## Consequences

- `cli.analyze_command`, `indexes.py`, `indexfiles.py`, `kindcheck.py`; the README's *Indexes*.
