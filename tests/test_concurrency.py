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
from pathlib import Path
import pymupdf
from semantic_pdf_diff import cli
import stubs
from stubs import chat_answer, prompt_of, request_body, serving, situating_answer, slow, source_data, topics_answer

@contextlib.contextmanager
def jittery_model():
    """Answers depend only on the request's content; latency is random, so requests
    finish out of order. Some tiles are 'incomplete', so refinement children are queued."""
    state = {'requests': 0, 'lock': threading.Lock(), 'active': 0, 'peak': 0}
    def post(handler):
        body = request_body(handler)
        with state['lock']:
            state['requests'] += 1
            state['active'] += 1
            state['peak'] = max(state['peak'], state['active'])
            broke = state.get('balance') is not None and state['requests'] > state['balance']
        if broke:  # the account ran out: the provider refuses with 402
            with state['lock']:
                state['active'] -= 1
            handler.send_response(402); handler.end_headers()
            handler.wfile.write(b'{"error": "Insufficient balance"}')
            return
        time.sleep(random.uniform(0, 0.03))
        parts = body['messages'][1]['content']
        prompt = prompt_of(parts)
        # the answer the same whichever comes first, the text or the images (images_first)
        digest = hashlib.sha256(json.dumps(sorted(parts, key=lambda p: p['type'] != 'text')).encode()).hexdigest()
        if prompt.startswith('This is one table'):  # a table's rules query: each row read by itself
            answer = {'reading': 'rows', 'why': 'stub'}
        elif prompt.startswith('This is a block of two columns'):  # the key-value check: a table, as before it
            answer = {'reading': 'table', 'why': 'stub'}
        elif prompt.startswith('You wrote the rules below') or prompt.startswith('You wrote structure rules'):
            answer = {'verdict': 'keep'}
        elif prompt.startswith('These are the lines of one table'):  # its structure: every line a row, the
            worst = re.search(r'row holding line\s+(\d+)', prompt).group(1)  # worst suspect copied as it is
            line = re.search(rf'^{worst}:  (.*?)(   \[.*\])?$', prompt, re.M).group(1)
            answer = {'rules': [], 'examples': [{'line': worst, 'cells': [c.strip() for c in line.split('|')]}]}
        elif 'Compare exactly' in prompt:
            relation = ['equivalent', 'different', 'complementary', 'unrelated'][int(digest, 16) % 4]
            answer = {'relation': relation, 'rationale': 'stub', 'confidence': .9, 'same_conditions': True}
        elif 'Explain a difference' in prompt:
            answer = {'kind': ['changed', 'not_same_item'][int(digest, 16) % 2], 'rationale': 'stub', 'confidence': .8}
        elif situating_answer(prompt):
            answer = situating_answer(prompt)
        elif topics_answer(prompt):
            answer = topics_answer(prompt)
        elif len(parts) > 1:  # an image: a claim derived from its pixels
            answer = {'claims': [{'entity': 'drawing', 'attribute': 'label', 'value': digest[:4], 'kind': 'diagram',
                                  'quote': digest[:4], 'confidence': .8}],
                      'complete': int(digest, 16) % 3 != 0, 'issues': []}
        else:
            data = source_data(prompt)
            claims = [{'entity': 'equipment', 'attribute': 'power', 'value': v, 'unit': 'kW', 'kind': 'text',
                       'quote': f'{v} kW', 'confidence': .9} for v in re.findall(r'(\d+) kW', data)]
            answer = {'claims': claims, 'complete': True, 'issues': []}
        # What reached the model, for tests of what settings change: the body without the model's
        # name or how the answer travels (docs/plans/content-addressed-queries).
        role = ('table-rules' if prompt.startswith('This is one table') else 'key-value'
                if prompt.startswith('This is a block of two columns') else 'table-review'
                if prompt.startswith('You wrote the rules below') else 'table-structure'
                if prompt.startswith('These are the lines of one table') else 'compare' if 'Compare exactly' in prompt
                or 'Explain a difference' in prompt else 'triage' if situating_answer(prompt) else 'topics'
                if topics_answer(prompt) else 'extract')
        seen = hashlib.sha256(json.dumps({k: v for k, v in body.items()
                                          if k not in ('model', 'stream', 'stream_options')},
                                         sort_keys=True).encode()).hexdigest()
        images = [hashlib.sha256(base64.b64decode(p['image_url']['url'].split(',', 1)[1])).hexdigest()
                  for p in parts if p.get('type') == 'image_url']
        params = {k: v for k, v in body.items() if k not in ('model', 'messages', 'stream', 'stream_options')}
        with state['lock']:
            state['active'] -= 1
            state.setdefault('queries', []).append((role, seen))
            state.setdefault('transcript', []).append((role, prompt, images, params, parts[0]['type'] != 'text'))
        chat_answer(handler, answer, usage={'prompt_tokens': 100, 'completion_tokens': 20, 'estimated_cost': 0.001})
    with serving(post, threaded=True) as url:
        yield url, state

