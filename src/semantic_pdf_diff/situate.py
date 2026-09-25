"""Situating: figures, what cites them, and what they (and sections) are about.

This module's first part is mechanical: it finds figures (drawing clusters, images and
captions), the prose that cites them by label, and the claims inside them. The model
requests that write "about" statements build on it.
"""
import re
from .models import Figure, Reference

KINDS = {"figure": "figure", "figures": "figure", "fig": "figure", "figs": "figure", "table": "table",
         "tables": "table", "sheet": "sheet", "sheets": "sheet", "drawing": "sheet", "drawings": "sheet",
         "dwg": "sheet", "exhibit": "exhibit", "exhibits": "exhibit"}
NUMBER = r"((?:[A-Z]{1,3}-?)?\d+(?:[.-]\d+)*[a-z]?)"
CAPTION = re.compile(r"^\s*(Figure|Fig\.?|Table|Sheet|Drawing|Dwg\.?|Exhibit)\s+" + NUMBER + r"\s*[:.\-–—]?", re.IGNORECASE)
MENTION = re.compile(r"\b(Figures?|Figs?\.?|Tables?|Sheets?|Drawings?|Dwg\.?|Exhibits?)\s+" + NUMBER, re.IGNORECASE)

CELL = 10.0          # grid resolution (points) for clustering vector drawings
BRIDGE = 2           # gaps of up to this many cells (about 20 points) don't split a cluster
MIN_PATHS = 10       # a drawing cluster needs this many paths...
MIN_AREA = 0.02      # ...and this share of the page area to count as a figure
MAX_PATH_AREA = 0.6  # paths covering more of the page (frames, backgrounds) are ignored
CAPTION_GAP = 72.0   # a caption pairs with a region at most this far above or below it
LIST_ENTRY = re.compile(r"\.{2,}\s*\d+\s*$")  # "Figure 3-1. Title ........ 12" in a list of figures
LIST_PAGE = 5        # this many unpaired caption lines on one page make it a list of figures or tables

def label_of(kind, number):
    return f"{KINDS[kind.lower().rstrip('.')]} {number.upper()}"

def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))

def _overlap(a, b):
    return _area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))

