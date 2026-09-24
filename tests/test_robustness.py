import contextlib
import io
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff.models import Claim, Evidence, Extraction, Judgment, PdfLocator, Settings
from semantic_pdf_diff.llm import Client, ModelFailure, redact_url
from semantic_pdf_diff.compare import numeric_check
from semantic_pdf_diff.extract import extract_pdf, tiles
from semantic_pdf_diff.cli import main

CID = 'sha256:' + 'a' * 64 + '.pdf'
GOOD = {'entity':'primary pump','attribute':'rated power','value':'10','unit':'kW','conditions':'',
        'kind':'text','quote':'10 kW','confidence':.9}

def ev(id, value, unit):
    return Evidence(id=id,content='sha256:' + id[0].lower() * 64 + '.pdf',
                    locator=PdfLocator(page=1,bbox=(0,0,1,1),region='text',task='t'),entity='e',attribute='a',
                    value=value,unit=unit,kind='text',quote='q',confidence=1)

@contextlib.contextmanager
def stub(replies):
    """Serve (status, headers, body) replies in order, repeating the last; records requests."""
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_POST(self):
            seen.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            status, headers, body = replies[min(len(seen), len(replies)) - 1]
            self.send_response(status)
            for k, v in headers.items(): self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())
    server = HTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', seen
    finally:
        server.shutdown(); server.server_close(); thread.join()

def reply(content, **extra):
    return (200, {}, {'choices':[{'finish_reason':'stop','message':{'content':content}}], **extra})

EMPTY = '{"claims":[],"complete":true,"issues":[]}'

class Recorder:
    """Extraction fake: records (source type, prompt, images) and answers via respond()."""
    def __init__(self, respond, **settings):
        self.s = Settings(**settings)
        self.respond, self.tasks = respond, []
    def ask(self, prompt, schema, images=()):
        source = prompt.split('Source type: ')[1].split('\n')[0]
        self.tasks.append((source, prompt, list(images)))
        return self.respond(source, prompt)

def pdf(path, build, width=500, height=500):
    doc = pymupdf.open(); page = doc.new_page(width=width, height=height); build(page); doc.save(path); doc.close()
    return path

class ResponseShapeTests(unittest.TestCase):
    def ask(self, replies, **settings):
        with stub(replies) as (url, seen), tempfile.TemporaryDirectory() as d:
            client = Client(Settings(**{'base_url': url, 'retries': 0, **settings}), Path(d))
            return client.ask('x', Extraction), seen

    def test_null_usage_is_tolerated(self):
        value, _ = self.ask([reply(EMPTY, usage=None)])
        self.assertTrue(value.complete)

    def test_malformed_shapes_become_model_failures(self):
        for body in [{'choices':[{'finish_reason':'stop','message':{'content':None}}]},
                     {'choices':[{'finish_reason':'stop','message':None}]},
                     {'choices':[]}, {'choices':None}, [1, 2]]:
            with self.subTest(body=body), self.assertRaises(ModelFailure):
                self.ask([(200, {}, body)])

    def test_fenced_and_wrapped_json(self):
        for content in ['```json ' + EMPTY + '```', '```\n' + EMPTY + '\n```', 'Here you go: ' + EMPTY + ' Done.']:
            with self.subTest(content=content):
                self.assertTrue(self.ask([reply(content)])[0].complete)

    def test_retry_after_is_honoured(self):
        with patch('semantic_pdf_diff.llm.time.sleep') as sleep:
            value, seen = self.ask([(429, {'Retry-After':'5'}, b'busy'), reply(EMPTY)], retries=1)
        self.assertTrue(value.complete)
        self.assertEqual(len(seen), 2)
        sleep.assert_called_once_with(5.0)

    def test_request_body_options(self):
        _, seen = self.ask([reply(EMPTY)])
        self.assertEqual(seen[0]['temperature'], 0.0)
        self.assertNotIn('seed', seen[0])
        self.assertNotIn('response_format', seen[0])
        _, seen = self.ask([reply(EMPTY)], temperature=None, seed=7, response_format='json_schema')
        self.assertNotIn('temperature', seen[0])
        self.assertEqual(seen[0]['seed'], 7)
        self.assertEqual(seen[0]['response_format']['json_schema']['schema'], Extraction.model_json_schema())

    def test_http_key_warning(self):
        with tempfile.TemporaryDirectory() as d:
            for url, warned in [('http://remote.example/v1', True), ('http://127.0.0.1:8000/v1', False),
                                ('https://remote.example/v1', False)]:
                stream = io.StringIO()
                with self.subTest(url=url), contextlib.redirect_stderr(stream):
                    Client(Settings(base_url=url), Path(d), api_key='k')
                self.assertEqual('unencrypted' in stream.getvalue(), warned)

