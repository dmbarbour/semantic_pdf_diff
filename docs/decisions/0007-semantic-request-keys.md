# 0007. Recorded answers keyed by request meaning and an interpreter fingerprint

- **Status:** Superseded by [0009](0009-content-addressed-queries.md) (2026-09-28)
- **Source:** [test models plan: assessment](../plans/test-models-and-record-replay-2026-09-24.md#assessment), [decisions 2026-09-25](../plans/test-models-and-record-replay-2026-09-24.md#decisions-2026-09-25) and [2026-09-28](../plans/test-models-and-record-replay-2026-09-24.md#decisions-2026-09-28); [store milestone 2 review](../reviews/store-m2-sqlite-store-2026-09-24.md); [meta-audit](../reviews/meta-audit-2026-09-28.md); [content-addressed queries](../plans/content-addressed-queries-2026-09-28.md)

## Context

The response cache first keyed on the full request bytes: prompt text, image bytes and settings. Any incidental change, such as a PyMuPDF rendering difference or a chunking change, would have turned every recorded answer into a miss, so recordings would rarely replay.

## Decision

- **The store's response cache was keyed by meaning** (store milestone 2, 2026-09-24):
  - extraction: role, region, content, task, a hash of the input text, and the crop's specification (content, page, rectangle, scale) rather than its PNG bytes
  - comparison: a hash of the comparison settings and the two evidence IDs
  - the hash of the request bytes stored with each entry; the `cache_check` setting raised on a mismatch
- **Fixtures used the same key plus an interpreter fingerprint** (2026-09-25): prompts and output-shaping settings, without the model (the responder stood for it) or library versions.

## Consequences

- Incidental byte changes no longer invalidated answers. But whatever the key left out could serve a stale answer:
  - Keys were kept in step with prompts by hand. A lever that added a prompt slot needed its own key suffix: the chart rules nearly weren't keyed, the tile locator's thumbnail never was, and table numbers were keyed without reaching the model.
  - The fingerprint held every lever, so a variant re-asked everything (round r01 was voided, $10).
  - Comparisons keyed by claim IDs kept serving old answers after claims were reworded. Re-keying found 105 stale.
- Superseded on 2026-09-28 by queries keyed by what reaches the model ([0009](0009-content-addressed-queries.md)).
- Answers were carried over by replaying under both keys. The semantic keys, the fingerprint, `cache_check` and the re-keying code were removed on 2026-09-30; they remain in git history.
