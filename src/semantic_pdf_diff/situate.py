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

# --- model requests ------------------------------------------------------------------

# Bump when prompts or request construction change; part of the triage interpreter.
PROMPT_VERSION = 1

SITUATE_FIGURE = '''Situate one figure (or table, or drawing sheet) from an engineering document, using only the
material below: its caption, the sentences that cite it, claims extracted from it, and its image if given.
Return JSON {"about": "what it depicts: subject, scope and the kinds of information shown",
"role": "why the document includes it, as the citing sentences explain; empty if they don't say",
"keywords": ["component, system or topic terms"]}.
Do not state specific values, quantities or design decisions in "about" or "role". Do not guess beyond the material.
'''

SITUATE_SECTION = '''Describe one section of an engineering document, using only the material below: its heading
path, its text, claims extracted from it (including from charts and diagrams), the figures it contains, and page
images if given. Return JSON {"type": "specification|requirements|narrative|calculation|data|drawing|procedure|
legal|administrative|reference|other", "density": "low|medium|high (how much specific engineering information)",
"keywords": ["component, system or topic terms"], "about": "a few sentences on the section's subject and scope:
the components and kinds of information it covers"}.
Omit specific values, quantities and design decisions from "about". Do not guess beyond the material.
'''

MAX_CITATIONS = 8
MAX_FIGURE_CLAIMS = 40
MAX_SECTION_CLAIMS = 150
MAX_OVERVIEWS = 3

def claim_line(e):
    unit = f" {e.unit}" if e.unit else ""
    conditions = f" ({e.conditions})" if e.conditions else ""
    return f"- {e.entity} | {e.attribute} | {e.value}{unit}{conditions}"

def diagram_heavy(section):
    """Little text but drawings or images: e.g. drawing sheets."""
    pages = section.last_page - section.first_page + 1
    sig = section.signals
    return sig.get("characters", 0) / pages < 800 and (sig.get("drawings", 0) / pages > 200 or sig.get("images", 0) > 0)

def fit_text(text, client, prompt, images):
    """Trim section text to the request budget; returns (text, trimmed?)."""
    from .llm import SYSTEM
    s = client.s
    room = (s.context_tokens - s.output_tokens - s.safety_tokens - 256 - len(images) * s.image_tokens
            - len((SYSTEM + prompt).encode()))
    data = text.encode()
    if len(data) <= room:
        return text, False
    return data[:max(0, room)].decode(errors="ignore"), True

def situate(doc, content, evidence, sections, output, client, dispatch, progress, image_side=None):
    """Figures, then sections (bottom-up): returns (figures, sections, unresolved, issues).

    Model requests run on the dispatcher; everything else on this thread.
    """
    import hashlib
    import pymupdf
    from .models import FigureAbout, SectionAbout
    figures, unresolved = figure_map(doc, evidence)
    by_id = {e.id: e for e in evidence}
    stem = content.split(":", 1)[1][:12]
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    side = image_side or client.s.image_side
    issues = []

    def render(page_no, rect, name):
        page = doc[page_no - 1]
        rect = pymupdf.Rect(rect)
        scale = min(2.5, side / max(rect.width, rect.height, 1))
        page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False).save(assets / name)
        return output / "assets" / name

    def key(kind, ident, *parts):
        return ("triage", kind, content, ident, hashlib.sha256("\x00".join(parts).encode()).hexdigest())

    section_of = {}
    for section in sections:
        for page in range(section.first_page, section.last_page + 1):
            section_of[page] = section

    # 1. Figures with labels: the ones prose can cite.
    for figure in figures:
        if not figure.label:
            continue
        heading = " > ".join(section_of[figure.page].heading_path) if figure.page in section_of else ""
        citations = "\n".join(f"- (page {r.page}) {r.text}" for r in figure.references[:MAX_CITATIONS]) or "(none found)"
        claims = "\n".join(claim_line(by_id[i]) for i in figure.claims[:MAX_FIGURE_CLAIMS] if i in by_id) or "(none)"
        prompt = (SITUATE_FIGURE + f"\nSection: {heading}\nCaption: {figure.caption}\nCiting sentences:\n{citations}"
                  f"\nClaims extracted from it:\n{claims}\n")
        images = [render(figure.page, figure.bbox, f"{stem}-{figure.id.replace(':', '-')}.png")] if figure.region else []

        def finish(result, error, figure=figure):
            progress.finish("failed" if error else "complete")
            if error is not None:
                issues.append({"target": figure.id, "issue": str(error), "failed": True})
                return
            figure.about, figure.role, figure.keywords = result.about, result.role, list(result.keywords)
        progress.add()
        dispatch.submit(prompt, FigureAbout, images, key("figure", figure.id, prompt), finish)
    dispatch.drain()

    # 2. Sections, from their text, claims and figures.
    text_by_page = {n: page.get_text("text") for n, page in enumerate(doc, 1)}
    updated = {}
    for section in sections:
        pages = range(section.first_page, section.last_page + 1)
        text = "\n".join(text_by_page[p] for p in pages).strip()
        inside = [e for e in evidence if e.locator.page in pages]
        claims = "\n".join(claim_line(e) for e in inside[:MAX_SECTION_CLAIMS]) or "(none)"
        figs = "\n".join(f"- {f.label or 'unlabelled figure'} (page {f.page}): {f.about or f.caption or '(not described)'}"
                         for f in figures if f.page in pages and (f.label or f.claims)) or "(none)"
        images = []
        if diagram_heavy(section):
            images = [render(p, doc[p - 1].rect, f"{stem}-overview-p{p}.png") for p in list(pages)[:MAX_OVERVIEWS]]
        heading = " > ".join(section.heading_path) or "(no heading)"
        head = (SITUATE_SECTION + f"\nHeading path: {heading}\nPages: {section.first_page}-{section.last_page}"
                f"\nFigures:\n{figs}\nClaims:\n{claims}\nText:\n")
        body, trimmed = fit_text(text, client, head, images)
        if trimmed:
            issues.append({"target": section.id, "issue": "text trimmed to fit the context budget", "failed": False})
        prompt = head + body

        def finish(result, error, section=section):
            progress.finish("failed" if error else "complete")
            if error is not None:
                issues.append({"target": section.id, "issue": str(error), "failed": True})
                updated[section.id] = section
                return
            updated[section.id] = section.model_copy(update={"about": result.about, "section_type": result.type,
                                                             "density": result.density, "keywords": list(result.keywords)})
        progress.add()
        dispatch.submit(prompt, SectionAbout, images, key("section", section.id, prompt), finish)
    dispatch.drain()
    return figures, [updated.get(s.id, s) for s in sections], unresolved, issues
