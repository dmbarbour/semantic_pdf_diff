"""Reranking a comparison's candidate pairs before the judge (the rerank lever; portable reports, milestone 5).
Retrieval's candidates share words; in proposals mode most are judged unrelated (the same property of another item, the
same item's other property), and the pair cap leaves the rest unjudged. A cross-encoder told the task scores each
claim's candidates; pairs below a threshold (rerank_threshold, in hundredths) aren't judged, and the judge takes
the rest best first.

Measured offline on six recorded proposals runs (2026-10-20): Qwen3-Reranker-8B, told the task and given claims as
sentences, kept every pair the judge called equivalent or different at a threshold of 0.02, and left 26-64% of the
unrelated unjudged in five of them; end to end, none was lost at 0.02, 0.05 or 0.1. As a search engine's reranker (no
instruction) it was no better than TF-IDF.

A reranker's request is a query like any other (llm.Request): named by what reaches the reranker, recorded, replayed and
cached as the judge's are, and counted under the caps. Two endpoints:
- deepinfra: DeepInfra's inference API (POST {"queries", "documents", "instruction"}), which scores the first query
  against every document; its cost is in inference_status.
- tei: Hugging Face's text-embeddings-inference /rerank (POST {"query", "texts"}), answering [{"index", "score"}]; no
  instruction (its cross-encoders, bge-reranker and ms-marco, take none).
"""
import hashlib
import json

from .llm import Request
from .recipes import Recipe
from .schema import Ranking

# What the reranker is told the task is (deepinfra's instruction field), and the version of how a request is built.
INSTRUCTION = ("Given a claim from one engineering design document, retrieve claims from another design that state the "
               "same property of the same kind of component, so that their values can be compared")
VERSION = 1

def sentence(claim):
    """A claim as the reranker reads it: "The rated power of the rotor, for 10 m/s." (its subject; its value is what a
    comparison asks about, not what makes two claims counterparts)."""
    scope = f", for {claim.conditions}" if claim.conditions else ""
    return f"The {claim.attribute} of the {claim.entity}{scope}."

def endpoint(s):
    """Where the settings' reranker is asked: rerank_url ({model} filled in), else DeepInfra's inference API where the
    chat endpoint is DeepInfra's; anywhere else rerank_url must be set (an API key isn't sent where it wasn't meant)."""
    if s.rerank_url:
        return s.rerank_url.replace("{model}", s.rerank_model)
    if "api.deepinfra.com" in s.base_url:
        return f"https://api.deepinfra.com/v1/inference/{s.rerank_model}"
    raise ValueError(f"rerank_model is {s.rerank_model!r} but no rerank_url is set for the endpoint {s.base_url}")

def request(s, query, documents, key=None):
    """A request scoring documents against query with the settings' reranker (s.rerank_model, s.rerank_api)."""
    instructed = s.rerank_api == "deepinfra"
    canonical = {"rerank": s.rerank_model, "api": s.rerank_api, "version": VERSION,
                 "instruction": INSTRUCTION if instructed else "", "query": query, "documents": list(documents)}
    name = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    prompt = "\n".join([f"RERANK {s.rerank_model} ({s.rerank_api})", *([INSTRUCTION] if instructed else []),
                        "QUERY: " + query, "DOCUMENTS:", *(f"{i}. {d}" for i, d in enumerate(documents, 1))])

    def body():
        sent = ({"queries": [query] * len(documents), "documents": list(documents), "instruction": INSTRUCTION}
                if instructed else {"query": query, "texts": list(documents)})
        return json.dumps(sent).encode()

    def read(result):
        """(the scores, usage as the chat endpoint reports it)."""
        if instructed:
            scores, status = result["scores"], result.get("inference_status") or {}
            usage = {"prompt_tokens": int(result.get("input_tokens") or status.get("tokens_input") or 0),
                     "completion_tokens": 0}
            if isinstance(status.get("cost"), (int, float)):
                usage["estimated_cost"] = float(status["cost"])
        else:
            scores, usage = [x["score"] for x in sorted(result, key=lambda x: x["index"])], {}
        if len(scores) != len(documents):
            raise ValueError(f"{len(scores)} scores for {len(documents)} documents")
        return Ranking(scores=[float(x) for x in scores]), usage

    words = len(prompt.encode()) // 3 + 64
    return Request(body, Recipe(key) if key is not None else None, Ranking, words, prompt, (), query=name,
                   description={"template": "rerank", "source_type": "", "text_chars": len(prompt), "image_bytes": [],
                                "params": {"rerank": s.rerank_model}},
                   url=endpoint(s), model=s.rerank_model, read=read)

def ranked(pairs, dispatch, client, mode, label):
    """The candidate pairs ((retrieval score, a, b), best first) the judge takes, reranked: each claim's candidates
    scored in one request; pairs below the threshold left out, the rest best first by the reranker (a pair whose
    request failed keeps the threshold's score). Returns (the pairs kept, {(a id, b id): score}, a summary)."""
    s = client.s
    candidates = {}
    for retrieved, a, b in pairs:
        candidates.setdefault(a.id, (a, []))[1].append(b)
    scores, failed = {}, 0

    def finish(a, bs):
        def done(value, error):
            nonlocal failed
            if error is not None:
                failed += 1
                return
            for b, score in zip(bs, value.scores):
                scores[a.id, b.id] = round(score, 4)
        return done

    for aid in sorted(candidates):
        a, bs = candidates[aid]
        bs = sorted(bs, key=lambda b: b.id)
        dispatch.make_room()
        dispatch.submit_request(request(s, sentence(a), [sentence(b) for b in bs], ("rerank", mode, label, a.id)),
                                finish(a, bs))
    dispatch.drain()
    least = s.rerank_threshold / 100  # the setting's 1-10 are hundredths
    score = lambda p: scores.get((p[1].id, p[2].id), least)
    kept = sorted((p for p in pairs if score(p) >= least), key=lambda p: (-score(p), -p[0], p[1].id, p[2].id))
    summary = {"model": s.rerank_model, "threshold": least, "requests": len(candidates), "failed": failed,
               "below_threshold": len(pairs) - len(kept)}
    return kept, scores, summary
