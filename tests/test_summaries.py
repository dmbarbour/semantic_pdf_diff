"""Cited summaries (summaries.py; docs/plans/single-source-outputs-2026-09-23.md, milestone 4): a source's parts
summarized from their claims alone, each sentence citing the claims it rests on, checked against them by code. The
owner, 2026-11-06: "This seems like a good design for milestone 4."; "Claims only"; a sentence failing its check kept
and marked; "Yes, with provenance." (the export)."""
import stubs  # noqa: F401 (a clean environment)
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import indexes, summaries
from semantic_pdf_diff.report import Cards, summaries_html, unpacked
from semantic_pdf_diff.schema import Summary
from stubs import Asks, Board, chat_answer, prompt_of, request_body, serving
from test_analyze import run
from test_embed import endpoint
from test_indexes import claim, report

PUMPS = [claim("A-1", "ca", "P-101 pump", "rated power", "75", "kW", page=2),
         claim("A-2", "ca", "P-101 pump", "head", "42", "m", page=2),
         claim("A-3", "ca", "P-102 pump", "rated power", "1,000", "W", page=3),
         claim("A-4", "ca", "P-102 pump", "head", "40", "m", page=3)]

def data(headed=False):
    found = report([dict(c) for c in PUMPS])
    found["sections"] = ([{"content": "ca", "id": "s1", "heading_path": ["4 Pumps"], "first_page": 2, "last_page": 3}]
                         if headed else [{"content": "ca", "id": "s1", "heading_path": [], "first_page": 1,
                                          "last_page": 9}])
    for e in found["evidence"]:
        e["section"] = "s1"
    return found

class Checked(unittest.TestCase):
    def test_a_sentence_cites_claims_given_and_states_only_their_numbers(self):
        named = {"C1": PUMPS[0], "C2": PUMPS[2]}
        answer = Summary.model_validate({"sentences": [
            {"text": "P-101 is rated 75 kW (C1), P-102 1000 W.", "cites": ["C2"]},  # its names written in count
            {"text": "Each runs at 1,750 rpm.", "cites": ["C1", "C9"]},  # C9 isn't one given
            {"text": "Both are submersible.", "cites": []}]})
        found = summaries.written(answer, named)
        self.assertEqual([(s["text"], s["claims"], s["check"]) for s in found], [
            ("P-101 is rated 75 kW, P-102 1000 W.", ["A-3", "A-1"], ""),
            ("Each runs at 1,750 rpm.", ["A-1"], "states 1750, which the claims it cites don't give"),
            ("Both are submersible.", [], "cites no claim it was given")])

class Units(unittest.TestCase):
    def test_a_headless_section_across_pages_page_by_page_a_headed_one_whole(self):
        d = data()
        self.assertEqual([(k, key, title, [c["id"] for c in claims])
                          for k, key, title, claims in summaries.units(d, indexes.built(d), ["sections"])],
                         [("sections", ["ca", "s1", 2], "page 2", ["A-1", "A-2"]),
                          ("sections", ["ca", "s1", 3], "page 3", ["A-3", "A-4"])])
        d = data(headed=True)
        self.assertEqual([(key, title) for _, key, title, _ in summaries.units(d, indexes.built(d), ["sections"])],
                         [(["ca", "s1", None], "4 Pumps")])
        self.assertEqual([title for _, _, title, _ in summaries.units(d, indexes.built(d), ["subjects"])],
                         ["P-101 pump", "P-102 pump"])

    def test_a_files_summary_from_its_sections_citing_their_claims(self):
        d = data()
        board = Board()
        found = summaries.read(d, indexes.built(d), Asks(), "analysis", "x", ["files"], board)
        self.assertEqual(board.drawn(), [("summaries", 2, "summaries", 2), ("summaries of files", 1, "summaries", 1)])
        self.assertEqual((found["files"], found["asked"], found["failed"]),
                         ([{"key": ["ca"], "title": "a.pdf", "sentences": []}], 3, 0))  # its sections' asked first
        self.assertNotIn("sections", found)  # asked, not kept: only the kinds named
        prompt, named = summaries.of_parts("one document, a.pdf,", "a.pdf", [
            {"title": "page 2", "sentences": [{"text": "P-101 gives 75 kW.", "claims": ["A-1"], "check": ""}]},
            {"title": "page 3", "sentences": [{"text": "P-102 gives 1000 W.", "claims": ["A-3"], "check": ""}]}],
            {e["id"]: e for e in d["evidence"]})
        self.assertIn('"P-101 gives 75 kW. (C1)"', prompt)
        self.assertEqual({n: c["id"] for n, c in named.items()}, {"C1": "A-1", "C2": "A-3"})

