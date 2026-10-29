"""The embed lever (embed.py; docs/plans/search-2026-10-20.md, milestone 5): claims embedded after the comparison, for a
search by meaning: near:ID, like:ID blending meaning in, and meaning:"..." from the command line. Its requests recorded
and replayed like the judge's. The owner, 2026-10-20: "Please proceed with that and the model-supported search
ideas."
"""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from stubs import chat_answer, prompt_of, request_body, serving, source_data
from semantic_pdf_diff import cli, embed, fixtures
from semantic_pdf_diff.dispatch import Dispatcher
from semantic_pdf_diff.llm import Client
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.store import Store
from test_portable_report import search_report, toy_vector

UNREACHABLE = "http://127.0.0.1:9/v1"  # replay must never call the model

def embedding_model(asked):
    """A stub /embeddings endpoint answering the toy embedding of each input, cut to the dimensions asked."""
    def post(handler):
        body = request_body(handler)
        asked.append(body)
        rows = [{"index": i, "embedding": toy_vector(text)[:body["dimensions"]]}
                for i, text in enumerate(body["input"])]
        handler.send_response(200)
        handler.end_headers()
        handler.wfile.write(json.dumps({"data": rows, "usage": {"prompt_tokens": 7 * len(rows)}}).encode())
    return post

def uncut_model(asked):
    """A stub /embeddings endpoint serving a model that can't be cut, as vLLM does: dimensions refused (HTTP 400, why
    in JSON), else the toy embedding of each input, all 32 of its dimensions."""
    def post(handler):
        body = request_body(handler)
        asked.append(body)
        if "dimensions" in body:
            handler.send_response(400, "Bad Request")
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"error": {
                "message": f'Model "{body["model"]}" does not support matryoshka representation, changing output '
                           "dimensions will lead to poor results.", "type": "invalid_request_error"}}).encode())
            return
        rows = [{"index": i, "embedding": toy_vector(text)} for i, text in enumerate(body["input"])]
        handler.send_response(200)
        handler.end_headers()
        handler.wfile.write(json.dumps({"data": rows}).encode())
    return post

class Vectors(unittest.TestCase):
    def test_kept_small_and_compared_by_cosine(self):
        kept = embed.packed([3.0, 4.0])
        self.assertEqual(embed.unpacked(kept), [76, 102])  # unit length, x 127
        self.assertAlmostEqual(embed.cosine(embed.unpacked(kept), [76, 102]), 1.0)
        self.assertAlmostEqual(embed.cosine([127, 0], [0, -127]), 0.0)
        self.assertEqual(embed.unpacked(embed.packed([-1.0, 0.0])), [-127, 0])

    def test_a_request_asks_the_dimensions_and_reads_vectors_in_order(self):
        s = Settings(base_url="https://api.deepinfra.com/v1/openai", embed_model="Qwen/Qwen3-Embedding-8B",
                     embed_dimensions=64)
        request = embed.request(s, ["a", "b"])
        self.assertEqual(request.url, "https://api.deepinfra.com/v1/openai/embeddings")
        self.assertEqual(json.loads(request.raw), {"model": "Qwen/Qwen3-Embedding-8B", "input": ["a", "b"],
                                                    "dimensions": 64, "encoding_format": "float"})
        value, usage = request.read({"data": [{"index": 1, "embedding": [0.0, 1.0]},
                                              {"index": 0, "embedding": [1.0, 0.0]}],
                                     "usage": {"prompt_tokens": 4}})
        self.assertEqual([embed.unpacked(v) for v in value.vectors], [[127, 0], [0, 127]])
        self.assertEqual(usage, {"prompt_tokens": 4, "completion_tokens": 0})
        with self.assertRaises(ValueError):
            request.read({"data": [{"index": 0, "embedding": [1.0]}]})  # one vector for two texts
        typed = json.loads(embed.request(s, ["rated output"], query=True).raw)["input"][0]
        self.assertEqual(typed, f"Instruct: {embed.INSTRUCTION}\nQuery: rated output")
        name = lambda **k: embed.request(Settings(**{"embed_model": "m", **k}), ["a"]).query  # noqa: E731
        self.assertNotEqual(name(), name(embed_dimensions=128))
        self.assertNotEqual(name(), name(embed_model="n"))
        self.assertEqual(embed.endpoint(Settings(embed_model="m", embed_url="http://e:80/{model}/embed")),
                         "http://e:80/m/embed")

