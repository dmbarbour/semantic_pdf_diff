# 0049. A glossary is metadata beside the claims, each definition holding as far as it reaches

- **Status:** Accepted (2026-11-17, retiring the plan it was made in)
- **Source:** the owner, 2026-10-15: "Seems we should consider developing a glossary for abbreviations, framings, etc.. not as a set of claims, but as metadata for reports, comparisons, and comprehending claims in context."; 2026-10-30: "Please proceed with the glossary."; "Related, the report search function could also have glossary access."; "Yes, let's add align_glossary as a default"; "Yes, turn on the recommended items."; 2026-10-31: "Confirm glossary on by default."
- **Builds on:** [0046](0046-one-source-analyzed-with-indexes-of-what-was-read.md); made in [indexes and glossaries](../research/indexes-and-glossaries-measured-2026-11-17.md) (milestones 2 and 5)

## Decision

- **Metadata, never claims:** a source's abbreviations, defined terms, symbols and the conventions framing its values, each with where it's defined and how far it reaches.
- **Read from blocks found by their headings,** before the claims: as laid out where the layout allows, else the model reads the block's text and a term is kept only where it and its meaning are in that text; prose definitions by pattern; a drawn legend's picture asked apart from its words.
- **Reach:** the document, one sheet, or a discipline's sheets (a list on S-001 holds for the S sheets); the nearest definition holds.
- **An abbreviation is one word, however it's written:** a meaning written out is folded into its term in alignment, retrieval and topics (`align_glossary`, `retrieve_glossary`, `topic_glossary`, defaults); spelling terms out instead paired claims wrongly. Shown to the reader, the judge or the explainer: levers, off (no different from their null arms).
- **Reports:** a term's meaning beside the claims using it; search finds a term's meaning.

## Consequences

- `glossary.py`, `terms.py`; the report's Glossary view, `index/glossary.csv`.
