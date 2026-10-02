"""Page tests: reading whole pages by slicing or shrinking them, and by asking for close-ups.

The eye test's cards measure what a model reads in an image of a given size. A PDF page fixes the
text's size in points, and we choose how to cut the page up. The owner, 2026-09-30: "we should be
looking at visual acuity within this sort of slicing vs. shrinking tradeoff frame"; and "how good
vision models are at asking for close-up views of a regions (and identifying those regions) when
(a) prompted to do so as needed, and (b) we know when it's needed based on prior test results. Sort
of an investigative test."

Sheets are synthetic pages at real sizes (a letter page; an ARCH D drawing sheet with line work),
with random codes and numbers at known positions and font sizes. Two ways to read them:
- Static plans: the whole page shrunk into one image, or tiles of a given side in points (the
  pipeline's own tiling), each rendered at a given size in pixels.
- Close-ups: an overview, from which the model lists what it reads and asks for close-ups (boxes,
  or cells of a labelled grid drawn on the image), each of which may ask for closer ones, within a
  depth and a quota. Prompted to zoom as needed ("free"), or told the page has text below the
  model's measured threshold at this scale ("informed").
Scored by recall per font size, spurious items, queries and tokens; for close-ups, also whether the
requested regions held the text too small to read.
"""
import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from pydantic import Field
from .eyetest import CAP, _Answer, code, compact, number, threshold

PAGES = {"letter": (612, 792), "archd": (2592, 1728)}
FONT_PT = (4, 5, 6, 7, 8, 10, 12, 14)
TILES = {"letter": (420, 288, 204, 144), "archd": (864, 576, 420, 288)}
# What each kind of sheet holds: items per font size scattered over it, and clusters of small text
# (count, size in points, items per font size). Detail sheets have body text an overview can read
# and small text only in their clusters (callouts on a drawing, small print on a page), so there
# is a right answer to where a close-up is needed.
LAYOUTS = {
    "letter": {"scattered": dict.fromkeys(FONT_PT, 5)},
    "archd": {"scattered": dict.fromkeys(FONT_PT, 12)},
    "letter-detail": {"scattered": {10: 8, 12: 8, 14: 8}, "clusters": (2, (170, 110), {4: 4, 5: 4})},
    "archd-detail": {"scattered": {24: 6, 32: 6, 48: 6}, "clusters": (3, (380, 250), {5: 2, 6: 2, 7: 2, 8: 2})},
    # Corner sheets (the owner, 2026-09-30: "tiny illegible text across multiple cells ... Perhaps stick it on a
    # four corners"): one cluster centred where four cells of the overview's grid meet, so one close-up of a
    # range of cells covers it, and one inside a single cell for contrast. Read only by close-ups.
    "letter-corner": {"scattered": {10: 8, 12: 8, 14: 8}, "clusters": (2, (170, 110), {4: 4, 5: 4}), "corner": True},
    "archd-corner": {"scattered": {24: 6, 32: 6, 48: 6}, "clusters": (2, (380, 250), {5: 2, 6: 2, 7: 2, 8: 2}),
                     "corner": True},
}
ZOOM_ONLY = ("letter-corner", "archd-corner")

def grid_shape(width, height):
    """(columns, rows) of the labelled grid drawn over an image of this shape (about GRID_CELLS cells)."""
    cols = max(1, round(math.sqrt(GRID_CELLS * width / height)))
    return cols, max(1, round(GRID_CELLS / cols))

def paper(kind):
    return kind.split("-")[0]

def fonts(kind):
    layout = LAYOUTS[kind]
    return sorted(set(layout["scattered"]) | set((layout.get("clusters") or (0, 0, {}))[2]))
