# Improvement rounds, 2026-09-26 to 2026-09-28: the record

- **Date:** 2026-10-03, when the rounds' working data left the repository.
- **The owner:** "I don't believe we need benchmark rounds, for example, though having a historical record of what was tested and the outcomes could be useful under `docs/research/rounds.md` or similar."
- **Where the data is:** every round's folder (`benchmarks/rounds/<round>/`), the spot check sc01 (`benchmarks/spotchecks/sc01/`), the evaluation batches s01 and s02 (`benchmarks/batches/`), the rounds' history (`benchmarks/history.jsonl`) and the spend ledgers are in git history up to commit `d0a5e43` (2026-10-03).
  - A shallow clone leaves them out.
  - The five round batches the tests replay stay, under `tests/fixtures/rounds/`.

## What a round was

The [query improvement plan](../plans/query-improvement-2026-09-26.md) tried levers on how documents are read, one per variant.

- **Method:**
  - Each variant was read against the same baseline on the development slices.
  - The units whose claims changed were judged pairwise by a panel of hosted models, in both orders.
  - A variant was accepted only without a loss in any stratum (text, table, visual).
- **Held-out rounds** (`h`) checked accepted levers on slices never used to design them.
- **The levers accepted became the defaults on 2026-09-28** (`benchmarks/champion.json`).
- **The details** are in each round's review (linked below), the [lever index](../reviews/levers.md), and the [statistics audit](../reviews/statistics-audit-2026-09-28.md).

## Decisions

| Round | Set | Variant | Units judged | Win rate (90% interval) | By stratum | Decision | Review |
|---|---|---|---|---|---|---|---|
| r01 | dev | lead-in | – | – | – | – | [review](../reviews/round-01-2026-09-26.md) |
| r01 | dev | neighbours | – | – | – | – | [review](../reviews/round-01-2026-09-26.md) |
| r01 | dev | table-filter | 48 | 0.43 (0.35–0.51) | page 0.43 | inconclusive: judge more units | [review](../reviews/round-01-2026-09-26.md) |
| r01 | dev | text-layer | – | – | – | – | [review](../reviews/round-01-2026-09-26.md) |
| r01b | dev | lead-in | 15 | 0.71 (0.56–0.85) | table 0.71 | accepted: wins | [review](../reviews/round-01-2026-09-26.md) |
| r01b | dev | neighbours | 24 | 0.68 (0.56–0.80) | text 0.68 | accepted: wins | [review](../reviews/round-01-2026-09-26.md) |
| r01b | dev | table-filter | 12 | 0.41 (0.23–0.57) | page 0.41 | inconclusive: judge more units | [review](../reviews/round-01-2026-09-26.md) |
| r01b | dev | text-layer | 16 | 0.72 (0.56–0.88) | visual 0.72 | accepted: wins | [review](../reviews/round-01-2026-09-26.md) |
| r02 | dev | combined | 24 | 0.68 (0.54–0.81) | table 0.75; text 0.72; visual 0.56 | accepted: wins | – |
| r02h | heldout | combined | 16 | 0.71 (0.56–0.86) | table 0.81; text 0.55; visual 0.75 | accepted: wins | – |
| r03 | dev | bands | 16 | 0.83 (0.70–0.94) | visual 0.83 | accepted: wins | [review](../reviews/round-03-2026-09-26.md) |
| r03 | dev | grow | 16 | 0.80 (0.70–0.89) | visual 0.80 | accepted: wins | [review](../reviews/round-03-2026-09-26.md) |
| r03 | dev | stem | 24 | 0.63 (0.51–0.75) | table 0.51; text 0.69 | accepted: wins | [review](../reviews/round-03-2026-09-26.md) |
| r04 | dev | combined | 40 | 0.64 (0.54–0.73) | table 0.42; text 0.67; visual 0.71 | accepted: wins | – |
| r04h | heldout | combined | 24 | 0.69 (0.57–0.82) | table 0.71; text 0.68; visual 0.69 | accepted: wins | – |
| r05 | dev | details | 8 | 0.64 (0.41–0.86) | visual 0.64 | inconclusive: judge more units | [review](../reviews/round-05-2026-09-27.md) |
| r05 | dev | references | 17 | 0.50 (0.35–0.66) | table 1.00; text 0.47 | inconclusive: judge more units | [review](../reviews/round-05-2026-09-27.md) |
| r05b | dev | details | 20 | 0.50 (0.38–0.64) | visual 0.50 | inconclusive: judge more units | [review](../reviews/round-05-2026-09-27.md) |
| r05c | dev | details | 20 | 0.47 (0.34–0.61) | visual 0.47 | inconclusive: judge more units | [review](../reviews/round-05-2026-09-27.md) |
| r05d | dev | details | 21 | 0.42 (0.28–0.56) | visual 0.42 | inconclusive: judge more units | [review](../reviews/round-05-2026-09-27.md) |
| r06 | dev | locator | 32 | 0.49 (0.37–0.61) | visual 0.49 | inconclusive: judge more units | [review](../reviews/round-06-2026-09-27.md) |
| r06 | dev | reconcile | 32 | 0.58 (0.47–0.69) | table 0.59; text 0.72; visual 0.42 | no worse: accept only with another gain (e.g. cost) | [review](../reviews/round-06-2026-09-27.md) |
| r07 | dev | locator | 32 | 0.58 (0.47–0.68) | visual 0.58 | no worse: accept only with another gain (e.g. cost) | [review](../reviews/round-07-2026-09-27.md) |
| r07 | dev | reconcile | 32 | 0.54 (0.43–0.65) | table 0.47; text 0.61; visual 0.54 | inconclusive: judge more units | [review](../reviews/round-07-2026-09-27.md) |
| r08 | dev | charts | 32 | 0.59 (0.47–0.71) | visual 0.59 | no worse: accept only with another gain (e.g. cost) | [review](../reviews/round-08-2026-09-27.md) |
| r08 | dev | reconcile | 32 | 0.56 (0.45–0.67) | table 0.50; text 0.65; visual 0.54 | no worse: accept only with another gain (e.g. cost) | [review](../reviews/round-08-2026-09-27.md) |
| r09 | dev | aa | 32 | 0.48 (0.37–0.61) | table 0.67; text 0.40; visual 0.48 | inconclusive | [review](../reviews/round-09-2026-09-28.md) |
| r09 | dev | excerpts | 31 | 0.51 (0.39–0.63) | table 0.25; text 0.62; visual 0.44 | inconclusive (re-decided 2026-10-02, see the round-09 review) | [review](../reviews/round-09-2026-09-28.md) |
| r09b | dev | fragments | 32 | 0.66 (0.53–0.77) | table 0.00; text 0.77; visual 0.44 | accepted: wins (re-decided 2026-10-02, see the round-09 review) | [review](../reviews/round-09-2026-09-28.md) |
| r09h | heldout | fragments | 21 | 0.66 (0.50–0.81) | text 0.89; visual 0.40 | no worse: accept only with another gain (e.g. cost) (re-decided 2026-10-02, see the round-09 review) | [review](../reviews/round-09-2026-09-28.md) |

