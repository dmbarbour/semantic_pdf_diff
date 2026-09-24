import hashlib
import json
import math
import re
from pathlib import Path
import pymupdf
from .models import DerivationStep, Evidence, Extraction, PdfLocator, Section
from .llm import ModelFailure

# Bump when prompt assembly or task construction changes, not only the template text;
# it is part of the extraction interpreter. 2: section heading path in prompts.
PROMPT_VERSION = 2

EXTRACT = '''Extract atomic engineering claims from this one source. Return JSON:
{"claims":[{"entity":"component/system", "attribute":"property or directed relationship",
"value":"literal value or target", "unit":"literal unit or empty", "conditions":"load, scenario, time, tolerances, scope",
"kind":"text|table|chart|diagram", "quote":"short exact supporting text or visible labels",
"confidence":0.0, "approximate":false}], "complete":true, "issues":[]}
Maximum 6 claims. Set complete=false if content is clipped, ambiguous, unreadable, or more claims remain.
For tables associate row labels, column headers and units. For charts preserve series, axes, units,
operating point and trend; estimated plotted readings MUST be approximate. For diagrams extract
labeled components and directed connections; never invent direction on unmarked edges.
Preserve negation, requirements versus proposed capabilities, ranges and inequality signs.
Extract evidence only, not commentary. Use a short canonical entity and attribute; keep numeric value separate from unit.
'''

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

def visual_regions(page, side):
    """Tiles first so higher-resolution crops win de-duplication; overview last."""
    regions = []
    if max(page.rect.width, page.rect.height) > side:
        regions = [(f"tile:{i}", r) for i, r in enumerate(tiles(page.rect, side))]
    return regions + [("overview", page.rect)]

def render(page, rect, target, max_side):
    # clip is in rotated page coordinates, as used by Page.get_pixmap.
    scale = min(2.5, max_side / max(rect.width, rect.height))
    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False).save(target)

def same_form(row, header):
    """True if a row matches most non-empty cells of a header, position by position."""
    pairs = [(a, b) for a, b in zip(row, header) if a not in (None, "") or b not in (None, "")]
    return bool(pairs) and sum(a == b for a, b in pairs) / len(pairs) >= 0.5

def union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

def pdf_sections(doc, depth, pages_per_section):
    """Sections from the outline down to `depth`, else fixed page ranges.

    Returns (sections, section of each page). Assignment is per page: a page belongs to
    the last outline entry starting on or before it, so an entry sharing its start page
    with a later one gets no pages of its own.
    """
    count = len(doc)
    path, starts = [], {}
    for level, title, page in doc.get_toc(simple=True):
        if level > depth:
            continue
        path = path[:level - 1] + [" ".join(str(title).split())]
        if 1 <= page <= count:
            starts[page] = list(path)
    sections, owner = [], {}
    if starts:
        current = None
        for number in range(1, count + 1):
            heading = starts.get(number, current["heading_path"] if current else [])
            if current is None or heading is not current["heading_path"]:
                current = {"first_page": number, "heading_path": heading}
                sections.append(current)
            current["last_page"] = number
        sections = [Section(id=f"sec{i}", origin="outline", **fields) for i, fields in enumerate(sections, 1)]
    else:
        sections = [Section(id=f"sec{i}", origin="pages", first_page=first, last_page=min(count, first + pages_per_section - 1))
                    for i, first in enumerate(range(1, count + 1, pages_per_section), 1)]
    for section in sections:
        for number in range(section.first_page, section.last_page + 1):
            owner[number] = section
    return sections, owner

# How each extraction pass gets from PDF bytes to a claim.
DERIVATION = {
    "text": [DerivationStep(step="pdf-text-layer", detail="grouped text blocks"), DerivationStep(step="model-extraction")],
    "table": [DerivationStep(step="pdf-table-detection", detail="row with provisional header"), DerivationStep(step="model-extraction")],
    "tile": [DerivationStep(step="pdf-render", detail="page tile"), DerivationStep(step="model-extraction", detail="vision")],
    "overview": [DerivationStep(step="pdf-render", detail="whole page"), DerivationStep(step="model-extraction", detail="vision")],
}

