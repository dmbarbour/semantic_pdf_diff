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
import math
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
            problems.append(f"{hook} is chosen by one lever, but {', '.join(k.lever_name for k in mine)} all "
                            "provide it")
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
TABLE_CUT_NOTE = "THIS REGION CUTS A TABLE: its first row, then the rows in the region, as the PDF's text has them:"
TABLE_CUT_BYTES = 1500
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

# The extraction template's conditions, split (the split_conditions lever): scope stays in conditions, frame has a
# field of its own, and a tolerance goes with the value, in uncertainty.
CONDITIONS_SPEC = '"conditions":"load, scenario, time, tolerances, scope",'
SPLIT_SPEC = ('"conditions":"scope: the load, scenario, operating point, time or place it holds for", '
              '"frame":"how its value is read, if stated: what it is measured to or from, a datum, net or gross", '
              '"uncertainty":"a stated tolerance or uncertainty, if any",')
CONDITIONS_RULE = 'put conditions (e.g. "at theta = 0", "at rated speed") in conditions.'
SPLIT_RULE = (CONDITIONS_RULE + "\nPut what a value is measured to or from (to face of finish, to centreline, above "
              "a datum, net or gross) in frame, not conditions; a tolerance (± 0.5 mm) in uncertainty. A limit "
              "(maximum, at least, up to, below) isn't a frame: keep it with the value or the attribute.")
# The table rules' prompt likewise (tablerules.RULES): a frame bullet after the conditions', a frame in the templates
TABLE_CONDITIONS = "  is the heading or slide title the table sits under (what it's about, not a circumstance)\n"
TABLE_FRAME = ("- frame is how the values are read, where the table or the text above states it: what a height or "
               "length is\n  measured from or to (a datum, face of finish), net or gross; it isn't a condition\n")
TABLE_TEMPLATE = '"conditions":"...", "uncertainty":""'
TABLE_SPLIT = '"conditions":"...", "frame":"", "uncertainty":""'

class SplitConditions(Lever):
    lever_name, stage, off = "split_conditions", "instructions", {"split_conditions": False}
    # the reader's conditions split into scope (conditions) and frame (its own field), a tolerance with the value
    # (the claim context plan's milestone 4: readers' conditions held frame, "face of finish", and positions); the
    # template's lines replaced where a prompt keeps them
    split_conditions: Annotated[bool, _shaping()] = True

    def instructions(self, builtin):
        text = super().instructions(builtin)
        if not self.split_conditions:
            return text
        return text.replace(CONDITIONS_SPEC, SPLIT_SPEC).replace(CONDITIONS_RULE, SPLIT_RULE)

    def table_rules_text(self, builtin):
        text = super().table_rules_text(builtin)
        if not self.split_conditions:
            return text
        return text.replace(TABLE_CONDITIONS, TABLE_CONDITIONS + TABLE_FRAME).replace(TABLE_TEMPLATE, TABLE_SPLIT)

# The extraction template's stance (the read_holders lever): who the source reports holds a claim, and their attitude,
# asked of the reader where no holder column gives it (the claim context plan's milestone 5)
KIND_SPEC = '"kind":"text|table|chart|diagram",'
STANCE_SPEC = ('"stance":[{"holder":"who the source says holds it, if not the source itself",'
               '"attitude":"proposes, supports, opposes or reports"}],\n')
NEGATION_RULE = "Preserve negation, requirements versus proposed capabilities, ranges and inequality signs."
STANCE_RULE = ("\nWhere the source reports a claim as someone else's (\"Company A proposes\", \"according to B\", a "
               "quotation), put who holds it in stance with their attitude, not in entity or conditions; leave stance "
               "empty for what the source states in its own voice.")

class ReadHolders(Lever):
    lever_name, stage, off = "read_holders", "instructions", {"read_holders": False}
    # the reader asked who holds a claim the source reports as another's, and their attitude (the claim context
    # plan's milestone 5: RAN1's text and overview claims name no company); a row's holder column still gives its own
    read_holders: Annotated[bool, _shaping()] = False

    def instructions(self, builtin):
        text = super().instructions(builtin)
        if not self.read_holders:
            return text
        return text.replace(KIND_SPEC, STANCE_SPEC + KIND_SPEC).replace(NEGATION_RULE, NEGATION_RULE + STANCE_RULE)

# The table rules' prompt: a condition the text above names for some columns only kept to those columns' templates
# (the column_conditions lever; the coaster's "speeds are design values at the element's entry" written into its
# heights' claims, docs/reviews/levers.md)
TABLE_SHARED = "a state) belongs in the templates' conditions."
TABLE_SOME = (" A condition it names for some columns only (\"speeds are at the element's entry\") belongs in those "
              "columns' templates alone: write them apart from the other columns'.")

class ColumnConditions(Lever):
    lever_name, stage, off = "column_conditions", "instructions", {"column_conditions": False}
    # the table rules told a condition the text gives some columns isn't every column's (the claim context plan's
    # milestone 4: a sibling's scope misapplied)
    column_conditions: Annotated[bool, _shaping(frozenset({"table"}))] = False

    def table_rules_text(self, builtin):
        text = super().table_rules_text(builtin)
        return text.replace(TABLE_SHARED, TABLE_SHARED + TABLE_SOME) if self.column_conditions else text

# The table rules' templates: what the text names for some columns only, given by column and added by code to those
# columns' claims alone (the conditions_by_column lever: column_conditions' answers still wrote one template over
# every column, the speeds' scope with it, docs/reviews/levers.md)
TABLE_KEYED = (" One it names for some columns only (\"pressures are at the inlet\") goes in the template's "
               "\"column_conditions\" instead, by column ({\"D\": \"at the inlet\"}): it's added to those columns' "
               "claims alone.")
TABLE_KEYED_FRAME = (" A frame it gives some columns only (\"depths are below ground surface\") goes in "
                     "\"column_frame\" likewise ({\"B\": \"below ground surface\"}).")
TABLE_LAST_EXAMPLE = "  over columns B:C, entity {*.header}, attribute {A.cell_name}, value {*}, unit {A.cell_unit}\n"
TABLE_KEYED_EXAMPLE = ("- a table \"Bridge spans\" with columns Span | Length (m) | Clearance (m) | Load rating (t), "
                       "under \"load ratings are\n  for a single vehicle\": one template over columns B:D, entity {A}, "
                       "attribute {*.name}, value {*}, unit {*.unit},\n  column_conditions {\"D\": \"for a single "
                       "vehicle\"}\n")
