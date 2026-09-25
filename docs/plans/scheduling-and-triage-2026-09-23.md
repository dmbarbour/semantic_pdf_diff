# Rate-aware scheduling, section triage and claim quality signals

- **Status:** Active (2026-09-24)
- **Depends on:** [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (sections as units of work)

## Context

We run an in-house gemma-4 server. The real constraint is **tokens per minute**, not a total call budget, so `max_calls` is the wrong primary control. Current limits (2026-09-23, subject to change): **300k tokens/min during business hours, 500k outside them**. Runs are meant to proceed unattended: the typical user starts a run and comes back later, rather than watching it. File sizes vary widely: one group may submit a single very large file, another several small ones. Per-file budgets therefore don't work; work has to be divided into logical **sections**.

Today calls are strictly sequential, which will not scale to folders with hundreds of files.

## Goals

1. Keep the server busy up to a configured throughput without overloading it.
2. Make the most useful results arrive first, so a run that is stopped early is still valuable, and the coverage record honestly shows what wasn't reached.
3. Treat large and small files fairly.
4. Attach transparent quality signals to claims for sorting and filtering.

## Design

### Scheduler

- **Rate-aware concurrency:** a limit on tokens per minute (and optionally requests per minute), fed by the `usage` numbers the client already collects. Back off when latency rises or on 429/503, and honour `Retry-After` (already implemented). `max_calls` remains only as a safety stop.
- **Limits by time of day:** limits change with business hours and may change over time, so they are configuration, not code. For example:

  ```json
  "rate_limits": [
    {"days": "mon-fri", "hours": "08:00-18:00", "tokens_per_minute": 300000},
    {"tokens_per_minute": 500000}
  ]
  ```

  The first matching rule applies (local time). Configured limits are ceilings; adaptive backoff still reacts to the server's actual responses, which covers limits changing without notice. Rate limits don't affect output, so they are not part of the store's interpreter.
- **No time budgets.** Runs go until done, or until the user stops them; stopping is always safe (see resume below).
- **Estimates in `--plan`:** expected calls, tokens and wall-clock time under the configured limits. For scale: at roughly 2–5k tokens per call, 300k tokens/min allows about 60–150 calls per minute, so the ~900 visual tasks of the NREL 5 MW vs IEA 15 MW sample pair take roughly 5–15 minutes before text and comparison calls. (Per-call tokens depend on how the server counts image tokens; calibrate from real `usage` numbers.)
- **Fair share across sections:** a priority queue over sections from *all* sources, so a 900-page file doesn't starve ten 20-page files. Priority comes from triage (below).
- **Stop any time, resume later:** results are persisted per task (the store), and the coverage record marks unreached sections as `not_reached`, distinct from `failed`.

### Progress and preliminary reports

Users can generate and inspect reports **while a run is still going**. That needs work ordered so partial results mean something:

- **Every report is stamped with its status:** what fraction of each source and section has been extracted, which comparisons are complete, partial or not started, and when the snapshot was taken. Reports read the store while the run writes to it (SQLite WAL allows this).
- **Balance progress across the sources being compared.** If source A is fully extracted and source B only 10%, most of A's claims look "unmatched" merely because B's counterpart hasn't been read yet. The scheduler advances compared sources together (fair share across sources as well as sections), and prefers sections that align with already-extracted sections on the other side.
- **Honest gap labels:** a claim is shown as "counterpart may not be extracted yet" (revisions, `check`), or a criterion cell as "not yet reached" (proposals), while relevant sections are still pending; only once they are done does it become "no counterpart found" or "no evidence found".
- **Comparison interleaves with extraction:** in claim-level modes, a candidate pair is queued as soon as both claims exist. In criteria-first proposal mode, each source is mapped to criteria as its sections complete, and a criterion's cross-source description is produced (and marked provisional) once every source's relevant sections are done or the user asks for a preliminary report. Either way, preliminary reports contain findings, not just evidence.
- **Progress display and logging,** so users can see things moving:
  - **On a terminal:** `tqdm` progress bars per stage and source (tasks done, tokens per minute, estimated time remaining).
  - **Otherwise** (redirected output, background jobs, logs): periodic **heartbeat** lines with the same numbers, at a configurable interval.
  - **Verbosity:** `-q`, the default, `-v` and `-vv`, plus `--log-file`. Built on Python's `logging`, so levels and destinations are ordinary configuration. `-vv` includes per-request details, never credentials.
- **`status` command:** a plain-text progress summary (per source: sections done, pending and failed; tokens used; estimated time remaining at current limits) that works in any terminal, including inside the sandbox.

### Triage before detailed extraction

Score every section cheaply, then run detailed extraction in score order. Signals, cheapest first:

- **Signals needing no model:** density of numbers and units, tables present, density of vector drawings and images, whether a text layer exists, requirement language (`shall`, `must`).
- **Boilerplate detection:** headers and footers repeated across pages, content identical across files, tables of contents, reference lists. Skip these or de-duplicate them.
- **One model call per section** on its headings and text (the whole section when it fits the context budget, which with the deployment's 262,144-token window is nearly always; a representative sample otherwise), returning the section type (specification, narrative, legal, appendix data), estimated density, keywords, and an **"about" statement**: a few sentences on the section's subject and scope that omit its specific values and decisions. The statement is used for section embeddings and alignment ([retrieval-recall](retrieval-recall-2026-09-23.md)). Only sections too large for one request compose it from subsections' statements.

Triage decides *order*, never *exclusion*. Low-scoring sections are still extracted if throughput allows, and are never silently dropped.

### Situating stage (model triage, decided 2026-09-25)

Extraction is organized by **medium** (text groups, table rows, image tiles), but meaning is organized by **reference**: a figure is explained by prose elsewhere, and a drawing-only section by its sheet title, title block and callouts. Situating is therefore **its own stage after extraction**. It consumes what extraction produced (claims from every pass, section text, sections, signals), plus a few images where text is thin.

1. **Figures and references, found mechanically:** image blocks and dense vector-drawing clusters, paired with nearby captions ("Figure 3: …", "Fig. 3", "Table 2", "Sheet M-101"). A drawing sheet (a page with a title block, or many vector paths per text character, and no captions) is one figure, labelled from its title block (sheet number and title). A regex over text blocks finds the paragraphs that cite figures ("as shown in Figure 3", "refer to M-101"), building a reference graph (prose → figure) with exact provenance. Visual claims inside a figure's region are attached to it.
2. **Figure "about", first (bottom-up):** one request for *every* figure, labelled or not (decided 2026-09-25: a figure is situated by where it sits as much as by what cites it). It gets the figure's location (page, position, section path), caption or title block, the text before and after it (a sheet's own text for sheets), the whole paragraphs citing it with their sections, its visual claims and an image. It returns what the figure depicts and why it's there, plus any label or title printed in the figure itself. Labels read this way resolve outstanding references; a figure that gains citations is asked once more, with them.
3. **Section "about", from everything:** heading path, full text (whole sections fit the 262,144-token context), claims from all passes, and the figure "abouts". Diagram-heavy sections with little text (per their signals, e.g. drawing sheets) add a few low-resolution page overviews (a small cap per request), the sheet title, title-block rows and visual claims. The request returns type, estimated density, keywords and the "about" statement.
4. **Situating context is linked, not rewritten:** a claim can gain links to the prose or figure that explains it, recorded as annotations. Claims themselves are never changed after extraction.

It has **its own bound role** (`triage`): changing its model or prompts clears only situating results on `--reset`. Storage: sections gain `about`, type and keywords; a `situation` row per content holds its figures (caption, bounding box, references, "about", linked claims), unresolved references and request issues. (Built as one row per content rather than a figure table: figures are always read and replaced together.) `--plan` counts section and figure requests separately. The one entanglement a single bottom-up pass doesn't resolve is prose whose meaning depends on a diagram; its own claims come from text, so it's no worse than before.

#### Quality checks

Mechanical checks run on every run and are reported, never silently applied:

- **Reference resolution:** the share of "Figure N" / "Sheet X" references that resolve to a detected figure. Unresolved references point to missed figures, a recall signal that needs no labels. So does the share of detected figures with no caption or reference.
- **"About" statements omit values:** numbers with units in an "about" statement are flagged, since aboutness should leave out specific values and decisions.
- **Grounding:** the key terms of a figure's or section's "about" should appear in its caption, referencing prose, claims or text. Low overlap flags a possible hallucination.
- **Shape:** length bounds; every section with extracted claims gets an "about".

Human checks: reports offer a small sample of figure and section "abouts" for review (usefulness and correctness as reusable annotations). The [evaluation benchmarks](evaluation-benchmarks-2026-09-23.md) label figure–reference links and rate "abouts" against the public corpus.

#### Alternatives to evaluate later

Measured against the first pass above, on the evaluation benchmarks, not built speculatively:

- **Diagrams as structured text:** the model transcribes a diagram into a graph (nodes, edges, labels) or into Mermaid/SVG that would render a semantically similar diagram. Claims could then be derived mechanically from edges, and topologies compared across sources. Promising for block diagrams and P&IDs, poor for charts and geometric drawings. A render-and-compare check by the same model isn't independent evidence.
- **Vector geometry for connectivity:** in vector PDFs, lines, arrowheads and label positions (`get_drawings`) could recover connections mechanically, with the model only resolving ambiguities.
- **Composite images:** render the diagram crop together with its associated text (caption, referencing sentences, section heading) as one image, in case the model binds text to image regions better inside the image than across the prompt. Also useful as a single view for human reviewers in reports.
- **Sections first, then figures:** gives figures more context at the cost of a second round of requests.
- **Mixed mode (escalate on doubt):** situate once everywhere, cheaply. Where confidence is low or a quality check flags a result (unresolved references, values in an "about", poor grounding), run additional independent passes (e.g. a different context bundle, representation or ordering from the alternatives above) and keep what they agree on. Disagreement is itself reported. The extra cost goes only where it's needed, and agreement between variants is a better signal than the model's self-reported confidence. The same pattern could later apply to extraction of hard regions.

Where these would integrate is open. Figure-level situating (step 2) is the natural place for the first three.

### Claim quality signals

Keep three separate axes. They answer different questions, and mixing them into one opaque score would hide which one drives a ranking.

| Axis | Question | Signals |
|---|---|---|
| **Reliability** | Is the extraction right? | native vs visual source, `quote_verified`, native and visual passes agreeing, `approximate`, retry depth, model confidence (lowest weight; uncalibrated) |
| **Specificity** | Is it a usable engineering fact? | number plus unit, stated conditions, specific entity (`P-101`) vs generic ("the system"), requirement vs capability vs hedged wording |
| **Salience** | Does the source treat it as important? | how often the entity is referenced across the source, section type (executive summary vs appendix), repetition across files |

Rules:

- Use the signals for **scheduling, sorting and filtering**. Show each component in the report. Never let them hide evidence.
- Salience is the riskiest axis: it is domain-specific, and it is close to the "importance ranking" the README disclaims. Label it clearly.
- Calibrate later with real feedback: if reviewers can mark findings "useful" or "wrong" in the report, those labels can tune the weights instead of intuition.
- Derivation (how directly a claim was obtained) is shown alongside these axes but is not one of them: a direct read is not automatically more reliable than a model extraction.

### Epistemic status and skeptical prompting

Whatever its derivation, a claim can be a measurement, a calculation, a simulation result, a projection, a requirement, a target or an unsupported assertion, and it may or may not state its uncertainty. People mislead with statistics and graphs all the time. So:

- **Record the basis of each claim:** extraction returns `basis` (measured / calculated / simulated / projected / required / targeted / asserted / unknown) and any stated uncertainty (interval, tolerance or "none given"). This extends the current prompt, which already distinguishes requirements from proposed capabilities. It applies to every format, including deterministic spreadsheet claims, whose basis may come from headers, notes or the surrounding document.
- **Comparison respects basis the way it respects conditions:** a measured value and a projected value are not a contradiction. A basis mismatch vetoes a confident *different* or *equivalent* judgment, just as unmatched conditions do today.
- **Lead the model to be suspicious**, since judgment quality is initially limited by gemma-4. Instructions ask it to question its own interpretation of columns and labels, and to notice presentation that can mislead: truncated or log axes, missing error bars, selective ranges, projections presented as results, totals that don't add up, and claims that don't fit together. Suspicions are recorded as issues on the claim or finding and shown in reports; they never silently drop evidence.
- These prompt changes are interpreter changes (prompt versions), so they are made deliberately and versioned.

## Milestones

0. ✅ *Done 2026-09-24 (`6a2b622`).* **Prerequisite: union provenance** (see the store plan's *Decisions*), so results don't depend on which task finishes first.
1. ✅ *Done 2026-09-24 (`1a3d460`, `456e6a9`, and progress/logging; see the [review](../reviews/scheduling-m1-concurrency-2026-09-24.md)).* **Merged with milestone 2 (decided 2026-09-24; see the [store completion review](../reviews/store-complete-2026-09-24.md)): an in-memory task queue run by worker threads with a single store writer, plus** the concurrent client: time-of-day rate-limit rules, adaptive backoff, a modest concurrency cap; tests against a stub server that simulates latency and 429s; token and time estimates in `--plan`; progress bars, heartbeats and configurable verbosity.
2. ◐ *Partly done 2026-09-24: fair share across compared sources (pages fed round-robin, one queue for all their PDFs) and `not_reached` for work cut off by `max_calls`. Section priorities wait for triage (milestones 3–4); persisting the queue waits for preliminary reports (milestone 6).* **Persisting the task queue and the section queue** (the queue itself arrives with milestone 1): tasks persisted for progress reporting; fair share across sections and across compared sources; `not_reached` coverage status.
3. ✅ *Done 2026-09-24 (see the [review](../reviews/scheduling-m3-triage-signals-2026-09-24.md)): per-section signals, and repeated table rows followed.* **Triage without the model:** cheap signals and boilerplate detection. Use drawing sets as a test case: table detection there finds mostly drawing geometry, and about half the rows repeat across sheets (title blocks, legends; see the [store milestone 4 review](../reviews/store-m4-pdf-sections-2026-09-24.md)).
4. ✅ *Done 2026-09-25 (`34ac923`, `0988581` and the quality checks; see the [review](../reviews/scheduling-m4-situating-2026-09-25.md)). The human-review sample of "abouts" moves to milestone 8 (reviewer feedback).* **Situating stage** (see *Situating stage* above): figures and references found mechanically; figure then section "abouts" as a separate stage after extraction, with its own bound `triage` role; mechanical quality checks in every report.
5. **Epistemic status:** prompts ask for basis, uncertainty, context and role (filling the schema v2 fields); skeptical instructions; the basis veto in comparison. A deliberate prompt-version change.
6. **Preliminary reports:** status stamps, honest gap labels, comparison interleaved with extraction, the `status` command.
7. **Claim quality signals** with sorting and filtering in reports.
8. **Reviewer feedback:** review controls in reports and `import-reviews` (the first capture path for annotations), feeding calibration.

## Open questions

None currently.

## Decisions (2026-09-23)

- **Context window:** the gemma-4 deployment serves 262,144 tokens; configure `context_tokens` to match. Extraction chunk sizes (`text_bytes`, tile size) are separate settings and stay small so each extraction stays focused. Large requests are for section-level work (triage, "about" statements) and criterion-level comparison. How much of a section triage reads is part of the extraction interpreter, since it shapes what the model sees.
- **Throughput limits:** 300k tokens/min in business hours, 500k outside; configurable by time of day, and expected to change.
- **Repeated boilerplate (2026-09-24): extract once, on strong evidence only.** A block is treated as repeated only if its source data is *exactly* identical (digits never normalized), in the same position, on at least 3 pages of the same content. The first occurrence is extracted; each repeat gets a coverage row ("identical to task X on page N, not re-sent") and occurrences of the first's claims in its own section. `dedupe_repeated` (on by default) turns it off.
  - **Amended by evidence: table rows only.** Measured on the samples, isolating repeated *text* blocks always added calls (+14% on the rules PDF, +6% on NREL 5 MW, and it cut the drawing set's savings from 45% to 32%): grouped text carries a repeated header at no extra call, while isolating it adds one. Table rows are one call each, so following them saves 45% of calls on `dc_cd.pdf` and costs nothing elsewhere. Text is never de-duplicated, which also removes any risk to footnotes. Rows follow from their third sighting; image tiles are always extracted. See the [triage review](../reviews/scheduling-m3-triage-signals-2026-09-24.md).
- **Section ordering (2026-09-24):** deferred to preliminary reports (milestone 6), where order first has value; triage (milestone 3) stores per-section signals for it. See the [fair-share review](../reviews/scheduling-m2-fair-share-2026-09-24.md).
- **`tqdm`** is accepted as a dependency for progress bars.
- **Concurrent requests:** assume the server caps them. Use a modest, configurable concurrency limit (single digits by default) and let adaptive backoff find the working level, leaving room for the user's other tools on the same server. Tune the default from real runs.
- **Time budgets:** none. Runs proceed unattended until done or stopped; preliminary reports cover the need to look early.
- **Reviewer feedback:** stored as reusable annotations in the store, exportable and importable (see [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (*Annotations*)).
