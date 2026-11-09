# Tentative matches: hypotheses with levels, their evidence kept

- **Status:** Active (2026-11-07): milestones [1](#1-a-scorer-for-matching), [5](#5-a-controlled-proposals-pair) and [2](#2-links-and-their-evidence-by-code-stage-1) built 2026-11-07 (5 before 2, so links are scored on proposals); [3](#3-more-signals-candidates-by-meaning) built 2026-11-08 but for both directions; [5](#5-a-controlled-proposals-pair) extended and [4](#4-tied-together-and-tested-stage-2-as-levers) built 2026-11-08; [6](#6-levels-from-numbers) built 2026-11-09 (passed its held-out rule; Fellegi-Sunter, proposals only; EM without keys not built). [Design questions](#design-questions) all answered 2026-11-07.
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
- **Built 2026-11-08** (0.47.0; the owner: "Please proceed."):
  - **Names spelled alike** (letters' trigrams, half in common at least: "flocculators", "flocculation"), a source of candidates and part of the names' signal; by code, always.
  - **Names alike in meaning** (`link_meaning`, off; with an embedding model, `embed_model`): each claim's name embedded once (`embed.names`), before the topics count links. Two subjects alike where their names' cosine is 0.8 or more and each is the other's likest.
  - **One family of evidence for the names:** their words, spelling and meaning count once toward a level. On the turbine pair, "Rotor Speed" and "rotor-speed error" were plausible by name and meaning, both the names'.
  - **Numbers that differ** rule a pair out between revisions only. Between proposals they ruled out the turbine pair's likest pair by meaning, NREL's 5 MW turbine and IEA's 15 MW (0.86): two designs' counterparts differ by their numbers too.
  - **The turbine pair** (Qwen/Qwen3-Embedding-8B, 155 names, three requests; with `match_subjects`): six possible links, none plausible. Right: NREL's baseline turbine and IEA's reference one (0.86), and the two offshore turbines (0.85). Wrong or loose: DOWEC's and IEA's "turbine" (0.82), "aerodynamic torque" and CCBlade's aerodynamic power, the pitch controller's model and CCBlade's, "Rotor Speed" and "rotor-speed error". No two turbines here share properties: one family of evidence each.
  - **The controlled PDF pairs** (a variant, the same model): links unchanged, plausible 4 of 4 right, the possible one unscorable. The model's other names (`search_names`) had already matched the renamed items.
  - **The reranker as a signal** (`link_rerank`, off; with `rerank_model`; built 2026-11-08 after the owner: "I believe DeepInfra has rerankers, pretty sure we've used them previously": Claude had looked only at `/models`, which DeepInfra's inference API isn't listed in):
    - **How it's asked:** each subject alone in the source with fewer, one request each, against the other source's (`rerank.subjects`, 60 at most), told the task: "the same item or play the same part". Before the topics, on the subjects built without the model's other names.
    - **How it counts:** a subject's likest at 0.8 or more is evidence of its own (it reads names and properties together, so it isn't the names' family).
    - **The turbine pair** (Qwen/Qwen3-Reranker-8B, DeepInfra's API; 52 requests; with `link_meaning` and `match_subjects`): it scores relevance, not identity. Its right pair, NREL's baseline turbine and IEA's reference one, scored 0.98, with meaning plausible: the only plausible link, and right. Wrong pairs scored as high: IEA's "15-MW turbine" and "Region 2½" 0.97, "turbine" and "Drivetrain" 0.95. Under 0.8 they were mostly wrong, hence the threshold. Alone it makes a link possible at most. Naming a reranker also reranks the claims' pairs before the judge, so 551 pairs were judged again ($0.11).
    - **The controlled PDF pairs** ($0.002, 21 requests): it agreed with every right link (alum and ferric sulfate 0.95, the two plants 0.99, the split's P-101C and P-101E 0.998) and added no wrong one.
  - **Not built:** both directions asked by `match_subjects` (the owner, 2026-11-08: "Doubling requests isn't good unless it pays off."): no sample shows its worth yet; it waits on more keyed proposals pairs (milestone 5, extended).

### 4. Tied together and tested (stage 2, as levers)

The owner: "let's just adapt the normal levers approaches perhaps". Each test a lever, judged paired against a null arm, on by default only by the owner's call.

- **Code tests, by what the hypothesis says:**
  - *the same item within a source:* restatements across the two raise it; contradictions under one state lower it;
  - *the same item across revisions:* values in common raise it; a few that differ are changes, not evidence against it;
  - *the corresponding element across proposals:* roles and structure, not values: properties in common, one kind, part-of neighbours matched (the tower of the matched turbine), units and magnitudes that fit (a height isn't a frequency).
- **A look as a test:** a gap's look finding the property under the other's name raises a match; "no place" and "not shown" say nothing (in proposals they're mostly coverage).
- **The model's read, discriminating** (Fable): not "do these match?", which invites relations and leans to confirming, but a question with a wrong answer: name a property of one that contradicts the hypothesis, or choose between the candidate and a decoy (the next best candidate). Values hidden in proposals, as a gap's look hides the other's value. Its sub-answers logged as signals, never a confidence word.
- **Built 2026-11-08** (0.49.0; the owner: "please proceed with milestone 4 and the answer-key improvement for milestone 5"), both levers off; measured on the extended controlled proposals pairs (milestone 5: three pairs, every format), each arm rebuilt from the same recorded reports where it asks nothing:
  - **`link_tests`** (code, no requests):
    - *Distinct properties:* properties in common count only where this pair's are more than either subject has in common with any other candidate. The wrong links were among siblings: P-101A plausible with each of the other design's three pumps, the camelback with each track element, all by shared properties.
    - *Values that fit* (proposals): a property both give, of one kind of unit and within ten times; else possible at most.
  - **`link_read`** (a request a link, 80 at most): each link shown against a decoy, the other source's subject with the most properties in common but the linked one, the order set by their names. Values hidden between proposals. Picked: evidence. The decoy or neither: possible at most. Entries of kind "link_read".
  - **One family for a model's readings:** the reranker's, `match_subjects`' answer and the read count once. On the turbine pair, the reranker and the read alone made IEA's "15-MW turbine" and NREL's "Region 2½" plausible.
  - **Measured** (proposals pairs, every format):

    | Arm | Plausible: right of | Possible: right of |
    |---|---|---|
    | Neither | 25 of 43 | 26 of 68 |
    | `link_tests` | 16 of 16 | 20 of 41 |
    | `link_tests` and `link_read` ($0.005, 56 reads) | 24 of 25 | 12 of 32 |

    - **Revisions:** links unchanged in every arm (plausible 10 of 10).
    - **The reads:** picked 26, neither 29 (mostly siblings, which hidden values can't tell apart: rightly left possible), the decoy 1. The one wrong plausible link: Cyclone's bunny hop for Ridgeback's helix, which Cyclone dropped. A role gone still invites a pick over a weaker decoy.
  - **The turbine pair** (both levers with meaning, the reranker and `match_subjects`; 12 reads, $0.004): the read turned down the reranker's wrong pairs (Design Point, Drivetrain, a flapwise mode: neither or the decoy). Two plausible: NREL's baseline and IEA's reference turbines (right); DOWEC's and IEA's "turbine" (loose).
  - **Held-out rule, written 2026-11-08 before the held-out pairs were generated** (Claude's, under [0037](../decisions/0037-levers-judged-paired-and-promoted-held-out.md)'s paired method; the owner, 2026-11-08: "I'm inclined to add them, but no reason to skip the proper test phase"):
    - **Unit:** one proposals pair in one format, of seeds 2 and 3 (`controlled.py heldout`): 30 units, none seen in development. One run each with both levers on; the arms without them rebuilt from the same reports (`link_tests` asks nothing; the reads' entries left out).
    - **`link_tests`** passes where wrong plausible links fall, summed over the units, at p < 0.1 by a sign flip over the units that change, and plausible links' precision falls in no format.
    - **`link_read`** (with `link_tests`) passes where right plausible links rise by the same test, plausible links' precision stays 90% or more overall and 80% or more in every format.
    - **Reported, not judged:** right links lost at any level; firm matches (neither lever touches them).
    - **Checked once,** on the code as committed (02d461a); a lever failing it stays off, its held-out result quoted.
  - **Held-out result, 2026-11-08** (`controlled.py heldout --seed 2 --seed 3`; $0.70; 30 units): both pass.

    | Arm | Plausible: right of | Possible: right of |
    |---|---|---|
    | Neither | 69 of 124 | 53 of 153 |
    | `link_tests` | 32 of 32 | 62 of 121 |
    | `link_tests` and `link_read` | 57 of 60 | 37 of 93 |

    - **`link_tests`:** wrong plausible links 55 → 0 (18 units changed, p < 0.0001); precision in each format 46–82% → 100%.
    - **`link_read`:** right plausible links 32 → 57 (20 units changed, p < 0.0001); precision 95% overall, 87.5% at least in each format (Markdown and PDF 7 of 8 and 14 of 16; the rest all right).
    - **Reported, not judged:** right links at any level 122 → 94 with the tests (siblings' pairs that nothing sets apart lose their link; the reads keep 94), wrong ones 155 → 59.
    - **Defaults:** both on since 2026-11-09 (the owner: "Yes, turn both on by default."; 0.50.0); round 0's settings keep them off. `link_read` asks between proposals only, as it was held out: between revisions the split revision's two right links were read each with the other as its decoy, the model said neither, and both fell to possible. A decoy that's never a subject's other link is an idea in the lever index, to be measured and held out again.
  - **Not built:** *a look as a test.* Links aren't looked for (the owner: links feed "links and topics for now"), so no look tests one. *Part-of neighbours* (the tower of the matched turbine). *The same item within a source:* links are across sources so far.

### 5. A controlled proposals pair

- Two seeds of one domain template: identity is the template's role (each design's tower), values differ, some roles absent or renamed, one decoy role (Fable). Scored by role: the evidence proposals' weights are fitted from, which revisions' pairs can't give.
- With today's revision knobs: `renamed` (P-101B now P-201B: names fail, values carry the match: plausible's natural test) and `wtp-s1-gaps` (facts filed under other subjects: links within a source).
- Free to generate, pennies to read.
- **Built 2026-11-07** (`proposals.py`; `comparison.score_proposals`; recorded $0.14 with the row-by-row runs): Harrow Creek's design basis (`wtp-s1`) against Pine Ridge's (`wtp-s1-proposal`): the template drawn from the next seed (its values its own), its items named its own way (the flash mixer, the clarifiers, intake pumps IP-1 to IP-3, ferric sulfate's feed, a chlorine contact tank), the filters, flocculation and chlorine named alike, the UV option gone, a backwash pump (a decoy), the clarifiers' loading rate not given and the flash mixer's volume given (2 gaps). Compared in proposals mode, every format. A fact's role is its id; a fact only one design gives takes the other's name for its item from their facts in common (`comparison._items`).
  - **Matching by role:** 12 of 12 right in the PDF (9 of 9 in Word, 12 of 12 elsewhere), none wrong; of the 10 roles both give, 9 matched (Word 5 of 9). The model's other names (`search_names`, on by default) matched the renamed ones (IP-1 and P-101A, the flash mixer and the rapid mix basin, the clarifiers and the sedimentation basins, the contact tank and Option B).
  - **Left apart:** alum and ferric sulfate (each design's coagulant: its doses in common, no word), the two plants (their names share "water treatment plant"), and the decoy. The links of milestone 2 are scored on these.
  - **Gaps another source fills:** 2 of 2 in every format.
- **Extended 2026-11-08** (the owner, after asking whether the sample sufficed to judge asking both ways: "please proceed with milestone 4 and the answer-key improvement for milestone 5"; recorded $0.25): three pairs.
  - **Cedar Falls' design basis** (`wtp-s1-cedar`) against Harrow Creek's: named by function (a coagulation tank, slow mixing tanks, settling basins, low-lift pumps LL-1 to LL-3, sodium hypochlorite's feed, ultraviolet reactors); its chlorine contact option gone; a sludge pump (a decoy); its finished water's turbidity limit not given; its filters' backwash rate given.
  - **The Cyclone roller coaster** (`coaster-s1-proposal`) against Ridgeback: a chain lift, a main drop, a heartline roll, an airtime hill, steel bents; its helix gone; a bunny hop (a decoy for the airtime hill); its maximum vertical acceleration not given; its trains' length given.
  - **Pine Ridge,** as before.
  - **The model's other names miss more** of Cedar Falls' and Cyclone's renames, so matching and links have work: Cedar Falls' PDF matched 5 of its 10 roles (6 of 7 matches right), and its links were 4 of 8 plausible right before milestone 4's tests.
  - **Held-out seeds** (fresh seeds of each design) aren't generated yet: due before levels' numbers are fitted (milestone 6).

### 6. Levels from numbers

The owner: "then figure out how to analyze or evidence a fuzzy, weighted, or probabilistic numeric match (Bayesian, BM25, etc.)".

- **Fellegi–Sunter weights** (Fable): each signal banded; m (how often a band occurs among pairs that match) from the keys' matching pairs, u among the candidate pairs that don't; a signal's weight log(m/u), a pair's score their sum (a log-likelihood ratio: Bayesian with independent signals).
- **Correlated signals** (name words and property names; embeddings and BM25) overcount under independence: a regularized logistic regression on the same features is the alternative, measured beside it.
- **Levels as thresholds** on the score, set on held-out pairs for each level's share right (say firm 95% or more, plausible 60%; the owner's call).
- **Without keys:** expectation-maximization (Winkler's) fits m and u on real pairs, a rater of its own beside the keys (0018).
- **Held out:** weights and thresholds fitted on development seeds, judged on fresh seeds and one domain never fitted on (a rolling window); the turbine pair stays by eye, never a fit's target. Binomial intervals per level.

- **Built 2026-11-09** (the owner: "Please proceed with milestone 6."; checked first with the advisor):
  - **A pair's features apart from its leveling** (`links.candidates`; behaviour preserved: the 289 recorded controlled reports rebuilt to identical links), banded (`links.bands`): names alike, meaning, properties in common (0 to 3), distinct from siblings', values that fit, the judge's counting verdicts (0 to 2), the model's match.
  - **Fitted on proposals only** (`linkfit.py`): revisions' subjects left alone hold too few counterparts to fit (the split revision's two), so revisions keep the rubric, though the owner chose two weighings.
  - **On the default recordings.** With `match_subjects` on, the model matches most renamed items firmly and leaves mostly siblings alone (165 of 173 validation pairs), so meaning and the model's match never showed; they weigh nothing until fitted. The reranker's signal isn't fitted (naming one re-judges every claim pair).
  - **Fellegi-Sunter weights** (seed 1: 149 labelled pairs, 53 matches; log2 of each band's share among matches over its share among non-matches): names alike +6.1, distinct properties +3.5, two counting verdicts +3.0, one property in common +5.1 (a band to watch: seed 1's pairs sharing one property were mostly matches), values that don't fit −0.7. A ridge logistic on the same bands chose the same pairs.
  - **Left out a template at a time** (development): the top-scored as many as there are matches, the coaster 7 of 10 right, the water plants 28 of 43.
  - **Thresholds set on seeds 2 and 3** (validation, looked at before): plausible at a score of 2.807 (95% right), possible at −0.146 (`link_weights.json`, `weights/1`, stamped with the candidate generator and rubric it was fitted on).
  - **The read** only raises (a possible link picked over its decoy is plausible). As a test it lowered 10 validation links, every one right: siblings the reads can't tell apart, which the weights already weigh.

    | Validation (seeds 2, 3), the cap and reads applied | Plausible: right of |
    |---|---|
    | The rubric (today's defaults) | 57 of 60 |
    | Weights, the read lowering | 58 of 61 |
    | Weights, no read | 68 of 71 |
    | Weights, the read raising (`link_levels: weights`) | 71 of 74 |

  - **Calibration on validation** (the share right by the share the score says): 0.9–1.0, 53 of 54; 0.7–0.9, 17 of 27 (overconfident); 0.3–0.5, 28 of 75; 0.1–0.3, 28 of 124; under 0.1, 1 of 92.
  - **`link_levels`** (`rubric`, the default, or `weights`): a link under weights says its score and the share of matches it says (`likely`).
  - **Held-out rule, written 2026-11-09 before seeds 4 and 5 were generated** (Claude's, as 0037; the advisor: a three-way split, seeds 2 and 3 now spent on thresholds):
    - **Units:** one proposals pair in one format, of seeds 4 and 5: 30 units.
    - **Arms:** the rubric (today's defaults) and `link_levels: weights`, each run with its own reads (`controlled.py heldout`, twice: the second replays all but its reads).
    - **Target:** right plausible links more with the weights, summed over the units, at p < 0.1 by a sign flip over the units that change.
    - **Guards:** the weights' plausible links 90% right or more overall and 80% or more in every format, and no more than 3 points under the rubric's overall.
    - **Reported, not judged:** the calibration of `likely` by band; possible links; right links at any level.
    - **Checked once,** on the code as committed; failing, `link_levels` stays `rubric`, its held-out result quoted.
  - **Held-out result, 2026-11-09** (seeds 4 and 5, 30 units; the rubric arm $0.72, the weights arm $0.005, its own reads): passes.

    | Arm | Plausible: right of | Possible: right of |
    |---|---|---|
    | The rubric (today's defaults) | 48 of 50 | 25 of 61 |
    | `link_levels: weights` | 62 of 65 | 18 of 51 |

    - **Target:** right plausible links 48 → 62 (14 units changed, p = 0.0001).
    - **Guards:** 95.4% of the weights' plausible links right (the rubric's 96.0%: 0.6 points under); the least, Markdown, 9 of 11 (81.8%); the PDFs 12 of 13; Word, decks and workbooks every one.
    - **Calibration** (the share right by the share the score says): 0.9–1.0, 49 of 49; 0.7–0.9, 15 of 22 (a little overconfident, as on validation); 0.3–0.5, 16 of 45 (it says 0.33); 0.1–0.3, 37 of 149 (it says 0.20); under 0.1, 2 of 77.
    - **Defaults** are the owner's call.
  - **The turbine pair, by eye** (offline, its report as recorded): the weights make 9 plausible links, most wrong. Among them: "Drivetrain" and IEA's "15-MW turbine", "aerodynamic torque" and CCBlade's aerodynamic power, "Rotor Speed" and "rotor-speed error", REpower's machine and "turbine". Each by names alike alone (+6.1, enough by itself to pass the plausible threshold). The rubric, which needs two families of evidence, makes 2 (one right, one loose).
    - **So the held-out check measured another seed of the same templates, not another kind of document.** On the controlled designs, counterparts renamed share words far more often than on real ones, so the weights trust names more than real documents bear.
    - **Claude's recommendation:** keep `rubric` the default. Before the weights are trusted:
      - a held-out template the weights never saw (the convention center, the link protocol), with decoys named alike;
      - the names' weight bounded, or the rubric's two families required of the weights too;
      - EM on real pairs without keys, a rater of its own.
  - **Followed up 2026-11-09** (the owner: "Please proceed."; the advisor checked the approach, its decision rule written before looking: refit, then the turbine pair; promoted to a held-out check only if it beats the rubric on validation and looks right on the turbine):
    - **Two families required of the weights** (as the rubric requires): on validation they then choose the rubric's very pairs, 57 of 60. All the weights had gained came from links on one family, mostly names alone.
    - **Decoys named alike not added to development:** the fitted names' weight would then only say how many Claude chose to plant.
    - **The non-matches' rates (u) from real documents instead** (the standard way: across two real documents nearly every candidate pair is a non-match), the matches' (m) still from the keys. The development slices' only comparison of two documents but the turbines (kept for the check) is the drawings pair: 487 candidates, the same generator.
      - **What the keys had misled:** the controlled designs' non-matches seldom share exactly one property; the drawings' candidates do 47% of the time (sheet titles, scales).
      - **Refitted:** names alike +2.4 (was +6.1), one property in common −1.4 (was +5.1), distinct properties +5.8, one counting verdict +4.0.
      - **The turbine pair:** no candidate scores above 2, so names alone no longer make a link plausible.
      - **Validation,** the cap and the read applied: 57 of 60, a tie with the rubric. The rule stops there: not promoted, and the Harbor template (below) stays sealed for a candidate that beats the rubric.
    - **A template held out for that check** (`proposals.HELDOUT_PAIRS`, never in development's corpus): the Harbor Telemetry Link against the Lakeshore protocol, renamed by role, its Version field gone, decoys named like the other's items (a status report period, a measurement interval), 2 gaps. Built, not yet run: seeing its links would spend it.
    - **`likely` is calibrated on the controlled templates only.** On the turbine pair, wrong links said 0.82–0.90 under weights/1; it isn't calibrated for real documents.
    - **So, on today's signals, the rubric's two families do the work.** The numbers wait for richer signals recorded in settings closer to real use: meaning, the reranker, the model's match. `link_levels` stays `rubric`; `link_weights.json` keeps weights/1, off.

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
