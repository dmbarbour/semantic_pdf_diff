"""A source's glossary (glossary.py): docs/plans/indexes-and-glossaries-2026-10-29.md, milestone 2. The owner,
2026-10-15: "a glossary for abbreviations, framings, etc.. not as a set of claims, but as metadata for reports,
comparisons, and comprehending claims in context"; 2026-10-30: "Please proceed with the glossary.\""""
import stubs  # noqa: F401 (a clean environment)
import json
import re
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff import glossary
from semantic_pdf_diff.schema import GlossaryTerms
from semantic_pdf_diff.textdocs import parse
from stubs import chat_answer, prompt_of, request_body, serving
from test_analyze import run
from test_embed import endpoint

class Prose(unittest.TestCase):
    def test_definitions_in_passing_their_letters_the_words_initials(self):
        self.assertEqual(glossary.prose("The pump's net positive suction head (NPSH) is 3 m."),
                         [("NPSH", "net positive suction head")])
        self.assertEqual(glossary.prose("Its NPSHr (net positive suction head required) is 3 m."),
                         [("NPSHr", "net positive suction head required")])
        self.assertEqual(glossary.prose("each User Equipment (UE) and a non-return valve (NRV)"),
                         [("UE", "User Equipment"), ("NRV", "non-return valve")])
        self.assertEqual(glossary.prose("the Bureau of Land Management (BLM)"), [("BLM", "Bureau of Land Management")])
        for text in ("the feed pump (P-101) runs", "a valve (see Table 5)", "a flow (FT) of 3", "rated (kW)"):
            self.assertEqual(glossary.prose(text), [], text)

