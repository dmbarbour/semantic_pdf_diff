"""Situating: figures, what cites them, and what they (and sections) are about.

This module's first part is mechanical: it finds figures (drawing clusters, images and
captions), the prose that cites them by label, and the claims inside them. The model
requests that write "about" statements build on it.
"""
import math
import re
from .models import Figure, Reference

KINDS = {"figure": "figure", "figures": "figure", "fig": "figure", "figs": "figure", "table": "table",
         "tables": "table", "sheet": "sheet", "sheets": "sheet", "drawing": "sheet", "drawings": "sheet",
         "dwg": "sheet", "exhibit": "exhibit", "exhibits": "exhibit"}
NUMBER = r"((?:[A-Z]{1,3}-?)?\d+(?:[.-]\d+)*[a-z]?)"
# A caption's label is followed by a separator, a capitalized title or nothing; "Figure 1 shows…" is prose.
CAPTION = re.compile(r"^\s*(Figure|Fig\.?|Table|Sheet|Drawing|Dwg\.?|Exhibit)\s+" + NUMBER
                     + r"\s*(?:[:.\-–—]|(?=(?-i:[A-Z0-9(\"“]))|$)", re.IGNORECASE)
MENTION = re.compile(r"\b(Figures?|Figs?\.?|Tables?|Sheets?|Drawings?|Dwg\.?|Exhibits?)\s+" + NUMBER, re.IGNORECASE)

CELL = 10.0          # grid resolution (points) for clustering vector drawings
BRIDGE = 2           # gaps of up to this many cells (about 20 points) don't split a cluster
MIN_PATHS = 10       # a drawing cluster needs this many paths...
MIN_AREA = 0.02      # ...and this share of the page area to count as a figure
MAX_PATH_AREA = 0.6  # paths covering more of the page (frames, backgrounds) are ignored
CAPTION_GAP = 72.0   # a caption pairs with a region at most this far above or below it
LIST_ENTRY = re.compile(r"\.{2,}\s*\d+\s*$")  # "Figure 3-1. Title ........ 12" in a list of figures
LIST_PAGE = 5        # this many unpaired caption lines on one page make it a list of figures or tables
SHEET_PATHS = 500    # a page with this many vector paths, and at least one per two text characters, is a
                     # drawing sheet (drawing sets: 2 to 4 paths per character; reports: about 0.01)
SHEET_NUMBER = re.compile(r"^[A-Z]{1,2}-?\d{1,3}(?:\.\d{1,2})?[A-Z]?$")
PARAGRAPH = 1500     # characters of a citing paragraph kept

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

def native_rect(page):
    """The page in unrotated coordinates, like text, drawings and figure boxes."""
    return page.rect * page.derotation_matrix

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
    import pymupdf
    near.sort(key=lambda x: (lambda r: (round(r.y0), r.x0))(pymupdf.Rect(x[2]) * page.rotation_matrix))
    return label_of("sheet", number), " ".join(text for _, text, _ in near)[:200]

def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))

def _overlap(a, b):
    return _area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))

def page_drawings(page):
    return page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings()

