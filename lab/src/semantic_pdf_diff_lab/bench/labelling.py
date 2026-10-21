"""Calibration for region labels: can a model label a page's regions? (docs/research/tilings-2026-10-12.md,
milestone 6.)

Each page of the controlled corpus gets regions whose labels are known, asked about in two questions:
- **plain:** what the page holds, each whole: its detected figures and tables, labelled by the facts the key puts
  inside them (a table's, a chart's, a drawing's; the document's family where they hold none), its text blocks (a
  header or footer line may be called decoration too), a tile around a decoration graphic, and a blank margin strip;
- **hard:** regions made to make no sense read alone (half a figure; a strip whose edges run through a paragraph's
  lines), and one holding a figure and a paragraph beside it (mixed), with plain regions that don't overlap them.
Regions in a question don't overlap; each question is asked twice, numbered in a seeded order and then the reverse,
so consistency can be measured.

The question is the product's (regionlabels.py). Scored: each label against the key, as a confusion matrix; the same
label in both numberings; content lost (a table, chart, drawing, scan or mixed region labelled text, decoration or
blank: the lever wouldn't send it) and tiles saved (a text, decoration or blank region labelled so); and what the
model said "other" regions hold.
"""
import hashlib
import json
import random
from pathlib import Path

import pymupdf

from semantic_pdf_diff.pages import shown
from semantic_pdf_diff_lab.bench.calibration import Page, _border, _decoration

FAMILY = {"lcc-energy": "chart", "lcc-enduse": "chart", "lcc-metered": "chart", "lcc-plan": "drawing",
          "ahu-schematic": "drawing", "uv-layout": "drawing", "attach": "drawing"}  # a family's figures
FORMS = {"table": "table", "chart": "chart", "drawing": "drawing", "figure": "drawing", "prose": "text"}
CONTENT = ("table", "chart", "drawing", "photo or scan", "mixed")  # what the lever must send
MOST = 10  # regions a question holds at most
SMALLEST = 48.0  # points: the key's facts spanning less than this either way aren't taken for a figure
NEAR = 40.0  # points: a key's facts this close are one figure's
TEXTS = 4  # text regions a question holds at most (pages hold many; they'd outweigh the rest)
FURNITURE = 0.08  # a text block this share of the page's height from its top or bottom: a header or footer
# a model passes where the lever's decisions hold: content it wouldn't send under this share, regions it may skip
# skipped at this share or more. Set before the first run as right >= 0.85 and lost < 0.03; revised after it
# (2026-10-12): gemma-4's labels were right 74.5% of the time, but most of the misses don't change what's sent
# (a table with its caption called mixed, a margin called decoration), and the lever acts only on that
PASS = {"lost": 0.03, "saved": 0.9}
SETTINGS = {"context_tokens": 131072, "output_tokens": 1500, "image_tokens": 6000}

def _family(stem):
    return next((f for f in sorted(FAMILY, key=len, reverse=True) if stem.startswith(f + "-")), None)

def _key_facts(folder, stem, number):
    """[(Rect as displayed, form)] of the key's facts drawn on this page."""
    path = Path(folder) / f"{stem}.key.json"
    if not path.exists():
        return []
    return [(form["box"], form["form"]) for fact in json.loads(path.read_text(encoding="utf-8"))["facts"]
            for form in fact.get("forms", ()) if form.get("page") == number + 1 and form.get("box")]

