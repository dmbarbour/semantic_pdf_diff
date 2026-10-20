"""Topics for browsing a report (topics.py; docs/plans/portable-reports-2026-10-19.md, milestone 3): claims split
by the words of what they're about, found on both sides, into about even topics."""
import stubs  # noqa: F401 (a clean environment)
import random
import unittest
from semantic_pdf_diff import topics

def claim(entity, attribute):
    return {"entity": entity, "attribute": attribute}

def plant():
    """Two sides' claims about pumps, valves and tanks, with a word one side alone uses."""
    claims, sides = [], []
    for side in ("A", "B"):
        for i in range(12):
            claims += [claim(f"pump P-{i}", "rated power"), claim(f"valve V-{i}", "nominal diameter"),
                       claim(f"tank T-{i}", "storage volume")]
            sides += [side] * 3
    claims.append(claim("chiller", "cooling capacity"))  # A's alone
    sides.append("A")
    return claims, sides

class Words(unittest.TestCase):
    def test_words_are_lower_case_without_plurals_numbers_or_the_commonest(self):
        self.assertEqual(topics.words("Rated Powers of the 2 Pumps (total)"), {"rated", "power", "pump"})
        self.assertEqual(topics.words("glass status"), {"glass", "status"})  # not plurals

    def test_the_number_of_topics_grows_with_the_root_of_the_claims(self):
        self.assertEqual([topics.target(n) for n in (2, 50, 800, 13000)], [2, 5, 15, 15])

class Splitting(unittest.TestCase):
    def test_topics_are_words_both_sides_use_and_each_claim_goes_to_its_own(self):
        claims, sides = plant()
        way = topics.best(topics.ways(claims, sides))
        self.assertEqual(way.name, "by subject")
        found = {frozenset(t) for t in way.topics}
        self.assertIn(frozenset({"pump", "rated", "power"}), found)
        named = {w: t for t, words in enumerate(way.topics) for w in words}
        for c, t in zip(claims, way.placed):
            if c["entity"].startswith("pump"):
                self.assertEqual(t, named["pump"])
            if c["entity"].startswith("tank"):
                self.assertEqual(t, named["tank"])
        self.assertNotIn("chiller", named)  # one side's word makes no topic
        self.assertIsNone(way.placed[-1])
        self.assertEqual(way.measures["both_sides"], 1.0)
        self.assertGreater(way.measures["even"], 0.95)

    def test_the_same_claims_in_another_order_split_the_same_way(self):
        claims, sides = plant()
        first = topics.best(topics.ways(claims, sides))
        order = list(range(len(claims)))
        random.Random(7).shuffle(order)
        again = topics.best(topics.ways([claims[i] for i in order], [sides[i] for i in order]))
        self.assertEqual(again.topics, first.topics)
        self.assertEqual([again.placed[order.index(i)] for i in range(len(claims))], first.placed)

    def test_a_label_is_a_topics_first_words(self):
        self.assertEqual(topics.label(["tower", "steel", "density"]), "Tower, steel")

if __name__ == "__main__":
    unittest.main()
