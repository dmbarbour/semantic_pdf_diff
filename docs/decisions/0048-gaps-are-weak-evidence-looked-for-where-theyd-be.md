# 0048. Gaps are weak evidence, looked for where they'd be, never findings

- **Status:** Accepted (2026-11-17, retiring the plan it was made in)
- **Source:** the owner, 2026-10-28: "Gaps in claims seems like a difficult target because we don't know where we should be looking for what we don't know without sufficient context."; answering where gaps reach: "Not gaps that a page points to, just gaps in general. [...] there are still gaps in what we know about it that a different proposal might specify in its claims about the corresponding elements. That's the clearest sort of gap [...] knowing or identifying what we don't know requires reading between the lines and also identifying what can reasonably be inferred from multiple claims in context."; 2026-11-07: "All four recommendations look good as a start."; "Go ahead and turn on `look_gaps`."
- **Builds on:** [0047](0047-commentary-logged-beside-claims-that-never-change.md), [0046](0046-one-source-analyzed-with-indexes-of-what-was-read.md); made in [single-document analysis](../research/single-document-analysis-measured-2026-11-17.md) (milestones 5 and 7, design question 3)

## Decision

- **Gaps in general, by kind:** a property another source gives for the same subject (the clearest); one a subject's siblings give; one declared and not given ("see Table 5", "TBD", an empty cell in a filled table); one its dossier suggests. A checklist of what a kind of document should give stays with [criteria-first comparison](../plans/n-way-comparison-2026-09-23.md).
- **Weak, said so, never a finding:** each gap says where it was expected and why, and which state of the subject it's about; it isn't proof of absence nor counted against the document.
- **An inference isn't a gap:** a value other claims imply is an entry in the log, citing them; that the document doesn't state it is weaker still.
- **Looked for before it's reported** (`look_gaps`, a default since 2026-11-07): where the property would be, the source asked whether it gives it there.
- **Links' gaps** ("if one item") follow [0045](0045-possible-matches-are-links-kept-apart.md).

## Consequences

- `indexes.py`'s gaps, `crossmatch.py`'s looks; the report's gaps, `index/gaps.csv`.
