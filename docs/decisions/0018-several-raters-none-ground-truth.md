# 0018. Quality is judged by several raters, none of them ground truth

- **Status:** Accepted (2026-09-25; restated 2026-09-28)
- **Source:** [evaluation benchmarks plan: decisions 2026-09-25](../plans/README.md#retired); [evaluation s01 review](../plans/README.md#retired); [quality without ground truth](../research/quality-without-ground-truth-2026-09-28.md); [benchmarks README](../../benchmarks/README.md); [content-addressed queries](../plans/README.md#retired), milestone 6, and architecture clean-up, milestone 6d (judgement records)

## Context

The project needed accuracy numbers for extraction, retrieval and comparison, but no single labeller is reliable on engineering documents. A person tires and misses things, and a model judge has its own blind spots. Treating any one of them as the truth would hide their errors.

## Decision

- **Several reviewers label independently:** the owner, Claude in a session, and a panel of hosted models from different families (the first: gemini-3.1-pro, Qwen3.5-397B, Kimi-K3). The model under test doesn't judge its own work.
- **Nobody is ground truth.** The owner, 2026-09-28, after a person's per-claim marks were called an "absolute measure": no rater is ground truth, humans included. People are probably better raters than the cheapest judges, but still raters (as the research note's preface paraphrases it).
- **Agreement is measured** (Krippendorff's α: 0.80 and above reliable, 0.667–0.80 tentative), and disagreement is kept as information, not resolved away.
- **Each label is a verdict, then flags** from a taxonomy drawn from published error analyses (entity and scope binding first). Each also records its **clarity** (clear, context insufficient, source illegible, item ambiguous) and the reviewer's **confidence**, so that faults in the question are told apart from faults in the answer.
- **Exact keys are raters too.** The controlled corpus's generated keys score extraction exactly on its own documents, but only on them ([controlled documents](../plans/controlled-documents-2026-10-01.md), the owner's idea).

## Consequences

- Quality figures are estimates per rater and per set, reported with their uncertainty. They're never called absolute or "gold".
- **Every rater's answers are judgement records of one shape** (the lab's `eval/judgements.py`, 2026-09-30): a rater and its kind (a model judge, a person, or a mechanical check), a question, a target, an answer, and a status with its attempts. The quote check is such a rater: is each claim's quote on its page, as extraction's quote matching reads it? A heuristic, weighed as one.
- **Verdict files keep their own layout,** read through one adapter, so rounds can be re-decided from them alone. Since 2026-10-02 each carries its rubric: a file judged under one rubric isn't added to under another, and a unit's verdicts under two rubrics are refused (a mid-round rubric change went undetected before).
- Combining raters into one weighted estimate, each weighted by its estimated reliability, is the tentative *Weighted quality estimates* plan ([plans index](../plans/README.md)).
- Reviewing costs agreement work: a contested item (consensus below 0.8) is discussed. Clarity flags often show that the item or rubric is ambiguous, not that a reviewer erred.
