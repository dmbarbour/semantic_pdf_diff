"""The second pass (dossiers.py; docs/plans/single-document-analysis-2026-10-28.md, milestone 3): each subject's
claims read together, what's learnt kept as a log beside the claims. The owner, 2026-10-28: "a second pass [...] where
claims are analyzed in context"; 2026-10-31: "Agree with all second-pass recommendations." (the subject's dossier, a
stage, text first)."""
import stubs  # noqa: F401 (a clean environment)
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import dossiers, indexes
from semantic_pdf_diff.report import unpacked
from semantic_pdf_diff.schema import SecondPass
from stubs import chat_answer, prompt_of, request_body, serving
from test_analyze import run
from test_embed import endpoint
from test_indexes import claim, report

PUMPS = [claim("A-1", "ca", "P-101 pump", "head", "42", "m", page=2), claim("A-2", "ca", "P-101 pump", "head", "45",
                                                                          "m", page=7),
         claim("A-3", "ca", "P-101 pump", "rated power", "75", "kW", page=2),
         claim("A-4", "ca", "P-102 pump", "head", "40", "m", page=3), claim("A-5", "ca", "P-102 pump", "NPSH", "3", "m",
                                                                          page=3),
         claim("A-6", "ca", "P-103 pump", "NPSH", "4", "m", page=4)]

def data():
    found = report(PUMPS, sections=[{"content": "ca", "id": "s1", "heading_path": ["4 Pumps"],
                                     "about": "The feed pumps' duty points."}])
    for e in found["evidence"]:
        e["section"] = "s1"
    found["evidence"][0]["snippet"] = "The feed pump P-101 delivers 350 m3/h at a head of 42 m at 60 Hz."
    return found

class Dossier(unittest.TestCase):
    def test_a_subjects_claims_named_with_their_passages_sections_abouts_and_siblings(self):
        d = data()
        made = dossiers.dossiers(d, indexes.built(d))
        self.assertEqual([(source, subject, sorted(named)) for source, subject, named, _ in made],
                         [("a", "P-101 pump", ["C1", "C2", "C3"]), ("a", "P-102 pump", ["C1", "C2"])])  # P-103: one
        dossier = made[0][3]
        self.assertEqual([c["value"] for c in dossier["claims"]], ["42", "75", "45"])  # where they're read
        self.assertEqual(dossier["claims"][0]["passage"], d["evidence"][0]["snippet"])
        self.assertEqual(dossier["claims"][0]["section"], "4 Pumps")
        self.assertEqual(dossier["about"], ["The feed pumps' duty points."])
        self.assertEqual(dossier["siblings"], {"kind": "pump (P)", "items": 3, "they give, it doesn't": ["NPSH"]})
        self.assertIn("Read one subject's claims from an engineering source together", dossiers.prompt(dossier))

    def test_only_what_the_dossier_bears_out_logged(self):
        d = data()
        _, subject, named, dossier = dossiers.dossiers(d, indexes.built(d))[0]
        answer = SecondPass.model_validate({
            "context": [{"claim": "C2", "adds": "condition", "text": "at 60 Hz", "quote": "at 60 Hz"},
                        {"claim": "C1", "adds": "scope", "text": "phase 2", "quote": "for phase 2"}],  # not its words
            "relations": [{"a": "C1", "b": "C3", "relation": "contradicts", "why": "42 m and 45 m at one point"},
                          {"a": "C1", "b": "C9", "relation": "restates"}, {"a": "C1", "b": "C2", "relation": "rhymes"}],
            "suspicions": [{"claim": "C3", "kind": "misread", "why": "C3 against C1"}],
            "inferences": [{"text": "about 25 kW hydraulic", "claims": ["C1", "C2"]}, {"text": "x", "claims": ["C7"]}],
            "missing": [{"property": "NPSH", "why": "its siblings give it"}]})
        entries, dropped = dossiers.logged(answer, "a", subject, named, dossier, ("second", "analysis", "x"))
        self.assertEqual(dropped, 4)
        self.assertEqual([(e["kind"], e["claims"], e.get("relation", "")) for e in entries],
                         [("context", ["A-3"], ""), ("relation", ["A-1", "A-2"], "contradicts"),
                          ("suspicion", ["A-2"], "misread"), ("inference", ["A-1", "A-3"], ""), ("missing", [], "")])
        self.assertEqual(len({e["id"] for e in entries}), 5)
        self.assertEqual(entries[2]["why"], "“45” (page 7) against “42” (page 2)")  # its names as a reader finds them

    def test_the_index_and_the_cards_say_what_it_found(self):
        from semantic_pdf_diff.report import Cards
        d = data()
        d["commentary"] = {"entries": [
            {"kind": "relation", "relation": "contradicts", "source": "a", "subject": "P-101 pump",
             "claims": ["A-1", "A-2"], "why": "42 m and 45 m at one point", "id": "c-1", "key": []},
            {"kind": "missing", "source": "a", "subject": "P-101 pump", "claims": [], "text": "NPSH",
             "why": "its siblings give it", "id": "c-2", "key": []}]}
        index = indexes.built(d)
        self.assertEqual([(x["subject"], x["said"], x["where"]) for x in index["inconsistencies"]],
                         [("P-101 pump", ["42 m", "45 m"], ["a.pdf, page 2", "a.pdf, page 7"])])
        likely = [g for g in index["gaps"] if g["kind"] == "likely"]
        self.assertEqual([(g["subject"], g["property"], g["where"]) for g in likely],
                         [("P-101 pump", "NPSH", "a.pdf, page 2")])
        card = Cards(d).card("A-1")
        self.assertIn("Read with its subject's other claims", card)
        self.assertIn("Contradicts page 7: 45 m (42 m and 45 m at one point)", card)

