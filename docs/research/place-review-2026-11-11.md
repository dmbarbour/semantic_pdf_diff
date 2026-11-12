# Place: where a component is used in a system, not where a document discusses it

- **Status:** Reviewed (2026-11-11); answered 2026-11-12 (below), questions 2 to 4 continued in [the system use review](system-use-review-2026-11-12.md).
- **Asked for:** the owner, 2026-11-11, on Claude's report of milestone 10: "Since you're mentioning matched sections, it seems you and I had a very different understanding for what 'place' meant when we were talking about it. I was thinking more about where a component is used in a system. Not where the section discussing a component appears in a document discussing the component, which seems much less meaningful as evidence. Review this misunderstanding and its outcomes with Fable."
- **Done by:** Claude's account first, then Fable (claude-fable-5-1), read-only, checking it against the code, the record and recorded reports; Fable's claims checked by Claude (below).
- **Concerns:** [evidence combined numerically](../plans/evidence-combination-2026-11-11.md) (milestone 10), [tentative matches](../plans/tentative-matches-2026-11-07.md) (milestones 10 and 12), [the same-thing review](same-thing-review-2026-11-09.md), [the gotchas review](gotchas-review-2026-11-09.md), [the evidence combination review](evidence-combination-review-2026-11-11.md).

## The answer

The owner is right: "place" was built as a component's position in a document, and the owner meant its position in a system. The document sense was Claude's first, in its own draft of the same-thing review; Fable named a `place` band for it; Claude's question to the owner supplied the word; the owner's answer added "relationships", which nobody asked about. Claude's first account put the origin on Fable's review; the record says otherwise.

## The record, in order

- **The owner, 2026-10-01** (`relations.py`'s docstring): "We'll need to develop a fairly wide array of 'relations', e.g. component of, within, attached to, etc."
- **The owner, 2026-11-09,** asking for the same-thing review: "how we're integrating context (not just properties of a thing, but also of how it's used)". No "place".
- **Claude's draft** (same-thing review, "What isn't used"): "**Where it is:** its section's heading path and "about" (a pump in "Raw water intake" and one in "Filter backwash"), the figure or sheet it's drawn on"; direction 2, "Sections matched across documents". The document sense starts here, Claude's.
- **Fable's second opinion,** the same day: "across designs, identity is a hypothesis about role in a structure. Names are the weakest proxy" (the owner's sense), then, as the concrete step, "Sections matched across sources ... A link's band `place`" and "a third family, place/use"; relations (a `neighbour` band, a schematics pair) last.
- **Question B,** Claude's: "A third family, place/use, in the rubric". The owner: "Yes, we need place/use/context relationships that are also 'fitted' based on intelligence and heuristics, generally fuzzy not all or nothing." The yes was read as approval of sections; "relationships" wasn't in the question and wasn't asked about.
- **Tentative matches' milestones** (70bcb40): 10 "Place, use and context, fitted: Sections matched across sources (headings, abouts, the firm matches in them): a link's `place` band"; 12 "Relations: Part of, connected to, serves". The system sense went to 12, never built.
- **The evidence combination review,** 2026-11-11: "place" a family and places that don't correspond negative evidence, unexamined, though the owner had just quoted Claude's "place lowering a link".
- **Milestone 10's build** (2d56c25): the controlled PDFs have no outline (the gotchas review's item 11), so Claude put neighbours in document order in its place (`links._places`, `_place`). When the proxy's input was missing, a weaker proxy replaced it instead of a return to the concept.
- **Why nobody noticed:** on the water treatment template, sections are subsystems (Treatment Process, Chemical Feed, Disinfection), so the two senses agree on every knob. Real documents are often organised by discipline or deliverable, where they don't.
- **Recoverable from the record:** the owner's "relations, e.g. component of, within, attached to"; the claim-context plan (across designs "what a thing is (its kind, its role ...) counts most"); "how it's used"; "relationships". And Claude's own `proposals.spruce_lake` docstring, written on the day of the knob: "a decoy only where it is, and what it serves, can tell apart".

## Outcomes

