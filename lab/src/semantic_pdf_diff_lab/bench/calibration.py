"""Calibration: can a model judge tilings? (docs/plans/tile-selection-2026-10-10.md, milestone 4.)

The owner, 2026-10-10: "a calibration step that tests if a model is any good at this sort of question, tuned with
known-bad cuts and pseudo-random candidate ordering."

Each page of the controlled corpus gets a known-good tiling: XY-cut blocks over its text and its graphics other than
decoration, every block kept, accepted only where the measures find no line or word cut, every line and figure held
whole, no graphic missed and no tile of decoration or blank space alone. Known-bad tilings are made from it, each kept
only where the measures find its fault (KINDS). A question offers the good tiling and two bad ones of different kinds
(or one, where a page has only one), in a pseudo-random order seeded by the page's text and the question, and is asked
twice: the second time each candidate moves one place on, so position bias and consistency can be measured.

The question is the product's (tilechoice.py). Scored: the good tiling chosen, by the kinds beside it; each position's
share of choices; the same tiling chosen in both orders; and the problems named, against each kind's fault. Asked with
ties (the ties arms), the model may name several tilings it can't choose between: how often it does, and with what,
is scored too, and the report lists those questions for inspection.
"""
import hashlib
import json
import random
from pathlib import Path

import pymupdf

from semantic_pdf_diff.pages import shown
from semantic_pdf_diff.segmentation import grown, tiles as grid_tiles, xy_cut
from semantic_pdf_diff.tilechoice import PROBLEMS
from semantic_pdf_diff.tiling import measure, words

SIDE = 420  # points: tile_points, today's
# the known-bad kinds, each with the problem it shows (tilechoice.PROBLEMS)
KINDS = {
    "midline": "cuts text",       # each tile halved at the middle of its longer side: refinement's old cut
    "grid": "cuts text",          # the plain grid on the page, blank tiles left out
    "shifted": "cuts text",       # the good tiles' edges between rows moved into the nearest line
    "decoration": "decoration or blank",  # the good tiles and one holding only decoration
    "border": "decoration or blank",      # the good tiles and one of the page's margin alone
    "figure split": "splits a figure",    # the tile holding a figure cut through the figure's middle
    "missing": "misses content",  # the good tiles but the one holding most of the page's graphics, or its most lines
    # each good tile grown a quarter of its size a side, then to whole lines, kept where it cuts none: the grid's
    # fault, lines read twice
    "overlap": "repeats text",
}
# near cases (milestone 5, before its lever is trusted): one known-good against one tiling a little off, or against a
# heuristic cut where the measures find a fault in it; the fault expected is the measures' (fault_of)
NEAR = {
    "one cut": "one edge between two tiles moved into the line nearest it",
    "one overlap": "one tile grown down into the tile below it by three lines, cutting none",
    "today": "today's tiling (the default levers' cut, every tile kept)",
    "snapped": "the snapped grid, every tile kept",
}
# how the candidates are drawn (tilechoice.sketch), their pictures' suffix, and which questions are asked: outlined;
# or with what no tile holds greyed out, after the first run's misses (a tiling missing most of a page looked like the
# page untouched); near, dimmed; and both dimmed, asked with ties (the owner, 2026-10-12: "We should probably enable
# models to say that there isn't a best choice betwee two options.")
ARMS = {"outlined": {"suffix": "", "dimmed": False, "near": False, "ties": False},
        "dimmed": {"suffix": "-dimmed", "dimmed": True, "near": False, "ties": False},
        "near": {"suffix": "-dimmed", "dimmed": True, "near": True, "ties": False},
        "ties": {"suffix": "-dimmed", "dimmed": True, "near": False, "ties": True},
        "near-ties": {"suffix": "-dimmed", "dimmed": True, "near": True, "ties": True}}
