"""Subjects across documents and the gaps another source fills (crossmatch.py, indexes.given_elsewhere, the look_gaps
lever; docs/plans/single-document-analysis-2026-10-28.md, milestone 7). The owner, 2026-11-07, answering its design:
"All four recommendations look good as a start."."""
import stubs  # noqa: F401 (a clean environment)
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import crossmatch, indexes
from semantic_pdf_diff.dossiers import ELSEWHERE, look_prompt
from semantic_pdf_diff.report import unpacked
from semantic_pdf_diff.schema import SubjectMatch
from stubs import chat_answer, prompt_of, request_body, serving, text_pdf
from test_analyze import run
from test_embed import endpoint
from test_indexes import claim, report

A = [claim("A-1", "ca", "NREL 5-MW baseline turbine", "rated power", "5", "MW"),
     claim("A-2", "ca", "NREL 5-MW baseline turbine", "rotor diameter", "126", "m"),
     claim("A-3", "ca", "blade-pitch controller", "proportional gain", "0.0188", "s"),
     claim("A-4", "ca", "generator", "rated speed", "1173.7", "rpm")]
B = [claim("B-1", "cb", "IEA Wind 15-MW reference turbine", "rated power", "15", "MW"),
     claim("B-2", "cb", "DTU Basic Controller", "proportional gain", "0.0103", "s"),
     claim("B-3", "cb", "monopile", "diameter", "10", "m")]

class Answers:
    """A model answering each subject's request as given ({the asked item's name: answer}), "" else."""
    def __init__(self, said):
        self.said, self.asked = said, []

    def ask(self, prompt, schema, images=(), key=None):
        item = json.loads(prompt[len(crossmatch.PROMPT):])["item"]["name"]
        self.asked.append((item, prompt))
        return schema.model_validate(self.said.get(item, {}))

def data(findings=()):
    return report(A + B, findings, ("a", "b"), mode="proposals")

class Asked(unittest.TestCase):
    def test_a_subject_alone_shown_its_likeliest_counterparts_and_the_judges_verdicts(self):
        d = data([{"a": "A-3", "b": "B-2", "relation": "uncertain"}])
        found = crossmatch.asked(d, indexes.built(d))
        # the source with fewer subjects alone asks (3 to 3: the first); one sharing no name word or property with
        # any of the other's isn't asked (the generator)
        self.assertEqual([(src, s["name"], other, [o["name"] for o in cands]) for src, s, other, cands, _ in found],
                         [("a", "blade-pitch controller", "b", ["DTU Basic Controller"]),  # a property's name
                          ("a", "NREL 5-MW baseline turbine", "b", ["IEA Wind 15-MW reference turbine"])])
        shown = json.loads(found[0][4][len(crossmatch.PROMPT):])
        self.assertEqual(shown["item"], {"name": "blade-pitch controller", "properties": {"proportional gain":
                                                                                         "0.0188 s"}})
        self.assertEqual(shown["candidates"]["B1"]["judged"], {"uncertain": 1})  # evidence, not a match
        self.assertIn("not by values alike", found[0][4])

    def test_answers_checked_one_counterpart_each_and_the_index_joins_them(self):
        d = data()
        model = Answers({"NREL 5-MW baseline turbine": {"match": "B1", "relation": "corresponding",
                                                        "why": "each proposal's turbine"},
                         "blade-pitch controller": {"match": "B7", "relation": "same"}})  # not one shown
        found = crossmatch.read(d, indexes.built(d), model, "proposals", "x")
        self.assertEqual({k: found[k] for k in ("asked", "matched", "taken", "dropped", "failed")},
                         {"asked": 2, "matched": 1, "taken": 0, "dropped": 1, "failed": 0})
        (match,) = found["entries"]
        self.assertEqual((match["kind"], match["source"], match["subject"], match["other_source"], match["other"],
                          match["relation"], match["claims"]),
                         ("match", "a", "NREL 5-MW baseline turbine", "b", "IEA Wind 15-MW reference turbine",
                          "corresponding", []))
        d["commentary"] = {"entries": found["entries"]}
        turbine = next(s for s in indexes.built(d)["subjects"] if s["name"] == "NREL 5-MW baseline turbine")
        self.assertEqual((turbine["matched_by"], sorted(turbine["claims"])),
                         ("model: the corresponding element", ["a", "b"]))
        taken = Answers({"NREL 5-MW baseline turbine": {"match": "B1", "relation": "corresponding"},
                         "blade-pitch controller": {"match": "B1", "relation": "state"}})
        self.assertEqual(crossmatch.read(d, indexes.built(data()), taken, "proposals", "x")["matched"], 2)
        self.assertEqual(SubjectMatch.model_validate({}).match, "")

