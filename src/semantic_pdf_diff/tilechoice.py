"""The model chooses a page's tiling: the question (docs/plans/tile-selection-2026-10-10.md, milestones 4 and 5).

One shrunk image of the page as it is, then one per candidate tiling: the page with that candidate's tiles outlined,
washed and numbered, and the candidate's letter in a strip above it. The model names the best candidate and, for each,
its problems from a closed list (PROBLEMS). The page tests' lesson: marks drawn on an image are read as the page's own
until the prompt says they aren't.

Calibration asks it with known-good and known-bad candidates (lab: bench/calibration.py) before any answer is trusted;
no lever asks it yet.
"""
import json

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