class Blocks(unittest.TestCase):
    def test_a_sheets_abbreviations_its_column_under_its_heading(self):
        doc = pymupdf.open()
        page = doc.new_page(width=1200, height=800)
        page.insert_text((60, 100), "ABBREVIATIONS", fontsize=12)
        for k, line in enumerate(["AFF ABOVE FINISHED FLOOR", "TYP TYPICAL", "UNO UNLESS NOTED OTHERWISE"]):
            page.insert_text((60, 130 + 14 * k), line, fontsize=9)
        page.insert_text((700, 130), "BEAM B-1 W12X26", fontsize=9)  # another column: not the block's
        page.insert_text((60, 400), "GENERAL NOTES", fontsize=12)  # a gap and another heading: not the block's
        page.insert_text((60, 420), "1. ALL DIMENSIONS TO FACE OF FINISH", fontsize=9)
        (heading, text, band, region), = glossary.page_blocks(page)
        self.assertIsNone(band)  # a sheet's block doesn't run on
        self.assertEqual(heading, "ABBREVIATIONS")
        self.assertIn("AFF ABOVE FINISHED FLOOR", text)
        self.assertIn("UNO UNLESS NOTED OTHERWISE", text)
        self.assertNotIn("W12X26", text)
        self.assertNotIn("DIMENSIONS", text)

    def test_a_list_running_past_its_page_read_on_to_the_next_heading(self):
        doc = pymupdf.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 80), "2 References", fontsize=12)
        page.insert_text((72, 100), "Some text about the references, at length.", fontsize=10)
        page.insert_text((72, 600), "3.1 Abbreviations", fontsize=12)
        for k in range(8):
            page.insert_text((72, 622 + 14 * k), f"T{k} term number {k}", fontsize=10)
        page.insert_text((290, 770), "Page 1", fontsize=8)  # its footer: not the list's end
        page = doc.new_page(width=612, height=792)
        page.insert_text((290, 30), "TS 99.999", fontsize=8)  # its header
        for k in range(8, 12):
            page.insert_text((72, 72 + 14 * (k - 8)), f"T{k} term number {k}", fontsize=10)
        page.insert_text((72, 160), "4 Architecture", fontsize=12)
        page.insert_text((72, 180), "The system has parts.", fontsize=10)
        (heading, text, first_page, last_page, region), = glossary.pdf_blocks(doc, [])
        self.assertEqual((heading, first_page, last_page, region), ("3.1 Abbreviations", 1, 2, None))
        self.assertIn("T0 term number 0", text)
        self.assertIn("T11 term number 11", text)
        for left_out in ("Page 1", "TS 99.999", "Architecture", "has parts", "References"):
            self.assertNotIn(left_out, text)

    def test_headings_that_define_terms(self):
        for title in ("Abbreviations", "3.2 Abbreviations", "ABBREVIATIONS:", "Definitions and abbreviations",
                      "Terms, definitions and abbreviations", "List of Acronyms", "Nomenclature", "SYMBOL LEGEND",
                      "Glossary of terms", "Appendix B - Glossary"):
            self.assertTrue(glossary.HEADING.match(title), title)
        for title in ("Abbreviations used for pumps are listed in Table 3", "General notes", "Design basis"):
            self.assertFalse(glossary.HEADING.match(title), title)

    def test_a_text_files_glossary_its_table_as_it_is_its_text_for_the_model(self):
        doc = parse("# Spec\n\nSome text.\n\n## Abbreviations\n\n| Term | Meaning |\n|---|---|\n"
                    "| NPSH | net positive suction head |\n| TDH | total dynamic head |\n\n"
                    "AFF - above finished floor\n\n## Pumps\n\nThe pumps.\n", True)
        (heading, text, lines, rows), = glossary.text_blocks(doc)
        self.assertEqual(heading, "Abbreviations")
        self.assertEqual(rows, [["NPSH", "net positive suction head"], ["TDH", "total dynamic head"]])
        self.assertEqual(text, "AFF - above finished floor")

    def test_a_term_kept_only_where_the_block_has_it_and_its_meaning(self):
        answer = GlossaryTerms.model_validate({"terms": [
            {"term": "AFF", "meaning": "Above finished floor", "kind": "abbreviation"},
            {"term": "TYP", "meaning": "typical", "kind": "convention"},
            {"term": "FFL", "meaning": "finished floor level"},  # not in the block
            {"term": "UNO", "meaning": "unless otherwise noted"}]})  # its meaning reworded
        kept, dropped = glossary.kept(answer, "ABBREVIATIONS\nAFF ABOVE FINISHED FLOOR\nTYP  TYPICAL\n"
                                              "UNO UNLESS NOTED OTHERWISE")
        self.assertEqual(kept, [("AFF", "Above finished floor", "abbreviation"), ("TYP", "typical", "convention")])
        self.assertEqual(dropped, 2)

    def test_a_list_of_tabbed_lines_as_it_is(self):
        text = ("For the purposes of the present document, the following apply.\n"
                + "".join(f"T{k}\tterm number {k}\n" for k in range(6)))
        self.assertEqual(glossary.tabbed(text)[:2], [("T0", "term number 0"), ("T1", "term number 1")])
        self.assertIsNone(glossary.tabbed("A\tb\nsome prose\nmore prose"))

    def test_a_heading_holding_others_left_to_them(self):
        doc = parse("# 3 Abbreviations and Definitions\n\n## 3.1 Abbreviations\n\nAFF - above finished floor\n\n"
                    "## 3.2 Definitions\n\nPump: a machine.\n\n# 4 Pumps\n\nText.\n", True)
        self.assertEqual([b[0] for b in glossary.text_blocks(doc)], ["3.1 Abbreviations", "3.2 Definitions"])

    def test_a_symbol_on_a_sheet_reaches_that_sheet_its_abbreviations_the_document(self):
        f = {"source": "set", "content": "c"}
        reach = lambda *a: glossary.entry(*a[:3], f, "set.pdf, page 4", "LEGEND", "model", *a[3:])  # noqa: E731
        self.assertEqual(reach("W", "WASHER", "symbol", "sheet E-201")["reach"], "sheet")
        self.assertEqual(reach("W", "WASHER", "symbol", "sheet E-201")["sheet"], "sheet E-201")
        self.assertEqual(reach("[circle]", "MOTOR", "term", "sheet E-201")["reach"], "sheet")  # drawn
        self.assertEqual(reach("TYP", "typical", "convention", "sheet G-001")["reach"], "document")  # set-wide
        self.assertEqual(reach("W", "WASHER", "symbol")["reach"], "document")  # not on a sheet
        self.assertNotIn("sheet", reach("TYP", "typical", "convention", "sheet G-001"))

    def test_a_long_block_in_parts_at_line_ends(self):
        text = "\n".join(f"T{k} term number {k} of the list" for k in range(400))
        found = glossary.parts(text)
        self.assertGreater(len(found), 2)
        self.assertTrue(all(len(p) <= glossary.PART_CHARS for p in found))
        self.assertEqual("\n".join(found), text)

