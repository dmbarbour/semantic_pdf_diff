# Samples and testing

## Tests and demo

The product is `src/semantic_pdf_diff`. The lab, how it's measured and improved (rounds, judges, review panels, spot checks, controlled documents, eye and page tests), is its own distribution in `lab/` (`semantic_pdf_diff_lab`), installed beside it. It adds its commands to `semantic-pdf-diff` through entry points. `tests/test_boundaries.py` keeps the product from importing it.

```bash
pip install -e '.[dev]' -e lab
python -m unittest discover -s tests -v
QUICK=1 python -m unittest discover -s tests    # skips the slowest tests (marked @slow): for iterating
python scripts/run_tests.py                     # the same suite, one module per process on every CPU: about 4.5 minutes
python examples/demo.py
```

**The commit gate** (`scripts/gate.py`; enabled in a checkout by `git config core.hooksPath scripts/hooks`):

- `scripts/run_tests.py` run over every module records a pass for the tree it tested: the working folder as git would commit it, untracked files included. A tree edited during the run gets no pass.
- A pre-commit hook lets a commit through when its staged tree has a recorded pass. Otherwise it checks the staged tree out into a temporary folder (with `samples/` linked in), runs the quick suite there (about 3 minutes), records the pass, and blocks the commit on a failure. A partial commit is tested as committed.
- `python scripts/gate.py status` says whether the working tree and the staged tree have passes.

Tests use a local HTTP stub, temporary PDFs and controlled evidence. They exercise cross-format and many-to-one retrieval, case-sensitive unit conversion, uncertainty gates, UTF-8 chunking, text grouping and refinement, table column splitting, tile spacing and coverage, rotated pages, visual quote checks, malformed/truncated/null API output, `Retry-After`, claim salvage, caching, budgets, quote validation and HTML escaping. Synthetic spreadsheet tests check that the generated messy samples match their answer keys; they need the `dev` extra and are skipped without it. None of this establishes real-model extraction accuracy; see [VALIDATION.md](VALIDATION.md) and [what's measured](../benchmarks/README.md#whats-measured).

`examples/demo-output/report.html` is an explicitly hand-authored fixture report; it makes no API calls.

## Public sample corpus

A public test corpus of competing proposals and design revisions can be downloaded into the git-ignored `samples/` folder. Real documents are sensitive and aren't shared (the tool runs on them inside a multi-layer sandbox), so readers' heuristics are developed on this corpus and must fall back gracefully where real documents differ, e.g. a PDF without an outline (the evidence store plan, 2026-09-24). Every file is checked against a pinned SHA-256 hash, and TLS is always verified:

```bash
python scripts/fetch_samples.py --list      # sets, sizes, sources and terms
python scripts/fetch_samples.py             # default sets (~150 MB)
python scripts/fetch_samples.py --all --make-zips
```

| Set | Contents |
| --- | --- |
| `solar-decathlon-2013` | Four competing house designs, one folder per team (drawings, project manual, jury score sheets), plus shared rules |
| `wind-reference-turbines` | Three reference turbine designs with PDF reports and `.xlsx` data, plus an older spreadsheet revision |
| `ietf-quic-transport` | Plain-text draft revisions through RFC 9000 |
| `3gpp-ts38300-revisions` | Zipped `.docx` revisions of a 5G specification (one legacy `.doc`) |
| `3gpp-ran1-beam-management` | Four companies' competing `.docx` proposals plus moderator summaries |
| `3gpp-rel19-aiml-views` | Nine companies' competing views in `.pptx`, `.docx` and PDF |
| `archive-edge-cases` | Nested zips |
| `nasa-flagship-concepts` (optional, ~320 MB) | Competing mission-concept reports, interim and final |
| `wide-pages` (optional, ~145 MB) | Pages wider than bands serve, for tile selection: slide decks, landscape text pages, construction drawings and posters, split into `dev/` and a held-out test set, `heldout/` (measured only to check a change already chosen on `dev/`) |

The 3GPP files are kept as downloaded zips, since zips are meant to be read as folders. Sources and terms are in `scripts/samples.json`. For example:

```bash
semantic-pdf-diff compare samples/wind-reference-turbines/nrel-5mw/NREL-5MW-reference-turbine.pdf \
  samples/wind-reference-turbines/iea-15mw/IEA-15MW-reference-turbine.pdf --store wind-diff
```

## Recorded answers (replay fixtures)

Recorded model answers let the real pipeline run offline. A query is named by the hash of what reaches the model, so a changed query is a miss, never a stale answer. The design is in [decisions 0006 to 0010](decisions/README.md).

- **The committed fixture:** `tests/fixtures/replay-slices.zip`, answers from `google/gemma-4-31B-it` (DeepInfra) for the development runs in `scripts/slices.json`.
- **Slices:** page ranges cut from the public samples, byte-identical for the PyMuPDF version pinned in `slices.json`. `make_slices.py` says so when bytes differ.
- **What a fixture holds:** `semantic-pdf-diff fixtures summary FILE` lists answers per responder, role and outcome, tokens, and the PyMuPDF version it was recorded with.

```bash
python scripts/fetch_samples.py --set wind-reference-turbines --set solar-decathlon-2013 --set nasa-flagship-concepts
python scripts/make_slices.py                                  # writes samples/slices/
python -m unittest discover -s tests -p test_replay_slices.py  # the first three development runs, about 100 s
```

The replay test skips without the slices, when the fixture was recorded from other slices, or under a PyMuPDF version other than the fixture's, since text and renderings may differ. `REPLAY_ALL=1` replays every run the fixture holds rather than the first three: the committed fixture holds the development runs, and held-out runs are recorded into local fixtures only.

**Recording** calls the model configured through `OPENAI_*` and costs money. `scripts/record_runs.py` runs the slice runs live with a fixture attached:

```bash
python scripts/record_runs.py --fixture tests/fixtures/slices.sqlite --set dev --max-cost 1 \
    --pack tests/fixtures/replay-slices.zip
python scripts/record_runs.py --replay --fixture tests/fixtures/replay-slices.zip --out benchmarks/runs/baseline
```

- **Into an archive:** each corpus's working `.sqlite` (git-ignored: `tests/fixtures/slices.sqlite`, the controlled corpus's `benchmarks/controlled/fixture.sqlite`, the real pairs' and the probes') keeps every answer ever recorded, every variant's. A query is named by what reaches the model, so variants' answers sit side by side. Several processes may record into one archive at once. A `.zip` is for replay only.
- **Modes:** by default `record-new`, which asks only what was never asked: the model's failures replay as failures, and transient ones (timeouts, server errors) are asked again. `--retry-failures` uses `replay-or-record`, which asks recorded failures again too. `--replay` asks nothing and fails on anything unrecorded, as the fixture's own responder whatever the environment says.
- **Resumable:** a rerun replays what's recorded. At `--max-cost` it stops with exit code 3. The spend goes to the repository's ledger (`--ledger` names another).
- **Variants:** `--variant FILE` merges a settings JSON over the base settings. Every setting that can change a query is saved, resolved, in `<out>/settings.json`.

