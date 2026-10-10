"""Figures found on a page: captions, clusters of vector drawings and images paired with them, drawing sheets known by
their title blocks; and figure labels ("Figure 3-1"), as captions and citing prose give them. Split from situate.py,
which asks a model about the figures found (code review 2026-10-08, A13).
"""
import math
import re

from .pages import native, reading_blocks, shown
from .schema import Figure

KINDS = {"figure": "figure", "figures": "figure", "fig": "figure", "figs": "figure", "table": "table",
         "tables": "table", "sheet": "sheet", "sheets": "sheet", "drawing": "sheet", "drawings": "sheet",
         "dwg": "sheet", "exhibit": "exhibit", "exhibits": "exhibit"}
NUMBER = r"((?:[A-Z]{1,3}-?)?\d+(?:[.-]\d+)*[a-z]?)"
# A caption's label is followed by a separator, a capitalized title or nothing; "Figure 1 shows…" is prose.
# The separator mustn't start a number: "Table 5-1 summarizes" isn't "Table 5" plus "-".
CAPTION = re.compile(r"^\s*(Figure|Fig\.?|Table|Sheet|Drawing|Dwg\.?|Exhibit)\s+" + NUMBER
                     + r"\s*(?:[:.\-–—](?!\d)|(?=(?-i:[A-Z0-9(\"“]))|$)", re.IGNORECASE)
MENTION = re.compile(r"\b(Figures?|Figs?\.?|Tables?|Sheets?|Drawings?|Dwg\.?|Exhibits?)\s+" + NUMBER, re.IGNORECASE)

CELL = 10.0          # grid resolution (points) for clustering vector drawings
BRIDGE = 2           # gaps of up to this many cells (about 20 points) don't split a cluster
MIN_PATHS = 10       # a drawing cluster needs this many paths...
MIN_AREA = 0.02      # ...and this share of the page area to count as a figure
MAX_PATH_AREA = 0.6  # paths covering more of the page (frames, backgrounds) are ignored
CAPTION_GAP = 72.0   # a caption pairs with a region at most this far above or below it
LIST_ENTRY = re.compile(r"\.{2,}\s*\d+\s*$")  # "Figure 3-1. Title ........ 12" in a list of figures
LIST_PAGE = 5        # this many unpaired caption lines on one page make it a list of figures or tables
BANNER_HEIGHT = 36   # a page-wide rectangle no taller than this is a heading bar or frame, not a figure
BANNER_WIDTH = 0.4   # share of the page width that makes a rectangle or region "page-wide"
SHEET_PATHS = 500    # a page with this many vector paths, and at least one per two text characters, is a
                     # drawing sheet (drawing sets: 2 to 4 paths per character; reports: about 0.01)
SHEET_NUMBER = re.compile(r"^[A-Z]{1,2}-?\d{1,3}(?:\.\d{1,2})?[A-Z]?$")

def label_of(kind, number):
    return f"{KINDS[kind.lower().rstrip('.')]} {number.upper()}"

def label_key(label):
    """Labels match regardless of hyphens: 'sheet A-101' cites 'sheet A101'."""
    return label.replace("-", "") if label else label

def targets(by_label, label):
    """Figures a label cites; a panel ('figure 2-4A') cites its figure ('figure 2-4') if it has none of its own."""
    key = label_key(label)
    found = by_label.get(key)
    if not found and re.search(r"\d[A-Z]$", key):
        found = by_label.get(key[:-1])
    return found

def model_label(text, kind):
    """A label the model read from a figure, normalized like a caption's; None if it isn't one."""
    text = " ".join((text or "").split())
    match = MENTION.search(text)
    if match:
        return label_of(*match.groups())
    if kind == "sheet" and SHEET_NUMBER.match(text):
        return label_of("sheet", text)
    return None

def is_sheet(drawings, characters):
    return drawings >= SHEET_PATHS and drawings >= characters / 2

