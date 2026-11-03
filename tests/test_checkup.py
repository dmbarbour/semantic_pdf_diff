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

import pyte

from stubs import chat_answer, prompt_of, request_body, serving, user_settings
from semantic_pdf_diff import acuity, checkup, cli
from semantic_pdf_diff.settings import Settings, user_settings as saved_settings

def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue()

@contextlib.contextmanager
def endpoint(listed=("gemma-4", "Qwen/Qwen3-Reranker-8B"), misread=False, info=None):
    """A stub endpoint: its models listed (info: LiteLLM's /model/info, else none), sums added, the card's code read
    (misread: another; an image 258 tokens), the acuity cards of capitals 7 px and up read (misread: none), a
    reranker scoring the first document higher, and an embedding model putting the pump's two sentences together."""
    codes, real, drawn, real_card = [], checkup.card, [], acuity.card

    def eye_card(folder, rng, size, side):
        path, lines = real_card(folder, rng, size, side)
        drawn.append((size, lines))
        return path, lines

    def card(folder, rng, side=None):
        path, code = real(folder, rng, side)
        codes.append(code)
        return path, code

    def get(handler):
        if handler.path.endswith("/model/info"):
            handler.send_response(200 if info is not None else 404)
            handler.end_headers()
            handler.wfile.write(json.dumps({"data": info or []}).encode())
            return
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
        if prompt == acuity.PROMPT:  # the check's cards' lines of 7 px and up: each card finds its own among them
            check = drawn[-len(acuity.SIZES):]
            lines = [] if misread else [line for size, lines in check if size >= 7 for line in lines]
            chat_answer(handler, {"lines": lines}, usage={"prompt_tokens": 400, "completion_tokens": 200})
            return
        if prompt.startswith("Add "):
            a, b = map(int, re.findall(r"\d+", prompt)[:2])
            chat_answer(handler, {"sum": a + b}, usage={"prompt_tokens": 90, "completion_tokens": 5,
                                                        "estimated_cost": 0.00002})
        else:  # an image is 258 tokens here, as gemma-4's at DeepInfra
            imaged = any(part["type"] == "image_url" for part in body["messages"][1]["content"])
            chat_answer(handler, {"code": "ZZZ-0000" if misread else codes[-1].lower()},
                        usage={"prompt_tokens": 120 + 258 * imaged, "completion_tokens": 9})
    with serving(post, get=get) as url, patch.object(checkup, "card", card), patch.object(acuity, "card", eye_card), \
            patch.dict(os.environ, {"OPENAI_BASE_URL": url}):
        yield url

