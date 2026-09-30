"""Judge prompts, golden and replayed.

A byte change in a judge prompt changes its query hash, so every recorded verdict misses and
judging is paid again (88% of spend). The goldens make such a change deliberate: it shows here
as a diff. After an intended change, regenerate with GOLDEN_UPDATE=1 and review the diff.

The replays judge committed round batches again from their own fixtures (replay.zip), offline,
and must reproduce the committed verdicts: the answers are found by the queries rebuilt today.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import postmortem, review, rounds
from semantic_pdf_diff.llm import folder_client
from semantic_pdf_diff.models import EVALUATOR_SETTINGS, PairVerdict, Settings

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

ROUNDS = Path(__file__).resolve().parent.parent / "benchmarks" / "rounds"
REPLAYED = {"v1": "r05/pairs-details", "v2": "r07/pairs-locator", "v3": "r08/pairs-charts", "v4": "r09h/pairs-fragments"}

class RecordedJudging(unittest.TestCase):
    def test_committed_batches_judge_again_to_the_same_verdicts(self):
        for rubric, name in REPLAYED.items():
            folder = ROUNDS / name
            self.assertEqual(json.loads((folder.parent / "round.json").read_text()).get("rubric", "v1"), rubric)
            for path in sorted((folder / "verdicts").glob("*.json")):
                committed = json.loads(path.read_text(encoding="utf-8"))
                with self.subTest(batch=name, judge=committed["reviewer"]), tempfile.TemporaryDirectory() as d:
                    copy = Path(d)
                    for f in ("pairs.json", "replay.zip"):
                        shutil.copy(folder / f, copy / f)
                    (copy / "images").symlink_to(folder / "images")
                    settings = Settings(model=committed["reviewer"], **EVALUATOR_SETTINGS)
                    with folder_client(copy, settings, mode="replay") as client:
                        rounds.judge_pairs(copy, client, committed["reviewer"], rubric=rubric)
                    again = json.loads((copy / "verdicts" / path.name).read_text(encoding="utf-8"))["verdicts"]
                    self.assertEqual(again, committed["verdicts"])
                    self.assertEqual((copy / "replay.zip").read_bytes(), (folder / "replay.zip").read_bytes())

    def test_a_folder_records_its_answers_once_and_packs_them(self):
        import http.server, threading
        asked = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                asked.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
                answer = {"better": "B", "note": "stub"}
                body = json.dumps({"choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}],
                                   "usage": {"prompt_tokens": 10, "completion_tokens": 5, "estimated_cost": 0.001}})
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(body.encode())
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        settings = Settings(model="judge", base_url=f"http://127.0.0.1:{server.server_port}/v1", retries=0,
                            **EVALUATOR_SETTINGS)
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "images").mkdir()
            for item in ITEMS:
                (folder / item["image"]).write_bytes(item["id"].encode())
            (folder / "pairs.json").write_text(json.dumps({"items": ITEMS}))
            with folder_client(folder, settings) as client:
                rounds.judge_pairs(folder, client, "judge", rubric="v4")
            self.assertEqual(len(asked), 4)  # two units, both orders
            packed = (folder / "replay.zip").read_bytes()
            shutil.rmtree(folder / "verdicts")
            with folder_client(folder, settings) as client:  # judged again: every answer is recorded
                rounds.judge_pairs(folder, client, "judge", rubric="v4")
            self.assertEqual(len(asked), 4)
            self.assertEqual((folder / "replay.zip").read_bytes(), packed)  # nothing new: the same bytes
            with folder_client(folder, settings, mode="replay") as client:  # another rubric: other queries
                _, count, failures = rounds.judge_pairs(folder, client, "judge", rubric="v3", verdicts_dir="v3")
            self.assertEqual((len(asked), count, len(failures)), (4, 0, 4))

    def test_the_post_mortem_reading_is_replayed(self):
        folder = ROUNDS / "r09b" / "pairs-fragments"
        recorded = json.loads((folder / "postmortem.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(folder / "replay.zip", Path(d) / "replay.zip")
            with folder_client(d, Settings(model="google/gemini-3.1-pro", **EVALUATOR_SETTINGS), mode="replay") as client:
                reading = postmortem.read(recorded, client)
        self.assertEqual(reading.model_dump(), recorded["reading"])

if __name__ == "__main__":
    unittest.main()
