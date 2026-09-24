# Rate-aware scheduling, section triage and claim quality signals

- **Status:** Planned
- **Depends on:** [projects-and-evidence-store](projects-and-evidence-store-2026-09-23.md) (sections as units of work)

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
- **Honest "unmatched" labels:** a claim is shown as "counterpart may not be extracted yet" while relevant sections on the other side are still pending, and only as "no counterpart found" once they are done.
- **Comparison interleaves with extraction:** a candidate pair is queued for comparison as soon as both claims exist, instead of waiting for all extraction to finish, so preliminary reports contain findings, not just evidence.
- **`status` command:** a plain-text progress summary (per source: sections done, pending and failed; tokens used; estimated time remaining at current limits) that works in any terminal, including inside the sandbox.

### Interactive views (future direction)

A long-running process that users check on from time to time suggests an interactive mode: live preliminary reports, pending alias and keyword questions, and review annotations (see the *Decisions* in [retrieval-recall](retrieval-recall-2026-09-23.md)), all read from the same store.

- **Terminal UI first**, because the primary user's sandbox cannot show a web page: a Python TUI over the store (progress, findings, evidence with quotes, pending questions and answering them). Candidate libraries are `curses` (standard library) or Textual (an optional extra).
- **Local web server later**, for users outside such a sandbox, reusing the same view layer.
- Both are readers of the store plus writers of annotations only; extraction stays in the background process.

### Triage before detailed extraction

Score every section cheaply, then run detailed extraction in score order. Signals, cheapest first:

- **Signals needing no model:** density of numbers and units, tables present, density of vector drawings and images, whether a text layer exists, requirement language (`shall`, `must`).
- **Boilerplate detection:** headers and footers repeated across pages, content identical across files, tables of contents, reference lists. Skip these or de-duplicate them.
- **One model call per section** on its headings plus a text sample, returning the section type (specification, narrative, legal, appendix data), estimated density, keywords, and an **"about" statement**: a few sentences on the section's subject and scope that omit its specific values and decisions. The statement is used for section embeddings and alignment ([retrieval-recall](retrieval-recall-2026-09-23.md)). For very large sections, it is composed from subsections' statements.

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
6. Reviewer feedback (as reusable annotations) feeding calibration.
7. Time-of-day rate-limit rules; token and time estimates in `--plan`.
8. Balanced progress across compared sources; comparison interleaved with extraction; status-stamped preliminary reports; `status` command.
9. (Future) Terminal UI over the store; later a local web server.

## Open questions

- Does the server also limit concurrent requests or queue depth? Adaptive backoff handles it either way, but a known cap avoids wasted 429s.
- `curses` or Textual for the TUI? `curses` adds no dependency; Textual is much quicker to build a usable interface with.

## Decisions (2026-09-23)

- **Throughput limits:** 300k tokens/min in business hours, 500k outside; configurable by time of day, and expected to change.
- **Time budgets:** none. Runs proceed unattended until done or stopped; preliminary reports cover the need to look early.
- **Reviewer feedback:** stored as reusable annotations in the store, exportable and importable (see the *Decisions* in [retrieval-recall](retrieval-recall-2026-09-23.md)).