class Remembered(unittest.TestCase):
    """The checks remembered (endpoints.json, beside the answers cache) in a cache of the test's own."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Path(temp.name) / "store"
        cache = patch.dict(os.environ, {"SEMANTIC_PDF_DIFF_CACHE": str(Path(temp.name) / "cache")})
        cache.start()
        self.addCleanup(cache.stop)
        self.memory = Path(temp.name) / "cache" / "endpoints.json"

    def config(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["config", *map(str, argv), "--store", str(self.store)])
        return code, out.getvalue() + err.getvalue()

class ConfigTest(Remembered):
    def test_every_check_passes_against_a_working_endpoint(self):
        with endpoint() as url, user_settings({"model": "gemma-4", "rerank_model": "Qwen/Qwen3-Reranker-8B",
                                               "rerank_api": "tei", "rerank_url": url + "/rerank",
                                               "embed_model": "toy"}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, 0, out)
        self.assertIn(f"checking gemma-4, Qwen/Qwen3-Reranker-8B (reranker), toy (embedding model) at {url}", out)
        self.assertIn("  endpoint  ok: 2 models listed, gemma-4 among them", out)
        self.assertRegex(out, r"  json      ok: (\d+) \+ (\d+) = \d+")
        self.assertRegex(out, r'  image     ok: read "[a-z]{3}-\d{4}"; an image 1000 px square is 258 tokens')
        self.assertIn("  acuity    ok: capitals 6.9 px tall and up read at 1000 px square (pages are tiled for text 7 "
                      "px and up)", out)
        self.assertIn("  reranker  ok: scores 0.91 for the counterpart, 0.02 for the unrelated claim", out)
        self.assertIn("  embedding ok: cosine 1.00 with the counterpart, 0.01 with the unrelated claim; 3 dimensions, "
                      "the model's own", out)
        self.assertIn("cost: $0.0000, as the provider reports it", out)
        self.assertTrue(out.endswith("every check passed\n"))
        self.assertFalse(self.store.exists())  # a check makes no store

    def test_each_check_is_a_bar_while_it_runs(self):
        # the owner, 2026-11-02: "there is no progress bar on initial testing or calibration. So it's unclear whether
        # my system is frozen or just moving slowly."
        class Screen(io.StringIO):  # a terminal, as far as the bars can tell
            def isatty(self):
                return True
        with endpoint() as url, user_settings({"model": "gemma-4", "rerank_model": "Qwen/Qwen3-Reranker-8B",
                                               "rerank_api": "tei", "rerank_url": url + "/rerank"}), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(Screen()) as err:
            code = cli.main(["config", "test", "--store", str(self.store)])
        self.assertEqual(code, 0)
        drawn = err.getvalue()
        for row in ("check    endpoint ", "1/1 listing", "1/1 answer", "2/2 answers", "8/8 cards", "1/1 ranking"):
            self.assertIn(row, drawn)
        self.assertNotIn("embedding ", drawn)  # no embedding model: no bar
        screen = pyte.Screen(200, 40)
        pyte.Stream(screen).feed(drawn.replace("\n", "\r\n"))
        self.assertFalse([row for row in screen.display if "█" in row or "░" in row])  # erased once done
        self.assertNotIn("check: ", drawn)  # nor a line counting its requests: each check's line says it

    def test_very_verbose_logs_each_request(self):
        with endpoint(), user_settings({"model": "gemma-4"}), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            code = cli.main(["config", "test", "--store", str(self.store), "-vv"])
        self.assertEqual(code, 0)
        self.assertRegex(err.getvalue(), r"Sum : ok in [\d.]+s \(95 tokens\)")

    def test_a_failed_check_exits_5_saying_what_failed(self):
        with endpoint(listed=("other-model",), misread=True), user_settings({"model": "gemma-4", "retries": 0}):
            code, out = run("config", "test", "--store", self.store)
        self.assertEqual(code, checkup.FAILED)
        self.assertIn("  endpoint  FAILED: 1 models listed, not gemma-4 (`config models WORDS` lists those like it)",
                      out)
        self.assertRegex(out, r'  image     FAILED: read "ZZZ-0000", not "[A-Z]{3}-\d{4}"')
        self.assertIn("  reranker  --: not configured, so reranking is off: `config set --user rerank_model NAME` "
                      "names one (`config models rerank` lists the endpoint's), `none` goes without", out)
        self.assertIn("  embedding --: not configured, so search by meaning is off: `config set --user embed_model "
                      "NAME` names one (`config models embedding` lists the endpoint's), `none` goes without", out)
        self.assertIn("  acuity    FAILED: read no card's items at 90%, up to capitals 16 px tall at 1000 px square: "
                      "pages' text would be misread", out)
        self.assertTrue(out.endswith("3 check(s) failed: endpoint, image, acuity\n"))
        with endpoint(), user_settings({"model": "gemma-4", "rerank_model": None, "embed_model": None}):
            code, out = run("config", "test", "--store", self.store, "--only", "reranker,embedding")
        self.assertIn("  reranker  --: none: rerank_model is none, so reranking is off", out)
        self.assertIn("  embedding --: none: embed_model is none, so search by meaning is off", out)

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

class ConfigModels(Remembered):
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
                      "architecture": {"input_modalities": ["text", "image"]},
                      "top_provider": {"max_completion_tokens": 16000}}
        vllm = {"id": "local/reader", "max_model_len": 32768}
        with endpoint(listed=(deepinfra, embedder, openrouter, vllm)), tempfile.TemporaryDirectory() as d, \
                user_settings({"model": "google/gemma-4-31B-it"}):
            code, out = run("config", "models", "--store", Path(d) / "s")
            self.assertEqual(code, 0)
            self.assertEqual(out.splitlines(), [
                "acme/seer                                  128,000 tokens (16,000 out)  $0.50 in, $1.50 out a million"
                "  vision",
                "google/gemma-4-31B-it  (model)  chat                    262,144 tokens  $0.20 in, $0.40 out a million"
                "  vlm, vision, reasoning",
                "local/reader                                             32,768 tokens",
                "Qwen/Qwen3-Embedding-8B         embedding                32,768 tokens  $0.005 in a million"])
            self.assertEqual(run("config", "models", "vision", "--store", Path(d) / "s")[1].split("\n")[1][:5], "googl")
            self.assertEqual(run("config", "models", "embedding", "--store", Path(d) / "s")[1][:8], "Qwen/Qwe")
            code, out = run("config", "models", "seer", "--json", "--store", Path(d) / "s")
        self.assertEqual(json.loads(out), [{"id": "acme/seer", "mode": "", "context": 128000, "output": 16000,
                                            "price_in": 0.5, "price_out": 1.5, "tags": ["vision"], "named_by": [],
                                            "checked": {}}])

    def test_a_bare_listing_completed_from_litellms_model_info(self):
        """A LiteLLM proxy lists names alone; its /model/info says each one's mode, context, price and images (the
        owner: "can you list mode and other relevant stats (context size, etc.) upon for `config models`?")."""
        info = [{"model_name": "dev/gemma", "model_info": {"mode": "chat", "max_input_tokens": 262144,
                                                           "max_output_tokens": 8192, "supports_vision": True,
                                                           "input_cost_per_token": 2e-07,
                                                           "output_cost_per_token": 4e-07}},
                {"model_name": "dev/gemma", "model_info": {"mode": None, "max_input_tokens": 1}},  # a 2nd deployment
                {"model_name": "dev/bge-reranker", "model_info": {"mode": "rerank", "input_cost_per_token": 0}},
                {"model_name": "dev/bge-m3", "model_info": {"mode": "embedding"}}]
        with endpoint(listed=("dev/gemma", "dev/bge-reranker", "dev/bge-m3", "dev/unknown"), info=info), \
                user_settings({"model": "dev/gemma"}):
            self.assertEqual(self.config("models")[1].splitlines(), [
                "dev/bge-m3          embedding",
                "dev/bge-reranker    rerank",
                "dev/gemma  (model)  chat       262,144 tokens (8,192 out)  $0.20 in, $0.40 out a million  vision",
                "dev/unknown"])
            self.assertEqual(self.config("models", "rerank")[1], "dev/bge-reranker  rerank\n")
        with endpoint(listed=("dev/gemma",)):  # a server without /model/info: names alone
            self.assertEqual(self.config("models")[1], "dev/gemma\n")

class TryingAndForgetting(Remembered):
    """Endpoint setup, milestone 2: a candidate tried before it's set, checks run selectively, the checks remembered
    shown and forgotten (the owner, 2026-10-28: "better configuration setup, support for browsing available models at
    the endpoint and validating the endpoint, running a few checks if not calibrated")."""
    def test_a_candidate_tried_before_its_set_and_remembered(self):
        with endpoint(listed=("gemma-4", "gemma-4-turbo")) as url, user_settings({"model": "gemma-4"}):
            code, out = self.config("test", "--model", "gemma-4-turbo")
            self.assertEqual(code, 0, out)
            self.assertIn(f"checking gemma-4-turbo at {url}", out)
            self.assertIn("  endpoint  ok: 2 models listed, gemma-4-turbo among them", out)
            self.assertRegex(out, r'  image     ok: read "[a-z]{3}-\d{4}"; an image 1000 px square is 258 tokens')
            self.assertNotIn("reranker", out)  # another model's check
            self.assertEqual(saved_settings()["model"], "gemma-4")  # not set
            self.assertEqual(self.config("test")[0], 0)  # the model set
            code, out = self.config("checks")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], f"checks remembered passing in {self.memory}; a run checks a model first unless its "
                                   "checks are here")
        self.assertEqual(lines[1], f"gemma-4 at {url}  (model)")
        self.assertRegex(lines[2], r"^  json      passed \d{4}-\d\d-\d\d \d\d:\d\d UTC$")
        self.assertRegex(lines[3], r"^  image     passed .* UTC; an image 1000 px square is 258 tokens$")
        self.assertRegex(lines[4], r"^  acuity    passed .* UTC; capitals 6.9 px tall and up read at 1000 px square$")
        self.assertEqual(lines[5], f"gemma-4-turbo at {url}")
        self.assertEqual(lines[-1], "`semantic-pdf-diff config checks --forget [MODEL]` forgets them: the next run "
                                    "checks again")

    def test_a_candidate_reranker_or_embedding_model_tried_as_one(self):
        """The owner: "how do we distinguish checking a rerank or embedding model?" By the flag naming its role: each
        candidate gets its role's check alone, remembered under it."""
        with endpoint(listed=("gemma-4", "bge-m3")) as url, user_settings({"model": "gemma-4", "rerank_api": "tei"}):
            code, out = self.config("test", "--rerank", "bge-reranker", "--embed", "bge-m3", "--base-url", url)
            self.assertEqual(code, 0, out)
            self.assertIn(f"checking bge-reranker (reranker), bge-m3 (embedding model) at {url}", out)
            self.assertIn("  reranker  ok: scores 0.91", out)
            self.assertIn("  embedding ok: cosine", out)
            self.assertNotIn("json", out)
            self.assertNotIn("rerank_model", saved_settings())  # not set
            lines = self.config("checks")[1].splitlines()
        self.assertIn(f"bge-m3 at {url}/embeddings", lines)
        self.assertIn("  embedding passed", lines[lines.index(f"bge-m3 at {url}/embeddings") + 1])

    def test_a_chat_candidate_the_endpoint_lists_as_an_embedding_model(self):
        listed = ({"id": "gemma-4", "metadata": {"tags": ["chat"]}}, {"id": "bge-m3", "metadata": {"tags": ["embed"]}})
        with endpoint(listed=listed), user_settings({"model": "gemma-4"}):
            code, out = self.config("test", "--model", "bge-m3", "--only", "json")
        self.assertIn("  endpoint  ok: 2 models listed, bge-m3 among them; listed as an embedding model, not a chat "
                      "model (`config test --embed bge-m3` tries it as one)", out)

    def test_only_some_checks_or_those_not_remembered(self):
        with endpoint(), user_settings({"model": "gemma-4"}):
            code, out = self.config("test", "--only", "image")
            self.assertEqual(code, 0, out)
            self.assertIn("  image     ok", out)
            self.assertNotIn("  json", out)
            code, out = self.config("test", "--new")  # the image's remembered: json only
            self.assertIn("  json      ok", out)
            self.assertNotIn("  image", out)
            self.assertEqual(self.config("test", "--new"), (0, f"every check asked for is remembered passing in "
                                                               f"{self.memory} (`config checks` lists them): nothing "
                                                               "was asked\n"))
            code, out = self.config("test", "--only", "json,eyes")
        self.assertEqual(code, 1)
        self.assertIn("--only: no check is named eyes; the checks: json, image, acuity, reranker, embedding", out)

    def test_checks_forgotten_a_models_or_every_one(self):
        with endpoint(listed=("gemma-4", "gemma-4-turbo")), user_settings({"model": "gemma-4"}):
            self.config("test")
            self.config("test", "--model", "gemma-4-turbo")
        self.assertEqual(self.config("checks", "--forget", "llama"),
                         (0, f"no check of llama is remembered in {self.memory} (`config checks` lists them)\n"))
        self.assertEqual(self.config("checks", "--forget", "gemma-4-turbo"),
                         (0, f"3 check(s) of gemma-4-turbo forgotten in {self.memory}: the next run checks again\n"))
        self.assertNotIn("gemma-4-turbo", self.config("checks")[1])
        self.assertEqual(self.config("checks", "--forget")[1].split(" in ")[0], "3 check(s) of any model forgotten")
        self.assertTrue(self.config("checks")[1].startswith(f"no check is remembered in {self.memory}: a run checks "
                                                            "each model before its first request"))