class Shown(unittest.TestCase):
    def test_each_sentence_followed_by_its_claims_one_not_borne_out_marked(self):
        d = data(headed=True)
        found = {"sections": [{"key": ["ca", "s1", None], "title": "4 Pumps", "sentences": [
                    {"text": "P-101 is rated 75 kW.", "claims": ["A-1"], "check": ""},
                    {"text": "Each runs at 1,750 rpm.", "claims": ["A-2"],
                     "check": "states 1750, which the claims it cites don't give"}]}],
                 "files": [{"key": ["ca"], "title": "a.pdf", "sentences": [
                     {"text": "Two pumps.", "claims": ["A-1", "A-3"], "check": ""}]}]}
        shown, count = summaries_html(found, Cards(d), lambda c: "a / a.pdf")
        self.assertEqual(count, 2)
        self.assertIn('<h2>a / a.pdf</h2><p>Two pumps. <a href="#claim=A-1" title="page 2: 75 kW">[1]</a> '
                      '<a href="#claim=A-3" title="page 3: 1,000 W">[2]</a></p>', shown)
        self.assertIn('<span class="warning">Each runs at 1,750 rpm.</span> <small class="warning">(not borne out by '
                      'the claims it cites: states 1750, which the claims it cites don&#x27;t give)</small>', shown)
        self.assertEqual(summaries_html({}, Cards(d), str), ('', 0))

class Exported(unittest.TestCase):
    def test_a_summary_a_chunk_labelled_with_its_model_and_the_claims_it_cites(self):
        # the owner, 2026-11-06, of summaries in the export: "Yes, with provenance."
        from semantic_pdf_diff import export
        d = data(headed=True)
        d["settings"] = {"model": "gemma-4"}
        d["summaries"] = {"sections": [{"key": ["ca", "s1", None], "title": "4 Pumps", "sentences": [
            {"text": "P-101 is rated 75 kW at 42 m.", "claims": ["A-1", "A-2"], "check": ""},
            {"text": "It runs at 1,750 rpm.", "claims": ["A-1"],
             "check": "states 1750, which the claims it cites don't give"}]}]}
        files = {f["content"]: f for f in d["files"]}
        (title, text), = export.summary_chunks(d, files)
        self.assertEqual(title, "Summary: 4 Pumps")
        self.assertIn('kind: "summary, written by the model"\nmodel: "gemma-4"\nfiles: ["a.pdf"]', text)
        self.assertIn("P-101 is rated 75 kW at 42 m. [1, 2] It runs at 1,750 rpm. [1] (not borne out by the claims it "
                      "cites: states 1750, which the claims it cites don't give)", text)
        self.assertIn("[1] P-101 pump rated power: 75 kW [a.pdf, page 2]", text)
        self.assertEqual(export.runs([1, 2, 3, 4, 7, 9, 10]), "[1–4, 7, 9, 10]")

class Analyzed(unittest.TestCase):
    def test_an_analysis_writes_the_summaries_it_is_asked_for(self):
        state = {"embedded": [], "names": 0}
        serve = endpoint(state)

        def post(handler):
            if not handler.path.endswith("/embeddings"):
                body = request_body(handler)
                prompt = prompt_of(body["messages"][1]["content"])
                if prompt.startswith("Summarize"):
                    state.setdefault("asked", []).append(prompt)
                    return chat_answer(handler, {"sentences": [{"text": "The pumps are rated 10 and 12 kW.",
                                                                "cites": ["C1", "C2"]}]})
                handler.rfile = io.BytesIO(json.dumps(body).encode())
                handler.headers.replace_header("Content-Length", str(len(json.dumps(body).encode())))
            return serve(handler)
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            (root / "pumps.md").write_text("# Pumps\n\npump1 | rated power | 10 | kW\n\n"
                                           "pump2 | rated power | 12 | kW\n")
            config = root / "settings.json"
            config.write_text(json.dumps({"summaries": ["sections"], "second_pass": False, "search_names": False,
                                          "topic_names": False}))
            args = ("analyze", root / "pumps.md", "--store", root / "out", "--base-url", url, "--config", config,
                    "--no-situate")
            code, _, _ = run(*args)
            found = json.loads((root / "out" / "report.json").read_text())
            page = unpacked((root / "out" / "report.html").read_text())
            again, _, _ = run(*args)
        self.assertEqual((code, again), (0, 0))
        self.assertEqual(len(state["asked"]), 1)  # one section, then from the cache
        self.assertEqual([(s["title"], [x["check"] for x in s["sentences"]]) for s in found["summaries"]["sections"]],
                         [("Pumps", [""])])
        self.assertIn('<button data-view="summaries" title="Written by the model, each sentence citing its claims">'
                      'Summaries 1</button>', page)

if __name__ == "__main__":
    unittest.main()
