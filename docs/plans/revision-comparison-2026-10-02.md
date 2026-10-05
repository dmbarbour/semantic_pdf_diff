# Comparing revisions: align items, then explain differences

- **Status:** Active (2026-10-03): milestones 1 (research) and 2 (alignment, a first version) done; milestone 3 (real revision pairs) begun with three pairs (RAN1's feature-lead summaries added 2026-10-04). The owner, on the outline: "Looks good! Please do so." The owner answered the plan's four open questions the same day (decisions 6 to 9), and added two points (decisions 10 and 11).
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
12. **Regroupings shown as the tool sees them (2026-10-03).** On Claude's two options for showing a split or merge (a finding with several members, or a separate section beside the pairwise findings), the owner: "I think b is better. The issue is that regroupings can get messy in general, so there is no clear way to present them always. It's best that the report is honest about how the pdf_semantic_diff is viewing the groupings in these cases."
    - **Claude's reading:** the report gains a section of groupings: how alignment grouped the two revisions' items (matched, renamed, attached, ambiguous, unaligned, and split or merge candidates), each with its evidence and what was then done with its claims (settled, judged, not compared). Candidates are labelled as candidates, found by names and values, not confirmed. Pairwise findings stay as they are.

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
- **From milestone 4's misses** (2026-10-03; the owner: "Regarding the conditions changes and explanations, see if we can extract some difficulty knobs from those for control docs."). Most are on a new base, a link protocol's specification modelled on QUIC's and TS 38.300's confounders:
  - **look-alikes:** a value changed beside its look-alikes (the extended short report's field beside the short report's; the Session ID's maximum beside the Session ID Length field)
  - **list members:** a list's member replaced by another of the same shape, and one added
  - **a numbered condition inserted,** the rest renumbered: a number names a place, not an item
  - **a lead-in's conditions changed:** the sentences under it kept word for word, so the quotes match and the conditions don't
  - **conditions reworded,** meaning the same (on the treatment plant)

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
- **Milestone 2, alignment, a first version (2026-10-02): done.** The owner: "Nice job! Please proceed."
  - **Code:**
    - `align.py`: items, their correspondence, assignment with a margin, claims within items
    - the `align` lever, on for revisions mode; proposals keep retrieval
    - a chosen hook, `correspondence`, through which comparison asks which claims to judge and which are settled
  - **The report:**
    - settled findings are marked "settled without a model"
    - a claim whose item has no counterpart is listed as "unaligned" (possibly added or removed)
    - `retrieval` carries the alignment's summary
  - **How it decides, as built:**
    - **Items** are a tag in the entity, else its words. A claim named by position ("blower 5") joins the tagged item whose values it clearly repeats.
    - **Item pairs** are scored as 0.6 shared values (rare ones counting more), 0.3 name, 0.1 attributes. A name counts only if its identifiers agree: "Room 104" isn't "Room 105", nor "Revision C" "Revision D", nor "Option 1" "Option 2".
    - **Assignment** is best first, needing a margin of 0.15 over the next candidate and a floor of 0.3. Near-ties go to the judge.
    - **Leftover items find a home:** a reader may split one thing into two items, or file three revisions' dates under one. A leftover attaches to the item, or the group of items, uniquely holding most of its values, else to the item of its exact name (decision 11's "favoured, not assumed", in a simple form).
    - **Claims within matched items:**
      - A value's readings form a group: settled if any of them agree on conditions across the revisions (readers phrase conditions differently), judged if none do.
      - The rest pair by attribute, each claim with its best partner.
      - Identifiers and generic words ("dimension 2") don't name an attribute; such claims pair only by value.
  - **On the six pairs** (seed 1, development evidence; recorded and replayed alike):

    | Measure | Before alignment | With alignment |
    |---|---|---|
    | Changes found | 22 / 22 | 22 / 22 |
    | Additions found | 10 / 13 | 13 / 13 |
    | Removals found | 7 / 7 | 7 / 7 |
    | Unchanged facts confirmed | 198 / 198 | 198 / 198 |
    | "Different" findings that are changes | 41 / 120 | 31 / 33 |
    | Pairs judged by the model | 1,798 | 58 |
    | Pairs settled without a model | 0 | 336 |
    | Uncertain findings | 66 | 4 |

    - The two "different" findings that aren't scored as changes are P-101B's real power change, read by the image reader as "blower 2": an extraction naming error.
    - Every pair judged had been judged before or nearly so: $0.0016 of new recordings in all.
  - **Fixed by inspection along the way:**
    - a value inside words ("ROOM 102 ENLARGED") read as the number 102
    - "a" dropped as a stop word, so "valve A" became "valve"
    - one-to-one forced on items a reader had split
    - conditions phrased differently by readers blocking settlements
    - generic attributes pairing a room's width with its depth
  - **Left as they are** (decision 1's kind):
    - three floor plan readings under generic names ("component", "dimension line 2") with no counterpart
    - readings of a changed value under a generic attribute, left unpaired
    - The report lists them as unmatched.
  - **Not yet:**
    - split and merge findings with several members (a report schema change, for the owner)
    - calibrated confidences
    - BM25F; it wasn't needed on these pairs
- **Milestone 2, the first knobs (2026-10-02): four of design item 7's eight.** The owner: "Looks good."
  - **Each revision's key now logs its edits from its base:**
    - kinds: changed, added, removed, renamed, moved, conditions, split
    - read in the comparison's direction, so the scorer can tell a rename from a removal and an addition
  - **Four new pairs, each one knob:**

    | Pair | Edit | What the comparison did |
    |---|---|---|
    | `wtp-tables-s1-clean-renamed` | P-101B renamed P-201B, values kept | Aligned by its values; all 84 facts confirmed, 150 pairs settled, none judged; the summary lists `P-101B → P-201B` |
    | `wtp-tables-s1-clean-reordered` | a valve moved down its schedule across the split tables, a blower up | All 84 confirmed; 5 pairs judged, 145 settled |
    | `wtp-s1-conditions` | the filtration rate now "with all filters in service", the raw turbidity a 99th percentile, values kept | The turbidity judged different; the filtration rate judged uncertain (the product's rule for other conditions) |
    | `wtp-tables-s1-clean-split` | pump P-101C replaced by P-101E and P-101F, their capacities summing to its own | Reported as 4 facts removed and 8 added, the old pump never compared with its parts: split detection isn't built |

  - **A miss, found and fixed:**
    - At first the turbidity's change was settled as unchanged: the readers put the percentile in the attribute ("95th percentile turbidity"), and alignment dropped identifiers from attributes.
    - Attributes whose identifiers conflict no longer fit, unless both are positions ("dimension 1", "dimension 2").
  - **The scorer:**
    - renamed facts scored under one id
    - a conditions change with the value kept classed apart ("settled" is a miss)
    - for each split, whether the old item was compared with its parts
  - **Cost:** $0.054 to read the four revisions and judge their pairs. The six earlier pairs scored as before.
  - **Left:** the other four knobs (a section moved, units restated, fungible items, a table split in two), merges, near-ties, and split detection.
- **Groupings, as alignment sees them (2026-10-03; decision 12).**
  - **The report gains a groupings section:** every group alignment formed (matched, renamed, attached, ambiguous, unaligned, and split or merge candidates), each with:
    - its items' names and claims
    - its evidence (shared values, how the names relate, the candidates' scores, a stem and sums)
    - its outcome: settled, judged by relation, left without a counterpart
  - **It says in so many words that it's alignment's view, not a verdict.** Pairwise findings are unchanged; `report.json` gains `groupings` (empty in proposals mode).
  - **Split and merge candidates** are leftover items whose names share a stem, one on one side and two or more on the other: a tag less its final letter (`P-101C`, then `P-101E` and `P-101F`), or a name's words with its identifiers' leading digits (Room 104, then Room 104A and Room 104B).
    - The evidence lists any attribute whose value is the parts' sum within rounding.
    - Their claims are listed as "regrouped", not compared claim by claim.
    - A model's confirmation of a candidate is left for later.
  - **On the ten pairs,** offline:
    - the split pair's P-101C showed as a split candidate into P-101E and P-101F, its capacity 7,650 = 4,102 + 3,548
    - the renamed pair's P-101B → P-201B showed as renamed
    - no other pair gained a candidate
  - **The scorer** reports for each split how the groupings viewed it.
- **The revision pairs in Markdown (2026-10-03; the adapters plan's milestone 1).**
  - The nine pairs Markdown can carry, compared with alignment.
  - **Every change, addition and removal found; no false change; 0–6 pairs judged per pair.**
  - **Three misses, fixed** (the PDF pairs scored as before):
    - **A condition moved:** one revision's reader put "95th percentile" in the conditions, the other's "99th percentile" in the attribute. Conflicting identifiers anywhere in attribute and conditions now block a settlement.
    - **Synonyms:** "number of inversions" against "inversion count". "Number" and "quantity" fold to "count", and a value each item holds under one property only pairs whatever the attributes are called.
    - **A superseded value beside the new one:** the later revision's "raised from 178 ft" took the old reading, leaving 230 ft unpaired. A leftover reading may now pair with one whose value group went to the judge, under the same attribute.
- **Milestone 3, real revision pairs (2026-10-03): the first two.** The owner: "I agree with the recommended order. No issues with spending a few dollars to get both of these done."
  - **The pairs** (`scripts/real_pairs.py`; measurements in `benchmarks/real-pairs/results.json`):
    - QUIC transport draft-34 against RFC 9000: plain text, the RFC editor's revision of the last draft, mostly editorial
    - 3GPP TS 38.300 v19.2.0 against v19.3.0: Word, a quarter's technical changes
  - **The rater:** a mechanical text diff (`bench/real_pairs.py`), one rater among others.
    - Both files' paragraphs, page furniture dropped, are aligned by difflib.
    - A "different" finding whose claims both sit in unchanged text is suspect.
    - A changed paragraph whose numbers changed, touched by no finding of note and no unmatched claim, is a possible miss.

    | | QUIC draft-34 → RFC 9000 | TS 38.300 v19.2 → v19.3 |
    |---|---|---|
    | Claims, earlier / later | 2,489 / 2,069 | 5,288 / 5,361 |
    | Paragraph groups changed in the text | 308 | 47 |
    | Settled without a model | 1,042 | 4,845 |
    | Judged | 998 | 501 |
    | "Different": in changed text / in unchanged text | 9 / 13 | 9 / 12 |
    | Numeric changes in the text, of them unseen | 32, 15 | 12, 3 |
    | Claims unaligned (possibly added or removed) | 332 | 102 |
    | Claims in matched items left unpaired | 710 | 244 |
    | Cost (extraction, comparison) | $0.52 | $0.59 |

  - **Read by hand:**
    - **TS 38.300's differences in changed text are changes,** one substantive: the UE's LP-WUS monitoring went from "does not monitor" to "monitors LP-WUS regardless of which DRX cycle". The rest are lists of message contents reworded.
    - **The suspect differences are pairing faults:**
      - list members paired with each other (an RA Report's contents)
      - positional attributes ("detection condition 1" against "2")
      - two of a kind (a BSR's "extended short" and "short" formats)
      - one figure read two ways in the two revisions (QUIC's "Connection ID Length" field, 8 bits, against the Connection ID, 0..160)
    - **The unseen numeric changes are references,** not values: a contents page's numbers, "Figures 7 and 8", a new citation's number.
  - **Alignment fixes the real documents called for** (the controlled pairs scored as before, in every format):
    - **Values in words settle like numbers:** case, spacing and punctuation folded. A specification's claims are mostly words, and QUIC's first run sent 1,812 pairs to the judge, 822 of them judged equivalent; then 952.
    - **Claims left over pair by all their words,** best first: statements reworded.
    - **A range or a list is a value in words:** "0..160" had been keyed as the number 0.
    - **A unit written in the value counts:** "63.3 mph" is 63.3 with the unit mph.
    - **A fact filed under another entity in one revision** pairs by its value with the one leftover holding it ("first drop" against "Ridgeback" for the ride's maximum acceleration, met in the Word corpus).
  - **Left open:**
    - list members and positional attributes (the "why different" pass, milestone 4, is where they'd be told apart)
    - claims left unpaired (710 and 244)
    - the rater counting references as numeric changes
- **Milestone 4, "why different" (2026-10-03): a first version.** The owner: "Excellent work! Please proceed with 1. Then we'll work on reading pictures."
  - **The design (Claude's, within design item 3):**
    - **A lever, `explain_differences`** (comparison stage, revisions only, on by default per decision 7): after judging, one more call for each "different" or "uncertain" finding. Settled, complementary and unrelated findings aren't explained.
    - **What the call is sent:**
      - both claims as the judge saw them (empty fields dropped), with their sections and crops
      - the judgment and its rationale
      - whether the two quotes are the same text
      - each claim's item: its other claims in its own revision, up to 8, those naming its attribute first
      - the other revision's claims stating each claim's value, in either claim's item, up to 4, the counterpart itself left out
    - **A checklist** in the prompt (`compare.EXPLAIN`):
      - values the other revision still or already states (members of one list, numbered conditions)
      - nothing stated elsewhere (B replaced A)
      - identical quotes
      - readers' own conditions and numbering
      - names the source gives (95th and 99th percentile)
      - quotes and images supporting their values
      - superseded values
    - **The output** is a kind: changed, conditions, renamed, moved, restated, split_or_merge, misread, not_same_item or unclear, with a rationale. It's recorded on the finding as `explanation`; the judge's relation stays as it was.
    - **The report** counts explained differences by kind in three groups:
      - value changes: changed, conditions
      - editorial changes: renamed, moved, restated, split or merge
      - not changes: misread, not the same item
      - It lists value changes first and filters by kind.
    - **The scorer** (`bench/controlled/comparison.py`) checks each kind against what its claims are per the keys:
      - a changed value: changed
      - a conditions change: conditions
      - the same fact unchanged: an editorial kind
      - two facts' claims: not the same item, or split or merge across a split
      - a misreading: misread
      - Also reported: the share of named value changes that are changes.
    - **`scripts/controlled.py run --unaligned`** compares the PDF pairs again with alignment off, so the explanations meet many non-changes, as before alignment.
  - **Prompt version 2** fixed what version 1 got wrong:
    - The counterpart was among its own value's echoes, so a conditions change looked like two statements side by side. The controlled conditions pair was named "not the same item" 5 times of 6.
    - "Conditions" was named where both revisions quote the same sentence (QUIC 6 times, TS 38.300 3 times): readers attach context of their own.

    | Version 2 | Kinds right | Changes named as value changes | Non-changes named as value changes |
    |---|---|---|---|
    | Controlled pairs, aligned (28 pair runs) | 73 of 76 | 74 of 74 (conditions changes: 5 of 6 named exactly) | 0 of 2 |
    | Controlled PDF pairs, unaligned (10) | 147 of 171 | 46 of 46 | 8 of 125 |

    - **Unaligned:** of the judge's 117 scored "different" findings, 42 were changes (0.36). Of the 54 findings explained as value changes, 46 were (0.85).
    - **The misses:**
      - two facts' claims named "changed": 7 of 89
      - readers' positional numbering with equal values ("dimension 1" against "dimension 2") named "not the same item" rather than restated: 2 aligned, 15 unaligned. It's still not a change.
      - the PDF conditions pair's turbidity (95th then 99th percentile) named "changed"
  - **Real pairs, rated by the text diff:**

    | | QUIC draft-34 → RFC 9000 | TS 38.300 v19.2 → v19.3 |
    |---|---|---|
    | Explained ("different" and "uncertain") | 65 | 64 |
    | Value changes named, in changed text / unchanged text (version 1) | 8 / 2 (5 / 4) | 20 / 3 (17 / 3) |
    | Suspect differences (unchanged text) | 13: 10 not the same item, 1 restated, 1 split, 1 misread | 12: 8 not the same item, 2 changed, 2 split |
    | Not the same item, in changed text / unchanged text | 25 / 14 | 5 / 30 |
    | "Conditions" where the quotes are the same text (version 1) | 3 (6) | 2 (3) |

    - The pairing faults milestone 3 read by hand are named "not the same item":
      - QUIC's Connection ID field against its length field
      - TS 38.300's RA Report list members, detection conditions 1 and 2, the BSR's short and extended short formats
  - **Cost:**
    - version 1: $0.016 (controlled), $0.032 (real pairs)
    - version 2: $0.017 (controlled), $0.034 (real pairs)
    - the unaligned pairs: $0.18, mostly fresh judgments, since the pre-alignment answers no longer matched today's claims
  - **The committed controlled fixture** holds only what its standard runs replay. The unaligned runs' answers stay local, like the real pairs'.
  - **Not done:**
    - confirming split or merge candidates by a model (see the open question)
    - explaining possible renamings: alignment finds renamed items by their values, settles them, and lists them in the groupings
    - reading a misread value again from its crop: the crops are sent and the checklist asks, but there's no separate reading
  - **Left open:**
    - "conditions" named on identical quotes
    - readers' numbering named "not the same item"
    - the rater could count value-change kinds in unchanged text as its suspect measure

- **Knobs from milestone 4's misses, and prompt versions 3 and 4 (2026-10-03).** The owner: "Regarding the conditions changes and explanations, see if we can extract some difficulty knobs from those for control docs."
  - **A new base, the link protocol's specification** (`corpus.link_protocol`, 21 facts), written to the real specifications' confounders:
    - two report formats with nested names
    - a header table with each field beside its length field
    - a report's contents as a list
    - numbered conditions
    - timers whose state is named only by a lead-in sentence
  - **Five pairs** (design item 7), each in PDF, Markdown and Word: look-alikes changed, a list member replaced and one added, a numbered condition inserted, a lead-in's conditions changed, and conditions reworded (on the treatment plant). Recording them cost $0.063.

    | Knob (version 4) | PDF | Markdown | Word |
    |---|---|---|---|
    | Look-alikes: the extended short format's field, the Session ID's maximum | 3 of 3 changes, no false change, each named changed | the same; a short/extended pairing named not the same item | the same; two such pairings named not the same item |
    | A list member replaced, one added | every addition and removal found; 2 unchanged timers named conditions (their readers attached the wrong lead-in) | every addition and removal found, nothing judged | the same |
    | A numbered condition inserted | the new condition found | the new condition paired with an old one, named not the same item (not counted as found) | the same, 4 pairings named not the same item |
    | A lead-in's conditions changed, the sentences kept | missed: settled as no change (the readings' conditions were already wrong), one claim unread | 1 judged, named conditions; one claim unread | 2 of 2 named conditions |
    | Conditions reworded | all settled | all settled | all settled |

  - **Version 3:**
    - a value in words echoes by its numbers ("no acknowledgement received within 856" against "... is received within 856")
    - conditions echo too: whether each claim's conditions are still, or already, stated in the other revision
    - The lead-in knob's Word pair went from not the same item to conditions.
  - **Version 4:**
    - numbers the source gives (conditions, steps) are positions, renumbered when one is inserted
    - identical quotes name conditions only when the conditions were replaced
    - The numbered-condition knob went from changed to not the same item.

    | | Version 2 | Version 4 |
    |---|---|---|
    | Controlled pairs, aligned: kinds right | 73 of 76 (28 pair runs) | 100 of 108 (43, with the knobs) |
    | Controlled PDF pairs, unaligned: kinds right | 147 of 171 (10 pairs) | 189 of 216 (15) |
    | QUIC: value changes named in changed / unchanged text | 8 / 2 | 6 / 3 |
    | TS 38.300: the same | 20 / 3 | 17 / 1 |
    | Suspect differences named changed (QUIC; TS 38.300) | 0; 2 | 0; 1 |

  - **Cost:**
    - version 3: $0.027 (controlled), $0.116 (unaligned), $0.037 (real pairs)
    - version 4: $0.029, $0.076, $0.039
  - **Left open:**
    - **"Conditions" on identical quotes** (QUIC 4). Two readers give the same sentence different context, and a changed lead-in looks the same to the echoes. Telling them apart needs the source text around each claim (its lead-in, its heading) in the explanation's prompt; that's the next step here.
    - **A lead-in's state misattributed** by the PDF readers when two lead-ins share a page: an extraction difficulty the knob now measures.
    - **The scorer counts an inserted condition as found** only when it's left unmatched; paired with an old one and explained "not the same item", it isn't.
  - **The committed controlled fixture** is now written by `scripts/controlled.py pack`: the standard runs replayed against a copy of the working fixture, and only the answers they use packed. Recording no longer packs.
- **A third real pair: RAN1's feature-lead summaries (2026-10-04).** The owner, on the plans review's cheap wins: "Go for the cheap wins!" Milestone 3 named "the moderator's summaries".
  - **The pair:** summary #0 and #3 of RAN1 #116's AI/ML beam management discussion (R1-2401596 and R1-2401599, Word). Each is mostly tables of companies' views, with proposals revised round by round. Read with the Word reader's tables on a grid (the adapters plan, "Merged and nested cells").
  - **What changed between them:** mostly additions, not changes. The rater's text diff finds 13 changed blocks, 66 lines in the earlier summary and 535 in the later: new companies' views and new proposals.

    | | RAN1 #0 → #3 |
    |---|---|
    | Claims | 994 → 1,188 (56 from pictures) |
    | Settled without a model | 803 |
    | Pairs judged | 169 |
    | "Different" findings | 3: two named "not the same item" (two members of one proposal's list of specification support), one "changed" |
    | Numeric changes unseen | 2, both the document's own number and title |

  - **The one named "changed":** for BM-Case2, summary #0 says reporting several past time instances in one report is "not needed"; summary #3's Proposal 8 lists it as a reporting capability. It may be a real reversal of the moderator's proposals; not yet checked against the documents.
  - **Most of the later summary's new claims have no counterpart,** as additions should: 104 not compared, 59 unaligned, 8 without a confirmed counterpart, in changed text.
  - Cost: $0.273 with TS 38.300's re-reading (its equations, the adapters plan).

## Open questions

- **Split and merge confirmation (design item 1's note: "a change to its schema decided in that milestone").** Claude's recommendation:
  - defer it until a pair produces candidates that need a model: the controlled split pair's candidate is right without one, and neither real pair produced a candidate
  - when built, record the confirmation on the grouping, which is already alignment's view (decision 12), rather than add a finding with several members
