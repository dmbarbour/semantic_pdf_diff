"""Detected tables: whether one is really a table (the table_filter lever), its rows' boxes, and repeated
headers. Split from extract.py (milestone 7).
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
