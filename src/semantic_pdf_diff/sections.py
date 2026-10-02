"""A document's sections: from its outline (down to a depth) or fixed page ranges, located on the page, and
their text. Split from extract.py (milestone 7).
"""
import re

import pymupdf

from .models import Section
from .pages import display_y, native, shown, shown_by_matrix, top_by_matrix

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
