"""`semantic-pdf-diff config test` and `config models` (checkup.py; decision 0032): the endpoint, a JSON answer, an
eye-test card, the reranker and the embedding model checked by asking; the endpoint's models listed, those in use
marked."""
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
    """A stub endpoint: its models listed, sums added, the card's code read (misread: another; an image 258 tokens),
    a reranker scoring the first document higher, and an embedding model putting the pump's two sentences
    together."""
    codes, real = [], checkup.card

    def card(folder, rng, side=None):
        path, code = real(folder, rng, side)
        codes.append(code)
        return path, code

    def get(handler):
        handler.send_response(200)
        handler.end_headers()
        data = [m if isinstance(m, dict) else {"id": m} for m in listed]
        handler.wfile.write(json.dumps({"object": "list", "data": data}).encode())

    def post(handler):
        body = request_body(handler)
        if handler.path.endswith("/rerank"):
            handler.send_response(200)
            handler.end_headers()
            handler.wfile.write(json.dumps([{"index": 1, "score": 0.02}, {"index": 0, "score": 0.91}]).encode())
            return
        if handler.path.endswith("/embeddings"):
            rows = [{"index": i, "embedding": [float("pump" in t), float("door" in t), 0.1]}
                    for i, t in enumerate(body["input"])]
            handler.send_response(200)
            handler.end_headers()
            handler.wfile.write(json.dumps({"data": rows}).encode())
            return
        prompt = prompt_of(body["messages"][1]["content"])
        if prompt.startswith("Add "):
            a, b = map(int, re.findall(r"\d+", prompt)[:2])
            chat_answer(handler, {"sum": a + b}, usage={"prompt_tokens": 90, "completion_tokens": 5,
                                                        "estimated_cost": 0.00002})
        else:  # an image is 258 tokens here, as gemma-4's at DeepInfra
            imaged = any(part["type"] == "image_url" for part in body["messages"][1]["content"])
            chat_answer(handler, {"code": "ZZZ-0000" if misread else codes[-1].lower()},
                        usage={"prompt_tokens": 120 + 258 * imaged, "completion_tokens": 9})
    with serving(post, get=get) as url, patch.object(checkup, "card", card), \
            patch.dict(os.environ, {"OPENAI_BASE_URL": url}):
        yield url

class ConfigTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Path(temp.name) / "store"

    def test_every_check_passes_against_a_working_endpoint(self):
        with endpoint() as url, user_settings({"model": "gemma-4", "rerank_model": "Qwen/Qwen3-Reranker-8B",
                                               "rerank_api": "tei", "rerank_url": url + "/rerank",
                                               "embed_model": "toy"}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, 0, out)
        self.assertIn(f"checking gemma-4 at {url}", out)
        self.assertIn("  endpoint  ok: 2 models listed, gemma-4 among them", out)
        self.assertRegex(out, r"  json      ok: (\d+) \+ (\d+) = \d+")
        self.assertRegex(out, r'  image     ok: read "[a-z]{3}-\d{4}"; an image 1000 px square is 258 tokens')
        self.assertIn("  reranker  ok: scores 0.91 for the counterpart, 0.02 for the unrelated claim", out)
        self.assertIn("  embedding ok: cosine 1.00 with the counterpart, 0.01 with the unrelated claim", out)
        self.assertIn("cost: $0.0000, as the provider reports it", out)
        self.assertTrue(out.endswith("every check passed\n"))
        self.assertFalse(self.store.exists())  # a check makes no store

    def test_a_failed_check_exits_5_saying_what_failed(self):
        with endpoint(listed=("other-model",), misread=True), user_settings({"model": "gemma-4", "retries": 0}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn("  endpoint  FAILED: 1 models listed, not gemma-4 (`config models WORDS` lists those like it)",
                      out)
        self.assertRegex(out, r'  image     FAILED: read "ZZZ-0000", not "[A-Z]{3}-\d{4}"')
        self.assertIn("  reranker  --: none set (rerank_model)", out)
        self.assertIn("  embedding --: none set (embed_model)", out)
        self.assertTrue(out.endswith("2 check(s) failed: endpoint, image\n"))

    def test_no_model_set_fails_and_says_how_to_set_one(self):
        with endpoint(), user_settings({}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn("checking no model at", out)
        self.assertIn("  endpoint  ok: 2 models listed\n", out)
        self.assertIn("  model     FAILED: none set: `config set --user model NAME` names one (`config models vision` "
                      "lists those reading images)", out)
        self.assertIn("  json      --: skipped: no model is set", out)
        self.assertTrue(out.endswith("1 check(s) failed: model\n"))

    def test_a_reranker_not_served_where_asked_says_where(self):
        with endpoint() as url, user_settings({"rerank_model": "m", "retries": 0}):  # the stub serves tei's at /rerank
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn(f"at {url}/rerank (rerank_api and rerank_url say where it's served)", out)

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

class NoModel(unittest.TestCase):
    def test_a_comparison_without_a_model_stops_listing_those_reading_images(self):
        listed = [{"id": f"vision-{k:02}", "metadata": {"context_length": 8192, "tags": ["vision"]}}
                  for k in range(20)] + [{"id": "text-only", "metadata": {"tags": ["chat"]}}]
        with endpoint(listed=listed), tempfile.TemporaryDirectory() as d, user_settings({}):
            (Path(d) / "a.txt").write_text("Pump rated power 10 kW")
            (Path(d) / "b.txt").write_text("Pump rated power 12 kW")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
                code = cli.main(["compare", str(Path(d) / "a.txt"), str(Path(d) / "b.txt"), "--store",
                                 str(Path(d) / "out")])
            made = (Path(d) / "out").exists()
        said = err.getvalue().splitlines()
        self.assertEqual((code, made), (1, False))  # stopped before the store is made
        self.assertEqual(said[0], "Error: No model is set: `semantic-pdf-diff config set --user model NAME` names "
                                  "one for every store (`config set model NAME` for one store, --model for one run).")
        self.assertRegex(said[1], r"^The endpoint at http://127\.0\.0\.1:\d+/v1 lists 21 models; these 20 read "
                                  r"images:$")
        self.assertEqual(said[2], "  vision-00  8,192 tokens  vision")
        self.assertEqual(len(said), 2 + 15 + 1)
        self.assertEqual(said[-1], "  and 5 more: `semantic-pdf-diff config models vision`")

    def test_an_endpoint_out_of_reach_says_what_names_it(self):
        from semantic_pdf_diff.settings import Settings
        said = checkup.unset_model(Settings(base_url="http://127.0.0.1:9/v1")).splitlines()[1]
        self.assertRegex(said, r"^The endpoint at http://127\.0\.0\.1:9/v1 can't be asked for its models "
                               r"\(URLError: .*\)\. \$OPENAI_BASE_URL names the endpoint, else the user's base_url .* "
                               r"`semantic-pdf-diff config test` checks it\.$")

class ConfigModels(unittest.TestCase):
    def test_the_endpoints_models_those_in_use_marked(self):
        with endpoint(listed=("gemma-4", "gemma-4-turbo", "llama")), tempfile.TemporaryDirectory() as d:
            code, out = run("config", "models", "gemma", "--store", Path(d) / "s")
        self.assertEqual((code, out), (0, "gemma-4  (model)\ngemma-4-turbo\n"))
        with endpoint(listed=("llama",)), tempfile.TemporaryDirectory() as d:
            self.assertEqual(run("config", "models", "gemma", "--store", Path(d) / "s")[1],
                             "no model at the endpoint holds 'gemma'\n")

    def test_what_the_endpoint_says_of_each_model(self):
        deepinfra = {"id": "google/gemma-4-31B-it", "metadata": {
            "context_length": 262144, "pricing": {"input_tokens": 0.2, "output_tokens": 0.4},
            "tags": ["chat", "vlm", "vision", "reasoning"]}}
        embedder = {"id": "Qwen/Qwen3-Embedding-8B",
                    "metadata": {"context_length": 32768, "pricing": {"input_tokens": 0.005}, "tags": ["embed"]}}
        openrouter = {"id": "acme/seer", "context_length": 128000, "pricing": {"prompt": "0.0000005",
                                                                               "completion": "0.0000015"},
                      "architecture": {"input_modalities": ["text", "image"]}}
        vllm = {"id": "local/reader", "max_model_len": 32768}
        with endpoint(listed=(deepinfra, embedder, openrouter, vllm)), tempfile.TemporaryDirectory() as d, \
                user_settings({"model": "google/gemma-4-31B-it"}):
            code, out = run("config", "models", "--store", Path(d) / "s")
            self.assertEqual(code, 0)
            self.assertEqual(out.splitlines(), [
                "acme/seer                       128,000 tokens  $0.50 in, $1.50 out a million  vision",
                "google/gemma-4-31B-it  (model)  262,144 tokens  $0.20 in, $0.40 out a million  chat, vlm, vision, "
                "reasoning",
                "local/reader                     32,768 tokens",
                "Qwen/Qwen3-Embedding-8B          32,768 tokens  $0.005 in a million            embed"])
            self.assertEqual(run("config", "models", "vision", "--store", Path(d) / "s")[1].split("\n")[1][:5], "googl")
            code, out = run("config", "models", "seer", "--json", "--store", Path(d) / "s")
        self.assertEqual(json.loads(out), [{"id": "acme/seer", "context": 128000, "price_in": 0.5, "price_out": 1.5,
                                            "tags": ["vision"], "named_by": []}])

if __name__ == "__main__":
    unittest.main()
