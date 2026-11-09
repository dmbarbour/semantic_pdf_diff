# Fitting-together gotchas: all-or-nothing decisions that will bite

- **Status:** Reviewed (2026-11-09); for the owner.
- **Asked for:** the owner, 2026-11-09, after learning that properties were joined across sources only by exact name: "So it seems weighted/fuzzy joining of properties hasn't been done yet, as part of fitting things together. I agree that's a natural part of what we're doing already, to the extent I didn't understand we're treating it separately. We'll also add context of use as something to compare heuristically. Please add a review to find other such elements that might be gotchas for us down the road."
- **Done by:** Fable (claude-fable-5-1), read-only, three of its claims checked by running the functions locally (no requests); summarized here, its ranking kept.
- **Builds on:** [the same-thing review](same-thing-review-2026-11-09.md), [tentative matches](../plans/tentative-matches-2026-11-07.md) (milestones 8 to 13).

## The gotchas, ranked

Ranked by being upstream of links (a wrong firm group, or a key decided within one source, can't be mended later: links only see subjects left alone), unmeasured, and likely on the owner's documents.

1. **Other names chain and ignore disagreement** (`indexes.aliases`): every source's glossary terms and every group of the model's other names are one union-find. Only properties are guarded (`kin`). A term two sources define differently (`indexes.terms` marks it) still joins both meanings, so unrelated items become one firm match "by other names". Softer: other names as a link's evidence with a level, not a key; terms defined differently left out. Measured by a knob planting one abbreviation with two meanings.
2. **Between proposals, a tag or the same words is a firm match** (`indexes.matched`): P-101 in two designs is a numbering habit, not identity; "intake pump" in both, likewise. Firm groups are never looked at again, and give gaps (`given_elsewhere`). Not measured: the controlled pairs rename their items, so the coincidence never happens. Softer: a shared tag or name a strong name signal, firm only with a second family, as links already need. Measured by a knob keeping tags with roles permuted.
3. **Values compare within a small unit table** (`align.value_key`, `values.unit`): any other unit is keyed by its text as written. "1,250 gpm" isn't "1250 gal/min"; 150 psi and 1,034 kPa never meet. A revision that converts units loses the values that revisions are matched by (their score's 0.6), and `links._fits` calls such pairs misfits. Softer: key by unit kind with a richer table. Measured by a revision knob converting a schedule's units.
4. **Holders compared as exact word sets** (`align.holders`, `_holders_differ`): "Nokia" and "Nokia, Nokia Shanghai Bell" differ, so their claims never pair and an attribution can be called changed. Bites on the 3GPP pair. Softer: holders same, overlapping or different.
5. **An item keyed by the first tag in its entity, at extraction** (`align.Side`, `TAG`): "ASTM A36 bolts" is keyed A36; "RFC9001", "SA-516" likewise; "Pump P-101 to clarifier CL-1" is P-101's. Grades and standards become items, and a claim naming two things belongs to whichever comes first. Everything after inherits it. Softer: tags as a signal among a subject's names; a claim naming two tags a relation (milestone 12).
6. **One property, four keys** (`indexes.joined` and `given`: case folded; `links.property_keys`: word sets; `crossmatch`: `fold`): the bug Fable's earlier review found was one such mismatch. Sibling gaps and gaps another source fills still key exactly. Milestone 8 covers properties across sources; the same joiner should serve within a source and among siblings.
7. **Match candidates need a shared word or property name; one direction; first asker keeps** (`crossmatch.candidates`, `asked`, `read`): a subject named with no word in common is never asked, and a contested candidate goes by A to Z, not evidence. Softer: candidates from `links.candidates` (spelling, meaning, the judge's pairings); contests settled by evidence.
8. **Context records paired by exact heading, then position** (`records._keyed`, `changed_records`): one inserted note shifts every pair after it. Softer: assignment with a margin over wording.
9. **Conditions alike or not** (`dossiers.differing`, `align._conditions`, `compare.vetoes`' `same_conditions`): reworded conditions hide a contradiction or block a settle; "missing" and "the same" are one. Softer: same, compatible, different, unknown.
10. **Kinds from the name alone, properties joined at a count** (`indexes.kind_of`, `_joins`, `JOIN_ITEMS`): siblings' gaps rest on them. Softer: membership with a level; the model's regrouping a signal, not an override.
11. **Place will be empty where it's needed most** (`sections.pdf_sections`): a PDF without an outline falls back to page ranges with no heading path; drawings and scans have none. Milestone 10's place family needs a section source for them, or it scores on the templates (which have outlines) for the wrong reason.
12. **Thresholds set by eye on few documents:** `align`'s FLOOR, MARGIN, PAIRING, JOINING, WORDING; `links`' RARE, NAME_SHARE, SPELLED, MEANING and RERANKED (the turbine pair alone), FIT, LINKS; `indexes.OTHER_CLAIMS`; the judge's 0.7. None swept. Cheapest: a sweep of each on the recorded controlled reports (no requests), reporting where results plateau.
13. **The scorer shares the assumptions** (`comparison._matching`'s `most()`): a subject is scored by its majority item, so a wrong merge one item dominates scores right; `_items` maps facts by exact entity. Tighten it with item 2, or firm errors stay invisible.

## Patterns

- **Identity decided once, upstream, by exact keys** (1, 2, 5, 6): the entity read → its key → other names → matched. Links see only the leftovers; milestones 8 and 10 add evidence to links, neither revisits firm groups or keys within a source.
- **Several definitions of "the same name"** (6 to 9): case folded, `fold`, word sets, trigrams. One names layer with levels would serve all.
- **Unit tables apart** (3): the product's, the scorer's, the search's; `value_key` uses the smallest.
- **Booleans where levels are needed** (4, 9, 10): holders, conditions, kinds.
- **Covered by the plan:** 6 across sources (milestone 8), sections and use (10, with 11's caveat), relations (12), raters for real documents (13). **Not covered:** 1 to 5, 8, 9, 12, 13.

## Not to worry about

- Links never chained; `LINKS` a view over `candidates()`: deliberate, evidence kept.
- `kin`'s guard; readings clustered against a representative: against chaining by design.
- The judge's vetoes erring to "uncertain"; `_conflict`'s identifier rule; `Terms.named` requiring one meaning: conservative and cheap.
- Tags as keys within one revision: strong identity in one document; the problem is across designs (2) and tags that aren't equipment (5).
- Topics: browsing only, nothing downstream.

## Fable's first three, as levers

1. **Firm matches between proposals need two families** (2, with 1): a shared tag, name or other name a signal; firm only with a second (the judge's pairings, the model's match, distinct properties). Null arm: today's. Held out on a knob keeping tags across designs. First, since property joins inherit the groups.
2. **Values keyed by unit kind** (3): a revisions lever changing no request; measured on a units-converted knob, and `_fits`' misfits on the proposals pairs.
3. **Other names as evidence, terms defined differently left out** (1), with the scorer's `most()` tightened (13) so both show.

## Claude's note on order

Milestone 8 (properties fitted together) goes ahead as the owner approved: it isn't blocked by firm groups, since on today's controlled pairs firm groups are right, and its measure (the gap scorer's buckets) sees properties, not groups. Fable's three come next as milestones of their own, each with its knob built first, then the rest of 8 to 13. Every gotcha not yet covered has a row in the [lever index](../reviews/levers.md).
