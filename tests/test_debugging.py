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

def limiting_reranks(state):
    """test_embed's stub endpoint, its /rerank refused as a LiteLLM proxy's rate limit refuses, resetting 3 h later."""
    serve = endpoint(state)

    def post(handler):
        if handler.path.endswith("/rerank"):
            request_body(handler)
            state["reranks"] = state.get("reranks", 0) + 1
            message = ("Rate limit exceeded for api_key: 5e1f. Limit type: requests. Current limit: 300, Remaining: 0."
                       " Limit resets at: 2026-10-29 18:00:00 UTC")
            handler.send_response(429, "Too Many Requests")
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Retry-After", "10800")
            handler.end_headers()
            handler.wfile.write(json.dumps({"error": {"message": message, "code": "429"}}).encode())
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
        # refused, or never sent once sending stopped: said apart
        self.assertEqual(found["comparison"]["reranker"]["failed"], rerank["failed"])
        self.assertEqual(found["comparison"]["reranker"]["not_sent"], rerank["never_answered"])
        self.assertIn(f"  reranker: {rerank['asked']} requests, {rerank['failed']} failed, {rerank['never_answered']} "
                      "not sent", out)
        self.assertIn(f"  reranker   Qwen/Qwen3-Reranker-8B (rerank API) at {url}/rerank", out)
        self.assertRegex(out, r"\n  rerank +\d+ +0 +\d+ +\d+\n")
        self.assertIn(f"  rerank        {rerank['failed']:>7}  ModelFailure: HTTP 400: Bad Request: {REFUSED}", out)
        self.assertIn("never answered: not sent, as after sending stopped", out)

    def test_a_reranker_rate_limited_till_later_pauses_the_run_at_once(self):
        """The owner, 2026-10-29: "This time I received another `paused: 25 requests failed in a row` with HTTP 429s.
        Apparently the reranker limits are set differently than the chat completion limits, e.g. only 300 requests then
        resets after a few hours."."""
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(limiting_reranks(state)) as url:
            root = Path(d)
            for name, power in (("a.md", 10), ("b.md", 12)):
                (root / name).write_text("# Plant\n\n" + "".join(f"pump{k} | rated power | {power + k} | kW\n\n"
                                                                  for k in range(8)))
            config = root / "settings.json"
            config.write_text(json.dumps({"rerank_model": "BAAI/bge-reranker-v2-m3", "concurrency": 1,
                                          "search_names": False, "topic_names": False}))
            code, _, said = run("compare", root / "a.md", root / "b.md", "--store", root / "out", "--base-url", url,
                                "--config", config, "--no-situate")
            _, out, _ = run("debug", "--store", root / "out", "--cache", root / "out")
            _, as_json, _ = run("debug", "--store", root / "out", "--cache", root / "out", "--json")
        self.assertEqual(code, 3)  # paused, as for the budget: run it again once the limit resets
        self.assertEqual(state["reranks"], 1)  # not retried, nor asked again: 25 failing in a row before
        self.assertRegex(said, rf"Paused: rate limit reached at {url}/rerank until \S+ \S+ \S+ \(in 3 h 0 min\); "
                               r"HTTP 429: Too Many Requests: Rate limit exceeded .* Limit resets at: 2026-10-29 "
                               r"18:00:00 UTC\. Rerun the same command to resume")
        found = json.loads(as_json)
        reranker = found["comparison"]["reranker"]
        self.assertEqual((reranker["failed"], reranker["not_sent"]), (0, reranker["requests"]))
        self.assertNotIn("compare", {s["step"] for s in found["steps"] if s["answered"]})  # the judge never asked
        self.assertIn(f"  paused: rate limit reached at {url}/rerank until ", out)

    def test_no_store_yet_says_so_and_makes_none(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "none"
            code, out, _ = run("debug", "--store", folder)
            self.assertFalse(folder.exists())
        self.assertEqual(code, 0)
        self.assertIn("no requests asked yet (no store, or no run in it)", out)
        self.assertIn("endpoint (the store's settings): ", out)

    def test_errors_counted_by_step_most_frequent_first_and_cut_short(self):
        roles = {"q1": ("extract", "text"), "q2": ("extract", "tile"), "q3": ("extract", "tile"),
                 "q4": ("rerank", "proposals"), "q5": ("rerank", "proposals")}
        outcomes = {"q1": ("ok", None), "q2": ("invalid", "Invalid: no JSON"), "q3": ("invalid", "Invalid: no JSON"),
                    "q4": ("invalid", "x" * 400)}
        steps, errors = debugging.steps(roles, outcomes)
        self.assertEqual(steps, [{"step": "extract", "asked": 3, "answered": 1, "failed": 2, "never_answered": 0},
                                 {"step": "rerank", "asked": 2, "answered": 0, "failed": 1, "never_answered": 1}])
        self.assertEqual(errors.most_common(), [(("extract (tile)", "Invalid: no JSON"), 2),
                                                (("rerank", "x" * 297 + "..."), 1)])
        self.assertEqual(len(debugging.short("x" * 400)), debugging.ERROR_CHARACTERS)

    def test_a_long_step_name_keeps_the_columns(self):
        """The owner, 2026-10-29: "table-structure-review [...] (this name is too wide for our columns)"."""
        found = {"version": "0", "python": "3", "pymupdf": "", "store": "s", "cache": "c", "endpoint_of": "e",
                 "endpoint": {"base_url": "u", "model": "m", "reranker": None, "embedding": None},
                 "environment": {"OPENAI_BASE_URL": True, "OPENAI_API_KEY": True}, "comparison": None,
                 "steps": [{"step": "table-structure-review", "asked": 16, "answered": 14, "failed": 2,
                            "never_answered": 0},
                           {"step": "extract", "asked": 7198, "answered": 6432, "failed": 772, "never_answered": 3}],
                 "errors": [{"step": "table-structure-review", "count": 2, "error": "Truncated"}], "other_errors": 0}
        table = [line for line in debugging.lines(found) if line.startswith("  ") and "asked" not in line][-3:-1]
        self.assertEqual(table, ["  table-structure-review         16        14       2               0",
                                 "  extract                     7,198     6,432     772               3"])
