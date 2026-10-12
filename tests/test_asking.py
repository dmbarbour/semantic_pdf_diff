"""Asking calibration (bench/asking.py): tiles whose cuts are known, read as the product reads a tile, and scored on
whether their answers ask for another tiling."""
import stubs
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.tiling import cut_by
from semantic_pdf_diff_lab.bench import asking
from semantic_pdf_diff_lab.bench.calibration import Page

CORPUS = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
PAGE = "lcc-s1-clean"

class Tiles(unittest.TestCase):
    def test_whole_tiles_cut_nothing_cut_tiles_name_their_edges(self):
        with pymupdf.open(CORPUS / f"{PAGE}.pdf") as doc:
            p = Page(f"{PAGE}.pdf", doc, 0)
            found = asking.tiles(p)
            lines = [tuple(b) for b, _ in p.lines]
            kinds = [t["kind"] for t in found]
            self.assertEqual(kinds[0], "good")
            self.assertTrue(set(kinds[1:]) <= {"good", *asking.CUT_KINDS} and len(set(kinds)) > 1)
            for t in found:
                edges, cut = cut_by(tuple(t["rect"]), lines)
                if t["kind"] == "good":
                    self.assertEqual(cut, [])
                else:
                    self.assertTrue(t["cut"] and t["edges"])
            self.assertLessEqual(sum(k != "good" for k in kinds), asking.CUT_TILES)

class Client(stubs.Recorder):
    """Every tile's answer says its right edge cuts content, as asked; with `said`, its issues say so too."""
    said = False

    def answer(self, prompt, schema, images, key):
        if schema is Extraction:
            return Extraction(claims=[], complete=True, cut=["right"],
                              issues=["text cut off at the right"] if self.said else [])
        return schema.model_validate({})

class Reading(unittest.TestCase):
    def test_answers_are_scored_by_whether_they_ask(self):
        found = asking.cases(CORPUS, {f"{PAGE}-p1"})
        with tempfile.TemporaryDirectory() as folder:
            read = asking.read_all(folder, Client(another_tiling="asked", refinement_depth=0), found)
        self.assertEqual(len(read), sum(len(ts) for pages in found.values() for ts in pages.values()))
        self.assertTrue(all(t["named"] == ["right"] and not t["said"] for t in read.values()))
        asked, today = asking.score(read, "asked"), asking.score(read, "today")
        self.assertEqual((asked["asks_when_cut"], asked["asks_when_whole"]), (1.0, 1.0))
        self.assertFalse(asked["passes"])  # it asks about every tile
        self.assertEqual((today["asks_when_cut"], today["asks_when_whole"]), (0.0, 0.0))
        right = [t for t in read.values() if t["kind"] != "good"]
        self.assertEqual(asked["an_edge_right"], round(sum("right" in t["edges"] for t in right) / len(right), 3))

if __name__ == "__main__":
    unittest.main()
