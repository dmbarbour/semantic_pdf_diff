"""Detected tables: whether one is really a table (the table_filter lever), its rows' boxes, repeated headers, and
its grid for the rules query (pdf_grid). Split from extract.py (milestone 7).
"""
import pymupdf

from .pages import shown

def same_form(row, header):
    """True if a row matches most non-empty cells of a header, position by position."""
    pairs = [(a, b) for a, b in zip(row, header) if a not in (None, "") or b not in (None, "")]
    return bool(pairs) and sum(a == b for a, b in pairs) / len(pairs) >= 0.5

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

def pdf_grid(header, body, boxes, title="", place=""):
    """A detected table's grid as the rules query sees it (tablerules.Grid; the one table model's step 1): its cells'
    text folded to one line, a header cell PyMuPDF merged (None) labelled as its left neighbour, and heuristic
    repairs: a row with an empty first cell and no number in it continues the row above (a wrapped cell) and joins
    it; a row of only its first cell is a section row (tablerules.grid). Rows keep their boxes and, as keys, the
    index of their first body row."""
    from . import tablerules
    width = max([len(header)] + [len(r) for r in body])
    clean = lambda row: [" ".join(str(c).split()) if c is not None else "" for c in row] + [""] * (width - len(row))
    labels, last = [], ""
    for c in list(header) + [None] * (width - len(header)):
        last = last if c is None else " ".join(str(c).split())
        labels.append(last)
    rows, kept_boxes, keys = [], [], []
    boxes = list(boxes) + [None] * (len(body) - len(boxes))
    for ri, (row, box) in enumerate(zip(body, boxes)):
        cells = clean(row)
        if not any(cells):
            continue
        if rows and not cells[0] and not any(tablerules.number(c) is not None for c in cells if c):
            rows[-1] = [" ".join(t for t in (a, b) if t) for a, b in zip(rows[-1], cells)]  # a wrapped cell
            if box and kept_boxes[-1]:
                a = kept_boxes[-1]
                kept_boxes[-1] = (min(a[0], box[0]), min(a[1], box[1]), max(a[2], box[2]), max(a[3], box[3]))
            continue
        rows.append(cells)
        kept_boxes.append(tuple(box) if box else None)
        keys.append(ri)
    if any(b is None for b in kept_boxes):
        return None  # rows without boxes can't be placed: read row by row
    g = tablerules.grid([tablerules.letter(k) for k in range(1, width + 1)], labels, rows,
                        [str(k + 2) for k in range(len(rows))], [0] * len(rows), title, place, kept_boxes)
    g.keys = [keys[k] for k in g.keys]
    return g

def _filled(row):
    return [c for c in row if c is not None and str(c).strip()]

def _words_only(row):
    """A row of labels: filled, and no digit in it ("up to 173" is a value, "Capacity (gpm)" a label)."""
    cells = _filled(row)
    return bool(cells) and not any(ch.isdigit() for c in cells for ch in str(c))

def _numbers(rows):
    from . import tablerules
    return any(tablerules.number(" ".join(str(c).split())) is not None for r in rows for c in _filled(r))

