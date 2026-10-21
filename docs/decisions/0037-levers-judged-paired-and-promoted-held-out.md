# 0037. A lever is judged on the same inputs as its baseline, by rules fixed before judging, and promoted only on held-out evidence

- **Status:** Accepted (2026-10-21)
- **Source:** the [query improvement plan](../plans/query-improvement-2026-09-26.md) (acceptance rules; decisions of 2026-09-26 and 2026-09-28; the audit's proposals, answered 2026-09-28 to 30); the [overall review](../plans/README.md#retired) and statistics audit; the [rounds' record](../research/rounds.md); the [lever index](../reviews/levers.md); [judging a lever](../samples-and-testing.md#judging-a-lever); the [content-addressed queries plan](../plans/README.md#retired) (query checks, milestone 3; decision rules simulated, milestone 5)

## Context

Rounds r01 to r09 (2026-09-26 to 28) tried one lever per variant on the development slices, judged pairwise by a panel of hosted models; the levers they accepted became the defaults on 2026-09-28 (the owner: "promote clear champions to defaults"). Judging was $37.77 of the $45.82 spent to 2026-10-03.

The audits found the method's own flaws:
- **Repeated looks:** stopping at 16, 24 or 32 units accepted a lever with no effect 12–18% of the time, against 6–9% for one look.
- **Several variants a round:** 14–26% of rounds accepted some lever with no effect; "no worse" named no gain.
- **Dependence:** bands cut from one region were counted as independent.

Rounds are paused since r09b (2026-09-28). The owner, 2026-10-04: "We'll defer query rounds for just a bit longer." Since 2026-10-14 levers have mostly been measured on the controlled corpus ([0036](0036-controlled-documents-with-exact-keys.md)), the development slices beside it.

## Decision

**A round** (the lab's `eval/rounds` and `scripts/run_round.py`):
- **One lever per variant, on the same inputs as the baseline.** The unit is an input's claims, judged pairwise in both orders, each judge's two orders averaged before judges are combined; claims identical on both sides keep their labels.
- **Strata:** the kind of region and the document family.
- **Accepted when:**
  - the overall 90% interval lies above 0.50, or its lower bound is at least 0.45 with a gain named in advance (its metric and threshold)
  - no stratum's interval lies wholly below 0.45 on 6 units or more
  - failures and partials don't rise, and cost per page stays within a cap
- **Decided once, at a fixed sample** (32 units). Win rates are over changed units, with coverage beside them; intervals are cluster-robust by page region; a bound within 0.03 of its threshold is flagged borderline; strata below 0.45 on 10 units or more are watched.
- **Criteria are written into `round.json` before judging** and locked when it starts (the owner's decision A, 2026-09-28).
- **Rejected variants stay in the log,** so ideas aren't retried blindly.
- **Queries are checked before judging.** The owner (2026-09-28): "Ability to easily dump, view, and validate sample queries by a high-end model or human certainly would be good to avoid wasting time on obvious errors"; "The strong model pass per round, including yourself and a few others, seems wise".
  - After replay, each variant's queries are dumped against the baseline's (`queries dump`: changed, added and removed queries only), and checkers look for obvious errors: junk or misplaced context, wrong headings or stems, cut-off text, bad images, rules that don't apply.
  - The checkers, left to Claude by the owner: Claude reading the dump, Gemini 3.1 Pro and MiMo-V2.6-Pro (`scripts/run_round.py`, `QUERY_CHECKERS`, with the trial that chose them); 30 queries a variant, at most $2 a round (`round.json`: `query_checks`).
  - Only a problem in what the variant changed holds the round (exit 4), until fixed or accepted (`--accept-checks`). Older problems go to the lever index as leads.

**Promotion** (decision A): a lever reaches the defaults only after a combination round and a held-out check, and the held-out effect is the one quoted. The held-out rule (the owner, 2026-09-30: "Use middle rule"): mean above 0.5, lower bound at least 0.45, no stratum loss.

**A post-mortem for every lever after every round.** The owner, 2026-09-30: "always have a post-mortem analysis/review for levers after each round (whether good or bad or useless), e.g. based on judging/inspecting a random subset of positive and negative results, with attention to whether there's any obvious direction to tweak or partition them". `postmortem.py` samples wins, losses and splits; Claude writes the round's review from it. Every lever idea gets a row in the lever index when raised; levers not accepted or parked are tried again against later defaults.

**Judges** (the owner, 2026-09-28): a cheap judge (MiMo-V2.6-Pro) on every unit, a second (Qwen3.5-397B) where it leaves a unit unsettled; the expensive confirmation judges off by default. A round names its rubric; document administration is neutral from v2.

**Budget:** a round pauses at its cap, or on an out-of-balance error, and resumes without paying again: recordings go into the fixture, verdicts are cached, and the ledger records every attempt.

**While rounds are paused,** a lever is measured on the controlled corpus by Claude's paired-documents method (since 2026-10-14; `scripts/paired.py`):
- arms share one answer archive, so a query a lever leaves alone moves nothing
- each document's change is summed, with a sign-flip p-value; target and guards are named first
- a lever that rewords many queries is also judged against null arms (do-nothing changes of the same kind)
- better only when the target improves on the base and on every null at p < 0.1 with no guard worse

Defaults then change by judgement on that evidence, recorded in the lever index as "by judgement, not a round". The owner, 2026-10-02: "For early development, we shouldn't consider any levers defaults like a null hypothesis; just try to get things vaguely somewhat working by eyeball and intuition (or your non-biological equivalent) before we scientifically pursue systematic improvements."

## Consequences

- **Simulated error rates** (`tests/test_decisions.py`'s simulation, round 9's A/A unit scores as the null; seed 1, 400 rounds, run 2026-10-21):
  - a lever with no effect is accepted 6.8% of the time and lands on "no worse" 11.5%; with five variants a round, some null lever is accepted in 27% of rounds
  - with five null variants a round, 3.8% of rounds promote one under the held-out rule (11.3% on the mean alone, 1.8% when the held-out round must win again)
  - a real effect with a true rate of 0.60, 0.65 or 0.70 is found 38%, 54% or 79% of the time at 32 units, and promoted under the held-out rule 20%, 45% or 71% of the time
  - on 2026-09-30's code: 5.8%, 11% and 26%; 4.5%, 12.5–12.8% and 1.0–1.4%; found 35%, 58% and 78%, promoted 47% at 0.65 and 73% at 0.70
- **Judging is most of a round's cost,** so a rubric change re-pays every verdict and is judged like a lever (an A/A control, golden prompts).
- **Paired documents can't see a change confined to one or two documents** (p can't fall below 0.5); such a lever is judged by inspecting them.
- **Open, in the plans index's *Resumed query rounds*:** model-proposed variants, rubric v7, the responder fixed per cycle, automatic acceptance (assumed, "to be confirmed"), levers acting on part of a page, the controlled stratum's part in acceptance, the measurements owed.
- **The rounds' working data left the repository** on 2026-10-03 (the owner); their record is [docs/research/rounds.md](../research/rounds.md), and five round batches stay as test fixtures.
