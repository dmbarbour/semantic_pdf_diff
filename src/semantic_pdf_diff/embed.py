"""Claims embedded by a model, for a search by meaning (docs/plans/search-2026-10-20.md, milestone 5; the embed lever):
`near:ID` in the page and the command line, the claims most like a claim in meaning, and `meaning:"..."` from the
command line, which embeds what's typed too.

A claim is embedded as the sentence the reranker reads ("The rated power of the rotor, for 10 m/s.": what it's about,
not its value), each distinct sentence once, EMBED_A_REQUEST to a request. A request is a query like any other
(llm.Request): named by what reaches the model, recorded, replayed and cached as the judge's are. Its answer is kept
small: each vector, of the dimensions asked for (embed_dimensions; a model trained to be cut, as Qwen3-Embedding is,
answers any), unit length, its components as signed bytes in base64. Cosine of two: their bytes' dot product over
their lengths.

The OpenAI-compatible /embeddings endpoint ({"model", "input", "dimensions"}), the chat endpoint's own unless embed_url
names another.
"""
import base64
import hashlib
import json
import math

from .llm import Request
from .rerank import sentence

VERSION = 1  # of how a request is built
EMBED_A_REQUEST = 64
# how a search's text is put to an embedding model trained with instructions (Qwen3-Embedding): a claim as it is, a
# query told the task
INSTRUCTION = "Given what a reader looks for in engineering documents, retrieve the claims that state it"

def endpoint(s):
    return (s.embed_url or s.base_url.rstrip("/") + "/embeddings").replace("{model}", s.embed_model or "")

def packed(vector):
    """A vector as kept: unit length, each component a signed byte (x 127), in base64."""
    length = math.sqrt(sum(x * x for x in vector)) or 1.0
    return base64.b64encode(bytes((round(x / length * 127) & 0xFF) for x in vector)).decode("ascii")

def unpacked(text):
    """A kept vector's components, as signed bytes."""
    return [b - 256 if b > 127 else b for b in base64.b64decode(text)]

def cosine(a, b):
    """Two kept vectors' cosine (unpacked)."""
    dot = sum(x * y for x, y in zip(a, b))
    return dot / ((math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))) or 1.0)

def request(s, texts, key=None, query=False):
    """A request embedding texts with the settings' model (s.embed_model, s.embed_dimensions); query: a search's text,
    told the task."""
    from .schema import Vectors
    sent = [f"Instruct: {INSTRUCTION}\nQuery: {t}" if query else t for t in texts]
    canonical = {"embed": s.embed_model, "dimensions": s.embed_dimensions, "version": VERSION, "input": sent}
    name = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    prompt = "\n".join([f"EMBED {s.embed_model} ({s.embed_dimensions} dimensions)", *sent])

    def body():
        return json.dumps({"model": s.embed_model, "input": sent, "dimensions": s.embed_dimensions,
                           "encoding_format": "float"}).encode()

    def read(result):
        """(the vectors, kept small, in order; usage as the chat endpoint reports it)."""
        rows = sorted(result["data"], key=lambda x: x["index"])
        if len(rows) != len(texts):
            raise ValueError(f"{len(rows)} vectors for {len(texts)} texts")
        usage = result.get("usage") or {}
        out = {"prompt_tokens": int(usage.get("prompt_tokens") or 0), "completion_tokens": 0}
        if isinstance(usage.get("estimated_cost"), (int, float)):
            out["estimated_cost"] = float(usage["estimated_cost"])
        return Vectors(vectors=[packed(r["embedding"]) for r in rows]), out

    words = len(prompt.encode()) // 3 + 64
    return Request(body, None if key is None else key, Vectors, words, prompt, (), query=name,
                   description={"template": "embed", "source_type": "", "text_chars": len(prompt), "image_bytes": [],
                                "params": {"embed": s.embed_model, "dimensions": s.embed_dimensions}},
                   url=endpoint(s), model=s.embed_model, read=read)

def embedded(evidence, dispatch, s, label):
    """The claims' vectors, as a report keeps them: {"model", "dimensions", "vectors": [kept vectors], "of": {claim's
    id: its vector's index}, "requests", "failed"}; a claim whose request failed has none."""
    from .recipes import Recipe
    of_sentence = {}
    for e in evidence:
        of_sentence.setdefault(sentence_of(e), []).append(e["id"])
    sentences = sorted(of_sentence)
    vectors, of, failed = [None] * len(sentences), {}, 0

    def finish(start, count):
        def done(value, error):
            nonlocal failed
            if error is not None:
                failed += 1
                return
            vectors[start:start + count] = value.vectors
        return done

    batches = range(0, len(sentences), EMBED_A_REQUEST)
    for start in batches:
        texts = sentences[start:start + EMBED_A_REQUEST]
        dispatch.make_room()
        dispatch.submit_request(request(s, texts, Recipe(("embed", label, str(start // EMBED_A_REQUEST)))),
                                finish(start, len(texts)))
    dispatch.drain()
    kept = []
    for text, vector in zip(sentences, vectors):
        if vector is None:
            continue
        for claim in of_sentence[text]:
            of[claim] = len(kept)
        kept.append(vector)
    return {"model": s.embed_model, "dimensions": s.embed_dimensions, "vectors": kept, "of": of,
            "requests": len(batches), "failed": failed}

class Claim:
    """A claim's fields as rerank.sentence reads them, from a report's evidence (a dict)."""
    def __init__(self, e):
        self.entity, self.attribute, self.conditions = e["entity"], e["attribute"], e.get("conditions", "")

def sentence_of(e):
    return sentence(Claim(e))