**The committed zip is exported, not pruned** (recording tooling, 2026-10-17):

- **`--pack ZIP`** runs into fresh stores in a temporary folder and copies every answer the runs are served or record into a new fixture, which is packed. Recording and exporting is one command; with `--replay`, it exports again from the archive, asking nothing. The runs need fresh stores, since a store already holding a region's claims asks nothing for it.
- **The controlled corpus:** `scripts/controlled.py pack` exports `replay.zip` from its archive the same way. After a change, `controlled.py refresh --jobs 6 --max-cost 2` does every step in order (the standard and row-by-row runs recorded, the export, both replays, scoring, the context measures), with stores bound to other settings reading again what changed. It exits 1 only when a run or a step fails, 3 at the cap.
- **Runs at once:** `--jobs N` (`controlled.py run`, `pack` and `refresh`; `record_runs.py`) spreads the runs over N processes sharing the archive, the documents before the pairs that replay their extraction. The cost cap is checked as each run starts, so runs started together may overshoot it together. On 2026-10-17, six processes exported the corpus in 1.5 minutes (5 alone), eight the slices in 45 seconds (2 minutes alone).
- **The same runs export the same zip,** whatever else the archive holds: the answers they're served, their queries' descriptions and the recipes they noted. Packing is reproducible, so the zip's bytes change only when the runs' answers do.
- **Merging:** `semantic-pdf-diff fixtures merge ARCHIVE SOURCE...` copies in the answers an archive lacks (an arm's copy, a colleague's recording), keeping the archive's own. `--prefer` lets the sources' answers win instead, for a committed zip merged into its archive: an archive holding a variant's later answer to a query would otherwise replay it in place of the committed one.
- **Pruning** (`fixtures prune ARCHIVE --unused-since TIME`) still drops answers no run used since a time, with its guards, but nothing needs it.