class ValidationTests(unittest.TestCase):
    def test_salvage_keeps_valid_claims(self):
        result = Extraction.model_validate({'complete': True, 'notes': 'ignored', 'claims': [
            {**GOOD, 'reasoning': 'extra key dropped'},
            {**GOOD, 'unit': None, 'conditions': None, 'approximate': None},
            {**GOOD, 'confidence': 5},
            {**GOOD, 'quote': 'x' * 401},
            'not a claim']})
        self.assertEqual(len(result.claims), 2)
        self.assertFalse(result.complete)
        self.assertIn('Discarded 3 malformed claim(s)', result.issues)

    def test_salvage_caps_claims_and_issues(self):
        result = Extraction.model_validate({'complete': True, 'claims': [GOOD] * 15,
                                            'issues': [f'issue {i}' for i in range(20)]})
        self.assertEqual(len(result.claims), 12)
        self.assertFalse(result.complete)
        self.assertEqual(len(result.issues), 10)

    def test_judgment_ignores_extra_keys(self):
        j = Judgment.model_validate({'relation':'equivalent','rationale':'r','confidence':.9,'same_conditions':True,'notes':'x'})
        self.assertEqual(j.relation, 'equivalent')

    def test_legacy_json_mode(self):
        self.assertEqual(Settings(json_mode=True).response_format, 'json_object')
        self.assertEqual(Settings(json_mode=True, response_format='json_schema').response_format, 'json_schema')
        with patch.dict(os.environ, {'PDF_DIFF_JSON_MODE':'true'}, clear=True):
            self.assertEqual(Settings.from_env().response_format, 'json_object')
        with patch.dict(os.environ, {'PDF_DIFF_RESPONSE_FORMAT':'json_schema'}, clear=True):
            self.assertEqual(Settings.from_env(json_mode=False).response_format, 'none')

class UnitTests(unittest.TestCase):
    def test_prefix_case_is_significant(self):
        self.assertFalse(numeric_check(ev('A-1','5','mW'), ev('B-1','5','MW'))['equal'])
        self.assertTrue(numeric_check(ev('A-1','5000','mW'), ev('B-1','5','W'))['equal'])
        self.assertFalse(numeric_check(ev('A-1','5','mPa'), ev('B-1','5','MPa'))['equal'])

    def test_ambiguous_symbols_abstain(self):
        self.assertIsNone(numeric_check(ev('A-1','5','S'), ev('B-1','5','s')))
        self.assertIsNone(numeric_check(ev('A-1','5','M'), ev('B-1','5','m')))

    def test_unambiguous_case_variants(self):
        self.assertTrue(numeric_check(ev('A-1','10','KW'), ev('B-1','10000','W'))['equal'])
        self.assertTrue(numeric_check(ev('A-1','1','l/s'), ev('B-1','60','L/min'))['equal'])

class TileTests(unittest.TestCase):
    def test_even_spacing_and_overlap(self):
        for w, h, side in [(612, 792, 420), (595, 842, 420), (1191, 842, 300), (420, 420, 420)]:
            with self.subTest(size=(w, h, side)):
                rect = pymupdf.Rect(0, 0, w, h)
                regions = list(tiles(rect, side))
                for axis, span in [(0, w), (1, h)]:
                    starts = sorted({r[axis] for r in regions})
                    gaps = {round(b - a, 6) for a, b in zip(starts, starts[1:])}
                    self.assertLessEqual(len(gaps), 1)
                    self.assertTrue(all(g <= side * 0.82 + 1e-9 for g in gaps))
                    self.assertAlmostEqual(max(r[axis + 2] for r in regions), span)

