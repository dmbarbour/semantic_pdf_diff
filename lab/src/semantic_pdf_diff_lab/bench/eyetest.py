"""Eye tests for vision models: images whose answers are known and can't be guessed in context.

Hosts don't say how they resize images (DeepInfra ignores gemma-4's image budget), and prices and
token counts can't be counted on, so what a model can read is measured, not assumed. The owner,
2026-09-30: "read this line of random numbers at various sizes, like an eye test for humans", and
binding tested "in a few forms (name=val, table rows, boxes with text connected by edges with text;
generated graphs or charts...)". Random codes and numbers are drawn at known sizes, so an answer
is scored exactly: no rater is needed, and nothing on the page makes a wrong reading plausible.

Families:
- read: lines of codes and numbers at a glyph height, image size and shape (acuity).
- pairs: names and values to pair up: on one row, across a wide gap, or a value below its name.
- table: cells looked up by row and column label, with or without grid lines.
- graph: boxes joined by labelled arrows; every arrow's two ends and its label.
- chart-values: grouped bars with a legend and each bar's value printed above it.
- chart-axis: bars read against a labelled axis (within a quarter of its step).

Glyph heights are cap heights in the image's own pixels, before any resizing by the host. Every
image's text layer is checked against its answers before it's sent.
"""
import json
import math
import random
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from pydantic import ConfigDict, Field
from semantic_pdf_diff.schema import Lenient

CAP = {"helv": 0.718, "cour": 0.562, "tiro": 0.662}  # cap height per em (the fonts' metrics)
LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"                    # no I, O or Q, as drawings avoid them
INCHES = ("1/8", "1/4", "3/8", "1/2", "5/8", "3/4", "7/8")
SERIES_COLORS = ((0.12, 0.47, 0.71), (1.0, 0.5, 0.05), (0.17, 0.63, 0.17))
FAMILIES = ("read", "confusable", "words", "pseudo", "pairs", "table", "graph", "chart-values", "chart-axis")
READING = ("read", "confusable", "words", "pseudo")  # families scored as transcribed lines
PASS = 0.9  # a glyph height is read when 90% of its items are
LARGE = 16  # glyphs above this (px) measure a ceiling, and stay out of the threshold fit

# --- answers ------------------------------------------------------------------------------------

class _Answer(Lenient):
    model_config = ConfigDict(coerce_numbers_to_str=True)

class Lines(_Answer):
    lines: list[str] = Field(default_factory=list)

class Pair(_Answer):
    name: str = ""
    value: str = ""

class Pairs(_Answer):
    pairs: list[Pair] = Field(default_factory=list)

class Lookup(_Answer):
    n: int = 0
    value: str = ""

class Lookups(_Answer):
    answers: list[Lookup] = Field(default_factory=list)

class Arrow(_Answer):
    start: str = ""
    end: str = ""
    label: str = ""

class Arrows(_Answer):
    edges: list[Arrow] = Field(default_factory=list)

SCHEMAS = {"read": Lines, "confusable": Lines, "words": Lines, "pseudo": Lines, "pairs": Pairs, "table": Lookups, "graph": Arrows, "chart-values": Lookups,
           "chart-axis": Lookups}

# --- random content -----------------------------------------------------------------------------

def code(rng):
    """A random label: "HX-402", "P-17B", "K7Q", "RT58"."""
    kind = rng.random()
    if kind < 0.4:
        return "".join(rng.choices(LETTERS, k=rng.randint(1, 3))) + "-" + str(rng.randint(1, 999)) + \
            (rng.choice(LETTERS) if rng.random() < 0.3 else "")
    if kind < 0.7:
        return rng.choice(LETTERS) + str(rng.randint(0, 9)) + rng.choice(LETTERS)
    return "".join(rng.choices(LETTERS, k=2)) + str(rng.randint(10, 99))

def number(rng, plain=False):
    """A random value: "4827", "31.6", "0.075", "-12.5", "±0.05", 2'-9 1/2" (plain: digits and a point only)."""
    kind = rng.random() if not plain else rng.random() * 0.6
    if kind < 0.3:
        return str(rng.randint(10, 9999))
    if kind < 0.6:
        digits = rng.randint(1, 3)
        return f"{rng.randint(0, 999)}.{str(rng.randint(1, 10 ** digits - 1)).zfill(digits).rstrip('0')}"
    if kind < 0.75:
        return f"{rng.choice('-+')}{rng.randint(0, 99)}.{rng.randint(1, 9)}"
    if kind < 0.85:
        return f"±0.{str(rng.randint(1, 99)).zfill(2).rstrip('0')}"
    fraction = f" {rng.choice(INCHES)}" if rng.random() < 0.6 else ""
    return f"{rng.randint(0, 40)}'-{rng.randint(0, 11)}{fraction}\""

# Meaningful words read differently from random codes (the owner, 2026-09-30: "We can expect gemma-4 etc.
# to do slightly better on meaningful words than on random texts and numbers. But only when it's meaningful
# to gemma-4. Shape of word, for example."). Pseudo-words keep a word's shape without its meaning, and show
# whether a model "corrects" what it can't quite see into a word it knows.
WORDS = tuple("""
about above across actual adjust after again agent air align allow alloy along also amount angle annual anchor
answer apply area argue arrange assembly assume attach average axial balance basic batch beam bearing below bending
between blade block board boiler bolt bottom bracket branch brief bright broad budget building cable capacity carbon
casing ceiling center chamber change channel charge check circuit clamp clear close coating coil column combine
common compact concrete condition conduit connect contain control cooling copper corner correct cost cover crane
current curve cycle damper damage define degree demand density depth design detail device diameter direct
discharge distance double drawing drive duct early edge effect electric element energy engine equal error exhaust
expansion factor failure fan feature field filter final finish fitting fixed flange flat floor flow fluid force
format frame frequency friction front fuel future gasket gauge general glass grade gravel ground guide handle
header heater height hinge housing humid impact input inside install joint keyway ladder layer leakage length
level limit linear liquid load local lower machine main manual margin material maximum measure metal meter method
minimum model module motor mount nominal normal nozzle number offset opening operate option outlet output outside
panel partial passage pattern piping pitch plate point pressure process profile pulley pump quality radius range
rated rating ratio reactor record reduce relief remote repair return rigid rotor rubber safety sample screen seal
section sensor service shaft sheet shield signal single sleeve slope socket solid source space speed spring square
stage standard steel storage strain stress structure supply support surface switch system tank target thermal
thread tolerance torque total tower transfer tube turbine unit upper valve vapor velocity vent vessel voltage wall
washer water weight welding width winding window wire""".split())
# Letters by height profile, the outline that gives a word its shape (Bouma 1971: ascending and descending
# parts, slenderness and outer parts are the cues readers confuse letters by).
HEIGHTS = {"x-height": "acemnorsuvwxz", "ascender": "bdfhklt", "descender": "gpqy", "dotted": "ij"}
# Look-alikes within a height class: letter confusion studies and lists of common misreadings (a/o, c/e/o,
# n/u, g/q, b/d; rn/m, cl/d and vv/w are multi-letter, left out to keep words' lengths).
CLOSE = {"a": "oe", "o": "aec", "e": "coa", "c": "eo", "n": "ur", "u": "nv", "r": "n", "v": "u",
         "b": "dh", "d": "b", "h": "bk", "k": "h", "f": "t", "t": "f", "g": "q", "q": "gp", "p": "q"}