TABLE_KEYED_EXAMPLE_FRAME = ("- a table \"Bridge spans\" with columns Span | Length (m) | Clearance (m) | Load "
                             "rating (t), under \"clearances\n  are above mean high water; load ratings are for a "
                             "single vehicle\": one template over columns B:D, entity {A},\n  attribute {*.name}, "
                             "value {*}, unit {*.unit}, column_conditions {\"D\": \"for a single vehicle\"},\n  "
                             "column_frame {\"C\": \"above mean high water\"}\n")
TABLE_NUMBER = '"number":true}],'
TABLE_BY_COLUMN = '"number":true, "column_conditions":{}}],'
TABLE_BY_COLUMN_FRAME = '"number":true, "column_conditions":{}, "column_frame":{}}],'

class ConditionsByColumn(Lever):
    lever_name, stage, off = "conditions_by_column", "instructions", {"conditions_by_column": False}
    # the table rules' templates given conditions (and frames, with split_conditions) by column (the claim context
    # plan's milestone 4: a sibling's scope misapplied)
    conditions_by_column: Annotated[bool, _shaping(frozenset({"table"}))] = False

    def table_rules_text(self, builtin):
        text = super().table_rules_text(builtin)
        if not self.conditions_by_column:
            return text
        frame = getattr(self, "split_conditions", False)
        return text.replace(TABLE_SHARED, TABLE_SHARED + TABLE_KEYED + (TABLE_KEYED_FRAME if frame else "")) \
            .replace(TABLE_NUMBER, TABLE_BY_COLUMN_FRAME if frame else TABLE_BY_COLUMN) \
            .replace(TABLE_LAST_EXAMPLE,
                     TABLE_LAST_EXAMPLE + (TABLE_KEYED_EXAMPLE_FRAME if frame else TABLE_KEYED_EXAMPLE))

class VisualRules(Lever):
    lever_name, stage, off = "visual_rules", "instructions", {"visual_rules": []}
    # appended for image tasks only (tiles, figures, overview)
    visual_rules: Annotated[list[str], _shaping(VISUAL)] = Field(default_factory=list)

    def region_rules(self, region):
        return super().region_rules(region) + (_rules(self.visual_rules) if region in ("tile", "figure", "overview")
                                               else "")

class ImagesFirst(Lever):
    lever_name, stage, off = "images_first", "instructions", {"images_first": False}
    # a request's images before its text, as Google's guidance for gemma-4 has them (docs/reviews/levers.md's ideas)
    images_first: Annotated[bool, _shaping(VISUAL, roles=EXTRACT + TRIAGE + COMPARE)] = True

    def puts_images_first(self):
        return self.images_first

LAYER_RULE = ("This region's text layer is cut at its edges: its fragments are no reason to set complete=false. "
              "Judge completeness by the image.")

class CompleteByImage(Lever):
    lever_name, stage, off = "complete_by_image", "instructions", {"complete_by_image": False}
    # an image task's completeness is the image's: under images_first, the model called tiles incomplete for their text
    # layer's cuts (the slices: image tasks not complete 43 -> 136, those blaming the text 8 -> 44)
    complete_by_image: Annotated[bool, _shaping(VISUAL)] = False

    def region_rules(self, region):
        rules = super().region_rules(region)
        return rules + (_rules([LAYER_RULE]) if self.complete_by_image and region in ("tile", "figure", "overview")
                        else "")

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
        def text(blocks, number):
            leave = self.context_left_out(reader, number)
            return " ".join(t for b, t in blocks if b not in leave)
        head = text(blocks[:i0], page_no)
        tail = text(blocks[i1 + 1:], page_no)
        if before and len(head) < before and page_no > 1:
            head = text(reader.page_blocks(page_no - 1), page_no - 1) + " " + head
        if after and len(tail) < after and page_no < reader.pages:
            tail = tail + " " + text(reader.page_blocks(page_no + 1), page_no + 1)
        if before and head.strip():
            lines.append("Before: ..." + head.strip()[-before:])
        if after and tail.strip():
            lines.append("After: " + tail.strip()[:after] + "...")
        return lines

class LeaveFurniture(Lever):
    lever_name, stage, off = "leave_furniture", "context", {"leave_furniture": False}
    # a page's running headers and footers and its page number (Context.furniture) are left out of neighbouring text,
    # a table's lead-in and image tasks' text layers (query checks, 2026-09-28: Gemini flagged them in 5 of 8
    # sampled queries). A text task still reads them
    leave_furniture: Annotated[bool, _shaping(TEXTUAL | VISUAL)] = False

    def context_left_out(self, reader, page_no):
        return reader.furniture(page_no) if self.leave_furniture else {}

class TableContext(Lever):
    lever_name, stage = "table_context", "context"
    off = {"table_context": 0}
    marks = {"table_context": re.compile(r"^Above the table: \.\.\.(.*)$", re.M)}
    # characters of text above a table (lead-in, caption)
    table_context: Annotated[int, _shaping(frozenset({"table"}))] = Field(default=400, ge=0, le=20000)

    def table_lines(self, reader, page_no, top, flat):
        """Text just above a table (its lead-in sentence or caption)."""
        lines = super().table_lines(reader, page_no, top, flat)
        above = reader.text_above(page_no, top, self.context_left_out(reader, page_no)) if self.table_context else ""
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

class Decoration(Lever):
    lever_name, stage, off = "decoration", "segmentation", {"decoration": False}
    # set decoration aside when a tile's graphics are counted: rules, margin bars, a frame's sides, what repeats in
    # the same place on neighbouring pages, an image behind a page's visible text (segmentation.decoration)
    decoration: Annotated[bool, _selecting(VISUAL)] = True

    def content_graphics(self, reader, page):
        graphics = super().content_graphics(reader, page)
        if not self.decoration:
            return graphics
        found = set(map(tuple, reader.decoration(page)))
        return [g for g in graphics if tuple(g) not in found]

class Tiling(Lever):
    lever_name, stage, off = "tiling", "segmentation", {"tiling": "grid", "band_width": 1.6}
    # bands: full-width, cut at whitespace gaps, on report-sized pages
    tiling: Annotated[Literal["grid", "bands"], _selecting(VISUAL)] = "bands"
    # pages up to this many tiles wide get bands; past 1.6, a band is lower, keeping its area (segmentation.band_height)
    band_width: Annotated[float, _selecting(VISUAL)] = Field(default=1.6, ge=1.0, le=6.0)

    def tiling_of(self, reader, page):
        """Bands on a report-sized page (bands skip those no graphic that counts touches: text tasks cover them)."""
        how = super().tiling_of(reader, page)
        return "bands" if self.tiling == "bands" and page.rect.width <= self.band_width * self.tile_points else how

