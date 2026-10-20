"""The rerank lever (rerank.py; docs/plans/portable-reports-2026-10-19.md, milestone 5): in proposals mode, each claim's
candidates scored by a reranker before the judge; pairs below the threshold not judged, the rest judged best first;
its requests recorded and replayed like the judge's. The owner, 2026-10-20, on the measured proposal: "Yes, please."
"""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from stubs import chat_answer, prompt_of, request_body, serving, source_data, user_settings
from semantic_pdf_diff import cli, rerank
from semantic_pdf_diff.settings import Settings

UNREACHABLE = 'http://127.0.0.1:9/v1'  # replay must never call the model

class Requests(unittest.TestCase):
    def test_the_common_rerank_is_asked_beside_the_chat_endpoint_and_told_the_task(self):
        # the owner, 2026-10-20: "DeepInfra-specific code for rerankers": the /rerank vLLM, llama.cpp, Infinity and
        # LiteLLM serve, after Cohere's and Jina's, is the default
        s = Settings(base_url="http://models.internal:8000/v1", rerank_model="Qwen/Qwen3-Reranker-8B")
        documents = ["The rated power of the fan.", "The volume of the tank."]
        request = rerank.request(s, "The rated power of the pump.", documents)
        self.assertEqual(request.url, "http://models.internal:8000/v1/rerank")
        self.assertEqual(json.loads(request.raw), {"model": "Qwen/Qwen3-Reranker-8B",
                                                   "query": "The rated power of the pump.", "documents": documents,
                                                   "top_n": 2, "instruction": rerank.INSTRUCTION})
        value, usage = request.read({"id": "x", "results": [{"index": 1, "relevance_score": 0.8},
                                                            {"index": 0, "relevance_score": 0.1}],
                                     "usage": {"prompt_tokens": 30, "total_tokens": 30}})
        self.assertEqual((value.scores, usage), ([0.1, 0.8], {"prompt_tokens": 30, "completion_tokens": 0}))
        with self.assertRaises(ValueError):
            request.read({"results": [{"index": 0, "relevance_score": 0.1}]})  # one score for two documents

    def test_deepinfra_is_told_the_task_and_scores_its_first_query_against_every_document(self):
        s = Settings(base_url="https://api.deepinfra.com/v1/openai", rerank_model="Qwen/Qwen3-Reranker-8B",
                     rerank_api="deepinfra")
        documents = ["The rated power of the fan.", "The volume of the tank."]
        request = rerank.request(s, "The rated power of the pump.", documents, ("rerank", "proposals", "x", "A-1"))
        self.assertEqual(request.url, "https://api.deepinfra.com/v1/inference/Qwen/Qwen3-Reranker-8B")
        sent = json.loads(request.raw)
        self.assertEqual(sent["queries"], ["The rated power of the pump."] * 2)
        self.assertEqual(sent["instruction"], rerank.INSTRUCTION)
        value, usage = request.read({"scores": [0.9, 0.001], "input_tokens": 40,
                                     "inference_status": {"cost": 2e-6, "tokens_input": 40}})
        self.assertEqual((value.scores, usage), ([0.9, 0.001], {"prompt_tokens": 40, "completion_tokens": 0,
                                                                  "estimated_cost": 2e-6}))
        with self.assertRaises(ValueError):
            request.read({"scores": [0.9]})  # one score for two documents

    def test_a_query_is_named_by_what_reaches_the_reranker_including_which_reranker(self):
        s = Settings(base_url="https://api.deepinfra.com/v1/openai", rerank_model="m")
        api = lambda name: Settings(base_url=s.base_url, rerank_model="m", rerank_api=name)  # noqa: E731
        name = lambda s, q="q", d=("d",): rerank.request(s, q, list(d)).query  # noqa: E731
        self.assertEqual(name(s), name(s))
        self.assertNotEqual(name(s), name(s, q="other"))
        self.assertNotEqual(name(s), name(s, d=("d", "e")))
        self.assertNotEqual(name(s), name(Settings(base_url=s.base_url, rerank_model="n")))
        self.assertEqual(len({name(api(a)) for a in ("rerank", "deepinfra", "tei")}), 3)

    def test_tei_takes_a_query_and_texts_and_answers_scores_by_index(self):
        s = Settings(rerank_model="bge-reranker-v2-m3", rerank_api="tei", rerank_url="http://reranker:8080/rerank")
        request = rerank.request(s, "q", ["a", "b"])
        self.assertEqual((request.url, json.loads(request.raw)), ("http://reranker:8080/rerank",
                                                                 {"query": "q", "texts": ["a", "b"]}))
        value, usage = request.read([{"index": 1, "score": 0.2}, {"index": 0, "score": 0.7}])
        self.assertEqual((value.scores, usage), ([0.7, 0.2], {}))

    def test_an_api_key_goes_only_to_the_chat_endpoints_host_unless_the_reranker_is_named(self):
        inhouse = Settings(base_url="http://localhost:8000/v1", rerank_model="m", rerank_api="deepinfra")
        with self.assertRaises(ValueError):  # an in-house chat endpoint, DeepInfra's API: never DeepInfra's host
            rerank.endpoint(inhouse)
        self.assertEqual(rerank.endpoint(inhouse.model_copy(update={"rerank_api": "tei"})),
                         "http://localhost:8000/v1/rerank")
        self.assertEqual(rerank.endpoint(Settings(base_url="https://api.deepinfra.com/v1/openai/", rerank_model="m",
                                                  rerank_api="deepinfra")),
                         "https://api.deepinfra.com/v1/inference/m")
        self.assertEqual(rerank.endpoint(Settings(rerank_model="m", rerank_url="https://x/{model}/rank")),
                         "https://x/m/rank")

    def test_the_threshold_is_hundredths_from_1_to_10_and_a_setting_like_any(self):
        # the owner, 2026-10-20: "perhaps 1-10 corresponding to 0.01-0.10 ... Default 3?"
        import argparse
        import os
        from unittest.mock import patch
        from pydantic import ValidationError
        from semantic_pdf_diff.cli import add_run_options, load_settings
        self.assertEqual(Settings().rerank_threshold, 3)
        for wrong in (0, 11):
            with self.assertRaises(ValidationError):
                Settings(rerank_threshold=wrong)
        parser = argparse.ArgumentParser()
        add_run_options(parser)
        with patch.dict(os.environ, {}, clear=True), user_settings({"rerank_model": "m", "rerank_threshold": 5}):
            kept = load_settings(parser.parse_args([]))  # a persistent setting: the user's (`config set --user`)
            flagged = load_settings(parser.parse_args(["--rerank-threshold", "2"]))  # a flag overrides it
        self.assertEqual((kept.rerank_model, kept.rerank_threshold, flagged.rerank_threshold), ("m", 5, 2))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parser.parse_args(["--rerank-threshold", "20"])

    def test_the_lever_acts_in_proposals_mode_with_a_reranker_named(self):
        self.assertFalse(Settings().reranks("proposals"))
        self.assertTrue(Settings(rerank_model="m").reranks("proposals"))
        self.assertFalse(Settings(rerank_model="m").reranks("revisions"))