PSEUDO_LEVELS = ("close", "profile", "shape")  # trickiest first; "shape" changes the outline (the owner's r → h)

def height(letter):
    return next(k for k, v in HEIGHTS.items() if letter in v)

def substitutes(letter, level):
    """Letters that can replace `letter` at a level: a look-alike of the same height (close), another letter of
    the same height (profile), or a letter of another height (shape)."""
    same = [c for c in HEIGHTS[height(letter)] if c != letter]
    if level == "close":
        return list(CLOSE.get(letter, ""))
    if level == "profile":
        return [c for c in same if c not in CLOSE.get(letter, "") and c not in "ij"]
    return [c for k, v in HEIGHTS.items() if k not in (height(letter), "dotted") for c in v]

# Characters often mistaken for each other in codes (lists of common misreadings: O/0/D/Q, I/l/1, S/5, B/8,
# Z/2, G/6/C). Confusable codes are built from them, in the forms the ordinary codes take.
CONFUSABLE_GROUPS = ("O0DQ", "Il1", "S5", "B8", "Z2", "G6C")
CONFUSABLE = {a: set(g) - {a} for g in CONFUSABLE_GROUPS for a in g}
# Helvetica draws a lowercase l and a capital I as the same stroke (only their spacing differs), so no eye can tell
# them apart: on look-alike cards they're scored as one character. Every model's most common "swap" was l read as I.
SAME_GLYPH = str.maketrans({"l": "I"})

def confusable_code(rng):
    """A code made mostly of look-alike characters: "B8-0D5", "S5Z2", "lI1-O0"."""
    pick = lambda n: "".join(rng.choice(rng.choice(CONFUSABLE_GROUPS)) for _ in range(n))
    kind = rng.random()
    if kind < 0.4:
        return pick(rng.randint(1, 3)) + "-" + pick(rng.randint(2, 3))
    return pick(rng.randint(3, 6))

def word(rng):
    w = rng.choice(WORDS)
    return w.capitalize() if rng.random() < 0.3 else w

def pseudo(rng, level="close"):
    """(pseudo-word, the word it came from): one inner letter replaced at a level of trickiness (see
    substitutes), giving a string that isn't a word in the list."""
    while True:
        w = rng.choice([w for w in WORDS if len(w) >= 5])
        spots = [k for k in range(1, len(w) - 1) if w[k] in "".join(HEIGHTS.values()) and substitutes(w[k], level)]
        if not spots:
            continue
        k = rng.choice(spots)
        p = w[:k] + rng.choice(substitutes(w[k], level)) + w[k + 1:]
        if p not in WORDS:
            return (p.capitalize(), w.capitalize()) if rng.random() < 0.3 else (p, w)

def unique(rng, make, n, taken=()):
    seen, out = set(taken), []
    while len(out) < n:
        x = make(rng)
        if compact(x) not in seen:
            seen.add(compact(x))
            out.append(x)
    return out

# --- cards and drawing --------------------------------------------------------------------------

@dataclass(frozen=True)
class Card:
    family: str
    w: int
    h: int
    glyph: float       # cap height, in the image's pixels
    font: str = "helv"
    seed: int = 1
    layout: str = ""   # pairs: inline, columns, stacked; table: grid, open; chart-values: series count
    count: int = 0     # lines, pairs, rows, nodes, categories or bars (0: the family's default)

    @property
    def id(self):
        parts = [self.family, f"{self.w}x{self.h}", f"g{self.glyph:g}", self.font]
        parts += [self.layout] if self.layout else []
        parts += [f"n{self.count}"] if self.count else []
        return "-".join(parts + [f"s{self.seed}"])

class Canvas:
    """A blank image of the card's size, drawn in points at 72 dpi (a point is a pixel)."""
    def __init__(self, card):
        import pymupdf
        self.pymupdf = pymupdf
        self.doc = pymupdf.open()
        self.page = self.doc.new_page(width=card.w, height=card.h)
        self.font, self.size = card.font, card.glyph / CAP[card.font]
        self.glyph, self.w, self.h = card.glyph, card.w, card.h
        self.margin = max(8.0, self.size)

    def width(self, text, size=None):
        return self.pymupdf.get_text_length(text, fontname=self.font, fontsize=size or self.size)

    def text(self, x, baseline, text, size=None, color=(0, 0, 0)):
        self.page.insert_text((x, baseline), text, fontname=self.font, fontsize=size or self.size, color=color)

    def centred(self, cx, baseline, text, size=None, color=(0, 0, 0)):
        self.text(cx - self.width(text, size) / 2, baseline, text, size, color)

    def rect(self, r, color=None, fill=None, width=1.0):
        shape = self.page.new_shape()
        shape.draw_rect(self.pymupdf.Rect(r))
        shape.finish(color=color, fill=fill, width=width)
        shape.commit()

    def line(self, p, q, color=(0, 0, 0), width=1.0, dashes=None):
        shape = self.page.new_shape()
        shape.draw_line(p, q)
        shape.finish(color=color, width=width, dashes=dashes)
        shape.commit()

    def polygon(self, points, fill=(0, 0, 0)):
        shape = self.page.new_shape()
        shape.draw_polyline(list(points) + [points[0]])
        shape.finish(color=fill, fill=fill, closePath=True, width=0.5)
        shape.commit()

    def png(self):
        return self.page.get_pixmap(dpi=72, alpha=False).tobytes("png")

    def text_layer(self):
        return self.page.get_text("text")

def render(card, image=True):
    """(png bytes or None, truth, prompt) for a card. Raises ValueError when the image's text layer
    lacks any of the truth's strings (a drawing bug, caught before a model is asked)."""
    rng = random.Random(card.id)
    canvas = Canvas(card)
    truth, prompt, strings = DRAW[card.family](card, rng, canvas)
    layer = compact(canvas.text_layer())
    missing = [s for s in strings if compact(s) not in layer]
    if missing:
        raise ValueError(f"{card.id}: not in the image's text layer: {missing[:5]}")
    return (canvas.png() if image else None), truth, prompt

JSON_ONLY = "Return only JSON: "
RANDOM = "Everything written in it is random: nothing can be guessed or corrected from context, so read it."

def _lines(card, rng, c, make):
    """Lines of tokens from make(rng), placed as a block at a random spot; (lines, the tokens' sources)."""
    n, gap, room = card.count or 5, c.size * 1.6, c.w - 2 * c.margin
    lines, sources = [], []
    for _ in range(n):
        tokens = []
        while len(tokens) < 8:
            token, source = make(rng)
            if c.width("   ".join(tokens + [token])) > room:
                break
            tokens.append(token)
            sources.append(source)
        if tokens:
            lines.append("   ".join(tokens))
    if not lines or gap * len(lines) > c.h - 2 * c.margin:
        raise ValueError(f"{card.id}: glyphs too large for the image")
    block_w, block_h = max(c.width(l) for l in lines), gap * len(lines)
    x0 = c.margin + rng.random() * max(0.0, room - block_w)
    y0 = c.margin + rng.random() * max(0.0, c.h - 2 * c.margin - block_h)
    for k, line in enumerate(lines):
        c.text(x0, y0 + c.glyph + k * gap, line)
    return lines, sources

