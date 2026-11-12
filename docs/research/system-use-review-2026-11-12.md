# System use: what makes two designs' components the same or comparable

- **Status:** Reviewed (2026-11-12); answered the same day (below): two families; siblings paired one to one only where meaningfully differentiated, Claude's proposal for judging it below, for the owner; then milestone 10 of [evidence combined numerically](../plans/evidence-combination-2026-11-11.md) is rewritten from this review.
- **Asked for:** the owner, 2026-11-12, answering [the place review](place-review-2026-11-11.md)'s questions:
  - Q2: "I don't know which relations best show two design's components are the same. Certainly, serving the same role or duty would be a big part. Having similar inputs and outputs. Similar roles for the upstream and downstream components. Develop a list of suspects that an engineer, mechanic, or architect might examine. Ask Fable for recommendations, too."
  - Q3: "Existing claims first, and carefully determine where we should be asking readers for more role and context info. Ask Fable to review and make suggestions, too."
  - Q4: "I'm not sure of your intention here. Is this one request per component as part of the second pass, after gathering enough information to present it? Or something else? It seems to me that understanding components requires understanding what they're part of, and so does identifying whether two things are the same or at least comparable. This entangles things in some awkward ways, and I'm also struggling to understand the best approaches. Perhaps review our options, ask Fable for a backup review."
  - Q5 (the family's name) waits on this review: "Perhaps revisit after expanding on Q2?"
- **Done by:** Claude's draft and Fable's (claude-fable-5-1) review written apart, read-only, each measuring recorded reports (no requests); then Fable's critique of Claude's draft; Fable's key claims checked by Claude (below).

## Q4 first: what the request was

- **Yes, as the owner put it:** one request a subject, per source, in the second pass, after its dossier is gathered (its claims, quotes, headings, context records), asking where it sits in its own document's system: part of what, fed by what, feeds what, serves what, its duty, the medium it handles. Not a comparison.
- **The circularity is at the comparison, not the reading:** "P-101A feeds the rapid mix basin" needs only names resolved within one source; "P-101A corresponds to IP-1 because both feed the mixer" needs the two mixers settled first.
- Comparisons don't run the second pass today (`dossiers.py` runs in analyze); a request a subject, not a pair.

## What recorded claims already hold

Measured by Claude (seed 1, two reading modes, 9 reports a pair) and Fable (held-out seeds 16 and 17, 10 reports a pair; the turbine pair; the building and schematics corpora):

- **A connection in a numbered sentence stays in the quote; the fields drop it.** Birch Hollow's "Sludge pump P-101B moves 1,336 gpm of sludge from the basins" and "returns 779 gpm of washwater to the head of the plant": in the quotes always, in conditions never; "to the filters" reached conditions in 2 of 9 reports (Claude; 2 of 10, Fable). The role stays in the name ("Sludge pump"), sometimes in the attribute ("sludge flow").
- **A sentence that is a relation becomes a relation claim:** the air handler schematic's "From Hall C, the air passes to the return fan" is read "Hall C | flows to | return fan"; 21 to 23 of its 29 claims name another part (Fable). The cut is the sentence's type, not the document's.
- **Containers reach names or captions, unreliably:** Spruce Lake's decoy filters were named with their building ("administration building air handling unit filters") in 8 of 9 reports (Claude) and 8 of 10 (Fable); in the misses the reader wrote "Filters". The building's plans put "in Hall C" in rooms' conditions; "from AHU-3" reaches conditions in some formats (`lcc-s1-traps-revised.xlsx`).
- **Roles sit in table records, not claims:** Harrow Creek's pumps are "P-101A" with capacity, head and motor; "Raw water pumps" is only in the table's context record. Markdown has no records (Fable).
- **The medium is in every unit and nowhere weighed:** Spruce Lake's decoy filters at 346 to 486 cfm/ft² (air) against the plant's 2.8 to 4.2 gpm/ft² (water). The product's unit table doesn't know cfm/ft², and counts cfm and gpm as one kind ("flow"), so air against water can't show as kinds differing.
- **The wrong group, recomputed under today's default:** seed 17's PDF joins Spruce Lake's "Filters" to Harrow Creek's "filtration" at 0.943 (Fable's parts: names +1.5, the model's pick +1.5, properties +0.9, the judge +0.6, values −0.5, the last only because the unit is unknown). **And it began within one source:** Spruce Lake's subject holds both the decoy's 3 claims ("Filters", cfm/ft²) and 2 of its real granular filtration's (gpm/ft²).
- **Birch Hollow's contested tags right by naming luck:** the pump keyed "P-101A" in both designs (raw water against backwash) is held at 0.13 by "no property in common" and "a rival shares more", which hold only while the reader writes "TDH" in one and "total dynamic head" in the other (Fable). The duty conflict weighs nothing.
- **The turbine pair** (real): few stated relations; about 157 attributes name a sub-part with the turbine as entity ("rated generator speed", "inertia about the high-speed shaft"), a part-of cue; system context in headings (tower, drivetrain, control system). Its recorded report has no index: judging the pair needs a fresh comparison (a few cents).
- **What the model is shown when matching** (`crossmatch.described`, `_shown`): names, other names, properties, verdicts; no records, sections' abouts or conditions.

## Q2: the suspects

The owner's three, marked; the rest Claude's and Fable's, merged. "For" and "against": how strongly agreement and conflict speak.

| Suspect | Who | For | Against | Where documents say it | In today's claims |
| --- | --- | --- | --- | --- | --- |
| **Role or duty** (the owner: "serving the same role or duty"): raw water, backwash, sludge removal; duty, standby | Engineer | Strong where stated | Strong (backwash against raw water) | Names' modifiers, verbs ("delivers", "returns"), schedules' service column | Names (folded), quotes; records |
| **Inputs and outputs** (the owner: "similar inputs and outputs"): from what, to what; power and signals in | Engineer, mechanic | Strong | Strong for opposite directions | "From the basins", "to the filters"; flow diagrams, P&IDs | Quotes; conditions rarely; relation claims from diagrams |
| **Upstream and downstream neighbours' roles** (the owner: "similar roles for the upstream and downstream components"), by kind: a basin before, filters after | Engineer | Strong where both say it | Moderate | Process narratives, diagrams ("ahead of the clearwell") | Diagrams' relation claims; a few quotes |
| **Medium handled:** raw water, sludge, washwater, air, light, a chemical | Engineer, mechanic | Moderate (siblings share it) | **Strong** (air against water settles Spruce Lake) | Units (cfm, gpm, MGD, nm), names, attributes ("sludge flow") | Every claim with a unit |
| **Container, part of:** system, subsystem, train, building, assembly | All | Moderate; nil where the container is the whole plant | Strong where containers are of different kinds (building services against process) | Records' lead-ins and captions, names' qualifiers, headings naming a subsystem (Q1), drawing enclosures | Records, names (8 of 10), some conditions |
| **What it serves:** a hall, a zone, a population, the filters | Mechanic, architect | Strong for zones | Moderate | Schedules' "area served", "serves", "conditions Hall C" | Conditions in the building corpus; quotes |
| **Kind or class:** pump, basin, stop; centrifugal against vertical turbine; dual-media against cartridge filter | All | A prerequisite (the properties family is mostly a kind cue) | Strong, except alternatives (UV against chlorine contact) | Names' head noun, captions, specification sections | Names, `indexes.kinds` |
| **Capacity against the system:** a pump's flow against the plant's flow and its duty count; a backwash rate against filter area | Engineer | Moderate (designs differ in scale: ratios, not values) | Moderate | Values | Values; ratios not computed |
| **Count and arrangement:** one of three in parallel, N+1, trains A and B, "one filter out of service" | Engineer, mechanic | Weak for "the same", good for "comparable" | Weak | Quantities, tag suffixes, conditions | Quantities, conditions |
| **Mounted on, driven by, powered from, controls** | Mechanic | Moderate | Moderate | Drawings, bills of materials, control narratives | Diagrams' relation claims only |
| **Interfaces:** flanges, shafts, voltage, motor control centre | Mechanic | Moderate | Strong when incompatible | Datasheets, schedules | Some attributes |
| **Operating envelope:** head, pressure, temperature, speed | Engineer, mechanic | Weak (designs scale) | Moderate (already the values family) | Values | Values |
| **A space's program:** meeting, mechanical, exhibit | Architect | Strong | Strong | Room names, room schedules | Names |
| **Adjacency and access:** next to, opens onto, its door | Architect | Strong for rooms across plans | Moderate | Plans, door schedules | Door claims ("MEETING 102 \| door \| D102") |
| **Location:** roof, mezzanine, north intake | Architect | Weak | Moderate | Conditions, quotes, drawings | A few |
| **Numbering habits:** tag prefixes, specification and sheet numbers | Document | Weak: orders siblings | Nil across designs (Birch Hollow) | Tags | Tags |
| **Sections naming a component or subsystem** (the owner's Q1: "a weak signal") | Document | Weak, only where a heading holds a subject's name | Weak | Headings | Sections with an outline (not the controlled PDFs) |

- **Siblings share every positive cue** (three raw water pumps: one duty, medium, container, neighbours): that is why place by neighbours lifted wrong siblings and moved nothing. So this evidence is mostly **against** (medium, container, duty in conflict) and only weakly **for**; where it can't tell siblings apart, "comparable" is the right answer.
- **Not "no counterpart":** a container with no counterpart in the other design (Spruce Lake's administration building) is a kind conflict (building services against process), not two containers matched elsewhere; too few anchors stays neutral.
- **First to try:** medium, from units, every claim, every format; then container and kind from records and folded names; then duty and targets from names' modifiers and quotes. Neighbours last: stated only where a sentence or a drawing is the relation.

## Q3: existing claims first, and where to ask

**Readable without a request:**

1. **Units → medium:** a unit → medium table of its own (gpm, MGD, L/s: liquid; cfm, in. w.g.: air; nm: light), separate from the unit table's kinds; a subject's media from all its units. Teaching the unit table cfm/ft² as a loading rate would erase the one signal Spruce Lake has.
2. **Records → container and kind:** lead-ins and captions already on claims' records; their last sentence and the caption's noun phrase. Tables only (not Markdown).
3. **Names → role words:** the modifiers before the tag or head noun ("Backwash", "Washwater recycle", "administration building air handling unit"), compared by meaning ("raw water", "intake", "low-lift" alike; "backwash" not). Today they are names' words, diluted; a conflict between names keyed alike weighs nothing.
4. **Quotes → duty and targets** ("delivers ... to the filters", "moves ... from the basins"): the object resolved to a subject of the same source. Moderate: a few claims a document; "from 150 ft to 190 ft" isn't a connection.
5. **Conditions:** reliable where present, rarely present.
6. **Sections:** headings naming a subject (Q1's weak signal); abouts where an outline exists (the turbine's "tower and monopile", "drivetrain").
7. **Within one source first:** a subject whose claims carry two containers or two media (Spruce Lake's "Filters") is two things; split it before any comparison.

**Where asking is worth it:**

- **Show the model what's there:** each subject's system line (from 1 to 6) in `match_subjects`' and the read's view of a subject; today they see names, properties and verdicts only. The cheapest request-side change (no extra requests; longer prompts); the lever index's use profile row.
- **The second pass's request a subject** (the Q4 request): the dossier already shows claims, passages, records and abouts; one more key, a system line (kind, medium, duty, part of, serves, fed by, feeds, location), each with the dossier's exact words as its quote, checked as adds are. Contested subjects first (siblings, same-named decoys, pairs near a cut), as `look_gaps` targets gaps; pennies a pair.
- **The reader** (`tasks.EXTRACT`): at most one rule (a numbered sentence's "to", "from", "serves" kept in conditions as scope); every recording re-made (about $0.2 a seed set). Per-claim `role` and `context` are the wrong grain (a role is a subject's, repeated on each claim) and undefined ("role" already names a figure's role, a lab fact's and an attribute's). Last.
- **Each judged against a null arm** of the same request count and prompt length (`scripts/paired.py`), on fresh seeds.

## Q4: the options

| Option | The circularity | Requests | Fails when |
| --- | --- | --- | --- |
| **A. A description per source, then compared** | Deferred: descriptions name their own document's things | 0 (claims, records, units) or 1 a subject | Descriptions generic; "the basins" resolved wrong |
| **B. Top-down from systems** (the plant, buildings, subsystems first) | Assumes the top is easy | 0 | Documents by discipline; subsystems renamed or partitioned differently; one system holding everything |
| **C. Iteration from anchors** (built in part: `indexes.built` joins confident pairs by `links.merges` first; `links._places` used them) | A fixed point from confident pairs | 0 | Too few anchors near (Spruce Lake); a wrong anchor spreads; siblings share anchors |
| **D. Descriptions by kind, not identity** ("a pump moving raw water to a mixing basin") | Dissolved: no identity across documents needed | 0, with a kind lexicon and embeddings | Kind words differ (clarifier, settling basin: meaning helps); siblings alike, which is right: comparable |
| **E. Joint matching** (one assignment, structure consistent) | Solved at once | 0; code and tuning | Opaque to the report's "why"; amplifies errors; overkill for 40 subjects |
| **F. Per-pair questions to the model,** both system lines shown | The model reasons over both | 1 a link | Confirms what it's shown; never sees the structure |

**Recommended** (Fable's design; Claude agrees): a description per subject per source by kind (A's shape, D's slots), compared slot by slot; container and targets through pass 1's anchors where they exist (C), by meaning where they don't; conflicts as points against, agreements weakly for, capped as a family. B adds nothing new: where a system is a subject (the plant, the building) it is the container slot; where it is only a heading it is Q1's weak signal. F only for links the family leaves between the cuts.

**Steps, cheapest first:**

1. **Within-source split** (a fix: bugs first): a subject holding two containers' or two media's claims.
2. **Medium:** the unit → medium table, a subject's media; logged weighing nothing, each point's share right measured on development's candidates, then weighed by eye.
3. **Container and kind** from records and names; **duty and targets** from names' modifiers and quotes; the same way.
4. **Shown to the model** in `match_subjects` and the read; a prompt lever against a null arm.
5. **The second pass's system line,** contested subjects first; a prompt lever against a null arm.
6. **The reader's rule,** last.

**Measured by:** Spruce Lake's "Filters" ~ "filtration" from 0.943 to under 0.7 on fresh seeds; the within-source split caught; Birch Hollow's keyed pumps held under 0.35 when their properties are named alike (a knob variant); development's average precision within ±0.005; a knob where siblings differ only by system position, with sections by discipline so document place and system place disagree; a schematics proposals pair scored by its relations; the turbine pair by eye (a fresh comparison, a few cents).

## What Claude is likely to get wrong (Fable)

- Section correspondence returning as place under a new name: count a heading only where it holds a subject's name (Q1).
- Assuming attributes and conditions carry relations: on numbered sentences they don't; quotes, records and units do.
- Treating medium as a unit kind: cfm and gpm are one kind; a medium table is another thing.
- A family that lifts siblings: mostly against, its "for" capped, "comparable" allowed as an answer.
- Scoring "no counterpart for the container" as "counterparts differ".
- Over-resolving containers: "the plant" holds everything; weigh a container by how few subjects share it.
- Measuring on spent seeds or on knobs where both senses agree; asking the reader before the heuristics are measured.
- Forgetting the within-source half: comparison can't repair a subject that is already two things.

## Questions for the owner

1. **Same or comparable:** three raw water pumps P-101A to C in one design against IP-1 to 3 in the other, alike in duty, medium and connections. Report them as a comparable group (three against three, no pairs), or paired one to one by their numbering's order (A with 1)?
2. **Q5, revisited:** the suspects split two ways: what a component does and handles (duty, medium, kind) and where it sits (part of, serves, fed by, feeds). One family ("use", say), or two ("duty" and "setting", say)? Names aren't settled by this; the split is the question.

The order of the steps is Claude's; the second pass's request starts on contested subjects unless the owner prefers every subject.

## The owner's answers (2026-11-12)

- **1:** "IIUC, whether we can compare them one vs. one depends on if they are meaningfully differentiated. If it's just three fungible pumps coordinating in a shared role, then how would it make sense to match them one to one? But how should we approach making this judgement in our analysis? I don't know."
- **2:** "Two families seems wiser given there's a clear split." Their names: open (Claude's suggestion below).

## Siblings: when to pair one to one (Claude's proposal, for the owner)

**Today both the product and the lab pair siblings by their numbering's order:**

- **The product:** between Harrow Creek and Pine Ridge, the model's name groups (`synonyms`) pair P-101A with IP-1, B with 2, C with 3, and the index joins them on those groups ("other names", 0.821 each). Between Harrow Creek and Birch Hollow, P-101B joins P-201B and C joins C by evidence (0.723), their spelling alike.
- **The lab:** the templates rename "Raw water pump P-101A" to "Intake pump IP-1" and to "P-201A" by order (`proposals.py`), so the scorer counts P-101A ~ IP-2 wrong though it is as valid.
- **The template's parallel pumps aren't parallel:** each of the three raw water pumps gets its own random capacity, head and motor (`corpus.py`). In a real bank they are usually alike, so here every set would look differentiated by size: an artefact, and nothing to tune a size rule on.

**The proposal** (proposals only; within revisions a tag names one thing over time):

- **Sibling sets** within one source: today's kinds (`indexes.kinds`: tag stems, numbered names), narrowed by the use family's slots (the same kind, duty and medium). Birch Hollow's P-101A to C (backwash, sludge, washwater recycle) are a numbering scheme, not siblings.
- **Differentiated or fungible, categorical first:** members differ meaningfully where their setting differs (what each serves, feeds or is part of: the north intake and the south; train A's filters and train B's) or their duty differs. A tag suffix never differentiates. Size only by class (a small jockey pump among mains), never by spread within a class.
- **One to one needs correspondence:** both sets differentiated and their differentiators corresponding (the north intake's pump with the north intake's; the small one with the small one). Otherwise a set-to-set link at the set's probability, its members listed, the set's properties compared: count, each unit's range, total and firm capacity (one out of service), arrangement.
- **Numerically:** within a fungible set a member's evidence against the other set's members is symmetric, so its margin over its own siblings is near zero. That margin, measured, is the sign of fungibility, and what should stop a member pair forming at 0.821.
- **The lab:** keys naming sibling sets, and a scorer rule counting a match within corresponding sets as right ("comparable"), committed before fresh seeds as a held-out rule is; two knobs: a bank of identical parallel pumps, and a differentiated bank (a jockey pump; north and south intakes). The base template's pumps made alike re-records the revisions pairs.
- **The families' names** (Claude's suggestion): "use" for what a component does and handles (duty, medium, kind); "setting" for where it sits (part of, serves, fed by, feeds).

**For the owner:**

1. **Duty and standby:** "P-101A and B duty, C standby" against "IP-1 and 2 duty, IP-3 standby". The standbys paired (C with 3), or the sets paired with "two duty, one standby" as their arrangement (pumps usually rotate duty)?
2. **Size classes:** 4,000, 4,000 and 2,000 gpm against 5,000, 5,000 and 1,500 gpm. The small ones paired and the large ones a set, or all three a set with the pattern compared?
3. **The names:** "use" and "setting", or others?

## The owner's answers on siblings (2026-11-12)

- **1:** "Ideally, we'd match with domain knowledge of the subject. I, personally, don't have domain knowledge of pump duty cycles and rotation."
- **2:** "It seems reasonable to pair large to large and small to small, especially if there's a good reason to have them organized that way (and reasonable to assume there is). But perhaps we should be looking for that reason as a distinguishing role? That would give us the stronger foundation to distinguish them."
- **3:** "The word "use" is easy to confuse with a verb, so perhaps "usage" or "role" or something? Ask a thesaurus."
- "Please have Fable review things too."

## Fable's review of the sibling proposal (2026-11-12, read-only, offline)

**The 0.821 is one thing, the model's name groups:** `synonyms.PROMPT`'s groups pair P-101A with IP-1 by order, `indexes.aliases` makes the group a key, the index joins on it ("other names") and the combiner counts a key both give (+2.6). Without those groups the nine pump pairs sit at 0.25 to 0.29, flat (Fable; Claude checked that no pump group forms). So the margin Claude proposed to measure is already near zero in the evidence; the key bypasses it. The prompt already refuses "items numbered apart (web 1 and web 2)". A second site: apart, the pumps are asked of `match_subjects`, and its match of two numbered tags of different schemes weighs +2.0 (about 0.75) unless demoted the same way.

**Domain knowledge** (common practice; Fable's confidence in brackets, no standard cited):

- **A bank sharing one tag number with suffix letters (P-101A to C) is one service** (high); a unit of another size or role gets another number (P-102) or a note.
- **Identical units are the default in a bank** (high): firm capacity is rated with the largest unit out of service, so any unit must be able to be the one out.
- **Duty, standby, lead and lag rotate** (high): the controls alternate the lead by run-hours or each start. "Standby" is the set's arrangement ("two duty, one standby"), not a member's identity: don't pair C with 3. A standby is differentiated where its driver differs (an engine-driven standby, a variable-speed drive on the lead only) or its size.
- **A jockey or pony pump** (high): a small unit keeping pressure or carrying minimum flows ("low-flow", "minimum flow", "turndown", "night"); never interchangeable with the mains.
- **Trains** (high): Train A mirrors Train B; pair train to train where both designs have trains, else sets.
- **HVAC:** N+1 chillers often identical (medium); air handlers differ by area served (high: "AHU-3 serves Hall C"), never fungible.
- **Assemblies:** a turbine's three blades are a balanced set (high): report the count and one blade's properties.
- **Architecture:** typical rooms and floors are sets (high); numbered rooms differ by location and adjacency, and across designs the number means nothing.
- **What documents say:** one row "3 @ 4,000 gpm" against separate rows; "TYP.", "identical", "each", "N+1", "duty/standby", "lead/lag", "alternate", "jockey", "pony", "low-flow", "VFD", "future"; a Service column ("raw water", "backwash"); "area served"; different tag numbers; a different driver.

**The owner's Q2, a size's reason:** stated reasons (jockey, low-flow, a separate tag number or Service row, "P-102 carries night flows") weigh as duty; the model's guess from knowledge ("probably a low-flow unit") is logged as an inference without a quote and weighs less; with no reason, a size class is a weak "comparable", never a one-to-one join, compared by ratios within the set (5,000 and 1,500 against 4,000 and 2,000 both "two large, one small"), a class of two or more or a stated reason. The template's three random draws always make a class: nothing to tune on.

**Domain knowledge in the analysis:**

- **The kind dossier** (`dossiers.KIND_PROMPT`, one request a kind a source, already mentions "identical, duty and standby"): a key for whether the items are interchangeable, as the source says it, each answer quoting the passages (checked as adds are). In comparisons a request a kind a source (the second pass doesn't run there). Tested with knobs: an identical bank; a differentiated one (a jockey; north and south intakes); a stated "two duty, one standby"; and a **trap**: today's random-valued bank, where the right answer is "not stated". A null arm without the key.
- **A table of document patterns** (one tag number with suffix letters; the words above; a Service column): no requests; Birch Hollow's P-101A to C (three duties) must not be a set.
- **The second pass's line a subject** can't see the set; the reader's words last.

**Claude's proposal, corrected:**

- **A fix first:** between proposals, a name group of two numbered tags of different schemes (P-101A, IP-1) is not a key, nor is the model's match of them; then the set-to-set link is the shape of what remains.
- **`indexes.kinds` isn't sibling sets:** it groups both sources' subjects by tag letters (Harrow Creek against Birch Hollow: one "pump (P)" kind of nine, four duties). Sets need a partition a source and the names' head words (backwash, sludge, recycle), available now.
- **A margin near zero means undifferentiated by the evidence weighed,** not fungible: duty words weigh nothing yet, so a jockey among mains shows none either.
- **A set's probability** through the same `candidates` and `combined` path, as a subject of the set's members (count, each property's range, total and firm capacity, arrangement words), so the report's "why" keeps one shape.
- **The scorer:** `comparison._matching`'s read already takes related pairs from splits; a `sets` argument with the cross-pairs of corresponding sets is the "comparable" rule, committed before fresh seeds.
- **The base template's pumps stay distinct:** the revisions knobs need distinct values (`revisions.renamed_later`, `split_later`); the identical bank is a proposals knob.
- **A set-to-set link shows:** both sets' members and counts, each property's range a side, total and firm capacity, the arrangement words quoted, and why no pairs: undifferentiated in either source; differentiated, but not correspondingly; differentiated one side only. Gaps stay a member's.

**The families' names** (ranked): **duty** and **placement** (nouns; the owner's own "duty"; few collisions in the code; slots within duty: kind, medium, service, arrangement; within placement: part of, serves, fed by, feeds, location; "duty" also names the duty/standby arrangement, hence that slot's name); **service** and **connections** (the schedules' and P&IDs' words; 32 collisions; connections misses part of); **function** and **position** (plain; code's words). Rejected: role, usage, setting, situation, context, topology, siting.

**Likely mistakes next:** building fungibility before removing the ordinal key; `indexes.kinds` as sibling sets; a margin near zero read as fungible; a size rule tuned on random draws; standbys paired; the base template's pumps made identical; asking the model "interchangeable?" without quotes and without the trap knob; the scorer's one-to-one ids taken as truth before the set rule.

## Checked by Claude

- `values.search_unit("cfm/ft²")` is None; cfm and gpm are both "flow". True.
- Seed 17's PDF, rebuilt offline under today's default: "Filters" ~ "filtration" at 0.943; Spruce Lake's side holds the decoy's 3 claims (cfm/ft²) and 2 of granular filtration's (gpm/ft²). True (the family parts not rechecked).
- `crossmatch.py` reads no records. True.
- Seed 1's Birch Hollow and Spruce Lake reports: quotes, conditions and names as stated (2 of 9; 8 of 9). True.
- Not checked: the turbine counts, the schematics' 21 to 23 of 29, Birch Hollow's 0.13 and its parts.

## Claude, on Fable's opinion

- **Agreed,** including its corrections of Claude's draft: medium first (units are in every claim; names depend on the reader), stage in the process train dropped as a carrier (it was sections again), the top-down prior dropped as a mechanism, the within-source split added.
- **Kept from Claude's draft:** capacity against the system, type or class, a space's program and adjacency; per-claim role as the wrong grain; the second pass targeted at contested subjects.