# a model passes, under an arm, at these shares or more (set by judgement, 2026-10-11: gemma-4 chose the known-good
# 95% of the time, the same in both orders 91%, with the dimmed sketches; 90% and 87% with outlines alone)
PASS = {"good_chosen": 0.9, "same_in_both_orders": 0.85}
SHIFT_GAP = 24.0  # points: tiles this close, one above the other, share an edge (shifted)
MARGIN = 24.0  # points: a margin narrower than this gives no border tile
SETTINGS = {"context_tokens": 131072, "output_tokens": 1000, "image_tokens": 6000}  # the questions' shape (evaluator)

class Page:
    """A page and what the measures read of it."""

    def __init__(self, file, doc, number):
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        self.file, self.number, self.page = file, number, doc[number]
        self.settings = Settings()
        self.reader = reader = Context(doc, self.settings)
        self.lines = reader.lines(self.page)
        self.graphics = reader.graphics(self.page)
        decoration = {tuple(d) for d in reader.decoration(self.page)}
        self.decoration = [g for g in self.graphics if tuple(g) in decoration]
        self.content = [g for g in self.graphics if tuple(g) not in decoration]
        self.figures = [shown(self.page, f.bbox) for f in reader.figures(self.page, number) if f.region]
        self.words = words(self.page)
        self.id = f"{Path(file).stem}-p{number + 1}"
        self.seed = hashlib.sha256(f"{self.page.get_text()}|{self.id}".encode()).hexdigest()[:16]

    def measured(self, rects):
        """The page measures of a tiling, with "lines missed": lines no tile holds whole."""
        regions = [(f"tile:{i}", r, "") for i, r in enumerate(rects)]
        found = measure(self.page, regions, self.lines, self.graphics, self.words, self.figures, self.decoration)
        page = found["page"]
        page["lines_missed"] = sum(1 for b, _ in self.lines if not any(b in r + (-1, -1, 1, 1) for r in rects))
        return page

def good(p):
    """The known-good tiling (XY-cut, each detected figure kept whole), or None where the measures find a fault."""
    rects = xy_cut(p.page.rect, SIDE, p.lines, p.content + p.figures)  # a figure as one box: no cut inside it
    if not rects:
        return None
    m = p.measured(rects)
    faults = ("lines_cut_sideways", "lines_cut_across", "words_cut", "figures_not_whole", "decoration_only", "blank",
              "lines_missed")
    if any(m[f] for f in faults) or (m["graphics_missed"] or 0) > 0:
        return None
    return rects

def _midline(p, rects):
    out = []
    for r in rects:
        if r.width > r.height:
            mid = (r.x0 + r.x1) / 2
            out += [pymupdf.Rect(r.x0, r.y0, mid, r.y1), pymupdf.Rect(mid, r.y0, r.x1, r.y1)]
        else:
            mid = (r.y0 + r.y1) / 2
            out += [pymupdf.Rect(r.x0, r.y0, r.x1, mid), pymupdf.Rect(r.x0, mid, r.x1, r.y1)]
    return out

def _grid(p, rects):
    boxes = [b for b, _ in p.lines] + p.content
    return [t for t in grid_tiles(p.page.rect, SIDE) if any(t.intersects(b) for b in boxes)]

def _shifted(p, rects):
    """Where one tile sits above another (a gap under SHIFT_GAP between them), the edges between them moved to the
    middle of the line nearest that gap that either holds, so both tiles cut it."""
    out = [pymupdf.Rect(r) for r in rects]
    for i, a in enumerate(rects):
        for j, b in enumerate(rects):
            if i == j or not 0 <= b.y0 - a.y1 < SHIFT_GAP or min(a.x1, b.x1) <= max(a.x0, b.x0):
                continue
            near = [box for box, _ in p.lines if box.intersects(a) or box.intersects(b)]
            if not near:
                continue
            gap = (a.y1 + b.y0) / 2
            line = min(near, key=lambda box: abs((box.y0 + box.y1) / 2 - gap))
            out[i].y1 = out[j].y0 = (line.y0 + line.y1) / 2
    return [r for r in out if r.height > 1]

