# 0041. Evidence is combined numerically; nothing is pinned

- **Status:** Accepted (2026-11-11)
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
