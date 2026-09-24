import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
import pymupdf
from semantic_pdf_diff import cli
from semantic_pdf_diff.models import Source
from semantic_pdf_diff.report import write_report
from semantic_pdf_diff.store import Store, StoreError

sys.path.insert(0, str(Path(__file__).parent))
from test_store import model_server  # noqa: E402

def pdf_bytes(text):
    doc = pymupdf.open(); page = doc.new_page(width=300, height=300); page.insert_text((40, 40), text)
    data = doc.tobytes(); doc.close()
    return data

def touch_later(path):
    """Make sure a rewritten file's modification time differs from the scan's."""
    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))

class Registry(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.team = self.root / 'team-a'
        self.team.mkdir()
        (self.team / 'one.pdf').write_bytes(pdf_bytes('Pump 10 kW'))
        (self.team / 'two.pdf').write_bytes(pdf_bytes('Fan 3 kW'))
        (self.team / 'notes.md').write_text('# notes')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as z:
            z.writestr('inner.pdf', pdf_bytes('Chiller 350 kW'))
            z.writestr('__MACOSX/._inner.pdf', b'x')
        (self.team / 'bundle.zip').write_bytes(buffer.getvalue())
        self.store = Store(self.root / 'store')
        self.addCleanup(self.store.close)

    def test_declare_once_then_update(self):
        self.store.save_source(Source(name='team-a', roots=[str(self.team)]))
        with self.assertRaises(StoreError):
            self.store.save_source(Source(name='team-a', roots=[]))
        self.store.save_source(Source(name='team-a', metadata={'revision': 'C'}, roots=[str(self.team)]), replace=True)
        self.assertEqual(self.store.source('team-a').metadata, {'revision': 'C'})
        with self.assertRaises(ValueError):
            Source(name='bad@name')

    def test_rescan_fast_path_and_changes(self):
        described = []
        describe = lambda name, data: described.append(name) or {}
        self.store.save_source(Source(name='team-a', roots=[str(self.team)]))
        first = self.store.rescan('team-a', describe=describe)
        self.assertEqual(first['files'], 5)  # one, two, notes, bundle.zip and its member
        self.assertEqual(self.store.issues('team-a'), [('team-a/bundle.zip!/__MACOSX/._inner.pdf', 'hidden')])
        described.clear()
        again = self.store.rescan('team-a', describe=describe)
        self.assertEqual((again['reused_disk_files'], described), (4, []))
        self.assertEqual(self.store.issues('team-a'), [('team-a/bundle.zip!/__MACOSX/._inner.pdf', 'hidden')])
        old = {f.path: f.content for f in self.store.files('team-a')}
        (self.team / 'one.pdf').write_bytes(pdf_bytes('Pump 12 kW')); touch_later(self.team / 'one.pdf')
        (self.team / 'two.pdf').unlink()
        (self.team / 'three.pdf').write_bytes(pdf_bytes('Valve DN100'))
        changed = self.store.rescan('team-a', describe=describe)
        self.assertEqual((changed['added'], changed['removed'], changed['changed']),
                         (['team-a/three.pdf'], ['team-a/two.pdf'], ['team-a/one.pdf']))
        self.assertEqual(sorted(described), ['team-a/one.pdf', 'team-a/three.pdf'])
        self.assertEqual(set(self.store.orphaned_content()), {old['team-a/one.pdf'], old['team-a/two.pdf']})

    def test_remove_orphans_content(self):
        self.store.save_source(Source(name='team-a', roots=[str(self.team)]))
        self.store.rescan('team-a')
        self.store.remove_source('team-a')
        self.assertEqual(self.store.files('team-a'), [])
        self.assertEqual(len(self.store.orphaned_content()), 5)
        with self.assertRaises(StoreError):
            self.store.remove_source('team-a')

class CommandLine(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.store = self.root / 'store'
        rules = pdf_bytes('Rule 4: fan limit 3 kW')  # generated once: PyMuPDF gives each new PDF a unique ID
        for team, power in (('team-a', '10'), ('team-b', '12')):
            folder = self.root / team
            folder.mkdir()
            (folder / 'pump.pdf').write_bytes(pdf_bytes(f'Pump rated power {power} kW'))
            (folder / 'shared-rules.pdf').write_bytes(rules)
            (folder / 'readme.md').write_text('# not yet supported')

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main([str(a) for a in argv])
        return code, out.getvalue(), err.getvalue()

    def source(self, *argv):
        return self.cli('source', argv[0], '--store', self.store, *argv[1:])

    def test_manage_sources(self):
        self.assertEqual(self.source('add', 'team-a', '--path', self.root / 'team-a', '--meta', 'organization=Team A')[0], 0)
        code, out, _ = self.source('list')
        self.assertIn('team-a\tdeclared\t3 files\t{"organization": "Team A"}', out)
        self.source('update', 'team-a', '--meta', 'revision=C', '--meta', 'organization=')
        shown = json.loads(self.source('show', 'team-a')[1])
        self.assertEqual(shown['source']['metadata'], {'revision': 'C'})
        self.assertEqual(len(shown['files']), 3)
        self.assertEqual(self.source('add', 'team-a', '--path', self.root / 'team-a')[0], 1)
        self.assertEqual(self.source('remove', 'team-a')[0], 0)
        self.assertEqual(self.source('list')[1], '')

    def test_compare_declared_sources(self):
        with model_server() as (url, state):
            self.source('add', 'team-a', '--path', self.root / 'team-a')
            self.source('add', 'team-b', '--path', self.root / 'team-b')
            code, _, err = self.cli('compare', '--store', self.store, 'team-a', 'team-b', '--base-url', url, '--no-vision')
            report = json.loads((self.store / 'report.json').read_text())
            self.assertEqual(code, 2)  # --no-vision and the unsupported .md are incomplete
            self.assertEqual(len(report['shared']), 1)  # the identical rules PDF
            # The stub calls 10 kW and 12 kW equivalent; the numeric check vetoes that to uncertain.
            self.assertEqual([f['relation'] for f in report['findings']], ['uncertain'])
            self.assertIn('Numeric conversion disagrees', report['findings'][0]['rationale'])
            unsupported = [r for r in report['coverage'] if r['task'] == 'unsupported']
            self.assertEqual(len(unsupported), 1)  # both readme.md files are the same content
            self.assertEqual(unsupported[0]['issues'], ['No adapter for .md files yet'])

    def test_rescan_is_automatic_unless_configured(self):
        with model_server() as (url, state):
            self.source('add', 'team-a', '--path', self.root / 'team-a')
            self.source('add', 'team-b', '--path', self.root / 'team-b')
            run = lambda *extra: self.cli('compare', '--store', self.store, 'team-a', 'team-b', '--base-url', url,
                                          '--no-vision', *extra)
            run()
            pump = self.root / 'team-a' / 'pump.pdf'
            pump.write_bytes(pdf_bytes('Pump rated power 11 kW')); touch_later(pump)
            manual = self.root / 'manual.json'; manual.write_text('{"rescan": "manual"}')
            run('--config', manual)
            values = lambda: {e['value'] for e in json.loads((self.store / 'report.json').read_text())['evidence']}
            self.assertIn('10', values())
            run()
            self.assertIn('11', values())
            self.assertNotIn('10', values())

    def test_export_and_import(self):
        self.source('add', 'team-a', '--path', self.root / 'team-a', '--meta', 'revision=C')
        elsewhere = self.root / 'manifests'; elsewhere.mkdir()
        target = elsewhere / 'team-a.source.json'
        self.source('export', 'team-a', '--output', target, '--with-hashes')
        exported = json.loads(target.read_text())
        self.assertEqual(exported['roots'], ['../team-a'])
        self.assertEqual(len(exported['files']), 3)
        self.assertEqual(self.source('import', target, '--name', 'team-a-copy')[0], 0)
        self.assertEqual({f['content'] for f in json.loads(self.source('show', 'team-a-copy')[1])['files']},
                         {f['content'] for f in exported['files']})
        (self.root / 'team-a' / 'readme.md').write_text('# changed')
        _, _, err = self.source('import', target, '--name', 'team-a-changed')
        self.assertIn("1 file(s) differ from the manifest's hashes", err)

    def test_manifest_links(self):
        with model_server() as (url, state):
            for team in ('team-a', 'team-b'):
                self.source('add', team, '--path', self.root / team)
                self.source('export', team, '--output', self.root / f'{team}.source.json')
                self.source('remove', team)
            run = lambda: self.cli('compare', '--store', self.store, '--manifest', self.root / 'team-a.source.json',
                                   '--manifest', self.root / 'team-b.source.json', '--base-url', url, '--no-vision')
            code, _, err = run()
            self.assertIn("Linked source 'team-a'", err)
            self.assertEqual({s['kind'] for s in json.loads((self.store / 'report.json').read_text())['sources']}, {'manifest'})
            _, _, err = run()
            self.assertNotIn('Linked', err)
            edited = json.loads((self.root / 'team-a.source.json').read_text())
            edited['metadata'] = {'revision': 'D'}
            (self.root / 'team-a.source.json').write_text(json.dumps(edited))
            _, _, err = run()
            self.assertIn("Updated source 'team-a'", err)
            (self.root / 'team-b.source.json').unlink()
            self.assertIn('manifest missing: orphaned', self.source('list')[1])

    def test_shortcut_takes_folders_and_guards_names(self):
        with model_server() as (url, state):
            code, _, _ = self.cli(self.root / 'team-a', self.root / 'team-b', '--out', self.store, '--base-url', url,
                                  '--no-vision')
            sources = json.loads((self.store / 'report.json').read_text())['sources']
            self.assertEqual([(s['name'], s['kind']) for s in sources], [('team-a', 'shortcut'), ('team-b', 'shortcut')])
            other = self.root / 'other'
            self.source('add', 'declared', '--path', self.root / 'team-a')
            (self.root / 'declared').mkdir()
            code, _, err = self.cli(self.root / 'declared', self.root / 'team-b', '--out', self.store, '--base-url', url)
            self.assertEqual(code, 1)
            self.assertIn("already has a declared source named 'declared'", err)

class ReportLinks(unittest.TestCase):
    def test_crops_link_relative_to_the_report_folder(self):
        from test_pipeline import ev
        a = ev(image='assets/abc-tile-p1-0.png'); b = ev('B-1')
        data = {'mode': 'proposals', 'findings': [], 'unmatched': [{'id': a.id, 'note': 'n'}], 'shared': [],
                'evidence': [a.model_dump(), b.model_dump()], 'coverage': [], 'retrieval': {},
                'sources': [Source(name='A').model_dump()], 'files': []}
        with tempfile.TemporaryDirectory() as d:
            write_report(data, Path(d) / 'reports' / 'r1', assets=Path(d) / 'store' / 'assets')
            html = (Path(d) / 'reports' / 'r1' / 'report.html').read_text()
            self.assertIn('src="../../store/assets/abc-tile-p1-0.png"', html)

if __name__ == '__main__':
    unittest.main()
