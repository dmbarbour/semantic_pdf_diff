"""Page coordinates: the one owner of the two frames every box on a page lives in.

A PDF page's boxes (text blocks, drawings, and the locators we record) are in its unrotated
coordinates. What a reader sees is the page turned by its /Rotate: drawing sheets are often
stored sideways. Reading order, "above", "before" and positions on the page are about what's
displayed. Every conversion between the two goes through here: the rotated-sheet bugs came back
once because conversions were fixed site by site (docs/reviews/meta-audit-2026-09-28.md).
"""
import pymupdf

def shown(page, box):
    """A box (unrotated page coordinates) as the page is displayed."""
    return pymupdf.Rect(box) * page.rotation_matrix

def shown_point(page, point):
    return pymupdf.Point(point) * page.rotation_matrix

def native(page, rect):
    """A displayed rectangle in the page's unrotated coordinates (what locators record)."""
    return pymupdf.Rect(rect) * page.derotation_matrix

def native_page(page):
    """The whole page in its unrotated coordinates."""
    return page.rect * page.derotation_matrix

def display_y(page, bbox):
    """The top of a box (unrotated page coordinates) as the page is displayed: section
    positions follow reading order, which on a rotated page isn't the unrotated y."""
    return top_by_matrix(page.rotation_matrix if page.rotation else None, bbox)

def top_by_matrix(matrix, bbox):
    """display_y for a page known only by its rotation matrix (None: not rotated)."""
    return (pymupdf.Rect(bbox) * matrix).y0 if matrix is not None else float(bbox[1])

def shown_by_matrix(matrix, bbox):
    """shown for a page known only by its rotation matrix (None: not rotated)."""
    return pymupdf.Rect(bbox) * matrix if matrix is not None else pymupdf.Rect(bbox)

def reading_blocks(page):
    """Text-layer blocks in reading order as displayed. PyMuPDF's sort=True orders unrotated
    coordinates, which on a rotated page (drawing sheets) is across the page as displayed; there
    the blocks are sorted by their displayed position instead. Unrotated pages keep sort=True's
    order exactly, so their queries are unchanged."""
    blocks = page.get_text("blocks", sort=not page.rotation)
    if page.rotation:
        blocks.sort(key=lambda b: (round(shown(page, b[:4]).y1), shown(page, b[:4]).x0))
    return blocks

def reading_dict_blocks(page):
    """The text dictionary's blocks, and each block's lines, in reading order as displayed."""
    blocks = page.get_text("dict", sort=not page.rotation)["blocks"]
    if page.rotation:
        blocks.sort(key=lambda b: (round(shown(page, b["bbox"]).y1), shown(page, b["bbox"]).x0))
        for b in blocks:
            b.get("lines", []).sort(key=lambda l: (round(shown(page, l["bbox"]).y1), shown(page, l["bbox"]).x0))
    return blocks

def lines(page):
    """Text lines as displayed: [(Rect, text)]."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", ()):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                out.append((shown(page, line["bbox"]), text))
    return out
