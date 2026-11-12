# Evidence combined numerically: grades per point, a probability per pair

- **Status:** Active (2026-11-11; the owner: "I've reviewed and don't see anything obviously wrong. Please get started."). Milestones 0 to 6 built 2026-11-11.
- **The owner, 2026-11-11:** "IIRC, we discussed the possible/plausible/firm distinction as a qualitative rubric for judges localized to a point of evidence, but how we combine things is more numerical, and combining multiple points of evidence into a holistic metric. The way you're describing it here, you missed or lost that point." Then: "please review things with yourself and Fable to see where we've gone off track then we'll prepare a plan to get back on track."
- **The owner's answers to the review's questions (2026-11-11), in their words:**
  - **Weights:** "We clearly need some better training sets for analysis. But yes, we can start with hand-set weights adjusted by eye."
  - **Firm groups on the score:** "Not only is it okay, I'm pretty sure it's necessary. Firm groups aren't like a 100% on a Bayesian that cannot be shifted by evidence. More generally, nothing should ever be pinned at 0% or 100% if we're using Bayesian analysis. Perhaps firm group is only 80% without corroborating evidence."
  - **Models' grades:** "I think it's fine for models to carry their own possible/plausible/firm grades. TBH, I'd have asked models for numeric confidence scores, but the answer from models seems to be 100% confidence about 90% of the time. Perhaps we should have added "being 100% confident about anything, even whether you have the right numeric bases and interpretation for '2+2=4' without knowing the full context, will be dismissed as delusional" or something. But currently I simply doubt the ability of models to judge or emit a real confidence score. Only techniques such as embeddings or cross-encoders that could touch the probability distributions underneath seem to have decent metrics."
  - **Display:** "I think it's a good idea to report confidence scores numerically. We could certainly experiment with qualitative bands outside possible/plausible/firm, whether for display or model output."
  - **Thresholds:** "You'll be the one tuning things based on measurement and initially by analysis."
- **Takes over** the tentative row *Evidence combined numerically* (2026-11-11), and from [tentative matches](tentative-matches-2026-11-07.md) (paused at its milestone 10) its milestones 10 (place and use) and 13 (a panel of judges).
- **Builds on:** [the evidence combination review](../research/evidence-combination-review-2026-11-11.md) (Claude, then Fable); tentative matches' evidence log (`links.candidates`), banding (`links.bands`) and fitting (lab `linkfit.py`); alignment's weighted score (`align._score`); no rater is ground truth ([0018](../decisions/0018-several-raters-none-ground-truth.md)); levers judged paired and promoted held out ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)); early development by eye.

## Why

