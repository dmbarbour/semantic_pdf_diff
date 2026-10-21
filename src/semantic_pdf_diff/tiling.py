"""A tiling's measures, without the model (docs/research/tilings-2026-10-12.md, milestone 1).

A tiling is a page's image tasks: its tiles, and the figures read whole beside them (visual_regions; the overview is
counted, not measured). Each tile is measured against the page's text lines, words and graphics, as displayed:

- **lines cut sideways:** a line the tile holds in height but not in length (the trials review's measure: 6,400 on
  the samples' grid pages); **lines cut across:** a line a tile's top or bottom edge runs through
- **words cut:** a word the tile touches but doesn't hold
- **graphics share:** the part of the tile graphics other than decoration cover (on a 2-point raster, rounded
  outward: a hairline rule counts as 2 points wide)
- **text only:** text and no graphic other than decoration (a text task already reads it); **decoration only:**
  graphics, all of them decoration (the caller's), and no text; **blank:** neither

and the page as a whole:

- **lines read twice:** lines held whole by more than one tile
- **overlap:** the tiles' summed area over the area they cover (1.0: no overlap)
- **figures not whole:** detected figures that no tile or figure task holds whole: what's drawn or written in the
  figure's box, not its white margin (2026-10-12: a tile 2 points short of a chart's box was counted as splitting it)
- **graphics missed:** the share of the page's graphics no tile or figure task covers
- **images:** image tasks sent, the overview included

What counts as a graphic is the caller's (segmentation._graphics, or a lever's choice); the measures don't decide it.
"""
import math

import pymupdf

from .pages import shown

SLACK = 1.0  # points a box may stand past a tile's edge and still be held
RASTER = 2.0  # points per cell when a tile's areas are measured
PAGE_RASTER = 4.0  # and a page's

# Boxes are compared as (x0, y0, x1, y1) tuples: PyMuPDF's Rect methods cost most of a page's measuring.

def _box(r):
    return (r[0], r[1], r[2], r[3])

def _meets(a, b):
    """Whether two boxes share an area (PyMuPDF's Rect.intersects: an empty box meets nothing)."""
    return (a[0] < a[2] and a[1] < a[3] and b[0] < b[2] and b[1] < b[3]
            and a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3])

def _held(box, rect):
    return (box[0] >= rect[0] - SLACK and box[1] >= rect[1] - SLACK
            and box[2] <= rect[2] + SLACK and box[3] <= rect[3] + SLACK)

def _cut_sideways(box, rect):
    return (_meets(box, rect) and (box[0] < rect[0] - SLACK or box[2] > rect[2] + SLACK)
            and box[1] >= rect[1] - SLACK and box[3] <= rect[3] + SLACK)

def _cut_across(box, rect):
    return _meets(box, rect) and (box[1] < rect[1] - SLACK or box[3] > rect[3] + SLACK)

def _inked(box, lines, graphics):
    """A detected figure's box trimmed to the text and graphics inside it (a box with none is kept whole)."""
    inside = [b for b in (*lines, *graphics) if _meets(b, box)]
    if not inside:
        return box
    return (max(box[0], min(b[0] for b in inside)), max(box[1], min(b[1] for b in inside)),
            min(box[2], max(b[2] for b in inside)), min(box[3], max(b[3] for b in inside)))

def cut_by(rect, boxes):
    """(the edges of rect running through a box, [the boxes it cuts]): boxes it meets without holding."""
    rect, edges, cut = _box(rect), set(), []
    for b in map(_box, boxes):
        if not _meets(b, rect) or _held(b, rect):
            continue
        cut.append(b)
        edges |= {e for e, out in (("top", b[1] < rect[1] - SLACK), ("bottom", b[3] > rect[3] + SLACK),
                                   ("left", b[0] < rect[0] - SLACK), ("right", b[2] > rect[2] + SLACK)) if out}
    return [e for e in ("top", "bottom", "left", "right") if e in edges], cut

def words(page):
    """A page's words as displayed: [Rect]."""
    return [shown(page, w[:4]) for w in page.get_text("words")]

class _Raster:
    """Cells of `step` points over a rect, marked by the boxes laid on it (rounded outward)."""

    def __init__(self, rect, step=RASTER):
        self.rect, self.step = _box(rect), step
        self.cols = max(1, math.ceil((self.rect[2] - self.rect[0]) / step))
        self.rows = max(1, math.ceil((self.rect[3] - self.rect[1]) / step))
        self.cells = [bytearray(self.cols) for _ in range(self.rows)]

    def add(self, box):
        (ox, oy, ex, ey), step = self.rect, self.step
        x0, y0, x1, y1 = max(box[0], ox), max(box[1], oy), min(box[2], ex), min(box[3], ey)
        if x1 < x0 or y1 < y0:
            return
        c0 = min(self.cols - 1, math.floor((x0 - ox) / step))
        r0 = min(self.rows - 1, math.floor((y0 - oy) / step))
        c1 = max(c0 + 1, math.ceil((x1 - ox) / step))  # a hairline still marks a cell
        r1 = max(r0 + 1, math.ceil((y1 - oy) / step))
        for row in self.cells[r0:r1]:
            row[c0:c1] = b"\x01" * (c1 - c0)

    def count(self):
        """Cells marked."""
        return sum(self.cols - row.count(0) for row in self.cells)

    def share(self):
        return self.count() / (self.rows * self.cols)

    def outside(self, other):
        """Cells marked here and not in other (a raster of the same rect and step)."""
        return sum(sum(1 for a, b in zip(mine, theirs) if a and not b) if any(mine) else 0
                   for mine, theirs in zip(self.cells, other.cells))

