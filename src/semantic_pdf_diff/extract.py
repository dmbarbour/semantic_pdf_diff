import contextlib
import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
import math
import re
import unicodedata
from pathlib import Path
import pymupdf
from .pages import (display_y, lines as _lines, native, native_page, reading_blocks, reading_dict_blocks, shown,
                    shown_by_matrix, shown_point, top_by_matrix)
from .models import DerivationStep, Evidence, Extraction, PdfLocator, Section, Settings, claim_id, merge_occurrences
from .levers import LAYER_NOTE, LOCATOR_NOTE, lever_marks
from .situate import page_figures
from .dispatch import Dispatcher
from .llm import CallLimitReached, NotRecorded
from .progress import NoProgress, log

# Bump when prompt assembly or task construction changes, not only the template text;
# it is part of the extraction interpreter. 2: section heading path in prompts.
# 3: exactly repeated table rows follow their first occurrence. 4: claims per request configurable.
# 5: headings by position on the page; table rows located by their own box.
# 6: rules for unfamiliar charts, attributes free of conditions, parts of a whole; figure tasks.
PROMPT_VERSION = 6

EXTRACT = '''Extract atomic engineering claims from this one source. Return JSON:
{"claims":[{"entity":"component/system", "attribute":"property or directed relationship",
"value":"literal value or target", "unit":"literal unit or empty", "conditions":"load, scenario, time, tolerances, scope",
"kind":"text|table|chart|diagram", "quote":"short exact supporting text or visible labels",
"confidence":0.0, "approximate":false}], "complete":true, "issues":[]}
Maximum {max_claims} claims. Set complete=false if content is clipped, ambiguous, unreadable, or more claims remain.
For tables associate row labels, column headers and units. For charts preserve series, axes, units,
operating point and trend; estimated plotted readings MUST be approximate. For diagrams extract
labeled components and directed connections; never invent direction on unmarked edges.
Preserve negation, requirements versus proposed capabilities, ranges and inequality signs.
Extract evidence only, not commentary. Use a short canonical entity and attribute; keep numeric value separate from unit.
The attribute names the property only: put conditions (e.g. "at theta = 0", "at rated speed") in conditions.
If a value is one of several parts (one layer, one material, one member), say what it is part of in the attribute
(e.g. "spar cap material"), not "composition".
If you are not sure how to read a chart, diagram or drawing convention, say so in issues, lower confidence, and mark
readings approximate; do not guess what an unexplained symbol, colour or line style means.
'''

@dataclass(frozen=True)
class ExtractQuery:
    """An extraction request's text in parts: the one owner of its layout (code review 2026-10-01, A1: prompts were
    assembled inline and parsed back at markers in three places). prompt() is the bytes sent; read() takes a logged
    prompt back into its parts, so no reader splits at markers of its own."""
    instructions: str  # the template with its claim cap filled, then the rules (the configuration's, the region's)
    region: str
    heading: str = ""  # the headings the region falls under
    context: str = ""  # CONTEXT_NOTE and the levers' lines
    data: str = ""     # the source data: text, a table row, or an image task's note and text layer

    def prompt(self):
        return (self.instructions + "\nSource type: " + self.region + (f"\nSection: {self.heading}" if self.heading else "")
                + (f"\n{self.context}" if self.context else "") + "\nSOURCE DATA:\n" + self.data)

    @property
    def request(self):
        """The part after the instructions: what this task, not every task, was given."""
        return self.prompt()[len(self.instructions) + 1:]

    @classmethod
    def read(cls, prompt):
        instructions, _, rest = prompt.partition("\nSource type: ")
        head, _, data = rest.partition("\nSOURCE DATA:\n")
        region, _, tail = head.partition("\n")
        heading = ""
        if tail.startswith("Section: "):
            heading, _, tail = tail[len("Section: "):].partition("\n")
        return cls(instructions, region, heading, tail, data)

def extraction_template(s):
    """The extraction instructions in force: the baseline, or a variant's (with {max_claims} unfilled)."""
    return s.instructions(EXTRACT)

# Numbered markers, from outer to inner: "Contest 9.", "9-2." or "3.1", "c.", "(iii)", "4.".
STEM = re.compile(r"^\s*(Contest \d+\.|\d+-\d+\.|\d+(?:\.\d+)+\.?|[a-z]\.|\((?:[ivx]+|\d+|[a-z])\)\.?|\d+\.)(?=\s|$)")

TITLED = re.compile(r"\s*[-–—:]?\s*[A-Z]")  # a title: a capitalised word, after any dash or colon

def _section(marker):
    """(3, 2, 1) for "3.2.1", or None when the marker isn't digits and dots with at least one inner dot."""
    return tuple(int(n) for n in marker.rstrip(".").split(".")) if re.fullmatch(r"\d+(?:\.\d+)+\.?", marker) else None

def _follows(number, before):
    """Whether section `number` can come next after `before`: its first child (3.2 → 3.2.1), or the next at
    some level, then first children (3.2.1 → 3.2.2, 3.3, 4.1; a first child may be numbered 0 or 1)."""
    return any(number[:k] == before[:k] and number[k] == before[k] + 1 and all(n in (0, 1) for n in number[k + 1:])
               for k in range(min(len(number), len(before)))) or (
        len(number) == len(before) + 1 and number[:-1] == before and number[-1] in (0, 1))

def _numbered(marker, title, styled=False, before=()):
    """Whether digits and dots ("3.2", "12.") start a numbered item with this title, rather than being
    a value in a table ("3.83 -43.73E+6", "0.6 s", "1.35 Partial safety factor"), where the next cell
    would become the item's "title". A list item ("4.") takes any word. A section number takes a
    capitalised title, never starts at 0, and is set as a heading (`styled`) or follows one of the
    section numbers `before` (the ones it sits under, and the last one seen). Other markers ("c.",
    "(ii)") always count."""
    number = _section(marker)
    if number is None:
        return not re.fullmatch(r"\d+\.", marker) or bool(re.match(r"\s*[-–—:]?\s*[^\W\d_]", title))
    return (number[0] > 0 and bool(TITLED.match(title))
            and (styled or any(_follows(number, b) for b in before)))

