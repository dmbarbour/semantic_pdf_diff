import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli, queries
from semantic_pdf_diff.models import Settings
from test_concurrency import jittery_model
from test_settings import document

class Checker:
    """A stand-in checker model: flags any query whose change added text before its region."""
    def __init__(self):
        self.s, self.calls, self.cache_hits, self.usage, self.prompts = Settings(), 0, 0, {}, []
    def ask(self, prompt, schema, images=(), key=None):
        self.prompts.append((prompt, list(images)))
        if '\n+Before: ...' in prompt:
            return schema(ok=False, problems=['junk-context', 'not-a-tag'], note='Before: holds table cells')
        return schema(ok=True)

class Dumps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.dir.name)
        a, b = document(root / 'a.pdf', 10), document(root / 'b.pdf', 12)
        with jittery_model() as (url, _), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for side, settings in (('base', {'context_before': 0}), ('variant', {})):  # the variant adds text before
                config = root / f'{side}.json'
                config.write_text(json.dumps({**settings, 'situate': False}))
                cli.main([str(a), str(b), '--out', str(root / side / 'run1'), '--base-url', url, '--config', str(config)])

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_a_dump_against_a_baseline_shows_only_what_changed(self):
        out = self.root / 'dump'
        summary = queries.dump(self.root / 'variant', out, against=self.root / 'base', sample=50)
        self.assertGreater(summary['unchanged'], 0)  # image queries don't depend on text before
        self.assertEqual(summary['by_status'], {'changed': summary['candidates'], 'added': 0, 'removed': 0, 'sampled': 0})
        shown = queries.items(out)
        self.assertEqual(len(shown), summary['candidates'])
        for item in shown:
            self.assertIn('context_before', item['notes'])  # what the lever added, per query
            self.assertTrue(any(line.startswith('+Before: ...') for line in item['diff']))
            self.assertNotEqual(item['query'], item['baseline_query'])
        self.assertIn('Before: ...', (out / 'index.html').read_text())

    def test_a_dump_of_one_lever_samples_by_document_and_kind(self):
        out = self.root / 'lever'
        summary = queries.dump(self.root / 'variant', out, lever='visual_text_layer', sample=4)
        shown = queries.items(out)
        self.assertEqual(len(shown), 4)
        self.assertTrue(all('visual_text_layer' in i['notes'] and i['status'] == 'sampled' for i in shown))
        self.assertTrue(all(i['images'] and (out / i['images'][0]).exists() for i in shown))  # the images it was sent
        self.assertGreater(summary['candidates'], 4)

    def test_checkers_flag_queries_and_the_page_shows_them(self):
        out = self.root / 'checked'
        shown = queries.dump(self.root / 'variant', out, against=self.root / 'base', sample=3)['shown']
        self.assertGreater(shown, 1)
        checker = Checker()
        target, count, failures = queries.check(out, checker, 'stub-checker')
        self.assertEqual((count, failures), (shown, []))
        self.assertTrue(all('<<<REQUEST' in p and 'Compared with the baseline' in p for p, _ in checker.prompts))
        flagged = queries.flagged(out)
        self.assertEqual(len(flagged), shown)
        self.assertEqual(next(iter(flagged.values()))['stub-checker']['problems'], ['junk-context'])  # tags kept to the list
        queries.check(out, checker, 'stub-checker')  # checked already: nothing asked again
        self.assertEqual(len(checker.prompts), shown)
        self.assertIn('Before: holds table cells', (out / 'index.html').read_text())

if __name__ == '__main__':
    unittest.main()