def measure_tile(rect, lines, word_boxes, graphics, decoration=()):
    """One tile's measures (see the module's note). lines: [(Rect, text)]; word_boxes, graphics, decoration: [Rect]
    (decoration: those of graphics that are decoration)."""
    rect = _box(rect)
    boxes = [_box(b) for b, _ in lines]
    decoration = {_box(d) for d in decoration}
    touching = [g for g in map(_box, graphics) if _meets(g, rect)]
    content = [g for g in touching if g not in decoration]
    has_text = any(_meets(b, rect) for b in boxes)
    raster = _Raster(rect)
    for g in content:
        raster.add(g)
    return {
        "lines_cut_sideways": sum(1 for b in boxes if _cut_sideways(b, rect)),
        "lines_cut_across": sum(1 for b in boxes if _cut_across(b, rect)),
        "words_cut": sum(1 for w in map(_box, word_boxes) if _meets(w, rect) and not _held(w, rect)),
        "graphics_share": round(raster.share(), 4) if content else 0.0,
        "text_only": has_text and not content,
        "decoration_only": not has_text and bool(touching) and not content,
        "blank": not has_text and not touching,
    }

def measure(page, regions, lines, graphics, word_boxes=None, figures=(), decoration=()):
    """A page's tiling measured: {"tiles": [per tile, with its tag], "page": the page's measures}.

    regions: visual_regions' [(tag, Rect, note)]; lines: [(Rect, text)] as displayed; graphics: [Rect];
    word_boxes: [Rect] (words(page) if None); figures: the detected figures' boxes as displayed, [Rect]."""
    word_boxes = [_box(w) for w in (words(page) if word_boxes is None else word_boxes)]
    lines = [(_box(b), t) for b, t in lines]
    graphics = [_box(g) for g in graphics]
    decoration = {_box(d) for d in decoration}
    tiles = [(tag, _box(r)) for tag, r, _ in regions if tag.startswith("tile")]
    wholes = [_box(r) for tag, r, _ in regions if tag.startswith(("tile", "figure"))]
    per_tile = [{"tag": tag, **measure_tile(r, lines, word_boxes, graphics, decoration)} for tag, r in tiles]
    boxes = [b for b, _ in lines]
    holders = [sum(1 for _, r in tiles if _held(b, r)) for b in boxes]
    covered, drawn, seen = (_Raster(page.rect, PAGE_RASTER) for _ in range(3))
    for _, r in tiles:
        covered.add(r)
    area = sum(abs(pymupdf.Rect(r) & page.rect) for _, r in tiles)
    union = covered.count() * PAGE_RASTER * PAGE_RASTER
    content = [g for g in graphics if g not in decoration]
    for g in content:
        drawn.add(g)
    for r in wholes:
        seen.add(r)
    drawn_cells = drawn.count()
    missed = drawn.outside(seen)
    page_measures = {
        "tiles": len(tiles),
        "images": len(regions),
        "lines": len(boxes),
        "lines_cut_sideways": sum(t["lines_cut_sideways"] for t in per_tile),
        "lines_cut_across": sum(t["lines_cut_across"] for t in per_tile),
        "words_cut": sum(t["words_cut"] for t in per_tile),
        "text_only": sum(t["text_only"] for t in per_tile),
        "decoration_only": sum(t["decoration_only"] for t in per_tile),
        "blank": sum(t["blank"] for t in per_tile),
        "lines_read_twice": sum(1 for n in holders if n > 1),
        "overlap": round(area / union, 4) if union else None,
        "figures_not_whole": sum(1 for f in map(_box, figures)
                                 if not any(_held(_inked(f, boxes, content), r) for r in wholes)),
        "graphics_missed": round(missed / drawn_cells, 4) if drawn_cells else None,
    }
    return {"tiles": per_tile, "page": page_measures}

BUDGET_PIXELS = 645_000  # what gemma-4 sees of an image at its default budget, whatever its shape (research:
# gemma4-images-2026-09-30): a larger render is shrunk to this area, a smaller one enlarged without new detail

def detail(rect, side):
    """Pixels per point the model sees of a region rendered with its longer side at `side` (visuals.render)."""
    if rect.is_empty:
        return None
    scale = min(2.5, side / max(rect.width, rect.height))
    return round(min(scale, math.sqrt(BUDGET_PIXELS / (rect.width * rect.height))), 3)