LINE = re.compile(r"^(\w+) \| ([\w ]+) \| ([\d.]+) \| (\w+)$", re.M)

def model(state):
    """A stub endpoint: claims read from lines "item | property | value | unit", every pair judged different, and a
    reranker (the common /rerank, or tei's) scoring 0.9 the documents naming the query's item, 0.001 the rest."""
    def post(handler):
        body = request_body(handler)
        state['requests'].append(handler.path)
        if handler.path.endswith('/rerank'):
            item = body['query'].split(' of the ', 1)[1].split()[0]
            scores = [0.9 if f'of the {item}' in text else 0.001 for text in body.get('texts') or body['documents']]
            answer = ([{'index': i, 'score': x} for i, x in enumerate(scores)] if 'texts' in body else
                      {'results': sorted(({'index': i, 'relevance_score': x} for i, x in enumerate(scores)),
                                         key=lambda r: -r['relevance_score'])})
            handler.send_response(200)
            handler.end_headers()
            handler.wfile.write(json.dumps(answer).encode())
            return
        prompt = prompt_of(body['messages'][1]['content'])
        if 'Compare exactly' in prompt:
            return chat_answer(handler, {'relation': 'different', 'rationale': 'stub', 'confidence': .9,
                                         'same_conditions': True})
        claims = [{'entity': e, 'attribute': a, 'value': v, 'unit': u, 'kind': 'text', 'quote': m.group(0),
                   'confidence': .9}
                  for m in LINE.finditer(source_data(prompt)) for e, a, v, u in [m.groups()]]
        return chat_answer(handler, {'claims': claims, 'complete': True, 'issues': []})
    return post

