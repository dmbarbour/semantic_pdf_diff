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

Each lever acts only through its hooks (milestone 4), so a configuration may leave any out: a lever left out asks
exactly what its `off` settings ask (tests/test_golden_requests.py). The geometry the segmentation levers choose
from is in segmentation.py; a document's caches and access are in the reader the hooks are given (extract.Context).
"""
import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Extraction regions (regions.py): a changed setting clears the stored results of the regions it can change.
from .regions import ALL as ALL_REGIONS, TEXTUAL, VISUAL

# --- declarations ---------------------------------------------------------------------------------------------


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
    off: ClassVar[dict] = {}        # its settings that ask exactly what leaving it out of a configuration asks
    marks: ClassVar[dict] = {}

# Lines levers add to prompts (their text lives with the lever; extract.py writes them).
LAYER_NOTE = "TEXT LAYER OF THIS REGION (from the PDF, may be partial; use it to read small labels):"
LOCATOR_NOTE = ("The last image is the whole page, small, with this region outlined in red: it shows where the "
                "region sits, for orientation only.")

def _shaping(regions=ALL_REGIONS, roles=EXTRACT):
    return Declared("shaping", roles, regions)

def _selecting(regions=ALL_REGIONS, roles=EXTRACT):
    return Declared("selecting", roles, regions)

def _rules(rules):
    return "".join(rule.rstrip() + "\n" for rule in rules)

class ExtractPrompt(Lever):
    lever_name, stage, off = "extract_prompt", "instructions", {"extract_prompt": None}
    extract_prompt: Annotated[str | None, _shaping()] = None  # replaces the extraction instructions

    def base_instructions(self, builtin):
        return self.extract_prompt or super().base_instructions(builtin)

class ExtractRules(Lever):
    lever_name, stage, off = "extract_rules", "instructions", {"extract_rules": []}
    extract_rules: Annotated[list[str], _shaping()] = Field(default_factory=list)  # appended to the instructions

    def instructions(self, builtin):
        return super().instructions(builtin) + _rules(self.extract_rules)

class VisualRules(Lever):
    lever_name, stage, off = "visual_rules", "instructions", {"visual_rules": []}
    # appended for image tasks only (tiles, figures, overview)
    visual_rules: Annotated[list[str], _shaping(VISUAL)] = Field(default_factory=list)

    def region_rules(self, region):
        return super().region_rules(region) + (_rules(self.visual_rules) if region in ("tile", "figure", "overview") else "")

class Neighbours(Lever):
    lever_name, stage = "neighbours", "context"
    off = {"context_before": 0, "context_after": 0}
    marks = {"context_before": re.compile(r"^Before: \.\.\.(.*)$", re.M),
             "context_after": re.compile(r"^After: (.*)\.\.\.$", re.M)}
    context_before: Annotated[int, _shaping(TEXTUAL)] = Field(default=400, ge=0, le=20000)  # characters before
    context_after: Annotated[int, _shaping(TEXTUAL)] = Field(default=400, ge=0, le=20000)   # characters after

    def text_lines(self, reader, page_no, segments, text):
        """Text before the task's first block and after its last, crossing to the neighbouring pages when the
        page runs out."""
        lines = super().text_lines(reader, page_no, segments, text)
        before, after = self.context_before, self.context_after
        if not before and not after:
            return lines
        first, last = segments[0][0], segments[-1][0]
        blocks = reader.page_blocks(page_no)
        boxes = [b for b, _ in blocks]
        i0 = boxes.index(first) if first in boxes else 0
        i1 = len(boxes) - 1 - boxes[::-1].index(last) if last in boxes else len(boxes) - 1
        head = " ".join(t for _, t in blocks[:i0])
        tail = " ".join(t for _, t in blocks[i1 + 1:])
        if before and len(head) < before and page_no > 1:
            head = " ".join(t for _, t in reader.page_blocks(page_no - 1)) + " " + head
        if after and len(tail) < after and page_no < reader.pages:
            tail = tail + " " + " ".join(t for _, t in reader.page_blocks(page_no + 1))
        if before and head.strip():
            lines.append("Before: ..." + head.strip()[-before:])
        if after and tail.strip():
            lines.append("After: " + tail.strip()[:after] + "...")
        return lines

class TableContext(Lever):
    lever_name, stage = "table_context", "context"
    off = {"table_context": 0}
    marks = {"table_context": re.compile(r"^Above the table: \.\.\.(.*)$", re.M)}
    # characters of text above a table (lead-in, caption)
    table_context: Annotated[int, _shaping(frozenset({"table"}))] = Field(default=400, ge=0, le=20000)

    def table_lines(self, reader, page_no, top, flat):
        """Text just above a table (its lead-in sentence or caption)."""
        lines = super().table_lines(reader, page_no, top, flat)
        above = reader.text_above(page_no, top) if self.table_context else ""
        return lines + (["Above the table: ..." + above.strip()[-self.table_context:]] if above.strip() else [])

class StemContext(Lever):
    lever_name, stage = "stem_context", "context"
    off = {"stem_context": False}
    marks = {"stem_context": re.compile(r"^Within: (.+)$", re.M)}
    # tell text and table tasks which numbered items and headings they're under
    stem_context: Annotated[bool, _shaping(TEXTUAL)] = True

    def _within(self, reader, page_no, box):
        path = reader.stem_path(page_no, box) if self.stem_context else []
        return ["Within: " + " > ".join(path)] if path else []

    def text_lines(self, reader, page_no, segments, text):
        return super().text_lines(reader, page_no, segments, text) + self._within(reader, page_no, segments[0][0])

    def table_lines(self, reader, page_no, top, flat):
        return super().table_lines(reader, page_no, top, flat) + self._within(reader, page_no, top)

class References(Lever):
    lever_name, stage, parked = "references", "context", True
    off = {"references": False}
    marks = {"references": re.compile(r"^((?:Defined elsewhere|Cited): .+)$", re.M)}
    # abbreviations defined elsewhere and cited figures' captions as context
    references: Annotated[bool, _shaping(TEXTUAL)] = False

    def _cited(self, reader, text):
        line = reader.cited(text) if self.references else ""
        return [line] if line else []

    def text_lines(self, reader, page_no, segments, text):
        return super().text_lines(reader, page_no, segments, text) + self._cited(reader, text)

    def table_lines(self, reader, page_no, top, flat):
        return super().table_lines(reader, page_no, top, flat) + self._cited(reader, flat)

class TileLocator(Lever):
    lever_name, stage, parked = "tile_locator", "context", True
    off = {"tile_locator": False}
    marks = {"tile_locator": re.compile("^(" + re.escape(LOCATOR_NOTE) + ")$", re.M)}
    # with each tile, a page thumbnail outlining where the tile sits
    tile_locator: Annotated[bool, _shaping(VISUAL)] = False

    def tile_lines(self, reader, page, rect, tag):
        lines = super().tile_lines(reader, page, rect, tag)
        return lines + ([LOCATOR_NOTE] if self.tile_locator and tag.startswith("tile") else [])

    def tile_images(self, reader, page, rect, tag):
        images = super().tile_images(reader, page, rect, tag)
        return images + ([reader.locator(page, rect, tag)] if self.tile_locator and tag.startswith("tile") else [])

class Tiling(Lever):
    lever_name, stage, off = "tiling", "segmentation", {"tiling": "grid"}
    # bands: full-width, cut at whitespace gaps, on report-sized pages
    tiling: Annotated[Literal["grid", "bands"], _selecting(VISUAL)] = "bands"

    def tiles(self, reader, page):
        """On a report-sized page, full-width bands cut at whitespace gaps, skipping bands with no graphics (text
        tasks already cover them); otherwise the platform's grid."""
        side = self.tile_points
        if self.tiling != "bands" or page.rect.width > 1.6 * side:
            return super().tiles(reader, page)
        from .segmentation import _graphics, bands
        graphics = _graphics(page)
        return [(f"tile:{i}", r, "") for i, r in enumerate(
            b for b in bands(page, side) if any(b.intersects(g) for g in graphics))]

