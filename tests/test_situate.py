import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff import cli
from semantic_pdf_diff.dispatch import Dispatcher
from semantic_pdf_diff.llm import ModelFailure
from semantic_pdf_diff.models import Evidence, Extraction, Judgment, Occurrence, PdfLocator, Section, Settings
from semantic_pdf_diff.progress import NoProgress
from semantic_pdf_diff.provenance import triage_interpreter
from semantic_pdf_diff.situate import (CAPTION, figure_map, find_figures, grounding, quality, situate, targets,
                                      values_in)
from semantic_pdf_diff.store import InterpreterMismatch, Store
from stubs import situating_answer

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

    def test_list_entries_and_repeats_are_not_citations(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            contents = doc.new_page(width=400, height=500)
            contents.insert_text((40, 60), 'Figure 1. Pump arrangement ........ 2')
            page = doc.new_page(width=400, height=500)
            page.insert_text((40, 40), 'Figure 1 shows the pumps; the valves in Figure 1 are shut.')
            diagram(page, 100, 100)
            page.insert_text((100, 290), 'Figure 1: Pump arrangement')
            doc.save(Path(d) / 'l.pdf'); doc.close()
            doc = pymupdf.open(Path(d) / 'l.pdf')
            figures, _ = figure_map(doc, [])
            doc.close()
        (fig1,) = [f for f in figures if f.label == 'figure 1']
        self.assertEqual([(r.page, r.paragraph) for r in fig1.references],
                         [(2, 'Figure 1 shows the pumps; the valves in Figure 1 are shut.')])

    def test_labels_captions_and_panels(self):
        self.assertFalse(CAPTION.match('Figure 1 shows the pumps'))
        self.assertFalse(CAPTION.match('Table 5-1 summarizes the drivetrain'))  # not 'Table 5' plus a separator
        self.assertEqual(CAPTION.match('Table 5-1. Drivetrain').group(2), '5-1')
        self.assertTrue(all(CAPTION.match(t) for t in ('Figure 1: Pumps', 'Table 2 Pump sizes', 'TABLE 3 PUMP SCHEDULE')))
        by_label = {'figure 24': ['fig'], 'sheet A101': ['sheet']}
        self.assertEqual(targets(by_label, 'figure 2-4A'), ['fig'])    # a panel cites its figure
        self.assertEqual(targets(by_label, 'sheet A-101'), ['sheet'])  # hyphens don't matter
        self.assertIsNone(targets(by_label, 'figure 25'))

    def test_heading_bars_and_frames_are_not_figures(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=612, height=792)
            page.draw_rect(pymupdf.Rect(36, 100, 560, 114), color=None, fill=(0.8, 0.85, 0.95))  # heading bar
            page.insert_text((40, 111), '9-3. Dinner Party')
            page.draw_rect(pymupdf.Rect(20, 300, 550, 330))                                     # boxed heading
            page.insert_text((200, 320), 'Contest 10. Energy Balance')
            diagram(page, 100, 450)
            page.insert_text((100, 640), 'Figure 1: Pump arrangement')
            doc.save(Path(d) / 'h.pdf'); doc.close()
            doc = pymupdf.open(Path(d) / 'h.pdf')
            figures = find_figures(doc)
            doc.close()
        self.assertEqual([f.label for f in figures], ['figure 1'])
        self.assertGreater(figures[0].bbox[1], 400)

    def test_figures_are_read_whole_unless_a_tile_holds_them(self):
        from semantic_pdf_diff.extract import visual_regions
        from semantic_pdf_diff.situate import page_figures
        page = self.doc[1]  # figure 1: a 180 x 190 point drawing with its caption
        tags = lambda side: [t for t, _, _ in visual_regions(page, side, page_figures(page, 2))]
        self.assertIn('figure:0', tags(120))      # small tiles cut it: read it whole too
        self.assertNotIn('figure:0', tags(1000))  # one tile holds the whole page
        rect = {t: r for t, r, _ in visual_regions(page, 120, page_figures(page, 2))}['figure:0']
        self.assertGreaterEqual(rect.y1, 290)     # the caption is included

    def test_bands_and_grown_tiles_keep_lines_whole(self):
        from semantic_pdf_diff.extract import _lines, grown, visual_regions
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        for y in range(60, 760, 14):  # a page of text lines...
            page.insert_text((50, y), 'Line of engineering text with a value of 12.5 kW at design load', fontsize=9)
        diagram(page, 150, 300)  # ...and a diagram in the middle
        cut = lambda regions: sum(1 for r in regions for box, _ in _lines(page) if r.intersects(box) and box not in r)
        grid = [r for t, r, _ in visual_regions(page, 420) if t.startswith('tile')]
        bands = [r for t, r, _ in visual_regions(page, 420, tiling='bands') if t.startswith('tile')]
        self.assertGreater(cut(grid), 10)
        self.assertLess(len(bands), len(grid))
        self.assertTrue(bands)
        self.assertEqual(len({(round(b.x0), round(b.x1)) for b in bands}), 1)  # all span the content's full width
        self.assertEqual(cut(bands), 0)
        tile = grid[0]
        self.assertLessEqual(cut([grown(page, tile)]), cut([tile]))

    def test_sheet_details_are_read_one_by_one_with_their_titles(self):
        from semantic_pdf_diff.extract import sheet_details, visual_regions
        doc = pymupdf.open()
        page = doc.new_page(width=2448, height=1584)
        page.draw_rect(pymupdf.Rect(108, 72, 2394, 1512))  # frame
        page.draw_line(pymupdf.Point(2124, 72), pymupdf.Point(2124, 1512))  # title-block border
        page.insert_text((2210, 1480), 'S-522', fontsize=50)
        page.insert_text((2150, 1400), 'DECK DETAILS', fontsize=20)
        for name, title, x, y in [('C1', 'DECKING FOOTING PLAN', 250, 700), ('C3', 'FOOTING ELEVATION', 1200, 700),
                                  ('A1', 'MODULE CONNECTION', 250, 1400)]:
            diagram(page, x + 50, y - 400)
            for i in range(12):  # dimensions and notes in small print
                page.insert_text((x + 60, y - 420 + 14 * i), f'{i + 1}" TYP', fontsize=9)
            page.insert_text((x, y), name, fontsize=25, fontname='cour')  # in its bubble
            page.insert_text((x + 50, y), title, fontsize=25)
            page.insert_text((x + 50, y + 14), '1" = 1\'-0"', fontsize=9)
        for i in range(20):
            page.insert_text((2140, 200 + 14 * i), f'NOTE {i}', fontsize=9)
        found = {n: (t, r) for n, t, r in sheet_details(page)}
        self.assertEqual(set(found) - {''}, {'C1', 'C3', 'A1'})
        self.assertEqual(found['C1'][0], 'DECKING FOOTING PLAN 1" = 1\'-0"')
        for name, (_, rect) in found.items():
            if name:
                others = [r for n, (_, r) in found.items() if n and n != name]
                self.assertFalse(any(abs(rect & r) > 0.02 * abs(rect) for r in others))  # details don't overlap
        self.assertGreaterEqual(found[''][1].x0, 2124)  # the title-block column
        self.assertLess(found['C1'][1].y1, found['A1'][1].y0 + 5)   # C1 ends where A1 begins
        self.assertLess(found['C1'][1].x1, 1200)                    # and before C3
        notes = [n for t, _, n in visual_regions(page, 420, details=True) if t.startswith('tile')]
        self.assertIn('Sheet S-522 DECK DETAILS. Detail C3: FOOTING ELEVATION 1" = 1\'-0"', notes)
        self.assertFalse(any(n for t, _, n in visual_regions(page, 420) if t.startswith('tile')))  # off by default

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

class Sheets(unittest.TestCase):
    def test_sheet_is_one_figure_labelled_from_its_title_block(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            prose = doc.new_page(width=600, height=400)
            prose.insert_text((40, 60), 'Pumps are laid out as shown; see Sheet M201 for the pump room.')
            sheet = doc.new_page(width=1200, height=800)
            for i in range(100):  # few paths: the title block alone makes it a sheet
                x = 40 + (i % 60) * 15
                sheet.draw_line(pymupdf.Point(x, 60 + (i // 60) * 50), pymupdf.Point(x + 10, 90 + (i // 60) * 50))
            for y in (600, 620, 640):
                sheet.insert_text((60, y), 'NOTE', fontsize=8)
            sheet.insert_text((1050, 760), 'M-201', fontsize=40)
            sheet.insert_text((1000, 700), 'PUMP ROOM PLAN', fontsize=20)
            doc.save(Path(d) / 's.pdf'); doc.close()
            doc = pymupdf.open(Path(d) / 's.pdf')
            figures, unresolved = figure_map(doc, [])
            doc.close()
        (drawing,) = figures
        self.assertEqual((drawing.kind, drawing.label, drawing.title, drawing.label_source),
                         ('sheet', 'sheet M-201', 'PUMP ROOM PLAN', 'title block'))
        self.assertEqual(drawing.bbox, (0, 0, 1200, 800))
        self.assertEqual([r.page for r in drawing.references], [1])  # 'M201' cites 'M-201'
        self.assertEqual(unresolved, [])

    def test_many_paths_without_a_title_block_make_a_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=1200, height=800)
            for i in range(600):
                x = 40 + (i % 60) * 15
                page.draw_line(pymupdf.Point(x, 60 + (i // 60) * 50), pymupdf.Point(x + 10, 90 + (i // 60) * 50))
            page.insert_text((60, 700), 'GENERAL NOTE: VERIFY ALL DIMENSIONS', fontsize=9)
            doc.save(Path(d) / 's.pdf'); doc.close()
            doc = pymupdf.open(Path(d) / 's.pdf')
            (drawing,) = find_figures(doc)
            doc.close()
        self.assertEqual((drawing.kind, drawing.label), ('sheet', None))

class Recorder:
    """Answers situating requests from the stub; extraction finds nothing; records requests."""
    def __init__(self, fail=(), **settings):
        self.s = Settings(**settings)
        self.calls, self.cache_hits, self.usage = 0, 0, {}
        self.asked, self.fail = [], fail
    def ask(self, prompt, schema, images=(), key=None):
        self.asked.append((prompt, list(images), key))
        if any(f in prompt for f in self.fail):
            raise ModelFailure('stub failure')
        if schema is Judgment:
            return Judgment(relation='equivalent', rationale='fixture', confidence=.9, same_conditions=True)
        if situating_answer(prompt):
            return schema.model_validate(situating_answer(prompt))
        return Extraction(claims=[], complete=True)

class Requests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.doc = pymupdf.open(build(self.dir / 'f.pdf'))
        self.addCleanup(self.doc.close)
        self.sections = [Section(id='s1', first_page=1, last_page=2, heading_path=['Pumps'], origin='outline'),
                         Section(id='s2', first_page=3, last_page=4, heading_path=['Sheets'], origin='outline',
                                 signals={'characters': 50, 'drawings': 1200})]

    def run_situate(self, client, evidence=()):
        with Dispatcher(client) as dispatch:
            return situate(self.doc, 'sha256:' + 'a' * 64 + '.pdf', list(evidence), self.sections, self.dir, client,
                           dispatch, NoProgress())

    def test_every_figure_in_context_then_sections(self):
        client = Recorder()
        # A label only the figure itself shows (the stub "reads" it from the text after the figure).
        self.doc[2].insert_text((60, 440), 'PRINTED LABEL Sheet M-101')
        tile = ev('ev-tile', 2, 'tile', (90, 90, 300, 300))
        sheet = ev('ev-sheet', 3, 'tile', (50, 240, 260, 410))  # on the uncaptioned diagram
        figures, sections, unresolved, issues = self.run_situate(client, [tile, sheet])
        prompts = [p for p, _, _ in client.asked]
        kinds = ['figure' if 'Situate one figure' in p else 'section' for p in prompts]
        self.assertEqual(kinds, ['figure'] * 4 + ['section'] * 2)  # every figure, one again, then sections
        fig1_prompt, fig1_images, key = client.asked[0]
        self.assertIn('Location: page 2 of 4, middle of the page; section: Pumps', fig1_prompt)
        self.assertIn('Label: figure 1 (from its caption)', fig1_prompt)
        self.assertIn('Caption: Figure 1: Pump arrangement', fig1_prompt)
        # The whole citing paragraph, with where it is.
        self.assertIn('- (page 1, section: Pumps) The pump arrangement is shown in Figure 1. See also Table 7', fig1_prompt)
        self.assertEqual(len(fig1_images), 1)
        self.assertEqual(key[:2], ('triage', 'figure'))
        uncaptioned = prompts[1]
        self.assertIn('Text before it:\nNotes on the arrangement', uncaptioned)
        self.assertIn('Claims extracted from it:\n- e | a | v', uncaptioned)
        self.assertEqual(client.asked[2][1], [])  # a caption without a drawing: no image
        # The model read "Sheet M-101" from the uncaptioned figure: references resolve, and it is asked again.
        (m101,) = [f for f in figures if f.label == 'sheet M-101']
        self.assertEqual((m101.page, m101.label_source), (3, 'model'))
        self.assertEqual(len(m101.references), 2)
        self.assertIn('Paragraphs citing it:\n- (page 3, section: Sheets) Notes on the arrangement', prompts[3])
        self.assertEqual(sorted(r.label for r in unresolved), ['table 7'])
        (fig1,) = [f for f in figures if f.label == 'figure 1']
        self.assertEqual(fig1.about, 'stub figure: Figure 1: Pump arrangement')
        self.assertIn('stub figure: Figure 1', prompts[4])  # sections see their figures' abouts
        self.assertIn('- sheet M-101 (page 3): stub figure', prompts[5])
        self.assertEqual([s.about for s in sections], ['stub section: Pumps', 'stub section: Sheets'])
        self.assertEqual([images for _, images, _ in client.asked[4:]], [[], []])  # no scans: no overviews
        self.assertEqual(issues, [])

    def test_failures_are_issues_and_long_text_is_trimmed(self):
        client = Recorder(fail=('Heading path: Sheets',), context_tokens=2048, output_tokens=256, image_tokens=100)
        long = pymupdf.open()
        for _ in range(2):
            long.new_page().insert_textbox(pymupdf.Rect(20, 20, 580, 820), 'pump flow ' * 200)
        self.doc = long
        self.sections = self.sections[:1] + [self.sections[1].model_copy(update={'first_page': 2, 'last_page': 2})]
        self.sections[0] = self.sections[0].model_copy(update={'last_page': 1})
        _, sections, _, issues = self.run_situate(client)
        self.assertEqual({(i['target'], i['failed']) for i in issues if i['target'].startswith('s')},
                         {('s1', False), ('s2', False), ('s2', True)})
        self.assertEqual(sections[1].about, '')
        self.assertTrue(all(len(p.encode()) < 2048 for p, _, _ in client.asked))

class Storage(unittest.TestCase):
    def pdfs(self, root):
        a = build(root / 'a.pdf')
        b = root / 'b.pdf'
        doc = pymupdf.open(); doc.new_page().insert_text((40, 40), 'Pump rated power 12 kW'); doc.save(b); doc.close()
        return a, b

    def run_cli(self, root, a, b, *extra, client=None):
        client = client or Recorder(vision=False)
        with patch('semantic_pdf_diff.cli.Client', lambda settings, store: client), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main([str(a), str(b), '--out', str(root / 'out'), '--no-vision', *extra])
        return code, client, err.getvalue()

    def situating_calls(self, client):
        return sum(bool(situating_answer(p)) for p, _, _ in client.asked)

    def test_results_are_stored_and_reused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            _, first, _ = self.run_cli(root, a, b)
            self.assertEqual(self.situating_calls(first), 5)  # a: 3 figures + 1 section; b: 1 section
            report = json.loads((root / 'out/evidence.json').read_text())
            self.assertTrue(all(s['about'].startswith('stub section') for s in report['sections']))
            figures = [f for c in report['situation'].values() for f in c['figures'] if f['label']]
            self.assertEqual(sorted(f['label'] for f in figures), ['figure 1', 'figure 2'])
            _, second, _ = self.run_cli(root, a, b)
            self.assertEqual(self.situating_calls(second), 0)
            again = json.loads((root / 'out/evidence.json').read_text())
            self.assertEqual(again['situation'], report['situation'])
            self.assertEqual(again['sections'], report['sections'])
            self.assertEqual({c: x['quality'] for c, x in again['situation'].items()},
                             {c: x['quality'] for c, x in report['situation'].items()})  # checks rerun on loaded results
            page = (root / 'out/report.html').read_text()
            self.assertIn('Situating: figures and sections', page)
            self.assertIn('stub figure: Figure 1: Pump arrangement', page)

    def test_failed_requests_are_retried_next_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            _, _, log = self.run_cli(root, a, b, client=Recorder(fail=('Caption: Figure 2',), vision=False))
            self.assertIn('1 request(s) failed', log)
            _, second, _ = self.run_cli(root, a, b)
            self.assertEqual(self.situating_calls(second), 4)  # a again; b was complete

    def test_a_failed_extraction_task_does_not_block_situating(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            client = Recorder(fail=('SOURCE DATA:\nPump rated power 12 kW',), vision=False)
            code, _, _ = self.run_cli(root, a, b, client=client)
            self.assertEqual(code, 2)
            report = json.loads((root / 'out/evidence.json').read_text())
            self.assertTrue(any(r['status'] == 'failed' for r in report['coverage']))
            self.assertEqual(len(report['situation']), 2)  # both PDFs situated anyway
            _, again, _ = self.run_cli(root, a, b)          # the retry succeeds: b is situated afresh
            self.assertEqual(sum('Describe one section' in p for p, _, _ in again.asked), 1)

    def test_no_situate_skips_the_stage(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            _, client, _ = self.run_cli(root, a, b, '--no-situate')
            self.assertEqual(self.situating_calls(client), 0)
            self.assertEqual(json.loads((root / 'out/evidence.json').read_text())['situation'], {})

    def test_changed_triage_interpreter_needs_a_reset_that_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(root, a, b)
            with Store(root / 'out') as store:
                evidence_before = store.db.execute('SELECT COUNT(*) FROM task').fetchone()[0]
                changed = triage_interpreter(Settings()).model_copy(update={'prompt_hash': 'different'})
                with self.assertRaises(InterpreterMismatch):
                    store.bind(changed)
                preview = store.bind(changed, reset=True, dry_run=True)
                self.assertEqual(preview['situated_content'], 2)
                store.bind(changed, reset=True)
                self.assertEqual(store.db.execute('SELECT COUNT(*) FROM situation').fetchone()[0], 0)
                self.assertEqual(store.db.execute('SELECT COUNT(*) FROM task').fetchone()[0], evidence_before)
                self.assertTrue(all(s.about == '' for (c,) in store.db.execute('SELECT DISTINCT content FROM section')
                                    for s in store.sections(c)))

class Quality(unittest.TestCase):
    def test_values_and_names(self):
        about = 'The NREL 5-MW turbine: a 126 m rotor, 90% efficiency at 12.1 rpm; see Figure 3 and 2 pumps'
        self.assertEqual(values_in(about, 'NREL 5-MW baseline'), ['126 m', '90%', '12.1 rpm'])

    def test_grounding(self):
        self.assertEqual(grounding('Blade structural properties along the span',
                                   'Figure 2: Distributed blade structural properties along span'), 1.0)
        self.assertLess(grounding('Offshore mooring line tensions', 'Figure 2: Blade structural properties'), .5)
        self.assertIsNone(grounding('The figure shows', 'anything'))

    def test_flags(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open(build(Path(d) / 'f.pdf'))
            tile = ev('ev-tile', 2, 'tile', (90, 90, 300, 300))
            figures, unresolved = figure_map(doc, [tile])
            fig1 = next(f for f in figures if f.label == 'figure 1')
            fig1.about = 'Pump arrangement rated at 10 kW'                       # a value
            fig2 = next(f for f in figures if f.label == 'figure 2')
            fig2.about = 'Offshore mooring tensions for floating platforms'     # ungrounded
            sections = [Section(id='s1', first_page=1, last_page=2, origin='pages', about='Pump arrangement'),
                        Section(id='s2', first_page=3, last_page=4, origin='pages')]
            q = quality(doc, figures, sections, unresolved, [tile])
            doc.close()
        unlabelled = next(f for f in figures if not f.label)
        found = {(f['target'], f['check']) for f in q['flags']}
        self.assertEqual(found, {(fig1.id, 'values'), (fig2.id, 'grounding'), ('s1', 'shape'),
                                 (unlabelled.id, 'missing')})  # s2 has no claims, so no about is expected
        self.assertEqual(q['references'], {'resolved': 2, 'unresolved': 2, 'rate': .5})
        self.assertEqual(q['figures'], {'total': 3, 'unlabelled': 1, 'labelled_uncited': 1, 'labelled_from_caption': 2,
                                        'labelled_from_title_block': 0, 'labelled_from_model': 0})

if __name__ == '__main__':
    unittest.main()
