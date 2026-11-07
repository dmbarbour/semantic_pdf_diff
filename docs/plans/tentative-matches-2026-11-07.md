# Tentative matches: hypotheses with levels, their evidence kept

- **Status:** Planned (2026-11-07). [Design questions](#design-questions) 1 to 3 answered 2026-11-07; 4 and 5 open.
- **The owner, 2026-11-07,** after [single-document analysis](single-document-analysis-2026-10-28.md)' milestone 7 (subjects across documents) was built: "I suspect we might want to support weaker, plausible or tentative matches in some way, for our reports, analysis, etc.. Any ideas on that? Match candidates by meaning might help, but I think we probably first need a viable model for "possibly relevant or a match, not sure, investigate further and see if things fit when tied together" instead of all-or-nothing."
- **The owner, answering Claude's suggestion (2026-11-07):**
  - "Three levels is a start. Outside of embeddings and cross-encoders, it's difficult to turn model confidence into numbers. Perhaps we start with a three-levels rubric then figure out how to analyze or evidence a fuzzy, weighted, or probabilistic numeric match (Bayesian, BM25, etc.). I'd like a review from Fable on our ideas here and suggestions to improve them."
  - On whether plausible matches feed the merged index and its gaps: "It should feed links and topics for now, until we're confident in our tooling and we have a good idea on how to index with weighted relationships. Exploring those options should be a plan step."
  - On tying a match together and testing it with the model: "For stage 2, I'm ambivalent, let's just adapt the normal levers approaches perhaps."
- **Reviewed** by Fable (claude-fable-5-1), 2026-11-07, at the owner's request; its suggestions are folded in below, marked "(Fable)".
- **Takes over** the tentative row of the same name (2026-11-07).
- **Builds on:** milestone 7's matching (`indexes.matched`, `crossmatch.py`, `look_gaps`); alignment's item scores ([0038](../decisions/0038-revisions-aligned-then-differences-explained.md); `align._score`, its floor and margin); the search's embeddings and reranker (`embed`, `rerank`); levers judged paired and promoted held-out ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)); no rater is ground truth ([0018](../decisions/0018-several-raters-none-ground-truth.md)).

## Why

Matching is all or nothing: two subjects are one group (`indexes.matched`) or apart. What lies between is found and dropped:

- **Alignment's own in-between states:** a near-tie is "ambiguous" (scored, sent to the judge), a split or merge a "candidate". `align._score` (values 0.6, name 0.3, attributes 0.1; FLOOR 0.3, MARGIN 0.15) is already a three-level rubric in all but name: aligned, ambiguous, none (Fable).
- **The model's:** `match_subjects` answers "a state of" (logged, never shown) and its answers whose candidate another took (dropped). On the turbine pair, 4 of 21 matched and 4 dropped. A taken candidate is evidence of many to one ("tower and monopile" against a tower), not a miss (Fable).
- **The judge's:** "uncertain" verdicts linked the turbine pair's subjects, wrongly as matches. They're weak evidence, not nothing.

The owner's model is "possibly relevant or a match, not sure, investigate further and see if things fit when tied together".

## Concepts

- **A relation and a level are two things** (Fable): the relation is what the match claims (the same item, the corresponding element, a state of it); the level is how well it's evidenced (firm, plausible, possible). Tensions store their level in `relation`; matches won't.
- **Groups and links:**
  - a firm match joins two subjects into one group, as today;
  - a plausible or possible one is a link between two subjects that stay apart: `subject["links"]: [{other, relation, level, evidence}]`, many to many, never chained (a link isn't an edge of `aliases()`' union-find, so A~B~C doesn't follow);
  - a link raised to firm becomes a group.
- **Evidence per pair, logged, non-matches too** (Fable): one entry a (subject, candidate) pair asked, of kind `match_evidence`, with each signal's raw value and the mode. A weight is fitted from the pairs that matched and those that didn't; logging only matches loses the second.
- **A level is a view of the evidence** (Fable): the rubric (milestone 2), then a weight table (milestone 6), each versioned, maps a pair's evidence to its level when a report is written. A new rubric changes views, never the log; "the latest entry decides" would depend on the order answers came in.
- **The mode changes what evidence says** (Fable): a value in common is strong evidence of one item across revisions, and coincidence across proposals (two designs' towers sharing a value). The judge's verdicts likewise. Revisions' and proposals' evidence are weighed apart ([question 4](#design-questions)).
- **Never a finding,** as gaps aren't. A plausible link feeds links and topics (the owner's answer), not the merged index or its gaps.

## Milestones

### 1. A scorer for matching

There's none: milestone 7's "matching, scored against the keys' items" wasn't built (Fable). In the lab (`comparison.py`):

- Each subject's claims bound to the keys' facts (`_bound`), so each subject has its keys' items (their entities, renames mapped).
- A group or link is right where both sides' items agree, wrong where they don't, unscorable where unbound.
- Per level: how many, right, wrong, unscorable; the keys' items both sides give (`OTHER_CLAIMS` claims or more) matched at no level; and whether firm > plausible > possible in share right.
- Today's matching measured first (the baseline): firm only.

### 2. Links and their evidence, by code (stage 1)

- **Kept and shown, not dropped:** alignment's ambiguous items and split or merge candidates (revisions); `match_subjects`' "state of" answers and its taken candidates (proposals); subjects linked only by the judge's verdicts.
- **The signals** each pair logs (Fable's list, those code has today): a tag in common, identifiers that conflict (`align.identifiers`: Room 104 isn't Room 105), name words in common, values in common and how rare (`Side.holders`), property names in common (joined by `kin` and other names first, so one property named three ways isn't three), the judge's verdicts by relation, the model's answer and relation.
- **The rubric** (the owner: "Three levels is a start"): hand thresholds on hand weights, by mode. Plausible needs two independent signals; at most 3 links a subject; possible only the best few by score (Fable: the turbine pair's 21 subjects with up to 8 candidates each would be up to 170 possible links one way).
- **Shown** (the owner: "links and topics"): the Subjects view's "possibly the same as …" with relation, level and why; a search for one finds the other, marked; topics count a plausible pair's claims as one subject's. No gaps from links, so no looks for them.
- **No requests.**

### 3. More signals: candidates by meaning

- **BM25 or TF-IDF** over each subject's text (name, other names, property names; `retrieval.py`'s), as a signal and to find candidates sharing no word (today's `crossmatch.candidates` needs a word or a property name in common).
- **Embeddings** of the same text (`embed.py`), where the run made vectors.
- **The reranker** (`rerank.py`, a cross-encoder), asked "the same item or the corresponding element?" of a candidate pair (the owner: "Outside of embeddings and cross-encoders, it's difficult to turn model confidence into numbers").
- **Both directions asked** (a subject of each source asked its counterparts): agreeing answers are evidence.
- Each a lever ([0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)), its signal logged whether or not it's used.

### 4. Tied together and tested (stage 2, as levers)

The owner: "let's just adapt the normal levers approaches perhaps". Each test a lever, judged paired against a null arm, on by default only by the owner's call.

- **Code tests, by what the hypothesis says:**
  - *the same item within a source:* restatements across the two raise it; contradictions under one state lower it;
  - *the same item across revisions:* values in common raise it; a few that differ are changes, not evidence against it;
  - *the corresponding element across proposals:* roles and structure, not values: properties in common, one kind, part-of neighbours matched (the tower of the matched turbine), units and magnitudes that fit (a height isn't a frequency).
- **A look as a test:** a gap's look finding the property under the other's name raises a match; "no place" and "not shown" say nothing (in proposals they're mostly coverage).
- **The model's read, discriminating** (Fable): not "do these match?", which invites relations and leans to confirming, but a question with a wrong answer: name a property of one that contradicts the hypothesis, or choose between the candidate and a decoy (the next best candidate). Values hidden in proposals, as a gap's look hides the other's value. Its sub-answers logged as signals, never a confidence word.

### 5. A controlled proposals pair

- Two seeds of one domain template: identity is the template's role (each design's tower), values differ, some roles absent or renamed, one decoy role (Fable). Scored by role: the evidence proposals' weights are fitted from, which revisions' pairs can't give.
- With today's revision knobs: `renamed` (P-101B now P-201B: names fail, values carry the match: plausible's natural test) and `wtp-s1-gaps` (facts filed under other subjects: links within a source).
- Free to generate, pennies to read.

### 6. Levels from numbers

The owner: "then figure out how to analyze or evidence a fuzzy, weighted, or probabilistic numeric match (Bayesian, BM25, etc.)".

- **Fellegi–Sunter weights** (Fable): each signal banded; m (how often a band occurs among pairs that match) from the keys' matching pairs, u among the candidate pairs that don't; a signal's weight log(m/u), a pair's score their sum (a log-likelihood ratio: Bayesian with independent signals).
- **Correlated signals** (name words and property names; embeddings and BM25) overcount under independence: a regularized logistic regression on the same features is the alternative, measured beside it.
- **Levels as thresholds** on the score, set on held-out pairs for each level's share right (say firm 95% or more, plausible 60%; the owner's call).
- **Without keys:** expectation-maximization (Winkler's) fits m and u on real pairs, a rater of its own beside the keys (0018).
- **Held out:** weights and thresholds fitted on development seeds, judged on fresh seeds and one domain never fitted on (a rolling window); the turbine pair stays by eye, never a fit's target. Binomial intervals per level.

### 7. Indexing with weighted relationships, explored

The owner: "until we're confident in our tooling and we have a good idea on how to index with weighted relationships. Exploring those options should be a plan step."

- **What to explore:**
  - plausible matches in the merged index as weighted edges rather than groups: a subject's values beside a linked one's, marked by level;
  - gaps "if one item", ranked by the link's score;
  - search ranking by a link's weight;
  - the export's chunks (a subject's linked subjects named).
- **Measured** by milestone 1's scorer, and by eye on the owner's documents' kinds (the turbine pair).
- **The owner decides** what, if anything, moves from links into the index.

## Measurement

- **The scorer** (milestone 1) on the controlled pairs, every format: each level's count and share right, the keys' items matched at no level, before and after each milestone.
- **The controlled proposals pair** (milestone 5) for proposals' evidence.
- **By eye:** the turbine pair (NREL 5 MW and IEA 15 MW slices), never a fit's target.
- **Cost:** stage 1 none; candidates by meaning, the reranker's and embeddings' requests; stage 2's model read, a request a plausible link (capped). Estimated before each run, asked first above $5.

## Design questions

1. **Levels:** answered 2026-11-07 (quoted at the top): three, a rubric first, numbers after (milestone 6).
2. **What plausible matches feed:** answered 2026-11-07: links and topics, not the merged index or its gaps; weighted relationships in the index explored as a step (milestone 7).
3. **Stage 2 with the model:** answered 2026-11-07: as levers, the normal way (milestone 4).
4. **One weighing or two?** (Fable) Revisions' and proposals' evidence weighed apart (a value in common means another thing in each), so two rubrics and later two weight tables, or one with the mode a signal? Claude's recommendation: two.
5. **Many to one for corresponding elements?** (Fable) One to one for the same item; the corresponding element allowed one to many among plausible links ("tower and monopile" against a tower and a monopile), firm staying one to one? Claude's recommendation: yes.