def _stem_level(marker):
    if marker.startswith("Contest"):
        return 0
    if re.match(r"\d+-\d+\.|\d+(\.\d+)+", marker):
        return 1
    if re.match(r"[a-z]\.", marker):
        return 2
    return 3 if marker.startswith("(") else 4

def stem_index(doc):
    """{page: [(displayed y, parents)]}: for each line, the numbered items and headings it sits
    under (research round 1), so a list item keeps its parents across page breaks. Lines that
    repeat at the same height on most pages (headers, footers) are skipped."""
    from collections import Counter
    def key(line):
        return re.sub(r"\d+", "#", "".join(s["text"] for s in line["spans"]).strip()), round(line["bbox"][1] / 5)
    pages = [reading_dict_blocks(page) for page in doc]
    seen, sizes = Counter(), Counter()
    for blocks in pages:
        keys = set()
        for block in blocks:
            for line in block.get("lines", ()):
                keys.add(key(line))
                for span in line["spans"]:
                    sizes[round(span["size"])] += len(span["text"])
        seen.update(keys)
    margins = {k for k, n in seen.items() if n >= max(2, len(doc) // 2) and k[0]}
    body = sizes.most_common(1)[0][0] if sizes else 10
    stack, pending, last, index = [], None, None, {}
    def push(level, marker, title):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, marker, title))
    for number, (page, blocks) in enumerate(zip(doc, pages), 1):
        rows = index.setdefault(number, [])
        for block in blocks:
            for line in block.get("lines", ()):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text or key(line) in margins:
                    continue
                first = line["spans"][0]
                heading = (first["size"] > body + 0.5 or (first["flags"] & 16 and len(text) < 60)) and len(text) < 90
                styled = heading and first["size"] > body - 0.5  # not a chart's axis labels
                before = [n for n in (*(_section(m) for _, m, _ in stack), last) if n]
                match = STEM.match(text)
                if match and text[match.end():].strip():
                    if not _numbered(match.group(1), text[match.end():], styled, before):
                        match = None
                    last = _section(STEM.match(text).group(1)) or last
                if pending is not None and _numbered(pending[1], text, pending[2] or styled, before):
                    # A marker alone on its line opens its item once the next line shows it's one: a title
                    # ("3.2.2" / "Insulation Analysis"). A lone value ("23.47" / "-125.30E+6") closes nothing.
                    push(pending[0], pending[1], "" if match else text)
                pending = None
                if match:
                    level = _stem_level(match.group(1))
                    level = 1 if heading and level > 1 else level
                    rest = text[match.end():].strip()
                    if rest:
                        push(level, match.group(1), rest)
                    else:
                        pending = (level, match.group(1), styled)
                        last = _section(match.group(1)) or last
                rows.append((display_y(page, line["bbox"]), [f"{m} {t[:70]}".strip() for _, m, t in stack]))
    return index

SHORT_FORM = re.compile(r"\(([A-Za-z][A-Za-z0-9&/.-]{1,9})\)")

def _long_form(short, before):
    """The words before "(short)" that spell it out (Schwartz and Hearst, 2003): the short
    form's letters are matched right to left, its first letter at a word's start; None if none."""
    words = before.split()[-min(len(short) + 5, 2 * len(short)):]
    text = " ".join(words)
    letters = [c.lower() for c in short if c.isalnum()]
    i = len(text) - 1
    for k in range(len(letters) - 1, -1, -1):
        while i >= 0 and (text[i].lower() != letters[k] or (k == 0 and i > 0 and text[i - 1].isalnum())):
            i -= 1
        if i < 0:
            return None
        i -= 1
    found = text[text.rfind(" ", 0, i + 1) + 1:].strip(" ,;:")
    return found if len(found) > len(short) and short.lower() not in found.lower() else None

def glossary(doc):
    """{abbreviation: long form} for "long form (ABBR)" anywhere in the document (first one wins)."""
    out = {}
    for page in doc:
        text = " ".join(page.get_text("text").split())
        for match in SHORT_FORM.finditer(text):
            short = match.group(1).rstrip(".")
            if short in out or not any(c.isupper() for c in short) or short.isdigit():
                continue
            found = _long_form(short, text[max(0, match.start() - 200):match.start()])
            if found:
                out[short] = found
    return out

MAX_REFERENCES = 3  # definitions, and cited figures or tables, added per chunk

def references(text, terms, figures):
    """Context lines for what a chunk cites but doesn't hold: abbreviations defined elsewhere in
    the document, and the captions of the figures and tables it mentions (research round 1)."""
    from .situate import MENTION, label_key, label_of, targets
    lines = []
    defined = [f"{short} = {long}" for short, long in terms.items()
               if f"({short})" not in text and re.search(rf"\b{re.escape(short)}s?\b", text)]
    if defined:
        lines.append("Defined elsewhere: " + "; ".join(defined[:MAX_REFERENCES]))
    by_label = {}
    for figure in figures:
        if figure.label:
            by_label.setdefault(label_key(figure.label), []).append(figure)
    cited = []
    for match in MENTION.finditer(text):
        label = label_of(*match.groups())
        found = targets(by_label, label)
        name = label[0].upper() + label[1:]
        if found and found[0].caption and found[0].caption[:60] not in " ".join(text.split()):
            entry = f"{found[0].caption[:150]} (page {found[0].page})"
        elif found:
            continue  # the chunk is the caption, or the figure has none
        else:
            entry = f"{name}: not found in this document"
        if entry not in cited:
            cited.append(entry)
    if cited:
        lines.append("Cited: " + "; ".join(cited[:MAX_REFERENCES]))
    return "\n".join(lines)

CONTEXT_NOTE = "CONTEXT (for reference only: do not extract claims from it):"

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

FOLD = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-", "’": "'", "‘": "'", "“": '"',
                      "”": '"', "·": "•", "∙": "•", "×": "x"})
ELLIPSIS = re.compile(r"\s*(?:\.\s?\.\s?\.|…|\s\|\s)\s*")  # "a ... b", and table cells "a | b"

LINE_HYPHEN = re.compile(r"(\w)-\s+(?=\w)")  # "linear-\nspring": a compound broken at a line end