RENDER_PX = (768, 1536)
OVERVIEW_PX = 1024          # the long side of a close-up run's overview
CROP_PX = 768               # the long side of each close-up
MAX_DEPTH, MAX_ZOOMS, QUOTA = 2, 6, 40
GRID_CELLS = 12             # about this many cells in a labelled grid
GRID_RED = (0.85, 0.1, 0.1)
VARIANTS = ("free-boxes", "free-cells", "informed-boxes", "informed-cells", "informed-ranges")
GRIDDED = ("cells", "ranges")
RANGE = re.compile(r"[A-K]\d+\s*(?::|-|–|—|\bto\b)\s*[A-K]\d+", re.I)  # a request naming a rectangle of cells  # variants naming regions by a labelled grid drawn over the image

class Found(_Answer):
    items: list[str] = Field(default_factory=list)
    zoom: list = Field(default_factory=list)

@dataclass(frozen=True)
class Sheet:
    kind: str
    seed: int = 1

    @property
    def id(self):
        return f"{self.kind}-s{self.seed}"

def sheets():
    return [Sheet(k, s) for k in LAYOUTS for s in (1, 2)]

# --- drawing ------------------------------------------------------------------------------------

def _touches(box, p, q, pad):
    """Whether the segment p-q passes within pad of box (sampled)."""
    for k in range(41):
        x, y = p[0] + (q[0] - p[0]) * k / 40, p[1] + (q[1] - p[1]) * k / 40
        if box[0] - pad <= x <= box[2] + pad and box[1] - pad <= y <= box[3] + pad:
            return True
    return False

def draw(sheet):
    """(document, page, items): items are {"text", "pt" (font size), "box" (points)}. Line work
    on drawing sheets keeps clear of the items; every item is checked against the text layer."""
    import pymupdf
    rng = random.Random(sheet.id)
    w, h = PAGES[paper(sheet.kind)]
    layout = LAYOUTS[sheet.kind]
    doc = pymupdf.open()
    page = doc.new_page(width=w, height=h)
    drawing = paper(sheet.kind) == "archd"
    margin = 54 if drawing else 36
    blocked = [(w - 700, h - 280, w - margin, h - margin)] if drawing else []  # a title block
    items, seen = [], set()
    overlaps = lambda a, b, pad: not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])

    def place(pt, area, cluster=None):
        while True:
            text = code(rng) if rng.random() < 0.5 else number(rng)
            if compact(text) in seen:
                continue
            width, cap = pymupdf.get_text_length(text, fontname="helv", fontsize=pt), CAP["helv"] * pt
            if width > area[2] - area[0]:
                continue
            x, y = rng.uniform(area[0], area[2] - width), rng.uniform(area[1] + cap, area[3] - 0.3 * pt)
            box = (x, y - cap, x + width, y + 0.25 * pt)
            others = [i["box"] for i in items] + blocked + ([] if cluster is not None else clusters)
            if any(overlaps(box, b, pt) for b in others):
                continue
            page.insert_text((x, y), text, fontname="helv", fontsize=pt)
            items.append({"text": text, "pt": pt, "box": box, "cluster": cluster})
            seen.add(compact(text))
            return

    clusters = []
    count, (cw, ch), per_size = layout.get("clusters") or (0, (0, 0), {})
    if layout.get("corner"):  # the first cluster sits on an inner corner of the overview's grid
        cols, rows = grid_shape(w, h)
        corners = [(w * i / cols, h * j / rows) for i in range(1, cols) for j in range(1, rows)]
        cx, cy = rng.choice([c for c in corners if not any(overlaps((c[0] - cw / 2, c[1] - ch / 2, c[0] + cw / 2,
                                                                       c[1] + ch / 2), b, 60) for b in blocked)])
        clusters.append((cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))
        cell_w, cell_h, pad = w / cols, h / rows, 10
        if cw + 2 * pad > cell_w or ch + 2 * pad > cell_h:
            raise ValueError(f"{sheet.id}: a cluster can't fit inside one cell")
        for _ in range(500):  # the rest each inside one cell
            if len(clusters) >= count:
                break
            i, j = rng.randrange(cols), rng.randrange(rows)
            x = rng.uniform(i * cell_w + pad, (i + 1) * cell_w - pad - cw)
            y = rng.uniform(j * cell_h + pad, (j + 1) * cell_h - pad - ch)
            rect = (x, y, x + cw, y + ch)
            if not any(overlaps(rect, b, 30) for b in clusters + blocked) and \
                    margin <= x and x + cw <= w - margin and margin <= y and y + ch <= h - margin:
                clusters.append(rect)
        if len(clusters) < count:
            raise ValueError(f"{sheet.id}: no room for a cluster inside one cell")
    while len(clusters) < count:
        x, y = rng.uniform(margin, w - margin - cw), rng.uniform(margin, h - margin - ch)
        rect = (x, y, x + cw, y + ch)
        if not any(overlaps(rect, b, 60) for b in clusters + blocked):
            clusters.append(rect)
    for k, rect in enumerate(clusters):
        for pt, n in per_size.items():
            for _ in range(n):
                place(pt, rect, cluster=k)
    for pt, n in layout["scattered"].items():
        for _ in range(n):
            place(pt, (margin, margin, w - margin, h - margin))
    if drawing:
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(margin / 2, margin / 2, w - margin / 2, h - margin / 2))
        shape.draw_rect(pymupdf.Rect(*blocked[0]))
        for k in range(1, 4):
            y = blocked[0][1] + k * (blocked[0][3] - blocked[0][1]) / 4
            shape.draw_line((blocked[0][0], y), (blocked[0][2], y))
        shape.finish(color=(0, 0, 0), width=1.2)
        lines = 0
        while lines < 60:
            p = (rng.uniform(margin, w - margin), rng.uniform(margin, h - margin))
            length, angle = rng.uniform(40, 400), rng.choice((0, math.pi / 2, rng.uniform(0, math.pi)))
            q = (p[0] + length * math.cos(angle), p[1] + length * math.sin(angle))
            if not (margin <= q[0] <= w - margin and margin <= q[1] <= h - margin):
                continue
            if any(_touches(i["box"], p, q, 3) for i in items):
                continue
            shape.draw_line(p, q)
            lines += 1
        shape.finish(color=(0.35, 0.35, 0.35), width=0.6)
        shape.commit()
    layer = compact(page.get_text("text"))
    missing = [i["text"] for i in items if compact(i["text"]) not in layer]
    if missing:
        raise ValueError(f"{sheet.id}: not in the text layer: {missing[:5]}")
    return doc, page, items

