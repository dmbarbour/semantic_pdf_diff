# Indexes and glossaries: a source's subjects, figures, claims and terms, alone or merged across a comparison

- **Status:** Active (2026-10-29): milestone 1 built the same day (0.7.0), with [single-document analysis](single-document-analysis-2026-10-28.md)'s milestone 1 (`analyze`); the glossary (milestone 2), names merged and kinds (milestone 3), and the glossary used by the comparison and given to the reader (milestone 5) built 2026-10-30. [Design questions](#design-questions) 1 to 3 answered 2026-10-29, 4 and 5 on 2026-10-30.
- **The owner, 2026-10-29:**
  - "We have a lot of open plans. I'd like to focus on two things that will be immediately useful to me: single document outputs, and building indexes and glossaries, e.g. of claims, diagrams, subjects. Even for a single document that would be useful, and it seems deeply related to the problem of comparing things regardless."
  - "Well, I say "single document" but I really mean "single source" that might be a folder of docs."
- **The owner's answers, 2026-10-29** (chosen from options I offered):
  - **The command:** a new one, `analyze`, for one source; `compare` stays for two or more.
  - **Files besides report.html:** Markdown, CSV and JSON, and "An excel file is also a good representation for indices. We already output excel workbooks of claims, but not really designed as an indexing model."
  - **In a comparison:** one merged index, each subject or term listed once, with what each source says side by side.
- **The owner, 2026-10-30:** "Please proceed with the glossary." And, of design questions 4 and 5, in their words below.
- **The owner, 2026-10-30,** after names merged the index's subjects: "Will these subject merges extend to comparisons and analysis later? Alright, please proceed."
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

### Reach and provenance

The owner, 2026-10-30: "Also think on how much provenance or context should be tracked in the glossary, e.g. a legend that is `[red square] = Foo` isn't much useful beyond that diagram unless unusually consistent."

- **What an entry keeps** (provenance): its source and file, where it's defined (page or lines), the block's heading (or prose), how it was read (as listed, by the model from words, from a picture, from prose), and its reach. The request that read it is in the store's query log and the answers cache, so it's traced and reproduced as claims are.
- **Its reach** (built 2026-10-30): how far a definition holds.
  - **The document** (a file): an abbreviations list or definitions clause ("for the purposes of the present document"), prose definitions, and a drawing set's abbreviations, terms and conventions, which by convention hold for the set.
  - **One sheet:** a symbol on a drawing sheet, drawn or lettered ("[circle with M] = MOTOR" on sheet E-001; "W = WASHER RECEPTACLE"). A legend explains its own drawing.
  - **Consistent:** a sheet's symbol meaning the same on two sheets or more is said so ("alike on 3 sheets"); then it's worth more than one sheet's.
- **What reach decides:**
  - **Search:** only terms reaching their documents, and consistent symbols, are other names; a mark described in brackets never is.
  - **Comparisons:** "defined differently" weighs the meanings reaching their documents; a letter meaning one thing on one sheet and another elsewhere isn't a conflict.
  - **Display:** a sheet's term says so ("sheet E-201 only"), in index.md, the CSV and workbook (a Reach column) and the page.
  - **Later** (milestone 5): the reader and the judge given only the terms whose reach covers the span they read.
