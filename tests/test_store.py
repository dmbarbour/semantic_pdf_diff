import contextlib
import io
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch
import pymupdf
from semantic_pdf_diff import cli
from semantic_pdf_diff.llm import CacheKeyMismatch, Client
from semantic_pdf_diff.models import Claim, Extraction, Judgment, PdfLocator, Evidence, Settings
from semantic_pdf_diff.provenance import extraction_interpreter
from semantic_pdf_diff.store import InterpreterMismatch, Store, StoreError, StoreInUse

EMPTY = {'claims': [], 'complete': True, 'issues': []}

@contextlib.contextmanager
def model_server():
    """Stub model: one claim for text containing 'kW', equivalence for comparisons."""
    state = {'requests': 0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['requests'] += 1
            prompt = body['messages'][1]['content'][0]['text']
            if 'Compare exactly' in prompt:
                answer = {'relation': 'equivalent', 'rationale': 'stub', 'confidence': .9, 'same_conditions': True}
            elif 'SOURCE DATA:\n' in prompt and 'kW' in prompt.split('SOURCE DATA:\n')[1]:
                value = prompt.split('SOURCE DATA:\n')[1].split(' kW')[0].split()[-1]
                answer = {'claims': [{'entity': 'pump', 'attribute': 'rated power', 'value': value, 'unit': 'kW',
                                      'kind': 'text', 'quote': f'{value} kW', 'confidence': .9}],
                          'complete': True, 'issues': []}
            else:
                answer = EMPTY
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'choices': [{'finish_reason': 'stop',
                                                      'message': {'content': json.dumps(answer)}}]}).encode())
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', state
    finally:
        server.shutdown(); server.server_close(); thread.join()

def make_pdf(path, lines):
    doc = pymupdf.open()
    for text in lines:
        page = doc.new_page(width=300, height=300); page.insert_text((40, 40), text)
    doc.save(path); doc.close()
    return path

def evidence(eid, task, region):
    return Evidence(id=eid, content='sha256:' + 'a' * 64 + '.pdf', entity='e', attribute='a', value='1', kind='text',
                    quote='q', confidence=1, locator=PdfLocator(page=1, bbox=(0, 0, 1, 1), region=region, task=task))

class StoreBasics(unittest.TestCase):
    def test_layout_permissions_and_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / 'store'
            with Store(folder):
                pass
            self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(os.stat(folder / 'store.sqlite').st_mode), 0o600)
            self.assertTrue((folder / 'assets').is_dir())
            with Store(folder):
                pass

    def test_schema_version_mismatch_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            with Store(d):
                pass
            db = sqlite3.connect(Path(d) / 'store.sqlite')
            with db:
                db.execute("UPDATE meta SET value='1' WHERE key='schema_version'")
            db.close()
            with self.assertRaisesRegex(StoreError, 'new store'):
                Store(d)

    def test_single_writer(self):
        with tempfile.TemporaryDirectory() as d, Store(d):
            with self.assertRaises(StoreInUse):
                Store(d)