class Looked(unittest.TestCase):
    def test_a_gap_another_source_fills_is_looked_for_without_its_value(self):
        gap = {"kind": "other_source", "source": "a", "subject": "P101", "property": "NPSH",
               "why": "b gives 3 m (b.pdf, page 2)"}
        text = look_prompt(gap, [])
        self.assertIn(f"Why it was expected: {ELSEWHERE}", text)
        self.assertNotIn("3 m", text)

    def test_a_comparison_matches_what_names_leave_and_looks_for_what_the_other_gives(self):
        state = {"embedded": [], "names": 0, "matched": [], "looked": []}
        serve = endpoint(state)

        def post(handler):
            if not handler.path.endswith("/embeddings"):
                body = request_body(handler)
                prompt = prompt_of(body["messages"][1]["content"])
                if "Compare exactly" in prompt:  # (the stub's "different" would join their properties: none here)
                    return chat_answer(handler, {"relation": "unrelated", "rationale": "stub", "confidence": .9,
                                                 "same_conditions": False})
                if "Two engineering sources describe two proposals" in prompt:
                    state["matched"].append(prompt)
                    return chat_answer(handler, {"match": "B1", "relation": "corresponding", "why": "each turbine"})
                if "found no value of one property" in prompt:
                    state["looked"].append(prompt)
                    given = "property: NPSH" in prompt
                    return chat_answer(handler, {"reads": "given" if given else "not_given",
                                                 "value": "3.1" if given else "", "unit": "m" if given else ""})
                handler.rfile = io.BytesIO(json.dumps(body).encode())
                handler.headers.replace_header("Content-Length", str(len(json.dumps(body).encode())))
            return serve(handler)
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            # (the stub reads one-word items and units; the turbine and the machine share a property's name)
            text_pdf(root / "a.pdf", ["P101 | head | 42 | m", "P101 | flow | 5 | lps",
                                      "turbine | rated power | 5 | MW"])
            text_pdf(root / "b.pdf", ["P101 | head | 44 | m", "P101 | NPSH | 3 | m",
                                      "machine | rated power | 15 | MW"])
            config = root / "settings.json"
            config.write_text(json.dumps({"match_subjects": True, "look_gaps": True, "search_names": False,
                                          "topic_names": False, "vision": False}))
            args = ("compare", root / "a.pdf", root / "b.pdf", "--store", root / "out", "--base-url", url,
                    "--config", config, "--no-situate")
            code, _, _ = run(*args)
            found = json.loads((root / "out" / "report.json").read_text())
            page = unpacked((root / "out" / "report.html").read_text())
            index = (root / "out" / "index.md").read_text()
            again, _, _ = run(*args)
        self.assertEqual(again, code)
        self.assertEqual(len(state["matched"]), 1)  # once, then from the cache
        self.assertEqual(len(state["looked"]), 2)
        self.assertFalse(any("3 m" in p or "5 lps" in p for p in state["looked"]))  # not the other's value
        log = found["commentary"]
        self.assertEqual(log["matched"], {"asked": 1, "matched": 1, "taken": 0, "dropped": 0, "failed": 0})
        self.assertEqual(log["looked"], {"asked": 2, "failed": 0, "skipped": 0})
        # the model's pick is one point of evidence; with the shared property it joins them (link_levels: combined)
        self.assertIn("### turbine (also machine)\nClaims: a.pdf 1; b.pdf 1 (matched by evidence)", index)
        self.assertIn("### Another source gives it", index)
        self.assertIn("- a.pdf: **P101: NPSH** (a.pdf, page 2; b.pdf gives 3 m (b.pdf, page 2)); looked for on a.pdf, "
                      "page 1: it gives 3.1 m", index)  # expected where its first value is; looked for where named
        self.assertIn("- b.pdf: **P101: flow** (b.pdf, page 1; a.pdf gives 5 lps (a.pdf, page 2)); looked for on "
                      "b.pdf, page 1: not given", index)
        self.assertIn("Not given by a.pdf as read; looked for on a.pdf, page 1: it gives 3.1 m", page)  # b's card
        self.assertIn("— <small>looked for on b.pdf, page 1: not given</small>", page)  # the subjects' blank cell

if __name__ == "__main__":
    unittest.main()
