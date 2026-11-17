# 0051. Summaries cite claims, are checked by code, and are never claims

- **Status:** Accepted (2026-11-17, retiring the plan it was made in)
- **Source:** the owner, 2026-11-02, naming cited summaries among "the most valuable to me in the short term"; 2026-11-06, on the design: "This seems like a good design for milestone 4."; "I'd like summaries per subject and topic, too."; "Claims only, but let's not discard the other as a lever. We might want to combine related sentences from multiple sources to gain context when composing claims? Something like that."; on a sentence failing its check: "We'll go with the recommendation."; in the export: "Yes, with provenance."; 2026-11-07: "Go ahead and turn on summaries."
- **Builds on:** [0047](0047-commentary-logged-beside-claims-that-never-change.md), [0050](0050-outputs-written-for-people-and-a-rag-ingest.md); made in [single-source outputs](../research/single-source-outputs-measured-2026-11-17.md) (milestone 4)

## Decision

- **Five kinds:** a section's, a file's (from its sections'), the source's (from its files'), a subject's and a topic's; sections', files' and the source's a default in analyses (`summaries`).
- **From claims only:** each claim given with its id, item, property, value, conditions, quote and place; a summary of summaries is given theirs with the claims they cite, so every sentence cites claims, never a summary.
- **Checked by code, each sentence:** it cites one claim or more among those given, and each number it states is a cited claim's; a sentence failing is kept and marked, never corrected or dropped, and the failures are counted.
- **An output, never a claim:** labelled generated and checked, each citation a link to its claim, in the report's Summaries view and the export with its provenance; asked through the answers cache, it changes no claim.

## Consequences

- `summaries.py`; summaries from a section's text too stay a lever idea.
