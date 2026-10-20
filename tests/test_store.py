import contextlib
import io
import json
import os
import shutil
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from semantic_pdf_diff import cli
from semantic_pdf_diff import fixtures
from semantic_pdf_diff.llm import Client
from semantic_pdf_diff.schema import Extraction, PdfLocator, Evidence
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.provenance import content_id, extraction_interpreter
from semantic_pdf_diff.binding import InterpreterMismatch, bind
from semantic_pdf_diff.store import Store, StoreError, StoreInUse
from stubs import chat_answer, prompt_of, request_body, serving, situating_answer, source_data, text_pdf

EMPTY = {'claims': [], 'complete': True, 'issues': []}

@contextlib.contextmanager
def model_server():
    """Stub model: one claim for text containing 'kW', equivalence for comparisons."""
    state = {'requests': 0}
    def post(handler):
        body = request_body(handler)
        state['requests'] += 1
        prompt = prompt_of(body['messages'][1]['content'])
        if 'Compare exactly' in prompt:
            answer = {'relation': 'equivalent', 'rationale': 'stub', 'confidence': .9, 'same_conditions': True}
        elif situating_answer(prompt):
            answer = situating_answer(prompt)
        elif 'SOURCE DATA:\n' in prompt and 'kW' in source_data(prompt):
            value = source_data(prompt).split(' kW')[0].split()[-1]
            answer = {'claims': [{'entity': 'pump', 'attribute': 'rated power', 'value': value, 'unit': 'kW',
                                  'kind': 'text', 'quote': f'{value} kW', 'confidence': .9}],
                      'complete': True, 'issues': []}
        else:
            answer = EMPTY
        chat_answer(handler, answer)
    with serving(post) as url:
        yield url, state

make_pdf = text_pdf  # (path, a text a page)

def evidence(eid, task, region):
    return Evidence(id=eid, content='sha256:' + 'a' * 64 + '.pdf', entity='e', attribute='a', value='1', kind='text',
                    quote='q', confidence=1, locator=PdfLocator(page=1, bbox=(0, 0, 1, 1), region=region, task=task))


class ReadOnly(unittest.TestCase):
    def test_a_reader_neither_writes_nor_waits_on_a_writer(self):
        import sqlite3
        from semantic_pdf_diff.store import Store, StoreError
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / 'store'
            with self.assertRaises(StoreError):
                Store.open(folder)
            self.assertFalse(folder.exists())  # nothing created
            with Store(folder):  # the writer holds its lock...
                with Store.open(folder) as reader:  # ...and a reader opens anyway
                    self.assertEqual(reader.files(), [])
                    with self.assertRaises(sqlite3.OperationalError):
                        reader.set_reconcile(not reader.reconciles())

