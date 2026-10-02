import stubs  # noqa: F401 (a clean environment)
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
        # Every query replays, including those answered once for several tasks (identical queries,
        # e.g. the same page in both documents, share one answer and are asked once).
        self.assertEqual(replayed['usage']['fixture'], {**replayed['usage']['fixture'], 'recorded': 0, 'missing': 0})
        self.assertGreater(replayed['usage']['fixture']['replayed'], live['usage']['fixture']['recorded'])

    def test_replays_form_the_same_reports(self):
        """What a fixture is for: the sample documents and the answers to prior queries are enough to
        form the same reports, byte for byte (SOURCE_DATE_EPOCH fixes when they say they were made)."""
        import os
        from unittest.mock import patch
        self.record()
        with patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '1790000000'}):
            self.run_cli('one', UNREACHABLE, '--fixture', str(self.fixture))
            self.run_cli('two', UNREACHABLE, '--fixture', str(self.fixture))
        for name in ('evidence.json', 'report.json', 'report.html'):
            self.assertEqual((self.root / 'one' / name).read_bytes(), (self.root / 'two' / name).read_bytes(), name)
        self.assertIn('"created_at": "2026-09-21T', (self.root / 'one' / 'report.json').read_text())

    def test_unrecorded_requests_fail_visibly(self):
        self.record()
        with sqlite3.connect(self.fixture) as db:
            db.execute("DELETE FROM response WHERE rowid IN (SELECT r.rowid FROM response r JOIN recipe q "
                       "ON q.query = r.query WHERE q.role = 'extract' LIMIT 2)")
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
            db.execute("UPDATE response SET outcome = 'invalid', answer = '', error = 'ValueError: Truncated model output' "
                       "WHERE rowid IN (SELECT r.rowid FROM response r JOIN recipe q ON q.query = r.query "
                       "WHERE q.role = 'triage' LIMIT 2)")  # situating failures aren't refined into new requests
        code, report, _ = self.run_cli('replay', UNREACHABLE, '--fixture', str(self.fixture))
        self.assertEqual(report['usage']['fixture']['missing'], 0)
        failed = [i for x in report['situation'].values() for i in x['issues'] if i['failed']]
        self.assertEqual(len(failed), 2)
        self.assertTrue(all('Recorded failure: ValueError: Truncated' in i['issue'] for i in failed))
        with jittery_model() as (url, state):  # record-new: failures stay recorded failures, nothing is asked
            code, report, _ = self.run_cli('new', url, '--fixture', str(self.fixture), '--fixture-mode', 'record-new')
            self.assertEqual(state['requests'], 0)
            self.assertEqual(len([i for x in report['situation'].values() for i in x['issues'] if i['failed']]), 2)
        with jittery_model() as (url, state):
            self.run_cli('again', url, '--fixture', str(self.fixture), '--fixture-mode', 'replay-or-record')
            self.assertEqual(state['requests'], 2)  # only the recorded failures are asked again
        with sqlite3.connect(self.fixture) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM response WHERE error IS NOT NULL').fetchone()[0], 0)

    def test_an_aa_control_asks_its_regions_afresh_and_replays_them_apart(self):
        import sqlite3
        self.record()
        with sqlite3.connect(self.fixture) as db:
            tiles = db.execute("SELECT COUNT(DISTINCT query) FROM recipe WHERE role='extract' "
                               "AND region IN ('tile', 'overview')").fetchone()[0]
        self.assertGreater(tiles, 0)
        with jittery_model() as (url, state):  # only the image regions are asked; text replays
            self.run_cli('aa', url, '--fixture', str(self.fixture), '--fixture-mode', 'record-new',
                         '--fresh-regions', 'tile,overview', '--no-situate')
            self.assertGreater(state['requests'], 0)
            self.assertLessEqual(state['requests'], tiles)
        with sqlite3.connect(self.fixture) as db:  # a second sample of each image query, beside the first
            fresh = db.execute("SELECT COUNT(*) FROM response WHERE sample = 1").fetchone()[0]
        self.assertEqual(fresh, state['requests'])  # each asked once, even where both documents share a page
        code, report, _ = self.run_cli('aa-replay', UNREACHABLE, '--fixture', str(self.fixture),
                                       '--fresh-regions', 'tile,overview', '--no-situate')
        self.assertEqual(report['usage']['fixture']['missing'], 0)  # replayed from the control's own answers

    def test_prune_keeps_what_the_latest_runs_used(self):
        from semantic_pdf_diff.fixtures import Fixture, _now
        import time
        self.record()
        with sqlite3.connect(self.fixture) as db:  # an answer from an older prompt, never asked for again
            db.execute("INSERT INTO response SELECT 'stale', responder, sample, outcome, answer, error, usage, recorded, "
                       "NULL FROM response LIMIT 1")
        time.sleep(1.1)
        mark = _now()
        time.sleep(1.1)
        self.run_cli('replay', UNREACHABLE, '--fixture', str(self.fixture))
        with Fixture(self.fixture) as f:
            self.assertEqual(f.prune(mark, dry_run=True)['answers_removed'], 1)
            f.prune(mark)
        _, report, _ = self.run_cli('again', UNREACHABLE, '--fixture', str(self.fixture))
        self.assertEqual(report['usage']['fixture']['missing'], 0)

    def test_prune_refuses_on_a_replay_that_missed(self):
        from semantic_pdf_diff.fixtures import Fixture, FixtureError, _now
        import time
        self.record()
        time.sleep(1.1)
        mark = _now()
        time.sleep(1.1)
        with Fixture(self.fixture) as f:  # nothing ran since the mark: every answer looks unused
            with self.assertRaisesRegex(FixtureError, 'no run replayed'):
                f.prune(mark)
        # A replay under the wrong responder answers nothing, as when .env wasn't loaded (2026-09-28).
        self.run_cli('wrong', UNREACHABLE, '--fixture', str(self.fixture), '--responder', 'someone-else')
        with Fixture(self.fixture) as f:
            refused = f.prune(mark, dry_run=True)['refused']
            self.assertTrue(any('missed' in r for r in refused) and any('would drop' in r for r in refused))
            with self.assertRaises(FixtureError):
                f.prune(mark)
            self.assertGreater(f.db.execute('SELECT COUNT(*) FROM response').fetchone()[0], 0)  # nothing dropped
            f.prune(mark, force=True)
            self.assertEqual(f.db.execute('SELECT COUNT(*) FROM response').fetchone()[0], 0)

    def test_running_out_of_balance_pauses_and_resumes(self):
        from semantic_pdf_diff import ledger
        ledger_path = self.root / 'ledger.jsonl'
        with jittery_model() as (url, state):
            state['balance'] = 12  # the 13th request is refused: 402
            code, _, log = self.run_cli('live', url, '--fixture', str(self.fixture), '--fixture-mode', 'replay-or-record',
                                        '--ledger', str(ledger_path), '--ledger-tag', 'round=r00', '--ledger-tag', 'step=record')
            paid = state['requests']
        self.assertEqual(code, 3)
        self.assertIn('Paused: provider balance exhausted', log)
        with sqlite3.connect(self.fixture) as db:  # running out isn't the model's failure
            self.assertEqual(db.execute('SELECT COUNT(*) FROM response WHERE error IS NOT NULL').fetchone()[0], 0)
        records = ledger.read(ledger_path)
        self.assertEqual(len(records), 12)
        self.assertEqual({(r['round'], r['step']) for r in records}, {('r00', 'record')})
        self.assertAlmostEqual(ledger.spent(ledger_path, round='r00'), 0.012)
        with jittery_model() as (url, state):  # topped up: resume
            code, report, _ = self.run_cli('live2', url, '--fixture', str(self.fixture), '--fixture-mode', 'replay-or-record')
            self.assertNotEqual(code, 3)
            self.assertGreaterEqual(report['usage']['fixture']['replayed'], 12)  # identical queries share answers
            self.assertFalse(any(r['status'] == 'not_reached' for r in report['coverage']))

    def test_cost_cap_stops_sending(self):
        with jittery_model() as (url, state):
            code, report, log = self.run_cli('capped', url, '--max-cost', '0.005')
            self.assertEqual(code, 3)
            self.assertIn('cost cap reached', log)
            self.assertLessEqual(state['requests'], 5 + 4)  # the cap, plus requests already in flight
            self.assertTrue(any(r['status'] == 'not_reached' for r in report['coverage']))

    def test_responders_and_changed_queries_are_kept_apart(self):
        self.record('--responder', 'model-a')
        _, other, _ = self.run_cli('b', UNREACHABLE, '--fixture', str(self.fixture), '--responder', 'model-b')
        self.assertEqual(other['usage']['fixture']['replayed'], 0)
        # A setting that shapes extraction queries changes them: none of their answers applies.
        _, changed, _ = self.run_cli('c', UNREACHABLE, '--fixture', str(self.fixture), '--responder', 'model-a',
                                     settings={'claims_per_request': 9})
        self.assertGreater(changed['usage']['fixture']['missing'], 0)
        with sqlite3.connect(self.fixture) as db:
            extraction = {q for (q,) in db.execute("SELECT query FROM recipe WHERE role = 'extract'")}
        self.assertTrue(extraction)
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
        with sqlite3.connect(self.fixture) as db:
            self.assertEqual(sum(a['answers'] for a in summary['answers']),
                             db.execute('SELECT COUNT(*) FROM response').fetchone()[0])
        self.assertEqual({a['role'] for a in summary['answers']}, {'extract', 'triage', 'compare'})
        self.assertEqual(len(summary['contents']), 2)  # the documents recorded from, for the replay test
        _, replayed, _ = self.run_cli('zip', UNREACHABLE, '--fixture', str(first))
        self.assertEqual(self.outcome(replayed), self.outcome(live))
        code, _, log = self.run_cli('zip2', UNREACHABLE, '--fixture', str(first), '--fixture-mode', 'replay-or-record')
        self.assertEqual(code, 1)
        self.assertIn('pack it', log)


