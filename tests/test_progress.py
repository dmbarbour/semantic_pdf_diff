import contextlib
import io
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli
from semantic_pdf_diff.progress import Progress, log, requests_log, setup_logging

sys.path.insert(0, str(Path(__file__).parent))
from test_sources import pdf_bytes  # noqa: E402
from test_store import model_server  # noqa: E402

class Heartbeats(unittest.TestCase):
    def setUp(self):
        setup_logging()
        self.addCleanup(setup_logging)

    def test_heartbeat_lines_without_a_terminal(self):
        t = [0.0]
        client = type('C', (), {'usage': {'prompt_tokens': 0, 'completion_tokens': 0}})()
        progress = Progress('extract', client, bar=False, heartbeat=30, clock=lambda: t[0])
        with self.assertLogs('semantic_pdf_diff', level='INFO') as logs:
            progress.add(4)
            progress.finish()
            t[0] = 31
            client.usage['prompt_tokens'] = 3100
            progress.finish('failed')
            progress.add(2)
            progress.close()
        self.assertEqual(len(logs.output), 2)
        # At the heartbeat: 2 of 4 tasks, 3100 tokens in 31 s, 2 tasks left at 2 per 31 s.
        self.assertRegex(logs.output[0], r'extract: 2/4 tasks, 1 failed, (5999|6000) tokens/min, about 0.5 min left')
        self.assertIn('extract: 2 tasks done, 1 failed in 31s', logs.output[1])

    def test_bar_tracks_a_growing_total(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            progress = Progress('compare', bar=True)
            progress.add(3); progress.finish(); progress.add(2); progress.finish()
            self.assertEqual((progress.bar.total, progress.bar.n), (5, 2))
            progress.close()
        self.assertIn('compare', stderr.getvalue())

class Verbosity(unittest.TestCase):
    def tearDown(self):
        setup_logging()

    def levels(self, **kw):
        setup_logging(**kw)
        return log.handlers[0].level, requests_log.getEffectiveLevel()

    def test_levels(self):
        self.assertEqual(self.levels(quiet=True)[0], logging.WARNING)
        self.assertEqual(self.levels(), (logging.INFO, logging.INFO))
        self.assertEqual(self.levels(verbosity=1), (logging.DEBUG, logging.INFO))
        self.assertEqual(self.levels(verbosity=2), (logging.DEBUG, logging.DEBUG))

    def test_cli_log_file_and_request_lines(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, power in (('a.pdf', 10), ('b.pdf', 12)):
                (root / name).write_bytes(pdf_bytes(f'Pump rated power {power} kW'))
            with contextlib.redirect_stderr(io.StringIO()) as err, contextlib.redirect_stdout(io.StringIO()):
                cli.main([str(root / 'a.pdf'), str(root / 'b.pdf'), '--out', str(root / 'out'), '--base-url', url,
                          '--no-vision', '-vv', '--log-file', str(root / 'run.log')])
            logged = (root / 'run.log').read_text()
            self.assertIn('Extraction', logged)
            self.assertIn('ok in', logged)
            self.assertIn('extract:', logged)
            with contextlib.redirect_stderr(io.StringIO()) as quiet, contextlib.redirect_stdout(io.StringIO()):
                cli.main([str(root / 'a.pdf'), str(root / 'b.pdf'), '--out', str(root / 'out'), '--base-url', url,
                          '--no-vision', '-q'])
            self.assertEqual(quiet.getvalue(), '')

class PlanEstimates(unittest.TestCase):
    def test_estimates_and_call_limit_warning(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'a.pdf').write_bytes(pdf_bytes('Pump rated power 10 kW'))
            (root / 'b.pdf').write_bytes(pdf_bytes('Pump rated power 12 kW'))
            config = root / 'c.json'
            config.write_text(json.dumps({'rate_limits': [{'tokens_per_minute': 10000}], 'max_calls': 3}))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cli.main([str(root / 'a.pdf'), str(root / 'b.pdf'), '--plan', '--config', str(config)])
            plan = json.loads(out.getvalue())
            self.assertEqual([s['text_tasks'] for s in plan['sources']], [1, 1])
            total = plan['total']
            self.assertEqual(total['calls'], sum(s['text_tasks'] + s['visual_tasks'] for s in plan['sources']))
            self.assertEqual(total['minutes_at_that_limit'], round(total['tokens'] / 10000, 1))
            self.assertIn('max_calls is 3', plan['warning'])

if __name__ == '__main__':
    unittest.main()
