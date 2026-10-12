"""The tile_choice lever: each tiler's cut measured, the best taken, the model asked where none is best."""
import stubs  # noqa: F401 (a clean environment)
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff.context import Context
from semantic_pdf_diff.failures import ModelFailure
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.tilechoice import Choice

CORPUS = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
SLIDE, REPORT, PLAN = ("lcc-s1-slide", 1), ("lcc-s1-clean", 0), ("lcc-plan-s1-clean", 0)
UNSETTLED = ("coaster-s1", 0)  # no cut is best: bands, the grid, snapped and XY-cut unbeaten

class Asker:
    """The model, as the reader asks it: answers `best`, or fails; counts the questions."""

    def __init__(self, best="B", fail=False):
        self.best, self.fail, self.asked = best, fail, []

    def __call__(self, prompt, schema, images=(), key=None):
        self.asked.append((prompt, list(images), key))
        if self.fail:
            raise ModelFailure("the endpoint is down")
        return Choice(best=self.best, problems={})

class Choosing(unittest.TestCase):
    def choose(self, where, asker, mode="model"):
        stem, number = where
        doc = pymupdf.open(CORPUS / f"{stem}.pdf")
        self.addCleanup(doc.close)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        s = Settings(tile_choice=mode)
        reader = Context(doc, s, Path(folder.name), "stem")
        reader.ask = asker
        page = doc[number]
        how = s.tiling_of(reader, page)
        return how, reader.page_choices[number], reader, s, page

    def test_a_cut_at_least_as_good_as_the_rest_is_taken_without_asking(self):
        asker = Asker()
        how, record, *_ = self.choose(SLIDE, asker)  # the grid cuts the slide's lines; XY-cut cuts none, in one tile
        self.assertEqual((record["default"], how), ("grid", "xycut"))
        self.assertEqual((record["asked"], asker.asked), (False, []))

    def test_cuts_as_good_as_each_other_go_to_the_default_without_asking(self):
        from unittest import mock
        from semantic_pdf_diff import tilechoice
        even = dict.fromkeys(tilechoice.MEASURES, 0)
        worse = {**even, "cuts": 5}
        found = {"bands": ([], even), "grid": ([], worse), "xycut": ([], dict(even))}
        asker = Asker()
        with mock.patch.object(tilechoice, "candidates", return_value=found):
            how, record, *_ = self.choose(REPORT, asker)
        self.assertEqual((how, record["clear"], record["asked"], asker.asked), ("bands", True, False, []))

    def test_on_a_report_page_bands_send_fewest_images(self):
        how, record, *_ = self.choose(REPORT, Asker())  # its one band holds text alone: skipped, as today
        self.assertEqual((how, record["clear"], record["scores"]["bands"]["images"]), ("bands", True, 0))

    def test_where_none_is_best_the_model_chooses_among_those_no_other_beats(self):
        asker = Asker("B")
        how, record, reader, s, page = self.choose(UNSETTLED, asker)
        self.assertTrue(record["asked"])
        self.assertGreaterEqual(len(record["front"]), 2)
        from semantic_pdf_diff.tilechoice import MEASURES, MOST
        best = sorted(record["front"], key=lambda h: [record["scores"][h][m] for m in MEASURES])[:MOST]
        self.assertEqual(set(record["order"]), set(best))  # the best by the measures of those no other beats
        self.assertEqual(how, record["order"][1])
        _, images, key = asker.asked[0]
        self.assertEqual(len(images), 1 + len(record["order"]))  # the page, then a sketch per candidate
        self.assertTrue(all(Path(i).exists() for i in images))
        self.assertEqual(key[0], "tilechoice")
        tiles = [r for tag, r, _ in s.visual_regions(reader, page, page.number) if tag.startswith("tile")]
        self.assertEqual(tiles, [r for _, r, _ in s.kept_tiles(reader, page, s.tiles_for(reader, page, how))])
        self.assertEqual(len(asker.asked), 1)  # the choice kept: asked once a page

    def test_cuts_the_model_names_as_equally_good_are_each_read(self):
        from semantic_pdf_diff import tilechoice
        for best, n in (("A and B", 2), ("A, B and C", 3)):
            asker = Asker(best)
            how, record, reader, s, page = self.choose(UNSETTLED, asker)
            with self.subTest(best=best):
                self.assertIn('joined by "and"', asker.asked[0][0])
                by_measures = sorted(record["order"][:n], key=lambda h: [record["scores"][h][m]
                                                                         for m in tilechoice.MEASURES])
                self.assertEqual(how.split("+"), by_measures[:tilechoice.TIED])
                self.assertEqual(record["answer"], how)
                self.assertTrue(record["issues"][0].startswith("The model named "))
                tiles = [r for tag, r, _ in s.visual_regions(reader, page, page.number) if tag.startswith("tile")]
                each = [r for part in how.split("+") for _, r, _ in s.tiles_for(reader, page, part)]
                self.assertEqual(tiles, [r for _, r, _ in s.kept_tiles(reader, page, s.tiles_for(reader, page, how))])
                self.assertEqual([r for _, r, _ in s.tiles_for(reader, page, how)], each)

    def test_a_failed_question_or_an_answer_naming_none_falls_back_to_the_measures(self):
        for asker in (Asker(fail=True), Asker("Z")):
            how, record, *_ = self.choose(UNSETTLED, asker)
            with self.subTest(fail=asker.fail):
                self.assertTrue(record["asked"])
                self.assertIsNone(record["answer"])
                self.assertEqual(how, "bands")  # the default: no other cut beats it
                self.assertTrue(record["issues"][0].endswith("the cut chosen by the measures"))

    def test_by_the_measures_alone_the_model_is_never_asked(self):
        asker = Asker()
        how, record, *_ = self.choose(UNSETTLED, asker, mode="measures")
        self.assertEqual((how, record["asked"], asker.asked), ("bands", False, []))

    def test_a_drawing_sheet_keeps_the_tilers_cut(self):  # XY-cut's larger tiles lost facts there (milestones 3, 5)
        for mode in ("measures", "model"):
            doc = pymupdf.open(CORPUS / f"{PLAN[0]}.pdf")
            with doc:
                s = Settings(tile_choice=mode, decoration=True)  # with decoration the rule took XY-cut on a sheet
                reader = Context(doc, s)
                reader.ask = Asker()
                self.assertEqual(s.tiling_of(reader, doc[PLAN[1]]), "grid")
                self.assertEqual((reader.page_choices, reader.ask.asked), ({}, []))

    def test_off_leaves_the_tilers_cut(self):
        doc = pymupdf.open(CORPUS / f"{SLIDE[0]}.pdf")
        with doc:
            s = Settings(tile_choice="off")
            reader = Context(doc, s)
            self.assertEqual(s.tiling_of(reader, doc[SLIDE[1]]), "grid")
            self.assertEqual(reader.page_choices, {})

