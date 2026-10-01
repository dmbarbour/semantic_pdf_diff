# Controlled documents with known facts

- **Status:** Active (2026-10-01): milestones 1, 2a (table knobs), 2b (prose traps and layout knobs) and 3a (charts and scanned pages) done.
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
- **Values drawn from the seed** within plausible ranges, so they can't be guessed. They're written in the forms documents use: `1,250`, `0.075`, `±0.05`, `4–6`, `≥ 3`, `2'-9 1/2"`, `-43.73E+6`.
- **Distractors in the key, marked as such:** another component's value of the same kind, superseded values, negations ("not rated for…"), ranges and inequalities.

**2. Renderers: each fact in one or more forms, at a known place** (PyMuPDF, as the eye and page tests draw):
- **Prose:** templated sentences in several phrasings, conditions in clauses, a section and numbered-item structure, captions and cross-references ("see Table 3").
- **Tables:**
  - layouts: items in rows or in columns, case tables, matrices
  - with the table plan's hazards as knobs
- **Charts:** bars, stacked bars with legends, lines with operating points; printed values or axis-only; panels labelled (a)–(f).
- **Drawings:** sheets at real sizes (rotated as stored), labelled components, arrows, dimensions in feet and inches, callouts, details with grid-referenced titles, title blocks and revision tables, line work.
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
3. **Charts, drawings and rasterised pages,** reusing the eye and page tests' drawing.
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
  - **Not yet:** drawings (dimension strings, tags with leaders, title blocks), stacked bars, line charts, and noise on scans. Those come in milestone 3b.

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

## Open questions

None at present.
