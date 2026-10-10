"""The comparison's vetoes (compare.vetoes): numeric arithmetic and uncertain provenance make a confident judgment
uncertain. They were reachable only through compare() (code review 2026-10-08: a test gap); test_sources checks one
through it."""
import stubs  # noqa: F401 (a clean environment)
import unittest
from types import SimpleNamespace

from semantic_pdf_diff.compare import vetoes
from semantic_pdf_diff.schema import Judgment

def claim(confidence=0.9, approximate=False):
    return SimpleNamespace(confidence=confidence, approximate=approximate)

def judged(relation, confidence=0.9, same_conditions=True):
    return Judgment(relation=relation, rationale="stub", confidence=confidence, same_conditions=same_conditions)

EQUAL, UNEQUAL = {"equal": True}, {"equal": False}

class Vetoes(unittest.TestCase):
    def test_a_confident_judgment_with_matching_conditions_stands(self):
        for relation, calc in (("equivalent", EQUAL), ("different", UNEQUAL), ("complementary", None),
                               ("unrelated", None)):
            with self.subTest(relation):
                self.assertEqual(vetoes(judged(relation), claim(), claim(), calc), [])

    def test_each_rule(self):
        cases = [
            ("conditions not established", judged("different", same_conditions=False), claim(), claim(), None,
             ["Matching conditions were not established"]),
            ("arithmetic against equivalence", judged("equivalent"), claim(), claim(), UNEQUAL,
             ["Numeric conversion disagrees with equivalence"]),
            ("arithmetic against a difference", judged("different"), claim(), claim(), EQUAL,
             ["Numeric values are equal after conversion; review semantic difference"]),
            ("a reading's low confidence", judged("complementary"), claim(confidence=0.6), claim(), None,
             ["Low model confidence (uncalibrated)"]),
            ("the judge's low confidence", judged("equivalent", confidence=0.5), claim(), claim(), EQUAL,
             ["Low model confidence (uncalibrated)"]),
            ("an approximate value", judged("equivalent"), claim(), claim(approximate=True), EQUAL,
             ["Approximate visual value requires review"]),
        ]
        for name, judgment, a, b, calc, reasons in cases:
            with self.subTest(name):
                self.assertEqual(vetoes(judgment, a, b, calc), reasons)

    def test_where_rules_dont_apply(self):
        # conditions and approximation matter only to an equivalence or a difference; confidence not to "unrelated"
        self.assertEqual(vetoes(judged("complementary", same_conditions=False), claim(), claim(approximate=True), None),
                         [])
        self.assertEqual(vetoes(judged("unrelated", confidence=0.1), claim(confidence=0.1), claim(), None), [])

    def test_reasons_add_up_in_order(self):
        reasons = vetoes(judged("equivalent", confidence=0.5, same_conditions=False), claim(approximate=True), claim(),
                         UNEQUAL)
        self.assertEqual(reasons, ["Matching conditions were not established",
                                   "Numeric conversion disagrees with equivalence",
                                   "Low model confidence (uncalibrated)", "Approximate visual value requires review"])

if __name__ == "__main__":
    unittest.main()
