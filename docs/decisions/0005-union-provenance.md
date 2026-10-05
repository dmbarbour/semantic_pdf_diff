# 0005. Union provenance: one claim per fact in a piece of content, every sighting kept

- **Status:** Accepted (2026-09-24)
- **Source:** [evidence store plan: decisions](../plans/sources-and-evidence-store-2026-09-23.md#decisions-2026-09-23) ("Union provenance", amending the completed plan); [store review](../reviews/store-complete-2026-09-24.md) (de-duplication under concurrency)

## Context

The same fact is often read several times: by the text and table passes, by tiles and the overview, and on more than one page. Evidence IDs included the locator, so each sighting was its own evidence, and de-duplication kept whichever copy it saw first. With concurrent tasks, that order varies from run to run.

## Decision

- **A claim is a fact within one piece of content.** Its evidence ID (`models.claim_id`) derives only from the content ID and the claim's identity:
  - entity, attribute, value and conditions, whitespace-normalized and case-folded
  - unit, exactly (`mW` isn't `MW`)
  - `approximate` and basis
- **Where it was found is a set of occurrences:** page, box, pass, task, section, crop, quote, `quote_verified`, confidence and derivation. The quote belongs to the occurrence.
- **Sightings merge** across native and visual passes and across pages of the same content (`models.merge_occurrences`).
- **One representative occurrence** serves displays and model re-checks: native before visual, tile before overview, then the smallest region, then page and task order.
- **Not merged:** claims in different files, which are different content.

## Consequences

- Task order doesn't matter: concurrent and sequential runs give identical evidence, and replay is idempotent.
- Reports say how many times, and by which passes, a claim was found. Agreement between passes is listed, never silent, and counts as a reliability signal.
- Two readings that differ only in their quote are one claim. Readings that differ in a unit's case are two.
- The same fact in two files stays two claims. Comparison and retrieval relate them.
