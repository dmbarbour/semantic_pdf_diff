"""The another_tiling lever: a partial tile asking for it is read again under the page's next candidate cut."""
import stubs  # noqa: F401 (a clean environment)
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff import retiling
from semantic_pdf_diff.context import Context
from semantic_pdf_diff.schema import Extraction, edges
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.tiling import cut_by

CORPUS = Path(__file__).resolve().parent.parent / "benchmarks/controlled/docs"
WIDE = ("lcc-s1-wide-letter", 0)  # a grid of six tiles, each cutting lines; XY-cut holds them in two

def said(*issues, cut=()):
    return {"row": {"issues": list(issues)}, "claims": (), "cut": list(cut)}

class Asking(unittest.TestCase):
    def test_an_answer_names_edges_in_words_or_a_list(self):
        self.assertEqual(edges(["Bottom", "right edge"]), ["bottom", "right"])
        self.assertEqual(edges("the upper and left edges"), ["top", "left"])
        self.assertEqual(Extraction.model_validate({"claims": [], "complete": False, "cut": "right"}).cut, ["right"])
        self.assertEqual(Extraction.model_validate({"claims": [], "complete": True}).cut, [])

    def test_said_reads_the_issues_asked_the_edges_too(self):
        self.assertTrue(retiling.asks(said("The table is cut off at the bottom of the image"), "said"))
        self.assertTrue(retiling.asks(said("Text truncated on the right"), "said"))
        self.assertFalse(retiling.asks(said("The legend is ambiguous"), "said"))
        self.assertFalse(retiling.asks(said(cut=["right"]), "said"))
        self.assertFalse(retiling.asks(said("Cut at the image's right edge"), "said"))  # the edges' own note
        self.assertTrue(retiling.asks(said(cut=["right"]), "asked"))
        self.assertTrue(retiling.asks(said(), "measures"))
        continued = {"row": {"task": "tile:p1:0-c3", "issues": ["text cut off"]}, "claims": (), "cut": ["right"]}
        self.assertFalse(any(retiling.asks(continued, mode) for mode in ("measures", "said", "asked")))  # full

    def test_the_edges_a_tile_cuts_by(self):
        found, cut = cut_by((100, 100, 200, 200), [(90, 120, 150, 130), (150, 150, 160, 210), (120, 120, 130, 130)])
        self.assertEqual((found, len(cut)), (["bottom", "left"], 2))

class Retiled(unittest.TestCase):
    def reader(self, where=WIDE, **settings):
        stem, number = where
        doc = pymupdf.open(CORPUS / f"{stem}.pdf")
        self.addCleanup(doc.close)
        s = Settings(**{**stubs.TILING_BEFORE, "another_tiling": "said", **settings})
        reader = Context(doc, s)
        page = doc[number]
        return s, reader, page, [r for r in s.visual_regions(reader, page, number) if r[0].startswith("tile")]

    def test_the_other_cuts_tiles_hold_what_a_tile_cuts_each_read_once_a_page(self):
        s, reader, page, tiles = self.reader()
        self.assertEqual(retiling.other_cut(s, reader, page)["how"], "xycut")
        lines = [tuple(b) for b, _ in reader.lines(page)]
        first = retiling.retiled(s, reader, page, *tiles[0][:2], said("cut off"))
        self.assertEqual([t for t, _ in first], ["tile:xycut0", "tile:xycut1"])
        for cut in cut_by(tuple(tiles[0][1]), lines)[1]:
            self.assertTrue(any(cut_by(tuple(r), [cut])[1] == [] for _, r in first))
        self.assertEqual(retiling.retiled(s, reader, page, *tiles[1][:2], said("cut off")), [])  # read already

    def test_the_tags_dont_depend_on_which_tile_asks_first(self):
        orders = []
        for order in (lambda t: t, lambda t: t[::-1]):
            s, reader, page, tiles = self.reader()
            orders.append(sorted(x for tag, r, _ in order(tiles)
                                 for x in retiling.retiled(s, reader, page, tag, r, said("cut off")) or ()))
        self.assertEqual(orders[0], orders[1])

    def test_a_tile_cutting_nothing_is_halved(self):
        s, reader, page, tiles = self.reader(("ahu-schematic-s1-clean", 0))
        self.assertIsNone(retiling.retiled(s, reader, page, *tiles[0][:2], said("cut off")))
        self.assertEqual([t for t, *_ in s.refined_tile(reader, page, tiles[0][0], tiles[0][1], said("cut off"))],
                         ["tile:0-r0", "tile:0-r1"])

    def test_off_or_not_asking_halves(self):
        for mode, done in (("off", said("cut off")), ("said", said("The legend is ambiguous"))):
            s, reader, page, tiles = self.reader()
            s = s.model_copy(update={"another_tiling": mode})
            self.assertEqual([t for t, *_ in s.refined_tile(reader, page, *tiles[0][:2], done)],
                             ["tile:0-r0", "tile:0-r1"])

class Job(unittest.TestCase):
    def test_a_partial_tile_naming_a_cut_is_read_again_under_another_cut(self):
        from semantic_pdf_diff.jobs import extract_pdf

        class Client(stubs.Recorder):
            prompts = []

            def answer(self, prompt, schema, images, key):
                if schema is Extraction and key[3].startswith("tile:"):
                    self.prompts.append((key[3], prompt))
                    return Extraction(claims=[], complete=key[3] != "tile:p1:0", cut=["right"])
                return Extraction(claims=[], complete=True) if schema is Extraction else schema.model_validate({})
        with tempfile.TemporaryDirectory() as d:
            doc = pymupdf.open(CORPUS / f"{WIDE[0]}.pdf")
            path = Path(d) / "t.pdf"
            doc.select([WIDE[1]])
            doc.save(path)
            doc.close()
            client = Client(**{**stubs.TILING_BEFORE, "another_tiling": "asked"}, refinement_depth=1)
            _, coverage = extract_pdf(path, "sha256:" + "c" * 64 + ".pdf", Path(d), client)
        tasks = [r["task"] for r in coverage if r["task"].startswith("tile")]
        self.assertIn("tile:p1:xycut0", tasks)
        self.assertFalse([t for t in tasks if "-r" in t])
        (row,) = [r for r in coverage if r["task"] == "tile:p1:0"]
        self.assertIn("Cut at the image's right edge", row["issues"])
        self.assertTrue(all(retiling.RULE in p for _, p in Client.prompts))

if __name__ == "__main__":
    unittest.main()
