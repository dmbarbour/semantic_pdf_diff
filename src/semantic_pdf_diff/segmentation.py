"""Page segmentation for image tasks: tiles (a grid or whitespace bands), crops grown to whole lines, a drawing
sheet's details, and blank tiles found. The geometry only: which of it a run uses is the segmentation levers'
choice (levers.py: Tiling, GrowTiles, SheetDetails, SkipEmpty, FigureTasks). Rectangles are as displayed.
"""
import bisect
import math
import re

import pymupdf

from .pages import lines as _lines, shown, shown_point

def tiles(rect, side, overlap=0.18):
    """Evenly spaced tiles covering rect; neighbours overlap by at least `overlap`."""
    def starts(lo, hi):
        span = hi - lo
        if span <= side:
            return [lo]
        n = math.ceil((span - side) / (side * (1 - overlap))) + 1
        step = (span - side) / (n - 1)
        return [lo + k * step for k in range(n)]
    for y in starts(rect.y0, rect.y1):
        for x in starts(rect.x0, rect.x1):
            yield pymupdf.Rect(x, y, min(x + side, rect.x1), min(y + side, rect.y1))

FIGURE_PAD = 8.0  # points around a figure's region

def _graphics(page, drawings=None):
    """Drawings (smaller than half the page: not frames) and images, as displayed. drawings: the page's, if already
    fetched (Context.drawings)."""
    boxes = []
    for d in page.get_cdrawings() if drawings is None else drawings:
        r = shown(page, d["rect"])
        if r.height < 0.5 * page.rect.height:
            boxes.append(r)
    for image in page.get_image_info():
        boxes.append(shown(page, image["bbox"]))
    return boxes

def bands(page, height, gap_from=0.5, pad=4.0, overlap=0.15, lines=None, graphics=None):
    """Full-width bands down a page, each cut at the widest empty horizontal gap in the lower
    part of its window, so lines, charts and legends aren't split (research round 1: on the
    report slices this cut 7 lines where a grid cut 2,126). Falls back to an overlapping cut. lines, graphics: the
    page's, if already read (Context.lines, Context.graphics)."""
    lines = _lines(page) if lines is None else lines
    graphics = _graphics(page) if graphics is None else graphics
    boxes = [b for b in [r for r, _ in lines] + graphics if not b.is_empty or b.height > 0]
    if not boxes:
        return []
    content = pymupdf.Rect(boxes[0])
    for b in boxes:
        content |= b
    content = (content + (-pad, -pad, pad, pad)) & page.rect
    spans, gaps = sorted((b.y0, b.y1) for b in boxes), []
    reach = spans[0][1]
    for y0, y1 in spans[1:]:
        if y0 > reach + 1:
            gaps.append((reach, y0))
        reach = max(reach, y1)
    out, top = [], content.y0
    while content.y1 - top > height:
        fits = [g for g in gaps if top + gap_from * height <= (g[0] + g[1]) / 2 <= top + height]
        if fits:
            gap = max(fits, key=lambda g: (g[1] - g[0], g[0]))
            cut = following = (gap[0] + gap[1]) / 2
        else:
            cut, following = top + height, top + height * (1 - overlap)
        out.append(pymupdf.Rect(content.x0, top, content.x1, cut))
        top = following
    out.append(pymupdf.Rect(content.x0, top, content.x1, content.y1))
    return out

def grown(page, rect, limit=0.25, lines=None):
    """A crop grown to include every text line it cuts, by at most `limit` of its size per side."""
    lines = _lines(page) if lines is None else lines
    most = rect + (-limit * rect.width, -limit * rect.height, limit * rect.width, limit * rect.height)
    out = pymupdf.Rect(rect)
    for _ in range(3):
        changed = False
        for box, _ in lines:
            if out.intersects(box) and box not in out and box in most:
                out |= box
                changed = True
        if not changed:
            break
    return out & page.rect

# a refined half's least share of its tile (the owner, 2026-10-09: "a tuning lever ... start with 25%")
LEAST_HALF = 0.25
REFINE_OVERLAP = 12.0  # points a cut's halves share, within its gap where it has one

