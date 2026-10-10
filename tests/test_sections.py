import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff import cli
from semantic_pdf_diff.jobs import extract_pdf
from semantic_pdf_diff.sections import pdf_sections
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.provenance import content_id
import stubs
from stubs import ROUND0, source_data

def make_pdf(path, pages, toc=None, metadata=None, height=300):
    return stubs.text_pdf(path, pages, height=height, toc=toc, metadata=metadata)

class Recorder(stubs.Recorder):
    """Records prompts and keys; answers with a claim quoting any 'N kW' in the source."""
    def __init__(self, **settings):
        super().__init__(**settings)
        self.asked = []
    def record(self, prompt, schema, images, key):
        self.asked.append((prompt, key))
        self.images = getattr(self, 'images', []) + [(prompt, list(images))]
    def answer(self, prompt, schema, images, key):
        data = source_data(prompt)
        if ' kW' in data:
            value = data.split(' kW')[0].split()[-1]
            return Extraction(claims=[{'entity': 'pump', 'attribute': 'power', 'value': value, 'unit': 'kW',
                                       'kind': 'text', 'quote': f'{value} kW', 'confidence': .9}], complete=True)
        return Extraction(claims=[], complete=True)

TOC = [[1, 'Intro', 1], [1, 'Design', 2], [2, 'Pumps', 3], [2, 'Fans', 3], [3, 'Deep detail', 4], [1, 'Appendix', 5]]

class SectionDetection(unittest.TestCase):
    def sections(self, pages, toc=None, depth=2, per=20):
        with tempfile.TemporaryDirectory() as d:
            path = make_pdf(Path(d) / 't.pdf', [''] * pages, toc)
            with pymupdf.open(path) as doc:
                return pdf_sections(doc, depth, per)

    def test_outline_sections_by_page(self):
        sections, owner = self.sections(5, TOC)
        self.assertEqual([(x.first_page, x.last_page, x.heading_path) for x in sections],
                         [(1, 1, ['Intro']), (2, 2, ['Design']), (3, 4, ['Design', 'Fans']), (5, 5, ['Appendix'])])
        self.assertTrue(all(x.origin == 'outline' for x in sections))
        self.assertEqual(owner[4].heading_path, ['Design', 'Fans'])

    def test_depth_limit(self):
        sections, owner = self.sections(5, TOC, depth=3)
        self.assertEqual(owner[4].heading_path, ['Design', 'Fans', 'Deep detail'])
        sections, owner = self.sections(5, TOC, depth=1)
        self.assertEqual([x.heading_path for x in sections], [['Intro'], ['Design'], ['Appendix']])

    def test_pages_before_the_first_entry(self):
        sections, _ = self.sections(4, [[1, 'Body', 3]])
        self.assertEqual([(x.first_page, x.last_page, x.heading_path) for x in sections], [(1, 2, []), (3, 4, ['Body'])])

    def test_page_range_fallback(self):
        sections, owner = self.sections(45, per=20)
        self.assertEqual([(x.first_page, x.last_page, x.origin) for x in sections],
                         [(1, 20, 'pages'), (21, 40, 'pages'), (41, 45, 'pages')])
        self.assertEqual(owner[45].id, 'sec3')

