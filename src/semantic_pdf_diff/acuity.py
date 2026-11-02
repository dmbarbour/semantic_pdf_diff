"""How small a model reads: a card a size, five lines of random codes and numbers at one capitals' height each, read
back and scored exactly; the acuity check (checkup.py; docs/plans/endpoint-setup-2026-10-28.md, milestone 5; the
owner, 2026-11-02: "Always test a model that hasn't been tested. If there are calibrations, run those up front.", then,
on one chart's trial: "Go ahead with the per-size probe cards.").

The lab's eye test, its read family (lab/src/semantic_pdf_diff_lab/bench/eyetest.py), at one image size: the square an
image is sent at (image_side). Its items, prompt, pass mark and fit are the lab's, so a measure here reads as the eye
test's threshold (gemma-4 at DeepInfra: 7.0 px at 1024 px square, docs/research/eye-tests-2026-09-30.md).

One chart of every size wasn't a probe: with 24 lines, gemma-4 missed some 16 px lines, and two charts of four
measured nothing (2026-11-02). A long transcription measures attention as much as sight.
"""
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import ConfigDict, Field

from .schema import Lenient

SIZES = (5, 6, 7, 8, 10, 12, 14, 16)  # capitals' heights, px: a card each
LINES = 5    # a card's lines
TOKENS = 8   # a line's codes and numbers, at most: fewer where they don't fit
PASS = 0.9   # a size is read when this share of its items are, in order (the eye test's)
CAP = 0.718  # Helvetica's capitals' height, of its size
LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O or Q, as drawings avoid them
INCHES = ("1/8", "1/4", "3/8", "1/2", "5/8", "3/4", "7/8")

PROMPT = ("The image shows a few lines of codes and numbers. Everything written in it is random: nothing can be "
          "guessed or corrected from context, so read it. Transcribe every line exactly as printed, top to bottom, "
          "keeping the order of the items in each line. Write ? for each character you can't read.\n"
          'Return only JSON: {"lines": ["first line", "second line"]}')

class Lines(Lenient):
    model_config = ConfigDict(coerce_numbers_to_str=True)
    lines: list[str] = Field(default_factory=list, max_length=8 * LINES)  # a line given in parts, at most 8

def code(rng):
    """A random label: "HX-402", "P-17B", "K7Q", "RT58"."""
    kind = rng.random()
    if kind < 0.4:
        return "".join(rng.choices(LETTERS, k=rng.randint(1, 3))) + "-" + str(rng.randint(1, 999)) + \
            (rng.choice(LETTERS) if rng.random() < 0.3 else "")
    if kind < 0.7:
        return rng.choice(LETTERS) + str(rng.randint(0, 9)) + rng.choice(LETTERS)
    return "".join(rng.choices(LETTERS, k=2)) + str(rng.randint(10, 99))

def number(rng):
    """A random value: "4827", "31.6", "0.075", "-12.5", "±0.05", 2'-9 1/2"."""
    kind = rng.random()
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

FOLD = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-", "’": "'", "‘": "'", "′": "'",
                      "“": '"', "”": '"', "″": '"', "×": "x"})

def norm(text):
    """Text as scored: folded before NFKC as well as after, unlike the lab's, since NFKC makes a double prime (″) two
    primes, so an inch mark written so was misread."""
    return " ".join(unicodedata.normalize("NFKC", str(text).translate(FOLD)).translate(FOLD).casefold().split())

def drawn(rng, size, side):
    """(a page, its lines): LINES lines of codes and numbers, half each, their capitals size px tall, placed as a
    block at a random spot on a square side points a side (a point a pixel, at 72 dpi)."""
    import pymupdf
    font = size / CAP
    margin, gap = max(8.0, font), font * 1.6
    room = side - 2 * margin
    lines = []
    for _ in range(LINES):
        tokens = []
        while len(tokens) < TOKENS:
            token = code(rng) if rng.random() < 0.5 else number(rng)
            if pymupdf.get_text_length("   ".join(tokens + [token]), fontname="helv", fontsize=font) > room:
                break
            tokens.append(token)
        lines.append("   ".join(tokens))
    width = max(pymupdf.get_text_length(line, fontname="helv", fontsize=font) for line in lines)
    x = margin + rng.random() * max(0.0, room - width)
    y = margin + rng.random() * max(0.0, side - 2 * margin - gap * LINES)
    doc = pymupdf.open()
    page = doc.new_page(width=side, height=side)
    for k, line in enumerate(lines):
        page.insert_text((x, y + size + k * gap), line, fontname="helv", fontsize=font)
    return page, lines

def card(folder, rng, size, side):
    """(a card's PNG path, its lines): drawn's, on a square side px a side, as large as an image is sent."""
    page, lines = drawn(rng, size, side)
    path = Path(folder) / f"acuity-{size}.png"
    page.get_pixmap(dpi=72, alpha=False).save(path)
    page.parent.close()
    return path, lines

def cards(folder, rng, side):
    """[(capitals' height, a card's PNG path, its lines)], a card a size of SIZES."""
    return [(size, *card(folder, rng, size, side)) for size in SIZES]

def score(lines, answer):
    """The share of a card's items read exactly, in order (the eye test's): answer, the lines read."""
    expected = [norm(t) for line in lines for t in line.split()]
    given = [norm(t) for line in answer for t in str(line).split()]
    matched = sum(b.size for b in SequenceMatcher(None, expected, given, autojunk=False).get_matching_blocks())
    return matched / len(expected)

def monotone(values):
    """The closest non-decreasing sequence (pool adjacent violators): reading can only get easier as glyphs grow, so
    a dip (one misread glyph at one size) is averaged with its neighbours."""
    blocks = []  # [mean, count]
    for v in values:
        blocks.append([v, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            (m1, n1), (m2, n2) = blocks.pop(), blocks.pop()
            blocks.append([(m1 * n1 + m2 * n2) / (n1 + n2), n1 + n2])
    return [m for m, n in blocks for _ in range(n)]

def threshold(points):
    """The capitals' height (px) at which reading reaches PASS, interpolated on the monotone fit of points [(height,
    share read)]; None where even the largest isn't read."""
    points = sorted(points)
    heights, shares = [h for h, _ in points], monotone([s for _, s in points])
    for k, (h, s) in enumerate(zip(heights, shares)):
        if s >= PASS:
            if k == 0:
                return float(h)
            h0, s0 = heights[k - 1], shares[k - 1]
            return round(h0 + (PASS - s0) / (s - s0) * (h - h0), 1)
    return None