## Proving a refactor changes nothing

A refactor or performance change must leave every output as it was ([decision 0027](decisions/0027-behaviour-changes-apart-from-refactors.md)). Replay before and after the change, offline, and compare:

```bash
python scripts/refactor_check.py                    # the working tree against HEAD (about 5 minutes)
python scripts/refactor_check.py --against main~2   # against another revision; --only slices|controlled
```

- **What it replays:** the slices' development runs and the controlled corpus's standard and row-by-row runs, in the working tree and in the revision (checked out into a temporary git worktree, `samples/` linked in), all four at once. Each tree replays from its own fixtures, and nothing is asked of a model.
- **What it compares:** every report.json, whole, but for `created_at` and the tree's path. How each run went is in `run.json` beside it, not the report, and isn't compared. It exits 1 on any difference, listing each run and the fields that differ.
- **A request that isn't recorded fails the replay.** That alone shows a change reached the model; the check names the replay that failed and its log.
- **What the replays don't cover, compare directly:**
  - a renderer's pages, from the same report documents
  - the lab's outputs, regenerated byte for byte (`scripts/eye_test.py report`)
  - a rewritten pure function, against the old one on random inputs
- **Then the full suite:** `python scripts/run_tests.py`.

A changed output means a behaviour change. It goes in a fix of its own, with its test.

## Controlled documents

Documents for fictional projects, generated with every fact's form and place known, so a reader's claims and a comparison's findings are scored exactly against an answer key ([decision 0036](decisions/0036-controlled-documents-with-exact-keys.md)). A key is exact for its own documents only: one strong rater among others ([0018](decisions/0018-several-raters-none-ground-truth.md)). How each part was built and first measured is in the [controlled documents plan](plans/controlled-documents-2026-10-01.md) (closed 2026-10-21).

```bash
python scripts/controlled.py generate        # every document and key, byte for byte as committed
python scripts/controlled.py run --replay    # read every document and compare every pair from replay.zip, offline
python scripts/controlled.py score           # results.json (extraction) and comparisons.json (revision pairs)
python scripts/controlled.py context         # context.json: claims' context against the keys
```

- **Where:** `benchmarks/controlled/docs` (PDFs and their `.key.json`), with the same documents as Markdown (`docs-md`), Word (`docs-docx`), slide decks (`docs-pptx`) and workbooks (`docs-xlsx`). The code is the lab's `bench/controlled/`. Recording and `refresh` are under *Recorded answers*; a lever's arms under *Judging a lever*.
- **Generated, not drawn by hand:** a project's facts are drawn from a seed within plausible ranges and laid out by code. The same seed gives the same bytes, so the pipeline asks the same queries and recorded answers replay. A test (`test_controlled`, `Corpus`) generates every committed document again and compares bytes; it skips under a PyMuPDF other than the fixture's.
- **What a key knows:** each fact (entity and aliases, attribute and synonyms, value, unit, conditions, basis) and where it's placed; every printed number's role (a fact, a distractor such as a superseded value, a section or page number, a tick label); the relations between parts, each with its phrasings and its inverse (`relations.py`).
- **How claims are classed:**
  - right; loose (the fact's value and attribute, a vague entity); misbound (a fact's value under another fact's entity or attribute); wrong unit; misread (a printed number that isn't a fact); inexact (a bar read against its axis, off by more than a quarter step); hallucinated (a value printed nowhere, whether it conflicts or not); facts missed
  - conditions kept, by reader
  - relations: right, implied, reversed, wrong, invented
  - revision pairs: changes, additions and removals found, unchanged facts confirmed, and the share of "different" findings that are changes
- **Reading the figures:** one seed and one sample per query, so they're counts to compare between knobs and arms, not rates to quote. Claims the scorer marks wrong are read by hand; the scorer's flaws found that way are fixed before a figure is quoted.

### Knobs built

A knob draws a document under one difficulty, with the same facts as its clean drawing, so its effect is the difference; `all` combines a family's knobs.

