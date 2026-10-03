# Controlled documents with known facts

- **Status:** Active (2026-10-02): milestones 1, 2 (table, prose and layout knobs), 3 (charts, scans, schematics, relations and drawing sheets) and 4 (revision pairs and comparison scoring) done.
- **Depends on:** the [eye and page tests](../research/eye-tests-2026-09-30.md) (drawing code, recorded queries, profiles); [one table model](one-table-model-2026-09-30.md) (table hazards; its table eye tests become part of this); [content-addressed queries](content-addressed-queries-2026-09-28.md) (the same documents ask the same queries, so answers replay); [query improvement](query-improvement-2026-09-26.md) (rounds).
- **Why:**
  - **The owner (2026-10-01):** "similar to the eye test as a controlled test, we could have controlled PDF tests, i.e. where you generate a few PDFs with known facts to extract for fictional projects. This might provide a more robust control without relying on yours or my ability to extract facts."
  - **And:** "pseudo-random so we can still leverage caching and fast testing. We can include things like the stacked tables as another difficulty knob, and generally build a list of troublesome and messy scenarios we've already encountered, mitigating some weaknesses of this approach."

## Goal

- **Documents generated from a fact sheet and a seed:** the same seed gives the same PDF, byte for byte. So the pipeline asks the same queries, recorded answers replay, and tests run offline and fast.
- **Every fact's form and place known,** so extraction is scored exactly (right, misbound, misread, missed), and comparison is scored on revision pairs with known changes.
- **The messy situations we've met reproduced as knobs** (catalogue below), so the control isn't a test of clean documents only. Every failure met later in a round or spot check gets a knob too.

## Design

