import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff.models import Evidence, Occurrence, PdfLocator
from semantic_pdf_diff.situate import figure_map, find_figures

def diagram(page, x, y, paths=16):
    for i in range(paths):
        page.draw_rect(pymupdf.Rect(x + (i % 4) * 45, y + (i // 4) * 35, x + (i % 4) * 45 + 30, y + (i // 4) * 35 + 20))
    page.draw_line(pymupdf.Point(x, y + 150), pymupdf.Point(x + 180, y + 150))

def build(path):
    doc = pymupdf.open()
    p1 = doc.new_page(width=400, height=500)
    p1.insert_text((40, 60), 'The pump arrangement is shown in Figure 1. See also Table 7 for sizes.')
    p2 = doc.new_page(width=400, height=500)
    diagram(p2, 100, 100)
    p2.insert_text((100, 290), 'Figure 1: Pump arrangement')
    p3 = doc.new_page(width=400, height=500)
    diagram(p3, 60, 250)                                  # a diagram without a caption
    p3.insert_text((40, 60), 'Notes on the arrangement in fig. 1 and Sheet M-101.')
    p4 = doc.new_page(width=400, height=500)
    p4.insert_text((40, 60), 'Figure 2: Drawing supplied separately')  # a caption without a drawing
    doc.save(path); doc.close()
    return path

def ev(eid, page, region, bbox):
    loc = PdfLocator(page=page, bbox=bbox, region=region, task=f'{region}:p{page}:0')
    occ = Occurrence(locator=loc, kind='text', quote='q', confidence=.9)
    return Evidence(id=eid, content='sha256:x.pdf', entity='e', attribute='a', value='v', kind='text', quote='q',
                    confidence=.9, locator=loc, occurrences=[occ])

class Figures(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.doc = pymupdf.open(build(Path(self.dir.name) / 'f.pdf'))
        self.addCleanup(self.doc.close)

    def test_figures_captions_and_regions(self):
        figures = {f.id: f for f in find_figures(self.doc)}
        (fig1,) = [f for f in figures.values() if f.label == 'figure 1']
        self.assertEqual((fig1.page, fig1.region, fig1.caption), (2, True, 'Figure 1: Pump arrangement'))
        self.assertLessEqual(fig1.bbox[1], 100)   # covers the drawing above the caption
        self.assertGreaterEqual(fig1.bbox[3], 290)
        (uncaptioned,) = [f for f in figures.values() if f.page == 3]
        self.assertEqual((uncaptioned.label, uncaptioned.region), (None, True))
        (fig2,) = [f for f in figures.values() if f.label == 'figure 2']
        self.assertEqual((fig2.page, fig2.region), (4, False))

    def test_references_resolve_and_unresolved_are_reported(self):
        tile_on_fig = ev('ev-tile', 2, 'tile', (90, 90, 300, 300))
        tile_elsewhere = ev('ev-far', 2, 'tile', (0, 400, 100, 500))
        citing = ev('ev-cite', 1, 'text', (30, 40, 380, 70))
        figures, unresolved = figure_map(self.doc, [tile_on_fig, tile_elsewhere, citing])
        (fig1,) = [f for f in figures if f.label == 'figure 1']
        self.assertEqual([r.page for r in fig1.references], [1, 3])  # "Figure 1" and "fig. 1"
        self.assertIn('Figure 1', fig1.references[0].text)
        self.assertEqual(fig1.references[0].evidence, ['ev-cite'])
        self.assertEqual(fig1.claims, ['ev-tile'])
        self.assertEqual(sorted(r.label for r in unresolved), ['sheet M-101', 'table 7'])

    def test_drawing_sheet_is_one_region(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=800, height=600)
            page.draw_rect(page.rect)                    # a frame around the whole sheet is ignored
            for x in range(60, 700, 20):
                page.draw_line(pymupdf.Point(x, 80), pymupdf.Point(x + 10, 480))
            doc.save(Path(d) / 's.pdf'); doc.close()
            doc = pymupdf.open(Path(d) / 's.pdf')
            (sheet,) = find_figures(doc)
            doc.close()
            self.assertEqual(sheet.page, 1)
            self.assertLess(sheet.bbox[0], 70)

if __name__ == '__main__':
    unittest.main()
