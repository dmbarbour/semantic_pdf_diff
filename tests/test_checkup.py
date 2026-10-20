"""`pdf-semantic-diff config test` and `config models` (checkup.py; docs/plans/configuration-in-the-store-2026-10-20.md,
milestone 5): the endpoint, a JSON answer, an eye-test card and the reranker checked by asking; the endpoint's models
listed, those in use marked."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import os
import random
import re
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stubs import chat_answer, prompt_of, request_body, serving, user_settings
from semantic_pdf_diff import checkup, cli

def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue()

@contextlib.contextmanager
def endpoint(listed=("gemma-4", "Qwen/Qwen3-Reranker-8B"), misread=False):
    """A stub endpoint: its models listed, sums added, the card's code read (misread: another), a reranker scoring
    the first document higher."""
    codes, real = [], checkup.card

    def card(folder, rng):
        path, code = real(folder, rng)
        codes.append(code)
        return path, code

    def get(handler):
        handler.send_response(200)
        handler.end_headers()
        handler.wfile.write(json.dumps({"object": "list", "data": [{"id": m} for m in listed]}).encode())

    def post(handler):
        body = request_body(handler)
        if handler.path.endswith("/rerank"):
            handler.send_response(200)
            handler.end_headers()
            handler.wfile.write(json.dumps([{"index": 1, "score": 0.02}, {"index": 0, "score": 0.91}]).encode())
            return
        prompt = prompt_of(body["messages"][1]["content"])
        if prompt.startswith("Add "):
            a, b = map(int, re.findall(r"\d+", prompt)[:2])
            chat_answer(handler, {"sum": a + b}, usage={"prompt_tokens": 90, "completion_tokens": 5,
                                                        "estimated_cost": 0.00002})
        else:
            chat_answer(handler, {"code": "ZZZ-0000" if misread else codes[-1].lower()})
    with serving(post, get=get) as url, patch.object(checkup, "card", card), \
            patch.dict(os.environ, {"OPENAI_BASE_URL": url}):
        yield url

class ConfigTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Path(temp.name) / "store"

    def test_every_check_passes_against_a_working_endpoint(self):
        with endpoint() as url, user_settings({"rerank_model": "Qwen/Qwen3-Reranker-8B", "rerank_api": "tei",
                                               "rerank_url": url + "/rerank"}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, 0, out)
        self.assertIn(f"checking gemma-4 at {url}", out)
        self.assertIn("  endpoint  ok: 2 models listed, gemma-4 among them", out)
        self.assertRegex(out, r"  json      ok: (\d+) \+ (\d+) = \d+")
        self.assertRegex(out, r'  image     ok: read "[a-z]{3}-\d{4}"')
        self.assertIn("  reranker  ok: scores 0.91 for the counterpart, 0.02 for the unrelated claim", out)
        self.assertIn("cost: $0.0000, as the provider reports it", out)
        self.assertTrue(out.endswith("every check passed\n"))
        self.assertFalse(self.store.exists())  # a check makes no store

    def test_a_failed_check_exits_5_saying_what_failed(self):
        with endpoint(listed=("other-model",), misread=True), user_settings({"retries": 0}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn("  endpoint  FAILED: 1 models listed, not gemma-4 (`config models WORDS` lists those like it)",
                      out)
        self.assertRegex(out, r'  image     FAILED: read "ZZZ-0000", not "[A-Z]{3}-\d{4}"')
        self.assertIn("  reranker  --: none set (rerank_model)", out)
        self.assertTrue(out.endswith("2 check(s) failed: endpoint, image\n"))

    def test_an_endpoint_not_reachable_skips_the_models(self):
        with socket.socket() as s:  # a port nothing listens on
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        with patch.dict(os.environ, {"OPENAI_BASE_URL": f"http://127.0.0.1:{port}/v1"}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn("  endpoint  FAILED: URLError", out)
        self.assertIn("  json      --: skipped: the endpoint isn't reachable", out)

    def test_the_card_is_a_random_code_drawn_large(self):
        with tempfile.TemporaryDirectory() as d:
            path, code = checkup.card(d, random.Random(3))
            import pymupdf
            pixmap = pymupdf.Pixmap(str(path))
        self.assertRegex(code, r"^[A-HJ-NP-Z]{3}-\d{4}$")
        self.assertEqual((pixmap.width, pixmap.height), (400, 120))

class ConfigModels(unittest.TestCase):
    def test_the_endpoints_models_those_in_use_marked(self):
        with endpoint(listed=("gemma-4", "gemma-4-turbo", "llama")), tempfile.TemporaryDirectory() as d:
            code, out = run("config", "models", "gemma", "--store", Path(d) / "s")
        self.assertEqual((code, out), (0, "gemma-4  (model)\ngemma-4-turbo\n"))
        with endpoint(listed=("llama",)), tempfile.TemporaryDirectory() as d:
            self.assertEqual(run("config", "models", "gemma", "--store", Path(d) / "s")[1],
                             "no model at the endpoint holds 'gemma'\n")

if __name__ == "__main__":
    unittest.main()
