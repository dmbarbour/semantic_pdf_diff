"""Region labels calibration (bench/labelling.py): regions whose labels are known, and the scoring."""
import stubs  # noqa: F401 (a clean environment)
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff.regionlabels import Labels
from semantic_pdf_diff_lab.bench import labelling
from semantic_pdf_diff_lab.bench.calibration import Page

CORPUS = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
CHARTS, TABLES = "lcc-enduse-s1-clean", "wtp-tables-s1-clean"

class Regions(unittest.TestCase):
    def regions(self, stem, number=0):
        doc = pymupdf.open(CORPUS / f"{stem}.pdf")
        self.addCleanup(doc.close)
        p = Page(f"{stem}.pdf", doc, number)
        return p, labelling.plain(p, CORPUS)

    def test_plain_regions_hold_the_pages_figures_text_and_margin_without_overlap(self):
        p, found = self.regions(CHARTS)
        self.assertEqual(sorted(r.why for r in found if r.key == "chart"),
                         ["a detected figure", "the key's chart, undetected"])  # the line chart isn't detected
        self.assertIn("blank", {r.key for r in found})
        self.assertTrue(any(r.why == "a header or footer" and "decoration" in r.accepted for r in found))
        for i, a in enumerate(found):
            for b in found[i + 1:]:
                self.assertFalse(a.overlaps(b), (a.why, b.why))
        _, tables = self.regions(TABLES)
        self.assertGreaterEqual(sum(r.key == "table" for r in tables), 3)

    def test_hard_regions_cut_a_figure_and_a_paragraph(self):
        p, found = self.regions("ahu-schematic-s1-clean")
        hard = labelling.hard(p, found)
        self.assertEqual([r.why for r in hard if r.key == "nonsense"],
                         ["half a drawing", "a strip through a paragraph's lines"])
        for i, a in enumerate(hard):
            for b in hard[i + 1:]:
                self.assertFalse(a.overlaps(b), (a.why, b.why))

    def test_questions_are_numbered_twice_the_second_the_reverse(self):
        p, _ = self.regions(CHARTS)
        asked = labelling.questions(p, CORPUS)
        self.assertEqual([q["id"] for q in asked], [f"{CHARTS}-p1-plain", f"{CHARTS}-p1-hard"])
        for q in asked:
            first, second = q["orders"]
            self.assertEqual(sorted(first), list(range(len(q["regions"]))))
            self.assertEqual(second, first[::-1])
            self.assertLessEqual(sum(r.key == "text" for r in q["regions"]), labelling.TEXTS)
        def plainly(qs):
            return [(q["id"], [(r.key, tuple(r.rect)) for r in q["regions"]], q["orders"]) for q in qs]
        self.assertEqual(plainly(asked), plainly(labelling.questions(p, CORPUS)))

class Everything:
    """A simulated model labelling every region one way."""

    def __init__(self, label):
        self.label = label

    def ask(self, prompt, schema, images=(), key=None):
        count = int(prompt.split(" with ", 1)[1].split()[0])
        return Labels(regions={str(i + 1): {"label": self.label} for i in range(count)})

class Scoring(unittest.TestCase):
    def test_a_model_calling_everything_text_loses_every_figure(self):
        with tempfile.TemporaryDirectory() as folder:
            asked = labelling.ask_all(folder, Everything("text"), CORPUS, {f"{CHARTS}-p1"})
        found = labelling.score(asked)
        self.assertEqual((found["questions"], found["answered"], found["unlabelled"]), (2, 2, 0))
        self.assertEqual((found["lost"], found["same_in_both_numberings"]), (1.0, 1.0))
        self.assertEqual(found["by_key"]["text"]["right"], 1.0)
        self.assertEqual(found["by_key"]["chart"]["said"], {"text": found["by_key"]["chart"]["asked"]})
        self.assertFalse(found["passes"])
        regions = [r for q in asked.values() for r in q["regions"]]
        texts = sum(2 for r in regions if "text" in r["accepted"])
        self.assertAlmostEqual(found["right"], texts / (2 * len(regions)), places=3)

if __name__ == "__main__":
    unittest.main()
