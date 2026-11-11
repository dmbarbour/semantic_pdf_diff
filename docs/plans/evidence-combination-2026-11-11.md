# Evidence combined numerically: grades per point, a probability per pair

- **Status:** Active (2026-11-11; the owner: "I've reviewed and don't see anything obviously wrong. Please get started."). Milestone 0 built 2026-11-11.
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

### 2. A scorer that ranks and calibrates (the lab, before any combiner)

- **`comparison._matching`** gains average precision over candidate pairs, log loss, and calibration by probability band (`linkfit.calibration` moved in), the keys one rater (0018).
- **A null arm:** today's levels as a two-valued score (plausible high, possible low, no link lowest), which a combiner has to beat in average precision.
- **Level counts** kept as guards at most, never a target (the targets of milestones 4 to 16 counted levels: part of the drift).

### 3. The combiner, hand-set (a lever, off)

- **Signed weights per point,** families bounded (a family's points by maximum or a decaying sum), a prior, the probability clipped away from 0 and 1. Set by eye (the owner: "hand-set weights adjusted by eye"), checked by milestone 2's measures on seeds 1 and 8 to 15 (development now), on the turbine pair and on the knobs (Birch Hollow, the metric pair, Spruce Lake).
- **Tuned to the keys' right outcomes,** not to today's levels: reproducing the rubric would re-encode it.
- **A decision record** when it lands: evidence combined numerically, nothing pinned.

### 4. Rules into weights, numbers shown

- **The caps, floors and splits** (link_tests' misfit, link_read's decoy or neither, keyed_links' floor and contest, other_names_fit's split, `distinct`) become weights; `property_alike` the same combiner in miniature.
- **Shown:** `link_said`, the Subjects view and index.md say a probability and each point's contribution.

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
