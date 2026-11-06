"""Each model checked before a run's first request, unless remembered as passing (checkup.first_use;
docs/plans/endpoint-first-use-2026-10-20.md, milestone 4; the owner, 2026-10-20: "we should always auto-test the model
endpoint if it isn't tested in memory")."""
import stubs
import contextlib
import io
import json
import os
import re
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from semantic_pdf_diff import acuity, checkup, cli
from semantic_pdf_diff.settings import Settings
from stubs import chat_answer, prompt_of, request_body, serving, source_data, text_pdf
from test_failing_endpoint import failing

EMPTY = {'claims': [], 'complete': True, 'issues': []}

@contextlib.contextmanager
def endpoint(right=True):
    """A stub endpoint answering the checks (its model listed with 65,536 tokens of context; sums, wrong unless
    right; the card read, an image 258 tokens) and a run's requests (a claim for a power in kW, equivalence)."""
    state, codes, real, drawn, real_card = {'checks': 0, 'requests': 0}, [], checkup.card, [], acuity.card

    def eye_card(folder, rng, size, side):
        path, lines = real_card(folder, rng, size, side)
        drawn.append(lines)
        return path, lines

    def card(folder, rng, side=None):
        path, code = real(folder, rng, side)
        codes.append(code)
        return path, code

    def get(handler):
        handler.send_response(200)
        handler.end_headers()
        listed = [{'id': 'gemma-4', 'metadata': {'context_length': 65536, 'tags': ['vision']}}]
        handler.wfile.write(json.dumps({'data': listed}).encode())

    def post(handler):
        body = request_body(handler)
        state['requests'] += 1
        content = body['messages'][1]['content']
        prompt = prompt_of(content)
        imaged = any(part['type'] == 'image_url' for part in content)
        if prompt.startswith('Add '):
            state['checks'] += 1
            a, b = map(int, re.findall(r'\d+', prompt)[:2])
            return chat_answer(handler, {'sum': a + b + (not right)}, usage={'prompt_tokens': 90,
                                                                             'completion_tokens': 5})
        if prompt == acuity.PROMPT:  # the check's cards' lines: each finds its own among them
            state['checks'] += 1
            return chat_answer(handler, {'lines': [line for lines in drawn[-len(acuity.SIZES):] for line in lines]})
        if prompt == checkup.CODE:
            state['checks'] += 1
            return chat_answer(handler, {'code': codes[-1]}, usage={'prompt_tokens': 120 + 258 * imaged,
                                                                    'completion_tokens': 9})
        if 'Compare exactly' in prompt:
            answer = {'relation': 'equivalent', 'rationale': 'stub', 'confidence': .9, 'same_conditions': True}
        elif 'SOURCE DATA:\n' in prompt and 'kW' in source_data(prompt):
            value = source_data(prompt).split(' kW')[0].split()[-1]
            answer = {'claims': [{'entity': 'pump', 'attribute': 'rated power', 'value': value, 'unit': 'kW',
                                  'kind': 'text', 'quote': f'{value} kW', 'confidence': .9}],
                      'complete': True, 'issues': []}
        else:
            answer = EMPTY
        chat_answer(handler, answer)
    with serving(post, get=get) as url, patch.object(checkup, 'card', card), \
            patch.object(acuity, 'card', eye_card):
        yield url, state