class TileCut(Lever):
    lever_name, stage, off = "tile_cut", "segmentation", {"tile_cut": "grid"}
    # how a page not cut into bands is cut: grid (evenly, overlapping), snapped (the grid's cuts moved to whitespace,
    # overlapping only where they cross something), xycut (blocks found by whitespace both ways, merged into tiles)
    tile_cut: Annotated[Literal["grid", "snapped", "xycut"], _selecting(VISUAL)] = "grid"

    def tiling_of(self, reader, page):
        how = super().tiling_of(reader, page)
        return self.tile_cut if how == "grid" else how

class TileChoice(Lever):
    lever_name, stage, off = "tile_choice", "segmentation", {"tile_choice": "off"}
    # which cut a page gets, among the tilers' (bands where they apply, grid, snapped, xycut), each measured
    # (tilechoice.choose): the one at least as good as the rest on every measure; where none is, the default unless
    # another beats it (measures), or the model's choice among those no other beats (model; calibrated first:
    # scripts/calibration.py), read with each of two it names as equally good. A drawing sheet keeps the tiler's cut:
    # XY-cut's larger tiles lost facts there (milestones 3 and 5), and the small-text measure doesn't see why
    tile_choice: Annotated[Literal["off", "measures", "model"], _selecting(VISUAL)] = "measures"

    def tiling_of(self, reader, page):
        how = super().tiling_of(reader, page)
        if self.tile_choice == "off" or any(f.kind == "sheet" for f in reader.figures(page, page.number + 1)):
            return how
        from .tilechoice import choose
        return choose(self, reader, page, how, ask=self.tile_choice == "model")

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
        from .figures import title_block
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
        return [x for x, blank in zip(regions, _empty(page, [r for _, r, _ in regions], reader.lines(page),
                                                     reader.graphics(page))) if not blank]

class SkipTextOnly(Lever):
    lever_name, stage, off = "skip_text_only", "segmentation", {"skip_text_only": False}
    # don't send tiles holding text and no graphic that counts (the text tasks read them), on every page, as bands; or
    # on every page but a drawing sheet's (except_sheets: its text tasks miss what its tiles read, milestones 3 and 6)
    skip_text_only: Annotated[bool | Literal["except_sheets"], _selecting(VISUAL)] = False

    def kept_tiles(self, reader, page, regions):
        regions = super().kept_tiles(reader, page, regions)
        if not self.skip_text_only or not regions or not reader.text_read:
            return regions
        if self.skip_text_only == "except_sheets" and any(f.kind == "sheet" for f in reader.figures(page, page.number)):
            return regions
        texts = [box for box, _ in reader.lines(page) if not box.is_empty]
        graphics = self.content_graphics(reader, page)
        return [x for x in regions if not any(x[1].intersects(b) for b in texts)
                or any(x[1].intersects(g) for g in graphics)]

MOST_OF_PAGE = 0.5  # a table covering more of a page than this is a frame or a layout to the leave_text lever
NUMERIC = 0.6  # and one with fewer of its cells holding a number is left to the text tasks too (set on the corpus:
# its schedules and charts 0.75 to 1, a drawing's labels found as a table 0.5, a specification table 0.42)

class LeaveText(Lever):
    lever_name, stage, off = "leave_text", "inclusion", {"leave_text": "none"}
    # a PDF page's text tasks leave out the text of what other readers read: its detected tables (the table reader),
    # and with figures, its detected figures but their captions (the figure task or a tile). Flattened, a table's
    # columns shift and a chart's values pair with the wrong months (the corpus's text tasks: 139 misbound claims, 116
    # in tables and charts; docs/reviews/levers.md's ideas). A drawing sheet keeps its text (its frame is found as
    # tables), as does a page under a "table" covering most of it (a frame, a layout), and a table of words more than
    # numbers (a drawing's labels found as a table, a specification: the text tasks read facts there it missed)
    leave_text: Annotated[Literal["none", "tables", "tables and figures"], _shaping(TEXTUAL)] = "tables"

    def text_left_out(self, reader, page, number, tables):
        boxes = super().text_left_out(reader, page, number, tables)
        figures = reader.figures(page, number)
        if self.leave_text == "none" or any(f.kind == "sheet" for f in figures):
            return boxes
        area = page.mediabox.width * page.mediabox.height
        def numeric(rows):
            cells = [str(c) for row in rows for c in row if c is not None and str(c).strip()]
            return sum(any(ch.isdigit() for ch in c) for c in cells) >= NUMERIC * len(cells) if cells else False
        boxes = boxes + [tuple(t) for t, rows in tables
                         if (t[2] - t[0]) * (t[3] - t[1]) <= MOST_OF_PAGE * area and numeric(rows)]
        if self.leave_text == "tables and figures":
            from .figures import drawn_without_caption
            boxes += [drawn_without_caption(page, f) for f in figures if f.region]
        return boxes

class RegionLabels(Lever):
    lever_name, stage, off = "region_labels", "segmentation", {"region_labels": "off"}
    # the model labels the tiles a page sends (regionlabels.py; calibrated first: scripts/labelling.py): text,
    # decoration and blank tiles aren't sent, a nonsense tile is joined to its neighbour
    region_labels: Annotated[Literal["off", "model"], _selecting(VISUAL)] = "off"

    def sent_tiles(self, reader, page, regions):
        regions = super().sent_tiles(reader, page, regions)
        if self.region_labels == "off" or not regions:
            return regions
        from .regionlabels import label_tiles
        return label_tiles(self, reader, page, regions)

class AnotherTiling(Lever):
    lever_name, stage, off = "another_tiling", "segmentation", {"another_tiling": "off"}
    # a partial tile is read again under the page's next candidate cut, not in halves (retiling.py): the tiles of
    # that cut holding what the measures find it cuts; one continued at the claim limit is halved, for more room.
    # Always (measures), or where it asks: its issues say it's cut
    # (said), or it names the edges cutting content when a rule asks (asked; calibrated first: scripts/asking.py)
    another_tiling: Annotated[Literal["off", "measures", "said", "asked"], _shaping(VISUAL)] = "measures"

    def region_rules(self, region):
        from .retiling import RULE
        rules = super().region_rules(region)
        return rules + (_rules([RULE]) if self.another_tiling == "asked" and region == "tile" else "")

    def refined_tile(self, reader, page, tag, rect, done):
        if self.another_tiling != "off":
            from .retiling import asks, retiled
            found = retiled(self, reader, page, tag, rect, done) if asks(done, self.another_tiling) else None
            if found is not None:  # [] where the tiles that hold what it cuts are read already
                # read at depth 1 whichever tile asks first: its depth sets its text layer and whether it's refined
                # again (the determinism review, D7)
                return [(t, r, {"depth": 1}) for t, r in found]
        return super().refined_tile(reader, page, tag, rect, done)

