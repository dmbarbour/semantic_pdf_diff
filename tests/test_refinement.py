"""A partial tile refined in halves cut between lines or columns (decision 0029)."""
import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff.jobs import extract_pdf
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.pages import lines
from semantic_pdf_diff.retiling import tile_lines
from semantic_pdf_diff.segmentation import halves
from stubs import TILING_BEFORE
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

    def test_a_scans_band_is_cut_between_the_lines_its_image_shows(self):
        """scan_halves (docs/plans/text-cut-by-tiles-2026-10-28.md, milestone 2; the owner, 2026-11-02: "Let's go with
        your recommendations on the low-hanging fruit."): a band without a text layer was cut down its middle,
        through every line; its image's own lines say where to cut."""
        from semantic_pdf_diff.segmentation import image_lines
        text = pymupdf.open(); written = text.new_page(width=500, height=400)
        paragraph(written)
        boxes = [b for b, _ in lines(written)]  # before another page is added: it ends this one's handle
        two = text.new_page(width=500, height=400)
        for i in range(24):  # two columns, staggered: no row gap runs across both
            two.insert_text((30, 40 + 12 * i), 'left column text', fontsize=10)
            two.insert_text((280, 46 + 12 * i), 'right column text', fontsize=10)
        doc = pymupdf.open()
        for source in text:  # each page an image of it alone: a scan, no text layer
            scan = doc.new_page(width=500, height=400)
            scan.insert_image(scan.rect, pixmap=source.get_pixmap(dpi=150))
        page = doc[0]
        self.assertEqual(lines(page), [])
        band = pymupdf.Rect(30, 40, 470, 290)
        found = image_lines(page, band)
        self.assertEqual(len(found), 16)  # its sixteen lines, as the image shows them
        self.assertEqual([len(cut(boxes, half)) for half in halves(page, band)], [16, 16])  # down every line
        parts = halves(page, band, inked=found)
        self.assertEqual([cut(found, half) for half in parts], [[], []])  # no line's ink cut (a box's leading may be)
        held = [[b for b in boxes if abs(b & half) > abs(b) / 2] for half in parts]
        self.assertEqual([len(h) for h in held], [8, 8])
        self.assertTrue(all(half.x0 <= 30 and half.x1 >= 470 for half in parts))
        tile = pymupdf.Rect(20, 25, 480, 340)
        ink = image_lines(doc[1], tile)
        parts = halves(doc[1], tile, inked=ink)
        self.assertEqual([cut(ink, half) for half in parts], [[], []])
        self.assertEqual(len(ink), 2)  # staggered, the rows run together: a block a column, apart at the gutter
        self.assertTrue(any(b.x1 < 260 for b in ink) and any(b.x0 > 260 for b in ink))
        self.assertTrue(all(half.y0 <= 25 and half.y1 >= 340 for half in parts))  # down the gutter
        blank = pymupdf.Rect(0, 350, 500, 400)  # nothing found: across the shorter side, crossing no line
        self.assertEqual(halves(page, blank, inked=image_lines(page, blank)),
                         [pymupdf.Rect(0, 350, 500, 387), pymupdf.Rect(0, 363, 500, 400)])

    def test_without_a_gap_the_cut_crosses_fewest_lines_and_halves_grow_to_whole_lines(self):
        doc = pymupdf.open(); page = doc.new_page(width=500, height=400)
        page.insert_text((40, 100), 'one long line ' * 6, fontsize=10)  # the only line, across the middle
        boxes = [b for b, _ in lines(page)]
        tile = pymupdf.Rect(30, 90, 470, 104)  # no gap of a quarter's share: the line can't be missed
        parts = halves(page, tile)
        self.assertTrue(any(boxes[0] in half for half in parts))

    def test_parts_are_cut_around_where_they_can_be(self):  # halve_parts: the cut follows the parts
        doc = pymupdf.open(); page = doc.new_page(width=400, height=300)
        for i in range(18):
            page.insert_text((20, 30 + 14 * i), 'note text', fontsize=10)  # a column of text, x 20 to about 70
        bars = [pymupdf.Rect(x, 50, x + 20, 250) for x in (150, 190, 230, 270, 310)]  # a chart: bars with gaps
        for bar in bars:
            page.draw_rect(bar, fill=(0, 0, 0))
        boxes = lines(page)
        tile, figure = pymupdf.Rect(10, 10, 390, 290), pymupdf.Rect(150, 50, 330, 250)
        through = halves(page, tile, boxes, bars)
        self.assertFalse(any(figure in half for half in through))  # cut down a gap between its bars
        around = halves(page, tile, boxes, bars, parts=[figure])
        self.assertTrue(any(figure in half for half in around))
        self.assertEqual(halves(page, tile, boxes, bars, parts=[pymupdf.Rect(140, 40, 400, 300)]), through)  # not held

