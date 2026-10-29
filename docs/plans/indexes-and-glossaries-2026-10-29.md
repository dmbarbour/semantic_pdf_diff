# Indexes and glossaries: a source's subjects, figures, claims and terms, alone or merged across a comparison

- **Status:** Active (2026-10-29): milestone 1 built the same day (0.7.0), with [single-document analysis](single-document-analysis-2026-10-28.md)'s milestone 1 (`analyze`); the glossary (milestone 2) next. [Design questions](#design-questions) 1 to 3 answered the same day; 4 and 5 open.
- **The owner, 2026-10-29:**
  - "We have a lot of open plans. I'd like to focus on two things that will be immediately useful to me: single document outputs, and building indexes and glossaries, e.g. of claims, diagrams, subjects. Even for a single document that would be useful, and it seems deeply related to the problem of comparing things regardless."
  - "Well, I say "single document" but I really mean "single source" that might be a folder of docs."
- **The owner's answers, 2026-10-29** (chosen from options I offered):
  - **The command:** a new one, `analyze`, for one source; `compare` stays for two or more.
  - **Files besides report.html:** Markdown, CSV and JSON, and "An excel file is also a good representation for indices. We already output excel workbooks of claims, but not really designed as an indexing model."
  - **In a comparison:** one merged index, each subject or term listed once, with what each source says side by side.
