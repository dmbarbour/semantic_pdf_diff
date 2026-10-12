"""The region_labels lever: the model labels the tiles a page sends, and the labels decide what's sent."""
import stubs  # noqa: F401 (a clean environment)
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff import regionlabels
from semantic_pdf_diff.context import Context
from semantic_pdf_diff.failures import ModelFailure
from semantic_pdf_diff.regionlabels import Labels
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.settings import Settings

CORPUS = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
SLIDE = ("lcc-s1-slide", 1)  # a wide page: grid tiles, some of text alone
SHEET = ("lcc-plan-s1-clean", 0)  # a drawing sheet

class Question(unittest.TestCase):
    def test_the_prompt_names_every_label_and_suggests_none(self):
        text = regionlabels.prompt(3)
        for label in regionlabels.LABELS:
            self.assertIn(f'- "{label}": ', text)
        self.assertIn("3 regions", text)
        self.assertIn("aren't part of the page", text)
        self.assertIn('"label": "..."', text)
        self.assertIn("1 region outlined", regionlabels.prompt(1))

    def test_answers_are_read_leniently(self):
        answer = Labels.model_validate({"regions": {
            "1": {"label": "Text"}, "region 2": "Photo", "3": {"label": "other", "what": " a  QR code "},
            "4": {"label": "a bar chart"}, "5": {"label": "spreadsheet"}, "9": {"label": "text"}}})
        self.assertEqual(regionlabels.labels(answer, 5), {
            1: ("text", ""), 2: ("photo or scan", ""), 3: ("other", "a QR code"), 4: ("chart", ""), 5: (None, "")})

class Acting(unittest.TestCase):
    def regions(self, *rects):
        return [(f"tile:{i}", pymupdf.Rect(r), "") for i, r in enumerate(rects)]

    def test_text_decoration_and_blank_tiles_are_not_sent(self):
        regions = self.regions((0, 0, 100, 100), (100, 0, 200, 100), (200, 0, 300, 100), (300, 0, 400, 100))
        found = {"labels": ["text", "chart", "blank", "decoration"], "other": {}, "issues": []}
        sent, done = regionlabels.act(regions, found)
        self.assertEqual([t for t, _, _ in sent], ["tile:1"])
        self.assertEqual(done["dropped"], ["tile:0", "tile:2", "tile:3"])

    def test_a_nonsense_tile_is_joined_to_the_neighbour_it_touches_most(self):
        regions = self.regions((0, 0, 100, 50), (0, 50, 100, 300), (100, 50, 120, 60))
        found = {"labels": ["table", "nonsense", "table"], "other": {}, "issues": []}
        sent, done = regionlabels.act(regions, found)
        self.assertEqual([(t, tuple(r)) for t, r, _ in sent],
                         [("tile:0", (0, 0, 100, 300)), ("tile:2", (100, 50, 120, 60))])
        self.assertEqual(done["joined"], {"tile:1": "tile:0"})
        alone, done = regionlabels.act(self.regions((0, 0, 100, 50)), {"labels": ["nonsense"], "other": {}})
        self.assertEqual(len(alone), 1)
        self.assertIn("no neighbour", done["issues"][0])

    def test_labels_are_checked_against_what_the_measures_see(self):
        regions = self.regions((0, 0, 100, 100), (100, 0, 200, 100))
        found = {"labels": ["blank", "chart"], "other": {}}
        measured = [{"text_only": True, "decoration_only": False, "blank": False},
                    {"text_only": False, "decoration_only": False, "blank": True}]
        sent, done = regionlabels.act(regions, found, measured)
        self.assertEqual(done["issues"], ['tile:0: "blank", but the measures find text',
                                          'tile:1: "chart", but the measures find blank alone'])
        self.assertEqual([t for t, _, _ in sent], ["tile:1"])  # skipped: the measures find nothing to see there

    def test_a_tile_the_measures_find_a_graphic_in_is_sent_whatever_its_label(self):
        regions = self.regions((0, 0, 100, 100), (100, 0, 200, 100))
        found = {"labels": ["blank", "text"], "other": {}}
        drawn = {"text_only": False, "decoration_only": False, "blank": False}
        sent, done = regionlabels.act(regions, found, [drawn, drawn])
        self.assertEqual(([t for t, _, _ in sent], done["dropped"]), (["tile:0", "tile:1"], []))
        self.assertEqual(done["issues"], ['tile:0: "blank", but the measures find a graphic that counts: sent',
                                          'tile:1: "text", but the measures find a graphic that counts: sent'])