class Marks:
    """A page's drawn marks, read once: horizontal rules (lines, thin boxes, stroked boxes' edges), filled boxes, and
    text spans with their styles. In the page's coordinates, as its tables' boxes are (pages without rotation)."""
    def __init__(self, page):
        self.page, self._drawn, self._spans, self._words = page, None, None, None

    def _draw(self):
        if self._drawn is None:
            segs, fills = [], []
            for d in self.page.get_drawings():
                stroked = d.get("color") is not None and d.get("type") in ("s", "fs")
                for item in d["items"]:
                    if item[0] == "l" and abs(item[1].y - item[2].y) <= 1:
                        segs.append((min(item[1].x, item[2].x), max(item[1].x, item[2].x), (item[1].y + item[2].y) / 2))
                    elif item[0] == "re":
                        r = item[1]
                        if r.height <= 1.5:
                            segs.append((r.x0, r.x1, (r.y0 + r.y1) / 2))
                        elif stroked:
                            segs += [(r.x0, r.x1, r.y0), (r.x0, r.x1, r.y1)]
                r = d["rect"]
                if d.get("fill") is not None and r.height > 1.5 and r.width > 1.5:
                    fills.append((pymupdf.Rect(r), tuple(round(c, 1) for c in d["fill"])))
            self._drawn = (segs, fills)
        return self._drawn

    def rules(self, bbox, cover=0.6):
        """The y of each horizontal rule drawn across most of a table's width."""
        x0, y0, x1, y1 = bbox
        segs = sorted(((max(a, x0), min(b, x1), y) for a, b, y in self._draw()[0]
                       if y0 - 2 <= y <= y1 + 2 and min(b, x1) > max(a, x0)), key=lambda s: s[2])
        groups = []
        for seg in segs:
            if groups and seg[2] - groups[-1][-1][2] <= 1.5:
                groups[-1].append(seg)
            else:
                groups.append([seg])
        out = []
        for g in groups:
            covered, end = 0.0, None
            for a, b, _ in sorted(g):
                covered += max(0.0, b - max(a, end if end is not None else a))
                end = b if end is None else max(end, b)
            if covered >= cover * (x1 - x0):
                out.append(sum(y for _, _, y in g) / len(g))
        return out

    def styles(self, bbox, boxes):
        """Each row's look, right of its first column (often styled as labels): the fill under it and whether most
        of its text is bold. None for a row without a box."""
        if self._spans is None:
            self._spans = [sp for b in self.page.get_text("dict")["blocks"] for line in b.get("lines", [])
                           for sp in line["spans"] if sp["text"].strip()]
        fills = self._draw()[1]
        out = []
        for box in boxes:
            if box is None:
                out.append(None)
                continue
            x0, y0, x1, y1 = box
            inner = [sp for sp in self._spans if x0 - 1 <= sp["bbox"][0] and sp["bbox"][2] <= x1 + 1
                     and y0 < (sp["bbox"][1] + sp["bbox"][3]) / 2 < y1]
            left = min((sp["bbox"][0] for sp in inner), default=x0)
            values = [sp for sp in inner if sp["bbox"][0] > left + 1]
            bold = sum(len(sp["text"]) for sp in values if sp["flags"] & 16 or "bold" in sp["font"].lower())
            total = sum(len(sp["text"]) for sp in values)
            point = pymupdf.Point(x1 - (x1 - x0) * 0.25, (y0 + y1) / 2)
            fill = None
            for r, colour in fills:  # the last drawn is on top
                if r.contains(point):
                    fill = colour
            out.append((fill, total > 0 and bold * 2 > total))
        return out

    def cuts(self, box, edges):
        """The column boundaries (k: between columns k and k + 1) a word in a row's box is cut by: its box crossing
        the boundary's x with 15% to 85% of it on each side ("7.4" parted into "7." and "4")."""
        if box is None or not edges:
            return set()
        if self._words is None:
            self._words = [w[:4] for w in self.page.get_text("words")]
        x0, y0, x1, y1 = box
        out = set()
        for a, b, c, d in self._words:
            if not (y0 < (b + d) / 2 < y1 and x0 - 1 <= a and c <= x1 + 1) or c - a <= 0:
                continue
            for k, x in enumerate(edges):
                if x is not None and 0.15 < (x - a) / (c - a) < 0.85:
                    out.add(k)
        return out

def split_cuts(row, box, edges, marks):
    """The boundaries a word in a row is cut by, where the cut parts text across two filled cells (a word the
    parser kept whole in one cell isn't split, wherever a column line runs)."""
    filled = lambda k: k < len(row) and row[k] is not None and str(row[k]).strip()
    return {j for j in marks.cuts(box, edges) if filled(j) and filled(j + 1)}

def column_edges(table):
    """The x of each boundary between a detected table's columns (the median over its rows' cells; None where no
    row has both cells), or None for a table without cell boxes."""
    import statistics
    rows = [getattr(r, "cells", None) for r in getattr(table, "rows", None) or []]
    rows = [r for r in rows if r]
    if not rows:
        return None
    width = max(len(r) for r in rows)
    edges = []
    for k in range(width - 1):
        xs = [r[k][2] for r in rows if len(r) > k + 1 and r[k] is not None and r[k + 1] is not None]
        edges.append(statistics.median(xs) if xs else None)
    return edges

def cut_columns(rows, boxes, edges, marks):
    """(rows, edges, how many boundaries joined): columns joined across a boundary where every row with text on both
    sides of it has a word cut there ("7. | 4" is "7.4"; a phantom column holding only the overflow of cut words),
    without a space where the word was cut. A boundary with two separate values in any row stays."""
    if not edges or not rows or len(boxes) != len(rows):
        return rows, edges, 0
    cut = [marks.cuts(b, edges) if b else set() for b in boxes]
    filled = lambda r, k: k < len(r) and r[k] is not None and str(r[k]).strip()
    join = []
    for j in range(len(edges)):
        both = [i for i, r in enumerate(rows) if filled(r, j) and filled(r, j + 1)]
        if both and all(j in cut[i] for i in both):
            join.append(j)
    if not join:
        return rows, edges, 0
    width = max(len(r) for r in rows)
    out = []
    for i, row in enumerate(rows):
        row = list(row) + [None] * (width - len(row))
        for j in sorted(join, reverse=True):
            a, b = row[j], row[j + 1]
            if filled(row, j) and filled(row, j + 1):
                merged = str(a).rstrip() + ("" if j in cut[i] else " ") + str(b).lstrip()
            else:
                merged = a if filled(row, j) else b if filled(row, j + 1) else a if a is not None else b
            row = row[:j] + [merged] + row[j + 2:]
        out.append(row)
    return out, [x for k, x in enumerate(edges) if k not in join], len(join)