def _folded(text):
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "").translate(FOLD)
    return " ".join(LINE_HYPHEN.sub(r"\1-", text).casefold().split())

def excerpted(quote, text, in_order=True):
    """The quote is excerpts of text: its parts between ellipses ("...", "…") or cell bars
    (" | ") each appear in order, up to case, whitespace, Unicode forms, line-end hyphenation
    ("linear-\nspring") and dash, quote-mark and bullet variants; with in_order, a part may also
    be words read in order across a pseudo-table (a header and its value), within about three
    times its length (round 9: that window let chart-axis labels through as values).
    A third of text claims were rejected by the verbatim check for such quotes (overall review,
    2026-09-28); paraphrases and quotes from the context still fail."""
    parts = [p for p in (_folded(p) for p in ELLIPSIS.split(quote)) if p]
    if not parts:
        return False
    haystack, at = _folded(text), 0
    for part in parts:
        found = haystack.find(part, at)
        end = found + len(part) if found >= 0 else (_in_order(part.split(), haystack, at, 3 * len(part) + 40)
                                                     if in_order else None)
        if end is None:
            return False
        at = end
    return True

def _in_order(words, haystack, start, span):
    """End of the first place after `start` where the words appear in order within `span`
    characters (a row header and its value read across a pseudo-table), or None."""
    begin = haystack.find(words[0], start)
    while begin >= 0:
        at = begin + len(words[0])
        for word in words[1:]:
            at = haystack.find(word, at)
            if at < 0 or at - begin > span:
                break
            at += len(word)
        else:
            return at
        begin = haystack.find(words[0], begin + 1)
    return None

def covered(quote, text, fold=False):
    """Every word of the quote occurs in text; tolerates quotes spanning table cells."""
    words = terms(quote, fold)
    return bool(words) and words <= terms(text, fold)

from .segmentation import (FIGURE_PAD, SCALE, _empty, _graphics, bands, grown, sheet_details,  # noqa: F401
                           tiles)

LOCATOR_SIDE = 384  # pixels: the page thumbnail that shows where a tile sits

class Context:
    """A document's reader for the context levers (levers.py: text_lines, table_lines, tile_lines, tile_images):
    the caches and document access their hooks share. A query's context is CONTEXT_NOTE followed by the lines
    the configuration's levers give, in their order. What a lever added is found again by its marks
    (lever_notes). The reader works on the page as displayed (see pages), so rotated sheets read like upright
    ones."""

    def __init__(self, doc, s, assets=None, stem=""):
        self.doc, self.s = doc, s
        self.assets, self.stem = assets, stem  # where the locator's images go, and their names' stem
        self.blocks, self.stems, self.cited_by, self.page_lines = {}, {}, {}, {}
        self.tables_on = {}  # page -> the boxes of its tables (a row's lead-in is above its whole table)

    @staticmethod
    def compose(lines):
        lines = [line for line in lines if line]
        return (CONTEXT_NOTE + "\n" + "\n".join(lines)) if lines else ""

    def for_text(self, page_no, segments, text):
        return self.compose(self.s.text_lines(self, page_no, segments, text))

    def for_table(self, page_no, bbox, flat):
        return self.compose(self.s.table_lines(self, page_no, self.table_top(page_no, bbox), flat))

    def for_tile(self, page, rect, tag):
        """(context, extra images) for an image task."""
        return self.compose(self.s.tile_lines(self, page, rect, tag)), tuple(self.s.tile_images(self, page, rect, tag))

    # --- what the hooks read

    @property
    def pages(self):
        return len(self.doc)

    def lines(self, page):
        """A page's text lines as displayed (pages.lines), once per page: the segmentation hooks share them."""
        if page.number not in self.page_lines:
            self.page_lines[page.number] = _lines(page)
        return self.page_lines[page.number]

    def figures(self, page, number):
        """The page's detected figures (situate.page_figures)."""
        return page_figures(page, number)

    def page_blocks(self, page_no):
        """The page's text blocks in reading order: [(bbox, text)]."""
        if page_no not in self.blocks:
            self.blocks[page_no] = [(tuple(b[:4]), " ".join(b[4].split())) for b in reading_blocks(self.doc[page_no - 1])
                                    if b[6] == 0 and b[4].strip()]
        return self.blocks[page_no]

    def table_top(self, page_no, row_box):
        for box in self.tables_on.get(page_no, ()):
            if pymupdf.Rect(row_box) in pymupdf.Rect(box) + (-2, -2, 2, 2):
                return box
        return row_box

    def text_above(self, page_no, bbox):
        """The text of the blocks just above a box (a table's lead-in sentence or caption), as displayed."""
        page = self.doc[page_no - 1]
        table = shown(page, bbox)  # as displayed (rotated sheets)
        return " ".join(t for b, t in self.page_blocks(page_no)
                        if shown(page, b).y1 <= table.y0 + 2 and shown(page, b).x1 > table.x0 and shown(page, b).x0 < table.x1)

    def stem_path(self, page_no, bbox):
        """The numbered items and headings a region sits under, e.g. ['9-2. Cooking', 'c. ...'] (also
        what judges are told a unit sits under)."""
        if not self.stems:
            self.stems.update(stem_index(self.doc))
        top = display_y(self.doc[page_no - 1], bbox)
        for number in range(page_no, 0, -1):  # the last line above it, on this page or earlier ones
            above = [p for y, p in self.stems.get(number, []) if number < page_no or y < top - 1]
            if above:
                return above[-1]
        return []

    def cited(self, text):
        """Abbreviations defined elsewhere and the captions of figures and tables the text cites, as one line."""
        if not self.cited_by:
            self.cited_by.update(terms=glossary(self.doc),
                                 figures=[f for n, page in enumerate(self.doc, 1) for f in page_figures(page, n)])
        return references(text, self.cited_by["terms"], self.cited_by["figures"])

    def locator(self, page, rect, tag):
        """The whole page, small, with the region outlined: rendered once into the store, its path returned."""
        where = f"{self.stem}-{tag.replace(':', '-')}-where.png"
        render_locator(page, rect, self.assets / where)
        return "assets/" + where

