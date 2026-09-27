# Duplicate claims: where they come from

- **Date:** 2026-09-27
- **Prompted by:** round 3. In every variant, judges penalized repeated values and the same fact under two entity names.
- **Data:** the champion's extraction on the development slices (`benchmarks/runs/r03/baseline`, 3,125 claims).

## Findings

**About a third of claims have a near-duplicate on the same page.** A near-duplicate has the same number and unit, and its attribute shares a word. The measure is loose: it also catches distinct facts such as "Door D1 identifier 1.02" and "Window W2 identifier 1.02".

| Kind | Claims | Near-duplicates | Share |
|---|---|---|---|
| Text | 534 | 94 | 18% |
| Table | 285 | 98 | 34% |
| Visual | 2,306 | 802 | 35% |
| **All** | **3,125** | **994** | **32%** |

**Nearly all come from different readings of the same place, not from one answer.**
- Within one task: 160 near-duplicate sightings.
- Across tasks: 1,219.

| Pair of regions | Near-duplicate sightings |
|---|---|
| Overview and tile | 312 |
| Overview and text | 166 |
| Tile and tile (overlap) | 162 |
| Figure and tile | 155 |
| Text and tile | 116 |
| Figure and overview | 64 |
| Overview and table | 57 |

**Why they don't merge.**
- A claim's identity is its exact entity, attribute, value, unit and conditions, after case and whitespace folding.
- Two readings of one fact rarely agree word for word: "handrails / material / 2x4 cedar" and "handrail / material/dimension / 2x4 cedar".
- Only identical wordings become occurrences of one claim.

**It matters beyond judging:**
- Reports list the same fact several times.
- Comparison pays for each copy.
- Agreement between independent readings is evidence of a correct reading. Today it is thrown away; it is the same signal the "repeated readings" lever would buy with extra requests.

## Options

1. **Reconcile sightings mechanically.** On one page, claims with equal normalized value and unit whose entity and attribute match after light normalization become occurrences of one claim, keeping every wording. Normalization means singular forms, splitting "material/dimension", and dropping stopwords.
   - Cheap and deterministic.
   - Risk: merging distinct facts that share a value (D1 and W2). Guard with the quotes' positions: sightings must overlap in the page region they came from.
2. **Reconcile with the model:** one request per page listing its claims and asking which state the same fact.
   - Better at paraphrase, but costs about +1 request per page, and the answers are themselves non-deterministic (recorded, like any answer).
3. **Read less twice:**
   - Scope the overview to page-level facts: titles, legends, relations between parts. It currently re-reads everything the tiles read.
   - Tell visual tasks which facts the text layer already yielded.
   - Cuts cost as well as repeats, but a second reading is also a check, and scoping loses it.
4. **Leave the evidence alone and group at presentation:** reports and judges see facts grouped by value, and comparison aligns them anyway. Nothing changes in the data model.

**Recommendation:** option 1 as a lever, with the position guard, and the number of agreeing sightings kept as a corroboration count. Then try option 3's overview scoping separately. Option 1 changes what counts as "one claim" in the evidence model (identity and occurrences), so it needs the owner's review before it becomes a default.
