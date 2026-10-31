"""Each claim's snippet of its source's text (docs/plans/report-snippets-and-bookmarks-2026-10-28.md, milestone 1).
The owner, 2026-10-28: "when a claim comes from text or the PDF text layer, we should include the relevant snippet of
text in the report even when the image is dropped due to lower priority."; 2026-10-31: "Agreed with report snippets
recommendations." (stored with the claim at extraction, out of search at first, on every card that has one)."""
import stubs  # noqa: F401 (a clean environment)
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import levers
from semantic_pdf_diff.quotes import NOTES, row_snippet, snippet
from semantic_pdf_diff.report import snippet_html, unpacked
from stubs import serving
from test_analyze import asked, run

TEXT = ("The plant has three pumps. The feed pump P-101 delivers 350 m3/h at a head of 42 m. Its motor is rated "
        "75 kW. The tank holds 750 m3.")

class Snippet(unittest.TestCase):
    def test_the_sentences_holding_its_quote(self):
        self.assertEqual(snippet(TEXT, "delivers 350  m3/h", limit=80),
                         "The feed pump P-101 delivers 350 m3/h at a head of 42 m.")  # cut at sentences' ends
        self.assertEqual(snippet(TEXT, "delivers 350 m3/h"), TEXT)  # the whole, under the limit
        self.assertEqual(snippet(TEXT, "the shaft speed"), "")  # a quote not in it: none
        long = "x" * 2000 + " the quote here " + "y" * 2000
        self.assertEqual(len(snippet(long, "quote here", limit=100)), 102)  # cut mid-text, "…" either side
        self.assertEqual(snippet(TEXT, "P-101 ... 42 m", limit=80),
                         "The feed pump P-101 delivers 350 m3/h at a head of 42 m.")  # its longest fragment found

    def test_a_table_row_under_its_header_and_never_the_pipelines_notes(self):
        self.assertEqual(snippet('Header: ["Tag", "Capacity", null]\nRow: ["P-101", "350", ""]', "P-101 | 350"),
                         "Tag | Capacity\nP-101 | 350")
        self.assertEqual(row_snippet(["Tag", "Head (m)"], ["P-102", "40"]), "Tag | Head (m)\nP-102 | 40")
        layer = "\n" + levers.LAYER_NOTE + "\nP-101 FEED PUMP 350 GPM"
        self.assertEqual(snippet(layer, "350 GPM"), "P-101 FEED PUMP 350 GPM")
        for note in (levers.LAYER_NOTE, levers.TABLE_CUT_NOTE):  # the notes quotes.NOTES knows, as levers words them
            self.assertTrue(NOTES.fullmatch(note), note)

    def test_shown_with_its_quote_marked_folded_below_a_crop(self):
        e = {"snippet": "Tag | Capacity\nP-101 | 350", "quote": "P-101 | 350"}
        self.assertEqual(snippet_html(e), '<div class="snippet">Tag | Capacity\n<em>P-101</em> | 350</div>')
        self.assertIn('class="snippet folded"', snippet_html(e, folded=True))
        self.assertEqual(snippet_html({"quote": "x"}), "")

    def test_in_full_where_its_crop_was_left_out_and_never_shown_the_judge(self):
        from semantic_pdf_diff.compare import pair_request
        from semantic_pdf_diff.report import Cards
        from semantic_pdf_diff.schema import Evidence, PdfLocator
        from semantic_pdf_diff.settings import Settings
        e = Evidence(id="A-1", content="ca", locator=PdfLocator(page=3, bbox=(0, 0, 1, 1), region="tile", task="t"),
                     entity="P-101", attribute="flow", value="350", unit="gpm", kind="diagram", quote="350 GPM",
                     confidence=.9, snippet="P-101 FEED PUMP 350 GPM").model_dump()
        data = {"evidence": [e], "files": [{"source": "a", "path": "a.pdf", "content": "ca"}], "sections": []}
        cut = Cards(data, lambda e: "<p class='cut'>Crop left out for the report's size budget</p>").card("A-1")
        shown = Cards(data, lambda e: '<span class="shot"><img class="crop"></span>').card("A-1")
        self.assertIn('<div class="snippet">P-101 FEED PUMP <em>350 GPM</em></div><p class=\'cut\'>', cut)
        self.assertIn('<div class="snippet folded"', shown)
        prompt = pair_request(Settings(), "proposals", Evidence(**e), Evidence(**{**e, "id": "B-1"}))[0]
        self.assertNotIn("FEED PUMP", prompt)  # the report's, never the judge's

class Analyzed(unittest.TestCase):
    def test_a_text_claims_snippet_on_its_card_and_not_searched(self):
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(asked(state)) as url:
            root = Path(d)
            (root / "spec.md").write_text("# Plant\n\nThe feed pumps are duty and standby.\n\n"
                                          "pump | rated power | 75 | kW\n\nThe blower runs at night only.\n")
            config = root / "settings.json"
            config.write_text(json.dumps({"search_names": False, "topic_names": False}))
            code, _, _ = run("analyze", root / "spec.md", "--store", root / "out", "--base-url", url, "--config",
                             config, "--no-situate")
            data = json.loads((root / "out" / "report.json").read_text())
            page = unpacked((root / "out" / "report.html").read_text())
            _, found, _ = run("search", "standby", "--store", root / "out")
        self.assertEqual(code, 0)
        (claim,) = data["evidence"]
        self.assertIn("pump | rated power | 75 | kW", claim["snippet"])
        self.assertIn("The feed pumps are duty and standby.", claim["snippet"])  # the sentence before it too
        self.assertIn('<div class="snippet">', page)  # a text claim has no crop: in full
        self.assertIn("0 claims found", found)  # a snippet's words aren't searched (design question 2)

if __name__ == "__main__":
    unittest.main()