def drawing_regions(page, drawings=None):
    """Bounding boxes of clusters of vector paths, found on a coarse grid."""
    width, height = page.rect.width, page.rect.height
    page_area = width * height
    drawings = page_drawings(page) if drawings is None else drawings
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
    """Figures per page: regions (drawing clusters, images) paired with captions. A drawing
    sheet (a page with a title block, or with many vector paths per text character) is one figure,
    labelled from its title block; its drawings aren't split further.
    A page with captions isn't a sheet: its drawings are captioned figures (e.g. charts)."""
    figures = []
    for number, page in enumerate(doc, 1):
        captions = []
        for block in page.get_text("blocks", sort=True):
            match = CAPTION.match(block[4]) if block[6] == 0 else None
            if match:
                captions.append((tuple(block[:4]), " ".join(block[4].split()), label_of(*match.groups()),
                                 KINDS[match.group(1).lower().rstrip(".")]))
        # Entries in a list of figures or tables look like captions but aren't figures.
        captions = [c for c in captions if not LIST_ENTRY.search(c[1])]
        drawings = page_drawings(page)
        label, title = title_block(page) if not captions else (None, "")
        sheet = not captions and (label is not None or is_sheet(len(drawings), len(page.get_text("text").strip())))
        regions = [] if sheet else drawing_regions(page, drawings) + image_regions(page)
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
            items.append(dict(bbox=tuple(native_rect(page)), kind="sheet", label=label, title=title,
                              label_source="title block" if label else ""))
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
            by_label.setdefault(label_key(f.label), []).append(f)
    captions = {(f.page, f.caption) for f in figures if f.caption}
    unresolved = []
    for number, page in enumerate(doc, 1):
        for block in page.get_text("blocks", sort=True):
            if block[6] != 0:
                continue
            text = " ".join(block[4].split())
            # Captions and list-of-figures entries name figures; they don't cite them.
            if (number, text) in captions or LIST_ENTRY.search(text):
                continue
            seen = set()
            for match in MENTION.finditer(text):
                label = label_of(*match.groups())
                if label_key(label) in seen:  # one reference per paragraph and label
                    continue
                seen.add(label_key(label))
                reference = Reference(page=number, bbox=tuple(block[:4]), text=sentence_around(text, match), label=label,
                                      paragraph=text[:PARAGRAPH])
                cited = targets(by_label, label)
                if not cited:
                    unresolved.append(reference)
                for figure in cited or ():
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

def resolve(figures, unresolved):
    """Attach unresolved references to figures that have since gained a label (e.g. read by
    the model). Returns (figures that gained references, references still unresolved)."""
    by_label = {}
    for f in figures:
        if f.label:
            by_label.setdefault(label_key(f.label), []).append(f)
    gained, still = [], []
    for reference in unresolved:
        cited = targets(by_label, reference.label)
        if not cited:
            still.append(reference)
        for figure in cited or ():
            figure.references.append(reference)
            gained.append(figure) if figure not in gained else None
    return gained, still

def surroundings(page, bbox, limit=1500):
    """(text before, text after) a figure on its page, outside it, in reading order."""
    before, after = [], []
    middle = (bbox[1] + bbox[3]) / 2
    for block in page.get_text("blocks", sort=True):
        text = " ".join(block[4].split()) if block[6] == 0 else ""
        box = tuple(block[:4])
        if not text or _overlap(box, bbox) > 0.5 * _area(box):
            continue
        (before if (box[1] + box[3]) / 2 < middle else after).append(text)
    return " ".join(before)[-limit:], " ".join(after)[:limit]

def position(page, figure):
    if figure.kind == "sheet" and _area(figure.bbox) >= 0.9 * _area(tuple(page.rect)):
        return "the whole page"
    import pymupdf
    shown = pymupdf.Rect(figure.bbox) * page.rotation_matrix  # as the page is displayed
    top, bottom = page.rect.y0, page.rect.y1
    third = ((shown.y0 + shown.y1) / 2 - top) / max(bottom - top, 1)
    return "top of the page" if third < 1 / 3 else "middle of the page" if third < 2 / 3 else "bottom of the page"

def figure_map(doc, evidence):
    """Figures with their references and claims, plus unresolved references."""
    figures = find_figures(doc)
    unresolved = find_references(doc, figures)
    attach_claims(figures, evidence)
    return figures, unresolved

# --- model requests ------------------------------------------------------------------

# Bump when prompts or request construction change; part of the triage interpreter.
PROMPT_VERSION = 2

