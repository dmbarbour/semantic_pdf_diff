"""A tiling's measures without the model (tile-selection-2026-10-10, milestone 1): tiling.measure, and the lab's runs
over a folder."""
import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff.pages import lines
from semantic_pdf_diff.segmentation import _graphics
from semantic_pdf_diff.tiling import measure, measure_tile, words
from stubs import TILING_BEFORE

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

    def test_a_figure_is_held_by_what_is_drawn_in_it_not_its_white_margin(self):
        _doc, page = text_page(count=2)
        drawn = pymupdf.Rect(300, 150, 500, 300)
        page.draw_rect(drawn, fill=(0, 0, 0))
        detected = drawn + (-6, -6, 6, 6)  # a figure's box, a margin around what's drawn
        for tile, split in (((0, 0, 502, 400), 0), ((0, 0, 498, 400), 1)):  # short of the box; then of the drawing
            found = measure(page, regions(tile), lines(page), _graphics(page), figures=[detected])["page"]
            self.assertEqual(found["figures_not_whole"], split, tile)

class Candidates(unittest.TestCase):
    """Milestone 3's candidate tilings, each a lever off by default."""

    def test_decoration_rules_bars_furniture_and_a_backdrop_but_not_a_figure_or_a_scan(self):
        # furniture is drawn alike in the same place: a picture where a neighbour has the figure is still a figure
        from semantic_pdf_diff.segmentation import decoration
        doc = pymupdf.open()
        for _ in range(3):
            page = doc.new_page(width=612, height=792)
            page.draw_rect(pymupdf.Rect(560, 20, 590, 50), fill=(0.8, 0.4, 0.1), color=None)  # a logo on every page
        page = doc[1]
        page.draw_rect(pymupdf.Rect(40, 60, 572, 61), fill=(0.5, 0.5, 0.5), color=None)  # a rule under the header
        page.draw_rect(pymupdf.Rect(20, 80, 26, 380), fill=(0.1, 0.2, 0.4), color=None)  # a bar down the margin
        page.draw_rect(pymupdf.Rect(300, 500, 450, 600), fill=(0, 0, 0), color=None)  # a figure
        for i in range(10):
            page.insert_text((60, 100 + 14 * i), "the pump delivers 10 kW at its rated point", fontsize=10)
        from semantic_pdf_diff.segmentation import marks
        for other, colour in ((doc[0], (0.6, 0, 0)), (doc[2], (0, 0.6, 0))):  # other figures in the same place
            other.draw_rect(pymupdf.Rect(300, 500, 450, 600), fill=colour, color=None)
        found = decoration(page, _graphics(page), lines(page), [marks(doc[0]), marks(doc[2])])
        graphics = [_graphics(p) for p in doc]
        self.assertEqual({tuple(round(v) for v in g): d for g, d in zip(graphics[1], found)},
                         {(560, 20, 590, 50): True, (40, 60, 572, 61): True, (20, 80, 26, 380): True,
                          (300, 500, 450, 600): False})
        backdrop = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 80), False)
        backdrop.clear_with(230)
        _doc, page = text_page(width=612, height=792, count=20)
        page.insert_image(page.rect, pixmap=backdrop, overlay=False)
        self.assertEqual(decoration(page, _graphics(page), lines(page)), [True])
        scan = pymupdf.open()
        page = scan.new_page(width=612, height=792)
        page.insert_image(page.rect, pixmap=backdrop)
        for i in range(20):  # an OCR layer: invisible text over the scan
            page.insert_text((40, 60 + 14 * i), "the pump delivers 10 kW at its rated point", fontsize=10,
                             render_mode=3)
        self.assertEqual(decoration(page, _graphics(page), lines(page)), [False])

    def test_a_long_line_in_a_drawing_is_the_drawing_not_a_rule(self):  # a plan's gridlines, a schematic's duct
        from semantic_pdf_diff.segmentation import decoration
        _doc, page = text_page(width=612, height=792, count=5)
        page.draw_line((100, 400), (100, 700), width=1)  # inside the drawing
        page.draw_line((40, 380), (572, 380), width=1)  # a rule above it
        drawing = pymupdf.Rect(80, 390, 560, 720)
        graphics = _graphics(page)
        self.assertEqual(decoration(page, graphics, lines(page)), [True, True])
        self.assertEqual({tuple(round(v) for v in g): d
                          for g, d in zip(graphics, decoration(page, graphics, lines(page), drawn=[drawing]))},
                         {(100, 400, 100, 700): False, (40, 380, 572, 380): True})

    def test_decoration_underlines_text_masks_and_text_panels_but_not_a_figure_with_labels(self):
        from semantic_pdf_diff.segmentation import decoration
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((60, 100), "GENERAL NOTES", fontsize=10)
        heading = lines(page)[0][0]
        page.draw_rect(pymupdf.Rect(heading.x0, heading.y1 + 1, heading.x1 - 5, heading.y1 + 2), fill=(0, 0, 0),
                       color=None)  # an underline
        page.insert_text((60, 140), "ALL WORK SHALL CONFORM", fontsize=10)
        note = lines(page)[1][0]
        page.draw_rect(note + (-1, -1, 1, 1), fill=(1, 1, 1), color=None, overlay=False)  # a mask behind the note
        panel = pymupdf.Rect(300, 200, 560, 330)  # a section's panel, a heading bar inside it
        page.draw_rect(panel, fill=(0.9, 0.9, 0.95), color=None, overlay=False)
        page.draw_rect(pymupdf.Rect(310, 210, 550, 236), fill=(0.1, 0.2, 0.4), color=None)
        page.insert_text((320, 228), "Background", fontsize=12, color=(1, 1, 1))
        for i in range(5):
            page.insert_text((310, 260 + 14 * i), "space radiation can cause cancer", fontsize=10)
        figure = pymupdf.Rect(60, 400, 300, 600)  # a figure: labels, and a curve that isn't text
        page.draw_rect(figure, color=(0, 0, 0), width=0.5)
        page.draw_polyline([(80, 580), (150, 480), (220, 450), (280, 420)], color=(0.8, 0, 0), width=1.5)
        page.insert_text((70, 595), "flow (gpm)", fontsize=8)
        graphics = _graphics(page)
        found = {tuple(round(v) for v in g): d for g, d in zip(graphics, decoration(page, graphics, lines(page)))}
        self.assertTrue(found[tuple(round(v) for v in pymupdf.Rect(heading.x0, heading.y1 + 1, heading.x1 - 5,
                                                                  heading.y1 + 2))])
        self.assertTrue(found[tuple(round(v) for v in note + (-1, -1, 1, 1))])
        self.assertTrue(found[tuple(round(v) for v in panel)])
        self.assertTrue(found[(310, 210, 550, 236)])
        self.assertFalse(found[tuple(round(v) for v in figure)])
        self.assertFalse(found[(80, 420, 280, 580)])

    def test_a_snapped_grid_cuts_at_whitespace_without_overlap(self):
        from semantic_pdf_diff.segmentation import snapped, tiles
        doc = pymupdf.open()
        page = doc.new_page(width=900, height=300)
        for x in (40, 480):  # two columns, a gutter between 420 and 480
            for i in range(15):
                page.insert_text((x, 30 + 16 * i), "a short line of text here ok", fontsize=10)
        cut = snapped(page.rect, 420, lines(page), [])
        self.assertEqual(len(cut), len(list(tiles(page.rect, 420))))
        self.assertEqual(measure(page, regions(*cut), lines(page), [])["page"]["lines_cut_sideways"], 0)
        self.assertAlmostEqual(cut[0].x1, cut[1].x0)  # the gutter: no overlap

    def test_xy_cut_holds_columns_whole_in_tiles_that_fit(self):
        from semantic_pdf_diff.segmentation import xy_cut
        doc = pymupdf.open()
        page = doc.new_page(width=1200, height=800)
        for x in (40, 440, 840):  # three columns of 40 lines
            for i in range(40):
                page.insert_text((x, 40 + 18 * i), "a column line of some words", fontsize=12)
        cut = xy_cut(page.rect, 420, lines(page), [])
        found = measure(page, regions(*cut), lines(page), [])["page"]
        self.assertEqual((found["lines_cut_sideways"], found["lines_cut_across"], found["lines_read_twice"]), (0, 0, 0))
        for r in cut:
            self.assertLessEqual(max(r.width, r.height), 1.6 * 420 + 0.01)
            self.assertLessEqual(min(r.width, r.height), 420 + 0.01)

    def test_the_levers_skip_text_only_tiles_band_wide_pages_and_render_by_area(self):
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        doc, page = text_page(width=960, height=540, count=25, top=40)
        page.draw_rect(pymupdf.Rect(700, 300, 900, 500), fill=(0, 0, 0), color=None)
        def tiles(**kw):
            s = Settings(**{**TILING_BEFORE, **kw})  # the grid, so text-only tiles are there to skip
            return [r for tag, r, _ in s.visual_regions(Context(doc, s), page, 0) if tag.startswith("tile")]
        every, kept = tiles(), tiles(skip_text_only=True)
        self.assertLess(len(kept), len(every))
        self.assertTrue(all(r.intersects(pymupdf.Rect(700, 300, 900, 500)) for r in kept))
        self.assertEqual(tiles(skip_text_only="except_sheets"), kept)  # not a drawing sheet
        banded = tiles(band_width=2.4)
        self.assertTrue(banded and all(r.height <= 1.6 * 420 * 420 / 960 + 0.01 for r in banded))
        self.assertEqual(Settings().render_side(pymupdf.Rect(0, 0, 800, 200)), 1000)
        self.assertEqual(Settings(render_area=True).render_side(pymupdf.Rect(0, 0, 800, 200)), 2000)
        self.assertEqual(Settings(render_area=True).render_side(pymupdf.Rect(0, 0, 400, 400)), 1000)

    def test_text_only_tiles_are_sent_where_no_text_task_reads_the_page(self):  # a Word document's pictures
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        for width, settings in ((612, {}), (960, {"skip_text_only": True, "tile_choice": "off"})):
            doc, page = text_page(width=width, height=792, count=30, top=40)  # text alone: bands, or a grid

            def tiles(text_read, doc=doc, page=page, settings=settings):
                s = Settings(**settings)
                reader = Context(doc, s)
                reader.text_read = text_read
                return [r for tag, r, _ in s.visual_regions(reader, page, 0) if tag.startswith("tile")]
            self.assertEqual(tiles(True), [])
            self.assertTrue(tiles(False))

    def test_a_drawing_sheets_text_only_tiles_are_kept_except_sheets(self):  # milestones 3 and 6: facts lost there
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        corpus = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
        with pymupdf.open(corpus / "lcc-plan-s1-clean.pdf") as doc:
            page = doc[0]
            def tiles(**kw):
                s = Settings(**kw)
                return [r for tag, r, _ in s.visual_regions(Context(doc, s), page, 0) if tag.startswith("tile")]
            every = tiles()
            self.assertLess(len(tiles(skip_text_only=True)), len(every))
            self.assertEqual(tiles(skip_text_only="except_sheets"), every)