def _gaps(boxes, axis, lo, hi):
    """The ranges of [lo, hi] along an axis (0: x, 1: y) that no box covers."""
    reach, out = lo, []
    for a, z in sorted((b.x0, b.x1) if axis == 0 else (b.y0, b.y1) for b in boxes):
        if a > reach:
            out.append((reach, min(a, hi)))
        reach = max(reach, z)
        if reach >= hi:
            break
    if reach < hi:
        out.append((reach, hi))
    return [g for g in out if g[1] >= g[0]]

def halves(page, rect, lines=None, graphics=None, least=LEAST_HALF, overlap=REFINE_OVERLAP, parts=()):
    """A partial tile's two halves for refinement (review-bugs-2026-10-09, item 6), each grown to whole lines.

    The cut crosses no text line where it can: in a gap between lines or between columns (no graphic or part crossed
    either, if possible: parts, boxes such as a figure's), nearest the middle of what the tile holds, each side holding
    at least `least` of its extent, ties
    going to the cut across the tile's shorter side (a band is cut between its lines, not down them). Otherwise the
    cut crossing the fewest lines. Measured on what the tile holds, not on the tile, so neither half is left blank.
    A tile without text, such as a drawing or a scan, is cut at the middle of its longer side, as before."""
    lines = _lines(page) if lines is None else lines
    texts = [box & rect for box, _ in lines if box.intersects(rect)]
    if not texts:
        return _middle(rect, overlap)
    marks = texts + [g & rect for g in [*(_graphics(page) if graphics is None else graphics),
                                        *(x for x in parts if not x.contains(rect))]  # a part the tile is in: no help
                     if g.intersects(rect)]
    shorter = 1 if rect.height < rect.width else 0  # the axis whose cut divides the shorter side
    best = None

    def extent(boxes, axis):
        return min(b.x0 if axis == 0 else b.y0 for b in boxes), max(b.x1 if axis == 0 else b.y1 for b in boxes)

    def rank(crossed, cut, lo, hi, axis):
        return (crossed, round(abs(cut - (lo + hi) / 2) / (hi - lo) / 0.05), axis != shorter)
    for axis in (0, 1):
        for tier, blockers in enumerate((marks, texts)):
            lo, hi = extent(blockers, axis)
            first, last = lo + least * (hi - lo), hi - least * (hi - lo)
            for g0, g1 in _gaps(blockers, axis, lo, hi):
                if max(g0, first) <= min(g1, last) and g1 > g0:
                    cut = min(max((lo + hi) / 2, g0, first), g1, last)
                    found = ((tier, *rank(0, cut, lo, hi, axis)), axis, cut, (g0, g1))
                    best = min(best, found) if best else found
    if best is None:  # no gap: the cut crossing the fewest lines
        for axis in (0, 1):
            lo, hi = extent(texts, axis)
            first, last = lo + least * (hi - lo), hi - least * (hi - lo)
            spans = [(a + 1, z - 1) for a, z in ((b.x0, b.x1) if axis == 0 else (b.y0, b.y1) for b in texts)
                     if z - a > 2]
            starts, ends = sorted(a for a, _ in spans), sorted(z for _, z in spans)
            for cut in {(lo + hi) / 2} | {v for span in spans for v in span if first <= v <= last}:
                crossed = bisect.bisect_left(starts, cut) - bisect.bisect_right(ends, cut)  # spans strictly around it
                found = ((2, *rank(crossed, cut, lo, hi, axis)), axis, cut, (cut, cut))
                best = min(best, found) if best else found
    _, axis, cut, (g0, g1) = best
    end, start = (min(cut + overlap, g1), max(cut - overlap, g0)) if g1 > g0 else (cut + overlap, cut - overlap)
    if axis == 0:
        parts = [pymupdf.Rect(rect.x0, rect.y0, end, rect.y1), pymupdf.Rect(start, rect.y0, rect.x1, rect.y1)]
    else:
        parts = [pymupdf.Rect(rect.x0, rect.y0, rect.x1, end), pymupdf.Rect(rect.x0, start, rect.x1, rect.y1)]
    return [grown(page, part & rect, lines=lines) for part in parts]

MOSTLY = 0.5  # a figure covering this share of what a tile holds makes the tile mostly that figure

