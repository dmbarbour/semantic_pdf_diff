"""Eye tests: every card draws its answers, scoring tells errors apart, and recorded answers replay."""
import json
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import eyetest
from semantic_pdf_diff.eyetest import Card

FOLDER = Path(__file__).resolve().parent.parent / "benchmarks" / "eyetest"

class Perfect:
    """A model that reads everything right (from the answer key), or answers one card family wrongly."""
    def __init__(self, truths, wrong=None):
        self.truths, self.wrong, self.asked = truths, wrong, []
    def ask(self, prompt, schema, images=(), key=None):
        self.asked.append(key)
        card, truth = self.truths[key[1]]
        answer = eyetest.perfect(card, truth)
        if card.family == self.wrong:
            answer = {"lines": ["?"]} if card.family == "read" else {}
        return schema.model_validate(answer)

class Cards(unittest.TestCase):
    def test_every_card_draws_its_answers(self):
        cards = eyetest.suite("quick") + eyetest.suite("standard")[::5]
        for card in cards:
            with self.subTest(card=card.id):
                _, truth, prompt = eyetest.render(card, image=False)  # raises if the text layer lacks an answer
                self.assertEqual(eyetest.score(card, truth, eyetest.perfect(card, truth))["score"], 1.0)
                self.assertIn("JSON", prompt)
        self.assertEqual(len({c.id for c in eyetest.suite("standard")}), len(eyetest.suite("standard")))

    def test_images_are_drawn_the_same_every_time(self):
        for card in eyetest.suite("quick")[::4]:
            self.assertEqual(eyetest.render(card)[0], eyetest.render(card)[0])

class Scoring(unittest.TestCase):
    def test_reading(self):
        truth = {"lines": ["AB-12   4.75   K7Q", "2'-9 1/2\"   ±0.05"]}
        right = eyetest.score("read", truth, {"lines": ["AB-12 4.75 K7Q", "2'-9 1/2\" ±0.05"]})
        self.assertEqual((right["score"], right["cer"]), (1.0, 0.0))
        wrong = eyetest.score("read", truth, {"lines": ["AB-12 4.15 K7Q"]})  # a misread and a line missed
        self.assertAlmostEqual(wrong["score"], 2 / 6, places=3)
        self.assertGreater(wrong["cer"], 0)

    def test_pseudo_words_read_as_the_words_they_came_from_count_as_autocorrected(self):
        card = Card("pseudo", 1024, 1024, 8)
        _, truth, prompt = eyetest.render(card, image=False)
        self.assertTrue(all(eyetest.norm(t) not in eyetest.WORDS for line in truth["lines"] for t in line.split()))
        self.assertEqual(prompt, eyetest.render(Card("words", 1024, 1024, 8), image=False)[2])  # the same instructions
        corrected = eyetest.score(card, truth, {"lines": [" ".join(truth["sources"])]})
        self.assertEqual((corrected["score"], corrected["autocorrected"]), (0.0, len(truth["sources"])))
        self.assertEqual(eyetest.score(card, truth, eyetest.perfect(card, truth))["autocorrected"], 0)

    def test_pseudo_word_levels_keep_or_change_the_height_profile(self):
        import random
        outline = lambda w: "".join(eyetest.height(ch)[0] for ch in w.lower())
        rng = random.Random(1)
        for level in eyetest.PSEUDO_LEVELS:
            for _ in range(50):
                fake, real = eyetest.pseudo(rng, level)
                changed = [(a, b) for a, b in zip(fake.lower(), real.lower()) if a != b]
                self.assertEqual(len(changed), 1)
                (new, old), = changed
                if level == "close":
                    self.assertIn(new, eyetest.CLOSE[old])
                self.assertEqual(outline(fake) == outline(real), level != "shape", (level, fake, real))

    def test_pairs_tell_misbound_from_misread(self):
        truth = {"pairs": {"K7Q": "4.75", "HX-402": "88", "P-17B": "1250"}}
        answer = {"pairs": [{"name": "K7Q", "value": "88"}, {"name": "HX-402", "value": "4.75"},
                            {"name": "P-17B", "value": "1258"}, {"name": "ZZ9", "value": "1"}]}
        s = eyetest.score("pairs", truth, answer)
        self.assertEqual((s["right"], s["misbound"], s["misread"], s["unknown_name"], s["missed"]), (0, 2, 1, 1, 0))

    def test_lookups_note_a_value_from_the_same_row(self):
        truth = {"questions": [{"n": 1, "key": "R1|C1", "value": "10"}, {"n": 2, "key": "R2|C2", "value": "40"}],
                 "cells": {"R1|C1": "10", "R1|C2": "20", "R2|C1": "30", "R2|C2": "40"}}
        s = eyetest.score("table", truth, {"answers": [{"n": 1, "value": "20"}, {"n": 2, "value": "?"}]})
        self.assertEqual((s["right"], s["misbound"], s["same_row_or_column"], s["declined"]), (0, 1, 1, 1))
        axis = {"questions": [{"n": 1, "key": "A", "value": "70", "tolerance": 5}], "cells": {"A": "70", "B": "90"}}
        self.assertEqual(eyetest.score("chart-axis", axis, {"answers": [{"n": 1, "value": "72"}]})["right"], 1)
        self.assertEqual(eyetest.score("chart-axis", axis, {"answers": [{"n": 1, "value": "90"}]})["misbound"], 1)

    def test_arrows(self):
        truth = {"edges": [{"start": "A1", "end": "B2", "label": "x"}, {"start": "B2", "end": "C3", "label": "y"},
                           {"start": "C3", "end": "A1", "label": "z"}]}
        answer = {"edges": [{"start": "B2", "end": "A1", "label": "x"}, {"start": "B2", "end": "C3", "label": "z"},
                            {"start": "A1", "end": "C3", "label": "q"}]}
        s = eyetest.score("graph", truth, answer)
        self.assertEqual((s["right"], s["reversed"], s["label_misbound"], s["label_misread"]), (0, 1, 1, 1))

    def test_threshold_interpolates_where_reading_first_holds(self):
        self.assertEqual(eyetest.threshold([(4, 0.2), (6, 0.8), (8, 1.0), (10, 1.0)]), 7.0)
        self.assertEqual(eyetest.threshold([(4, 0.95), (6, 1.0)]), 4.0)
        self.assertIsNone(eyetest.threshold([(4, 0.1), (6, 0.5)]))
        # a dip is averaged with its neighbours (reading only gets easier as glyphs grow)
        for got, want in zip(eyetest.monotone([0.1, 0.95, 0.91, 1.0]), [0.1, 0.93, 0.93, 1.0]):
            self.assertAlmostEqual(got, want)
        self.assertEqual(eyetest.threshold([(4, 0.1), (6, 0.95), (8, 0.91), (10, 1.0)]), 5.93)
        self.assertEqual(eyetest.threshold([(4, 0.1), (6, 0.95), (8, 0.75), (10, 1.0)]), 8.67)  # 6 and 8 pooled at 0.85