def picture(page, clip, px, grid=False):
    """(png, (width, height)) of a page region rendered with its long side at px; with grid, a
    labelled grid of about GRID_CELLS cells drawn over it (returned too, as {label: region})."""
    import pymupdf
    clip = pymupdf.Rect(clip)
    scale = px / max(clip.width, clip.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False)
    png, size = pix.tobytes("png"), (pix.width, pix.height)
    if not grid:
        return png, size, {}
    cols, rows = grid_shape(clip.width, clip.height)
    doc = pymupdf.open()
    canvas = doc.new_page(width=size[0], height=size[1])
    canvas.insert_image(canvas.rect, stream=png)
    shape = canvas.new_shape()
    for i in range(1, cols):
        shape.draw_line((i * size[0] / cols, 0), (i * size[0] / cols, size[1]))
    for j in range(1, rows):
        shape.draw_line((0, j * size[1] / rows), (size[0], j * size[1] / rows))
    shape.finish(color=GRID_RED, width=1.0)
    shape.commit()
    cells = {}
    for j in range(rows):
        for i in range(cols):
            label = f"{'ABCDEFGHJK'[i]}{j + 1}"
            x0, y0 = i * size[0] / cols, j * size[1] / rows
            canvas.draw_rect(pymupdf.Rect(x0 + 1, y0 + 1, x0 + 29, y0 + 17), color=None, fill=(1, 1, 1))
            canvas.insert_text((x0 + 3, y0 + 14), label, fontname="helv", fontsize=13, color=GRID_RED)
            cells[label] = pymupdf.Rect(clip.x0 + i * clip.width / cols, clip.y0 + j * clip.height / rows,
                                        clip.x0 + (i + 1) * clip.width / cols, clip.y0 + (j + 1) * clip.height / rows)
    return canvas.get_pixmap(dpi=72, alpha=False).tobytes("png"), size, cells

