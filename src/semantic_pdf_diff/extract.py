import contextlib
import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
import math
import re
from pathlib import Path
import pymupdf
from .models import DerivationStep, Evidence, Extraction, PdfLocator, Section, claim_id, merge_occurrences
from .situate import page_figures
from .dispatch import Dispatcher
from .llm import CallLimitReached
from .progress import NoProgress, log

# Bump when prompt assembly or task construction changes, not only the template text;
# it is part of the extraction interpreter. 2: section heading path in prompts.
# 3: exactly repeated table rows follow their first occurrence. 4: claims per request configurable.
# 5: headings by position on the page; table rows located by their own box.
# 6: rules for unfamiliar charts, attributes free of conditions, parts of a whole; figure tasks.
PROMPT_VERSION = 6

EXTRACT = '''Extract atomic engineering claims from this one source. Return JSON:
{"claims":[{"entity":"component/system", "attribute":"property or directed relationship",
"value":"literal value or target", "unit":"literal unit or empty", "conditions":"load, scenario, time, tolerances, scope",
"kind":"text|table|chart|diagram", "quote":"short exact supporting text or visible labels",
"confidence":0.0, "approximate":false}], "complete":true, "issues":[]}
Maximum {max_claims} claims. Set complete=false if content is clipped, ambiguous, unreadable, or more claims remain.
For tables associate row labels, column headers and units. For charts preserve series, axes, units,
operating point and trend; estimated plotted readings MUST be approximate. For diagrams extract
labeled components and directed connections; never invent direction on unmarked edges.
Preserve negation, requirements versus proposed capabilities, ranges and inequality signs.
Extract evidence only, not commentary. Use a short canonical entity and attribute; keep numeric value separate from unit.
The attribute names the property only: put conditions (e.g. "at theta = 0", "at rated speed") in conditions.
If a value is one of several parts (one layer, one material, one member), say what it is part of in the attribute
(e.g. "spar cap material"), not "composition".
If you are not sure how to read a chart, diagram or drawing convention, say so in issues, lower confidence, and mark
readings approximate; do not guess what an unexplained symbol, colour or line style means.
'''

def extraction_template(s):
    """The extraction instructions in force: the baseline, or a variant's (with {max_claims} unfilled)."""
    template = s.extract_prompt or EXTRACT
    return template + "".join(rule.rstrip() + "\n" for rule in s.extract_rules)

# Numbered markers, from outer to inner: "Contest 9.", "9-2." or "3.1", "c.", "(iii)", "4.".
STEM = re.compile(r"^\s*(Contest \d+\.|\d+-\d+\.|\d+(?:\.\d+)+\.?|[a-z]\.|\((?:[ivx]+|\d+|[a-z])\)\.?|\d+\.)(?=\s|$)")

def _stem_level(marker):
    if marker.startswith("Contest"):
        return 0
    if re.match(r"\d+-\d+\.|\d+(\.\d+)+", marker):
        return 1
    if re.match(r"[a-z]\.", marker):
        return 2
    return 3 if marker.startswith("(") else 4

