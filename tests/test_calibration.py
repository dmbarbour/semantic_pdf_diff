"""Tiling calibration: the question (tilechoice.py) and its known-good and known-bad cases (bench/calibration.py)."""
import stubs  # noqa: F401 (a clean environment)
import re
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff import tilechoice
from semantic_pdf_diff_lab.bench import calibration

CORPUS = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
TABLES, DECORATED = "wtp-tables-s1-clean", "lcc-s1-decorated"

def _page(stem, number=0):
    doc = pymupdf.open(CORPUS / f"{stem}.pdf")
    return doc, calibration.Page(f"{stem}.pdf", doc, number)

class Question(unittest.TestCase):
    def test_a_sketch_draws_the_page_and_a_strip_above_it(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 100), "the pump delivers 10 kW", fontsize=10)
            plain = pymupdf.Pixmap(tilechoice.sketch(page, side=512))
            drawn = pymupdf.Pixmap(tilechoice.sketch(page, [pymupdf.Rect(60, 80, 300, 120)], "B", side=512))
        self.assertEqual((plain.width, plain.height), (396, 512))
        self.assertEqual(drawn.width, 396)
        self.assertEqual(drawn.height, 512 + 40)  # the strip naming the tiling

    def test_a_dimmed_sketch_greys_what_no_tile_holds(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=600, height=600)  # white: a pixel's colour says whether it was greyed
            tile = pymupdf.Rect(300, 300, 600, 600)
            drawn = pymupdf.Pixmap(tilechoice.sketch(page, [tile], "A", side=600, dimmed=True))
            plain = pymupdf.Pixmap(tilechoice.sketch(page, [tile], "A", side=600))
        outside, inside = (100, 40 + 100), (500, 40 + 500)  # pixels below the strip
        self.assertLess(drawn.pixel(*outside)[0], 200)
        self.assertEqual(plain.pixel(*outside), (255, 255, 255))
        self.assertEqual(drawn.pixel(*inside), plain.pixel(*inside))  # inside a tile, only its wash
        self.assertIn("greyed out", tilechoice.prompt(list("AB"), dimmed=True))
        self.assertNotIn("greyed out", tilechoice.prompt(list("AB")))

    def test_the_prompt_names_each_candidate_and_suggests_no_answer(self):
        text = tilechoice.prompt(list("ABC"))
        self.assertIn("tilings A, B and C", text)
        self.assertIn("aren't part of the page", text)
        for problem in tilechoice.PROBLEMS:
            self.assertIn(f'"{problem}"', text)
        self.assertIn('"best": "A or B or C"', text)
        self.assertNotIn('joined by "and"', text)
        self.assertIn('equally good, name each, joined by "and"', tilechoice.prompt(list("ABC"), ties=True))

    def test_answers_are_read_leniently_and_only_as_offered(self):
        answer = tilechoice.Choice.model_validate({"best": "Tiling b.", "problems": {
            "A": ["Cuts text", "something else"], "tiling C": "splits a figure; repeats text", "D": ["cuts text"]}})
        self.assertEqual(tilechoice.chosen(answer, list("ABC")), "B")
        self.assertEqual(tilechoice.problems(answer, list("ABC")),
                         {"A": ["cuts text"], "C": ["splits a figure", "repeats text"]})
        self.assertIsNone(tilechoice.chosen(tilechoice.Choice.model_validate({"best": "D"}), list("ABC")))
        self.assertIsNone(tilechoice.chosen(tilechoice.Choice.model_validate({}), list("ABC")))

    def test_a_tie_names_several_and_chooses_none(self):
        def named(best):
            return tilechoice.named(tilechoice.Choice.model_validate({"best": best}), list("ABC"))
        self.assertEqual(named("C and A"), ["A", "C"])
        self.assertEqual(named("Tilings A, B and C."), ["A", "B", "C"])
        self.assertEqual(named(["B", "A"]), ["A", "B"])  # a list, read as lines
        for hedged in ("A or B", "A and D", ""):
            self.assertEqual(named(hedged), [], hedged)
        self.assertIsNone(tilechoice.chosen(tilechoice.Choice.model_validate({"best": "A and B"}), list("ABC")))