SITUATE_FIGURE = '''Situate one figure (or table, drawing sheet or image) from an engineering document, using only the
material below: where it sits in the document, its caption or title block, the text around it, the paragraphs
that cite it, claims extracted from it, and its image if given.
Return JSON {"about": "what it depicts: subject, scope and the kinds of information shown",
"role": "why the document includes it, as the citing paragraphs or surrounding text explain; empty if they don't say",
"keywords": ["component, system or topic terms"],
"label": "an identifier printed in the figure itself, e.g. Figure 3, Sheet A-101, Detail 4; empty if none",
"title": "a title printed in the figure itself; empty if none"}.
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
MAX_SECTION_FIGURES = 60
MAX_OVERVIEWS = 3
SHEET_TEXT = 3000     # characters of a drawing sheet's own text
AROUND = 1500         # characters of text before and after a figure
SCALES = (1, 0.5, 0.25, 0.1)  # material is cut to these shares until a request fits the budget

def claim_line(e):
    unit = f" {e.unit}" if e.unit else ""
    conditions = f" ({e.conditions})" if e.conditions else ""
    return f"- {e.entity} | {e.attribute} | {e.value}{unit}{conditions}"

def room(client, prompt, images):
    """Bytes left in the request budget after the prompt and images."""
    from .llm import SYSTEM
    s = client.s
    return (s.context_tokens - s.output_tokens - s.safety_tokens - 256 - len(images) * s.image_tokens
            - len((SYSTEM + prompt).encode()))

def fit_text(text, client, prompt, images):
    """Trim section text to the request budget; returns (text, trimmed?)."""
    left = room(client, prompt, images)
    data = text.encode()
    if len(data) <= left:
        return text, False
    return data[:max(0, left)].decode(errors="ignore"), True

def fit(build, client, images):
    """The first build(scale) that fits the budget; returns (prompt, trimmed?)."""
    for scale in SCALES:
        prompt = build(scale)
        if room(client, "", images) - len(prompt.encode()) >= 0:
            return prompt, scale < 1
    return prompt, True  # still too large: the request fails and is reported

def scanned(page, text):
    """Images and almost no text: a scan, which only an image of the page can show."""
    return bool(page.get_images()) and len(text.strip()) < 200

def figure_material(doc, figure, section_of, by_id, text_by_page):
    """Everything a figure request is given besides the image, as {part: text}."""
    page = doc[figure.page - 1]
    heading = lambda p: " > ".join(section_of[p].heading_path) if p in section_of and section_of[p].heading_path else ""
    part = {"location": f"page {figure.page} of {len(doc)}, {position(page, figure)}"
                        + (f"; section: {heading(figure.page)}" if heading(figure.page) else "")}
    if figure.label:
        part["label"] = f"{figure.label} (from its {figure.label_source or 'caption'})"
    if figure.caption:
        part["caption"] = figure.caption
    if figure.title:
        part["title"] = figure.title
    if position(page, figure) == "the whole page":
        part["text on the sheet"] = " ".join(text_by_page[figure.page].split())
    else:
        part["text before it"], part["text after it"] = surroundings(page, figure.bbox, AROUND)
    part["paragraphs citing it"] = "\n".join(
        f"- (page {r.page}" + (f", section: {heading(r.page)}" if heading(r.page) else "") + f") {r.paragraph or r.text}"
        for r in figure.references[:MAX_CITATIONS])
    part["claims extracted from it"] = "\n".join(claim_line(by_id[i]) for i in figure.claims[:MAX_FIGURE_CLAIMS] if i in by_id)
    return part

def figure_prompt(part, scale):
    limits = {"text on the sheet": SHEET_TEXT, "text before it": AROUND, "text after it": AROUND,
              "paragraphs citing it": MAX_CITATIONS * PARAGRAPH, "claims extracted from it": 6000}
    lines = [SITUATE_FIGURE]
    for name, text in part.items():
        limit = limits.get(name)
        if limit is not None:
            limit = int(limit * scale)
            text = text[-limit:] if name == "text before it" else text[:limit]
        title = name[0].upper() + name[1:]
        if not text:
            lines.append(f"{title}: (none)")
        elif limit is not None or "\n" in text:
            lines.append(f"{title}:\n{text}")
        else:
            lines.append(f"{title}: {text}")
    return "\n".join(lines) + "\n"

def situate(doc, content, evidence, sections, output, client, dispatch, progress, image_side=None):
    """Figures, then sections (bottom-up): returns (figures, sections, unresolved, issues).

    Every figure gets a request. Figures that gain citations from labels the model read
    get one more, with the citing paragraphs. Model requests run on the dispatcher;
    everything else on this thread.
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
    text_by_page = {n: page.get_text("text") for n, page in enumerate(doc, 1)}
    issues = []

    def render(page_no, rect, name):
        page = doc[page_no - 1]
        rect = pymupdf.Rect(rect) * page.rotation_matrix  # figure boxes are unrotated; rendering isn't
        whole = abs(rect & page.rect) >= 0.99 * abs(page.rect)
        scale = min(2.5, side / max(rect.width, rect.height, 1))
        page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=None if whole else rect, alpha=False).save(assets / name)
        return output / "assets" / name

    def key(kind, ident, *parts):
        return ("triage", kind, content, ident, hashlib.sha256("\x00".join(parts).encode()).hexdigest())

    section_of = {}
    for section in sections:
        for page in range(section.first_page, section.last_page + 1):
            section_of[page] = section

    def ask_figure(figure):
        images = [render(figure.page, figure.bbox, f"{stem}-{figure.id.replace(':', '-')}.png")] if figure.region else []
        part = figure_material(doc, figure, section_of, by_id, text_by_page)
        prompt, trimmed = fit(lambda scale: figure_prompt(part, scale), client, images)
        if trimmed:
            issues.append({"target": figure.id, "issue": "material trimmed to fit the context budget", "failed": False})

        def finish(result, error):
            progress.finish("failed" if error else "complete")
            if error is not None:
                issues.append({"target": figure.id, "issue": str(error), "failed": True})
                return
            figure.about, figure.role, figure.keywords = result.about, result.role, list(result.keywords)
            label = model_label(result.label, figure.kind)
            if not figure.label and label:
                figure.label, figure.label_source = label, "model"
            if not figure.title and result.title:
                figure.title = " ".join(result.title.split())
        progress.add()
        dispatch.submit(prompt, FigureAbout, images, key("figure", figure.id, prompt), finish)

    # 1. Every figure; then those that gained citations from labels read by the model.
    for figure in figures:
        ask_figure(figure)
    dispatch.drain()
    gained, unresolved = resolve(figures, unresolved)
    if gained:
        attach_claims(gained, evidence)  # claims from the newly citing text
        for figure in gained:
            ask_figure(figure)
        dispatch.drain()

    # 2. Sections, from their text, claims and figures.
    sheets = {f.page for f in figures if f.kind == "sheet" and position(doc[f.page - 1], f) == "the whole page"}
    updated = {}
    for section in sections:
        pages = range(section.first_page, section.last_page + 1)
        text = "\n".join(text_by_page[p] for p in pages).strip()
        inside = [e for e in evidence if e.locator.page in pages]
        claims = "\n".join(claim_line(e) for e in inside[:MAX_SECTION_CLAIMS]) or "(none)"
        figs = "\n".join(f"- {f.label or 'unlabelled ' + f.kind} (page {f.page}): {f.about or f.caption or '(not described)'}"
                         for f in [f for f in figures if f.page in pages][:MAX_SECTION_FIGURES]) or "(none)"
        # Sheets are shown by their figure requests; scans only by an image of the page.
        overview = [p for p in pages if p not in sheets and scanned(doc[p - 1], text_by_page[p])][:MAX_OVERVIEWS]
        images = [render(p, native_rect(doc[p - 1]), f"{stem}-overview-p{p}.png") for p in overview]
        heading = " > ".join(section.heading_path) or "(no heading)"
        head = (SITUATE_SECTION + f"\nHeading path: {heading}\nPages: {section.first_page}-{section.last_page} of {len(doc)}"
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

# --- quality checks --------------------------------------------------------------------

# A number with a unit: the kind of specific value an "about" statement should leave out.
VALUE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?\s?-?(?:[kMG]?Wh?|[kM]?Pa|bar|psi|mm|cm|km|m|m²|m2|m³|m3|kg|t|tonnes|"
                   r"L/s|l/s|L/min|gpm|°C|°F|K|%|Hz|kV|V|kVA|A|rpm|dB|ms|s|min|h|hrs?|ft|in|lbs?|k?N|k?Nm|m/s|km/h|mph)"
                   r"(?![\w/])")
STOPWORDS = frozenset("""about above after also among and are around based been being between both but can
contains containing describes describing depicts depicting details detailing document each figure figures
for from has have how includes including information into its kind kinds main more most other over
provides section sections shown shows such than that the their them there these this those through
table tables under using various what when where which while with within without""".split())
GROUNDING_MIN = 0.5
ABOUT_LENGTH = {"figure": (20, 800), "section": (40, 1200)}

def terms(text):
    """Content words, lowercased, with a plural 's' dropped."""
    words = re.findall(r"[a-z][a-z\-]{3,}", text.lower())
    return {w[:-1] if w.endswith("s") and not w.endswith("ss") else w for w in words if w not in STOPWORDS}

def grounding(about, material):
    """Share of the about's content words found in its material (None if it has none)."""
    wanted = terms(about)
    if not wanted:
        return None
    have = terms(material)
    return len(wanted & have) / len(wanted)

def values_in(about, names=""):
    """Numbers with units in an about, except those in names (e.g. 'IEA 15 MW' in a heading)."""
    squash = lambda s: re.sub(r"[\s\-]", "", s.lower())
    return [m.group() for m in VALUE.finditer(about) if squash(m.group()) not in squash(names)]

def quality(doc, figures, sections, unresolved, evidence):
    """Mechanical checks on situating results; reported, never applied."""
    by_id = {e.id: e for e in evidence}
    claim_text = lambda ids: " ".join(f"{by_id[i].entity} {by_id[i].attribute} {by_id[i].conditions}"
                                      for i in ids if i in by_id)
    flags = []

    def check(kind, target, about, material, names, expected=True):
        if not about:
            if expected:
                flags.append({"target": target, "check": "missing", "detail": f"no {kind} about"})
            return
        low, high = ABOUT_LENGTH[kind]
        if not low <= len(about) <= high:
            flags.append({"target": target, "check": "shape", "detail": f"{len(about)} characters"})
        found = values_in(about, names)
        if found:
            flags.append({"target": target, "check": "values", "detail": ", ".join(found[:5])})
        share = grounding(about, material)
        if share is not None and share < GROUNDING_MIN:
            flags.append({"target": target, "check": "grounding",
                          "detail": f"{share:.0%} of its terms appear in its material"})

    pages_text = {n: page.get_text("text") for n, page in enumerate(doc, 1)}
    for f in figures:
        page = doc[f.page - 1]
        around = [pages_text[f.page]] if position(page, f) == "the whole page" else surroundings(page, f.bbox, AROUND)
        material = " ".join([f.caption, f.title, *around, *(r.paragraph or r.text for r in f.references),
                             claim_text(f.claims)])
        check("figure", f.id, f.about + " " + f.role if f.role else f.about, material, f"{f.caption} {f.title} {f.label or ''}")
    for s in sections:
        pages = range(s.first_page, s.last_page + 1)
        inside = [e.id for e in evidence if e.locator.page in pages]
        heading = " ".join(s.heading_path)
        material = " ".join([heading, *(pages_text.get(p, "") for p in pages), claim_text(inside),
                             *(f.about for f in figures if f.page in pages)])
        check("section", s.id, s.about, material, heading, expected=bool(inside))
    labelled = [f for f in figures if f.label]
    resolved = sum(len(f.references) for f in figures)
    return {
        "references": {"resolved": resolved, "unresolved": len(unresolved),
                       "rate": round(resolved / (resolved + len(unresolved)), 3) if resolved + len(unresolved) else None},
        "figures": {"total": len(figures), "unlabelled": len(figures) - len(labelled),
                    "labelled_uncited": sum(1 for f in labelled if not f.references),
                    **{f"labelled_from_{source.replace(' ', '_')}": sum(1 for f in labelled if f.label_source == source)
                       for source in ("caption", "title block", "model")}},
        "flags": flags,
    }
