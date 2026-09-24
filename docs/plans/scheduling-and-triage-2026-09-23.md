# Rate-aware scheduling, section triage and claim quality signals

- **Status:** Planned
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

1. **Concurrent client:** time-of-day rate-limit rules, adaptive backoff, a modest concurrency cap; tests against a stub server that simulates latency and 429s; token and time estimates in `--plan`; progress bars, heartbeats and configurable verbosity.
2. **Persistent task queue and section queue:** extraction restructured into discrete, persisted tasks (moved here from the store plan, since resume already works by cache replay); fair share across sections and across compared sources; `not_reached` coverage status.
3. **Triage without the model:** cheap signals and boilerplate detection. Use drawing sets as a test case: table detection there finds mostly drawing geometry, and about half the rows repeat across sheets (title blocks, legends; see the [store milestone 4 review](../reviews/store-m4-pdf-sections-2026-09-24.md)).
4. **Model triage per section:** type, density, keywords and the "about" statement.
5. **Epistemic status:** prompts ask for basis, uncertainty, context and role (filling the schema v2 fields); skeptical instructions; the basis veto in comparison. A deliberate prompt-version change.
6. **Preliminary reports:** status stamps, honest gap labels, comparison interleaved with extraction, the `status` command.
7. **Claim quality signals** with sorting and filtering in reports.
8. **Reviewer feedback:** review controls in reports and `import-reviews` (the first capture path for annotations), feeding calibration.

## Open questions

None currently.

## Decisions (2026-09-23)

- **Context window:** the gemma-4 deployment serves 262,144 tokens; configure `context_tokens` to match. Extraction chunk sizes (`text_bytes`, tile size) are separate settings and stay small so each extraction stays focused. Large requests are for section-level work (triage, "about" statements) and criterion-level comparison. How much of a section triage reads is part of the extraction interpreter, since it shapes what the model sees.
- **Throughput limits:** 300k tokens/min in business hours, 500k outside; configurable by time of day, and expected to change.
- **Concurrent requests:** assume the server caps them. Use a modest, configurable concurrency limit (single digits by default) and let adaptive backoff find the working level, leaving room for the user's other tools on the same server. Tune the default from real runs.
- **Time budgets:** none. Runs proceed unattended until done or stopped; preliminary reports cover the need to look early.
- **Reviewer feedback:** stored as reusable annotations in the store, exportable and importable (see [sources-and-evidence-store](sources-and-evidence-store-2026-09-23.md) (*Annotations*)).
