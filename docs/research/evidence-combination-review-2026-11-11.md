# Evidence combination: how levels became rules, and the way back

- **Status:** Reviewed (2026-11-11); for the owner, ahead of a plan.
- **Asked for:** the owner, 2026-11-11, on Claude's questions about milestone 10 ("place lowering a link"): "I'd like you to clarify why you'd consider "place lowering a link" to overrule "plausible link is good" as if the latter was a ruling that overrides the general direction of composing evidence? IIRC, we discussed the possible/plausible/firm distinction as a qualitative rubric for judges localized to a point of evidence, but how we combine things is more numerical, and combining multiple points of evidence into a holistic metric. The way you're describing it here, you missed or lost that point. If this is a misunderstanding or accidental redirection on your part, please review things with yourself and Fable to see where we've gone off track then we'll prepare a plan to get back on track."
- **Done by:** Claude's account first, then Fable (claude-fable-5-1), read-only, checking it against the code and the record; four of Fable's claims checked by Claude (below).
- **Concerns:** [tentative matches](../plans/tentative-matches-2026-11-07.md) (paused at milestone 10), [the same-thing review](same-thing-review-2026-11-09.md), [the gotchas review](gotchas-review-2026-11-09.md).

## The answer to the owner's question

It was Claude's misframing, not the owner's misunderstanding. `links.linked` implements "A plausible link is good" as a floor: a pair keyed alike is plausible "however little else is said". A floor can only be lowered by another rule, so place became an "overrule". In a numeric combination the question doesn't arise: a shared tag is one signed weight, a place that doesn't correspond another, and the pair's standing their sum. The owner's answer was about how much one point of evidence says; Claude wired it as an outcome.

## Claude's account

- **The owner's intent:** possible, plausible and firm grade one point of evidence (a judge's or the model's qualitative confidence about what it was shown); combining points is numerical and holistic (2026-11-07: "start with a three-levels rubric then figure out how to analyze or evidence a fuzzy, weighted, or probabilistic numeric match (Bayesian, BM25, etc.)").
- **What was built:** the three words put on the whole pair, the rubric counting families of evidence (two plausible, one possible) as the combiner.
- **Milestone 6** tried numbers (Fellegi-Sunter weights): passed a held-out check on new seeds of the same templates, failed by eye on the turbine pair (names over-trusted), tied the rubric when refitted with real non-match rates, and was set aside: "on today's signals, the rubric's two families do the work".
- **Since then every lever added rules to the rubric:** caps (values that don't fit, the read's decoy or neither: possible at most), a floor (keyed alike: plausible), splits of firm groups (a rival sharing more properties; no property shared), property gaps counted by families, link gaps and linked values gated on "plausible".
- **Questions to the owner were put as outcomes** ("a plausible link or a possible link?"), and the answers read as rulings.
- **Why:** levels on the pair from the start; milestone 6 set aside; held-out targets counting levels, so rules moving pairs across a band won; each gotcha fixed locally and in binary.

## Fable's second opinion (summarized, its order kept)

### Diagnosis: Claude's account, checked

- **The wrong bullet blamed.** "A level is a view of the evidence" (Fable's, 2026-11-07) is sound: a versioned function of logged evidence; a weight table qualifies. The seed is the bullet beside it, also Fable's: "the level is how well it's evidenced (firm, plausible, possible)", which put the three words on the pair from the first day. Fable owns that.
- **The first real drift is milestone 2's build.** The plan as first committed (e54446b): "hand thresholds on hand weights, by mode. Plausible needs two independent signals." The build kept the second sentence (`len(signals) >= 2`) and dropped the first; the "score" became a tuple of counts used only to order links for the cap.
- **Fable's later reviews pushed toward rules too:** milestone 4's "its sub-answers logged as signals, never a confidence word" argued against eliciting the per-point grade the owner means; the same-thing review's "the two-family rule required of any numbers" rule-ified the weights; the gotchas review's "Softer:" items became three more rule levers (14 to 16).
- **Milestone 6 was set aside by Claude's own bar, not by evidence:** a pre-written rule stopping at a tie (57 of 60 on validation), against the owner's "early development by eye"; Harbor never spent, EM never built, the logistic never measured apart, the thresholds never re-set after the refit.
- **Recoverable from the record, and nobody asked:** "model confidence" in the owner's 2026-11-07 words; decision 0018 (raters' verdicts with confidence, combined as a weighted estimate), cited and never applied; the judge's confidence in every finding (`compare.py`), which `links._paired` discards, counting verdicts by relation only.
- **Claude's account too kind in one more way:** held-out rules written first are sound as discipline, but their targets (counts per band) are part of the problem; and its sketch's "levels become display bands" would reuse the three words for the output, recreating the confusion.

