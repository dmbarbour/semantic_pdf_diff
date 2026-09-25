import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli, review
from semantic_pdf_diff.models import PanelLabel, Settings
from semantic_pdf_diff.taxonomy import CLARITY, CONFIDENCE, TAXONOMY, flag_names
from test_concurrency import jittery_model, make_pdf

class Alpha(unittest.TestCase):
    def test_krippendorff_worked_example(self):
        # Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability", nominal example: 0.743.
        units = [[1, 1, 1], [2, 2, 3, 2], [3, 3, 3, 3], [3, 3, 3, 3], [2, 2, 2, 2], [1, 2, 3, 4], [4, 4, 4, 4],
                 [1, 1, 2, 1], [2, 2, 2, 2], [5, 5, 5], [1, 1], [3]]
        self.assertAlmostEqual(review.krippendorff_alpha(units), 0.743, places=3)
        self.assertEqual(review.krippendorff_alpha([['a', 'a'], ['b', 'b']]), 1.0)
        self.assertLess(review.krippendorff_alpha([['a', 'b'], ['b', 'a']]), 0)
        self.assertIsNone(review.krippendorff_alpha([['a', 'a'], ['a', 'a']]))  # no variation: undefined

class Consensus(unittest.TestCase):
    def test_reliable_reviewers_outweigh_random_ones(self):
        import random
        rng = random.Random(3)
        classes = ['correct', 'flawed', 'wrong', 'not_a_claim']
        truth = {f'i{n}': rng.choice(classes) for n in range(60)}
        labels = {}
        for item, true in truth.items():
            given = {}
            for r in ('careful-1', 'careful-2', 'careful-3'):
                given[r] = true if rng.random() < 0.85 else rng.choice(classes)
            for r in ('random-1', 'random-2'):
                given[r] = rng.choice(classes)
            labels[item] = given
        posteriors, confusion = review.dawid_skene(labels, classes)
        consensus = {i: max(p, key=p.get) for i, p in posteriors.items()}
        self.assertGreaterEqual(sum(consensus[i] == truth[i] for i in truth), 54)  # at least 90% recovered
        reliability = {r: sum(confusion[r][c][c] for c in classes) / len(classes) for r in confusion}
        self.assertGreater(min(reliability[r] for r in reliability if r.startswith('careful')),
                           max(reliability[r] for r in reliability if r.startswith('random')))

class Highlight(unittest.TestCase):
    def test_box_lands_on_the_region_in_crops_and_pages(self):
        import pymupdf
        doc = pymupdf.open(); doc.new_page(width=400, height=400)
        box = (100, 200, 200, 260)
        for clip in (None, (60, 150, 260, 320)):  # a whole page, and a crop whose origin isn't (0, 0)
            with self.subTest(clip=clip):
                pix = pymupdf.Pixmap(review.render(doc, 1, clip, box, side=400))
                zoom = pix.width / (400 if clip is None else clip[2] - clip[0])
                ox, oy = (0, 0) if clip is None else clip[:2]
                x, y = int((box[0] - ox) * zoom) + 1, int(((box[1] + box[3]) / 2 - oy) * zoom)
                red, green, _ = pix.pixel(x, y)
                self.assertGreater(red, 150); self.assertLess(green, 100)
                red, green, _ = pix.pixel(x + 20, y)  # inside the box: untouched white
                self.assertGreater(green, 200)

class FakePanel:
    """Answers every item with the first verdict, plus one real and one invented flag."""
    def __init__(self):
        self.s = Settings()
        self.calls, self.cache_hits, self.usage = 0, 0, {'prompt_tokens': 0, 'completion_tokens': 0}
        self.prompts = []
    def ask(self, prompt, schema, images=(), key=None):
        self.prompts.append((prompt, list(images)))
        kind = prompt.split('ITEM (', 1)[1].split(')', 1)[0]
        flag = sorted(flag_names(kind))[0]
        return PanelLabel(verdict=TAXONOMY[kind]['verdicts'][0]['name'], flags=[flag, 'made_up_flag'],
                          clarity='clear', confidence='high', note='ok')

