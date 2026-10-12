# 0029. A page's tiles are chosen by measures; the model's questions about tiling stay calibrated levers

- **Status:** Accepted (2026-10-12)
- **Source:** the [tile selection plan](../plans/tile-selection-2026-10-10.md), from the [trials review](../reviews/trials-2026-10-08.md)'s finding 5

## Context

A page's image tasks were its tiles, its figures read whole and its overview. Report-sized pages got full-width bands; anything wider got an evenly spaced, overlapping grid. On the samples' first 40 pages the grid cut 6,400 lines sideways on 236 of 244 pages, and 42% of tile answers held no claims. The owner, 2026-10-08: "We probably need a whole plan just to improve tile selection and find/create examples that lead to such perverse outcomes."

The owner's idea (2026-10-10): show the model a shrunk page and one sketch per candidate tiling, and ask which is best, calibrated first "with known-bad cuts and pseudo-random candidate ordering". Also: models asked to label regions, with "mixed" and "nonsense" labels, and "models could feasibly request an alternative tiling as a refinement option. It isn't necessarily a problem to combine claims from two different tilings of the same page."

What was found:
- **Measures without the model** (lines cut, figures split, content missed, tiles of decoration or blank, lines read twice, small text, images) rank the candidate cuts well. Choosing by them sends fewer images and no measure gets worse on any kind of page.
- **The model's answers can be calibrated,** and were:
  - It picks a known-good tiling over a known-bad one 95% of the time.
  - Its region labels lose 0.8% of content regions.
  - Asked, it names a cut for half the tiles that cut content.
- **Its answers add little the measures don't know.** Asked to choose, it picked XY-cut's large tiles on drawing sheets and lost facts. It can't see small print or how a region is cut.
- **Drawing sheets are the exception.** Larger tiles and skipped text tiles lose facts there.
- **A drawing's lines aren't decoration.** A plan's gridlines and a schematic's ducts are long and thin like rules.

## Decision

- **Candidates:** each page's cut is chosen among bands (where today gives them), the grid, the snapped grid and XY-cut.
- **The rule** (`tile_choice: measures`): take the cut at least as good as the rest on every measure; where none is, keep the tiler's cut unless another beats it.
- **A drawing sheet keeps the tiler's cut** (the grid).
- **Decoration doesn't count** (`decoration`): rules, furniture repeated across pages, underlines, text masks, text panels and a backdrop don't make a tile worth sending. A long line inside a detected figure is the drawing, not a rule.
- **Text-only tiles** are skipped only as bands are today (`skip_text_only` stays off). A Word picture's text-only tiles are always sent, since no text task reads them.
- **Refinement** (`another_tiling: measures`, `halve_parts`):
  - A partial tile is read again under the page's next cut by the measures: the tiles holding whole what it cuts, each read once a page, tagged by their cut so a replay doesn't depend on answer order.
  - A tile continued at the claim limit is halved instead: it's full, not cut.
  - Halves are cut between lines, around the detected figures the tile holds, each holding at least a quarter of what the tile holds.
- **Claims from several tilings are kept,** as any two tasks' are ([0005](0005-union-provenance.md)).
- **The model's questions stay levers, off by default:**
  - choosing a tiling (`tile_choice: model`, with ties)
  - labelling regions (`region_labels`)
  - naming the edges a tile cuts (`another_tiling: asked`)
  - Each has a calibration bench (`scripts/calibration.py`, `labelling.py`, `asking.py`), and is trusted only where its profile passes.
- **Every change is a lever, off until measured;** defaults change by judgement on measured evidence ([0011](0011-settings-classified-by-effect.md), [0013](0013-levers-as-mixins.md)).

## Consequences

- **Fewer images:**
  - The controlled corpus: 873 → 841 image tasks, facts right 3,438 → 3,439, loose claims 490 → 432, misbound 261 → 244.
  - The samples' report pages send half their tiles.
  - Held-out slides cut half as many lines.
- **Defaults not set by a round:** four were set by judgement, recorded in the lever index and the plan. `benchmarks/round0.json` pins them off, so round 0 stays round 0.
- **Tests:** tests of a mechanism written against the old cut name it (`stubs.TILING_BEFORE`).
- **Asking the model needs a calibration first.** A model or prompt without a passing profile gets the measures' choice.
- **Not settled:**
  - Small text, which the measures count but don't weigh against fewer cuts.
  - Scans, where a tile's graphic is the page itself.
  - Real pages with no answer key: the evidence there is distinct values, not facts.
  - These are rows in the plans index (*Tile selection, further*) and the lever index.