def _decoration(p, rects):
    texts = [b for b, _ in p.lines]
    for d in sorted(p.decoration, key=lambda d: -abs(d)):
        tile = (d + (-6, -6, 6, 6)) & p.page.rect
        if tile.width < 24:
            tile.x0, tile.x1 = max(0, tile.x0 - 12), min(p.page.rect.x1, tile.x1 + 12)
        if tile.height < 24:
            tile.y0, tile.y1 = max(0, tile.y0 - 12), min(p.page.rect.y1, tile.y1 + 12)
        if not any(tile.intersects(b) for b in texts + p.content):
            return rects + [tile]
    return None

def _border(p, rects):
    """The good tiles and a strip of the widest margin: between the page's edge and everything on it."""
    boxes = [b for b, _ in p.lines] + p.graphics
    extent = pymupdf.Rect(boxes[0])
    for b in boxes[1:]:
        extent |= b
    page = p.page.rect
    margins = {"top": extent.y0 - page.y0, "bottom": page.y1 - extent.y1, "left": extent.x0 - page.x0,
               "right": page.x1 - extent.x1}
    side, width = max(margins.items(), key=lambda m: m[1])
    if width < MARGIN:
        return None
    depth = min(width - 2, 72.0)
    strip = {"top": pymupdf.Rect(extent.x0, page.y0, extent.x1, page.y0 + depth),
             "bottom": pymupdf.Rect(extent.x0, page.y1 - depth, extent.x1, page.y1),
             "left": pymupdf.Rect(page.x0, extent.y0, page.x0 + depth, extent.y1),
             "right": pymupdf.Rect(page.x1 - depth, extent.y0, page.x1, extent.y1)}[side]
    return rects + [strip]

def _figure_split(p, rects):
    for f in sorted(p.figures, key=lambda f: -abs(f)):
        holders = [i for i, r in enumerate(rects) if f in r + (-1, -1, 1, 1)]
        if not holders:
            continue
        i = holders[0]
        r = rects[i]
        if f.width >= f.height:
            mid = (f.x0 + f.x1) / 2
            parts = [pymupdf.Rect(r.x0, r.y0, mid, r.y1), pymupdf.Rect(mid, r.y0, r.x1, r.y1)]
        else:
            mid = (f.y0 + f.y1) / 2
            parts = [pymupdf.Rect(r.x0, r.y0, r.x1, mid), pymupdf.Rect(r.x0, mid, r.x1, r.y1)]
        return rects[:i] + parts + rects[i + 1:]
    return None

def _missing(p, rects):
    if len(rects) < 2:
        return None

    def weight(r):
        drawn = sum(abs(g & r) for g in p.content)
        return (drawn, sum(1 for b, _ in p.lines if b in r + (-1, -1, 1, 1)))
    dropped = max(range(len(rects)), key=lambda i: weight(rects[i]))
    return rects[:dropped] + rects[dropped + 1:]

def _overlap(p, rects):
    out = []
    for r in rects:
        wider = (r + (-0.25 * r.width, -0.25 * r.height, 0.25 * r.width, 0.25 * r.height)) & p.page.rect
        out.append(grown(p.page, wider, lines=p.lines))
    return out

MAKERS = {"midline": _midline, "grid": _grid, "shifted": _shifted, "decoration": _decoration, "border": _border,
          "figure split": _figure_split, "missing": _missing, "overlap": _overlap}

def shows(kind, m):
    """Whether a bad tiling's measures show its kind's fault."""
    cuts = m["lines_cut_sideways"] + m["lines_cut_across"]
    return {"midline": cuts > 0, "grid": cuts > 0, "shifted": m["lines_cut_across"] > 0,
            "decoration": m["decoration_only"] > 0, "border": m["blank"] + m["decoration_only"] > 0,
            "figure split": m["figures_not_whole"] > 0,
            "missing": m["lines_missed"] > 0 or (m["graphics_missed"] or 0) > 0.05,
            "overlap": m["lines_read_twice"] > 0 and cuts == 0 and m["words_cut"] == 0}[kind]