def legend_sheet(path):
    """A drawing sheet whose SYMBOL LEGEND has two marks drawn and one lettered, each beside its meaning."""
    doc = pymupdf.open()
    page = doc.new_page(width=1200, height=800)
    page.insert_text((60, 100), "SYMBOL LEGEND", fontsize=12)
    page.draw_circle((70, 126), 6)
    page.draw_line((70, 120), (70, 132))
    page.insert_text((100, 130), "JUNCTION BOX", fontsize=9)
    page.draw_rect((64, 142, 76, 152))
    page.draw_line((64, 142), (76, 152))
    page.draw_line((64, 152), (76, 142))
    page.insert_text((100, 150), "DISCONNECT SWITCH", fontsize=9)
    page.insert_text((66, 170), "W", fontsize=9)
    page.insert_text((100, 170), "WASHER RECEPTACLE", fontsize=9)
    doc.save(path)

class Store:
    """As much of a store as glossary.read asks: a file's origin, and its folder."""
    def __init__(self, folder, path):
        self.folder, self.path = folder, path

    def origin(self, source, path):
        return (str(self.path),)

class Pictured(unittest.TestCase):
    def test_a_drawn_legend_read_from_its_picture_and_its_words(self):
        from semantic_pdf_diff.llm import Client
        from semantic_pdf_diff.settings import Settings
        asked = []

        def post(handler):
            body = request_body(handler)
            parts = body["messages"][1]["content"]
            asked.append((prompt_of(parts), sum(1 for p in parts if p.get("type") == "image_url")))
            return chat_answer(handler, {"terms": [
                {"term": "[circle with a line through it]", "meaning": "JUNCTION BOX", "kind": "symbol"},
                {"term": "W", "meaning": "WASHER RECEPTACLE", "kind": "symbol"},
                {"term": "[square]", "meaning": "MOTOR STARTER", "kind": "symbol"}]})  # not in its words
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            legend_sheet(root / "e-001.pdf")
            data = {"files": [{"source": "set", "path": "e-001.pdf", "content": "sha256:" + "e" * 64 + ".pdf"}],
                    "sections": []}
            client = Client(Settings(base_url=url, retries=0), None)
            found = glossary.read(data, Store(root / "store", root / "e-001.pdf"), client, "analysis", "x")
            pictures = list((root / "store" / "assets").glob("glossary-*.png"))
        asked.sort(key=lambda a: a[1])
        (words, none), (prompt, images) = asked  # its words read as any block's, and its picture asked
        self.assertIn("Read the terms an engineering document defines", words)
        self.assertIn("Read the symbols a drawing's legend defines", prompt)
        self.assertIn("JUNCTION BOX", prompt)
        self.assertEqual((none, images, len(pictures)), (0, 1, 1))
        self.assertEqual([(t["term"], t["meaning"], t["how"]) for t in found["terms"]],
                         [("[circle with a line through it]", "JUNCTION BOX", "picture"),
                          ("W", "WASHER RECEPTACLE", "model")])  # the words' reading kept before the picture's
        self.assertEqual(found["dropped"], 3)  # the picture's made-up square, and the words' two in brackets

    def test_without_vision_its_words_alone(self):
        from semantic_pdf_diff.llm import Client
        from semantic_pdf_diff.settings import Settings
        asked = []

        def post(handler):
            body = request_body(handler)
            parts = body["messages"][1]["content"]
            asked.append(sum(1 for p in parts if isinstance(p, dict) and p.get("type") == "image_url"))
            return chat_answer(handler, {"terms": []})
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            legend_sheet(root / "e-001.pdf")
            data = {"files": [{"source": "set", "path": "e-001.pdf", "content": "sha256:" + "e" * 64 + ".pdf"}],
                    "sections": []}
            client = Client(Settings(base_url=url, retries=0, vision=False), None)
            glossary.read(data, Store(root / "store", root / "e-001.pdf"), client, "analysis", "x")
        self.assertEqual(asked, [0])

