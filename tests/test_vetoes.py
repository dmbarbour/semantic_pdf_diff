"""The comparison's vetoes (compare.vetoes): numeric arithmetic and uncertain provenance make a confident judgment
uncertain. They were reachable only through compare() (code review 2026-10-08: a test gap); test_sources checks one
through it."""
import stubs  # noqa: F401 (a clean environment)
import unittest
from types import SimpleNamespace

from semantic_pdf_diff.compare import vetoes
from semantic_pdf_diff.schema import Judgment

def claim(confidence=0.9, approximate=False, kind="chart"):
    return SimpleNamespace(confidence=confidence, approximate=approximate, kind=kind, image=None)

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

    def test_only_a_value_read_off_a_picture_is_approximate_enough_to_veto(self):
        # "Preliminary estimates put the number of beams at 23", then 19: stated, not read off a chart
        stated = claim(approximate=True, kind="text")
        self.assertEqual(vetoes(judged("different"), stated, claim(kind="text"), UNEQUAL), [])
        cropped = SimpleNamespace(confidence=0.9, approximate=True, kind="table", image="crop.png")  # a tile's reading
        self.assertEqual(vetoes(judged("different"), cropped, claim(), UNEQUAL),
                         ["Approximate visual value requires review"])

    def test_reasons_add_up_in_order(self):
        reasons = vetoes(judged("equivalent", confidence=0.5, same_conditions=False), claim(approximate=True), claim(),
                         UNEQUAL)
        self.assertEqual(reasons, ["Matching conditions were not established",
                                   "Numeric conversion disagrees with equivalence",
                                   "Low model confidence (uncalibrated)", "Approximate visual value requires review"])

if __name__ == "__main__":
    unittest.main()

class SharedAnswers(unittest.TestCase):
    def test_a_judgment_shared_by_two_pairs_is_vetoed_once_in_each(self):
        """One note in two files of a source asks the same query twice; the second waited on the first and was given
        its answer, which the first's veto had changed: its reason prepended twice (the determinism review, D4)."""
        import tempfile
        from pathlib import Path
        from semantic_pdf_diff.compare import compare
        from semantic_pdf_diff.llm import build_request
        from semantic_pdf_diff.schema import Evidence, PdfLocator, claim_id
        from semantic_pdf_diff.settings import Settings

        def note(content):
            e = Evidence(id="x", content=content, entity="Pump P-1", attribute="capacity", value="100", unit="gpm",
                         kind="text", quote="Pump P-1 capacity 100 gpm", confidence=0.6,
                         locator=PdfLocator(page=1, bbox=(0, 0, 100, 20), region="text", task="text:p1:0"))
            return e.model_copy(update={"id": claim_id(content, e)})

        class Cached:  # every answer at hand: the judge is unsure
            def __init__(self):
                self.s = Settings(concurrency=4)
            def prepare(self, prompt, schema, images, key):
                return build_request(self.s, prompt, schema, images, key)
            def cached(self, request):
                return Judgment(relation="equivalent", rationale="same value", confidence=0.95, same_conditions=True)
            def send(self, request):
                raise AssertionError("asked the model")
            def save(self, request, value):
                pass

        left = [note("sha256:" + "a" * 64 + ".pdf"), note("sha256:" + "b" * 64 + ".pdf")]
        right = [note("sha256:" + "c" * 64 + ".pdf")]
        for seed in (1, 2, 3):
            with stubs.answers_shuffled(seed), tempfile.TemporaryDirectory() as d, self.subTest(seed=seed):
                found = compare(left, right, Path(d), Cached(), "proposals")["findings"]
                self.assertEqual([f["rationale"] for f in found],
                                 ["Low model confidence (uncalibrated). same value"] * 2)