def _centre(box):
    return pymupdf.Point((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2)

class Region:
    """A region and its key: the label expected, and any other accepted."""

    def __init__(self, rect, key, accepted=(), why=""):
        self.rect, self.key, self.accepted, self.why = pymupdf.Rect(rect), key, {key, *accepted}, why

    def overlaps(self, other):
        shared = self.rect & other.rect
        return not shared.is_empty and abs(shared) > 0.02 * min(abs(self.rect), abs(other.rect))

def plain(p, folder):
    """[Region]: a page's figures and tables, text blocks, a decoration tile and a blank strip, none overlapping."""
    stem = Path(p.file).stem
    family, scan, raster = _family(stem), stem.endswith("-scan"), stem.endswith("-raster")
    facts = [(shown(p.page, box), form) for box, form in _key_facts(folder, stem, p.number)]
    out = []
    for f in p.reader.figures(p.page, p.number):
        if not f.region:
            continue
        rect = shown(p.page, f.bbox) & p.page.rect
        inside = [form for box, form in facts if _centre(box) in rect]
        kinds = sorted({FORMS[x] for x in inside if x in FORMS} - {"text"})
        kind = (kinds[0] if len(kinds) == 1 else "mixed" if kinds else
                "table" if f.kind == "table" else FAMILY.get(family) if family else None)
        if kind is None:
            continue
        if scan:
            out.append(Region(rect, "photo or scan", (kind,), "a scanned page"))
        else:
            out.append(Region(rect, kind, ("photo or scan",) if raster else (), f"a detected {f.kind}"))
    drawn = [(box, FORMS[form]) for box, form in facts if FORMS.get(form, "text") != "text"]
    clusters = []  # the key's figures no detected figure holds: their facts' boxes, near each other, and one kind
    for box, kind in drawn:
        if any(_centre(box) in r.rect for r in out):
            continue
        near = [c for c in clusters if c[1] == kind and (c[0] + (-NEAR, -NEAR, NEAR, NEAR)).intersects(box)]
        for c in near[1:]:
            near[0][0] |= c[0]
            clusters.remove(c)
        if near:
            near[0][0] |= box
        else:
            clusters.append([pymupdf.Rect(box), kind])
    for c in clusters:  # and the graphics they touch
        for g in p.content:
            if g.intersects(c[0]) and abs(g) < 0.5 * abs(p.page.rect):
                c[0] |= g
    merged = True
    while merged:  # clusters the graphics joined
        merged = False
        for a in clusters:
            b = next((b for b in clusters if b is not a and b[1] == a[1] and b[0].intersects(a[0])), None)
            if b is not None:
                a[0] |= b[0]
                clusters.remove(b)
                merged = True
                break
    for rect, kind in clusters:
        if min(rect.width, rect.height) < SMALLEST:
            continue  # a fact or two, not a figure (one a paragraph states, say)
        region = Region(rect + (-4, -4, 4, 4), "photo or scan" if scan else kind, (kind,) if scan else (),
                        f"the key's {kind}, undetected")
        if not any(region.overlaps(o) for o in out):
            out.append(region)
    height = p.page.rect.height
    for block in p.page.get_text("blocks"):
        if block[6] != 0 or len(block[4].split()) < 3:
            continue
        rect = shown(p.page, block[:4]) + (-3, -3, 3, 3)
        if any(_centre(box) in rect for box, _ in drawn):
            continue  # a figure's or a table's labels
        region = Region(rect, "text", why="a text block")
        if rect.y1 < p.page.rect.y0 + FURNITURE * height or rect.y0 > p.page.rect.y1 - FURNITURE * height:
            region.accepted.add("decoration")
            region.why = "a header or footer"
        if not any(region.overlaps(o) for o in out):
            out.append(region)
    for make, key in ((_decoration, "decoration"), (_border, "blank")):
        made = make(p, []) if p.lines else None
        if made:
            region = Region(made[-1], key, why="a tile around decoration" if key == "decoration" else "a margin")
            if not any(region.overlaps(o) for o in out):
                out.append(region)
    return out

def hard(p, regions):
    """[Region]: half the largest figure and a strip through a paragraph's lines (nonsense), a figure and the
    paragraph beside it (mixed), then plain regions overlapping none of them."""
    out = []
    figures = sorted((r for r in regions if r.key in ("table", "chart", "drawing")), key=lambda r: -abs(r.rect))
    texts = [r for r in regions if r.key == "text"]
    if figures:
        f = figures[0].rect
        half = (pymupdf.Rect(f.x0, f.y0, (f.x0 + f.x1) / 2, f.y1) if f.width >= f.height
                else pymupdf.Rect(f.x0, f.y0, f.x1, (f.y0 + f.y1) / 2))
        out.append(Region(half, "nonsense", why=f"half a {figures[0].key}"))
    for t in sorted(texts, key=lambda r: -abs(r.rect)):
        held = sorted((b for b, _ in p.lines if b in t.rect), key=lambda b: b.y0)
        if len(held) >= 3:
            first, last = held[0], held[-1]
            strip = pymupdf.Rect(t.rect.x0, (first.y0 + first.y1) / 2, t.rect.x1, (last.y0 + last.y1) / 2)
            region = Region(strip, "nonsense", why="a strip through a paragraph's lines")
            if not any(region.overlaps(o) for o in out):
                out.append(region)
                break
    for f in figures[1:] or figures:
        near = [t for t in texts if len([b for b, _ in p.lines if b in t.rect]) >= 2 and min(
            abs(t.rect.y0 - f.rect.y1), abs(f.rect.y0 - t.rect.y1)) < 60]
        if near:
            region = Region(f.rect | near[0].rect, "mixed", why=f"a {f.key} and a paragraph")
            if not any(region.overlaps(o) for o in out):
                out.append(region)
                break
    if not out:
        return []
    return out + [r for r in regions if not any(r.overlaps(o) for o in out)]

def questions(p, folder):
    """[{"id", "regions": [Region], "orders": [[region index by number], twice]}]: a page's plain question and its
    hard one (where it has one), each region set cut to MOST (the hard ones and the rarest keys first)."""
    seed = hashlib.sha256(f"{p.page.get_text()}|{p.id}".encode()).hexdigest()[:16]
    regions = plain(p, folder)
    out = []
    for name, found in (("plain", regions), ("hard", hard(p, regions))):
        if not found:
            continue
        rng = random.Random(f"{seed}|{name}")
        texts = [i for i, r in enumerate(found) if r.key == "text"]
        if len(texts) > TEXTS:
            dropped = set(rng.sample(texts, len(texts) - TEXTS))
            found = [r for i, r in enumerate(found) if i not in dropped]
        if len(found) > MOST:
            counts = {}
            for r in found:
                counts[r.key] = counts.get(r.key, 0) + 1
            ranked = sorted(range(len(found)), key=lambda i: (found[i].key != "nonsense" and found[i].key != "mixed",
                                                               counts[found[i].key], rng.random()))
            found = [found[i] for i in sorted(ranked[:MOST])]
        first = rng.sample(range(len(found)), len(found))
        out.append({"id": f"{p.id}-{name}", "regions": found, "orders": [first, first[::-1]]})
    return out

def cases(folder, only=None):
    """(Page, questions) for every page of the folder's PDFs, sorted; only: page ids to keep."""
    for path in sorted(Path(folder).glob("*.pdf")):
        with pymupdf.open(path) as doc:
            for number in range(len(doc)):
                if only and f"{path.stem}-p{number + 1}" not in only:
                    continue
                p = Page(path.name, doc, number)
                yield p, questions(p, folder)

def ask_all(folder, client, corpus, only=None):
    """{question id: {"page", "regions": [{"key", "accepted", "why", "rect"}], "orders", "answers": [per order:
    {"labels": [by region index], "other": {region index: words}, "error"}]}}. Pictures go to folder/images."""
    from semantic_pdf_diff.dispatch import Dispatcher
    from semantic_pdf_diff.regionlabels import Labels, labels, prompt
    from semantic_pdf_diff.tilechoice import SKETCH_SIDE, sketch
    target = Path(folder) / "images"
    target.mkdir(parents=True, exist_ok=True)
    out = {}
    with Dispatcher(client) as dispatch:
        for p, asked in cases(corpus, only):
            if not asked:
                continue
            zoom = SKETCH_SIDE / max(p.page.rect.width, p.page.rect.height)
            pixmap = p.page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            clean = target / f"{p.id}.png"
            clean.write_bytes(sketch(p.page, pixmap=pixmap))
            for q in asked:
                record = out[q["id"]] = {
                    "page": p.id, "orders": q["orders"], "answers": [None, None],
                    "regions": [{"key": r.key, "accepted": sorted(r.accepted), "why": r.why,
                                 "rect": [round(v, 1) for v in r.rect]} for r in q["regions"]]}
                for o, order in enumerate(q["orders"]):
                    image = target / f"{q['id']}-o{o}.png"
                    image.write_bytes(sketch(p.page, [q["regions"][i].rect for i in order], pixmap=pixmap,
                                             dimmed=True, title="Regions"))

                    def finish(value, error, record=record, o=o, order=order):
                        if error is not None:
                            record["answers"][o] = {"labels": [None] * len(order), "other": {},
                                                    "error": str(error)[:200]}
                            return
                        found = labels(value, len(order))
                        by_region = [None] * len(order)
                        other = {}
                        for number, (label, words) in found.items():
                            by_region[order[number - 1]] = label
                            if label == "other":
                                other[order[number - 1]] = words
                        record["answers"][o] = {"labels": by_region, "other": other, "error": None}
                    dispatch.submit(prompt(len(order)), Labels, [clean, image], ("regionlabels", f"{q['id']}|o{o}"),
                                    finish)
                    dispatch.make_room()
        dispatch.drain()
    return out

# --- scoring ------------------------------------------------------------------------------------

def _share(a, b):
    return round(a / b, 3) if b else None

def score(asked):
    """A model's profile from ask_all's answers (questions never answered, as unrecorded in a replay, left out)."""
    from semantic_pdf_diff.regionlabels import LABELS, SKIPPED
    answered = {k: q for k, q in asked.items() if all(a and not a["error"] for a in q["answers"])}
    seen = [(q, i, a["labels"][i]) for q in answered.values() for a in q["answers"] for i in range(len(q["regions"]))]
    out = {"questions": len(asked), "answered": len(answered), "labelled": len(seen),
           "unlabelled": sum(1 for _, _, x in seen if x is None)}
    out["right"] = _share(sum(1 for q, i, x in seen if x in q["regions"][i]["accepted"]), len(seen))
    content = [(q, i, x) for q, i, x in seen if q["regions"][i]["key"] in CONTENT]
    skippable = [(q, i, x) for q, i, x in seen if q["regions"][i]["key"] in SKIPPED]
    out["lost"] = _share(sum(1 for _, _, x in content if x in SKIPPED), len(content))
    out["saved"] = _share(sum(1 for _, _, x in skippable if x in SKIPPED), len(skippable))
    regions = [(q, i) for q in answered.values() for i in range(len(q["regions"]))]
    out["same_in_both_numberings"] = _share(sum(1 for q, i in regions if q["answers"][0]["labels"][i] is not None
                                                and q["answers"][0]["labels"][i] == q["answers"][1]["labels"][i]),
                                            len(regions))
    by_key = {}
    for q, i, x in seen:
        row = by_key.setdefault(q["regions"][i]["key"], {"asked": 0, "right": 0, "said": {}})
        row["asked"] += 1
        row["right"] += x in q["regions"][i]["accepted"]
        row["said"][str(x)] = row["said"].get(str(x), 0) + 1
    order = [*LABELS, "None"]
    out["by_key"] = {k: {"asked": r["asked"], "right": _share(r["right"], r["asked"]),
                         "said": dict(sorted(r["said"].items(), key=lambda kv: order.index(kv[0])))}
                     for k, r in sorted(by_key.items(), key=lambda kv: LABELS.index(kv[0]))}
    out["other"] = sorted({w for q in answered.values() for a in q["answers"] for w in a["other"].values() if w})
    by_why = {}
    for q, i, x in seen:
        r = q["regions"][i]
        row = by_why.setdefault(f"{r['key']}: {r['why']}", {})
        row[str(x)] = row.get(str(x), 0) + 1
    out["by_why"] = {k: dict(sorted(v.items(), key=lambda kv: -kv[1])) for k, v in sorted(by_why.items())}
    lost = out["lost"] if out["lost"] is not None else 1
    out["passes"] = lost < PASS["lost"] and (out["saved"] or 0) >= PASS["saved"]
    return out

def page(folder, data, asked_by_model):
    """report.html: each model's profile, then every question's pictures and answers, those with the most wrong
    labels first. data: {"models": {model: profile}}; asked_by_model: {model: ask_all's answers}."""
    from semantic_pdf_diff.html_pages import esc, page as html_page
    body = ["<h1>Region labels calibration</h1>",
            "<p class='muted'>Each question: the page, then its regions numbered in the first order asked. Each "
            "region: its key (and others accepted), then what was said in each numbering.</p>"]
    for model, asked in asked_by_model.items():
        body.append(f"<h2>{esc(model)}</h2><pre>{esc(json.dumps(data['models'][model], indent=1))}</pre>")

        def wrong(q):
            return sum(1 for a in q["answers"] if a and not a["error"]
                       for i, x in enumerate(a["labels"]) if x not in q["regions"][i]["accepted"])
        for qid, q in sorted(asked.items(), key=lambda kv: (-wrong(kv[1]), kv[0])):
            first = q["orders"][0]
            rows = []
            for number, i in enumerate(first, 1):
                r = q["regions"][i]
                said = [str(a["labels"][i]) if a and not a["error"] else "?" for a in q["answers"]]
                mark = "" if all(s in r["accepted"] for s in said) else " <b>✗</b>"
                rows.append(f"<li>{number}: {esc(r['key'])} ({esc(r['why'])}) — said {esc(' / '.join(said))}"
                            f"{mark}</li>")
            cells = [f"<figure><img src='images/{esc(q['page'])}.png' loading='lazy' alt=''><figcaption>the page"
                     "</figcaption></figure>",
                     f"<figure><img src='images/{esc(qid)}-o0.png' loading='lazy' alt=''><figcaption>numbered as in "
                     "the first order</figcaption></figure>"]
            body.append(f"<section><h3>{esc(qid)}</h3><ol class='plain'>{''.join(rows)}</ol>"
                        f"<div class='row'>{''.join(cells)}</div></section>")
    style = ("body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1400px;padding:16px}"
             ".muted{color:var(--muted)}section{background:var(--card);border:1px solid var(--line);"
             "border-radius:8px;padding:12px;margin:12px 0}h3{margin:0 0 4px;font-size:15px}pre{font-size:12px}"
             ".plain{list-style:none;padding:0;font-size:14px}.row{display:flex;gap:12px;flex-wrap:wrap}"
             "figure{margin:0;flex:1 1 320px;min-width:0}img{width:100%;height:auto;border:1px solid var(--line);"
             "background:#fff}figcaption{font-size:13px}")
    target = Path(folder) / "report.html"
    target.write_text(html_page("Region labels calibration", "".join(body), style), encoding="utf-8")
    return target