def inked_figures(settings, reader, page):
    """A page's detected figures as displayed, each trimmed to the lines and content graphics in it (tiling._inked)."""
    from .tiling import _inked
    lines = [tuple(b) for b, _ in reader.lines(page)]
    content = [tuple(g) for g in settings.content_graphics(reader, page)]
    return [pymupdf.Rect(_inked(tuple(shown(page, f.bbox)), lines, content))
            for f in reader.figures(page, page.number) if f.region]

def mostly_figure(settings, reader, page, rect):
    """Whether a tile holds a detected figure whole covering MOSTLY of the extent of what it holds (its lines and
    content graphics, within it)."""
    from .tiling import _held
    held = [f for f in inked_figures(settings, reader, page) if _held(tuple(f), tuple(rect))]
    if not held:
        return False
    inside = [b & rect for b in [*(b for b, _ in reader.lines(page)), *settings.content_graphics(reader, page)]
              if b.intersects(rect)]
    extent = pymupdf.Rect(rect.x1, rect.y1, rect.x0, rect.y0)
    for b in inside:
        extent |= b
    return any(abs(f) >= MOSTLY * abs(extent) for f in held) if not extent.is_empty else False

def _middle(rect, overlap):
    """Today's cut: the middle of the longer side."""
    if rect.width > rect.height:
        mid = (rect.x0 + rect.x1) / 2
        return [pymupdf.Rect(rect.x0, rect.y0, mid + overlap, rect.y1),
                pymupdf.Rect(mid - overlap, rect.y0, rect.x1, rect.y1)]
    mid = (rect.y0 + rect.y1) / 2
    return [pymupdf.Rect(rect.x0, rect.y0, rect.x1, mid + overlap),
            pymupdf.Rect(rect.x0, mid - overlap, rect.x1, rect.y1)]

# --- candidate tilings (tile-selection-2026-10-10, milestone 3): each a lever, off by default (levers.py)

RULE_POINTS = 8.0  # a graphic no thicker than this, and at least RULE_REACH of the page's width or height long, is a
RULE_REACH = 1 / 3  # rule, a bar down a margin or a frame's side
NEIGHBOURS = 3     # pages either side where a graphic is looked for in the same place
REPEATED = 2       # neighbours holding it (or all, if fewer) make it furniture: a header, footer, logo, template banner
PLACE = 1.0        # points: the same place
BACKDROP = 0.6     # an image covering this share of the page, under most of its visible text, is a backdrop
UNDERLINE_POINTS, UNDERLINE_GAP = 2.0, 4.0  # a line this thin, this close under a text line and no wider, underlines it
MASK_POINTS = 3.0  # a graphic no larger than the text lines it holds, by this much a side, is the text's background

def _place(box):
    return tuple(round(v / PLACE) for v in box)

def visible_share(page):
    """The share of a page's text layer drawn visibly: an OCR'd scan's text is invisible (render mode 3), a page's
    own text isn't. None if the page has no text."""
    seen = total = 0
    for span in page.get_texttrace():
        n = len(span["chars"])
        total += n
        seen += n if span["type"] != 3 and span.get("opacity", 1) > 0 else 0
    return seen / total if total else None

def marks(page, drawings=None):
    """{place: {signature}}: what a page draws where, to find what repeats on its neighbours (decoration): an image
    by its digest, a drawing by its paths' kinds, colours and stroke. Not the place alone: a report's appendix may
    put a different picture in the same place on every page."""
    out = {}
    for d in page.get_cdrawings() if drawings is None else drawings:
        signature = ("drawing", "".join(item[0] for item in d.get("items") or ()), str(d.get("fill")),
                     str(d.get("color")), round(d.get("width") or 0, 1))
        out.setdefault(_place(shown(page, d["rect"])), set()).add(signature)
    for image in page.get_image_info(hashes=True):
        out.setdefault(_place(shown(page, image["bbox"])), set()).add(("image", image["digest"]))
    return out

