"""The model chooses a page's tiling: the question (docs/plans/tile-selection-2026-10-10.md, milestones 4 and 5).

One shrunk image of the page as it is, then one per candidate tiling: the page with that candidate's tiles outlined,
washed and numbered, and the candidate's letter in a strip above it. The model names the best candidate and, for each,
its problems from a closed list (PROBLEMS). The page tests' lesson: marks drawn on an image are read as the page's own
until the prompt says they aren't.

Calibration asks it with known-good and known-bad candidates (lab: bench/calibration.py) before any answer is trusted.

The tile_choice lever (levers.py) asks it where the tilers' cuts can't be ranked (choose): each candidate cut is
measured (tiling.measure), and where one is at least as good as every other on every measure (MEASURES) it's taken
without asking. Otherwise the cuts no other beats on every measure are the candidates: the default among them is kept
(tile_choice "measures"), or the model chooses (tile_choice "model"), falling back to that rule when it can't be asked
or its answer names none.
"""
import hashlib
import json
import random

import pymupdf

from pydantic import Field

from .schema import Lenient

PROBLEMS = ("cuts text", "splits a figure", "misses content", "decoration or blank", "repeats text")
LETTERS = "ABCDEF"
SKETCH_SIDE = 1024  # pixels: a picture's longer side, the page's (the strip above is besides)
COLOURS = ((0.85, 0.20, 0.20), (0.15, 0.45, 0.85), (0.10, 0.60, 0.30), (0.80, 0.50, 0.05), (0.55, 0.25, 0.75),
           (0.05, 0.60, 0.65))

DIM = 0.6  # how far what no tile holds is greyed out (dimmed sketches)

def sketch(page, tiles=None, letter=None, side=SKETCH_SIDE, pixmap=None, dimmed=False):
    """PNG bytes: the page as displayed, its longer side at `side` pixels; with tiles ([Rect], as displayed), each
    outlined in its colour, washed and numbered from 1 beside its top left corner (inside it at the page's edge), and
    "Tiling <letter>" in a strip above the page; dimmed, what no tile holds greyed out. pixmap: the page already
    rendered at this size."""
    rect = page.rect
    zoom = side / max(rect.width, rect.height)
    pixmap = pixmap or page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    if tiles is None:
        return pixmap.tobytes("png")
    strip = max(40, round(side * 0.05))
    with pymupdf.open() as out:  # drawn in pixels: one point to a pixel
        canvas = out.new_page(width=pixmap.width, height=pixmap.height + strip)
        whole = pymupdf.Rect(0, strip, pixmap.width, strip + pixmap.height)
        canvas.insert_image(whole, pixmap=pixmap)
        shown = [pymupdf.Rect(t.x0 * zoom, t.y0 * zoom + strip, t.x1 * zoom, t.y1 * zoom + strip) for t in tiles]
        if dimmed:  # the page greyed, then each tile's part of it shown again on top
            canvas.draw_rect(whole, color=None, fill=(0.55, 0.55, 0.55), fill_opacity=DIM)
            with pymupdf.open() as source:
                source.new_page(width=pixmap.width, height=pixmap.height).insert_image(
                    pymupdf.Rect(0, 0, pixmap.width, pixmap.height), pixmap=pixmap)
                for r in shown:
                    r = r & whole
                    if not r.is_empty:
                        canvas.show_pdf_page(r, source, 0, clip=r - (0, strip, 0, strip))
        canvas.draw_line((0, strip - 1), (pixmap.width, strip - 1), color=(0.3, 0.3, 0.3), width=1)
        if letter:
            canvas.insert_text((12, strip * 0.72), f"Tiling {letter}", fontname="hebo", fontsize=strip * 0.6,
                               color=(0, 0, 0))
        width = max(2.0, side / 400)
        for i, r in enumerate(shown):
            colour = COLOURS[i % len(COLOURS)]
            canvas.draw_rect(r, color=colour, fill=colour, width=width, fill_opacity=0.12, stroke_opacity=0.95)
        size = max(12.0, side / 64)
        for i, r in enumerate(shown):  # numbers last, so no tile's wash covers another's number
            number = str(i + 1)
            w, h = size * (0.6 * len(number) + 0.6), size * 1.2
            x = r.x0 - w if r.x0 >= w else r.x0  # left of the corner, in the margin, so no text is covered
            label = pymupdf.Rect(x, r.y0, x + w, r.y0 + h)
            canvas.draw_rect(label, color=None, fill=COLOURS[i % len(COLOURS)], fill_opacity=0.95)
            canvas.insert_text((label.x0 + size * 0.3, label.y1 - size * 0.28), number, fontname="hebo", fontsize=size,
                               color=(1, 1, 1))
        return canvas.get_pixmap(dpi=72, alpha=False).tobytes("png")