def answering(state):
    """test_embed's stub endpoint, a glossary's request answered with each "TERM - meaning" line of its text, and one
    term its text hasn't."""
    serve = endpoint(state)

    def post(handler):
        if handler.path.endswith("/embeddings"):
            return serve(handler)
        body = request_body(handler)
        prompt = prompt_of(body["messages"][1]["content"])
        if "Read the terms an engineering document defines" in prompt:
            state["asked"] = state.get("asked", 0) + 1
            text = prompt.split("TEXT:\n", 1)[1]
            terms = [{"term": m[1], "meaning": m[2], "kind": "abbreviation"}
                     for m in re.finditer(r"^(\w+) - (.+)$", text, re.M)]
            if state.get("short") and len(terms) > 1:  # too many terms for its output: cut short
                return chat_answer(handler, {"terms": terms[:1]}, finish="length")
            return chat_answer(handler, {"terms": terms + [{"term": "XYZ", "meaning": "made up"}]})
        handler.rfile = __import__("io").BytesIO(json.dumps(body).encode())
        handler.headers.replace_header("Content-Length", str(len(json.dumps(body).encode())))
        return serve(handler)
    return post

class Read(unittest.TestCase):
    def analyze(self, settings, **given):
        state = {"embedded": [], "names": 0, **given}
        with tempfile.TemporaryDirectory() as d, serving(answering(state)) as url:
            root = Path(d)
            (root / "spec.md").write_text(
                "# Spec\n\npump | rated power | 10 | kW\n\nThe net positive suction head (NPSH) is checked.\n\n"
                "## Abbreviations\n\n| Term | Meaning |\n|---|---|\n| TDH | total dynamic head |\n\n"
                "AFF - above finished floor\n\nTYP - typical\n\n## Pumps\n\nfan | air flow | 3 | cms\n")
            config = root / "settings.json"
            config.write_text(json.dumps({"search_names": False, "topic_names": False, **settings}))
            code, _, _ = run("analyze", root / "spec.md", "--store", root / "out", "--base-url", url, "--config",
                             config, "--no-situate")
            data = json.loads((root / "out" / "report.json").read_text())
            self.page = (root / "out" / "report.html").read_text()
            self.index = (root / "out" / "index.md").read_text()
        return code, data, state

    def test_an_analysis_reads_its_sources_glossary(self):
        code, data, state = self.analyze({})
        self.assertEqual(code, 0)
        found = data["glossary"]
        self.assertEqual([(t["term"], t["meaning"], t["how"]) for t in found["terms"]],
                         [("AFF", "above finished floor", "model"), ("NPSH", "net positive suction head", "prose"),
                          ("TDH", "total dynamic head", "table"), ("TYP", "typical", "model")])
        self.assertEqual((found["blocks"], found["dropped"], found["failed"]), (1, 1, 0))  # XYZ: not in the block
        self.assertEqual(state["asked"], 1)
        aff = found["terms"][0]
        self.assertEqual((aff["block"], aff["source"], aff["kind"]), ("Abbreviations", "spec.md", "abbreviation"))
        self.assertRegex(aff["where"], r"spec\.md, lines \d+–\d+")
        from semantic_pdf_diff.report import unpacked
        self.assertIn('<button data-view="glossary">Glossary 4</button>', unpacked(self.page))  # shown, and listed
        self.assertRegex(self.index,
                         r"- \*\*NPSH\*\* \(abbreviation\): net positive suction head \(\S*spec\.md, line \d+\)")

    def test_a_part_cut_short_asked_again_in_halves(self):
        code, data, state = self.analyze({}, short=True)
        self.assertEqual(code, 0)
        self.assertEqual([t["term"] for t in data["glossary"]["terms"] if t["how"] == "model"], ["AFF", "TYP"])
        self.assertEqual(state["asked"], 3)  # the block, then its halves

    def test_off_none_read(self):
        code, data, state = self.analyze({"glossary": False})
        self.assertEqual(code, 0)
        self.assertNotIn("glossary", data)
        self.assertNotIn("asked", state)

if __name__ == "__main__":
    unittest.main()