def tilings(p, near=False):
    """{kind: [Rect]} for a page: "good" and each bad kind whose fault the measures find (the near kinds, if near);
    {} without a good one."""
    rects = good(p)
    if rects is None:
        return {}
    out = {"good": rects}
    for kind, make in (NEAR_MAKERS if near else MAKERS).items():
        bad = make(p, rects)
        if bad and (fault_of(p.measured(bad)) in NEAR_FAULTS.get(kind, PROBLEMS) if near
                    else shows(kind, p.measured(bad))):
            out[kind] = bad
    return out

def fault_of(m):
    """The problem a tiling's measures show first (tilechoice.PROBLEMS), or None: cut text, then a split figure,
    content missed, a tile of decoration or blank alone, lines read twice."""
    if m["lines_cut_sideways"] + m["lines_cut_across"] + m["words_cut"]:
        return "cuts text"
    if m["figures_not_whole"]:
        return "splits a figure"
    if m["lines_missed"] or (m["graphics_missed"] or 0) > 0.05:
        return "misses content"
    if m["decoration_only"] + m["blank"]:
        return "decoration or blank"
    return "repeats text" if m["lines_read_twice"] else None

def _stacked(p, rects):
    """(i, j): the first tile and the one below it (within SHIFT_GAP, overlapping across), with a line in either."""
    for i, a in enumerate(rects):
        for j, b in enumerate(rects):
            if i != j and 0 <= b.y0 - a.y1 < SHIFT_GAP and min(a.x1, b.x1) > max(a.x0, b.x0) and any(
                    box.intersects(a) or box.intersects(b) for box, _ in p.lines):
                return i, j
    return None

def _one_cut(p, rects):
    pair = _stacked(p, rects)
    if pair is None:
        return None
    i, j = pair
    a, b = rects[i], rects[j]
    gap = (a.y1 + b.y0) / 2
    line = min((box for box, _ in p.lines if box.intersects(a) or box.intersects(b)),
               key=lambda box: abs((box.y0 + box.y1) / 2 - gap))
    out = [pymupdf.Rect(r) for r in rects]
    out[i].y1 = out[j].y0 = (line.y0 + line.y1) / 2
    return out

def _one_overlap(p, rects):
    pair = _stacked(p, rects)
    if pair is None:
        return None
    i, j = pair
    below = sorted((box for box, _ in p.lines if box.intersects(rects[j]) and box.y0 >= rects[j].y0 - 1),
                   key=lambda box: box.y0)
    if len(below) < 3:
        return None
    out = [pymupdf.Rect(r) for r in rects]
    out[i].y1 = below[2].y1 + 1
    out[i] = grown(p.page, out[i], lines=p.lines)
    return out

def _heuristic(how):
    def make(p, rects):
        s, reader = p.settings, p.reader
        how_ = s.tiling_of(reader, p.page) if how is None else how
        cut = s.cut_named(reader, p.page, how_)
        return cut if how_ == "bands" else [s.grow(reader, p.page, r, p.page.rect) for r in cut]
    return make

NEAR_FAULTS = {"one cut": ("cuts text",), "one overlap": ("repeats text",)}  # the others: any fault the measures find
NEAR_MAKERS = {"one cut": _one_cut, "one overlap": _one_overlap, "today": _heuristic(None),
               "snapped": _heuristic("snapped")}

def near_questions(p, found):
    """[{"id", "kinds": [the good, one near kind], "orders"}]: each near kind against the known-good, in a seeded
    order, then swapped."""
    out = []
    for kind in sorted(k for k in found if k != "good"):
        kinds = ["good", kind]
        first = random.Random(f"{p.seed}|{kind}").sample(kinds, 2)
        out.append({"id": f"{p.id}-{kind.replace(' ', '-')}", "kinds": kinds, "orders": [first, first[::-1]]})
    return out