def compare(root, url):
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = cli.main(['compare', str(root / 'a.pdf'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                         '--base-url', url, '--no-situate'])
    return code, err.getvalue()

class FirstUse(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(checkup, 'first_use', stubs.first_use)  # the product's, not the tests' stand-in
        patcher.start()
        self.addCleanup(patcher.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name, power in (('a.pdf', 10), ('b.pdf', 12)):
            text_pdf(self.root / name, [f'Pump rated power {power} kW'])
        self.memory = self.root / 'out' / 'endpoints.json'  # beside the store's answers (the tests' cache)

    def test_a_first_run_checks_each_model_and_the_next_remembers(self):
        with endpoint() as (url, state):
            code, said = compare(self.root, url)
            self.assertNotEqual(code, 5, said)
            self.assertIn(f'First use: json, image, acuity checked before anything is asked (remembered in '
                          f'{self.memory}): no record there yet (each answers cache keeps its own)',
                          said)
            self.assertIn('  endpoint  ok: 1 models listed, gemma-4 among them (65,536 tokens of context)', said)
            self.assertRegex(said, r'  json      ok: \d+ \+ \d+ = \d+')
            self.assertRegex(said, r'  image     ok: read "[A-Z]{3}-\d{4}"; an image 1000 px square is 258 tokens')
            self.assertIn('  acuity    ok: capitals 5 px tall and up read at 1000 px square', said)
            self.assertEqual(state['checks'], 11)  # a sum, the card, the card's prompt alone, and 8 acuity cards
            self.assertGreater(state['requests'], 3)
            passed = json.loads(self.memory.read_text())['passed']
            self.assertEqual(stat.S_IMODE(os.stat(self.memory).st_mode), 0o600)
            self.assertEqual(sorted(passed), [f'acuity {url} gemma-4 1000', f'chat {url} gemma-4',
                                              f'image {url} gemma-4 1000'])
            self.assertEqual(passed[f'acuity {url} gemma-4 1000']['legible_px'], 5)
            self.assertEqual(passed[f'chat {url} gemma-4']['context_tokens'], 65536)
            self.assertEqual(passed[f'image {url} gemma-4 1000']['image_tokens'], 258)
            # calibrated (milestone 5): the window listed, an image's tokens a tenth added, where no layer sets them
            self.assertIn('Calibrated from what was measured: context_tokens 65,536, image_tokens 284 (`config show` '
                          'marks them)', said)
            self.assertEqual(self.extracting(), (65536, 284))
            code, said = compare(self.root, url)  # remembered: not checked, but asked a sum (the ping)
            self.assertNotIn('First use', said)
            self.assertRegex(said, r'The endpoint answers: json in [\d.]+ s \(\$0\.\d{5}; asked each run, the '
                                   r'first-use checks remembered in \S+, what they measured used: context_tokens '
                                   r'65,536, image_tokens 284\)')
            self.assertNotIn('Calibrated', said)  # (the owner, 2026-11-06: "token mentions at the start even when
            # I've already run calibration previously")
            self.assertEqual(state['checks'], 12)  # the ping's sum alone
            self.assertEqual(self.extracting(), (65536, 284))  # used all the same

    def extracting(self):
        """(context_tokens, image_tokens) as the store's extraction was asked with them (evidence.json)."""
        used = json.loads((self.root / 'out' / 'evidence.json').read_text())['interpreters']['extract']['settings']
        return used['context_tokens'], used['image_tokens']

    def test_a_run_says_its_models_and_each_feature_missed_for_want_of_one(self):
        """The owner, 2026-11-02: "always do a quick check on settings before starting, always let users know if
        they've missed an important one." (the settings check)"""
        with endpoint() as (url, state):
            code, said = compare(self.root, url)
            self.assertNotEqual(code, 5, said)
            self.assertIn(f'Models: gemma-4 at {url}; no reranker (not configured); no embedding model (not '
                          'configured)\n', said)
            self.assertIn("Reranking is off: no rerank_model is configured. A reranker scores each claim's candidates, "
                          "and those below rerank_threshold aren't judged.\n  `semantic-pdf-diff config set --user "
                          "rerank_model NAME` names one (`config models rerank` lists the endpoint's), `none` goes "
                          "without and stops this.\n", said)
            self.assertIn("Search by meaning is off: no embed_model is configured.", said)
            with stubs.user_settings({'model': 'gemma-4', 'rerank_model': None, 'embed_model': 'none'}):
                code, said = compare(self.root, url)
        self.assertIn(f'Models: gemma-4 at {url}; no reranker (none chosen); no embedding model (none chosen)\n',
                      said)
        self.assertNotIn(' is off', said)

    def test_a_value_set_wins_warned_of_where_the_measure_says_its_unsafe(self):
        with endpoint() as (url, state), stubs.user_settings({'model': 'gemma-4', 'image_tokens': 100,
                                                               'context_tokens': 32768}):
            code, said = compare(self.root, url)
        self.assertNotEqual(code, 5, said)
        self.assertIn('image_tokens is 100, but an image 1000 px square was 258 tokens there: requests may be refused '
                      'or cut. `semantic-pdf-diff config unset image_tokens` (with --user, if it\'s the user\'s) uses '
                      'what was measured (284)', said)
        self.assertNotIn('context_tokens is', said)  # smaller than the window: safe
        self.assertNotIn('Calibrated', said)
        self.assertEqual(self.extracting(), (32768, 100))

    def test_config_show_marks_what_was_measured(self):
        with endpoint() as (url, state):
            compare(self.root, url)
        cache = Path(os.environ['SEMANTIC_PDF_DIFF_CACHE'])  # the store's cache, which the tests' runs don't use
        cache.mkdir(exist_ok=True)
        (cache / 'endpoints.json').write_text(self.memory.read_text().replace(url, 'http://localhost:8000/v1'))
        self.addCleanup((cache / 'endpoints.json').unlink)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            cli.main(['config', 'show', '--store', str(self.root / 'out')])
        shown = {line.split()[0]: line for line in out.getvalue().splitlines() if 'tokens ' in line}
        self.assertRegex(shown['context_tokens'], r'^  context_tokens +65536 \(measured\) ')

    def test_a_check_failing_stops_the_run_before_anything_is_asked(self):
        with endpoint(right=False) as (url, state):
            code, said = compare(self.root, url)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn('Stopped: json failed its check, so nothing was asked: `semantic-pdf-diff config test` checks '
                      'again', said)
        self.assertEqual(state['requests'], state['checks'])
        self.assertNotIn(f'chat {url} gemma-4', json.loads(self.memory.read_text())['passed'])

    def test_an_endpoint_out_of_reach_or_turning_the_key_away_says_what_to_set(self):
        code, said = compare(self.root, 'http://127.0.0.1:9/v1')  # nothing answers there
        self.assertEqual(code, checkup.FAILED)
        self.assertIn("the endpoint can't be reached: $OPENAI_BASE_URL names the endpoint", said)

        def refused(handler):
            handler.send_response(401)
            handler.end_headers()
        with serving(refused, get=refused) as url:
            code, said = compare(self.root, url)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn("key       FAILED: refused (HTTP 401): OPENAI_API_KEY isn't set", said)
        self.assertIn("the endpoint refused the key: OPENAI_API_KEY holds the one it takes", said)
        self.assertIn('Stopped: endpoint, key, json, image, acuity failed their check', said)

    def remember(self, url, **settings):
        """Every check the settings call for remembered passing, as a run before this one would have left them."""
        remembered = checkup.keys(Settings(base_url=url, model='gemma-4', **settings))
        self.memory.parent.mkdir(exist_ok=True)
        checkup._kept(self.memory, {k: {'at': 'then'} for k in remembered.values()})

    def test_requests_failing_in_a_row_forget_what_was_remembered(self):
        for name, power in (('a.pdf', 10), ('b.pdf', 12)):  # 40 pages a side: more requests than the 25 that stop it
            text_pdf(self.root / name, [f'Pump {k} rated power {power + k} kW' for k in range(40)])
        state = {'requests': 0}

        def post(handler):  # the ping's sum answered, every request of the run's refused
            prompt = prompt_of(request_body(handler)['messages'][1]['content'])
            if prompt.startswith('Add '):
                a, b = map(int, re.findall(r'\d+', prompt)[:2])
                return chat_answer(handler, {'sum': a + b})
            state['requests'] += 1
            handler.send_error(404)
        with serving(post) as url:
            self.remember(url)
            code, said = compare(self.root, url)
        self.assertEqual(code, 5)
        self.assertNotIn('First use', said)  # remembered, so pinged alone: the requests failed instead
        self.assertIn('The endpoint answers: json in', said)
        self.assertIn('Sending stopped', said)
        self.assertEqual(json.loads(self.memory.read_text())['passed'], {})
        with endpoint() as (url, _):  # checked again, saying why (the owner, 2026-11-06: "It seems the initial
            # calibration queries aren't cached?")
            self.remember(url)
            checkup.forget(self.memory, Settings(base_url=url, model='gemma-4'), "a run's requests failed in a row")
            _, said = compare(self.root, url)
        self.assertRegex(said, r'First use: json, image, acuity checked before anything is asked \(remembered in '
                               r'\S+\): forgotten \d{4}-\d\d-\d\d \d\d:\d\d UTC: a run\'s requests failed in a row\n')
        gone = json.loads(self.memory.read_text())['forgotten']
        self.assertFalse([k for k in gone if url in k])  # passed since (the stopped run's endpoint's stay)
        self.assertTrue(gone)

    def test_a_remembered_endpoint_down_stops_the_run_at_once_and_is_checked_again(self):
        """The owner, 2026-11-02: "Even if the endpoints are tested in cache, do a lightweight ping to ensure the
        endpoints are up. [...] Better to fail fast up front even if it costs a little." (the ping)"""
        state = {'requests': 0}
        with serving(failing(state)) as url:
            self.remember(url)
            code, said = compare(self.root, url)
        self.assertEqual(code, checkup.FAILED)
        self.assertNotIn('First use', said)
        self.assertIn('  json      FAILED: ModelFailure: HTTP 404: Not Found', said)
        self.assertIn('Stopped: json failed its check, so nothing was asked', said)
        self.assertEqual(state['requests'], 1)  # the ping's sum alone: 404 isn't retried
        self.assertFalse((self.root / 'out' / 'evidence.json').exists())
        self.assertEqual(json.loads(self.memory.read_text())['passed'], {})  # all checked again next time

    def test_config_test_remembers_too(self):
        with endpoint() as (url, state), patch.dict(os.environ, {'OPENAI_BASE_URL': url}):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = cli.main(['config', 'test', '--store', str(self.root / 'none')])
            memory = Path(os.environ['SEMANTIC_PDF_DIFF_CACHE']) / 'endpoints.json'  # the cache in effect's
            self.addCleanup(memory.unlink)
            _, said = compare(self.root, url)  # a store with an answers cache of its own (the tests'): its own record
        self.assertEqual(code, 0, out.getvalue())
        self.assertIn(f'chat {url} gemma-4', json.loads(memory.read_text())['passed'])
        self.assertIn(f'First use: json, image, acuity checked before anything is asked (remembered in {self.memory}):'
                      f' no record there yet (each answers cache keeps its own); {memory} remembers them, but a run '
                      "reads only its own answers cache's record", said)

    def test_why_a_check_is_asked_again(self):
        url = 'http://127.0.0.1:9/v1'
        self.remember(url, image_side=1000)
        wider = Settings(base_url=url, model='gemma-4', image_side=1200)
        self.assertEqual(checkup.why_missing(wider, self.memory, ['image', 'acuity']),
                         ['remembered at image_side 1000, not 1200'])
        other = Settings(base_url=url, model='gemma-3')
        self.assertEqual(checkup.why_missing(other, self.memory, ['json']), ['never passed there'])
        checkup.record(self.memory, wider, [checkup.Check('image', False, 'read nothing')])
        self.assertEqual([re.sub(r'\d{4}-.* UTC', 'WHEN', x) for x in
                          checkup.why_missing(wider, self.memory, ['image', 'acuity'])],
                         ['image forgotten WHEN: image failed its check',
                          'acuity remembered at image_side 1000, not 1200'])
        self.assertEqual(checkup.forget_model(self.memory, 'gemma-4'), 3)
        self.assertEqual([re.sub(r'\d{4}-.* UTC', 'WHEN', x) for x in checkup.why_missing(
            Settings(base_url=url, model='gemma-4'), self.memory, ['json'])],
            ['forgotten WHEN: `config checks --forget` forgot it'])

if __name__ == '__main__':
    unittest.main()