class ChoosingAModel(Remembered):
    """Endpoint setup, milestone 3: a model's name checked as it's set, and the models checked marked."""
    LISTED = ({"id": "google/gemma-4-31B-it", "metadata": {"context_length": 262144, "tags": ["chat", "vision"]}},
              {"id": "acme/text-only", "metadata": {"tags": ["chat"]}})

    def test_a_name_set_is_checked_against_the_listing_warned_of_never_refused(self):
        with endpoint(listed=self.LISTED) as url, user_settings({}):
            code, out = self.config("set", "--user", "model", "google/gemma-4-31b-it")
            self.assertEqual(code, 0)
            self.assertIn(f"warning: the endpoint at {url} lists 2 models, not google/gemma-4-31b-it; like it: "
                          "google/gemma-4-31B-it (`config models WORDS` lists them); `semantic-pdf-diff config test "
                          "--model google/gemma-4-31b-it` tries it (a few cents)", out)
            self.assertEqual(saved_settings()["model"], "google/gemma-4-31b-it")  # set all the same
            code, out = self.config("set", "--user", "model", "acme/text-only")
            self.assertIn("warning: the endpoint doesn't tag acme/text-only as reading images, and pages are read as "
                          "images (vision): `semantic-pdf-diff config test --model acme/text-only` tries it", out)
            code, out = self.config("set", "model", "google/gemma-4-31B-it")  # a store's, checked alike
            self.assertTrue(out.endswith("google/gemma-4-31B-it is among the endpoint's models\n"), out)
            with socket.socket() as s:  # a port nothing listens on
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
            with patch.dict(os.environ, {"OPENAI_BASE_URL": f"http://127.0.0.1:{port}/v1"}):
                code, out = self.config("set", "--user", "model", "gemma-4")
        self.assertEqual(code, 0)
        self.assertIn(f"not checked: the endpoint at http://127.0.0.1:{port}/v1 can't be asked for its models "
                      "(URLError", out)

    def test_a_reranker_or_embedding_models_name_checked_as_one(self):
        listed = (*self.LISTED, {"id": "BAAI/bge-m3", "metadata": {"tags": ["embed"]}})
        with endpoint(listed=listed), user_settings({}):
            self.assertIn("warning: the endpoint lists google/gemma-4-31B-it as a chat model, not an embedding model "
                          "(embed_model): `semantic-pdf-diff config test --embed google/gemma-4-31B-it` tries it",
                          self.config("set", "--user", "embed_model", "google/gemma-4-31B-it")[1])
            self.assertIn("warning: the endpoint lists BAAI/bge-m3 as an embedding model, not a chat model (model)",
                          self.config("set", "--user", "model", "BAAI/bge-m3")[1])
            self.assertTrue(self.config("set", "--user", "embed_model", "BAAI/bge-m3")[1].endswith(
                "BAAI/bge-m3 is among the endpoint's models\n"))
            self.config("set", "--user", "rerank_url", "http://rerank.example/v1/rerank")
            self.assertIn("not checked: a reranker served apart, at http://rerank.example/v1/rerank, isn't among the "
                          "endpoint's models", self.config("set", "--user", "rerank_model", "bge-reranker")[1])

    def test_the_models_checked_marked_with_what_was_measured(self):
        with endpoint(listed=self.LISTED), user_settings({"model": "google/gemma-4-31B-it"}):
            self.config("test")
            code, out = self.config("models")
            self.assertEqual(code, 0)
            self.assertEqual(out.splitlines(), [
                "acme/text-only                  chat",
                "google/gemma-4-31B-it  (model)  chat  262,144 tokens  vision  checked: json, image, acuity (an "
                "image 258 tokens; capitals 6.9 px read)"])
            listed = json.loads(self.config("models", "--json")[1])
        self.assertEqual({k: sorted(v) for k, v in listed[1]["checked"].items()},
                         {"json": ["at", "context_tokens"], "image": ["at", "image_tokens", "side"],
                          "acuity": ["at", "legible_px", "read", "side"]})