def prompt(letters, dimmed=False):
    """The question, for candidates named by these letters, in the order their images follow the page's; dimmed: the
    sketches grey out what no tile holds."""
    names = ", ".join(letters[:-1]) + f" and {letters[-1]}" if len(letters) > 1 else letters[0]
    example = {"best": " or ".join(letters), "problems": {x: ["..."] for x in letters}}  # no answer suggested
    return (
        f"The first image is a page of a document, shrunk. The next {len(letters)} show the same page cut into tiles, "
        f"one candidate tiling each: tilings {names}, in that order. A tiling's tiles are outlined in colour, lightly "
        "shaded and numbered beside a corner, and its letter is printed in a strip above the page. The outlines, "
        "shading, numbers and letters are drawn on to show the tiles: they aren't part of the page."
        + (" What no tile holds is greyed out." if dimmed else "") + "\n"
        "Each tile will be read on its own, close up. A good tiling:\n"
        "- cuts no text: every line of text lies whole inside one tile\n"
        "- splits no figure: each chart, drawing, diagram or picture lies whole inside one tile\n"
        "- misses no content: all the page's text and figures are inside its tiles\n"
        "- has no tile holding only decoration (rules, borders, logos, a background) or blank space\n"
        "- repeats little: few lines lie inside more than one tile\n"
        "You can't read the page's text at this size, and needn't: judge where the text and figures are.\n"
        "Which tiling is best? For each tiling, list its problems, using only these words: "
        + ", ".join(f'"{p}"' for p in PROBLEMS) + " (an empty list if it has none).\n"
        f"Return only JSON: {json.dumps(example)}")

class Choice(Lenient):
    best: str = ""
    problems: dict = Field(default_factory=dict)

def chosen(answer, letters):
    """The letter the answer names as best, or None (a letter it wasn't offered, or none)."""
    text = (answer.best or "").strip().upper().removeprefix("TILING").strip(" .:")
    return text if text in letters else None

def problems(answer, letters):
    """{letter: [problem]}: what the answer lists for each candidate offered, only PROBLEMS' words, in their order."""
    out = {}
    for key, found in (answer.problems or {}).items():
        letter = str(key).strip().upper().removeprefix("TILING").strip(" .:")
        if letter not in letters:
            continue
        said = " ".join(map(str, found)).lower() if isinstance(found, list) else str(found).lower()
        out[letter] = [p for p in PROBLEMS if p in said]
    return out

# --- the choice (milestone 5)

CANDIDATES = ("bands", "grid", "snapped", "xycut")  # the tilers' cuts (Platform.cut_named); bands where Tiling's apply
MEASURES = ("cuts", "figures split", "missed", "empty", "read twice", "small text", "images")  # each fewer is better
LEGIBLE_PX = 7.0  # capitals this tall or more are read: gemma-4's eye test, about 7 px at 1024 px (the cards)
CAP_SHARE = 0.6  # a text line's capitals, as a share of its box's height
RELIABLE = ("cuts text", "decoration or blank")  # the problems calibration found named reliably (92 to 100%)
FAULTS = {"cuts": "cuts text", "figures split": "splits a figure", "missed": "misses content",
          "empty": "decoration or blank", "read twice": "repeats text"}
MOST = 3  # candidates shown at most

def scores(measured, lines, rects, sides):
    """A cut's MEASURES from its page measures (tiling.measure's "page"): lines cut sideways or across, figures no
    tile holds whole, lines and graphics missed (lines no tile touches, and 1 for more than 5% of the graphics),
    tiles of decoration or blank alone, lines read twice, lines whose capitals no tile holding them shows LEGIBLE_PX
    tall (larger tiles show less detail: tiling.detail), tiles (candidates counts those sent). sides: each tile's
    render side (render_side)."""
    from .tiling import detail
    touched = sum(1 for box, _ in lines if any(box.intersects(r) for r in rects))
    details = [detail(r, side) or 0 for r, side in zip(rects, sides)]
    small = 0
    for box, _ in lines:
        shown_at = [d for r, d in zip(rects, details) if box in r + (-1, -1, 1, 1)]
        if shown_at and CAP_SHARE * min(box.width, box.height) * max(shown_at) < LEGIBLE_PX:
            small += 1
    return {"cuts": measured["lines_cut_sideways"] + measured["lines_cut_across"],
            "figures split": measured["figures_not_whole"],
            "missed": len(lines) - touched + ((measured["graphics_missed"] or 0) > 0.05),
            "empty": measured["decoration_only"] + measured["blank"],
            "read twice": measured["lines_read_twice"], "small text": small, "images": measured["tiles"]}

def beats(a, b):
    """Whether scores a are at least as good as b on every measure, and better on one."""
    return all(a[m] <= b[m] for m in MEASURES) and any(a[m] < b[m] for m in MEASURES)

def front(scored):
    """The candidates no other beats, in CANDIDATES' order."""
    return [h for h in scored if not any(beats(scored[o], scored[h]) for o in scored if o != h)]