- **Win rate:** the variant's share of pairwise preferences against the baseline, with a 90% interval (bootstrap until 2026-09-28, then cluster-robust by page region).
- **Rounds r02 and r04** combined the levers accepted before them. Their records are in the round-01 and round-03 reviews and the plan's progress.
- **The defaults since 2026-09-28** (the champion):
  - neighbouring text, the text layer with images, table lead-ins, numbered-item stems, whitespace bands and grown tiles (rounds 1–4)
  - merged readings (r06–r08, no worse with fewer claims; the owner's design decision)
  - fragment quotes (r09b, held out in r09h)
  - skip empty tiles (cost only)

## Spend

Every model call's reported cost, from the ledgers, as of 2026-10-03.

- **By month:** September 2026 $43.39; October 2026 (to the 3rd) $2.43.
- **By kind:**
  - judging $37.77
  - extraction $5.25
  - comparison $1.13
  - eye tests $0.84
  - page tests $0.72
  - situating $0.13
- **By round:**

  | Round | USD | Round | USD | Round | USD |
  |---|---|---|---|---|---|
  | r00 | 0.83 | r04 | 1.70 | r06 | 3.38 |
  | r01 | 10.03 | r04h | 1.21 | r07 | 3.38 |
  | r01b | 3.40 | r05 | 1.04 | r08 | 3.55 |
  | r02 | 1.09 | r05b | 1.36 | r09 | 2.18 |
  | r02h | 0.96 | r05c | 0.99 | r09b | 0.55 |
  | r03 | 2.51 | r05d | 1.11 | r09h | 0.14 |

- **Other tags:**

  | Tag | USD |
  |---|---|
  | maintenance | 2.66 |
  | controlled documents | 1.05 |
  | eye tests | 0.84 |
  | page tests | 0.72 |
  | real revision pairs | 0.68 |
  | spot check sc01 | 0.46 |

- **Total:** $45.82.
- **The ledgers now stay local** (`benchmarks/ledger.jsonl`, git-ignored) for the budget caps. A month's spend is added here.

## Also removed, with their records

- **Spot check sc01:**
  - Its findings are in [spotcheck-sc01](../reviews/spotcheck-sc01-2026-09-30.md).
  - The owner (2026-10-03): "I won't get back to that spotcheck." So the survey it awaited is dropped, and nothing waits on it.
- **Evaluation batches s01 and s02:**
  - The panel's labels and the owner's. Their findings are in [evaluation-s01](../reviews/evaluation-s01-2026-09-25.md).
  - The owner: "I think we won't use those labels again."
- **The eye and page tests' generated pages,** and the page test's recorded answers. The findings are in [eye tests](eye-tests-2026-09-30.md) and [page tests](page-tests-2026-10-01.md). The eye tests' answers stay, as a test replays them.