class Embedded(unittest.TestCase):
    def test_each_sentence_once_recorded_and_replayed(self):
        evidence = search_report()["evidence"]
        evidence.append({**evidence[0], "id": "A-again"})  # says what A-pump says: one sentence, one vector
        asked = []
        with tempfile.TemporaryDirectory() as d, serving(embedding_model(asked)) as url:
            fixture_path = Path(d) / "answers.sqlite"
            s = Settings(base_url=url, embed_model="toy", embed_dimensions=32)
            client = Client(s, None, fixture=fixtures.open(fixture_path, "record"), mode="replay-or-record")
            with Dispatcher(client) as dispatch:
                kept = embed.embedded(evidence, dispatch, s, "label")
            client.close()
            self.assertEqual((kept["requests"], kept["failed"], len(kept["vectors"])), (1, 0, 13))
            self.assertEqual(kept["of"]["A-again"], kept["of"]["A-pump"])
            self.assertEqual(len(asked[0]["input"]), 13)
            replay = Client(Settings(base_url=UNREACHABLE, embed_model="toy", embed_dimensions=32), None,
                            fixture=fixtures.open(fixture_path, "replay"), mode="replay")
            with Dispatcher(replay) as dispatch:
                again = embed.embedded(evidence, dispatch, replay.s, "label")
            replay.close()
        self.assertEqual(again, kept)

    def test_a_failed_request_leaves_its_claims_without_vectors(self):
        evidence = search_report()["evidence"]
        s = Settings(base_url=UNREACHABLE, embed_model="toy", embed_dimensions=32, retries=0)
        with tempfile.TemporaryDirectory() as d:
            client = Client(s, None, fixture=fixtures.open(Path(d) / "answers.sqlite", "record"),
                            mode="replay-or-record")
            with Dispatcher(client) as dispatch, self.assertLogs("semantic_pdf_diff", "WARNING") as said:
                kept = embed.embedded(evidence, dispatch, s, "label")
            client.close()
        self.assertEqual((kept["failed"], kept["vectors"], kept["of"]), (1, [], {}))
        self.assertIn(f"toy at {UNREACHABLE}/embeddings: 1 of 1 requests failed (", said.output[-1])

    def test_a_model_that_cant_be_cut_is_asked_again_without_dimensions(self):
        """The owner, 2026-10-29: "I still cannot get embeddings to work [...] Getting an `HTTP 400: Bad Request`"."""
        evidence, asked = search_report()["evidence"], []
        with serving(uncut_model(asked)) as url:
            s = Settings(base_url=url, embed_model="toy", embed_dimensions=64, retries=0, stop_after_failures=1)
            client = Client(s, None)
            with Dispatcher(client) as dispatch:
                kept = embed.embedded(evidence, dispatch, s, "label")
            client.close()
        self.assertEqual((kept["requests"], kept["failed"], len(kept["vectors"])), (1, 0, 13))
        self.assertEqual([sorted(body) for body in asked], [["dimensions", "encoding_format", "input", "model"],
                                                            ["input", "model"]])
        self.assertEqual(len(embed.unpacked(kept["vectors"][0])), 32)  # the model's own size
        self.assertIsNone(client.transport.failing)  # the refusal isn't the endpoint failing

    def test_a_refusal_says_why_the_server_refused(self):
        def refusing(handler):
            request_body(handler)
            handler.send_response(400, "Bad Request")
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(b'{"error": {"message": "input is too long:\\n 600 tokens, at most 512"}}')
        with serving(refusing) as url:
            s = Settings(base_url=url, embed_model="toy", retries=0)
            client = Client(s, None)
            with self.assertRaises(Exception) as refused:
                client.transport.send(embed.request(s, ["a"]))
            client.close()
        self.assertEqual(str(refused.exception), "HTTP 400: Bad Request: input is too long: 600 tokens, at most 512")

LINE = re.compile(r"^(\w+) \| ([\w ]+) \| ([\d.]+) \| (\w+)$", re.M)