def candidates(settings, reader, page, default):
    """{how: (tiles [Rect], scores)}: each cut the page may get, as tiles_for would make it but every tile kept; its
    images are those sent (tiles_for's, then kept_tiles': bands skip text-only bands, skip_empty blank tiles...)."""
    from .pages import shown
    from .tiling import measure, words
    lines, graphics = reader.lines(page), reader.graphics(page)
    decoration = reader.decoration(page) if getattr(settings, "decoration", False) else ()
    figures = [shown(page, f.bbox) for f in reader.figures(page, page.number) if f.region]
    word_boxes = words(page)
    out = {}
    for how in CANDIDATES:
        if how == "bands" and default != "bands":
            continue  # bands only where Tiling gives them: a wide page's bands were dropped (milestone 3)
        rects = settings.cut_named(reader, page, how)
        if how != "bands":
            rects = [settings.grow(reader, page, r, page.rect) for r in rects]
        regions = [(f"tile:{i}", r, "") for i, r in enumerate(rects)]
        measured = measure(page, regions, lines, graphics, word_boxes, figures, decoration)["page"]
        found = scores(measured, lines, rects, [settings.render_side(r) for r in rects])
        found["images"] = len(settings.kept_tiles(reader, page, settings.tiles_for(reader, page, how)))
        out[how] = (rects, found)
    return out

def choose(settings, reader, page, default, ask=False):
    """The cut a page gets, by name, its record kept in reader.page_choices: a candidate at least as good as the rest
    on every measure (the default, if it's one); where there's none, the default if no other beats it, else the first
    of those no other beats that beats it; with ask, the model's choice among those no other beats (up to MOST), the
    rule above where it can't be asked or names none."""
    if page.number in reader.page_choices:
        return reader.page_choices[page.number]["chosen"]
    found = candidates(settings, reader, page, default)
    scored = {h: v[1] for h, v in found.items()}
    best = front(scored)
    clear = [h for h in scored if all(scored[h][m] <= scored[o][m] for o in scored for m in MEASURES)]
    pick = clear or [h for h in best if h == default or beats(scored[h], scored[default])]
    by_rule = default if default in pick else pick[0]
    record = {"default": default, "scores": scored, "front": best, "clear": bool(clear), "chosen": by_rule,
              "asked": False}
    reader.page_choices[page.number] = record
    if clear or not ask or reader.ask is None or reader.assets is None:
        return by_rule
    shown_ = sorted(best, key=lambda h: tuple(scored[h][m] for m in MEASURES))[:MOST]
    record.update(asked=True, **_asked(reader, page, {h: found[h][0] for h in shown_}, scored))
    record["chosen"] = record.get("answer") or by_rule
    return record["chosen"]

def _asked(reader, page, tilings, scored):
    """The question asked: {"order", "answer" (a cut's name, or None), "problems" {how: [problem]}, "issues"}."""
    from .failures import ModelFailure
    from .regions import crop_name
    seed = hashlib.sha256(f"{page.get_text()}|{page.number}".encode()).hexdigest()
    order = random.Random(seed).sample(sorted(tilings), len(tilings))
    letters = list(LETTERS[:len(order)])
    zoom = SKETCH_SIDE / max(page.rect.width, page.rect.height)
    pixmap = reader.pixmap(page, pymupdf.Matrix(zoom, zoom))
    tag = f"vision:p{page.number}:tiling"
    images = [reader.assets / crop_name(reader.stem, tag, "-page")]
    images[0].write_bytes(sketch(page, pixmap=pixmap))
    for letter, how in zip(letters, order):
        images.append(reader.assets / crop_name(reader.stem, tag, f"-{letter}"))
        images[-1].write_bytes(sketch(page, tilings[how], letter, pixmap=pixmap, dimmed=True))
    out = {"order": order, "answer": None, "problems": {}, "issues": []}
    try:
        key = ("tilechoice", f"p{page.number}", reader.stem)
        answer = reader.ask(prompt(letters, dimmed=True), Choice, images, key)
    except ModelFailure as e:
        out["issues"].append(f"The tiling question failed ({e}); the cut chosen by the measures")
        return out
    letter = chosen(answer, letters)
    if letter is None:
        out["issues"].append(f"The tiling answer named no candidate ({answer.best!r}); the cut chosen by the measures")
    else:
        out["answer"] = order[letters.index(letter)]
    named = problems(answer, letters)
    out["problems"] = {order[letters.index(x)]: found for x, found in named.items()}
    for how in order:  # the reliable problems checked against the measures: a diagnostic
        measured = {FAULTS[m] for m in FAULTS if scored[how][m]}
        said = set(out["problems"].get(how, []))
        for problem in RELIABLE:
            if (problem in said) != (problem in measured):
                out["issues"].append(f"{how}: \"{problem}\" " + ("named by the model, not found by the measures"
                                     if problem in said else "found by the measures, not named by the model"))
    return out