Tentative matches put possible, plausible and firm on the whole pair and combined evidence by rules: families of evidence counted (two plausible, one possible), then caps (values that don't fit, the model picking a decoy), a floor (a shared tag), splits of firm groups (a rival sharing more properties, no shared property), and consumers gated on "plausible". Firm groups are all or nothing. The review traces how; this plan replaces the rules with a combination.

## Concepts

- **A grade is one point of evidence's** (the owner): possible, plausible or firm, given where a judge or a model reads one thing (the judge's verdict on two claims, the model's match, its read against a decoy). Models' grades are qualitative; a model's numeric self-confidence isn't trusted (the owner: "100% confidence about 90% of the time").
- **Code's evidence is continuous where it can be:** a shared name word's rarity (its IDF over the subjects' names), names' spelling share, embeddings' cosine and the reranker's score (the owner: these "touch the probability distributions underneath"), properties in common and the margin over the best rival, values' fit (a ratio, unit kinds agreeing), place (later).
- **A pair's standing is a probability:** each point a signed weight (a log-likelihood ratio), weights of one family (names, the model's readings, properties, values, the judge, place) bounded together so no family decides alone, summed with a prior into log-odds, the probability never 0 or 1 (the owner: "nothing should ever be pinned at 0% or 100%").
- **Negative evidence is weight, not a cap:** values of other unit kinds, a decoy picked, a rival sharing more properties, places that don't correspond, identifiers that differ (strong between revisions, mild between proposals).
- **Firm is a threshold, not a certainty:** a group joined where its probability passes the merge threshold, carrying its probability, shifted by later evidence (the owner: "Perhaps firm group is only 80% without corroborating evidence": a shared key alone starts near 0.8).
- **Hard rules only for scope and cost:** no chaining (A~B and B~C don't make A~C); a source's two subjects aren't linked by this plan; caps on how many links and reads.
- **Shown as numbers:** a link or group shows its probability and each point's contribution; bands, if any, in other words than the grades (the owner: "experiment with qualitative bands outside possible/plausible/firm").
- **Thresholds are Claude's** (the owner), set first by analysis of the recorded reports' score distributions, then by measurement.

## Milestones

The owner's order: bugs, then behaviour-preserving changes, then features.

### 0. The weights table's stamp (a bug)

`link_weights.json` says the candidate generator it was fitted on (`candidates/1`); nothing checks it, and it predates `keyed_links` and `unit_kinds`. Checked where it's read, or the table retired (`link_levels: weights` is off).

- **Built 2026-11-11:** `links.CANDIDATES` versions what `candidates()` makes (`candidates/2` since `keyed_links` added pairs keyed alike); `links.weights()` returns a table only where its stamp is that version, so weights/1 is stale and `link_levels: weights` keeps the rubric, a warning saying so once. weights/1 stays in the repository until milestone 9 refits.

### 1. Evidence recorded continuously (behaviour-preserving)

- **`links.candidates`** gains each rule's inputs as numbers (`candidates/2`): the shared words' IDF, the spelling share, the cosine and the reranker's score where asked, properties in common and the best rival's count, the values' ratio and unit kinds, the key or other names shared, the model's match and read, the judge's verdicts with their confidence (logged, weighing nothing until measured: the owner doubts it).
- **Today's levels kept;** the recorded reports (the controlled corpus's, seeds 1 and 8 to 15, the slices') rebuild identically. No requests.
- **The consumers inventoried** (2026-11-11): linked values, gaps given otherwise and link gaps (`indexes`), topics (`report.report_topics`) gate on "plausible"; the Subjects view and index.md show `link_said`; the lab's scorer counts by level; link reads aren't chosen by level, but by the link set (so a new set changes requests).
- **Built 2026-11-11** (`candidates/3`): each candidate pair carries `features`: the rarest shared name word's IDF over the subjects' names, the names' words' share in common, their spelling's (trigrams), the cosine and the reranker's score where asked, properties in common and the most either has with another candidate, the values' largest ratio of one unit kind and how many pairs are of other kinds, values in common, keyed, the model's answers and read, the judge's verdicts with its confidence, alignment's groupings. Kept beside the link, not in it: a report's links are unchanged, and the features are made again from any recorded report.
  - **Behaviour preserved:** the 693 recorded comparison reports' indexes (the controlled pairs and every held-out arm) rebuild identically.
  - **Found on the way, fixed first** (two commits of their own): an index differed between two runs of the same code, a set's order, set by the process's hash seed, deciding ties: a property's names ("Height" and "height" tie on `natural`, which folds case), and a kind of tagged items' name (its most said word, "track" and "element" tying). Every recorded comparison report's index is now the same under any seed.

### 2. A scorer that ranks and calibrates (the lab, before any combiner)

- **`comparison._matching`** gains average precision over candidate pairs, log loss, and calibration by probability band (`linkfit.calibration` moved in), the keys one rater (0018).
- **A null arm:** today's levels as a two-valued score (plausible high, possible low, no link lowest), which a combiner has to beat in average precision.
- **Level counts** kept as guards at most, never a target (the targets of milestones 4 to 16 counted levels: part of the drift).
- **Built 2026-11-11** (`comparison._ranking`, `linkfit.average_precision`, `linkfit.log_loss`; `tests/test_linkfit.py`): every scored proposals report's matching gains "ranking": every firm group and candidate pair, labelled by the keys, scored by its probability where given, else by today's level (firm 3, plausible 2, possible 1, not linked 0); its average precision (ties counted together), the same of the candidate pairs alone (the links' own ranking, firm groups apart), the precision at plausible and at possible or above, and log loss and calibration where probabilities are given.
- **The null arm's baseline** (development: seeds 1 and 8 to 15, the recorded reports rebuilt offline at today's defaults; mean of the units' average precision):

  | Template | Units | All pairs | Candidate pairs alone |
  |---|---|---|---|
  | Every one | 182 | 0.939 | 0.634 (175 units) |
  | Pine Ridge | 37 | 0.949 | 0.681 |
  | Cedar Falls | 37 | 0.907 | 0.685 |
  | Cyclone | 37 | 0.968 | 0.722 |
  | Birch Hollow (the tags' knob) | 37 | 0.916 | 0.372 |
  | Pine Ridge in metric | 29 | 0.947 | 0.689 |
  | Spruce Lake (seed 1 only) | 5 | 1.000 | 1.000 |

  - Firm groups, mostly right, lift every ranking; the candidate pairs' alone is where a combiner shows: Birch Hollow's contested tags, plausible and wrong, rank above its right links.

### 3. The combiner, hand-set (a lever, off)

- **Signed weights per point,** families bounded (a family's points by maximum or a decaying sum), a prior, the probability clipped away from 0 and 1. Set by eye (the owner: "hand-set weights adjusted by eye"), checked by milestone 2's measures on seeds 1 and 8 to 15 (development now), on the turbine pair and on the knobs (Birch Hollow, the metric pair, Spruce Lake).
- **Tuned to the keys' right outcomes,** not to today's levels: reproducing the rubric would re-encode it.
- **A decision record** when it lands: evidence combined numerically, nothing pinned.
- **Built 2026-11-11** (`link_levels: combined`, `links.contributions`, `links.combined`, `combined/1`, off; [decision 0041](../decisions/0041-evidence-combined-numerically.md)):
  - **Weights by eye, guided by development's points** (seeds 1 and 8 to 15, 2,357 candidate pairs, 0.31 matches by chance; each weight about its log-likelihood ratio, shrunk toward 0, the strongest capped):

    | Point | Share right | Weight |
    |---|---|---|
    | Properties in common, no rival as many | 0.93 | +0.9 each, at most 2.5 |
    | Spelled alike | 1.00 | up to +1.5 (capped lower: the turbine pair) |
    | Picked over a decoy | 0.95 | +1.5 |
    | Magnitudes close; the judge paired them | 0.95; 0.94 | +0.4; +0.6 to +0.8 |
    | Words in common, a rare one | 0.38 | +0.6 × share; +0.15 × IDF |
    | Properties in common, a rival as many | 0.31 | 0 |
    | A rival shares more | 0.05 | −1.2 each, at most −2.4 |
    | The decoy picked; other kinds of unit | 0.00; 0.21 | −2.5; −0.5 |
    | A key both give | (contested ones only) | +2.2: with the prior near 0.8 alone (the owner) |

  - **Correlated evidence counted less:** between siblings (a rival shares as many properties), values close and the judge's pairings at 0.3 of their weight (0.31 right: chance, against 0.95 apart); for a pair keyed alike, the judge's pairing and the read count nothing (0.10 right: the key put them there, milestone 14).
  - **Families bounded:** a family's points for decay by half each and are capped at 1.5, so one family alone (names, or the model's readings) stays under plausible: the rubric's two families, made soft. Prior −1.2; probabilities kept within 0.02 of 0 and 1.
  - **Levels shown by the probability** (for consumers, until milestone 5): possible from 0.35 (development: above it about 90% right, under it mostly a weak name), plausible from 0.6 (above one family alone, 0.57).
  - **Measured** (development, 182 units, the recorded reports rebuilt offline; the null arm's in parentheses): the candidate pairs' average precision 0.794 (0.634), every template better (Birch Hollow 0.834, from 0.372); all pairs' 0.964 (0.939); log loss 0.416; calibrated by band: said 0.03, right 3%; 0.24, 23%; 0.33, 33%; 0.60, 82%; 0.74, 98%; 0.95, 95%.
  - **The turbine pair, by eye:** plausible only the two the rubric calls plausible (DOWEC's turbine and "turbine"; IEA's 15-MW and NREL's 5-MW, 0.86 each); six possible (the rubric ten), the single family's at 0.52 to 0.57 ("Rotor Speed" and "rotor-speed error", IEA's turbine and "Region 2½").
  - **Off:** held out by template (Harbor, then milestone 8's second) before any default.

### 4. Rules into weights, numbers shown

- **The caps, floors and splits** (link_tests' misfit, link_read's decoy or neither, keyed_links' floor and contest, other_names_fit's split, `distinct`) become weights; `property_alike` the same combiner in miniature.
- **Shown:** `link_said`, the Subjects view and index.md say a probability and each point's contribution.
- **Built 2026-11-11** (under `link_levels: combined`):
  - **The caps and floor of links are weights in the combiner already** (milestone 3: the misfit, the decoy, a key, a rival sharing more); the splits of firm groups (`keyed_links`' contest, `other_names_fit`) move to milestone 6, where firm groups go on the score.
  - **Properties by weight** (`links.property_combined`): names alike +1.5, values of one kind that fit +1.0, far apart −1.0, only other kinds −2.5 (once a veto), the judge's pairing +1.5, a prior −1.5, families capped; `indexes.given_otherwise` drops a gap from 0.6, notes "possibly given as X (0.50)" from 0.35.
  - **Shown:** a combined link says its probability and each family's signed part ("possibly the counterpart of Pine Ridge Water Treatment Plant (b; 0.90: names +1.5, properties +1.5, values +0.4)"), in the Subjects view, index.md and the export; a link gap says the link's probability.
  - **Identifiers that differ** (Room 104, Room 105) recorded as a feature, weighing nothing between proposals: 0.33 of such pairs right on development, 0.31 by chance.
  - **Measured** (development, gaps, the recorded reports rebuilt): gaps another source fills unchanged (155 right, 26 both give it); link gaps 26 right of 310 under the rubric, 26 right of 36 combined (the combiner's plausible links no longer the contested tags').

### 5. Consumers on the probability

- Linked values, gaps given otherwise, link gaps and topics take the pair's probability with a threshold each, rank by it and show it; a gap given otherwise kept with "possibly given as X (p)" below its threshold.
- **Thresholds** set by analysis of the recorded reports first (the owner: "initially by analysis").
- **Built 2026-11-11** (`links.USES`, `links.trusted`): linked values, link gaps and topics take a combined link where its probability reaches their cut, a rubric's by its level; gaps given otherwise by `SHOWN` (milestone 4). Link gaps from 0.6 (development: all 26 right ones from 0.5 to 0.8, the fewest wrong, 10, at 0.6 and 0.7); linked values and topics at 0.6 for now. Link gaps come in their links' order, the most probable first.

### 6. Firm groups between proposals on the score

- **`indexes.matched`' proposals branch** joins where the pair's probability passes the merge threshold, an assignment with a margin as `align` does; a shared key a strong point (near 0.8 alone), a contest weighing against it. The owner: "Not only is it okay, I'm pretty sure it's necessary."
- **Architectural, so not a lever at first; the exception recommended:** the old path kept behind a setting until milestone 2's measures pass on development and held out, then removed.
- **Revisions later:** their findings-based groups carry a probability too (nothing pinned), the findings the dominant evidence; after proposals.
- **Built 2026-11-11** (under `link_levels: combined`, which keeps the old path behind it: the rubric's indexes byte-identical, the 693 recorded reports checked):
  - **Two passes** (`indexes.built`, `links.merges`): every pair keyed alike kept apart and the model's matches as evidence, not joins; each candidate pair's probability; joined one to one, the likeliest first, from `MERGE` (0.70) and by `MERGE_MARGIN` (0.1) over each side's next likeliest; built again, a keyed pair joined by its key (matched by "name" or "other names"), any other by "evidence", each group carrying its probability (shown by `matched_by`'s readers).
  - **The universe changed, so the weights were measured again** (the first pass: 11,144 candidate pairs, 3,692 matches): a key both give 1,749 of 1,876 right (0.93; contested ones 13 of 133), so a family of its own, +2.6 (near 0.8 alone, the owner's figure); names, the judge and the read count nothing beside a key (shown by it); a key with no property in common (both giving some) 187 of 302 (0.62): −0.9, `other_names_fit`'s rule as a weight. The judge's "unrelated" (0.24 right) tried at −0.4 and dropped: right groups 1,842 → 1,787.
  - **The merge cut by analysis** (development, 182 units rebuilt, firm groups right / wrong, items matched of 1,621, all pairs' average precision, false gaps):

    | | Firm right / wrong | Items matched | Average precision | Gaps both give it |
    |---|---|---|---|---|
    | The rubric (today's defaults) | 1,734 / 0 | 1,158 | 0.938 | 226 |
    | Combined, from 0.70 | 1,842 / 12 | 1,226 | 0.963 | 40 |
    | Combined, from 0.75 | 1,780 / 12 | 1,164 | 0.961 | 40 |

    - The 12 wrong: Harrow Creek's UV option and another design's chlorine contact tank, joined by evidence (two properties in common, the read's pick, the judge's pairing), the tank's keyed counterpart contested by a rival; a hard case the evidence points the wrong way on.
  - **Recorded** (seed 1, $0.007, against today's defaults as recorded): firm 329 right, 3 wrong (308, 0); items matched 232 of 278 (215); all pairs' average precision 0.969 (0.954), the candidate pairs' 0.826 (0.725); gaps right 27 (27), both give it 7 (36).

### The combiner held out (milestones 3 to 6 together)

- **Held-out rule, written 2026-11-11 before seeds 16 and 17 were generated** (decision 0037; by template, the sealed Harbor among them, spent by it):
  - **Units:** one proposals pair in one format, seeds 16 and 17: the six development templates' pairs and the sealed Harbor template (`controlled.py heldout --sealed`): 70 units.
  - **Arms:** today's defaults (`link_levels: rubric`) and `link_levels: combined`, each a recorded run.
  - **Target:** all pairs' average precision higher combined, unit by unit, at p < 0.1 by a sign flip over the units that change.
  - **Guards:** combined firm groups 98% right or more overall (development 99.3%); the keys' items a right group holds not fewer, summed; right gaps (both kinds) not fewer, summed.
  - **Reported, not judged:** the candidate pairs' average precision; log loss and calibration by band; false gaps; firm groups wrong, listed; Harbor's units apart (the template nothing was tuned on).
  - **Checked once,** on the code as committed (0.62.0); the default the owner's call.
- **Held out, 2026-11-11** (seeds 16 and 17, 70 units, both arms recorded, $1.57; Harbor spent): **passed.**
  - **Target met:** all pairs' average precision 0.954 → 0.973, 53 units changed, p < 0.0001.
  - **Guards met:** combined firm groups 737 right of 745 (98.9%); items matched 446 → 474 of 589; right gaps 60 → 60.
  - **Reported:** the candidate pairs' average precision 0.722 → 0.748; log loss 0.282; false gaps 66 → 19; calibration cautious above 0.5 (said 0.62, right 92%; 0.81, 96%; 0.95, 99.5%), close below (0.25, 28%; 0.32, 38%; 0.03, 0%).
  - **By template** (mean average precision, today's → combined): Harbor, sealed, 0.984 → 0.983 (flat); Birch Hollow 0.916 → 0.984; Cedar Falls 0.899 → 0.935; Pine Ridge 0.946 → 0.966, in metric 0.961 → 0.977; Spruce Lake 0.998 → 1.000; Cyclone 0.970 → 0.964.
  - **The 8 wrong firm groups,** each joined by evidence at 0.71 to 0.82: Harrow Creek's UV option and a chlorine contact basin (5, the hard case of development); Harbor's extended short status report and short status report (1, its look-alike decoy); Spruce Lake's filters and the building's (2: the place decoy, which the reader's names kept apart on development; place's work, milestone 10).
  - **On by default,** 2026-11-11 (the owner: "D1. Yes, turn it on by default."). Round 0 keeps the rubric.

### 7. Graded model answers (a prompt lever, off)

- `match_subjects` and `link_read` answer with a grade (possible, plausible, firm) besides their pick. Judged against a null arm; the proposals seeds, the corpus and the slices re-recorded (about $0.2 a seed set).
- **Ideas beside it** (lever index rows): bands other than the three words for models' output (the owner); the owner's wording against overconfidence ("being 100% confident about anything [...] will be dismissed as delusional"), a perhaps; the judge's numeric confidence as a measured feature.

### 8. Training sets (the owner: "We clearly need some better training sets for analysis")

- **Development data:** seeds 2 to 15, spent for promotion, now development's (with seed 1).
- **A second sealed template of another genre** (schedules or drawings), so held-out checks are by template, not seed; Harbor spent only on a combiner candidate.
- **A model panel on public real pairs** (tentative matches' milestone 13, moved here): each member grades sampled pairs, shown what the read shows plus sections, abouts and crops; agreement reported, disagreements shown; sampled across the probability range so calibration is measured everywhere.
- **Winkler's EM on unlabelled real pairs** for non-match rates: a rater of its own.
- **Built 2026-11-11: the second sealed template** (`proposals.westlake`, `HELDOUT_PAIRS`; Harbor, spent by the combiner's check, moved to `SPENT_PAIRS`): the Westlake convention center against the Lakeshore one, a domain no development template has and a genre of prose (templated paragraphs, a rooms table), its items renamed by role (Hall C the West Pavilion, AHU-3 rooftop unit RTU-2, the options schemes, meeting rooms 101 to 104 breakout rooms 201 to 204, section titles too), the indoor design temperatures not given and a rigging capacity given (3 gaps), and a decoy named as the other's hall (the storage "Hall C", a floor area and a clear ceiling height as the exhibit hall has). Rendered in every format; generated and read only by `controlled.py heldout --sealed`, never seen until a candidate's check spends it.

- **Built 2026-11-12: links in review batches** (the lab's `review sample --links N`, `review judge`, `review links`): two subjects of a comparison's two sources, sampled round-robin over the combiner's probability bands (and the groups joined by name), each side's names, claims (six at most), sections and its first claim's crop and page; blind to the probability and how it was reached. Verdicts: the same, comparable (the owner: "whether two things are the same or at least comparable"), different; fields for kind, function and integration (the owner's families), so the panel's answers label them too. `review links` scores the panel's consensus (Dawid-Skene) against the probabilities: by band, average precision, log loss, calibration. Public real pairs replayed from the slices fixture at no cost: the turbine pair and the drawings pair.
- **First panel, 2026-11-12** (72 links, 36 a pair; gemini-3.1-pro, Qwen3.5-397B, MiMo-V2.6-Pro; $2.05, pilots $0.20): a first pilot found "the same" read as one physical object (two designs' rotors called comparable); each item now says whether its sources are two designs or two revisions, and counterparts are "the same".
  - **Agreement:** verdicts α 0.56 (under 0.667: tentative at best); the same or comparable against different α 0.74; fields: kind 0.70, function 0.68, integration 0.53; flags low (0.00 to 0.44).
  - **Turbines:** the probability ranks "the same" with average precision 0.71 (the same or comparable 0.80); above 0.8, 7 of 9 the same; 0.7 to 0.9 said 0.83, observed 6 of 9. Wrong by consensus: generator speed ~ rotor speed (0.86), the integrated tower ~ the transition piece (0.77); comparable: tower mass ~ the tower, blade-pitch angle ~ blade pitch (an aspect against its thing).
  - **Drawings:** average precision 0.39; above 0.8, 2 of 8 the same. The panel's "different" are right on reading: generic names joined as keys or near them: "sheet" ~ "sheet" (0.96, two sheets), "detail" ~ "detail" (0.80), "component" ~ "component H" (a deck detail against a grid bubble), "A1" ~ "Bedroom Section (A1)".
  - **Calibration on real pairs:** overconfident above 0.6 (development's corpus has few generic names).
  - **Its 72 links are development data now** (re-scored offline after each change, no requests); a held-out check takes a fresh sample without them.
  - **Fixed 2026-11-12: a document's parts' names** ("sheet", "detail", "grid line") no key between proposals, nor names' evidence: "the same" ranked 0.46 to 0.63.

### 9. Weights fitted

- Where the training sets allow: non-match rates from real pairs (the drawings pair showed synthetic ones mislead), match rates from the keys, shrunk toward the hand-set weights (53 matches are too few alone). Held out by template.

### 10. Function and integration, as weighted evidence (tentative matches' milestone 10, redefined 2026-11-12)

The owner, 2026-11-11: "I was thinking more about where a component is used in a system. Not where the section discussing a component appears in a document discussing the component". Designed in the [place review](../research/place-review-2026-11-11.md) and the [system use review](../research/system-use-review-2026-11-12.md).

- **Two families** (the owner: "Two families seems wiser given there's a clear split."; their names: "Perhaps "function" and "integration"", constants in code):
  - **Function:** what a component does and handles: kind, medium, service, arrangement (duty and standby, N+1).
  - **Integration:** where it sits in its system: part of, serves, fed by, feeds, location.
  - Mostly evidence against (media, containers or duties in conflict), agreement weakly for (siblings share every positive cue); "comparable" an answer.
- **Siblings** (the owner: "whether we can compare them one vs. one depends on if they are meaningfully differentiated"): one to one only where both sets are differentiated and their differentiators correspond; otherwise a set-to-set link (count, each unit's range, total and firm capacity, arrangement). Differentiated by function or integration, a stated reason for a size class weighing as function ("looking for that reason as a distinguishing role"), the model's guess less, a tag's letter never.
- **Steps, cheapest first** (bugs first):
  1. **Units of two series not paired by their numbering** (a fix): the model's name groups, its match, the judge's pairings and the tags' spelling.
  2. **A subject split within one source** where its claims carry two containers or two media (a fix: Spruce Lake's "Filters").
  3. **Medium from units** (function): a unit → medium table of its own; logged weighing nothing, each point's share right measured, then weighed by eye.
  4. **Container and kind** from context records and names; **service and targets** from names' modifiers and quotes.
  5. **Sibling sets and set-to-set links:** sets a source by tag series and names' head words (not `indexes.kinds`); a table of document patterns; the kind dossier asked whether a kind's items are interchangeable, quoting the passages (a prompt lever against a null arm, with a trap knob).
  6. **Shown to the model** in `match_subjects` and the read (a prompt lever).
  7. **The second pass's system line,** contested subjects first (a prompt lever).
  8. **One reader rule,** last.
- **Sections:** a weak signal only where a heading names a subject (the owner: "especially when the sections are naming components or subsystems").
- **Measured by:** Spruce Lake's "Filters" ~ "filtration" (0.943) under 0.7 on fresh seeds; the within-source split caught; Birch Hollow's keyed pumps held under 0.35 when their properties are named alike; development's average precision within ±0.005; knobs: siblings told apart by system position alone with sections by discipline, a bank of identical units, a differentiated bank (a jockey pump; north and south intakes), a stated "two duty, one standby", the trap (random values: "not stated"); a schematics proposals pair; the turbine pair by eye.
- **Earlier, place as document position** (2026-11-11, kept at weight 0):
    - **Place by neighbours in document order** (a feature, `links._places`, `_place`; weighing nothing): the controlled PDFs have no outline, so their sections are page ranges with no heading (the gotchas review's item 11), and sections can't say place there. Instead, each subject's neighbours in its document (its claims' middle position: page and line, paragraph or height), and a pair's neighbours whose counterparts (firm groups, keyed pairs) are each other's neighbours.
    - **As evidence** (development's first pass, 11,144 pairs, 0.33 by chance): half or more of them in common 0.56 right; some 0.19; none 0.01 (12 of 861); too few anchors near to say 0.28.
    - **Weighed** (+0.8, −0.6, −2.5; or against only) **it moved nothing** on development (firm 1,834 to 1,942 right, 12 to 16 wrong; average precision ±0.001) or on seeds 16 and 17 (spent; the six development pairs: average precision 0.971 → 0.969 with it, 0.971 against only): siblings share neighbours, so "in common" lifts wrong siblings; and where place would help (Spruce Lake's decoy, its own section), too few anchors are near to say.
    - **Next for place (superseded by the place review):** sections from a PDF's headings where it has no outline (by type size and weight: the lever index's row), so place by sections; or use (milestone 10's other half) as the model's context.

## Later

- Revisions' groups on probability (milestone 6's follow-up).
- Keys within a source (the gotchas review's items 1, 2, 5 and 6): still all or nothing after this.

## Measurement

- **Targets:** average precision and calibration (milestone 2), paired by unit, sign-flip tests as before; level counts guards at most.
- **Development:** seeds 1 to 15, the turbine pair by eye (never a fit's target), the knobs.
- **Held out:** by template (Harbor, then milestone 8's), rules written before they're run.
- **Cost:** milestones 0 to 6 no requests but where a new link set changes the reads; milestone 7 and the panel pennies a pair; estimated first, asked above $5.

## Questions answered

1. **Tentative matches' milestone 11** (link gaps looked for) and 2. **revisions' groups on probability**, asked whether now or later: "We'll wait until after the relevant evidence combo repairs." Milestone 11 after milestone 5; revisions' groups after milestone 6.