# What each lever added to a query, found by the lines its builder writes (the levers' marks). For
# diagnostics only (the queries dump, docs/plans/content-addressed-queries-2026-09-28.md): a query is found by
# its hash, never by these. tests/test_sections.py checks each builder against its mark.
LEVER_MARKS = lever_marks(Settings)

def lever_notes(prompt):
    """{lever: what it added (shortened)} for the levers whose lines a query's text holds."""
    notes = {}
    for lever, mark in LEVER_MARKS:
        found = [m.group(1).strip() for m in mark.finditer(prompt)]
        if found:
            joined = " | ".join(found)
            notes[lever] = joined if len(joined) <= 240 else joined[:237] + "..."
    return notes

def render_locator(page, rect, target, side=LOCATOR_SIDE, width=3):
    """The whole page, small, with rect (displayed coordinates) outlined in red."""
    scale = side / max(page.rect.width, page.rect.height)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
    box = (rect * pymupdf.Matrix(scale, scale)).irect & pix.irect
    for edge in (pymupdf.IRect(box.x0, box.y0, box.x1, box.y0 + width), pymupdf.IRect(box.x0, box.y1 - width, box.x1, box.y1),
                 pymupdf.IRect(box.x0, box.y0, box.x0 + width, box.y1), pymupdf.IRect(box.x1 - width, box.y0, box.x1, box.y1)):
        pix.set_rect(edge & pix.irect, (255, 0, 0))
    pix.save(target)

def render(page, rect, target, max_side):
    # clip is in rotated page coordinates, as used by Page.get_pixmap.
    scale = min(2.5, max_side / max(rect.width, rect.height))
    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False).save(target)

def same_form(row, header):
    """True if a row matches most non-empty cells of a header, position by position."""
    pairs = [(a, b) for a, b in zip(row, header) if a not in (None, "") or b not in (None, "")]
    return bool(pairs) and sum(a == b for a, b in pairs) / len(pairs) >= 0.5

def text_pieces(page, text_bytes):
    pieces = []
    for bi, block in enumerate(reading_blocks(page)):
        if block[6] != 0:
            continue
        for ci, chunk in enumerate(split_utf8(block[4].strip(), text_bytes)):
            if chunk.strip():
                pieces.append((f"{bi}.{ci}", tuple(block[:4]), chunk))
    return pieces

def text_groups(page, text_bytes, section_of=None):
    """Consecutive text blocks grouped up to the byte budget (oversized blocks split),
    never across a section boundary (section_of(bbox) names a block's section).

    Returns [(ids, [(bbox, text)])], where ids like '3.0-5.0' name the blocks grouped.
    """
    pieces = text_pieces(page, text_bytes)
    part = section_of or (lambda bbox: None)
    groups, group, size = [], [], 0
    for piece in pieces + [None]:
        extra = len(piece[2].encode()) + 2 if piece else 0
        if group and (piece is None or size + extra > text_bytes or part(piece[1]) != part(group[-1][1])):
            ids = group[0][0] + (f"-{group[-1][0]}" if len(group) > 1 else "")
            groups.append((ids, [(b, t) for _, b, t in group]))
            group, size = [], 0
        if piece:
            group.append(piece)
            size += extra
    return groups

UNIT = re.compile(r"\d\s?(?:[kMG]?W|kWh|[kM]?Pa|bar|psi|mm|cm|km|m²|m2|m³|m3|kg|L/s|l/s|L/min|°C|°F|K|%|Hz|kV|V|kVA|A|rpm|dB)\b")
REQUIREMENT = re.compile(r"\b(?:shall|must|required|requirement)\b", re.IGNORECASE)

def page_signals(page, tables):
    """Cheap triage signals for one page; summed per section."""
    text = page.get_text("text")
    drawings = page.get_cdrawings() if hasattr(page, "get_cdrawings") else page.get_drawings()
    return {"numbers": len(re.findall(r"\d+(?:[.,]\d+)?", text)), "units": len(UNIT.findall(text)),
            "requirements": len(REQUIREMENT.findall(text)), "tables": tables, "images": len(page.get_images()),
            "drawings": len(drawings), "characters": len(text.strip())}

def union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

HEADING_GAP = 40.0  # an outline entry this close above the next one is only its parent heading

def _squash(text):
    return re.sub(r"[\W_]+", "", text).casefold()

def heading_y(page, title):
    """Where an outline title sits on its page (unrotated y), or 0 when it can't be found.

    Outline destinations are often just the top of the page, so the title's own text line
    is looked for instead."""
    want = _squash(title)
    if len(want) < 3:
        return 0.0
    top = lambda bbox: display_y(page, bbox)
    for block in page.get_text("dict")["blocks"]:
        lines = block.get("lines", ())
        # A heading may be split across lines ("9-2." and "Cooking"), or begin a block.
        joined = "".join(_squash("".join(span["text"] for span in line["spans"])) for line in lines)
        if joined and joined.startswith(want):
            return top(block["bbox"])
        for line in lines:
            text = _squash("".join(span["text"] for span in line["spans"]))
            # A line may hold most of a long title, but a fragment such as a sheet number isn't the title.
            if len(text) >= 3 and (text.startswith(want) or (want.startswith(text) and len(text) >= 0.6 * len(want))):
                return top(line["bbox"])
    return 0.0

class SectionIndex:
    """Which section a point in the document belongs to: the last one starting at or above it.

    index[page] is the section at the top of a page (used for per-page signals)."""

    def __init__(self, sections, doc=None):
        self.sections = sorted(sections, key=lambda s: (s.first_page, s.first_y))
        # Positions are as displayed; boxes are unrotated, so rotated pages need converting.
        self.rotations = {n: page.rotation_matrix for n, page in enumerate(doc, 1) if page.rotation} if doc else {}

    def top(self, page, bbox):
        return top_by_matrix(self.rotations.get(page), bbox)

    def box(self, page, bbox):
        """The section a box (unrotated coordinates) starts in."""
        return self.at(page, self.top(page, bbox))

    def spanned_box(self, page, bbox):
        matrix = self.rotations.get(page)
        box = shown_by_matrix(matrix, bbox)
        return self.spanned(page, box.y0, box.y1)

    def at(self, page, y=0.0):
        if not self.sections:
            return None
        found = self.sections[0]
        for section in self.sections:
            if (section.first_page, section.first_y) <= (page, y + 0.5):
                found = section
            else:
                break
        return found

    def __getitem__(self, page):
        return self.at(page, 0.0)

    def spanned(self, page, y0, y1):
        """Sections a region of a page overlaps, top first."""
        found = [self.at(page, y0)]
        found += [s for s in self.sections if s.first_page == page and y0 < s.first_y < y1 and s not in found]
        return [s for s in found if s is not None]

    def boundaries(self, page):
        """y positions on a page where a new section starts."""
        return [s.first_y for s in self.sections if s.first_page == page and s.first_y > 0]