def questions(p, found):
    """[{"id", "kinds": [the good and one or two bad], "orders": [[kind, ...] by position, twice]}] for a page: its bad
    kinds shuffled (seeded by the page) and paired, the last one alone paired with another drawn at random."""
    rng = random.Random(p.seed)
    bad = sorted(k for k in found if k != "good")
    if not bad:
        return []
    rng.shuffle(bad)
    pairs = [bad[i:i + 2] for i in range(0, len(bad), 2)]
    if len(pairs[-1]) == 1 and len(bad) > 1:
        pairs[-1].append(rng.choice([k for k in bad if k != pairs[-1][0]]))
    out = []
    for n, pair in enumerate(pairs):
        kinds = ["good"] + pair
        first = random.Random(f"{p.seed}|{n}").sample(kinds, len(kinds))
        second = first[-1:] + first[:-1]  # each moves one place on
        out.append({"id": f"{p.id}-q{n}", "kinds": kinds, "orders": [first, second]})
    return out

def cases(folder, only=None, near=False):
    """(Page, {kind: [Rect]}, questions) for every page of the folder's PDFs, sorted; only: page ids to keep; near: the
    near cases' questions (near_questions), not the stark ones."""
    for path in sorted(Path(folder).glob("*.pdf")):
        with pymupdf.open(path) as doc:
            for number in range(len(doc)):
                if only and f"{path.stem}-p{number + 1}" not in only:
                    continue
                p = Page(path.name, doc, number)
                found = tilings(p, near)
                yield p, found, (near_questions if near else questions)(p, found)

def ask_all(folder, client, corpus, only=None, arm="outlined"):
    """{question id: {"page", "kinds", "orders", "answers": [per order: {"named", "problems", "error"}],
    "measures": {kind: page measures}}}: every question asked in both orders, under an arm of ARMS. Pictures go to
    folder/images."""
    from semantic_pdf_diff.dispatch import Dispatcher
    from semantic_pdf_diff.tilechoice import LETTERS, SKETCH_SIDE, Choice, named, problems, prompt, sketch
    target = Path(folder) / "images"
    target.mkdir(parents=True, exist_ok=True)
    out = {}
    with Dispatcher(client) as dispatch:
        for p, found, asked in cases(corpus, only, ARMS[arm]["near"]):
            if not asked:
                continue
            zoom = SKETCH_SIDE / max(p.page.rect.width, p.page.rect.height)
            pixmap = p.page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            clean = target / f"{p.id}.png"
            clean.write_bytes(sketch(p.page, pixmap=pixmap))
            for q in asked:
                record = out[q["id"]] = {"page": p.id, "kinds": q["kinds"], "orders": q["orders"],
                                         "answers": [None, None],
                                         "measures": {k: p.measured(found[k]) for k in q["kinds"]}}
                record["faults"] = {k: KINDS.get(k) or fault_of(record["measures"][k]) for k in q["kinds"][1:]}
                for o, order in enumerate(q["orders"]):
                    letters = list(LETTERS[:len(order)])
                    images = [clean]
                    for letter, kind in zip(letters, order):
                        image = target / f"{p.id}-{kind.replace(' ', '-')}-{letter}{ARMS[arm]['suffix']}.png"
                        if not image.exists():
                            image.write_bytes(sketch(p.page, found[kind], letter, pixmap=pixmap,
                                                     dimmed=ARMS[arm]["dimmed"]))
                        images.append(image)
                    key = ("tilechoice", f"{q['id']}|o{o}", arm)

                    def finish(value, error, record=record, o=o, letters=letters):
                        record["answers"][o] = ({"named": [], "problems": {}, "error": str(error)[:200]}
                                                if error is not None else
                                                {"named": named(value, letters), "problems": problems(value, letters),
                                                 "error": None, "raw": value.best})
                    dispatch.submit(prompt(letters, dimmed=ARMS[arm]["dimmed"], ties=ARMS[arm]["ties"]), Choice,
                                    images, key, finish)
                    dispatch.make_room()
        dispatch.drain()
    return out

