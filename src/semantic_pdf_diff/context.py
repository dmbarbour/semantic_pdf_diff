"""The document reader the context levers' hooks share (levers.py), the lines levers add found again in a prompt
(their marks), and the locator thumbnail. Split from extract.py (milestone 7).
"""
import re

import pymupdf

from .pages import display_y, lines as _lines, native, reading_blocks, shown
from .regions import crop_name
from .segmentation import _graphics
from .figures import page_figures
from .stems import glossary, references, stem_index

CONTEXT_NOTE = "CONTEXT (for reference only: do not extract claims from it):"

LOCATOR_SIDE = 384  # pixels: the page thumbnail that shows where a tile sits
FURNITURE_BAND = 0.1  # a text block within this share of a page's height of its top or bottom may be page furniture

class Recent:
    """What a page yields, kept for the last few pages asked about: a page's crops and passes ask for the same again
    and again, and a drawing sheet's drawings or display list is large, so only a few pages' are kept (code review
    2026-10-08, A7, A8). By page number: one document's, which a reading doesn't change."""
    def __init__(self, make, size=2):
        self.make, self.size, self.kept = make, size, []  # [(page number, what it yielded)]

    def __call__(self, page):
        for number, value in self.kept:
            if number == page.number:
                return value
        value = self.make(page)
        self.kept = [(page.number, value)] + self.kept[:self.size - 1]
        return value