class SectionContext(unittest.TestCase):
    def test_heading_path_in_prompt_key_and_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_pdf(Path(d) / 't.pdf', ['Intro text', 'Overview', 'Pump rated power 10 kW', 'More', 'End'], TOC)
            client = Recorder(vision=False, **ROUND0)
            seen = []
            evidence, _ = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client, on_sections=seen.extend)
            prompt, key = next((p, k) for p, k in client.asked if '10 kW' in p)
            self.assertIn('\nSection: Design > Fans\n', prompt)
            self.assertEqual(key[-1], 'Design > Fans')
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].section, next(x.id for x in seen if x.heading_path == ['Design', 'Fans']))
            self.assertTrue(evidence[0].quote_verified)

    def test_titles_on_the_page_divide_it(self):
        from semantic_pdf_diff.sections import SectionIndex, section_text
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            first = doc.new_page(width=400, height=400)
            for y, text in ((40, '1 Pumps'), (80, 'Pump rated power 10 kW'), (200, '2 Fans'), (240, 'Fan rated power 3 kW')):
                first.insert_text((40, y), text)
            doc.new_page(width=400, height=400).insert_text((40, 40), 'Fan motor 5 kW')
            doc.set_toc([[1, '1 Pumps', 1], [1, '2 Fans', 1]])
            path = Path(d) / 't.pdf'
            doc.save(path); doc.close()
            with pymupdf.open(path) as doc:
                sections, index = pdf_sections(doc, 2, 20)
                pumps, fans = sections
                self.assertEqual((pumps.first_page, pumps.last_page, fans.first_page, fans.last_page), (1, 1, 1, 2))
                self.assertLess(pumps.first_y, 40); self.assertGreater(fans.first_y, 150)
                self.assertEqual(pumps.last_y, fans.first_y)
                self.assertIs(index.at(1, 230), fans); self.assertIs(index.at(1, 70), pumps); self.assertIs(index[2], fans)
                self.assertIn('10 kW', section_text(doc, pumps)); self.assertNotIn('3 kW', section_text(doc, pumps))
                self.assertIn('3 kW', section_text(doc, fans)); self.assertIn('5 kW', section_text(doc, fans))
            client = Recorder(vision=False)
            evidence, _ = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
            headings = {k: p.split('\nSection: ', 1)[1].split('\n', 1)[0] for p, _ in client.asked
                        for k in ('10 kW', '3 kW', '5 kW') if k in source_data(p)}
            self.assertEqual(headings, {'10 kW': '1 Pumps', '3 kW': '2 Fans', '5 kW': '2 Fans'})
            self.assertEqual({e.value: e.section for e in evidence}, {'10': 'sec1', '3': 'sec2', '5': 'sec2'})

    def test_visual_claims_take_the_section_where_their_quote_is(self):
        class Seeing(Recorder):
            def ask(self, prompt, schema, images=(), key=None):
                if images:  # 'reads' both values off the image
                    self.asked.append((prompt, key))
                    return Extraction(claims=[{'entity': e, 'attribute': 'power', 'value': v, 'unit': 'kW', 'kind': 'diagram',
                                               'quote': f'{e} rated power {v} kW', 'confidence': .8}
                                              for e, v in (('Pump', '10'), ('Fan', '3'))], complete=True)
                return super().ask(prompt, schema, images, key)
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=400, height=400)
            for y, text in ((40, '1 Pumps'), (80, 'Pump rated power 10 kW'), (200, '2 Fans'), (240, 'Fan rated power 3 kW')):
                page.insert_text((40, y), text)
            doc.set_toc([[1, '1 Pumps', 1], [1, '2 Fans', 1]])
            path = Path(d) / 't.pdf'
            doc.save(path); doc.close()
            client = Seeing(tile_points=1000)  # one tile (and the overview) covers the whole page
            evidence, _ = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
            visual = [p for p, k in client.asked if k and k[1] in ('tile', 'overview')]
            self.assertTrue(visual and all('\nSection: 1 Pumps | 2 Fans\n' in p for p in visual))
            self.assertEqual({e.value: e.section for e in evidence}, {'10': 'sec1', '3': 'sec2'})

    def test_rotated_sheets_tables_and_title_fragments(self):
        from semantic_pdf_diff.sections import heading_y
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=600, height=400)
            for r in range(4):  # a ruled 4 x 2 table
                page.draw_line(pymupdf.Point(100, 100 + 30 * r), pymupdf.Point(400, 100 + 30 * r))
            for c in (100, 250, 400):
                page.draw_line(pymupdf.Point(c, 100), pymupdf.Point(c, 190))
            for r, (a, b) in enumerate((('Item', 'Power'), ('Pump', '10 kW'), ('Fan', '3 kW'))):
                page.insert_text((110, 120 + 30 * r), a); page.insert_text((260, 120 + 30 * r), b)
            page.insert_text((500, 380), 'S-522')  # a sheet number in the title block
            page.set_rotation(90)
            self.assertEqual(heading_y(page, 'S-522 - DECK FOOTING DETAILS'), 0.0)  # a fragment isn't the title
            path = Path(d) / 'r.pdf'
            doc.save(path); doc.close()
            client = Recorder(vision=False)
            evidence, _ = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
            with pymupdf.open(path) as doc:
                native = doc[0].rect * doc[0].derotation_matrix
            tables = [e for e in evidence if e.locator.region == 'table']
            self.assertTrue(tables)
            for e in tables:  # row boxes in unrotated coordinates, like every other locator
                self.assertTrue(pymupdf.Rect(e.locator.bbox) in native + (-1, -1, 1, 1), e.locator.bbox)
                # A displayed row (an unrotated column here), not the whole 300 x 90 table.
                self.assertLess(pymupdf.Rect(e.locator.bbox).get_area(), 0.75 * 300 * 90)

    def test_overviews_and_figures_are_not_refined(self):
        class Partial(Recorder):
            def ask(self, prompt, schema, images=(), key=None):
                if images:
                    self.asked.append((prompt, key))
                    return Extraction(claims=[], complete=False)  # every image answer 'partial'
                return super().ask(prompt, schema, images, key)
        with tempfile.TemporaryDirectory() as d:
            path = make_pdf(Path(d) / 't.pdf', ['Pump rated power 10 kW'], height=600)
            _, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d),
                                      Partial(tile_points=200, refinement_depth=1, **ROUND0))
            tasks = [r['task'] for r in coverage]
            self.assertTrue(any(t.startswith('tile:') and '-r' in t for t in tasks))  # tiles are refined
            self.assertFalse(any(t.startswith(('overview', 'figure')) and '-r' in t for t in tasks))

    def test_query_levers(self):
        from semantic_pdf_diff.provenance import extraction_interpreter
        r0 = lambda **levers: Settings(vision=False, **{**ROUND0, **levers})  # levers relative to round 0
        # A store binds levers: it mustn't mix evidence from different variants. (Answers are shared
        # wherever a variant's queries are the same: they're found by what reaches the model.)
        self.assertNotEqual(extraction_interpreter(r0()).settings, extraction_interpreter(r0(table_filter=True)).settings)
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=400, height=400)
            pad = ' Further description follows in the operating manual for the plant room equipment.' * 2
            for y, text in ((40, 'The pumps described here serve the chilled water loop.' + pad), (160, 'Pump rated power 10 kW.' + pad),
                            (280, 'Both pumps are duty and standby.' + pad)):
                page.insert_textbox(pymupdf.Rect(40, y - 12, 380, y + 90), text, fontsize=9)
            path = Path(d) / 't.pdf'
            doc.save(path); doc.close()
            prompts = {}
            for name, settings in (('base', {'text_bytes': 260}), ('lever', {'context_before': 300, 'context_after': 300,
                                   'text_bytes': 260, 'extract_rules': ['Say which loop a pump serves.']})):
                client = Recorder(vision=False, **{**ROUND0, **settings})
                extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
                prompts[name] = next((p, k) for p, k in client.asked if '10 kW' in source_data(p))
            base_prompt, base_key = prompts['base']
            prompt, key = prompts['lever']
            self.assertNotIn('CONTEXT', base_prompt)
            self.assertIn('CONTEXT (for reference only', prompt)
            self.assertIn('Before: ...The pumps described here serve the chilled water loop.', prompt)
            self.assertIn('After: Both pumps are duty and standby.', prompt)
            self.assertIn('Say which loop a pump serves.', prompt)
            self.assertEqual(len(key), len(base_key) + 1)  # context hash only when context is present

    def test_stem_context_follows_numbered_items_across_pages(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            first = doc.new_page(width=400, height=400)
            first.insert_text((40, 40), '9-2. Cooking', fontsize=14)
            first.insert_text((40, 80), 'a. Reduced points are earned between 16 oz and 80 oz.', fontsize=9)
            second = doc.new_page(width=400, height=400)
            second.insert_text((40, 60), 'c. The starting water weight shall be at least 96 oz.', fontsize=9)
            path = Path(d) / 's.pdf'
            doc.save(path); doc.close()
            client = Recorder(vision=False, stem_context=True)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
            prompt = next(p for p, _ in client.asked if '96 oz' in source_data(p))
            self.assertIn('Within: 9-2. Cooking > a. Reduced points are earned', prompt)
            plain = Recorder(vision=False, stem_context=False)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), plain)
            self.assertFalse(any('Within:' in p for p, _ in plain.asked))

    def test_stem_context_skips_values_in_tables(self):
        from semantic_pdf_diff.stems import stem_index
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=500)
        lines = (('7.3 Baseline Blade-Pitch Controller', 14), ('3.83 -43.73E+6', 9), ('0.6 s', 9),
                 ('7.4 - Final Screen', 9), ('2. install the pump', 9), ('7.4.1', 9), ('Insulation Analysis', 9),
                 ('1.35', 9), ('Partial safety factor', 9), ('23.47', 9), ('-125.30E+6', 9), ('12.5', 9), ('3.1', 9),
                 ('The pump runs at night.', 9))
        for y, (text, size) in enumerate(lines):
            page.insert_text((40, 30 + 20 * y), text, fontsize=size)
        paths = [parents[-1] for _, parents in stem_index(doc)[1]]
        self.assertEqual(paths[1:3], ['7.3 Baseline Blade-Pitch Controller'] * 2)  # "3.83" is a value, not an item
        self.assertEqual(paths[3:5], ['7.4 - Final Screen', '2. install the pump'])  # titled, and next after 7.3
        self.assertEqual(paths[6], '7.4.1 Insulation Analysis')  # a title on the next line
        self.assertEqual(set(paths[7:]), {'7.4.1 Insulation Analysis'})  # a table row, and lone values, aren't items

    def test_each_lever_leaves_its_mark(self):
        """lever_notes (the queries dump's diagnostics) finds what each lever's builder writes: with the
        lever off no query carries its note, with it on some query does."""
        from semantic_pdf_diff.settings import lever_notes
        from test_robustness import Recorder
        from test_settings import document
        off = {'context_before': 0, 'context_after': 0, 'table_context': 0, 'stem_context': False,
               'references': False, 'figure_tasks': False, 'sheet_details': False, 'visual_text_layer': 0,
               'tile_locator': False}
        on = {'context_before': 300, 'context_after': 300, 'table_context': 300, 'stem_context': True,
              'references': True, 'figure_tasks': True, 'sheet_details': True, 'visual_text_layer': 1500,
              'tile_locator': True}
        with tempfile.TemporaryDirectory() as d:
            paths = {sheet: document(Path(d) / f'doc-{sheet}.pdf', 10, sheet) for sheet in (False, True)}
            def notes(settings, sheet=False):
                client = Recorder(lambda source, prompt: Extraction(claims=[], complete=True), **settings)
                path = paths[sheet]
                extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d) / 'out', client)
                return set().union(*(lever_notes(prompt) for _, prompt, _ in client.tasks))
            none = notes(off)
            self.assertEqual(none, {'section'})  # headings come from the outline, whatever the levers
            for lever in on:
                with self.subTest(lever=lever):
                    self.assertIn(lever, notes({**off, lever: on[lever]}, sheet=lever == 'sheet_details'))

    def test_references_bring_definitions_and_cited_captions(self):
        from semantic_pdf_diff.stems import _long_form, glossary
        self.assertEqual(_long_form('LCOE', 'we report the levelized cost of energy'), 'levelized cost of energy')
        self.assertIsNone(_long_form('LCOE', 'we report the annual yield'))
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            first = doc.new_page(width=400, height=400)
            first.insert_text((40, 40), 'The rotor uses a proportional-integral (PI) pitch controller.', fontsize=9)
            second = doc.new_page(width=400, height=400)
            for i in range(16):
                second.draw_rect(pymupdf.Rect(60 + (i % 4) * 45, 60 + (i // 4) * 35, 90 + (i % 4) * 45, 80 + (i // 4) * 35))
            second.insert_text((60, 230), 'Figure 3: Pitch response to a wind step')
            third = doc.new_page(width=400, height=400)
            third.insert_text((40, 60), 'The PI gains give 12 kW of margin (Figure 3, Table 9).', fontsize=9)
            path = Path(d) / 'r.pdf'
            doc.save(path)
            self.assertEqual(glossary(doc), {'PI': 'proportional-integral'})
            doc.close()
            client = Recorder(vision=False, references=True)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
            prompt = next(p for p, _ in client.asked if '12 kW' in source_data(p))
            self.assertIn('Defined elsewhere: PI = proportional-integral', prompt)
            self.assertIn('Cited: Figure 3: Pitch response to a wind step (page 2); Table 9: not found in this document',
                          prompt)
            plain = Recorder(vision=False)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), plain)
            self.assertFalse(any('Defined elsewhere' in p or 'Cited:' in p for p, _ in plain.asked))

    def test_tiles_come_with_a_page_locator_when_asked(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=900, height=900)  # larger than a tile: tiled
            page.insert_text((40, 60), 'Pump rated 12 kW', fontsize=9)
            path = Path(d) / 'big.pdf'
            doc.save(path); doc.close()
            client = Recorder(vision=True, tile_locator=True)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d) / 'on', client)
            tiles = [(p, i) for p, i in client.images if 'Source type: tile' in p]
            self.assertTrue(tiles)
            self.assertTrue(all(len(i) == 2 and str(i[1]).endswith('-where.png') for _, i in tiles))
            self.assertTrue(all('outlined in red' in p for p, _ in tiles))
            overview = [i for p, i in client.images if 'Source type: overview' in p]
            self.assertTrue(overview and all(len(i) == 1 for i in overview))  # only tiles get one
            plain = Recorder(vision=True)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d) / 'off', plain)
            self.assertTrue(all(len(i) <= 1 for _, i in plain.images))

    def test_image_rules_reach_image_tasks_and_make_them_different_requests(self):
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open()
            page = doc.new_page(width=900, height=900)
            page.insert_text((40, 60), 'Pump rated 12 kW', fontsize=9)
            path = Path(d) / 'p.pdf'
            doc.save(path); doc.close()
            keys = {}
            for name, extra in (('plain', {}), ('visual', {'visual_rules': ['Read charts only at labelled ticks.']})):
                client = Recorder(vision=True, **extra)
                extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d) / name, client)
                keys[name] = {k[3]: k for _, k in client.asked if k}
                prompts = {k[3]: p for p, k in client.asked if k}
                if name == 'visual':  # the rule reaches image tasks only
                    self.assertTrue(all(('labelled ticks' in p) == t.startswith(('tile', 'overview', 'figure'))
                                        for t, p in prompts.items()))
            for task, key in keys['plain'].items():  # a fixture must never serve one's answer for the other
                self.assertEqual(key == keys['visual'][task], task.startswith('text'))

    def test_excerpt_quotes_are_accepted_and_paraphrases_are_not(self):
        from semantic_pdf_diff.quotes import excerpted
        text = ('The structural-damping ratio was set to 1% critical in all modes of the isolated tower. '
                'This resulted in an equivalent driveshaft linear-\nspring constant of 867,637,000 N\u2022m/rad.\n'
                'Wind speed Rotor speed Pitch\n22.0 12.1 19.94 -105.90E+6\ngelcoat glass_uniax E1 [Pa] 3.440E+09 4.370E+10')
        for quote in ['structural-damping ratio ... 1% critical', 'The Structural\u2013Damping Ratio was set to 1% critical',
                      'linear-spring constant of 867,637,000 N·m/rad', '22.0 | 12.1 | 19.94 | -105.90E+6',
                      'gelcoat E1 [Pa] 3.440E+09']:
            with self.subTest(quote=quote):
                self.assertTrue(excerpted(quote, text))
        for quote in ['the damping ratio is 5% critical', '1% critical ... structural-damping ratio',
                      'The rotor speed is 12.1 rpm at rated wind speed']:
            with self.subTest(quote=quote):
                self.assertFalse(excerpted(quote, text))
        self.assertFalse(excerpted('gelcoat E1 [Pa] 3.440E+09', text, in_order=False))  # fragments only
        self.assertTrue(excerpted('22.0 | 12.1 | 19.94 | -105.90E+6', text, in_order=False))

    def displayed_page(self, path, rotated, caption=False):
        """One page as displayed (600 x 400): a heading, a paragraph, a lead-in over a ruled table, a note
        beside it, a figure with text around it. Stored upright, or sideways with /Rotate 90."""
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=600) if rotated else doc.new_page(width=600, height=400)
        if rotated:
            page.set_rotation(90)
        at = (lambda x, y: pymupdf.Point(x, y) * page.derotation_matrix) if rotated else pymupdf.Point
        text = lambda x, y, t, size=9: page.insert_text(at(x, y), t, fontsize=size, rotate=90 if rotated else 0)
        text(40, 30, '3.1 Pumps', 12)
        text(40, 50, 'The pumps serve the chilled water loop and run at night.')
        text(40, 70, 'Pump schedule for the chilled water loop:')
        for r in range(4):
            page.draw_line(at(40, 80 + 30 * r), at(340, 80 + 30 * r))
        for c in range(3):
            page.draw_line(at(40 + 150 * c, 80), at(40 + 150 * c, 170))
        for r, (a, b) in enumerate((('Item', 'Power'), ('Pump', '10 kW'), ('Fan', '3 kW'))):
            text(45, 100 + 30 * r, a)
            text(195, 100 + 30 * r, b)
        text(420, 120, 'SHEET NOTES BESIDE THE TABLE')
        text(40, 250, 'Text above the figure describes the pump curve.')
        for i in range(12):  # a figure: a cluster of drawings (a displayed box turned whole: two turned corners
            x, y = 60 + (i % 4) * 40, 270 + (i // 4) * 30  # make a box of no width)
            box = pymupdf.Rect(x, y, x + 25, y + 18)
            page.draw_rect(box * page.derotation_matrix if rotated else box)
        text(40, 380, 'Text below the figure gives the duty point.')
        if caption:
            text(60, 365, 'Figure 2: Pump curve')
        doc.set_toc([[1, '3.1 Pumps', 1]])
        doc.save(path)
        doc.close()
        return path

    def test_a_page_reads_the_same_upright_or_rotated(self):
        """Metamorphic: the same page as displayed, stored upright or sideways (/Rotate), gets the same
        queries and the same situating context (one owner of page coordinates: pages.py)."""
        from semantic_pdf_diff.situate import surroundings
        with tempfile.TemporaryDirectory() as d:
            prompts, around = {}, {}
            for rotated in (False, True):
                path = self.displayed_page(Path(d) / f'page-{rotated}.pdf', rotated)
                client = Recorder(vision=False, table_context=400, context_before=400, context_after=400)
                extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
                prompts[rotated] = sorted(p for p, _ in client.asked)
                with pymupdf.open(path) as doc:
                    page = doc[0]
                    figure = pymupdf.Rect(pymupdf.Point(55, 265) * page.derotation_matrix,
                                          pymupdf.Point(225, 353) * page.derotation_matrix)  # the figure's box, unrotated
                    around[rotated] = surroundings(page, tuple(figure))
            self.assertTrue(any('Above the table: ...' in p and 'Pump schedule for the chilled water loop:' in p
                                for p in prompts[False]))
            self.assertEqual(prompts[False], prompts[True])
            self.assertIn('Text above the figure', around[False][0])
            self.assertEqual(around[False], around[True])  # a figure's surroundings too (situating)

    def test_figures_and_section_text_are_the_same_upright_or_rotated(self):
        """Metamorphic, for situating: the same page as displayed, stored upright or sideways, has the same
        captioned figure (its box as displayed) and the same section text (code review 2026-10-01, item 6)."""
        from semantic_pdf_diff.sections import section_text
        from semantic_pdf_diff.pages import shown
        from semantic_pdf_diff.figures import page_figures
        with tempfile.TemporaryDirectory() as d:
            figures, texts = {}, {}
            for rotated in (False, True):
                path = self.displayed_page(Path(d) / f'page-{rotated}.pdf', rotated, caption=True)
                with pymupdf.open(path) as doc:
                    page = doc[0]
                    figures[rotated] = [(f.caption, tuple(round(v) for v in shown(page, f.bbox)), f.kind)
                                        for f in page_figures(page, 1)]
                    texts[rotated] = sorted(line.strip() for section in pdf_sections(doc, 2, 20)[0]
                                            for line in section_text(doc, section).splitlines() if line.strip())
            self.assertTrue(any(caption == 'Figure 2: Pump curve' for caption, _, _ in figures[False]), figures[False])
            self.assertEqual(figures[False], figures[True])
            self.assertIn('Text below the figure gives the duty point.', texts[False])
            self.assertEqual(texts[False], texts[True])

    def rotated_sheet(self, path):
        """A page rotated 90° (like the drawing sets): a sentence displayed above a table, a note beside it."""
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=600)
        page.set_rotation(90)
        at = lambda x, y: pymupdf.Point(x, y) * page.derotation_matrix  # displayed -> unrotated
        text = lambda x, y, t: page.insert_text(at(x, y), t, fontsize=9, rotate=90)
        text(40, 40, 'Pump schedule for the chilled water loop.')
        text(420, 120, 'SHEET NOTES BESIDE THE TABLE')
        for r in range(4):
            page.draw_line(at(40, 80 + 30 * r), at(340, 80 + 30 * r))
        for c in range(3):
            page.draw_line(at(40 + 150 * c, 80), at(40 + 150 * c, 170))
        for r, (a, b) in enumerate((('Item', 'Power'), ('Pump', '10 kW'), ('Fan', '3 kW'))):
            text(45, 100 + 30 * r, a)
            text(195, 100 + 30 * r, b)
        doc.save(path)
        doc.close()
        return path

    def test_rotated_pages_read_in_displayed_order_and_tables_get_the_text_above(self):
        from semantic_pdf_diff.pages import reading_blocks
        with tempfile.TemporaryDirectory() as d:
            path = self.rotated_sheet(Path(d) / 'sheet.pdf')
            with pymupdf.open(path) as doc:
                order = [b[4].split()[0] for b in reading_blocks(doc[0])]
            self.assertEqual(order[0], 'Pump')  # unrotated order put the sentence last
            self.assertLess(order.index('Item'), order.index('SHEET'))
            client = Recorder(vision=False, table_context=400)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
            rows = [p for p, _ in client.asked if 'Above the table' in p]
            self.assertTrue(rows)
            self.assertTrue(all('chilled water loop' in p.split('SOURCE DATA')[0] for p in rows))
            self.assertFalse(any('SHEET NOTES' in p.split('SOURCE DATA')[0] for p in rows))  # beside, not above

    def test_table_filter_keeps_tables_and_drops_grids(self):
        from semantic_pdf_diff.tables import real_table
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)
        def grid(x, y, rows, cols, w=150, h=30):
            for r in range(rows + 1):
                page.draw_line(pymupdf.Point(x, y + h * r), pymupdf.Point(x + w * cols, y + h * r))
            for c in range(cols + 1):
                page.draw_line(pymupdf.Point(x + w * c, y), pymupdf.Point(x + w * c, y + h * rows))
        grid(100, 100, 3, 2)   # a real table
        for r, (a, b) in enumerate((('Item', 'Power'), ('Pump', '10 kW'), ('Fan', '3 kW'))):
            page.insert_text((110, 120 + 30 * r), a); page.insert_text((260, 120 + 30 * r), b)
        grid(100, 400, 5, 4, w=100)  # a chart's gridlines: no text in the cells
        page.insert_text((150, 560), 'Wind speed (m/s)')
        verdicts = sorted((t.bbox[1] < 300, real_table(page, t, t.extract())) for t in page.find_tables().tables)
        self.assertIn((True, True), verdicts)    # the table is kept
        self.assertNotIn((False, True), verdicts)  # the grid, if detected at all, is dropped

    def test_split_headings_are_found_and_outline_order_is_kept(self):
        from semantic_pdf_diff.sections import heading_y
        doc = pymupdf.open()
        page = doc.new_page(width=400, height=400)
        page.insert_text((40, 60), 'Contest 9. Home')
        page.insert_text((40, 150), '9-2.'); page.insert_text((90, 150), 'Cooking')  # a numbered heading in two pieces
        page.insert_text((40, 190), 'Rules about cooking')
        self.assertGreater(heading_y(page, '9-2. Cooking'), 130)
        # 'Missing child' isn't on the page: it can't start above its parent, so the parent collapses into it.
        doc.set_toc([[1, 'Contest 9. Home', 1], [2, 'Missing child', 1], [2, '9-2. Cooking', 1]])
        sections, index = pdf_sections(doc, 2, 20)
        self.assertEqual([x.heading_path for x in sections],
                         [['Contest 9. Home', 'Missing child'], ['Contest 9. Home', '9-2. Cooking']])
        self.assertEqual(index.at(1, 180).heading_path[-1], '9-2. Cooking')

    def fake_tables(self, by_page, height=300):
        class Table:
            def __init__(self, bbox, rows): self.bbox, self.rows = bbox, rows
            def extract(self): return self.rows
        def find_tables(page, *a, **k):
            return type('T', (), {'tables': [Table(b, r) for b, r in by_page.get(page.number, [])]})()
        return patch.object(pymupdf.Page, 'find_tables', find_tables)

    def table_prompts(self, by_page):
        with tempfile.TemporaryDirectory() as d, self.fake_tables(by_page):
            path = make_pdf(Path(d) / 't.pdf', ['', ''])
            client = Recorder(vision=False)
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
            return [(k[3], source_data(p)) for p, k in client.asked if k[1] == 'table']

    def test_table_continues_across_pages(self):
        prompts = self.table_prompts({0: [((20, 200, 280, 290), [['Tag', 'Flow'], ['P-1', '10']])],
                                      1: [((20, 10, 280, 80), [['P-2', '12'], ['P-3', '14']])]})
        page2 = [text for task, text in prompts if task.startswith('table:p2')]
        self.assertEqual(len(page2), 2)
        self.assertTrue(all(text.startswith('Header: ["Tag", "Flow"]') for text in page2))
        self.assertIn('"P-2"', page2[0])

    def test_empty_rows_are_skipped_without_renumbering(self):
        prompts = self.table_prompts({0: [((20, 20, 280, 120), [['Tag', 'Flow'], [None, ''], ['P-1', '10']])]})
        self.assertEqual([task for task, _ in prompts], ['table:p1:0:1'])

    def test_repeated_header_is_not_a_row(self):
        prompts = self.table_prompts({0: [((20, 200, 280, 290), [['Tag', 'Flow'], ['P-1', '10']])],
                                      1: [((20, 10, 280, 80), [['Tag', 'Flow'], ['P-2', '12']])]})
        page2 = [text for task, text in prompts if task.startswith('table:p2')]
        self.assertEqual(len(page2), 1)
        self.assertIn('"P-2"', page2[0])

    def test_unrelated_tables_do_not_continue(self):
        for second in [((20, 150, 280, 200), [['A', 'B'], ['1', '2']]),        # not at the top
                       ((20, 10, 280, 80), [['A', 'B', 'C'], ['1', '2', '3']]),  # different width
                       ((20, 10, 280, 80), [['Pump', 'Flow'], ['P-2', '12']])]:   # same form, own header
            with self.subTest(second=second):
                prompts = self.table_prompts({0: [((20, 200, 280, 290), [['Tag', 'Flow'], ['P-1', '10']])], 1: [second]})
                page2 = [text for task, text in prompts if task.startswith('table:p2')]
                self.assertTrue(all(not text.startswith('Header: ["Tag", "Flow"]') for text in page2))