def _joined(upper, lower):
    out = []
    for k in range(max(len(upper), len(lower))):
        a = upper[k] if k < len(upper) else None
        b = lower[k] if k < len(lower) else None
        texts = [" ".join(str(t).split()) for t in (a, b) if t is not None and str(t).strip()]
        out.append(" ".join(texts) if texts else (a if a is not None else b))
    return out

def ruled_rows(rows, boxes, rules, least=3, share=0.4):
    """(rows, boxes, how many joined): a table whose row boundaries are mostly ruled (3 or more, and 40% or more of
    them, drawn across most of its width) has its rows joined across the boundaries without a rule, which are lines
    of one row the parser took for rows (HabEx: each text line shaded with a box of its own). Two rows both labelled
    and both with a digit in the same column stay apart. Else unchanged."""
    if len(rows) < 3 or len(boxes) != len(rows) or any(b is None for b in boxes):
        return rows, boxes, 0
    ruled = [any(abs(boxes[k][1] - y) <= 1.5 for y in rules) for k in range(1, len(rows))]
    if all(ruled) or sum(ruled) < max(least, share * len(ruled)):
        return rows, boxes, 0
    def apart(upper, lower):
        digit = lambda c: c is not None and any(ch.isdigit() for ch in str(c))
        return (bool(_filled(upper[:1])) and bool(_filled(lower[:1]))
                and any(digit(a) and digit(b) for a, b in zip(upper[1:], lower[1:])))
    out_rows, out_boxes = [list(rows[0])], [tuple(boxes[0])]
    for k in range(1, len(rows)):
        if ruled[k - 1] or apart(out_rows[-1], rows[k]):
            out_rows.append(list(rows[k]))
            out_boxes.append(tuple(boxes[k]))
        else:
            a, b = out_boxes[-1], boxes[k]
            out_rows[-1] = _joined(out_rows[-1], rows[k])
            out_boxes[-1] = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
    return out_rows, out_boxes, len(rows) - len(out_rows)

def pdf_parts(header, body, boxes, styles=None):
    """A detected table's parts, each (header, body rows, their boxes), repaired from its parsed rows (the one table
    model's step 1, measured on the controlled PDFs' true tables):
    - empty rows between the lines of a header dropped (others kept in place, so rows keep their numbers)
    - a header over several lines: rows of labels (no digit in them) above rows of numbers join it, as a second
      level ("Rated point > Capacity (gpm)") under a header with merged cells, else as its next line ("Entry" +
      "speed")
    - stacked tables split: a row of labels, two or more, followed by rows of numbers starts a new part with
      its own header (blowers under pumps); with the rows' styles (Marks.styles), only a row styled unlike most
      rows (a header's fill or bold), so a row of words ("Spectrometer type | IFS | IFS") stays a row"""
    boxes = list(boxes) + [None] * (len(body) - len(boxes))
    rows = list(zip(body, boxes))
    seen = [st for st in styles or [] if st is not None]
    usual = max(seen, key=seen.count) if seen else None
    styled = lambda i: styles is None or (i < len(styles) and styles[i] is not None and styles[i] != usual)
    parts, current, held = [], [list(header), []], []
    i = 0
    while i < len(rows):
        row, box = rows[i]
        if not _filled(row) and not current[1]:
            held.append((row, box))  # an empty row under the header: dropped if a header line follows, else kept
            i += 1  # in place, so the rows after it keep their numbers
            continue
        rest = [r for r, _ in rows[i + 1:i + 4]]
        if not current[1] and _words_only(row) and _numbers(rest):  # the header's next line or level
            merged = any(c is None for c in current[0][1:])
            width = max(len(current[0]), len(row))
            head = list(current[0]) + [None] * (width - len(current[0]))
            joined, last = [], None
            for k in range(width):
                top = head[k] if head[k] is not None else (last if merged else None)
                last = top if head[k] is not None else last
                low = row[k] if k < len(row) else None
                parts_ = [" ".join(str(t).split()) for t in (top, low) if t is not None and str(t).strip()]
                joined.append((" > " if merged and len(parts_) == 2 else " ").join(parts_) or None)
            current[0] = joined
            held = []
            i += 1
            continue
        # a stacked table's header
        if current[1] and _words_only(row) and len(_filled(row)) >= 2 and _numbers(rest) and styled(i):
            parts.append(current)
            current = [list(row), []]
            i += 1
            continue
        if not current[1]:
            current[1], held = held, []
        current[1].append((row, box))
        i += 1
    parts.append(current)
    return [(head, [r for r, _ in rows_], [b for _, b in rows_]) for head, rows_ in parts if rows_]