def make_pdf(path, pages):
    doc = pymupdf.open()
    for i, text in enumerate(pages):
        page = doc.new_page(width=400, height=400)
        page.insert_text((40, 40), text)
        page.draw_rect(pymupdf.Rect(60 + 20 * i, 120, 200, 260))
        page.draw_line(pymupdf.Point(200, 190), pymupdf.Point(340, 190 + 30 * i))
    doc.set_metadata({})  # the same bytes each time (no date, no fresh id), so the same content id: what's sampled
    doc.save(path, no_new_id=True); doc.close()  # from a run by id (test_rounds' batches) is sampled alike
    return path

@slow
class Determinism(unittest.TestCase):
    def run_with(self, root, a, b, url, workers):
        config = root / f'config-{workers}.json'
        # small tiles of text, sent and halved as before milestone 8: many tasks, refinement and merging
        # small tiles of text, sent and halved as before milestone 8: many tasks, refinement and merging
        config.write_text(json.dumps({'concurrency': workers, 'tile_points': 180, 'retries': 0, **stubs.TILING_BEFORE}))
        out = root / f'out-{workers}'
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cli.main(['compare', str(a), str(b), '--store', str(out), '--base-url', url, '--config', str(config)])
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

    def test_answers_handled_in_any_order_agree(self):
        """Recorded one at a time, then replayed with the answers handled in orders drawn from seeds, as a live run's
        arrive: everything written but the run's own record agrees (the determinism review, 2026-10-12)."""
        with jittery_model() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a = make_pdf(root / 'a.pdf', ['Pump 10 kW, fan 3 kW', 'Chiller 350 kW', 'Valve 1 kW'])
            b = make_pdf(root / 'b.pdf', ['Pump 12 kW, fan 3 kW', 'Chiller 350 kW', 'Heater 9 kW'])
            fixture = root / 'answers.sqlite'
            runs = {}
            for seed in (None, 1, 2, 3):
                config = root / f'config-{seed}.json'
                config.write_text(json.dumps({'concurrency': 1 if seed is None else 4, 'tile_points': 180,
                                              'retries': 0, **stubs.TILING_BEFORE}))
                out = root / f'out-{seed}'
                mode = ['--fixture-mode', 'record-new'] if seed is None else ['--fixture-mode', 'replay',
                                                                             '--responder', 'gemma-4']
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), \
                        (stubs.answers_shuffled(seed) if seed else contextlib.nullcontext()):
                    cli.main(['compare', str(a), str(b), '--store', str(out), '--base-url', url, '--config',
                              str(config), '--fixture', str(fixture), *mode])
                report = json.loads((out / 'report.json').read_text())
                for run_record in ('settings', 'created_at'):  # how the run was set up and when
                    report.pop(run_record)
                runs[seed] = {'evidence': json.loads((out / 'evidence.json').read_text()), 'report': report}
        recorded = runs.pop(None)
        self.assertTrue(recorded['report']['findings'])
        for seed, run in runs.items():
            for part in run:
                with self.subTest(seed=seed, part=part):
                    self.assertEqual(run[part], recorded[part])

