"""The leave_text lever: a PDF page's text tasks leave out the text of its detected tables and figures."""
import stubs  # noqa: F401 (a clean environment)
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff.context import Context
from semantic_pdf_diff.extract import text_groups
from semantic_pdf_diff.figures import drawn_without_caption
from semantic_pdf_diff.settings import Settings

CORPUS = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"

def texts(stem, mode, number=0):
    """The text blocks a page's text tasks send under a leave_text mode."""
    with pymupdf.open(CORPUS / f"{stem}.pdf") as doc:
        page = doc[number]
        s = Settings(leave_text=mode)
        tables = [tuple(t.bbox) for t in page.find_tables().tables]
        boxes = s.text_left_out(Context(doc, s), page, number + 1, tables)
        return [t for _, segments in text_groups(page, s.text_bytes, None, boxes) for _, t in segments]

class LeaveText(unittest.TestCase):
    def test_a_charts_values_leave_the_text_tasks_but_its_caption_stays(self):
        every, kept = texts("lcc-energy-s1-clean", "none"), texts("lcc-energy-s1-clean", "tables and figures")
        self.assertIn("September", every)
        self.assertNotIn("September", kept)
        self.assertIn("Figure 1. Monthly cooling energy, May to October", kept)
        self.assertTrue(any(t.startswith("Figure 1 compares") for t in kept))  # the prose citing it

    def test_a_tables_rows_leave_the_text_tasks(self):
        every, kept = texts("coaster-tables-s1-clean", "none"), texts("coaster-tables-s1-clean", "tables")
        self.assertIn("E1\n129\n45.6\n2.58\n0.69", every)
        self.assertNotIn("E1\n129\n45.6\n2.58\n0.69", kept)
        self.assertIn("Table 1b. Brakes", kept)  # captions sit outside the table's box

    def test_a_drawing_sheet_keeps_its_text(self):  # its frame is found as tables covering it
        self.assertEqual(texts("lcc-plan-s1-clean", "tables and figures"), texts("lcc-plan-s1-clean", "none"))

    def test_a_caption_is_cut_from_its_figures_box(self):
        with pymupdf.open(CORPUS / "lcc-energy-s1-clean.pdf") as doc:
            (figure,) = [f for f in Context(doc, Settings()).figures(doc[0], 1) if f.region]
            box = drawn_without_caption(doc[0], figure)
        self.assertEqual((round(figure.bbox[3]), round(box[3])), (460, 446))  # cut at the caption's top

if __name__ == "__main__":
    unittest.main()
