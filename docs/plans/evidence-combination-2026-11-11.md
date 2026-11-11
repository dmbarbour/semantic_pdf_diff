# Evidence combined numerically: grades per point, a probability per pair

- **Status:** Active (2026-11-11; the owner: "I've reviewed and don't see anything obviously wrong. Please get started."). Milestones 0 to 4 built 2026-11-11.
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

### 6. Firm groups between proposals on the score

- **`indexes.matched`' proposals branch** joins where the pair's probability passes the merge threshold, an assignment with a margin as `align` does; a shared key a strong point (near 0.8 alone), a contest weighing against it. The owner: "Not only is it okay, I'm pretty sure it's necessary."
- **Architectural, so not a lever at first; the exception recommended:** the old path kept behind a setting until milestone 2's measures pass on development and held out, then removed.
- **Revisions later:** their findings-based groups carry a probability too (nothing pinned), the findings the dominant evidence; after proposals.

### 7. Graded model answers (a prompt lever, off)

- `match_subjects` and `link_read` answer with a grade (possible, plausible, firm) besides their pick. Judged against a null arm; the proposals seeds, the corpus and the slices re-recorded (about $0.2 a seed set).
- **Ideas beside it** (lever index rows): bands other than the three words for models' output (the owner); the owner's wording against overconfidence ("being 100% confident about anything [...] will be dismissed as delusional"), a perhaps; the judge's numeric confidence as a measured feature.

### 8. Training sets (the owner: "We clearly need some better training sets for analysis")

- **Development data:** seeds 2 to 15, spent for promotion, now development's (with seed 1).
- **A second sealed template of another genre** (schedules or drawings), so held-out checks are by template, not seed; Harbor spent only on a combiner candidate.
- **A model panel on public real pairs** (tentative matches' milestone 13, moved here): each member grades sampled pairs, shown what the read shows plus sections, abouts and crops; agreement reported, disagreements shown; sampled across the probability range so calibration is measured everywhere.
- **Winkler's EM on unlabelled real pairs** for non-match rates: a rater of its own.

### 9. Weights fitted

- Where the training sets allow: non-match rates from real pairs (the drawings pair showed synthetic ones mislead), match rates from the keys, shrunk toward the hand-set weights (53 matches are too few alone). Held out by template.

### 10. Place and use, as weighted evidence (tentative matches' milestone 10)

- Sections matched across sources (headings, abouts, the groups already in them) as a place point; a subject's use (sections, kind, role words, conditions) as the model's context. Spruce Lake's baseline: the reader already carries place into names; place's work is the links resting on the judge alone (150 of 197 wrong on seeds 12 to 15) and the contested tags.

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
