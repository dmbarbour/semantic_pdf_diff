"""Situating: figures, what cites them, and what they (and sections) are about.

This module's first part is mechanical: given the figures found (figures.py), it finds the prose that cites them
by label and the claims inside them. The model requests that write "about" statements build on it.
"""
import re
from .figures import LIST_ENTRY, MENTION, _area, _overlap, find_figures, label_key, label_of, model_label, targets
from .schema import Reference
from .pages import native_page, shown
from .regions import crop_name, crop_stem

PARAGRAPH = 1500     # characters of a citing paragraph kept

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
        inside = []
        for e in evidence:
            for o in e.occurrences or [e]:
                where = o.locator
                # A visual claim's locator is its whole tile or overview: attach it when tile
                # and figure mostly overlap either way; overviews only for figures covering a
                # quarter of the page, or every claim on a page would join every figure.
                if where.page == figure.page and where.region in ("tile", "overview", "figure") and figure.region:
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
    """(text before, text after) a figure on its page, outside it, in reading order as displayed:
    on a rotated sheet, "before" is above the figure as a reader sees it, not above it in the
    page's stored coordinates (the meta-audit, 2026-09-28; upright pages are unchanged)."""
    from .pages import reading_blocks
    before, after = [], []
    figure = shown(page, bbox)
    middle = (figure.y0 + figure.y1) / 2
    for block in reading_blocks(page):
        text = " ".join(block[4].split()) if block[6] == 0 else ""
        box = tuple(block[:4])
        if not text or _overlap(box, bbox) > 0.5 * _area(box):
            continue
        at = shown(page, box)
        (before if (at.y0 + at.y1) / 2 < middle else after).append(text)
    return " ".join(before)[-limit:], " ".join(after)[:limit]

def position(page, figure):
    if figure.kind == "sheet" and _area(figure.bbox) >= 0.9 * _area(tuple(page.rect)):
        return "the whole page"
    box = shown(page, figure.bbox)  # as the page is displayed
    top, bottom = page.rect.y0, page.rect.y1
    third = ((box.y0 + box.y1) / 2 - top) / max(bottom - top, 1)
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

def in_section(evidence, section, index):
    """Claims in a section: by the section recorded with them, or by position for claims
    recorded without one."""
    return [e for e in evidence if (e.section or index.box(e.locator.page, e.locator.bbox).id) == section.id]

def figure_material(doc, figure, index, by_id, text_by_page):
    """Everything a figure request is given besides the image, as {part: text}."""
    page = doc[figure.page - 1]
    heading = lambda p, box=(0, 0, 0, 0): " > ".join(index.box(p, box).heading_path) if index.sections else ""
    where = heading(figure.page, figure.bbox)
    part = {"location": f"page {figure.page} of {len(doc)}, {position(page, figure)}" + (f"; section: {where}" if where else "")}
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
        f"- (page {r.page}" + (f", section: {heading(r.page, r.bbox)}" if heading(r.page, r.bbox) else "")
        + f") {r.paragraph or r.text}"
        for r in figure.references[:MAX_CITATIONS])
    part["claims extracted from it"] = "\n".join(claim_line(by_id[i]) for i in figure.claims[:MAX_FIGURE_CLAIMS] if i in by_id)
    return part

def instructions(kind):
    """A situating prompt's instructions, for a figure or a section (the rest is its material)."""
    return {"figure": SITUATE_FIGURE, "section": SITUATE_SECTION}[kind]

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
    from .schema import FigureAbout, SectionAbout
    figures, unresolved = figure_map(doc, evidence)
    by_id = {e.id: e for e in evidence}
    stem = crop_stem(content)
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    side = image_side or client.s.image_side
    text_by_page = {n: page.get_text("text") for n, page in enumerate(doc, 1)}
    issues = []

    def render(page_no, rect, name):
        page = doc[page_no - 1]
        rect = shown(page, rect)  # figure boxes are unrotated; rendering isn't
        whole = abs(rect & page.rect) >= 0.99 * abs(page.rect)
        scale = min(2.5, side / max(rect.width, rect.height, 1))
        page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=None if whole else rect, alpha=False).save(assets / name)
        return output / "assets" / name

    def key(kind, ident, *parts):
        return ("triage", kind, content, ident, hashlib.sha256("\x00".join(parts).encode()).hexdigest())

    from .sections import SectionIndex, section_text
    index = SectionIndex(sections, doc)

    def ask_figure(figure):
        images = [render(figure.page, figure.bbox, crop_name(stem, figure.id))] if figure.region else []
        part = figure_material(doc, figure, index, by_id, text_by_page)
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
        text = section_text(doc, section).strip()
        inside = in_section(evidence, section, index)
        claims = "\n".join(claim_line(e) for e in inside[:MAX_SECTION_CLAIMS]) or "(none)"
        mine = [f for f in figures if index.box(f.page, f.bbox).id == section.id][:MAX_SECTION_FIGURES]
        figs = "\n".join(f"- {f.label or 'unlabelled ' + f.kind} (page {f.page}): {f.about or f.caption or '(not described)'}"
                         for f in mine) or "(none)"
        # Sheets are shown by their figure requests; scans only by an image of the page.
        overview = [p for p in pages if p not in sheets and scanned(doc[p - 1], text_by_page[p])][:MAX_OVERVIEWS]
        images = [render(p, native_page(doc[p - 1]), crop_name(stem, f"overview-p{p}")) for p in overview]
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
    from .sections import SectionIndex, section_text
    index = SectionIndex(sections, doc)
    for s in sections:
        inside = [e.id for e in in_section(evidence, s, index)]
        heading = " ".join(s.heading_path)
        material = " ".join([heading, section_text(doc, s), claim_text(inside),
                             *(f.about for f in figures if index.box(f.page, f.bbox).id == s.id)])
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
