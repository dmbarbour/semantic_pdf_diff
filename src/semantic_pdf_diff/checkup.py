"""`semantic-pdf-diff config test` and `config models` (docs/plans/configuration-in-the-store-2026-10-20.md,
milestone 5, as cameo_ingest's): the endpoint, the key and each model the settings name checked for a few cents, and
the endpoint's models listed.

The checks ask for real: never the answers cache, so a check passes only when the model answers now. The image check
is an eye-test card: a random code drawn large, which can't be guessed, read back exactly (the lab's eye tests measure
how small a model can read: lab/src/semantic_pdf_diff_lab/bench/eyetest.py).
"""
import json
import os
import random
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from .schema import Lenient

LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O or Q, as drawings avoid them
FAILED = 5  # the exit code when a check fails (cameo_ingest's)

class Sum(Lenient):
    sum: int = 0

class Code(Lenient):
    code: str = Field(default="", max_length=40)

@dataclass
class Check:
    name: str
    ok: bool | None  # None: not checked, or nothing to check
    said: str
    seconds: float = 0.0

    def line(self, width=9):  # "embedding" the longest
        mark = {True: "ok", False: "FAILED", None: "--"}[self.ok]
        took = f" ({self.seconds:.1f} s)" if self.seconds >= 0.05 else ""
        return f"  {self.name:<{width}} {mark}: {self.said}{took}"

@dataclass(frozen=True)
class Listed:
    """A model as the endpoint lists it, with what the endpoint says of it, where it says (the owner, 2026-10-20: "We
    could let people know what's available."): its context window in tokens, its price in dollars a million tokens in
    and out, and its tags (DeepInfra's: chat, vision, embed and more; vision too where OpenRouter lists images among
    its inputs)."""
    id: str
    context: int | None = None
    price_in: float | None = None
    price_out: float | None = None
    tags: tuple = ()

    @property
    def reads_images(self):
        return "vision" in self.tags or "vlm" in self.tags

    def described(self):
        """[its context, its price, its tags], each "" where the endpoint doesn't say."""
        prices = [f"${p:.2f} {way}" if p >= 0.01 or not p else f"${p:.2g} {way}"
                  for p, way in ((self.price_in, "in"), (self.price_out, "out")) if p is not None]
        return [f"{self.context:,} tokens" if self.context else "",
                ", ".join(prices) + " a million" if prices else "", ", ".join(self.tags)]

def _count(*values):
    return next((int(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0), None)

def _price(value, scale=1.0):
    try:
        return round(float(value) * scale, 6) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None

def described(item):
    """A /models item as Listed: DeepInfra's metadata (context_length; pricing in dollars a million tokens; tags),
    vLLM's max_model_len, or OpenRouter's fields (context_length; pricing in dollars a token; architecture's input
    modalities)."""
    get = lambda d, k: d.get(k) if isinstance(d, dict) else None  # noqa: E731
    meta, top, arch = (get(item, k) or {} for k in ("metadata", "top_provider", "architecture"))
    context = _count(get(meta, "context_length"), get(item, "context_length"), get(item, "max_model_len"),
                     get(top, "context_length"))
    if isinstance(get(meta, "pricing"), dict):
        price_in, price_out = (_price(get(meta["pricing"], k)) for k in ("input_tokens", "output_tokens"))
    else:
        price_in, price_out = (_price(get(get(item, "pricing"), k), 1e6) for k in ("prompt", "completion"))
    tags = [str(x) for x in (get(meta, "tags") or get(item, "tags") or []) if isinstance(x, str)]
    if "image" in (get(arch, "input_modalities") or []):
        tags.append("vision")
    return Listed(str(item["id"]), context, price_in, price_out, tuple(dict.fromkeys(tags)))

def listed(settings, api_key=""):
    """The endpoint's models (GET {base_url}/models, the OpenAI format) as Listed, sorted by id (case aside); OSError
    or ValueError when they can't be listed."""
    url = settings.base_url.rstrip("/") + "/models"
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + api_key} if api_key else {})
    with urllib.request.urlopen(request, timeout=min(settings.timeout, 30)) as response:
        data = json.load(response)
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("the endpoint's /models answer holds no list of models")
    found = {str(m["id"]): described(m) for m in items if isinstance(m, dict) and m.get("id")}
    return [found[k] for k in sorted(found, key=lambda k: (k.casefold(), k))]

def models(settings, api_key=""):
    """The endpoint's models' ids (listed's order)."""
    return [m.id for m in listed(settings, api_key)]

def used(settings):
    """{model id: the settings naming it}: what the configuration asks."""
    out = {settings.model: ["model"]}
    if settings.rerank_model:
        out.setdefault(settings.rerank_model, []).append("rerank_model")
    if settings.embed_model:
        out.setdefault(settings.embed_model, []).append("embed_model")
    return out

def card(folder, rng):
    """(an eye-test card's PNG path, its code): a random code ("HXR-4027") drawn large on white."""
    import pymupdf
    code = "".join(rng.choices(LETTERS, k=3)) + "-" + "".join(rng.choices("0123456789", k=4))
    page = (doc := pymupdf.open()).new_page(width=300, height=90)
    page.insert_text((24, 60), code, fontsize=40, fontname="helv")
    path = Path(folder) / "card.png"
    page.get_pixmap(dpi=96).save(path)
    doc.close()
    return path, code

def _timed(name, check):
    started = time.monotonic()
    try:
        ok, said = check()
    except Exception as e:  # noqa: BLE001 (a check's failure is its result, whatever it is)
        ok, said = False, f"{type(e).__name__}: {e}"
    return Check(name, ok, said, time.monotonic() - started)