class KeysOfTheirOwn(Remembered):
    """A reranker's and an embedding model's keys from variables of their own (the owner, 2026-11-02: "We could enable
    users to assign reranker and embedding model their own key, but the key must never be stored; they could specify
    environment variables where to find the key, though.")."""
    def test_each_model_sent_the_key_its_variable_holds_and_none_kept(self):
        sent = {}

        def post(handler):
            body = request_body(handler)
            sent[handler.path.rsplit("/", 1)[-1]] = handler.headers.get("Authorization")
            if handler.path.endswith("/rerank"):
                handler.send_response(200)
                handler.end_headers()
                handler.wfile.write(json.dumps([{"index": 1, "score": 0.02}, {"index": 0, "score": 0.91}]).encode())
            else:
                rows = [{"index": i, "embedding": [float("pump" in t), float("door" in t), 0.1]}
                        for i, t in enumerate(body["input"])]
                handler.send_response(200)
                handler.end_headers()
                handler.wfile.write(json.dumps({"data": rows}).encode())
        keys = {"OPENAI_API_KEY": "chat-key-1", "RERANK_KEY": "rerank-key-2"}
        with serving(post) as url, patch.dict(os.environ, {"OPENAI_BASE_URL": url, **keys}), \
                user_settings({"model": "gemma-4", "rerank_model": "r", "rerank_api": "tei",
                               "rerank_url": url + "/rerank", "rerank_key_env": "RERANK_KEY", "embed_model": "e",
                               "embed_key_env": "EMBED_KEY"}):
            code, out = self.config("test", "--only", "reranker,embedding")
            kept = saved_settings()
            remembered = self.memory.read_text()
            refused = self.config("set", "--user", "embed_key_env", "rerank-key-2")[1]
        self.assertEqual(code, 0, out)
        self.assertEqual(sent, {"rerank": "Bearer rerank-key-2", "embeddings": None})  # EMBED_KEY unset: no key
        self.assertEqual((kept["rerank_key_env"], kept["embed_key_env"]), ("RERANK_KEY", "EMBED_KEY"))
        self.assertFalse(any(k in json.dumps(kept) + remembered for k in keys.values()))
        self.assertIn("this names an environment variable holding a key", refused)
        self.assertNotIn("rerank-key-2", refused)  # a key given in its place isn't said back
        s = Settings(model="m", rerank_model="r", rerank_key_env="RERANK_KEY")
        self.assertIn("reranker r (its key from $RERANK_KEY, which isn't set: asked without a key)",
                      checkup.guidance(s)[0])

    def test_the_endpoints_key_from_model_key_env_and_the_others_given_it(self):
        """model_key_env (the owner, 2026-11-02: "For consistency, we should add a `model_env_key` option. The others
        default to this one, and it defaults to `OPENAI_API_KEY` IIRC.")."""
        from semantic_pdf_diff.llm import Client
        sent = {}

        def post(handler):
            request_body(handler)
            sent[handler.path.rsplit("/", 1)[-1]] = handler.headers.get("Authorization")
            handler.send_response(200)
            handler.end_headers()
            handler.wfile.write(json.dumps([{"index": 1, "score": 0.02}, {"index": 0, "score": 0.91}]).encode())
        keys = {"OPENAI_API_KEY": "default-key-1", "CHAT_KEY": "chat-key-2"}
        with serving(post) as url, patch.dict(os.environ, {"OPENAI_BASE_URL": url, **keys}), \
                user_settings({"model": "gemma-4", "model_key_env": "CHAT_KEY", "rerank_model": "r",
                               "rerank_api": "tei", "rerank_url": url + "/rerank"}):
            code, out = self.config("test", "--only", "reranker")
            kept = saved_settings()
            refused = self.config("set", "--user", "model_key_env", "chat-key-2")[1]
            shown = self.config("show")[1]
            asked = (Client(Settings(model_key_env="CHAT_KEY"), None).api_key, Client(Settings(), None).api_key)
        self.assertEqual(code, 0, out)
        self.assertEqual(sent, {"rerank": "Bearer chat-key-2"})  # no key of its own: the endpoint's
        self.assertEqual(asked, ("chat-key-2", "default-key-1"))
        self.assertEqual(kept["model_key_env"], "CHAT_KEY")
        self.assertFalse(any(k in json.dumps(kept) + shown + refused for k in keys.values()))
        self.assertIn("this names an environment variable holding a key", refused)
        self.assertRegex(shown, r"\n  CHAT_KEY +set\n")
        self.assertEqual(Settings().model_key_env, "OPENAI_API_KEY")
        self.assertIn("m at http://localhost:8000/v1 (its key from $CHAT_KEY, which isn't set: asked without a key)",
                      checkup.guidance(Settings(model="m", model_key_env="CHAT_KEY"))[0])
        self.assertNotIn("its key", checkup.guidance(Settings(model="m"))[0])
        self.assertEqual(checkup.advice([checkup.Check("key", False, "refused (HTTP 401)")], "CHAT_KEY"),
                         ["the endpoint refused the key: CHAT_KEY holds the one it takes"])

