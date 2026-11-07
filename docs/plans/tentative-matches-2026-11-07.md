# Tentative matches: hypotheses with levels, their evidence kept

- **Status:** Active (2026-11-07): milestones [1](#1-a-scorer-for-matching), [5](#5-a-controlled-proposals-pair) and [2](#2-links-and-their-evidence-by-code-stage-1) built 2026-11-07 (5 before 2, so links are scored on proposals). [Design questions](#design-questions) all answered 2026-11-07.
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
  - a plausible or possible one is a link between two subjects that stay apart: `subject["links"]: [{other, relation, level, evidence}]`, many to many (a corresponding element may link to several: [question 5](#design-questions)), never chained (a link isn't an edge of `aliases()`' union-find, so A~B~C doesn't follow);
  - a link raised to firm becomes a group.
- **Evidence per pair, logged, non-matches too** (Fable): one entry a (subject, candidate) pair asked, of kind `match_evidence`, with each signal's raw value and the mode. A weight is fitted from the pairs that matched and those that didn't; logging only matches loses the second.
- **A level is a view of the evidence** (Fable): the rubric (milestone 2), then a weight table (milestone 6), each versioned, maps a pair's evidence to its level when a report is written. A new rubric changes views, never the log; "the latest entry decides" would depend on the order answers came in.
- **The mode changes what evidence says** (Fable): a value in common is strong evidence of one item across revisions, and coincidence across proposals (two designs' towers sharing a value). The judge's verdicts likewise. So revisions' and proposals' evidence are weighed apart: two rubrics, later two weight tables ([question 4](#design-questions)).
- **Never a finding,** as gaps aren't. A plausible link feeds links and topics (the owner's answer), not the merged index or its gaps.

## Milestones

### 1. A scorer for matching

There's none: milestone 7's "matching, scored against the keys' items" wasn't built (Fable). In the lab (`comparison.py`):

- Each subject's claims bound to the keys' facts (`_bound`), so each subject has its keys' items (their entities, renames mapped).
- A group or link is right where both sides' items agree, wrong where they don't, unscorable where unbound.
- Per level: how many, right, wrong, unscorable; the keys' items both sides give (`OTHER_CLAIMS` claims or more) matched at no level; and whether firm > plausible > possible in share right.
- Today's matching measured first (the baseline): firm only.
- **Built 2026-11-07** (`comparison._matching`; comparisons.json's `matching`). The baseline, revisions' matching as the index makes it (by the findings, then names), firm only, on the controlled revision pairs as recorded:

  | Format | Subjects matched | Right | Wrong | Unscorable | Items both give, matched |
  |---|---|---|---|---|---|
  | PDF | 505 | 482 | 1 | 22 | 354 of 355 |
  | Markdown | 369 | 367 | 0 | 2 | 301 of 301 |
  | Word | 405 | 403 | 0 | 2 | 303 of 303 |
  | Decks | 406 | 403 | 0 | 3 | 306 of 306 |
  | Workbooks | 384 | 381 | 0 | 3 | 305 of 305 |

  - **So revisions match well already:** alignment decides their items first, and the findings follow it. The one wrong is the two halls' sheets (`lcc-plans`), alike but for their title blocks; most unscorable are drawing sheets' claims bound to no fact.
  - **Proposals have no controlled pair yet** (milestone 5): where matching is weakest (the turbine pair's tower), there's nothing keyed to score.

### 2. Links and their evidence, by code (stage 1)

- **Kept and shown, not dropped:** alignment's ambiguous items and split or merge candidates (revisions); `match_subjects`' "state of" answers and its taken candidates (proposals); subjects linked only by the judge's verdicts.
- **The signals** each pair logs (Fable's list, those code has today): a tag in common, identifiers that conflict (`align.identifiers`: Room 104 isn't Room 105), name words in common, values in common and how rare (`Side.holders`), property names in common (joined by `kin` and other names first, so one property named three ways isn't three), the judge's verdicts by relation, the model's answer and relation.
- **The rubric** (the owner: "Three levels is a start"): hand thresholds on hand weights, by mode. Plausible needs two independent signals; at most 3 links a subject; possible only the best few by score (Fable: the turbine pair's 21 subjects with up to 8 candidates each would be up to 170 possible links one way).
- **Shown** (the owner: "links and topics"): the Subjects view's "possibly the same as …" with relation, level and why; a search for one finds the other, marked; topics count a plausible pair's claims as one subject's. No gaps from links, so no looks for them.
- **No requests.**
- **Built 2026-11-07** (`links.py`; each subject's `links` in the index):
  - **Pairs asked:** subjects alone in each source, sharing a name word or a property's name, or paired by the findings, alignment's groupings (ambiguous, split or merge candidates) or the model's answers. `match_subjects` now keeps an answer whose candidate another took ("taken", a link, never a match).
  - **The rubric** (`rubric/1`), two weighings: a name word counts where it's rare among the subjects' names (four at most; the turbine pair's "blade" and "turbine" name dozens, and linked 42 pairs by it before), or most of two names' words are shared. Values in common count between revisions only. So does the judge's "uncertain", since alignment chose those pairs; between proposals it's doubt. Identifiers that differ rule a pair out (Room 104, Room 105).
  - **Shown:** the Subjects view's "possibly the counterpart of …" (relation, level, signals), found by a search for either name; index.md's line under the subject.
  - **Topics:** a plausible link's claims counted with the other's name. Only links from the findings and the glossary, not from the model's other names or matches: those are asked after the topics, and the other names are asked a request a topic, so the topics would shift between being named and being shown.
  - **Scored** (`comparison._matching`'s `links`, by level; a link across a split the keys record counts right):

    | Format | Plausible | Right | Possible | Right |
    |---|---|---|---|---|
    | PDF | 4 | 4 | 1 | 0 (1 unscorable) |
    | Markdown, Word | 3 each | 3 each | 0 | |
    | Decks, workbooks | 3 each | 3 each | 1 each | 1 each |

    - The proposals pair's alum and ferric sulfate (their doses in common and the judge's pairing) and its two plants (their names and the judge's pairing), plausible in every format; its decoy linked to nothing. The split revision's P-101C, plausible with each of P-101E and P-101F (a many-to-one, as question 5 answered).
  - **The turbine pair,** offline (its report as recorded, with the model's matches): 4 possible links, each by one rare name word ("DOWEC turbine" and IEA's "turbine", "Rotor Speed" and "rotor-speed error"): worth a look, at most.
  - **Recorded again for the topics** ($0.004): the slice runs (12 answers: the other names a topic asks, and two topics' names) and the controlled corpus.

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
- **Built 2026-11-07** (`proposals.py`; `comparison.score_proposals`; recorded $0.14 with the row-by-row runs): Harrow Creek's design basis (`wtp-s1`) against Pine Ridge's (`wtp-s1-proposal`): the template drawn from the next seed (its values its own), its items named its own way (the flash mixer, the clarifiers, intake pumps IP-1 to IP-3, ferric sulfate's feed, a chlorine contact tank), the filters, flocculation and chlorine named alike, the UV option gone, a backwash pump (a decoy), the clarifiers' loading rate not given and the flash mixer's volume given (2 gaps). Compared in proposals mode, every format. A fact's role is its id; a fact only one design gives takes the other's name for its item from their facts in common (`comparison._items`).
  - **Matching by role:** 12 of 12 right in the PDF (9 of 9 in Word, 12 of 12 elsewhere), none wrong; of the 10 roles both give, 9 matched (Word 5 of 9). The model's other names (`search_names`, on by default) matched the renamed ones (IP-1 and P-101A, the flash mixer and the rapid mix basin, the clarifiers and the sedimentation basins, the contact tank and Option B).
  - **Left apart:** alum and ferric sulfate (each design's coagulant: its doses in common, no word), the two plants (their names share "water treatment plant"), and the decoy. The links of milestone 2 are scored on these.
  - **Gaps another source fills:** 2 of 2 in every format.

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
4. **One weighing or two?** (Fable) Revisions' and proposals' evidence weighed apart (a value in common means another thing in each), so two rubrics and later two weight tables, or one with the mode a signal? Answered 2026-11-07 (the owner: "I'll accept these recommendations."): two, as Claude recommended.
5. **Many to one for corresponding elements?** (Fable) One to one for the same item; the corresponding element allowed one to many among plausible links ("tower and monopile" against a tower and a monopile), firm staying one to one? Answered 2026-11-07 (as 4): yes, as Claude recommended.