# --- prompts ------------------------------------------------------------------------------------

def _base(whole):
    return (f"The image shows {'a whole page' if whole else 'a close-up of part of a page'}. Codes and numbers are "
            "scattered on it; they're random, so nothing can be guessed from context. List every code or number you can "
            "read exactly as printed. Leave out anything you can't read exactly: don't guess.")

def static_prompt(whole):
    return _base(whole) + '\nReturn only JSON: {"items": ["..."]}'

def zoom_prompt(whole, variant, threshold=None, can_zoom=True):
    informed, cells, ranges = variant.startswith("informed"), variant.endswith(GRIDDED), variant.endswith("ranges")
    text = _base(whole)
    if can_zoom:
        grid_note = "the red grid and its labels are drawn over the page to name regions, and aren't part of it"
        where = (f'name each by its grid cell (e.g. "B2") or a rectangle of cells (e.g. "B2:C3"), as labelled in red; '
                 f'{grid_note}' if ranges else
                 f'name each by its grid cell, as labelled in red (e.g. "B2"; {grid_note})' if cells else
                 "give each as a box [x0, y0, x1, y1] in coordinates from 0 to 1000 across and down the image")
        if informed and threshold:
            text += (f" This page has text too small to read at this scale: text under about {threshold:.0f} pixels "
                     "tall (capital letters) in this image can't be read reliably. Find every region with text that "
                     f"small and ask for a close-up of each: {where}. At most {MAX_ZOOMS}.")
        else:
            text += (" If some text is too small to read here, ask for close-ups of the regions where it is: "
                     f"{where}. At most {MAX_ZOOMS}, or none if you've read everything.")
        example = '["B2", "C3:D4"]' if ranges else '["B2", "C3"]' if cells else "[[100, 200, 350, 420]]"
        return text + f'\nReturn only JSON: {{"items": ["..."], "zoom": {example}}}'
    return text + '\nReturn only JSON: {"items": ["..."]}'

# --- reading ------------------------------------------------------------------------------------

def _region(request, clip, cells, page_rect):
    """A zoom request as a page region (padded, clamped, at least 48 points a side), or None."""
    import pymupdf
    if isinstance(request, str) and request.strip().startswith("["):
        try:
            request = json.loads(request)
        except ValueError:
            return None
    if isinstance(request, str):
        ends = [e.strip().upper() for e in re.split(r"\s*(?::|-|–|—|\bto\b)\s*", request.strip(), maxsplit=1)]
        if not all(e in cells for e in ends):
            return None
        rect = pymupdf.Rect(cells[ends[0]]) | cells[ends[-1]]  # one cell, or the rectangle of cells between two
    else:
        values = request.get("box") if isinstance(request, dict) else request
        try:
            x0, y0, x1, y1 = (float(v) for v in values)
        except (TypeError, ValueError):
            return None
        x0, x1 = sorted((x0, x1))
        y0, y1 = sorted((y0, y1))
        rect = pymupdf.Rect(clip.x0 + x0 / 1000 * clip.width, clip.y0 + y0 / 1000 * clip.height,
                            clip.x0 + x1 / 1000 * clip.width, clip.y0 + y1 / 1000 * clip.height)
    pad = max(rect.width, rect.height) * 0.08
    rect = pymupdf.Rect(rect.x0 - pad, rect.y0 - pad, rect.x1 + pad, rect.y1 + pad)
    if rect.width < 48:
        rect.x0, rect.x1 = rect.x0 - (48 - rect.width) / 2, rect.x1 + (48 - rect.width) / 2
    if rect.height < 48:
        rect.y0, rect.y1 = rect.y0 - (48 - rect.height) / 2, rect.y1 + (48 - rect.height) / 2
    rect &= page_rect
    if rect.is_empty or rect.width * rect.height > 0.8 * clip.width * clip.height:
        return None  # nothing, or no closer than what was seen
    return rect

