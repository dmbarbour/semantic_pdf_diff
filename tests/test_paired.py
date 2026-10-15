"""Arms compared document by document (lab bench/paired.py; docs/samples-and-testing.md, "Judging a lever"): the
sign-flip test and interval, the verdicts against base and null arms, its false alarms under no effect, and the
scorer's facts found per fact."""
import random
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from stubs import needs_lab

needs_lab()
from semantic_pdf_diff_lab.bench import controlled, paired  # noqa: E402

def arm(*counts, measure="facts right"):
    """An arm of documents d0, d1... with one measure's counts (no facts listed)."""
    return {f"d{i}": ({measure: n}, {}) for i, n in enumerate(counts)}

class SignFlip(unittest.TestCase):
    def test_no_change_is_no_evidence(self):
        self.assertEqual(paired.sign_flip([0, 0, 0]), 1.0)
        self.assertEqual(paired.sign_flip([]), 1.0)

    def test_every_document_one_way_is_exact(self):
        self.assertEqual(paired.sign_flip([1] * 10), 2 / 2 ** 10)  # all plus or all minus

    def test_changes_that_cancel_are_no_evidence(self):
        self.assertEqual(paired.sign_flip([3, -3, 2, -2]), 1.0)

    def test_many_documents_are_drawn_and_seeded(self):
        changes = [1, -1, 2, 1, 1, 3, -1, 1, 1, 2, 1, -2, 1, 1, 2, 1, 1, 1, -1, 2]
        self.assertGreater(len([c for c in changes if c]), paired.EXACT)
        p = paired.sign_flip(changes)
        self.assertEqual(p, paired.sign_flip(changes))  # the same draws every time
        self.assertLess(p, 0.05)

    def test_the_interval_holds_the_sum_and_is_seeded(self):
        changes = [2, -1, 0, 3, 1, 0, -2, 4]
        low, high = paired.interval(changes)
        self.assertLessEqual(low, sum(changes))
        self.assertGreaterEqual(high, sum(changes))
        self.assertEqual((low, high), paired.interval(changes))

class Verdicts(unittest.TestCase):
    def test_a_measure_better_on_most_documents_is_better(self):
        c = paired.compare(arm(*[5] * 12), arm(*[6] * 11, 5), "facts right")
        self.assertEqual((c["change"], c["moved"], c["verdict"]), (11, 11, "better"))

    def test_fewer_errors_are_better(self):
        c = paired.compare(arm(*[3] * 12, measure="relations reversed"),
                           arm(*[1] * 12, measure="relations reversed"), "relations reversed")
        self.assertEqual(c["verdict"], "better")

    def test_a_measure_with_no_better_direction_has_no_verdict(self):
        c = paired.compare(arm(*[3] * 12, measure="relations unscored"),
                           arm(*[1] * 12, measure="relations unscored"), "relations unscored")
        self.assertIsNone(c["verdict"])

    def test_facts_gained_and_lost_are_counted_by_fact(self):
        before = {"d": ({"facts right": 2}, {"a": "right", "b": "right", "c": "loose"})}
        after = {"d": ({"facts right": 2}, {"a": "right", "c": "right"})}
        c = paired.compare(before, after, "facts right")
        self.assertEqual((c["change"], c["gained"], c["lost"]), (0, 1, 1))

    def test_a_lever_no_better_than_a_null_arm_is_no_different(self):
        base, lever, null = arm(*[5] * 12), arm(*[7] * 12), arm(*[7] * 11, 6)
        result = paired.judge(lever, base, [null])
        self.assertEqual(result["against base"]["verdict"], "better")
        self.assertEqual(result["nulls against base"][0]["verdict"], "better")  # the rewording alone moved it
        self.assertEqual(result["verdict"], "no different")

    def test_a_lever_better_than_base_and_every_null_is_better(self):
        base, null = arm(*[5] * 12), arm(*[5] * 6, *[6] * 6)
        self.assertEqual(paired.judge(arm(*[8] * 12), base, [null])["verdict"], "better")

    def test_a_guard_made_worse_vetoes(self):
        base = {f"d{i}": ({"facts right": 5, "relations reversed": 3}, {}) for i in range(12)}
        lever = {f"d{i}": ({"facts right": 4, "relations reversed": 0}, {}) for i in range(12)}
        self.assertEqual(paired.judge(lever, base, target="relations reversed")["verdict"], "worse")

    def test_documents_only_one_arm_read_are_left_out(self):
        c = paired.compare(arm(5, 5), arm(5, 5, 9), "facts right")
        self.assertEqual((c["documents"], c["change"]), (2, 0))

class FalseAlarms(unittest.TestCase):
    def test_churn_with_no_effect_is_rarely_called_a_change(self):
        """Arms of 80 documents whose facts move both ways at random, as a rewording moves them: called "better"
        or "worse" in about LEVEL of trials, not more."""
        rng = random.Random(7)
        alarms, trials = 0, 200
        with mock.patch.object(paired, "DRAWS", 999), mock.patch.object(paired, "RESAMPLES", 100):
            for _ in range(trials):
                before = arm(*[20] * 80)
                after = arm(*[20 + rng.choice((-2, -1, 0, 0, 0, 0, 1, 2)) for _ in range(80)])
                alarms += paired.compare(before, after, "facts right")["verdict"] is not None
        self.assertLess(alarms / trials, paired.LEVEL + 0.05)

class Scorer(unittest.TestCase):
    def test_facts_found_name_each_fact_and_how(self):
        project = controlled.water_treatment(1)
        _, log = controlled.render(project)
        key = controlled.key(project, log)
        a, b, c = [f for f in project.facts if f.role == "fact"][:3]
        claims = [{"entity": f.entity, "attribute": f.attribute, "value": f"{f.value}", "unit": f.unit,
                   "conditions": f.conditions} for f in (a, b)]
        found = controlled.facts_found(key, claims)
        self.assertEqual(found, {a.id: "right", b.id: "right"})
        measures, facts = paired.measures(key, claims)
        self.assertEqual((measures["facts right"], measures["claims right"], facts), (2, 2, found))

    def test_context_is_kept_in_its_place_or_by_a_record(self):
        project = controlled.water_treatment(1)
        _, log = controlled.render(project)
        key = controlled.key(project, log)
        a = next(f for f in project.facts if f.role == "fact")
        entry = next(f for f in key["facts"] if f["id"] == a.id)
        entry["context"] = {**(entry.get("context") or {}), "frame": "measured at the plant inlet",
                            "scope": "during the winter season"}
        claim = {"id": "e1", "entity": a.entity, "attribute": a.attribute, "value": f"{a.value}", "unit": a.unit,
                 "conditions": "winter season"}
        by_field, _ = paired.measures(key, [{**claim, "frame": "at the plant inlet"}])
        by_record, _ = paired.measures(key, [claim], {"e1": "NOTES: all readings measured at the plant inlet."})
        lost, _ = paired.measures(key, [claim])
        self.assertEqual([(m["scope kept"], m["frame kept"], m["frame in its field"]) for m in (by_field, by_record,
                                                                                                    lost)],
                         [(1, 1, 1), (1, 1, 0), (1, 0, 0)])

    def test_an_arm_is_read_from_its_runs_stores(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(paired.arm(Path(d), Path(d)), {})
            self.assertEqual(paired.key_of("c", "spec-s1.docx"), Path("c/docs-docx/spec-s1.key.json"))
            self.assertEqual(paired.key_of("c", "spec-s1"), Path("c/docs/spec-s1.key.json"))