class FigureRefinement(Lever):
    lever_name, stage, off = "figure_refinement", "segmentation", {"refine_figures": "halves"}
    # a partial tile mostly one figure it holds whole (a chart or drawing no figure task reads, since the tile does) is
    # looked at again whole, told what it returned and what it noted, not cut in halves (again); with the image budget
    # fixed, a half is no closer a look than the whole is (milestone 7)
    refine_figures: Annotated[Literal["halves", "again"], _selecting(VISUAL)] = "halves"

    def refined_tile(self, reader, page, tag, rect, done):
        if self.refine_figures == "again":
            from .segmentation import mostly_figure
            if mostly_figure(self, reader, page, rect):
                return [(f"{tag}-a", rect, {"continued": done["claims"], "noted": done["row"].get("issues", ())})]
        return super().refined_tile(reader, page, tag, rect, done)

class HalveParts(Lever):
    lever_name, stage, off = "halve_parts", "segmentation", {"halve_parts": False}
    # a refined tile's halves are cut around the detected figures it holds where they can be, as around a graphic: the
    # cut follows the parts (milestone 7; a figure of several graphics was cut through a gap inside it)
    halve_parts: Annotated[bool, _selecting(VISUAL)] = True

    def tile_parts(self, reader, page):
        parts = super().tile_parts(reader, page)
        if not self.halve_parts:
            return parts
        from .segmentation import inked_figures
        return parts + inked_figures(self, reader, page)

class RenderArea(Lever):
    lever_name, stage, off = "render_area", "segmentation", {"render_area": False}
    # render a long region to a square's pixel area (image_side squared), not its longer side to image_side: a 4:1
    # band gets twice the detail; the model's image budget is an area (research: gemma4-images-2026-09-30)
    render_area: Annotated[bool, _shaping(VISUAL)] = False

    def render_side(self, rect):
        side = super().render_side(rect)
        if not self.render_area or rect.is_empty:
            return side
        return round(side * math.sqrt(max(rect.width, rect.height) / min(rect.width, rect.height)))

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
    # none: every table row by row, as before. Tables read on a grid: Excel's, CSV's, Word's, decks' and PDF's (not
    # charts' data)
    table_rules: Annotated[int | None, _selecting(frozenset({"table"}))] = Field(default=0, ge=0)

    def rules_from(self):
        return self.table_rules

class TableReview(Lever):
    lever_name, stage, off = "table_review", "segmentation", {"table_review": 0}
    # the most times a table's rules, applied, are shown to the model with what they gave for three rows (or a
    # summary's claims): kept, or revised rules used if they pass the checks, and shown again; 0: never (the owner,
    # 2026-10-07: "Sort of an 'is this your final answer' opportunity? For tables, which are super-efficient due to
    # rules-driven processing, this seems a cheap lever to add"; "a cap of e.g. 10 will surely be safe yet more than
    # cover the use cases ... just keeping the last revision")
    table_review: Annotated[int, _shaping(frozenset({"table"}))] = Field(default=10, ge=0, le=100)

    def reviews_tables(self):
        return self.table_review

class TableStructure(Lever):
    lever_name, stage, off = "table_structure", "segmentation", {"table_structure": False}
    # a PDF table whose lines, after the heuristics (rows joined across unruled boundaries, two-line headers merged,
    # stacked tables split), still hold a suspect (a line with no rule above it, an empty first cell with values, a
    # lone label, units alone...) is asked how its lines group into rows, with its image: rules from a closed
    # vocabulary, applied mechanically, checked against lines the model copies from the image and reviewed as
    # table_review says (tablestructure.py; the owner, 2026-10-07: "comprehensible suggestions/rules about how to
    # work around confusing formatting, with feedback similar to how we approach claims rules")
    table_structure: Annotated[bool, _selecting(frozenset({"table"}))] = True

    def asks_structure(self):
        return self.table_structure

class VisualTextLayer(Lever):
    lever_name, stage, off = "visual_text_layer", "inclusion", {"visual_text_layer": 0}
    marks = {"visual_text_layer": re.compile("^" + re.escape(LAYER_NOTE) + "\n(.*)$", re.M)}
    # characters of a region's PDF text sent with its image
    visual_text_layer: Annotated[int, _shaping(VISUAL)] = Field(default=1500, ge=0, le=20000)

    def region_text(self, reader, page, rect, layer, text):
        text = super().region_text(reader, page, rect, layer, text)
        left = self.context_left_out(reader, page.number + 1)
        if left:  # what a block left out (its middle in the region) says, line by line
            from .pages import shown
            gone = {line for box, lines in left.items() for line in lines
                    if (shown(page, box).tl + shown(page, box).br) / 2 in rect}
            layer = "".join(line + "\n" for line in layer.splitlines() if " ".join(line.split()) not in gone)
        if not self.visual_text_layer or not layer.strip():
            return text
        return (text + "\n" if text else "") + LAYER_NOTE + "\n" + self.cut_layer(" ".join(layer.split()),
                                                                                 self.visual_text_layer)

class TableCuts(Lever):
    lever_name, stage, off = "table_cuts", "inclusion", {"table_cuts": False}
    marks = {"table_cuts": re.compile("^" + re.escape(TABLE_CUT_NOTE) + "\n", re.M)}
    # an image region cutting a detected table is sent the table's first row and the rows it touches, whole, as the
    # PDF's text has them (controlled documents, 2026-10-14: a tile holding a door schedule's lower rows, without its
    # header or door column, filed the doors' sizes under the rooms as "dimension 1" and "dimension 2"; the lever
    # index's "repeat a table's header block in every tile that cuts the table")
    table_cuts: Annotated[bool, _shaping(VISUAL)] = False

    def region_text(self, reader, page, rect, layer, text):
        text = super().region_text(reader, page, rect, layer, text)
        if not self.table_cuts:
            return text
        from .pages import native
        from .tables import cut_by
        note = cut_by(native(page, rect), reader.table_rows_on.get(page.number + 1, ()), TABLE_CUT_BYTES)
        return (text + "\n" if text else "") + TABLE_CUT_NOTE + "\n" + note if note else text