class FolderFixtures(unittest.TestCase):
    def test_answers_survive_a_crash_and_are_packed_later(self):
        from semantic_pdf_diff.fixtures import FOLDER_FIXTURE, FOLDER_WORKING, folder_fixture
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            f = folder_fixture(folder)
            f.record('q1', 'judge', outcome='ok', answer='{"better": "A"}')
            f.close()
            packed = (folder / FOLDER_FIXTURE).read_bytes()
            crashed = folder_fixture(folder)
            crashed.record('q2', 'judge', outcome='ok', answer='{"better": "B"}')
            crashed.db.close()  # the process dies: nothing is packed
            self.assertEqual((folder / FOLDER_FIXTURE).read_bytes(), packed)
            again = folder_fixture(folder)  # the next run finds the paid answer, and packs it
            self.assertEqual(again.answer('q2', 'judge')[1], '{"better": "B"}')
            again.close()
            self.assertNotEqual((folder / FOLDER_FIXTURE).read_bytes(), packed)
            (folder / FOLDER_WORKING).unlink()  # a fresh clone: the zip alone
            fresh = folder_fixture(folder)
            self.assertEqual({q for (q,) in fresh.db.execute('SELECT query FROM response')}, {'q1', 'q2'})
            fresh.close()

    def test_answers_pulled_into_the_zip_are_merged(self):
        import shutil
        from semantic_pdf_diff.fixtures import FOLDER_FIXTURE, folder_fixture
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            here, there = Path(a), Path(b)
            f = folder_fixture(here)
            f.record('q1', 'judge', outcome='ok', answer='{}')
            f.close()
            shutil.copy(here / FOLDER_FIXTURE, there / FOLDER_FIXTURE)
            g = folder_fixture(there)
            g.record('q2', 'judge', outcome='ok', answer='{}')
            g.close()
            shutil.copy(there / FOLDER_FIXTURE, here / FOLDER_FIXTURE)  # pulled: the working file lacks q2
            h = folder_fixture(here)
            self.assertIsNotNone(h.answer('q2', 'judge'))
            h.close()

if __name__ == '__main__':
    unittest.main()
