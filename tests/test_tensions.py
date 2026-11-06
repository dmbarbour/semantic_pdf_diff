"""Tensions (tensions.py; docs/plans/single-document-analysis-2026-10-28.md, milestone 4): a subject's claims hard to
hold together on engineering grounds, by level, what would reconcile them looked for in the source by code. The owner,
2026-11-06: "We'll need to also look for qualitative inconsistencies, with levels of suspicion. E.g. claiming
low-alloy steel combined with a claim of corrosion resistance without a clear mitigating factor."""
import stubs  # noqa: F401 (a clean environment)
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import indexes, tensions
from semantic_pdf_diff.report import Cards, suspects_html, unpacked
from semantic_pdf_diff.schema import Tensions
from stubs import chat_answer, prompt_of, request_body, serving
from test_analyze import run
from test_embed import endpoint
from test_indexes import claim, report

HATCH = [claim("A-1", "ca", "Access hatch frame", "material", "low-alloy steel", "", page=2),
         claim("A-2", "ca", "Access hatch frame", "corrosion resistance", "resists the wet well's hydrogen sulfide",
               "", page=2),
         claim("A-3", "ca", "Wet well", "working volume", "9,000", "gal", page=3),
         claim("A-4", "ca", "Wet well", "diameter", "12", "ft", page=3)]

def data(galvanized=False):
    found = report([dict(c) for c in HATCH])
    if galvanized:  # the clean twin's: what reconciles it, said elsewhere in the source
        found["evidence"].append(claim("A-5", "ca", "Access hatch frame", "finish", "hot-dip galvanised after "
                                                                                     "fabrication", "", page=5))
    return found

def answer(*found):
    return Tensions.model_validate({"tensions": list(found)})

STEEL = {"claims": ["C1", "C2"], "level": "reason", "why": "C1 isn't corrosion-resistant on its own",
         "reconcile": ["hot-dip galvanized", "epoxy coating"]}

class Asked(unittest.TestCase):
    def test_a_subject_holding_a_word_value_is_asked_with_the_reviewers_concerns(self):
        d = data()
        found = tensions.asked(d, indexes.built(d))
        self.assertEqual([subject for _, subject, _, _ in found], ["Access hatch frame"])  # the wet well's are numbers
        _, _, named, dossier = found[0]
        text = tensions.prompt(dossier, ["carbon steel in wet service needs a coating or an allowance"])
        self.assertIn("Find claims hard to hold together on engineering grounds", text)
        self.assertIn("A reviewer asks you to watch for these too:\n- carbon steel in wet service needs a coating",
                      text)
        self.assertIn('"value": "low-alloy steel"', text)
        self.assertNotIn("reviewer", tensions.prompt(dossier))  # none given: the model's own knowledge

    def test_only_what_the_dossier_bears_out_logged_and_reconciled_where_the_source_says_so(self):
        for galvanized, reconciled in ((False, []), (True, ["A-5"])):
            d = data(galvanized)
            _, subject, named, _ = tensions.asked(d, indexes.built(d))[0]
            entries, dropped = tensions.logged(
                answer(STEEL, {**STEEL, "claims": ["C9"]}, {**STEEL, "level": "maybe"}, {**STEEL, "why": " "}),
                "a", subject, named, ("tensions", "analysis", "x"), tensions.places(d, "a"))
            self.assertEqual(dropped, 3)
            self.assertEqual([(e["kind"], e["claims"], e["relation"], e.get("reconciled", [])) for e in entries],
                             [("tension", ["A-1", "A-2"], "reason", reconciled)])
            self.assertEqual(entries[0]["why"], "“low-alloy steel” (page 2) isn't corrosion-resistant on its own")

    def test_reconciling_words_are_a_words_forms_not_any_word(self):
        said = [("A", "claim", set(tensions._words("hot-dip galvanised and epoxy coated after fabrication")))]
        self.assertEqual(tensions.found(["hot-dip galvanized"], said), [("A", "claim")])
        self.assertEqual(tensions.found(["epoxy coating"], said), [("A", "claim")])
        self.assertEqual(tensions.found(["cathodic protection"], said), [])
        self.assertEqual(tensions.found(["the", "of a"], said), [])  # no word asked for

