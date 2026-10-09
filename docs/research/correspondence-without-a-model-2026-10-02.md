# Correspondence without a model

- **Date:** 2026-10-02
- **For:** the [revision comparison plan](../plans/revision-comparison-2026-10-02.md), milestone 1.
- **Asked by:** the owner: "We should do some research on what can help here, making it more soft/probabilistic/heuristic in nature without fully intelligent. Tools like BM25F or similar might apply, or a weighted mixture of techniques that each can output confidence between 0 and 1. Pairwise analyses of all pairs of things is super-expensive, so if we can use other means and filter it down that's good." Also the owner's margin rule and splits and merges (the plan's decisions 10 and 11).
- **Method:**
  - **Primary sources,** read by three research agents: record linkage and blocking; BM25F, the ratio test and assignment; diff, alignment and schema matching. Each reference below was opened, or checked against Crossref where the publisher blocks fetching.
  - **Offline measurements** on the six controlled revision pairs' recorded comparisons (`scripts/alignment_sketch.py`, removed 2026-10-08 as superseded by the align lever; in git history from `fbb1d9d` back), with no model calls. Two claims correspond when the extraction scorer binds both to the same fact of the key.

## Summary

- **Decide correspondence between items first, and between claims only within aligned items.** Mature diff tools all work this way: unique anchors first, then containers judged by the anchors they share, then fuzzy leftovers, then moves, renames and splits found among what's left.
- **On our six pairs, an items-first sketch sends the judge 47 pairs instead of 1,798.**
  - It still covers all 22 changes and all 198 unchanged facts.
  - It sends no pair touching an added or removed fact, so all 20 additions and removals would be reported as such.
  - Another 408 pairs have equal values and need no judge.
- **Scoring claims alone fails on exactly what a diff is for.** With signals combined claim by claim, 24 of the 59 claim pairs of changed facts scored as non-matches. A changed value has only its names to go on; its item's unchanged values are what identify it.
- **The owner's "weighted mixture of techniques" has a classic form:** Fellegi–Sunter record linkage.
  - Each signal's agreement adds log2(m/u) bits of evidence; the bits sum.
  - Two thresholds give match, non-match and a "possible match" band for clerical review. Our judge is the clerk.
