import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli
from semantic_pdf_diff.store import Store

sys.path.insert(0, str(Path(__file__).parent))
from test_sources import pdf_bytes, touch_later  # noqa: E402
from test_store import model_server  # noqa: E402

class Maintenance(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.store = self.root / 'store'
        for team, power in (('team-a', '10'), ('team-b', '12')):
            (self.root / team).mkdir()
            (self.root / team / 'pump.pdf').write_bytes(pdf_bytes(f'Pump rated power {power} kW'))
        server = model_server()
        self.url, self.state = server.__enter__()
        self.addCleanup(server.__exit__, None, None, None)
        self.cli('source', 'add', 'team-a', '--store', self.store, '--path', self.root / 'team-a', '--meta', 'revision=C')
        self.cli('source', 'add', 'team-b', '--store', self.store, '--path', self.root / 'team-b')
        self.compare()

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def compare(self):
        return self.cli('compare', '--store', self.store, 'team-a', 'team-b', '--base-url', self.url, '--no-vision')

    def show(self, view, style='jsonl'):
        code, out, _ = self.cli('show', view, '--store', self.store, '--format', style)
        self.assertEqual(code, 0)
        return [json.loads(line) for line in out.splitlines()] if style == 'jsonl' else out

    def test_views(self):
        self.assertIn('| name | kind | roots | manifest | files | meta.revision |', self.show('sources', 'md'))
        self.assertTrue(self.show('source_files', 'csv').startswith('source,path,content,size,extracted\n'))
        occurrences = self.show('evidence_occurrences')
        self.assertEqual({(r['source'], r['path'], r['page'], r['value']) for r in occurrences},
                         {('team-a', 'team-a/pump.pdf', 1, '10'), ('team-b', 'team-b/pump.pdf', 1, '12')})
        self.assertTrue(all(r['tasks'] >= 1 for r in self.show('coverage_by_source')))
        comparisons = self.show('comparisons')
        self.assertEqual([(c['first'], c['second'], c['findings']) for c in comparisons], [('team-a', 'team-b', 1)])
        self.assertEqual(self.show('orphaned_content'), [])

    def test_gc_collects_only_orphaned_content(self):
        with Store(self.store) as store:
            old = store.files('team-a')[0].content
        crop = self.store / 'assets' / (old.split(':', 1)[1][:12] + '-tile-p1-0.png')
        crop.write_bytes(b'png')
        pump = self.root / 'team-a' / 'pump.pdf'
        pump.write_bytes(pdf_bytes('Pump rated power 11 kW')); touch_later(pump)
        self.compare()
        self.assertEqual([r['content'] for r in self.show('orphaned_content')], [old])
        code, out, _ = self.cli('gc', '--store', self.store, '--dry-run')
        preview = json.loads(out)
        self.assertEqual((preview['content'], preview['crops'], preview['evidence']), (1, 1, 1))
        self.assertGreater(preview['cached_responses'], 0)
        self.assertTrue(crop.exists())
        json.loads(self.cli('gc', '--store', self.store)[1])
        self.assertFalse(crop.exists())
        self.assertEqual(self.show('orphaned_content'), [])
        with Store(self.store) as store:
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM evidence WHERE content=?', (old,)).fetchone()[0], 0)
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM response_cache WHERE content=?', (old,)).fetchone()[0], 0)
            self.assertGreater(store.db.execute('SELECT COUNT(*) FROM evidence').fetchone()[0], 0)
        before = self.state['requests']
        self.compare()  # nothing still referenced was collected, so nothing is re-extracted
        self.assertEqual(self.state['requests'], before)

    def test_gc_removes_sources_with_missing_manifests_only_when_asked(self):
        manifest = self.root / 'team-c.source.json'
        self.cli('source', 'export', 'team-a', '--store', self.store, '--output', manifest)
        edited = json.loads(manifest.read_text()); edited['name'] = 'team-c'
        manifest.write_text(json.dumps(edited))
        self.cli('compare', '--store', self.store, '--manifest', manifest, 'team-b', '--base-url', self.url, '--no-vision')
        manifest.unlink()
        self.assertEqual(json.loads(self.cli('gc', '--store', self.store)[1])['sources'], [])
        preview = json.loads(self.cli('gc', '--store', self.store, '--orphaned-sources', '--dry-run')[1])
        self.assertEqual(preview['sources'], ['team-c'])
        json.loads(self.cli('gc', '--store', self.store, '--orphaned-sources')[1])
        self.assertEqual(sorted(r['name'] for r in self.show('sources')), ['team-a', 'team-b'])

    def test_report_regenerates_without_model_calls(self):
        (self.store / 'report.html').unlink()
        before = self.state['requests']
        code, out, _ = self.cli('report', '--store', self.store)
        self.assertEqual((code, self.state['requests']), (0, before))
        self.assertIn('team-a ↔ team-b', (self.store / 'report.html').read_text())
        code, _, err = self.cli('report', '--store', self.store, '--comparison', 99)
        self.assertEqual(code, 1)
        self.assertIn('no comparison 99', err)
        self.assertEqual(self.cli('show', 'sources', '--store', self.root / 'nowhere')[0], 1)

if __name__ == '__main__':
    unittest.main()
