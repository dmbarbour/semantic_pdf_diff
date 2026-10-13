import stubs  # noqa: F401 (a clean environment)
import sys
import unittest
from pathlib import Path
from semantic_pdf_diff.compare import compare, file_difference, relative_path
from semantic_pdf_diff.schema import FileRef

sys.path.insert(0, str(Path(__file__).parent))
from test_pipeline import Fake, ev  # noqa: E402

def files(source, entries):
    return [FileRef(source=source, path=p, content=f'sha256:{c * 64}.{p.rsplit(".", 1)[1].lower()}')
            for p, c in entries]

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
        self.assertEqual(diff['modified'],
                         [['rev1/b.pdf', 'rev2/b.pdf'], ['rev1/pack.zip!/m.pdf', 'rev2/pack.zip!/m.pdf']])
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
        result = compare([unique_left, shared], [shared, unique_right], Path('.'), Fake(relation='equivalent'),
                         'revisions')
        pairs = {(f['a'], f['b']): f['relation'] for f in result['findings']}
        self.assertEqual(pairs.get(('A-1', 'S-1')), 'equivalent')
        self.assertNotIn(('S-1', 'S-1'), pairs)
        self.assertEqual(result['shared'], ['S-1'])
        self.assertNotIn('A-1', [u['id'] for u in result['unmatched']])

if __name__ == '__main__':
    unittest.main()

class InputOrder(unittest.TestCase):
    def test_a_comparison_doesnt_depend_on_its_claims_order(self):
        """Explanations' siblings and echoes, item names, ties and lists followed the input's order, canonical only
        because the store sorts (the determinism review, D10)."""
        import json
        import random
        import tempfile
        from semantic_pdf_diff.schema import PdfLocator

        def side(letter, shift):
            found = []
            for f, content in enumerate('cd'):
                for i in range(1, 7):
                    for attribute, value in (('rated power', 10 + i + shift * (i % 2)), ('flow', 50)):
                        found.append(ev(f'{letter}-{f}{i}{attribute[0]}', content=f'sha256:{content * 64}.pdf',
                                        entity=f'pump P-{i}' if i < 5 else 'pump', attribute=attribute,
                                        value=str(value), unit='kW' if attribute == 'rated power' else 'L/s',
                                        locator=PdfLocator(page=i, bbox=(0, 0, 100, 100), region='text',
                                                           task=f'text:{i}')))
            return found
        left, right = side('A', 0), side('B', 1)
        results = []
        for seed in (None, 1, 2, 3):
            a, b = list(left), list(right)
            if seed:
                random.Random(seed).shuffle(a)
                random.Random(seed + 10).shuffle(b)
            with tempfile.TemporaryDirectory() as d:
                found = compare(a, b, Path(d), Fake(kind='changed'), 'revisions')
            results.append(json.dumps(found, sort_keys=True, default=str))
        for seed, result in zip((1, 2, 3), results[1:]):
            with self.subTest(seed=seed):
                self.assertEqual(result, results[0])