- **The margin rule (decision 10) is Lowe's ratio test.** A gap in bits between the best counterpart and the next is a posterior odds ratio, so the margin can be set as odds.
- **Splits and merges have no library.** Prior art for a post-pass over leftovers:
  - origin analysis and group linkage (one old item's claims covered by two new ones)
  - iMAP (a new value as the sum of two or three old ones)
- **No new dependency is needed** for a first version: pure Python at these sizes. Splink is the reference design.

## What our six pairs show

**Today:** 1,798 pairs judged. They held 488 of the 550 claim pairs that truly correspond; each fact still had some pair among them.

**Single signals, claim by claim:**

| Signal | Pairs it links | Of them true | Note |
|---|---|---|---|
| A value with its unit, printed once in each revision | 161 | 154 | Covers only 154 of 491 true unchanged pairs: readers repeat a value, so "once" must count items, not claims |
| Any equal value | 699 | 423 | Repeated values (door sizes, chart values misread alike) |
| A shared tag | 719 | 275 | Tags identify items, not claims: P-101A's capacity and head share one |
| Today's TF-IDF, best candidate | – | right for 309 of 322 earlier claims | The margin over the next candidate fell under 0.05 on 4 |

**Signals combined claim by claim** (Fellegi–Sunter weights from the other five pairs, each pair scored once):

| Pair | Sure (posterior ≥ 0.95): true / all | To the judge (0.05–0.95) | Changed facts' claim pairs scored as non-matches |
|---|---|---|---|
| `wtp-s1` | 33 / 33 | 41 | 1 / 5 |
| `coaster-s1` | 28 / 28 | 27 | 1 / 7 |
| `wtp-tables-s1-clean` | 182 / 341 | 316 | 5 / 11 |
| `lcc-s1-traps` | 22 / 22 | 21 | 0 / 3 |
| `lcc-energy-s1-clean` | 19 / 56 | 188 | 0 / 5 |
| `lcc-plan-s1-clean` | 159 / 194 | 289 | 17 / 28 |

- Perfect where names are clear. Weak under positional names and repeated values, where signals that overlap (entity, tag, TF-IDF) were counted as if independent and grew overconfident.
- Changed values lost: 24 of 59 of their claim pairs scored as non-matches, so they would read as one removal and one addition.

**Items first** (an item is a tag, else the folded entity name):
- **Aligning items:** by dice over shared values, rare values counting more, greedily with a margin.
- **Pairing claims within an aligned item:** equal values first, then attribute and conditions, best first.

| Pair | Items aligned | Ambiguous | Equal values | To judge (false) |
|---|---|---|---|---|
| `wtp-s1` | 14 of 15 | 0 | 32 | 7 (2) |
| `coaster-s1` | 11 of 12 | 0 | 26 | 6 (2) |
| `wtp-tables-s1-clean` | 28 of 32 | 6 | 118 | 5 (1) |
| `lcc-s1-traps` | 13 of 14 | 0 | 19 | 3 (0) |
| `lcc-energy-s1-clean` | 9 of 9 | 0 | 35 | 9 (4) |
| `lcc-plan-s1-clean` | 21 of 22 | 0 | 178 | 17 (6) |

- **Every changed and unchanged fact** had a true pair among them, and no pair touched an added or removed fact.
- **The 6 ambiguous items were the image reader's "blower 4–6".** Their names point one way and their values another, so the margin left them for the judge (decision 10).
- **The 15 false pairs to judge:**
  - "n/a" cells
  - a material claim paired with a capacity
  - chart values the text reader bound to the wrong month
  - a dimension named only "dimension 1" paired with an area

**Caveats:**
- The sketches were built while looking at these six pairs. They're development evidence, which decision 7 allows for now; held-out pairs come later.
- "True" rests on the extraction scorer's binding of claims to facts.
- The controlled PDFs have no outline: each page is one section, so structure (heading paths) couldn't be tried.
- One seed, one sample per query.

## Prior art and what transfers

**1. Probabilistic record linkage** (Fellegi and Sunter [1]; Winkler [3]).
- **Weights:** m = P(agree | match), u = P(agree | non-match). Agreement adds log2(m/u), disagreement log2((1−m)/(1−u)), and the weights sum.
- **Thresholds:** links above an upper threshold, non-links below a lower one, "possible links" between for clerical review. For given error bounds this gives the smallest review band.
- **Estimating m and u:**
  - With labels: m from labelled matches, u from random pairs. Our controlled pairs' keys are labels.
  - Without labels: EM over the match/non-match mixture, which can settle on the wrong split [3]. One document pair (about 60 matches) is too little; pool across pairs.
- **Term frequency:** a rare value's agreement counts more. P(agree on value v | non-match) ≈ the value's frequency on each side. Splink caps it with a minimum u [5].
  - Winkler's warning fits us exactly: a name seen once in each of two small lists isn't a link without corroboration [3].
- **Independence:** the model assumes signals are independent given match status. Ours overlap (a quote contains the entity and value), so merge correlated signals into one comparison or scores grow overconfident. Our claim-level sketch shows this.
- **Changing records** ("Linking temporal records" [13]): values legitimately change over time, so disagreement on a changing attribute should decay in weight, not count fully against a match. For revisions that's the point: penalise value disagreement lightly, or changed items fall out.

**2. Fielded similarity: BM25F** (Robertson, Zaragoza and Taylor [19]; Robertson and Zaragoza [20]).
- **Mechanism:** each field's term frequency, weighted and length-normalised, is summed into one pseudo-frequency, saturated once, then multiplied by IDF.
- **Why one saturation:** summing per-field BM25 scores "can lead to a dangerous over-estimation of the importance of the term" [21]. A word repeated across a claim's fields should count once.
- **Parameters:** 0.5 < b < 0.8 and 1.2 < k1 < 2 are "reasonably good in many circumstances" [20]. For one- to five-word fields, b near 0.
- **Fit:** fields entity, attribute, value with unit (one token), conditions, heading, quote; small integer weights. Score both directions (BM25 is asymmetric).
- **Scores aren't probabilities** [20]:
  - Dividing by the best score is "just as meaningless as dividing by pi" [22]; a removed claim's best candidate would still score 1.
  - Normalising by self-match, s(a,b)/√(s(a,a)·s(b,b)), clipped at 1, is usable.
  - A logistic fit is better (item 8).
- **Implementations:** no Python library does BM25F.
  - Lucene has the simple form, one b for all fields [23]; Terrier, a b per field (Java) [24].
  - bm25s and rank_bm25 handle one field.
  - About 50 lines is simplest.
- **With tens of claims per item, IDF is coarse.** Measure BM25F against today's TF-IDF before relying on it.

**3. Blocking: never scoring all pairs** (Christen [9]; Papadakis et al. [10]).
- **Standard keys:** an attribute word, a unit, a tag's stem, a value. Also sorted neighbourhood (document order is a natural key), canopy clustering, MinHash LSH.
- **Two measures:**
  - pairs completeness: true pairs kept, of all true pairs
  - reduction ratio: pairs not scored, of all pairs
- **For us the funnel matters more than the arithmetic:**
  - 32,830 claim pairs on these six pairs are cheap to score mechanically
  - what costs is the judge; measure completeness (true pairs reaching a sure match or the judge) and reduction (pairs settled without it)
  - audit a sample of discarded pairs with the judge
- **Real specifications** (thousands of claims) need blocking in front of item scoring: an index on tags, values and attribute words.

**4. Margins and ambiguity** (Lowe [8]; Conneau et al. [14]).
- **Lowe's ratio test:** accept the nearest neighbour only if its distance is under 0.8 of the second nearest's. It removed 90% of false matches and under 5% of correct ones.
- **Why it works:** a global threshold fails because items differ in distinctiveness. The runner-up estimates the density of false matches near each item, a per-item noise floor (the owner's "0.81 vs. 0.80").
- **In log-odds terms,** with one true candidate, the posterior odds that the best is right rather than the runner-up are 2^(w1 − w2). The margin is an odds threshold, set against the measured noise.
- **Caveat:** the runner-up must be a different object. A split's two halves are legitimate co-winners, not ambiguity, so they go to the split pass rather than the margin.
- **Mutual nearest neighbours,** and CSLS's correction for "hubs" (claims near everything, such as boilerplate) [14], are cheap extra filters.

**5. Assignment: one counterpart favoured** (Jaro [2]; Sadinle [4]).
- **Two approaches in the sources:**
  - Jaro solves a linear sum assignment and thresholds the pairs it assigns: the most likely one-to-one matching under independence. In Python: `scipy.optimize.linear_sum_assignment` [18].
  - With one symmetric score and no ties, greedy best-first gives the stable matching [15].
- **Optimal assignment's flaw:** it can trade one sure pair for two mediocre ones. Greedy with a margin is simpler and explains itself.
- **Leaving items unassigned:** pad the cost matrix with a threshold cost (the `lap` library's cost limit [16]); an item is then assigned only if its cost is under the threshold.
- **Reporting ambiguity:** an assignment's regret (the total lost if a pair is forbidden) flags fragile pairs.

**6. Splits and merges** (decision 11).
- **No record linkage or diff library detects them.** Each tool that handles them does so in a post-pass over leftovers:
  - **origin analysis** ranks leftover deleted and new items against each other; an original may survive and split part off [11]
  - **group linkage** tests whether two new records together cover an old one [12]
  - **RefactoringMiner** matches in stages that loosen, and finds an extracted method when an old method's statements make up most of a new one [25]
- **Sums and concatenations:** iMAP searches a deliberately small space (concatenation; add, subtract, multiply or divide two columns), checked against shared data [26]. For us: a new value as the sum of two or three leftovers of one attribute and unit, checked against the item's unchanged values.
- **Conservation:** the Census records how tracts split ("205 becomes 205.01–.03") with the overlapping areas [17]. Our analogues: capacities that sum, tags with a shared stem (`P-101` → `P-101A`, `P-101B`).

**7. Diff and alignment tools.**
- **Patience diff** (Cohen [27]) takes the longest common subsequence of lines unique on both sides, then recurses between them. Heckel (1978) used the same anchors to find moved blocks [28].
  - A line unique on both sides is almost surely the same thing; spurious matches come from repeated lines.
  - That's our "a value printed once in each revision".
- **Git:**
  - Histogram diff falls back to the rarest common element.
  - `-M` pairs a deletion with an addition at 50% similarity or more (a rename).
  - `--color-moved` finds moved blocks [29].
  - Renames and moves among leftovers transfer directly.
- **GumTree** (Falleri et al. [30]) maps the largest identical subtrees top-down. It then maps containers whose descendants share anchors (dice over 0.5) bottom-up.
  - A mapped node under a new parent is a move; a new label is a rename.
  - Its dice is what the items-first sketch uses. It pairs "blower 5" with "blower 6" by their claims, whatever their names.
- **daff** (tabular diff [31]) aligns rows without keys by trying subsets of the most distinct columns as a composite key, then marks rows outside the longest in-order runs as moved. A row survives edits while any untouched subset of its fields stays unique.
- **Word and DeltaXML** detect moves, but report an edited move, or a move between a table and prose, as a deletion and an insertion. None reports splits or merges [32].
- **Schema matching:**
  - COMA combines matchers by aggregation (max, average, weighted) and selection (threshold, max-N, max-delta) [33]; max-delta keeps near-ties, where splits hide.
  - Similarity Flooding lifts a pair when its neighbours match [34], which would carry runs of renumbered rows.

**8. Calibration and the noise floor** (Niculescu-Mizil and Caruana [35]).
- **Platt scaling** (a logistic fit) beats isotonic regression below a few hundred to a thousand calibration cases. Our weights are already log-odds, so a logistic fit is natural.
- **Thresholds:** the upper threshold is the lowest score meeting a precision target; the lower, where the miss rate meets its target. The band between is the judge's budget.
- **The noise floor:** fitting the tail of non-match scores needs no labels (Sariyar et al. fit a generalised Pareto [36]), and that tail is the noise floor for the margin. With few labels, pool across document pairs.

**9. Libraries.**

| Library | What it offers | Licence | Fit |
|---|---|---|---|
| Splink [5] | Fellegi–Sunter with comparison levels, term frequency, EM, blocking rules, charts; runs in-process on DuckDB | MIT | Heavy for us (fixed columns, SQL comparisons); the reference design |
| recordlinkage [6] | pandas-native comparisons, ECM on binary features | BSD-3 | Light, quiet since 2023 |
| dedupe [7] | active learning; joins one-to-one, many-to-one, many-to-many | MIT | The judge could be its labeller |
| scipy `linear_sum_assignment` [18] | optimal assignment | BSD | Only if greedy proves wrong |
| GumTree, RefactoringMiner, daff [30, 25, 31] | tree, refactoring and table diff | LGPL-3, MIT, MIT | Designs to copy, not code to use |

## Recommendation for milestone 2

1. **Items:** a tag, else the folded entity name; table rows and headings once real documents provide them.
2. **Item correspondence as log-odds evidence,** Fellegi–Sunter style:
   - **shared values:** dice, rare values counting more (term frequency), positive evidence only, since values change
   - **names:** the same tag; a similar name; BM25F over the item's names
   - **attributes:** the overlap of the two items' attribute sets
   - **structure:** where headings exist
   - correlated signals merged into one comparison; value disagreement penalised lightly
3. **Assignment:** greedy best-first, one counterpart favoured.
   - A pair is accepted only when it leads its runner-up by a margin in bits, set against the measured noise floor.
   - Ambiguous items go to the judge (decision 10).
   - Optimal assignment, if ever, only inside ambiguous groups.
4. **Claims within an aligned item:**
   - equal values settle as equivalent without the judge (checked by the "conditions changed, value kept" knob)
   - then attribute and conditions, best first
   - leftovers of one attribute are candidate changes, for the judge
5. **Leftover items:** additions and removals, then a post-pass for:
   - renames: leftovers similar enough (git's `-M`), or tags renumbered alike
   - splits and merges: values covered by two items, sums of two or three, tag stems
6. **Confidence:**
   - weights from the controlled pairs' labels, pooled
   - a logistic calibration
   - thresholds from precision and miss-rate targets
   - the margin from the non-match tail
7. **No new dependency:** pure Python at these sizes. Adding scipy for optimal assignment would be an architecture question, raised if greedy fails.
8. **Measured as a funnel:**
   - pairs settled without the judge
   - true pairs reaching a sure match or the judge
   - the judge's false pairs
   - ambiguous items
   - a judged sample of discarded pairs

## What this doesn't settle

- **Real documents:** long specifications with boilerplate values repeated across sections, and real headings. The controlled pairs have neither.
- **Equal values settled without the judge:** a condition changed in words the claims don't carry would pass as unchanged. The knob measures it.
- **Proposals mode:** two designs share few values. Names, kinds and structure must carry correspondence, and the same log-odds framework would weigh them.

## References

1. Fellegi and Sunter, "A Theory for Record Linkage", JASA 64, 1969. https://doi.org/10.1080/01621459.1969.10501049
2. Jaro, "Advances in Record-Linkage Methodology as Applied to Matching the 1985 Census of Tampa, Florida", JASA 84, 1989. https://doi.org/10.1080/01621459.1989.10478785
3. Winkler, "Matching and Record Linkage", Census research report RR93/08, 1993. https://www.census.gov/content/dam/Census/library/working-papers/1993/adrm/rr93-8.pdf
4. Sadinle, "Bayesian Estimation of Bipartite Matchings for Record Linkage", JASA 112, 2017. https://arxiv.org/abs/1601.06630
5. Splink. https://github.com/moj-analytical-services/splink ; term frequency: https://moj-analytical-services.github.io/splink/topic_guides/comparisons/term-frequency.html
6. recordlinkage. https://github.com/J535D165/recordlinkage
7. dedupe. https://docs.dedupe.io/en/latest/API-documentation.html
8. Lowe, "Distinctive Image Features from Scale-Invariant Keypoints", IJCV 60(2), 2004. https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf
9. Christen, "A Survey of Indexing Techniques for Scalable Record Linkage and Deduplication", TKDE 24, 2012. https://doi.org/10.1109/TKDE.2011.127
10. Papadakis et al., "Blocking and Filtering Techniques for Entity Resolution: A Survey", CSUR 53, 2020. https://arxiv.org/abs/1905.06167
11. Godfrey and Zou, "Using Origin Analysis to Detect Merging and Splitting of Source Code Entities", TSE 31, 2005. https://plg.uwaterloo.ca/~migod/papers/2003/wcre03-tseVersion.pdf
12. On et al., "Group Linkage", ICDE 2007. https://pike.psu.edu/publications/icde07.pdf
13. Li et al., "Linking Temporal Records", PVLDB 4, 2011. https://www.vldb.org/pvldb/vol4/p956-li.pdf
14. Conneau et al., "Word Translation Without Parallel Data", 2018. https://arxiv.org/abs/1710.04087
15. Abraham et al., "The Stable Roommates Problem with Globally-Ranked Pairs", 2008. https://eprints.gla.ac.uk/150599/1/150599.pdf
16. lap (linear assignment with a cost limit). https://github.com/gatagat/lap
17. Census tract relationship files, explanation. https://www2.census.gov/geo/pdfs/maps-data/data/rel2020/tract/explanation_tab20_tract20_tract10.pdf
18. SciPy, `linear_sum_assignment`. https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linear_sum_assignment.html
19. Robertson, Zaragoza and Taylor, "Simple BM25 Extension to Multiple Weighted Fields", CIKM 2004. https://doi.org/10.1145/1031171.1031181
20. Robertson and Zaragoza, "The Probabilistic Relevance Framework: BM25 and Beyond", 2009. https://www.staff.city.ac.uk/~sbrp622/papers/foundations_bm25_review.pdf
21. Zaragoza et al., "Microsoft Cambridge at TREC-13: Web and HARD tracks", 2004. https://trec.nist.gov/pubs/trec13/papers/microsoft-cambridge.web.hard.pdf
22. Lucene wiki, "Scores As Percentages". https://cwiki.apache.org/confluence/display/LUCENE/ScoresAsPercentages
23. Lucene, `CombinedFieldQuery`. https://lucene.apache.org/core/9_12_0/sandbox/org/apache/lucene/sandbox/search/CombinedFieldQuery.html
24. Terrier, BM25F. https://github.com/terrier-org/terrier-core/blob/5.x/modules/core/src/main/java/org/terrier/matching/models/BM25F.java
25. Tsantalis et al., "Accurate and Efficient Refactoring Detection in Commit History", ICSE 2018. https://users.encs.concordia.ca/~nikolaos/publications/ICSE_2018.pdf ; https://github.com/tsantalis/RefactoringMiner
26. Dhamankar et al., "iMAP: Discovering Complex Semantic Matches between Database Schemas", SIGMOD 2004. https://homes.cs.washington.edu/~pedrod/papers/sigmod04.pdf
27. Cohen, "Patience Diff Advantages", 2010. https://bramcohen.livejournal.com/73318.html
28. Heckel, "A Technique for Isolating Differences Between Files", CACM 1978. https://doi.org/10.1145/359460.359467
29. git-diff documentation. https://git-scm.com/docs/git-diff
30. Falleri et al., "Fine-grained and Accurate Source Code Differencing", ASE 2014. https://hal.science/hal-01054552/document ; https://github.com/GumTreeDiff/gumtree
31. daff. https://github.com/paulfitz/daff
32. Word `CompareDocuments`: https://learn.microsoft.com/en-us/office/vba/api/word.application.comparedocuments ; DeltaXML moves: https://docs.deltaxignia.com/xml-compare/latest/detecting-and-handling-moves ; Draftable on Word's compare: https://www.draftable.com/draftable-legal-blog/draftable-legal-vs-microsoft-word-compare-legal-document-comparison
33. Do and Rahm, "COMA: A System for Flexible Combination of Schema Matching Approaches", VLDB 2002. https://www.vldb.org/conf/2002/S17P03.pdf
34. Melnik et al., "Similarity Flooding", ICDE 2002. https://dbs.uni-leipzig.de/files/research/publications/2002-1/pdf/icde2002-sf.pdf
35. Niculescu-Mizil and Caruana, "Predicting Good Probabilities with Supervised Learning", ICML 2005. https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf
36. Sariyar et al., "Controlling False Match Rates in Record Linkage Using Extreme Value Theory", JBI 44, 2011. https://pubmed.ncbi.nlm.nih.gov/21352952/