class Asking(unittest.TestCase):
    def test_a_suite_is_asked_scored_and_shown(self):
        cards = eyetest.suite("quick")
        truths = {c.id: (c, eyetest.render(c, image=False)[1]) for c in cards}
        with tempfile.TemporaryDirectory() as d:
            answers = eyetest.ask(d, Perfect(truths, wrong="graph"), cards)
            self.assertEqual(len(answers), len(cards))
            result = eyetest.results(cards, answers)
            families = result["summary"]["families"]
            self.assertEqual({f: v["score"] for f, v in families.items() if f != "graph"},
                             dict.fromkeys(set(families) - {"graph"}, 1.0))
            self.assertEqual(families["graph"]["score"], 0.0)
            self.assertEqual(set(result["summary"]["thresholds"]), {"768x768", "1536x1536", "1584x384"})
            data = {"suite": "quick", "cards": {i: {"family": c.family, "truth": t} for i, (c, t) in truths.items()},
                    "models": {"perfect": result}}
            self.assertIn("Eye tests", eyetest.page(d, data).read_text())

    @unittest.skipUnless((FOLDER / "replay.zip").exists(), "no recorded eye tests")
    def test_recorded_answers_replay(self):
        import pymupdf
        from semantic_pdf_diff.fixtures import Fixture, unpack
        from semantic_pdf_diff.llm import folder_client
        from semantic_pdf_diff.models import Settings
        with tempfile.TemporaryDirectory() as d, Fixture(unpack(FOLDER / "replay.zip", d)) as fixture:
            recorded = fixture.meta().get("pymupdf")
        if recorded != pymupdf.VersionBind:
            self.skipTest(f"recorded with PyMuPDF {recorded}; images differ under {pymupdf.VersionBind}")
        data = json.loads((FOLDER / "results.json").read_text(encoding="utf-8"))
        model = "google/gemma-4-31B-it"
        cards = [c for c in eyetest.suite(data["suite"]) if c.id in data["models"][model]["cards"]][::7]
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "replay.zip").write_bytes((FOLDER / "replay.zip").read_bytes())
            with folder_client(d, Settings(model=model, base_url="http://127.0.0.1:9/v1", **eyetest.EYE_SETTINGS),
                               mode="replay") as client:
                answers = eyetest.ask(d, client, cards)
        for card in cards:
            self.assertEqual(answers[card.id], data["models"][model]["cards"][card.id]["answer"])

if __name__ == "__main__":
    unittest.main()
