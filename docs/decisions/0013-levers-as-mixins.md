# 0013. Levers are mixins on a platform class, composed from data

- **Status:** Accepted (2026-10-02)
- **Source:** [architecture clean-up](../plans/architecture-cleanup-2026-10-02.md): [decisions](../plans/architecture-cleanup-2026-10-02.md#decisions-2026-10-02), [design](../plans/architecture-cleanup-2026-10-02.md#levers-as-mixins-on-a-platform-class), [progress](../plans/architecture-cleanup-2026-10-02.md#progress) milestones 3–5; [lever architecture research](../research/lever-architecture-2026-10-02.md), [the owner's direction](../research/lever-architecture-2026-10-02.md#the-owners-direction-2026-10-02-and-a-prototype); [code review 2026-10-01: decisions](../reviews/code-review-2026-10-01.md#decisions-2026-10-02) item 4

## Context

A lever (one way of reading documents, such as context lines or tiling) was a settings field plus every place that knew about it: branches where it acted, and five hand-kept tables that already disagreed. Segmentation levers were parameters of one seven-parameter function, parked levers branched through every request, and the order of a prompt's parts lived only in statement order.

## Decision

- **The owner (2026-10-02):**
  - "perhaps we should treat them as settings of some form for now"
  - "having one platform/container class for the instantiated configuration (instead of global state) would be relatively conventional OO. Order of classes would impact order of prompt text, but that's a permutation we can choose to exercise or not. In any case, condition-based composition isn't very robust or extensible, so I'd prefer mixins if the transition is viable. We could always start it as mixins that merely modify a set of configuration options, if that's the best we can easily do."
  - "yes use same lever model for all parts of the pipeline, and levers could have a simple common way to express their assumptions (e.g. as a small test to run after all mixins are applied) enabling detection of conflicts based on the final type instead of an intermediate type."
  - On the design's six points, proposed by Claude: "Looks good to me."
- **The platform** (`levers.Platform`) holds an instantiated configuration, replacing global settings state. It declares the pipeline's hooks, each with a default, and is a pydantic model, so every lever's settings are fields of one validated object.
- **A lever** (`levers.Lever`) is a pydantic mixin: its settings (each declared, [0011](0011-settings-classified-by-effect.md)), the hooks it provides, its marks in prompts (for diagnostics), its `off` settings and its assumptions.
- **A configuration is data:** an ordered list of lever names plus settings (`"levers": [...]` in a settings file). `levers.compose()` builds its class with `type()`, cached. Named configurations: `benchmarks/round0.json`, `benchmarks/champion.json`.
- **Hooks are chained or chosen:**
  - `@chained`: every provider adds its part and calls `super()` first, so the list's order is the parts' order.
  - `@chosen`: at most one lever decides (the tiler, say).
  - A platform-wide check refuses a second chooser, or a chained provider that doesn't call `super()`.
- **Order is prompt order.** Named configurations keep a fixed order; permuting is an experiment's explicit choice.
- **Assumptions run once on the final type,** collected from its method resolution order. A configuration that fails one is refused before any request.
- **One model for the whole pipeline:** extraction's five stages (instructions, context, segmentation, inclusion, matching); comparison (retrieval is the chosen hook `candidates`); judges' rubrics as clause mixins (the lab's `rubrics.py`).
- **Levers stay settings:** flat field names and `PDF_DIFF_*` variables are unchanged.
- **A lever left out asks exactly what its `off` settings ask.** Parked levers stay in the default configuration, switched off.

## Consequences

- Adding a lever touches only its class. The settings tables, bindings and docs follow from its declarations.
- Extraction's binding includes the order of the levers acting on it: reordering asks for `--reset` and changes queries, which are then paid for.
- A test holds the champion equal to the defaults, so a default can't move without a round.
- Behaviour spread over a class hierarchy is harder to read than a branch. `Settings.explain()` lists each hook's providers in order.
- The move kept every request byte-identical (golden requests, query snapshots of every slice), so nothing was re-recorded.
- Configurations as data make a lever search (combining and mutating configurations) possible; it's a tentative plan.
