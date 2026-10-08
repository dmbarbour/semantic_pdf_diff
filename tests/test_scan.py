import stubs  # noqa: F401 (a clean environment)
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from semantic_pdf_diff.scan import Limits, read_origin, scan

def zip_bytes(members):
    """members: {name: bytes}."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    return buffer.getvalue()

def encrypted_zip():
    """A one-member zip whose headers claim encryption (zipfile won't write that flag itself)."""
    data = bytearray(zip_bytes({'locked.pdf': b'l'}))
    for signature, offset in ((b'PK\x03\x04', 6), (b'PK\x01\x02', 8)):
        at = data.find(signature)
        data[at + offset] |= 0x1
    return bytes(data)

class FolderScanning(unittest.TestCase):
    def test_a_broken_link_or_unreadable_file_is_an_issue_not_the_end(self):
        # code review 2026-10-08, C1: one of them aborted the whole scan
        import os
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'team-a'
            root.mkdir()
            (root / 'a.pdf').write_bytes(b'pdf a')
            (root / 'gone.pdf').symlink_to(root / 'nowhere.pdf')
            locked = root / 'locked.pdf'
            locked.write_bytes(b'pdf locked')
            locked.chmod(0)
            try:
                result = scan([root])
            finally:
                locked.chmod(0o600)
        self.assertEqual([f.path for f in result.files], ['team-a/a.pdf'] + (['team-a/locked.pdf'] if os.geteuid() == 0 else []))
        reasons = dict(result.issues)
        self.assertTrue(reasons['team-a/gone.pdf'].startswith('unreadable: FileNotFoundError'))
        if os.geteuid() != 0:  # root reads it anyway
            self.assertTrue(reasons['team-a/locked.pdf'].startswith('unreadable: PermissionError'))

    def test_a_file_gone_since_the_scan_is_a_failed_open_row(self):
        from semantic_pdf_diff.extract import Job, run_jobs
        rows = []
        job = Job('sha256:' + 'c' * 64 + '.pdf', lambda: Path('/nonexistent/x.pdf').read_bytes(),
                  on_task=lambda row, found: rows.append(row))
        with tempfile.TemporaryDirectory() as d:
            run_jobs([[job]], Path(d), object())
        self.assertEqual([(r['task'], r['status']) for r in rows], [('open', 'failed')])
        self.assertEqual(job.state['result'][1], rows)

    def test_folder_files_hidden_and_clutter(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'team-a'
            (root / 'design').mkdir(parents=True)
            (root / 'design' / 'summary.pdf').write_bytes(b'pdf one')
            (root / 'notes.md').write_bytes(b'# notes')
            (root / 'copy-of-summary.pdf').write_bytes(b'pdf one')
            (root / 'README').write_bytes(b'no extension')
            (root / '.hidden.pdf').write_bytes(b'x')
            (root / '.git' / 'objects').mkdir(parents=True)
            (root / '.git' / 'objects' / 'a.pdf').write_bytes(b'y')
            (root / '__MACOSX').mkdir()
            (root / '__MACOSX' / '._summary.pdf').write_bytes(b'z')
            (root / 'Thumbs.db').write_bytes(b't')
            result = scan([root])
            paths = {f.path: f for f in result.files}
            self.assertEqual(set(paths), {'team-a/design/summary.pdf', 'team-a/notes.md',
                                          'team-a/copy-of-summary.pdf', 'team-a/README'})
            self.assertEqual(paths['team-a/design/summary.pdf'].content, paths['team-a/copy-of-summary.pdf'].content)
            self.assertTrue(paths['team-a/design/summary.pdf'].content.endswith('.pdf'))
            self.assertRegex(paths['team-a/README'].content, r'^sha256:[0-9a-f]{64}$')
            self.assertEqual(sorted(p for p, reason in result.issues if reason == 'hidden'),
                             ['team-a/.git', 'team-a/.hidden.pdf', 'team-a/Thumbs.db', 'team-a/__MACOSX'])

    def test_file_roots_missing_roots_and_labels(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'x').mkdir(); (Path(d) / 'y').mkdir()
            a = Path(d) / 'x' / 'report.pdf'; a.write_bytes(b'a')
            b = Path(d) / 'y' / 'report.pdf'; b.write_bytes(b'b')
            result = scan([a, b, Path(d) / 'missing.pdf'])
            self.assertEqual([f.path for f in result.files], ['report.pdf', 'report.pdf[2]'])
            self.assertIn('not found', [reason for _, reason in result.issues])

class ArchiveScanning(unittest.TestCase):
    def scan_zip(self, members, limits=Limits(), name='bundle.zip'):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        path = Path(d.name) / name
        path.write_bytes(zip_bytes(members) if isinstance(members, dict) else members)
        return scan([path], limits)

    def test_members_are_files_and_clutter_is_hidden(self):
        result = self.scan_zip({'report.pdf': b'pdf', 'sub/data.csv': b'a,b', '__MACOSX/._report.pdf': b'x',
                                'sub/.DS_Store': b'y'})
        self.assertEqual(sorted(f.path for f in result.files),
                         ['bundle.zip', 'bundle.zip!/report.pdf', 'bundle.zip!/sub/data.csv'])
        self.assertEqual(sorted(reason for _, reason in result.issues), ['hidden', 'hidden'])

    def test_nested_archives_and_depth_limit(self):
        inner = zip_bytes({'deep.pdf': b'deep'})
        middle = zip_bytes({'inner.zip': inner, 'mid.pdf': b'mid'})
        outer = zip_bytes({'middle.zip': middle})
        result = self.scan_zip(outer)
        self.assertIn('bundle.zip!/middle.zip!/inner.zip!/deep.pdf', [f.path for f in result.files])
        limited = self.scan_zip(outer, Limits(max_depth=2))
        self.assertNotIn('bundle.zip!/middle.zip!/inner.zip!/deep.pdf', [f.path for f in limited.files])
        self.assertIn(('bundle.zip!/middle.zip!/inner.zip', 'skipped: archive nested deeper than 2 levels'), limited.issues)

    def test_unsafe_encrypted_bombs_and_budget(self):
        result = self.scan_zip({'../evil.pdf': b'e', '/abs.pdf': b'a', 'ok.pdf': b'fine'})
        reasons = dict(result.issues)
        self.assertEqual(reasons['bundle.zip!/../evil.pdf'], 'rejected: unsafe path')
        self.assertEqual(reasons['bundle.zip!//abs.pdf'], 'rejected: unsafe path')
        self.assertEqual(dict(self.scan_zip(encrypted_zip()).issues)['bundle.zip!/locked.pdf'], 'skipped: encrypted')
        self.assertIn('bundle.zip!/ok.pdf', [f.path for f in result.files])
        bomb = self.scan_zip({'zeros.bin': b'\0' * 200_000}, Limits(ratio_limit=10, ratio_min_bytes=1000))
        self.assertEqual(dict(bomb.issues)['bundle.zip!/zeros.bin'], 'skipped: compression ratio exceeds limit')
        capped = self.scan_zip({'a.pdf': b'x' * 5000, 'b.pdf': b'y' * 5000}, Limits(max_source_bytes=8000))
        self.assertTrue(any('exceeds' in reason for _, reason in capped.issues))

    def test_read_origin_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'src'; root.mkdir()
            (root / 'plain.pdf').write_bytes(b'plain')
            (root / 'pack.zip').write_bytes(zip_bytes({'a.pdf': b'member', 'n.zip': zip_bytes({'b.pdf': b'nested'})}))
            result = scan([root, root / 'plain.pdf'])
            data = {f.path: read_origin(f.origin) for f in result.files}
            self.assertEqual(data['src/plain.pdf'], b'plain')
            self.assertEqual(data['plain.pdf'], b'plain')
            self.assertEqual(data['src/pack.zip!/a.pdf'], b'member')
            self.assertEqual(data['src/pack.zip!/n.zip!/b.pdf'], b'nested')

if __name__ == '__main__':
    unittest.main()