class ExtractionTests(unittest.TestCase):
    def test_small_text_blocks_share_one_task(self):
        def build(page):
            for i, line in enumerate(['Section 3', 'Primary pump', 'Rated power 10 kW', 'Page 3']):
                page.insert_text((40, 40 + 60 * i), line)
        def respond(source, prompt):
            return Extraction(claims=[GOOD], complete=True)
        with tempfile.TemporaryDirectory() as d:
            client = Recorder(respond, vision=False)
            evidence, _ = extract_pdf(pdf(Path(d)/'t.pdf', build), CID, Path(d), client)
            self.assertEqual([t[0] for t in client.tasks], ['text'])
            self.assertEqual(len(evidence), 1)
            doc = pymupdf.open(Path(d)/'t.pdf')
            block = [b for b in doc[0].get_text('blocks') if '10 kW' in b[4]][0]
            self.assertEqual(evidence[0].locator.bbox, tuple(block[:4]))
            self.assertTrue(evidence[0].quote_verified)

    def test_text_refinement_splits_on_block_boundaries(self):
        def build(page):
            page.insert_text((40, 40), 'Primary pump rated power 10 kW')
            page.insert_text((40, 200), 'Secondary pump rated power 7 kW')
        with tempfile.TemporaryDirectory() as d:
            client = Recorder(lambda s, p: Extraction(claims=[], complete=False), vision=False)
            extract_pdf(pdf(Path(d)/'t.pdf', build), CID, Path(d), client)
            bodies = [p.split('SOURCE DATA:\n')[1] for _, p, _ in client.tasks]
            self.assertEqual(len(bodies), 3)
            self.assertIn('Primary', bodies[1]); self.assertNotIn('Secondary', bodies[1])
            self.assertIn('Secondary', bodies[2]); self.assertNotIn('Primary', bodies[2])

    def fake_tables(self, rows):
        class Table:
            bbox = (10, 10, 400, 100)
            def extract(self): return rows
        return patch.object(pymupdf.Page, 'find_tables', lambda self, *a, **k: type('T', (), {'tables': [Table()]})())

    def test_table_quote_may_span_cells(self):
        claim = {**GOOD, 'kind':'table', 'quote':'Pump 10 kW'}
        with tempfile.TemporaryDirectory() as d, self.fake_tables([['Item','Power'], ['Pump','10 kW']]):
            client = Recorder(lambda s, p: Extraction(claims=[claim] if s == 'table' else [], complete=True), vision=False)
            evidence, coverage = extract_pdf(pdf(Path(d)/'t.pdf', lambda p: None), CID, Path(d), client)
            self.assertEqual(len(evidence), 1)
            self.assertTrue(all(r['status'] != 'partial' for r in coverage))

    def test_table_refinement_keeps_header_and_row_label(self):
        rows = [['Item','Power','Flow','Head','Speed'], ['Pump P1','10 kW','20 L/s','35 m','1450 rpm']]
        with tempfile.TemporaryDirectory() as d, self.fake_tables(rows):
            client = Recorder(lambda s, p: Extraction(claims=[], complete=s != 'table'), vision=False)
            _, coverage = extract_pdf(pdf(Path(d)/'t.pdf', lambda p: None), CID, Path(d), client)
            tables = [p for s, p, _ in client.tasks if s == 'table']
            self.assertEqual(len(tables), 3)
            for prompt in tables:
                header, row = [json.loads(line.split(': ', 1)[1]) for line in prompt.split('SOURCE DATA:\n')[1].splitlines()]
                self.assertEqual((header[0], row[0]), ('Item', 'Pump P1'))
                self.assertEqual(len(header), len(row))
            self.assertEqual(sorted(r['task'] for r in coverage if r['task'].startswith('table')),
                             ['table:0:0', 'table:0:0:c0', 'table:0:0:c1'])

    def test_oversized_table_row_is_split_not_skipped(self):
        rows = [['Item'] + [f'Column {i}' for i in range(8)], ['Pump'] + ['x' * 60 for _ in range(8)]]
        with tempfile.TemporaryDirectory() as d, self.fake_tables(rows):
            client = Recorder(lambda s, p: Extraction(claims=[], complete=True), vision=False, text_bytes=300)
            _, coverage = extract_pdf(pdf(Path(d)/'t.pdf', lambda p: None), CID, Path(d), client)
            tables = [r for r in coverage if r['task'].startswith('table')]
            self.assertGreater(len(tables), 1)
            self.assertTrue(all(r['status'] == 'complete' for r in tables))
            self.assertTrue(all(len(p.split('SOURCE DATA:\n')[1].encode()) <= 300 for s, p, _ in client.tasks if s == 'table'))

    def test_visual_duplicates_are_merged_across_refinement(self):
        claim = {**GOOD, 'kind':'diagram'}
        with tempfile.TemporaryDirectory() as d:
            client = Recorder(lambda s, p: Extraction(claims=[claim], complete=False), refinement_depth=2)
            evidence, coverage = extract_pdf(pdf(Path(d)/'t.pdf', lambda p: None), CID, Path(d), client)
            self.assertTrue(any('-r1-r0' in r['task'] for r in coverage))
            self.assertEqual(len(evidence), 1)
            self.assertTrue(evidence[0].locator.task.startswith('tile:'))

    def test_visual_quotes_checked_against_text_layer(self):
        text = lambda page: page.insert_text((40, 40), 'Pump 10 kW')
        for name, build, quote, expected in [('a', text, '10 kW', True), ('b', text, '99 kW', False),
                                             ('c', lambda page: None, '10 kW', None)]:
            def respond(source, prompt):
                claims = [{**GOOD, 'kind':'chart', 'quote':quote}] if source == 'overview' else []
                return Extraction(claims=claims, complete=True)
            with self.subTest(quote=quote), tempfile.TemporaryDirectory() as d:
                evidence, _ = extract_pdf(pdf(Path(d)/(name + '.pdf'), build, height=300), CID, Path(d),
                                             Recorder(respond, tile_points=1000))
                self.assertEqual([e.quote_verified for e in evidence], [expected])

    def test_rotated_page_bboxes_are_unrotated(self):
        def build(page):
            page.insert_text((40, 40), 'Pump rated power 10 kW')
            page.set_rotation(90)
        def respond(source, prompt):
            return Extraction(claims=[{**GOOD, 'quote':'10 kW', 'entity':source}], complete=True)
        with tempfile.TemporaryDirectory() as d:
            evidence, _ = extract_pdf(pdf(Path(d)/'t.pdf', build, width=800, height=300), CID, Path(d), Recorder(respond))
            self.assertTrue({'text', 'tile', 'overview'} <= {e.entity for e in evidence})
            for e in evidence:
                x0, y0, x1, y1 = e.locator.bbox
                self.assertTrue(-0.01 <= x0 < x1 <= 800.01 and -0.01 <= y0 < y1 <= 300.01, (e.locator.task, e.locator.bbox))
            self.assertTrue(all(e.quote_verified for e in evidence if e.entity == 'tile' and '10 kW' in e.quote))

class CliTests(unittest.TestCase):
    def test_config_must_be_object(self):
        with tempfile.TemporaryDirectory() as d:
            config = Path(d)/'c.json'; config.write_text('[1, 2]')
            path = pdf(Path(d)/'t.pdf', lambda p: None)
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main([str(path), str(path), '--plan', '--config', str(config)]), 1)
            self.assertIn('JSON object', err.getvalue())

    def test_plan_counts_even_tiles(self):
        with tempfile.TemporaryDirectory() as d:
            path = pdf(Path(d)/'t.pdf', lambda p: None, width=612, height=792)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main([str(path), str(path), '--plan'])
            self.assertEqual(json.loads(out.getvalue())['sources'][0]['visual_tasks'], 7)

    def test_url_credentials_redacted(self):
        self.assertEqual(redact_url('https://user:secret@api.example:8443/v1'), 'https://api.example:8443/v1')
        self.assertEqual(redact_url('http://localhost:8000/v1'), 'http://localhost:8000/v1')

if __name__ == '__main__': unittest.main()
