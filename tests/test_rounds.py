import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import pymupdf
import unittest
from pathlib import Path
from semantic_pdf_diff import cli
from semantic_pdf_diff_lab.eval import rounds
from unittest.mock import patch
from semantic_pdf_diff.llm import ModelFailure
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff_lab.eval.models import PairVerdict
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
        from semantic_pdf_diff_lab.eval import insights
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

    def test_large_units_are_cut_into_bands_by_where_claims_were_read(self):
        claims = lambda ids, y: {i: {'entity': 'e', 'attribute': 'a', 'value': i, 'quote': i, '_box': [0, y(n), 10, y(n) + 5]}
                                 for n, i in enumerate(ids)}
        key = ('run', 'c', 1, 'visual')
        base = {key: {'claims': claims([f'x{i:02}' for i in range(60)], lambda n: n * 10), 'tasks': 3},
                ('run', 'c', 2, 'text'): {'claims': claims(['t1'], lambda n: 0), 'tasks': 1}}
        var = {key: {'claims': claims([f'x{i:02}' for i in range(50)], lambda n: n * 10), 'tasks': 3}}
        a, b = rounds.split_units(base, var, limit=25)
        bands = sorted(k for k in a if k[:4] == key)
        self.assertEqual(len(bands), 3)  # 60 claims, at most 25 per band
        self.assertEqual(sum(len(a[k]['claims']) for k in bands), 60)
        self.assertTrue(all(k[4][2] <= k[4][3] for k in bands))
        top = bands[0]
        self.assertEqual(a[top]['claims'].keys(), b[top]['claims'].keys())  # the variant lost only lower claims
        self.assertIn(('run', 'c', 2, 'text'), a)  # small units stay whole

    def test_bands_cut_a_turned_sheet_across_as_displayed(self):
        """Bands were cut by unrotated y, which on a sheet turned a quarter is a strip down the
        page as read (code review 2026-10-01, item 15)."""
        doc = pymupdf.open()
        page = doc.new_page(width=1224, height=792)
        page.set_rotation(90)
        # Claims along the unrotated x (down the page as displayed), at one unrotated y; ids out of order.
        ids = [f'x{(n * 7) % 60:02}' for n in range(60)]
        claims = {i: {'entity': 'e', 'attribute': 'a', 'value': i, 'quote': i, '_box': [20 * n, 300, 20 * n + 10, 310]}
                  for n, i in enumerate(ids)}
        key = ('run', 'c', 1, 'visual')
        units = {key: {'claims': claims, 'tasks': 1}}
        a, _ = rounds.split_units(units, units, limit=25, rotation=lambda run, content, number: page.rotation_matrix)
        bands = sorted(k for k in a if k[:4] == key)
        self.assertEqual(len(bands), 3)
        spans = sorted((min(claims[i]['_box'][0] for i in a[k]['claims']), max(claims[i]['_box'][2] for i in a[k]['claims']))
                       for k in bands)
        self.assertTrue(all(one[1] < two[0] for one, two in zip(spans, spans[1:])))  # each band a stretch of the sheet
        for k in bands:
            region = rounds.band_region(page, k[4])
            for i in a[k]['claims']:
                self.assertTrue(region.contains(pymupdf.Rect(claims[i]['_box'])))  # the crop shows its claims
        upright, _ = rounds.split_units(units, units, limit=25)
        self.assertNotEqual(sorted(sorted(upright[k]['claims']) for k in upright),
                            sorted(sorted(a[k]['claims']) for k in bands))  # unrotated, the cut fell elsewhere
        doc.close()

    def test_scores_average_each_judges_orders_and_skip_single_orders(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / 'pairs.json').write_text(json.dumps({'items': [{'id': 'u1', 'family': 'text'}, {'id': 'u2', 'family': 'text'}],
                                                           'units': {'units': 10, 'unchanged': 8}}))
            (folder / 'verdicts').mkdir()
            both = {'baseline-first': {'score': 1.0}, 'variant-first': {'score': 0.0}}  # a flip: 0.5
            (folder / 'verdicts' / 'j1.json').write_text(json.dumps({'reviewer': 'j1', 'verdicts': {
                'u1': both, 'u2': {'baseline-first': {'score': 1.0}}}}))  # u2: one order only (biased)
            (folder / 'verdicts' / 'j2.json').write_text(json.dumps({'reviewer': 'j2', 'verdicts': {
                'u1': {'baseline-first': {'score': 1.0}, 'variant-first': {'score': 1.0}}}}))
            self.assertEqual(rounds.unit_scores(folder), {'u1': 0.75})
            with patch('semantic_pdf_diff_lab.eval.review.reviewer_file', lambda r: r):
                self.assertEqual(rounds.unsettled(folder, ['j1']), {'u1', 'u2'})  # flipped; failed an order
            self.assertEqual(rounds.decide(folder)['coverage'], 0.2)

    def test_units_judged_on_the_wrong_input_can_be_left_out(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            items = [{'id': f'u{i}', 'family': 'text'} for i in range(3)]
            (folder / 'pairs.json').write_text(json.dumps({'items': items, 'units': {'units': 3, 'unchanged': 0}}))
            (folder / 'verdicts').mkdir()
            (folder / 'verdicts' / 'j.json').write_text(json.dumps({'reviewer': 'j', 'verdicts': {
                u: {'baseline-first': {'score': s}, 'variant-first': {'score': s}} for u, s in (('u0', 1.0), ('u1', 1.0), ('u2', 0.0))}}))
            self.assertEqual(rounds.decide(folder)['units_judged'], 3)
            left = rounds.decide(folder, exclude=['u2'])  # u2 judged on another unit's crop, say
            self.assertEqual((left['units_judged'], left['overall']['mean']), (2, 1.0))

    def test_a_small_stratum_cannot_block(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            items = [{'id': f't{i}', 'family': 'text'} for i in range(12)] + [{'id': 'b1', 'family': 'table'},
                                                                              {'id': 'b2', 'family': 'table'}]
            (folder / 'pairs.json').write_text(json.dumps({'items': items, 'units': {'units': 14, 'unchanged': 0}}))
            (folder / 'verdicts').mkdir()
            win = {'baseline-first': {'score': 1.0}, 'variant-first': {'score': 1.0}}
            loss = {'baseline-first': {'score': 0.0}, 'variant-first': {'score': 0.0}}
            (folder / 'verdicts' / 'j.json').write_text(json.dumps({'reviewer': 'j', 'verdicts': {
                **{f't{i}': win for i in range(12)}, 'b1': loss, 'b2': loss}}))
            decision = rounds.decide(folder)
            self.assertEqual(decision['strata_units']['table'], 2)
            self.assertTrue(decision['decision'].startswith('accepted'))  # two lost tables don't block
            self.assertEqual(decision['borderline'], [])

    def test_document_families_are_strata_too(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            items = [{'id': f'r{i}', 'family': 'text', 'run': 'report-a'} for i in range(14)] + \
                    [{'id': f'd{i}', 'family': 'text', 'run': 'sheets-b'} for i in range(6)]
            (folder / 'pairs.json').write_text(json.dumps({'items': items, 'units': {'units': 20, 'unchanged': 0}}))
            (folder / 'verdicts').mkdir()
            win = {'baseline-first': {'score': 1.0}, 'variant-first': {'score': 1.0}}
            loss = {'baseline-first': {'score': 0.0}, 'variant-first': {'score': 0.0}}
            (folder / 'verdicts' / 'j.json').write_text(json.dumps({'reviewer': 'j', 'verdicts': {
                **{f'r{i}': win for i in range(14)}, **{f'd{i}': loss for i in range(6)}}}))
            self.assertEqual(rounds.decide(folder)['decision'], 'accepted: wins')  # the kinds alone: all text
            decision = rounds.decide(folder, documents={'report-a': 'reports', 'sheets-b': 'drawings'})
            self.assertEqual(decision['decision'], 'rejected: loses in drawings')
            self.assertEqual(decision['strata_units'], {'text': 20, 'drawings': 6, 'reports': 14})

    def test_a_bound_near_its_threshold_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            outcomes = [1.0] * 13 + [0.5] * 6 + [0.0] * 5  # low bound 0.524: a win, but only just
            items = [{'id': f't{i}', 'family': 'text'} for i in range(len(outcomes))]
            (folder / 'pairs.json').write_text(json.dumps({'items': items, 'units': {'units': 24, 'unchanged': 0}}))
            (folder / 'verdicts').mkdir()
            (folder / 'verdicts' / 'j.json').write_text(json.dumps({'reviewer': 'j', 'verdicts': {
                f't{i}': {'baseline-first': {'score': x}, 'variant-first': {'score': x}} for i, x in enumerate(outcomes)}}))
            decision = rounds.decide(folder)
            self.assertEqual(decision['decision'], 'accepted: wins')
            self.assertEqual(decision['borderline'], ['overall low 0.524 near 0.5'])

    def test_images_and_page_text_come_back_from_the_documents(self):
        """A batch's crops and page text are the documents' content, so they aren't committed (the owner, 2026-10-02):
        pairs.json holds the rest, and rerender makes them again, byte for byte."""
        import shutil
        folder = self.root / 'batch-rerender'
        built = rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=8, limit=1)
        lean = json.loads((folder / 'pairs.json').read_text())
        self.assertFalse(any('page_text' in i for i in lean['items']))  # kept apart, in pages.json
        self.assertTrue(all('page_text' in i for i in rounds.load_batch(folder)['items']))
        banded = [i for i in built['items'] if i['band']]
        self.assertTrue(banded)
        for i in banded:  # a band's crop is its own unit's (rounds 9, 9b and 9h once shared one between two units)
            self.assertIn(f"-{i['family']}-b", i['image'])
        originals = {p.name: p.read_bytes() for p in (folder / 'images').iterdir()}
        pages = (folder / rounds.PAGES).read_text()
        shutil.rmtree(folder / 'images')
        (folder / rounds.PAGES).unlink()
        with self.assertRaisesRegex(ValueError, 'no page text: restore it'):
            rounds.judge_pairs(folder, Judge(), 'judge')
        rounds.rerender(folder, self.root)  # a.pdf and b.pdf: the documents the runs read
        self.assertEqual({p.name: p.read_bytes() for p in (folder / 'images').iterdir()}, originals)
        self.assertEqual((folder / rounds.PAGES).read_text(), pages)

    def test_failed_verdicts_are_not_asked_again_until_the_retry(self):
        folder = self.root / 'batch-retry'
        rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=2)

        class Flaky(Judge):
            def __init__(self):
                super().__init__()
                self.fail = True
            def ask(self, prompt, schema, images=(), key=None):
                self.prompts.append(prompt)
                if self.fail:
                    raise ModelFailure('TimeoutError: The read operation timed out')
                return PairVerdict(better='same', note='ok')
        judge = Flaky()
        _, _, failures = rounds.judge_pairs(folder, judge, 'flaky')
        asked = len(judge.prompts)
        self.assertEqual(len(failures), asked)
        rounds.judge_pairs(folder, judge, 'flaky')  # a later chunk: the failed ones aren't asked again
        self.assertEqual(len(judge.prompts), asked)
        judge.fail = False
        rounds.judge_pairs(folder, judge, 'flaky', retry_failed=True)  # once more, at the end
        self.assertEqual(len(judge.prompts), 2 * asked)
        self.assertEqual(json.loads((folder / 'failures' / 'flaky.json').read_text()), {})

    def test_a_spot_check_is_blind_and_imports_as_verdicts(self):
        folder = self.root / 'spot'
        rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=4, limit=5)
        page = rounds.write_spotcheck(folder).read_text()
        order = json.loads((folder / 'spotcheck-order.json').read_text())
        self.assertNotIn('baseline', page.split('id="data">')[1].split('</script>')[0].replace('"baseline":', ''))
        rounds.judge_pairs(folder, Judge(), 'counter')  # the panel, for the comparison
        items = list(order)
        answers = [{'item': items[0], 'better': 'A', 'a_problems': ['missing'], 'b_problems': [], 'confidence': 'high',
                    'note': 'A reads the whole row'},
                   {'item': items[1], 'better': 'unsure', 'a_problems': [], 'b_problems': [], 'confidence': '', 'note': ''}]
        file = self.root / 'answers.json'
        file.write_text(json.dumps({'format': rounds.SPOTCHECK_FORMAT, 'batch': 'spot', 'reviewer': 'Dana Q',
                                    'answers': answers}))
        verdicts = json.loads(rounds.import_spotcheck(folder, file).read_text())['verdicts']
        first = verdicts[items[0]]
        chosen = next(iter(first.values()))
        self.assertEqual(chosen['score'], 1.0 if order[items[0]] == 'variant' else 0.0)  # A mapped back to its side
        side_a = order[items[0]]
        self.assertEqual(chosen[f'{side_a}_problems'], ['missing'])
        self.assertIsNone(next(iter(verdicts[items[1]].values()))['score'])  # "can't tell" isn't a score
        result = rounds.anchor(folder)['Dana Q']
        self.assertEqual(result['units'], 1)

    def test_claims_are_marked_one_by_one_by_people_and_judges(self):
        folder = self.root / 'spot-claims'
        batch = rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=3, limit=5)
        rounds.write_spotcheck(folder)
        order = json.loads((folder / 'spotcheck-order.json').read_text())

        class Marker(Judge):  # marks every claim of the first set shown wrong, the second right
            def ask(self, prompt, schema, images=(), key=None):
                self.prompts.append(prompt)
                count = lambda letter: sum(1 for line in prompt.splitlines() if line.startswith(letter) and '. ' in line[:4])
                return PairVerdict(better='B', note='marked', a_claims=[{'n': k + 1, 'mark': 'wrong', 'problems': ['misread']}
                                                                       for k in range(count('A'))],
                                   b_claims=[{'n': k + 1, 'mark': 'ok'} for k in range(count('B'))])
        judge = Marker()
        rounds.judge_pairs(folder, judge, 'marker', rubric='v5')
        self.assertTrue(all('A1. ' in p for p in judge.prompts if 'SET A (all 0' not in p))
        verdicts = json.loads((folder / 'verdicts' / 'marker.json').read_text())['verdicts']
        some = next(u for u in verdicts if batch['items'][0]['id'] == u)
        first = verdicts[some]['baseline-first']['claims']
        self.assertTrue(all(c['mark'] == 'wrong' for c in first['baseline']))  # A was the baseline in that order
        self.assertTrue(all(c['mark'] == 'ok' for c in first['variant']))
        shares = rounds.claim_shares(folder)
        for side in ('baseline', 'variant'):  # each claim was in set A once (wrong) and in set B once (right)
            self.assertEqual(shares[side]['wrong'], shares[side]['ok'])
            self.assertEqual(shares[side]['wrong_share'], 0.5)
        # a person marks the first claim of set A right
        item = batch['items'][0]
        answers = [{'item': item['id'], 'better': 'A', 'a_problems': [], 'b_problems': [], 'confidence': 'low', 'note': '',
                    'claims': {'A': {'0': {'mark': 'ok', 'problems': []}}, 'B': {}}}]
        file = self.root / 'claim-answers.json'
        file.write_text(json.dumps({'format': rounds.SPOTCHECK_FORMAT, 'batch': 'spot-claims', 'reviewer': 'Kim',
                                    'answers': answers}))
        mine = json.loads(rounds.import_spotcheck(folder, file).read_text())['verdicts'][item['id']]
        marked = next(iter(mine.values()))['claims'][order[item['id']]]
        self.assertEqual((marked[0]['index'], marked[0]['mark']), (0, 'ok'))
        self.assertEqual(marked[0]['claim'], {k: v for k, v in item[order[item['id']]][0].items() if not k.startswith('_')})
        result = rounds.anchor(folder)['Kim']
        self.assertEqual(result['claims_marked'][order[item['id']]]['ok'], 1)
        self.assertIsNone(result['claim_agreement_with_judges'])  # the judges' two orders disagreed there: unsure

    def test_context_completes_the_sets_without_moving_marked_claims(self):
        folder = self.root / 'spot-context'
        batch = rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=3, limit=1)
        before = {i['id']: [rounds._ident(c) for c in i['baseline']] for i in batch['items']}
        after = rounds.add_context(folder, self.root / 'baseline', self.root / 'variant', n=3, limit=1)
        for item in after['items']:
            shown = [rounds._ident(c) for c in item['baseline']]
            self.assertEqual(shown[:len(before[item['id']])], before[item['id']])  # earlier positions kept
            self.assertEqual(item['hidden_shared'], 0)
            self.assertTrue((folder / item['page_image']).exists())
            self.assertEqual(set(item['sources']), {'baseline', 'variant'})  # each side's own inputs
        page = rounds.write_spotcheck(folder).read_text()
        self.assertIn('Pump 10 kW', page)  # a text claim's input, from its run's query log

    def test_judges_see_the_whole_page_and_every_claim_grouped(self):
        folder = self.root / 'spot-whole'
        rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=4, limit=1)
        with self.assertRaises(ValueError):  # v6 needs the whole page first
            rounds.judge_pairs(folder, Judge(), 'early', rubric='v6')
        batch = rounds.add_context(folder, self.root / 'baseline', self.root / 'variant', n=4, limit=1)

        class Grouped(Judge):  # shared claims right, A's own wrong, B's own unsure
            def ask(self, prompt, schema, images=(), key=None):
                self.prompts.append(prompt)
                self.images = getattr(self, 'images', []) + [list(images)]
                count = lambda letter: sum(1 for line in prompt.splitlines() if line.startswith(letter) and '. ' in line[:4])
                marks = lambda letter, mark: [{'n': k + 1, 'mark': mark} for k in range(count(letter))]
                return PairVerdict(better='B', s_claims=marks('S', 'ok'), a_claims=marks('A', 'wrong'),
                                   b_claims=marks('B', 'unsure'))
        judge = Grouped()
        rounds.judge_pairs(folder, judge, 'grouped', rubric='v6')
        self.assertTrue(all('CLAIMS IN BOTH SETS' in p and "The whole page's text layer" in p for p in judge.prompts))
        for prompt, images in zip(judge.prompts, judge.images):  # a band: its crop, then the page with it outlined
            self.assertEqual(len(images), 2 if 'The first image shows this part' in prompt else 1)
        self.assertEqual(any(len(i) == 2 for i in judge.images), any(i['band'] for i in batch['items']))
        verdicts = json.loads((folder / 'verdicts' / 'grouped.json').read_text())['verdicts']
        for item in batch['items']:
            shared = {rounds._ident(c) for c in item['baseline']} & {rounds._ident(c) for c in item['variant']}
            for order, v in verdicts[item['id']].items():
                own = {'baseline': 'wrong', 'variant': 'unsure'} if order == 'baseline-first' else \
                      {'variant': 'wrong', 'baseline': 'unsure'}
                for side in ('baseline', 'variant'):
                    self.assertEqual(sorted(m['index'] for m in v['claims'][side]), list(range(len(item[side]))))
                    for m in v['claims'][side]:  # each mark lands on its own claim, at the side's own index
                        claim = item[side][m['index']]
                        self.assertEqual(m['claim'], {k: x for k, x in claim.items() if not k.startswith('_')})
                        self.assertEqual(m['mark'], 'ok' if rounds._ident(claim) in shared else own[side])

    def test_units_show_each_reading_as_its_own_task_gave_it(self):
        from types import SimpleNamespace
        from semantic_pdf_diff.schema import Claim, Evidence, PdfLocator, claim_id
        from semantic_pdf_diff.store import Store
        content = 'sha256:' + 'a' * 64 + '.pdf'
        def reading(entity, attribute, task, region, quote='10 kW'):
            claim = Claim(entity=entity, attribute=attribute, value='10', unit='kW', kind='text', quote=quote,
                          confidence=.9)
            return Evidence(**claim.model_dump(), id=claim_id(content, claim), content=content,
                            locator=PdfLocator(page=1, bbox=(0, 0, 300, 300), region=region, task=task))
        with tempfile.TemporaryDirectory() as d, \
                patch.object(Store, 'files', lambda self, source=None: [SimpleNamespace(content=content)]):
            # A text lever rewords the text reading; the tile's reading of the same fact is untouched.
            # A third run's tile reads the same fact but quotes it differently: that unit has changed.
            for side, words, tile_quote in (('base', ('Pump', 'power'), '10 kW'), ('var', ('Pump P-1', 'power'), '10 kW'),
                                            ('quoted', ('Pump', 'power'), 'Pump P-1 10 kW')):
                with Store(Path(d) / side / 'run1') as store:
                    store.db.execute("INSERT INTO content (id, size) VALUES (?, 1)", (content,))
                    for task, region, (entity, attribute), quote in (('text:p1:0', 'text', words, '10 kW'),
                                                                     ('tile:p1:0', 'tile', ('pump P-1', 'rated power'), tile_quote)):
                        store.record_task({'content': content, 'page': 1, 'task': task, 'status': 'complete', 'claims': 1},
                                          [reading(entity, attribute, task, region, quote)])
                    store.set_reconcile(True)
                    self.assertEqual(len(store.evidence(content)), 1)  # one fact, two readings
            base, var = rounds.collect(Path(d) / 'base'), rounds.collect(Path(d) / 'var')
            visual = ('run1', content, 1, 'visual')
            self.assertEqual(set(base[visual]['claims']), set(var[visual]['claims']))  # unchanged: not a changed unit
            (claim,) = var[visual]['claims'].values()
            self.assertNotEqual(claim['_claim'], next(iter(base[visual]['claims'].values()))['_claim'])  # merged anew
            self.assertEqual(next(iter(var[visual]['claims'].values()))['entity'], 'pump P-1')  # the tile's own words
            text = ('run1', content, 1, 'text')
            self.assertNotEqual(set(base[text]['claims']), set(var[text]['claims']))
            quoted = rounds.collect(Path(d) / 'quoted')
            self.assertNotEqual(set(base[visual]['claims']), set(quoted[visual]['claims']))  # only the quote differs

    def test_every_lever_gets_a_post_mortem(self):
        from semantic_pdf_diff_lab.eval import postmortem
        from semantic_pdf_diff.settings import Settings
        folder = self.root / 'post-mortem'
        rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=8)
        rounds.judge_pairs(folder, Judge(), 'counter')
        (folder / 'decision.json').write_text(json.dumps(rounds.decide(folder)))

        class Analyst:
            s, calls, cache_hits, usage = Settings(), 0, 0, {}
            def ask(self, prompt, schema, images=(), key=None):
                self.prompt = prompt
                return schema(patterns=['wins read the pump rating'], tweaks=['keep it'], partitions=[], next=[])
        analyst = Analyst()
        evidence = postmortem.write(folder, client=analyst, units=2)
        self.assertEqual(evidence['reading']['patterns'], ['wins read the pump rating'])
        self.assertIn('kind of region', evidence['partitions'])
        self.assertEqual(set(evidence['samples']), {'won', 'lost', 'split'})
        self.assertTrue(all(len(v) <= 2 for v in evidence['samples'].values()))
        self.assertIn('"partitions"', analyst.prompt)
        self.assertTrue((folder / 'postmortem.html').exists())

        class Broken(Analyst):
            def ask(self, prompt, schema, images=(), key=None):
                raise RuntimeError('no answer')
        again = postmortem.write(folder, client=Broken())  # the evidence stands without the reading
        self.assertIn('no answer', again['reading_failed'])

    def test_gains_are_measured_against_the_baseline(self):
        measured = rounds.gains(self.root / 'baseline', self.root / 'variant')
        base = rounds.mechanical(self.root / 'baseline')['all']['distinct_claims']
        var = rounds.mechanical(self.root / 'variant')['all']['distinct_claims']
        self.assertAlmostEqual(measured['claims'], round((var - base) / base, 4))
        self.assertIsNone(measured['tokens'])  # no fixture: tokens can't be measured

    def test_batches_record_their_checks(self):
        folder = self.root / 'checked-batch'
        batch = rounds.build_batch(self.root / 'baseline', self.root / 'variant', folder, n=6, limit=1,
                                   documents={'nothing': 'reports'})
        checks = batch['units']['checks']
        self.assertEqual((checks['asymmetric_units'], checks['foreign_readings']), (0, 0))
        self.assertIsNone(checks['scope'])  # no settings.json beside these runs: scope unknown, not checked
        self.assertEqual(checks['without_family'], ['run1'])  # the run isn't a known slice
        self.assertGreaterEqual(checks['hidden_unique_claims'], 0)

    def test_bands_do_not_depend_on_which_side_is_the_baseline(self):
        claim = lambda y, task='tile:p1:0': {'_box': [0, y, 100, y + 10], '_task': task}
        # 30 claims each, 20 shared; three shared ones were read at different heights by each side.
        a = {('r', 'c', 1, 'visual'): {'claims': {f's{i}': claim(10 * i) for i in range(20)}
                                       | {f'a{i}': claim(300 + 10 * i) for i in range(10)}, 'tasks': 1}}
        b = {('r', 'c', 1, 'visual'): {'claims': {f's{i}': claim(10 * i + (97 if i < 3 else 0)) for i in range(20)}
                                       | {f'b{i}': claim(300 + 10 * i) for i in range(10)}, 'tasks': 1}}
        one, two = rounds.split_units(a, b, limit=10)
        three, four = rounds.split_units(b, a, limit=10)
        self.assertEqual((set(one), set(two)), (set(four), set(three)))
        self.assertGreater(len(one), 1)  # cut into bands

    def test_intervals_and_rules(self):
        mean, low, high = rounds.interval([1.0] * 40 + [0.0] * 10)
        self.assertAlmostEqual(mean, 0.8)
        self.assertTrue(0.65 < low < 0.8 < high < 0.92)
        self.assertIsNone(rounds.interval([]))
        self.assertEqual(rounds.interval([1.0, 0.0], clusters=['r', 'r']), (0.5, 0.0, 1.0))  # one region: no information
        self.assertAlmostEqual(rounds._t_quantile(0.90, 10), 1.812, places=3)
        # Bands of one region move together: counted as one, the interval widens.
        values = [1.0] * 24 + [0.0] * 8
        regions = [f'u-r-p{i // 4}-table' for i in range(32)]  # 8 regions of 4 bands, all alike within
        _, low, high = rounds.interval(values)
        _, clustered_low, clustered_high = rounds.interval(values, clusters=regions)
        self.assertLess(clustered_low, low - 0.08)
        self.assertGreater(clustered_high, high)
        self.assertEqual(rounds.region('u-habex-52da8af4-p4-table-b2of4'), 'u-habex-52da8af4-p4-table')

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

    def test_variants_by_kind_stay_apart(self):
        """Two variants of one round were drawn as one unlabelled point per kind (code review 2026-10-01, item 14)."""
        from semantic_pdf_diff import ledger
        with tempfile.TemporaryDirectory() as d:
            history = Path(d) / 'history.jsonl'
            for variant, win in (('locator', 0.7), ('reconcile', 0.3)):
                for stratum in ('text', 'table'):
                    ledger.figure(history, metric='win_rate', value={'mean': win, 'low': win - 0.1, 'high': win + 0.1},
                                  round='r06', variant=variant, stratum=stratum)
            page = rounds.report(history, Path(d) / 'report.html').read_text()
            for variant in ('locator', 'reconcile'):
                for stratum in ('text', 'table'):
                    self.assertIn(f'<title>r06 {variant} {stratum}</title>', page)

if __name__ == '__main__':
    unittest.main()