# --- scoring ------------------------------------------------------------------------------------

def _share(a, b):
    return round(a / b, 3) if b else None

def score(asked):
    """A model's profile from ask_all's answers (questions never answered, as unrecorded in a replay, left out). A
    tiling is chosen where it's named alone; a tie (several named) chooses none, and is counted apart."""
    from semantic_pdf_diff.tilechoice import LETTERS
    answered = {k: q for k, q in asked.items() if all(a and not a["error"] for a in q["answers"])}
    picks = [(q, o, _picks(q, o)) for q in answered.values() for o in (0, 1)]
    out = {"questions": len(asked), "answered": len(answered), "asked": len(picks),
           "invalid": sum(1 for _, _, kinds in picks if not kinds)}
    out["good_chosen"] = _share(sum(1 for _, _, kinds in picks if kinds == ("good",)), len(picks))
    out["tied"] = _share(sum(1 for _, _, kinds in picks if len(kinds) > 1), len(picks))
    out["good_tied"] = _share(sum(1 for _, _, kinds in picks if len(kinds) > 1 and "good" in kinds), len(picks))
    both = list(answered.values())
    same = [q for q in both if _picks(q, 0) and set(_picks(q, 0)) == set(_picks(q, 1))]
    out["same_in_both_orders"] = _share(len(same), len(both))
    out["good_in_both_orders"] = _share(sum(1 for q in same if _picks(q, 0) == ("good",)), len(both))
    out["tied_questions"] = sum(1 for q in both if len(_picks(q, 0)) > 1 or len(_picks(q, 1)) > 1)
    by_kind = {}
    for q, o, kinds in picks:
        for bad in q["kinds"][1:]:
            k = by_kind.setdefault(bad, {"asked": 0, "good_chosen": 0, "this_chosen": 0, "tied_with_good": 0,
                                         "fault_named": 0})
            k["asked"] += 1
            k["good_chosen"] += kinds == ("good",)
            k["this_chosen"] += kinds == (bad,)
            k["tied_with_good"] += len(kinds) > 1 and {"good", bad} <= set(kinds)
            letter = LETTERS[q["orders"][o].index(bad)]
            k["fault_named"] += q["faults"][bad] in q["answers"][o]["problems"].get(letter, [])
    out["by_kind"] = {bad: {"asked": k["asked"], **{m: _share(k[m], k["asked"]) for m in (
        "good_chosen", "this_chosen", "tied_with_good", "fault_named")}} for bad, k in sorted(by_kind.items())}
    good_named = [q["answers"][o]["problems"].get(LETTERS[q["orders"][o].index("good")], []) for q, o, _ in picks]
    out["good_faulted"] = _share(sum(1 for g in good_named if g), len(good_named))
    out["good_faults"] = {p: sum(1 for g in good_named if p in g) for p in sorted({p for g in good_named for p in g})}
    out["passes"] = all((out[k] or 0) >= least for k, least in PASS.items())
    positions = {}
    for q, o, kinds in picks:
        n = len(q["orders"][o])
        row = positions.setdefault(str(n), {"asked": 0, "chosen": [0] * n, "good_at": [0] * n})
        row["asked"] += 1
        row["good_at"][q["orders"][o].index("good")] += 1
        if len(kinds) == 1:
            row["chosen"][q["orders"][o].index(kinds[0])] += 1
    out["positions"] = {n: {"asked": r["asked"], "chosen": [_share(c, r["asked"]) for c in r["chosen"]],
                            "good_at": [_share(c, r["asked"]) for c in r["good_at"]]} for n, r in positions.items()}
    return out

def _picks(q, o):
    """The kinds an answer names as best, in the order asked: one, several (a tie), or none."""
    from semantic_pdf_diff.tilechoice import LETTERS
    return tuple(q["orders"][o][LETTERS.index(x)] for x in q["answers"][o]["named"])