class Asker:
    """The model, as the reader asks it: labels every region `label`, or fails."""

    def __init__(self, label="chart", fail=False):
        self.label, self.fail, self.asked = label, fail, []

    def __call__(self, prompt, schema, images=(), key=None):
        self.asked.append((prompt, list(images), key))
        if self.fail:
            raise ModelFailure("the endpoint is down")
        count = int(prompt.split(" with ", 1)[1].split()[0])
        return Labels(regions={str(i + 1): {"label": self.label} for i in range(count)})

class Lever(unittest.TestCase):
    def regions(self, asker, mode="model", where=SLIDE):
        stem, number = where
        doc = pymupdf.open(CORPUS / f"{stem}.pdf")
        self.addCleanup(doc.close)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        s = Settings(region_labels=mode)
        reader = Context(doc, s, Path(folder.name), "stem")
        reader.ask = asker
        page = doc[number]
        tiles = [r for r in s.visual_regions(reader, page, number) if r[0].startswith("tile")]
        return tiles, reader.page_labels.get(number), Settings().visual_regions(Context(doc, Settings()), page, number)

    def test_asked_once_a_page_about_the_tiles_it_sends(self):
        asker = Asker("chart")
        tiles, record, today = self.regions(asker)
        self.assertEqual(tiles, [r for r in today if r[0].startswith("tile")])  # charts: every tile sent
        self.assertEqual(len(asker.asked), 1)
        prompt, images, key = asker.asked[0]
        self.assertIn(f"{len(tiles)} regions", prompt)
        self.assertEqual((len(images), key[0]), (2, "regionlabels"))
        self.assertTrue(all(Path(i).exists() for i in images))
        self.assertEqual(record["found"]["labels"], ["chart"] * len(tiles))

    def test_tiles_labelled_text_are_not_sent(self):
        tiles, record, today = self.regions(Asker("text"))
        self.assertEqual(tiles, [])
        self.assertEqual(len(record["dropped"]), len([r for r in today if r[0].startswith("tile")]))

    def test_a_drawing_sheets_text_is_sent(self):  # its text tasks miss facts its tiles find (milestone 3)
        tiles, record, today = self.regions(Asker("text"), where=SHEET)
        self.assertEqual((tiles, record["dropped"]), ([r for r in today if r[0].startswith("tile")], []))
        _, record, _ = self.regions(Asker("blank"), where=SHEET)
        self.assertTrue(record["dropped"])  # its blank tiles still aren't

    def test_a_failed_question_sends_every_tile(self):
        tiles, record, today = self.regions(Asker(fail=True))
        self.assertEqual(tiles, [r for r in today if r[0].startswith("tile")])
        self.assertTrue(record["issues"][0].startswith("The labels question failed"))

    def test_off_asks_nothing(self):
        asker = Asker()
        _, record, _ = self.regions(asker, mode="off")
        self.assertEqual((asker.asked, record), ([], None))

class Job(unittest.TestCase):
    def test_a_pdf_job_records_the_labels(self):
        from semantic_pdf_diff.jobs import extract_pdf

        class Client(stubs.Recorder):
            def answer(self, prompt, schema, images, key):
                if schema is Labels:
                    return Labels(regions={"1": {"label": "other", "what": "a QR code"}, "2": "text"})
                return Extraction(claims=[], complete=True) if schema is Extraction else schema.model_validate({})
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open(CORPUS / f"{SLIDE[0]}.pdf")
            path = Path(d) / "t.pdf"
            doc.select([SLIDE[1]])
            doc.save(path)
            doc.close()
            _, coverage = extract_pdf(path, "sha256:" + "b" * 64 + ".pdf", Path(d), Client(region_labels="model"))
        (row,) = [r for r in coverage if r["task"] == "vision:p1:labels"]
        self.assertEqual(row["status"], "complete")
        self.assertTrue(row["issues"][0].startswith("Tiles labelled: 0 other, 1 text"))
        self.assertIn("Not sent: tile:1", row["issues"])
        self.assertIn("tile:0 holds a QR code (other)", row["issues"])

if __name__ == "__main__":
    unittest.main()