| Documents | Knobs |
|---|---|
| Equipment and track schedules (`wtp-tables`, `coaster-tables`) | `stacked` (a section row relabelling the columns), `multilevel` (grouped headers), `multivalue` (two values in a cell), `dense` (20 rows), `continued` (split across a page, the header repeated) |
| A convention centre's design basis (`lcc`) | `traps` (alternatives compared, a scope, context in a caption only, requirements and negations, a range, an abbreviation defined elsewhere, a part of a part), `furniture` (a running header of numbers that aren't facts), `two-column`; for refinement and tile selection, `decorated`, `landscape`, `slide`, `wide-letter`, `frame`, `frame-lines`, `background`, `scanned-frame` |
| Chart studies (`lcc-energy`, `lcc-enduse`, `lcc-metered`): grouped and stacked bars, lines | `axis` (no printed values), `raster` (the chart as an image), `legend-caption` (series named only in the caption), `scan` (every page an image) |
| Schematics (`ahu-schematic`, `uv-layout`) | `prose`, `prose-hard` (no figure; plain, or inverse, passive and narrated), `figure-only` (the text cites the figure), `leaders` (names on leader lines), `folded` (the path snaking back), `legend` (link kinds told only by line style) |
| A floor plan sheet (`lcc-plan`) | `small` (4.5 pt dimension text), `vertical` (depths written sideways), `rotated` (stored turned 90°) |
| A procedure diagram (`attach`): a message sequence chart | `raster` |
| Word only (`word.py`) | tracked changes, footnotes, numbered lists, merged cells, nested tables, a layout table, text boxes, comments, Word charts |
| Slide decks (`slides.py`) | speaker notes |

Bases that are a difficulty in themselves: two sheets told apart only by their title blocks (`lcc-plans`); a link protocol's specification (`spec`: look-alike formats, fields beside their length fields, numbered conditions, values whose state only a lead-in names); data sheets of headerless key-value blocks (`wtp-datasheets`); proposals' summaries whose claims have holders and attitudes (`views`, `views-grouped`, `views-prose`, `views-poll`, `views-echo`); design notes with hedged values (`hedges`). Revision pairs (`revisions.py`) edit a corpus document: values changed in every form, items added, dropped, renamed, moved or split, a superseded value printed beside the new, conditions changed or reworded, a numbered condition inserted, a message inserted, a holder's view or a hedge changed, context records alone restated, and names abbreviated as an abbreviations list defines them (`wtp-s1-abbreviated`: "an SWD of" for "a side water depth of", two abbreviated values revised).

### The catalogue of situations

Every situation met in this project's documents, where it was recorded, and the knob or base that reproduces it ("–": none yet). A situation met later, in a round, a spot check or a trial, gets a row, and a knob when one is built.

