import stubs  # noqa: F401 (a clean environment)
from stubs import source_data
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff.extract import extract_pdf
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.provenance import content_id

HEADER = 'ACME Pumping Station - Design Report'

class Recorder(stubs.Recorder):
    """Claims the header, 'kW' values and table rows it's shown; records what was sent."""
    def __init__(self, **settings):
        super().__init__(vision=False, **settings)
        self.sent = []
    def answer(self, prompt, schema, images, key):
        data = stubs.source_data(prompt)
        self.sent.append((key[3], data))
        claims = []
        if HEADER in data:
            claims.append({'entity': 'report', 'attribute': 'title', 'value': 'ACME Pumping Station', 'kind': 'text',
                           'quote': 'ACME Pumping Station', 'confidence': .9})
        if data.startswith('Header:'):
            cell = data.split('\nRow: ')[1].split('"')[1]
            claims.append({'entity': 'title block', 'attribute': 'row', 'value': cell, 'kind': 'table',
                           'quote': cell, 'confidence': .9})
        return Extraction(claims=claims, complete=True)

def build(path):
    doc = pymupdf.open()
    for i in range(1, 5):
        page = doc.new_page(width=400, height=400)
        page.insert_text((40, 30), HEADER)
        page.insert_text((40, 120), f'Pump P-{i} rated power {10 + i} kW')
        page.insert_text((40, 360), f'1. Measured at site on day {i}')
        page.insert_text((300, 390), f'Page {i} of 4')
        if i == 4:
            page.insert_text((40, 220), HEADER)  # the same text, elsewhere: not boilerplate
    doc.save(path); doc.close()
    return path

class Table:
    def __init__(self, bbox, rows): self.bbox, self.rows = bbox, rows
    def extract(self): return self.rows

def title_blocks(page, *args, **kw):
    n = page.number + 1
    tables = [Table((250, 300, 390, 340), [['Field', 'Value'], ['Designer', 'ACME'], ['Sheet', f'A-10{n}']])]
    if n == 4:
        tables.append(Table((20, 250, 160, 290), [['Field', 'Value'], ['Designer', 'ACME']]))
    return type('T', (), {'tables': tables})()

class Repeats(unittest.TestCase):
    def run_extraction(self, **settings):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        path = build(Path(self.dir.name) / 'r.pdf')
        client = Recorder(**settings)
        with patch.object(pymupdf.Page, 'find_tables', title_blocks):
            evidence, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(self.dir.name), client)
        return client, evidence, coverage

    def sent_containing(self, client, text):
        return [task for task, data in client.sent if text in data]

    def test_text_is_never_deduplicated(self):
        client, _, coverage = self.run_extraction()
        # The repeated header is sent with its page's text on every page: grouped text
        # costs no extra call, while isolating it would (see the triage review).
        self.assertEqual(sorted({t.split(':')[1] for t in self.sent_containing(client, HEADER)}), ['p1', 'p2', 'p3', 'p4'])
        self.assertFalse([r for r in coverage if r['task'].startswith('text') and r.get('duplicate_of')])
        for i in range(1, 5):
            self.assertTrue(self.sent_containing(client, f'day {i}'))

    def test_table_rows_need_proof_before_following(self):
        client, _, coverage = self.run_extraction()
        designer = [t for t, d in client.sent if '"Designer", "ACME"' in d]
        # Sent on pages 1 and 2 while repetition is unproven, then followed; page 4's
        # copy in another table position is sent too.
        self.assertEqual(sorted(t.split(':')[1] for t in designer), ['p1', 'p2', 'p4'])
        self.assertEqual(sorted(r['page'] for r in coverage if r.get('duplicate_of', '').startswith('table:p1:0')), [3, 4])
        sheets = [t for t, d in client.sent if '"Sheet"' in d]
        self.assertEqual(len(sheets), 4)  # the sheet number differs on every page

    def test_can_be_turned_off(self):
        client, _, coverage = self.run_extraction(dedupe_repeated=False)
        self.assertEqual(len([t for t, d in client.sent if '"Designer", "ACME"' in d]), 5)
        self.assertFalse([r for r in coverage if r.get('duplicate_of')])

    def test_followed_rows_carry_the_first_claims(self):
        _, evidence, _ = self.run_extraction()
        (designer,) = [e for e in evidence if e.value == 'Designer']
        pages = sorted(o.locator.page for o in designer.occurrences)
        self.assertEqual(pages, [1, 2, 3, 4, 4])  # every sighting, including page 4's other table

    def test_followers_carry_every_turn_of_a_continued_answer(self):
        # code review 2026-10-08, A14: followers copied the first turn's claims only, not its continuations'.
        # Latent: only image tasks continue today, and only table rows repeat; continuations forced on here.
        class Continued(Recorder):
            def ask(self, prompt, schema, images=(), key=None):
                answer = super().ask(prompt, schema, images, key)
                if '"Designer", "ACME"' not in source_data(prompt):
                    return answer
                if key[3].endswith('-c1'):  # the rest, asked for
                    return Extraction(claims=[{'entity': 'title block', 'attribute': 'designer', 'value': 'ACME',
                                               'kind': 'table', 'quote': 'ACME', 'confidence': .9}], complete=True)
                return Extraction(claims=[c.model_dump() for c in answer.claims], complete=False)  # at the limit: more
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        path = build(Path(self.dir.name) / 'r.pdf')
        client = Continued(claims_per_request=1)
        with patch.object(pymupdf.Page, 'find_tables', title_blocks), \
                patch.object(type(client.s), 'continuation_limit', lambda self, region: 3):
            evidence, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(self.dir.name), client)
        followed = [r for r in coverage if r.get('duplicate_of', '').startswith('table:p1:0')]
        self.assertTrue(followed)
        self.assertEqual({r['claims'] for r in followed}, {2})
        (acme,) = [e for e in evidence if e.value == 'ACME' and e.attribute == 'designer']
        self.assertIn(3, [o.locator.page for o in acme.occurrences])

    def test_section_signals(self):
        _, _, _ = self.run_extraction()
        from semantic_pdf_diff.extract import pdf_sections
        seen = []
        client = Recorder()
        path = Path(self.dir.name) / 'r.pdf'
        with patch.object(pymupdf.Page, 'find_tables', title_blocks):
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(self.dir.name), client,
                        on_sections=lambda sections: seen.append(sections))
        final = seen[-1]
        self.assertEqual(sum(x.signals['tables'] for x in final), 5)
        self.assertGreaterEqual(sum(x.signals['units'] for x in final), 4)

class ConcurrentFollowers(unittest.TestCase):
    def test_followers_agree_with_sequential_runs(self):
        """Followers may be queued before their first occurrence's answer arrives."""
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from test_concurrency import jittery_model
        from semantic_pdf_diff.llm import Client
        results = []
        with jittery_model() as (url, state), tempfile.TemporaryDirectory() as d:
            path = build(Path(d) / 'r.pdf')
            for workers in (1, 6):
                client = Client(Settings(base_url=url, vision=False, concurrency=workers, retries=0), None)
                with patch.object(pymupdf.Page, 'find_tables', title_blocks):
                    evidence, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
                results.append(([e.model_dump() for e in evidence], coverage))
        self.assertTrue(any(r.get('duplicate_of') for r in results[0][1]))
        self.assertEqual(results[0], results[1])

if __name__ == '__main__':
    unittest.main()
