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
cached as the judge's are, and counted under the caps. Three APIs (rerank_api), none assumed of an endpoint (the owner,
2026-10-20, of the first version: "DeepInfra-specific code for rerankers"):
- rerank: the /rerank most servers take, after Cohere's and Jina's (vLLM, llama.cpp, Infinity, LiteLLM): POST
  {"model", "query", "documents", "top_n", "instruction"}, answering {"results": [{"index", "relevance_score"}]}. vLLM
  gives the instruction to the model's template (Qwen3-Reranker's); a server whose rerankers take none ignores it.
- deepinfra: DeepInfra's inference API (POST {"queries", "documents", "instruction"}), which scores the first query
  against every document; its cost is in inference_status. DeepInfra serves no /rerank.
- tei: Hugging Face's text-embeddings-inference /rerank (POST {"query", "texts"}), answering [{"index", "score"}]; no
  instruction (its cross-encoders, bge-reranker and ms-marco, take none).
Each is asked at rerank_url, else beside the chat endpoint, on its host: an API key isn't sent where it wasn't meant.
"""
import hashlib
import json
import logging

from .failures import BudgetExceeded
from .llm import Request
from .progress import NoProgress
from .recipes import Recipe
from .schema import Ranking

# What the reranker is told the task is (the instruction field), and the version of how a request is built.
INSTRUCTION = ("Given a claim from one engineering design document, retrieve claims from another design that state the "
               "same property of the same kind of component, so that their values can be compared")
VERSION = 1
log = logging.getLogger("semantic_pdf_diff")

def sentence(claim):
    """A claim as the reranker reads it: "The rated power of the rotor, for 10 m/s." (its subject; its value is what a
    comparison asks about, not what makes two claims counterparts)."""
    scope = f", for {claim.conditions}" if claim.conditions else ""
    return f"The {claim.attribute} of the {claim.entity}{scope}."

def endpoint(s):
    """Where the settings' reranker is asked: rerank_url ({model} filled in), else beside the chat endpoint: its
    /rerank, or for DeepInfra's API its inference API beside the OpenAI-compatible one (.../v1/openai: .../v1/inference/
    MODEL). ValueError where that can't be told."""
    if s.rerank_url:
        return s.rerank_url.replace("{model}", s.rerank_model)
    base = s.base_url.rstrip("/")
    if s.rerank_api != "deepinfra":
        return base + "/rerank"
    if base.endswith("/openai"):
        return base.removesuffix("/openai") + "/inference/" + s.rerank_model
    raise ValueError(f"rerank_api is deepinfra, but the endpoint {base} isn't DeepInfra's OpenAI-compatible one "
                     "(.../v1/openai): set rerank_url")

def request(s, query, documents, key=None):
    """A request scoring documents against query with the settings' reranker (s.rerank_model, s.rerank_api)."""
    instructed = s.rerank_api != "tei"
    canonical = {"rerank": s.rerank_model, "api": s.rerank_api, "version": VERSION,
                 "instruction": INSTRUCTION if instructed else "", "query": query, "documents": list(documents)}
    name = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    prompt = "\n".join([f"RERANK {s.rerank_model} ({s.rerank_api})", *([INSTRUCTION] if instructed else []),
                        "QUERY: " + query, "DOCUMENTS:", *(f"{i}. {d}" for i, d in enumerate(documents, 1))])

    def body():
        if s.rerank_api == "rerank":
            sent = {"model": s.rerank_model, "query": query, "documents": list(documents), "top_n": len(documents),
                    "instruction": INSTRUCTION}
        elif s.rerank_api == "deepinfra":
            sent = {"queries": [query] * len(documents), "documents": list(documents), "instruction": INSTRUCTION}
        else:
            sent = {"query": query, "texts": list(documents)}
        return json.dumps(sent).encode()

    def read(result):
        """(the scores, usage as the chat endpoint reports it)."""
        if s.rerank_api == "rerank":  # most relevant first: put back in order
            scores = [x["relevance_score"] for x in sorted(result["results"], key=lambda x: x["index"])]
            given = result.get("usage") or {}
            usage = {"prompt_tokens": int(given.get("prompt_tokens") or given.get("total_tokens") or 0),
                     "completion_tokens": 0}
        elif s.rerank_api == "deepinfra":
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

def ranked(pairs, dispatch, client, mode, label, progress=None):
    """The candidate pairs ((retrieval score, a, b), best first) the judge takes, reranked: each claim's candidates
    scored in one request; pairs below the threshold left out, the rest best first by the reranker (a pair whose
    request failed keeps the threshold's score). Returns (the pairs kept, {(a id, b id): score}, a summary).
    progress: its requests counted, and a bar of the claims reranked."""
    progress = progress or NoProgress()
    s = client.s
    candidates = {}
    for retrieved, a, b in pairs:
        candidates.setdefault(a.id, (a, []))[1].append(b)
    scores, failed, errors, unsent = {}, 0, [], []

    def finish(a, bs):
        def done(value, error):
            nonlocal failed
            progress.finish("failed" if error is not None else "complete")
            bar.tick()
            if isinstance(error, BudgetExceeded):  # not sent: sending had stopped, or a cap
                unsent.append(error)
                return
            if error is not None:
                failed += 1
                errors.append(error)
                return
            for b, score in zip(bs, value.scores):
                scores[a.id, b.id] = round(score, 4)
        return done

    bar = progress.bar('rerank', len(candidates), 'claims')
    for aid in sorted(candidates):
        a, bs = candidates[aid]
        bs = sorted(bs, key=lambda b: b.id)
        dispatch.make_room()
        progress.add()
        dispatch.submit_request(request(s, sentence(a), [sentence(b) for b in bs], ("rerank", mode, label, a.id)),
                                finish(a, bs))
    dispatch.drain()
    if failed:  # a reranker asked where it isn't served fails every request: said, not left to report.json
        log.warning(f"The reranker {s.rerank_model} at {endpoint(s)}: {failed} of {len(candidates)} requests failed "
                    f"({errors[0]}); their pairs were judged unranked, and the next run asks again. `semantic-pdf-diff "
                    f"config test` checks it; rerank_api and rerank_url say where it's served")
    if unsent:  # the reranker's doing or not: said apart (the owner, 2026-10-29, on a run that paused before it:
        # "reranker: 13,435 requests, 13,435 failed")
        log.warning(f"The reranker {s.rerank_model}: {len(unsent)} of {len(candidates)} requests not sent "
                    f"({unsent[0]}); the next run asks again")
    least = s.rerank_threshold / 100  # the setting's 1-10 are hundredths
    score = lambda p: scores.get((p[1].id, p[2].id), least)
    kept = sorted((p for p in pairs if score(p) >= least), key=lambda p: (-score(p), -p[0], p[1].id, p[2].id))
    summary = {"model": s.rerank_model, "threshold": least, "requests": len(candidates), "failed": failed,
               **({"not_sent": len(unsent)} if unsent else {}), "below_threshold": len(pairs) - len(kept)}
    return kept, scores, summary