class GrowTiles(Lever):
    lever_name, stage, off = "grow_tiles", "segmentation", {"grow_tiles": False}
    grow_tiles: Annotated[bool, _shaping(VISUAL)] = True  # extend grid tiles to include every text line they cut

    def grow(self, reader, page, rect, within):
        rect = super().grow(reader, page, rect, within)
        if not self.grow_tiles:
            return rect
        from .segmentation import grown
        return grown(page, rect, lines=reader.lines(page)) & within

class SheetDetails(Lever):
    lever_name, stage, parked, off = "sheet_details", "segmentation", True, {"sheet_details": False}
    marks = {"sheet_details": re.compile(r"^(.+\. Detail [A-H]\d{1,2}\b.*)$", re.M)}  # "Drawing sheet. Detail B4: ..."
    # cut drawing sheets into their details, titled from the sheet
    sheet_details: Annotated[bool, _selecting(VISUAL)] = False

    def viewports(self, reader, page):
        """A drawing sheet's details (and its title-block and notes columns), each noted with the sheet's and
        the detail's titles. Side columns get no note: with "Title block" (round 5b), or even the sheet's title
        (5c), the model skipped a legible revision table as not engineering."""
        areas = super().viewports(reader, page)
        if not self.sheet_details:
            return areas
        from .segmentation import sheet_details
        found = sheet_details(page, reader.lines(page))
        if not found:
            return areas
        from .situate import title_block
        label, heading = title_block(page)
        sheet = " ".join(x for x in (label.title() if label else "Drawing sheet", heading) if x)
        return areas + [(rect, f"{sheet}. " + (f"Detail {number}: {title}" if title else f"Detail {number}") if number
                         else "") for number, title, rect in found]