### Other places the drift shows

- **Planned numeric, built as a gate:** milestone 7's "gaps "if one item", ranked by the link's score" built as `if link["level"] != "plausible": continue` (`indexes.if_one_item`), the same in `given_otherwise` and `linked_values`.
- **The product already has a weighted combiner:** `align._score` (values 0.6, names 0.3, attributes 0.1; floor and margin) matches revisions 482 of 483. Proposals got a count of families instead.
- **Continuous signals collapsed before any combiner sees them:** a shared word's rarity, trigram share, cosine and property overlap into one boolean `alike`; properties capped at 3 and verdicts at 2 in `bands()`; `distinct` a boolean contest.
- **The weights arm rule-ified too:** under `link_levels: weights`, `keyed` and the read's pick force plausible, neither in the table.
- **The weights table stale and unchecked:** stamped `candidates/1`, which nothing checks; fitted before `keyed` and `unit_kinds`.
- **Firm grouping all or nothing upstream:** `matched`, `firm_keyed`'s `len(own & q) > max(common, 1)`, `alike()`; links see only the leftovers.
- **The scorer counts by band:** right and wrong per level, no ranking metric, no calibration outside the fit path.
- **Display:** `link_said` names the pair's level, not the points' grades.

### Back on track: the shape

- **Vocabulary:** possible, plausible and firm reserved for per-point grades: the judge's verdict on a claim pair (it has a relation and a confidence), the model's match answer (a graded field to add), the read's pick, decoy or neither. The pair gets a score and a probability, shown with each point's contribution; display bands, if wanted, in other words.
- **Per-point evidence, continuous where code makes it:** a shared word's IDF over the subjects' names; trigram share; cosine; properties in common and the margin over the best rival (in place of `distinct`); value fit as a ratio and unit kind agreeing; place correspondence (milestone 10) as a score; a shared key or other name; the model's match with its grade; the read's pick; the judge's verdicts with their confidence.
- **Combiner:** additive log-odds (the Fellegi-Sunter shape `linkfit.fitted` and `links.scored` already have), each point a signed weight. Negative evidence as weights, not caps: unit kinds differing (strong), magnitudes far apart, the decoy picked (strong), neither (weak), a rival sharing more properties (by margin), place differing (moderate), keyed items sharing no property (moderate), identifiers differing (strong between revisions, mild between proposals).
- **Correlated evidence:** points grouped in families (names, the model's readings, properties, values, the judge, place), combined within a family by maximum or a decaying sum, across families by sum: the two-family rule's soft version, one family's contribution bounded, never a veto. A regularized logistic over family sub-scores later, with more than 53 matches.
- **Hard against soft:** hard only where structural or a cost: one source's two subjects never linked; no chaining; a one-to-one assignment for "the same" on scores with a margin, as `align` does; the link and read caps. Every claim about evidence (identifiers, misfit, decoy, contest, keyed, shared property, place) a signed weight.
- **Firm grouping:** for proposals a threshold on the same pair score plus an assignment margin, so `firm_keyed` consults the score and in time `matched`'s proposals branch folds into the scoring pass: the one real architectural change. Revisions keep the findings-based `matched` (it works).
- **Downstream:** each consumer (link gaps, gaps given otherwise, linked values, topics) takes the link's probability with a threshold setting of its own, ranks by it, and shows the number; `property_alike` gets the same combiner in miniature, a gap dropped at a probability, else "possibly given as X (p)".
- **The turbine failure, read again:** non-match rates from synthetic pairs (fixed once by the real drawings pair: names +6.1 to +2.4), so non-match rates from real pairs as the standing rule; 53 matches too few (the one-property band flipped +5.1 to −1.4 on refit), so hand-set priors with shrinkage toward them; names weighted by IDF continuously ("turbine", shared by dozens, near nothing); held out by template and genre, not seed.

### Keep and unwind (the owner's order: bugs, then architecture, then features)

- **Keep:** `candidates()` as the evidence log; `bands()`' idea, widened; `linkfit` (fit, logistic, calibration, threshold); the scorer's binding; every controlled pair and knob (Birch Hollow, the metric and converted documents, Spruce Lake; Harbor sealed); `link_read` (a per-point grade of the right kind); `unit_kinds` (`measured()` a feature); `property_alike`'s families as features; the commentary log; `linked_values`' display; held-out discipline.
- **Convert, in order:**
  1. *Behaviour-preserving:* every rule's inputs as continuous features in `candidates()`; the judge's confidence and a graded model answer logged; today's levels kept; the recorded reports rebuilt identically (free).
  2. *Behaviour-changing:* a combiner with hand weights tuned first to reproduce today's levels on the recorded reports (a regression check, no requests), then adjusted by eye on the turbine pair and the knobs; floors and caps as weights; `distinct` a margin; downstream gates thresholds on probability.
  3. `firm_keyed` and `other_names_fit` consulting the score (the no-chain guard kept, structural); `matched`'s proposals branch folded in.
  4. Fitted where keys exist, non-match rates from real pairs; weights/1 discarded, not reused.
- **Unwind the words:** `link_said`, the lever index's rows and the plan's milestone tables describe band movements; rewritten as scores once step 2 lands.

### Evaluation without ground truth

- **The method kept, the metric changed:** paired units and sign flips stay; targets: average precision over candidate pairs (the keys as one rater, 0018), log loss and calibration by score band (`linkfit.calibration` moved into the scorer); precision at the display threshold a guard. Null arm: today's rubric as a two-valued score, which the combiner must beat in average precision, not only in counts moved.
- **Held out by template and genre,** not seed (seeds 2 to 15 are spent): Harbor and a second sealed template of another genre, spent only on a combiner candidate; a rolling window after.
- **Per-point grades measured on their own:** the share right by grade for each rater (firm above plausible above possible).
- **A model panel on public real pairs** (milestone 13): each member grades sampled pairs, shown what the read shows plus sections, abouts and crops; agreement reported, disagreement shown, not averaged; the sample stratified by score so calibration is measured across the range. Pennies a pair.
- **Winkler's EM** on unlabelled real pairs for non-match rates (and match rates with hand priors): a rater of its own.
- **A level count** a guard at most, never a target.

### Risks and open questions

- 53 matches are too few to fit: hand priors with shrinkage until the panel gives labels. Acceptable as "early development by eye"?
- A graded model answer changes prompts (`crossmatch`), so proposals' recordings re-record (about $0.2 a seed set).
- Firm grouping on scores touches `indexes.matched`, upstream of gaps and the merged index: the one change that can't start as a lever.
- Which consumers get thresholds of their own, and are they the owner's settings?
- The gotchas review's items 1, 2, 5 and 6 (keys within a source) stay all or nothing after this: a second round.

## Checked by Claude

- **The plan as first committed** (e54446b) reads: "hand thresholds on hand weights, by mode. Plausible needs two independent signals". True.
- **The judge's confidence** is in every finding (`compare.py`'s schema), and `links._paired` counts verdicts by relation only. True.
- **`link_weights.json`** says `"candidates": "candidates/1"`; nothing in `links.py` reads or checks it. True.
- **Milestone 7's plan** says "gaps "if one item", ranked by the link's score"; `if_one_item` gates on "plausible". True.

## Claude, on Fable's opinion

- **Agreed throughout,** including the parts that fall on Claude: milestone 6 was set aside by a bar Claude wrote, and the outcome questions to the owner were Claude's.
- **One addition:** the owner's "A plausible link is good." stays on record as the owner's words; what changes is its reading, a shared tag weighing about what a plausible point of evidence weighs, not a floor on the pair.
- **A plan follows** with the owner (the owner: "then we'll prepare a plan to get back on track"); the shape above is the starting point, not decided.