class Batches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        root = Path(cls.dir.name)
        a = make_pdf(root / 'a.pdf', ['Pump 10 kW, fan 3 kW', 'Chiller 350 kW'])
        b = make_pdf(root / 'b.pdf', ['Pump 12 kW, fan 3 kW', 'Heater 9 kW'])
        config = root / 'c.json'
        config.write_text(json.dumps({'concurrency': 4, 'tile_points': 180, 'retries': 0}))
        with jittery_model() as (url, _), contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            cli.main([str(a), str(b), '--out', str(root / 'store'), '--base-url', url, '--config', str(config)])
        cls.store = root / 'store'

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def batch(self, name='b1', seed=1):
        folder = Path(self.dir.name) / name
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(['review', 'sample', str(folder), '--store', f'SECRET-RESPONDER={self.store}', '--claims', '6',
                      '--abouts', '2', '--pairs', '2', '--seed', str(seed)])
        return folder, json.loads((folder / 'batch.json').read_text())

    def labels(self, batch, reviewer, verdict_index=0):
        return {'format': review.FORMAT, 'version': 1, 'batch': batch['name'], 'reviewer': reviewer, 'labels': [
            {'item': i['id'], 'verdict': TAXONOMY[i['type']]['verdicts'][verdict_index]['name'], 'flags': [],
             'clarity': CLARITY[0]['name'], 'confidence': CONFIDENCE[0]['name'], 'note': ''} for i in batch['items']]}

    def test_sampling_is_stratified_blind_and_reproducible(self):
        folder, batch = self.batch()
        types = [i['type'] for i in batch['items']]
        self.assertEqual((types.count('claim'), types.count('about'), types.count('pair')), (6, 2, 2))
        kinds = {i['shown']['kind'] for i in batch['items'] if i['type'] == 'claim'}
        self.assertGreater(len(kinds), 1)  # round-robin over claim kinds
        self.assertTrue(all((folder / img['src']).exists() for i in batch['items'] for img in i['images']))
        page = (folder / 'review.html').read_text()
        self.assertNotIn('SECRET-RESPONDER', page)  # reviewers don't see who produced an item
        self.assertIn(batch['items'][0]['id'], page)
        _, again = self.batch('b1-again')
        self.assertEqual([i['id'] for i in again['items']], [i['id'] for i in batch['items']])

    def test_labels_are_validated_imported_and_compared(self):
        folder, batch = self.batch('b2')
        good, other = self.labels(batch, 'david'), self.labels(batch, 'claude', verdict_index=-1)
        other['labels'][0]['verdict'] = good['labels'][0]['verdict']
        bad = json.loads(json.dumps(good))
        bad['labels'][0]['flags'] = ['not_a_flag']
        bad['labels'][1]['clarity'] = 'murky'
        paths = {}
        for name, data in (('good', good), ('other', other), ('bad', bad)):
            paths[name] = folder / f'{name}.json'
            paths[name].write_text(json.dumps(data))
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(['review', 'import', str(folder), str(paths['good']), str(paths['other'])])
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cli.main(['review', 'import', str(folder), str(paths['bad'])]), 1)
        self.assertIn('not_a_flag', err.getvalue())
        self.assertIn('murky', err.getvalue())
        result = review.agreement(folder)
        self.assertEqual(result['reviewers'], ['claude', 'david'])
        claims = result['types']['claim']
        self.assertEqual(claims['verdict_agreement']['claude ~ david'].split('/')[1], str(claims['items']))
        scores = review.scores(folder)
        self.assertEqual({row['store'] for row in scores}, {'SECRET-RESPONDER'})

    def test_panel_reviews_are_cleaned_into_labels(self):
        folder, batch = self.batch('b3')
        panel = FakePanel()
        target, count, failures = review.judge(folder, panel, 'panel/model-x')
        self.assertEqual((count, failures), (len(batch['items']), []))
        self.assertEqual(target.name, 'panel_model-x.json')
        data = json.loads(target.read_text())
        self.assertTrue(all('made_up_flag' not in l['flags'] and 'unknown flags dropped' in l['note'] for l in data['labels']))
        self.assertEqual(review.validate(batch, data), [])
        prompt, images = panel.prompts[0]
        self.assertNotIn('SECRET-RESPONDER', prompt)
        self.assertTrue(images and all(Path(p).exists() for p in images))

if __name__ == '__main__':
    unittest.main()
