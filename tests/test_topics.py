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

class Named(unittest.TestCase):
    """The topic_names lever: the model chooses among the ways and names the chosen way's topics; any failure leaves
    the most even way, named by its words."""
    def setUp(self):
        claims, sides = plant()
        self.claims = [{**c, "side": s} for c, s in zip(claims, sides)]
        self.found = topics.ways(claims, sides)

    def answer(self, way, names):
        from semantic_pdf_diff.schema import TopicNames
        return lambda prompt: TopicNames(way=way, names=names)

    def test_the_model_chooses_a_way_and_names_its_topics(self):
        asked = []
        def ask(prompt):
            asked.append(prompt)
            return self.answer(1, ["Pumps", "Valves ", "Storage  tanks"][:len(self.found[0].topics)])(prompt)
        chosen = topics.named(self.found, self.claims, ask)
        self.assertEqual(chosen["way"], "by subject")
        self.assertEqual(chosen["topics"], self.found[0].topics)
        self.assertEqual(chosen["names"], ["Pumps", "Valves", "Storage tanks"][:len(self.found[0].topics)])
        self.assertIn("WAY 1 (by subject):", asked[0])
        self.assertIn("(24 claims): pump P-0 — rated power; pump P-0 — rated power; pump P-1 — rated power",
                      asked[0])  # alternating between the sides

    def test_an_answer_that_does_not_fit_leaves_the_words(self):
        self.assertEqual(topics.named(self.found, self.claims, self.answer(9, ["x"])),
                         {"failed": f"way 9 of {len(self.found)}"})
        self.assertIn("names for", topics.named(self.found, self.claims, self.answer(1, ["only one"]))["failed"])

    def test_a_failed_request_leaves_the_words(self):
        from semantic_pdf_diff.failures import ModelFailure
        def ask(prompt):
            raise ModelFailure("HTTP 504: Gateway Timeout")
        self.assertEqual(topics.named(self.found, self.claims, ask),
                         {"failed": "ModelFailure: HTTP 504: Gateway Timeout"})

    def test_a_report_shows_the_models_names_unless_its_topics_have_changed(self):
        import tempfile
        from pathlib import Path
        from semantic_pdf_diff.report import report_topics, unpacked, write_report
        from test_portable_report import plant_report
        data = plant_report()
        found, _ = report_topics(data)
        way = found[0]
        names = [f"Topic {i}" for i in range(len(way.topics))]
        with tempfile.TemporaryDirectory() as d:
            write_report({**data, "topics": {"way": way.name, "topics": way.topics, "names": names}}, Path(d))
            shown = unpacked((Path(d) / "report.html").read_text())
            self.assertIn(">Topic 0 <small>", shown)
            self.assertIn("named by the model", shown)
            stale = {"way": way.name, "topics": [["other", "words"]] * len(way.topics), "names": names}
            write_report({**data, "topics": stale}, Path(d))
            self.assertNotIn(">Topic 0 <small>", unpacked((Path(d) / "report.html").read_text()))

if __name__ == "__main__":
    unittest.main()