class Context:
    """A document's reader for the context levers (levers.py: text_lines, table_lines, tile_lines, tile_images):
    the caches and document access their hooks share. A query's context is CONTEXT_NOTE followed by the lines
    the configuration's levers give, in their order. What a lever added is found again by its marks
    (settings.lever_notes). The reader works on the page as displayed (see pages), so rotated sheets read like upright
    ones."""

    def __init__(self, doc, s, assets=None, stem="", terms=None):
        self.doc, self.s = doc, s
        self.terms = terms  # the document's glossary (terms.Terms), for the reader_glossary lever; None: none read
        self.assets, self.stem = assets, stem  # where the locator's images go, and their names' stem
        self.blocks, self.stems, self.cited_by, self.page_lines, self.page_graphics = {}, {}, {}, {}, {}
        self.page_figures, self.page_decoration, self.page_marks = {}, {}, {}
        self.page_margins, self.page_furniture, self.sightings = {}, {}, None
        self.tables_on = {}  # page -> the boxes of its tables (a row's lead-in is above its whole table)
        self.table_rows_on = {}  # page -> its tables as detected, [(box, rows, row boxes)] (table_cuts)
        # how the model is asked mid-reading (the client's ask), where a job can: the tiling question (tile_choice); and
        # each page's choice of cut, its record (tilechoice.choose); its tiles' labels (regionlabels); the cut a partial
        # tile is read again under (retiling.other_cut)
        self.ask, self.page_choices, self.page_labels, self.page_retilings = None, {}, {}, {}
        # whether text tasks read the pages' text layers: a PDF's do; a Word document's pictures' don't (its text tasks
        # read its paragraphs), so a picture's text-only tiles are sent (pictures.Reading)
        self.text_read = True
        # a page's vector drawings (never changed by their readers), and its display list: Page.get_pixmap builds one
        # for every crop, interpreting the whole page again
        self.drawings = Recent(lambda page: page.get_cdrawings())
        self._display_lists = Recent(lambda page: page.get_displaylist(annots=True))

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

    def graphics(self, page):
        """A page's drawings and images as displayed (segmentation's, frames left out), once per page: a drawing
        sheet's take up to a second, and each refined tile reads them."""
        if page.number not in self.page_graphics:
            self.page_graphics[page.number] = _graphics(page, self.drawings(page))
        return self.page_graphics[page.number]

    def decoration(self, page):
        """The page's graphics that are decoration (segmentation.decoration), once per page: [Rect]. Its neighbours'
        graphics are read to find what repeats in the same place."""
        if page.number not in self.page_decoration:
            from .segmentation import NEIGHBOURS, decoration
            graphics = self.graphics(page)
            nearby = [self.marks(self.doc[n]) for n in range(max(0, page.number - NEIGHBOURS),
                                                            min(len(self.doc), page.number + NEIGHBOURS + 1))
                      if n != page.number and self.doc[n].rect == page.rect]
            drawn = [shown(page, f.bbox) for f in self.figures(page, page.number + 1)]
            found = decoration(page, graphics, self.lines(page), nearby, self.marks(page), drawn)
            self.page_decoration[page.number] = [g for g, d in zip(graphics, found) if d]
        return self.page_decoration[page.number]

    def marks(self, page):
        """What the page draws where (segmentation.marks), once per page."""
        if page.number not in self.page_marks:
            from .segmentation import marks
            self.page_marks[page.number] = marks(page, self.drawings(page))
        return self.page_marks[page.number]

    def figures(self, page, number=None):
        """The page's detected figures (figures.page_figures), once per page: the figure tasks and the tiling
        measures both ask. Kept by the page, and numbered from 1 (their ids carry it), whatever number a caller has
        (once kept by it: a 0-based caller got the page before's figures)."""
        if page.number not in self.page_figures:
            self.page_figures[page.number] = page_figures(page, page.number + 1, self.drawings(page))
        return self.page_figures[page.number]

    def pixmap(self, page, matrix, clip=None):
        """Page.get_pixmap(matrix=matrix, clip=clip, alpha=False), rendered as it does, from the page's display list."""
        return self._display_lists(page).get_pixmap(matrix=matrix, colorspace=pymupdf.csRGB, alpha=False, clip=clip)

    def page_blocks(self, page_no):
        """The page's text blocks in reading order: [(bbox, text)]."""
        if page_no not in self.blocks:
            self.blocks[page_no] = [(tuple(b[:4]), " ".join(b[4].split()))
                                    for b in reading_blocks(self.doc[page_no - 1]) if b[6] == 0 and b[4].strip()]
        return self.blocks[page_no]

    def table_top(self, page_no, row_box):
        for box in self.tables_on.get(page_no, ()):
            if pymupdf.Rect(row_box) in pymupdf.Rect(box) + (-2, -2, 2, 2):
                return box
        return row_box

    def text_above(self, page_no, bbox, leave=()):
        """The text of the blocks just above a box (a table's lead-in sentence or caption), as displayed; blocks
        whose boxes are in leave left out."""
        page = self.doc[page_no - 1]
        table = shown(page, bbox)  # as displayed (rotated sheets)
        return " ".join(t for b, t in self.page_blocks(page_no)
                        if shown(page, b).y1 <= table.y0 + 2 and shown(page, b).x1 > table.x0
                        and shown(page, b).x0 < table.x1 and b not in leave)

    def repeated(self, page_no):
        """The boxes of a page's text blocks saying exactly what blocks in the same place (within 2 points) said on
        REPEATED earlier pages (whitespace and case folded); page_blocks' boxes."""
        from .segmentation import REPEATED
        place = lambda box, said: (" ".join(said.split()).casefold(), tuple(round(v / 2) for v in box))
        if self.sightings is None:
            self.sightings = {}
            for n in range(1, self.pages + 1):
                for box, said in self.page_blocks(n):
                    self.sightings.setdefault(place(box, said), []).append(n)
        return [box for box, said in self.page_blocks(page_no)
                if sum(n < page_no for n in sorted(set(self.sightings[place(box, said)]))) >= REPEATED]

    def _margins(self, page_no):
        """The page's text blocks near its top or bottom (FURNITURE_BAND), as displayed: {box: (band, what it says
        with its numbers blanked, its lines)}; page_blocks' boxes."""
        if page_no not in self.page_margins:
            page, out = self.doc[page_no - 1], {}
            band = FURNITURE_BAND * page.rect.height
            for b in reading_blocks(page):
                if b[6] != 0 or not b[4].strip():
                    continue
                r = shown(page, b[:4])
                where = "top" if r.y1 <= page.rect.y0 + band else "bottom" if r.y0 >= page.rect.y1 - band else None
                if where:
                    lines = tuple(" ".join(line.split()) for line in b[4].splitlines() if line.strip())
                    out[tuple(b[:4])] = (where, re.sub(r"\d+", "#", " ".join(lines)).casefold(), lines)
            self.page_margins[page_no] = out
        return self.page_margins[page_no]

    def furniture(self, page_no):
        """A page's furniture (running headers and footers, page numbers): {box: its lines} of the blocks near its
        top or bottom saying the same, numbers aside, in the same band on REPEATED of the NEIGHBOURS pages either side
        of the same size (all of them, if fewer); page_blocks' boxes. A one-page document has none."""
        if page_no not in self.page_furniture:
            from .segmentation import NEIGHBOURS, REPEATED
            page = self.doc[page_no - 1]
            size = (round(page.rect.width), round(page.rect.height))
            nearby = [n for n in range(max(1, page_no - NEIGHBOURS), min(self.pages, page_no + NEIGHBOURS) + 1)
                      if n != page_no and (round(self.doc[n - 1].rect.width),
                                           round(self.doc[n - 1].rect.height)) == size]
            seen = [{(where, said) for where, said, _ in self._margins(n).values()} for n in nearby]
            needed = min(REPEATED, len(nearby))
            self.page_furniture[page_no] = {
                box: lines for box, (where, said, lines) in self._margins(page_no).items()
                if needed and sum((where, said) in other for other in seen) >= needed}
        return self.page_furniture[page_no]

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

    def words_in(self, page, rect):
        """The text layer within a displayed region (an image task's)."""
        return page.get_text("text", clip=native(page, rect))

    def locator(self, page, rect, tag):
        """The whole page, small, with the region outlined: rendered once into the store, its path returned."""
        where = crop_name(self.stem, tag, "-where")
        render_locator(page, rect, self.assets / where, pixmap=self.pixmap)
        return "assets/" + where

def render_locator(page, rect, target, side=LOCATOR_SIDE, width=3, pixmap=None):
    """The whole page, small, with rect (displayed coordinates) outlined in red. pixmap: Context.pixmap."""
    scale = side / max(page.rect.width, page.rect.height)
    matrix = pymupdf.Matrix(scale, scale)
    pix = pixmap(page, matrix) if pixmap is not None else page.get_pixmap(matrix=matrix, alpha=False)
    box = (rect * pymupdf.Matrix(scale, scale)).irect & pix.irect
    for edge in (pymupdf.IRect(box.x0, box.y0, box.x1, box.y0 + width),
                 pymupdf.IRect(box.x0, box.y1 - width, box.x1, box.y1),
                 pymupdf.IRect(box.x0, box.y0, box.x0 + width, box.y1),
                 pymupdf.IRect(box.x1 - width, box.y0, box.x1, box.y1)):
        pix.set_rect(edge & pix.irect, (255, 0, 0))
    pix.save(target)
