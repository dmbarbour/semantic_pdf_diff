# Research note: comparing competing designs (and revisions)

- **Date:** 2026-09-25
- **Status:** Input for discussion; nothing here is decided.
- **Prompted by:** the owner's brainstorm (not authoritative). When comparing different designs, ask whether a value matters to an external client or user, or is internal to the design. Relevance depends on context (a pitch rate affects moment of inertia, which may matter depending on how the system is mounted), so perhaps ask *where* a value could become externally relevant.
- **Triggering case:** the first review batch ([evaluation-s01](../reviews/evaluation-s01-2026-09-25.md)). The reviewers split on whether NREL 5 MW's pitch angle at 25 m/s and IEA 15 MW's pitch-controller objective are "complementary" or "unrelated".

## What established practice offers

Several fields already separate what stakeholders observe from what designers choose, and model how one becomes the other.

| Field | Key idea | What it gives us |
|---|---|---|
| Systems engineering (NASA SE Handbook, INCOSE, DoD) | Needs → **measures of effectiveness** (MOE, how stakeholders judge success) → **measures of performance** (MOP, quantitative, designed to) → technical performance measures → design parameters; **key performance parameters** are the critical few. Black-box vs white-box views; **interface control documents** fix what crosses the boundary. | A *level* for every claim. Cross-design comparison belongs at MOE/MOP level and at interfaces. |
| Design theory (Hubka & Eder; Weber's CPM/PDD; Suh; Gero's FBS; MIT tradespace exploration) | **Characteristics** (set directly by the designer: structure, dimensions, materials) vs **properties** (behaviour, only influenced through characteristics); external conditions come from neighbouring systems. Tradespace work separates *design variables* from *attributes* stakeholders value. | A principled internal/external test: set directly → internal; perceived by a stakeholder or constrained by a neighbouring system → external. |
| QFD / House of Quality; Kano | Customer needs × engineering characteristics, with relationship strengths, correlations and competitive benchmarking; Kano's "indifferent" attributes. | A characteristic with no strong link to any need is internal for comparison; "indifferent" is the formal name for "even similarity doesn't matter". |
| Decision analysis (Keeney; MAUT; Pugh) | **Fundamental** objectives (ends) vs **means** objectives; attributes should be direct, unambiguous and preferentially independent; proxies are legitimate when labelled. | Compare ends; treat design parameters as evidence and explanation, not as separate criteria (else double counting). |
| Change propagation (DSMs; Clarkson, Simons & Eckert; Eckert's absorbers, carriers and multipliers; margins) | Dependencies between parameters, typed spatial, energy, information or material; change propagates when margins are exceeded. Configuration management's Class I change: affects **form, fit, function or interface**. | "Where could this matter?" becomes path-finding from a parameter to a boundary or MOE; margins say whether the path is live. Class I/II gives revisions a severity scale. |
| Source selection (FAR 15.304/305); design competitions (Solar Decathlon juried and measured contests) | Evaluation factors set in advance; proposals rated against requirements (strengths, weaknesses, deficiencies), not parameter by parameter against each other. | A factor list as the comparison schema: the criteria-first plan already points this way. |
| Reference designs in practice (IEA and NREL wind turbines; upscaling studies; windIO) | Reports lead with externally relevant, often normalised parameters: class, rated power, rotor diameter, specific power, tip speed, rotor-nacelle mass. Controllers and structure are design description. Different sizes are compared through scaling trends or dimensionless groups. | Normalisation is part of comparability. A domain schema (windIO) can seed the frame. |
| NLP work (ArxivDIGESTables, ORKG templates, DesignQA) | Comparison tables are built schema first, then values; user intent improves the schema. | Nobody seems to classify extracted design claims by stakeholder or interface relevance before comparing them: open ground. |

A worked example supporting the owner's intuition: **blade-pitch control is internal on a fixed-bottom turbine but crosses the interface on a floating one**. Standard above-rated pitch control can give negative damping of platform pitch motion (Larsen & Hanson 2007), which is why floating variants add platform feedback. Relevance depends on the reader's context, which is a user input, not a property of the claim.

## Synthesis for the tool (inference, for discussion)

**Place claims on a comparison frame before relating them.** Compare only claims in the same cell of *function or objective × level × interface*; other claims explain. This is criteria-first comparison ([n-way plan](../plans/n-way-comparison-2026-09-23.md)) with a firmer basis for choosing and organising criteria. The frame can be seeded from a domain schema, a competition's contests, a solicitation's factors, or model-proposed and user-edited criteria.

**Questions to ask of each claim or criterion:**

1. **Function:** what function or objective does it serve?
2. **Level:** need, MOE, MOP/KPP, design parameter, external condition, or rationale/intent.
3. **Set or emergent:** does the designer set it directly (characteristic), or does it emerge (property)?
4. **Interface:** does it cross the system boundary, and at which interface (grid, foundation or platform, transport, occupant, site or regulator)? What kind (spatial, energy, information, material)?
5. **Concerns:** which stakeholders' concerns does it reach (client, operator, integrator, certifier, neighbour)?
6. **Propagation:** if it's internal, is there a path to a boundary or MOE, and under what conditions ("only if floating")?
7. **Comparability:** is it comparable as-is, per unit, dimensionless, or only against a scaling trend?
8. **Conditions:** under what conditions (site class, load case, climate) does it hold?

**Default relevance:** claims at MOE/MOP level or on an interface are for comparing; internal design parameters explain. A parameter moves up to "compare" when question 6 finds a path that is live in the reader's stated context (mounting, site, client).

**Relation vocabulary** (replacing today's single list):

- **Across proposals:** first find the counterpart, then relate.
  - *Comparable* (same frame cell and conditions): the values are equal, better, worse or differ (no known direction of preference).
  - *Comparable after normalising.*
  - *Conditions differ:* report both, don't rank.
  - *Alternative means:* same function, different approach. Describe, don't score.
  - *Cross-level:* e.g. a value against an objective.
  - *No counterpart:* in only one proposal; a finding in itself.
  - *Internal only:* suppressed by default.
- **Across revisions** (same design): unchanged, changed (value, unit, conditions or basis), added, removed, refined (narrower or more precise), re-based (same value, new basis). A severity flag marks changes touching form, fit, function or interface, directly or through a path.

**The pitch case under this scheme:**
- NREL's pitch angle at 25 m/s is a steady-state operating value, internal and conditioned on wind speed.
- IEA's controller objective is rationale.
- Both serve "above-rated power regulation", so they're *cross-level* or *alternative means*.
- Neither matters externally to a fixed-bottom reader; for a floating-platform reader, both reach the platform interface.

## My own thoughts (Claude, brainstorming)

- **Propagation paths are evidence-web edges.** "Pitch schedule → rotor thrust variation → platform pitch damping → mooring loads" is a chain of *affects* and *input to* relations: exactly the vocabulary planned for [evidence webs](../plans/README.md). The two plans probably share a data model: claims as nodes, typed and conditional dependencies as edges, and relevance as reachability from a stakeholder concern.
- **Relevance could be a review dimension now, before any design is settled.** A review item could ask "who outside the system would care about this claim?" (none / a named interface or stakeholder / depends on context: which?). Labels from people and the panel would show whether models can answer it reliably, which decides how much of the frame can be automated.
- **The level question may be cheap for the model and valuable.** Telling a requirement or objective from a measured or designed value overlaps with the epistemic-status work (basis: required, targeted, measured…), which the extraction prompt already half-asks.
- **The reader's context should be explicit input,** like the criteria: "a floating platform in the North Sea", "a client comparing houses for a cold climate". The same claim changes relevance with it, so results must record the context they were computed under (another interpreter input).
- **Risk: over-structuring.** Hand-built frames and propagation graphs are expensive, and domain schemas like windIO exist only for a few domains. The first version should probably ask the model the relevance and level questions per claim or criterion, let reviewers check them, and only then decide whether to model propagation explicitly.

## Sources

- NASA Systems Engineering Handbook (MOE, MOP, TPM): https://www.nasa.gov/wp-content/uploads/2018/09/nasa_systems_engineering_handbook_0.pdf
- Roedler & Jones, INCOSE Technical Measurement Guide (2005): https://www.acqnotes.com/Attachments/INCOSE%20Technical%20Performance%20Measurements%20by%20Roedler%20and%20Jones,%20Dec%2005.pdf
- SEBoK, Measurement: https://sebokwiki.org/wiki/Measurement
- Weber, CPM/PDD: https://link.springer.com/chapter/10.1007/978-1-4471-6338-1_16
- Hubka & Eder, Theory of Technical Systems: https://link.springer.com/content/pdf/10.1007/978-3-642-52121-8.pdf
- MIT MATE / tradespace exploration: https://seari.mit.edu/mate.php
- Keeney & Gregory 2005, selecting attributes: https://pubsonline.informs.org/doi/10.1287/opre.1040.0158
- Clarkson, Simons & Eckert 2004, Change Prediction Method: https://doi.org/10.1115/1.1765117
- Eckert, Clarkson & Zanker 2004, absorbers, carriers and multipliers: https://link.springer.com/article/10.1007/s00163-003-0031-7
- MIL-HDBK-61A (Class I changes: form, fit, function, interface): https://www.acqnotes.com/Attachments/MIL-HDBK-61A%20(SE)Configuration%20Management%20Guidance.pdf
- FAR 15.304: https://www.acquisition.gov/far/15.304
- Sieros et al. 2012, upscaling wind turbines: https://onlinelibrary.wiley.com/doi/abs/10.1002/we.527
- windIO (IEA Wind Task 37): https://windio.readthedocs.io/
- ArxivDIGESTables: https://aclanthology.org/2024.emnlp-main.538/
- ORKG comparisons: https://arxiv.org/html/2308.12981
- Also cited, from memory: Hauser & Clausing 1988 (House of Quality); Pimmler & Eppinger 1994 (interaction types); Larsen & Hanson 2007 (negative damping on floating turbines); Suh (axiomatic design); Gero (FBS); ISO/IEC/IEEE 42010; Kano 1984.
