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

    def legacy_fixture(self, run, path):
        """A schema-3 fixture of a recorded run, keyed the old way (tuple and fingerprint), built
        from the run's query log and the new fixture's answers."""
        import hashlib
        from semantic_pdf_diff import provenance
        from semantic_pdf_diff.fixtures import _legacy_fingerprint
        from semantic_pdf_diff.models import Settings
        from semantic_pdf_diff.store import Store
        settings = Settings(**json.loads((self.root / f'{run}.json').read_text()))
        make = {'extract': provenance.extraction_interpreter, 'triage': provenance.triage_interpreter,
                'compare': provenance.comparison_interpreter}
        old = sqlite3.connect(path)
        old.executescript("""
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE request (key TEXT, interpreter TEXT, kind TEXT, region TEXT, content TEXT, key_parts TEXT,
                                  prompt TEXT, images TEXT, schema TEXT, PRIMARY KEY (key, interpreter));
            CREATE TABLE response (key TEXT, interpreter TEXT, responder TEXT, answer TEXT, usage TEXT, recorded TEXT,
                                   error TEXT, used TEXT, PRIMARY KEY (key, interpreter, responder));
            CREATE TABLE interpreter (fingerprint TEXT PRIMARY KEY, role TEXT, description TEXT);
            INSERT INTO meta VALUES ('schema_version', '3');""")
        answers = dict((q, (a, e)) for q, a, e in sqlite3.connect(self.fixture).execute(
            'SELECT query, answer, error FROM response WHERE sample = 0'))
        with Store(self.root / run) as store:
            for q in store.queries():
                parts = list(q['recipe'])
                fingerprint = _legacy_fingerprint(make[parts[0]](settings))
                keyed = list(parts)
                if keyed[0] == 'compare':
                    keyed[2] = ''
                key = hashlib.sha256(json.dumps(keyed, sort_keys=True, default=str).encode()).hexdigest()
                old.execute('INSERT OR IGNORE INTO request VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                            (key, fingerprint, parts[0], parts[1], '', json.dumps(parts), q['prompt'],
                             json.dumps(q['images']), ''))
                answer, error = answers[q['hash']]
                old.execute('INSERT OR IGNORE INTO response VALUES (?, ?, ?, ?, ?, ?, ?, NULL)',
                            (key, fingerprint, 'gemma-4', answer, '{}', '2026-09-01', error))
        old.commit()
        old.close()

    def test_old_fixtures_are_re_keyed_by_replay(self):
        _, live, _ = self.record()
        legacy = self.root / 'v3.sqlite'
        self.legacy_fixture('live', legacy)
        rekeyed = self.root / 'v4.sqlite'
        _, replayed, _ = self.run_cli('rekey', UNREACHABLE, '--fixture', str(rekeyed), '--rekey-from', str(legacy))
        self.assertEqual(replayed['usage']['fixture']['missing'], 0)
        self.assertEqual(replayed['usage']['fixture']['stale'], 0)
        self.assertEqual(self.outcome(replayed), self.outcome(live))
        with sqlite3.connect(rekeyed) as db:  # the original dates come along
            self.assertEqual({d for (d,) in db.execute('SELECT recorded FROM response')}, {'2026-09-01'})
        _, again, _ = self.run_cli('rekeyed', UNREACHABLE, '--fixture', str(rekeyed))  # now on its own
        self.assertEqual(again['usage']['fixture']['missing'], 0)
        # An answer recorded for a query that's since changed has no obvious transition: it's let go.
        with sqlite3.connect(legacy) as db:
            db.execute("UPDATE request SET prompt = prompt || ' (older wording)' WHERE kind = 'triage' AND rowid = "
                       "(SELECT MIN(rowid) FROM request WHERE kind = 'triage')")
        _, stale, _ = self.run_cli('rekey2', UNREACHABLE, '--fixture', str(self.root / 'v4b.sqlite'),
                                   '--rekey-from', str(legacy))
        self.assertEqual(stale['usage']['fixture']['stale'], 1)
        self.assertGreaterEqual(stale['usage']['fixture']['missing'], 1)

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

if __name__ == '__main__':
    unittest.main()
