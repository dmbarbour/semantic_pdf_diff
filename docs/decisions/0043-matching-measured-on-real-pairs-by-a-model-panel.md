# 0043. Matching is measured on real pairs by a model panel, and held out on fresh ones

- **Status:** Accepted (2026-11-16)
- **Source:** the owner, 2026-11-09: "Not viable for me to mark things [...] But bringing back our panel of judges is something we could try, if we can ensure we provide enough context for their judgements to be meaningful."; 2026-11-11: "We clearly need some better training sets for analysis"; 2026-11-13: "Feel free to bring in a few more sets for training, and search for a few more holdouts as needed."
- **Builds on:** [0018](0018-several-raters-none-ground-truth.md) (several raters, none ground truth), [0019](0019-offline-review-pages.md) (review pages), [0037](0037-levers-judged-paired-and-promoted-held-out.md) (held-out promotion); [evidence combined numerically](../research/evidence-combination-measured-2026-11-16.md), milestones 8 and 9

## Context

- The controlled corpus scores matching exactly, but only its templates: its designs reward names, the judge and the model's pick far more than real documents do, and once its errors were few it could show no further gain.

## Decision

- **Links in review batches:** two subjects of a comparison's two sources, sampled across the combiner's probability, shown blind with their names, claims, sections and crops; a panel of models of other families than the reader's grades them the same (counterparts), comparable or different, with kind, function and integration.
- **The consensus is a rater, not the truth:** Dawid-Skene over the panel; agreement reported; the owner's rulings correct it where it errs on a principle ([0042](0042-counterparts-only-where-differentiated.md)'s numbering).
- **Development and held-out pairs:** public real pairs of the kinds the owner's work resembles (reference turbines' reports, Solar Decathlon drawings), development's panel batches the fit's and the fixes' measure; a change held out on fresh pairs, the rule written before they're recorded; spent pairs become development's.
- **Weights fitted on both:** real links for what real documents say, the controlled corpus beside them at a low weight, shrunk toward the hand-set weights ([0041](0041-evidence-combined-numerically.md)).

## Consequences

- The lab's `review sample --links N [--exclude BATCH]`, `review judge`, `review links`; the ranking measures in `eval/ranking.py`.
- Each held-out check costs a few dollars (recording, three models' judgements); estimated first, asked above five.
