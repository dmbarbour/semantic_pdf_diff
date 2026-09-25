"""Replay recorded model answers on the sample slices: the real pipeline, offline, per responder.

Needs the fetched samples cut into slices (scripts/fetch_samples.py, scripts/make_slices.py)
and the same PyMuPDF version the fixture was recorded with; otherwise it skips. Answers
differ between responders, so outcomes are checked for shape, not exact content.
"""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
import pymupdf
from semantic_pdf_diff import cli, fixtures

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / 'tests/fixtures/replay-slices.zip'
SLICES = ROOT / 'samples/slices'
MANIFEST = json.loads((ROOT / 'scripts/slices.json').read_text())
RUNS = {'turbines': ('nrel-5mw-p25-36', 'iea-15mw-p20-31'), 'drawings': ('dc-cd-p39-42', 'calg-cd-p39-42'),
        'rules': ('rules-2013-p35-38', 'rules-2013-p35-38')}
UNREACHABLE = 'http://127.0.0.1:9/v1'

def unavailable():
    if not FIXTURE.exists():
        return f'no fixture at {FIXTURE}'
    missing = [s['name'] for s in MANIFEST['slices'] if not (SLICES / f"{s['name']}.pdf").exists()]
    if missing:
        return f'slices missing ({", ".join(missing)}); run scripts/make_slices.py'
    return None

@unittest.skipIf(unavailable(), unavailable())
class ReplaySlices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        with fixtures.Fixture(fixtures.unpack(FIXTURE, cls.dir.name)) as f:
            cls.summary = f.summary()
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
        config.write_text(json.dumps({'claims_per_request': 20, 'output_tokens': 4000, 'context_tokens': 262144,
                                      'image_tokens': 300}))
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
                    if run != 'rules':
                        self.assertTrue(report['findings'])
                    else:
                        self.assertEqual(report['findings'], [])  # identical content is shared, not compared

if __name__ == '__main__':
    unittest.main()
