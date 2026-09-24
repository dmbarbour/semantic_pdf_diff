import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff import cli
from semantic_pdf_diff.extract import extract_pdf, pdf_sections
from semantic_pdf_diff.models import Extraction, Judgment, Settings
from semantic_pdf_diff.provenance import content_id

def make_pdf(path, pages, toc=None, metadata=None, height=300):
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(width=300, height=height)
        if text:
            page.insert_text((40, 40), text)
    if toc:
        doc.set_toc(toc)
    if metadata:
        doc.set_metadata(metadata)
    doc.save(path); doc.close()
    return path

class Recorder:
    """Records prompts and keys; answers with a claim quoting any 'N kW' in the source."""
    def __init__(self, **settings):
        self.s = Settings(**settings)
        self.calls, self.cache_hits, self.usage = 0, 0, {}
        self.asked = []
    def ask(self, prompt, schema, images=(), key=None):
        self.asked.append((prompt, key))
        if schema is Judgment:
            return Judgment(relation='equivalent', rationale='fixture', confidence=.9, same_conditions=True)
        data = prompt.split('SOURCE DATA:\n')[1]
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
            client = Recorder(vision=False)
            seen = []
            evidence, _ = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client, on_sections=seen.extend)
            prompt, key = next((p, k) for p, k in client.asked if '10 kW' in p)
            self.assertIn('\nSection: Design > Fans\n', prompt)
            self.assertEqual(key[-1], 'Design > Fans')
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0].section, next(x.id for x in seen if x.heading_path == ['Design', 'Fans']))
            self.assertTrue(evidence[0].quote_verified)

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
            return [(k[3], p.split('SOURCE DATA:\n')[1]) for p, k in client.asked if k[1] == 'table']

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
            _, files = cli.register_sources([a, b])
            self.assertEqual(files[0].metadata, {'title': 'PS-3 Design Summary', 'author': 'Team A'})
            self.assertEqual(files[1].metadata, {})

    def test_sections_survive_a_rerun_from_the_store(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = make_pdf(root / 'a.pdf', ['Intro', 'Design', 'Pump rated power 10 kW', 'x', 'y'], TOC)
            b = make_pdf(root / 'b.pdf', ['Pump rated power 12 kW'])
            for _ in range(2):
                client = Recorder(vision=False)
                with patch('semantic_pdf_diff.cli.Client', lambda settings, store: client), \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cli.main([str(a), str(b), '--out', str(root / 'out'), '--no-vision'])
                report = json.loads((root / 'out/report.json').read_text())
                self.assertEqual(len([x for x in report['sections'] if x['origin'] == 'outline']), 4)
                self.assertIn('§ Design &gt; Fans', (root / 'out/report.html').read_text())

if __name__ == '__main__':
    unittest.main()
