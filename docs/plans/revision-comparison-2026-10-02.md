# Comparing revisions: align items, then explain differences

- **Status:** Active (2026-10-02): milestone 1 (research) done. The owner, on the outline: "Looks good! Please do so." The owner answered the plan's four open questions the same day (decisions 6 to 9), and added two points (decisions 10 and 11).
- **From:** [controlled documents](controlled-documents-2026-10-01.md) milestone 4, where every change was found but most "different" findings weren't changes.
- **Depends on:**
  - controlled documents (revision pairs, exact comparison scoring)
  - [multi-format adapters](multi-format-adapters-2026-09-23.md) (`.txt`/`.md` and `.docx`), to read real revision series
  - the [architecture clean-up](architecture-cleanup-2026-10-02.md)'s levers (the `candidates` hook)
- **Why:**
  - **The owner (2026-10-02):** "Any suggestions for improving analysis of differences? I assume we can use some form of multi-pass approach, e.g. establish candidate differences then analyze them by some means for 'why different' with attention to known issues like renamings or context shifts. And I don't have ideas for the second issue other than somehow improving analysis and comprehension of near-tacit entities within a corpus, which is non-trivial."
  - **The measured problem:** on six revision pairs, gemma-4 found 22 of 22 changes and confirmed 198 of 198 unchanged facts, but only 41 of 120 "different" findings were changes.
    - 59 came from names by position ("blower 5", "dimension 2"), which shift when a row is inserted.
    - 17 took two items of a kind for one item changed (two track elements, two revisions' dates, two design options).
    - 3 of 13 additions were paired with a neighbour and called changes.
  - **The cost:** 1,798 pairs judged for six small pairs ($0.247), 854 of them unrelated. Judging pairs one by one doesn't scale to long specifications.

## Goal

- **A revision comparison that reports what changed, and only that:** changes, additions and removals, each explained, with unchanged content confirmed.
- **Correspondence decided cheaply and softly, before any value is judged:** cheap signals, each with a confidence, decide which items correspond across the whole document. The judge sees only what they leave uncertain.
- **Working first, measured systematically later** (decision 7): developed by inspection on controlled revision pairs, then on real revision series; held-out sets and promotion rules come with systematic improvement.

## Today

- **Pairs are chosen by text similarity:** each claim's top 4 by TF-IDF, from either side (`compare.candidates`).
- **A judge sees one pair at a time:** two claims, their crops, and a numeric check. In revisions mode it's told that "corresponding claims describe the same object".
- **The judge decides correspondence and difference at once,** from two claims alone. Correspondence is a question about the whole inventory:
  - whether the helix is new depends on whether the earlier revision has one
  - whether "blower 5" is the same blower in both revisions depends on the tables

## Decisions (2026-10-02)

1. **Items with nothing to anchor them may be misaligned.** The owner: "I think the 'no anchors' risk is acceptable because even a human would definitely get that wrong or just consider it a wholesale replacement of a component."
2. **Repeated values make weak identity, and that's fair.** The owner: "Similar with repeated values risks; fungible things naturally have weak identity even to the human eye."
3. **Overfitting is a risk, met with breadth and held-out sets.** The owner: "I agree this is a risk. It's partially mitigated by trials, but we can increase breadth of samples, too, when we feel there is risk of overfitting, and perhaps support a more robust approach to 'learning' lever promotions with training vs. test sets (though... not sure this applies, but perhaps something analogous applies)." The analogue is design item 5.
4. **Real samples:** the owner: "the samples we have at the moment were from a relatively brief research, IIRC without focus on revisions of the same documents (which should be an easier search), and of course we haven't really touched the docx or pptx samples yet (which will greatly expand our available test samples, IIUC)."
5. **Controlled documents in place of spot checks.** The owner: "I'm hoping these fictional controlled tests with known difficulty knobs will greatly mitigate need for spot checks, so I can focus on findings from actual trials later; those findings become new difficulty knobs."
6. **Correspondence scored softly, researched first.** On Claude's proposal to settle exact matches without a model, the owner: "We should do some research on what can help here, making it more soft/probabilistic/heuristic in nature without fully intelligent. Tools like BM25F or similar might apply, or a weighted mixture of techniques that each can output confidence between 0 and 1. Pairwise analyses of all pairs of things is super-expensive, so if we can use other means and filter it down that's good." (Design item 2; milestone 1.)
7. **No defaults to beat in early development.** On Claude's proposal to keep comparison levers opt-in until a real check, the owner: "For early development, we shouldn't consider any levers defaults like a null hypothesis; just try to get things vaguely somewhat working by eyeball and intuition (or your non-biological equivalent) before we scientifically pursue systematic improvements." (Measures; milestone 7.)
8. **Held-out sets as a rolling window.** On Claude's proposal to retire a held-out series after three checks, the owner: "I think we could use something closer to a rolling window? No need to be too aggressive with retiring tests, so long as the collection is just barely big and mobile enough that specializing/overfitting to them is infeasible or impractical." (Design item 5.)
9. **Proposals mode deferred, not for long.** The owner: "Let's defer proposals comparison mode for a little bit longer, but it is an important use case that we shouldn't defer too much longer, so we should seek opportunities where it begins to make sense to pursue it." (Openings for proposals mode.)
10. **No alignment on a slim margin.** The owner: "if we have a lot of high-confidence counterparts they should also be considered unaligned without model support; this shouldn't be a `0.51 vs. 0.49` decision, for example, or whatever our scoring equivalent turns out to be in context of the noise floor (match `0.81 vs. 0.80`)." (Design items 1 and 2.)
11. **Splits and merges, with one-to-one favoured, not assumed.** The owner: "we could consider splitting/merging to be another viable relationship (and knob to test), so I wouldn't strongly assume 1:1 correspondences or alignments, just favor it heuristically, e.g. two resistors in series could be combined, or one could be split, as a trivial example. Not sure how to approach that, though." (Design items 1, 3 and 7.)

## Design

The mechanisms below are Claude's, built on the owner's multi-pass idea and decision 6.

**1. Items and alignment (revisions mode).**
- **Items:** a revision's claims grouped by the thing they describe.
  - Claims sharing a tag join one item. A tag is an identifier of letters and digits, such as `P-101B`, `V-314`, `D103` or `AHU-3`.
  - Other claims are grouped by their folded entity name.
  - Positional names ("blower 5") are items like any other; alignment sorts them out.
- **Item correspondence is scored** (design item 2), not decided by one rule. The strongest signal for revisions is anchors:
  - A value printed once in each revision (a number with its unit, a date, a length) ties the claims holding it.
  - A value that repeats within a revision is a weak anchor (decision 2).
  - Most facts don't change between revisions (198 of 220 on the controlled pairs), so most items share most of their values. Diff tools anchor on unique unchanged lines the same way.
- **One counterpart is favoured, not assumed** (decision 11): most confident first, an item whose counterpart is settled is less likely to take another. Pairs below a confidence floor stay unaligned.
- **No alignment on a slim margin** (decision 10): when an item's best counterpart isn't clearly ahead of its next, it's ambiguous, however confident both are.
  - "Clearly" is set against the scores' noise floor, measured on the controlled pairs, not fixed in advance.
  - Claude's reading: an ambiguous item isn't aligned mechanically. The judge decides it, as it decides the middle band; without a judge's support it stays unaligned.
  - Prior art: Lowe's ratio test in image feature matching accepts a match only when the best is clearly better than the second best.
- **Splits and merges** (decision 11). Claude's proposed approach, cheapest signals first:
  - **anchors divided:** one item's unchanged values found in two items of the other revision, little overlapping, suggest a split; the reverse, a merge
  - **names related:** a shared tag stem (`P-101` → `P-101A` and `P-101B`), "A/B", "1 and 2", "divided", "combined"
  - **values that add up:** a leftover value equal to the sum of two others of one attribute and unit (two resistors in series; a room divided, its areas summing), tried only on leftovers, two or three terms at a time
  - **structure:** the new items where the old one was (the same table, rows or rooms side by side)
  - A candidate split or merge goes to the "why different" pass (design item 3) to confirm. The report then needs a finding with several members, a change to its schema decided in that milestone.
- **Within an aligned item:** claims are paired by attribute. Leftover values of one attribute are a candidate change (room 102's two widths, once its depth anchors the room).
- **Unaligned items:**
  - one only in the later revision is added; one only in the earlier is removed
  - their claims aren't sent for comparison, so the report lists them without a counterpart, as it lists additions and removals today
  - unaligned items with similar names and no anchors go to the judge as possible renamings
- **Mechanism:** a provider of the `candidates` hook. The hook learns the mode; proposals mode keeps retrieval.
- **Expected** (Claude's inference, to be seen):
  - the 59 positional-name and 17 same-kind differences aren't sent to the judge
  - the 3 additions taken for changes become additions
  - an item whose every value changed under a positional name is misaligned, as decision 1 accepts

**2. Correspondence without a model: cheap signals, each with a confidence (decision 6).**
- **Research first** (milestone 1), then a first version by inspection.
- **Candidate signals,** each a confidence between 0 and 1:
  - **anchors:** values shared once in each revision (design item 1)
  - **fielded lexical similarity:** BM25F over entity, attribute, conditions, quote and section, each field weighted
  - **identifiers:** the same tag; tags renumbered alike (`P-101B` → `P-201B`)
  - **value agreement:** equal after unit conversion (today's numeric check)
  - **structure:** the same heading path, the same table, row label and column header, a nearby place in the reading order
  - **semantic similarity, later:** embeddings ([retrieval recall](retrieval-recall-2026-09-23.md))
- **Combining them:**
  - **Prior art to research:**
    - **probabilistic record linkage:** Fellegi and Sunter weigh each field's agreement by how likely it is among true matches against non-matches, with two thresholds: match, possible match, non-match
    - **the margin between candidates:** Lowe's ratio test (decision 10), and how linkage handles one record matching several
    - **one-to-many matching:** splits and merges in record linkage and in schema matching (decision 11)
    - **blocking:** cheap keys (a tag, an attribute word, a value bucket) so all pairs are never scored
    - **sequence alignment and diff algorithms:** reading order
    - **schema and ontology matching:** attributes named differently
  - **Weights from the controlled pairs:** their exact labels can set the weights, with other pairs held back to check them.
  - **Two thresholds and a margin:**
    - above the upper, and clearly ahead of the next candidate, matched, with equal values settled as equivalent without a model
    - below the lower, not compared
    - between, or above but not clearly ahead (decision 10), the judge decides
- **The risk:** a condition or scope changed in words the claims don't carry. The knob "conditions changed, value kept" shows it.

**3. Explaining differences ("why different").**
- **A second, targeted call** for each "different" or "uncertain" finding and each possible renaming. It's sent:
  - both claims with their quotes, sections and table context, and both crops
  - the alignment's evidence: shared anchors, the signals' confidences, the item's other values
- **A checklist of known confounders:**
  - the same item, renamed or renumbered
  - moved: another section, table or row
  - conditions or scope changed
  - units restated
  - a superseded value printed beside the new one
  - an alternative or option, not the same item
  - a misreading: the value read again from each crop
- **The output is the difference's kind:** a change, a renaming, a move, a restatement, a split or merge, a misreading, not the same item, or other conditions. The report groups differences by kind.
- **Scored exactly:** each revision edit records its kind in the key, so "why" is scored as well as "whether".

**4. Identity at extraction (the owner's "near-tacit entities").**
- **Cheap partial steps first:**
  - readers asked to name a row by its tag and a dimension by what it measures, not by position (the lever index row "names that carry identity")
  - table claims carry the parse's row label and column header ([one table model](one-table-model-2026-09-30.md) overlaps)
  - tags found by pattern near a value
- **A per-document entity register later:** tags, row labels, captions, headings and defined abbreviations, with a model pass only for what's left. Claims would point at register entries.
- **Revisions need this least,** since alignment infers identity from the other revision. Proposals need it most (two designs share no values).
- **Measured** by a new extraction count (claims named by position, per document) and by the pairs' precision.

**5. Development and held-out sets (decisions 3 and 8; milestone 7).**
- **Development is everything looked at while building:** the seed-1 controlled documents and pairs, the development slices, the development real series.
- **Held-out sets are scored only when a change is up for promotion,** against a rule written before the check, as rounds' criteria are. They're drawn from:
  - **fresh seeds of the same pairs:** new values and layouts, nearly free to generate; catch fitting to particular values
  - **held-out knobs:** pairs of kinds built but not scored during development; catch fitting to particular traps
  - **a held-out project, later:** a backup domain (traffic control, district heating, …); catches fitting to the generator's phrasing and layouts
  - **held-out real series**, once real pairs can be read (item 6)
- **A rolling window (decision 8):** the held-out collection keeps just big and mobile enough that fitting to it is impractical.
  - New members join as they're made (controlled seeds cost cents; real series as found).
  - The oldest move into development, gradually rather than by fixed retirement.
- **The same split could serve the controlled stratum in rounds** (controlled documents milestone 5): seed 1 for development, fresh seeds held out.
- **More configurations, more lucky winners:** with several cursors (lever search), held-out confirmation is the guard.

**6. Real revision pairs.**
- **Already fetched, all waiting on adapters** (the product reads only PDFs):
  - QUIC transport Internet-Drafts -00, -20 and -34, and RFC 9000 (`.txt`)
  - 3GPP TS 38.300 v17.0.0, v19.2.0 and v19.3.0 (`.docx`; v19.2 → v19.3 is a small-difference pair; v15.0.0 is a legacy `.doc`)
  - the 3GPP RAN1 #116 moderator's first and last summaries (`.docx`)
- **Raters, none absolute:**
  - **the authors' record:** each 3GPP specification ends with a change history table listing its change requests
  - **a mechanical text diff:** a reported change in an unchanged paragraph is suspect, and a changed paragraph with no reported change a possible miss
  - **model judges** on sampled differences
  - **the owner** on a small sample
- **More series, searched for revisions this time (decision 4).** Likely sources, not yet checked:
  - component datasheets with revision-history sections
  - arXiv papers' versions
  - versioned standards archives
  - regulatory dockets with revised reports
  - Public documents only, as now.
- **Each failure found becomes a knob** (decision 5; controlled documents milestone 6).

**7. New revision knobs,** each edit's kind recorded in the key:
- an item renamed (P-101B → P-201B), its values kept
- rows reordered
- a section moved
- a value restated in other units (gpm as L/s)
- conditions changed, the value kept
- fungible items: many repeated values (door sizes)
- a table split in two
- an item replaced wholesale: the same tag, every value changed (decision 1's case)
- an item split (decision 11): a pump replaced by two smaller ones whose capacities sum to its own; a meeting room divided by a new wall, the two areas summing to about the old one
- items merged (decision 11): two rooms joined by removing a wall; two valves replaced by one
- near-ties: several items alike enough that alignment is ambiguous (decision 10)

## Milestones

1. **Research: correspondence without a model** (design item 2).
   - A research note: record linkage, BM25F, blocking, alignment and diff algorithms, schema matching.
   - For each: what applies to claims and revisions, what it needs, and how its confidence is set.
   - No model spend.
2. **Alignment, a first version,** on the seed-1 pairs (design items 1 and 2).
   - Built from the research, tuned by inspection (decision 7).
   - Edit kinds recorded in the keys.
   - The new knobs (design item 7) added as they're needed.
3. **Real revision pairs,** once the `.txt`/`.md` and `.docx` adapters are built (in their own plan):
   - the QUIC drafts, TS 38.300 and the moderator's summaries
   - the raters above
   - a search for more series
4. **"Why different"** (design item 3).
5. **Identity at extraction** (design item 4), with the one table model plan.
6. **Proposals mode,** when an opening below makes it natural (decision 9).
7. **Systematic improvement:** the rolling held-out window, a promotion rule, and the measures below as gates. When the first versions work by inspection.

## Measures

- **Per pair, exact:**
  - changes found
  - additions and removals found
  - unchanged facts confirmed
  - false changes
  - splits and merges recognised
  - items left ambiguous by the margin, and how the judge decided them
  - the share of "different" findings that are changes
  - with milestone 4, the kinds named right
  - pairs sent to the judge, pairs settled without one, and cost
- **Until milestone 7 these are diagnostics, read by eye** (decision 7). No current behaviour is a default that a new one must beat.

## Openings for proposals mode (decision 9)

Claude's reading of where proposals mode begins to make sense:
- **Once alignment's signals work:** counterparts across two designs can be scored with the same signals, structure and kind standing in for anchors.
- **Once the entity register exists** (design item 4): it's what proposals need most.
- **Once `.docx` and `.pptx` can be read:** two fetched sets are competing proposals.
  - `3gpp-ran1-beam-management`: four companies' contributions on one agenda item
  - `3gpp-rel19-aiml-views`: nine companies' views, in `.pptx`, `.docx` and PDF
- **Controlled proposals:** two fictional designs of one system from the same fact sheet's kinds, with counterparts known. The controlled generator can make them.
- **[Criteria-first comparison](n-way-comparison-2026-09-23.md)** holds the plan for proposals and N-way comparison.

## Costs

| Step | Estimate |
|---|---|
| Milestone 1: research | no model spend |
| Milestone 2: the six pairs compared again, as the first version takes shape | under $0.25 a try, less as fewer pairs reach the judge |
| Milestone 3: real specifications (hundreds of pages each) | dollars; estimated and mentioned before running |
| Milestone 4: a call per candidate difference | cents on the controlled pairs |
| Milestone 5: the controlled corpus read again under the extraction change | estimated before running |
| Milestone 7: fresh seeds for the held-out window | cents each |

## Relation to other plans

- **[Controlled documents](controlled-documents-2026-10-01.md):** its revision pairs and scorer measure this plan; its milestone 6 turns this plan's findings into knobs.
- **[Retrieval recall](retrieval-recall-2026-09-23.md):** BM25 and embeddings are signals here and providers of the `candidates` hook there. For revisions, alignment comes first; for proposals, retrieval.
- **[Criteria-first comparison](n-way-comparison-2026-09-23.md):** proposals and N-way comparison (decision 9).
- **Recognising versions of one document** (plans index): pairs whose order is known; the version signals help find real series.
- **[Multi-format adapters](multi-format-adapters-2026-09-23.md):** `.txt`/`.md` and `.docx` first, which unlock the real series.
- **[Lever index](../reviews/levers.md):** the two rows from controlled documents milestone 4 ("a change needs the same item", "names that carry identity") are built here.

## Not in scope

- **Relations:** schematics' links aren't compared yet (controlled documents milestone 4).
- **Comparing more than two revisions at once.**

## Progress

- **Milestone 1, research (2026-10-02): done.** [Correspondence without a model](../research/correspondence-without-a-model-2026-10-02.md).
  - **Prior art:**
    - Fellegi–Sunter record linkage is the owner's "weighted mixture": signals as log-odds weights, two thresholds, a review band for the judge.
    - Lowe's ratio test is the margin (decision 10).
    - Patience diff and GumTree align containers by shared unique anchors, as design item 1 does.
    - Origin analysis, group linkage and iMAP cover splits and merges (decision 11).
    - BM25F handles fielded names.
  - **Measured offline** on the six pairs, with no model calls (`scripts/alignment_sketch.py`):
    - **Claims scored alone lose changes:** 24 of the 59 claim pairs of changed facts scored as non-matches.
    - **Items first:**
      - the judge gets 47 pairs instead of 1,798, 15 of them false
      - all 22 changes and 198 unchanged facts are covered
      - no pair touches an added or removed fact
      - 408 pairs have equal values, settled without the judge
      - the image reader's "blower 4–6" were left ambiguous by the margin
  - **The design, adjusted by the research:**
    - value disagreement weighs lightly, since values change between revisions
    - correlated signals are merged before weighting
    - the margin is an odds threshold in bits, against the non-match scores' tail
    - greedy best-first rather than optimal assignment
    - no new dependency
  - **Caveat:** the sketches were built while looking at these pairs; development evidence (decision 7).

## Open questions

None at present.