def _read(card, rng, c):
    lines, _ = _lines(card, rng, c, lambda r: ((code(r) if r.random() < 0.5 else number(r)), None))
    prompt = ("The image shows a few lines of codes and numbers. " + RANDOM + " Transcribe every line exactly as "
              "printed, top to bottom, keeping the order of the items in each line. Write ? for each character "
              "you can't read.\n" + JSON_ONLY + '{"lines": ["first line", "second line"]}')
    return {"lines": lines}, prompt, lines

def _confusable(card, rng, c):
    """The ordinary codes' prompt: whether a model tells look-alikes apart when nothing else tells them."""
    lines, _ = _lines(card, rng, c, lambda r: (confusable_code(r), None))
    prompt = ("The image shows a few lines of codes and numbers. " + RANDOM + " Transcribe every line exactly as "
              "printed, top to bottom, keeping the order of the items in each line. Write ? for each character "
              "you can't read.\n" + JSON_ONLY + '{"lines": ["first line", "second line"]}')
    return {"lines": lines, "confusable": True}, prompt, lines

WORDS_PROMPT = ("The image shows a few lines of words. Transcribe every line exactly as printed, letter by letter, "
                "top to bottom; don't correct spelling. Write ? for each character you can't read.\n" + JSON_ONLY +
                '{"lines": ["first line", "second line"]}')

def _words(card, rng, c):
    lines, _ = _lines(card, rng, c, lambda r: (word(r), None))
    return {"lines": lines}, WORDS_PROMPT, lines

def _pseudo(card, rng, c):
    """The same prompt as real words: whether a model reads what's printed or the word it expects."""
    lines, sources = _lines(card, rng, c, lambda r: pseudo(r, card.layout or "close"))
    return {"lines": lines, "sources": sources, "level": card.layout or "close"}, WORDS_PROMPT, lines