class SkipEmpty(Lever):
    lever_name, stage, off = "skip_empty", "segmentation", {"skip_empty": False}
    skip_empty: Annotated[bool, _selecting(VISUAL)] = True  # don't send tiles with no text, drawing or image

    def kept_tiles(self, reader, page, regions):
        """Blank tiles dropped, the others keeping their numbers (and so their recorded keys)."""
        regions = super().kept_tiles(reader, page, regions)
        if not self.skip_empty or not regions:
            return regions
        from .segmentation import _empty
        return [x for x, blank in zip(regions, _empty(page, [r for _, r, _ in regions], reader.lines(page))) if not blank]

class FigureTasks(Lever):
    lever_name, stage, off = "figure_tasks", "segmentation", {"figure_tasks": False}
    marks = {"figure_tasks": re.compile(r"^Caption: (.+)$", re.M)}
    # read each detected figure whole, besides the tile grid (which can cut through figures)
    figure_tasks: Annotated[bool, _selecting(frozenset({"figure"}))] = True

    def figure_regions(self, reader, page, number, grid):
        """Each detected figure (drawing or image, with its caption) read whole, unless it fits inside one tile
        or is the whole page (a drawing sheet: the overview)."""
        regions = super().figure_regions(reader, page, number, grid)
        if not self.figure_tasks:
            return regions
        from .pages import shown
        from .segmentation import FIGURE_PAD
        for i, figure in enumerate(f for f in reader.figures(page, number) if f.region):
            box = (shown(page, figure.bbox) + (-FIGURE_PAD, -FIGURE_PAD, FIGURE_PAD, FIGURE_PAD)) & page.rect
            if box.is_empty or abs(box) >= 0.9 * abs(page.rect) or any(box in r for r in grid):
                continue
            regions.append((f"figure:{i}", box, f"Caption: {figure.caption}" if figure.caption else ""))
        return regions

class TableRules(Lever):
    lever_name, stage, off = "table_rules", "segmentation", {"table_rules": None}
    # a table of more body rows than this is read as a model says it should be (tablerules.py: rules applied to every
    # row, each row read by itself, or a summary), one query per table; 0, the default: every table (the owner,
    # 2026-10-05: "I was under the impression we'd also ask how to translate rows to claims even for short tables");
    # none: every table row by row, as before. Tables read on a grid: Excel's, CSV's, Word's and decks' (not yet PDF's,
    # nor charts' data)
    table_rules: Annotated[int | None, _selecting(frozenset({"table"}))] = Field(default=0, ge=0)

    def rules_from(self):
        return self.table_rules

