import hashlib
import json
import math
import re
from pathlib import Path
import pymupdf
from .models import Evidence, Extraction
from .llm import ModelFailure

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

def union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

def extract_pdf(path, label, output, client):
    s = client.s
    evidence, coverage = [], []
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    assets = output / "assets"
    assets.mkdir(exist_ok=True, parents=True)
    seen = set()

    def consume(page_no, bbox, source, family, text, image=None, check=None, locate=None):
        """Run one extraction task, record it in the ledger and return its status.

        check(quote) -> bool | None. Native tasks reject claims failing it; visual tasks
        only record the result. locate(quote) narrows a claim's bbox within the task.
        Exact duplicate claims within one family (native or visual) on a page are kept once.
        """
        row = {"document": label, "page": page_no, "bbox": list(bbox), "source": source,
               "image": image, "status": "complete", "issues": [], "claims": 0}
        images = [output / image] if image else []
        prompt = EXTRACT + "\nSource type: " + source.split(":")[0] + "\nSOURCE DATA:\n" + text
        try:
            result = client.ask(prompt, Extraction, images)
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
                eid = label + "-" + hashlib.sha256((digest + repr(key) + repr(where)).encode()).hexdigest()[:16]
                evidence.append(Evidence(**claim.model_dump(), id=eid, document=label, page=page_no,
                                         bbox=where, source=source, image=image, quote_verified=verified))
                row["claims"] += 1
        except ModelFailure as e:
            row.update(status="failed", issues=[str(e)])
        coverage.append(row)
        return row["status"]

    def text_task(page_no, segments, source, depth=0):
        """segments: [(bbox, text)] of consecutive blocks sent together."""
        text = "\n\n".join(t for _, t in segments)
        def locate(quote):
            return next((b for b, t in segments if quoted(quote, t)), union(b for b, _ in segments))
        status = consume(page_no, union(b for b, _ in segments), source, "native", text,
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
            text_task(page_no, part, f"{source}:r{i}", depth + 1)

    def table_task(page_no, bbox, source, header, row, columns, depth=0):
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
            coverage.append({"document": label, "page": page_no, "bbox": list(bbox), "source": source, "image": None,
                             "status": "partial", "issues": ["Table row exceeds text budget; inspect visual tiles"], "claims": 0})
            return
        if fits:
            status = consume(page_no, bbox, source, "native", text,
                             check=lambda q: quoted(q, text) or covered(q, flat))
            if status == "complete" or depth >= s.refinement_depth or not splittable:
                return
        rest = columns[1:]
        middle = (len(rest) + 1) // 2
        for i, part in enumerate([rest[:middle], rest[middle:]]):
            # Budget-driven splits are mandatory; only quality-driven ones use depth.
            table_task(page_no, bbox, f"{source}:c{i}", header, row, [columns[0], *part], depth + (1 if fits else 0))

    def visual_task(page_no, page, tag, rect, depth=0):
        name = f"{label}-p{page_no}-{tag.replace(':', '-')}.png"
        render(page, rect, assets / name, s.image_side)
        native = rect * page.derotation_matrix
        layer = page.get_text("text", clip=native)
        check = (lambda q: covered(q, layer, fold=True)) if layer.strip() else None
        status = consume(page_no, native, tag, "visual", "", "assets/" + name, check=check)
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
            raise ValueError(f"{label}: encrypted PDF needs to be decrypted before comparison")
        if not doc.is_pdf or not len(doc):
            raise ValueError(f"{label}: expected a nonempty PDF")
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
                    text_task(number, [(b, t) for _, b, t in group], f"text:{ids}")
                    group, size = [], 0
                if piece:
                    group.append(piece)
                    size += extra
            try:
                found = [(table.bbox, table.extract()) for table in page.find_tables().tables]
            except Exception as e:  # PyMuPDF table detection raises assorted internal errors
                found = []
                coverage.append({"document": label, "page": number, "bbox": list(page.rect * page.derotation_matrix),
                                 "source": "table-detection", "image": None, "status": "failed",
                                 "issues": [type(e).__name__ + ": " + str(e)], "claims": 0})
            for ti, (bbox, rows) in enumerate(found):
                if not rows:
                    continue
                header = rows[0]
                width = max(len(r) for r in rows)
                for ri, row in enumerate(rows[1:] or rows):
                    table_task(number, tuple(bbox), f"table:{ti}:{ri}", header, row, list(range(width)))
            if s.vision:
                for tag, rect in visual_regions(page, s.tile_points):
                    visual_task(number, page, tag, rect)
            else:
                coverage.append({"document": label, "page": number, "bbox": list(page.rect * page.derotation_matrix),
                                 "source": "vision", "image": None, "status": "skipped",
                                 "issues": ["Visual extraction disabled; charts, diagrams and scans may be missed"], "claims": 0})
    return evidence, coverage, digest
