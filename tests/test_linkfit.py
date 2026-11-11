"""The lab's measures of a ranking of pairs (measures.average_precision, log_loss; comparison._ranking): evidence
combined numerically, milestone 2. A combiner is judged by how it ranks and how well its probabilities are
calibrated, not by counts moved across a level."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff import indexes
from semantic_pdf_diff_lab.bench.controlled import comparison, measures
from test_indexes import report
from test_links import A, B

class Measures(unittest.TestCase):
    def test_average_precision_counts_ties_together(self):
        # 3 matches; at 3: 1 of 1 right; at 2: 2 of 3; at 0: 3 of 5
        self.assertEqual(measures.average_precision([(3, True), (2, True), (2, False), (0, False), (0, True)]),
                         round(1 / 3 + (1 / 3) * (2 / 3) + (1 / 3) * (3 / 5), 4))
        self.assertEqual(measures.average_precision([(2, False), (2, True)]),
                         measures.average_precision([(2, True), (2, False)]))  # whatever order ties come in
        self.assertIsNone(measures.average_precision([(1, False)]))

    def test_log_loss_keeps_probabilities_off_0_and_1(self):
        self.assertAlmostEqual(measures.log_loss([(0.5, True), (0.5, False)]), 0.6931, places=4)
        self.assertLess(measures.log_loss([(1.0, False)]), 7.0)  # pinned at 1 and wrong: finite

class Ranking(unittest.TestCase):
    def test_todays_levels_as_the_null_arm(self):
        data = report(A + B, [], ("a", "b"), mode="proposals")
        data["index"] = indexes.built(data)
        items = {"Harrow Creek Water Treatment Plant": "plant", "Pine Ridge Water Treatment Plant": "plant",
                 "Alum": "coagulant", "ferric sulfate": "coagulant", "Room 104": "room 104",
                 "Room 105": "room 105", "backwash pump": "backwash pump"}
        entity = {e["id"]: e["entity"] for e in data["evidence"]}

        def most(claims):
            return {items[entity[c]] for c in claims}

        def read(x, y):
            return "unscorable" if not x or not y else "right" if x & y else "wrong"
        ranked = comparison._ranking(data, data["index"]["subjects"], ["a", "b"], most, read)["ranking"]
        # the plants plausible (right), the rooms plausible (wrong: 104 isn't 105), alum and ferric sulfate possible
        self.assertEqual((ranked["pairs"], ranked["matches"]), (3, 2))
        self.assertEqual(ranked["average_precision"], round((1 / 2) * (1 / 2) + (1 / 2) * (2 / 3), 4))
        self.assertEqual(ranked["precision"], {"plausible": 0.5, "possible": round(2 / 3, 4)})
        self.assertNotIn("log_loss", ranked)  # no probabilities given

if __name__ == "__main__":
    unittest.main()
