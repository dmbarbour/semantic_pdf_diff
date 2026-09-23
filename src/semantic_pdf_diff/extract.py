import hashlib
import json
from pathlib import Path
import fitz
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

def tiles(rect, side, overlap=0.18):
    def starts(lo, hi):
        if hi - lo <= side:
            return [lo]
        result, x = [lo], lo
        while x + side < hi:
            x = min(x + side * (1 - overlap), hi - side)
            if x == result[-1]:
                break
            result.append(x)
        return result
    for y in starts(rect.y0, rect.y1):
        for x in starts(rect.x0, rect.x1):
            yield fitz.Rect(x, y, min(x + side, rect.x1), min(y + side, rect.y1))

def render(page, rect, target, max_side):
    # clip is in rotated page coordinates, as used by Page.get_pixmap.
    scale = min(2.5, max_side / max(rect.width, rect.height))
    page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=rect, alpha=False).save(target)

def extract_pdf(path, label, output, client):
    s = client.s
    evidence, coverage = [], []
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    assets = output / "assets"
    assets.mkdir(exist_ok=True, parents=True)
    seen = set()

    def consume(page_no, bbox, source, text, image=None, depth=0):
        row = {"document": label, "page": page_no, "bbox": list(bbox), "source": source,
               "image": image, "status": "complete", "issues": [], "claims": 0}
        images = [output / image] if image else []
        prompt = EXTRACT + "\nSource type: " + source + "\nSOURCE DATA:\n" + text
        try:
            result = client.ask(prompt, Extraction, images)
            row["status"] = "complete" if result.complete else "partial"
            row["issues"] = result.issues
            for claim in result.claims:
                # Native prose/table evidence must quote actual source text. Image labels
                # cannot be deterministically checked and remain reviewable in the report.
                if not image and " ".join(claim.quote.split()) not in " ".join(text.split()):
                    row["status"] = "partial"
                    row["issues"].append("Rejected claim with unsupported literal quote")
                    continue
                key = (page_no, source.split(":")[0], claim.entity.casefold(), claim.attribute.casefold(),
                       claim.value, claim.unit, claim.conditions, claim.quote)
                if key in seen:
                    continue
                seen.add(key)
                eid = label + "-" + hashlib.sha256((digest + repr(key) + repr(tuple(bbox))).encode()).hexdigest()[:16]
                evidence.append(Evidence(**claim.model_dump(), id=eid, document=label, page=page_no,
                                         bbox=tuple(bbox), source=source, image=image))
                row["claims"] += 1
        except ModelFailure as e:
            row.update(status="failed", issues=[str(e)])
        coverage.append(row)
        if not image and row['status'] != 'complete' and depth < s.refinement_depth and len(text.encode()) > 400:
            for i, part in enumerate(split_utf8(text, max(200, len(text.encode()) // 2))):
                consume(page_no, bbox, source + f":refine{i}", part, depth=depth+1)
        return row['status']

    with fitz.open(path) as doc:
        if doc.needs_pass:
            raise ValueError(f"{label}: encrypted PDF needs to be decrypted before comparison")
        if not doc.is_pdf or not len(doc):
            raise ValueError(f"{label}: expected a nonempty PDF")
        for number, page in enumerate(doc, 1):
            # Native coordinates stay unrotated (PDF point coordinates).
            for bi, block in enumerate(page.get_text("blocks", sort=True)):
                if block[6] != 0:
                    continue
                for ci, chunk in enumerate(split_utf8(block[4], s.text_bytes)):
                    if chunk.strip():
                        consume(number, block[:4], f"text:{bi}:{ci}", chunk)
            try:
                tables = page.find_tables().tables
                for ti, table in enumerate(tables):
                    rows = table.extract()
                    if not rows:
                        continue
                    header = json.dumps(rows[0], ensure_ascii=False)
                    for ri, row in enumerate(rows[1:] or rows):
                        text = "Header: " + header + "\nRow: " + json.dumps(row, ensure_ascii=False)
                        if len(text.encode()) <= s.text_bytes:
                            consume(number, table.bbox, f"table:{ti}:{ri}", text)
                        else:
                            coverage.append({"document":label,"page":number,"source":f"table:{ti}:{ri}",
                                "status":"partial","issues":["Table row exceeds text budget; inspect visual tiles"],"claims":0})
            except Exception as e:
                coverage.append({"document":label,"page":number,"source":"table-detection", "status":"failed",
                                 "issues":[type(e).__name__ + ": " + str(e)],"claims":0})
            if s.vision:
                regions = [("overview", page.rect)]
                if max(page.rect.width, page.rect.height) > s.tile_points:
                    regions += [(f"tile:{i}", r) for i, r in enumerate(tiles(page.rect, s.tile_points))]
                for kind, rect in regions:
                    filename = f"{label}-p{number}-{kind.replace(':','-')}.png"
                    render(page, rect, assets / filename, s.image_side)
                    native_rect = rect * page.derotation_matrix
                    status = consume(number, native_rect, kind, "", "assets/" + filename)
                    # Refine only local tiles; an overview may be incomplete because it
                    # spans many facts. All overview areas already have tile coverage.
                    if status != "complete" and kind.startswith("tile:"):
                        def refine(parent, depth, prefix):
                            if depth > s.refinement_depth or min(parent.width,parent.height) < 100:
                                return
                            if parent.width > parent.height:
                                mid = (parent.x0+parent.x1)/2
                                children = [fitz.Rect(parent.x0,parent.y0,mid+12,parent.y1), fitz.Rect(mid-12,parent.y0,parent.x1,parent.y1)]
                            else:
                                mid = (parent.y0+parent.y1)/2
                                children = [fitz.Rect(parent.x0,parent.y0,parent.x1,mid+12), fitz.Rect(parent.x0,mid-12,parent.x1,parent.y1)]
                            for ci, child in enumerate(children):
                                tag = prefix + f"-r{ci}"
                                name = f"{label}-p{number}-{tag}.png"
                                render(page,child,assets/name,s.image_side)
                                state = consume(number, child*page.derotation_matrix, tag, "", "assets/"+name)
                                if state != "complete":
                                    refine(child,depth+1,tag)
                        refine(rect,1,kind.replace(':','-'))
            else:
                coverage.append({"document":label,"page":number,"source":"vision", "status":"skipped",
                    "issues":["Visual extraction disabled; charts, diagrams and scans may be missed"],"claims":0})
    return evidence, coverage, digest