| What | Built on | Verdict |
| --- | --- | --- |
| Spruce Lake's decoy: the administration building's air handling filters against the plant's filters (`proposals.spruce_lake`) | Called a "decoy in another section" | **Keep:** a system-use knob (what it serves). Combined, 2 wrong firm groups on seeds 16 and 17: the owner's sense failing today, with a number |
| Spruce Lake's renamed, reordered sections | Document place | **Keep, relabel:** a layout check (matching survives renamed sections), not place |
| Birch Hollow's contested tags, Pine Ridge's backwash pump, Cedar Falls' sludge pump | Told apart by what each does ("delivers to the filters", "returns washwater to the head of the plant") | **Keep:** already system-use knobs |
| Place by neighbours in document order (`links._places`, `_place`, `features["place"]`, candidates/4) | Document place | **Keep at weight 0; rename pending** (Fable: "adjacency", so "place" is free; the owner's call, question 5) |
| Plan text: milestone 10 of both plans; "Next for place" (sections from PDFs' headings) | Document place | **Superseded,** pointer added now; rewritten after the owner's answers |
| Lever rows: sections matched with a `place` band; place by neighbours; a section source "for the place family" | Document place | **Relabelled now:** the section source stays useful (dossiers, abouts, looks); its reason changes |
| Lever rows: a use profile; a `neighbour` band from relations and a schematics proposals pair | The owner's sense | **Keep:** milestone 10's core, not 12's |
| The gotchas review's item 11 (no outline, place empty) | Document place | True of sections; no longer about place (the review stays as written) |

## The owner's sense as evidence

Two subjects of two designs are likelier one where their place in the system corresponds:

- **For:** containers correspond (part of the intake, the filter gallery, AHU-3); flow neighbours correspond (fed by the rapid mix basin, feeds the filters); what they serve corresponds (Hall C, the clearwell); duties agree (raw water against raw water, duty against duty).
- **Against:** containers whose counterparts differ (the building's air handling against the treatment process); duties in conflict (backwash against raw water).
- **Too few anchors:** no point either way, never negative.

**Where it is today** (Fable, on recorded reports; checked by Claude where marked):

- **Names:** the reader folds the role into the entity ("Backwash pump P-101A", "administration building air handling unit filters"); today this is names' evidence, diluted by spelling.
- **Conditions and scope:** in prose the reader puts a connection in scope, not a relation ("Backwash pump P-101A | delivery flow rate | 3,395 | to the filters"; "Chlorine | feed rate | 3.3 | ahead of the clearwell"). In diagrams relation-shaped claims appear, and the lab's phrase table (`relations.RELATIONS`) recognises them.
- **Context records:** a lead-in such as "The administration building's air handling units are served as follows", captured as a record with subject and scope.
- **Sections' abouts and keywords:** the system a section covers, where sections are subsystems; absent for PDFs without an outline.
- **Claim fields `role` and `context`:** in the schema, asked by no prompt (checked: `schema.Claim`, "Prompts don't ask for these yet").
- **Not today:** the second pass's relations are among one subject's claims (restates, corroborates, refines, differs by condition, contradicts, derived from; checked: `dossiers.RELATIONS`), not system relations; and comparisons don't run the second pass. The controlled keys' relational facts come only from the schematics and sheets templates (checked); the lab's matching scorer drops them (checked: `comparison._matching`, `not f.get("relation")`).

**Cheapest first** (Fable's ladder):

1. **A relation graph per source from existing claims, no requests:** relation-shaped attributes by the lab's phrase table (moved into the product), plus conditions and scope naming another subject of the same source ("to the filters" → the filters subject), resolved by the alias machinery; rebuilt offline from recorded reports.
2. **Use words per subject:** role words from names, records and abouts' keywords, compared across a pair by words and by meaning (embeddings exist).
3. **A system line from the second pass in comparisons:** part of, feeds, serves, duty; a request a subject.
4. **`role` and `context` defined in the reader's prompt:** every recording re-made (about $0.2 a seed set); last.

**In the combiner** (`links.contributions`): a family of its own, capped like the others, using `_place`'s anchor idea (firm groups and keyed pairs as counterparts) over the relation graph instead of document order. Points: a container's counterpart shared (strong), a flow neighbour's counterpart shared (decaying), serves a counterpart, role words agree; against: containers' counterparts differ, role words conflict. Logged weighing nothing first, each point's share right measured, then weighed by eye.

**Measured by:**

- **Knobs that exist:** same-named components in different systems (Spruce Lake's filters; Birch Hollow's contested tags). Target: Spruce Lake's 2 wrong firm groups to 0.
- **A knob that separates the senses** (Claude will build it unless the owner objects): siblings told apart by system position alone (P-101A/B/C against IP-1/2/3, each with a stated duty or connection, nothing else differing), in a new base template so the revisions pairs aren't re-recorded; sections by discipline with subsystems crossing them, so document place and system place disagree.
- **A schematics proposals pair:** one topology with renamed parts and a same-named part in another position (a filter on the return), scored by parts' ids (`relations.Index` maps claims to things). The scorer's relational part comes first.
- **By eye:** the turbine pair (tower, nacelle, rotor: part of).

## The pattern, and what changes

The same shape as the levels review, two days apart: the owner's domain word → the nearest thing the pipeline stores → the word names the mechanism → a plan approved on the word → measured on the word. Levels: a grade of one point became the pair's level. Place: a component's position in a system became its claims' section, then their order in the document.

- **A word naming a family, band, milestone or knob gets a one-line definition with a domain example in the question itself:** "By place I mean: the backwash pump sits in the filter gallery and feeds the filters. Not: its table is in section 4."
- **A contrast, not a yes/no:** "system position or document position?" A yes hides a mismatch; a choice shows it.
- **An answer using a word the question didn't** ("relationships") is recorded as a difference and asked about.
- **Mechanisms named by mechanism** ("section correspondence", "document adjacency"); the owner's words kept for the owner's concepts.
- **A knob where the senses disagree,** not one where they coincide.
- **A proxy's input missing** (no outline): back to the concept, not a weaker proxy. Fable, of its own part: a first concrete step written as "a proxy for X" in the same line, with X's cheapest form beside it.

## Questions for the owner

1. **Section correspondence:** a weak signal worth keeping where documents are organised by system ("4 Process Units" against "2 Treatment Process"), or dropped?
2. **Which relations carry identity most across designs:** part of, flow neighbours, serves, duty? For example the intake pump IP-1 against P-101A: "serves the north intake" against "delivers to the rapid mix basin".
3. **Relations from existing claims first** (no requests: Backwash pump P-101A's scope "to the filters" becomes an edge to the filters), **or the reader asked now** (`role` and `context` defined; every recording re-made)?
4. **The second pass in comparisons,** a request a subject, so each subject gets a system line (Spruce Lake's building filters: "part of the administration building's air handling; serves the offices")?
5. **The family's name:** "system" or "use", with today's neighbours feature renamed "adjacency" so "place" isn't a mechanism's name?

## The owner's answers (2026-11-12)

- **1:** "We can keep matching sections as a weak signal, especially when the sections are naming components or subsystems."
- **2:** "I don't know which relations best show two design's components are the same. Certainly, serving the same role or duty would be a big part. Having similar inputs and outputs. Similar roles for the upstream and downstream components. Develop a list of suspects that an engineer, mechanic, or architect might examine. Ask Fable for recommendations, too."
- **3:** "Existing claims first, and carefully determine where we should be asking readers for more role and context info. Ask Fable to review and make suggestions, too."
- **4:** "I'm not sure of your intention here. Is this one request per component as part of the second pass, after gathering enough information to present it? Or something else? It seems to me that understanding components requires understanding what they're part of, and so does identifying whether two things are the same or at least comparable. This entangles things in some awkward ways, and I'm also struggling to understand the best approaches. Perhaps review our options, ask Fable for a backup review."
- **5:** "Seems viable, but this is trying to fit some connotations. Perhaps revisit after expanding on Q2?" (open)
- Questions 2 to 4 are taken up in [the system use review](system-use-review-2026-11-12.md).

## Checked by Claude

- `relations.py`'s docstring quotes the owner, 2026-10-01, "component of, within, attached to". True.
- `proposals.spruce_lake`'s docstring: "a decoy only where it is, and what it serves, can tell apart". True.
- The same-thing review's lines: Claude's "Where it is: its section's heading path", direction 2 "Sections matched across documents", Fable's "role in a structure" and `place` band, question B and the owner's answer. True.
- `dossiers.RELATIONS` is epistemic only; `Fact.relation` is set in the lab only by `schematics.py` and `sheets.py`; `comparison._matching` drops relational facts; `Claim.role` and `context` are asked by no prompt. True.
- The plan's held-out result: Spruce Lake's filters and the building's, 2 wrong firm groups. True.
- Not checked: the recorded reports' quoted claims (Fable read them; the shapes match the templates).

## Claude, on Fable's opinion

- **Agreed,** including the correction of Claude's account: the document sense was Claude's draft before it was Fable's band, and the question supplied the word.
- **One emphasis:** nothing built on the document sense needs unwinding in code; the neighbours feature weighs nothing. What changes is milestone 10's design and the names.
