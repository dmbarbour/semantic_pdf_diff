"""Requests failing in a row stop a run (docs/plans/endpoint-first-use-2026-10-20.md, milestone 1; the owner,
2026-10-20: "Without verbose mode, we can get 13k bad requests without noticing.")."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli
from semantic_pdf_diff.checkup import Sum
from semantic_pdf_diff.failures import EndpointFailing, Invalid, ModelFailure, Truncated
from semantic_pdf_diff.llm import Transport, build_request
from semantic_pdf_diff.settings import Settings
from stubs import chat_answer, serving, text_pdf
from test_store import model_server

def failing(state, answered=()):
    """A stub endpoint refusing every request (HTTP 404, not retried) but the numbered ones answered."""
    def post(handler):
        handler.rfile.read(int(handler.headers['Content-Length']))
        state['requests'] += 1
        if state['requests'] in answered:
            return chat_answer(handler, {'sum': 2})
        handler.send_error(404)
    return post

def run(root, url):
    err = io.StringIO()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
        code = cli.main(['compare', str(root / 'a.pdf'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                         '--base-url', url, '--no-vision', '--no-situate'])
    return code, err.getvalue()

class InARow(unittest.TestCase):
    def test_a_run_whose_requests_all_fail_stops_and_says_so_then_resumes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, power in (('a.pdf', 10), ('b.pdf', 12)):  # 40 pages a side: 80 extraction requests
                text_pdf(root / name, [f'Pump {k} rated power {power + k} kW' for k in range(40)])
            state = {'requests': 0}
            with serving(failing(state)) as url:
                code, said = run(root, url)
            self.assertEqual(code, 5)
            self.assertIn(f'Sending stopped: 25 requests in a row failed at {url}/chat/completions, the last with '
                          'HTTP 404: Not Found; `semantic-pdf-diff config test` checks the endpoint', said)
            self.assertIn('Paused: 25 requests in a row failed', said)
            # those in flight when the 25th failed are sent too (the workers' and the pending bound's), no more
            self.assertGreaterEqual(state['requests'], 25)
            self.assertLess(state['requests'], 40)
            report = json.loads((root / 'out' / 'report.json').read_text())
            statuses = {r['status'] for r in report['coverage']}
            self.assertEqual(statuses - {'skipped'}, {'failed', 'not_reached'})  # (skipped: vision is off)
            with model_server() as (url, served):  # the endpoint mended: every page is asked, the failed ones too
                code, said = run(root, url)
            self.assertNotIn('Sending stopped', said)
            self.assertNotEqual(code, 5)
            report = json.loads((root / 'out' / 'report.json').read_text())
            self.assertEqual({r['status'] for r in report['coverage']} - {'skipped'}, {'complete'})
            self.assertEqual(len([r for r in report['coverage'] if r['claims']]), 80)

    def test_an_answer_starts_the_count_again(self):
        state = {'requests': 0}
        with serving(failing(state, answered={3})) as url:
            transport = Transport(Settings(base_url=url, stop_after_failures=3, retries=0), api_key='')
            ask = lambda: transport.send(build_request(transport.s, 'Add 1 and 1.', Sum))  # noqa: E731
            for _ in range(2):
                self.assertRaises(ModelFailure, ask)
            self.assertEqual(ask().sum, 2)  # the third answered: two failures, then none in a row
            for _ in range(2):
                self.assertRaises(ModelFailure, ask)
            self.assertIsNone(transport.failing)
            with self.assertRaisesRegex(ModelFailure, 'HTTP 404'):  # the third in a row
                ask()
            self.assertRegex(transport.failing, r'^3 requests in a row failed at http://127\.0\.0\.1:\d+/v1/chat/'
                                                r'completions, the last with HTTP 404: Not Found')
            with self.assertRaisesRegex(EndpointFailing, '3 requests in a row'):  # not sent
                ask()
        self.assertEqual(state['requests'], 6)

    def test_answers_cut_short_or_not_json_dont_stop_sending(self):
        """An answer came back: the endpoint works. The owner's run, 2026-10-29, paused on 25 extraction answers in a
        row cut short (dense pages, refined into smaller pieces anyway), and its reranker and judge were never
        asked."""
        state = {'requests': 0}

        def post(handler):
            handler.rfile.read(int(handler.headers['Content-Length']))
            state['requests'] += 1
            if state['requests'] % 2:
                return chat_answer(handler, {'sum': 2}, finish='length')
            return chat_answer(handler, 'not JSON')
        with serving(post) as url:
            transport = Transport(Settings(base_url=url, stop_after_failures=3, retries=0), api_key='')
            for n in range(8):
                with self.assertRaises(Invalid if n % 2 else Truncated):
                    transport.send(build_request(transport.s, 'Add 1 and 1.', Sum))
            self.assertIsNone(transport.failing)
        self.assertEqual(state['requests'], 8)

if __name__ == '__main__':
    unittest.main()