def stem_index(doc):
    """{page: [(displayed y, parents)]}: for each line, the numbered items and headings it sits
    under (research round 1), so a list item keeps its parents across page breaks. Lines that
    repeat at the same height on most pages (headers, footers) are skipped."""
    from collections import Counter
    def key(line):
        return re.sub(r"\d+", "#", "".join(s["text"] for s in line["spans"]).strip()), round(line["bbox"][1] / 5)
    pages = [page.get_text("dict", sort=True)["blocks"] for page in doc]
    seen, sizes = Counter(), Counter()
    for blocks in pages:
        keys = set()
        for block in blocks:
            for line in block.get("lines", ()):
                keys.add(key(line))
                for span in line["spans"]:
                    sizes[round(span["size"])] += len(span["text"])
        seen.update(keys)
    margins = {k for k, n in seen.items() if n >= max(2, len(doc) // 2) and k[0]}
    body = sizes.most_common(1)[0][0] if sizes else 10
    stack, pending, index = [], None, {}
    for number, (page, blocks) in enumerate(zip(doc, pages), 1):
        rows = index.setdefault(number, [])
        for block in blocks:
            for line in block.get("lines", ()):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text or key(line) in margins:
                    continue
                first = line["spans"][0]
                heading = (first["size"] > body + 0.5 or (first["flags"] & 16 and len(text) < 60)) and len(text) < 90
                match = STEM.match(text)
                if match:
                    level = _stem_level(match.group(1))
                    level = 1 if heading and level > 1 else level
                    while stack and stack[-1][0] >= level:
                        stack.pop()
                    rest = text[match.end():].strip()
                    stack.append([level, match.group(1), rest])
                    pending = stack[-1] if not rest else None  # a marker alone: its text is the next line
                elif pending is not None:
                    pending[2], pending = text, None
                rows.append((display_y(page, line["bbox"]), [f"{m} {t[:70]}".strip() for _, m, t in stack]))
    return index

SHORT_FORM = re.compile(r"\(([A-Za-z][A-Za-z0-9&/.-]{1,9})\)")

def _long_form(short, before):
    """The words before "(short)" that spell it out (Schwartz and Hearst, 2003): the short
    form's letters are matched right to left, its first letter at a word's start; None if none."""
    words = before.split()[-min(len(short) + 5, 2 * len(short)):]
    text = " ".join(words)
    letters = [c.lower() for c in short if c.isalnum()]
    i = len(text) - 1
    for k in range(len(letters) - 1, -1, -1):
        while i >= 0 and (text[i].lower() != letters[k] or (k == 0 and i > 0 and text[i - 1].isalnum())):
            i -= 1
        if i < 0:
            return None
        i -= 1
    found = text[text.rfind(" ", 0, i + 1) + 1:].strip(" ,;:")
    return found if len(found) > len(short) and short.lower() not in found.lower() else None

def glossary(doc):
    """{abbreviation: long form} for "long form (ABBR)" anywhere in the document (first one wins)."""
    out = {}
    for page in doc:
        text = " ".join(page.get_text("text").split())
        for match in SHORT_FORM.finditer(text):
            short = match.group(1).rstrip(".")
            if short in out or not any(c.isupper() for c in short) or short.isdigit():
                continue
            found = _long_form(short, text[max(0, match.start() - 200):match.start()])
            if found:
                out[short] = found
    return out

MAX_REFERENCES = 3  # definitions, and cited figures or tables, added per chunk

def references(text, terms, figures):
    """Context lines for what a chunk cites but doesn't hold: abbreviations defined elsewhere in
    the document, and the captions of the figures and tables it mentions (research round 1)."""
    from .situate import MENTION, label_key, label_of, targets
    lines = []
    defined = [f"{short} = {long}" for short, long in terms.items()
               if f"({short})" not in text and re.search(rf"\b{re.escape(short)}s?\b", text)]
    if defined:
        lines.append("Defined elsewhere: " + "; ".join(defined[:MAX_REFERENCES]))
    by_label = {}
    for figure in figures:
        if figure.label:
            by_label.setdefault(label_key(figure.label), []).append(figure)
    cited = []
    for match in MENTION.finditer(text):
        label = label_of(*match.groups())
        found = targets(by_label, label)
        name = label[0].upper() + label[1:]
        if found and found[0].caption and found[0].caption[:60] not in " ".join(text.split()):
            entry = f"{found[0].caption[:150]} (page {found[0].page})"
        elif found:
            continue  # the chunk is the caption, or the figure has none
        else:
            entry = f"{name}: not found in this document"
        if entry not in cited:
            cited.append(entry)
    if cited:
        lines.append("Cited: " + "; ".join(cited[:MAX_REFERENCES]))
    return "\n".join(lines)

CONTEXT_NOTE = "CONTEXT (for reference only: do not extract claims from it):"
LAYER_NOTE = "TEXT LAYER OF THIS REGION (from the PDF, may be partial; use it to read small labels):"

# Text shorter than this is not split further during refinement.
MIN_REFINE_BYTES = 400
# Visual refinement stops at crops narrower than this (PDF points).
MIN_REFINE_POINTS = 100

def split_utf8(text, limit):
    """Bound all chunks without dropping characters, including non-ASCII PDF text."""
    chunk, size = [], 0
    for char in text:
        n = len(char.encode())
        if size + n > limit and chunk:
            yield "".join(chunk)
            chunk, size = [], 0
        chunk.append(char)
        size += n
    if chunk:
        yield "".join(chunk)

def normalize(text):
    return " ".join(text.split())

def terms(text, fold=False):
    return set(re.findall(r"\w+(?:[.,/]\w+)*", text.casefold() if fold else text))

def quoted(quote, text):
    """The quote appears verbatim in text, up to whitespace."""
    return normalize(quote) in normalize(text)

def covered(quote, text, fold=False):
    """Every word of the quote occurs in text; tolerates quotes spanning table cells."""
    words = terms(quote, fold)
    return bool(words) and words <= terms(text, fold)

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

def _lines(page):
    """Text lines as displayed: [(Rect, text)]."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                out.append((pymupdf.Rect(line["bbox"]) * page.rotation_matrix, text))
    return out

def _graphics(page):
    """Drawings (smaller than half the page: not frames) and images, as displayed."""
    boxes = []
    for d in page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings():
        r = pymupdf.Rect(d["rect"]) * page.rotation_matrix
        if r.height < 0.5 * page.rect.height:
            boxes.append(r)
    for image in page.get_image_info():
        boxes.append(pymupdf.Rect(image["bbox"]) * page.rotation_matrix)
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
                a, b = (pymupdf.Point(p) * page.rotation_matrix for p in item[1:3])
                if abs(a.x - b.x) < 1:
                    found.append((a.x, min(a.y, b.y), max(a.y, b.y)))
            elif item[0] == "re":
                r = pymupdf.Rect(item[1]) * page.rotation_matrix
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
    spans = [(s["size"], s["text"].strip(), pymupdf.Rect(s["bbox"]) * page.rotation_matrix)
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

def visual_regions(page, side, figures=(), tiling="grid", grow=False, details=False, skip_empty=False):
    """Tiles, then whole figures, then the overview: [(tag, Rect, note)] in displayed coordinates.

    Tiles are a fixed grid (tiling="grid"), or on report-sized pages full-width bands cut at
    whitespace gaps, skipping bands with no graphics that text tasks already cover
    (tiling="bands"). grow extends grid tiles to whole text lines. details cuts a drawing sheet
    into its details (and title-block and notes columns), each tiled on its own when larger
    than a tile, with the sheet's and the detail's titles as the note. A grid can cut a chart
    from its legend or a diagram in two, so each detected figure (drawing or image, with its
    caption) is also read whole, unless it already fits inside one tile or is the whole page
    (a drawing sheet: the overview)."""
    regions = []
    if max(page.rect.width, page.rect.height) > side:
        lines = _lines(page) if grow or details else None
        viewports = sheet_details(page, lines) if details else []
        if viewports:
            from .situate import title_block
            label, heading = title_block(page)
            sheet = " ".join(x for x in (label.title() if label else "Drawing sheet", heading) if x)
            parts = []
            for number, title, rect in viewports:
                # Side columns get no note: with "Title block" (round 5b), or even the sheet's title
                # (5c), the model skipped a legible revision table as not engineering.
                note = f"{sheet}. " + (f"Detail {number}: {title}" if title else f"Detail {number}") if number else ""
                # Larger crops lose small print (round 5: a 620-point crop missed a title block's
                # revision table that 420-point tiles read), so a detail is tiled like a page.
                pieces = [rect] if max(rect.width, rect.height) <= 1.25 * side else list(tiles(rect, side))
                parts += [(grown(page, r, lines=lines) & rect if grow else r, note) for r in pieces]
            regions = [(f"tile:{i}", r, note) for i, (r, note) in enumerate(parts) if not r.is_empty]
        elif tiling == "bands" and page.rect.width <= 1.6 * side:
            graphics = _graphics(page)
            regions = [(f"tile:{i}", r, "") for i, r in enumerate(
                b for b in bands(page, side) if any(b.intersects(g) for g in graphics))]
        else:
            lines = lines if lines is not None else (_lines(page) if grow else None)
            regions = [(f"tile:{i}", grown(page, r, lines=lines) if grow else r, "")
                       for i, r in enumerate(tiles(page.rect, side))]
    if skip_empty and regions:  # drop blank tiles, keeping the others' numbers (and so their recorded keys)
        regions = [x for x, empty in zip(regions, _empty(page, [r for _, r, _ in regions])) if not empty]
    grid = [r for _, r, _ in regions] or [page.rect]
    for i, figure in enumerate(f for f in figures if f.region):
        shown = (pymupdf.Rect(figure.bbox) * page.rotation_matrix + (-FIGURE_PAD, -FIGURE_PAD, FIGURE_PAD, FIGURE_PAD)) & page.rect
        whole_page = abs(shown) >= 0.9 * abs(page.rect)
        if shown.is_empty or whole_page or any(shown in r for r in grid):
            continue
        regions.append((f"figure:{i}", shown, f"Caption: {figure.caption}" if figure.caption else ""))
    return regions + [("overview", page.rect, "")]

LOCATOR_SIDE = 384  # pixels: the page thumbnail that shows where a tile sits
LOCATOR_NOTE = ("The last image is the whole page, small, with this region outlined in red: it shows where the "
                "region sits, for orientation only.")

def render_locator(page, rect, target, side=LOCATOR_SIDE, width=3):
    """The whole page, small, with rect (displayed coordinates) outlined in red."""
    scale = side / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    box = (rect * pymupdf.Matrix(scale, scale)).irect & pix.irect
    for edge in (pymupdf.IRect(box.x0, box.y0, box.x1, box.y0 + width), pymupdf.IRect(box.x0, box.y1 - width, box.x1, box.y1),
                 pymupdf.IRect(box.x0, box.y0, box.x0 + width, box.y1), pymupdf.IRect(box.x1 - width, box.y0, box.x1, box.y1)):
        pix.set_rect(edge & pix.irect, (255, 0, 0))
    pix.save(target)

def render(page, rect, target, max_side):
    # clip is in rotated page coordinates, as used by Page.get_pixmap.
    scale = min(2.5, max_side / max(rect.width, rect.height))
    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False).save(target)

def same_form(row, header):
    """True if a row matches most non-empty cells of a header, position by position."""
    pairs = [(a, b) for a, b in zip(row, header) if a not in (None, "") or b not in (None, "")]
    return bool(pairs) and sum(a == b for a, b in pairs) / len(pairs) >= 0.5

def text_pieces(page, text_bytes):
    pieces = []
    for bi, block in enumerate(page.get_text("blocks", sort=True)):
        if block[6] != 0:
            continue
        for ci, chunk in enumerate(split_utf8(block[4].strip(), text_bytes)):
            if chunk.strip():
                pieces.append((f"{bi}.{ci}", tuple(block[:4]), chunk))
    return pieces

def text_groups(page, text_bytes, section_of=None):
    """Consecutive text blocks grouped up to the byte budget (oversized blocks split),
    never across a section boundary (section_of(bbox) names a block's section).

    Returns [(ids, [(bbox, text)])], where ids like '3.0-5.0' name the blocks grouped.
    """
    pieces = text_pieces(page, text_bytes)
    part = section_of or (lambda bbox: None)
    groups, group, size = [], [], 0
    for piece in pieces + [None]:
        extra = len(piece[2].encode()) + 2 if piece else 0
        if group and (piece is None or size + extra > text_bytes or part(piece[1]) != part(group[-1][1])):
            ids = group[0][0] + (f"-{group[-1][0]}" if len(group) > 1 else "")
            groups.append((ids, [(b, t) for _, b, t in group]))
            group, size = [], 0
        if piece:
            group.append(piece)
            size += extra
    return groups

UNIT = re.compile(r"\d\s?(?:[kMG]?W|kWh|[kM]?Pa|bar|psi|mm|cm|km|m²|m2|m³|m3|kg|L/s|l/s|L/min|°C|°F|K|%|Hz|kV|V|kVA|A|rpm|dB)\b")
REQUIREMENT = re.compile(r"\b(?:shall|must|required|requirement)\b", re.IGNORECASE)

def page_signals(page, tables):
    """Cheap triage signals for one page; summed per section."""
    text = page.get_text("text")
    drawings = page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings()
    return {"numbers": len(re.findall(r"\d+(?:[.,]\d+)?", text)), "units": len(UNIT.findall(text)),
            "requirements": len(REQUIREMENT.findall(text)), "tables": tables, "images": len(page.get_images()),
            "drawings": len(drawings), "characters": len(text.strip())}

def union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

HEADING_GAP = 40.0  # an outline entry this close above the next one is only its parent heading

def _squash(text):
    return re.sub(r"[\W_]+", "", text).casefold()

def heading_y(page, title):
    """Where an outline title sits on its page (unrotated y), or 0 when it can't be found.

    Outline destinations are often just the top of the page, so the title's own text line
    is looked for instead."""
    want = _squash(title)
    if len(want) < 3:
        return 0.0
    top = lambda bbox: display_y(page, bbox)
    for block in page.get_text("dict")["blocks"]:
        lines = block.get("lines", ())
        # A heading may be split across lines ("9-2." and "Cooking"), or begin a block.
        joined = "".join(_squash("".join(span["text"] for span in line["spans"])) for line in lines)
        if joined and joined.startswith(want):
            return top(block["bbox"])
        for line in lines:
            text = _squash("".join(span["text"] for span in line["spans"]))
            # A line may hold most of a long title, but a fragment such as a sheet number isn't the title.
            if len(text) >= 3 and (text.startswith(want) or (want.startswith(text) and len(text) >= 0.6 * len(want))):
                return top(line["bbox"])
    return 0.0

def display_y(page, bbox):
    """The top of a box (unrotated page coordinates) as the page is displayed: section
    positions follow reading order, which on a rotated page isn't the unrotated y."""
    import pymupdf
    return (pymupdf.Rect(bbox) * page.rotation_matrix).y0 if page.rotation else float(bbox[1])

class SectionIndex:
    """Which section a point in the document belongs to: the last one starting at or above it.

    index[page] is the section at the top of a page (used for per-page signals)."""

    def __init__(self, sections, doc=None):
        self.sections = sorted(sections, key=lambda s: (s.first_page, s.first_y))
        # Positions are as displayed; boxes are unrotated, so rotated pages need converting.
        self.rotations = {n: page.rotation_matrix for n, page in enumerate(doc, 1) if page.rotation} if doc else {}

    def top(self, page, bbox):
        import pymupdf
        matrix = self.rotations.get(page)
        return (pymupdf.Rect(bbox) * matrix).y0 if matrix is not None else float(bbox[1])

    def box(self, page, bbox):
        """The section a box (unrotated coordinates) starts in."""
        return self.at(page, self.top(page, bbox))

    def spanned_box(self, page, bbox):
        import pymupdf
        matrix = self.rotations.get(page)
        shown = pymupdf.Rect(bbox) * matrix if matrix is not None else pymupdf.Rect(bbox)
        return self.spanned(page, shown.y0, shown.y1)

    def at(self, page, y=0.0):
        if not self.sections:
            return None
        found = self.sections[0]
        for section in self.sections:
            if (section.first_page, section.first_y) <= (page, y + 0.5):
                found = section
            else:
                break
        return found

    def __getitem__(self, page):
        return self.at(page, 0.0)

    def spanned(self, page, y0, y1):
        """Sections a region of a page overlaps, top first."""
        found = [self.at(page, y0)]
        found += [s for s in self.sections if s.first_page == page and y0 < s.first_y < y1 and s not in found]
        return [s for s in found if s is not None]

    def boundaries(self, page):
        """y positions on a page where a new section starts."""
        return [s.first_y for s in self.sections if s.first_page == page and s.first_y > 0]

def real_table(page, table, rows):
    """Whether a detected table looks like a table, not a chart's gridlines, a drawing sheet's
    frame or paragraphs in boxes (docs/research/round-01): at least half its cells filled, few
    words straddling cell edges, 2+ rows and columns, 6+ words, under half the page, and not
    mostly long paragraphs. On the samples this kept 4 of 4 real tables and dropped 70 of 70 others."""
    cells = [c for row in rows for c in row]
    if len(rows) < 2 or max((len(r) for r in rows), default=0) < 2 or not cells:
        return False
    filled = [str(c).strip() for c in cells if c is not None and str(c).strip()]
    if len(filled) / len(cells) < 0.5 or sum(len(c.split()) for c in filled) < 6:
        return False
    if sum(len(c) > 80 for c in filled) > 0.3 * len(filled):
        return False
    box = pymupdf.Rect(table.bbox)
    if abs(box) > 0.5 * abs(page.rect):
        return False
    edges = [pymupdf.Rect(c) for c in getattr(table, "cells", None) or [] if c]
    if edges:
        words = [pymupdf.Rect(w[:4]) * page.rotation_matrix for w in page.get_text("words")]
        words = [w for w in words if w.intersects(box) and w.width > 0]
        split = sum(1 for w in words if any(0.15 < abs(w & c) / abs(w) < 0.85 for c in edges if w.intersects(c)))
        if words and split / len(words) > 0.05:
            return False
    return True

def row_boxes(table, extracted):
    """Each row's box (None where unknown), aligned with the extracted rows; [] if they don't align."""
    rows = getattr(table, "rows", None) or []
    boxes = [tuple(r.bbox) if getattr(r, "bbox", None) else None for r in rows]
    return boxes if len(boxes) == len(extracted) else []

def pdf_sections(doc, depth, pages_per_section):
    """Sections from the outline down to `depth`, else fixed page ranges.

    Returns (sections, SectionIndex). An outline section runs from its title's position
    (see heading_y) to the next title's, so one page can end one section and start the
    next. A title directly followed by the next one (a parent heading and its first
    child) gets no section of its own; the child's heading path includes it.
    """
    count = len(doc)
    path, starts = [], []
    for level, title, page in doc.get_toc(simple=True):
        if level > depth:
            continue
        path = path[:level - 1] + [" ".join(str(title).split())]
        if 1 <= page <= count:
            starts.append((page, heading_y(doc[page - 1], str(title)), list(path)))
    if starts:
        # Keep outline order: an entry can't start above the one before it on the same page
        # (a title that wasn't found takes its predecessor's position).
        for i in range(1, len(starts)):
            page, y, heading = starts[i]
            if page == starts[i - 1][0] and y < starts[i - 1][1]:
                starts[i] = (page, starts[i - 1][1], heading)
        starts.sort(key=lambda s: s[0])  # stable: outline order within a page
        kept = []
        for start in starts:
            if kept and kept[-1][0] == start[0] and start[1] - kept[-1][1] < HEADING_GAP:
                kept.pop()  # nothing of its own between it and the next title
            kept.append(start)
        if kept[0][0] > 1 or _content_above(doc, kept[0][0], kept[0][1]):
            kept.insert(0, (1, 0.0, []))  # front matter before the first title
        fields = []
        for i, (page, y, heading) in enumerate(kept):
            if i + 1 < len(kept):
                next_page, next_y, _ = kept[i + 1]
                if next_y > 0 and _content_above(doc, next_page, next_y):
                    last_page, last_y = next_page, next_y
                else:
                    last_page, last_y = max(page, next_page - 1), None
            else:
                last_page, last_y = count, None
            fields.append({"first_page": page, "first_y": y, "last_page": last_page, "last_y": last_y,
                           "heading_path": heading})
        sections = [Section(id=f"sec{i}", origin="outline", **f) for i, f in enumerate(fields, 1)]
    else:
        sections = [Section(id=f"sec{i}", origin="pages", first_page=first, last_page=min(count, first + pages_per_section - 1))
                    for i, first in enumerate(range(1, count + 1, pages_per_section), 1)]
    return sections, SectionIndex(sections, doc)

def _content_above(doc, page, y):
    """Whether any text on a page sits above y (displayed), else a section starting at y starts the page."""
    import pymupdf
    p = doc[page - 1]
    return y > 0 and any(b[6] == 0 and b[4].strip() and (pymupdf.Rect(b[:4]) * p.rotation_matrix).y1 <= y + 1
                         for b in p.get_text("blocks"))

def section_text(doc, section):
    """A section's text, clipped to where it starts and ends on its first and last pages."""
    import pymupdf
    parts = []
    for number in range(section.first_page, section.last_page + 1):
        page = doc[number - 1]
        shown = page.rect  # section positions are as displayed
        top = section.first_y if number == section.first_page else shown.y0
        bottom = section.last_y if number == section.last_page and section.last_y is not None else shown.y1
        if bottom <= top:
            continue
        parts.append(page.get_text("text", clip=pymupdf.Rect(shown.x0, top - 1, shown.x1, bottom - 1)))
    return "\n".join(parts)

# How each extraction pass gets from PDF bytes to a claim.
DERIVATION = {
    "text": [DerivationStep(step="pdf-text-layer", detail="grouped text blocks"), DerivationStep(step="model-extraction")],
    "table": [DerivationStep(step="pdf-table-detection", detail="row with provisional header"), DerivationStep(step="model-extraction")],
    "tile": [DerivationStep(step="pdf-render", detail="page tile"), DerivationStep(step="model-extraction", detail="vision")],
    "figure": [DerivationStep(step="pdf-render", detail="detected figure with its caption"),
               DerivationStep(step="model-extraction", detail="vision")],
    "overview": [DerivationStep(step="pdf-render", detail="whole page"), DerivationStep(step="model-extraction", detail="vision")],
}

@dataclass
class Job:
    """Extraction of one PDF content item, fed a page at a time by run_jobs."""
    content: str
    load: object                     # () -> path or bytes, called when the job starts
    on_task: object = None           # (row, evidence) as each task finishes
    on_sections: object = None       # (sections) once known
    on_done: object = None           # (evidence, coverage) when the job is complete
    state: dict = field(default_factory=lambda: {"pending": 0, "result": None})
    steps: object = None

def run_jobs(queues, output, client, dispatcher=None, progress=None):
    """Run extraction jobs with fair share: one queue per source, pages fed round-robin
    across sources so compared sources advance together.

    Model requests run on the dispatcher's worker threads; everything else here. A job
    whose pages are all fed keeps its document open until its own pending requests
    (which may queue refinement) finish, while its source moves on to the next job.
    """
    own = dispatcher is None
    dispatch = dispatcher or Dispatcher(client)
    # Pages are fed only while few requests are pending, so prepared requests
    # (which hold image data) stay bounded however large the documents.
    bound = max(4, 2 * dispatch.workers)
    queues = [deque(q) for q in queues]
    active, draining = [None] * len(queues), []

    def done(job):
        if job.on_done:
            job.on_done(*job.state["result"])

    with (dispatch if own else contextlib.nullcontext()):
        while True:
            fed = False
            for i, queue in enumerate(queues):
                # Each source feeds one page per turn; a job that has run out of pages
                # hands over to the source's next job within the same turn.
                while True:
                    if active[i] is None and queue:
                        job = queue.popleft()
                        job.steps = _pdf_job(job.load(), job, output, client, dispatch, progress or NoProgress())
                        active[i] = job
                    job = active[i]
                    if job is None:
                        break
                    while dispatch.pending() >= bound:
                        dispatch.wait_one()
                    step = next(job.steps, "done")
                    fed = True
                    if step == "page":
                        break
                    active[i] = None
                    if step == "waiting":
                        draining.append(job)
                    else:
                        done(job)
            for job in list(draining):
                if job.state["pending"] == 0 and next(job.steps, "done") == "done":
                    draining.remove(job)
                    done(job)
            if not fed:
                if not draining and not any(queues) and not any(active):
                    break
                if not dispatch.pending():
                    raise RuntimeError("extraction scheduler stalled: jobs wait on requests that aren't pending")
                dispatch.wait_one()

def extract_pdf(path, content, output, client, on_task=None, on_sections=None, dispatcher=None, progress=None):
    """Extract evidence from one PDF (a path or its bytes), identified by its content ID.

    Returns (evidence, coverage), both independent of the order in which tasks finish.
    on_task(row, evidence) is called as each task finishes, so a store can persist
    results task by task; on_sections(sections) is called once sections are known.
    """
    job = Job(content, lambda: path, on_task, on_sections)
    run_jobs([[job]], output, client, dispatcher, progress)
    return job.state["result"]

def _pdf_job(path, job, output, client, dispatch, progress):
    """Generator doing one PDF's extraction: yields "page" before feeding each page, then
    "waiting" while its requests are pending; job.state["result"] is set at the end."""
    content, on_task, on_sections, state = job.content, job.on_task, job.on_sections, job.state
    s = client.s
    evidence, coverage = [], []
    stem = content.split(":", 1)[1][:12]
    assets = output / "assets"
    assets.mkdir(exist_ok=True, parents=True)
    page_section = None  # a SectionIndex once the document is open

    def record(row, items=()):
        coverage.append(row)
        if on_task:
            on_task(row, list(items))

    repeats = {}

    def follow(entry, page_no, bbox, task, region):
        """Record a repeated block from its first occurrence's result, without a model call."""
        note = f"identical to {entry['task']} on page {entry['page']}; not re-sent"
        step = DerivationStep(step="repeated-block", detail=note)
        section = page_section.box(page_no, bbox)
        copies = [e.model_copy(update={"locator": PdfLocator(page=page_no, bbox=tuple(bbox), region=region, task=task),
                                       "section": section.id, "derivation": [*e.derivation, step]})
                  for e in entry["found"]]
        row = {"content": content, "page": page_no, "bbox": list(bbox), "task": task, "image": None,
               "status": entry["row"]["status"], "issues": [note], "claims": len(copies), "duplicate_of": entry["task"]}
        evidence.extend(copies)
        record(row, copies)

    def consume(page_no, bbox, task, text, image=None, check=None, locate=None, crop=None, derivation=None, then=None,
                repeat_key=None, repeat_after=1, place=None, context="", extra_images=()):
        """Queue one extraction task; when it finishes, record it and call then(status).

        repeat_key identifies exactly repeated boilerplate: once `repeat_after` earlier
        sightings prove the repetition, the task follows the first occurrence's result
        instead of calling the model (or is extracted normally if that one failed).

        check(quote) -> bool | None. Native tasks reject claims failing it; visual tasks
        only record the result. locate(quote) narrows a claim's bbox within the task.
        place(quote) -> box or None: where a visual claim's quote sits, to find its section.
        Each claim found becomes one occurrence; sightings of the same claim by other
        tasks are merged into one piece of evidence afterwards (union provenance).
        """
        region = task.split(":")[0]
        entry = None
        if repeat_key is not None and s.dedupe_repeated:
            entry = repeats.setdefault(repeat_key, {"task": task, "page": page_no, "seen": 0, "done": False,
                                                    "ok": False, "found": [], "row": None, "followers": []})
            entry["seen"] += 1
            if entry["task"] != task and entry["seen"] - 1 >= repeat_after:
                again = lambda: consume(page_no, bbox, task, text, image, check, locate, crop, derivation, then,
                                        place=place, context=context, extra_images=extra_images)
                if not entry["done"]:
                    entry["followers"].append((lambda: follow(entry, page_no, bbox, task, region), again))
                elif entry["ok"]:
                    follow(entry, page_no, bbox, task, region)
                else:
                    again()
                return
            if entry["task"] != task:
                entry = None  # an early sighting, extracted normally before repetition is proven
        found = []
        row = {"content": content, "page": page_no, "bbox": list(bbox), "task": task,
               "image": image, "status": "complete", "issues": [], "claims": 0}
        images = ([output / image] if image else []) + [output / x for x in extra_images]
        section = page_section.box(page_no, bbox)  # the heading above the region, not the page's
        # A region spanning sections (a tile, an overview) is told all their headings.
        heading = " | ".join(" > ".join(x.heading_path) for x in page_section.spanned_box(page_no, bbox)
                             if x.heading_path)
        rules = "".join(rule.rstrip() + "\n" for rule in s.visual_rules) if region in ("tile", "figure", "overview") else ""
        prompt = (extraction_template(s).replace("{max_claims}", str(s.claims_per_request)) + rules
                  + "\nSource type: " + region
                  + (f"\nSection: {heading}" if heading else "") + (f"\n{context}" if context else "")
                  + "\nSOURCE DATA:\n" + text)
        key = ("extract", region, content, task, hashlib.sha256(text.encode()).hexdigest(), crop, heading)
        if context:  # only then, so requests without context keep their recorded keys
            key += (hashlib.sha256(context.encode()).hexdigest(),)
        if rules:  # image-task rules aren't in the interpreter's prompt hash (text tasks keep replaying),
            key += ("visual rules", hashlib.sha256(rules.encode()).hexdigest())  # so they're in the key

        def finish(result, error):
            state["pending"] -= 1
            if error is not None:
                row.update(status="not_reached" if isinstance(error, CallLimitReached) else "failed", issues=[str(error)])
            else:
                handle(result)
            evidence.extend(found)
            record(row, found)
            progress.finish(row["status"])
            if entry is not None:  # the first occurrence of a repeated block: release its followers
                entry.update(done=True, ok=row["status"] in ("complete", "partial"), found=list(found), row=row)
                for followed, again in entry.pop("followers"):
                    followed() if entry["ok"] else again()
                entry["followers"] = []
            log.debug("%s %s: %s, %d claim(s)%s", Path(name).name, task, row["status"], row["claims"],
                      f" ({'; '.join(row['issues'])[:200]})" if row["issues"] else "")
            if then:
                then(row["status"])

        def handle(result):
            row["status"] = "complete" if result.complete else "partial"
            row["issues"] = list(result.issues)
            for claim in result.claims:
                verified = check(claim.quote) if check else None
                if not image and not verified:
                    row["status"] = "partial"
                    row["issues"].append("Rejected claim with unsupported literal quote")
                    continue
                eid = claim_id(content, claim)
                if any(e.id == eid for e in found):
                    continue  # the same claim twice in one response: keep the first
                where = tuple(locate(claim.quote) if locate else bbox)
                spot = place(claim.quote) if place else where
                home = page_section.box(page_no, spot).id if spot is not None else section.id
                found.append(Evidence(**claim.model_dump(), id=eid, content=content, section=home,
                                      locator=PdfLocator(page=page_no, bbox=where, region=region, task=task),
                                      derivation=derivation or DERIVATION[region], image=image, quote_verified=verified))
                row["claims"] += 1

        progress.add()
        state["pending"] += 1
        dispatch.submit(prompt, Extraction, images, key, finish)

    blocks_of = {}

    def page_blocks(page_no):
        """The page's text blocks in reading order: [(bbox, text)]."""
        if page_no not in blocks_of:
            blocks_of[page_no] = [(tuple(b[:4]), " ".join(b[4].split())) for b in doc[page_no - 1].get_text("blocks", sort=True)
                                  if b[6] == 0 and b[4].strip()]
        return blocks_of[page_no]

    def surrounding(page_no, first, last, before, after):
        """Text before the block at `first` and after the block at `last`, crossing to the
        neighbouring pages when the page runs out."""
        if not before and not after:
            return ""
        blocks = page_blocks(page_no)
        boxes = [b for b, _ in blocks]
        i0 = boxes.index(first) if first in boxes else 0
        i1 = len(boxes) - 1 - boxes[::-1].index(last) if last in boxes else len(boxes) - 1
        head = " ".join(t for _, t in blocks[:i0])
        tail = " ".join(t for _, t in blocks[i1 + 1:])
        if before and len(head) < before and page_no > 1:
            head = " ".join(t for _, t in page_blocks(page_no - 1)) + " " + head
        if after and len(tail) < after and page_no < len(doc):
            tail = tail + " " + " ".join(t for _, t in page_blocks(page_no + 1))
        parts = []
        if before and head.strip():
            parts.append("Before: ..." + head.strip()[-before:])
        if after and tail.strip():
            parts.append("After: " + tail.strip()[:after] + "...")
        return (CONTEXT_NOTE + "\n" + "\n".join(parts)) if parts else ""

    tables_on = {}  # page -> the boxes of its tables (a row's lead-in is above its whole table)

    def table_top(page_no, row_box):
        for box in tables_on.get(page_no, ()):
            if box[1] - 2 <= row_box[1] <= box[3] + 2:
                return box
        return row_box

    def lead_in(page_no, bbox, limit):
        """Text just above a table (its lead-in sentence or caption), as context."""
        if not limit:
            return ""
        above = " ".join(t for b, t in page_blocks(page_no) if b[3] <= bbox[1] + 2)
        return (CONTEXT_NOTE + "\nAbove the table: ..." + above.strip()[-limit:]) if above.strip() else ""

    stems = {}

    def within(page_no, bbox):
        """The numbered items and headings a region sits under, e.g. '9-2. Cooking > c. ...'."""
        if not s.stem_context:
            return ""
        if not stems:
            stems.update(stem_index(doc))
        top = display_y(doc[page_no - 1], bbox)
        path = []
        for number in range(page_no, 0, -1):  # the last line above it, on this page or earlier ones
            above = [p for y, p in stems.get(number, []) if number < page_no or y < top - 1]
            if above:
                path = above[-1]
                break
        return ("Within: " + " > ".join(path)) if path else ""

    def with_within(context, page_no, bbox):
        line = within(page_no, bbox)
        if not line:
            return context
        return (context + "\n" + line) if context else (CONTEXT_NOTE + "\n" + line)

    cited = {}

    def with_references(context, text):
        if not s.references:
            return context
        if not cited:
            cited.update(terms=glossary(doc), figures=[f for n, page in enumerate(doc, 1) for f in page_figures(page, n)])
        lines = references(text, cited["terms"], cited["figures"])
        if not lines:
            return context
        return (context + "\n" + lines) if context else (CONTEXT_NOTE + "\n" + lines)

    def text_task(page_no, segments, task, depth=0):
        """segments: [(bbox, text)] of consecutive blocks sent together."""
        text = "\n\n".join(t for _, t in segments)
        context = with_within(surrounding(page_no, segments[0][0], segments[-1][0], s.context_before, s.context_after),
                              page_no, segments[0][0])
        context = with_references(context, text)
        def locate(quote):
            return next((b for b, t in segments if quoted(quote, t)), union(b for b, _ in segments))
        consume(page_no, union(b for b, _ in segments), task, text, check=lambda q: quoted(q, text), locate=locate,
                context=context,
                then=lambda status: refine_text(page_no, segments, text, task, depth, status))

    def refine_text(page_no, segments, text, task, depth, status):
        if status == "complete" or depth >= s.refinement_depth:
            return
        if len(segments) > 1:
            middle = len(segments) // 2
            parts = [segments[:middle], segments[middle:]]
        elif len(text.encode()) > MIN_REFINE_BYTES:
            bbox = segments[0][0]
            parts = [[(bbox, p)] for p in split_utf8(text, max(200, len(text.encode()) // 2))]
        else:
            return
        for i, part in enumerate(parts):
            text_task(page_no, part, f"{task}:r{i}", depth + 1)

    def table_task(page_no, bbox, task, header, row, columns, depth=0, derivation=None, repeat_key=None):
        """Send one table row with its header; split wide or partial rows by column.

        Column 0 is kept in every split as the provisional row label.
        """
        pick = lambda cells: [cells[c] if c < len(cells) else None for c in columns]
        head, cells = pick(header), pick(row)
        text = "Header: " + json.dumps(head, ensure_ascii=False) + "\nRow: " + json.dumps(cells, ensure_ascii=False)
        flat = " ".join(str(c) for c in head + cells if c not in (None, ""))
        fits = len(text.encode()) <= s.text_bytes
        splittable = len(columns) > 2
        if not fits and not splittable:
            record({"content": content, "page": page_no, "bbox": list(bbox), "task": task, "image": None,
                    "status": "partial", "issues": ["Table row exceeds text budget; inspect visual tiles"], "claims": 0})
            return
        if fits:
            def then(status):
                if status != "complete" and depth < s.refinement_depth and splittable:
                    split_columns(page_no, bbox, task, header, row, columns, depth + 1, derivation)
            consume(page_no, bbox, task, text, derivation=derivation, check=lambda q: quoted(q, text) or covered(q, flat),
                    then=then, repeat_key=repeat_key, repeat_after=2,
                    context=with_references(with_within(lead_in(page_no, table_top(page_no, bbox), s.table_context),
                                                        page_no, table_top(page_no, bbox)), flat))
        else:
            split_columns(page_no, bbox, task, header, row, columns, depth, derivation)

    def split_columns(page_no, bbox, task, header, row, columns, depth, derivation):
        rest = columns[1:]
        middle = (len(rest) + 1) // 2
        for i, part in enumerate([rest[:middle], rest[middle:]]):
            # Budget-driven splits are mandatory; only quality-driven ones use depth.
            table_task(page_no, bbox, f"{task}:c{i}", header, row, [columns[0], *part], depth, derivation)

    def visual_task(page_no, page, tag, rect, depth=0, text=""):
        name = f"{stem}-{tag.replace(':', '-')}.png"
        render(page, rect, assets / name, s.image_side)
        native = rect * page.derotation_matrix
        layer = page.get_text("text", clip=native)
        check = (lambda q: covered(q, layer, fold=True)) if layer.strip() else None
        blocks = [(tuple(b[:4]), b[4]) for b in page.get_text("blocks", clip=native) if b[6] == 0]
        def place(quote):  # the first text block in the region holding the quote
            return next((box for box, text in blocks if covered(quote, text, fold=True)), None)
        if s.visual_text_layer and layer.strip():
            text = (text + "\n" if text else "") + LAYER_NOTE + "\n" + " ".join(layer.split())[:s.visual_text_layer]
        extra, context = (), ""
        if s.tile_locator and tag.startswith("tile"):  # where on the page this tile sits
            where = f"{stem}-{tag.replace(':', '-')}-where.png"
            render_locator(page, rect, assets / where)
            extra, context = ("assets/" + where,), CONTEXT_NOTE + "\n" + LOCATOR_NOTE
        consume(page_no, native, tag, text, "assets/" + name, check=check, place=place,
                crop=(tuple(round(v, 3) for v in rect), s.image_side), context=context, extra_images=extra,
                then=lambda status: refine_visual(page_no, page, tag, rect, depth, status))

    def refine_visual(page_no, page, tag, rect, depth, status):
        # Refine only local tiles; an overview or a whole figure may be incomplete because
        # it spans many facts, and all its areas already have tile coverage.
        if (status == "complete" or tag.split(":")[0] in ("overview", "figure") or depth >= s.refinement_depth
                or min(rect.width, rect.height) < MIN_REFINE_POINTS):
            return
        if rect.width > rect.height:
            mid = (rect.x0 + rect.x1) / 2
            children = [pymupdf.Rect(rect.x0, rect.y0, mid + 12, rect.y1), pymupdf.Rect(mid - 12, rect.y0, rect.x1, rect.y1)]
        else:
            mid = (rect.y0 + rect.y1) / 2
            children = [pymupdf.Rect(rect.x0, rect.y0, rect.x1, mid + 12), pymupdf.Rect(rect.x0, mid - 12, rect.x1, rect.y1)]
        for i, child in enumerate(children):
            visual_task(page_no, page, f"{tag}-r{i}", child, depth + 1)

    name = content if isinstance(path, (bytes, bytearray)) else Path(path).name
    opened = pymupdf.open(stream=path, filetype="pdf") if isinstance(path, (bytes, bytearray)) else pymupdf.open(path)
    with opened as doc:
        if doc.needs_pass:
            raise ValueError(f"{name}: encrypted PDF needs to be decrypted before comparison")
        if not doc.is_pdf or not len(doc):
            raise ValueError(f"{name}: expected a nonempty PDF")
        sections, owner = pdf_sections(doc, s.section_depth, s.section_pages)
        page_section = owner
        if on_sections:
            on_sections(sections)
        signals = {}
        # (header, width) of a table that ended near the bottom of the previous page
        carried = None
        for number, page in enumerate(doc, 1):
            yield "page"
            # Native coordinates stay unrotated (PDF point coordinates). Consecutive
            # blocks are grouped up to the byte budget; oversized blocks are split.
            for ids, segments in text_groups(page, s.text_bytes, lambda b, n=number: owner.box(n, b).id):
                text_task(number, segments, f"text:p{number}:{ids}")
            try:
                # Table detection works in displayed coordinates; locators are unrotated.
                native = lambda b: tuple(pymupdf.Rect(b) * page.derotation_matrix) if b else None
                found = [(native(table.bbox), rows, [native(b) for b in row_boxes(table, rows)])
                         for table in page.find_tables().tables for rows in [table.extract()]
                         if not s.table_filter or real_table(page, table, rows)]
            except Exception as e:  # PyMuPDF table detection raises assorted internal errors
                found = []
                record({"content": content, "page": number, "bbox": list(page.rect * page.derotation_matrix),
                        "task": f"table-detection:p{number}", "image": None, "status": "failed",
                        "issues": [type(e).__name__ + ": " + str(e)], "claims": 0})
            height = page.rect.height
            continuing, carried = carried, None
            tables_on[number] = [bbox for bbox, _, _ in found]
            for ti, (bbox, rows, boxes) in enumerate(found):
                if not rows:
                    continue
                shown = pymupdf.Rect(bbox) * page.rotation_matrix  # continuation is judged as displayed
                header, body, derivation = rows[0], rows[1:] or rows, None
                body_boxes = boxes[1:] if len(rows) > 1 else boxes
                width = max(len(r) for r in rows)
                # A table at the top of a page, as wide as one that ended at the bottom of the
                # previous page, continues it, unless its first row is a header of the same
                # form (a new table, e.g. the next day's schedule). An identical first row is
                # a repeated header and is skipped.
                if (ti == 0 and continuing and continuing[1] == width and shown.y0 - page.rect.y0 < 0.2 * height
                        and (rows[0] == continuing[0] or not same_form(rows[0], continuing[0]))):
                    if rows[0] != continuing[0]:
                        body, body_boxes = rows, boxes
                    header = continuing[0]
                    derivation = [DerivationStep(step="pdf-table-detection",
                                                 detail=f"row with header continued from page {number - 1}"),
                                  DerivationStep(step="model-extraction")]
                for ri, row in enumerate(body):
                    # Rows with no content (common where drawing geometry is detected as a
                    # table) cost a model call and can't yield a claim.
                    if all(c is None or not str(c).strip() for c in row):
                        continue
                    # Exactly repeated rows (same header and cells, same table position) follow their
                    # first occurrence from the third sighting on; text is never de-duplicated.
                    key = ("table", json.dumps([header, row], ensure_ascii=False, default=str),
                           tuple(round(v / 2) * 2 for v in bbox))
                    row_box = body_boxes[ri] if ri < len(body_boxes) and body_boxes[ri] else tuple(bbox)
                    table_task(number, tuple(row_box), f"table:p{number}:{ti}:{ri}", header, row, list(range(width)),
                               derivation=derivation, repeat_key=key)
                if shown.y1 - page.rect.y0 > 0.8 * height:
                    carried = (header, width)
                else:
                    carried = None
            section = owner[number].id
            for name_, value in page_signals(page, len(found)).items():
                signals.setdefault(section, {}).setdefault(name_, 0)
                signals[section][name_] += value
            if s.vision:
                shown_figures = page_figures(page, number) if s.figure_tasks else []
                for tag, rect, note in visual_regions(page, s.tile_points, shown_figures, s.tiling, s.grow_tiles,
                                                      s.sheet_details, s.skip_empty):
                    # Task tags are unique within content: "<region>:p<page>[:<index>]".
                    region, _, index = tag.partition(":")
                    tag = f"{region}:p{number}" + (f":{index}" if index else "")
                    # A figure's caption, or a sheet detail's titles, as source text.
                    visual_task(number, page, tag, rect, text=note)
            else:
                record({"content": content, "page": number, "bbox": list(page.rect * page.derotation_matrix),
                        "task": f"vision:p{number}", "image": None, "status": "skipped",
                        "issues": ["Visual extraction disabled; charts, diagrams and scans may be missed"], "claims": 0})
        if on_sections:
            on_sections([x.model_copy(update={"signals": signals.get(x.id, {})}) for x in sections])
        while state["pending"]:  # refinement may still render crops from this document
            yield "waiting"
    coverage.sort(key=lambda r: (r["page"] or 0, r["task"]))
    state["result"] = (merge_occurrences(evidence), coverage)
