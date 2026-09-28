# Meta-audit: why flaws escaped, and what structure would help

- **Date:** 2026-09-28
- **Asked by:** the owner, after the [statistics audit](statistics-audit-2026-09-28.md): why weren't these found earlier? Would better architecture and separation of concerns have helped? For example, are variant queries reified as classes deriving from a common query class, and are judgements, and every other item, reified likewise? Look for opportunities only; change nothing yet.
- **Method:** three read-only reviews ran in parallel, with no model calls:
  - the history of 21 flaws, from git and the review docs
  - the extraction side: queries and levers
  - the evaluation side: units, judgements, raters, decisions
- **What I checked myself:**
  - the three claim identities
  - tables numbered after filtering
  - the locator thumbnail missing from the request key
  - prune having no guard
  - r03's IEA-15 losses
  - the ledger's split of spend

## Summary

- **No test found any of the 21 flaws.** All were found by looking:
  - agent reviews and audits: 8
  - round analysis: 6
  - while building: 3
  - the owner: 2
  - a research note: 1
  - the review batch: 1
- **Better separation of concerns would plausibly have caught about half early:** 11 of 21, those where an invariant was never stated, a concept had no single owner, or the judged unit wasn't the unit of dependence.
  - **Not caught by structure:** reviewers lacking context, and flaws visible only in outputs (6 of 21). Those needed people looking.
  - **Caught by testing practice:** the 3 decision-rule flaws needed simulation under the null, which is testing practice more than architecture.
- **Variant queries aren't reified.** There's no query type and no lever type.
  - A lever is a Settings field spread over 4–5 hand-synchronised places.
  - Request keys are correct today only because those places were kept in step by hand.
- **Judgements aren't reified either.**
  - Only the model's raw answer (`PairVerdict`) is typed; everything after it is dicts.
  - Raters come in four shapes.
  - Claims have three different identities.
- **The biggest payoff is checks, not class hierarchies:**
  - a replay drift check
  - a per-lever scope test
  - rules checked when a batch is built
  - decision rules simulated under the null
- Value objects and registries come after those, as the checks make them safe to introduce.

## The flaws and how they escaped

| # | Flaw | Found by | Affected | Root cause |
|---|---|---|---|---|
| 1 | Sections by page; boxed headings taken as figures | review batch s01 | since the start | looking |
| 2 | Fingerprint held every lever, so variants re-asked everything | r01 judges' notes | r01 void ($10) | owner |
| 3 | Record mode re-asked recorded failures | r01b's retry count | r01b–r06 recordings | invariant |
| 4 | Early stopping with repeated looks | overall review's simulation (warned in r01b, r03, r04) | 8 of 11 acceptances | statistics |
| 5 | Claims sampled separately per side | r06 analysis | visual units r01–r06 | invariant |
| 6 | Rotated sheets: context in unrotated order | overall review | r01b–r04 (ken-cd tables 0.25) | owner |
| 7 | Table values taken for stems | the owner's spot check | r03 accepted; r04; defaults | looking |
| 8 | Merged claim's wording embellished | r07 tags (invented 11 → 31) | r07 | the method worked |
| 9 | False merges (Module A = Module B; a generic head) | r08 analysis; overall review | r06–r08 | looking |
| 10 | Chart rules missing from the request key | Claude, while writing it | none | owner |
| 11 | `record-new` makes transient failures permanent | overall review | recordings | invariant |
| 12 | Ledger kept only a request's last attempt | overall review; the provider's dashboard | all spend figures | looking |
| 13 | Judges lacked headings and the extractor's context | r07 remarks; overall review | r01–r08 | context |
| 14 | Judges lacked the whole page and full claim sets | the owner, sc01 item 4 | through r09h | context |
| 15 | Bands cut across mismatched tilings | Claude, building sc01 | none | unit |
| 16 | Bands of one region treated as independent | research note | r09h's bound | unit |
| 17 | Merged claims shown in text wording in visual units | suspected in r09h; statistics audit | visual strata r06–r09h | unit |
| 18 | Escalation failures lost or overwritten | statistics audit | r09 decided on 31 of 32 | invariant |
| 19 | Document-family strata planned, not built | statistics audit | 2 days | statistics |
| 20 | Several variants per round; "no worse" names no gain | statistics audit | r06–r08 | statistics |
| 21 | Prune after failed replays emptied the fixture | Claude, from the 787-byte zip | minutes | invariant |

**Every flaw lived hours to about 2 days** (rounds ran 26–28 September), so what matters is the rounds and decisions each one touched.

**Fixes caused flaws:** the method overhaul (d6734d4) introduced #15, #16 and #18 and made #14 worse. b89f097 and 5850dfd each fixed one flaw and created another.