def extract_pdf(path, content, output, client, on_task=None, on_sections=None):
    """Extract evidence from one PDF, identified by its content ID; returns (evidence, coverage).

    on_task(row, evidence) is called as each task finishes, so a store can persist
    results task by task; on_sections(sections) is called once sections are known.
    """
    s = client.s
    evidence, coverage = [], []
    stem = content.split(":", 1)[1][:12]
    assets = output / "assets"
    assets.mkdir(exist_ok=True, parents=True)
    seen = set()
    page_section = {}

    def record(row, items=()):
        coverage.append(row)
        if on_task:
            on_task(row, list(items))

    def consume(page_no, bbox, task, family, text, image=None, check=None, locate=None, crop=None, derivation=None):
        """Run one extraction task, record it in the ledger and return its status.

        check(quote) -> bool | None. Native tasks reject claims failing it; visual tasks
        only record the result. locate(quote) narrows a claim's bbox within the task.
        Exact duplicate claims within one family (native or visual) on a page are kept once.
        """
        region = task.split(":")[0]
        found = []
        row = {"content": content, "page": page_no, "bbox": list(bbox), "task": task,
               "image": image, "status": "complete", "issues": [], "claims": 0}
        images = [output / image] if image else []
        section = page_section[page_no]
        heading = " > ".join(section.heading_path)
        prompt = (EXTRACT + "\nSource type: " + region + (f"\nSection: {heading}" if heading else "")
                  + "\nSOURCE DATA:\n" + text)
        try:
            key = ("extract", region, content, task, hashlib.sha256(text.encode()).hexdigest(), crop, heading)
            result = client.ask(prompt, Extraction, images, key=key)
            row["status"] = "complete" if result.complete else "partial"
            row["issues"] = list(result.issues)
            for claim in result.claims:
                verified = check(claim.quote) if check else None
                if not image and not verified:
                    row["status"] = "partial"
                    row["issues"].append("Rejected claim with unsupported literal quote")
                    continue
                key = (page_no, family, claim.entity.casefold(), claim.attribute.casefold(),
                       normalize(claim.value), claim.unit.strip(), normalize(claim.conditions), normalize(claim.quote))
                if key in seen:
                    continue
                seen.add(key)
                where = tuple(locate(claim.quote) if locate else bbox)
                eid = "ev-" + hashlib.sha256((content + repr(key) + repr(where)).encode()).hexdigest()[:16]
                found.append(Evidence(**claim.model_dump(), id=eid, content=content, section=section.id,
                                      locator=PdfLocator(page=page_no, bbox=where, region=region, task=task),
                                      derivation=derivation or DERIVATION[region], image=image, quote_verified=verified))
                row["claims"] += 1
        except ModelFailure as e:
            row.update(status="failed", issues=[str(e)])
        evidence.extend(found)
        record(row, found)
        return row["status"]

    def text_task(page_no, segments, task, depth=0):
        """segments: [(bbox, text)] of consecutive blocks sent together."""
        text = "\n\n".join(t for _, t in segments)
        def locate(quote):
            return next((b for b, t in segments if quoted(quote, t)), union(b for b, _ in segments))
        status = consume(page_no, union(b for b, _ in segments), task, "native", text,
                         check=lambda q: quoted(q, text), locate=locate)
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

    def table_task(page_no, bbox, task, header, row, columns, depth=0, derivation=None):
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
            status = consume(page_no, bbox, task, "native", text, derivation=derivation,
                             check=lambda q: quoted(q, text) or covered(q, flat))
            if status == "complete" or depth >= s.refinement_depth or not splittable:
                return
        rest = columns[1:]
        middle = (len(rest) + 1) // 2
        for i, part in enumerate([rest[:middle], rest[middle:]]):
            # Budget-driven splits are mandatory; only quality-driven ones use depth.
            table_task(page_no, bbox, f"{task}:c{i}", header, row, [columns[0], *part], depth + (1 if fits else 0),
                       derivation)

    def visual_task(page_no, page, tag, rect, depth=0):
        name = f"{stem}-{tag.replace(':', '-')}.png"
        render(page, rect, assets / name, s.image_side)
        native = rect * page.derotation_matrix
        layer = page.get_text("text", clip=native)
        check = (lambda q: covered(q, layer, fold=True)) if layer.strip() else None
        status = consume(page_no, native, tag, "visual", "", "assets/" + name, check=check,
                         crop=(tuple(round(v, 3) for v in rect), s.image_side))
        # Refine only local tiles; an overview may be incomplete because it spans
        # many facts, and all overview areas already have tile coverage.
        if (status == "complete" or tag == "overview" or depth >= s.refinement_depth
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

    with pymupdf.open(path) as doc:
        if doc.needs_pass:
            raise ValueError(f"{Path(path).name}: encrypted PDF needs to be decrypted before comparison")
        if not doc.is_pdf or not len(doc):
            raise ValueError(f"{Path(path).name}: expected a nonempty PDF")
        sections, owner = pdf_sections(doc, s.section_depth, s.section_pages)
        page_section.update(owner)
        if on_sections:
            on_sections(sections)
        # (header, width) of a table that ended near the bottom of the previous page
        carried = None
        for number, page in enumerate(doc, 1):
            # Native coordinates stay unrotated (PDF point coordinates). Consecutive
            # blocks are grouped up to the byte budget; oversized blocks are split.
            pieces = []
            for bi, block in enumerate(page.get_text("blocks", sort=True)):
                if block[6] != 0:
                    continue
                for ci, chunk in enumerate(split_utf8(block[4].strip(), s.text_bytes)):
                    if chunk.strip():
                        pieces.append((f"{bi}.{ci}", tuple(block[:4]), chunk))
            group, size = [], 0
            for piece in pieces + [None]:
                extra = len(piece[2].encode()) + 2 if piece else 0
                if group and (piece is None or size + extra > s.text_bytes):
                    ids = group[0][0] + (f"-{group[-1][0]}" if len(group) > 1 else "")
                    text_task(number, [(b, t) for _, b, t in group], f"text:p{number}:{ids}")
                    group, size = [], 0
                if piece:
                    group.append(piece)
                    size += extra
            try:
                found = [(table.bbox, table.extract()) for table in page.find_tables().tables]
            except Exception as e:  # PyMuPDF table detection raises assorted internal errors
                found = []
                record({"content": content, "page": number, "bbox": list(page.rect * page.derotation_matrix),
                        "task": f"table-detection:p{number}", "image": None, "status": "failed",
                        "issues": [type(e).__name__ + ": " + str(e)], "claims": 0})
            height = page.rect.height
            continuing, carried = carried, None
            for ti, (bbox, rows) in enumerate(found):
                if not rows:
                    continue
                header, body, derivation = rows[0], rows[1:] or rows, None
                width = max(len(r) for r in rows)
                # A table at the top of a page, as wide as one that ended at the bottom of the
                # previous page, continues it, unless its first row is a header of the same
                # form (a new table, e.g. the next day's schedule). An identical first row is
                # a repeated header and is skipped.
                if (ti == 0 and continuing and continuing[1] == width and bbox[1] < 0.2 * height
                        and (rows[0] == continuing[0] or not same_form(rows[0], continuing[0]))):
                    if rows[0] != continuing[0]:
                        body = rows
                    header = continuing[0]
                    derivation = [DerivationStep(step="pdf-table-detection",
                                                 detail=f"row with header continued from page {number - 1}"),
                                  DerivationStep(step="model-extraction")]
                for ri, row in enumerate(body):
                    # Rows with no content (common where drawing geometry is detected as a
                    # table) cost a model call and can't yield a claim.
                    if all(c is None or not str(c).strip() for c in row):
                        continue
                    table_task(number, tuple(bbox), f"table:p{number}:{ti}:{ri}", header, row, list(range(width)),
                               derivation=derivation)
                if bbox[3] > 0.8 * height:
                    carried = (header, width)
                else:
                    carried = None
            if s.vision:
                for tag, rect in visual_regions(page, s.tile_points):
                    # Task tags are unique within content: "<region>:p<page>[:<index>]".
                    region, _, index = tag.partition(":")
                    tag = f"{region}:p{number}" + (f":{index}" if index else "")
                    visual_task(number, page, tag, rect)
            else:
                record({"content": content, "page": number, "bbox": list(page.rect * page.derotation_matrix),
                        "task": f"vision:p{number}", "image": None, "status": "skipped",
                        "issues": ["Visual extraction disabled; charts, diagrams and scans may be missed"], "claims": 0})
    return evidence, coverage