class Analyzed(unittest.TestCase):
    def test_an_analysis_reads_each_subjects_claims_together_once(self):
        state = {"embedded": [], "names": 0}
        serve = endpoint(state)

        def post(handler):
            if not handler.path.endswith("/embeddings"):
                body = request_body(handler)
                prompt = prompt_of(body["messages"][1]["content"])
                if "Read one subject's claims" in prompt:
                    state["asked"] = state.get("asked", 0) + 1
                    return chat_answer(handler, {"relations": [{"a": "C1", "b": "C2", "relation": "contradicts",
                                                                "why": "two heads"}],
                                                 "missing": [{"property": "NPSH", "why": "a sibling gives it"}]})
                handler.rfile = io.BytesIO(json.dumps(body).encode())
                handler.headers.replace_header("Content-Length", str(len(json.dumps(body).encode())))
            return serve(handler)
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            (root / "pumps.md").write_text("# Pumps\n\nP101 | head | 42 | m\n\nP101 | head | 45 | m\n\n"
                                           "P102 | head | 40 | m\n\nP103 | NPSH | 3 | m\n")  # (the stub's names)
            config = root / "settings.json"
            config.write_text(json.dumps({"second_pass": True, "search_names": False, "topic_names": False}))
            args = ("analyze", root / "pumps.md", "--store", root / "out", "--base-url", url, "--config", config,
                    "--no-situate")
            code, _, _ = run(*args)
            found = json.loads((root / "out" / "report.json").read_text())
            page = unpacked((root / "out" / "report.html").read_text())
            index = (root / "out" / "index.md").read_text()
            again, _, _ = run(*args)
        self.assertEqual((code, again), (0, 0))
        self.assertEqual(state["asked"], 1)  # P-101 alone has two claims; asked once, then from the cache
        log = found["commentary"]
        self.assertEqual((log["subjects"], log["dropped"], log["failed"]), (1, 0, 0))
        self.assertEqual([e["kind"] for e in log["entries"]], ["relation", "missing"])
        self.assertIn('<button data-view="inconsistencies">Inconsistencies 1</button>', page)
        self.assertIn("## Inconsistencies", index)
        self.assertIn("### Likely missing, read together", index)

if __name__ == "__main__":
    unittest.main()
