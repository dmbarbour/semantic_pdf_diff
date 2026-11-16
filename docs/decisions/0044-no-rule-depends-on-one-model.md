# 0044. No rule depends on one model

- **Status:** Accepted (2026-11-16)
- **Source:** the owner, 2026-11-13: "I'd prefer not to depend on any embedding model in particular, just as we don't depend specifically on gemma-4. But if you want an example, any of those would do."
- **Builds on:** [0034](0034-endpoint-checked-and-calibrated-on-first-use.md) (no model assumed), [0012](0012-temperature-zero-and-model-neutral-defaults.md) (model-neutral defaults)

## Context

- Role phrases compared by meaning helped two embedding models of three and hurt the third (an absolute cosine cutoff fits one model's scale; e5's models expect prefixes).

## Decision

- **Rules on a model's output are relative** (ranks, a run's own percentiles, mutual likest), or calibrated per run; never an absolute cutoff tuned on one model.
- **A model-dependent feature is measured with two models or more** before it's built; a lab arm may name a model, the product's defaults don't.
- **An optional model degrades to nothing:** without an embedding model or a reranker, their evidence is absent, not guessed.

## Consequences

- Role phrases by meaning weren't built; the names' meaning link (`links._meaning`, an absolute cosine) is to be made relative (the lever index's row).