class Provenance(unittest.TestCase):
    def test_document_properties_become_file_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            a = make_pdf(Path(d) / 'a.pdf', ['x'], metadata={'title': 'PS-3  Design\nSummary', 'author': 'Team A'})
            b = make_pdf(Path(d) / 'b.pdf', ['y'])
            from semantic_pdf_diff.scan import scan
            files = scan([a, b], describe=cli.document_properties).files
            self.assertEqual(files[0].metadata, {'title': 'PS-3 Design Summary', 'author': 'Team A'})
            self.assertEqual(files[1].metadata, {})
            self.assertEqual(cli.document_properties('notes.md', b'# not a pdf'), {})

    def test_sections_survive_a_rerun_from_the_store(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = make_pdf(root / 'a.pdf', ['Intro', 'Design', 'Pump rated power 10 kW', 'x', 'y'], TOC)
            b = make_pdf(root / 'b.pdf', ['Pump rated power 12 kW'])
            for _ in range(2):
                client = Recorder(vision=False)
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cli.main([str(a), str(b), '--out', str(root / 'out'), '--no-vision'], client=client)
                report = json.loads((root / 'out/report.json').read_text())
                self.assertEqual(len([x for x in report['sections'] if x['origin'] == 'outline']), 4)
                self.assertIn('§ Design &gt; Fans', (root / 'out/report.html').read_text())

if __name__ == '__main__':
    unittest.main()
