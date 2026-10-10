# 0028. The modules are layered without import cycles, each concept in one module

- **Status:** Accepted (2026-10-09)
- **Source:** the [code review of 2026-10-08](../reviews/code-review-2026-10-08.md), its architecture items 1 to 13; refines the one-owner rule of the [architecture clean-up](../plans/architecture-cleanup-2026-10-02.md)

## Context

The review found one import cycle through 21 of the product's modules, and two in the lab. They held together only through imports placed inside functions. The root was the schema module (`models`): it imported the levers at load, and the levers reached into seven implementation modules. Seventeen modules imported `models` for claim types alone. Concepts had no single owner either: the table grid lived in the rules module, Word's cell helpers were borrowed by the deck and workbook readers, and `extract.py` held five jobs.

## Decision

- **The schema is the bottom layer:** `schema.py` (claims, locators, answers, evidence, coverage, the report documents) imports nothing of the product. `settings.py` holds the settings and their loading. The client imports `Settings` for type checking only.
- **No import cycles,** in the product or the lab. `tests/test_boundaries.py` checks both, with the rule that the product never imports the lab ([0014](0014-lab-as-its-own-distribution.md)).
- **One module per concept,** importers import from it, and no module re-exports another's names. The moves of 2026-10-09 and 2026-10-10 are listed in the [code map](../how-it-works.md#code-map):
  - `jobs.py`: the scheduler and the readers
  - `visuals.py`: image tasks
  - `figures.py`: figure detection
  - `binding.py`: a store's binding policy
  - `tablegrid.py`: the grid
  - `office.py`: what the office formats share
  - `textmodel.py` and `textjob.py`: text formats' model and job
  - `failures.py`: how requests fail
  - `retrieval.py`
  - `explain.py`
  - `asking.py`: the ask, check and review exchange of both table queries
  - `recipes.py`
- **What a step needs travels as an object, not a long argument list:** `tasks.Task`, `extract.PdfTable`, `align.Alignment`.
- **The report's content is settled before it's saved,** and the writer only renders it, so the store keeps what the report shows.

## Consequences

- An import placed inside a function no longer hides a cycle. A new one fails `test_boundaries`.
- A new format registers in `textjob.FORMATS` (or `jobs.READERS`) instead of joining an if-chain.
- Callbacks that run late bind what they read when they're made (`PdfTable`): the late-binding bug the review found in the text formats' job (B1) can't recur there.