def _tied(q):
    return any(a and not a["error"] and len(a["named"]) > 1 for a in q["answers"])

def page(folder, data, asked_by_arm):
    """report.html: each model's profile under each arm and the questions it tied (each linked), then every
    question's pictures and answers, the wrong ones first, then the tied. data: {"models": {model: {arm: profile}}};
    asked_by_arm: {(model, arm): ask_all's answers}."""
    from semantic_pdf_diff.html_pages import esc, page as html_page
    from semantic_pdf_diff.tilechoice import LETTERS
    body = ["<h1>Tiling calibration</h1>",
            "<p class='muted'>Each question: the page, then its candidate tilings in the order asked; the known-good "
            "one is marked. Asked twice, each candidate moving one place on.</p>"]
    for (model, arm), asked in asked_by_arm.items():
        profile = data["models"][model][arm]
        body.append(f"<h2>{esc(model)}, {esc(arm)}</h2><pre>{esc(json.dumps(profile, indent=1))}</pre>")
        anchor = f"{model}|{arm}|"
        tied = [qid for qid, q in sorted(asked.items()) if _tied(q)]
        if tied:
            body.append("<p><b>Tied</b> (several named as equally good, in either order): " + ", ".join(
                f"<a href='#{esc(anchor + qid)}'>{esc(qid)}</a>" for qid in tied) + "</p>")
        wrong = sorted(asked.items(), key=lambda kv: (sum(_picks(kv[1], o) == ("good",) for o in (0, 1)
                                                          if kv[1]["answers"][o] and not kv[1]["answers"][o]["error"]),
                                                      not _tied(kv[1]), kv[0]))
        for qid, q in wrong:
            cells = [f"<figure><img src='images/{esc(q['page'])}.png' loading='lazy' alt=''><figcaption>the page"
                     "</figcaption></figure>"]
            for letter, kind in zip(LETTERS, q["orders"][0]):
                name = f"{q['page']}-{kind.replace(' ', '-')}-{letter}{ARMS[arm]['suffix']}.png"
                m = q["measures"][kind]
                note = (f"cut {m['lines_cut_sideways'] + m['lines_cut_across']}, figures split {m['figures_not_whole']}"
                        f", missed {m['lines_missed']} lines")
                cells.append(f"<figure><img src='images/{esc(name)}' loading='lazy' alt=''><figcaption><b>{letter}: "
                             f"{esc(kind)}</b> ({esc(note)})</figcaption></figure>")
            said = []
            for o, a in enumerate(q["answers"]):
                if a is None:
                    continue
                pick = " and ".join(_picks(q, o)) if not a["error"] else ""
                said.append(f"order {o + 1} ({esc(', '.join(q['orders'][o]))}): chose "
                            f"{esc(' and '.join(a['named']) or str(a.get('raw')))} = <b>{esc(pick or 'none')}</b>; "
                            f"problems {esc(json.dumps(a['problems']))}"
                            + (f"; error {esc(a['error'])}" if a["error"] else ""))
            body.append(f"<section id='{esc(anchor + qid)}'><h3>{esc(qid)}{' (tied)' if _tied(q) else ''}</h3>"
                        f"<p>{'<br>'.join(said)}</p><div class='row'>{''.join(cells)}</div></section>")
    style = ("body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1400px;padding:16px}"
             ".muted{color:var(--muted)}section{background:var(--card);border:1px solid var(--line);"
             "border-radius:8px;padding:12px;margin:12px 0}h3{margin:0 0 4px;font-size:15px}pre{font-size:12px}"
             ".row{display:flex;gap:12px;flex-wrap:wrap}figure{margin:0;flex:1 1 220px;min-width:0}"
             "img{width:100%;height:auto;border:1px solid var(--line);background:#fff}figcaption{font-size:13px}")
    target = Path(folder) / "report.html"
    target.write_text(html_page("Tiling calibration", "".join(body), style), encoding="utf-8")
    return target