def decoration(page, graphics, lines, nearby=(), own=None):
    """Which of a page's graphics (Context.graphics) are decoration, [bool]: what a tile can hold and still be text
    only, as displayed.

    - **rules:** no thicker than RULE_POINTS and at least RULE_REACH of the page long (rules, margin bars, a frame
      drawn as lines; a frame drawn as one path isn't a graphic at all)
    - **furniture:** drawn alike in the same place on REPEATED of the pages around it, or on all of them if there
      are fewer (nearby: marks(page) of those the same size; own: this page's, found if None)
    - **underlines:** no thicker than UNDERLINE_POINTS, within a text line's width and at most UNDERLINE_GAP below it
    - **text masks:** no larger than the text lines it holds, by MASK_POINTS a side (a box behind a drawing's notes)
    - **text panels:** a filled drawing holding text lines and no other graphic but decoration and hairlines (a
      poster's section box, a callout, a heading's bar), found smallest first so a panel may hold panels. Filled: a
      chart's line holds its labels in its box too
    - **a backdrop:** an image over BACKDROP of the page with most of the page's text lines on it, the text drawn
      visibly. A scan has no text layer, or an invisible one, so it stays a graphic."""
    area = abs(page.rect)
    own = marks(page) if own is None else own
    repeated = min(REPEATED, len(nearby)) or None
    images = {_place(shown(page, i["bbox"])) for i in page.get_image_info()}
    visible = None
    texts = sorted((box for box, _ in lines if not box.is_empty), key=lambda b: b.y1)
    bottoms = [b.y1 for b in texts]
    middles = sorted(((b.y0 + b.y1) / 2, (b.x0 + b.x1) / 2, i) for i, b in enumerate(texts))
    heights = [m[0] for m in middles]
    out, holding = [], []
    for g in graphics:
        holding.append(False)
        thin, long = min(g.width, g.height), max(g.width / page.rect.width, g.height / page.rect.height)
        if thin <= RULE_POINTS and long >= RULE_REACH:
            out.append(True)
            continue
        above = texts[bisect.bisect_left(bottoms, g.y0 - UNDERLINE_GAP):bisect.bisect_right(bottoms, g.y1 + 1)]
        if g.height <= UNDERLINE_POINTS and any(b.x0 - 2 <= g.x0 and g.x1 <= b.x1 + 2 and b.y0 < g.y0 for b in above):
            out.append(True)
            continue
        held = [texts[i] for _, x, i in middles[bisect.bisect_left(heights, g.y0):bisect.bisect_right(heights, g.y1)]
                if g.x0 <= x <= g.x1]
        if held:
            holding[-1] = True
            around = pymupdf.Rect(held[0])
            for b in held[1:]:
                around |= b
            if g in around + (-MASK_POINTS, -MASK_POINTS, MASK_POINTS, MASK_POINTS):
                out.append(True)
                continue
        key = _place(g)
        if repeated and sum(bool(own.get(key, set()) & other.get(key, set())) for other in nearby) >= repeated:
            out.append(True)
            continue
        backdrop = False
        if key in images and abs(g & page.rect) >= BACKDROP * area and lines:
            on = sum(1 for box, _ in lines if (box.tl + box.br) / 2 in g)
            if on >= 0.5 * len(lines):
                visible = visible_share(page) if visible is None else visible
                backdrop = bool(visible) and visible >= 0.5
        out.append(backdrop)
    filled = {place for place, found in own.items() if any(m[0] == "drawing" and m[2] != "None" for m in found)}
    return _panels(graphics, out, holding, filled)

def _panels(graphics, out, holding, filled):
    """decoration's text panels, smallest first: [bool] with them set. filled: the places of filled drawings."""
    order = sorted(range(len(graphics)), key=lambda i: graphics[i].x0)
    starts = [graphics[i].x0 for i in order]
    for i in sorted((i for i, g in enumerate(graphics) if holding[i] and not out[i] and _place(g) in filled),
                    key=lambda i: abs(graphics[i])):
        g = graphics[i]
        inside = (graphics[j] for j in order[bisect.bisect_left(starts, g.x0):bisect.bisect_right(starts, g.x1)]
                  if j != i and not out[j])
        if not any(h in g and min(h.width, h.height) > UNDERLINE_POINTS for h in inside):
            out[i] = True
    return out

