# Architecture clean-up, and levers as mixins

- **Status:** Planned (2026-10-02). Waiting for the owner's go, and open to change once the owner has read the full review.
- **From:**
  - the [code review of 2026-10-01](../reviews/code-review-2026-10-01.md), with the owner's decisions (2026-10-02)
  - the [lever architecture](../research/lever-architecture-2026-10-02.md) investigation, settled with the owner the same day
- **Before:** [controlled documents](controlled-documents-2026-10-01.md) milestone 4, which would otherwise grow `controlled.py` further.

## Goal

- **Fix** the bugs the review verified.
- **Give each concept one owner,** where today its knowledge sits in 3–7 hand-synchronised places.
- **Make levers mixins**, composed from data, for the whole pipeline.
- **Split the large modules.**
- **Package** the evaluation and bench tooling as an opt-in extra.

All of this without paying for answers twice: every step keeps requests byte-identical unless it says otherwise.

## Decisions (2026-10-02)

- **Temperature:** "just fixing temp at 0 for all the things is fine." Done (7ccccf1).
- **Defaults:** "model-neutral, but example settings could essentially be gemma-4." Done (7ccccf1).
- **Clean-up:** "Seems there's a fair bit of architecture clean-up to do."
- **Packaging:** "Python supports installing `package[extra-features]` ... this might offer a way to make meta-evaluation and bench tooling available via CLI without making it the default."
- **Levers:**
  - "perhaps we should treat them as settings of some form for now"
  - "condition-based composition isn't very robust or extensible, so I'd prefer mixins if the transition is viable. We could always start it as mixins that merely modify a set of configuration options"
  - "having one platform/container class for the instantiated configuration (instead of global state) would be relatively conventional OO"
  - "Order of classes would impact order of prompt text, but that's a permutation we can choose to exercise or not."
- **Scope of the lever model:** "yes use same lever model for all parts of the pipeline, and levers could have a simple common way to express their assumptions (e.g. as a small test to run after all mixins are applied) enabling detection of conflicts based on the final type instead of an intermediate type."
- **Claude's six design points:** the owner: "Looks good to me." They are recorded in the lever design below.
- **Images:** "we should not be committing images and images for development rounds. The fixture for CI testing answers is probably the exception."

## Design

### Levers as mixins on a platform class

- **The platform.**
  - One class holds an instantiated configuration and is passed where today's `Settings` object (`s`, `client.s`) travels: it replaces that global state.
  - It defines the pipeline's hooks, each with a default, for extraction (segmentation, context lines, inclusion, instructions, matching), situating, comparison and judging.
  - It is a pydantic model, so every lever's settings are fields of one validated object.
- **A lever.**
  - A mixin: a pydantic model with its own settings (fields with defaults and bounds), the hooks it changes, and its declarations:
    - its class (shaping or post)
    - the roles it binds
    - the stored results it invalidates
    - its mark in a prompt
  - The five tables kept by hand today (setting classes, role tuples, lever list, setting regions, lever marks) are generated from these declarations.
- **A configuration** is data: an ordered list of lever names plus their settings.
  - The class is composed from it with `type()` and cached.
  - Store binding hashes the configuration data. That replaces "compared against today's defaults" (review item 4).
  - A round's variant is a configuration.
  - Named configurations (round 0, the champion, each judge rubric version) live in the repository.
- **Order is prompt order.**
  - The chaining convention makes a list's order read as the order of the prompt's lines.
  - Named configurations keep a fixed order, so recorded answers keep replaying. Permuting is an experiment's explicit choice.
- **Chained and chosen hooks.**
  - Each hook is declared on the platform as *chained* (every lever adds its part: context lines, instructions) or *chosen* (one lever decides: tiling).
  - A platform-wide check: a chosen hook has exactly one provider, and every provider of a chained hook calls `super()`. A mixin can't then silently hide the ones below it.
- **Assumptions on the final type.**
  - Each lever may state its assumptions: small checks run once each, after composition, collected from the final type's method resolution order.
    - **Structural:** what the final type contains ("tile growing needs grid tiles").
    - **Behavioural:** run the hook on a tiny synthetic task ("my line appears once, before the source data").
  - A configuration that fails is refused before any request is made.
- **What stays outside.** Endpoint and runtime settings (URL, keys, timeouts, concurrency, cost caps, rate limits) stay a plain settings object beside the platform. The platform holds only what shapes what's asked. That split already exists in the settings classes, and it keeps transport out of what a search mutates.
- **`explain()`:** for each hook, the levers that contribute, in order. Behaviour spread across a class hierarchy is otherwise harder to read than a branch.
- **Levers stay settings,** as the owner put it: generated fields keep today's flat names (`context_before`) and environment variables, so configs, `.env` and recordings don't change.