class Cases(unittest.TestCase):
    def test_the_good_tiling_has_no_fault_and_each_bad_one_shows_its_own(self):
        for stem, expected in ((TABLES, {"midline", "grid", "border", "figure split", "missing", "overlap"}),
                               (DECORATED, {"midline", "grid", "shifted", "decoration", "border", "missing",
                                             "overlap"})):
            doc, p = _page(stem)
            with doc:
                found = calibration.tilings(p)
                self.assertEqual(set(found) - {"good"}, expected, stem)
                m = p.measured(found["good"])
                for fault in ("lines_cut_sideways", "lines_cut_across", "words_cut", "figures_not_whole",
                              "decoration_only", "blank", "lines_missed"):
                    self.assertEqual(m[fault], 0, (stem, fault))
                for kind in expected:
                    self.assertTrue(calibration.shows(kind, p.measured(found[kind])), (stem, kind))

    def test_questions_pair_every_bad_kind_and_replay_in_the_same_orders(self):
        doc, p = _page(TABLES)
        with doc:
            found = calibration.tilings(p)
            asked = calibration.questions(p, found)
            self.assertEqual(asked, calibration.questions(p, found))
        self.assertEqual({k for q in asked for k in q["kinds"][1:]}, set(found) - {"good"})
        for q in asked:
            self.assertEqual(q["kinds"][0], "good")
            self.assertEqual(len(set(q["kinds"])), len(q["kinds"]))
            first, second = q["orders"]
            self.assertEqual(sorted(first), sorted(q["kinds"]))
            self.assertEqual(second, first[-1:] + first[:-1])  # each candidate moves one place on

    def test_near_cases_show_one_fault_each_and_are_asked_both_ways(self):
        doc, p = _page(DECORATED)
        with doc:
            found = calibration.tilings(p, near=True)
            self.assertEqual(set(found) - {"good"}, {"one cut", "one overlap", "snapped"})
            self.assertEqual(calibration.fault_of(p.measured(found["one cut"])), "cuts text")
            self.assertEqual(calibration.fault_of(p.measured(found["one overlap"])), "repeats text")
            self.assertIsNone(calibration.fault_of(p.measured(found["good"])))
            asked = calibration.near_questions(p, found)
        self.assertEqual(len(asked), 3)
        for q in asked:
            first, second = q["orders"]
            self.assertEqual(second, first[::-1])

class Judge:
    """A simulated model: chooses the candidate whose picture is named for `prefer` (the known-good, always the
    first, or the known-good tied with the first other), and names each candidate's own fault, read from its picture's
    name."""

    def __init__(self, prefer="good"):
        self.prefer = prefer

    def ask(self, prompt, schema, images=(), key=None):
        letters = re.search(r"tilings ([A-F](?:, [A-F])*(?: and [A-F])?)", prompt).group(1)
        letters = re.findall(r"[A-F]", letters)
        kinds = [Path(i).stem.removesuffix("-dimmed").rsplit("-", 1)[0].split("-p1-", 1)[1].replace("-", " ")
                 for i in images[1:]]
        good = letters[kinds.index("good")]
        other = next(x for x in letters if x != good)
        best = {"good": good, "first": letters[0], "tie": f"{good} and {other}"}[self.prefer]
        return schema.model_validate({"best": best, "problems": {
            x: ([] if k == "good" else [calibration.KINDS[k]]) for x, k in zip(letters, kinds)}})

class Scoring(unittest.TestCase):
    def ask(self, judge, arm="outlined"):
        with tempfile.TemporaryDirectory() as folder:
            return calibration.ask_all(folder, judge, CORPUS, {f"{TABLES}-p1"}, arm)

    def test_a_judge_that_knows_scores_full_marks(self):
        found = calibration.score(self.ask(Judge()))
        self.assertEqual(found["answered"], found["questions"])
        self.assertEqual((found["good_chosen"], found["same_in_both_orders"], found["good_faulted"]), (1.0, 1.0, 0.0))
        for kind, row in found["by_kind"].items():
            self.assertEqual((row["good_chosen"], row["this_chosen"], row["fault_named"]), (1.0, 0.0, 1.0), kind)

    def test_a_judge_that_always_takes_the_first_shows_its_bias(self):
        found = calibration.score(self.ask(Judge("first")))
        self.assertEqual(found["positions"]["3"]["chosen"], [1.0, 0.0, 0.0])
        self.assertEqual(found["same_in_both_orders"], 0.0)  # the candidates moved; its choice didn't
        self.assertEqual(found["good_chosen"], found["positions"]["3"]["good_at"][0])

    def test_a_judge_that_ties_chooses_none_and_its_ties_are_counted(self):
        asked = self.ask(Judge("tie"), "ties")
        found = calibration.score(asked)
        self.assertEqual((found["good_chosen"], found["tied"], found["good_tied"], found["invalid"]),
                         (0.0, 1.0, 1.0, 0))
        self.assertEqual(found["tied_questions"], found["answered"])
        self.assertEqual(sum(r["tied_with_good"] * r["asked"] for r in found["by_kind"].values()), found["asked"])
        self.assertTrue(all(c == 0 for row in found["positions"].values() for c in row["chosen"]))
        self.assertTrue(all(len(a["named"]) == 2 for q in asked.values() for a in q["answers"]))

if __name__ == "__main__":
    unittest.main()