class Binding(unittest.TestCase):
    def seeded(self, d):
        store = Store(d)
        store.bind(extraction_interpreter(Settings()))
        store.db.execute("INSERT INTO content (id, size) VALUES (?, 1)", ('sha256:' + 'a' * 64 + '.pdf',))
        for task, region in [('text:0.0', 'text'), ('tile:0', 'tile'), ('overview', 'overview')]:
            store.record_task({'content': 'sha256:' + 'a' * 64 + '.pdf', 'task': task, 'status': 'complete'},
                              [evidence(f'ev-{region}', task, region)])
        return store

    def count(self, store, table):
        return store.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    def test_same_interpreter_binds_quietly(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            self.assertEqual(store.bind(extraction_interpreter(Settings())), {})

    def test_changed_interpreter_is_rejected_with_explanation(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            with self.assertRaises(InterpreterMismatch) as caught:
                store.bind(extraction_interpreter(Settings(tile_points=500)))
            self.assertIn('settings.tile_points', caught.exception.differences)
            self.assertIn('--reset', str(caught.exception))
            self.assertEqual(self.count(store, 'evidence'), 3)

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            preview = store.bind(extraction_interpreter(Settings(tile_points=500)), reset=True, dry_run=True)
            self.assertEqual((preview['tasks'], preview['evidence']), (2, 2))
            self.assertEqual(self.count(store, 'evidence'), 3)
            with self.assertRaises(InterpreterMismatch):
                store.bind(extraction_interpreter(Settings(tile_points=500)))

    def test_reset_is_selective(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            store.bind(extraction_interpreter(Settings(tile_points=500)), reset=True)
            regions = {r for (r,) in store.db.execute('SELECT region FROM evidence')}
            self.assertEqual(regions, {'text'})
            self.assertEqual(store.bind(extraction_interpreter(Settings(tile_points=500))), {})
            store.bind(extraction_interpreter(Settings(tile_points=500, model='other-model')), reset=True)
            self.assertEqual(self.count(store, 'evidence'), 0)

class SemanticCache(unittest.TestCase):
    def test_keys_decide_hits_and_debug_check_catches_collisions(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, Store(d) as store:
            client = Client(Settings(base_url=url, retries=0), store)
            key = ('extract', 'text', 'sha256:x.pdf', 'text:0', 'input-hash', None)
            client.ask('first prompt', Extraction, key=key)
            client.ask('first prompt', Extraction, key=key)
            self.assertEqual((state['requests'], client.cache_hits), (1, 1))
            for i in range(2, len(key)):
                changed = key[:i] + ('different',) + key[i + 1:]
                client.ask('first prompt', Extraction, key=changed)
            self.assertEqual(state['requests'], len(key) - 1)
            # A key that ignores a real change in the request is served silently...
            self.assertEqual(client.ask('edited prompt', Extraction, key=key).complete, True)
            self.assertEqual(state['requests'], len(key) - 1)
            # ...unless the debug check compares request bytes.
            checking = Client(Settings(base_url=url, retries=0, cache_check=True), store)
            with self.assertRaises(CacheKeyMismatch):
                checking.ask('edited prompt', Extraction, key=key)

class TaskIdentity(unittest.TestCase):
    def test_pages_never_share_tasks_or_cache_entries(self):
        """Same-sized pages have identical tile rectangles; the page must separate them."""
        from semantic_pdf_diff.extract import extract_pdf
        from semantic_pdf_diff.provenance import content_id
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, Store(Path(d) / 's') as store:
            path = make_pdf(Path(d) / 'two.pdf', ['Pump rated power 10 kW', 'Fan motor 3 kW'])
            cid = content_id(path.read_bytes(), path.name)
            from semantic_pdf_diff.models import FileRef, Source
            store.register(Source(id='s1', name='two', kind='file'), [FileRef(source='s1', path='two.pdf', content=cid)],
                           {cid: path.stat().st_size})
            client = Client(Settings(base_url=url, retries=0, tile_points=200), store)
            evidence, coverage = extract_pdf(path, cid, store.folder, client, on_task=store.record_task)
            tasks = [r['task'] for r in coverage]
            self.assertEqual(len(tasks), len(set(tasks)))
            self.assertEqual(client.cache_hits, 0)
            self.assertEqual(state['requests'], len(tasks))
            self.assertEqual(len(store.coverage(cid)), len(tasks))
            self.assertEqual({e.id for e in store.evidence(cid)}, {e.id for e in evidence})
            self.assertEqual({e.locator.page for e in evidence}, {1, 2})

class ResumeAndReuse(unittest.TestCase):
    def pdfs(self, root):
        return (make_pdf(root / 'a.pdf', ['Pump rated power 10 kW', 'Fan motor 3 kW']),
                make_pdf(root / 'b.pdf', ['Pump rated power 12 kW', 'Fan motor 3 kW']))

    def run_cli(self, a, b, out, url, *extra):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main([str(a), str(b), '--out', str(out), '--base-url', url, '--no-vision', *extra])
        return code, err.getvalue()

    def findings(self, out):
        report = json.loads((out / 'report.json').read_text())
        return sorted((f['a'], f['b'], f['relation']) for f in report['findings'])

    def test_interrupted_run_resumes_without_repeating_calls(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'baseline', url)
            baseline_requests, baseline = state['requests'], self.findings(root / 'baseline')
            state['requests'] = 0

            original = Client.ask
            def interrupting(client, *args, **kw):
                if client.calls >= 2:
                    raise KeyboardInterrupt
                return original(client, *args, **kw)
            with patch.object(Client, 'ask', interrupting), self.assertRaises(KeyboardInterrupt):
                self.run_cli(a, b, root / 'resumed', url)
            self.assertEqual(state['requests'], 2)
            self.run_cli(a, b, root / 'resumed', url)
            self.assertEqual(state['requests'], baseline_requests)
            self.assertEqual(self.findings(root / 'resumed'), baseline)

    def test_rerun_and_renamed_file_reuse_the_store(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'out', url)
            first = state['requests']
            code, log = self.run_cli(a, b, root / 'out', url)
            self.assertIn('Loaded from store: a.pdf', log)
            renamed = root / 'renamed.pdf'; shutil.copy(a, renamed)
            self.run_cli(renamed, b, root / 'out', url)
            self.assertEqual(state['requests'], first)

    def test_failed_tasks_are_retried_on_the_next_run(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            code, _ = self.run_cli(a, b, root / 'out', url, '--max-calls', '1')
            self.assertEqual(code, 2)
            with Store(root / 'out') as store:
                self.assertFalse(store.is_extracted(cli.register_sources([a, b])[1][0].content))
            code, _ = self.run_cli(a, b, root / 'out', url)
            report = json.loads((root / 'out/report.json').read_text())
            self.assertFalse(any(r['status'] == 'failed' for r in report['coverage']))

    def test_changed_settings_need_reset(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'out', url)
            code, log = self.run_cli(a, b, root / 'out', url, '--model', 'another-model')
            self.assertEqual(code, 1)
            self.assertIn('--reset', log)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cli.main([str(a), str(b), '--out', str(root / 'out'), '--model', 'another-model', '--reset', '--dry-run'])
            self.assertGreater(json.loads(out.getvalue())['would_clear']['evidence'], 0)
            code, _ = self.run_cli(a, b, root / 'out', url, '--model', 'another-model', '--reset')
            self.assertEqual(code, 2)  # --no-vision is deliberately incomplete

if __name__ == '__main__':
    unittest.main()
