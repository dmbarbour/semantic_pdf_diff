"""Page segmentation for image tasks: tiles (a grid or whitespace bands), crops grown to whole lines, a drawing
sheet's details, and blank tiles found. The geometry only: which of it a run uses is the segmentation levers'
choice (levers.py: Tiling, GrowTiles, SheetDetails, SkipEmpty, FigureTasks). Rectangles are as displayed.
"""
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

def _graphics(page):
    """Drawings (smaller than half the page: not frames) and images, as displayed."""
    boxes = []
    for d in page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings():
        r = shown(page, d["rect"])
        if r.height < 0.5 * page.rect.height:
            boxes.append(r)
    for image in page.get_image_info():
        boxes.append(shown(page, image["bbox"]))
    return boxes

def bands(page, height, gap_from=0.5, pad=4.0, overlap=0.15):
    """Full-width bands down a page, each cut at the widest empty horizontal gap in the lower
    part of its window, so lines, charts and legends aren't split (research round 1: on the
    report slices this cut 7 lines where a grid cut 2,126). Falls back to an overlapping cut."""
    boxes = [b for b in [r for r, _ in _lines(page)] + _graphics(page) if not b.is_empty or b.height > 0]
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

DETAIL_NUMBER = re.compile(r"^[A-H]\d{1,2}$")  # grid-referenced detail numbers (US National CAD Standard)
BORDER = 0.6  # a vertical line this share of the page height is a frame or title-block border

def _borders(page):
    """Long vertical lines as displayed: [(x, y0, y1)], merged when closer than 30 points."""
    found = []
    for d in page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings():
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
             for b in page.get_text("dict")["blocks"] for l in b.get("lines", ()) for s in l["spans"] if s["text"].strip()]
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
    boxes = [box for box, _ in lines] + [g for g in _graphics(page) if g.width < 0.5 * area.width and g.height < 0.5 * area.height]
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
def _empty(page, rects, lines=None):
    """Which rects hold no text line, drawing or image (blank paper: the model reports "the image is
    blank" and returns nothing; 7% of grid tiles on the development drawing sheets, round 5d)."""
    lines = _lines(page) if lines is None else lines
    marks = [box for box, _ in lines] + _graphics(page)
    return [not any(r.intersects(m) for m in marks) for r in rects]