class Merging(unittest.TestCase):
    def test_one_query_asked_for_two_samples_isnt_merged(self):
        # code review 2026-10-08: the merge key read a sample method long gone, so the A/A control's fresh regions
        # (another sample of the same query) took the first sample's answer when both were in flight
        from types import SimpleNamespace
        from semantic_pdf_diff.dispatch import Dispatcher
        from semantic_pdf_diff.fixtures import Replayer
        replay = Replayer(SimpleNamespace(), 'replay', 'm', fresh_regions=['tile'])
        client = SimpleNamespace(replay=replay, s=SimpleNamespace(concurrency=1))
        dispatch = Dispatcher.__new__(Dispatcher)
        dispatch.client = client
        tile = SimpleNamespace(query='q1', key=('extract', 'tile'))
        text = SimpleNamespace(query='q1', key=('extract', 'text'))
        self.assertNotEqual(dispatch._same(tile), dispatch._same(text))
        self.assertEqual(dispatch._same(text), dispatch._same(SimpleNamespace(query='q1', key=('extract', 'table'))))

    def test_a_query_asked_again_gets_its_first_outcome(self):
        """A query asked again while the first was in flight was given its outcome, failure included; asked a moment
        later, it was sent again and could be answered (the determinism review, D5): now both get the first's."""
        from types import SimpleNamespace
        from semantic_pdf_diff.dispatch import Dispatcher
        from semantic_pdf_diff.failures import ModelFailure

        class Client:
            def __init__(self):
                self.s, self.sent = SimpleNamespace(concurrency=2), 0
            def prepare(self, prompt, schema, images, key):
                return SimpleNamespace(query=prompt, key=key)
            def cached(self, request):
                return None
            def send(self, request):
                self.sent += 1
                if self.sent == 1:
                    raise ModelFailure("timed out")
                return SimpleNamespace(answer="yes")
            def save(self, request, value):
                pass
        for during in (True, False):
            outcomes = []
            finish = lambda value, error, outcomes=outcomes: outcomes.append((value and value.answer,
                                                                             str(error) if error else None))
            client = Client()
            with Dispatcher(client) as dispatch, self.subTest(during=during):
                dispatch.submit('q', None, (), None, finish)
                if not during:
                    dispatch.drain()
                dispatch.submit('q', None, (), None, finish)
                dispatch.drain()
                self.assertEqual(outcomes, [(None, 'timed out')] * 2)
                self.assertEqual(client.sent, 1)

    def test_the_last_call_goes_to_the_request_asked_first(self):
        """Requests were counted under max_calls as worker threads took the lock, so which was refused followed
        thread scheduling (the determinism review, D6): they're counted as they're asked."""
        import threading
        from semantic_pdf_diff.dispatch import Dispatcher
        from semantic_pdf_diff.llm import Client
        from semantic_pdf_diff.schema import Extraction
        from semantic_pdf_diff.settings import Settings
        release = threading.Event()

        def post(handler):
            request_body(handler)
            release.wait(5)
            chat_answer(handler, {'claims': [], 'complete': True, 'issues': []})
        with serving(post, threaded=True) as url:
            client = Client(Settings(base_url=url, concurrency=4, max_calls=2, retries=0), None)
            found = {}
            with Dispatcher(client) as dispatch:
                for name in ('first', 'second', 'third', 'fourth'):
                    dispatch.submit(name, Extraction, (), None,
                                    lambda value, error, name=name: found.__setitem__(name, type(error).__name__))
                release.set()
                dispatch.drain()
        self.assertEqual(found, {'first': 'NoneType', 'second': 'NoneType', 'third': 'CallLimitReached',
                                 'fourth': 'CallLimitReached'})
        self.assertEqual(client.paused, 'call limit reached (2 requests)')

if __name__ == '__main__':
    unittest.main()