def real_table(page, table, rows):
    """Whether a detected table looks like a table, not a chart's gridlines, a drawing sheet's
    frame or paragraphs in boxes (docs/research/round-01): at least half its cells filled, few
    words straddling cell edges, 2+ rows and columns, 6+ words, under half the page, and not
    mostly long paragraphs. On the samples this kept 4 of 4 real tables and dropped 70 of 70 others."""
    cells = [c for row in rows for c in row]
    if len(rows) < 2 or max((len(r) for r in rows), default=0) < 2 or not cells:
        return False
    filled = [str(c).strip() for c in cells if c is not None and str(c).strip()]
    if len(filled) / len(cells) < 0.5 or sum(len(c.split()) for c in filled) < 6:
        return False
    if sum(len(c) > 80 for c in filled) > 0.3 * len(filled):
        return False
    box = pymupdf.Rect(table.bbox)
    if abs(box) > 0.5 * abs(page.rect):
        return False
    edges = [pymupdf.Rect(c) for c in getattr(table, "cells", None) or [] if c]
    if edges:
        words = [shown(page, w[:4]) for w in page.get_text("words")]
        words = [w for w in words if w.intersects(box) and w.width > 0]
        split = sum(1 for w in words if any(0.15 < abs(w & c) / abs(w) < 0.85 for c in edges if w.intersects(c)))
        if words and split / len(words) > 0.05:
            return False
    return True

def row_boxes(table, extracted):
    """Each row's box (None where unknown), aligned with the extracted rows; [] if they don't align."""
    rows = getattr(table, "rows", None) or []
    boxes = [tuple(r.bbox) if getattr(r, "bbox", None) else None for r in rows]
    return boxes if len(boxes) == len(extracted) else []

def pdf_sections(doc, depth, pages_per_section):
    """Sections from the outline down to `depth`, else fixed page ranges.

    Returns (sections, SectionIndex). An outline section runs from its title's position
    (see heading_y) to the next title's, so one page can end one section and start the
    next. A title directly followed by the next one (a parent heading and its first
    child) gets no section of its own; the child's heading path includes it.
    """
    count = len(doc)
    path, starts = [], []
    for level, title, page in doc.get_toc(simple=True):
        if level > depth:
            continue
        path = path[:level - 1] + [" ".join(str(title).split())]
        if 1 <= page <= count:
            starts.append((page, heading_y(doc[page - 1], str(title)), list(path)))
    if starts:
        # Keep outline order: an entry can't start above the one before it on the same page
        # (a title that wasn't found takes its predecessor's position).
        for i in range(1, len(starts)):
            page, y, heading = starts[i]
            if page == starts[i - 1][0] and y < starts[i - 1][1]:
                starts[i] = (page, starts[i - 1][1], heading)
        starts.sort(key=lambda s: s[0])  # stable: outline order within a page
        kept = []
        for start in starts:
            if kept and kept[-1][0] == start[0] and start[1] - kept[-1][1] < HEADING_GAP:
                kept.pop()  # nothing of its own between it and the next title
            kept.append(start)
        if kept[0][0] > 1 or _content_above(doc, kept[0][0], kept[0][1]):
            kept.insert(0, (1, 0.0, []))  # front matter before the first title
        fields = []
        for i, (page, y, heading) in enumerate(kept):
            if i + 1 < len(kept):
                next_page, next_y, _ = kept[i + 1]
                if next_y > 0 and _content_above(doc, next_page, next_y):
                    last_page, last_y = next_page, next_y
                else:
                    last_page, last_y = max(page, next_page - 1), None
            else:
                last_page, last_y = count, None
            fields.append({"first_page": page, "first_y": y, "last_page": last_page, "last_y": last_y,
                           "heading_path": heading})
        sections = [Section(id=f"sec{i}", origin="outline", **f) for i, f in enumerate(fields, 1)]
    else:
        sections = [Section(id=f"sec{i}", origin="pages", first_page=first, last_page=min(count, first + pages_per_section - 1))
                    for i, first in enumerate(range(1, count + 1, pages_per_section), 1)]
    return sections, SectionIndex(sections, doc)

def _content_above(doc, page, y):
    """Whether any text on a page sits above y (displayed), else a section starting at y starts the page."""
    p = doc[page - 1]
    return y > 0 and any(b[6] == 0 and b[4].strip() and shown(p, b[:4]).y1 <= y + 1
                         for b in p.get_text("blocks"))

def section_text(doc, section):
    """A section's text, clipped to where it starts and ends on its first and last pages."""
    import pymupdf
    parts = []
    for number in range(section.first_page, section.last_page + 1):
        page = doc[number - 1]
        area = page.rect  # section positions are as displayed
        top = section.first_y if number == section.first_page else area.y0
        bottom = section.last_y if number == section.last_page and section.last_y is not None else area.y1
        if bottom <= top:
            continue
        # a clip is in the page's unrotated coordinates: on a sheet stored sideways, the displayed band differs
        parts.append(page.get_text("text", clip=native(page, pymupdf.Rect(area.x0, top - 1, area.x1, bottom - 1))))
    return "\n".join(parts)