**1. Fact sheets (the answer key).**
- **Fictional projects, each written in its kind of documents' own conventions.** The owner: "You could pick a new domain, e.g. roller coasters, water treatment, city traffic control, convention center design, etc.. but it's fine to use the current domains if that's easier... just find some inspirations and run with it, perhaps log a few more as backups."
  - **The first four** (new domains, so no real project's familiarity helps, plus one beside the development slices):
    - **A water treatment plant** ("Harrow Creek WTP"):
      - design criteria (flows, detention times, dosing)
      - equipment schedules (`P-101A`, blowers, filters)
      - a process flow diagram whose arrows matter
      - requirements and limits ("shall not exceed 0.3 NTU")
      - two disinfection options compared
    - **A steel roller coaster** ("Ridgeback"):
      - ride specifications (height, speed, length, g-forces)
      - train and car data
      - a track element table stacked with its supports
      - g-force and speed charts
      - an elevation sheet with dimensions
      - a revision that raises the lift hill
    - **A convention centre expansion** ("Lakeshore Hall C"):
      - drawing sheets (plans with room tags, door and window schedules, rotated sheets, small dimension text, grid references)
      - HVAC loads per hall under occupancy cases
      - electrical panel schedules
    - **A 3 MW wind turbine,** beside the development slices: properties, operating-point tables, controller gains, a blade's structural charts.
  - **Backups:** city traffic control (signal timing plans, intersection diagrams, volume counts), a district heating network, an observatory instrument, a micro-hydro plant, a ferry terminal, a data centre's cooling plant, a ski lift.
- **Facts:** entity, attribute, value, unit, conditions, and basis (required, proposed, measured, calculated).
  - Entities have invented names and tags ("Glenmore Pump Station", `P-101A`), with the aliases a reader may fairly use.
  - Relations: part of (a camera's detector), alternative to (the 2-ton unit against the baseline), supersedes (revision B's value).
  - **Relational facts, without a number** (needed for schematics): a subject, a relation and an object, such as "DM1 precedes DM2 on the light path", "the Lyot stop is in a pupil plane", "the focal plane mask is an HLC or a VC", "the filter wheel is movable".
    - **The owner (2026-10-01):** "We'll need to develop a fairly wide array of 'relations', e.g. component of, within, attached to, etc. and a lot of control docs that present relations in different ways, with varying levels of difficulty."
    - **The vocabulary:** each relation has the phrasings a reader may use and its inverse ("drives" against "driven by"), so a claim from either side scores. It grows as documents need it:
      - structure: part of, within, mounted on
      - flow: precedes (upstream of, feeds)
      - mechanism: drives, powered from
      - control: controls, measures, connected to (signals)
      - service: serves
      - alternatives and options
      - places: located at (a pupil, a focal plane)
      - states: movable, insertable
    - **Presentations, by difficulty:**
      - prose stated plainly, or inversely, passively, by possessive ("the fan's motor"), or narrated along a path
      - figures drawn as labelled boxes, or as symbols with leader labels; a path straight, or folded back with crossings; links labelled, or told apart only by line styles in a legend
      - each relation in the figure, the text, or both
- **Values drawn from the seed** within plausible ranges, so they can't be guessed. They're written in the forms documents use: `1,250`, `0.075`, `±0.05`, `4–6`, `≥ 3`, `2'-9 1/2"`, `-43.73E+6`.
- **Distractors in the key, marked as such:** another component's value of the same kind, superseded values, negations ("not rated for…"), ranges and inequalities.

**2. Renderers: each fact in one or more forms, at a known place** (PyMuPDF, as the eye and page tests draw):
- **Prose:** templated sentences in several phrasings, conditions in clauses, a section and numbered-item structure, captions and cross-references ("see Table 3").
- **Tables:**
  - layouts: items in rows or in columns, case tables, matrices
  - with the table plan's hazards as knobs
- **Charts:** bars, stacked bars with legends, lines with operating points; printed values or axis-only; panels labelled (a)–(f).
- **Drawings:** sheets at real sizes (rotated as stored), labelled components, arrows, dimensions in feet and inches, callouts, details with grid-referenced titles, title blocks and revision tables, line work.
- **Schematics and concept diagrams** (the owner, 2026-10-01: "things like the figures and concept drawings in items 5 and 9 of the spotcheck. These are full of useful claims and often have references to them"):
  - **What they show:**
    - labelled components joined by a path (light, flow or signal), in order
    - annotations on components ("in pupil")
    - movable or insertable parts (double arrows)
    - alternatives on one component ("HLC or VC")
    - branches for modes ("Guide mode")
    - stages of a process drawn left to right (lenslets, mask, dispersed images, data cube)
    - insets and colour scales
  - **Cited from the text** ("(Figure 5.5-12)"), which walks part of the path in words.
  - **Each fact placed in the figure only, the text only, or both,** so recall by form shows whether figures are used as a source, and both forms test corroboration (sc01 items 2, 5 and 9).
- **Page furniture:** running headers and footers, page numbers, watermarks, list-of-figures entries.
- **The text layer:**
  - normal; rasterised, like a scan
  - text drawn as outlines, later, since it needs glyph outlines
- **Each placement is recorded:** page, box, form, the scenarios in force.

**3. Determinism and caching:**
- Generation depends only on the seed and the code. PyMuPDF's version is noted, as the eye tests do, and replays are skipped under another.
- Queries are named by what reaches the model, so a corpus read twice is paid for once, and tests replay from a fixture.

**4. The corpus:**
- **A small fixed set:** about six projects, each with two revisions, 4–12 pages. Together they cover every scenario at least once.
- **Sweeps generated on demand:** one knob at a time (font size, a stacked table, density) against a clean document.

**5. Scoring:**
- **Extracted claims are matched to the key:** entity by alias, attribute by the key's synonyms, value and unit normalised (numbers parsed, unit forms folded).
  - **Outcomes:**
    - right
    - misbound (a key value under another fact's entity or attribute)
    - misread (the right fact, the wrong value)
    - missed
    - conditions kept or lost
    - basis right or wrong
  - Reported by form, scenario and knob.
- **Claims the key doesn't hold.** A key can't list every claim a reader may fairly make, but a generated document is known in full. The owner: "You should probably also account for hallucinated but viable claims that do not conflict?"
  - **Every printed number and label is logged with its role:** fact, distractor, a section or page number, a date, or a drawing's grid reference.
  - **A claim whose value isn't printed anywhere** (nor follows by unit conversion from a printed one) is **hallucinated.** It's an error, whether it conflicts or merely looks viable. So is a claim about an entity the document never names.
  - **A claim whose value is printed but filed under another fact's entity or attribute** is **misbound.**
  - **A claim whose value is printed in a non-fact role** (a page number as a value) is **misread.**
  - **The rest are printed values the key doesn't list as facts** (a fair claim the key lacks, or a combination). They're counted and sampled for review, and the key grows when they're fair.
- **Relational facts are scored by names,** since there's no number to find the fact by:
  - The claim's entity and attribute are matched against the fact's subject and relation, and its value's words against the object, by the same rare-word fit as numbers' bindings.
  - **A path given as a sequence** ("DM1 -> DM2 -> Focal plane mask -> Lyot stop", as item 9's readers wrote) stands for its adjacent pairs.
  - **Outcomes:**
    - right
    - reversed (the pair's order swapped, as the eye tests' arrows)
    - misbound (a component on the wrong path, or the wrong component's annotation)
    - invented (components or links the figure doesn't have)
  - Every label drawn is logged, as every number is.
- **Comparison, on revision pairs:** the report's changed, added and removed facts against the key's changes.
- **The key is exact for these documents only.** Their scores are one strong rater among others, never the measure of real-document quality (no ground truth).

**6. Uses:**
- **Regression tests,** replayed free.
- **An exactly scored stratum in every round,** beside the judged real documents. It costs no judging, which is 88% of spend.
- **Model profiles and selection,** beside the eye tests.
- **The table plan's medium test:** the same tables rendered here as PDFs, and written as CSV and XLSX.

## Scenario catalogue (knobs)

Each row is a situation met in this project's documents, with where it was recorded. Short names:
- **Reviews:** sc01 = [spot check sc01](../reviews/spotcheck-sc01-2026-09-30.md); s01 = [evaluation s01](../reviews/evaluation-s01-2026-09-25.md); rNN = round reviews; overall = [overall review](../reviews/overall-review-2026-09-28.md); levers = [lever index](../reviews/levers.md).
- **Research:** eye = [eye tests](../research/eye-tests-2026-09-30.md); RH = [round-01 heuristics](../research/round-01-context-heuristics-2026-09-26.md).
- **Code:** extract and situate = their modules' comments.

**Tables**

| Knob | Situation | Seen in |
|---|---|---|
| Stacked tables | Two tables in one grid, split by a styled header row; the second header lost, rows bound to the first | sc01 item 1 (HabEx p4) |
| Multi-level headers | "Cameras > UV Channel" cut to "UV" | sc01 |
| Wrapped cells | A cell's second line arrives as an unlabelled row; "Spectrometer resolution" read as counts | sc01 |
| Several values in a cell | `1×1 CCD201` (format and model) | the table plan |
| Components of components | A camera's detector; how to name a part of a part | sc01 |
| Dense tables | 20 rows: values from the same row or column, though legible | eye |
| Case tables | Operating points (wind speed 14, 15, 16…) as inputs, not properties | s01; NREL p10 |
| Subject above the table | Rows that need the lead-in ("Module A", "NREL 5-MW baseline") | r01; levers |
| Continued across pages | A repeated header, and a false continuation (the next day's schedule of the same form) | store m4 review; extract |
| False tables | Chart gridlines, sheet frames, boxed paragraphs, equation debris; a borderless real table missed | RH; levers |
| One-row tables | The only row sent as its own header | levers |
| Values taken for numbered items | Rows starting "3.83 -43.73E+6" read as section numbers | query improvement; extract |
| Schedules on rotated sheets | Wiring schedules; their lead-in the title block | r03; overall |
| Pseudo-tables in text | Table-like text in a text chunk; misbinding rose under loose quote matching | r09 |
| Quotes spanning cells | Cells joined with "\|", a header read with its value | r09 |
| Wide rows | Split by column; a split that separated header from values | extract; robustness baseline |
| Units in headers, totals rows, ± columns, min/nominal/max, footnote markers | Planned hazards | the table plan |

**Charts**

| Knob | Situation | Seen in |
|---|---|---|
| Readings off the axis | Values at 23° and 25° on an axis ending at 20° | r07, r08 |
| Trends for readings | Curves that peak and fall described as "increasing" | r08 |
| Stacked series and legends | Series swapped; legends split from charts by tiles | r07; r03 |
| Axis labels and multipliers as values | "0" and "1e10" read as stiffness | r09 |
| Stacked bars across alternatives | Monthly use for a 2-ton and a 2.5-ton unit; readings selective | sc01 item 2 |
| Panel labels | "(a) Mass density" taken for a numbered item | levers; extract |
| Printed values on grouped bars | Another bar's value; a category code as a value | eye |
| Unfamiliar conventions, signs | A minus sign dropped on re-asking | s01; r01 |

**Drawings and sheets**

| Knob | Situation | Seen in |
|---|---|---|
| Rotated sheets | Context taken from beside a table; before and after swapped | overall; meta-audit |
| Small dimension text | 2'-9 1/2" read as 2'-3" from an overview | s01; gemma-4 images research |
| Labels cut at tile edges | "2x4 CEDAR HANDRAILS" as "2x4 CED" | s01; RH |
| Close details | Values bound to the wrong module, grid line or detail; titles misattached | r05 |
| Title blocks and revision tables | Read as administration only, or switched extraction off; small print in large crops | r05; extract |
| Watermarks, blank tiles | "PRODUCED BY AN AUTODESK STUDENT PRODUCT"; "the image is blank" | levers; extract |
| Grid-referenced details | "B4" titles; detail markers that aren't figures | RH; extract |
| Single-letter identifiers | Module A merged with Module B | r08 |
| Distinct facts sharing a value | Door D1 and window W2, both 1.02 | duplicate-claims research |
| Arrows | Direction reversed (gemma-4: 15 of 118) | eye |
| Dense sheets | 100–300 claims per unit; an illegible page thumbnail | overall; r06, r07 |
| Fake bold | Text drawn twice, offset | situate |

**Schematics and concept diagrams**

| Knob | Situation | Seen in |
|---|---|---|
| Facts only in a figure | "Item 5 again ignores the figure as a source": a text unit has none of its page's figure readings | sc01 items 2 and 5 |
| Text that walks a figure's path, citing it | HabEx Figure 5.5-12: the UV channel's path in the figure and in the paragraph beside it | sc01 item 5 |
| Paths as sequences | Readers wrote "DM1 -> DM2 -> Focal plane mask -> Lyot stop" and its fragments as separate claims | sc01 item 9 |
| Alternatives on one component | "The focal plane mask can either be an HLC or a VVC" (caption and figure) | sc01 item 9 |
| Annotations as locations or conditions | "DM1 (in pupil)", "Lyot stop (in pupil)" | sc01 item 9 |
| Stages of a process | Lenslets, pinhole mask, dispersed images, data cube | sc01 item 5 (Figure 5.5-11) |
| Movable parts and modes | Double arrows on filters, grism and field stops; a "Guide mode" branch | sc01 item 5 (Figure 5.5-12) |

**Prose**

| Knob | Situation | Seen in |
|---|---|---|
| Alternatives as conditions | "2 ton unit" and "baseline unit size" as conditions | sc01 item 2 |
| Scope as a condition | "across the four mission concepts"; a count bound to the wrong noun | sc01 item 3 |
| Context in a caption only | The baseline's size named only in a figure caption | sc01 |
| Conditions lost or mixed in | "during the cool, martensite phase" dropped; attribute and condition run together | r07; s01 |
| Part stated as the whole | One layer's material as the composition | s01 |
| Quantity roles | Clearance read as depth; an elevation as a length | s01 |
| Abbreviations defined elsewhere, one entity under two names | "PI = proportional-integral"; "baseline blade-pitch controller" | levers; r03 |
| Quote forms | Elided quotes, line-end hyphenation, Unicode variants, paraphrase | r09 |
| Requirements, negation, ranges, inequalities | "shall not exceed 60 C" as "is 60 C"; "<= 85 dBA" as 85 dBA | extract (guarded); taxonomy examples |

**Layout, furniture and the text layer**

| Knob | Situation | Seen in |
|---|---|---|
| Running headers and footers, page numbers | In context in 5 of 8 sampled queries | levers |
| Text cut mid-sentence | "This focus is", "defined in the W" | levers |
| Numbered items across pages | "Contest 9 > 9-3 > k. > (iii)"; a heading split over lines | RH; extract |
| Several sections on one page | Rules attributed to the next section, which starts lower on the page | s01 |
| Boxed headings | Taken for figures | s01 |
| Caption traps | "Table 5-1 summarizes…", "Figure 1 shows…", list-of-figures entries, M201 against M-201 | s01; situate |
| Equations | Garbled, one character per line | RH |
| Scans | Images with little text | situate |
| Two columns, no outline | Layouts the samples lack | RH; store m4 review |

**Across pages and documents**

| Knob | Situation | Seen in |
|---|---|---|
| A caption on another page | Filter values bound only through a cited caption | r05 |
| Missing context, as judges saw it | Surrounding text 68, another page 36, legend 20, table header 16, heading 15, caption 13 | s01 |
| Two teams' designs | One design's datum used for the other | s01 |
| Units by case | `mW` as megawatts; "ton", kVA against kW, gauge against absolute (planned) | robustness baseline; units plan |
| Synonyms across documents | "P-101" against "primary pump" | store plan; retrieval plan |
| Superseded values | A hidden superseded sheet; errata (planned) | synthetic workbook |

## Milestones

1. **The fact model, the key and the scorer;** prose and plain tables; two projects generated deterministically.
   - The scorer is checked on perfect and deliberately flawed claim sets.
   - The pipeline reads the corpus with gemma-4, recorded (a few cents).
2. **The table, layout and prose knobs,** shared with the table plan's milestone 1 (its table eye tests become sweeps here).
3. **Charts, schematics, drawings and rasterised pages,** reusing the eye and page tests' drawing:
   - 3a: charts and scanned pages (done)
   - 3b: schematics and concept diagrams, with relational facts scored (done)
   - 3c: drawing sheets, stacked bars and line charts (done)
4. **Revision pairs and comparison scoring.**
5. **Into rounds:** the controlled stratum reported beside judged win rates, exactly scored.
6. **New failures become knobs:** each round's review and post-mortem adds the situations it finds.

## Progress

- **Milestone 1 (2026-10-01): done.**
  - **Code:** `controlled.py` and `scripts/controlled.py`. The corpus (PDFs and answer keys) is in `benchmarks/controlled/docs`, its recorded answers in `replay.zip`, and the scores in `results.json`.
  - **Two projects:** the water treatment plant (33 facts) and the roller coaster (31, one a superseded lift height), as prose and plain tables laid out by PyMuPDF's Story. The same seed gives the same PDF bytes.
  - **Every printed number is logged with its role,** and every fact located on its page.
  - **Binding is decided by words.** A printed value names one fact, so the question is which fact the claim's words describe best: entity, attribute and conditions taken together, rare words counting more, plurals and a few synonyms folded.
    - Matching names exactly was too brittle: 9 of the coaster's claims were marked misbound, though by hand most were right ("train | car count | 6").
    - **A ruling against leniency:** a test keeps true misbindings misbound (one pump's capacity under another's tag, or as its head).
  - **gemma-4 on the clean corpus** ($0.012): recall 1.0 on both documents, nothing misbound, 10 of 13 conditions kept.
    - Checked by hand: a sample of the "right" claims were right.
    - Expected for clean prose and tables. The knobs (milestone 2) are where failures should show.
  - **A test** generates the corpus again (byte-identical to the committed PDFs), replays the pipeline from the fixture, and gets the committed scores.

- **Milestone 2a, the table knobs (2026-10-01): done.**
  - **Two schedule documents per project:** WTP equipment (84 facts: pumps with blowers stacked under them, and 20 valves) and coaster track and structure (92 facts: elements with brakes under them, and 20 support columns).
  - **Each is drawn clean and under one knob at a time,** with the same facts either way:
    - **stacked:** a section row relabels the columns, as in HabEx p4
    - **multilevel:** grouped headers
    - **multivalue:** "hp / rpm" in one cell
    - **dense:** a 20-row table
    - **continued:** split across a page break with the header repeated
    - **all:** every knob together
  - Story can split a table across pages on its own. Such tables now start on a new page, so only the "continued" knob splits one.
    - **Corrected in milestone 2b:** the check saw only where a table opened, so in 9 of the 14 documents a table still ran over a page break (on the coaster's dense schedule, 14 rows on one page and the rest on the next). Each table's last row is now marked too, and those documents were drawn and read again; the table below is the corrected one.
  - **gemma-4 read all 14 documents for $0.29.** Rows identical across variants are the same queries, so their answers served every variant.

    | Knob | WTP: recall / right / misbound / loose | WTP misbound by reader (table, text, image) | Coaster: recall / right / misbound / loose | Coaster misbound by reader (table, text, image) |
    |---|---|---|---|---|
    | clean | 1.00 / 84 / 6 / 27 | 0, 0, 6 | 1.00 / 92 / 18 / 49 | 0, 18, 0 |
    | stacked | 1.00 / 84 / 9 / 27 | 3, 0, 6 | 1.00 / 88 / 9 / 52 | 9, 0, 0 |
    | multilevel | 1.00 / 84 / 6 / 15 | 3, 0, 3 | 1.00 / 92 / 20 / 38 | 10, 10, 0 |
    | multivalue | 1.00 / 84 / 0 / 18 | 0, 0, 0 | 0.94 / 86 / 25 / 16 | 6, 13, 12 |
    | dense | 1.00 / 84 / 0 / 29 | 0, 0, 0 | 1.00 / 92 / 0 / 39 | 0, 0, 0 |
    | continued | 1.00 / 84 / 6 / 18 | 0, 0, 6 | 1.00 / 92 / 15 / 34 | 0, 15, 0 |
    | all | 1.00 / 84 / 6 / 6 | 6, 0, 0 | 1.00 / 86 / 21 / 59 | 2, 16, 3 |

    - **Before the correction,** WTP dense had 6 misbound; coaster multilevel 44 (12, 32, 0), multivalue 28, and all 11 with 82 right. The findings below held either way.
    - **Loose** claims fit more than one fact, or none, by their words. They're the image reader's on every schedule (15–45 per document: "V-319 | column 2 value", rows read without their header). The table reader's appear only under grouped headers (14 on the coaster's multilevel, 22 on all), naming the group: "E3 | Dynamics | 57.5" is E3's entry speed.

  - **Every fact is found by some reader** (recall); misbinding is where the knobs show.
  - **The table reader misbinds only under a knob,** never on the clean, dense or continued schedules.
    - Under stacked and grouped headers, the brakes' values were filed under the track elements' labels ("BR1 | Vertical g | 33.5" is its entry speed). The blowers' pressures were filed as the pumps' TDH.
    - That's spot check sc01 item 1, reproduced and exactly scored.
  - **The text reader misbinds most on the coaster's schedules,** shifting columns in a table's text-layer chunk. The lever index has a new row for it.
  - **The image reader** now and then mislabels a row: pump P-101A's motor called "blower 1".
  - **Checked by hand:** the misbound and hallucinated claims were the model's errors.
    - One scorer flaw, found that way, was fixed: words from the conditions (where a model put the section's name) outweighed the attribute's. Attribute words now count most, entity words next, conditions only to break ties.
  - **One seed, one sample per query:** these are counts to compare between knobs, not rates to quote.

- **Milestone 2b, prose traps and layout knobs (2026-10-01): done.**
  - **A third project:** a convention centre expansion's design basis (Lakeshore Hall C, 23 facts), written to the prose traps of spot check sc01 and earlier reviews. Each fact has a plain and a trap phrasing:
    - **alternatives compared:** chilled beams against a VAV baseline, in one sentence (sc01 item 2's "2 ton unit")
    - **a scope:** a total "across the four halls" (sc01 item 3)
    - **context in a caption only:** the meeting rooms' table names its hall only in the caption
    - **requirements and negations:** "shall not exceed 45 dBA", "no less than", "not rated for snow loads above"
    - **a range:** "held between 66 and 75 °F"
    - **a part of a part:** AHU-3's supply fan motor
  - **Knobs:**
    - **clean:** the plain phrasings
    - **traps:** the trap phrasings
    - **furniture:** a running header of a document number and a date, logged as numbers that aren't facts
    - **two-column:** the page in two columns
    - **all:** every knob together
  - Number-free prose fills two pages, so columns and running headers matter without printing numbers a reader could mistake for facts.
  - **The scorer, extended:**
    - **A range claim** ("66 to 75 °F") stands for both its bounds. Feet and inches ("2'-9 1/2\"") stay one value.
    - **A limit counts as kept** however it's put: in words ("not to exceed", "no less than") or signs ("<= 39 psf"), in the conditions, entity, attribute or value.
    - **A claim read twice,** by two readers or overlapping tiles, counts once. Either reading may keep its conditions.
    - Units like "ft²" are no longer logged as printed numbers.
    - Conditions kept are reported by reader.
  - **Tables are kept whole** across pages and columns (the milestone 2a correction above).
  - **gemma-4 read the five documents for $0.021,** and the nine corrected table documents again for $0.116.

    | Knob | Recall | Right | Misbound | Conditions kept | Kept by the table reader |
    |---|---|---|---|---|---|
    | clean | 1.00 | 23 | 0 | 12 / 12 | 8 / 8 |
    | traps | 1.00 | 23 | 0 | 12 / 12 | **0 / 8** |
    | furniture | 1.00 | 23 | 0 | 12 / 12 | 8 / 8 |
    | two-column | 1.00 | 23 | 0 | 12 / 12 | 8 / 8 |
    | all | 1.00 | 23 | 0 | 12 / 12 | **0 / 8** |

  - **The prose traps didn't trip gemma-4** in these phrasings.
    - It named the alternatives as entities ("Chilled beam option | first cost | 20.8 M$"), the scope in the entity ("four halls"), and the limits ("maximum snow load rating", "<= 39 psf").
    - Neither the running header nor two columns cost a fact.
    - *Inferred:* sc01's failures came from real documents' context (the alternative named in a figure caption, far from the value), which these short, self-contained sentences don't reproduce. Harder phrasings are a backlog item for milestone 6.
  - **The caption trap shows by reader.** With the hall named only in the caption, the table reader dropped it for all 8 room values ("Room 101"). The text and image readers kept it ("Room 101", conditions "Hall C"). The lever index has a row.
  - **The scorer's own flaws, found by reading the claims by hand:** the range and the signs above, and claims dropped as repeats before their conditions were checked.
  - **Not yet:** text cut mid-sentence, numbered items across pages, boxed headings, caption traps ("Table 5-1 summarizes…"), equations and scans. They come with milestone 3's drawing tools, or as milestone 6 finds them.

- **Milestone 3a, charts and scanned pages (2026-10-01): done.**
  - **A fourth document:** Hall C's cooling energy study (21 facts). It has two charts and the text's totals:
    - **Figure 1:** the two options' monthly cooling energy, May to October, as grouped bars (sc01 item 2)
    - **Figure 2:** peak cooling load by zone, one series
    - **prose:** the season totals (the sums of the bars) and the peak demand
  - **Charts are drawn** into room Story leaves for them, after layout.
    - The drawer logs every number it draws: tick labels as structure, bar values as facts. So a bar's value and a tick label of the same number aren't confused.
    - Story lets a fixed-height box overflow the page, losing what follows it. Such a chart now starts a page.
  - **Knobs:**
    - **clean:** a vector chart, values printed above the bars
    - **axis:** no printed values, so bars are read against the axis
    - **raster:** the chart pasted as an image
    - **legend-caption:** the series named only in the caption ("dark bars: Option 1…")
    - **scan:** every page an image, with no text layer
    - **all:** every knob together
  - **The scorer, extended for bars read against an axis:**
    - A reading within a quarter of the axis's step is right.
    - A claim naming one bar is judged against that bar. Outside its tolerance (up to 10 tolerances off), it's **inexact**: a height misjudged and another bar's height read look alike to the eye.
    - References like "Figure 1" are no longer read as names. One had matched "Option 1".
    - **A limit:** a season total stated "over the cooling season (May to October)" ties with the May and October bars, so 2 right readings per document count as loose.
  - **gemma-4 read the six documents for $0.022:**

    | Knob | Recall | Right | Loose | Misbound | Inexact | Misread |
    |---|---|---|---|---|---|---|
    | clean | 1.00 | 21 | 0 | 7 | 0 | 1 |
    | axis | 1.00 | 21 | 2 | 0 | 9 | 0 |
    | raster | 1.00 | 21 | 2 | 0 | 0 | 0 |
    | legend-caption | 1.00 | 21 | 0 | 0 | 0 | 0 |
    | scan | 1.00 | 21 | 4 | 0 | 0 | 0 |
    | all | 0.95 | 20 | 0 | 2 | 11 | 0 |

  - **Printed values:** the image reader read every bar right. The text reader read the chart's values from the text layer and paired them with the wrong months (7 misbound), and took a tick label ("200") for a value. The lever index has a row.
  - **Values only against the axis:** 9 of the image reader's readings, of 8 of the 12 monthly bars, were off by more than a quarter step. With every knob on, 11 readings of 8 bars were off, up to 125 MWh (July's 375 read as 250).
    - Another reading of each bar (from another tile or reader) was right, so recall hides this; the inexact count shows it.
    - The eye test's axis cards read 100% when asked bar by bar.
    - *Inferred:* the extraction prompt doesn't ask for careful reading against the axis. The lever index has a row.
  - **The legend only in the caption** cost nothing alone. On the scanned page the image reader named series by colour 4 times ("May value (dark blue series)"). With every knob on, it missed Option 2's September bar.
  - **Checked by hand:** every misbound and inexact claim, and the loose ones.
  - **Not yet:**
    - schematics and concept diagrams (milestone 3b, since done)
    - drawing sheets (3c)
    - stacked bars and line charts (3c, with the drawing sheets)
    - noise on scans

- **Milestone 3b, schematics and relations (2026-10-01): done.**
  - **Relations** (`relations.py`): about 30, each with the phrasings a reader may use and its inverse.
    - **A claim is read into triples:**
      - its names matched to the document's parts and places
      - its relation found from the words left over
      - a path ("A -> B -> C") split into pairs, a list into its members, "between A and B" into two steps
    - **Each triple is classed:**
      - **right:** a fact, from either side
      - **implied:** true but not a stated fact, such as two steps upstream, a part of a part, a link whose kind isn't said, or a motor driving the unit its fan is part of
      - **reversed**
      - **wrong**
      - **invented:** a name the document doesn't have
      - **unscored:** no relation named, as when a function is described
  - **Two systems** (`schematics.py`), each a description of parts, a path, the parts hung off it, enclosures and links:
    - **AHU-3:** a recirculating air path, a casing round four parts, a motor and its panel, a controller, and a sensor on the duct (19 relations, 2 numbers)
    - **The Kestrel UV channel:** a light path, a guide-mode branch at the dichroic, focal and pupil planes, movable parts, and a field stop with two options (22 relations)
  - **Eight knobs:**
    - **clean:** labelled boxes and links, with every relation also stated plainly
    - **prose** and **prose-hard:** no figure; plain, or inverse, passive and narrated phrasings
    - **figure-only:** the text cites the figure
    - **leaders:** symbols with their names on leader lines
    - **folded:** the path snaking back in rows
    - **legend:** link kinds told only by line style
    - **all:** leaders, folded and legend, with half the relations also told in hard prose
  - **Drawn fairly:** a layout search places the parts off the path so no line crosses a box, and no two lines run together or leave a part at one angle (a test checks every layout). Labels never overlap.
  - **gemma-4 read the 16 documents for $0.048:**

    | Knob | AHU-3: relations found | AHU-3: wrong / implied | UV channel: relations found | UV channel: wrong / implied |
    |---|---|---|---|---|
    | clean | 1.00 | 0 / 0 | 1.00 | 0 / 2 |
    | prose | 1.00 | 0 / 0 | 0.91 | 0 / 0 |
    | prose-hard | 1.00 | 0 / 0 | 1.00 | 0 / 0 |
    | figure-only | 0.95 | 4 / 1 | 0.91 | 3 / 3 |
    | leaders | 0.95 | 5 / 8 | 0.86 | 11 / 3 |
    | folded | 1.00 | 4 / 2 | 1.00 | 7 / 2 |
    | legend | 0.89 | 4 / 11 | 0.82 | 6 / 2 |
    | all | 0.89 | 4 / 3 | 0.91 | 5 / 14 |

  - **Relations stated in words are read almost perfectly,** plainly or not. The one miss: the UV channel's two stop options, stated in one sentence, which no reader extracted.
  - **Figures cost a few relations each, and harder drawings more wrong ones:**
    - **Leader labels:** notes went to a neighbouring part ("EMCCD | plane | pupil plane", "narrow stop | mobility | movable"), and one name was read as "Ha".
    - **Legend-only line styles:** the image reader mostly wrote "connected to" without the kind (11 implied on AHU-3), and traced a control line to the wrong part.
    - **Outlines:** parts drawn outside a casing or channel outline (the outdoor air damper, the dichroic) were credited to it.
    - **Small marks:** the sensor's stem to its duct was missed whenever only the figure showed it.
  - **The scorer, found wanting by reading every claim that wasn't right, and fixed before these figures:**
    - **Phrasings readers used that the vocabulary lacked:**
      - paths: "airflow destination", "flow target", "output connection", "input source", "drive target", "power target"
      - membership: "system membership"
      - states: "selectability"
    - **Generic links:** "connected to" or "directed connection" now take their kind from beside them ("control signal", "drive shaft", "air or light"), and are implied without one.
    - **A part named as the attribute** ("UV channel | detector | EMCCD") reads as membership.
    - **Fair inferences counted wrong:** the duct serving the hall, a motor driving the unit, a sensor "located in" its duct.
    - **A fact missing from the key:** the description's "AHU-3, which conditions Hall C".
    - **A limit:** on a recirculating loop, everything is upstream of everything, so loop claims can only be implied, never wrong.
  - **Next:** more relations and more systems that present them in different ways (the owner's direction), within drawing sheets (3c) and beyond. Mechanical assemblies (attached to, mounted on, supported by) are the gap that stands out.

- **Milestone 3c, drawing sheets, stacked bars and line charts (2026-10-01): done.**
  - **A floor plan sheet** (`sheets.py`), an ARCH D sheet (36 × 24 in) at 1/8" = 1'-0", drawn as a drafter would:
    - a structural grid with lettered and numbered bubbles
    - seven rooms tagged with name, number and area
    - width and depth dimension strings in feet and inches
    - doors with swings and tags
    - a door schedule, general notes, a title block and a revision table
  - **Facts (45):** each room's width, depth and area; each door's width, height and room; each revision's date.
  - **Knobs:**
    - **clean**
    - **small:** dimension text at 4.5 pt
    - **vertical:** depth dimensions written sideways
    - **rotated:** the sheet stored turned 90°
    - **all:** small, vertical and rotated together
  - **Lengths are compared in inches,** however written: 58'-6", 58 ft 6 in, 58.5 ft, 702 in, or "58" with "'-6\"" as its unit. Dates are compared as dates.
  - **Stacked bars and line charts:** Hall C's energy by end use (cooling, fans and lighting stacked by month), the options' monthly peak loads as lines, and the season totals in the text (33 facts), under the chart knobs.
  - **gemma-4 read the 11 documents for $0.075:**

    | Sheet knob | Recall | Found right | Loose | Misbound | Relations right / reversed |
    |---|---|---|---|---|---|
    | clean | 1.00 | 43 | 26 | 6 | 7 / 1 |
    | small | 1.00 | 41 | 32 | 6 | 7 / 4 |
    | vertical | 0.98 | 41 | 16 | 8 | 6 / 3 |
    | rotated | 1.00 | 31 | 32 | 17 | 13 / 0 |
    | all | 0.98 | 32 | 32 | 19 | 13 / 0 |

    | End-use knob | Recall | Found right | Misbound | Inexact | Loose |
    |---|---|---|---|---|---|
    | clean | 1.00 | 33 | 5 | 0 | 0 |
    | axis | 1.00 | 33 | 0 | 10 | 0 |
    | raster | 1.00 | 33 | 2 | 0 | 0 |
    | legend-caption | 0.94 | 31 | 6 | 0 | 0 |
    | scan | 1.00 | 33 | 0 | 0 | 9 |
    | all | 0.82 | 27 | 0 | 11 | 0 |

  - **Sheets: every value is read, but binding suffers.**
    - **Rotation costs binding, not reading:** facts read right fall from 43 to 31, and misbound claims rise from 6 to 17. The text reader's misbound claims go from none to 5–7. The lever index has a row.
    - The image reader often gives a dimension without its room ("dimension | length | 23'-0\" | between grid lines"): 16–32 loose claims per sheet.
    - Door sizes from the schedule were filed under room names (the schedule's ROOM column), and once a depth was read as a width.
    - The table reader took room outlines for tables.
  - **Stacked bars and lines:**
    - Printed values: the image reader read them all right. The text reader paired the lines' labels with the wrong months (5 misbound), as on 3a's bars.
    - With the legend only in the caption, the image reader swapped the options where the lines cross.
    - On the scanned page it named segments by position ("top segment"): 9 loose.
    - Against the axis, 10–11 readings were off by more than a quarter step.
  - **The scorer, from reading the claims by hand:**
    - lengths and dates as above
    - "length" dropped as a synonym of width, since a room's length isn't its east-west side
    - a claim naming two things, the value's own among them ("D104 MEETING 104"), is loose, not misbound
    - **a value that repeats** (25 MWh in four months, a door width) **was counted once:** claims are now told apart by the fact each resolves to
    - season totals named like the months, the season telling them apart
    - door phrasings ("door identifier")
    - the corridor as a named thing
  - **A correction caught before any reading:** extending the chart drawer changed two committed chart PDFs' bytes. It was restored, and a test now generates every committed document again, byte for byte.
  - **Not covered:** the drawing scale is a fair claim the key lacks (1–4 misread per sheet); details, callouts and sections; noise on scans.

- **Milestone 4, revision pairs and comparison scoring (2026-10-02): done.**
  - **Code:** `revisions.py` (the pairs and their edits) and `comparison.py` (the scorer). `scripts/controlled.py run` reads every document, then compares each pair in revisions mode; `score` writes `comparisons.json`.
  - **Six pairs, one per kind of document.** Each pairs a corpus document with a revision made by editing it. The corpus document is unchanged byte for byte, so its recorded answers serve the pair; only the revision is read anew.

    | Pair (forms) | Changed | Added | Removed | Unchanged |
    |---|---|---|---|---|
    | `wtp-s1` (prose, tables) | design flow, a pump's capacity, maximum alum dose, UV's capital cost | pump P-101D (3 facts) | chlorine dose (its sentence) | 28 |
    | `coaster-s1` (prose; the change narrated) | lift hill height, train mass, hourly capacity, the loop's entry speed | the helix (3) | station platform length | 23 |
    | `wtp-tables-s1-clean` (schedules) | a pump's power, a blower's pressure, a valve's Cv | pump P-101D (4) | valve V-314 (3); the valves below move up across the split tables | 78 |
    | `lcc-s1-traps` (trap phrasings) | noise limit tightened ("shall not exceed"), roof snow rating ("not rated for … above"), chilled beams' first cost (stated against the baseline's) | room 105 (2) | room 104 (2): a renumbering | 18 |
    | `lcc-energy-s1-clean` (charts) | two monthly bars, the two season totals that follow them, a zone's peak load | – | – | 16 |
    | `lcc-plan-s1-clean` (drawing sheet) | room 102's width and area, door D103's width | revision D's date (the revision table) | – | 35 |

    - The coaster's corpus document is revision B, which says the lift hill "was raised from 178 ft to 230 ft". So its earlier revision is the generated one, and the later prints the superseded height beside the new.
  - **Keys stay honest by construction** (a test checks each rule):
    - a value is changed wherever it's printed, as a whole token ("3" never inside "3-second")
    - every fact must be placed on the page
    - a revision may print no number its base doesn't, besides facts, added items' names and page numbers, so an edit that missed a printed value is caught
  - **The scorer** binds each revision's claims to its own key's facts (`score.classify`; a range to both bounds). A finding then pairs one fact read in both revisions, or two facts. Each fact is classed by what the report says of it:
    - **changed:** reported (a "different" finding), called equivalent, uncertain, other, unpaired, unextracted
    - **unchanged:** confirmed (equivalent), false change (different), uncertain, other, unpaired, unextracted
    - **added or removed:** reported (a claim left without a counterpart, as the report lists them), as a change, called equivalent, other, unextracted
    - **every "different" finding** too: a change, no change, a misreading, across facts (two facts' claims), unscored (a claim bound to no fact). Precision is the share that are changes.
  - **gemma-4 compared the six pairs for $0.305:** $0.058 to read the six revisions, $0.247 for 1,798 comparisons.

    | Pair | Changes found | Additions | Removals | Unchanged confirmed | "Different" findings that are changes | Comparisons |
    |---|---|---|---|---|---|---|
    | `wtp-s1` | 4 / 4 | 3 / 3 | 1 / 1 | 28 / 28 | 5 / 5 | 172 |
    | `coaster-s1` | 4 / 4 | 1 / 3 | 1 / 1 | 23 / 23 | 7 / 11 | 165 |
    | `wtp-tables-s1-clean` | 3 / 3 | 4 / 4 | 3 / 3 | 78 / 78 | 4 / 15 | 606 |
    | `lcc-s1-traps` | 3 / 3 | 2 / 2 | 2 / 2 | 18 / 18 | 3 / 6 | 117 |
    | `lcc-energy-s1-clean` | 5 / 5 | – | – | 16 / 16 | 5 / 6 | 198 |
    | `lcc-plan-s1-clean` | 3 / 3 | 0 / 1 | – | 35 / 35 | 17 / 77 | 540 |

  - **Every change was found, and every unchanged fact confirmed:**
    - 22 of 22 changes paired with themselves as different
    - 198 of 198 unchanged facts paired with themselves as equivalent; none called different
    - 7 of 7 removals left without a counterpart, as the report lists removals
    - 10 of 13 additions likewise; the other 3 were taken for changes (below)
    - the coaster's superseded height, printed beside the new one, didn't hide its change
    - the renumbered room was reported as a removal and an addition, not as a change
  - **But most "different" findings weren't changes:** 41 of 120 were. The other 79:
    - **Names by position (59).** The image reader named rows by position ("blower 5") and dimensions by order ("dimension 2").
      - Inserting pump P-101D moved every blower down a row, so "blower 5" was B-402 in one revision and B-401 in the other: 11 false differences.
      - On the floor plan, unlabelled dimensions were compared across rooms' widths and depths: 48.
    - **Two items of a kind taken for one item changed (17).** In revisions mode the prompt says corresponding claims describe the same object, and the model took "the same kind" for "the same":
      - different track elements ("First drop | peak g | 2.3" against the Camelback's 2.8), and the new helix against older elements
      - revision D's date against revisions A, B and C's
      - the two cooling options' loads and demands: spot check sc01 item 2's alternatives trap, met again in comparison
    - **A claim bound to no fact (3).**
  - **The approximate-reading veto** made 23 of the energy study's findings uncertain. Most were the text reader's month-shifted chart values (milestone 3a's known flaw), read alike in both revisions.
  - **Checked by hand:**
    - every "different" and "uncertain" finding of the coaster, design basis and energy study pairs
    - every difference between two facts in the schedules pair, and 15 of the floor plan's 60, with its date findings
  - **The scorer's own flaw, found that way:** a range ("66 to 75 °F") was bound to its first number only, so the maximum temperature looked unextracted. It's now bound to both bounds, as extraction scoring reads one.
  - **The local run stores were rebuilt.** Stores bound before the architecture clean-up record the settings differently (temperature became a constant), so they refused to load. They were moved aside, and every document replayed from the fixture: no answer missing, the committed extraction scores unchanged, and the pairs' replayed comparisons scoring as recorded.
  - **The lever index has two new rows:** a change needs the same item, and names that carry identity.
  - **Not covered:**
    - relations (a door's room, schematics' links) aren't compared
    - conditions changed with the value kept, and items renamed
    - one seed, one sample per query
    - these are counts to compare between levers, not rates to quote

## Decisions (2026-10-01)

1. **Domains:** new ones for inspiration, with backups logged (design item 1); the owner left the choice open.
2. **Hallucinated claims count, viable or not:** the full log of printed content makes them exact (design item 5).
3. **The controlled stratum's weight in rounds.** The owner, on Claude's "join the decision criteria only once its scores track judged quality": "Not sure exactly what ... means, but if you mean that it's given extra weight because we have a clear standard then sure."
   - **Claude meant:** first only report it, and give it a role in accepting levers once it's seen to agree with judged quality on real documents, so a lever can't win by fitting the generator.
   - **The role proposed, for the owner's review:**
     - **An exact loss on the controlled stratum blocks a lever,** like a losing stratum: a regression against a clear standard is a real defect.
     - **An exact gain can serve as a "no worse" lever's named gain.**
     - **A gain there alone never promotes a lever** that the judged real documents don't support.

   - **The owner (2026-10-01):** "We can try this rule, though it may be a bit rigid. We should probably contemplate tracking multiple 'cursors' for leading configurations of levers to mitigate the local minima/maxima traps that we might run into with rigid rules." The cursors idea is recorded with the lever search (plans index).
4. **Representations as controls (2026-10-02).** The owner: "When we do add the alternative readers, we'll implicitly get a new form of control tests: same facts across two or more representations, within constraints of being unable to effectively represent all media (I'm not inclined to even try to interpret ASCII art as figures, for example.)"
   - **Claude's reading:** as each reader is added ([multi-format adapters](multi-format-adapters-2026-09-23.md)), the corpus is also written in that reader's format (`.txt`/`.md`, `.docx`, later `.pptx`, `.csv`/`.xlsx`), each fact with a known place in it. The same key then scores each representation, and the medium becomes a knob beside the others, extending the table plan's medium test (Uses).
   - **Only what a format carries:**
     - a chart or schematic stays out of plain text rather than being drawn as text
     - the facts it holds are marked absent from that representation, not missed

## Open questions

None at present.