def title_block(page):
    """(label, title) of a drawing sheet: the largest sheet-number-like text on the page and
    the mid-sized text next to it (e.g. 'S-701', 'PV DETAILS'); (None, '') if there is none."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            for s in line["spans"]:
                text, box = s["text"].strip(), s["bbox"]
                # Fake bold draws text twice, slightly offset: keep one.
                if text and not any(t == text and max(abs(a - b) for a, b in zip(box, other)) <= 3
                                    for _, t, other in spans):
                    spans.append((s["size"], text, box))
    if not spans:
        return None, ""
    median = sorted(size for size, _, _ in spans)[len(spans) // 2]
    numbers = [x for x in spans if SHEET_NUMBER.match(x[1]) and x[0] >= 2 * median]
    if not numbers:
        return None, ""
    size, number, box = max(numbers, key=lambda x: x[0])
    centre = lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    near = [x for x in spans if 0.35 * size <= x[0] <= 0.7 * size and math.dist(centre(box), centre(x[2])) <= 6 * size]
    near.sort(key=lambda x: (lambda r: (round(r.y0), r.x0))(shown(page, x[2])))
    return label_of("sheet", number), " ".join(text for _, text, _ in near)[:200]

def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))

def _overlap(a, b):
    return _area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))

def page_drawings(page):
    return page.get_cdrawings()

def _banner(d, page_width):
    """A heading bar or a frame around a heading: one wide, thin rectangle."""
    x0, y0, x1, y1 = d["rect"]
    items = d.get("items") or []
    rectangular = len(items) == 1 and items[0][0] in ("re", "qu")
    return rectangular and 4 <= y1 - y0 <= BANNER_HEIGHT and x1 - x0 >= BANNER_WIDTH * page_width

def drawing_regions(page, drawings=None):
    """Bounding boxes of clusters of vector paths, found on a coarse grid."""
    width, height = page.rect.width, page.rect.height
    page_area = width * height
    drawings = page_drawings(page) if drawings is None else drawings
    cells, counts = set(), {}
    for d in drawings:
        x0, y0, x1, y1 = d["rect"]
        if _area((x0, y0, x1, y1)) > MAX_PATH_AREA * page_area or _banner(d, width):
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
        wide_and_short = box[3] - box[1] <= BANNER_HEIGHT + 2 * CELL and box[2] - box[0] >= BANNER_WIDTH * width
        if paths >= MIN_PATHS and _area(box) >= MIN_AREA * page_area and not wide_and_short:
            regions.append(box)
    return sorted(regions, key=lambda b: (b[1], b[0]))

def image_regions(page):
    """Image blocks' boxes, as the page is displayed."""
    page_area = page.rect.width * page.rect.height
    return [tuple(shown(page, b["bbox"])) for b in page.get_text("dict")["blocks"]
            if b.get("type") == 1 and _area(b["bbox"]) >= 0.01 * page_area]

def find_figures(doc):
    """Figures per page: regions (drawing clusters, images) paired with captions. A drawing
    sheet (a page with a title block, or with many vector paths per text character) is one figure,
    labelled from its title block; its drawings aren't split further.
    A page with captions isn't a sheet: its drawings are captioned figures (e.g. charts)."""
    return [f for number, page in enumerate(doc, 1) for f in page_figures(page, number)]

def page_figures(page, number, drawings=None):
    """One page's figures (see find_figures). Captions, drawings and their pairing are worked out as the
    page is displayed ("below", "beside" and the page's width are about what a reader sees; a drawing sheet
    is often stored sideways), and each figure's box is recorded in the page's unrotated coordinates."""
    figures = []
    captions = []
    for block in reading_blocks(page):
        match = CAPTION.match(block[4]) if block[6] == 0 else None
        if match:
            captions.append((tuple(shown(page, block[:4])), " ".join(block[4].split()), label_of(*match.groups()),
                             KINDS[match.group(1).lower().rstrip(".")]))
    # Entries in a list of figures or tables look like captions but aren't figures.
    captions = [c for c in captions if not LIST_ENTRY.search(c[1])]
    drawings = page_drawings(page) if drawings is None else drawings  # the reader's, if fetched (Context.drawings)
    label, title = title_block(page) if not captions else (None, "")
    sheet = not captions and (label is not None or is_sheet(len(drawings), len(page.get_text("text").strip())))
    displayed = [dict(d, rect=tuple(shown(page, d["rect"]))) for d in drawings] if page.rotation else drawings
    regions = [] if sheet else drawing_regions(page, displayed) + image_regions(page)
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
    for item in items:
        if item.get("label"):
            item["label_source"] = "caption"
    if sheet:
        items.append(dict(bbox=tuple(page.rect), kind="sheet", label=label, title=title,
                          label_source="title block" if label else ""))
    for i, item in enumerate(sorted(items, key=lambda x: (x["bbox"][1], x["bbox"][0]))):  # in reading order
        if page.rotation:
            item = dict(item, bbox=tuple(native(page, item["bbox"])))
        figures.append(Figure(id=f"fig:p{number}:{i}", page=number, **item))
    return figures