BAND_AREA = 1.6  # a band's largest area in square tiles: today's widest band, 1.6 tiles by one
STRIP_REACH = 2.4  # a block's longest side in tiles where it's rendered by its area (render_area)

def band_height(width, side):
    """How tall a page's bands may be: a tile's side, or less on a page wider than BAND_AREA tiles, so a band's area
    stays at most BAND_AREA tiles (bands on wide pages, a candidate)."""
    return min(side, BAND_AREA * side * side / width)

def _crossings(boxes, axis):
    """f(v): how many boxes a cut at v along an axis (0: x, 1: y) runs through."""
    starts = sorted(b.x0 if axis == 0 else b.y0 for b in boxes)
    ends = sorted(b.x1 if axis == 0 else b.y1 for b in boxes)
    return lambda v: bisect.bisect_left(starts, v) - bisect.bisect_right(ends, v)

def _snapped_cuts(lo, hi, side, texts, graphics, axis, overlap, reach):
    """[(start, end)] along an axis: the grid's pieces (tiles' count), each cut moved within reach x side of the grid's
    place to where it crosses the fewest text lines, then graphics, then nearest the grid's place. A cut crossing
    nothing gets no overlap; one crossing something keeps the grid's, shared either side of it."""
    span = hi - lo
    if span <= side:
        return [(lo, hi)]
    n = math.ceil((span - side) / (side * (1 - overlap))) + 1
    lines_crossed, graphics_crossed = _crossings(texts, axis), _crossings(graphics, axis)
    edges = sorted({v for b in texts + graphics for v in ((b.x0, b.x1) if axis == 0 else (b.y0, b.y1))})
    cuts = []
    for k in range(1, n):
        nominal = lo + k * span / n
        window = (nominal - reach * side, nominal + reach * side)
        candidates = [nominal] + [v + d for v in edges[bisect.bisect_left(edges, window[0] - 1):
                                                       bisect.bisect_right(edges, window[1] + 1)]
                                  for d in (-0.5, 0.5) if window[0] <= v + d <= window[1]]
        best = min(candidates, key=lambda v: (lines_crossed(v), graphics_crossed(v), abs(v - nominal)))
        cuts.append((best, lines_crossed(best) + graphics_crossed(best) > 0))
    half = overlap * side / 2
    out, start = [], lo
    for cut, crossing in cuts:
        out.append((start, min(hi, cut + half) if crossing else cut))
        start = max(lo, cut - half) if crossing else cut
    out.append((start, hi))
    return out

def snapped(rect, side, lines, graphics, overlap=0.18, reach=0.12):
    """A grid whose cuts move to whitespace (less overlap on grids, a candidate): rows cut across the whole page, then
    each row's tiles cut within it, as _snapped_cuts. lines: [(Rect, text)]; graphics: those that count."""
    texts = [b for b, _ in lines if not b.is_empty]
    graphics = [g for g in graphics if not g.is_empty]
    out = []
    for y0, y1 in _snapped_cuts(rect.y0, rect.y1, side, texts, graphics, 1, overlap, reach):
        row = pymupdf.Rect(rect.x0, y0, rect.x1, y1)
        in_row = [b for b in texts if b.intersects(row)], [g for g in graphics if g.intersects(row)]
        for x0, x1 in _snapped_cuts(rect.x0, rect.x1, side, *in_row, 0, overlap, reach):
            out.append(pymupdf.Rect(x0, y0, x1, y1))
    return out

XY_PAD = 4.0  # points around a block's content

