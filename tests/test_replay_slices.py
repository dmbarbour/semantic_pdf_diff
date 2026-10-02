"""Replay recorded model answers on the sample slices: the real pipeline, offline, per responder.

Needs the fetched samples cut into slices (scripts/fetch_samples.py, scripts/make_slices.py)
and the same PyMuPDF version the fixture was recorded with; otherwise it skips. Answers
differ between responders, so outcomes are checked for shape, not exact content.
"""
import stubs  # noqa: F401 (a clean environment)
from stubs import slow
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff import cli, fixtures

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/fixtures/replay-slices.zip'
SLICES = ROOT / 'samples/slices'
MANIFEST = json.loads((ROOT / 'scripts/slices.json').read_text())
sys.path.insert(0, str(ROOT / 'scripts'))
import record_runs  # noqa: E402  (the settings every recording shares)
# The runs recorded in the fixture; by default only the first few development runs replay (REPLAY_ALL=1 for all).
RUNS = {r['name']: tuple(r['slices']) for r in MANIFEST.get('runs', [])
        if r['set'] == 'dev' or os.environ.get('REPLAY_ALL')}
if not os.environ.get('REPLAY_ALL'):
    RUNS = dict(list(RUNS.items())[:3])
UNREACHABLE = 'http://127.0.0.1:9/v1'

def unavailable():
    if not FIXTURE.exists():
        return f'no fixture at {FIXTURE}'
    missing = [s['name'] for s in MANIFEST['slices'] if not (SLICES / f"{s['name']}.pdf").exists()]
    if missing:
        return f'slices missing ({", ".join(missing)}); run scripts/make_slices.py'
    return None

@unittest.skipIf(unavailable(), unavailable())
@slow
class ReplaySlices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        with fixtures.open(FIXTURE, "read") as f:
            cls.summary = f.summary()
        from semantic_pdf_diff.provenance import content_id
        wanted = {content_id((SLICES / f'{n}.pdf').read_bytes(), f'{n}.pdf') for slices in RUNS.values() for n in slices}
        if not wanted <= set(cls.summary['contents']):
            raise unittest.SkipTest('the fixture was recorded from other slices; re-record (scripts/record_runs.py)')
        if cls.summary['meta'].get('pymupdf') != pymupdf.VersionBind:
            raise unittest.SkipTest(f"fixture recorded with PyMuPDF {cls.summary['meta'].get('pymupdf')}, "
                                    f"not {pymupdf.VersionBind}: text and renderings may differ")

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def replay(self, run, responder):
        a, b = (SLICES / f'{name}.pdf' for name in RUNS[run])
        out = Path(self.dir.name) / f'{run}-{responder.replace("/", "_")}'
        config = Path(self.dir.name) / 'settings.json'
        # The settings the fixture was recorded with (they're part of each request's fingerprint).
        config.write_text(json.dumps(record_runs.BASE_SETTINGS))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = cli.main([str(a), str(b), '--out', str(out), '--base-url', UNREACHABLE, '--config', str(config),
                             '--fixture', str(FIXTURE), '--responder', responder])
        return code, json.loads((out / 'report.json').read_text())

    def test_every_responder_replays_every_run(self):
        responders = sorted({a['responder'] for a in self.summary['answers']})
        self.assertTrue(responders)
        for responder in responders:
            for run in RUNS:
                with self.subTest(responder=responder, run=run):
                    code, report = self.replay(run, responder)
                    self.assertIn(code, (0, 2))  # 2: some task partial or failed, as recorded
                    self.assertEqual(report['usage']['api_calls'], 0)
                    self.assertEqual(report['usage']['fixture']['missing'], 0)
                    self.assertTrue(report['evidence'])
                    pages = {e['content']: e['locator']['page'] for e in report['evidence']}
                    self.assertTrue(all(1 <= p <= 12 for p in pages.values()))
                    self.assertEqual(len(report['situation']), len({f['content'] for f in report['files']}))
                    if RUNS[run][0] != RUNS[run][1]:
                        self.assertTrue(report['findings'])
                    else:
                        self.assertEqual(report['findings'], [])  # identical content is shared, not compared

if __name__ == '__main__':
    unittest.main()
