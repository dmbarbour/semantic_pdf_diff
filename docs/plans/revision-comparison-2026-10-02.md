# Comparing revisions: align items, then explain differences

- **Status:** Planned (2026-10-02), for the owner's review. The owner, on the outline: "Looks good! Please do so."
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

## Goal

- **A revision comparison that reports what changed, and only that:** changes, additions and removals, each explained, with unchanged content confirmed.
- **Most false differences gone without a model:** decide which items correspond across the whole document, not pair by pair.
- **Every step measured exactly** on controlled revision pairs, confirmed on pairs held out from development, then on real revision series.

## Today

- **Pairs are chosen by text similarity:** each claim's top 4 by TF-IDF, from either side (`compare.candidates`).
- **A judge sees one pair at a time:** two claims, their crops, and a numeric check. In revisions mode it's told that "corresponding claims describe the same object".
- **The judge decides correspondence and difference at once,** from two claims alone. Correspondence is a question about the whole inventory:
  - whether the helix is new depends on whether the earlier revision has one
  - whether "blower 5" is the same blower in both revisions depends on the tables

## Decisions (2026-10-02)

1. **Items with nothing to anchor them may be misaligned.** The owner: "I think the 'no anchors' risk is acceptable because even a human would definitely get that wrong or just consider it a wholesale replacement of a component."
2. **Repeated values make weak identity, and that's fair.** The owner: "Similar with repeated values risks; fungible things naturally have weak identity even to the human eye."
3. **Overfitting is a risk, met with breadth and held-out sets.** The owner: "I agree this is a risk. It's partially mitigated by trials, but we can increase breadth of samples, too, when we feel there is risk of overfitting, and perhaps support a more robust approach to 'learning' lever promotions with training vs. test sets (though... not sure this applies, but perhaps something analogous applies)." The analogue proposed is design item 5.
4. **Real samples:** the owner: "the samples we have at the moment were from a relatively brief research, IIRC without focus on revisions of the same documents (which should be an easier search), and of course we haven't really touched the docx or pptx samples yet (which will greatly expand our available test samples, IIUC)."
5. **Controlled documents in place of spot checks.** The owner: "I'm hoping these fictional controlled tests with known difficulty knobs will greatly mitigate need for spot checks, so I can focus on findings from actual trials later; those findings become new difficulty knobs."

## Design

**1. Items and alignment (a lever, revisions mode).**

The design below is Claude's, built on the owner's multi-pass idea.

- **Items:** a revision's claims grouped by the thing they describe.
  - Claims sharing a tag join one item. A tag is an identifier of letters and digits, such as `P-101B`, `V-314`, `D103` or `AHU-3`.
  - Other claims are grouped by their folded entity name.
  - Positional names ("blower 5") are items like any other; alignment sorts them out.
- **Anchors:** a value printed once in each revision (a number with its unit, a date, a length) ties the claims holding it.
  - A value that repeats within a revision is a weak anchor, counted only for items already aligned on others (decision 2).
  - Most facts don't change between revisions (198 of 220 on the controlled pairs), so most items share most of their values. Diff tools anchor on unique unchanged lines the same way.