class EyeCards(unittest.TestCase):
    """The acuity check's cards (acuity.py): the eye test's read family, a card a size (the owner, 2026-11-02: "Go
    ahead with the per-size probe cards.")."""
    def test_each_card_holds_its_lines_at_its_size(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as d:
            drawn = acuity.cards(d, random.Random(1), 1000)
            self.assertEqual([size for size, _, _ in drawn], list(acuity.SIZES))
            for size, path, lines in drawn:
                self.assertEqual(len(lines), acuity.LINES)
                self.assertTrue(all(line.strip() for line in lines))
                with pymupdf.open(path) as image:
                    self.assertEqual(tuple(image[0].rect)[2:], (1000, 1000))
        for seed in range(20):  # what's drawn is what's scored: the lines are the page's text, whole
            for size in acuity.SIZES:
                page, lines = acuity.drawn(random.Random(seed), size, 1000)
                self.assertEqual(acuity.norm(page.get_text()).split(),
                                 [acuity.norm(t) for line in lines for t in line.split()])

    def test_items_are_scored_in_order_and_fitted_as_the_eye_test_does(self):
        lines = ["HX-402   31.6   K7Q", "\u00b10.05   2'-9 1/2\"   RT58"]
        self.assertEqual(acuity.score(lines, ["hx-402 31.6 K7Q", "±0.05 2\u2032-9 1/2\u2033 RT58"]), 1.0)
        self.assertEqual(acuity.score(lines, ["HX-402 K7Q 31.6"]), 2 / 7)  # in order: the rest is misread
        self.assertEqual(acuity.score(lines, []), 0.0)
        # a dip at 8 px is averaged with 7's (reading only gets easier), then 90% is reached between 6 and 7 px
        self.assertEqual(acuity.threshold([(8, 0.95), (5, 0.0), (6, 0.5), (7, 1.0), (10, 1.0)]), 6.8)
        self.assertEqual(acuity.threshold([(5, 0.95), (6, 1.0)]), 5.0)
        self.assertIsNone(acuity.threshold([(14, 0.5), (16, 0.85)]))

if __name__ == "__main__":
    unittest.main()