def plans(sheet, max_tiles=None):
    """A sheet's static plans: (tile side in points, or None for the whole page; render px), leaving
    out those of more than max_tiles tiles."""
    import pymupdf
    from semantic_pdf_diff.extract import tiles
    rect = pymupdf.Rect(0, 0, *PAGES[paper(sheet.kind)])
    sides = [t for t in (None,) + TILES[paper(sheet.kind)]
             if max_tiles is None or t is None or len(list(tiles(rect, t))) <= max_tiles]
    return [(t, px) for t in sides for px in RENDER_PX]

def run_static(folder, client, sheet, strategies=None):
    """{strategy: [(key, items read)]}: each plan's queries. Strategies are (tile side in points or
    None for the whole page, render px)."""
    import pymupdf
    from semantic_pdf_diff.dispatch import Dispatcher
    from semantic_pdf_diff.extract import tiles
    doc, page, _ = draw(sheet)
    strategies = strategies or plans(sheet)
    target = Path(folder) / "images"
    target.mkdir(parents=True, exist_ok=True)
    out = {}
    with Dispatcher(client) as dispatch:
        for side, px in strategies:
            name = f"{'whole' if side is None else f't{side}'}-{px}"
            rects = [page.rect] if side is None else list(tiles(page.rect, side))
            out[name] = []
            for k, rect in enumerate(rects):
                png, _, _ = picture(page, rect, px)
                path = target / f"{sheet.id}-{name}-{k}.png"
                path.write_bytes(png)
                key = ("pagetest", f"{sheet.id}|{name}|{k}", [round(v, 2) for v in rect], px)  # region, px: labels

                def finish(value, error, name=name, key=key):
                    out[name].append((key[1], [] if error is not None else list(value.items), None if error is None
                                      else str(error)[:200], key[2]))
                dispatch.submit(static_prompt(side is None), Found, [path], key, finish)
        dispatch.drain()
    doc.close()
    return out

def run_zoom(folder, client, sheet, variant, threshold=None):
    """[(key, page region, depth, items read, regions asked for, error, requests that gave no close-up with
    why, every request as given)]: an overview, then the
    close-ups the model asks for, depth-first within MAX_DEPTH and QUOTA. threshold(w, h): the
    model's reading threshold in px for an image of that size (for "informed")."""
    import pymupdf
    from semantic_pdf_diff.dispatch import Dispatcher
    doc, page, _ = draw(sheet)
    target = Path(folder) / "images"
    target.mkdir(parents=True, exist_ok=True)
    grid = variant.endswith(GRIDDED)
    log, asked = [], [0]

    with Dispatcher(client) as dispatch:
        def ask(rect, depth, path_id):
            if asked[0] >= QUOTA:
                return
            asked[0] += 1
            px = OVERVIEW_PX if depth == 0 else CROP_PX
            png, size, cells = picture(page, rect, px, grid=grid and depth < MAX_DEPTH)  # no grid where no zooming
            file = target / f"{sheet.id}-{variant}-{path_id}.png"
            file.write_bytes(png)
            t = threshold(*size) if threshold else None
            prompt = zoom_prompt(depth == 0, variant, t, can_zoom=depth < MAX_DEPTH)
            key = ("pagetest", f"{sheet.id}|{variant}|{path_id}", [round(v, 2) for v in rect], px)

            def finish(value, error, rect=rect, depth=depth, path_id=path_id, cells=cells, key=key):
                if error is not None:
                    log.append((key[1], tuple(rect), depth, [], [], str(error)[:200], [], []))
                    return
                regions, unused = [], []  # unused: requests that gave no close-up, kept so none vanish unseen
                requests = list(value.zoom or []) if depth < MAX_DEPTH else []
                for n, request in enumerate(requests):
                    region = _region(request, rect, cells, page.rect) if n < MAX_ZOOMS else None
                    if region is None:
                        unused.append((str(request)[:60], "over the limit" if n >= MAX_ZOOMS else "not a usable region"))
                    elif any((region & r).get_area() > 0.8 * region.get_area() for r in regions):
                        unused.append((str(request)[:60], "repeats another"))
                    else:
                        regions.append(region)
                log.append((key[1], tuple(rect), depth, list(value.items), [tuple(r) for r in regions], None, unused,
                            [str(r)[:60] for r in requests]))
                for k, region in enumerate(regions):
                    ask(region, depth + 1, f"{path_id}.{k}")
            dispatch.submit(prompt, Found, [file], key, finish)
        ask(page.rect, 0, "0")
        dispatch.drain()
    doc.close()
    return log