class TextCuts(Lever):
    lever_name, stage, off = "text_cuts", "inclusion", {"text_cuts": "bytes"}
    # sentences: a text block too long for one task is cut after a sentence's end (else a word's), and an image task's
    # text layer at a word's end, rather than where the bytes run out (query checks, 2026-09-28: "This focus is"
    # ending a HabEx chunk; "defined in the W" ending an IEA-22 text layer)
    text_cuts: Annotated[Literal["bytes", "sentences"], _shaping(frozenset({"text"}) | VISUAL)] = "bytes"

    def split_text(self, text, limit):
        from .tasks import split_at_ends, split_utf8
        return split_at_ends(text, limit) if self.text_cuts == "sentences" else split_utf8(text, limit)

    def cut_layer(self, layer, limit):
        from .tasks import cut_at_word
        return cut_at_word(layer, limit) if self.text_cuts == "sentences" else layer[:limit]

class TextSpans(Lever):
    lever_name, stage, off = "text_spans", "inclusion", {"text_spans": "section"}
    # page: a page's text blocks are grouped up to the byte budget across section boundaries, headings and all;
    # section: a text task's blocks are one section's. Claims are placed by their quote's block either way. Word and
    # Markdown documents cut at every heading: the controlled spec's "4 Link Failure Detection" went alone, and its
    # conditions came back as "declaration condition 1 | no acknowledgement received within 856 ms" (2026-10-14)
    text_spans: Annotated[Literal["section", "page"], _shaping(frozenset({"text"}))] = "page"

    def text_section_of(self, section_of):
        return (lambda box: None) if self.text_spans == "page" else super().text_section_of(section_of)

class RepeatedText(Lever):
    lever_name, stage, off = "repeated_text", "inclusion", {"repeated_text": "keep"}
    # first: a PDF page's text tasks leave out a block saying exactly what blocks in the same place said on REPEATED
    # earlier pages (Context.repeated: a watermark, a title block's stamp), read where it was first (query checks,
    # 2026-09-28: a ken-cd text task holding only "PRODUCED BY AN AUTODESK STUDENT PRODUCT")
    repeated_text: Annotated[Literal["keep", "first"], _shaping(TEXTUAL)] = "first"

    def text_left_out(self, reader, page, number, tables):
        boxes = super().text_left_out(reader, page, number, tables)
        return boxes if self.repeated_text == "keep" else boxes + reader.repeated(number)

class LoneRows(Lever):
    lever_name, stage, off = "lone_rows", "inclusion", {"lone_rows": False}
    # a table row the same as its header (a one-row table: "AC Rating | 6.4 kW") sent once, not as its own header too
    # (query checks, 2026-09-28: the Ken manual's "AC Rating ... 6.4 kW")
    lone_rows: Annotated[bool, _shaping(frozenset({"table"}))] = True

    def row_text(self, head, cells):
        if self.lone_rows and head == cells:
            return "Row: " + json.dumps(cells, ensure_ascii=False)
        return super().row_text(head, cells)

class TableFilter(Lever):
    lever_name, stage, parked, off = "table_filter", "inclusion", True, {"table_filter": False}
    # drop detected "tables" that are charts, frames or paragraphs
    table_filter: Annotated[bool, _selecting(frozenset({"table", "table-detection"}))] = False

    def keep_table(self, reader, page, table, rows):
        if not super().keep_table(reader, page, table, rows):
            return False
        from .tables import real_table
        return not self.table_filter or real_table(page, table, rows)

class SkipSheetTables(Lever):
    lever_name, stage, off = "skip_sheet_tables", "inclusion", {"skip_sheet_tables": False}
    # a page recognised as a drawing sheet isn't searched for tables: what's found there is mostly its frame, title
    # block and keynote lists, which its text tasks and tiles read anyway (they keep a sheet's text), and detection
    # costs 1.4 s a sheet (the 2026-10-08 code review, A20; the owner: "We can add skipping table detection as a
    # lever, np.")
    skip_sheet_tables: Annotated[bool, _selecting(frozenset({"table", "table-detection", "figure"}))] = False

    def detects_tables(self, reader, page, number):
        if not super().detects_tables(reader, page, number):
            return False
        return not self.skip_sheet_tables or not any(f.kind == "sheet" for f in reader.figures(page, number))

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

class Positions(Lever):
    lever_name, stage, off = "positions", "matching", {"positions": "conditions"}
    # provenance: a text block opening with an item's label ("Condition 2:", "(b)") in a sequence the source numbers
    # gives its claims a position (the label and the list's lead-in), and the label leaves their conditions:
    # inserting an item renumbers the rest, so the spec's timeout read as "Condition 2" against "Condition 3" was
    # judged uncertain (2026-10-14; docs/plans/claim-context-2026-10-14.md, milestone 1). Applied as answers are stored
    positions: Annotated[Literal["conditions", "provenance"], Declared("post", EXTRACT, TEXTUAL)] = "provenance"

    def list_positions(self, blocks):
        if self.positions == "conditions":
            return super().list_positions(blocks)
        from .positions import list_positions
        return list_positions(blocks)

    def positioned(self, claim, position):
        if self.positions == "conditions" or position is None:
            return super().positioned(claim, position)
        from .positions import without_label
        return claim.model_copy(update={"conditions": without_label(claim.conditions, position)}), position

class Records(Lever):
    lever_name, stage, off = "records", "matching", {"records": False}
    # context records (docs/plans/claim-context-2026-10-14.md, milestone 3): a page's lists (their lead-ins and
    # labels) and a drawing sheet's notes and legends kept once, as records its claims reference (Evidence.records);
    # a list item's position names its list instead of copying its lead-in. Applied as answers are stored
    records: Annotated[bool, Declared("post", EXTRACT)] = True

    def page_structure(self, page_no, blocks, is_sheet):
        positions, records = super().page_structure(page_no, blocks, is_sheet)
        if not self.records:
            return positions, records
        from .records import list_records, note_records
        lists, positions = list_records(page_no, blocks, positions)
        notes = note_records(page_no, blocks) if is_sheet() else []
        under = {n.label.casefold(): n.id for n in notes}  # a numbered list under a notes heading is that note's
        lists = [r.model_copy(update={"parent": under[r.text.casefold()]}) if r.text.casefold() in under else r
                 for r in lists]
        return positions, records + lists + notes

    def printed_name(self, claim):
        if not self.records:
            return super().printed_name(claim)
        from .records import printed_before
        return printed_before(claim.quote, claim.value)

    def table_record(self, page_no, task, grid, context, box):
        if not self.records:
            return super().table_record(page_no, task, grid, context, box)
        from .records import table_record
        return table_record(page_no, task, grid, context, box)

