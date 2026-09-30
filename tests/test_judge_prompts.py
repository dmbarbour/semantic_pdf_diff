"""Golden judge prompts: every rubric's prompt, byte for byte, on fixed items.

A byte change in a judge prompt changes its query hash, so every recorded verdict misses and
judging is paid again (88% of spend). These goldens make such a change deliberate: it shows here
as a diff. After an intended change, regenerate with GOLDEN_UPDATE=1 and review the diff.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import review, rounds
from semantic_pdf_diff.models import PairVerdict

GOLDEN = Path(__file__).resolve().parent / "golden"
UPDATE = bool(os.environ.get("GOLDEN_UPDATE"))

def claim(entity, attribute, value, unit="", conditions="", quote=None, ident=None):
    c = {"entity": entity, "attribute": attribute, "value": value, "unit": unit, "conditions": conditions,
         "quote": quote or f"{entity} {value}{unit}", "_box": [10.0, 20.0, 30.0, 40.0]}
    if ident:
        c["_id"] = ident
    return c

PUMP, FAN, CHILLER = (claim("Pump P-1", "rated power", "10", "kW", ident="t-1~aa"),
                      claim("Fan F-2", "airflow", "3,000", "cfm", "at 0.5 in. w.g.", ident="t-1~bb"),
                      claim("Chiller CH-1", "capacity", "350", "tons", ident="t-1~cc"))
PUMP_12 = claim("Pump P-1", "rated power", "12", "kW", quote="Pump P-1 12 kW", ident="t-1~dd")
ITEMS = [
    {"id": "u-run-aaaa1111-p2-text", "run": "run", "content": "sha256:aaaa1111.pdf", "page": 2, "family": "text",
     "band": None, "image": "images/p2.png", "page_text": "3.1 Pumps\nPump P-1 10 kW\nFan F-2 3,000 cfm at 0.5 in. w.g.",
     "sections": ["3 Mechanical", "3.1 Pumps"], "before": "the pumps listed below serve the chilled water loop.",
     "within": "3.1 Pumps", "baseline": [PUMP, FAN], "variant": [PUMP_12, FAN, CHILLER], "hidden_shared": 2,
     "counts": {"baseline": 4, "variant": 5, "shared": 3},
     "page_image": "images/p2-page.png", "page_text_full": "3 Mechanical\n3.1 Pumps\nPump P-1 10 kW\nFan F-2 3,000 cfm"},
    {"id": "u-run-aaaa1111-p5-table-b0of2", "run": "run", "content": "sha256:aaaa1111.pdf", "page": 5,
     "family": "table", "band": [0, 2, 72.0, 300.0], "image": "images/p5-b0of2.png",
     "page_text": "TAG | CAPACITY\nCH-1 | 350 tons", "sections": [], "before": "", "within": "",
     "baseline": [CHILLER], "variant": [], "hidden_shared": 0, "counts": {"baseline": 1, "variant": 0, "shared": 0},
     "page_image": "images/p5-page.png", "page_text_full": "SCHEDULE\nTAG | CAPACITY\nCH-1 | 350 tons\nCH-2 | 400 tons"},
]

class Recorder:
    """A judge that answers nothing useful and remembers what it was asked."""
    def __init__(self, answer):
        self.answer, self.asked = answer, []
    def ask(self, prompt, schema, images=(), key=None):
        self.asked.append((prompt, [Path(i).name for i in images]))
        return self.answer

def transcript(asked):
    return "".join(f"=== images: {', '.join(images)}\n{prompt}\n" for prompt, images in asked)

class GoldenPrompts(unittest.TestCase):
    def check(self, name, text):
        path = GOLDEN / f"{name}.txt"
        if UPDATE:
            GOLDEN.mkdir(exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.assertTrue(path.exists(), f"{path}: no golden (run with GOLDEN_UPDATE=1)")
        self.assertEqual(text, path.read_text(encoding="utf-8"), f"{name}'s prompts changed: judging would be paid again")

    def test_every_pairwise_rubric(self):
        for rubric in rounds.RUBRICS:
            with self.subTest(rubric=rubric), tempfile.TemporaryDirectory() as d:
                folder = Path(d)
                (folder / "pairs.json").write_text(json.dumps({"items": ITEMS}))
                judge = Recorder(PairVerdict(better="same", note="golden"))
                rounds.judge_pairs(folder, judge, "golden", rubric=rubric)
                self.check(f"pairwise-{rubric}", transcript(judge.asked))

    def test_review_panel_prompts(self):
        items = [
            {"type": "claim", "shown": {"entity": "Pump P-1", "attribute": "rated power", "value": "10", "unit": "kW"},
             "context": {"page": 2, "section": "3.1 Pumps"}, "images": [{"caption": "the claim's region, outlined"}]},
            {"type": "about", "shown": {"about": "The pump schedule for the chilled water loop."},
             "context": {"page": 5}, "images": [{"caption": "the figure"}, {"caption": "the page"}]},
            {"type": "pair", "shown": {"a": "Pump P-1 10 kW", "b": "Pump P-1 12 kW", "relation": "changed"},
             "context": {}, "images": []},
        ]
        asked = [(review.judge_prompt(i), [c["caption"] for c in i["images"]]) for i in items]
        question = {"type": "claim", "request": {"summary": "Read the pump schedule", "instructions": "Extract claims.",
                                                 "query": "Pump P-1 10 kW"}}
        asked.append((review.question_prompt(question), []))
        self.check("review-panel", transcript(asked))

if __name__ == "__main__":
    unittest.main()