# --- scoring ------------------------------------------------------------------------------------

def score(sheet, answers):
    """Recall per font size, spurious items, and misses by whether a static plan's tiles held the item
    whole. answers: every item read (strings), from all of a plan's queries."""
    _, _, items = draw(sheet)
    truth = {compact(i["text"]): i for i in items}
    got = {compact(a) for a in answers if compact(a)}
    found = {k for k in truth if k in got}
    by_pt = {}
    for k, i in truth.items():
        by_pt.setdefault(i["pt"], []).append(k in found)
    return {"recall": round(len(found) / len(truth), 4), "items": len(truth),
            "by_pt": {f"{pt:g}": round(sum(v) / len(v), 3) for pt, v in sorted(by_pt.items())},
            "spurious": len(got - set(truth))}

def whole_in_tiles(sheet, side):
    """Share of items lying wholly inside at least one tile of a plan (the rest are cut by tile edges)."""
    import pymupdf
    from semantic_pdf_diff.extract import tiles
    doc, page, items = draw(sheet)
    rects = [page.rect] if side is None else list(tiles(page.rect, side))
    doc.close()
    return round(sum(any(pymupdf.Rect(r).contains(pymupdf.Rect(i["box"])) for r in rects) for i in items) / len(items), 4)

def zoom_quality(sheet, log, threshold):
    """For a close-up run: of the items too small to read in the overview (by the model's threshold),
    the share inside some requested close-up; and of the close-ups asked for, the share holding any."""
    import pymupdf
    _, _, items = draw(sheet)
    overview = [e for e in log if e[2] == 0]
    if not overview:
        return {}
    clip = pymupdf.Rect(overview[0][1])
    scale = OVERVIEW_PX / max(clip.width, clip.height)
    size = (round(clip.width * scale), round(clip.height * scale))
    t = threshold(*size) if threshold else 7.0
    small = [i for i in items if CAP["helv"] * i["pt"] * scale < t]
    regions = [pymupdf.Rect(r) for e in log for r in e[4]]
    first = [pymupdf.Rect(r) for r in overview[0][4]]
    covered = sum(any(r.contains(pymupdf.Rect(i["box"])) for r in regions) for i in small)
    useful = sum(any(r.contains(pymupdf.Rect(i["box"])) for i in small) for r in first)
    clusters = {i["cluster"] for i in items if i.get("cluster") is not None}
    found = {i["cluster"] for i in items if i.get("cluster") is not None
             and any(r.intersects(pymupdf.Rect(i["box"])) for r in first)}
    return {"small_items": len(small), "small_covered": round(covered / len(small), 3) if small else None,
            "first_zooms": len(first), "first_zooms_useful": round(useful / len(first), 3) if first else None,
            "threshold_px": round(t, 1),
            **({"clusters_found": round(len(found) / len(clusters), 3)} if clusters else {})}

