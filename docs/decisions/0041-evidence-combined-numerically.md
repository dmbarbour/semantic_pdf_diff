# 0041. Evidence is combined numerically; nothing is pinned

- **Status:** Accepted (2026-11-11; amended 2026-11-16, when [its plan](../plans/evidence-combination-2026-11-11.md) closed)
- **Source:** the owner, 2026-11-11: "we discussed the possible/plausible/firm distinction as a qualitative rubric for judges localized to a point of evidence, but how we combine things is more numerical, and combining multiple points of evidence into a holistic metric." And: "nothing should ever be pinned at 0% or 100% if we're using Bayesian analysis. Perhaps firm group is only 80% without corroborating evidence."
- **Builds on:** [0018](0018-several-raters-none-ground-truth.md) (no rater is ground truth), [0037](0037-levers-judged-paired-and-promoted-held-out.md) (levers judged paired, promoted held out); [the evidence combination review](../research/evidence-combination-review-2026-11-11.md) and [its plan](../plans/evidence-combination-2026-11-11.md)

## Context

- [Tentative matches](../plans/tentative-matches-2026-11-07.md) put possible, plausible and firm on the whole pair and combined evidence by rules: families counted (two plausible, one possible), then caps, a floor and splits added lever by lever; firm groups all or nothing. The owner's answers about one point of evidence were wired as outcomes.
- The review (Claude, then Fable) traced it to milestone 2's build, which kept "plausible needs two independent signals" and dropped "hand thresholds on hand weights".

## Decision

- **A grade belongs to one point of evidence:** possible, plausible or firm as a judge or a model gives it about what it was shown. Models' grades are qualitative; their numeric self-confidence isn't trusted (the owner: "100% confidence about 90% of the time"). Embeddings' and cross-encoders' scores are numeric evidence.
- **A pair's standing is a probability:** each point a signed weight in log-odds, a family's points for decaying and bounded (no family decides alone), points against summed, a prior; never 0 or 1. Evidence that follows from other evidence (siblings' values and the judge's pairings; what a key put before the judge and the read) counts less or nothing.
- **Negative evidence is a weight,** not a cap; hard rules only for scope and cost (no chaining; how many links and reads).
- **Levels are thresholds on the probability,** shown with the number and each family's part; firm is a threshold too, carrying its probability (proposals' firm groups next: the plan's milestone 6).
- **Weights are hand-set and adjusted by eye first** (the owner), checked by ranking and calibration (average precision, log loss), never by counts moved across a level; fitted when training sets allow.
- **Thresholds are Claude's,** set by analysis of development's distributions, then by measurement (the owner: "You'll be the one tuning things based on measurement and initially by analysis.").

## Consequences

- `link_levels: combined` (`links.contributions`, `links.combined`, `combined/1`): a lever, off until held out by template.
- The rules of milestones 4 to 16 become weights as consumers move onto the probability (the plan's milestones 4 to 6).
- The lab's scorer ranks and calibrates (`comparison._ranking`); level counts are guards at most.

## Amended 2026-11-16, as built

- **On by default:** `link_levels: combined` since 0.63.0 (the owner: "D1. Yes, turn it on by default."): levels are cuts on the probability (plausible 0.6, possible 0.35), proposals' firm groups join at 0.7, and linked values, link gaps and topics take a link by its probability.
- **Weights fitted, then held out** (`link_fit`, on by default since 0.69.0; the owner: "We'll turn it on by default."): a multiplier a point on its hand-set weight, fitted on real pairs a model panel judged ([0043](0043-matching-measured-on-real-pairs-by-a-model-panel.md)) with the controlled corpus beside them at a low weight, shrunk toward the hand-set weights; the families, caps, decay and prior unchanged. Real pairs read the model's pick and the judge's pairings as far weaker evidence than synthetic ones do; fitted on real links alone, the weights lost the controlled corpus's ranking, so the two are fitted together.
- **Models' grades not used:** asked of the read of a link (`read_grades`, off), a grade split right picks from wrong no better than a field carrying nothing, so a model's own grade isn't a point of evidence (the owner had doubted it: "I simply doubt the ability of models to judge or emit a real confidence score").
- **Function and integration** (the owner's two families, 2026-11-12) start with the medium a subject handles (`links.FUNCTION`); what tells two designs' components apart or matches them is [0042](0042-counterparts-only-where-differentiated.md).

