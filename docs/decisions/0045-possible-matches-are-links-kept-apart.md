# 0045. Subjects possibly one are links, kept apart; never merged, never chained

- **Status:** Accepted (2026-11-16, retiring the plan it was made in)
- **Source:** the owner, 2026-11-07: "I suspect we might want to support weaker, plausible or tentative matches in some way, for our reports, analysis, etc."; "we probably first need a viable model for "possibly relevant or a match, not sure, investigate further and see if things fit when tied together" instead of all-or-nothing"; on what they feed: "It should feed links and topics for now, until we're confident in our tooling and we have a good idea on how to index with weighted relationships."; on weighing revisions' and proposals' evidence apart and many to one: "I'll accept these recommendations."
- **Builds on:** [0038](0038-revisions-aligned-then-differences-explained.md) (revisions aligned item by item); refined by [0041](0041-evidence-combined-numerically.md) (a link's standing a probability) and [0042](0042-counterparts-only-where-differentiated.md); made in the tentative matches plan (2026-11-07 to 11; retired, see the [plans index](../plans/README.md#retired))

## Context

- Matching was all or nothing: two subjects one group or apart. Alignment's near-ties, the model's dropped answers and the judge's uncertain verdicts were found and thrown away.

## Decision

- **A link between two subjects that stay apart** (`subject["links"]`: the other, the relation, the probability and its parts, the evidence), many to one for a corresponding element (a tower against a tower and a monopile), never an edge chaining A to B to C; firm groups join, one to one.
- **A relation and a standing are two things:** what a link claims (the same item, the corresponding element, a state of it) apart from how well it's evidenced.
- **Every candidate pair's evidence is logged as numbers, non-matches too** (`links.candidates`' features), so weights can be fitted from both; a link's standing is a view of that evidence, recomputed when a report is written.
- **Revisions' and proposals' evidence weighed apart:** a value in common is strong evidence of one item between revisions and coincidence between designs.
- **What links feed:** the links themselves, topics, the linked values shown beside a subject (not merged), link gaps ("if one item"); never the merged index's values or its gaps, never a finding.

## Consequences

- `links.py` (`candidates`, `linked`, `contributions`, `combined`), `indexes.built`'s two passes; the link levers (`link_tests`, `link_read`, `link_gaps`, `linked_values`, `property_links`, `keyed_links`, `unit_kinds`, `other_names_fit`, `link_levels`, `link_fit`), each measured in the [lever index](../reviews/levers.md).
- Weighted edges in the merged index, linked values filling a subject's table, search ranked by a link's weight: the lever index's rows, for when the weights are trusted.
