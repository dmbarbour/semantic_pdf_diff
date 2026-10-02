# How levers are modelled, and how they could be

- **Date:** 2026-10-02
- **Asked by:** the owner, after the [code review](../reviews/code-review-2026-10-01.md): "We'll still be doing a lot with levers, and a lot of experiments with the parked ones (e.g. the genetic programming ideas later), perhaps we should treat them as settings of some form for now; I'd also like to investigate *how* levers are modeled, i.e. in architectural terms, e.g. some form of hierarchical mixin from OOP could support composition with less entanglement than conditional branching, leveraging extensibility."
- **Method:** read the lever code (`extract.py`, `models.py`, `provenance.py`, `store.py`) and the review's findings. Nothing changed.
- **Status:** a design investigation for the owner's review. Recommendations are Claude's.

## How a lever is built today

A lever is a `Settings` field plus every place that knows about it.

| Part | Where | Example: `context_before` |
|---|---|---|
| The value | A `Settings` field with a default and bounds | `context_before: int = 400` (`models.py`) |
| Its behaviour | A branch where it acts | `Context.neighbours` reads `self.s.context_before` |
| Its class (shaping, post, runtime, endpoint) | `models.SETTING_CLASSES` | "shaping" |
| Its role bindings | `provenance.LEVERS` and the three role tuples | in `LEVERS` |
| Its scope (regions whose stored results it invalidates) | `store.SETTING_REGIONS` | text |
| How to find it in a prompt | `extract.LEVER_MARKS` | `^Before: \.\.\.(.*)$` |
| Its documentation | `docs/configuration.md`, `levers.md` | (missing from configuration.md) |

**Seventeen levers, five kinds by where they act:**

| Kind | Levers | How it's built now |
|---|---|---|
| **Instructions** | `extract_prompt`, `extract_rules`, `visual_rules` | String concatenation in `extraction_template` and inline in `consume` |
| **Context lines** | `context_before`/`after`, `table_context`, `stem_context`, `references`, `tile_locator` | **Already composed:** `Context` has one provider per lever, joined in a fixed order (`for_text`, `for_table`, `for_tile`) |
| **Segmentation** (which regions become tasks) | `tiling`, `grow_tiles`, `sheet_details`, `skip_empty`, `figure_tasks`, `tile_points` | Branches inside `visual_regions(page, side, figures, tiling, grow, details, skip_empty)`: seven parameters, one per lever |
| **Inclusion** (what a task carries or keeps) | `visual_text_layer`, `table_filter` | Branches in `visual_task` and the table loop |
| **Matching and merging** (after the answer) | `quote_match`, `reconcile`, `dedupe_repeated` | Branches in `consume`, the visual check, `store.evidence` |

**What hurts:**
- **No single owner:** five tables are kept in step by hand, and they already disagree (review, item 3).
- **Entanglement:** segmentation levers are parameters of one function, so adding one changes a signature everyone calls. Parked levers (`sheet_details`, `references`, `tile_locator`, `table_filter`) branch through every request though they're off.
- **Implicit order:** a prompt's bytes depend on the order its parts are joined. That order lives in the code's statement order, not in a declaration.
- **Combination is by hand:** a variant is a dict of settings. Nothing describes which levers can combine, conflict or depend on each other, which genetic programming over configurations will need.

## Options

### A. Mixins: a query class composed from lever classes

```python
class Query:                        # the base: the prompt's fixed parts
    def context_lines(self, task): return []

class Neighbours(Query):
    def context_lines(self, task):
        return super().context_lines(task) + neighbours(task, self.s.context_before, self.s.context_after)

class Stems(Query):
    def context_lines(self, task):
        return super().context_lines(task) + within(task)

Champion = type("Champion", (Stems, Neighbours, Query), {})   # composed by inheritance
```

- **For:**
  - each lever's code is in one class
  - Python's method resolution order gives a deterministic composition
  - adding a lever needn't touch the others
- **Against:**
  - **Order is the class list.** The prompt's bytes then depend on the order of bases, a subtle place for a fact that recorded answers depend on.
  - **Levers act at five different points.** One query class would need a hook for each (regions, context, inclusion, instructions, matching), and most levers implement one. The base class becomes the place every concern meets: the entanglement moves rather than goes.
  - **Configurations are built at run time.** A round's variant or a genetic programme's individual would be a class made with `type()`. Classes are awkward to serialise, compare, hash for store binding, or mutate.
  - **Parameters still need a home:** `context_before`'s 400 characters is a value, not a class.

### B. Lever objects with declared hooks, composed by a pipeline

Each lever is an object that declares what it is and implements the hooks it needs.

```python
class Lever:                                # declarations, from which today's five tables are derived
    name: str
    params: type[BaseModel]                 # its settings: defaults, bounds, environment names
    kind: Literal["shaping", "post"]        # class
    roles: tuple[str, ...] = ("extract",)   # interpreters it binds
    regions: tuple[str, ...]                # stored results it invalidates
    order: int                              # where its contribution goes in a prompt: explicit, fixed

    # hooks: a lever implements only the ones it needs
    def regions(self, page, regions, p): return regions          # segmentation
    def context(self, task, p): return []                        # context lines
    def include(self, task, p): return task                      # what a task carries
    def instructions(self, task, p): return []                   # rules appended
    def accept(self, claim, task, p): return True                # matching and merging

class ContextLever(Lever):                  # shared behaviour by kind: inheritance where it fits
    regions = ("text", "table")
    def mark(self): ...                     # how its lines are found in a prompt (today's LEVER_MARKS)

class Neighbours(ContextLever):
    name, order = "neighbours", 10
    class params(BaseModel):
        before: int = Field(400, ge=0, le=20000)
        after: int = Field(400, ge=0, le=20000)
    def context(self, task, p):
        return neighbours(task, p.before, p.after)
```

