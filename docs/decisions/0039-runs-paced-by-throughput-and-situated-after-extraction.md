# 0039. Runs are paced by the server's throughput, fair across sources, and situated after extraction

- **Status:** Accepted (2026-10-21)
- **Source:** the [scheduling and triage plan](../plans/scheduling-and-triage-2026-09-23.md) (its decisions, 2026-09-23 to 2026-10-14; milestones 1 to 4) and its reviews: [concurrency](../plans/README.md#retired), fair share, triage signals, situating

## Context

Model calls were strictly sequential, which wouldn't scale to folders of hundreds of files. The in-house gemma-4 server's constraint is tokens per minute (300k in business hours, 500k outside, as of 2026-09-23, expected to change), not a total call budget. Runs are meant to proceed unattended, and file sizes vary widely, so per-file budgets don't work. A figure's meaning sits as much in where it is and the prose citing it as in the tile that reads it.

## Decision

- **Throughput, not budgets:**
  - Requests run on worker threads with a single store writer, at most `concurrency` in flight (4 by default). An adaptive gate halves that on a 429 or 503, or on latency over three times its baseline, and grows it by one after 8 successes. `Retry-After` is honoured (up to 60 s).
  - **`rate_limits`:** time-of-day rules in configuration, not code; the first matching rule applies, in local time, with `tokens_per_minute` and/or `requests_per_minute`. They're ceilings: the gate covers limits that change without notice.
  - **No time budgets:** a run goes until done or stopped, and stopping is always safe ([0003](0003-sqlite-evidence-store.md)). `max_calls` is a safety stop; work a stop cuts off is `not_reached`, apart from `failed`.
  - These are endpoint settings: they never change what a run writes ([0011](0011-settings-classified-by-effect.md), [0030](0030-only-answers-decide-what-a-run-writes.md)).
- **Fair share across sources:** one queue per source, pages fed round-robin across them, so compared sources advance together and one large file doesn't starve many small ones.
- **Repeated boilerplate read once, on strong evidence only:**
  - a table row exactly identical (digits never normalized), in the same table position, follows its first reading from its third sighting in one content: its claims gain occurrences, and its coverage row names the task it repeats (`dedupe_repeated`, a default)
  - a text block said exactly, in the same place, on two earlier pages leaves the page's text tasks (`repeated_text: first`, a default since 2026-10-14; the owner: "Apply the recommended defaults"); one that differs by a digit is always sent
  - image tiles are always read
- **Triage orders, never excludes:** each section's cheap signals (numbers, units, requirement words, tables, images, drawings, characters) are stored with it. Ordering by them waits for a use.
- **Situating is a stage of its own, after extraction** (`situate`, a default; `--no-situate`), for PDFs:
  - figures found mechanically (image blocks, dense vector-drawing clusters, captions; a drawing sheet is one figure, labelled from its title block), with the paragraphs citing them and the claims inside them
  - **every figure gets a request,** labelled or not (2026-09-25, on the owner's feedback that location situates a figure and some labels must be read from the figure itself): location, caption or title block, the text around it, citing paragraphs, its claims and an image; it returns what the figure depicts, why it's there and any label printed in it. New labels resolve references, and a figure that gains citations is asked once more.
  - then a request per section (heading path, text, claims, its figures' "abouts", overviews of scanned pages) for its type, density, keywords and a value-free "about"
  - **linked, never rewritten:** claims are never changed after extraction
  - its own bound role, `triage` ([0004](0004-store-bound-to-its-interpreters.md))
  - **mechanical checks reported, never applied:** references resolved, labelled figures never cited, values in an "about", "about" terms missing from their material, lengths, sections with claims and no "about"

## Consequences

- Concurrent and sequential runs write the same evidence ([0005](0005-union-provenance.md)); changing throughput settings never needs `--reset`.
- **Repeats:** following table rows saved 45% of calls on `dc_cd.pdf` (5,537 → 3,053) and cost nothing elsewhere. Isolating repeated text in tasks of its own always added calls (+14% on the rules PDF), so text leaves tasks instead (the slices' drawing sets: text tasks 205 → 188).
- **Situating** costs a request per figure and per section (stub counts, 2026-09-25: 290 on `dc_cd.pdf`'s 143 sheets, 86 on the NREL report; references resolved there 57 of 60 and 35 of 39).
- **Its readings serve other stages:** a sheet's title block is [claim context](../plans/claim-context-2026-10-14.md)'s `sheet` record; the "abouts" are meant as subject and scope records there, and for [retrieval recall](../plans/retrieval-recall-2026-09-23.md)'s section alignment.
- **Not built:** preliminary reports, section order and a persisted queue (*Interactive views*); claim quality signals (*Runtime quality spot checks*); reviewer feedback (*Reviewer feedback*); the epistemic basis and skeptical prompting (claim context).