def acuity(results_path, model):
    """threshold(w, h) in px from the eye test's cards for this model: its threshold per 1000 px of
    side at the nearest image size, times the side. None when the model has no eye test."""
    path = Path(results_path)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))["models"].get(model)
    if not data:
        return None
    relative = {tuple(map(int, k.split("x"))): v for k, v in data["summary"]["relative"].items() if v}

    def threshold(w, h):
        size = min(relative, key=lambda s: abs(math.log(s[0] * s[1] / (w * h))))
        return relative[size] * math.sqrt(w * h) / 1000
    return threshold

def usage(folder, responder):
    """{(query label, region): (prompt tokens, completion tokens)} as the host reported them, from the fixture.
    Labels alone are ambiguous: a query leaves out the model, so models asking for the same close-up share it,
    each run labelling it by its own numbering."""
    from semantic_pdf_diff.fixtures import folder_fixture
    fixture = folder_fixture(folder)
    try:
        rows = fixture.db.execute("SELECT r.region, r.parts, s.usage FROM response s JOIN recipe r ON r.query = s.query "
                                  "WHERE s.responder = ? AND r.role = 'pagetest'", (responder,)).fetchall()
    finally:
        fixture.close()
    out = {}
    for label, parts, used in rows:
        u = json.loads(used or "{}")
        region = tuple(round(v, 1) for v in json.loads(parts)[2])  # recorded at 2 decimals; matched at 1
        out[(label, region)] = (u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0)
    return out

def _cost(queries, tokens):
    """queries: [(label, page region)]."""
    found = [tokens.get((label, tuple(round(round(v, 2), 1) for v in rect)), (0, 0)) for label, rect in queries]
    return {"queries": len(queries), "prompt_tokens": sum(f[0] for f in found),
            "completion_tokens": sum(f[1] for f in found)}

def results(static, zooms, tokens, threshold=None):
    """Per sheet and plan: scores and costs. static: {sheet id: run_static's output}; zooms:
    {sheet id: {variant: run_zoom's log}}."""
    by_id = {s.id: s for s in sheets()}
    out = {"static": {}, "zoom": {}}
    unasked = lambda error: bool(error) and error.startswith("No recorded answer")  # replayed, never asked
    for sid, runs in static.items():
        sheet = by_id[sid]
        for name, queries in runs.items():
            if queries and all(unasked(q[2]) for q in queries):
                continue
            side = None if name.startswith("whole") else int(name.split("-")[0][1:])
            answers = [a for q in queries for a in q[1]]
            out["static"].setdefault(sid, {})[name] = {
                **score(sheet, answers), **_cost([(q[0], q[3]) for q in queries], tokens),
                "failed": sum(1 for q in queries if q[2]), "whole_in_tiles": whole_in_tiles(sheet, side)}
    for sid, runs in zooms.items():
        sheet = by_id[sid]
        for variant, log in runs.items():
            if not log or any(e[2] == 0 and unasked(e[5]) for e in log):
                continue
            answers = [a for e in log for a in e[3]]
            out["zoom"].setdefault(sid, {})[variant] = {
                **score(sheet, answers), **_cost([(e[0], e[1]) for e in log], tokens),
                "failed": sum(1 for e in log if e[5]),
                "zooms_unused": sum(len(e[6]) for e in log if len(e) > 6),
                "ranges_asked": sum(1 for e in log if len(e) > 7 for r in e[7] if RANGE.search(r)), "depths": {d: sum(1 for e in log if e[2] == d) for d in range(MAX_DEPTH + 1)},
                **zoom_quality(sheet, log, threshold)}
    return out