- **Not tracked yet:** a section's reach (a definition holding for one section of a document), and a set's reach across files (a folder source whose general sheet G-001 defines terms for its other files): both need a source's files read as one set.

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
  - the abbreviated revision pair (built 2026-10-30, `wtp-s1-abbreviated`): the water treatment plant's basins, filters and measures abbreviated in the later revision as an abbreviations list ahead of its sections defines them ("an SWD of", "SBs", eleven terms), two abbreviated values revised; in every format
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
- **Built 2026-10-30** (`glossary.py`; the `glossary` lever, on by default for the owner to confirm):
  - **Blocks:** a PDF's outline sections so headed; on a page, headings side by side (a sheet's SYMBOLS and ABBREVIATIONS) as one block, the band around them read as rows of words by position, since a sheet's text layer often lists a table's columns apart (the dc set's did: terms and meanings in separate runs); a text file's heading and its lines, a heading holding others so headed left to them (TS 38.300's 3 to its 3.1 and 3.2).
  - **As they are:** a text file's tables under the heading, and lists of tabbed lines (TS 38.300's 264 abbreviations, with no request).
  - **The model:** the rest, a part of 3,000 characters a request (one cut short: halves); a term kept only where its term and its meaning are in the part.
  - **Prose:** "net positive suction head (NPSH)" and "NPSH (net positive suction head)", the letters the words' initials.
  - **End to end** ($0.033): scical's ABBREVIATIONS sheet analyzed alone, 177 terms read, 1 dropped, 175 in the index; two slices re-run, two definitions in prose (CFD, PSF).
  - **By eye on real blocks** ($0.008): the dc set's SYMBOLS / ABBREVIATIONS 81 of 82 and 53 of 53 kept, correctly paired; scical's ABBREVIATIONS 99 of 100 and 77 of 77; a manual's DEFINITIONS 2 of 2; calg's SYMBOL LEGEND 25 of 27; TS 38.300's 3.2 Definitions 44 of 44.
  - **Shown:** index.md's Glossary, glossary.csv, the workbook's Glossary sheet, the page's Glossary view; in a comparison each term once with each source's meanings, one defined differently marked; each term and its meanings searched as one name.
  - **A list running past its page** (2026-10-30; a PDF without an outline): a block whose band runs to the page's end, a footer at most below it, read on from the next page's top in the same band, past its header, to a heading (a term's, a note's, or a numbered section's of one line) or a gap; pages, not sheets. The calg manual's DEFINITIONS read over pages 114 to 117 (49 definitions, to "END OF SECTION"), the ken manual's over 156 and 157.
  - **A drawn legend** (2026-10-30; the vision setting on): a sheet's block headed Symbols or Legend holding five drawn paths or more is read from its words as any block, and its picture is asked for its symbols, one with letters as printed, one drawn described in square brackets ("[circle with M] = MOTOR"), its meaning found in the words. Live ($0.008): calg's SYMBOL LEGEND 49 terms (25 from its words, 24 symbols from its picture), scical's SYMBOLS LEGEND 207 (194 and 13), dc's 7. Asked for every term at once, scical's picture answered past the output budget and its drawn symbols were lost: so the words and the picture are asked apart. A reading kept by kind (a table's, then the words', then the picture's, then prose's), and every order independent of the order answers come in.

### 3. Names merged, and kinds

- Other names and the glossary join a subject's names; the model asked only for what's left.
- **Built 2026-10-30, other names** (no requests): a glossary term reaching its document and its meaning, and the model's other names (search_names), join a source's subjects so named, match subjects across sources the findings left apart ("matched by other names"), and join a subject's properties ("NPSH", "net positive suction head"). A sheet's symbol isn't a name. On the coaster pair nothing new joined: its other names were already within subjects, and its two "lift hill"s are the findings' (the earlier lift hill paired with the later "Helix"). Not yet: the model asked for what's left.
- **Kinds** ([design question 4](#design-questions), answered: "indices for both, where feasible"): each kind of subject (pumps, rooms) with its items under it, where the items' names say the kind.
  - **Built 2026-10-30:** tagged items by their tag's letters, named by the word their names most share ("pump (P)"); items named with a number by the name without it ("Room"); a kind of two items or more, a table of its items by property, the most given first, "—" where an item gives none its siblings do (index.md, the workbook's Kinds sheet, kinds.csv, the page's Kinds view). On the two live slices: "Beam ID 4 opening" (openings 1, 3, 5), "dimension" (1 to 3), "drawing (A)" (A1, A6).
  - **The index built whenever a report is written** (not kept in the store), so `report` brings an older comparison's index up to date.
- Measured against the controlled keys.

### 4. Matching across sources, further

- Proposals' subjects matched beyond the judged pairs (names, other names, the glossary).
- Revisions' alignment with the glossary's names: built with milestone 5 (`align_glossary`).
- Conventions compared: a changed one reported once.

### 5. The glossary given to the reader and the judge

- The terms a span uses shown with it: a lever, off until measured against null arms ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)).
- **Built 2026-10-30** (the owner: "Will these subject merges extend to comparisons and analysis later?"):
  - **The glossary read before claims are compared** (it was read after), so the comparison can use it; the same requests.
  - **Then before claims are read** (2026-10-30), so the reader can use it too; the same requests, its PDFs' sections cut as their extraction cuts them.
  - **The controlled pair** ([Measurement](#measurement)): today's comparison finds neither change in any format (0/2): the changed values under "HDT" and "SWD" are never paired with "detention time" and "side water depth", so they're listed unmatched, not changed.
  - **In alignment** (`align_glossary`, revisions; a default since 2026-10-30, the owner: "Yes, let's add align_glossary as a default"): a meaning written out folded into its term ("side water depth" weighed as "SWD"), and a long meaning's last words where no other meaning ends so ("detention time" as "HDT"). The pair's changes found 2/2 in every format, nothing else moved; the other 113 controlled comparisons as before (none has a glossary). On TS 38.300's two versions (offline, 324 terms): judge pairs 871 → 844 and settled 5,940 → 5,954, by eye mostly right (the NG-U and Xn-U stacks' layers no longer paired across stacks).
  - **Spelling terms out instead** (tried first): the pair's changes found too, but on TS 38.300 a tenth of the judge pairs moved, some wrongly ("PDCP layer integrity protection" settled with "PDCP layer ciphering": the spelled-out PDCP four shared words of six). An abbreviation is one word whichever way it's written.
  - **To the judge** (`judge_glossary`; off, measured no different): each claim judged shown the terms its words use, as its document defines them. 16 of the pair's 31 judged pairs shown terms, no relation moved: the model already reads these letters. Its use would be a project's own letters; no controlled pair has those yet.
  - **To the reader** (`reader_glossary`; off, measured against a null arm: no different; the owner, 2026-10-30: "let's test glossary to reader"): each extraction request shown the terms its words use, as its document defines them ("Defined in this document: SWD = side water depth"), a long meaning and a term the words spell out left out. The null: the same line, its terms without their meanings. On the controlled corpus, TS 38.300's clauses 1 to 8 and 9 of scical's sheets, the lever moved what the null moved: rewording the requests reads again what was read two ways (TS's unmatched 75 → 32, the null 38), and where only one revision defines terms, only its reader is reworded (the abbreviated pair's workbook, unchanged confirmed 30 → 25 of 31, the null the same). On drawings the glossary's own mistakes reach every request: a capitalized word as a term ("OF"), one discipline's letters on another's sheets ("TS"). Found and fixed on the way: a list printing meanings first read reversed; a term of words across a line break stopped the run. $0.9 the arms.
  - **Not yet:** proposals mode's retrieval and the explainer, and a discipline's reach (lever ideas); the model's other names (search_names) in alignment, which are asked after the comparison, from its claims.

## Design questions

1. **The command:** answered 2026-10-29, `analyze`.
2. **The files written:** answered 2026-10-29: Markdown, CSV, JSON and an Excel workbook designed as an index.
3. **In a comparison:** answered 2026-10-29, one merged index.
4. **A subject's grain:** an item (P-101B) or a kind (pumps)? Answered 2026-10-30: "I think we should have indices for both, where feasible."
   - So both: items, as built, and kinds, each with its items under it where an entity names the kind ("pump P-101", "pump P-102" under "pump"). Kinds are milestone 3's, with the names.
   - These are single-document analysis's siblings, whose gaps it finds.
5. **Which files by default:** index.md, index.xlsx and the CSV files on every run, or only when asked? Answered 2026-10-30: "Keep every run."