- **Item alignment:** item pairs are scored by shared anchors and name evidence (the same tag is strong, a similar name weak). Then each item gets at most one counterpart, strongest pairs first.
- **Within an aligned item:** claims are paired by attribute. Leftover values of one attribute are a candidate change (room 102's two widths, once its depth anchors the room).
- **Unaligned items:**
  - one only in the later revision is added; one only in the earlier is removed
  - their claims aren't sent for comparison, so the report lists them without a counterpart, as it lists additions and removals today
  - unaligned items with similar names and no anchors go to the judge as possible renamings
- **Mechanism:** a lever on the `candidates` hook, off by default.
  - With it on, the judge sees only aligned pairs and possible renamings.
  - The hook learns the mode; proposals mode keeps TF-IDF.
- **Expected** (Claude's inference, to be measured):
  - the 59 positional-name and 17 same-kind differences aren't sent to the judge
  - the 3 additions taken for changes become additions
  - an item whose every value changed under a positional name is misaligned, as decision 1 accepts

**2. Exact matches settled without a model (a lever).**
- **What's settled:** claims in aligned items with the same attribute, value, unit and conditions are equivalent.
  - The report shows each such finding as settled mechanically.
  - Today each costs a model call; unrelated pairs, most of today's calls, vanish with alignment.
- **The risk:** a condition or scope changed in words the claims don't carry. The knob "conditions changed, value kept" measures it.

**3. Explaining differences ("why different", a lever).**
- **A second, targeted call** for each "different" or "uncertain" finding and each possible renaming. It's sent:
  - both claims with their quotes, sections and table context, and both crops
  - the alignment's evidence: shared anchors, the item's other values
- **A checklist of known confounders:**
  - the same item, renamed or renumbered
  - moved: another section, table or row
  - conditions or scope changed
  - units restated
  - a superseded value printed beside the new one
  - an alternative or option, not the same item
  - a misreading: the value read again from each crop
- **The output is the difference's kind:** a change, a renaming, a move, a restatement, a misreading, not the same item, or other conditions. The report groups differences by kind.
- **Scored exactly:** each revision edit records its kind in the key, so "why" is scored as well as "whether".

**4. Identity at extraction (the owner's "near-tacit entities").**
- **Cheap partial steps first:**
  - readers asked to name a row by its tag and a dimension by what it measures, not by position (the lever index row "names that carry identity")
  - table claims carry the parse's row label and column header ([one table model](one-table-model-2026-09-30.md) overlaps)
  - tags found by pattern near a value
- **A per-document entity register later:** tags, row labels, captions, headings and defined abbreviations, with a model pass only for what's left. Claims would point at register entries.
- **Revisions need this least,** since alignment infers identity from the other revision. It matters most for proposals mode (two designs share no values), which is out of scope here (open question 4).
- **Measured** by a new extraction count (claims named by position, per document) and by the pairs' precision.

**5. Development and held-out sets (the train/test analogue, decision 3).**
- **Development is everything looked at while building a lever:** the seed-1 controlled documents and pairs, and the development slices.
- **Held-out sets are scored only when a lever is up for promotion,** against a rule written before the check, as rounds' criteria are:
  - **a fresh seed of the same pairs:** new values and layouts, nearly free to generate; catches fitting to particular values
  - **held-out knobs:** pairs of kinds built but not scored during development; catches fitting to particular traps
  - **a held-out project, later:** a backup domain (traffic control, district heating, …); catches fitting to the generator's phrasing and layouts
  - **a held-out real series**, once real pairs can be read (item 6)
- **A held-out set wears out with use:** each check leaks a little of it into decisions. Controlled sets are refreshed with a new seed for each check; real held-out sets as new samples arrive (open question 3).
- **The same split could serve the controlled stratum in rounds** (controlled documents milestone 5): seed 1 for development, a fresh seed held out.
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

## Milestones

1. **Alignment, developed on the seed-1 pairs.**
   - The lever (design item 1).
   - Edit kinds recorded in the keys.
   - Per pair, beside today's measures: pairs sent to the judge, and cost.
2. **The held-out check:** a fresh seed of the six pairs and the new knobs' pairs (design item 7), each scored first here, against a rule written beforehand.
3. **Exact matches settled without a model** (design item 2), measured the same way.
4. **Real revision pairs,** once the `.txt`/`.md` and `.docx` adapters are built (in their own plan):
   - the QUIC drafts for development, TS 38.300 v19.2 → v19.3 held out, and the moderator's summaries
   - the raters above
   - a search for more series
5. **"Why different"** (design item 3), scored against the edit kinds.
6. **Identity at extraction** (design item 4), with the one table model plan.

## Measures and promotion

- **Per pair, exact:**
  - changes found
  - additions and removals found
  - unchanged facts confirmed
  - false changes
  - the share of "different" findings that are changes
  - with milestone 5, the kinds named right
  - pairs sent to the judge, and cost
- **A rule proposed for comparison levers,** on the held-out pairs:
  - no lost change, addition, removal or confirmation (exact counts, against the default)
  - the share of "different" findings that are changes rises
  - Real pairs, once readable, must be no worse by their raters.

## Costs

| Step | Estimate |
|---|---|
| Milestone 1: the six pairs compared again with alignment | under $0.25 (fewer calls than today's $0.25) |
| Milestone 2: a fresh seed (12 documents read, then compared with and without the lever) and the knob pairs | about $0.5–1 |
| Milestone 3: exact matches settled | cents, and fewer calls after |
| Milestone 4: real specifications (hundreds of pages each) | dollars; estimated and mentioned before running |
| Milestone 5: a call per candidate difference | cents on the controlled pairs |
| Milestone 6: the controlled corpus read again under the extraction lever | estimated before running |

## Relation to other plans

- **[Controlled documents](controlled-documents-2026-10-01.md):** its revision pairs and scorer measure this plan; its milestone 6 turns this plan's findings into knobs.
- **[Retrieval recall](retrieval-recall-2026-09-23.md):** BM25 and hybrid retrieval are other providers of the same `candidates` hook. For revisions, alignment comes first; for proposals, retrieval.
- **[Criteria-first comparison](n-way-comparison-2026-09-23.md):** proposals and N-way comparison, out of scope here.
- **Recognising versions of one document** (plans index): pairs whose order is known; the version signals help find real series.
- **[Multi-format adapters](multi-format-adapters-2026-09-23.md):** `.txt`/`.md` and `.docx` first, which unlock the real series.
- **[Lever index](../reviews/levers.md):** the two rows from controlled documents milestone 4 ("a change needs the same item", "names that carry identity") are built here.

## Not in scope

- **Proposals mode:** counterparts across two designs (open question 4).
- **Relations:** schematics' links aren't compared yet (controlled documents milestone 4).
- **Comparing more than two revisions at once.**

## Open questions

1. **Settling exact matches without a model** (design item 2) saves most calls, at the risk of a condition changed in words the claims don't carry. Claude recommends building it as a lever, off until the "conditions changed, value kept" knob has measured it.
2. **Promoting a comparison lever before real pairs can be read:**
   - Option a: keep it opt-in until milestone 4's real check.
   - Option b: make it a default on held-out controlled evidence alone.
   - Claude recommends option a. The controlled documents' rule says a controlled gain alone never promotes a lever; comparisons aren't judged on real documents yet.
3. **Wearing out held-out sets:** a fresh controlled seed for every promotion check, and a real held-out series retired after three checks? Claude's proposal; the number is a guess.
4. **Proposals mode later,** under criteria-first comparison, or sooner? Asked 2026-10-02; not yet answered.
