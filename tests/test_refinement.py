"""A partial tile refined in halves cut between lines or columns (review-bugs-2026-10-09, item 6; trials finding 5)."""
import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff.extract import extract_pdf
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.pages import lines
from semantic_pdf_diff.segmentation import halves
from test_robustness import CID, Recorder, pdf

WORDS = 'the pump delivers 10 kW at its rated point and the fan runs at 3 kW'

def paragraph(page, top=60, count=16, x=40):
    for i in range(count):
        page.insert_text((x, top + 14 * i), f'{i:02d} {WORDS}', fontsize=10)

def cut(boxes, half):
    """Lines a half touches without holding."""
    return [b for b in boxes if half.intersects(b) and b not in half + (-1, -1, 1, 1)]

class Halves(unittest.TestCase):
    def test_a_band_is_cut_between_its_lines_not_down_them(self):
        doc = pymupdf.open(); page = doc.new_page(width=500, height=400)
        paragraph(page)
        boxes = [b for b, _ in lines(page)]
        band = pymupdf.Rect(30, 40, 470, 290)  # wider than tall: the middle cut ran down every line
        parts = halves(page, band)
        self.assertEqual([cut(boxes, half) for half in parts], [[], []])
        self.assertTrue(all(half.x0 <= 30 and half.x1 >= 470 for half in parts))
        for half in parts:
            self.assertGreaterEqual(abs(half & band) / abs(band), 0.25)

    def test_a_tile_holding_text_in_part_of_it_leaves_no_half_blank(self):
        doc = pymupdf.open(); page = doc.new_page(width=500, height=400)
        paragraph(page, top=60, count=6)  # the top third of the tile; below it, blank
        boxes = [b for b, _ in lines(page)]
        tile = pymupdf.Rect(30, 40, 470, 340)
        parts = halves(page, tile)
        self.assertEqual([cut(boxes, half) for half in parts], [[], []])
        self.assertTrue(all(any(b in half for b in boxes) for half in parts))

    def test_two_columns_are_cut_at_their_gutter_when_lines_cross_every_row(self):
        doc = pymupdf.open(); page = doc.new_page(width=500, height=400)
        for i in range(24):  # lines staggered between the columns: no row gap runs across both
            page.insert_text((30, 40 + 12 * i), 'left column text', fontsize=10)
            page.insert_text((280, 46 + 12 * i), 'right column text', fontsize=10)
        boxes = [b for b, _ in lines(page)]
        tile = pymupdf.Rect(20, 25, 480, 340)
        parts = halves(page, tile)
        self.assertEqual([cut(boxes, half) for half in parts], [[], []])
        self.assertTrue(all(half.y0 <= 25 and half.y1 >= 340 for half in parts))  # cut down the gutter

    def test_a_tile_without_text_keeps_the_middle_cut(self):
        doc = pymupdf.open(); page = doc.new_page(width=500, height=400)
        page.draw_rect(pymupdf.Rect(50, 50, 450, 350))
        tile = pymupdf.Rect(0, 0, 500, 300)
        self.assertEqual(halves(page, tile), [pymupdf.Rect(0, 0, 262, 300), pymupdf.Rect(238, 0, 500, 300)])

    def test_without_a_gap_the_cut_crosses_fewest_lines_and_halves_grow_to_whole_lines(self):
        doc = pymupdf.open(); page = doc.new_page(width=500, height=400)
        page.insert_text((40, 100), 'one long line ' * 6, fontsize=10)  # the only line, across the middle
        boxes = [b for b, _ in lines(page)]
        tile = pymupdf.Rect(30, 90, 470, 104)  # no gap of a quarter's share: the line can't be missed
        parts = halves(page, tile)
        self.assertTrue(any(boxes[0] in half for half in parts))

class Refined(unittest.TestCase):
    def test_a_partial_bands_halves_hold_whole_lines_in_their_image_and_text(self):
        def build(page):
            paragraph(page, top=60, count=16)
            page.draw_rect(pymupdf.Rect(20, 60, 24, 240))  # a side bar, so the band is sent
        with tempfile.TemporaryDirectory() as d:
            client = Recorder(lambda source, prompt: Extraction(claims=[], complete=False), refinement_depth=1,
                              visual_text_layer=20000)
            path = pdf(Path(d) / 't.pdf', build, width=500, height=500)
            _, coverage = extract_pdf(path, CID, Path(d), client)
            with pymupdf.open(path) as doc:
                page_lines = lines(doc[0])
            refined = [r for r in coverage if r['task'].startswith('tile') and '-r' in r['task']]
            self.assertTrue(refined)
            for row in refined:
                half = pymupdf.Rect(row['bbox'])
                with self.subTest(task=row['task']):
                    self.assertEqual(cut([b for b, _ in page_lines], half), [])
            layers = [p.split('TEXT LAYER OF THIS REGION')[1] for s, p, _ in client.tasks
                      if s == 'tile' and 'TEXT LAYER OF THIS REGION' in p]
            for layer in layers:
                shown = layer.split('\n', 1)[1].split('\n')[0]
                for number in range(16):
                    if f'{number:02d} the' in shown:
                        self.assertIn(f'{number:02d} {WORDS}', shown)
            self.assertTrue(layers)

if __name__ == '__main__':
    unittest.main()
