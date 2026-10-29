"""`semantic-pdf-diff debug` (debugging.py): what a store's runs asked and what failed, with counts and the errors
recorded. The owner, 2026-10-29: "We should probably add a `semantic-pdf-diff debug` option that prints error
information and error counts. I'm not very able to copy a large script manually across two domains."
"""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from stubs import request_body, serving
from semantic_pdf_diff import cli, debugging
from test_embed import endpoint

REFUSED = ("litellm.BadRequestError: DeepinfraException - the reranker is not served here. Received Model "
           "Group=Qwen/Qwen3-Reranker-8B")

def refusing_reranks(state):
    """test_embed's stub endpoint (claims read from lines, pairs judged, other names, embeddings), its /rerank refused
    as a LiteLLM proxy refuses (HTTP 400, why in JSON)."""
    serve = endpoint(state)

    def post(handler):
        if handler.path.endswith("/rerank"):
            request_body(handler)
            handler.send_response(400, "Bad Request")
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"error": {"message": REFUSED, "code": "400"}}).encode())
            return
        return serve(handler)
    return post

def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()

class Debug(unittest.TestCase):
    def test_a_store_whose_reranker_failed_says_how_often_and_why(self):
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(refusing_reranks(state)) as url:
            root = Path(d)
            for name, power in (("a.md", 10), ("b.md", 12)):
                (root / name).write_text("# Plant\n\n" + "".join(f"pump{k} | rated power | {power + k} | kW\n\n"
                                                                  for k in range(8)))
            config = root / "settings.json"
            config.write_text(json.dumps({"rerank_model": "Qwen/Qwen3-Reranker-8B", "retries": 0,
                                          "stop_after_failures": 3, "search_names": False, "topic_names": False}))
            run("compare", root / "a.md", root / "b.md", "--store", root / "out", "--base-url", url, "--config",
                config, "--no-situate")
            # (the tests' stores keep their answers apart: stubs.py)
            code, out, _ = run("debug", "--store", root / "out", "--cache", root / "out")
            _, as_json, _ = run("debug", "--store", root / "out", "--cache", root / "out", "--json")
        self.assertEqual(code, 0)
        found = json.loads(as_json)
        steps = {s["step"]: s for s in found["steps"]}
        rerank = steps["rerank"]
        self.assertEqual(rerank["answered"], 0)
        self.assertGreaterEqual(rerank["failed"], 3)  # 3 in a row stop sending; those in flight fail too
        self.assertEqual(rerank["failed"] + rerank["never_answered"], rerank["asked"])
        self.assertGreater(rerank["never_answered"], 0)
        self.assertEqual(steps["extract"]["answered"], steps["extract"]["asked"])
        self.assertEqual(found["errors"][0], {"step": "rerank", "count": rerank["failed"],
                                              "error": f"ModelFailure: HTTP 400: Bad Request: {REFUSED}"})
        self.assertEqual(found["endpoint_of"], "the last comparison's")
        self.assertEqual(found["endpoint"]["reranker"], {"model": "Qwen/Qwen3-Reranker-8B", "api": "rerank",
                                                         "url": f"{url}/rerank"})
        self.assertEqual(found["comparison"]["reranker"]["failed"], rerank["asked"])
        self.assertIn(f"  reranker   Qwen/Qwen3-Reranker-8B (rerank API) at {url}/rerank", out)
        self.assertRegex(out, r"\n  rerank +\d+ +0 +\d+ +\d+\n")
        self.assertIn(f"  rerank        {rerank['failed']:>7}  ModelFailure: HTTP 400: Bad Request: {REFUSED}", out)
        self.assertIn("never answered: not sent, as after sending stopped", out)

    def test_no_store_yet_says_so_and_makes_none(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "none"
            code, out, _ = run("debug", "--store", folder)
            self.assertFalse(folder.exists())
        self.assertEqual(code, 0)
        self.assertIn("no requests asked yet (no store, or no run in it)", out)
        self.assertIn("endpoint (the store's settings): ", out)

    def test_errors_counted_by_step_most_frequent_first_and_cut_short(self):
        roles = {"q1": "extract", "q2": "extract", "q3": "extract", "q4": "rerank", "q5": "rerank"}
        outcomes = {"q1": ("ok", None), "q2": ("invalid", "Invalid: no JSON"), "q3": ("invalid", "Invalid: no JSON"),
                    "q4": ("invalid", "x" * 400)}
        steps, errors = debugging.steps(roles, outcomes)
        self.assertEqual(steps, [{"step": "extract", "asked": 3, "answered": 1, "failed": 2, "never_answered": 0},
                                 {"step": "rerank", "asked": 2, "answered": 0, "failed": 1, "never_answered": 1}])
        self.assertEqual(errors.most_common(1), [(("extract", "Invalid: no JSON"), 2)])
        self.assertEqual(len(debugging.short("x" * 400)), debugging.ERROR_CHARACTERS)
