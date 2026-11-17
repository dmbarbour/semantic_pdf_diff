# 0047. What's learnt about claims is a log of commentary beside them; claims never change

- **Status:** Accepted (2026-11-17, retiring the plan it was made in)
- **Source:** the owner, 2026-10-28: "I think we shouldn't 'change' claims as in any form of mutability. We could annotate them, have a log or graph of commentary - associations, conflicts, corroborations, re-situation or re-contextualization, etc.. Everything should be traceable, monotonic, and (assuming the answer cache) reproducible."; the same day: "we probably need to prioritize development of a second pass (or an entire refinement, situating, contextualizing strategy) where claims are analyzed in context [...] A lot of comparisons don't make sense because they're compared without enough context."; 2026-10-31: "Agree with all second-pass recommendations."; "Yes, turn `second_pass` on."; 2026-11-06, on tensions: "We'll need to also look for qualitative inconsistencies, with levels of suspicion. [...] this is where a model with some domain knowledge is likely necessary."
- **Builds on:** [0005](0005-union-provenance.md) (one claim per fact, every sighting kept), [0039](0039-runs-paced-by-throughput-and-situated-after-extraction.md) (situating changes no claim); made in [single-document analysis](../research/single-document-analysis-measured-2026-11-17.md) (milestones 3 to 6, design questions 1, 2, 4 and 5)

## Context

- Claims were compared without what else their source says of their subject, and mending them in place would lose what was read.

## Decision

- **Claims never change.** What a later pass learns (associations, conflicts, corroborations, inferences, gaps, re-reads, looks) is an entry in a log beside them, traceable to its pass, its request and the claims and quotes it rests on; entries are only added (a dispute is a new entry); views read the log, and the answers cache reproduces it.
- **Entries are held as ours and checked as they're written:** the claims an entry cites among those it was given, its quotes found; one failing is dropped and counted. A re-read is shown beside its claim, never in its place.
- **The second pass: one request a subject,** over its dossier (its claims, their quotes, records and sections' abouts), text first; claims it doubts are read again from their place; a kind's items are also read together.
- **Inconsistencies need the dossier:** candidates found by code within a subject, settled with it; arithmetic done by code; values differing by condition or by rounding aren't inconsistent. Tensions (claims hard to hold together on engineering grounds, with a level of suspicion) are a request of their own, a lever, off.
- **A stage after situating:** on in analyses; in comparisons only once measured (its notes shown to the judge, `judge_notes`, measured within noise: off).

## Consequences

- `dossiers.py`, `tensions.py`; the report's notes beside claims, its Inconsistencies and Suspects views.
