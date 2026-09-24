# Rate-aware scheduling, section triage and claim quality signals

- **Status:** Planned
- **Depends on:** [projects-and-evidence-store](projects-and-evidence-store-2026-09-23.md) (sections as units of work)

## Context

We run an in-house gemma-4 server. The real constraint is **tokens per minute**, not a total call budget, so `max_calls` is the wrong primary control. File sizes vary widely: one group may submit a single very large file, another several small ones. Per-file budgets therefore don't work; work has to be divided into logical **sections**.

Today calls are strictly sequential, which will not scale to folders with hundreds of files.

## Goals

1. Keep the server busy up to a configured throughput without overloading it.
2. Make the most useful results arrive first, so a run that is stopped early is still valuable, and the coverage record honestly shows what wasn't reached.
3. Treat large and small files fairly.
4. Attach transparent quality signals to claims for sorting and filtering.

## Design

### Scheduler

- **Rate-aware concurrency:** a limit on tokens per minute and requests per minute, fed by the `usage` numbers the client already collects. Back off when latency rises or on 429/503, and honour `Retry-After` (already implemented). `max_calls` remains only as a safety stop.
- **Fair share across sections:** a priority queue over sections from *all* sources, so a 900-page file doesn't starve ten 20-page files. Priority comes from triage (below).
- **Stop any time, resume later:** results are persisted per task (the store), and the coverage record marks unreached sections as `not_reached`, distinct from `failed`.

### Triage before detailed extraction

Score every section cheaply, then run detailed extraction in score order. Signals, cheapest first:

- **Signals needing no model:** density of numbers and units, tables present, density of vector drawings and images, whether a text layer exists, requirement language (`shall`, `must`).
- **Boilerplate detection:** headers and footers repeated across pages, content identical across files, tables of contents, reference lists. Skip these or de-duplicate them.
- **One model call per section** on its headings plus a text sample, returning the section type (specification, narrative, legal, appendix data) and estimated density.

Triage decides *order*, never *exclusion*. Low-scoring sections are still extracted if throughput allows, and are never silently dropped.

### Claim quality signals

Keep three separate axes. They answer different questions, and mixing them into one opaque score would hide which one drives a ranking.

| Axis | Question | Signals |
|---|---|---|
| **Reliability** | Is the extraction right? | native vs visual source, `quote_verified`, native and visual passes agreeing, `approximate`, retry depth, model confidence (lowest weight; uncalibrated) |
| **Specificity** | Is it a usable engineering fact? | number plus unit, stated conditions, specific entity (`P-101`) vs generic ("the system"), requirement vs capability vs hedged wording |
| **Salience** | Does the project treat it as important? | how often the entity is referenced across the project, section type (executive summary vs appendix), repetition across files |

Rules:

- Use the signals for **scheduling, sorting and filtering**. Show each component in the report. Never let them hide evidence.
- Salience is the riskiest axis: it is domain-specific, and it is close to the "importance ranking" the README disclaims. Label it clearly.
- Calibrate later with real feedback: if reviewers can mark findings "useful" or "wrong" in the report, those labels can tune the weights instead of intuition.

## Milestones

1. Concurrent client with rate limiting and adaptive backoff; tests against a stub server that simulates latency and 429s.
2. Section priority queue with fair share; `not_reached` coverage status.
3. Triage signals that need no model, plus boilerplate detection.
4. Model triage call per section.
5. Claim quality signals on evidence; sorting and filtering in the report.
6. Optional reviewer feedback in the report, feeding calibration.

## Open questions

- Which throughput limits does the gemma-4 deployment actually expose (tokens/min, concurrent requests, queue depth)?
- Should a run take a time budget ("best results within 30 minutes") as well as throughput limits?
- Where would reviewer feedback be stored so it survives report regeneration?
