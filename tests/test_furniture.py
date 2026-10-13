"""The leave_furniture lever: a page's running headers and footers and its page number are left out of neighbouring
text, a table's lead-in and image tasks' text layers."""
import stubs  # noqa: F401 (a clean environment)
import unittest

import pymupdf

from semantic_pdf_diff.context import Context
from semantic_pdf_diff.extract import text_groups
from semantic_pdf_diff.settings import Settings

HEADER, FOOTER = "Pump Station Design Report, Revision B", "Page {} of 4"

def report(pages=4, header=HEADER):
    """Pages with a running header and a numbered footer, two paragraphs each (the second page's first paragraph
    repeated near the top of the next, not in its margin)."""
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 40), header, fontsize=8)
        page.insert_text((270, 815), FOOTER.format(n), fontsize=8)
        page.insert_text((60, 200), f"Pump P-{n} is rated {10 * n} kW at 1450 rpm.", fontsize=10)
        page.insert_text((60, 400), f"Fan F-{n} moves {200 * n} L/s against 250 Pa.", fontsize=10)
    return doc

def context(doc, page_no, leave):
    """The context of the page's last text block (its paragraph about the fan)."""
    s = Settings(leave_furniture=leave, context_before=4000, context_after=4000)
    page = doc[page_no - 1]
    groups = text_groups(page, 50)
    (ids, segments), = [g for g in groups if "Fan" in g[1][0][1]]
    return Context(doc, s).for_text(page_no, segments, segments[0][1])

class Furniture(unittest.TestCase):
    def test_running_headers_and_page_numbers_are_furniture(self):
        doc = report()
        found = Context(doc, Settings()).furniture(2)
        self.assertEqual(sorted(lines for lines in found.values()), sorted([(HEADER,), ("Page 2 of 4",)]))

    def test_a_one_page_document_has_none(self):
        self.assertEqual(Context(report(pages=1), Settings()).furniture(1), {})

    def test_text_that_changes_from_page_to_page_isnt_furniture(self):
        doc = pymupdf.open()
        for n in range(3):
            doc.new_page(width=595, height=842).insert_text((60, 40), f"Chapter {'ABC'[n]}: Pumps", fontsize=8)
        self.assertEqual(Context(doc, Settings()).furniture(2), {})

    def test_neighbouring_text_leaves_it_out(self):
        doc = report()
        kept, left = context(doc, 2, False), context(doc, 2, True)
        self.assertIn(HEADER, kept)
        self.assertIn("Page 2 of 4", kept)
        for gone in (HEADER, "Page 1 of 4", "Page 2 of 4", "Page 3 of 4"):
            self.assertNotIn(gone, left)
        self.assertIn("Pump P-2 is rated 20 kW", left)
        self.assertIn("Pump P-3 is rated 30 kW", left)  # the next page's text

    def test_without_furniture_it_asks_as_before(self):
        doc = report(pages=1)
        self.assertEqual(context(doc, 1, True), context(doc, 1, False))

    def test_a_text_layer_leaves_it_out(self):
        doc = report()
        page = doc[1]
        layer = page.get_text("text")
        for leave in (False, True):
            s = Settings(leave_furniture=leave)
            text = s.region_text(Context(doc, s), page, page.rect, layer, "")
            self.assertEqual(HEADER in text, not leave)
            self.assertIn("Pump P-2 is rated 20 kW", text)

if __name__ == "__main__":
    unittest.main()