def drawing_regions(page):
    """Bounding boxes of clusters of vector paths, found on a coarse grid."""
    width, height = page.rect.width, page.rect.height
    page_area = width * height
    drawings = page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings()
    cells, counts = set(), {}
    for d in drawings:
        x0, y0, x1, y1 = d["rect"]
        if _area((x0, y0, x1, y1)) > MAX_PATH_AREA * page_area:
            continue
        cx0, cy0 = int(max(x0, 0) // CELL), int(max(y0, 0) // CELL)
        cx1, cy1 = int(min(x1, width) // CELL), int(min(y1, height) // CELL)
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                cells.add((cx, cy))
        centre = (int((x0 + x1) / 2 // CELL), int((y0 + y1) / 2 // CELL))
        counts[centre] = counts.get(centre, 0) + 1
    regions, seen = [], set()
    for start in cells:
        if start in seen:
            continue
        stack, component = [start], []
        seen.add(start)
        while stack:
            cx, cy = stack.pop()
            component.append((cx, cy))
            # Cells up to BRIDGE apart are connected: diagrams have gaps between boxes.
            for n in ((cx + dx, cy + dy) for dx in range(-BRIDGE, BRIDGE + 1) for dy in range(-BRIDGE, BRIDGE + 1)):
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        box = (min(c[0] for c in component) * CELL, min(c[1] for c in component) * CELL,
               (max(c[0] for c in component) + 1) * CELL, (max(c[1] for c in component) + 1) * CELL)
        paths = sum(counts.get(c, 0) for c in component)
        if paths >= MIN_PATHS and _area(box) >= MIN_AREA * page_area:
            regions.append(box)
    return sorted(regions, key=lambda b: (b[1], b[0]))

def image_regions(page):
    page_area = page.rect.width * page.rect.height
    return [tuple(b["bbox"]) for b in page.get_text("dict")["blocks"]
            if b.get("type") == 1 and _area(b["bbox"]) >= 0.01 * page_area]

def find_figures(doc):
    """Figures per page: regions (drawing clusters, images) paired with captions."""
    figures = []
    for number, page in enumerate(doc, 1):
        regions = drawing_regions(page) + image_regions(page)
        captions = []
        for block in page.get_text("blocks", sort=True):
            match = CAPTION.match(block[4]) if block[6] == 0 else None
            if match:
                captions.append((tuple(block[:4]), " ".join(block[4].split()), label_of(*match.groups()),
                                 KINDS[match.group(1).lower().rstrip(".")]))
        # Entries in a list of figures or tables look like captions but aren't figures.
        captions = [c for c in captions if not LIST_ENTRY.search(c[1])]
        pairs = []
        for ci, (cbox, *_ ) in enumerate(captions):
            for ri, rbox in enumerate(regions):
                horizontal = min(cbox[2], rbox[2]) - max(cbox[0], rbox[0]) > 0
                gap = max(rbox[1] - cbox[3], cbox[1] - rbox[3], 0)
                if horizontal and gap <= CAPTION_GAP:
                    pairs.append((gap, ci, ri))
        used_c, used_r, paired = set(), set(), {}
        for gap, ci, ri in sorted(pairs):
            if ci not in used_c and ri not in used_r:
                used_c.add(ci); used_r.add(ri)
                paired[ci] = ri
        if len(captions) - len(paired) >= LIST_PAGE:
            captions = [c for ci, c in enumerate(captions) if ci in paired]  # a list page: keep only real pairs
            paired = {i: paired[ci] for i, ci in enumerate(sorted(paired))}
        items = []
        for ci, (cbox, text, label, kind) in enumerate(captions):
            if ci in paired:
                items.append(dict(bbox=_union(cbox, regions[paired[ci]]), caption=text, label=label, kind=kind))
            else:
                items.append(dict(bbox=cbox, caption=text, label=label, kind=kind, region=False))
        items += [dict(bbox=r) for ri, r in enumerate(regions) if ri not in used_r]
        for i, item in enumerate(sorted(items, key=lambda x: (x["bbox"][1], x["bbox"][0]))):
            figures.append(Figure(id=f"fig:p{number}:{i}", page=number, **item))
    return figures

ABBREVIATIONS = {"fig", "figs", "no", "nos", "eq", "eqs", "ref", "refs", "approx", "e.g", "i.e", "vs", "cf", "dwg", "sec"}

def sentence_around(text, match):
    """The sentence containing a match; periods after abbreviations such as 'fig.' don't end it."""
    ends = [m.end() for m in re.finditer(r"[.!?]\s+", text)
            if text[:m.start()].split()[-1].lower().rstrip(".") not in ABBREVIATIONS] if text else []
    start = max([e for e in ends if e <= match.start()], default=0)
    stop = min([e for e in ends if e > match.end()], default=len(text))
    return text[start:stop].strip()[:400]

def find_references(doc, figures):
    """Attach sentences citing each figure by label. Returns unresolved references."""
    by_label = {}
    for f in figures:
        if f.label:
            by_label.setdefault(f.label, []).append(f)
    captions = {(f.page, f.caption) for f in figures if f.caption}
    unresolved = []
    for number, page in enumerate(doc, 1):
        for block in page.get_text("blocks", sort=True):
            if block[6] != 0:
                continue
            text = " ".join(block[4].split())
            if (number, text) in captions:
                continue
            for match in MENTION.finditer(text):
                label = label_of(*match.groups())
                reference = Reference(page=number, bbox=tuple(block[:4]), text=sentence_around(text, match), label=label)
                targets = by_label.get(label)
                if not targets:
                    unresolved.append(reference)
                for figure in targets or ():
                    if reference not in figure.references:
                        figure.references.append(reference)
    return unresolved

def attach_claims(figures, evidence):
    """Link visual claims inside each figure, and claims extracted from citing text."""
    for figure in figures:
        inside, citing = [], []
        for e in evidence:
            for o in e.occurrences or [e]:
                where = o.locator
                # A visual claim's locator is its whole tile or overview: attach it when tile
                # and figure mostly overlap either way; overviews only for figures covering a
                # quarter of the page, or every claim on a page would join every figure.
                if where.page == figure.page and where.region in ("tile", "overview") and figure.region:
                    shared = _overlap(where.bbox, figure.bbox)
                    close = shared >= 0.5 * max(min(_area(where.bbox), _area(figure.bbox)), 1e-6)
                    if close and (where.region == "tile" or _area(figure.bbox) >= 0.25 * _area(where.bbox)):
                        inside.append(e.id)
                for reference in figure.references:
                    if (where.page == reference.page and where.region == "text"
                            and _overlap(where.bbox, reference.bbox) > 0):
                        reference.evidence.append(e.id) if e.id not in reference.evidence else None
        figure.claims = sorted(set(inside))
    return figures

def figure_map(doc, evidence):
    """Figures with their references and claims, plus unresolved references."""
    figures = find_figures(doc)
    unresolved = find_references(doc, figures)
    attach_claims(figures, evidence)
    return figures, unresolved