def xy_cut(rect, side, lines, graphics, most=BAND_AREA, pad=XY_PAD):
    """Blocks found by whitespace both ways (XY-cut, a candidate), merged into tiles: a block is cut at its widest gap,
    down to blocks that fit (longer side at most `most` x side, area at most BAND_AREA tiles: no more than today's
    widest band; `most` is longer where a region is rendered by its area, render_area), then neighbouring blocks
    merged while their union fits and covers no other block. A block with no gap is cut as the grid cuts it. Tiles
    hug their content (pad), so blank margins aren't sent."""
    boxes = [b for b, _ in lines if not b.is_empty] + [g for g in graphics if not g.is_empty]
    boxes = [b & rect for b in boxes if b.intersects(rect)]
    if not boxes:
        return []

    def fits(r):
        return max(r.width, r.height) <= most * side + 0.01 and r.width * r.height <= BAND_AREA * side * side + 1

    def cut(boxes, bound):  # bound: up to the middle of the gaps around these boxes
        extent = pymupdf.Rect(boxes[0])
        for b in boxes[1:]:
            extent |= b
        extent = (extent + (-pad, -pad, pad, pad)) & bound
        if fits(extent):
            return [extent]
        best = None
        for axis in (0, 1):
            lo, hi = (extent.x0 + pad, extent.x1 - pad) if axis == 0 else (extent.y0 + pad, extent.y1 - pad)
            for g0, g1 in _gaps(boxes, axis, lo, hi):
                if g0 > lo and g1 < hi and g1 > g0:
                    middle = (g0 + g1) / 2
                    found = (-(g1 - g0), abs(middle - (lo + hi) / 2), axis, middle)
                    best = min(best, found) if best else found
        if best is None:
            return list(tiles(extent, side))
        _, _, axis, at = best
        before = [b for b in boxes if (b.x1 if axis == 0 else b.y1) <= at]
        after = [b for b in boxes if (b.x1 if axis == 0 else b.y1) > at]
        first, second = pymupdf.Rect(bound), pymupdf.Rect(bound)
        if axis == 0:
            first.x1 = second.x0 = at
        else:
            first.y1 = second.y0 = at
        pieces = cut(before, first) + cut(after, second)
        out = [pieces[0]]
        for i, piece in enumerate(pieces[1:], 1):
            union = out[-1] | piece
            others = out[:-1] + pieces[i + 1:]
            if fits(union) and all(abs(union & o) <= 0.05 * abs(o) for o in others):
                out[-1] = union
            else:
                out.append(piece)
        return out
    return cut(boxes, rect)

DETAIL_NUMBER = re.compile(r"^[A-H]\d{1,2}$")  # grid-referenced detail numbers (US National CAD Standard)
BORDER = 0.6  # a vertical line this share of the page height is a frame or title-block border

def _borders(page):
    """Long vertical lines as displayed: [(x, y0, y1)], merged when closer than 30 points."""
    found = []
    for d in page.get_cdrawings():
        for item in d.get("items") or ():
            if item[0] == "l":
                a, b = (shown_point(page, p) for p in item[1:3])
                if abs(a.x - b.x) < 1:
                    found.append((a.x, min(a.y, b.y), max(a.y, b.y)))
            elif item[0] == "re":
                r = shown(page, item[1])
                found += [(r.x0, r.y0, r.y1), (r.x1, r.y0, r.y1)]
    out = []
    for x, y0, y1 in sorted(v for v in found if v[2] - v[1] >= BORDER * page.rect.height):
        if out and x - out[-1][0] < 30:
            out[-1] = (out[-1][0], min(out[-1][1], y0), max(out[-1][2], y1))
        else:
            out.append((x, y0, y1))
    return out

def _widest_gap(boxes, lo, hi, band):
    """Middle of the widest x range in [lo, hi] that no box crossing the band covers, or None."""
    reach, gaps = lo, []
    for a, z in sorted((b.x0, b.x1) for b in boxes if b.intersects(band)):
        if z <= lo:
            continue
        if a > reach:
            gaps.append((reach, min(a, hi)))
        reach = max(reach, z)
        if reach >= hi:
            break
    if reach < hi:
        gaps.append((reach, hi))
    gaps = [g for g in gaps if g[1] > g[0]]
    return (lambda g: (g[0] + g[1]) / 2)(max(gaps, key=lambda g: g[1] - g[0])) if gaps else None

