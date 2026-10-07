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