class VisualTextLayer(Lever):
    lever_name, stage, off = "visual_text_layer", "inclusion", {"visual_text_layer": 0}
    marks = {"visual_text_layer": re.compile("^" + re.escape(LAYER_NOTE) + "\n(.*)$", re.M)}
    # characters of a region's PDF text sent with its image
    visual_text_layer: Annotated[int, _shaping(VISUAL)] = Field(default=1500, ge=0, le=20000)

    def region_text(self, reader, page, rect, layer, text):
        text = super().region_text(reader, page, rect, layer, text)
        if not self.visual_text_layer or not layer.strip():
            return text
        return (text + "\n" if text else "") + LAYER_NOTE + "\n" + " ".join(layer.split())[:self.visual_text_layer]

class TableFilter(Lever):
    lever_name, stage, parked, off = "table_filter", "inclusion", True, {"table_filter": False}
    # drop detected "tables" that are charts, frames or paragraphs
    table_filter: Annotated[bool, _selecting(frozenset({"table", "table-detection"}))] = False

    def keep_table(self, reader, page, table, rows):
        if not super().keep_table(reader, page, table, rows):
            return False
        from .tables import real_table
        return not self.table_filter or real_table(page, table, rows)

class QuoteMatch(Lever):
    lever_name, stage, off = "quote_match", "matching", {"quote_match": "exact"}
    # fragments: quotes normalized (Unicode, line-end hyphens) and made of "a ... b" or "a | b" parts;
    # excerpts: also words read in order across a pseudo-table. Applied as answers are stored: bound.
    quote_match: Annotated[Literal["exact", "fragments", "excerpts"], Declared("post", EXTRACT, TEXTUAL)] = "fragments"

    def loose_match(self, quote, text):
        if super().loose_match(quote, text):
            return True
        from .quotes import excerpted
        return self.quote_match != "exact" and excerpted(quote, text, in_order=self.quote_match == "excerpts")

class Reconcile(Lever):
    lever_name, stage, off = "reconcile", "matching", {"reconcile": False}
    # merge readings of one fact by different tasks into one claim; applied when evidence is read, not stored
    reconcile: Annotated[bool, Declared("post")] = True

    def reconciles(self):
        return self.reconcile

class ContinueReading(Lever):
    lever_name, stage, off = "continue_reading", "inclusion", {"continuations": 0}
    # an image task's answer incomplete with its claims at the limit is the model asking for more: the same task asked
    # again, told what it returned, for the rest (the owner, 2026-10-03: "enabling 'continue' based on a request from
    # the model"; splitting a picture loses its visual context). Text and table tasks are refined by splitting their
    # text instead: continued, a page's text task read the tables in it too, conditions from their headers copied onto
    # every row (the controlled schedules)
    continuations: Annotated[int, _selecting(VISUAL)] = Field(default=3, ge=0, le=20)

    def continuation_limit(self, region):
        return self.continuations if region in VISUAL else 0

class Align(Lever):
    lever_name, stage, off = "align", "comparison", {"align": False}
    # revisions: decide which items correspond across the two revisions before any value is judged, and settle equal
    # values without a model (align.py; docs/plans/revision-comparison-2026-10-02.md); proposals keep retrieval
    align: Annotated[bool, _selecting(roles=COMPARE)] = True

    def correspondence(self, left, right, mode):
        if not self.align or mode != "revisions":
            return super().correspondence(left, right, mode)
        from .align import align
        return align(left, right)

class VerifyVisuals(Lever):
    lever_name, stage, off = "verify_visuals", "comparison", {"verify_visuals": False}
    # send a claim's crop with it when it's compared, so the judgment can check the reading
    verify_visuals: Annotated[bool, _selecting(roles=COMPARE)] = True

    def comparison_images(self, evidence, output):
        images = super().comparison_images(evidence, output)
        return images + ([output / evidence.image] if self.verify_visuals and evidence.image else [])

class ExplainDifferences(Lever):
    lever_name, stage, off = "explain_differences", "comparison", {"explain_differences": False}
    # revisions: ask why each "different" or "uncertain" finding differs (a change, a renaming, not the same item...),
    # with the claims' items around them (compare.explain; docs/plans/revision-comparison-2026-10-02.md, milestone 4)
    explain_differences: Annotated[bool, _selecting(roles=COMPARE)] = True

    def explains(self, mode):
        return self.explain_differences and mode == "revisions"

class DedupeRepeated(Lever):
    lever_name, stage, off = "dedupe_repeated", "matching", {"dedupe_repeated": False}
    # extract exactly repeated table rows (same cells, same table position, 3+ pages) once
    dedupe_repeated: Annotated[bool, _shaping()] = True

    def dedupes_repeated_rows(self):
        return self.dedupe_repeated