class Again(unittest.TestCase):  # figure_refinement: a partial tile mostly one figure is looked at again whole
    def test_a_tile_mostly_a_chart_is_asked_again_told_its_claims_and_issues(self):
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.schema import Claim
        from semantic_pdf_diff.settings import Settings
        corpus = Path(__file__).resolve().parent.parent / 'benchmarks/controlled/docs'
        with pymupdf.open(corpus / 'lcc-enduse-s1-clean.pdf') as doc:
            page = doc[0]
            claim = Claim(entity='Hall C', attribute='lighting', value='12', unit='kWh', quote='12', kind='chart',
                          confidence=0.8)
            done = {'row': {'issues': ['legend partly unreadable']}, 'claims': (claim,), 'cut': []}
            for mode, expected in (('again', [('tile:0-a', {'continued': (claim,),
                                                            'noted': ['legend partly unreadable']})]),
                                   ('halves', [('tile:0-r0', {}), ('tile:0-r1', {})])):
                s = Settings(refine_figures=mode, **TILING_BEFORE)
                reader = Context(doc, s)
                tiles = [r for r in s.visual_regions(reader, page, 0) if r[0].startswith('tile')]
                found = s.refined_tile(reader, page, *tiles[0][:2], done)
                self.assertEqual([(t, again) for t, _, again in found], expected)
                text = [r for r in tiles if r[0] == 'tile:1']  # the tile below the chart: text
                self.assertEqual(len(s.refined_tile(reader, page, *text[0][:2], done)), 2)

    def test_a_scans_band_is_halved_between_its_lines_with_scan_halves(self):
        """The lever end to end, on the corpus's scan (no text layer) and its drawing sheet (a text layer: its tiles
        holding no text keep the middle cut)."""
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        corpus = Path(__file__).resolve().parent.parent / 'benchmarks/controlled/docs'
        done = {'row': {}, 'claims': (), 'cut': []}
        cuts = {}
        for name, page_no in (('lcc-s1-scanned-frame.pdf', 0), ('lcc-plan-s1-all.pdf', 0)):
            with pymupdf.open(corpus / name) as doc:
                page = doc[page_no]
                for mode in ('middle', 'lines'):
                    s = Settings(scan_halves=mode, **TILING_BEFORE)
                    reader = Context(doc, s)
                    tiles = [r for r in s.visual_regions(reader, page, page_no) if r[0].startswith('tile')]
                    plain = [r for r in tiles if not any(b.intersects(r[1]) for b, _ in reader.lines(page))]
                    tag, rect = plain[0][:2]
                    cuts[name, mode] = (rect, [r for _, r, _ in s.refined_tile(reader, page, tag, rect, done)])
        band, middle = cuts['lcc-s1-scanned-frame.pdf', 'middle']
        _, lines_cut = cuts['lcc-s1-scanned-frame.pdf', 'lines']
        self.assertGreater(band.width, band.height)  # a band: the middle cut ran down it
        self.assertTrue(all(h.height >= band.height - 1 for h in middle))
        self.assertTrue(all(h.width >= band.width - 1 for h in lines_cut))  # now across it, between its lines
        self.assertEqual(cuts['lcc-plan-s1-all.pdf', 'middle'][1], cuts['lcc-plan-s1-all.pdf', 'lines'][1])

    def test_the_note_names_what_the_earlier_answer_noted(self):
        from semantic_pdf_diff.schema import Claim
        from semantic_pdf_diff.tasks import NOTED_NOTE, continuation
        fan = Claim(entity='fan', attribute='power', value='3', unit='kW', quote='3 kW', kind='text', confidence=0.9)
        text = continuation([fan],
                            ['the legend is cut'])
        self.assertTrue(text.endswith(f'- fan | power | 3 kW\n{NOTED_NOTE}\n- the legend is cut'))

