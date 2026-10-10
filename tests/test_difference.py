import stubs  # noqa: F401 (a clean environment)
import sys
import unittest
from pathlib import Path
from semantic_pdf_diff.compare import compare, file_difference, relative_path
from semantic_pdf_diff.schema import FileRef

sys.path.insert(0, str(Path(__file__).parent))
from test_pipeline import Fake, ev  # noqa: E402

def files(source, entries):
    return [FileRef(source=source, path=p, content=f'sha256:{c * 64}.{p.rsplit(".", 1)[1].lower()}') for p, c in entries]

class FileDifference(unittest.TestCase):
    def test_relative_paths(self):
        self.assertEqual(relative_path('rev1/design/a.pdf'), 'design/a.pdf')
        self.assertEqual(relative_path('v1.zip!/a.pdf'), 'a.pdf')
        self.assertEqual(relative_path('rev1/bundle.zip!/a.pdf'), 'bundle.zip!/a.pdf')
        self.assertEqual(relative_path('report.pdf'), 'report.pdf')

    def test_classification_across_differently_named_roots(self):
        a = files('rev1', [('rev1/a.pdf', 'a'), ('rev1/b.pdf', 'b'), ('rev1/c.pdf', 'c'), ('rev1/e.pdf', 'e'),
                           ('rev1/pack.zip', 'z'), ('rev1/pack.zip!/m.pdf', 'm')])
        b = files('rev2', [('rev2/a.pdf', 'a'), ('rev2/b.pdf', 'B'), ('rev2/sub/c.pdf', 'c'), ('rev2/d.pdf', 'd'),
                           ('rev2/pack.zip', 'Z'), ('rev2/pack.zip!/m.pdf', 'M')])
        diff = file_difference(a, b)
        self.assertEqual(diff['unchanged'], ['rev2/a.pdf'])
        self.assertEqual(diff['modified'], [['rev1/b.pdf', 'rev2/b.pdf'], ['rev1/pack.zip!/m.pdf', 'rev2/pack.zip!/m.pdf']])
        self.assertEqual(diff['moved'], [['rev1/c.pdf', 'rev2/sub/c.pdf']])
        self.assertEqual((diff['added'], diff['removed']), (['rev2/d.pdf'], ['rev1/e.pdf']))

    def test_single_file_sources_compare_as_one_file(self):
        diff = file_difference(files('old', [('old.pdf', 'a')]), files('new', [('new.pdf', 'b')]))
        self.assertEqual(diff['modified'], [['old.pdf', 'new.pdf']])
        diff = file_difference(files('x', [('x.pdf', 'a')]), files('y', [('y.pdf', 'a')]))
        self.assertEqual(diff['unchanged'], ['y.pdf'])

class SharedTargets(unittest.TestCase):
    def test_unique_claims_match_shared_evidence(self):
        shared = ev('S-1', value='10', unit='kW')
        unique_left = ev('A-1', value='10000', unit='W')
        unique_right = ev('B-2', entity='firewall', attribute='log retention', value='90', unit='days',
                          conditions='security policy')
        result = compare([unique_left, shared], [shared, unique_right], Path('.'), Fake(relation='equivalent'), 'revisions')
        pairs = {(f['a'], f['b']): f['relation'] for f in result['findings']}
        self.assertEqual(pairs.get(('A-1', 'S-1')), 'equivalent')
        self.assertNotIn(('S-1', 'S-1'), pairs)
        self.assertEqual(result['shared'], ['S-1'])
        self.assertNotIn('A-1', [u['id'] for u in result['unmatched']])

if __name__ == '__main__':
    unittest.main()