# The canonical order: the prompt's (instructions, then context lines as the providers write them), then the
# stages that choose and keep. The defaults are the champion of the improvement rounds, promoted 2026-09-28
# (rounds 1-9; benchmarks/champion.json); round 0's settings are benchmarks/round0.json.
LEVER_CLASSES = (ExtractPrompt, ExtractRules, VisualRules, Neighbours, TableContext, StemContext, References,
                 TileLocator, Tiling, GrowTiles, SheetDetails, SkipEmpty, FigureTasks, TableRules, VisualTextLayer,
                 TableFilter, QuoteMatch, Reconcile, DedupeRepeated, ContinueReading, Align, VerifyVisuals,
                 ExplainDifferences)
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
            lines.append(f"{lever.lever_name} ({lever.stage or 'lever'}{', parked' if lever.parked else ''})"
                         + (": " if lever.model_fields else "") + ", ".join(f"{f} [{declared(cls, f).kind}]" if any(isinstance(m, Declared) for m in
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
        """The platform's own: room in the context for a prompt."""
        if self.context_tokens <= self.output_tokens + self.safety_tokens + 600:
            yield "Context must leave room for prompts after output and safety reserves"

    # --- hooks: instructions. The extraction prompt is the instructions (with {max_claims} unfilled), then the
    # region's rules, then the task's source type, section, context and data.

    @chosen
    def base_instructions(self, builtin):
        """The instructions rules are added to: the built-in ones (extract.EXTRACT), or a replacement."""
        return builtin

    @chained
    def instructions(self, builtin):
        return self.base_instructions(builtin)

    @chained
    def region_rules(self, region):
        """Rules for one kind of region's tasks only (region: text, table, tile, figure or overview)."""
        return ""

    # --- hooks: context lines. Each gets the document's reader (extract.Context): its caches and the document
    # access the providers share. A query's context is CONTEXT_NOTE followed by the lines, in the levers' order.

    @chained
    def text_lines(self, reader, page_no, segments, text):
        """Context lines for a text task: segments [(bbox, text)] in reading order, text the task's own."""
        return []

    @chained
    def table_lines(self, reader, page_no, top, flat):
        """Context lines for a table task: top, the box its lead-in sits above; flat, the rows as sent."""
        return []

    @chained
    def tile_lines(self, reader, page, rect, tag):
        """Context lines for an image task (tag: tile, figure or overview)."""
        return []

    @chained
    def tile_images(self, reader, page, rect, tag):
        """Images sent after an image task's own (paths under the store)."""
        return []

    # --- comparison: which claims are compared, and what a comparison is sent

    @chosen
    def candidates(self, left, right):
        """Pairs worth comparing, [(i, j, score)]: the platform's are a sparse TF-IDF bidirectional top-k union
        (compare.candidates); another retrieval (BM25, a reranker) would be a lever choosing otherwise."""
        from .compare import candidates
        return candidates(left, right, self)

    @chosen
    def correspondence(self, left, right, mode):
        """Which claims are compared, and which are settled without a model (align.Correspondence). The platform's:
        every retrieval candidate judged, none settled; the alignment lever decides otherwise for revisions."""
        from .align import Correspondence
        return Correspondence(self.candidates(left, right))

    @chained
    def comparison_images(self, evidence, output):
        """Images sent with a claim being compared (paths)."""
        return []

    @chosen
    def explains(self, mode):
        """Whether each "different" or "uncertain" finding is explained by a second call, which names the kind of
        difference (compare.explain): the platform's, never; the explain_differences lever's, in revisions mode."""
        return False

    # --- matching: how answers are checked and kept

    @chained
    def loose_match(self, quote, text):
        """Whether a quote that isn't in its source exactly (extract.quoted) is accepted all the same."""
        return False

    @chosen
    def reconciles(self):
        """Whether readings of one fact by different tasks are read as one claim (store.evidence)."""
        return False

    @chosen
    def continuation_limit(self, region):
        """How many times a task's answer that's incomplete with its claims at the limit is continued (tasks.TaskCore),
        by the task's region: the platform's, never."""
        return 0

    @chosen
    def rules_from(self):
        """The body rows a table may have before it's read by rules a model writes (tablerules.py); None: never."""
        return None

    @chosen
    def dedupes_repeated_rows(self):
        """Whether exactly repeated table rows are extracted once (extract.consume)."""
        return False

    # --- inclusion: what a task carries, and which detected tables are read

    @chained
    def region_text(self, reader, page, rect, layer, text):
        """An image task's source text, from its note (a caption, a detail's titles) and the region's text layer."""
        return text

    @chained
    def keep_table(self, reader, page, table, rows):
        """Whether a detected table is read as one."""
        return True

    # --- segmentation: which image tasks a page becomes. visual_regions is the order of steps; the hooks are
    # the choices within them.

    def visual_regions(self, reader, page, number):
        """[(tag, Rect, note)] in displayed coordinates: the page's tiles (none on a page no larger than one), the
        figures read whole, then the overview. A page divided into viewports (a sheet's details) is tiled one
        viewport at a time; otherwise the tiler chooses."""
        regions = []
        if max(page.rect.width, page.rect.height) > self.tile_points:
            areas = self.viewports(reader, page)
            regions = self._tile_areas(reader, page, areas) if areas else self.tiles(reader, page)
        regions = self.kept_tiles(reader, page, regions)
        grid = [r for _, r, _ in regions] or [page.rect]
        return regions + self.figure_regions(reader, page, number, grid) + [("overview", page.rect, "")]

    def _tile_areas(self, reader, page, areas):
        """Viewports tiled one by one, numbered across them: a small one whole; a larger one like a page, since
        larger crops lose small print (round 5: a 620-point crop missed a revision table 420-point tiles read)."""
        from .segmentation import tiles
        side, parts = self.tile_points, []
        for rect, note in areas:
            pieces = [rect] if max(rect.width, rect.height) <= 1.25 * side else list(tiles(rect, side))
            parts += [(self.grow(reader, page, r, rect), note) for r in pieces]
        return [(f"tile:{i}", r, note) for i, (r, note) in enumerate(parts) if not r.is_empty]

    @chosen
    def tiles(self, reader, page):
        """A page's tiles, [(tag, Rect, note)]: the platform's are an overlapping grid, each tile grown."""
        from .segmentation import tiles
        return [(f"tile:{i}", self.grow(reader, page, r, page.rect), "")
                for i, r in enumerate(tiles(page.rect, self.tile_points))]

    @chained
    def grow(self, reader, page, rect, within):
        """A tile as sent, from the tile as cut, kept within a bound (the page, or its viewport)."""
        return rect

    @chained
    def viewports(self, reader, page):
        """[(Rect, note)]: areas a page divides into, each tiled on its own; none, the page is tiled whole."""
        return []

    @chained
    def kept_tiles(self, reader, page, regions):
        """The tiles worth sending."""
        return regions

    @chained
    def figure_regions(self, reader, page, number, grid):
        """[(tag, Rect, note)] read besides the tiles (grid: the tiles kept, or the page)."""
        return []

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

def settings_table(cls):
    """Every setting as a Markdown table row (docs/configuration.md holds this table; tests/test_settings.py keeps it
    current): name, default, class, the lever owning it, the roles it binds, the regions it changes."""
    owner = {f: lever.lever_name for lever in LEVER_CLASSES for f in lever.model_fields}
    rows = ["| Setting | Default | Class | Lever | Bound by | Regions |", "|---|---|---|---|---|---|"]
    fields = cls.model_fields
    endpoint = [n for n in fields if declared(cls, n).kind == "endpoint"]
    levered = [f for lever in cls.lever_classes for f in lever.model_fields]
    order = endpoint + [n for n in fields if n not in endpoint and n not in levered] + levered
    for name in order:
        field = fields[name]
        d = declared(cls, name)
        default = field.get_default(call_default_factory=True)
        shown = json.dumps(default) if not isinstance(default, str) else f'"{default}"'
        regions = "all" if d.regions == ALL_REGIONS else ", ".join(sorted(d.regions))
        rows.append(f"| `{name}` | `{shown}` | {d.kind} | {owner.get(name, '')} | {', '.join(d.roles) or '-'} | "
                    f"{regions if d.roles and 'extract' in d.roles else '-'} |")
    return "\n".join(rows) + "\n"