class SheetRecords(Lever):
    lever_name, stage, off = "sheet_records", "matching", {"sheet_records": False}
    # a drawing sheet's title block kept as a record every claim on the sheet references (docs/plans/claim-context-
    # 2026-10-14.md, milestone 4: two halls' sheets alike but for their title blocks). Applied as answers are stored
    sheet_records: Annotated[bool, Declared("post", EXTRACT)] = True

    def page_structure(self, page_no, blocks, is_sheet):
        positions, records = super().page_structure(page_no, blocks, is_sheet)
        if not self.sheet_records:
            return positions, records
        from .records import sheet_record
        sheet = sheet_record(page_no, is_sheet())
        return positions, records + ([sheet] if sheet else [])

class CarriedHolders(Lever):
    lever_name, stage, off = "carried_holders", "matching", {"carried_holders": False}
    # with table_holders: a holder column's blank cell takes the nearest name above it (a company named on its first
    # row only, as merged cells print; stance.py). Applied as answers are stored
    carried_holders: Annotated[bool, Declared("post", EXTRACT, frozenset({"table"}))] = False

    def table_holder(self, header, row, above=()):
        found = super().table_holder(header, row, above)
        if found or not (self.carried_holders and self.table_holders):
            return found
        from .stance import table_holder
        return table_holder(header, row, above, carried=True)

class ViewAttitudes(Lever):
    lever_name, stage, off = "view_attitudes", "matching", {"view_attitudes": False}
    # a held claim whose value is a yes or a no is its holder's view of the proposition ("CMCC | support for Proposal
    # 3.2.4 | Y": Proposal 3.2.4, support, CMCC supports), not a value of the holder (stance.py). Applied as answers
    # are stored
    view_attitudes: Annotated[bool, Declared("post", EXTRACT)] = False

    def held(self, claim):
        claim = super().held(claim)
        if not self.view_attitudes:
            return claim
        from .stance import as_view
        return as_view(claim)

class TableHolders(Lever):
    lever_name, stage, off = "table_holders", "matching", {"table_holders": False}
    # a table's holder column (Company, Source, Proponent...) holds every claim read from its row: the row's cell as
    # the claims' stance (docs/plans/claim-context-2026-10-14.md, milestone 5; stance.py). Applied as answers are
    # stored
    table_holders: Annotated[bool, Declared("post", EXTRACT, frozenset({"table"}))] = True

    def table_holder(self, header, row, above=()):
        if not self.table_holders:
            return super().table_holder(header, row, above)
        from .stance import table_holder
        return table_holder(header, row)

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
    lever_name, stage, off = "align", "comparison", {"align": False, "align_printed": False}
    # revisions: decide which items correspond across the two revisions before any value is judged, and settle equal
    # values without a model (align.py; docs/plans/revision-comparison-2026-10-02.md); proposals keep retrieval
    align: Annotated[bool, _selecting(roles=COMPARE)] = True
    # a claim's name as printed (the records lever's) weighed beside its attribute as read: one printed label, one
    # property, however readers name it (docs/plans/claim-context-2026-10-14.md, Claim identity)
    align_printed: Annotated[bool, _selecting(roles=COMPARE)] = False

    def correspondence(self, left, right, mode):
        if not self.align or mode != "revisions":
            return super().correspondence(left, right, mode)
        from .align import align
        return align(left, right, printed=self.align_printed)

class VerifyVisuals(Lever):
    lever_name, stage, off = "verify_visuals", "comparison", {"verify_visuals": False}
    # send a claim's crop with it when it's compared, so the judgment can check the reading
    verify_visuals: Annotated[bool, _selecting(roles=COMPARE)] = True

    def comparison_images(self, evidence, output):
        images = super().comparison_images(evidence, output)
        return images + ([output / evidence.image] if self.verify_visuals and evidence.image else [])

class ExplainDifferences(Lever):
    lever_name, stage, off = "explain_differences", "comparison", {"explain_differences": False,
                                                                   "explain_context": False}
    # revisions: ask why each "different" or "uncertain" finding differs (a change, a renaming, not the same item...),
    # with the claims' items around them (explain.py; docs/plans/revision-comparison-2026-10-02.md, milestone 4)
    explain_differences: Annotated[bool, _selecting(roles=COMPARE)] = True
    # each claim's list position and name as printed shown to the explainer (the records lever's; docs/plans/
    # claim-context-2026-10-14.md, milestone 3), so "renumbered" or "renamed" rests on the source's own labels
    explain_context: Annotated[bool, _shaping(roles=COMPARE)] = False

    def explains(self, mode):
        return self.explain_differences and mode == "revisions"

class Editorial(Lever):
    lever_name, stage, off = "editorial", "comparison", {"editorial": False}
    # a claim judged or settled equivalent at another place in its list ("Condition 2" then "Condition 3") reported
    # as renumbered, an editorial change (a pair judged otherwise isn't one statement moved). The owner, 2026-10-14,
    # on renumbering: "editorial changes, like a new page number if we added some text or section numbering if we
    # inserted a section" (docs/plans/claim-context-2026-10-14.md, milestone 3)
    editorial: Annotated[bool, Declared("post", COMPARE)] = True

    def editorial_notes(self, a, b):
        notes = super().editorial_notes(a, b)
        if not self.editorial or a.position is None or b.position is None or a.position.label == b.position.label:
            return notes
        return notes + [f"renumbered: {a.position.label} → {b.position.label}"]

class RecordChanges(Lever):
    lever_name, stage, off = "record_changes", "comparison", {"record_changes": False}
    # a context record restated between revisions (a sheet's note, a list's lead-in, a table's lead-in or headers),
    # numbers aside, reported once with the claims it reaches (records.changed_records; the claim context plan's
    # milestone 4, design question 6: the owner, "add it"); the records lever keeps them
    record_changes: Annotated[bool, Declared("post", COMPARE)] = True

    def changed_records(self, earlier, later, left, right):
        if not self.record_changes:
            return super().changed_records(earlier, later, left, right)
        from .records import changed_records
        return changed_records(earlier, later, left, right)

