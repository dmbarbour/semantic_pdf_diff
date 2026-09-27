import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli, rounds
from semantic_pdf_diff.models import PairVerdict, Settings
from test_concurrency import jittery_model, make_pdf

class Judge:
    """A stand-in panel model: prefers the set with more claims, or always 'B' (pure position bias)."""
    def __init__(self, always_b=False):
        self.s, self.always_b = Settings(), always_b
        self.calls, self.cache_hits, self.usage, self.prompts = 0, 0, {'prompt_tokens': 0, 'completion_tokens': 0}, []
    def ask(self, prompt, schema, images=(), key=None):
        self.prompts.append(prompt)
        if self.always_b:
            return PairVerdict(better='B', note='position bias')
        a = prompt.split('SET A:')[1].split('SET B:')[0].count('\n- ')
        b = prompt.split('SET B:')[1].count('\n- ')
        return PairVerdict(better='A' if a > b else 'B' if b > a else 'same', note='counted')

class Rounds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        root = cls.root = Path(cls.dir.name)
        a = make_pdf(root / 'a.pdf', ['Pump 10 kW, fan 3 kW', 'Chiller 350 kW'])
        b = make_pdf(root / 'b.pdf', ['Pump 12 kW, fan 3 kW', 'Heater 9 kW'])
        with jittery_model() as (url, _), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for name, extra in (('baseline', {}), ('variant', {'extract_rules': ['A variant rule.']})):
                config = root / f'{name}.json'
                config.write_text(json.dumps({'concurrency': 4, 'tile_points': 180, 'retries': 0, 'situate': False, **extra}))
                cli.main([str(a), str(b), '--out', str(root / name / 'run1'), '--base-url', url, '--config', str(config)])

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_units_pair_page_regions_across_variants(self):
        base = rounds.collect(self.root / 'baseline')
        self.assertTrue({k[3] for k in base} >= {'text', 'visual'})
        picked, counts = rounds.pair_units(self.root / 'baseline', self.root / 'variant', n=6)
        self.assertTrue(picked)
        families = [k[3] for k, _, _ in picked]
        if len(set(families)) > 1:  # round-robin over families: the first two picks differ
            self.assertNotEqual(families[0], families[1])
        self.assertGreater(counts['units'], len(picked) - 1)
        for (_, _, _, family), a, b in picked:  # changed units only: identical answers can't prefer a side
            self.assertNotEqual(set(a), set(b))

    def test_position_bias_cancels_and_real_preference_decides(self):
        folder = self.root / 'batch'
        batch = rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=8)
        self.assertTrue(batch['items'] and all((folder / i['image']).exists() for i in batch['items']))
        rounds.judge_pairs(folder, Judge(always_b=True), 'biased')
        self.assertTrue(all(abs(s - 0.5) < 1e-9 for s in rounds.unit_scores(folder).values()))  # both orders cancel
        (folder / 'verdicts' / 'biased.json').unlink()
        rounds.judge_pairs(folder, Judge(), 'counter')
        decision = rounds.decide(folder)
        self.assertEqual(decision['units_judged'], len(batch['items']))
        self.assertEqual(rounds.decide(folder, limit=2)['units_judged'], 2)  # only units every judge has seen so far
        self.assertIn(decision['decision'].split(':')[0], ('accepted', 'rejected', 'no worse', 'inconclusive'))
        self.assertIn('overall', decision)

    def test_rubric_v2_tags_problems_and_keeps_remarks_for_the_insights_page(self):
        from semantic_pdf_diff import insights
        folder = self.root / 'batch-v2'
        batch = rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=4)
        (folder / 'round.json').parent.mkdir(exist_ok=True)

        class Tagger(Judge):
            def ask(self, prompt, schema, images=(), key=None):
                self.prompts.append(prompt)
                return PairVerdict(better='A', note='A binds values', a_problems=['duplicates', 'not-a-tag'],
                                   b_problems=['Misbound'], remarks='The page image is cut off at the right.')
        judge = Tagger()
        rounds.judge_pairs(folder, judge, 'tagger', rubric='v2')
        self.assertTrue(all('a_problems' in p and 'neutral' in p for p in judge.prompts))
        verdicts = json.loads((folder / 'verdicts' / 'tagger.json').read_text())['verdicts']
        first = verdicts[batch['items'][0]['id']]
        # Tags follow the sides, not the positions; unknown tags are dropped.
        self.assertEqual(first['baseline-first']['baseline_problems'], ['duplicates'])
        self.assertEqual(first['variant-first']['baseline_problems'], ['misbound'])
        self.assertEqual(first['baseline-first']['remarks'], 'The page image is cut off at the right.')
        analysis = insights.analyse(folder)
        self.assertEqual(analysis['summary']['units'], len(batch['items']))
        self.assertTrue(all(u['order_flipped'] == ['tagger'] for u in analysis['units']))  # always "A": flips
        self.assertEqual(analysis['summary']['remarks'], 2 * len(batch['items']))
        round_folder = self.root
        (round_folder / 'round.json').write_text(json.dumps({'name': 'rt', 'variants': {'v2': 'x.json'}}))
        (round_folder / 'pairs-v2').mkdir(exist_ok=True)
        for name in ('pairs.json', 'analysis.json'):
            (round_folder / 'pairs-v2' / name).write_text((folder / name).read_text())
        page = insights.page(round_folder).read_text()
        self.assertIn('cut off at the right', page)
        self.assertIn('duplicates', page)

    def test_judges_see_every_difference_and_the_same_shared_sample(self):
        import random
        a = {f'id{i:02}': i for i in range(40)}
        b = {k: v for k, v in a.items() if v not in (3, 7)} | {'new1': 1, 'new2': 2}
        shown_a, shown_b = rounds.shown(a, b, random.Random(1), limit=25)
        self.assertTrue({'id03', 'id07'} <= set(shown_a) and {'new1', 'new2'} <= set(shown_b))
        self.assertEqual(set(shown_a) - {'id03', 'id07'}, set(shown_b) - {'new1', 'new2'})  # same shared sample
        self.assertTrue(len(shown_a) <= 25 and len(shown_b) <= 25)

    def test_rubric_v1_prompt_is_unchanged(self):
        prompt = rounds.pairwise_prompt('v1')
        self.assertNotIn('a_problems', prompt)
        self.assertNotIn('neutral', prompt)
        self.assertIn('{page_text}', prompt)
        v3 = rounds.pairwise_prompt('v3').format(page=5, family='text', page_text='t', a='- a', b='- b',
                                                 sections='7 Control > 7.1 Filter')
        self.assertIn('under the headings: 7 Control > 7.1 Filter', v3)  # judges see what the extractor saw
        batch = json.loads((self.root / 'batch' / 'pairs.json').read_text()) if (self.root / 'batch').exists() else None
        if batch:
            self.assertTrue(all('sections' in i for i in batch['items']))

    def test_bootstrap_and_rules(self):
        mean, low, high = rounds.bootstrap([1.0] * 40 + [0.0] * 10)
        self.assertAlmostEqual(mean, 0.8)
        self.assertTrue(0.65 < low < 0.8 < high < 0.92)
        self.assertIsNone(rounds.bootstrap([]))

class Report(unittest.TestCase):
    def test_every_recorded_figure_is_drawn(self):
        from semantic_pdf_diff import ledger
        with tempfile.TemporaryDirectory() as d:
            history = Path(d) / 'history.jsonl'
            for rnd, win in (('r01', 0.62), ('r02', 0.41)):
                ledger.figure(history, metric='win_rate', value={'mean': win, 'low': win - 0.08, 'high': win + 0.08},
                              round=rnd, variant='neighbours', stratum='all')
                ledger.figure(history, metric='win_rate', value={'mean': win, 'low': win - 0.1, 'high': win + 0.1},
                              round=rnd, variant='neighbours', stratum='text')
                ledger.figure(history, metric='partial_rate', value=0.2, round=rnd, variant='baseline', stratum='all')
                ledger.figure(history, metric='spent', value=3.5, round=rnd, step='judge')
                ledger.figure(history, metric='decision', value='accepted: wins', round=rnd, variant='neighbours')
            target = rounds.report(history, Path(d) / 'report.html')
            page = target.read_text()
            self.assertEqual(page.count('<svg'), 6)
            self.assertIn('r02', page)
            self.assertIn('accepted: wins', page)
            self.assertIn('<circle', page)

if __name__ == '__main__':
    unittest.main()