class Refined(unittest.TestCase):
    def test_a_partial_bands_halves_hold_whole_lines_in_their_image_and_text(self):
        def build(page):
            paragraph(page, top=60, count=16)
            page.draw_rect(pymupdf.Rect(20, 60, 24, 240))  # a side bar, so the band is sent
        with tempfile.TemporaryDirectory() as d:
            client = Recorder(lambda source, prompt: Extraction(claims=[], complete=False), refinement_depth=1,
                              visual_text_layer=20000, **TILING_BEFORE)
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

    def test_a_scans_partial_band_is_halved_down_its_middle_and_its_rows_say_so(self):
        # the cause reproduced 2026-10-28 (docs/plans/text-cut-by-tiles-2026-10-28.md): with no text layer there are
        # no lines to cut between, so a band is halved down every line in it (scan_halves: middle, the default until
        # 2026-11-02); each tile's row records its path. By default now, between the lines its image shows
        def build(page):  # a letter page, scanned
            source = pymupdf.open().new_page(width=612, height=792)
            paragraph(source, count=40)
            page.insert_image(page.rect, pixmap=source.get_pixmap(dpi=100))
        for mode in ("middle", None):
            with tempfile.TemporaryDirectory() as d:
                client = Recorder(lambda source, prompt: Extraction(claims=[], complete=False), refinement_depth=1,
                                  **({"scan_halves": mode} if mode else {}))
                _, coverage = extract_pdf(pdf(Path(d) / 's.pdf', build, 612, 792), CID, Path(d), client)
            tiles = [r for r in coverage if r['task'].startswith('tile')]
            first = [r['tiling'] for r in tiles if '-r' not in r['task']]
            halved = [r for r in tiles if '-r' in r['task']]
            self.assertTrue(first and halved)
            self.assertEqual({str(x) for x in first}, {str({'cut': 'bands', 'depth': 0, 'text': False})})
            if mode is None:
                self.assertEqual({str(r['tiling']) for r in halved},
                                 {str({'cut': 'halves', 'depth': 1, 'text': False, 'image_lines': True})})
                continue
            self.assertEqual({str(r['tiling']) for r in halved},
                             {str({'cut': 'halves', 'depth': 1, 'text': False, 'middle': True})})
            for row in halved:  # the cut runs down the band: each half about half the page's width
                self.assertLess(pymupdf.Rect(row['bbox']).width, 0.6 * 612)
            self.assertEqual(tile_lines(coverage)[0],
                             f'Image tiles read: {len(tiles)} (bands {len(first)}, halves {len(halved)} ({len(halved)} '
                             f'down the middle)); {len(tiles)} on pages without a text layer')

class CutText(unittest.TestCase):
    """Text cut by tiles, milestone 2 (docs/plans/text-cut-by-tiles-2026-10-28.md): a tile's text layer by whole
    lines (whole_lines), and a tile saying its text was cut read again though answered complete (said_cut)."""
    def test_a_tile_cutting_a_line_sideways_is_given_the_line_whole(self):
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=200)
        page.insert_text((40, 60), 'the feed pump delivers 75 kW at its rated point', fontsize=12)
        page.insert_text((40, 120), 'the fan runs at 3 kW', fontsize=12)
        left = pymupdf.Rect(0, 40, 200, 70)  # the first line's start, and none of the second
        clipped = page.get_text('text', clip=left)
        for whole, expected in ((False, clipped), (True, 'the feed pump delivers 75 kW at its rated point\n')):
            s = Settings(whole_lines=whole)
            self.assertEqual(s.tile_layer(Context(doc, s), page, left, 0, clipped), expected)
        self.assertNotIn('rated point', clipped)
        s = Settings(whole_lines=True)  # a sliver of a line's height isn't touching it
        self.assertEqual(s.tile_layer(Context(doc, s), page, pymupdf.Rect(0, 60, 600, 115), 0, ''), '')

    def test_a_tile_saying_its_text_was_cut_is_read_again_though_complete(self):
        def build(page):
            paragraph(page, top=60, count=16)
            page.draw_rect(pymupdf.Rect(20, 60, 24, 240))  # a side bar, so the band is sent
        said = ['The text is clipped at the right edge']
        counts = {}
        for mode in ('noted', 'read again'):
            with tempfile.TemporaryDirectory() as d:
                client = Recorder(lambda source, prompt: Extraction(claims=[], complete=True, issues=said),
                                  refinement_depth=1, said_cut=mode, **TILING_BEFORE)
                _, coverage = extract_pdf(pdf(Path(d) / 't.pdf', build, width=500, height=500), CID, Path(d), client)
            tiles = [r for r in coverage if r['task'].startswith('tile')]
            counts[mode] = (sum(1 for r in tiles if r['tiling']['depth'] == 0),
                            sum(1 for r in tiles if r['tiling']['depth'] > 0))
        self.assertEqual(counts['noted'][1], 0)
        self.assertEqual(counts['read again'][0], counts['noted'][0])
        self.assertGreater(counts['read again'][1], 0)  # read again under the page's next cut

if __name__ == '__main__':
    unittest.main()
