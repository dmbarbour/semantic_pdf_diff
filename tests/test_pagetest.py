"""Page tests: sheets draw their items, static plans and close-up runs work, requests become regions."""
import tempfile
import unittest
from semantic_pdf_diff import pagetest
from semantic_pdf_diff.eyetest import CAP

class Reader:
    """A simulated model: reads the items wholly inside its image whose capitals are at least 6 px
    tall there, and asks for a close-up (a box) around each quarter of the image holding smaller ones."""
    def __init__(self, sheet, zoom=True):
        _, _, self.items = pagetest.draw(sheet)
        self.zoom, self.asked = zoom, []
    def ask(self, prompt, schema, images=(), key=None):
        (x0, y0, x1, y1), px = key[2], key[3]
        self.asked.append(key[1])
        scale = px / max(x1 - x0, y1 - y0)
        inside = [i for i in self.items if x0 <= i["box"][0] and i["box"][2] <= x1 and y0 <= i["box"][1] and i["box"][3] <= y1]
        read = [i["text"] for i in inside if CAP["helv"] * i["pt"] * scale >= 6]
        boxes = []
        if self.zoom and '"zoom"' in prompt:
            for qx in (0, 500):
                for qy in (0, 500):
                    small = [i for i in inside if CAP["helv"] * i["pt"] * scale < 6
                             and qx <= (i["box"][0] - x0) / (x1 - x0) * 1000 < qx + 500
                             and qy <= (i["box"][1] - y0) / (y1 - y0) * 1000 < qy + 500]
                    if small:
                        boxes.append([qx, qy, qx + 500, qy + 500])
        return schema.model_validate({"items": read, "zoom": boxes})

class Sheets(unittest.TestCase):
    def test_every_sheet_draws_its_items_the_same_way(self):
        for sheet in pagetest.sheets():
            _, page, items = pagetest.draw(sheet)  # raises when an item is missing from the text layer
            layout = pagetest.LAYOUTS[sheet.kind]
            count, _, per_size = layout.get("clusters") or (0, None, {})
            self.assertEqual(len(items), sum(layout["scattered"].values()) + count * sum(per_size.values()))
            _, page2, _ = pagetest.draw(sheet)
            self.assertEqual(pagetest.picture(page, page.rect, 512)[0], pagetest.picture(page2, page2.rect, 512)[0])

    def test_requests_become_page_regions(self):
        import pymupdf
        page = pymupdf.Rect(0, 0, 1000, 1000)
        clip = pymupdf.Rect(0, 0, 1000, 1000)
        box = pagetest._region([100, 100, 300, 200], clip, {}, page)
        self.assertTrue(box.contains(pymupdf.Rect(100, 100, 300, 200)))
        self.assertEqual(pagetest._region("[100, 100, 300, 200]", clip, {}, page), box)  # a box sent as text
        self.assertIsNotNone(pagetest._region("b2", clip, {"B2": pymupdf.Rect(250, 0, 500, 333)}, page))
        self.assertIsNone(pagetest._region([0, 0, 1000, 1000], clip, {}, page))  # no closer than the image
        self.assertIsNone(pagetest._region("Z9", clip, {}, page))
        tiny = pagetest._region([500, 500, 501, 501], clip, {}, page)
        self.assertGreaterEqual(min(tiny.width, tiny.height), 48)

class Reading(unittest.TestCase):
    def test_slicing_trades_queries_for_small_text(self):
        sheet = pagetest.Sheet("letter", 1)
        with tempfile.TemporaryDirectory() as d:
            static = pagetest.run_static(d, Reader(sheet), sheet, [(None, 768), (144, 768)])
        result = pagetest.results({sheet.id: static}, {}, {})["static"][sheet.id]
        whole, tiled = result["whole-768"], result["t144-768"]
        self.assertLess(whole["recall"], tiled["recall"])
        self.assertEqual((whole["queries"], tiled["queries"]), (1, 35))
        self.assertEqual(whole["by_pt"]["14"], 1.0)
        self.assertLess(whole["by_pt"]["4"], 1.0)
        self.assertEqual(whole["whole_in_tiles"], 1.0)

    def test_detail_sheets_keep_small_text_in_their_clusters(self):
        import pymupdf
        for kind in ("letter-detail", "archd-detail"):
            _, page, items = pagetest.draw(pagetest.Sheet(kind, 1))
            scale = pagetest.OVERVIEW_PX / max(page.rect.width, page.rect.height)
            for i in items:  # body text readable in the overview (6 px caps), cluster text not
                self.assertEqual(i["cluster"] is None, CAP["helv"] * i["pt"] * scale >= 6, (kind, i))

    def test_close_ups_reach_text_too_small_for_the_overview(self):
        sheet = pagetest.Sheet("archd", 1)
        with tempfile.TemporaryDirectory() as d:
            reader = Reader(sheet)
            log = pagetest.run_zoom(d, reader, sheet, "free-boxes")
            overview_only = pagetest.run_zoom(d, Reader(sheet, zoom=False), sheet, "free-boxes")
        self.assertLessEqual(len(log), pagetest.QUOTA)
        self.assertEqual(max(e[2] for e in log), pagetest.MAX_DEPTH)
        result = pagetest.results({}, {sheet.id: {"free-boxes": log, "none": overview_only}}, {})["zoom"][sheet.id]
        self.assertGreater(result["free-boxes"]["recall"], result["none"]["recall"])
        self.assertEqual(result["free-boxes"]["first_zooms_useful"], 1.0)
        self.assertEqual(result["none"]["queries"], 1)
        detail = pagetest.Sheet("archd-detail", 1)
        with tempfile.TemporaryDirectory() as d:
            log = pagetest.run_zoom(d, Reader(detail), detail, "free-boxes")
        quality = pagetest.results({}, {detail.id: {"free-boxes": log}}, {})["zoom"][detail.id]["free-boxes"]
        self.assertEqual(quality["clusters_found"], 1.0)  # the reader asks only where small text is

if __name__ == "__main__":
    unittest.main()
