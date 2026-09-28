# Overall review: the codebase and rounds 1–8

- **Date:** 2026-09-28
- **Scope:**
  - the whole codebase (about 7,600 lines in `src/` and `scripts/`, 124 commits since `v0.2.0`)
  - the query-improvement rounds r01–r08 (26 judged batches, 505 judged units plus r01's)
  - the plans' state
- **Method:**
  - Four read-only reviews ran in parallel: extraction, infrastructure, evaluation tooling, and a quantitative meta-analysis of every round's files.
  - I re-checked the most consequential findings: items 1, 3, 4, 5 and 6 of the priority list, by reading the code and running small snippets.
  - Nothing was changed and no model was called.

## Summary

- **The foundations are sound.**
  - Record/replay keying and the store's integrity are sound.
  - The threading model is simple.
  - Budget pauses resume cleanly.
  - Secrets stay out of outputs.
  - The round tooling has already caught its own measurement flaws four times.
- **The rounds have produced real but smaller gains than the individual results suggest.**
  - The combination rounds (the more honest measure) came out at:
    - r02 0.68 / r02h 0.71
    - r04 0.64 / r04h 0.69
  - The single-lever wins of 0.63–0.83 were inflated by early stopping.
- **Two champion levers are wrong on rotated drawing sheets.** The table lead-in and neighbouring text use unrotated coordinates, so on every dc, calg and ken sheet they supply text from beside the table (often the title block) rather than above it.
- **The round method accepts too easily.** Looking at 16, 24 and 32 units and stopping as soon as an interval clears roughly doubles the false-acceptance rate. 8 of 11 acceptances stopped early.
- **None of the gains has reached the tool yet.** The defaults are still round 0's, runtime settings included, and comparison, the product's output, has never been measured in a round.

## Priority fixes

| # | Severity | What | Where | Fix | Cost |
|---|---|---|---|---|---|
| 1 | Bug (verified) | **Rotated pages: lead-in, neighbouring text and stems use unrotated reading order.** dc-cd p1's table gets revision-table text as its "lead-in"; ken-cd's wiring schedule gets the title block. ken-cd tables were r04's worst stratum (0.25). | `extract.py:943–948` (`lead_in`, `table_top`), `:906–911` (`page_blocks`), `text_pieces`, `stem_index` (`sort=True` sorts unrotated) | Compare and sort by displayed rects; add rotated-page tests | Code only; sheet requests re-asked (cents) |
| 2 | Method | **Early stopping inflates acceptance:** 11.5–18% false acceptance with looks at 16/24/32, against 6–9% judged once at 32 (two independent simulations). | `run_round.py:200–202` | A fixed n ≥ 32, or a stricter interval at early looks; always a combination and held-out confirmation | None |
| 3 | Bug (verified) | **The ledger undercounts paid retries:** only a request's last attempt is recorded, though every attempt is billed (pydantic validation errors are retried). Round caps can be overrun. Separately, `record_runs --max-cost` applies per slice, not in total. | `llm.py:300–307` vs `_account`; `record_runs.py:76–77` | Account per attempt; pass the remaining cap to each slice | None |
| 4 | Bug (verified) | **`http.client.IncompleteRead`** (a dropped connection mid-response) isn't retried: it's an `HTTPException`, not an `OSError`, so it escapes and aborts a run. | `llm.py:343` | Add `http.client.HTTPException` to the retried errors | None |
| 5 | Bug (verified) | **`json_text` doesn't repair the failures we actually get:** raw control characters (26) and trailing text (3) among the fixture's 37 recorded failures. Under `record-new` they replay as failures forever. | `llm.py:81–102` | `json.JSONDecoder(strict=False).raw_decode` for the first object; re-ask those 37 once | Cents |
| 6 | Bug (verified) | **`reconcile`: a generic reading absorbs distinct facts.** "beam / W10X15" (text, ranked first) merges "Floor Beam @ Grid 4" and "@ Grid 5". Also, `reconcile` isn't bound to situating (figure links point at merged-away ids) and review batches read unreconciled evidence. | `readings.py:57–65, 89`; `provenance.py`; `review.py:95,104` | Require containment among all members; bind `reconcile` to the triage role; one evidence reader | None |
| 7 | Method | **Judging details:**<br>- Single-order verdicts (50 unit–judge pairs) carry position bias.<br>- Failed verdicts are re-sent on every chunk (the 30-minute stalls).<br>- Judges aren't told they see a sample, nor shown the extractor's context lines.<br>- A 2-unit stratum can reject a variant. | `rounds.py:283–289, 228, 309`; prompt | Average orders within a judge first; retry failures once; "n of N shown, the rest identical"; show the context lines; a minimum stratum size | None |
| 8 | Risk (my `record-new` change) | **Transient failures become permanent:** timeouts and exhausted 429/5xx retries are recorded as model failures, and `record-new` replays them. | `llm.py:257–262` | Record an error class; re-ask transient ones | None |
| 9 | Risk | **Any lever change clears all extraction in a store** (`SETTING_REGIONS` has no lever entries), so outside fixtures, toggling an image lever re-asks all text and tables. | `store.py:62–65` | Map levers to the regions they affect | None |
| 10 | Risk | **Rounds commit document content:** 728 page images, page text in 2,375 judge-cache files, `.git` at 49 MB. Fine for public slices; a leak if rounds ever run on sensitive documents. | `benchmarks/rounds/*` | Ignore images and judge caches, or refuse rounds on slices outside `slices.json` | None |
| 11 | Debt | **The tool's defaults were never measured:**<br>- claims_per_request 6<br>- output_tokens 1,400<br>- context_tokens 8,192<br>- image_tokens 1,200<br>- no champion levers<br><br>Every recording used 20 / 4,000 / 262,144 / 300 from `.env`. | `models.py:328–384` | Promote the champion together with the measured runtime settings | One full re-record (about $1) |

## The codebase

**Strengths**
- **Request keys and fingerprints are careful.** Every lever is either in the request key or in the prompt hash, so a variant never replays the wrong answer. That was checked lever by lever; `visual_rules` was the one gap, fixed in `62932ee`.
- **The threading model is simple and correct.** Workers only send HTTP; all state stays on one thread. `state["pending"]` accounting balances.
- **Store integrity:** per-task transactions, binding with dry-run and targeted reset, a WAL plus a writer lock, private permissions.
- **Secrets and privacy:**
  - The API key appears only in the request header.
  - URLs are redacted in reports.
  - HTTP error bodies aren't logged.
  - Archives are scanned in memory, with traversal, ratio and depth guards.
- **Evaluation tooling:**
  - Resumable and cached.
  - Rubrics versioned with replay compatibility.
  - Krippendorff's α and Dawid–Skene checked against references.
  - Human pages robust to partial answers.

**Debt**
- **`_pdf_job` is a 390-line closure** with about 15 nested functions and implicit shared state (`extract.py:779–1170`). The rotation bugs lived in its context builders. Moving `surrounding`, `lead_in`, `within` and `with_references` into a testable `PageContext` would help most.
- **Parked and rejected levers carry about 190 lines** and add branches to every request: `sheet_details`, `references`, `render_locator`, `real_table` and the `visual_rules` branch. Keep only those with a plausible next variant (locator on report pages; table filter), or move them to an experimental module.
- **Repeated page scans.** On a champion sheet page: 2 × `get_cdrawings` and 4 × `get_text`, where 1 and 2 would do. `skip_empty` recomputes the lines and graphics `grow` already has. That's minor next to model latency, but `--plan` pays it again.
- **Smaller items:**
  - The `get_cdrawings`/`get_drawings` fallback is repeated four times.
  - `FAMILY` is defined twice.
  - `rounds.fixture_tokens` is unused.
  - `Settings.from_env` can't parse list settings.
  - Stale docstrings: `fixtures.fingerprint`; the record/replay plan lists two fixture modes (now three).
- **Robustness:**
  - A corrupt archive member (bad CRC) crashes the scan.
  - The archive byte limit is checked after a member is decompressed.
  - The fixture's `used` marks are lost when a run fails, so a later prune can drop answers the interrupted run needed.
  - Billing detection is DeepInfra-specific (an OpenAI-style `429 insufficient_quota` is treated as throttling).

**Test gaps**
- The table lead-in (`table_context`) has no test at all.
- No context lever is tested on rotated pages.
- No test covers the generic-head merge, or `reconcile` toggling against a stored situation.
- `--plan` counts under the champion's levers are untested.
- `run_round.py`'s state transitions (pause, resume, reopen, resample) are untested.
- The small-stratum rejection and single-order weighting are untested.

## The rounds

**What they established** (details in the [lever index](levers.md)):

| Accepted into the champion | Evidence |
|---|---|
| Neighbouring text, text layer with images, table lead-in | r01b, then combined: r02 0.68 (0.54–0.81), r02h 0.71 (0.56–0.86) |
| Stems, bands, grown tiles | r03 singly (stopped early), then combined: r04 0.64 (0.54–0.73) at 40 units, r04h 0.69 (0.57–0.82) |
| Skip empty tiles | Mechanical: 4.5% fewer tile requests, 0 claims lost |
| Merged readings | r08 0.56 (0.45–0.67), no worse, with 13.5% fewer claims and the owner's decision |

- **Not accepted:** table filter, references, sheet details, tile locator, chart-reading rule.
- **Measurement lessons found along the way:**
  1. Fingerprints must leave levers out, or variants re-ask everything (r01).
  2. Judges must see the same claims from each side (r06).
  3. Recording must not retry old failures (r07).
  4. Judges must see the headings the extractor saw (r07).
  5. Crops change what gemma thinks is in scope (r05).
  6. Wide regions attach context from elsewhere on the page (r07).

**What the numbers say about the method** (from the meta-analysis):

| Measure | Value |
|---|---|
| Per-unit score SD | 0.38 (36% of units score 1.0, 18% score 0.0) |
| 90% half-width at 16 / 32 / 48 / 96 units | ±0.16 / ±0.11 / ±0.09 / ±0.06 |
| First chunk (8 units) against the final result | +0.08 on average, up to +0.24 |
| Qwen vs MiMo, same unit | sign agreement 68%, opposite 6%; κ 0.49; r 0.69 |
| Order flips (position consistency) | Qwen 19%, MiMo 14%; the first-shown set wins 54–57% of decisive verdicts (cancelled by judging both orders) |
| Judge retest with fixed claims (locator, r06 vs r07) | r 0.83, sign agreement 18 of 20 |
| Missing verdicts | Qwen 0.5%, MiMo 9.2% (timeouts on long units) |
| Cost per verdict | Qwen $0.019, MiMo $0.0045 |
| Units over 25 claims | 51% overall, 74% of visual; they score lower (0.54 vs 0.59) even after the sampling fix |
| Spend (ledger) | $36.55: judging $32.70 (89%), recording $3.85. About $5.20 per accepted lever. |

**Assessment**
- **The judges are consistent with each other and with themselves.** Most of the noise comes from re-extraction: every re-asked request is a fresh sample, and per-document directions wobble between rounds. Judge disagreement is the smaller part.
- **Levers that re-ask everything need an A/A control:** the baseline's changed requests re-asked once, to measure the noise floor in the same round. Prompt levers do this (charts; any rule), and so did r01 by accident.
- **Win rates are conditional on changed units.** A lever that changes 8 of 176 units and one that changes 91 aren't comparable, and decisions don't weigh coverage. The report joins series across rounds by variant name even though the baselines differ.
- **Pairwise preference can't see shared failures, and those dominate.** In r07–r08, 70% of verdicts tag both sides with duplicates. The 375 remarks most often name a fact both sides miss (159), duplicates (147) and text-layer or OCR trouble (131). The champion's absolute quality isn't tracked anywhere, and no round unit has a human label.
- **The held-out set has been used twice.** The current champion's newest parts (skip empty, merged readings) haven't had a held-out check.

## Where the project stands against its plans

- **Four plans are active at once:** scheduling and triage, record/replay, evaluation benchmarks, query improvement.
- **The main use case hasn't started.** Criteria-first comparison is next in line after scheduling, and every round so far ran extraction only.
- **Evaluation benchmarks:** the review batches and panel exist. Its milestones 1–4 aren't built: scoring against answer keys, synthetic documents with keys, expected-claim lists, retrieval scoring. Those are what would give an absolute quality measure.
- **Query improvement:**
  - Milestone 3's panel calibration against the owner's labels was done on s01/s02, not on round units.
  - Milestone 6 (variants proposed from failure clusters) has effectively begun through the remarks.
  - The planned "promote the champion at a milestone" is overdue.
- **Budget:** about $48.50 of $60 by estimate (ledger $36.55, plus about $12 of earlier panel work).

## Recommendations, in order

1. **Fix the verified bugs** (priority 1, 3, 4, 5, 6, 8). No model cost, except re-asking the rotated sheets' affected requests and the 37 recorded failures: cents.
2. **Change how rounds decide:**
   - a fixed 32 units per variant (no early looks), or a stricter interval at early looks
   - a minimum stratum size
   - orders averaged within a judge
   - failed verdicts retried once
   - judges told when they see a sample, and shown the extractor's context lines
   - an A/A control for levers that re-ask everything
3. **Cut judging cost:** MiMo as the primary judge, with Qwen only on split or low-confidence units. Smaller units: cap claims per unit, or judge per region. Together these would roughly halve the cost per decision.
4. **Promote the champion to the tool's defaults,** with the measured runtime settings (claims per request, token budgets). One full re-record, then a held-out check of the whole champion (about $2–3).
5. **Measure absolute quality:**
   - log tag rates for the champion each round
   - build the answer-key scoring from the evaluation plan
   - the owner's spot check at the top-up, picked to show what changed
6. **Then turn to comparison,** the product's output, with the same round machinery (criteria-first plan).
7. **Before any round on sensitive documents:** stop committing page images and page text.
