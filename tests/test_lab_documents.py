"""The lab sees every format a reader reads (code review 2026-10-08, E3): rounds' units, mechanical measures, batches
and review samples once read PDFs (and units text formats, whose batches then failed), so levers acting on images,
Word, decks or sheets were measured on PDFs alone."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import cli
from semantic_pdf_diff.store import Store
from semantic_pdf_diff_lab.eval import review, rounds
from semantic_pdf_diff_lab.eval.documents import Document, contents, extension
from semantic_pdf_diff_lab.eval.rounds.judging import TEXT_FORMAT
from test_concurrency import jittery_model, make_pdf
from test_images import png

NOTES = "# Plant\n\nPump P-1 is rated 10 kW.\n\nFan F-1 is rated 3 kW.\n\n# Heating\n\nHeater H-1 is rated 9 kW.\n"

class EveryFormat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.dir.name)
        first, second, slices = root / 'first', root / 'second', root / 'slices'  # slices: every document read
        for folder in (first, second, slices):
            folder.mkdir()
        make_pdf(first / 'a.pdf', ['Pump 10 kW, fan 3 kW', 'Chiller 350 kW'])
        (first / 'notes.md').write_text(NOTES)
        (first / 'photo.png').write_bytes(png(1600, 1200))
        make_pdf(second / 'b.pdf', ['Pump 12 kW, fan 3 kW', 'Heater 9 kW'])
        for path in [*first.iterdir(), *second.iterdir()]:
            shutil.copy(path, slices / path.name)
        cls.slices = slices
        files = [str(first), str(second)]
        with jittery_model() as (url, _), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            for name, extra in (('baseline', {}), ('variant', {'extract_rules': ['A variant rule.']})):
                config = root / f'{name}.json'
                config.write_text(json.dumps({'concurrency': 4, 'tile_points': 180, 'retries': 0, 'situate': False,
                                              **extra}))
                cli.main([*files, '--out', str(root / name / 'run1'), '--base-url', url, '--config', str(config)])
        # The stub reads text the same way under either variant: the variant loses the heater, as a lever might.
        with Store(root / 'variant' / 'run1') as store, store.db:
            store.db.execute("DELETE FROM evidence WHERE content LIKE '%.md' AND data LIKE '%9 kW%'")

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_units_and_measures_cover_every_format(self):
        units = rounds.collect(self.root / 'baseline')
        self.assertEqual({extension(content) for _, content, _, _ in units}, {'.pdf', '.md', '.png'})
        with Store.open(self.root / 'baseline' / 'run1') as store:
            families = sum(1 for c in contents(store) for row in store.coverage(c)
                           if rounds.FAMILY.get(rounds.region_of(row['task'])))
            self.assertEqual({extension(c) for c in contents(store)}, {'.pdf', '.md', '.png'})
        self.assertEqual(rounds.mechanical(self.root / 'baseline')['all']['tasks'], families)

    def test_an_image_is_shown_as_its_reader_laid_it_out(self):
        with Store.open(self.root / 'baseline' / 'run1') as store:
            image = next(c for c in contents(store) if c.endswith('.png'))
            boxes = [e.locator.bbox for e in store.evidence(image)]
            with Document.of(store, image) as doc:
                page = doc.pdf[0].rect
        self.assertAlmostEqual(page.width, 1600 * 96 / 72 * 180 / 1000 * 72 / 96, places=3)  # tile_points 180
        self.assertTrue(boxes)
        self.assertTrue(all(b[2] <= page.width + 0.01 and b[3] <= page.height + 0.01 for b in boxes))

    def test_batches_show_text_formats_as_lines_and_come_back_from_the_documents(self):
        folder = self.root / 'batch'
        built = rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=40, limit=1)
        by_format = {}
        for item in built['items']:
            by_format.setdefault(extension(item['content']), []).append(item)
        self.assertIn('.md', by_format)
        for item in by_format['.md']:
            self.assertIsNone(item['image'])
            self.assertIn('kW', item['page_text'])
        self.assertTrue(any(i['band'] for i in by_format['.md']))  # cut into bands by line
        self.assertTrue(all(i['image'] for f, items in by_format.items() if f != '.md' for i in items))
        self.assertTrue(all(i.get('layout') == {'tile_points': 180, 'image_side': 1000}
                            for i in by_format.get('.png', [])))
        for item, _, prompt, images, *_ in rounds.pair_requests(folder, rounds.load_batch(folder)):
            if item['image'] is None:
                self.assertIn(TEXT_FORMAT, prompt)
                self.assertEqual(images, [])
        rounds.add_context(folder, self.root / 'baseline', self.root / 'variant', n=40, limit=1)
        context = rounds.load_batch(folder)
        for item in context['items']:
            if extension(item['content']) == '.md':
                self.assertIsNone(item['page_image'])
                self.assertIn('Heater', item['page_text_full'])
        originals = {p.name: p.read_bytes() for p in (folder / 'images').iterdir()}
        pages = (folder / rounds.PAGES).read_text()
        shutil.rmtree(folder / 'images')
        (folder / rounds.PAGES).unlink()
        rounds.rerender(folder, self.slices)
        self.assertEqual({p.name: p.read_bytes() for p in (folder / 'images').iterdir()}, originals)
        self.assertEqual((folder / rounds.PAGES).read_text(), pages)

    def test_review_samples_show_every_format(self):
        folder = self.root / 'review'
        with contextlib.redirect_stdout(io.StringIO()):
            batch = review.sample([('x', self.root / 'baseline' / 'run1')], folder, claims=200, abouts=0, pairs=0)
        claims = [i for i in batch['items'] if i['type'] == 'claim']
        with Store.open(self.root / 'baseline' / 'run1') as store:
            formats = {c: extension(c) for c in contents(store)}
            by_claim = {e.id: formats[c] for c in formats for e in store.evidence(c)}
        shown = {by_claim[i['target']['claim']] for i in claims}
        self.assertEqual(shown, {'.pdf', '.md', '.png'})
        for item in claims:
            if by_claim[item['target']['claim']] == '.md':
                self.assertEqual(item['images'], [])
                self.assertIn('» ', item['texts'][0]['text'])
                self.assertIn('source text', review.judge_prompt(item))
            else:
                self.assertTrue(item['images'])
                self.assertNotIn('texts', item)
        self.assertIn('item.texts', (folder / 'review.html').read_text())

if __name__ == '__main__':
    unittest.main()