**Root causes:**
- **An invariant nobody stated (5; it also shows in #2, #15, #17).** For example: "a variant differs only where its lever acts."
  - **Would have caught them:** levers that declare their scope, with batch building checking that changes stay inside it.
  - **Would it have worked?** Likely yes, and cheaply, with no model calls: r01b's count of re-asked requests was exactly this signal.
- **A concept with no single owner (3).** Display order on rotated pages; request identity split across key, fingerprint and prompt.
  - The 25 September rotation fix went site by site, and the next day's new context builders brought the bug back.
  - **Would have caught them:** one owner for page context, a test that rotating a page leaves its context unchanged, and a check that the stored prompt equals the one built now.
- **The judged unit isn't the unit of dependence (3).**
  - **Would have caught them:** a unit type carrying its region cluster and tiling, intervals that require clusters, and a test that a text-only lever leaves visual units unchanged.
- **Decision rules never simulated under the null (3).**
  - **Would have caught them:** a harness that runs the rules on A/A or permuted scores and checks the false-acceptance rate. Both reviews found these flaws exactly that way, and r01b already suspected early stopping.
- **Reviewers lacking context (2).**
  - #13: building the judge's inputs from the recorded request would have prevented it.
  - #14: only a person trying to judge found it.
- **Visible only by looking (4).** The signals were there and got explained away:
  - **IEA-15 lost to stems in r03** (0.31 on 4 units, "compound attributes built from the Within: path"). The judges' reason was read as a design issue with the path. IEA-15 had junk paths ("0.5 Frequency [Hz]"); that the losing units had them is unverified.
  - **ken-cd tables at 0.25** were put down to misbinding noise, not the rotated-sheet bug.
  - Once looking got cheap (the insights page), fixes followed within hours.
- **Tests pinned to the example that motivated the code:**
  - #7 had one positive test.
  - #6 had no test on a rotated page.
  - The lever test checked only the defaults (#2).

## Separation of concerns today

**Queries (extraction):**
- **No request type before the prompt.**
  - Each kind's inputs are local variables inside a 390-line closure (`extract.py` `_pdf_job`), passed to a 14-argument `consume`.
  - The prompt and the key are built side by side from the same parts (extract.py:958–966). They're kept in step by hand: a lever that adds a new slot needs its own key suffix, which is how the chart rules were nearly missed (#10).
- **Three ways of keying:** extraction hashes the prompt's parts, situating hashes the whole prompt (in step by construction), and comparison uses its own tuple.
- **Other code reads the key by position or splits prompts at marker strings:** `llm.py`, `review.py` (`parts[5]` is the crop), `rounds.py` (`"SOURCE DATA:\n"`), tests.
- **The five extraction kinds share one prompt and one key.** A value object would fit them; a class hierarchy wouldn't earn its keep.

**Levers:**
- **A lever is a Settings field, echoed by hand in:**
  - `LEVERS` (fingerprint exclusions)
  - `SETTING_REGIONS` (which cached results to reset)
  - a key suffix, when it adds a slot
  - list parsing in `from_env`
  - merged readings have a separate mechanism of their own (store meta).
- **What the lever is for lives only in `levers.md` and the round files:** its hypothesis, status and evidence.
- **Three latent issues** (none has affected a decision yet):
  - **Tables are numbered after filtering.** A real table after a dropped one gets a new task id and is re-asked, adding re-ask noise to the table filter's result (r01b: inconclusive). Checked.
  - **The tile locator's thumbnail isn't in the key,** only its note. "A larger thumbnail on sheets" (a next idea in levers.md) would silently replay old answers, the #10 class again. Checked.
  - **Key and cache side effects, not verified:**
    - `quote_match` only changes post-processing, but a reset treats it as a text lever and deletes cached text answers.
    - Toggling `vision`, `figure_tasks` or `dedupe_repeated` changes every extraction request's fingerprint.

**Judgements and raters:**
- **Only `PairVerdict` is typed.** Verdicts, units, batches and decisions are dicts and strings:
  - unit ids are parsed back by regex
  - decisions are checked with `startswith`
  - the batch format's version has stayed 1 through several changes
- **Raters come in four shapes:**
  - model pairwise verdicts
  - people's answers: one order, and a score may be missing
  - review-batch labels: shared by models and people, validated, ready for Dawid–Skene. This is the precedent to follow.
  - the quote check: only rates per kind; `quote_verified` never reaches a batch claim
  - **Consequence:** the planned weighted quality model can't yet join them claim by claim.
- **Three claim identities** (checked):
  - `claim_id`: case-folded, no quote
  - `_ident`: exact, with the quote
  - `insights._claim_key`: case-folded, no quote
  - **Consequences:**
    - Whether a unit changed is judged by IDs, so a lever that changes only quotes looks unchanged.
    - v6 groups claims by exact text, so a claim can be "shared" to the sampler but "only in A" to the judges.
- **Parity between judges and people:**
  - People see each claim's request input; judges don't.
  - The spot-check page gives people v4's instructions; rounds now judge with v6.
- **Scores are computed twice, differently:** `insights` averages every verdict, while `decide` averages each judge's two orders first and drops judges with one order.
- **The round spec (`round.json`) isn't validated:** a typo in `"rubric"` silently judges with v1. Pre-registered criteria have nowhere to go.
- **Separation:**
  - `decide`, `build_batch` and `judge_pairs` each mix file reading, logic and writing.
  - The statistics are pure only in `interval` and the Dawid–Skene code.
  - `run_round.py` has no tests.
  - In fairness, the committed files let every round be re-decided offline, which is how the audits worked.

## Opportunities, most useful first

| # | Change | Would have caught | Cost and risk |
|---|---|---|---|
| 1 | **Replay drift check:** on a fixture hit, compare the recorded prompt (and image hashes) with the one built now; fail on a mismatch | #10; the thumbnail case; any stale answer | Small; no key or prompt changes. The safety net for everything below |
| 2 | **Per-lever scope test:** each lever off and on; a changed prompt or image means a changed key, and changes stay within the lever's declared regions. Every Settings field classified (lever, structural, transport) | #2, #10, table renumbering, #17 | Small; offline |
| 3 | **Checks when a batch is built:** hidden claims are all shared; swapping sides mirrors the units; a text-only lever changes no visual units; every unit has a document family; each claim's reading comes from its unit's kind | #5, #15, #17, #19, the v4 note on hidden claims | Small |
| 4 | **Decision rules as pure functions, simulated under the null in CI;** a typed round spec with pre-registered criteria (role, thresholds, strata, named gain), hashed when judging starts | #4, #16, #19, #20; implements decision A | Seconds of CPU; old round.json files keep working with defaults |
| 5 | **One claim identity:** claim ID and reading ID on every shown claim | #17; the sampler/judge mismatch | Cheap; `_ident` stays as a fallback for old batches |
| 6 | **A lever registry in code:** fields, whether it shapes requests or only post-processing, regions touched, key slot, and an `applies_to(request)` predicate. levers.md checked against it; a lever ID in the history | Hand-copied `LEVERS`/`SETTING_REGIONS` drift; enables decision B (each variant lists the requests it changes, for review) and decision A's catalogue | Moderate; keys unchanged if slots keep today's rule |
| 7 | **`ExtractQuery`, one value object** (region, task, text, context parts, rules, crop, heading, images) with `prompt()` and `key()` reproducing today's bytes; context providers composed the same way; one owner for page coordinates | #6 and #10 classes; positional key reads | Moderate; safe only with #1 in place; must keep bytes identical or re-record |
| 8 | **Judgement records and a Rater interface** (model judge, people's answers, the quote check): each record has a rater, a target (unit, side, claim), a question, an answer, a status and attempts | #18; retry policy in one place; counts derived rather than kept | Moderate; an adapter over today's files, no re-judging. What the weighted quality model consumes |
| 9 | **A Rubric object** (template, required fields, people's instructions, answer mapping), after golden prompt tests for v2–v6 | #13/#14 parity; v6's needs checked when a batch is built | Any byte change in a judge prompt re-pays judging, which is 88% of spend ($35.56 of $40.31). Only v1 has a golden test today |
| 10 | **Sampling that returns each unit's inclusion probability** | Statistics audit item 7 (weighting) | Small |

**Small fixes found along the way** (not made):
- number tables before filtering (changes keys for table-filter variants only)
- put the locator settings in the key before trying a larger thumbnail
- a guard on prune
- v6 instructions on the spot-check page
- count missing verdicts rather than failed attempts (since today, a failure and a failed retry count 2)

## Where it wouldn't pay

- **Pydantic for every dict.** Items 1–5 carry most of the value.
- **A class hierarchy for the extraction kinds.** They share one prompt and one key; situating and comparison have no levers.
- **Types don't find judge bias or re-asking noise.** Those need A/A controls and simulation.
- **They don't find missing context or junk in outputs either.** Those need people looking, early and cheaply.
- **The genetic-programming-like search (plans index: *Lever search*) is premature now.** At ±0.11 on 32 units and $1–3 per decision, searching many variants multiplies false acceptances and the winner's curse. It needs held-out gates (decision A) and a cheaper, less noisy fitness first, such as the weighted quality estimates or mechanical proxies.

## Lessons

1. **Check each comparison against its lever's declared scope before judging.** The costliest escapes (#2, #3, #5, #17) measured something other than the lever, and all were detectable without a model.
2. **Simulate each decision rule under the null when it's written, as a test.** The early-stopping warnings in r01b, r03 and r04 had no numbers, and changed nothing for 33 hours.
3. **Give each cross-cutting concept one owner, and fix the class, not the site.**
4. **Change the method in small steps, each with its invariant.** One overhaul brought three new flaws.
5. **Treat a stratum anomaly as a bug hunt before blaming the lever.** When a lever is built, dump the context it adds for each document, and get people looking at units early.

## A possible order, when the owner wants changes

1. Replay drift check, per-lever scope test, prune guard (items 1–2).
2. Batch checks and one claim identity (items 3, 5).
3. Pure decision rules with null simulations and a typed round spec (item 4). This is where decision A's pre-registered criteria live.
4. The lever registry, with `applies_to` and a list of changed requests (item 6, decision B), then `ExtractQuery` and context providers (item 7), byte-identical under the drift check.
5. Judgement records and raters (item 8), ahead of the weighted quality fit; then the Rubric with golden tests (item 9).
