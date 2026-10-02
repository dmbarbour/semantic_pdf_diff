"""Levers as mixins on a platform class (docs/plans/architecture-cleanup-2026-10-02.md, milestone 3).

The owner, 2026-10-02: "having one platform/container class for the instantiated configuration (instead of
global state) would be relatively conventional OO"; "condition-based composition isn't very robust or
extensible, so I'd prefer mixins if the transition is viable. We could always start it as mixins that merely
modify a set of configuration options"; levers "could have a simple common way to express their assumptions
(e.g. as a small test to run after all mixins are applied) enabling detection of conflicts based on the final
type instead of an intermediate type."

- A setting is a field annotated with its declaration (Declared): its class (endpoint, shaping, selecting,
  post), the roles whose stores it binds, and the extraction regions whose stored results it invalidates.
- A lever is a mixin (Lever): its settings, its marks in a prompt, the hooks it provides, its assumptions.
- The platform (Platform) holds the settings no lever owns and declares the pipeline's hooks: chained (every
  provider adds its part and calls super()) or chosen (one provider decides).
- A configuration is data: an ordered list of lever names and their settings. compose() turns the names into a
  class with type(), cached, checking its hooks; each instance runs every assumption in its type's MRO once.
- The tables once kept by hand (setting classes, role tuples, the lever list, setting regions, lever marks)
  are read off the declarations.

Milestone 3 moves the options; their behaviour still lives where it was, reading them, so every configuration
holds every lever (its order changes nothing yet). Milestone 4 moves behaviour into hooks, one kind at a time.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- declarations ---------------------------------------------------------------------------------------------

# Extraction regions (a task's prefix): a changed setting clears the stored results of the regions it can change.
ALL_REGIONS = frozenset({"text", "table", "tile", "figure", "overview", "vision", "table-detection"})
VISUAL = frozenset({"tile", "figure", "overview", "vision"})
TEXTUAL = frozenset({"text", "table"})

EXTRACT, TRIAGE, COMPARE = ("extract",), ("triage",), ("compare",)
EVERY_ROLE = EXTRACT + TRIAGE + COMPARE

@dataclass(frozen=True)
class Declared:
    """What a setting can change (docs/plans/content-addressed-queries-2026-09-28.md):
    - endpoint: how requests travel, budgets and limits; never what any query says
    - shaping: the content of queries (text, images, generation settings)
    - selecting: which queries are made (tasks added or removed), and which sources are read
    - post: what is done with answers; never an extraction query, though later stages read the result
    roles: the interpreters (stores' bindings) it's part of. regions: the extraction regions it can change.
    tests/test_settings.py toggles each setting through the whole pipeline and checks it keeps to its class."""
    kind: Literal["endpoint", "shaping", "selecting", "post"]
    roles: tuple = ()
    regions: frozenset = ALL_REGIONS

def declared(model, name):
    """A field's declaration."""
    return next(m for m in model.model_fields[name].metadata if isinstance(m, Declared))

STRICT = ConfigDict(extra="forbid")

# --- hooks ----------------------------------------------------------------------------------------------------

def chained(method):
    """A hook every provider adds its part to, calling super() first, so the levers' order is the parts' order."""
    method.__hook__ = "chained"
    return method

def chosen(method):
    """A hook one provider decides (a tiler, say): at most one lever may provide it."""
    method.__hook__ = "chosen"
    return method

def hooks(cls):
    """{hook name: chained or chosen}, as the classes in cls's MRO declare them."""
    out = {}
    for klass in reversed(cls.__mro__):
        for name, value in vars(klass).items():
            kind = getattr(value, "__hook__", None)
            if kind:
                out[name] = kind
    return out

def providers(cls, hook):
    """The classes defining a hook, in call order (the MRO), the platform's default last."""
    return [k for k in cls.__mro__ if hook in vars(k)]

def _calls_super(function):
    code = getattr(function, "__code__", None)
    return code is not None and "super" in code.co_names

def hook_problems(cls):
    """The platform-wide check: a chosen hook has one provider besides the platform's default, and every
    provider of a chained hook calls super(), so no mixin silently hides the ones below it."""
    problems = []
    for hook, kind in hooks(cls).items():
        mine = [k for k in providers(cls, hook) if issubclass(k, Lever)]
        if kind == "chosen" and len(mine) > 1:
            problems.append(f"{hook} is chosen by one lever, but {', '.join(k.lever_name for k in mine)} all provide it")
        if kind == "chained":
            problems += [f"{k.lever_name}'s {hook} doesn't call super(): the levers below it would be hidden"
                         for k in mine if not _calls_super(vars(k)[hook])]
    return problems

# --- levers ---------------------------------------------------------------------------------------------------

class Lever(BaseModel):
    """A mixin: its settings (fields declared with Declared), what it adds to prompts (marks: {setting: the
    pattern its lines match}, for diagnostics only), and optionally hooks and assumptions(self), which returns
    the problems it finds with the final configuration (each class's own runs once)."""
    model_config = STRICT
    lever_name: ClassVar[str] = ""
    stage: ClassVar[str] = ""      # instructions, context, segmentation, inclusion or matching
    parked: ClassVar[bool] = False  # kept as a setting, off by default (the owner, 2026-10-02)
    marks: ClassVar[dict] = {}

# Lines levers add to prompts (their text lives with the lever; extract.py writes them).
LAYER_NOTE = "TEXT LAYER OF THIS REGION (from the PDF, may be partial; use it to read small labels):"
LOCATOR_NOTE = ("The last image is the whole page, small, with this region outlined in red: it shows where the "
                "region sits, for orientation only.")

def _shaping(regions=ALL_REGIONS, roles=EXTRACT):
    return Declared("shaping", roles, regions)

def _selecting(regions=ALL_REGIONS, roles=EXTRACT):
    return Declared("selecting", roles, regions)

class ExtractPrompt(Lever):
    lever_name, stage = "extract_prompt", "instructions"
    extract_prompt: Annotated[str | None, _shaping()] = None  # replaces the extraction instructions

class ExtractRules(Lever):
    lever_name, stage = "extract_rules", "instructions"
    extract_rules: Annotated[list[str], _shaping()] = Field(default_factory=list)  # appended to the instructions

class VisualRules(Lever):
    lever_name, stage = "visual_rules", "instructions"
    # appended for image tasks only (tiles, figures, overview)
    visual_rules: Annotated[list[str], _shaping(VISUAL)] = Field(default_factory=list)

class Neighbours(Lever):
    lever_name, stage = "neighbours", "context"
    marks = {"context_before": re.compile(r"^Before: \.\.\.(.*)$", re.M),
             "context_after": re.compile(r"^After: (.*)\.\.\.$", re.M)}
    context_before: Annotated[int, _shaping(TEXTUAL)] = Field(default=400, ge=0, le=20000)  # characters before
    context_after: Annotated[int, _shaping(TEXTUAL)] = Field(default=400, ge=0, le=20000)   # characters after

class TableContext(Lever):
    lever_name, stage = "table_context", "context"
    marks = {"table_context": re.compile(r"^Above the table: \.\.\.(.*)$", re.M)}
    # characters of text above a table (lead-in, caption)
    table_context: Annotated[int, _shaping(frozenset({"table"}))] = Field(default=400, ge=0, le=20000)

class StemContext(Lever):
    lever_name, stage = "stem_context", "context"
    marks = {"stem_context": re.compile(r"^Within: (.+)$", re.M)}
    # tell text and table tasks which numbered items and headings they're under
    stem_context: Annotated[bool, _shaping(TEXTUAL)] = True

class References(Lever):
    lever_name, stage, parked = "references", "context", True
    marks = {"references": re.compile(r"^((?:Defined elsewhere|Cited): .+)$", re.M)}
    # abbreviations defined elsewhere and cited figures' captions as context
    references: Annotated[bool, _shaping(TEXTUAL)] = False

class TileLocator(Lever):
    lever_name, stage, parked = "tile_locator", "context", True
    marks = {"tile_locator": re.compile("^(" + re.escape(LOCATOR_NOTE) + ")$", re.M)}
    # with each tile, a page thumbnail outlining where the tile sits
    tile_locator: Annotated[bool, _shaping(VISUAL)] = False

class Tiling(Lever):
    lever_name, stage = "tiling", "segmentation"
    # bands: full-width, cut at whitespace gaps, on report-sized pages
    tiling: Annotated[Literal["grid", "bands"], _selecting(VISUAL)] = "bands"

class GrowTiles(Lever):
    lever_name, stage = "grow_tiles", "segmentation"
    grow_tiles: Annotated[bool, _shaping(VISUAL)] = True  # extend grid tiles to include every text line they cut

class SheetDetails(Lever):
    lever_name, stage, parked = "sheet_details", "segmentation", True
    marks = {"sheet_details": re.compile(r"^(Sheet .+ Detail .+)$", re.M)}
    # cut drawing sheets into their details, titled from the sheet
    sheet_details: Annotated[bool, _selecting(VISUAL)] = False

class SkipEmpty(Lever):
    lever_name, stage = "skip_empty", "segmentation"
    skip_empty: Annotated[bool, _selecting(VISUAL)] = True  # don't send tiles with no text, drawing or image

class FigureTasks(Lever):
    lever_name, stage = "figure_tasks", "segmentation"
    marks = {"figure_tasks": re.compile(r"^Caption: (.+)$", re.M)}
    # read each detected figure whole, besides the tile grid (which can cut through figures)
    figure_tasks: Annotated[bool, _selecting(frozenset({"figure"}))] = True

class VisualTextLayer(Lever):
    lever_name, stage = "visual_text_layer", "inclusion"
    marks = {"visual_text_layer": re.compile("^" + re.escape(LAYER_NOTE) + "\n(.*)$", re.M)}
    # characters of a region's PDF text sent with its image
    visual_text_layer: Annotated[int, _shaping(VISUAL)] = Field(default=1500, ge=0, le=20000)

class TableFilter(Lever):
    lever_name, stage, parked = "table_filter", "inclusion", True
    # drop detected "tables" that are charts, frames or paragraphs
    table_filter: Annotated[bool, _selecting(frozenset({"table", "table-detection"}))] = False

class QuoteMatch(Lever):
    lever_name, stage = "quote_match", "matching"
    # fragments: quotes normalized (Unicode, line-end hyphens) and made of "a ... b" or "a | b" parts;
    # excerpts: also words read in order across a pseudo-table. Applied as answers are stored: bound.
    quote_match: Annotated[Literal["exact", "fragments", "excerpts"], Declared("post", EXTRACT, TEXTUAL)] = "fragments"

class Reconcile(Lever):
    lever_name, stage = "reconcile", "matching"
    # merge readings of one fact by different tasks into one claim; applied when evidence is read, not stored
    reconcile: Annotated[bool, Declared("post")] = True

class DedupeRepeated(Lever):
    lever_name, stage = "dedupe_repeated", "matching"
    # extract exactly repeated table rows (same cells, same table position, 3+ pages) once
    dedupe_repeated: Annotated[bool, _shaping()] = True

# The canonical order: the prompt's (instructions, then context lines as the providers write them), then the
# stages that choose and keep. The defaults are the champion of the improvement rounds, promoted 2026-09-28
# (rounds 1-9; benchmarks/champion.json); round 0's settings are benchmarks/round0.json.
LEVER_CLASSES = (ExtractPrompt, ExtractRules, VisualRules, Neighbours, TableContext, StemContext, References,
                 TileLocator, Tiling, GrowTiles, SheetDetails, SkipEmpty, FigureTasks, VisualTextLayer, TableFilter,
                 QuoteMatch, Reconcile, DedupeRepeated)
REGISTRY = {c.lever_name: c for c in LEVER_CLASSES}
DEFAULT_LEVERS = tuple(REGISTRY)

# --- the platform ---------------------------------------------------------------------------------------------

class Composable(BaseModel):
    """What compose() builds on: the levers' order, the assumptions run on the final type, explain()."""
    model_config = STRICT
    levers: ClassVar[tuple] = ()          # the configuration's lever names, in order
    lever_classes: ClassVar[tuple] = ()   # and their classes

    @model_validator(mode="after")
    def _assumptions(self):
        problems = [p for klass in type(self).__mro__ if "assumptions" in vars(klass)
                    for p in vars(klass)["assumptions"](self)]
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @classmethod
    def explain(cls):
        """What the configuration is: each lever in order with its settings, and each hook with its providers: a
        chained hook's in the order of their parts, a chosen hook's decider (behaviour spread over a class
        hierarchy is otherwise harder to read than a branch)."""
        lines = []
        for lever in cls.lever_classes:
            lines.append(f"{lever.lever_name} ({lever.stage or 'lever'}{', parked' if lever.parked else ''}): "
                         + ", ".join(f"{f} [{declared(cls, f).kind}]" if any(isinstance(m, Declared) for m in
                                                                              cls.model_fields[f].metadata) else f
                                     for f in lever.model_fields))
        for hook, kind in hooks(cls).items():
            chain = [k.lever_name if issubclass(k, Lever) else "platform" for k in providers(cls, hook)]
            lines.append(f"hook {hook} ({kind}): " + (" -> ".join(reversed(chain)) if kind == "chained" else chain[0]))
        return "\n".join(lines)

class Platform(Composable):
    """The instantiated configuration: the settings that shape what's asked and how answers are kept, the
    pipeline's hooks, and the assumptions checked on the final type. Endpoint settings stay outside it."""
    marks: ClassVar[dict] = {"section": re.compile(r"^Section: (.+)$", re.M)}  # headings (always on)

    # Model-neutral defaults (the owner, 2026-10-02): a context most current vision models offer, and a
    # generous per-image bound. config.example.json holds gemma-4's measured profile (262,144 and 300).
    # The token budgets shape too: situating fits its text to what's left of the context window.
    context_tokens: Annotated[int, _shaping(roles=EXTRACT + TRIAGE)] = Field(default=32768, ge=2048)
    output_tokens: Annotated[int, _shaping(roles=EVERY_ROLE)] = Field(default=4000, ge=256)
    # Claims asked for per extraction request; raise with output_tokens (about 150 tokens per claim).
    # 20 and 4,000 are what every recording and round used (2026-09-26 on).
    claims_per_request: Annotated[int, _shaping()] = Field(default=20, ge=1, le=100)
    image_tokens: Annotated[int, _shaping(roles=EXTRACT + TRIAGE)] = Field(default=1200, ge=1)
    safety_tokens: Annotated[int, _shaping(roles=EXTRACT + TRIAGE)] = Field(default=400, ge=100)
    text_bytes: Annotated[int, _shaping(TEXTUAL)] = Field(default=1800, ge=200)
    image_side: Annotated[int, _shaping(VISUAL, roles=EXTRACT + TRIAGE)] = Field(default=1000, ge=256, le=2000)
    tile_points: Annotated[int, _selecting(VISUAL)] = Field(default=420, ge=100)
    refinement_depth: Annotated[int, _selecting()] = Field(default=1, ge=0, le=3)
    # Sections come from the PDF outline down to this depth, else fixed page ranges.
    section_depth: Annotated[int, _shaping()] = Field(default=2, ge=1, le=6)
    section_pages: Annotated[int, _shaping()] = Field(default=20, ge=1, le=1000)
    top_k: Annotated[int, _selecting(roles=COMPARE)] = Field(default=4, ge=1, le=30)
    min_score: Annotated[float, _selecting(roles=COMPARE)] = Field(default=0.10, ge=0, le=1)
    max_pairs: Annotated[int, _selecting(roles=COMPARE)] = Field(default=1000, ge=1)
    vision: Annotated[bool, _selecting(VISUAL)] = True
    # Situating stage: figure and section "about" statements after extraction.
    situate: Annotated[bool, _selecting(roles=())] = True
    verify_visuals: Annotated[bool, _selecting(roles=COMPARE)] = True
    response_format: Annotated[Literal["none", "json_object", "json_schema"], _shaping(roles=EVERY_ROLE)] = "none"
    seed: Annotated[int | None, _shaping(roles=EVERY_ROLE)] = None
    max_token_field: Annotated[Literal["max_tokens", "max_completion_tokens"], _shaping(roles=EVERY_ROLE)] = "max_tokens"
    aliases: Annotated[dict[str, str], _selecting(roles=COMPARE)] = Field(default_factory=dict)
    # Sources: rescan roots on every run ("auto") or only on `source update` ("manual").
    rescan: Annotated[Literal["auto", "manual"], _selecting(roles=())] = "auto"
    # Archive safety backstops: generous, and anything they stop is reported.
    max_zip_depth: Annotated[int, _selecting(roles=())] = Field(default=8, ge=4)
    max_source_bytes: Annotated[int, _selecting(roles=())] = Field(default=50 * 1024 ** 3, ge=1)
    zip_ratio_limit: Annotated[float, _selecting(roles=())] = Field(default=1000.0, gt=1)
    zip_ratio_min_bytes: Annotated[int, _selecting(roles=())] = Field(default=100 * 1024 ** 2, ge=0)

    def assumptions(self):
        """The platform's own: room in the context for a prompt; every lever whose behaviour the pipeline still
        reads directly is present (milestone 4 moves behaviour into hooks)."""
        if self.context_tokens <= self.output_tokens + self.safety_tokens + 600:
            yield "Context must leave room for prompts after output and safety reserves"
        missing = [name for name in DEFAULT_LEVERS if name not in type(self).levers]
        if missing:
            yield f"levers the pipeline still reads directly are missing: {', '.join(missing)}"

    def configuration(self):
        """The configuration as data: its levers in order and every setting the platform holds (endpoint
        settings aren't part of it). What store binding records, and what digest() hashes."""
        return {"levers": list(type(self).levers),
                **{name: value for name, value in self.model_dump(mode="json").items() if name in platform_fields(type(self))}}

    def digest(self):
        return hashlib.sha256(json.dumps(self.configuration(), sort_keys=True).encode()).hexdigest()[:16]

def platform_fields(cls):
    """The settings a platform class holds: every field not declared an endpoint setting."""
    return [n for n in cls.model_fields if declared(cls, n).kind != "endpoint"]

@lru_cache(maxsize=None)
def compose(levers=DEFAULT_LEVERS, base=Platform):
    """The platform class for an ordered list of levers (names in REGISTRY, or Lever classes): the levers mixed
    into the base, the first in the list first in a chained hook's parts (so a list reads as a prompt's order),
    checked for hook conflicts."""
    unknown = [n for n in levers if isinstance(n, str) and n not in REGISTRY]
    if unknown:
        raise ValueError(f"unknown levers: {', '.join(unknown)} (known: {', '.join(REGISTRY)})")
    classes = tuple(REGISTRY[n] if isinstance(n, str) else n for n in levers)
    names = tuple(c.lever_name for c in classes)
    if len(set(names)) != len(names):
        raise ValueError(f"a lever is listed twice: {list(names)}")
    cls = type(base.__name__, tuple(reversed(classes)) + (base,),
               {"__module__": __name__, "levers": names, "lever_classes": classes})
    problems = hook_problems(cls)
    if problems:
        raise ValueError("; ".join(problems))
    return cls

# --- tables read off the declarations ---------------------------------------------------------------------------

def setting_classes(cls):
    return {name: declared(cls, name).kind for name in cls.model_fields}

def role_settings(cls, role):
    """The settings a role's interpreter binds, in field order."""
    return tuple(name for name in cls.model_fields if role in declared(cls, name).roles)

def setting_regions(cls):
    """{setting: regions} for settings that change only some extraction regions; the rest change them all."""
    return {name: declared(cls, name).regions for name in cls.model_fields
            if declared(cls, name).regions != ALL_REGIONS}

def lever_marks(cls):
    """((setting, pattern), ...): the platform's marks, then each lever's, in the configuration's order."""
    return tuple(Platform.marks.items()) + tuple(item for lever in cls.lever_classes for item in lever.marks.items())

def lever_settings(levers=DEFAULT_LEVERS):
    """The settings the levers own (the rest are the platform's or endpoint settings)."""
    return tuple(f for name in levers for f in REGISTRY[name].model_fields)
