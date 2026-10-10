"""Image tasks over a page's regions (Visuals): the region rendered to a crop, its text layer, its context, a partial
tile refined in halves. For the PDF job and a Word document's pictures. Split from extract.py (code review
2026-10-08, A12).
"""
import pymupdf

from .pages import native
from .quotes import covered
from .regions import crop_name, region_of
from .segmentation import halves

# Visual refinement stops at crops narrower than this (PDF points).
MIN_REFINE_POINTS = 100

def render(page, rect, target, max_side, context=None):
    """A crop, saved: from the reader's display list of the page with a context (Context.pixmap), else as
    Page.get_pixmap renders it (the same pixels)."""
    # clip is in rotated page coordinates, as used by Page.get_pixmap.
    scale = min(2.5, max_side / max(rect.width, rect.height))
    matrix = pymupdf.Matrix(scale, scale)
    pix = context.pixmap(page, matrix, rect) if context is not None else page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
    pix.save(target)

class Visuals:
    """Image tasks over a page's regions, for the PDF job and a Word document's pictures (pictures.py): the region
    rendered to a crop, its text layer a check on quotes and, by region_text, context; its context lines (for_tile);
    a partial tile refined in halves.

    A PDF's claims are located in the region and placed in their section by the text block quoting them. A Word
    picture's are at its paragraph: `box`, the locator's box and the section's place both; its caption (`text`)
    stays with the halves a tile is refined into (`derivation`: its steps, the region's otherwise)."""
    def __init__(self, core, context_of, assets, stem, settings):
        self.core, self.context_of, self.assets, self.stem, self.s = core, context_of, assets, stem, settings

    def task(self, page_no, page, tag, rect, depth=0, text="", box=None, derivation=None):
        s = self.s
        name = crop_name(self.stem, tag)
        render(page, rect, self.assets / name, s.image_side, self.context_of)
        native_rect = native(page, rect)
        # one text page for the layer and the blocks, their flags the same (code review 2026-10-08, A6)
        textpage = (page.get_textpage(clip=native_rect, flags=pymupdf.TEXTFLAGS_TEXT) if not depth or box is None
                    else None)
        layer = (page.get_text("text", textpage=textpage) if not depth  # a refined half's by whole lines (review item 6)
                 else "".join(line + "\n" for line_box, line in self.context_of.lines(page)
                              if (line_box.tl + line_box.br) / 2 in rect))
        check = (lambda q: covered(q, layer, fold=True)) if layer.strip() else None
        if box is None:
            blocks = [(tuple(b[:4]), b[4]) for b in page.get_text("blocks", textpage=textpage) if b[6] == 0]

            def place(quote):  # the first text block in the region holding the quote
                return next((found for found, text in blocks if covered(quote, text, fold=True)), None)
        else:
            def place(quote):
                return box
        source = s.region_text(self.context_of, page, rect, layer, text)
        context, extra = self.context_of.for_tile(page, rect, tag)
        kept = text if box is not None else ""
        self.core.consume(page_no, native_rect if box is None else box, tag, source, "assets/" + name, check=check,
                          place=place, crop=(tuple(round(v, 3) for v in rect), s.image_side), context=context,
                          extra_images=extra, derivation=derivation,
                          then=lambda status: self.refine(page_no, page, tag, rect, depth, status, kept, box, derivation))

    def refine(self, page_no, page, tag, rect, depth, status, text, box, derivation):
        # Refine only local tiles; an overview or a whole figure may be incomplete because
        # it spans many facts, and all its areas already have tile coverage.
        s = self.s
        if (status not in ("partial", "failed") or region_of(tag) in ("overview", "figure") or depth >= s.refinement_depth
                or min(rect.width, rect.height) < MIN_REFINE_POINTS):
            return
        for i, child in enumerate(halves(page, rect, self.context_of.lines(page), self.context_of.graphics(page))):
            self.task(page_no, page, f"{tag}-r{i}", child, depth + 1, text, box, derivation)
