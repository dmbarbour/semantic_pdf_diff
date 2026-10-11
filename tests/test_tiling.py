"""A tiling's measures without the model (tile-selection-2026-10-10, milestone 1): tiling.measure, and the lab's runs
over a folder."""
import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff.pages import lines
from semantic_pdf_diff.segmentation import _graphics
from semantic_pdf_diff.tiling import measure, measure_tile, words

def text_page(width=600, height=400, count=10, x=40, top=60):
    """A page of `count` lines, each about 330 points long."""
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    for i in range(count):
        page.insert_text((x, top + 14 * i), f"{i:02d} the pump delivers 10 kW at its rated point today", fontsize=10)
    return doc, page

def regions(*rects, tag="tile"):
    return [(f"{tag}:{i}", pymupdf.Rect(r), "") for i, r in enumerate(rects)]

class Tiles(unittest.TestCase):
    def test_a_tile_cut_down_its_lines_counts_each_line_and_its_cut_words(self):
        _doc, page = text_page()
        found = measure_tile((0, 0, 200, 400), lines(page), words(page), [])
        self.assertEqual(found["lines_cut_sideways"], 10)
        self.assertEqual(found["lines_cut_across"], 0)
        self.assertGreaterEqual(found["words_cut"], 1)
        self.assertLessEqual(found["words_cut"], 10)  # at most one word per line straddles the edge
        self.assertTrue(found["text_only"])

    def test_a_tile_holding_its_lines_whole_cuts_none(self):
        _doc, page = text_page()
        found = measure_tile((20, 40, 420, 210), lines(page), words(page), [])
        self.assertEqual((found["lines_cut_sideways"], found["lines_cut_across"], found["words_cut"]), (0, 0, 0))

    def test_a_tile_edge_through_a_line_cuts_it_across(self):
        _doc, page = text_page()
        third = lines(page)[3][0]
        found = measure_tile((20, 40, 420, (third.y0 + third.y1) / 2), lines(page), words(page), [])
        self.assertEqual(found["lines_cut_across"], 1)
        self.assertEqual(found["lines_cut_sideways"], 0)

    def test_graphics_decoration_and_blank(self):
        _doc, page = text_page(count=2)
        page.draw_rect(pymupdf.Rect(450, 250, 550, 350), fill=(0, 0, 0))  # a block of 100 x 100 points
        graphics = _graphics(page)
        tile = (450, 250, 550, 350)
        self.assertEqual(measure_tile(tile, lines(page), words(page), graphics)["graphics_share"], 1.0)
        half = measure_tile((400, 250, 600, 350), lines(page), words(page), graphics)
        self.assertAlmostEqual(half["graphics_share"], 0.5, delta=0.02)
        self.assertFalse(half["text_only"] or half["blank"] or half["decoration_only"])
        self.assertTrue(measure_tile(tile, lines(page), words(page), graphics, decoration=graphics)["decoration_only"])
        self.assertTrue(measure_tile((0, 300, 100, 400), lines(page), words(page), graphics)["blank"])

class Pages(unittest.TestCase):
    def test_overlapping_tiles_read_lines_twice(self):
        _doc, page = text_page()
        found = measure(page, regions((20, 40, 420, 150), (20, 100, 420, 210)), lines(page), [])["page"]
        self.assertGreater(found["lines_read_twice"], 0)
        self.assertGreater(found["overlap"], 1.0)
        apart = measure(page, regions((20, 40, 420, 120), (20, 120, 420, 210)), lines(page), [])["page"]
        self.assertEqual(apart["lines_read_twice"], 0)
        self.assertAlmostEqual(apart["overlap"], 1.0, delta=0.02)

    def test_figures_not_whole_and_graphics_missed(self):
        _doc, page = text_page(count=2)
        figure = pymupdf.Rect(300, 150, 500, 300)  # under half the page's height: not taken for a frame
        page.draw_rect(figure, fill=(0, 0, 0))
        graphics = _graphics(page)
        split = regions((0, 0, 400, 400), (400, 0, 600, 225))  # the figure across two tiles; its lower right unread
        found = measure(page, split, lines(page), graphics, figures=[figure])["page"]
        self.assertEqual(found["figures_not_whole"], 1)
        self.assertAlmostEqual(found["graphics_missed"], 0.25, delta=0.03)  # 100 x 75 of 200 x 150
        read = split + regions(figure + (-8, -8, 8, 8), tag="figure")
        found = measure(page, read, lines(page), graphics, figures=[figure])["page"]
        self.assertEqual((found["figures_not_whole"], found["graphics_missed"]), (0, 0.0))
        self.assertEqual((found["tiles"], found["images"]), (2, 3))

class LabRuns(unittest.TestCase):
    def test_a_folder_measured_under_two_settings_compares_page_by_page(self):
        from semantic_pdf_diff.settings import Settings
        from semantic_pdf_diff_lab.bench import tiling
        with tempfile.TemporaryDirectory() as folder:
            doc, page = text_page(width=792, height=612, count=30, top=40)  # landscape: a grid
            doc.save(Path(folder) / "wide.pdf")
            doc, page = text_page(width=612, height=792, count=30, top=40)
            page.draw_rect(pymupdf.Rect(40, 500, 400, 700), fill=(0, 0, 0))
            doc.save(Path(folder) / "report.pdf")
            default = tiling.run(folder, Settings())
            grid = tiling.run(folder, Settings(tiling="grid"))
        modes = {r["file"]: r["mode"] for r in default}
        self.assertEqual(modes, {"report.pdf": "bands", "wide.pdf": "grid"})
        self.assertGreater(tiling.summary(default)["grid"]["lines_cut_sideways"], 0)
        self.assertEqual(tiling.summary(default)["bands"]["lines_cut_sideways"], 0)
        found = tiling.compare(default, grid)
        self.assertEqual([p["file"] for p in found["pages_changed"]], ["report.pdf"])

class Gallery(unittest.TestCase):
    def test_the_worst_development_pages_are_picked_one_per_document(self):
        from semantic_pdf_diff_lab.bench import gallery
        row = lambda file, page, cut: {"file": file, "page": page, "lines_cut_sideways": cut, "per_tile": [],
                                       "lines_cut_across": 0, "text_only": 0, "lines_read_twice": 0,
                                       "figures_not_whole": 0, "lines": 40, "mode": "grid", "width": 720}
        rows = [row("a.pdf", 1, 5), row("a.pdf", 2, 9), row("b.pdf", 1, 3), row("heldout/c.pdf", 1, 50),
                row("d.pdf", 1, 0)]
        picked = gallery.pick(rows)["lines_cut_sideways"]
        self.assertEqual([(r["file"], r["page"]) for r in picked], [("a.pdf", 2), ("b.pdf", 1)])

    def test_a_gallery_draws_each_page_under_each_configuration(self):
        from semantic_pdf_diff.settings import Settings
        from semantic_pdf_diff_lab.bench import gallery, tiling
        with tempfile.TemporaryDirectory() as folder:
            doc, _ = text_page(width=792, height=612, count=30, top=40)
            doc.save(Path(folder) / "wide.pdf")
            rows = tiling.run(folder, Settings())
            out = Path(folder) / "gallery"
            drawn = gallery.build(folder, rows, {"today": Settings(), "grid": Settings(tiling="grid")}, out, named=())
            self.assertGreater(drawn, 0)
            self.assertEqual(len(list((out / "pages").glob("*.png"))), 2 * drawn)
            self.assertIn("wide.pdf, page 1", (out / "index.html").read_text())

if __name__ == "__main__":
    unittest.main()