class Shown(unittest.TestCase):
    def test_the_cards_and_the_suspects_view(self):
        d = data()
        _, subject, named, _ = tensions.asked(d, indexes.built(d))[0]
        entries, _ = tensions.logged(answer(STEEL, {"claims": ["C2"], "level": "look", "why": "a rare claim",
                                                    "reconcile": ["stainless steel"]}),
                                     "a", subject, named, ("tensions", "analysis", "x"), tensions.places(d, "a"))
        d["commentary"] = {"entries": entries}
        card = Cards(d).card("A-1")
        self.assertIn("Needs a reason the document doesn&#x27;t give with page 2: resists the wet well&#x27;s hydrogen "
                      "sulfide: “low-alloy steel” (page 2) isn&#x27;t corrosion-resistant on its own (nothing that "
                      "reconciles it found in the document)", card)
        shown, open_ = suspects_html(entries, Cards(d))
        self.assertEqual(open_, 2)
        rows = shown.split("<tbody>")[1]
        self.assertLess(rows.index("Needs a reason"), rows.index("Worth a look (low priority)"))  # by level
        self.assertIn('<a href="#claim=A-1">page 2: low-alloy steel</a>', rows)
        self.assertIn('data-claims="A-1 A-2"', rows)  # found by the search as its claims are
        self.assertEqual(suspects_html([], Cards(d)), ('', 0))

class Analyzed(unittest.TestCase):
    def test_an_analysis_asks_each_subject_once_when_on(self):
        state = {"embedded": [], "names": 0}
        serve = endpoint(state)

        def post(handler):
            if not handler.path.endswith("/embeddings"):
                body = request_body(handler)
                prompt = prompt_of(body["messages"][1]["content"])
                if "Find claims hard to hold together" in prompt:
                    state.setdefault("asked", []).append(prompt)
                    return chat_answer(handler, {"tensions": [{"claims": ["C1", "C2"], "level": "conflict",
                                                               "why": "two materials", "reconcile": ["clad"]}]})
                if "SOURCE DATA:\n" in prompt:  # the frame's two claims, words (the shared stub reads numbers)
                    return chat_answer(handler, {"claims": [
                        {"entity": "frame", "attribute": "material", "value": "low-alloy steel", "unit": "",
                         "kind": "text", "quote": "low-alloy steel", "confidence": .9},
                        {"entity": "frame", "attribute": "finish", "value": "bare", "unit": "", "kind": "text",
                         "quote": "finish is bare", "confidence": .9}], "complete": True, "issues": []})
                handler.rfile = io.BytesIO(json.dumps(body).encode())
                handler.headers.replace_header("Content-Length", str(len(json.dumps(body).encode())))
            return serve(handler)
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            (root / "frame.md").write_text("# Frame\n\nThe frame is low-alloy steel. Its finish is bare.\n")
            config = root / "settings.json"
            config.write_text(json.dumps({"tensions": True, "reviewer_concerns": ["bare steel outdoors"],
                                          "second_pass": False, "search_names": False, "topic_names": False}))
            args = ("analyze", root / "frame.md", "--store", root / "out", "--base-url", url, "--config", config,
                    "--no-situate")
            code, _, _ = run(*args)
            found = json.loads((root / "out" / "report.json").read_text())
            page = unpacked((root / "out" / "report.html").read_text())
            again, _, _ = run(*args)
        self.assertEqual((code, again), (0, 0))
        self.assertEqual(len(state["asked"]), 1)  # once, then from the cache
        self.assertIn("- bare steel outdoors", state["asked"][0])
        log = found["commentary"]
        self.assertEqual((log["tensions"]["subjects"], log["tensions"]["failed"]), (1, 0))
        self.assertEqual([(e["kind"], e["relation"]) for e in log["entries"]], [("tension", "conflict")])
        self.assertIn('<button data-view="suspects" title="Claims hard to hold together, not reconciled">Suspects 1'
                      '</button>', page)

if __name__ == "__main__":
    unittest.main()