def run(settings, rng=None):
    """Every check, in order: [Check], and what they cost (dollars, as the provider reports it)."""
    from .llm import Client, is_local
    from . import embed
    from .rerank import request as rerank_request
    rng = rng or random.Random()
    client = Client(settings, None)
    key = client.api_key
    checks = []
    listed = []

    def endpoint():  # the chat model only: a reranker or an embedding model may be served apart, and is asked below
        listed.extend(models(settings, key))
        if settings.model not in listed:
            return False, (f"{len(listed)} models listed, not {settings.model} (`config models WORDS` lists those "
                           "like it)")
        return True, f"{len(listed)} models listed, {settings.model} among them"
    checks.append(_timed("endpoint", endpoint))
    if checks[-1].ok is False and not listed and _unreachable(checks[-1].said):
        return checks + [Check(name, None, "skipped: the endpoint isn't reachable") for name in
                         ("json", "image", "reranker", "embedding")], client.cost
    if checks[-1].ok is False and not listed:  # reachable, but listing no models (some servers don't)
        checks[-1] = Check("endpoint", None, "lists no models: " + checks[-1].said, checks[-1].seconds)
    if not key and not is_local(settings.base_url):
        checks.append(Check("key", None, "OPENAI_API_KEY isn't set (a local server may need none)"))

    def answer():
        a, b = rng.randint(11, 89), rng.randint(11, 89)
        got = client.ask(f'Add {a} and {b}. Return only the JSON object {{"sum": N}}.', Sum)
        return got.sum == a + b, f"{a} + {b} = {got.sum}" + ("" if got.sum == a + b else f", not {a + b}")
    checks.append(_timed("json", answer))

    def image():
        with tempfile.TemporaryDirectory(prefix="semantic-pdf-diff-check-") as folder:
            path, code = card(folder, rng)
            got = client.ask('The image shows one code: letters, a dash and digits. Return only the JSON object '
                             '{"code": "..."} with the code exactly as written.', Code, images=(path,))
        read = "".join(got.code.split()).upper()
        return read == code, f'read "{got.code}"' + ("" if read == code else f', not "{code}"')
    checks.append(_timed("image", image) if settings.vision else
                  Check("image", None, "not checked: vision is off"))

    def reranker():
        ranking = _asked(rerank_request(settings, "The rated power of the feed pump.",
                                        ["The feed pump is rated at 75 kW.",
                                         "The door of the control room is painted blue."]),
                         "rerank_api and rerank_url")(client.transport)
        first, second = ranking.scores
        return first > second, f"scores {first:.2f} for the counterpart, {second:.2f} for the unrelated claim"
    checks.append(_timed("reranker", reranker) if settings.rerank_model else
                  Check("reranker", None, "none set (rerank_model)"))

    def embedding():
        vectors = _asked(embed.request(settings, ["The rated power of the feed pump.",
                                                  "The feed pump is rated at 75 kW.",
                                                  "The door of the control room is painted blue."]),
                         "embed_url")(client.transport)
        query, near, far = (embed.unpacked(v) for v in vectors.vectors)
        a, b = embed.cosine(query, near), embed.cosine(query, far)
        return a > b, f"cosine {a:.2f} with the counterpart, {b:.2f} with the unrelated claim"
    checks.append(_timed("embedding", embedding) if settings.embed_model else
                  Check("embedding", None, "none set (embed_model)"))
    return checks, client.cost

def _asked(request, settings_named):
    """A reranker's or an embedding model's request sent: its answer, or its failure saying where it was asked and
    which settings say where it's served."""
    def send(transport):
        try:
            return transport.send(request)
        except Exception as e:  # noqa: BLE001 (a check's failure is its result, whatever it is)
            raise type(e)(f"{e} at {request.url} ({settings_named} say where it's served)") from None
    return send

def _unreachable(said):
    return said.startswith(("URLError", "ConnectionRefusedError", "TimeoutError", "socket.timeout", "OSError"))

def lines(settings, checks, cost):
    """`config test`'s report: what was checked, each check, what it cost, and how many failed."""
    from .llm import redact_url
    out = [f"checking {settings.model} at {redact_url(settings.base_url)}"]
    out += [c.line() for c in checks]
    failed = [c.name for c in checks if c.ok is False]
    out.append(f"cost: ${cost:.4f}, as the provider reports it")
    out.append(f"{len(failed)} check(s) failed: {', '.join(failed)}" if failed else "every check passed")
    return out

def listing(settings, words="", as_json=False):
    """`config models [WORDS]`: the endpoint's models whose name or tags hold every word ("vision" those that read
    images, at DeepInfra), with what the endpoint says of each; those the settings name marked."""
    names = used(settings)
    found = [m for m in listed(settings, os.getenv("OPENAI_API_KEY", ""))
             if all(w in " ".join((m.id,) + m.tags).casefold() for w in words.casefold().split())]
    if as_json:
        return [json.dumps([{"id": m.id, "context": m.context, "price_in": m.price_in, "price_out": m.price_out,
                             "tags": list(m.tags), "named_by": names.get(m.id, [])} for m in found], indent=1)]
    if not found:
        return [f"no model at the endpoint holds {words!r}" if words else "the endpoint lists no models"]
    return table(found, names)

def table(found, names=None):
    """Listed models a line each, in columns: the name (marked with the settings naming it), and what the endpoint
    says of it."""
    rows = [[m.id + (f"  ({', '.join(names[m.id])})" if names and m.id in names else "")] + m.described()
            for m in found]
    widths = [max(len(r[k]) for r in rows) for k in range(len(rows[0]))]
    return ["  ".join(cell.ljust(w) if k == 0 else cell.rjust(w) if k == 1 else cell.ljust(w)
                      for k, (cell, w) in enumerate(zip(r, widths)) if w).rstrip() for r in rows]
