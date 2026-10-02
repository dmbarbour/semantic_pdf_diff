"""Decision rules simulated under the null, and with real effects (the meta-audit: rules that were
never simulated let early stopping and multiplicity through). Seeded, so the rates are fixed; the
bounds leave a little room, and a change that weakens a rule fails here.

The null model is round 9's A/A control: a variant that re-asks the baseline's image queries and
changes nothing else. Its 32 unit scores, symmetrised: judges mostly pick a side even when there's
nothing to choose. Units sit in 27 regions, 5 cut into two bands whose scores often agree.
"""
import stubs  # noqa: F401 (a clean environment)
import collections
import random
import unittest
from semantic_pdf_diff_lab.eval import rounds
from semantic_pdf_diff_lab.eval.models import Criteria

NULL = [(0.0, 10), (0.125, 0.5), (0.25, 1), (0.375, 0.5), (0.5, 8), (0.625, 0.5), (0.75, 1), (0.875, 0.5), (1.0, 10)]
VALUES, WEIGHTS = zip(*NULL)

def simulated(rng, effect=0.0, regions=27, banded=5):
    """One variant's (scores, family, document, units): each unit a null draw, or with probability
    `effect` a clear win for the variant (true win rate 0.5 + effect / 2)."""
    scores, family, document = {}, {}, {}
    draw = lambda: 1.0 if rng.random() < effect else rng.choices(VALUES, WEIGHTS)[0]
    for r in range(regions):
        kind, doc = ("text", "table", "visual")[r % 3], ("reports", "drawings", "manuals", "rules")[r % 4]
        first, bands = draw(), 2 if r < banded else 1
        for b in range(bands):
            unit = f"u-run-p{r}-{kind}" + (f"-b{b}of{bands}" if bands > 1 else "")
            scores[unit] = first if b == 0 or rng.random() < 0.5 else draw()
            family[unit], document[unit] = kind, doc
    return scores, family, document, {"units": 60, "unchanged": 28, "changed_by_kind": {"text": 10, "table": 10, "visual": 12}}

def rates(rounds_run, effect=0.0, criteria=None, variants=1, gains=None, held_out=None, seed=1):
    """Shares over simulated rounds: variants accepted, "no worse" calls, rounds with any variant
    accepted, and rounds promoting one (accepted, then passing a held-out round under `held_out`)."""
    rng, counts = random.Random(seed), collections.Counter()
    for _ in range(rounds_run):
        results = [rounds.decide_scores(*simulated(rng, effect), criteria, gains) for _ in range(variants)]
        accepted = [r for r in results if r["accepted"]]
        counts["accepted"] += len(accepted)
        counts["no worse"] += sum(r["decision"].startswith(("no worse", "accepted: no worse")) for r in results)
        counts["any"] += bool(accepted)
        if held_out is not None:
            counts["promoted"] += any(rounds.decide_scores(*simulated(rng, effect), held_out)["accepted"] for _ in accepted)
    per_variant = rounds_run * variants
    return {"accepted": counts["accepted"] / per_variant, "no worse": counts["no worse"] / per_variant,
            "any": counts["any"] / rounds_run, "promoted": counts["promoted"] / rounds_run}

class UnderTheNull(unittest.TestCase):
    def test_a_lever_with_no_effect_is_rarely_accepted(self):
        r = rates(1000)
        self.assertLessEqual(r["accepted"], 0.08)  # 5.8%: the 90% interval's one-sided 5%, and a little more
        self.assertGreater(r["no worse"], 0.05)    # about one null lever in nine lands on "no worse"...

    def test_no_worse_is_accepted_only_with_its_named_gain(self):
        without = rates(1000)
        met = rates(1000, criteria=Criteria(gain={"metric": "tokens", "change": -0.10}), gains={"tokens": -0.20})
        missed = rates(1000, criteria=Criteria(gain={"metric": "tokens", "change": -0.10}), gains={"tokens": -0.05})
        self.assertAlmostEqual(missed["accepted"], without["accepted"])  # ...and isn't accepted without the gain
        self.assertAlmostEqual(met["accepted"], without["accepted"] + without["no worse"], places=6)

    def test_several_variants_raise_the_chance_of_a_false_win(self):
        r = rates(400, variants=5, held_out=Criteria(role="held-out"))
        self.assertTrue(0.15 <= r["any"] <= 0.35, r)  # about one round in four accepts a lever with no effect
        # The default held-out rule (the owner's choice: mean above 0.5, lower bound at least 0.45, no stratum
        # loss) promotes one in about twenty...
        self.assertLessEqual(r["promoted"], 0.07)
        # ...the owner's first example (the mean alone) about one in eight...
        loose = rates(400, variants=5, held_out=Criteria(role="held-out", held_out_low=0.0))
        self.assertLessEqual(loose["promoted"], 0.18)
        self.assertGreater(loose["promoted"], r["promoted"])
        # ...and requiring the held-out round to win again, about one in seventy.
        stricter = rates(400, variants=5, held_out=Criteria(role="combination"))
        self.assertLessEqual(stricter["promoted"], 0.04)

class WithARealEffect(unittest.TestCase):
    def test_a_clear_effect_is_usually_found(self):
        self.assertGreaterEqual(rates(400, effect=0.4)["accepted"], 0.65)  # true rate 0.70: found about 78% of the time
        self.assertLessEqual(rates(400, effect=0.2)["accepted"], 0.5)      # true rate 0.60: missed more often than found

class RoundSpecs(unittest.TestCase):
    def test_every_committed_round_validates_and_typos_fail(self):
        import json
        from pathlib import Path
        from pydantic import ValidationError
        from semantic_pdf_diff_lab.eval.models import RoundSpec
        specs = sorted(Path(__file__).resolve().parent.parent.glob('benchmarks/rounds/*/round.json'))
        self.assertGreater(len(specs), 10)
        for path in specs:
            with self.subTest(round=path.parent.name):
                spec = RoundSpec.model_validate_json(path.read_text())
                self.assertEqual(spec.criteria.role, 'development')  # the default, for rounds before criteria
        good = {'name': 'r', 'baseline': 'b.json', 'variants': {'v': 'v.json'}}
        for bad in ({'rubirc': 'v6'}, {'rubric': 'v9'}, {'criteria': {'role': 'dev'}}, {'units': 0}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                RoundSpec.model_validate({**good, **bad})

    def test_criteria_are_locked_when_judging_starts(self):
        state = {}
        first = {'role': 'development', 'win_low': 0.5}
        rounds.lock_criteria(state, first)
        rounds.lock_criteria(state, dict(first))  # the same: fine
        with self.assertRaisesRegex(ValueError, 'win_low'):
            rounds.lock_criteria(state, {**first, 'win_low': 0.45})

    def test_a_held_out_round_asks_only_that_the_change_holds(self):
        rng = random.Random(3)
        args = simulated(rng, effect=0.2)
        held = rounds.decide_scores(*args, Criteria(role='held-out'))
        developed = rounds.decide_scores(*args)
        mean = held['overall']['mean']
        self.assertEqual(held['accepted'], mean > 0.5 and held['overall']['low'] >= 0.45
                         and not held['decision'].startswith('rejected: loses in'))
        self.assertEqual(held['role'], 'held-out')
        self.assertEqual(developed['overall'], held['overall'])  # the same measurement, another rule

if __name__ == '__main__':
    unittest.main()