def endpoint(state):
    """A stub endpoint: claims read from lines "item | property | value | unit", every pair judged different, the
    other names asked for answered (the pump is the impeller), and /embeddings answering the toy embedding."""
    embeddings = embedding_model(state["embedded"])

    def post(handler):
        if handler.path.endswith("/embeddings"):
            return embeddings(handler)
        body = request_body(handler)
        prompt = prompt_of(body["messages"][1]["content"])
        if "Compare exactly" in prompt:
            return chat_answer(handler, {"relation": "different", "rationale": "stub", "confidence": .9,
                                         "same_conditions": True})
        if "Find the names" in prompt:
            state["names"] += 1
            return chat_answer(handler, {"items": [["pump", "impeller"]], "properties": []})
        claims = [{"entity": e, "attribute": a, "value": v, "unit": u, "kind": "text", "quote": m.group(0),
                   "confidence": .9}
                  for m in LINE.finditer(source_data(prompt)) for e, a, v, u in [m.groups()]]
        return chat_answer(handler, {"claims": claims, "complete": True, "issues": []})
    return post

class Compared(unittest.TestCase):
    def test_a_comparison_embeds_its_claims_and_asks_their_other_names(self):
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(endpoint(state)) as url:
            root = Path(d)
            (root / "a.md").write_text("# Plant\n\npump | rated power | 10 | kW\n\nfan | rated power | 3 | kW\n")
            (root / "b.md").write_text("# Plant\n\nimpeller | rated power | 12 | kW\n\nfan | rated power | 4 | kW\n")
            config = root / "settings.json"
            config.write_text(json.dumps({"embed_model": "toy", "embed_dimensions": 32, "search_names": True,
                                          "topic_names": False}))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main(["compare", str(root / "a.md"), str(root / "b.md"), "--store", str(root / "out"),
                          "--base-url", url, "--config", str(config), "--no-situate"])
            report = json.loads((root / "out" / "report.json").read_text())
            page = (root / "out" / "report.html").read_text()
            code, out, _ = run("search", "impeller", "--store", root / "out")
        self.assertEqual(report["synonyms"]["items"], [["pump", "impeller"]])
        self.assertEqual(state["names"], 1)
        self.assertEqual((report["vectors"]["model"], report["vectors"]["dimensions"]), ("toy", 32))
        self.assertEqual(sorted(report["vectors"]["of"]), sorted(e["id"] for e in report["evidence"]))
        self.assertEqual(len(state["embedded"]), 1)
        from test_portable_report import parts_of
        self.assertEqual(len(parts_of(page)["vectors"]["of"]), len(report["evidence"]))
        self.assertEqual(code, 0)
        self.assertIn("The model's other names for it: \"pump\"", out)  # the pump is a counterpart here already

def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()

class Meaning(unittest.TestCase):
    """meaning:"..." from the command line: what's typed, embedded as the claims were, through the answers cache."""
    def test_what_is_typed_finds_the_claims_nearest_in_meaning_once_asked(self):
        asked = []
        with tempfile.TemporaryDirectory() as d, serving(embedding_model(asked)) as url, \
                patch.dict(os.environ, {"OPENAI_BASE_URL": url}):
            folder = Path(d) / "store"
            with Store(folder) as store:
                store.save_comparison("2026-10-20T00:00:00", search_report())
            code, out, _ = run("search", 'meaning:"heaters"', "--store", folder)
            self.assertEqual(code, 0)
            self.assertEqual(out.splitlines()[0], "2 claims found: 1 in A; 1 in B")
            self.assertIn("heater", out.splitlines()[1])
            self.assertEqual([a["model"] for a in asked], ["toy"])
            self.assertTrue(asked[0]["input"][0].endswith("Query: heaters"))
            run("search", 'meaning:"heaters"', "--store", folder)
            self.assertEqual(len(asked), 1)  # asked again: the answers cache's

    def test_without_vectors_meaning_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "store"
            data = search_report()
            del data["vectors"]
            with Store(folder) as store:
                store.save_comparison("2026-10-20T00:00:00", data)
            with self.assertRaises(SystemExit):
                run("search", 'meaning:"heaters"', "--store", folder)

if __name__ == "__main__":
    unittest.main()