def pooled(model_results):
    """Each plan's scores pooled over a kind of sheet's seeds: {kind: {"static"|"zoom": {plan: {...}}}}."""
    out = {}
    for part in ("static", "zoom"):
        for sid, plans in model_results[part].items():
            kind = sid.rsplit("-s", 1)[0]
            for name, r in plans.items():
                acc = out.setdefault(kind, {}).setdefault(part, {}).setdefault(name, {"n": 0})
                acc["n"] += 1
                for k, v in r.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        acc[k] = acc.get(k, 0) + v
                    elif k == "by_pt":
                        for pt, x in v.items():
                            acc.setdefault("by_pt", {}).setdefault(pt, []).append(x)
    for kind in out.values():
        for part in kind.values():
            for acc in part.values():
                n = acc.pop("n")
                for k in list(acc):
                    if k == "by_pt":
                        acc[k] = {pt: round(sum(v) / len(v), 3) for pt, v in acc[k].items()}
                        acc["min_pt"] = threshold([(float(pt), v) for pt, v in acc[k].items()])  # read at 90%
                    elif k in ("recall", "whole_in_tiles", "small_covered", "first_zooms_useful", "threshold_px",
                               "clusters_found"):
                        acc[k] = round(acc[k] / n, 3)
                    else:
                        acc[k] = round(acc[k] / n, 1)  # per sheet
    return out

def _num(value):
    return "–" if value is None else f"{value:g}"

def page(folder, data):
    """report.html: for each kind of sheet, every plan's recall by font size and its cost, per model."""
    from semantic_pdf_diff.html_pages import esc
    from .eyetest import STYLE, _cell
    out = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width, initial-scale=1'><title>Page tests</title><style>{STYLE}</style></head><body>",
           "<h1>Page tests: slicing, shrinking and close-ups</h1>",
           "<p>Synthetic pages at real sizes with random codes and numbers at known font sizes. Static plans read the "
           "whole page shrunk into one image, or tiles of a given side in points rendered at a given size in pixels. "
           "Close-up runs start from an overview and follow the close-ups the model asks for (free: as it sees fit; "
           "informed: told the page has text below its measured threshold). Figures are per sheet, averaged over "
           "seeds; recall is the share of items read exactly.</p>"]
    for kind in LAYOUTS:
        w, h = PAGES[paper(kind)]
        out.append(f"<h2>{esc(kind)} ({w} × {h} pt)</h2>")
        for model, r in data["models"].items():
            pooled_ = r["pooled"].get(kind, {})
            for part in ("static", "zoom"):
                plans = pooled_.get(part)
                if not plans:
                    continue
                pts = [f"{p:g}" for p in fonts(kind)]
                extra = ["whole_in_tiles"] if part == "static" else ["small_covered", "first_zooms", "first_zooms_useful",
                                                                     "clusters_found"]
                out.append(f"<h3>{esc(model)}: {'static plans' if part == 'static' else 'close-ups'}</h3>"
                           "<div class='scroll'><table><tr><th>Plan</th>" + "".join(f"<th>{p} pt</th>" for p in pts) +
                           "<th>All</th><th>Smallest read (pt)</th><th>Spurious</th><th>Queries</th><th>Prompt tokens</th>" +
                           "".join(f"<th>{esc(e)}</th>" for e in extra) + "</tr>")
                for name, acc in plans.items():
                    out.append(f"<tr><td>{esc(name)}</td>" + "".join(_cell(acc.get("by_pt", {}).get(p)) for p in pts) +
                               _cell(acc.get("recall")) + f"<td>{_num(acc.get('min_pt'))}</td>"
                               f"<td>{acc.get('spurious', 0):g}</td><td>{acc.get('queries', 0):g}</td>"
                               f"<td>{acc.get('prompt_tokens', 0):g}</td>" +
                               "".join(f"<td>{'–' if acc.get(e) is None else f'{acc[e]:g}'}</td>" for e in extra) + "</tr>")
                out.append("</table></div>")
    out.append("</body></html>")
    target = Path(folder) / "report.html"
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    return target