- **Reviews:** sc01 = spot check sc01; s01 = evaluation s01; rNN = round reviews; overall = the overall review of 2026-09-28 (all four retired 2026-10-21: the [plans index](plans/README.md#retired) says how to read one, and the [rounds' record](research/rounds.md) keeps their findings); levers = [lever index](reviews/levers.md).
- **Plans:** the table plan = the one table model plan; the store plan = the evidence store plan; both retired 2026-10-21, as was the robustness baseline (the [plans index](plans/README.md#retired) says how to read one; the table plan's decisions are [0023](decisions/0023-tables-read-by-rules-a-model-writes.md) and [0024](decisions/0024-pdf-table-structure.md)).
- **Research:** eye = [eye tests](research/eye-tests-2026-09-30.md); RH = [round-01 heuristics](research/round-01-context-heuristics-2026-09-26.md).
- **Code:** extract and situate = their modules' comments.

**Tables**

| Situation | As met | Seen in | Built as |
|---|---|---|---|
| Stacked tables | Two tables in one grid, split by a styled header row; the second header lost, rows bound to the first | sc01 item 1 (HabEx p4) | `stacked` |
| Multi-level headers | "Cameras > UV Channel" cut to "UV" | sc01 | `multilevel`; Word's merged cells |
| Wrapped cells | A cell's second line arrives as an unlabelled row; "Spectrometer resolution" read as counts | sc01 | – |
| Several values in a cell | `1×1 CCD201` (format and model) | the table plan | `multivalue` |
| Components of components | A camera's detector; how to name a part of a part | sc01 | `traps` (AHU-3's supply fan motor); the schematics |
| Dense tables | 20 rows: values from the same row or column, though legible | eye | `dense` |
| Case tables | Operating points (wind speed 14, 15, 16…) as inputs, not properties | s01; NREL p10 | – |
| Subject above the table | Rows that need the lead-in ("Module A", "NREL 5-MW baseline") | r01; levers | the track schedules' lead-in; `spec` |
| Continued across pages | A repeated header, and a false continuation (the next day's schedule of the same form) | store m4 review; extract | `continued` (no false continuation) |
| False tables | Chart gridlines, sheet frames, boxed paragraphs, equation debris; a borderless real table missed | RH; levers | – |
| One-row tables | The only row sent as its own header | levers | – |
| Values taken for numbered items | Rows starting "3.83 -43.73E+6" read as section numbers | query improvement; extract | – |
| Schedules on rotated sheets | Wiring schedules; their lead-in the title block | r03; overall | `rotated` (the door schedule) |
| Pseudo-tables in text | Table-like text in a text chunk; misbinding rose under loose quote matching | r09 | – |
| Quotes spanning cells | Cells joined with "\|", a header read with its value | r09 | – |
| Wide rows | Split by column; a split that separated header from values | extract; robustness baseline | – |
| Units in headers, totals rows, ± columns, min/nominal/max, footnote markers | Planned hazards | the table plan | – |

**Charts**

| Situation | As met | Seen in | Built as |
|---|---|---|---|
| Readings off the axis | Values at 23° and 25° on an axis ending at 20° | r07, r08 | – |
| Trends for readings | Curves that peak and fall described as "increasing" | r08 | – |
| Stacked series and legends | Series swapped; legends split from charts by tiles | r07; r03 | `lcc-enduse`; `legend-caption` |
| Axis labels and multipliers as values | "0" and "1e10" read as stiffness | r09 | tick labels, in every chart (no multipliers) |
| Stacked bars across alternatives | Monthly use for a 2-ton and a 2.5-ton unit; readings selective | sc01 item 2 | `lcc-energy` (two options' bars) |
| Panel labels | "(a) Mass density" taken for a numbered item | levers; extract | – |
| Printed values on grouped bars | Another bar's value; a category code as a value | eye | `lcc-energy` |
| Unfamiliar conventions, signs | A minus sign dropped on re-asking | s01; r01 | – |

**Drawings and sheets**

| Situation | As met | Seen in | Built as |
|---|---|---|---|
| Rotated sheets | Context taken from beside a table; before and after swapped | overall; meta-audit | `rotated` |
| Small dimension text | 2'-9 1/2" read as 2'-3" from an overview | s01; gemma-4 images research | `small`, `vertical` |
| Labels cut at tile edges | "2x4 CEDAR HANDRAILS" as "2x4 CED" | s01; RH | – |
| Close details | Values bound to the wrong module, grid line or detail; titles misattached | r05 | – |
| Title blocks and revision tables | Read as administration only, or switched extraction off; small print in large crops | r05; extract | `lcc-plan`; `lcc-plans` |
| Watermarks, blank tiles | "PRODUCED BY AN AUTODESK STUDENT PRODUCT"; "the image is blank" | levers; extract | – |
| Grid-referenced details | "B4" titles; detail markers that aren't figures | RH; extract | – |
| Single-letter identifiers | Module A merged with Module B | r08 | – |
| Distinct facts sharing a value | Door D1 and window W2, both 1.02 | duplicate-claims research | `lcc-plan` (door sizes repeat) |
| Arrows | Direction reversed (gemma-4: 15 of 118) | eye | the schematics |
| Dense sheets | 100–300 claims per unit; an illegible page thumbnail | overall; r06, r07 | – |
| Fake bold | Text drawn twice, offset | situate | – |

**Schematics and concept diagrams**

| Situation | As met | Seen in | Built as |
|---|---|---|---|
| Facts only in a figure | "Item 5 again ignores the figure as a source": a text unit has none of its page's figure readings | sc01 items 2 and 5 | `figure-only` |
| Text that walks a figure's path, citing it | HabEx Figure 5.5-12: the UV channel's path in the figure and in the paragraph beside it | sc01 item 5 | the schematics' `clean` and `all` |
| Paths as sequences | Readers wrote "DM1 -> DM2 -> Focal plane mask -> Lyot stop" and its fragments as separate claims | sc01 item 9 | scored in every schematic |
| Alternatives on one component | "The focal plane mask can either be an HLC or a VVC" (caption and figure) | sc01 item 9 | `uv-layout` (a field stop's two options) |
| Annotations as locations or conditions | "DM1 (in pupil)", "Lyot stop (in pupil)" | sc01 item 9 | `uv-layout` |
| Stages of a process | Lenslets, pinhole mask, dispersed images, data cube | sc01 item 5 (Figure 5.5-11) | – |
| Movable parts and modes | Double arrows on filters, grism and field stops; a "Guide mode" branch | sc01 item 5 (Figure 5.5-12) | `uv-layout` |

**Prose**

| Situation | As met | Seen in | Built as |
|---|---|---|---|
| Alternatives as conditions | "2 ton unit" and "baseline unit size" as conditions | sc01 item 2 | `traps` |
| Scope as a condition | "across the four mission concepts"; a count bound to the wrong noun | sc01 item 3 | `traps` |
| Context in a caption only | The baseline's size named only in a figure caption | sc01 | `traps` (a table's hall); `legend-caption` |
| Conditions lost or mixed in | "during the cool, martensite phase" dropped; attribute and condition run together | r07; s01 | scored in every document |
| Part stated as the whole | One layer's material as the composition | s01 | – |
| Quantity roles | Clearance read as depth; an elevation as a length | s01 | – |
| Abbreviations defined elsewhere, one entity under two names | "PI = proportional-integral"; "baseline blade-pitch controller" | levers; r03 | `traps` (an abbreviation); the abbreviated revision pair (a revision abbreviating what its earlier one spells out, as its abbreviations list defines) |
| Quote forms | Elided quotes, line-end hyphenation, Unicode variants, paraphrase | r09 | – |
| Requirements, negation, ranges, inequalities | "shall not exceed 60 C" as "is 60 C"; "<= 85 dBA" as 85 dBA | extract (guarded); taxonomy examples | `traps` |

**Layout, furniture and the text layer**

| Situation | As met | Seen in | Built as |
|---|---|---|---|
| Running headers and footers, page numbers | In context in 5 of 8 sampled queries | levers | `furniture` |
| Text cut mid-sentence | "This focus is", "defined in the W" | levers | – |
| Numbered items across pages | "Contest 9 > 9-3 > k. > (iii)"; a heading split over lines | RH; extract | – |
| Several sections on one page | Rules attributed to the next section, which starts lower on the page | s01 | – |
| Boxed headings | Taken for figures | s01 | – |
| Caption traps | "Table 5-1 summarizes…", "Figure 1 shows…", list-of-figures entries, M201 against M-201 | s01; situate | – |
| Equations | Garbled, one character per line | RH | – |
| Scans | Images with little text | situate | `scan`, `scanned-frame` |
| Two columns, no outline | Layouts the samples lack | RH; store m4 review | `two-column` |

**Across pages and documents**

| Situation | As met | Seen in | Built as |
|---|---|---|---|
| A caption on another page | Filter values bound only through a cited caption | r05 | – |
| Missing context, as judges saw it | Surrounding text 68, another page 36, legend 20, table header 16, heading 15, caption 13 | s01 | – |
| Two teams' designs | One design's datum used for the other | s01 | – |
| Units by case | `mW` as megawatts; "ton", kVA against kW, gauge against absolute (planned) | robustness baseline; units plan | – |
| Synonyms across documents | "P-101" against "primary pump" | store plan; retrieval plan | – |
| Superseded values | A hidden superseded sheet; errata (planned) | synthetic workbook | `coaster` (a superseded lift height); Word's tracked changes |

### Backlog

Besides the rows above marked "–", from the plan's milestones:
- **Prose and layout:** harder prose traps, where the context a value needs is far from it (an alternative named only in a figure caption). The short, self-contained sentences of `traps` didn't trip gemma-4.
- **Scans:** noise; text drawn as outlines.
- **Drawing sheets:** details, callouts and sections; the drawing's scale, a fair claim the key lacks (1–4 claims classed misread per sheet).
- **Relations:** more of them, and more systems presenting them in different ways (the owner, 2026-10-01: "We'll need to develop a fairly wide array of 'relations', e.g. component of, within, attached to, etc. and a lot of control docs that present relations in different ways, with varying levels of difficulty."); mechanical assemblies (attached to, mounted on, supported by) are the gap that stands out. Relations aren't compared on revision pairs yet (`comparison.py`).
- **The corpus:** sweeps of one knob at a time against a clean document (font size, density), generated on demand; more seeds; the backup domains (city traffic control, a district heating network, an observatory instrument, a micro-hydro plant, a ferry terminal, a data centre's cooling plant, a ski lift).

## Judging a lever

A lever changes some queries, and gemma-4 answers a changed query anew. A reworded image prompt moves facts both ways even at temperature 0: on 2026-10-14 a rule meant to do nothing ("Read the image carefully.") moved the corpus's relations read right 416 → 444, as far as the arrow rule it was a control for. Totals can't tell that churn from a gain. Arms on the controlled corpus are compared document by document instead:

```bash
python scripts/controlled.py run --variant b62.json --jobs 6    # each arm a named variant, recorded into the archive
python scripts/paired.py b62 --base base --null b64 --target "hedge said"
python scripts/paired.py read/arrow --base read/base --null read/null --null read/null2 --target "relations reversed"
python scripts/paired.py read/lone --base read/base --target "claims right" --all
```

- **Arms are named variants** (`controlled.py run --variant FILE`): a JSON file with `settings` (an overlay on the corpus's: name every compared setting), `only` (the documents' file names as shell patterns, such as `["*.pdf", "views*"]`) and optionally `name`. Its runs go under `benchmarks/runs/controlled/variants/<name>/`, its answers into the archive; `--replay` replays it from the archive at no cost. `paired.py` takes a variant's name or a folder.
- **Arms share answers.** Every arm reads the one archive, so a query a lever leaves alone replays its answer and moves nothing.
- **Frozen code:** run an arm from a git worktree to pin the code while main moves; from a worktree, the archive, the ledger and the variants' runs are the main checkout's, so nothing needs folding back before the worktree goes. On 2026-10-17, b62's comparison (`hedge_rule` against its base and null) replayed as three variants from the archive at no cost, its verdict and numbers as recorded (the null short one document of 145: answers its arm recorded weren't kept).
- **Null arms for a lever that changes many queries.** A null arm changes the same queries to no purpose (a do-nothing rule of the same kind: `visual_rules` for an image rule, `extract_rules` for an instruction).
- **Target and guards, named first.** The target is the error the lever is for (reversed relations for an arrow rule, not relations right); the guard is facts read right.
- **The test:** each document's change, summed; a 90% interval from resampling documents; a two-sided sign-flip p-value (with no effect, either arm is as likely ahead on any document). Documents are the unit, since one query moves several of a document's facts.
- **The verdict** (`bench/paired.judge`): better when the target improves on the base and on every null arm at p < 0.1 and no guard is worse; worse when the target or a guard is worse on the base and on every null; otherwise no different.
- **What it can't see:** a change confined to one or two documents never reaches p < 0.1 (two documents can't go below 0.5), so a lever reaching few documents is judged by inspecting them.

## Synthetic samples

Deliberately messy synthetic spreadsheets (several tables on one sheet, multi-row headers, value/uncertainty pairs, a formula without a cached value, a hidden superseded sheet, a long list that must not be sampled), each with an answer key describing its true layout:

```bash
pip install -e '.[dev]'
python scripts/make_synthetic_samples.py    # writes samples/synthetic/
```

## Local embedding server

For retrieval development, `scripts/embedding_server.sh` runs any of the in-house embedding models locally on CPU (Hugging Face text-embeddings-inference in Docker), bound to localhost, with an OpenAI-compatible `/v1/embeddings` endpoint:

```bash
scripts/embedding_server.sh start                                   # all-MiniLM-L6-v2 on port 8081
scripts/embedding_server.sh start intfloat/multilingual-e5-small 8082
scripts/embedding_server.sh stop
```

Since 2026-10-20 the search uses embeddings where an embedding model is named (`embed_model`, and `embed_url` for an endpoint of its own, such as this one): a search by meaning, and *Claims like this* ([decision 0033](decisions/0033-self-contained-reports-and-their-search.md)). Comparison's candidate retrieval doesn't use them yet; see the [retrieval plan](plans/retrieval-recall-2026-09-23.md).
