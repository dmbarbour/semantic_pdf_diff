# Estimating quality without ground truth

- **Date:** 2026-09-28
- **Asked by:** the owner, after I called a person's per-claim marks an "absolute measure". No rater is ground truth, humans included. People are probably better raters than the cheapest judges, but still raters. Quality should be a **weighted estimate** over raters and heuristics, each with an estimated reliability, reported with uncertainty.
- **Method:** a literature search of primary sources (papers, surveys, documentation). The citations below are the ones the search verified; the unverified ones are listed at the end.

## The common idea

Every method here learns how reliable each source is from the **pattern of agreement between sources**, plus assumptions. The usual ones:
- sources err independently, given the truth
- sources beat chance
- or which sources share errors, stated up front

None needs a gold set. All the risk sits in those assumptions: the less independent the sources, the less the agreement says.

## What the literature offers

**Models of raters with no gold labels:**
- **The Dawid–Skene family:** a hidden true label per item, and a confusion matrix per rater, fitted by EM ([Dawid & Skene 1979](https://doi.org/10.2307/2346806)). We already use it in the review batches.
- **Extensions:**
  - item difficulty ([GLAD](https://papers.nips.cc/paper/3644-whose-vote-should-count-more-optimal-integration-of-labels-from-labelers-of-unknown-expertise))
  - "knows or guesses" competence ([MACE](https://aclanthology.org/N13-1132/))
  - Bayesian versions. A comparison of six models found the hierarchical Dawid–Skene, which partially pools raters, best, while unpooled models overfit ([Paun et al. 2018](https://aclanthology.org/Q18-1040/)).
- **Item response theory:** its rater models add a severity term for each rater ([Patz et al. 2002](https://journals.sagepub.com/doi/10.3102/10769986027004341)).
- **Requirements:** at least 3 conditionally independent sources for identifiability ([Allman et al. 2009](https://arxiv.org/abs/0809.5032)), and a "sources beat chance" prior, or the model can swap right and wrong.
- **Failure mode:** misspecified dependence biases the reliability estimates. With few sources the dependence can't be tested ([Albert & Dodd 2004](https://academic.oup.com/biometrics/article-abstract/60/2/427/7240836)).
- **No single best algorithm** across 17 methods and 5 datasets ([Zheng et al. 2017](https://www.vldb.org/pvldb/vol10/p541-zheng.pdf)).

**Pairwise models with noisy raters:**
- **Bradley–Terry / Thurstone:** P(A beats B) = σ(θA − θB).
- **Extensions:**
  - ties
  - a presentation-order term ([Davidson & Beaver 1977](https://www.semanticscholar.org/paper/On-Extending-the-Bradley-Terry-Model-to-Incorporate-Davidson-Beaver/14b981837cc0ff653984dc44f5ae40d75a2dc938)), which for us is a position-bias term per judge
  - each rater's reliability ([Crowd-BT](https://dl.acm.org/doi/10.1145/2433396.2433420))
- **In LLM practice:** bootstrap or sandwich intervals ([Chatbot Arena](https://arxiv.org/abs/2403.04132)).
- **With two variants per unit,** this reduces to our win rate. It adds judge terms, region effects, and pooling when a round has more than two variants.

**Weak supervision, for combining heuristics with judges:**
- **Snorkel:** heuristics vote or abstain, and a label model learns each one's accuracy from overlaps and conflicts alone ([Snorkel](https://arxiv.org/abs/1711.10160); [MeTaL](https://arxiv.org/abs/1810.02840)).
- **FlyingSquid** estimates accuracies in closed form from agreement between sources, given which sources depend on each other ([FlyingSquid](https://arxiv.org/abs/2002.11955); [Platanios et al. 2014](https://auai.org/uai2014/proceedings/individuals/313.pdf)).
- **Our mechanical checks are heuristics of exactly this kind:**
  - "Quote not found in the text layer" is strong evidence a claim is wrong; "quote found" is weak evidence it's right.
  - Agreement between readings is another source.
  - Judges and people join as further sources.

**Model judges: panels, biases and correlation:**
- **Panels:** a panel of three cheaper judges agreed with people better than one strong judge, at a seventh of the cost ([PoLL](https://arxiv.org/abs/2404.18796)).
- **Biases:** position, verbosity and self-preference ([Zheng et al. 2023](https://arxiv.org/abs/2306.05685)). Position bias is worst when two answers are close ([Shi et al. 2025](https://aclanthology.org/2025.ijcnlp-long.18/)), which are the decisions that matter. Self-preference grows with a model's ability to recognise its own output ([Panickssery et al. 2024](https://arxiv.org/abs/2404.13076)).
- **Correlation:** judges' errors are correlated, more so for larger models, even across providers ([Kim et al. 2025](https://arxiv.org/abs/2506.07962); [Goel et al. 2025](https://arxiv.org/abs/2502.04313)). One preprint found nine frontier judges worth about two independent votes ([2026](https://arxiv.org/abs/2605.29800)).
- **People as peers, not gold:** the [alt-test](https://aclanthology.org/2025.acl-long.782/) drops each person in turn and asks whether a model agrees with the rest at least as well; it needs 3+ people and 50–100 items.
- **Several answers can be reasonable:** forcing raters to pick one can mislead ([Guerdan et al. 2025](https://arxiv.org/abs/2503.05965)). Our "unsure" mark should stay an answer in its own right, not be dropped.

**A few labels, many model labels (prediction-powered inference):**
- **What it does:** valid intervals from a few labels plus many model predictions ([PPI](https://www.science.org/doi/10.1126/science.adi6000); [PPI++](https://arxiv.org/abs/2311.01453)). It can do worse than the labels alone at small samples ([2025](https://arxiv.org/abs/2505.20178)).
- **The catch:** it treats the labelled set as the truth, and no variant found needs no gold at all.
- **A reframing (the search agent's, not from a source):** define the target as "the expected mark under our human protocol". PPI is then valid by construction, with human bias part of the definition.
- **Label budget:** with noisy labels, one label on more items beats repeated labels on fewer ([Dorner & Hardt 2024](https://arxiv.org/abs/2402.02249)).

**Consistency as a signal, and its limits:**
- **Agreement across samples signals confidence** ([self-consistency](https://arxiv.org/abs/2203.11171); [SelfCheckGPT](https://aclanthology.org/2023.emnlp-main.557/)), but misses a model that has learned the wrong fact ([semantic entropy](https://oatml.cs.ox.ac.uk/blog/2024/06/19/detecting_hallucinations_2024.html)).
- **For us:** two overlapping crops agreeing is gemma checking gemma. It catches random misreads, not the same unit misread twice.
- **Tests without labels:** invariance and metamorphic tests check that outputs stay the same under changes that shouldn't matter ([CheckList](https://arxiv.org/abs/2005.04118)).
- **Disagreement as information:** [CrowdTruth 2.0](https://arxiv.org/abs/1808.06080) scores rater, item and annotation together, so ambiguous items aren't blamed on raters.

**Measurement theory:**
- **Reliability is not validity:** judges can agree on a wrong answer ([Wallach et al. 2025](https://arxiv.org/abs/2502.00561)).
- **Generalizability theory** splits variance across region, claim, rater and variant, and projects reliability for more judges or items.
- **Validation without gold** ([Campbell & Fiske 1959](https://pubmed.ncbi.nlm.nih.gov/13634291/)):
  - predict held-out raters' labels
  - convergent validity: different methods agree on the same quality
  - discriminant validity: incidental features such as claim length don't predict the score

## What this means for us

**The data we have or can get, as sources:**

| Source | What it says | Independence from the extractor |
|---|---|---|
| Quote check against the PDF text layer | Mechanical; abstains where there's no text layer | High: not a model |
| Unit and number sanity | Mechanical; abstains when not applicable | High |
| Agreement between readings (merged readings' count) | gemma reading gemma's input twice | Low: correlated with the extractor |
| MiMo, Qwen (judges) | Per-claim marks (rubric v5); pairwise verdicts | Medium; correlated with each other |
| The owner, and later a panel of people | Per-claim marks; pairwise verdicts | Higher, but few labels |

- **The most independent trio** is the quote check, one model judge and one person. Two model judges don't count as two independent sources.
- **Per-claim marks don't measure recall:** they say nothing about facts the extractor missed. Recall has to come from the pairwise verdicts ("missing"), from agreement between readings, and later from reference readings.

## Proposal

1. **One latent-class model of claim correctness** (Bayesian; small enough for exact MCMC). It would have:
   - a hidden right/wrong per claim
   - a sensitivity and specificity for each source, partially pooled by type (heuristics, model judges, people)
   - a difficulty effect per region
   - "unsure" as its own response
   - declared dependence: model judges share a factor, and agreement between readings shares one with the extractor
   - heuristics that abstain where they don't apply

   **Output:**
   - P(right) per claim
   - each variant's precision (mean P(right)) with an interval
   - each source's estimated reliability, including the owner's and each judge's
2. **Pairwise verdicts as a hierarchical Bradley–Terry model:** a position term per judge, ties, and region effects.
   - **Interval fix:** bootstrap over page regions, not bands. Bands cut from one region aren't independent, and today's bootstrap treats them as if they were.
3. **Report ranges, not one number:** refit under 2–3 plausible dependence structures and show the spread, since with few sources the structure can't be tested.
4. **Validate:**
   - leave-one-rater-out prediction
   - convergent checks: judges' marks should track the quote check
   - discriminant checks: they shouldn't track claim length
   - invariance tests: order swaps, shuffled claims, shifted crops
5. **Collecting labels from people:**
   - **Owner or a panel:** more items labelled once each, rather than the same items many times.
   - **A small overlap:** a subset seen by at least 3 people, so human reliability is estimated too. This matches the planned panel of people for the sensitive target tasks.

**Sequence:**
- **Step 1,** after the owner's spot check: re-judge its 16 regions with rubric v5 by MiMo and Qwen (about $0.40). Together with the quote check, that gives the owner's marks, two judges and a heuristic on the same claims: enough sources for a first fit.
- **Step 2:** fit the model offline and report each source's reliability and each side's precision, with intervals.
- **Step 3:** decide whether rounds report the model's estimates alongside, or instead of, the raw win rate.

## Pitfalls

- **Correlated judges:** errors shared across model judges shrink the effective number of judges. A judge from the extractor's own family would add self-preference; none of ours is gemma.
- **Small samples:** at around 100 items, EM can collapse or swap right and wrong. Priors ("sources beat chance") are required.
- **Close pairs:** position bias concentrates in close pairs, the decisions that matter. Judging both orders cancels it only on average.
- **Consistency is not correctness,** and reliability is not validity.

## Not verified by the search

- **Dawid–Skene DOI:** from memory; the reference was confirmed via Paun et al.'s bibliography.
- **CARE and the Ising-model aggregators:** 2026 preprints, not peer reviewed ([CARE](https://arxiv.org/abs/2603.00039), [Ising](https://arxiv.org/abs/2601.22336)).
- **Sample sizes:** no source gave item counts needed at our scale. The 3-source condition is the only firm requirement found.