# How each extraction pass gets from PDF bytes to a claim.
DERIVATION = {
    "text": [DerivationStep(step="pdf-text-layer", detail="grouped text blocks"), DerivationStep(step="model-extraction")],
    "table": [DerivationStep(step="pdf-table-detection", detail="row with provisional header"), DerivationStep(step="model-extraction")],
    "tile": [DerivationStep(step="pdf-render", detail="page tile"), DerivationStep(step="model-extraction", detail="vision")],
    "figure": [DerivationStep(step="pdf-render", detail="detected figure with its caption"),
               DerivationStep(step="model-extraction", detail="vision")],
    "overview": [DerivationStep(step="pdf-render", detail="whole page"), DerivationStep(step="model-extraction", detail="vision")],
}

@dataclass
class Job:
    """Extraction of one PDF content item, fed a page at a time by run_jobs."""
    content: str
    load: object                     # () -> path or bytes, called when the job starts
    on_task: object = None           # (row, evidence) as each task finishes
    on_sections: object = None       # (sections) once known
    on_done: object = None           # (evidence, coverage) when the job is complete
    state: dict = field(default_factory=lambda: {"pending": 0, "result": None})
    steps: object = None

def run_jobs(queues, output, client, dispatcher=None, progress=None):
    """Run extraction jobs with fair share: one queue per source, pages fed round-robin
    across sources so compared sources advance together.

    Model requests run on the dispatcher's worker threads; everything else here. A job
    whose pages are all fed keeps its document open until its own pending requests
    (which may queue refinement) finish, while its source moves on to the next job.
    """
    own = dispatcher is None
    dispatch = dispatcher or Dispatcher(client)
    # Pages are fed only while few requests are pending, so prepared requests
    # (which hold image data) stay bounded however large the documents.
    bound = max(4, 2 * dispatch.workers)
    queues = [deque(q) for q in queues]
    active, draining = [None] * len(queues), []

    def done(job):
        if job.on_done:
            job.on_done(*job.state["result"])

    with (dispatch if own else contextlib.nullcontext()):
        while True:
            fed = False
            for i, queue in enumerate(queues):
                # Each source feeds one page per turn; a job that has run out of pages
                # hands over to the source's next job within the same turn.
                while True:
                    if active[i] is None and queue:
                        job = queue.popleft()
                        job.steps = _pdf_job(job.load(), job, output, client, dispatch, progress or NoProgress())
                        active[i] = job
                    job = active[i]
                    if job is None:
                        break
                    while dispatch.pending() >= bound:
                        dispatch.wait_one()
                    step = next(job.steps, "done")
                    fed = True
                    if step == "page":
                        break
                    active[i] = None
                    if step == "waiting":
                        draining.append(job)
                    else:
                        done(job)
            for job in list(draining):
                if job.state["pending"] == 0 and next(job.steps, "done") == "done":
                    draining.remove(job)
                    done(job)
            if not fed:
                if not draining and not any(queues) and not any(active):
                    break
                if not dispatch.pending():
                    raise RuntimeError("extraction scheduler stalled: jobs wait on requests that aren't pending")
                dispatch.wait_one()

def extract_pdf(path, content, output, client, on_task=None, on_sections=None, dispatcher=None, progress=None):
    """Extract evidence from one PDF (a path or its bytes), identified by its content ID.

    Returns (evidence, coverage), both independent of the order in which tasks finish.
    on_task(row, evidence) is called as each task finishes, so a store can persist
    results task by task; on_sections(sections) is called once sections are known.
    """
    job = Job(content, lambda: path, on_task, on_sections)
    run_jobs([[job]], output, client, dispatcher, progress)
    return job.state["result"]