def sheet_details(page, lines=None):
    """A drawing sheet's details as displayed: [(number, title, Rect)], and its side columns
    (title block, notes) as ("", "", Rect); [] if the page has no detail numbers.

    Detail titles are large grid references such as "B4" at a detail's bottom left. A detail
    runs up to the next title above it and across to the widest gap before the next detail to
    its right (research round 1: this isolated all five details on dc S-522)."""
    lines = _lines(page) if lines is None else lines
    spans = [(s["size"], s["text"].strip(), shown(page, s["bbox"]))
             for b in page.get_text("dict")["blocks"] for l in b.get("lines", ()) for s in l["spans"]
             if s["text"].strip()]
    if not spans:
        return []
    median = sorted(size for size, _, _ in spans)[len(spans) // 2]
    numbers = [(t, r, size) for size, t, r in spans if DETAIL_NUMBER.match(t) and size >= 2 * median]
    borders = [b for b in _borders(page) if b[0] > 0.5 * page.rect.width and b[0] > max(r.x1 for _, r, _ in numbers)] \
        if numbers else []
    if not numbers or not borders:
        return []
    left = [b for b in _borders(page) if b[0] < 0.2 * page.rect.width]
    x0 = left[-1][0] if left else page.rect.x0
    right, y0, y1 = borders[0]
    area = pymupdf.Rect(x0, y0, right, y1)
    size = max(s for _, _, s in numbers)
    column = 6 * size  # titles closer than this in x share a column
    boxes = [box for box, _ in lines] + [g for g in _graphics(page)
                                         if g.width < 0.5 * area.width and g.height < 0.5 * area.height]
    boxes = [b for b in boxes if b.intersects(area)]
    view = {}
    for name, t, _ in numbers:
        top = area.y0
        for _, u, _ in numbers:
            if abs(u.x0 - t.x0) < column and u.y1 < t.y1 - 1.6 * size:
                top = max(top, u.y1 + 1.2 * size)  # below the title above (and its scale line)
        view[name] = [t.x0 - 1.2 * size, top, area.x1, min(area.y1, t.y1 + 1.2 * size)]  # with the scale bar
    for name, t, _ in numbers:
        r = view[name]
        for other, u, _ in numbers:
            ru = view[other]
            if u.x0 > t.x0 + column and ru[1] < r[3] and ru[3] > r[1]:
                band = pymupdf.Rect(t.x0, max(r[1], ru[1]), u.x0, min(r[3], ru[3]))
                gap = _widest_gap(boxes, t.x0 + column, u.x0 + 0.4 * size, band)
                edge = gap if gap is not None else u.x0 - 0.8 * size
                r[2] = min(r[2], edge)
                ru[0] = min(ru[0], edge)
    for name, t, _ in numbers:
        r = view[name]
        lefts = [view[o][2] for o, u, _ in numbers if u.x0 < t.x0 - column and view[o][1] < r[3] and view[o][3] > r[1]]
        r[0] = max(lefts) if lefts else area.x0
    out = []
    for name, t, s in sorted(numbers, key=lambda n: (n[1].y0, n[1].x0)):
        # The title is set about as large as the number, beside it; the scale line is small, below it.
        near = pymupdf.Rect(t.x1 - 1, t.y0 - s, t.x1 + 25 * s, t.y1 + s)
        beside = sorted((r for size, text, r in spans if r.intersects(near) and r.x0 >= near.x0 and text != name
                         and (size >= 0.6 * s or SCALE.search(text))), key=lambda r: (round(r.y0), r.x0))
        title = " ".join(text for size, text, r in spans for b in beside if r == b)
        out.append((name, " ".join(dict.fromkeys(title.split()))[:200], pymupdf.Rect(view[name]) & page.rect))
    edges = [b[0] for b in _borders(page) if b[0] >= right] + [page.rect.x1]
    for a, z in zip(edges, edges[1:]):
        column = pymupdf.Rect(a, y0, z, y1) & page.rect
        if any(box.intersects(column) and box.x0 >= a - 1 for box, _ in lines):
            out.append(("", "", column))
    return out

SCALE = re.compile(r"\d[\"']?\s*=\s*\d|\bSCALE\b|\bN\.?T\.?S\b", re.IGNORECASE)
def _empty(page, rects, lines=None, graphics=None):
    """Which rects hold no text line, drawing or image (blank paper: the model reports "the image is
    blank" and returns nothing; 7% of grid tiles on the development drawing sheets, round 5d)."""
    lines = _lines(page) if lines is None else lines
    marks = [box for box, _ in lines] + (_graphics(page) if graphics is None else graphics)
    return [not any(r.intersects(m) for m in marks) for r in rects]