### Packaging: the lab as an extra

- **Extras install optional *dependencies*,** not code: every module in a distribution is installed either way.
- **So the evaluation and bench tooling becomes its own distribution,** `semantic-pdf-diff-lab`, in this repository. The core declares it as the extra `lab`.
- **The lab registers its commands** through an entry-point group (`semantic_pdf_diff.commands`), and the core CLI lists whatever is installed.
  - `pip install semantic-pdf-diff[lab]` adds the rounds, review, spot-check and bench commands.
  - A plain install has only the diff tool.
- **Staged:** subpackages and an import-boundary test first; then the second distribution, which by then is a move.

## Milestones

Each ends with the full suite passing and a commit. Where requests mustn't change, `scripts/query_snapshot.py`, the golden prompts, the committed replays and the controlled-corpus byte test show they didn't.

1. **Guards.** Tests that would have caught the review's findings, before anything moves:
   - golden requests for situating and comparison on a synthetic document, under the defaults and under round 0 (judge prompts are golden already)
   - a consistency test of the hand-kept settings tables, until they're generated
   - the controlled-corpus test checking document ids and keys, not only existing PDFs
   - every test run with a cleared environment
   - test classes defined after `unittest.main()` moved above it
2. **Fixes** (the review's items; cents for the requests that change):
   - an evaluator-client helper with endpoint-only settings from the environment, and one cost cap per command, not per model or call (items 2, 9)
   - spot checks given `run_round`'s budget pause and public-slice guard (item 9)
   - situating bound to its budget settings (item 3)
   - refinement only after an answer, and a resumed run's stale task rows cleared (item 5)
   - rotation in `section_text` and figure detection, through `pages.py`, with the rotation test extended to figures and situating (item 6; rotated pages' requests re-asked)
   - an unreadable PDF recorded as a failed row, with the run continuing (item 7)
   - folder fixtures packed when their bytes differ (item 8)
   - one unit-score definition (item 11)
   - truncation not retried (item 12)
   - `reconcile` made linear (item 13)
   - the rounds chart and bands on rotated sheets (items 14, 15)
   - the controlled scorer:
     - typed values with units, fractions and dates
     - distinctive condition words only
     - the within / located-at tie
     - an offline re-score
3. **The lever platform:**
   - the platform class
   - lever mixins that set options only (the owner's starting point)
   - declarations generating the five tables
   - configuration digests for store binding (item 4)
   - chained and chosen hooks with the platform-wide check
   - assumption checks
   - `explain()`
   - round 0 and the champion as named configurations

   Requests unchanged.
4. **Extraction levers move into their mixins,** one kind at a time:
   - context lines (`Context`'s providers are nearly mixins already)
   - segmentation (`visual_regions` becomes a base tiler with chosen and chained hooks; parked levers leave the main path)
   - inclusion
   - instructions
   - matching

   Requests unchanged.
5. **Situating, comparison and judging on the same model.** Each judge rubric version becomes a named configuration of clause mixins, pinned byte for byte by the golden prompts. Requests unchanged.
6. **Single owners outside the levers:**
   - an `ExtractQuery` and a `Recipe` (prompts no longer parsed at markers)
   - a `Report` type
   - `fixtures.open` and a `Replayer`
   - a read-only `Store.open`
   - judgement files that carry their rubric
   - one rating loop
   - a `regions` module
   - a `values` module (number parsing and normalising)
   - HTML page helpers
7. **Module splits** (moves):
   - a `controlled/` package
   - `rounds` split by job behind a façade
   - `extract` split into sections, regions, quotes, context and tables
   - `llm.Client` split into request builder, transport and answers
   - `pipeline.py` out of the CLI, with scripts calling it rather than building command lines
   - a tested `RoundRunner` replacing `run_round.main`'s closure
8. **Packaging:**
   - `eval/` and `bench/` subpackages
   - the import-boundary test
   - lab commands through the entry-point group
   - then the `semantic-pdf-diff-lab` distribution and the `lab` extra
9. **Hygiene and docs:**
   - development rounds' page images and judge-cache page text leave version control, re-rendered byte-identically from the public slices when needed; the CI answers fixture stays
   - `git gc`; the ledger rotated
   - the user docs brought up to date, with a settings table generated from the lever declarations, and a test that every setting is documented

## Costs

- **Mostly none.** Every request-preserving step is checked offline.
- **Cents:** rotated pages' and situating requests re-asked after the fixes; one store rebind (answers replay).
- **No re-judging:** judge prompts stay byte-identical, and the goldens and committed replays prove it.

## Open questions

None now. The owner's reading of the full review may add some.