def _pdf_job(path, job, output, client, dispatch, progress):
    """Generator doing one PDF's extraction: yields "page" before feeding each page, then
    "waiting" while its requests are pending; job.state["result"] is set at the end."""
    content, on_task, on_sections, state = job.content, job.on_task, job.on_sections, job.state
    s = client.s
    evidence, coverage = [], []
    stem = content.split(":", 1)[1][:12]
    assets = output / "assets"
    assets.mkdir(exist_ok=True, parents=True)
    page_section = None  # a SectionIndex once the document is open

    def record(row, items=()):
        coverage.append(row)
        if on_task:
            on_task(row, list(items))

    repeats = {}

    def follow(entry, page_no, bbox, task, region):
        """Record a repeated block from its first occurrence's result, without a model call."""
        note = f"identical to {entry['task']} on page {entry['page']}; not re-sent"
        step = DerivationStep(step="repeated-block", detail=note)
        section = page_section.box(page_no, bbox)
        copies = [e.model_copy(update={"locator": PdfLocator(page=page_no, bbox=tuple(bbox), region=region, task=task),
                                       "section": section.id, "derivation": [*e.derivation, step]})
                  for e in entry["found"]]
        row = {"content": content, "page": page_no, "bbox": list(bbox), "task": task, "image": None,
               "status": entry["row"]["status"], "issues": [note], "claims": len(copies), "duplicate_of": entry["task"]}
        evidence.extend(copies)
        record(row, copies)

    def consume(page_no, bbox, task, text, image=None, check=None, locate=None, crop=None, derivation=None, then=None,
                repeat_key=None, repeat_after=1, place=None, context="", extra_images=()):
        """Queue one extraction task; when it finishes, record it and call then(status).

        repeat_key identifies exactly repeated boilerplate: once `repeat_after` earlier
        sightings prove the repetition, the task follows the first occurrence's result
        instead of calling the model (or is extracted normally if that one failed).

        check(quote) -> bool | None. Native tasks reject claims failing it; visual tasks
        only record the result. locate(quote) narrows a claim's bbox within the task.
        place(quote) -> box or None: where a visual claim's quote sits, to find its section.
        Each claim found becomes one occurrence; sightings of the same claim by other
        tasks are merged into one piece of evidence afterwards (union provenance).
        """
        region = task.split(":")[0]
        entry = None
        if repeat_key is not None and s.dedupes_repeated_rows():
            entry = repeats.setdefault(repeat_key, {"task": task, "page": page_no, "seen": 0, "done": False,
                                                    "ok": False, "found": [], "row": None, "followers": []})
            entry["seen"] += 1
            if entry["task"] != task and entry["seen"] - 1 >= repeat_after:
                again = lambda: consume(page_no, bbox, task, text, image, check, locate, crop, derivation, then,
                                        place=place, context=context, extra_images=extra_images)
                if not entry["done"]:
                    entry["followers"].append((lambda: follow(entry, page_no, bbox, task, region), again))
                elif entry["ok"]:
                    follow(entry, page_no, bbox, task, region)
                else:
                    again()
                return
            if entry["task"] != task:
                entry = None  # an early sighting, extracted normally before repetition is proven
        found = []
        row = {"content": content, "page": page_no, "bbox": list(bbox), "task": task,
               "image": image, "status": "complete", "issues": [], "claims": 0}
        images = ([output / image] if image else []) + [output / x for x in extra_images]
        section = page_section.box(page_no, bbox)  # the heading above the region, not the page's
        # A region spanning sections (a tile, an overview) is told all their headings.
        heading = " | ".join(" > ".join(x.heading_path) for x in page_section.spanned_box(page_no, bbox)
                             if x.heading_path)
        rules = s.region_rules(region)
        prompt = ExtractQuery(extraction_template(s).replace("{max_claims}", str(s.claims_per_request)) + rules,
                              region, heading, context, text).prompt()
        key = ("extract", region, content, task, hashlib.sha256(text.encode()).hexdigest(), crop, heading)
        if context:  # only then, so requests without context keep their recorded keys
            key += (hashlib.sha256(context.encode()).hexdigest(),)
        if rules:  # image-task rules aren't in the interpreter's prompt hash (text tasks keep replaying),
            key += ("visual rules", hashlib.sha256(rules.encode()).hexdigest())  # so they're in the key

        def finish(result, error):
            state["pending"] -= 1
            if error is not None:
                # not reached: the call limit, the cost cap, or an answer a replay doesn't hold. Nothing was learnt,
                # so it isn't refined; the next run asks it again.
                unreached = isinstance(error, (CallLimitReached, NotRecorded))
                row.update(status="not_reached" if unreached else "failed", issues=[str(error)])
            else:
                handle(result)
            evidence.extend(found)
            record(row, found)
            progress.finish(row["status"])
            if entry is not None:  # the first occurrence of a repeated block: release its followers
                entry.update(done=True, ok=row["status"] in ("complete", "partial"), found=list(found), row=row)
                for followed, again in entry.pop("followers"):
                    followed() if entry["ok"] else again()
                entry["followers"] = []
            log.debug("%s %s: %s, %d claim(s)%s", Path(name).name, task, row["status"], row["claims"],
                      f" ({'; '.join(row['issues'])[:200]})" if row["issues"] else "")
            if then:
                then(row["status"])

        def handle(result):
            row["status"] = "complete" if result.complete else "partial"
            row["issues"] = list(result.issues)
            for claim in result.claims:
                verified = check(claim.quote) if check else None
                if not image and not verified:
                    row["status"] = "partial"
                    row["issues"].append("Rejected claim with unsupported literal quote")
                    continue
                eid = claim_id(content, claim)
                if any(e.id == eid for e in found):
                    continue  # the same claim twice in one response: keep the first
                where = tuple(locate(claim.quote) if locate else bbox)
                spot = place(claim.quote) if place else where
                home = page_section.box(page_no, spot).id if spot is not None else section.id
                found.append(Evidence(**claim.model_dump(), id=eid, content=content, section=home,
                                      locator=PdfLocator(page=page_no, bbox=where, region=region, task=task),
                                      derivation=derivation or DERIVATION[region], image=image, quote_verified=verified))
                row["claims"] += 1

        progress.add()
        state["pending"] += 1
        dispatch.submit(prompt, Extraction, images, key, finish)

    def text_task(page_no, segments, task, depth=0):
        """segments: [(bbox, text)] of consecutive blocks sent together."""
        text = "\n\n".join(t for _, t in segments)
        context = context_of.for_text(page_no, segments, text)
        def locate(quote):
            return next((b for b, t in segments if quoted(quote, t)), union(b for b, _ in segments))
        match = lambda q: quoted(q, text) or s.loose_match(q, text)
        consume(page_no, union(b for b, _ in segments), task, text, check=match, locate=locate,
                context=context,
                then=lambda status: refine_text(page_no, segments, text, task, depth, status))

    def refine_text(page_no, segments, text, task, depth, status):
        if status not in ("partial", "failed") or depth >= s.refinement_depth:
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

    def table_task(page_no, bbox, task, header, row, columns, depth=0, derivation=None, repeat_key=None):
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
            def then(status):
                if status != "complete" and depth < s.refinement_depth and splittable:
                    split_columns(page_no, bbox, task, header, row, columns, depth + 1, derivation)
            context = context_of.for_table(page_no, bbox, flat)
            if repeat_key is not None and context:  # the same row under another lead-in or stem isn't a repeat
                repeat_key += (hashlib.sha256(context.encode()).hexdigest(),)
            consume(page_no, bbox, task, text, derivation=derivation,
                    check=lambda q: quoted(q, text) or covered(q, flat) or s.loose_match(q, text),
                    then=then, repeat_key=repeat_key, repeat_after=2, context=context)
        else:
            split_columns(page_no, bbox, task, header, row, columns, depth, derivation)

    def split_columns(page_no, bbox, task, header, row, columns, depth, derivation):
        rest = columns[1:]
        middle = (len(rest) + 1) // 2
        for i, part in enumerate([rest[:middle], rest[middle:]]):
            # Budget-driven splits are mandatory; only quality-driven ones use depth.
            table_task(page_no, bbox, f"{task}:c{i}", header, row, [columns[0], *part], depth, derivation)

    def visual_task(page_no, page, tag, rect, depth=0, text=""):
        name = f"{stem}-{tag.replace(':', '-')}.png"
        render(page, rect, assets / name, s.image_side)
        native_rect = native(page, rect)
        layer = page.get_text("text", clip=native_rect)
        check = (lambda q: covered(q, layer, fold=True)) if layer.strip() else None
        blocks = [(tuple(b[:4]), b[4]) for b in page.get_text("blocks", clip=native_rect) if b[6] == 0]
        def place(quote):  # the first text block in the region holding the quote
            return next((box for box, text in blocks if covered(quote, text, fold=True)), None)
        text = s.region_text(context_of, page, rect, layer, text)
        context, extra = context_of.for_tile(page, rect, tag)
        consume(page_no, native_rect, tag, text, "assets/" + name, check=check, place=place,
                crop=(tuple(round(v, 3) for v in rect), s.image_side), context=context, extra_images=extra,
                then=lambda status: refine_visual(page_no, page, tag, rect, depth, status))

    def refine_visual(page_no, page, tag, rect, depth, status):
        # Refine only local tiles; an overview or a whole figure may be incomplete because
        # it spans many facts, and all its areas already have tile coverage.
        if (status not in ("partial", "failed") or tag.split(":")[0] in ("overview", "figure") or depth >= s.refinement_depth
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

    name = content if isinstance(path, (bytes, bytearray)) else Path(path).name
    try:
        opened = pymupdf.open(stream=path, filetype="pdf") if isinstance(path, (bytes, bytearray)) else pymupdf.open(path)
        problem = ("encrypted; it needs to be decrypted before comparison" if opened.needs_pass
                   else "not a nonempty PDF" if not opened.is_pdf or not len(opened) else None)
    except (RuntimeError, ValueError) as error:  # corrupt, or not a PDF at all
        opened, problem = None, f"unreadable ({error})"
    if problem:  # one failed row, and the run goes on with the other documents; the next run tries it again
        if opened is not None:
            opened.close()
        record({"content": content, "page": None, "bbox": None, "task": "open", "image": None, "status": "failed",
                "issues": [f"{name}: {problem}"], "claims": 0})
        state["result"] = ([], coverage)
        return
    with opened as doc:
        context_of = Context(doc, s, assets, stem)  # the task functions above read it when they run
        sections, owner = pdf_sections(doc, s.section_depth, s.section_pages)
        page_section = owner
        if on_sections:
            on_sections(sections)
        signals = {}
        # (header, width) of a table that ended near the bottom of the previous page
        carried = None
        for number, page in enumerate(doc, 1):
            yield "page"
            # Native coordinates stay unrotated (PDF point coordinates). Consecutive
            # blocks are grouped up to the byte budget; oversized blocks are split.
            for ids, segments in text_groups(page, s.text_bytes, lambda b, n=number: owner.box(n, b).id):
                text_task(number, segments, f"text:p{number}:{ids}")
            try:
                # Table detection works in displayed coordinates; locators are unrotated.
                unrotated = lambda b: tuple(native(page, b)) if b else None
                found = [(unrotated(table.bbox), rows, [unrotated(b) for b in row_boxes(table, rows)])
                         for table in page.find_tables().tables for rows in [table.extract()]
                         if s.keep_table(context_of, page, table, rows)]
            except Exception as e:  # PyMuPDF table detection raises assorted internal errors
                found = []
                record({"content": content, "page": number, "bbox": list(native_page(page)),
                        "task": f"table-detection:p{number}", "image": None, "status": "failed",
                        "issues": [type(e).__name__ + ": " + str(e)], "claims": 0})
            height = page.rect.height
            continuing, carried = carried, None
            context_of.tables_on[number] = [bbox for bbox, _, _ in found]
            for ti, (bbox, rows, boxes) in enumerate(found):
                if not rows:
                    continue
                displayed = shown(page, bbox)  # continuation is judged as displayed
                header, body, derivation = rows[0], rows[1:] or rows, None
                body_boxes = boxes[1:] if len(rows) > 1 else boxes
                width = max(len(r) for r in rows)
                # A table at the top of a page, as wide as one that ended at the bottom of the
                # previous page, continues it, unless its first row is a header of the same
                # form (a new table, e.g. the next day's schedule). An identical first row is
                # a repeated header and is skipped.
                if (ti == 0 and continuing and continuing[1] == width and displayed.y0 - page.rect.y0 < 0.2 * height
                        and (rows[0] == continuing[0] or not same_form(rows[0], continuing[0]))):
                    if rows[0] != continuing[0]:
                        body, body_boxes = rows, boxes
                    header = continuing[0]
                    derivation = [DerivationStep(step="pdf-table-detection",
                                                 detail=f"row with header continued from page {number - 1}"),
                                  DerivationStep(step="model-extraction")]
                for ri, row in enumerate(body):
                    # Rows with no content (common where drawing geometry is detected as a
                    # table) cost a model call and can't yield a claim.
                    if all(c is None or not str(c).strip() for c in row):
                        continue
                    # Exactly repeated rows (same header and cells, same table position) follow their
                    # first occurrence from the third sighting on; text is never de-duplicated.
                    key = ("table", json.dumps([header, row], ensure_ascii=False, default=str),
                           tuple(round(v / 2) * 2 for v in bbox))
                    row_box = body_boxes[ri] if ri < len(body_boxes) and body_boxes[ri] else tuple(bbox)
                    table_task(number, tuple(row_box), f"table:p{number}:{ti}:{ri}", header, row, list(range(width)),
                               derivation=derivation, repeat_key=key)
                if displayed.y1 - page.rect.y0 > 0.8 * height:
                    carried = (header, width)
                else:
                    carried = None
            section = owner[number].id
            for name_, value in page_signals(page, len(found)).items():
                signals.setdefault(section, {}).setdefault(name_, 0)
                signals[section][name_] += value
            if s.vision:
                for tag, rect, note in s.visual_regions(context_of, page, number):
                    # Task tags are unique within content: "<region>:p<page>[:<index>]".
                    region, _, index = tag.partition(":")
                    tag = f"{region}:p{number}" + (f":{index}" if index else "")
                    # A figure's caption, or a sheet detail's titles, as source text.
                    visual_task(number, page, tag, rect, text=note)
            else:
                record({"content": content, "page": number, "bbox": list(native_page(page)),
                        "task": f"vision:p{number}", "image": None, "status": "skipped",
                        "issues": ["Visual extraction disabled; charts, diagrams and scans may be missed"], "claims": 0})
        if on_sections:
            on_sections([x.model_copy(update={"signals": signals.get(x.id, {})}) for x in sections])
        while state["pending"]:  # refinement may still render crops from this document
            yield "waiting"
    coverage.sort(key=lambda r: (r["page"] or 0, r["task"]))
    state["result"] = (merge_occurrences(evidence), coverage)
