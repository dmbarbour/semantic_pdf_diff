"""The document reader the context levers' hooks share (levers.py), the lines levers add found again in a prompt
(their marks), and the locator thumbnail. Split from extract.py (milestone 7).
"""
import pymupdf

from .levers import lever_marks
from .models import Settings
from .pages import display_y, lines as _lines, reading_blocks, shown
from .regions import crop_name
from .situate import page_figures
from .stems import glossary, references, stem_index

CONTEXT_NOTE = "CONTEXT (for reference only: do not extract claims from it):"

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
        where = crop_name(self.stem, tag, "-where")
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
