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

from semantic_pdf_diff import checkup, cli
from semantic_pdf_diff.settings import Settings
from stubs import chat_answer, prompt_of, request_body, serving, source_data, text_pdf
from test_failing_endpoint import failing

EMPTY = {'claims': [], 'complete': True, 'issues': []}

@contextlib.contextmanager
def endpoint(right=True):
    """A stub endpoint answering the checks (its model listed with 65,536 tokens of context; sums, wrong unless
    right; the card read, an image 258 tokens) and a run's requests (a claim for a power in kW, equivalence)."""
    state, codes, real = {'checks': 0, 'requests': 0}, [], checkup.card

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
    with serving(post, get=get) as url, patch.object(checkup, 'card', card):
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
            self.assertIn(f'First use: json, image checked before anything is asked (remembered in {self.memory})',
                          said)
            self.assertIn('  endpoint  ok: 1 models listed, gemma-4 among them (65,536 tokens of context)', said)
            self.assertRegex(said, r'  json      ok: \d+ \+ \d+ = \d+')
            self.assertRegex(said, r'  image     ok: read "[A-Z]{3}-\d{4}"; an image 1000 px square is 258 tokens')
            self.assertEqual(state['checks'], 3)  # a sum, the card, and the card's prompt alone
            self.assertGreater(state['requests'], 3)
            passed = json.loads(self.memory.read_text())['passed']
            self.assertEqual(stat.S_IMODE(os.stat(self.memory).st_mode), 0o600)
            self.assertEqual(sorted(passed), [f'chat {url} gemma-4', f'image {url} gemma-4 1000'])
            self.assertEqual(passed[f'chat {url} gemma-4']['context_tokens'], 65536)
            self.assertEqual(passed[f'image {url} gemma-4 1000']['image_tokens'], 258)
            # calibrated (milestone 5): the window listed, an image's tokens a tenth added, where no layer sets them
            self.assertIn('Calibrated from what was measured: context_tokens 65,536, image_tokens 284 (`config show` '
                          'marks them)', said)
            self.assertEqual(self.extracting(), (65536, 284))
            code, said = compare(self.root, url)  # remembered: nothing checked
            self.assertNotIn('First use', said)
            self.assertEqual(state['checks'], 3)

    def extracting(self):
        """(context_tokens, image_tokens) as the store's extraction was asked with them (evidence.json)."""
        used = json.loads((self.root / 'out' / 'evidence.json').read_text())['interpreters']['extract']['settings']
        return used['context_tokens'], used['image_tokens']

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

    def test_requests_failing_in_a_row_forget_what_was_remembered(self):
        for name, power in (('a.pdf', 10), ('b.pdf', 12)):  # 40 pages a side: more requests than the 25 that stop it
            text_pdf(self.root / name, [f'Pump {k} rated power {power + k} kW' for k in range(40)])
        state = {'requests': 0}
        with serving(failing(state)) as url:
            remembered = checkup.keys(Settings(base_url=url, model='gemma-4'))
            self.memory.parent.mkdir()
            checkup._kept(self.memory, {k: {'at': 'then'} for k in remembered.values()})
            code, said = compare(self.root, url)
        self.assertEqual(code, 5)
        self.assertNotIn('First use', said)  # remembered, so not checked: the requests failed instead
        self.assertIn('Sending stopped', said)
        self.assertEqual(json.loads(self.memory.read_text())['passed'], {})

    def test_config_test_remembers_too(self):
        with endpoint() as (url, state), patch.dict(os.environ, {'OPENAI_BASE_URL': url}):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = cli.main(['config', 'test', '--store', str(self.root / 'none')])
        self.assertEqual(code, 0, out.getvalue())
        memory = Path(os.environ['SEMANTIC_PDF_DIFF_CACHE']) / 'endpoints.json'  # the cache in effect's
        self.addCleanup(memory.unlink)
        self.assertIn(f'chat {url} gemma-4', json.loads(memory.read_text())['passed'])

if __name__ == '__main__':
    unittest.main()
