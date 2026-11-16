# 0042. Between two designs, counterparts only where they're told apart by more than numbering

- **Status:** Accepted (2026-11-16)
- **Source:** the owner, 2026-11-12: "whether we can compare them one vs. one depends on if they are meaningfully differentiated. If it's just three fungible pumps coordinating in a shared role, then how would it make sense to match them one to one?"; 2026-11-13: "I don't see how revisions of different things could be considered counterparts in general. Different designs or designers frequently have different numbering schema for revisions. Revision numbers are relevant for situating two versions of the same thing."; and on where a component sits, 2026-11-11: "I was thinking more about where a component is used in a system. Not where the section discussing a component appears in a document discussing the component."
- **Builds on:** [0041](0041-evidence-combined-numerically.md); [the place review](../research/place-review-2026-11-11.md), [the system use review](../research/system-use-review-2026-11-12.md), [evidence combined numerically](../research/evidence-combination-measured-2026-11-16.md) (milestone 10)

## Context

- The model's name groups paired two designs' raw water pumps by order (P-101A with IP-1) and the index made those pairs keys; revisions, sheets and grid lines of two houses' drawings joined by their numbers; generic names ("sheet", "detail", "equipment") joined as keys.

## Decision

- **A document's numbering identifies nothing across designs:** tags of two series, numbered document parts ("revision 3", "component 6", "Sheet M-101") and their spelling, the model's match and the judge's pairings between them weigh nothing; numbers situate versions of one thing (revisions), not counterparts.
- **Interchangeable units are compared as sets:** a source's units of one tag series named alike are a bank; two designs' banks are linked as sets, their values compared as ranges, never unit to unit.
- **A unit told apart is matched as itself:** a unit named otherwise or marked so in its claims (a jockey pump; low or minimum flow; a season) stands apart from its bank and may be paired one to one; duty, standby, lead and lag are a bank's arrangement, not a unit's identity.
- **Names that name no thing aren't keys:** a document's parts and category nouns alone ("sheet", "HVAC equipment") join nothing by name.
- **Where a component is used is its system, not its section:** evidence of use reads what it does and handles (function) and where it sits in its system (integration); a section's place in a document is a weak signal at most (the owner: "especially when the sections are naming components or subsystems").

## Consequences

- `align.series`, `align.placeholder`, `align.generic` (with `DOCUMENT_PARTS`, `CATEGORY_NOUNS`), `links.banks`, `links.sets`, `links.DIFFERENTIATES`; index.md's "Sets".
- The lab scores a bank's units matched across designs as right ("comparable"), and the link panel is told that a document's numbering makes nothing counterparts.