class Compared(unittest.TestCase):
    def run_cli(self, root, name, url, *extra, tei=False):
        config = root / 'settings.json'
        config.write_text(json.dumps({'rerank_model': 'stub-reranker', 'topic_names': False, **(
            {'rerank_api': 'tei', 'rerank_url': url.rsplit('/v1', 1)[0] + '/rerank'} if tei else {})}))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            cli.main(['compare', str(root / 'a.md'), str(root / 'b.md'), '--store', str(root / name), '--base-url', url,
                      '--config', str(config), '--no-situate', *extra])
        self.said = err.getvalue()
        return json.loads((root / name / 'report.json').read_text()), json.loads((root / name / 'run.json').read_text())

    def write(self, root):
        (root / 'a.md').write_text("# Plant\n\npump | rated power | 10 | kW\n\nfan | rated power | 3 | kW\n\n"
                                   "valve | rated power | 5 | kW\n")
        (root / 'b.md').write_text("# Plant\n\npump | rated power | 12 | kW\n\nfan | rated power | 4 | kW\n")

    def test_pairs_about_other_items_are_left_unjudged_and_the_rest_judged_best_first(self):
        state = {'requests': []}
        with tempfile.TemporaryDirectory() as d, serving(model(state)) as url:
            root = Path(d)
            self.write(root)
            report, _ = self.run_cli(root, 'out', url)  # the common /rerank, beside the chat endpoint
        evidence = {e['id']: e for e in report['evidence']}
        pairs = [(evidence[f['a']]['entity'], evidence[f['b']]['entity']) for f in report['findings']]
        self.assertEqual(sorted(pairs), [('fan', 'fan'), ('pump', 'pump')])  # pump-fan, valve-pump... ranked out
        self.assertTrue(all(f['rerank_score'] == 0.9 for f in report['findings']))
        reranked = report['retrieval']['reranked']
        self.assertEqual((reranked['model'], reranked['threshold'], reranked['failed']), ('stub-reranker', 0.03, 0))
        self.assertGreater(reranked['below_threshold'], 0)
        valve = next(e['id'] for e in report['evidence'] if e['entity'] == 'valve')
        self.assertEqual(next(u['status'] for u in report['unmatched'] if u['id'] == valve), 'ranked_out')
        self.assertEqual(sum(1 for p in state['requests'] if p == '/v1/rerank'), reranked['requests'])

    def test_a_reranker_not_served_there_is_said_and_every_pair_judged(self):
        state, answer = {'requests': []}, None

        def post(handler):
            if handler.path.endswith('/rerank'):  # DeepInfra's chat endpoint serves no /rerank
                handler.send_response(404)
                handler.end_headers()
                handler.wfile.write(b'{"detail": "Not Found"}')
                return
            return answer(handler)
        answer = model(state)
        with tempfile.TemporaryDirectory() as d, serving(post) as url:
            root = Path(d)
            self.write(root)
            report, _ = self.run_cli(root, 'out', url)
        warned = [line for line in self.said.splitlines() if line.startswith('The reranker')]
        self.assertEqual(len(warned), 1, self.said)
        self.assertIn(f'at {url}/rerank: 3 of 3 requests failed (', warned[0])
        self.assertIn('rerank_api and rerank_url', warned[0])
        self.assertEqual(report['retrieval']['reranked']['failed'], 3)
        self.assertEqual(len(report['findings']), 6)  # every candidate pair judged: 3 claims by 2

    def test_reranker_answers_are_recorded_and_replayed(self):
        state = {'requests': []}
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.write(root)
            fixture = root / 'answers.sqlite'
            with serving(model(state)) as url:
                live, _ = self.run_cli(root, 'live', url, '--fixture', str(fixture), '--fixture-mode',
                                       'replay-or-record', tei=True)
            replayed, run = self.run_cli(root, 'replayed', UNREACHABLE, '--fixture', str(fixture), '--fixture-mode',
                                         'replay', tei=True)
        self.assertEqual(run['usage']['api_calls'], 0)
        self.assertEqual([(f['a'], f['b'], f['rerank_score']) for f in replayed['findings']],
                         [(f['a'], f['b'], f['rerank_score']) for f in live['findings']])

if __name__ == '__main__':
    unittest.main()
