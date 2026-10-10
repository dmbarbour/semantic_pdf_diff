"""Judgement records: verdict files read as records, failures kept per verdicts folder, raters."""
import stubs  # noqa: F401 (a clean environment)
import json
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff_lab.eval import judgements, raters, rounds
from semantic_pdf_diff.failures import ModelFailure
from semantic_pdf_diff_lab.eval.models import PairVerdict
from test_judge_prompts import ITEMS

class Judge:
    """Prefers B and marks every claim of set A wrong, B's right; fails on the units in `failing`."""
    def __init__(self, failing=()):
        self.failing, self.asked = set(failing), []
    def ask(self, prompt, schema, images=(), key=None):
        self.asked.append(key)
        if key[1] in self.failing:
            raise ModelFailure("timed out")
        count = lambda letter: sum(1 for line in prompt.splitlines() if line.startswith(letter) and '. ' in line[:4])
        return PairVerdict(better="B", note="stub", a_claims=[{"n": k + 1, "mark": "wrong"} for k in range(count("A"))],
                           b_claims=[{"n": k + 1, "mark": "ok"} for k in range(count("B"))])

class Records(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.folder = Path(self.dir.name)
        (self.folder / "pairs.json").write_text(json.dumps({"items": ITEMS}))

    def test_verdicts_marks_and_failures_are_records(self):
        text, table = ITEMS[0]["id"], ITEMS[1]["id"]
        rounds.judge_pairs(self.folder, Judge(failing={table}), "judge-a", rubric="v5")
        records = judgements.read(self.folder)
        pairs = [r for r in records if r.question == "pair" and r.status == "answered"]
        self.assertEqual({(r.unit, r.order) for r in pairs}, {(text, "baseline-first"), (text, "variant-first")})
        self.assertEqual({r.answer["score"] for r in pairs}, {0.0, 1.0})  # B is the variant, then the baseline
        failed = [r for r in records if r.status == "failed"]
        self.assertEqual({(r.unit, r.attempts, r.rater) for r in failed}, {(table, 1, "judge-a")})
        claims = judgements.answered(records, "claim")
        shown = len(ITEMS[0]["baseline"]) + len(ITEMS[0]["variant"])
        self.assertEqual(len(claims), 2 * shown)  # every claim, in each order
        first = {(r.side, r.answer["mark"]) for r in claims if r.order == "baseline-first"}
        self.assertEqual(first, {("baseline", "wrong"), ("variant", "ok")})
        self.assertTrue(all(r.kind == "model" for r in records))

    def test_the_ask_again_rule(self):
        self.assertTrue(judgements.ask_again(0))
        self.assertFalse(judgements.ask_again(1))
        self.assertTrue(judgements.ask_again(1, retry_failed=True))
        self.assertFalse(judgements.ask_again(judgements.MAX_ATTEMPTS, retry_failed=True))

    def test_failures_under_one_rubric_dont_block_another(self):
        table = ITEMS[1]["id"]
        judge = Judge(failing={table})
        rounds.judge_pairs(self.folder, judge, "judge-a", rubric="v4")
        rounds.judge_pairs(self.folder, judge, "judge-a", rubric="v4", retry_failed=True)  # failed twice: done asking
        judge.failing = set()
        judge.asked = []
        rounds.judge_pairs(self.folder, judge, "judge-a", rubric="v4", retry_failed=True)
        self.assertEqual(judge.asked, [])
        rounds.judge_pairs(self.folder, judge, "judge-a", rubric="v6", verdicts_dir="verdicts-v6")
        self.assertIn(("judge", table, "v6", "baseline-first"), judge.asked)  # asked afresh under v6
        self.assertEqual(json.loads((self.folder / "failures" / "judge-a.json").read_text())[f"{table}|baseline-first"], 2)
        self.assertEqual({r.status for r in judgements.read(self.folder, "verdicts-v6")}, {"answered"})

    def test_the_quote_check_rates_every_claim(self):
        folder = self.folder
        items = json.loads(json.dumps(ITEMS))
        items[0]["baseline"][0]["quote"] = "Pump P-1 10 kW"      # on the page
        items[0]["variant"][0]["quote"] = "Pump P-1 12 kW"       # not
        (folder / "pairs.json").write_text(json.dumps({"items": items}))
        records = raters.QuoteCheck().rate(folder)
        self.assertEqual(len(records), sum(len(i["baseline"]) + len(i["variant"]) for i in items))
        found = {(r.unit, r.side, r.index): r.answer["found"] for r in records}
        self.assertTrue(found[(items[0]["id"], "baseline", 0)])
        self.assertFalse(found[(items[0]["id"], "variant", 0)])
        self.assertTrue(all(r.kind == "check" and r.question == "quote" for r in records))

class OneScore(unittest.TestCase):
    """A unit's score has one definition (code review 2026-10-01, item 11): the analysis once averaged
    every verdict flat, so a unit the decision scored 1.0 showed as 0.667 and was sampled as split."""
    def test_the_decision_and_the_analysis_agree(self):
        from semantic_pdf_diff_lab.eval import insights
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            items = [dict(i, baseline=[], variant=[], run="r", content="sha256:" + "a" * 64, page=1, image="x.jpg")
                     for i in ITEMS[:2]]
            (folder / "pairs.json").write_text(json.dumps({"items": items, "baseline": d, "variant": d}))
            (folder / "verdicts").mkdir()
            one, two = items[0]["id"], items[1]["id"]
            both = {"baseline-first": {"score": 1.0}, "variant-first": {"score": 1.0}}
            (folder / "verdicts" / "j1.json").write_text(json.dumps({"reviewer": "j1", "verdicts": {one: both}}))
            (folder / "verdicts" / "j2.json").write_text(json.dumps({"reviewer": "j2", "verdicts": {
                one: {"variant-first": {"score": 0.0}}, two: {"baseline-first": {"score": 0.0}}}}))  # one order each
            self.assertEqual(rounds.unit_scores(folder), {one: 1.0})
            analysis = insights.analyse(folder)
            self.assertEqual({u["id"]: u["score"] for u in analysis["units"]}, {one: 1.0})  # not 0.667; two unscored
            self.assertEqual(analysis["summary"]["split"], [])
            self.assertEqual(rounds.unsettled(folder, ["j1"]), {two})  # j1 never saw it
            self.assertEqual(rounds.unsettled(folder, ["j2"]), {one, two})  # an order each failed

    def test_flips_and_disagreements(self):
        flip = {"baseline-first": {"score": 1.0}, "variant-first": {"score": 0.0}}
        tie = {"baseline-first": {"score": 0.5}, "variant-first": {"score": 1.0}}
        lose = {"baseline-first": {"score": 0.0}, "variant-first": {"score": 0.0}}
        records = [judgements.Record(rater, "model", "pair", unit, order=o, answer=v)
                   for rater, verdicts in (("j1", {"u1": flip, "u2": tie}), ("j2", {"u2": lose}))
                   for unit, orders in verdicts.items() for o, v in orders.items()]
        v = judgements.UnitVerdicts(records)
        self.assertEqual((v.score("u1"), v.flipped("u1"), v.split("u1")), (0.5, ["j1"], True))
        self.assertEqual((v.score("u2"), v.flipped("u2"), v.disagree("u2")), (0.375, [], True))  # 0.75 against 0.0
        self.assertIsNone(v.score("u3"))

class Files(unittest.TestCase):
    """Judgement files carry their rubric, and one loop rates for every model rater (code review 2026-10-01, A1)."""
    def test_a_file_judged_under_one_rubric_refuses_another(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "pairs.json").write_text(json.dumps({"items": ITEMS}))
            target, _, _ = rounds.judge_pairs(folder, Judge(), "judge-a", rubric="v5")
            self.assertEqual(json.loads(target.read_text())["rubric"], "v5")
            self.assertEqual({r.rubric for r in judgements.read(folder)}, {"v5"})
            with self.assertRaisesRegex(judgements.JudgementError, "judged under rubric v5, not v6"):
                rounds.judge_pairs(folder, Judge(), "judge-a", rubric="v6")
            other = folder / "verdicts" / "judge-b.json"
            judgements.save(other, "judge-b", {ITEMS[0]["id"]: {"baseline-first": {"score": 1.0}}}, "v4")
            with self.assertRaisesRegex(judgements.JudgementError, "more than one rubric"):
                judgements.UnitVerdicts.read(folder)

    def test_one_loop_rates_and_keeps_failures_apart(self):
        from semantic_pdf_diff_lab.eval.models import PairVerdict
        answers, errors = judgements.rate(Judge(failing={"u2"}), [
            ("one", "A1. x\nB1. y", PairVerdict, [], ("judge", "u1")),
            ("two", "A1. x", PairVerdict, [], ("judge", "u2"))])
        self.assertEqual((list(answers), errors), (["one"], {"two": "timed out"}))

class Raters(unittest.TestCase):
    def test_a_model_judge_rates_and_keeps_its_errors(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "pairs.json").write_text(json.dumps({"items": ITEMS}))
            client = Judge(failing={ITEMS[1]["id"]})
            judge = raters.ModelJudge(client, "judge-a", rubric="v4")
            records = judge.rate(folder)
            self.assertEqual(len(judge.errors), 2)  # both orders of the failing unit
            self.assertEqual({r.status for r in records}, {"answered", "failed"})
            self.assertEqual(rounds.unit_scores(folder), {ITEMS[0]["id"]: 0.5})  # B in both orders: bias cancels

if __name__ == "__main__":
    unittest.main()
