import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli
from test_concurrency import jittery_model, make_pdf

UNREACHABLE = 'http://127.0.0.1:9/v1'  # replay must never call the model

class RecordAndReplay(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.a = make_pdf(self.root / 'a.pdf', ['Pump 10 kW, fan 3 kW', 'Chiller 350 kW'])
        self.b = make_pdf(self.root / 'b.pdf', ['Pump 12 kW, fan 3 kW', 'Heater 9 kW'])
        self.fixture = self.root / 'f.sqlite'

    def run_cli(self, out, url, *extra, settings=None):
        config = self.root / f'{out}.json'
        config.write_text(json.dumps({'concurrency': 4, 'tile_points': 180, 'retries': 0, **(settings or {})}))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main([str(self.a), str(self.b), '--out', str(self.root / out), '--base-url', url,
                             '--config', str(config), *extra])
        path = self.root / out / 'report.json'
        return code, json.loads(path.read_text()) if path.exists() else None, err.getvalue()

    def outcome(self, report):
        return {k: report[k] for k in ('evidence', 'coverage', 'findings', 'unmatched', 'sections', 'situation')}

    def record(self, *extra):
        with jittery_model() as (url, state):
            code, report, _ = self.run_cli('live', url, '--fixture', str(self.fixture), '--fixture-mode', 'replay-or-record',
                                           *extra)
        return code, report, state['requests']

    def test_replay_reproduces_a_recorded_run_offline(self):
        code, live, requests = self.record()
        self.assertGreater(requests, 10)
        self.assertEqual(live['usage']['fixture']['recorded'], requests)
        replay_code, replayed, _ = self.run_cli('replay', UNREACHABLE, '--fixture', str(self.fixture))
        self.assertEqual(replay_code, code)
        self.assertEqual(self.outcome(replayed), self.outcome(live))
        self.assertEqual(replayed['usage']['api_calls'], 0)
        self.assertEqual(replayed['usage']['fixture'], {**replayed['usage']['fixture'], 'replayed': requests,
                                                        'recorded': 0, 'missing': 0})

    def test_unrecorded_requests_fail_visibly(self):
        self.record()
        with sqlite3.connect(self.fixture) as db:
            db.execute("DELETE FROM response WHERE rowid IN (SELECT r.rowid FROM response r JOIN request q "
                       "ON q.key = r.key AND q.interpreter = r.interpreter WHERE q.kind = 'extract' LIMIT 2)")
        code, report, log = self.run_cli('replay', UNREACHABLE, '--fixture', str(self.fixture))
        self.assertEqual(code, 2)
        # The two failed tasks are refined into smaller requests, which weren't recorded either.
        missing = report['usage']['fixture']['missing']
        self.assertGreaterEqual(missing, 2)
        self.assertIn(f'{missing} request(s) have no answer', log)
        failed = [r for r in report['coverage'] if r['status'] == 'failed']
        self.assertGreaterEqual(len(failed), 2)  # situating requests can miss too; they aren't coverage tasks
        self.assertTrue(all('No recorded answer' in r['issues'][0] for r in failed))

    def test_recorded_failures_replay_as_failures_and_are_retried_when_recording(self):
        self.record()
        with sqlite3.connect(self.fixture) as db:
            db.execute("UPDATE response SET answer = '', error = 'ValueError: Truncated model output' WHERE rowid IN "
                       "(SELECT r.rowid FROM response r JOIN request q ON q.key = r.key AND q.interpreter = r.interpreter "
                       "WHERE q.kind = 'triage' LIMIT 2)")  # situating failures aren't refined into new requests
        code, report, _ = self.run_cli('replay', UNREACHABLE, '--fixture', str(self.fixture))
        self.assertEqual(report['usage']['fixture']['missing'], 0)
        failed = [i for x in report['situation'].values() for i in x['issues'] if i['failed']]
        self.assertEqual(len(failed), 2)
        self.assertTrue(all('Recorded failure: ValueError: Truncated' in i['issue'] for i in failed))
        with jittery_model() as (url, state):
            self.run_cli('again', url, '--fixture', str(self.fixture), '--fixture-mode', 'replay-or-record')
            self.assertEqual(state['requests'], 2)  # only the recorded failures are asked again
        with sqlite3.connect(self.fixture) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM response WHERE error IS NOT NULL').fetchone()[0], 0)

    def test_prune_keeps_what_the_latest_runs_used(self):
        from semantic_pdf_diff.fixtures import Fixture, _now
        import time
        self.record()
        with sqlite3.connect(self.fixture) as db:  # an answer from an older prompt, never asked for again
            db.execute("INSERT INTO response SELECT 'stale', interpreter, responder, answer, usage, recorded, error, NULL "
                       "FROM response LIMIT 1")
        time.sleep(1.1)
        mark = _now()
        time.sleep(1.1)
        self.run_cli('replay', UNREACHABLE, '--fixture', str(self.fixture))
        with Fixture(self.fixture) as f:
            self.assertEqual(f.prune(mark, dry_run=True)['answers_removed'], 1)
            f.prune(mark)
        _, report, _ = self.run_cli('again', UNREACHABLE, '--fixture', str(self.fixture))
        self.assertEqual(report['usage']['fixture']['missing'], 0)

    def test_responders_and_interpreters_are_kept_apart(self):
        self.record('--responder', 'model-a')
        _, other, _ = self.run_cli('b', UNREACHABLE, '--fixture', str(self.fixture), '--responder', 'model-b')
        self.assertEqual(other['usage']['fixture']['replayed'], 0)
        # A prompt-shaping setting changes the fingerprint: nothing recorded applies.
        _, changed, _ = self.run_cli('c', UNREACHABLE, '--fixture', str(self.fixture), '--responder', 'model-a',
                                     settings={'claims_per_request': 9})
        self.assertEqual(changed['usage']['fixture']['replayed'], 0)
        # The model name isn't part of it: the responder is.
        _, same, _ = self.run_cli('d', UNREACHABLE, '--fixture', str(self.fixture), '--responder', 'model-a',
                                  '--model', 'renamed')
        self.assertEqual(same['usage']['fixture']['missing'], 0)

    def test_packing_is_reproducible_and_packed_fixtures_replay(self):
        _, live, requests = self.record()
        first, second = self.root / 'one.zip', self.root / 'two.zip'
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(['fixtures', 'pack', str(self.fixture), str(first)])
            cli.main(['fixtures', 'pack', str(self.fixture), str(second)])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            cli.main(['fixtures', 'summary', str(first)])
        summary = json.loads(out.getvalue())
        self.assertEqual(sum(a['answers'] for a in summary['answers']), requests)
        self.assertEqual({a['kind'] for a in summary['answers']}, {'extract', 'triage', 'compare'})
        _, replayed, _ = self.run_cli('zip', UNREACHABLE, '--fixture', str(first))
        self.assertEqual(self.outcome(replayed), self.outcome(live))
        code, _, log = self.run_cli('zip2', UNREACHABLE, '--fixture', str(first), '--fixture-mode', 'replay-or-record')
        self.assertEqual(code, 1)
        self.assertIn('pack it', log)

if __name__ == '__main__':
    unittest.main()