- **Earlier, the owner on glossaries (2026-10-15):** "Seems we should consider developing a glossary for abbreviations, framings, etc.. not as a set of claims, but as metadata for reports, comparisons, and comprehending claims in context. This would be another plan of its own, IIUC." The tentative row *Document glossaries* is moved in whole ([the glossary](#the-glossary)).
- **Takes over:**
  - [single-document analysis](single-document-analysis-2026-10-28.md)'s milestone 2, subjects found mechanically: the subject index, which is [claim context](claim-context-2026-10-14.md)'s per-document entity register
  - the tentative row *Document glossaries*, and its two lever ideas (the [lever index](../reviews/levers.md): a glossary record; abbreviations as names in alignment)
- **Builds on:**
  - alignment's items (`align.Side`: a tag, else the entity's words) and its item correspondence ([0038](../decisions/0038-revisions-aligned-then-differences-explained.md))
  - situating's figures, the prose citing them and their "abouts" (PDFs; [0039](../decisions/0039-runs-paced-by-throughput-and-situated-after-extraction.md))
  - context records: tables' titles and headers, sheets' title blocks, notes and legend blocks (`records.py`)
  - other names (`search_names`), topics and search, the portable report ([0033](../decisions/0033-self-contained-reports-and-their-search.md))

## Why

- **A source's claims are only a flat list.** Search, topics and the Claims view reach them, and only in a comparison's report. Nothing gathers what a source says about one thing, lists its figures and tables, or says what its abbreviations mean.
- **Comparing needs the same gathering.**
  - Two sources' subjects matched, each subject's properties side by side.
  - A property one source gives for a subject and the other doesn't: [single-document analysis](single-document-analysis-2026-10-28.md)'s clearest gap.
  - An abbreviation and its expansion taken as one name ("TDH" and "total dynamic head").
- **A source may be a folder** of documents, as `compare`'s sources are: files, folders and zip archives. Every entry cites its file and where in it.
- **No workbook is written today.** The nearest is `show evidence_occurrences --format csv`, a flat table of claims.

## The indexes

| Index | An entry | Found by |
|---|---|---|
| **Subjects** | A thing claims are about (P-101B, MEETING 101, the rotor): its names as printed, its properties with values, units, conditions and where each is said; the figures and tables it appears in | Mechanically: tags in the entity, names as printed, row labels, headings; alignment's items (a claim named by position joins the tagged item whose values it repeats). Then other names and the glossary merge names, the model only for what's left (milestone 3) |
| **Properties** | A property ("rated power"), each subject's value for it | The subjects index turned over |
| **Claims** | Every claim, one row: subject, property, value, unit, conditions, holder, quote, file, where in it, kind (text, table, figure) | The store's evidence |
| **Figures and tables** | A figure, drawing sheet, picture or table: its label ("Figure 3-1", "sheet A-202", "Table 5"), caption or title, file and page, its "about", the prose citing it, the claims read from it | Situating's figures, references and abouts (PDFs, when situating runs); tables' records; sheets' title blocks |
| **Glossary** | An abbreviation, defined term, symbol or convention (TYP, UNO, AFF, a datum, declared units): its meaning, where it's defined, how far it reaches (a sheet, a section, the source) | [The glossary](#the-glossary) |
| **Topics** (built) | A few words splitting the claims evenly, to browse by | `topics.py`; for one source, a topic needn't be found on both sides |

### The glossary

From the tentative row, moved in:

- **What it holds:** a document's (or a sheet's, or a section's) abbreviations, defined terms, symbols, and the conventions that frame its values, each with where it's defined and how far it reaches. Metadata beside the claims, never claims of its own (the owner, 2026-10-15).
- **Where it comes from:**
  - **Blocks found by their headings:** ABBREVIATIONS, ACRONYMS, DEFINITIONS, TERMS AND DEFINITIONS, NOMENCLATURE, SYMBOLS and LEGEND sheets and clauses. `records.note_records` finds a drawing sheet's blocks already and keeps their text.
  - **Each block read into pairs:** mechanically where the layout gives them (two columns; "TERM - meaning"), else by the model, one request a block (pennies a document, recorded and cached as other queries are).
  - **Definitions in prose, by pattern:** "net positive suction head (NPSH)", "NPSH (net positive suction head)".
  - **A drawn legend's symbols:** from its crop, by vision, after the text blocks.
  - **Checked mechanically:** each term and its meaning are found in the block's text.
- **What uses it:**
  - **Reports:** a term's meaning beside the claims using it; search finds the claims of a term's expansion.
  - **Comparisons:** an abbreviation and its expansion as one name; two sources' conventions compared, a changed one reported once.
  - **Comprehension:** the reader and the judge given the terms a span uses (a lever, milestone 5).
- **Where to test:**
  - the drawing sets' ABBREVIATIONS sheets in `samples/`: Solar Decathlon 2013 dc, ken, calg and scical; sd15-stevens, sd15-calpoly; nps-crissy
  - 3GPP TS 38.300's abbreviations clause
  - controlled counterfactual pairs: a term abbreviated in one revision, spelled out in the other
- **What was in the way:** reading a real legend into pairs by geometry (dc's paired wrongly, ken's not at all, calg's is drawn). The model reading a block's text answers the first two; calg's needs vision.

### In a comparison: one merged index (answered)

- **Subjects matched across sources:**
  - revisions: alignment's item correspondence
  - proposals: the judged pairs (two subjects whose claims were judged counterparts), names and other names
  - each match says how it was made
- **Each subject listed once,** its properties in rows, a column per source. A subject or property one source gives and another doesn't is shown so: weak, never a finding.
- **The glossary merged by term:** one term with each source's meaning. A term defined differently, or a convention one source declares and the other doesn't, is marked.
- **Figures and tables** listed with their source; matched only where labels or sheet numbers agree (revisions).

## Outputs (answered)

- **report.html:** Subjects, Figures and Glossary views beside Claims, Topics and Search. A subject's entry leads to its claims' cards.
- **report.json:** an `index` part (subjects, properties, figures, glossary), for tools.
- **index.md:** the indexes as a readable document, A to Z, each entry with where it's said. Also usable as chunks for an LLM; [single-source outputs](single-source-outputs-2026-09-23.md)' RAG export shares its writing.
- **index/\*.csv:** one file per index.
- **index.xlsx:** designed as an index (the owner: "not really designed as an indexing model"):
  - a sheet per index, its header frozen and filters on
  - Subjects: a subject's row, its properties beneath it in Excel's outline, so a subject collapses; each value with where it's said
  - Claims: flat rows, for filtering and pivot tables
  - written as OOXML by our own code, the same bytes for the same data (as the lab's controlled workbooks are), with no new dependency
- **Written by** `analyze`, `compare` and `report`, beside report.html. They hold the documents' words, as the store does, so they're written owner-only.

## Measurement

- **Controlled documents:**
  - the fact sheet's items score subjects' grouping (precision and recall)
  - knobs to add: an abbreviations block; a term spelled out in one revision and abbreviated in the other
- **Real documents:**
  - the drawing sets' ABBREVIATIONS sheets, counted against their lines
  - TS 38.300's abbreviations clause (hundreds of terms), likewise
- **Counted:**
  - subjects per source, claims per subject, claims in no subject
  - figures with and without an about
  - glossary terms per block, and the share whose meaning is found in the block's text
- **The owner's documents:** feedback from use.

## Milestones

### 1. Indexes from what's read already

- **No new requests:** subjects (mechanical), properties, claims, figures and tables.
- **Shown** as views in report.html; a comparison's merged.
- **Written** as report.json's `index`, index.md, the CSV files and index.xlsx.
- **One source:** in `analyze`'s report, [single-document analysis](single-document-analysis-2026-10-28.md)'s milestone 1, built first.
- **Built 2026-10-29 (0.7.0):**
  - `indexes.py` and `indexfiles.py`; the page's Subjects and Figures and tables views, each value linked to its claim.
  - A merged subject's properties are one where they're named alike or the findings pair their claims.
  - **Two sample slices, analyzed live** (729 claims): 138 subjects, 250 properties, 29 figures and tables (drawing sheets, tables and figures with situating's abouts).
  - **The coaster revision pair** (a recorded comparison, 62 claims): 13 subjects, 10 matched by the findings. The car's "seating capacity" and "rider capacity" were two rows each blank on the other side until properties were joined by the findings. The 8 one-sided values left come from subjects matched apart (two "lift hill"s), which milestone 3's names would join.

### 2. The glossary

- Blocks found and read; definitions in prose; checked.
- Shown, exported, and given to search (an abbreviation finds its expansion's claims).
- Merged by term in a comparison.

### 3. Names merged

- Other names and the glossary join a subject's names; the model asked only for what's left.
- Measured against the controlled keys.

### 4. Matching across sources, further

- Proposals' subjects matched beyond the judged pairs (names, other names, the glossary).
- Conventions compared: a changed one reported once.

### 5. The glossary given to the reader and the judge

- The terms a span uses shown with it: a lever, off until measured against null arms ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)).

## Design questions

1. **The command:** answered 2026-10-29, `analyze`.
2. **The files written:** answered 2026-10-29: Markdown, CSV, JSON and an Excel workbook designed as an index.
3. **In a comparison:** answered 2026-10-29, one merged index.
4. **A subject's grain:** an item (P-101B) or a kind (pumps)?
   - **I'd index items,** with a kind's items listed under it where an entity names the kind ("pump P-101", "pump P-102" under "pump").
   - These are single-document analysis's siblings, whose gaps it finds.
5. **Which files by default:** index.md, index.xlsx and the CSV files on every run, or only when asked (`--index md,xlsx,csv`)?
   - **I'd write them on every run.** They're small, and `report` writes them again.
