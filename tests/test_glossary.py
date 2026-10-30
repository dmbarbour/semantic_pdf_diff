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
        (heading, text), = glossary.page_blocks(page)
        self.assertEqual(heading, "ABBREVIATIONS")
        self.assertIn("AFF ABOVE FINISHED FLOOR", text)
        self.assertIn("UNO UNLESS NOTED OTHERWISE", text)
        self.assertNotIn("W12X26", text)
        self.assertNotIn("DIMENSIONS", text)

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

    def test_a_long_block_in_parts_at_line_ends(self):
        text = "\n".join(f"T{k} term number {k} of the list" for k in range(400))
        found = glossary.parts(text)
        self.assertGreater(len(found), 2)
        self.assertTrue(all(len(p) <= glossary.PART_CHARS for p in found))
        self.assertEqual("\n".join(found), text)

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