class Figures(unittest.TestCase):
    def test_a_pages_figures_are_its_own_whatever_number_it_is_asked_by(self):
        # once kept by the number asked: a 0-based caller (2 for the third page) got the second page's, kept under 2
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        corpus = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
        doc = pymupdf.open()
        for name in ("lcc-s1-clean", "lcc-enduse-s1-clean", "lcc-plan-s1-clean"):
            with pymupdf.open(corpus / f"{name}.pdf") as source:
                doc.insert_pdf(source, from_page=0, to_page=0)
        reader = Context(doc, Settings())
        kinds = [[f.kind for f in reader.figures(page, page.number + 1)] for page in doc]
        self.assertIn("sheet", kinds[2])
        self.assertEqual([f.kind for f in reader.figures(doc[2], 2)], kinds[2])
        self.assertEqual([f.id for f in reader.figures(doc[2], 2)], [f.id for f in reader.figures(doc[2], 3)])

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
            default = tiling.run(folder, Settings(**TILING_BEFORE))  # bands and the grid as before milestone 8
            grid = tiling.run(folder, Settings(tiling="grid", **TILING_BEFORE))
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

    def test_a_rotated_page_is_drawn_as_displayed(self):
        from semantic_pdf_diff.pages import shown
        from semantic_pdf_diff_lab.bench import gallery
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=600)
        page.draw_rect(pymupdf.Rect(20, 20, 120, 60), fill=(0, 0, 0), color=None)
        page.set_rotation(90)
        box = shown(page, pymupdf.Rect(20, 20, 120, 60))  # where the block is displayed, as the tiles' coordinates are
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "page.png"
            gallery.draw(page, [], path, side=600)
            pix = pymupdf.Pixmap(str(path))
        self.assertEqual((pix.width, pix.height), (600, 400))
        dark = lambda x, y: pix.pixel(int(x), int(y))[0] < 60
        self.assertTrue(dark((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2))
        self.assertFalse(dark(70, 40))  # where the unrotated page would put it

    def test_a_gallery_draws_each_page_under_each_configuration(self):
        from semantic_pdf_diff.settings import Settings
        from semantic_pdf_diff_lab.bench import gallery, tiling
        with tempfile.TemporaryDirectory() as folder:
            doc, _ = text_page(width=792, height=612, count=30, top=40)
            doc.save(Path(folder) / "wide.pdf")
            before = Settings(**TILING_BEFORE)  # the grid cuts this page's lines: something to draw
            rows = tiling.run(folder, before)
            out = Path(folder) / "gallery"
            drawn = gallery.build(folder, rows, {"today": before, "grid": Settings(tiling="grid")}, out, named=())
            self.assertGreater(drawn, 0)
            self.assertEqual(len(list((out / "pages").glob("*.png"))), 2 * drawn)
            self.assertIn("wide.pdf, page 1", (out / "index.html").read_text())

if __name__ == "__main__":
    unittest.main()