class JudgeContext(Lever):
    lever_name, stage, off = "judge_context", "comparison", {"judge_context": False}
    # each claim's context records (the records lever's: its list's lead-in, its sheet's notes, its table's title and
    # headers) shown to the judge, which rules on subject, scope and frame apart; one ruled different makes a
    # confident relation uncertain (compare.vetoes). The claim context plan's milestone 4, design question 4 (the
    # owner: "this is clearly a lever, but you can start with your preference")
    judge_context: Annotated[bool, _shaping(roles=COMPARE)] = False

    def judged_context(self, evidence, records):
        shown = super().judged_context(evidence, records)
        if not self.judge_context:
            return shown
        from .records import context_shown
        return {**shown, **context_shown(evidence, records)}

    def judging(self):
        if not self.judge_context:
            return super().judging()
        from .compare import RULINGS
        from .schema import RuledJudgment
        return RULINGS, RuledJudgment

class DedupeRepeated(Lever):
    lever_name, stage, off = "dedupe_repeated", "matching", {"dedupe_repeated": False}
    # extract exactly repeated table rows (same cells, same table position, 3+ pages) once
    dedupe_repeated: Annotated[bool, _shaping()] = True

    def dedupes_repeated_rows(self):
        return self.dedupe_repeated

# The canonical order: the prompt's (instructions, then context lines as the providers write them), then the
# stages that choose and keep. The defaults are the champion of the improvement rounds, promoted 2026-09-28
# (rounds 1-9; benchmarks/champion.json), and since 2026-10-12 the tile selection plan's, by judgement (decoration,
# tile_choice, another_tiling, halve_parts: docs/plans/tile-selection-2026-10-10.md, milestone 8), leave_text's
# tables, images_first, repeated_text's first, lone_rows, text_spans' page, positions' provenance, records,
# editorial, record_changes, split_conditions, sheet_records and table_holders (docs/reviews/levers.md); round 0's
# settings are benchmarks/round0.json.
LEVER_CLASSES = (ExtractPrompt, SplitConditions, ReadHolders, ColumnConditions, ConditionsByColumn, ExtractRules,
                 VisualRules, ImagesFirst, CompleteByImage, Neighbours, LeaveFurniture, TableContext, StemContext,
                 References, TileLocator, Decoration, Tiling, TileCut, TileChoice, GrowTiles, SheetDetails, SkipEmpty,
                 SkipTextOnly, RegionLabels, AnotherTiling, FigureRefinement, HalveParts, RenderArea, FigureTasks,
                 TableRules, TableReview, TableStructure, VisualTextLayer, TableCuts, TextCuts, TextSpans, RepeatedText,
                 LoneRows, TableFilter, SkipSheetTables, LeaveText, QuoteMatch, Positions, Records, SheetRecords,
                 TableHolders, CarriedHolders, ViewAttitudes, Reconcile, DedupeRepeated, ContinueReading, Align,
                 VerifyVisuals, ExplainDifferences, Editorial, RecordChanges, JudgeContext)
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
                         + (": " if lever.model_fields else "")
                         + ", ".join(f"{f} [{declared(cls, f).kind}]"
                                     if any(isinstance(m, Declared) for m in cls.model_fields[f].metadata) else f
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
    # a refined tile's half holds at least this share of what the tile holds (segmentation.halves; the owner,
    # 2026-10-09: "a tuning lever ... start with 25%")
    least_half: Annotated[float, _selecting(VISUAL)] = Field(default=0.25, ge=0.05, le=0.5)
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
    max_token_field: Annotated[Literal["max_tokens", "max_completion_tokens"],
                               _shaping(roles=EVERY_ROLE)] = "max_tokens"
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
    def table_rules_text(self, builtin):
        """The table rules' prompt (tablerules.RULES as builtin): the platform's, as it is."""
        return builtin

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
        (retrieval.candidates); another retrieval (BM25, a reranker) would be a lever choosing otherwise."""
        from .retrieval import candidates
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

    @chained
    def editorial_notes(self, a, b):
        """The editorial changes between two paired claims, as notes ("renumbered: Condition 2 → Condition 3"): the
        platform's, none."""
        return []

    @chosen
    def changed_records(self, earlier, later, left, right):
        """The context records restated between two revisions' paired content, with the claims they reach
        (records.changed_records): the platform's, none."""
        return []

    @chained
    def judged_context(self, evidence, records):
        """What a claim being judged shows besides its own fields ({field: value}); records: its content's {id:
        ContextRecord}: the platform's, nothing."""
        return {}

    @chosen
    def judging(self):
        """The judge's further instructions and the schema of its answer: the platform's, none and Judgment."""
        from .schema import Judgment
        return "", Judgment

    @chosen
    def explains(self, mode):
        """Whether each "different" or "uncertain" finding is explained by a second call, which names the kind of
        difference (explain.py): the platform's, never; the explain_differences lever's, in revisions mode."""
        return False

    # --- matching: how answers are checked and kept

    @chained
    def loose_match(self, quote, text):
        """Whether a quote that isn't in its source exactly (extract.quoted) is accepted all the same."""
        return False

    @chosen
    def list_positions(self, blocks):
        """{box: Position} for a page's text blocks [(box, text)] in reading order: where each sits in a sequence
        the source numbers. The platform's: none found."""
        return {}

    @chained
    def page_structure(self, page_no, blocks, is_sheet):
        """(positions {box: Position}, context records [ContextRecord]) for a page's text blocks [(box, text)] in
        reading order; is_sheet() says whether the page is a drawing sheet. The platform's: the list positions
        hook's, and no records."""
        return self.list_positions(blocks), []

    @chosen
    def printed_name(self, claim):
        """A claim's name as printed in its verified quote (the words before its value), or "": the platform's."""
        return ""

    @chained
    def table_holder(self, header, row, above=()):
        """(the Links holding the claims read from a table row,) given its table's headers, the row's cells and the
        rows over it in its table (nearest last): the platform's, none."""
        return ()

    @chained
    def held(self, claim):
        """A claim read with its holders (a stance), as stored: the platform's, as it is."""
        return claim

    @chained
    def table_record(self, page_no, task, grid, context, box):
        """A table read by rules, as a context record its claims reference (its title, headers and the context its
        rows are given), or None: the platform's."""
        return None

    @chosen
    def positioned(self, claim, position):
        """(claim, position) as a claim read in a block at that position (or None) is kept: the platform's, the claim
        as read and no position."""
        return claim, None

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
    def asks_structure(self):
        """Whether a PDF table with suspect lines is asked how its lines group into rows (tablestructure.py)."""
        return False

    @chosen
    def reviews_tables(self):
        """The most times a table's rules, applied, are shown to the model for review (tablerules.py); 0: never."""
        return 0

    @chosen
    def dedupes_repeated_rows(self):
        """Whether exactly repeated table rows are extracted once (extract.consume)."""
        return False

    # --- inclusion: what a task carries, and which detected tables are read

    @chained
    def text_left_out(self, reader, page, number, tables):
        """Unrotated boxes whose text blocks a PDF page's text tasks leave out, to the readers of what they hold
        (tables: [(box, rows)] of the tables detected and read): the platform's, none."""
        return []

    @chosen
    def row_text(self, head, cells):
        """A table row's source data, with the header it's read under: the platform's, both."""
        return "Header: " + json.dumps(head, ensure_ascii=False) + "\nRow: " + json.dumps(cells, ensure_ascii=False)

    @chosen
    def puts_images_first(self):
        """Whether a request's images come before its text: the platform's, after."""
        return False

    @chosen
    def split_text(self, text, limit):
        """A text block's chunks of at most limit bytes (a text task's, and a refined one's halves), no character
        dropped: the platform's, cut where the bytes run out."""
        from .tasks import split_utf8
        return split_utf8(text, limit)

    @chosen
    def text_section_of(self, section_of):
        """What parts a page's text blocks into tasks (section_of(box) names a block's section): the platform's, its
        sections."""
        return section_of

    @chosen
    def cut_layer(self, layer, limit):
        """An image task's text layer, its whitespace folded, cut to limit characters: the platform's, anywhere."""
        return layer[:limit]

    @chosen
    def context_left_out(self, reader, page_no):
        """{box: its lines} of a page's text blocks that neighbouring text, a table's lead-in and image tasks' text
        layers leave out (page_blocks' boxes): the platform's, none."""
        return {}

    @chained
    def region_text(self, reader, page, rect, layer, text):
        """An image task's source text, from its note (a caption, a detail's titles) and the region's text layer."""
        return text

    @chained
    def keep_table(self, reader, page, table, rows):
        """Whether a detected table is read as one."""
        return True

    @chained
    def detects_tables(self, reader, page, number):
        """Whether a PDF page is searched for tables (its number from 1)."""
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
        regions = self.sent_tiles(reader, page, self.kept_tiles(reader, page, regions))
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

    def tiles(self, reader, page):
        """A page's tiles, [(tag, Rect, note)]: cut as tiling_of names (tiles_for)."""
        return self.tiles_for(reader, page, self.tiling_of(reader, page))

    @chained
    def tiling_of(self, reader, page):
        """How a page not divided into viewports is cut, by name (cut_named): the platform's is the grid."""
        return "grid"

    def tiles_for(self, reader, page, how):
        """[(tag, Rect, note)]: a page's tiles cut as `how` names. Bands no graphic that counts touches are skipped
        (where text tasks read the page: reader.text_read; else blank ones); the other cuts' tiles are each grown.
        Cuts joined, "xycut+grid" (tile_choice's ties): each one's tiles, numbered on."""
        if "+" in how:
            regions = [x for part in how.split("+") for x in self.tiles_for(reader, page, part)]
            return [(f"tile:{i}", r, note) for i, (_, r, note) in enumerate(regions)]
        cut = self.cut_named(reader, page, how)
        if how == "bands":
            graphics = self.content_graphics(reader, page)
            if not reader.text_read:
                graphics = graphics + [box for box, _ in reader.lines(page)]
            kept = [b for b in cut if any(b.intersects(g) for g in graphics)]
            return [(f"tile:{i}", r, "") for i, r in enumerate(kept)]
        return [(f"tile:{i}", self.grow(reader, page, r, page.rect), "") for i, r in enumerate(cut)]

    def cut_named(self, reader, page, how):
        """[Rect]: the page cut, before any tile is grown or skipped. bands: full width, at whitespace gaps
        (segmentation.bands); grid: evenly, overlapping; snapped: the grid's cuts moved to whitespace, overlapping only
        where they cross something; xycut: blocks found by whitespace both ways, merged into tiles."""
        from .segmentation import BAND_AREA, STRIP_REACH, band_height, bands, snapped, tiles, xy_cut
        side, lines = self.tile_points, reader.lines(page)
        if how == "bands":
            return bands(page, band_height(page.rect.width, side), lines=lines, graphics=reader.graphics(page))
        if how == "grid":
            return list(tiles(page.rect, side))
        graphics = self.content_graphics(reader, page)
        if how == "snapped":
            return snapped(page.rect, side, lines, graphics)
        # longer blocks where they're rendered by their area, as detailed as today's widest band
        reach = STRIP_REACH if getattr(self, "render_area", False) else BAND_AREA
        return xy_cut(page.rect, side, lines, graphics, most=reach)

    @chained
    def content_graphics(self, reader, page):
        """[Rect]: the page's graphics that make a tile worth sending (Context.graphics: drawings and images)."""
        return reader.graphics(page)

    @chained
    def render_side(self, rect):
        """Pixels a region's longer side is rendered at."""
        return self.image_side

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
    def sent_tiles(self, reader, page, regions):
        """The tiles sent, from those kept: once a page, after the keep rules (kept_tiles also counts each candidate
        cut's images: tilechoice.candidates)."""
        return regions

    @chained
    def refined_tile(self, reader, page, tag, rect, done):
        """[(tag, Rect, {"continued": claims, "noted": issues, "depth": d} or {})] read next for a tile whose answer
        was partial or failed (done: the answer's coverage row, claims and cut edges, tasks.TaskCore.consume; depth:
        the asker's plus one unless given): the platform's, its halves, "<tag>-r0" and "-r1" (segmentation.halves,
        each holding least_half of what the tile holds), cut around the parts tile_parts gives where they can be."""
        from .segmentation import halves
        found = halves(page, rect, reader.lines(page), reader.graphics(page), self.least_half,
                       parts=self.tile_parts(reader, page))
        return [(f"{tag}-r{i}", r, {}) for i, r in enumerate(found)]

    @chained
    def tile_parts(self, reader, page):
        """Boxes a tile's halves are cut around where they can be, as around a graphic (segmentation.halves): none."""
        return []

    @chained
    def figure_regions(self, reader, page, number, grid):
        """[(tag, Rect, note)] read besides the tiles (grid: the tiles kept, or the page)."""
        return []

    def configuration(self):
        """The configuration as data: its levers in order and every setting the platform holds (endpoint
        settings aren't part of it). What store binding records, and what digest() hashes."""
        return {"levers": list(type(self).levers),
                **{name: value for name, value in self.model_dump(mode="json").items()
                   if name in platform_fields(type(self))}}

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
