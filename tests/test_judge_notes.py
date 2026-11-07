"""The second pass in comparisons (the judge_notes lever; docs/plans/single-document-analysis-2026-10-28.md,
milestone 6): each source's subjects read together before judging, and the judge shown what that noted of each claim.
The owner, 2026-10-28: "A lot of comparisons don't make sense because they're compared without enough context";
2026-11-07: "Proceed with the recommended path."."""
import stubs  # noqa: F401 (a clean environment)
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff.compare import NOTED, pair_request
from semantic_pdf_diff.schema import Evidence, PdfLocator
from semantic_pdf_diff.settings import Settings
from stubs import chat_answer, prompt_of, request_body, serving
from test_analyze import run
from test_embed import endpoint

def claim(cid, value):
    return Evidence(id=cid, content="sha256:" + "a" * 64 + ".pdf", locator=PdfLocator(page=1, bbox=(0, 0, 1, 1),
                    region="text", task="t"), entity="pump", attribute="capacity", value=value, unit="gpm",
                    kind="text", quote=f"{value} gpm", confidence=.9)

class Shown(unittest.TestCase):
    def test_a_claims_notes_shown_the_judge_only_when_asked(self):
        a, b = claim("A-1", "1,200"), claim("B-1", "1,250")
        notes = {"A-1": ["Read together, differs by condition from 2,410 gpm (a.pdf, page 3): at runout"]}
        prompt = pair_request(Settings(judge_notes=True), "proposals", a, b, notes=notes)[0]
        self.assertIn(NOTED, prompt)
        self.assertIn('"noted": ["Read together, differs by condition from 2,410 gpm (a.pdf, page 3): at runout"]',
                      prompt)
        self.assertNotIn('"noted"', prompt.split("\nB=")[1])  # B has none
        self.assertNotIn("noted", pair_request(Settings(), "proposals", a, b, notes=notes)[0])
        self.assertNotIn("noted", pair_request(Settings(judge_notes=True), "proposals", a, b)[0])  # none noted

class Compared(unittest.TestCase):
    def test_a_comparison_reads_its_subjects_together_before_judging(self):
        state = {"embedded": [], "names": 0, "judged": []}
        serve = endpoint(state)

        def post(handler):
            if not handler.path.endswith("/embeddings"):
                body = request_body(handler)
                prompt = prompt_of(body["messages"][1]["content"])
                if "Read one subject's claims" in prompt:
                    state["read"] = state.get("read", 0) + 1
                    return chat_answer(handler, {"relations": [{"a": "C1", "b": "C2",
                                                                "relation": "differs_by_condition",
                                                                "why": "the second at runout"}]})
                if "Compare exactly" in prompt:
                    state["judged"].append(prompt)
                handler.rfile = io.BytesIO(json.dumps(body).encode())
                handler.headers.replace_header("Content-Length", str(len(json.dumps(body).encode())))
            return serve(handler)
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            (root / "a.md").write_text("# Pumps\n\npump | capacity | 1200 | gpm\n\npump | capacity | 2410 | gpm\n")
            (root / "b.md").write_text("# Pumps\n\npump | capacity | 1250 | gpm\n")
            config = root / "settings.json"
            config.write_text(json.dumps({"judge_notes": True, "search_names": False, "topic_names": False}))
            code, _, _ = run("compare", root / "a.md", root / "b.md", "--store", root / "out", "--base-url", url,
                             "--config", config)
            found = json.loads((root / "out" / "report.json").read_text())
        self.assertEqual(code, 0)
        self.assertEqual(state["read"], 1)  # a's pump, of two claims; b's has one
        self.assertTrue(state["judged"])
        self.assertTrue(any("Read together, differs by condition from" in p for p in state["judged"]))
        self.assertEqual([e["relation"] for e in found["commentary"]["entries"]], ["differs_by_condition"])

if __name__ == "__main__":
    unittest.main()