A configuration is data: `{"neighbours": {"before": 400, "after": 400}, "stems": {}, "bands": {"grow": True}}`. The pipeline calls each active lever's hooks in declared order.

- **For:**
  - **One owner per lever:** its value, behaviour, class, roles, regions, prompt mark and documentation are declared together. The five tables are generated, and a test checks every lever declares them.
  - **Composition, not entanglement:** `visual_regions` becomes a base segmentation followed by the active segmentation levers' transforms. A parked lever is simply not in the configuration, so it costs nothing to keep.
  - **Explicit order:** `order` fixes where a lever's text goes. Today's bytes are reproduced by giving each lever its current position; `query_snapshot` proves it.
  - **Configurations are data:** a variant, a champion, or a genetic programme's individual is a dict that serialises, hashes for store binding, diffs in a post-mortem, and mutates or crosses over directly.
  - **Room for genetics:** a lever can declare `conflicts` and `requires` (`grow_tiles` needs grid tiling), so a mutation can't produce an invalid individual.
  - **Inheritance still has a place:** shared behaviour by kind (`ContextLever`, `SegmentationLever`) is a shallow hierarchy. This keeps the owner's idea where it fits, extending a kind, while combining levers is composition.
- **Against:**
  - more structure than a settings field, though each lever is small
  - the settings file's flat names (`context_before`) need a mapping to lever parameters; generated fields can keep the flat names
  - a migration, done by kind (below)

### C. Per-stage function chains

Each stage keeps a list of functions (`segmenters`, `context_providers`, `matchers`), and settings choose which are in the list.

- **For:** the least structure. It is B without declarations.
- **Against:** class, roles, regions and marks stay in separate tables, so the "no single owner" problem remains.

### D. A registry only

The meta-audit's lever registry: declarations in one table, code unchanged.

- **For:** fixes the hand-kept tables, a day's work.
- **Against:** the branches and the seven-parameter functions stay. It is B's first step, not an alternative to it.

## Recommendation

**B, reached through D.** First give levers one owner, then move behaviour into lever objects one kind at a time, starting where the code is already shaped that way.

1. **Declarations** (D):
   - a `Lever` declaration for each of the 17 levers
   - generate `SETTING_CLASSES`, the role tuples, `LEVERS`, `SETTING_REGIONS` and `LEVER_MARKS` from them
   - a test that they're complete
   - a generated settings table in `configuration.md`

   Fixes review item 3 on the way. No request changes.
2. **Context levers:** `Context`'s providers become `ContextLever`s, with orders matching today's statement order. The closest to the target already.
3. **Segmentation levers:** `visual_regions` becomes a base tiler (grid or bands) plus transforms (grow, details, skip empty). The parked `sheet_details` moves out of the main path.
4. **Inclusion, instructions, matching:** the rest, ending the inline branches in `consume`.
5. **Configurations as data:** a round's variant becomes a lever configuration. Store binding hashes the configuration rather than comparing defaults, which also fixes review item 4.

**At every step,** `query_snapshot` and the golden prompts must show byte-identical requests, so recorded answers keep replaying and no re-recording is paid.

**Settings, per the owner:** levers stay settings for now. The `Settings` fields keep their flat names and environment variables, generated from each lever's parameters, so configs, `.env` and recordings don't change.

## Questions for the owner

- **Scope beyond extraction.** Situating, comparison and judging have prompt choices too (rubric clauses are string-replace chains; review, A1). Should the same lever model cover them, so a genetic programme can search a whole pipeline's configuration, or only extraction?
- **Interactions.** For genetic programming, should levers declare conflicts and dependencies from the start, or only when the search needs them?

## The owner's direction (2026-10-02), and a prototype

**The owner:**
- "I'd be surprised if Python's ample metaprogramming facilities didn't enable tuning an inheritance list from a settings file. Putting every concern into one base class would be troublesome, but having one platform/container class for the instantiated configuration (instead of global state) would be relatively conventional OO. Order of classes would impact order of prompt text, but that's a permutation we can choose to exercise or not. In any case, condition-based composition isn't very robust or extensible, so I'd prefer mixins if the transition is viable. We could always start it as mixins that merely modify a set of configuration options, if that's the best we can easily do."
- On the two questions: "yes use same lever model for all parts of the pipeline, and levers could have a simple common way to express their assumptions (e.g. as a small test to run after all mixins are applied) enabling detection of conflicts based on the final type instead of an intermediate type."

**A throwaway prototype (Claude's, not project code) confirms the mechanics:**
- **Composition from data:** a configuration's ordered lever names are composed into a class with `type()`.
- **One settings model:** each lever is a pydantic model with its own fields and hooks, so the composed class merges every lever's settings into one validated model. A setting whose lever isn't in the configuration is rejected.
- **Order is prompt order:** hooks chain through `super()`, and reordering the list reorders the prompt's lines.
- **Assumptions on the final type:** each lever's assumptions, collected from the final type's method resolution order and run once each, caught a conflict (bands with tile growing).
- **Store binding:** the configuration hashes as data: ordered names plus settings.

**Claude's earlier objections, revised:**
- **"Configurations become classes, awkward to serialise":** wrong framing. The configuration is the data; the class is derived from it and cached.
- **Byte order:** stays a real constraint, met by a canonical order for named configurations; permutations are an experiment's explicit choice, as the owner says.
