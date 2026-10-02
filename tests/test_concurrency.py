import contextlib
import base64
import hashlib
import io
import json
import random
import re
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import pymupdf
from semantic_pdf_diff import cli
from stubs import situating_answer, slow

@contextlib.contextmanager
def jittery_model():
    """Answers depend only on the request's content; latency is random, so requests
    finish out of order. Some tiles are 'incomplete', so refinement children are queued."""
    state = {'requests': 0, 'lock': threading.Lock(), 'active': 0, 'peak': 0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            with state['lock']:
                state['requests'] += 1
                state['active'] += 1
                state['peak'] = max(state['peak'], state['active'])
                broke = state.get('balance') is not None and state['requests'] > state['balance']
            if broke:  # the account ran out: the provider refuses with 402
                with state['lock']:
                    state['active'] -= 1
                self.send_response(402); self.end_headers()
                self.wfile.write(b'{"error": "Insufficient balance"}')
                return
            time.sleep(random.uniform(0, 0.03))
            parts = body['messages'][1]['content']
            prompt = parts[0]['text']
            digest = hashlib.sha256(json.dumps(parts).encode()).hexdigest()
            if 'Compare exactly' in prompt:
                relation = ['equivalent', 'different', 'complementary', 'unrelated'][int(digest, 16) % 4]
                answer = {'relation': relation, 'rationale': 'stub', 'confidence': .9, 'same_conditions': True}
            elif situating_answer(prompt):
                answer = situating_answer(prompt)
            elif len(parts) > 1:  # an image: a claim derived from its pixels
                answer = {'claims': [{'entity': 'drawing', 'attribute': 'label', 'value': digest[:4], 'kind': 'diagram',
                                      'quote': digest[:4], 'confidence': .8}],
                          'complete': int(digest, 16) % 3 != 0, 'issues': []}
            else:
                data = prompt.split('SOURCE DATA:\n')[1]
                claims = [{'entity': 'equipment', 'attribute': 'power', 'value': v, 'unit': 'kW', 'kind': 'text',
                           'quote': f'{v} kW', 'confidence': .9} for v in re.findall(r'(\d+) kW', data)]
                answer = {'claims': claims, 'complete': True, 'issues': []}
            # What reached the model, for tests of what settings change: the body without the model's
            # name or how the answer travels (docs/plans/content-addressed-queries).
            role = 'compare' if 'Compare exactly' in prompt else 'triage' if situating_answer(prompt) else 'extract'
            seen = hashlib.sha256(json.dumps({k: v for k, v in body.items() if k not in ('model', 'stream', 'stream_options')},
                                             sort_keys=True).encode()).hexdigest()
            images = [hashlib.sha256(base64.b64decode(p['image_url']['url'].split(',', 1)[1])).hexdigest()
                      for p in parts[1:] if p.get('type') == 'image_url']
            params = {k: v for k, v in body.items() if k not in ('model', 'messages', 'stream', 'stream_options')}
            with state['lock']:
                state['active'] -= 1
                state.setdefault('queries', []).append((role, seen))
                state.setdefault('transcript', []).append((role, prompt, images, params))
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(answer)}}],
                                         'usage': {'prompt_tokens': 100, 'completion_tokens': 20,
                                                   'estimated_cost': 0.001}}).encode())
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', state
    finally:
        server.shutdown(); server.server_close(); thread.join()

def make_pdf(path, pages):
    doc = pymupdf.open()
    for i, text in enumerate(pages):
        page = doc.new_page(width=400, height=400)
        page.insert_text((40, 40), text)
        page.draw_rect(pymupdf.Rect(60 + 20 * i, 120, 200, 260))
        page.draw_line(pymupdf.Point(200, 190), pymupdf.Point(340, 190 + 30 * i))
    doc.save(path); doc.close()
    return path

@slow
class Determinism(unittest.TestCase):
    def run_with(self, root, a, b, url, workers):
        config = root / f'config-{workers}.json'
        config.write_text(json.dumps({'concurrency': workers, 'tile_points': 180, 'retries': 0}))
        out = root / f'out-{workers}'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cli.main([str(a), str(b), '--out', str(out), '--base-url', url, '--config', str(config)])
        evidence = json.loads((out / 'evidence.json').read_text())
        report = json.loads((out / 'report.json').read_text())
        return {'evidence': evidence['evidence'], 'coverage': evidence['coverage'], 'findings': report['findings'],
                'unmatched': report['unmatched'], 'shared': report['shared']}

    def test_concurrent_and_sequential_runs_agree(self):
        with jittery_model() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = make_pdf(root / 'a.pdf', ['Pump 10 kW, fan 3 kW', 'Chiller 350 kW', 'Valve 1 kW'])
            b = make_pdf(root / 'b.pdf', ['Pump 12 kW, fan 3 kW', 'Chiller 350 kW', 'Heater 9 kW'])
            sequential = self.run_with(root, a, b, url, 1)
            state['peak'] = 0
            concurrent = self.run_with(root, a, b, url, 8)
            self.assertGreater(state['peak'], 1)  # requests really overlapped
            self.assertTrue(any(r['task'].count('-r') for r in sequential['coverage']))  # refinement happened
            self.assertTrue(any(len(e['occurrences']) > 1 for e in sequential['evidence']))  # merging happened
            for part in sequential:
                with self.subTest(part=part):
                    self.assertEqual(concurrent[part], sequential[part])

if __name__ == '__main__':
    unittest.main()