def _pairs(card, rng, c):
    n, layout = card.count or 12, card.layout or "inline"
    names = unique(rng, code, n)
    values = unique(rng, number, n, taken=map(compact, names))
    pairs = list(zip(names, values))
    room_w, room_h = c.w - 2 * c.margin, c.h - 2 * c.margin
    if layout == "inline":
        texts = [f"{a} = {b}" for a, b in pairs]
        cell_w = max(c.width(t) for t in texts) + 2 * c.size
        cols = max(1, min(4, int(room_w // cell_w)))
        rows = math.ceil(n / cols)
        cell_h = room_h / rows
        if cell_h < c.size * 1.8:
            raise ValueError(f"{card.id}: too many pairs for the image")
        for k, t in enumerate(texts):
            col, row = k % cols, k // cols
            x = c.margin + col * (room_w / cols) + rng.random() * max(0.0, room_w / cols - c.width(t))
            y = c.margin + row * cell_h + c.glyph + rng.random() * max(0.0, cell_h - c.size * 1.5)
            c.text(x, y, t)
    elif layout == "columns":  # names left, values right-aligned far off, rows close together
        gap = c.size * 1.5
        if gap * n > room_h:
            raise ValueError(f"{card.id}: too many pairs for the image")
        y0 = c.margin + rng.random() * (room_h - gap * n)
        right = c.w - c.margin - rng.random() * room_w * 0.15
        for k, (a, b) in enumerate(pairs):
            y = y0 + c.glyph + k * gap
            c.text(c.margin, y, a)
            c.text(right - c.width(b), y, b)
    else:  # stacked: each value just below its name, the next name further below
        cell_w = max(max(c.width(a), c.width(b)) for a, b in pairs) + 2.5 * c.size
        cols = max(1, min(4, int(room_w // cell_w)))
        rows = math.ceil(n / cols)
        inner, outer = c.size * 1.25, c.size * 2.1
        if rows * (inner + outer) > room_h:
            raise ValueError(f"{card.id}: too many pairs for the image")
        for k, (a, b) in enumerate(pairs):
            col, row = k % cols, k // cols
            x = c.margin + col * (room_w / cols)
            y = c.margin + c.glyph + row * (inner + outer)
            c.text(x, y, a)
            c.text(x, y + inner, b)
    prompt = ("The image shows names (codes) with their values. " + RANDOM + " A value belongs to a name by the "
              "layout: after it on the same row (perhaps across a wide gap), or just below it. List every name with "
              "its value, exactly as printed. Write ? for each character you can't read.\n" + JSON_ONLY +
              '{"pairs": [{"name": "...", "value": "..."}]}')
    return {"pairs": dict(pairs)}, prompt, names + values

def _questions(asks):
    return "\n".join(f"{k + 1}. {q}" for k, q in enumerate(asks))

def _table(card, rng, c):
    grid, rows, pad = (card.layout or "grid") == "grid", card.count or 8, c.size * 0.6
    row_h = c.size * (1.8 if grid else 1.45)
    rows = min(rows, int((c.h - 2 * c.margin) // row_h) - 1)
    labels = unique(rng, code, rows)
    columns, cells, taken = [], [], set(map(compact, labels))
    x_label = max(c.width(l) for l in labels) + 2 * pad
    used = x_label
    while len(columns) < 8:
        header = unique(rng, code, 1, taken=taken)[0]
        values = unique(rng, lambda r: number(r, plain=True), rows, taken=taken | {compact(header)})
        taken |= {compact(header)} | set(map(compact, values))
        width = max([c.width(header)] + [c.width(v) for v in values]) + 2 * pad
        if used + width > c.w - 2 * c.margin:
            break
        columns.append(header)
        cells.append((values, width))
        used += width
    if len(columns) < 3 or rows < 3:
        raise ValueError(f"{card.id}: glyphs too large for a table in the image")
    x0 = c.margin + rng.random() * (c.w - 2 * c.margin - used)
    y0 = c.margin + rng.random() * max(0.0, c.h - 2 * c.margin - row_h * (rows + 1))
    xs = [x0, x0 + x_label]
    for _, width in cells:
        xs.append(xs[-1] + width)
    baseline = lambda r: y0 + r * row_h + (row_h + c.glyph) / 2
    for j, header in enumerate(columns):
        c.text(xs[j + 1] + pad, baseline(0), header)
    for i, label in enumerate(labels):
        c.text(xs[0] + pad, baseline(i + 1), label)
        for j, (values, width) in enumerate(cells):
            c.text(xs[j + 2] - pad - c.width(values[i]), baseline(i + 1), values[i])  # right-aligned
    if grid:
        for r in range(rows + 2):
            c.line((xs[0], y0 + r * row_h), (xs[-1], y0 + r * row_h), width=0.8)
        for x in xs:
            c.line((x, y0), (x, y0 + (rows + 1) * row_h), width=0.8)
    else:
        c.line((xs[0], y0 + row_h), (xs[-1], y0 + row_h), width=0.8)  # a rule under the headers only
    table = {f"{labels[i]}|{columns[j]}": cells[j][0][i] for i in range(rows) for j in range(len(columns))}
    picks = rng.sample(sorted(table), min(8, len(table)))
    asks = [f'Row "{p.split("|")[0]}", column "{p.split("|")[1]}"' for p in picks]
    prompt = ("The image shows a table: row labels on the left, column labels across the top. " + RANDOM +
              " Answer each question with the value in that cell, exactly as printed; write ? if you can't read "
              "it.\n\n" + _questions(asks) + "\n\n" + JSON_ONLY + '{"answers": [{"n": 1, "value": "..."}]}')
    truth = {"questions": [{"n": k + 1, "key": p, "value": table[p]} for k, p in enumerate(picks)], "cells": table}
    return truth, prompt, labels + columns + [v for values, _ in cells for v in values]

def _border(rect, towards):
    """Where the segment from a box's centre towards a point leaves the box."""
    cx, cy = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
    dx, dy = towards[0] - cx, towards[1] - cy
    t = min((rect[2] - rect[0]) / 2 / abs(dx) if dx else math.inf, (rect[3] - rect[1]) / 2 / abs(dy) if dy else math.inf)
    return cx + t * dx, cy + t * dy

def _overlaps(a, b, pad=0.0):
    return not (a[2] + pad <= b[0] or b[2] + pad <= a[0] or a[3] + pad <= b[1] or b[3] + pad <= a[1])

def _graph(card, rng, c):
    target = card.count or 6
    cols = max(2, round(math.sqrt(target * c.w / c.h)))
    rows = max(2, math.ceil(target / cols))
    names = unique(rng, code, cols * rows)
    cell_w, cell_h = (c.w - 2 * c.margin) / cols, (c.h - 2 * c.margin) / rows
    boxes = {}
    for k, name in enumerate(names):
        col, row = k % cols, k // cols
        bw, bh = c.width(name) + 1.4 * c.size, 2.0 * c.size
        if bw > cell_w * 0.6 or bh > cell_h * 0.45:
            raise ValueError(f"{card.id}: glyphs too large for the graph")
        cx = c.margin + (col + 0.5 + rng.uniform(-0.15, 0.15)) * cell_w
        cy = c.margin + (row + 0.5 + rng.uniform(-0.15, 0.15)) * cell_h
        boxes[name] = (cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    at = lambda col, row: names[row * cols + col]
    candidates = [(at(i, j), at(i + 1, j)) for j in range(rows) for i in range(cols - 1)]
    candidates += [(at(i, j), at(i, j + 1)) for j in range(rows - 1) for i in range(cols)]
    for j in range(rows - 1):  # one diagonal per square at most: crossing diagonals would share a midpoint
        for i in range(cols - 1):
            if rng.random() < 0.35:
                candidates.append((at(i, j), at(i + 1, j + 1)) if rng.random() < 0.5 else (at(i + 1, j), at(i, j + 1)))
    rng.shuffle(candidates)
    chosen = candidates[:max(len(names) - 1, round(len(names) * 1.3))]
    labels = unique(rng, lambda r: code(r) if r.random() < 0.5 else number(r, plain=True), len(chosen),
                    taken=map(compact, names))
    stroke = max(1.0, c.size * 0.07)
    edges, label_boxes = [], []
    for (a, b), label in zip(chosen, labels):
        if rng.random() < 0.5:
            a, b = b, a
        centre_b = ((boxes[b][0] + boxes[b][2]) / 2, (boxes[b][1] + boxes[b][3]) / 2)
        centre_a = ((boxes[a][0] + boxes[a][2]) / 2, (boxes[a][1] + boxes[a][3]) / 2)
        p, q = _border(boxes[a], centre_b), _border(boxes[b], centre_a)
        lw, lh = c.width(label) + 0.5 * c.size, 1.3 * c.size
        for t in (0.5, 0.38, 0.62):
            mx, my = p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])
            spot = (mx - lw / 2, my - lh / 2, mx + lw / 2, my + lh / 2)
            if not any(_overlaps(spot, o, c.size * 0.3) for o in label_boxes + list(boxes.values())):
                break
        else:
            continue  # nowhere to put its label clearly: not drawn
        label_boxes.append(spot)
        edges.append({"start": a, "end": b, "label": label, "line": (p, q), "spot": spot})
    if len(edges) < 3:
        raise ValueError(f"{card.id}: too few arrows fit")
    for e in edges:
        (p, q), length = e["line"], math.dist(*e["line"])
        ux, uy = (q[0] - p[0]) / length, (q[1] - p[1]) / length
        head = min(1.2 * c.size, length / 3)
        base = (q[0] - ux * head, q[1] - uy * head)
        c.line(p, base, width=stroke)
        c.polygon([q, (base[0] - uy * head * 0.4, base[1] + ux * head * 0.4),
                   (base[0] + uy * head * 0.4, base[1] - ux * head * 0.4)])
    for name, box in boxes.items():
        c.rect(box, color=(0, 0, 0), fill=(1, 1, 1), width=stroke)
        c.centred((box[0] + box[2]) / 2, (box[1] + box[3] + c.glyph) / 2, name)
    for e in edges:
        c.rect(e["spot"], fill=(1, 1, 1), color=None)
        c.centred((e["spot"][0] + e["spot"][2]) / 2, (e["spot"][1] + e["spot"][3] + c.glyph) / 2, e["label"])
    prompt = ("The image shows boxes joined by arrows, each arrow with a label. " + RANDOM + " List every arrow: "
              "the box it starts from, the box it points to, and its label, all exactly as printed. Write ? for "
              "each character you can't read.\n" + JSON_ONLY + '{"edges": [{"start": "...", "end": "...", "label": "..."}]}')
    truth = {"edges": [{k: e[k] for k in ("start", "end", "label")} for e in edges]}
    return truth, prompt, names + [e["label"] for e in edges]

def _axes(c, top, step, left_labels):
    """A chart's frame: the plot area, and a vertical axis from 0 to `top` labelled every `step`."""
    left = c.margin + max(c.width(l) for l in left_labels) + c.size
    plot = (left, c.margin + 3 * c.size, c.w - c.margin, c.h - c.margin - 2.2 * c.size)
    scale = (plot[3] - plot[1]) / top
    for k in range(int(top / step) + 1):
        y = plot[3] - k * step * scale
        label = f"{k * step:g}"
        c.text(left - 0.5 * c.size - c.width(label), y + c.glyph / 2, label)
        c.line((left - 0.3 * c.size, y), (plot[2], y), color=(0.75, 0.75, 0.75), width=0.6)
    c.line((left, plot[1]), (left, plot[3]), width=1.0)
    c.line((left, plot[3]), (plot[2], plot[3]), width=1.0)
    return plot, scale

def _chart_values(card, rng, c):
    series_n, cats = int(card.layout or 2), card.count or 5
    series = unique(rng, code, series_n)
    values = {}
    top = 1000
    ticks = [f"{k * 200}" for k in range(6)]
    widest = c.width("000.0") + 0.3 * c.size
    plot_w = c.w - 2 * c.margin - c.width("1000") - c.size
    cats = min(cats, int(plot_w // (series_n * widest / 0.8)))
    if cats < 2:
        raise ValueError(f"{card.id}: glyphs too large for the chart")
    categories = unique(rng, code, cats, taken=map(compact, series))
    plot, scale = _axes(c, top, 200, ticks)
    group = (plot[2] - plot[0]) / cats
    bar = group * 0.8 / series_n
    for i, cat in enumerate(categories):
        for s, name in enumerate(series):
            v = f"{rng.randint(40, 950)}.{rng.randint(1, 9)}" if rng.random() < 0.5 else str(rng.randint(40, 950))
            values[f"{cat}|{name}"] = v
            x0 = plot[0] + i * group + group * 0.1 + s * bar
            y = plot[3] - float(v) * scale
            c.rect((x0, y, x0 + bar * 0.92, plot[3]), fill=SERIES_COLORS[s], color=None)
            c.centred(x0 + bar * 0.46, y - 0.35 * c.size, v)
        c.centred(plot[0] + (i + 0.5) * group, plot[3] + 1.6 * c.size, cat)
    x = plot[2]
    for s in reversed(range(series_n)):  # the legend, top right
        x -= c.width(series[s]) + 2.4 * c.size
        c.rect((x, c.margin + 0.4 * c.size, x + c.size, c.margin + 1.4 * c.size), fill=SERIES_COLORS[s], color=None)
        c.text(x + 1.4 * c.size, c.margin + 0.4 * c.size + c.glyph, series[s])
    picks = rng.sample(sorted(values), min(6, len(values)))
    asks = [f'Category "{p.split("|")[0]}", series "{p.split("|")[1]}"' for p in picks]
    prompt = ("The image shows a bar chart: for each category (named under the axis) a group of bars, one per "
              "series (named in the legend by colour), with each bar's value printed above it. " + RANDOM +
              " Answer each question with the value printed above that bar, exactly as printed; write ? if you "
              "can't tell.\n\n" + _questions(asks) + "\n\n" + JSON_ONLY + '{"answers": [{"n": 1, "value": "..."}]}')
    truth = {"questions": [{"n": k + 1, "key": p, "value": values[p]} for k, p in enumerate(picks)], "cells": values}
    return truth, prompt, series + categories + list(values.values())

def _chart_axis(card, rng, c):
    bars = card.count or 6
    step = rng.choice((10, 20, 25, 50, 200))
    top = step * rng.randint(4, 6)
    ticks = [f"{k * step:g}" for k in range(int(top / step) + 1)]
    plot_w = c.w - 2 * c.margin - max(c.width(t) for t in ticks) - c.size
    categories = unique(rng, code, bars)
    if max(c.width(x) for x in categories) * 1.15 * bars > plot_w:
        raise ValueError(f"{card.id}: glyphs too large for the chart")
    plot, scale = _axes(c, top, step, ticks)
    width = (plot[2] - plot[0]) / bars
    values = {}
    for i, cat in enumerate(categories):
        v = rng.randint(1, 2 * top // step) * step / 2
        values[cat] = f"{v:g}"
        x0 = plot[0] + i * width + width * 0.2
        c.rect((x0, plot[3] - v * scale, x0 + width * 0.6, plot[3]), fill=SERIES_COLORS[0], color=None)
        c.centred(plot[0] + (i + 0.5) * width, plot[3] + 1.6 * c.size, cat)
    asks = [f'Bar "{cat}"' for cat in categories]
    prompt = ("The image shows a bar chart with the bars' names under the axis. " + RANDOM + " Read each bar's "
              "height against the vertical axis and give it as a number, to the nearest half of the axis's labelled "
              "step; write ? if you can't tell.\n\n" + _questions(asks) + "\n\n" + JSON_ONLY +
              '{"answers": [{"n": 1, "value": "..."}]}')
    truth = {"questions": [{"n": k + 1, "key": cat, "value": values[cat], "tolerance": step / 4}
                           for k, cat in enumerate(categories)], "cells": values}
    return truth, prompt, categories + ticks

DRAW = {"read": _read, "confusable": _confusable, "words": _words, "pseudo": _pseudo, "pairs": _pairs, "table": _table, "graph": _graph, "chart-values": _chart_values,
        "chart-axis": _chart_axis}

# --- suites -------------------------------------------------------------------------------------

SQUARES = [(512, 512), (768, 768), (1024, 1024), (1536, 1536), (2048, 2048)]
SHAPES = [(1024, 256), (1584, 384), (3072, 768), (384, 1536)]  # bands (our report bands are 4:1), and a column

def suite(name="standard"):
    """The cards of a suite, in a fixed order."""
    cards = []
    if name == "quick":
        for w, h in [(768, 768), (1536, 1536), (1584, 384)]:
            cards += [Card("read", w, h, g) for g in (5, 8, 12)]
        cards += [Card("pairs", 1024, 1024, 8, layout="columns"), Card("table", 1024, 1024, 8, layout="open"),
                  Card("graph", 1024, 1024, 10), Card("chart-values", 1024, 1024, 10, layout="2"),
                  Card("chart-axis", 1024, 1024, 10)]
        return cards
    for seed in (1, 2):
        for w, h in SQUARES + SHAPES:
            cards += [Card("read", w, h, g, seed=seed) for g in (4, 5, 6, 7, 8, 10, 12, 16)]
    cards += [Card("read", 1024, 1024, g, font=f) for f in ("cour", "tiro") for g in (5, 6, 8, 10)]
    # Large glyphs: how far a model may be magnified. Qwen3-VL broke 14-point text into pieces in 144-point
    # tiles at 1536 px (capitals about 100 px tall; docs/research/page-tests-2026-09-30.md).
    cards += [Card("read", 1024, 1024, g, seed=seed) for seed in (1, 2) for g in (24, 32, 40, 48, 64)]
    # Words and pseudo-words at the codes' sizes and glyphs (one seed): what meaning and word shape add.
    cards += [Card("words", w, h, g) for w, h in SQUARES[1:] for g in (4, 5, 6, 7, 8, 10, 12)]
    cards += [Card("confusable", w, h, g) for w, h in SQUARES[1:] for g in (4, 5, 6, 7, 8, 10, 12)]
    cards += [Card("pseudo", w, h, g, layout=level) for level in PSEUDO_LEVELS for w, h in SQUARES[1:]
              for g in (4, 5, 6, 7, 8, 10, 12)]
    for layout in ("inline", "columns", "stacked"):
        cards += [Card("pairs", 1024, 1024, g, layout=layout) for g in (6, 8, 12)]
        cards += [Card("pairs", 2048, 2048, g, layout=layout) for g in (8, 12)]
    for layout in ("grid", "open"):
        cards += [Card("table", 1024, 1024, g, layout=layout, count=n) for n in (8, 20) for g in (6, 8, 12)]
        cards += [Card("table", 2048, 2048, g, layout=layout, count=20) for g in (8, 12)]
    for seed in (1, 2):
        cards += [Card("graph", 1024, 1024, g, count=n, seed=seed) for n in (6, 9) for g in (7, 10, 14)]
        cards += [Card("chart-values", 1024, 1024, g, layout=s, seed=seed) for s in ("2", "3") for g in (7, 10, 14)]
        cards += [Card("chart-axis", 1024, 1024, g, count=n, seed=seed) for n in (5, 9) for g in (8, 12)]
    return cards

# --- scoring ------------------------------------------------------------------------------------

FOLD = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-", "’": "'", "‘": "'", "′": "'",
                      "“": '"', "”": '"', "″": '"', "×": "x"})

def norm(text):
    return " ".join(unicodedata.normalize("NFKC", str(text)).translate(FOLD).casefold().split())

def compact(text):
    return norm(text).replace(" ", "")

def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]

def _number(text):
    try:
        return float(norm(text).replace(",", "").split()[0])
    except (ValueError, IndexError):
        return None

def score(card, truth, answer):
    """{"score": the share of items right, and counts by kind of error} for one answer (a dict)."""
    family = card.family if isinstance(card, Card) else card
    if family in READING:
        lines = lambda ls: [str(line).translate(SAME_GLYPH) if truth.get("confusable") else str(line) for line in ls or ()]
        expected = [norm(t) for line in lines(truth["lines"]) for t in line.split()]
        given = [norm(t) for line in lines(answer.get("lines")) for t in line.split()]
        matched = sum(b.size for b in SequenceMatcher(None, expected, given, autojunk=False).get_matching_blocks())
        want, got = "".join(expected), "".join(given)
        out = {"score": round(matched / len(expected), 4), "items": len(expected), "right": matched,
               "cer": round(min(1.0, edit_distance(want, got) / len(want)), 4), "unread": got.count("?")}
        if truth.get("confusable"):  # look-alikes swapped, counted where a token was read at its length
            raw_expected = [t for line in lines(truth["lines"]) for t in line.split()]
            raw_given = [t for line in lines(answer.get("lines")) for t in line.split()]
            swaps = 0
            for op, i1, i2, j1, j2 in SequenceMatcher(None, expected, given, autojunk=False).get_opcodes():
                if op == "replace":
                    for a, b in zip(raw_expected[i1:i2], raw_given[j1:j2]):
                        if len(a) == len(b):
                            swaps += sum(1 for x, y in zip(a, b) if x != y and y in CONFUSABLE.get(x, ()))
            out["confused"] = swaps
        if truth.get("sources"):  # pseudo-words read as the word they came from
            out["autocorrected"] = sum(1 for t in given if t in {norm(w) for w in truth["sources"]})
        return out
    if family == "pairs":
        expected = {compact(k): compact(v) for k, v in truth["pairs"].items()}
        owner = {v: k for k, v in expected.items()}
        counts = {"right": 0, "misbound": 0, "misread": 0, "unknown_name": 0}
        seen = set()
        for p in answer.get("pairs") or ():
            name, value = compact(p.get("name", "")), compact(p.get("value", ""))
            if name not in expected or name in seen:
                counts["unknown_name"] += name not in expected
                continue
            seen.add(name)
            kind = "right" if value == expected[name] else "misbound" if value in owner else "misread"
            counts[kind] += 1
        return {"score": round(counts["right"] / len(expected), 4), "items": len(expected),
                "missed": len(expected) - len(seen), **counts}
    if family == "graph":
        expected = [tuple(compact(e[k]) for k in ("start", "end", "label")) for e in truth["edges"]]
        labels = {e[2]: e for e in expected}
        counts = {"right": 0, "reversed": 0, "label_misread": 0, "label_misbound": 0, "ends_wrong": 0, "spurious": 0}
        left = list(expected)
        for a in answer.get("edges") or ():
            got = tuple(compact(a.get(k, "")) for k in ("start", "end", "label"))
            if got in left:
                left.remove(got)
                counts["right"] += 1
                continue
            same_ends = [e for e in left if {e[0], e[1]} == {got[0], got[1]}]
            if (got[1], got[0], got[2]) in left:
                left.remove((got[1], got[0], got[2]))
                counts["reversed"] += 1
            elif same_ends:
                left.remove(same_ends[0])
                counts["label_misbound" if got[2] in labels else "label_misread"] += 1
            elif got[2] in labels and labels[got[2]] in left:
                left.remove(labels[got[2]])
                counts["ends_wrong"] += 1
            else:
                counts["spurious"] += 1
        return {"score": round(counts["right"] / len(expected), 4), "items": len(expected), "missed": len(left), **counts}
    # lookups: table, chart-values, chart-axis
    given = {a.get("n"): a.get("value", "") for a in answer.get("answers") or ()}
    cells = truth["cells"]
    counts = {"right": 0, "misbound": 0, "misread": 0, "declined": 0, "same_row_or_column": 0}
    for q in truth["questions"]:
        value = str(given.get(q["n"], "") or "")
        if not compact(value) or compact(value).strip("?") == "":
            counts["declined"] += 1
            continue
        tolerance = q.get("tolerance")
        if tolerance is not None:
            got = _number(value)
            close = lambda v: got is not None and abs(got - float(v)) <= tolerance
            right = close(q["value"])
            others = [k for k, v in cells.items() if k != q["key"] and close(v) and not right]
        else:
            right = compact(value) == compact(q["value"])
            others = [k for k, v in cells.items() if k != q["key"] and compact(v) == compact(value)]
        if right:
            counts["right"] += 1
        elif others:
            counts["misbound"] += 1
            row, _, col = q["key"].partition("|")
            counts["same_row_or_column"] += any(o.split("|")[0] == row or (col and o.partition("|")[2] == col)
                                                for o in others)
        else:
            counts["misread"] += 1
    return {"score": round(counts["right"] / len(truth["questions"]), 4), "items": len(truth["questions"]), **counts}

def perfect(card, truth):
    """The answer a model that read everything right would give (for tests)."""
    family = card.family
    if family in READING:
        return {"lines": list(truth["lines"])}
    if family == "pairs":
        return {"pairs": [{"name": k, "value": v} for k, v in truth["pairs"].items()]}
    if family == "graph":
        return {"edges": [dict(e) for e in truth["edges"]]}
    return {"answers": [{"n": q["n"], "value": q["value"]} for q in truth["questions"]]}

# --- asking and reporting -----------------------------------------------------------------------

def images(folder, cards):
    """Write each card's image (deterministic bytes) under folder/images; returns {card id: (path, truth, prompt)}."""
    out = {}
    target = Path(folder) / "images"
    target.mkdir(parents=True, exist_ok=True)
    for card in cards:
        png, truth, prompt = render(card)
        path = target / f"{card.id}.png"
        if not path.exists() or path.read_bytes() != png:
            path.write_bytes(png)
        out[card.id] = (path, truth, prompt)
    return out

def ask(folder, client, cards, progress=None):
    """Ask the client's model every card; {card id: answer dict, or {"error": ...}}. Answers are
    recorded by query in the folder's fixture (llm.folder_client), so asking again is free."""
    from semantic_pdf_diff.dispatch import Dispatcher
    from semantic_pdf_diff.progress import NoProgress
    progress = progress or NoProgress()
    drawn, answers = images(folder, cards), {}
    with Dispatcher(client) as dispatch:
        for card in cards:
            path, _, prompt = drawn[card.id]

            def finish(value, error, card=card):
                progress.finish("failed" if error else "complete")
                answers[card.id] = {"error": str(error)[:300]} if error is not None else value.model_dump()
            progress.add()
            dispatch.submit(prompt, SCHEMAS[card.family], [path], ("eyetest", card.id), finish)
        dispatch.drain()
    return answers

def prompt_tokens(folder, responder):
    """{card id: prompt tokens the host reported}, from the folder's fixture (where it reported any)."""
    from semantic_pdf_diff.fixtures import folder_fixture
    fixture = folder_fixture(folder)
    try:
        rows = fixture.db.execute("SELECT r.region, s.usage FROM response s JOIN recipe r ON r.query = s.query "
                                  "WHERE s.responder = ? AND r.role = 'eyetest'", (responder,)).fetchall()
    finally:
        fixture.close()
    out = {}
    for card, usage in rows:
        tokens = json.loads(usage or "{}").get("prompt_tokens")
        if tokens:
            out[card] = tokens
    return out

def results(cards, answers, tokens=None, truths=None):
    """Per-card scores for one model, and its summary. truths: {card id: truth}, if already drawn."""
    per_card = {}
    for card in cards:
        truth = truths[card.id] if truths else render(card, image=False)[1]
        answer = answers.get(card.id)
        if answer is None:
            continue
        entry = {**asdict(card), "id": card.id, "answer": answer,
                 **({"prompt_tokens": tokens[card.id]} if tokens and card.id in tokens else {})}
        if "error" in answer:
            entry["score"] = None
        else:
            entry.update(score(card, truth, answer))
        per_card[card.id] = entry
    return {"cards": per_card, "summary": summarise(per_card.values())}

def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None

def monotone(values):
    """The closest non-decreasing sequence (pool adjacent violators): reading can only get easier as
    glyphs grow, so a dip (one misread glyph at one size) is averaged with its neighbours."""
    blocks = []  # [mean, count]
    for v in values:
        blocks.append([v, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            (m1, n1), (m2, n2) = blocks.pop(), blocks.pop()
            blocks.append([(m1 * n1 + m2 * n2) / (n1 + n2), n1 + n2])
    return [m for m, n in blocks for _ in range(n)]

def threshold(points):
    """The glyph height (px) at which reading reaches PASS, interpolated on the monotone fit of
    points [(glyph, share read)] for one image size. None when even the largest isn't read."""
    points = sorted(points)
    glyphs, shares = [g for g, _ in points], monotone([s for _, s in points])
    for k, (g, s) in enumerate(zip(glyphs, shares)):
        if s >= PASS:
            if k == 0:
                return float(g)
            g0, s0 = glyphs[k - 1], shares[k - 1]
            return round(g0 + (PASS - s0) / (s - s0) * (g - g0), 2)
    return None

def _scored(entry):
    """A card's score; a failed answer (a model looping until its output was cut off) read nothing."""
    return 0.0 if entry.get("score") is None else entry["score"]

def summarise(entries):
    entries = list(entries)
    out = {"families": {}, "acuity": {}, "thresholds": {}, "relative": {}, "failed": sum(1 for e in entries if e.get("score") is None)}
    for family in FAMILIES:
        mine = [e for e in entries if e["family"] == family]
        if not mine:
            continue
        by_glyph = {}
        for e in mine:
            by_glyph.setdefault(e["glyph"], []).append(_scored(e))
        errors = {}
        for e in mine:
            for k, v in e.items():
                if k in ("autocorrected", "confused", "misbound", "misread", "declined", "missed", "reversed", "label_misbound", "label_misread",
                         "ends_wrong", "spurious", "unknown_name", "same_row_or_column") and isinstance(v, int):
                    errors[k] = errors.get(k, 0) + v
        out["families"][family] = {"cards": len(mine), "score": _mean(_scored(e) for e in mine),
                                   "failed": sum(1 for e in mine if e.get("score") is None),
                                   "items": sum(e.get("items", 0) for e in mine), "errors": errors,
                                   "by_glyph": {f"{g:g}": _mean(s) for g, s in sorted(by_glyph.items())}}
    reads = [e for e in entries if e["family"] == "read" and e["font"] == "helv" and e["glyph"] <= LARGE]
    large = {}
    for e in entries:  # the ceiling: reading only gets harder past some size for some models
        if e["family"] == "read" and e["font"] == "helv" and e["glyph"] > LARGE:
            large.setdefault(f"{e['glyph']:g}", []).append(_scored(e))
    out["large"] = {g: _mean(v) for g, v in sorted(large.items(), key=lambda kv: float(kv[0]))}
    for size in sorted({(e["w"], e["h"]) for e in reads}, key=lambda s: (s[0] * s[1], s)):
        cells = {}
        for e in reads:
            if (e["w"], e["h"]) == size:
                cells.setdefault(e["glyph"], []).append(_scored(e))
        means = {g: _mean(s) for g, s in sorted(cells.items())}
        key = f"{size[0]}x{size[1]}"
        out["acuity"][key] = {f"{g:g}": m for g, m in means.items()}
        out["thresholds"][key] = t = threshold([(g, m) for g, m in means.items() if m is not None])
        # Per 1000 px of the image's side (the square root of its area): constant across sizes when the host
        # shrinks every image to a fixed budget (rendering larger gains nothing); falling when it doesn't.
        out["relative"][key] = None if t is None else round(t * 1000 / math.sqrt(size[0] * size[1]), 2)
    # Codes against words against pseudo-words, size by size: the smallest glyph read at 90%.
    out["by_kind"] = {}
    kind_of = lambda e: e["family"] if e["family"] != "pseudo" else f"pseudo-{e.get('layout') or 'close'}"
    for family in ("confusable", "words") + tuple(f"pseudo-{level}" for level in PSEUDO_LEVELS):
        mine = [e for e in entries if e["family"] in ("confusable", "words", "pseudo") and kind_of(e) == family]
        for size in sorted({(e["w"], e["h"]) for e in mine}, key=lambda s: (s[0] * s[1], s)):
            cells = {}
            for e in mine:
                if (e["w"], e["h"]) == size:
                    cells.setdefault(e["glyph"], []).append(_scored(e))
            t = threshold([(g, _mean(v)) for g, v in sorted(cells.items()) if _mean(v) is not None])
            out["by_kind"].setdefault(f"{size[0]}x{size[1]}", {})[family] = t
    for key in out["by_kind"]:
        out["by_kind"][key]["codes"] = out["thresholds"].get(key)
    tokens = {}
    for e in entries:
        if e.get("prompt_tokens") and e["family"] == "read":
            tokens.setdefault(f"{e['w']}x{e['h']}", []).append(e["prompt_tokens"])
    out["prompt_tokens"] = {k: round(sum(v) / len(v)) for k, v in tokens.items()}
    return out

# What every eye test query is asked with (a replay must ask the same queries).
EYE_SETTINGS = {"context_tokens": 131072, "output_tokens": 4000, "image_tokens": 6000}

def responders(folder):
    """The models whose answers the folder's fixture holds."""
    from semantic_pdf_diff.fixtures import folder_fixture
    fixture = folder_fixture(folder)
    try:
        return [r for (r,) in fixture.db.execute("SELECT DISTINCT responder FROM response ORDER BY responder")]
    finally:
        fixture.close()

# --- the page -----------------------------------------------------------------------------------

STYLE = """
body { font:15px/1.45 system-ui, sans-serif; margin:0 auto; max-width:1200px; padding:16px; }
h1 { font-size:22px; } h2 { font-size:18px; margin-top:28px; } h3 { font-size:15px; }
p, li { max-width:75ch; } .muted { color:var(--muted); }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; margin:8px 0 16px; font-variant-numeric:tabular-nums; }
th, td { border:1px solid var(--line); padding:4px 8px; text-align:right; }
th:first-child, td:first-child { text-align:left; }
td.good { color:var(--good); font-weight:600; } td.mid { color:var(--mid); } td.bad { color:var(--bad); }
details { background:var(--card); border:1px solid var(--line); border-radius:6px; margin:8px 0; padding:6px 10px; }
summary { cursor:pointer; }
pre { white-space:pre-wrap; word-break:break-word; font-size:13px; }
img { max-width:100%; height:auto; border:1px solid var(--line); }
"""

def _cell(value):
    import html
    if value is None:
        return '<td class="muted">–</td>'
    kind = "good" if value >= PASS else "mid" if value >= 0.5 else "bad"
    return f'<td class="{kind}">{html.escape(f"{value:.2f}")}</td>'

def page(folder, data):
    """report.html: the models side by side (acuity, thresholds, binding), then every card."""
    from semantic_pdf_diff.html_pages import esc
    models = list(data["models"])
    from semantic_pdf_diff.html_pages import page as html_page
    out = ["<h1>Eye tests for vision models</h1>",
           "<p>Random codes and numbers drawn at known sizes, so every answer is scored exactly and nothing can be "
           "guessed from context. Glyph heights are cap heights in the image's own pixels, before the host resizes "
           f"it. A size is read when {PASS:.0%} of its items are. Suite: {esc(data['suite'])}, {len(data['cards'])} "
           "cards.</p>"]
    out.append("<h2>Overview</h2><div class='scroll'><table><tr><th>Model</th>" +
               "".join(f"<th>{esc(f)}</th>" for f in FAMILIES) + "<th>Failed</th></tr>")
    for m in models:
        s = data["models"][m]["summary"]
        out.append(f"<tr><td>{esc(m)}</td>" + "".join(_cell((s["families"].get(f) or {}).get("score")) for f in FAMILIES)
                   + f"<td>{s['failed']}</td></tr>")
    out.append("</table></div>")
    sizes = list(next(iter(data["models"].values()))["summary"]["thresholds"]) if models else []
    for title, field, note in (
            ("Smallest glyph read, by image size (px)", "thresholds",
             f"Interpolated where reading first holds at {PASS:.0%}; – where even 16 px isn't read."),
            ("The same, per 1000 px of the image's side", "relative",
             "The threshold divided by the square root of the image's area. Constant across sizes: the host shrinks "
             "every image to a fixed budget, so rendering larger gains nothing. Falling as images grow: the model "
             "sees more of a larger image."),
            ("Prompt tokens, as the host reported them", "prompt_tokens",
             "The whole prompt: text and one image. Not every host reports tokens, or counts them the same way.")):
        out.append(f"<h2>{esc(title)}</h2><p class='muted'>{esc(note)}</p><div class='scroll'><table><tr><th>Image</th>"
                   + "".join(f"<th>{esc(m)}</th>" for m in models) + "</tr>")
        for size in sizes:
            values = [data["models"][m]["summary"][field].get(size) for m in models]
            out.append(f"<tr><td>{esc(size)}</td>" + "".join(f"<td>{'–' if v is None else f'{v:g}'}</td>" for v in values)
                       + "</tr>")
        out.append("</table></div>")
    kinds = [(m, data["models"][m]["summary"].get("by_kind", {})) for m in models]
    KINDS = ("codes", "confusable", "words") + tuple(f"pseudo-{level}" for level in PSEUDO_LEVELS)
    sizes_k = sorted({s for _, k in kinds for s in k}, key=lambda s: math.prod(map(int, s.split("x"))))
    if sizes_k:
        out.append("<h2>Codes, words and pseudo-words: smallest glyph read (px)</h2><p class='muted'>Confusable codes "
                   "are made of look-alikes (O/0/D/Q, I/l/1, S/5, B/8, Z/2, G/6/C). Real words have "
                   "shape and meaning. Pseudo-words change one letter: for a look-alike of the same height (close), "
                   "another letter of the same height (profile), or a letter of another height (shape). Lower is "
                   "better; the families table counts pseudo-words read as the word they came from (autocorrected).</p>"
                   "<div class='scroll'><table><tr><th>Image</th>" + "".join(
                       f"<th>{esc(m)}: {k}</th>" for m in models for k in KINDS) + "</tr>")
        for size in sizes_k:
            out.append(f"<tr><td>{esc(size)}</td>" + "".join(
                f"<td>{'–' if k.get(size, {}).get(f) is None else f'{k[size][f]:g}'}</td>"
                for _, k in kinds for f in KINDS) + "</tr>")
        out.append("</table></div>")
    large = sorted({g for m in models for g in data["models"][m]["summary"].get("large", {})}, key=float)
    if large:
        out.append("<h2>Large glyphs (1024 × 1024, share read)</h2><p class='muted'>How far a model may be magnified: "
                   "some read large text worse than small.</p><div class='scroll'><table><tr><th>Glyph</th>" +
                   "".join(f"<th>{esc(m)}</th>" for m in models) + "</tr>")
        for g in large:
            out.append(f"<tr><td>{esc(g)} px</td>" + "".join(_cell(data["models"][m]["summary"].get("large", {}).get(g))
                                                            for m in models) + "</tr>")
        out.append("</table></div>")
    for m in models:
        acuity = data["models"][m]["summary"]["acuity"]
        glyphs = sorted({g for row in acuity.values() for g in row}, key=float)
        out.append(f"<h3>Reading: {esc(m)}</h3><div class='scroll'><table><tr><th>Image</th>" +
                   "".join(f"<th>{esc(g)} px</th>" for g in glyphs) + "</tr>")
        for size, row in acuity.items():
            out.append(f"<tr><td>{esc(size)}</td>" + "".join(_cell(row.get(g)) for g in glyphs) + "</tr>")
        out.append("</table></div>")
    out.append("<h2>Binding</h2>")
    for family in FAMILIES[1:]:
        rows = [(m, data["models"][m]["summary"]["families"].get(family)) for m in models]
        rows = [(m, f) for m, f in rows if f]
        if not rows:
            continue
        glyphs = sorted({g for _, f in rows for g in f["by_glyph"]}, key=float)
        kinds = sorted({k for _, f in rows for k in f["errors"]})
        out.append(f"<h3>{esc(family)}</h3><div class='scroll'><table><tr><th>Model</th>" +
                   "".join(f"<th>{esc(g)} px</th>" for g in glyphs) + "<th>All</th>" +
                   "".join(f"<th>{esc(k)}</th>" for k in kinds) + "</tr>")
        for m, f in rows:
            out.append(f"<tr><td>{esc(m)}</td>" + "".join(_cell(f["by_glyph"].get(g)) for g in glyphs) + _cell(f["score"]) +
                       "".join(f"<td>{f['errors'].get(k, 0)}</td>" for k in kinds) + "</tr>")
        out.append("</table></div>")
    out.append("<h2>Cards</h2><p class='muted'>Images are drawn again by <code>scripts/eye_test.py report</code> "
               "(not kept in git).</p>")
    for family in FAMILIES:
        ids = [i for i, c in data["cards"].items() if c["family"] == family]
        out.append(f"<details><summary>{esc(family)} ({len(ids)} cards)</summary>")
        for i in ids:
            card = data["cards"][i]
            answers = []
            for m in models:
                entry = data["models"][m]["cards"].get(i)
                if entry is None:
                    continue
                scored = "failed" if entry.get("score") is None else f"{entry['score']:.2f}"
                answers.append(f"<p><b>{esc(m)}</b>: {scored}</p><pre>{esc(json.dumps(entry['answer'], ensure_ascii=False))}</pre>")
            out.append(f"<details><summary>{esc(i)}</summary><img loading='lazy' src='images/{esc(i)}.png' alt=''>"
                       f"<p><b>Answer key</b></p><pre>{esc(json.dumps(card['truth'], ensure_ascii=False))}</pre>"
                       + "".join(answers) + "</details>")
        out.append("</details>")
    target = Path(folder) / "report.html"
    target.write_text(html_page("Eye tests", "\n".join(out), STYLE) + "\n", encoding="utf-8")
    return target