class ReadingsInStore(unittest.TestCase):
    def test_the_store_reads_merged_readings_and_forgets_situating_when_that_changes(self):
        from semantic_pdf_diff.schema import Claim, claim_id
        content = 'sha256:' + 'a' * 64 + '.pdf'
        def sighting(entity, task):
            claim = Claim(entity=entity, attribute='material', value='2x4 cedar', kind='diagram', quote='2x4 CEDAR',
                          confidence=.9)
            return Evidence(**claim.model_dump(), id=claim_id(content, claim), content=content,
                            locator=PdfLocator(page=1, bbox=(0, 0, 300, 300), region='tile', task=task))
        with tempfile.TemporaryDirectory() as d, Store(Path(d) / 'store') as store:
            store.db.execute("INSERT INTO content (id, size) VALUES (?, 1)", (content,))
            for task, entity in (('tile:p1:0', 'handrails'), ('tile:p1:1', 'Handrail')):
                store.record_task({'content': content, 'page': 1, 'task': task, 'status': 'complete', 'claims': 1},
                                  [sighting(entity, task)])
            self.assertEqual(len(store.evidence(content)), 2)
            store.record_situation(content, [], [], [], [])
            self.assertTrue(store.set_reconcile(True))  # the situation linked the unmerged claims: forgotten
            self.assertIsNone(store.situation(content))
            self.assertEqual(len(store.evidence(content)), 1)
            self.assertEqual(len(store.evidence(content, reconcile=False)), 2)
            self.assertEqual(store.set_reconcile(True), {})  # unchanged: nothing cleared

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
        bind(store, extraction_interpreter(Settings()))
        store.db.execute("INSERT INTO content (id, size) VALUES (?, 1)", ('sha256:' + 'a' * 64 + '.pdf',))
        for task, region in [('text:0.0', 'text'), ('tile:0', 'tile'), ('overview', 'overview')]:
            store.record_task({'content': 'sha256:' + 'a' * 64 + '.pdf', 'task': task, 'status': 'complete'},
                              [evidence(f'ev-{region}', task, region)])
        return store

    def count(self, store, table):
        return store.db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]

    def test_same_interpreter_binds_quietly(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            self.assertEqual(bind(store, extraction_interpreter(Settings())), {})

    def test_a_lever_built_off_since_binds_quietly(self):
        # a store made before a lever existed: the lever, off, asks what the store's run asked
        import json
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            before = store.interpreter('extract')
            before['settings'].pop('column_conditions')
            before['settings']['levers'].remove('column_conditions')
            store.save_interpreter('extract', before)
            self.assertEqual(bind(store, extraction_interpreter(Settings())), {})
            self.assertEqual(store.interpreter('extract'), json.loads(json.dumps(
                extraction_interpreter(Settings()).model_dump())))  # rebound, as it is now
            store.save_interpreter('extract', before)
            with self.assertRaises(InterpreterMismatch) as caught:  # on, it asks something new
                bind(store, extraction_interpreter(Settings(column_conditions=True)))
            self.assertIn('settings.column_conditions', caught.exception.differences)
            self.assertIn('settings.levers', caught.exception.differences)

    def test_a_post_processing_lever_built_on_since_rebinds_by_itself(self):
        # a store made before sheet_records existed, the lever now on: it only post-processes answers
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            before = store.interpreter('extract')
            before['settings'].pop('sheet_records')
            before['settings']['levers'].remove('sheet_records')
            store.save_interpreter('extract', before)
            cleared = bind(store, extraction_interpreter(Settings(sheet_records=True)))
            self.assertTrue(cleared.get('automatic'))
            self.assertEqual(bind(store, extraction_interpreter(Settings(sheet_records=True))), {})
            for lever in ('column_conditions', 'sheet_records'):  # and with another lever built, off, since
                before['settings'].pop(lever, None)
                if lever in before['settings']['levers']:
                    before['settings']['levers'].remove(lever)
            store.save_interpreter('extract', before)
            self.assertTrue(bind(store, extraction_interpreter(Settings(sheet_records=True))).get('automatic'))

    def test_changed_interpreter_is_rejected_with_explanation(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            with self.assertRaises(InterpreterMismatch) as caught:
                bind(store, extraction_interpreter(Settings(tile_points=500)))
            self.assertIn('settings.tile_points', caught.exception.differences)
            self.assertIn('--reset', str(caught.exception))
            self.assertEqual(self.count(store, 'evidence'), 3)

    def test_dry_run_changes_nothing(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            preview = bind(store, extraction_interpreter(Settings(tile_points=500)), reset=True, dry_run=True)
            self.assertEqual((preview['tasks'], preview['evidence']), (2, 2))
            self.assertEqual(self.count(store, 'evidence'), 3)
            with self.assertRaises(InterpreterMismatch):
                bind(store, extraction_interpreter(Settings(tile_points=500)))

    def test_reset_is_selective(self):
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            bind(store, extraction_interpreter(Settings(tile_points=500)), reset=True)
            regions = {r for (r,) in store.db.execute('SELECT region FROM evidence')}
            self.assertEqual(regions, {'text'})
            self.assertEqual(bind(store, extraction_interpreter(Settings(tile_points=500))), {})
            bind(store, extraction_interpreter(Settings(tile_points=500, model='other-model')), reset=True)
            self.assertEqual(self.count(store, 'evidence'), 0)

    def test_saved_comparisons_outlive_a_free_rebind_not_a_reset(self):
        # code review 2026-10-08, C24: a rebind nobody was asked about deleted them silently
        with tempfile.TemporaryDirectory() as d, self.seeded(d) as store:
            store.save_comparison('2026-10-08T00:00:00', {'note': 'kept'})
            cleared = bind(store, extraction_interpreter(Settings(quote_match='exact')))  # post-processing only
            self.assertTrue(cleared.get('automatic'))
            self.assertNotIn('comparisons', cleared)
            self.assertEqual(self.count(store, 'comparison'), 1)
            cleared = bind(store, extraction_interpreter(Settings(quote_match='exact', tile_points=500)), reset=True)
            self.assertEqual((cleared['comparisons'], self.count(store, 'comparison')), (1, 0))

def cached_client(settings, store, folder):
    """A client caching in an answers cache in the folder (the user's, in a run: pipeline.answers_cache)."""
    return Client(settings, store, cache=fixtures.open(Path(folder) / 'answers.sqlite', 'record'))

class ContentAddressedCache(unittest.TestCase):
    def test_answers_are_found_by_what_reached_the_model(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, Store(Path(d) / 's') as store:
            client = cached_client(Settings(base_url=url, retries=0), store, d)
            self.addCleanup(client.close)
            key = ('extract', 'text', 'sha256:x.pdf', 'text:0', 'input-hash', None)
            client.ask('first prompt', Extraction, key=key)
            client.ask('first prompt', Extraction, key=key)
            self.assertEqual((state['requests'], client.cache_hits), (1, 1))
            # The recipe is a label: the same query built another way is the same query...
            client.ask('first prompt', Extraction, key=key[:3] + ('text:9',) + key[4:])
            self.assertEqual(state['requests'], 1)
            # ...and a changed query is asked, whatever recipe it comes with (no stale answer for it).
            client.ask('edited prompt', Extraction, key=key)
            self.assertEqual(state['requests'], 2)
            other = cached_client(Settings(base_url=url, retries=0, model='other-model'), store, d)  # another model
            self.addCleanup(other.close)
            other.ask('first prompt', Extraction, key=key)  # asked
            self.assertEqual(state['requests'], 3)
            # What each query was, and how it was built, is logged for diagnostics.
            logged = store.queries(content='sha256:x.pdf', task='text:0')
            self.assertEqual({q['prompt'] for q in logged}, {'first prompt', 'edited prompt'})

    def test_a_reset_keeps_cached_answers(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, Store(Path(d) / 's') as store:
            bind(store, extraction_interpreter(Settings()))
            client = cached_client(Settings(base_url=url, retries=0), store, d)
            self.addCleanup(client.close)
            key = ('extract', 'tile', 'sha256:x.pdf', 'tile:p1:0', 'input-hash', None)
            client.ask('a tile', Extraction, key=key)
            bind(store, extraction_interpreter(Settings(tile_points=500)), reset=True)
            client.ask('a tile', Extraction, key=key)
            self.assertEqual(state['requests'], 1)  # unchanged queries aren't paid for again

class TheUsersCache(unittest.TestCase):
    """One answers cache per user, shared by every store (docs/plans/configuration-in-the-store-2026-10-20.md,
    milestone 3; the owner, 2026-10-08: "The per-user default is tempting. Let's go with that instead.")."""
    def test_one_cache_answers_every_store(self):
        from semantic_pdf_diff.pipeline import RunOptions, make_client
        from stubs import per_user_cache
        key = ('extract', 'text', 'sha256:x.pdf', 'text:0', 'input-hash', None)
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, \
                patch.dict(os.environ, {'PDF_DIFF_CACHE': str(Path(d) / 'cache')}), \
                patch('semantic_pdf_diff.pipeline.answers_cache', per_user_cache):
            for name in ('first', 'second'):
                with Store(Path(d) / name) as store:
                    client = make_client(RunOptions(), Settings(base_url=url, retries=0), store)
                    try:
                        client.ask('a prompt', Extraction, key=key)
                    finally:
                        client.close()
            self.assertEqual((state['requests'], client.cache_hits), (1, 1))
            cache = Path(d) / 'cache' / 'answers.sqlite'
            # as sensitive as a store: its answers quote the documents
            self.assertEqual((stat.S_IMODE(os.stat(cache.parent).st_mode), stat.S_IMODE(os.stat(cache).st_mode)),
                             (0o700, 0o600))
            self.assertFalse((Path(d) / 'second' / 'answers.sqlite').exists())

    def test_a_stores_own_cached_answers_move_into_the_cache(self):
        import hashlib
        key = ('extract', 'text', 'sha256:x.pdf', 'text:0', 'input-hash', None)
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, Store(Path(d) / 's') as store:
            settings = Settings(base_url=url, retries=0)
            query = Client(settings, None).prepare('a prompt', Extraction, key=key).query
            old = hashlib.sha256((settings.model + '\x00' + query).encode()).hexdigest()  # a store's key, once
            with store.db:
                store.db.execute("INSERT INTO response_cache VALUES (?, 'extract', 'text', ?, ?, 'sha256:x.pdf')",
                                 (old, query, json.dumps({**EMPTY, 'issues': ['kept']})))
            client = cached_client(settings, store, d)
            self.assertEqual(client.ask('a prompt', Extraction, key=key).issues, ['kept'])
            client.close()
            self.assertEqual((state['requests'], client.cache_hits, store.cached(old)), (0, 1, None))
            again = cached_client(settings, store, d)  # from the cache now
            self.assertEqual(again.ask('a prompt', Extraction, key=key).issues, ['kept'])
            again.close()
            self.assertEqual(state['requests'], 0)

class TaskIdentity(unittest.TestCase):
    def test_pages_never_share_tasks_or_cache_entries(self):
        """Same-sized pages have identical tile rectangles; the page must separate them."""
        from semantic_pdf_diff.jobs import extract_pdf
        from semantic_pdf_diff.provenance import content_id
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, Store(Path(d) / 's') as store:
            path = make_pdf(Path(d) / 'two.pdf', ['Pump rated power 10 kW', 'Fan motor 3 kW'])
            cid = content_id(path.read_bytes(), path.name)
            from semantic_pdf_diff.schema import Source
            store.save_source(Source(name='two', roots=[str(path)]))
            store.rescan('two')
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
            code = cli.main(['compare', str(a), str(b), '--store', str(out), '--base-url', url, '--no-vision', *extra])
        return code, err.getvalue()

    def findings(self, out):
        report = json.loads((out / 'report.json').read_text())
        return sorted((f['a'], f['b'], f['relation']) for f in report['findings'])

    def interrupted_then_resumed(self, root, a, b, url, concurrency):
        config = root / f'concurrency-{concurrency}.json'
        config.write_text(json.dumps({'concurrency': concurrency}))
        original = Client.send
        def interrupting(client, *args, **kw):
            if client.calls >= 2:
                raise KeyboardInterrupt
            return original(client, *args, **kw)
        out = root / f'resumed-{concurrency}'
        with patch.object(Client, 'send', interrupting), self.assertRaises(KeyboardInterrupt):
            self.run_cli(a, b, out, url, '--config', str(config))
        self.run_cli(a, b, out, url, '--config', str(config))
        return self.findings(out)

    def test_interrupted_run_resumes_without_repeating_calls(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'baseline', url)
            baseline_requests, baseline = state['requests'], self.findings(root / 'baseline')
            state['requests'] = 0
            # Sequentially, nothing answered before the interruption is asked again.
            self.assertEqual(self.interrupted_then_resumed(root, a, b, url, 1), baseline)
            self.assertEqual(state['requests'], baseline_requests)
            # Concurrently, requests answered but not yet saved when interrupted may be
            # asked again (at most one per worker); the result is the same.
            state['requests'] = 0
            self.assertEqual(self.interrupted_then_resumed(root, a, b, url, 4), baseline)
            self.assertLessEqual(state['requests'], baseline_requests + 4)

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

    def test_a_changed_reader_reads_its_content_again_replaying_unchanged_queries(self):
        from unittest import mock
        from semantic_pdf_diff import jobs
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'out', url)
            first, findings = state['requests'], self.findings(root / 'out')
            with mock.patch.dict(jobs.READERS, {'.pdf': 'pdf/999'}):  # a reader changed since
                code, log = self.run_cli(a, b, root / 'out', url)
            self.assertNotIn('Loaded from store', log)          # read again,
            self.assertEqual(state['requests'], first)          # its unchanged queries answered from cache
            self.assertEqual(self.findings(root / 'out'), findings)
            with Store(root / 'out') as store:
                self.assertTrue(store.is_extracted(content_id(a.read_bytes(), a.name), 'pdf/999'))
            code, log = self.run_cli(a, b, root / 'out', url)  # the old version, a downgrade: read again too
            self.assertNotIn('Loaded from store', log)

    def test_failed_tasks_are_retried_on_the_next_run(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            code, _ = self.run_cli(a, b, root / 'out', url, '--max-calls', '1')
            self.assertEqual(code, 2)
            statuses = {r['status'] for r in json.loads((root / 'out/evidence.json').read_text())['coverage']}
            self.assertIn('not_reached', statuses)  # cut off by the call limit, not failed
            self.assertNotIn('failed', statuses)
            paused = json.loads((root / 'out/report.json').read_text())['paused']
            self.assertEqual(paused, 'call limit reached (1 requests)')  # what it cut followed the answers' order
            with Store(root / 'out') as store:
                self.assertFalse(store.is_extracted(content_id(a.read_bytes(), a.name), "pdf/1"))
            code, _ = self.run_cli(a, b, root / 'out', url)
            report = json.loads((root / 'out/report.json').read_text())
            self.assertFalse(any(r['status'] == 'failed' for r in report['coverage']))
            self.assertEqual(report['paused'], '')  # resumed: nothing cut

    def test_changed_settings_need_reset(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'out', url)
            code, log = self.run_cli(a, b, root / 'out', url, '--model', 'another-model')
            self.assertEqual(code, 1)
            self.assertIn('--reset', log)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                cli.main(['compare', str(a), str(b), '--store', str(root / 'out'), '--model', 'another-model',
                          '--reset', '--dry-run'])
            self.assertGreater(json.loads(out.getvalue())['would_clear']['extract']['evidence'], 0)
            code, _ = self.run_cli(a, b, root / 'out', url, '--model', 'another-model', '--reset')
            self.assertEqual(code, 2)  # --no-vision is deliberately incomplete

    def test_a_refusal_says_what_differs_what_going_ahead_clears_and_asks(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'out', url)
            config = root / 'more-claims.json'
            config.write_text(json.dumps({'claims_per_request': 25}))
            code, log = self.run_cli(a, b, root / 'out', url, '--config', str(config))
            self.assertEqual(code, 1)
            self.assertIn("claims_per_request: 20 -> 25 (shapes what's asked)", log)
            self.assertIn('Going ahead clears what they affect', log)
            self.assertRegex(log, r'at most [\d,]+ would be asked again \(about [\d,]+ tokens')
            self.assertIn('rerun with --reset', log)

    def test_a_post_processing_change_is_applied_without_asking_and_costs_nothing(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d); a, b = self.pdfs(root)
            self.run_cli(a, b, root / 'out', url)
            first = state['requests']
            config = root / 'exact-quotes.json'
            config.write_text(json.dumps({'quote_match': 'exact'}))
            code, log = self.run_cli(a, b, root / 'out', url, '--config', str(config))
            self.assertNotEqual(code, 1)  # not refused
            self.assertIn('only post-process answers (quote_match', log)
            self.assertEqual(state['requests'], first)  # recomputed from cached answers

if __name__ == '__main__':
    unittest.main()

class ResumedRuns(unittest.TestCase):
    """A run stopped by the call limit, then resumed, leaves the store as one uninterrupted run would: no task
    rows from the stopped run's refinements (code review 2026-10-01, item 5)."""
    def test_a_resumed_run_keeps_only_its_own_tasks(self):
        import contextlib, io, json, tempfile
        from pathlib import Path
        from semantic_pdf_diff import cli
        from semantic_pdf_diff.store import Store
        from test_concurrency import jittery_model
        from test_settings import document
        with tempfile.TemporaryDirectory() as d, jittery_model() as (url, _):
            root = Path(d)
            a, b = document(root / 'a.pdf', 10, True), document(root / 'b.pdf', 12, True)
            run = lambda limit: cli.main(['compare', str(a), str(b), '--store', str(root / 'out'), '--base-url', url,
                                          '--no-situate'] + (['--config', str(limit)] if limit else []))
            limit = root / 'limit.json'
            limit.write_text(json.dumps({'max_calls': 12}))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                run(limit)  # stopped part way: tasks not reached
                run(None)   # resumed
            report = json.loads((root / 'out' / 'report.json').read_text())
            with Store(root / 'out') as store:
                stored = {(r['content'], r['task']) for c in {r['content'] for r in report['coverage']}
                          for r in store.coverage(c)}
        ran = {(r['content'], r['task']) for r in report['coverage']}
        self.assertFalse([r for r in report['coverage'] if r['status'] == 'not_reached'])
        self.assertEqual(stored, ran)

class SharedAnswers(unittest.TestCase):
    def test_collecting_content_keeps_an_answer_another_content_asked_for(self):
        """A query two contents ask (the same page in two files) is cached under whichever asked first; collecting
        that content dropped the answer the other still uses (the determinism review, D12)."""
        with tempfile.TemporaryDirectory() as d, Store(Path(d) / 'store') as store:
            kept, gone = 'sha256:' + 'a' * 64 + '.pdf', 'sha256:' + 'b' * 64 + '.pdf'
            with store.db:
                store.db.execute("INSERT INTO source VALUES ('s', '{}', NULL, '{}')")
                for content in (kept, gone):
                    store.db.execute("INSERT INTO content VALUES (?, 1, 0)", (content,))
                store.db.execute("INSERT INTO file VALUES ('s', 'a.pdf', ?, 1, '', '', '', '{}')", (kept,))
            for content in (kept, gone):
                store.note_query('q-shared', ('extract', 'text', content, 'text:p1:0'), 'prompt', [])
            store.note_query('q-own', ('extract', 'text', gone, 'text:p2:0'), 'prompt', [])
            with store.db:  # a store's own cache, from before the user's (2026-10-20)
                store.db.execute("INSERT INTO response_cache VALUES ('k-shared', 'extract', 'text', 'q-shared', '{}', "
                                 "?)", (gone,))  # the gone content asked first
                store.db.execute("INSERT INTO response_cache VALUES ('k-own', 'extract', 'text', 'q-own', '{}', ?)",
                                 (gone,))
            self.assertEqual(store.gc()['cached_responses'], 1)
            self.assertIsNotNone(store.cached('k-shared'))
            self.assertIsNone(store.cached('k-own'))

class OneTaskTwice(unittest.TestCase):
    def test_a_claim_one_task_gives_twice_is_kept_once_fresh_and_from_the_store(self):
        """The store kept the last copy and a fresh run both, so the claim's sightings, representative and
        confidence differed between a run and one read back (the determinism review, D13)."""
        from semantic_pdf_diff.tasks import TaskCore
        content = 'sha256:' + 'a' * 64 + '.pdf'
        at = PdfLocator(page=1, bbox=(0, 0, 10, 10), region='table', task='table:p1:0:0')
        first, second = (Evidence(id='ev-1', content=content, entity='pump', attribute='flow', value='5', unit='L/s',
                                  kind='table', quote=q, confidence=c, locator=at)
                         for q, c in (('5', .9), ('5 L/s', .6)))
        core = TaskCore.__new__(TaskCore)
        core.coverage, core.evidence = [], [first, second]
        fresh, _ = core.result(lambda r: r)
        with tempfile.TemporaryDirectory() as d, Store(Path(d) / 'store') as store:
            with store.db:
                store.db.execute("INSERT INTO content VALUES (?, 1, 0)", (content,))
            row = {'content': content, 'task': 'table:p1:0:0', 'page': 1, 'status': 'complete', 'issues': []}
            store.record_task(row, [first, second])
            loaded = store.evidence(content, reconcile=False)
        self.assertEqual([e.model_dump() for e in loaded], [e.model_dump() for e in fresh])
        self.assertEqual((len(fresh), fresh[0].quote, fresh[0].confidence, len(fresh[0].occurrences)),
                         (1, '5', .9, 1))

class Orders(unittest.TestCase):
    def test_coverage_comes_back_by_page_and_task_not_as_written(self):
        """Rows were read back in the order tasks finished, which a live run and its replay don't share; the lab's
        units followed it (the determinism review, D2)."""
        content = 'sha256:' + 'a' * 64 + '.pdf'
        rows = [{'content': content, 'task': t, 'page': p, 'status': 'complete', 'issues': []}
                for t, p in (('tile:p2:0', 2), ('text:p1:0', 1), ('overview:p1', 1), ('table:p1:0:0', 1))]
        found = []
        for order in (rows, rows[::-1]):
            with tempfile.TemporaryDirectory() as d, Store(Path(d) / 'store') as store:
                with store.db:
                    store.db.execute("INSERT INTO content VALUES (?, 1, 0)", (content,))
                for row in order:
                    store.record_task(row, [])
                found.append([r['task'] for r in store.coverage(content)])
        self.assertEqual(found, [['overview:p1', 'table:p1:0:0', 'text:p1:0', 'tile:p2:0']] * 2)