class Job(unittest.TestCase):
    def test_a_pdf_job_asks_once_and_records_the_choice(self):
        from semantic_pdf_diff.jobs import extract_pdf

        class Client(stubs.Recorder):
            def __init__(self, **settings):
                super().__init__(**settings)
                self.choices = 0

            def answer(self, prompt, schema, images, key):
                if schema is Choice:
                    self.choices += 1
                    return Choice(best="A", problems={"A": ["cuts text"]})
                return Extraction(claims=[], complete=True) if schema is Extraction else schema.model_validate({})
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open(CORPUS / f"{UNSETTLED[0]}.pdf")
            path = Path(d) / "t.pdf"
            doc.select([UNSETTLED[1]])
            doc.save(path)
            doc.close()
            client = Client(tile_choice="model")
            _, coverage = extract_pdf(path, "sha256:" + "a" * 64 + ".pdf", Path(d), client)
        self.assertEqual(client.choices, 1)
        (row,) = [r for r in coverage if r["task"] == "vision:p1:tiling"]
        self.assertEqual(row["status"], "complete")
        self.assertTrue(row["issues"][0].startswith("Cut as "))
        self.assertEqual(row["issues"][0], "Cut as bands (offered bands, xycut, snapped; the default bands)")
        self.assertIn('bands: "cuts text" named by the model, not found by the measures', row["issues"])
        self.assertIn('snapped: "decoration or blank" found by the measures, not named by the model', row["issues"])

if __name__ == "__main__":
    unittest.main()
