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

    def line(self, width=9):
        mark = {True: "ok", False: "FAILED", None: "--"}[self.ok]
        took = f" ({self.seconds:.1f} s)" if self.seconds >= 0.05 else ""
        return f"  {self.name:<{width}} {mark}: {self.said}{took}"

def models(settings, api_key=""):
    """The endpoint's models (GET {base_url}/models, the OpenAI format), their ids sorted; OSError or ValueError when
    they can't be listed."""
    url = settings.base_url.rstrip("/") + "/models"
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + api_key} if api_key else {})
    with urllib.request.urlopen(request, timeout=min(settings.timeout, 30)) as response:
        data = json.load(response)
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("the endpoint's /models answer holds no list of models")
    return sorted({str(m["id"]) for m in items if isinstance(m, dict) and m.get("id")})

def used(settings):
    """{model id: the settings naming it}: what the configuration asks."""
    out = {settings.model: ["model"]}
    if settings.rerank_model:
        out.setdefault(settings.rerank_model, []).append("rerank_model")
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
    from .rerank import request as rerank_request
    rng = rng or random.Random()
    client = Client(settings, None)
    key = client.api_key
    checks = []
    listed = []

    def endpoint():  # the chat model only: a reranker may be served apart (DeepInfra's are), and is asked below
        listed.extend(models(settings, key))
        if settings.model not in listed:
            return False, (f"{len(listed)} models listed, not {settings.model} (`config models WORDS` lists those "
                           "like it)")
        return True, f"{len(listed)} models listed, {settings.model} among them"
    checks.append(_timed("endpoint", endpoint))
    if checks[-1].ok is False and not listed and _unreachable(checks[-1].said):
        return checks + [Check(name, None, "skipped: the endpoint isn't reachable") for name in
                         ("json", "image", "reranker")], client.cost
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
        ranking = client.transport.send(rerank_request(settings, "The rated power of the feed pump.",
                                                       ["The feed pump is rated at 75 kW.",
                                                        "The door of the control room is painted blue."]))
        first, second = ranking.scores
        return first > second, f"scores {first:.2f} for the counterpart, {second:.2f} for the unrelated claim"
    checks.append(_timed("reranker", reranker) if settings.rerank_model else
                  Check("reranker", None, "none set (rerank_model)"))
    return checks, client.cost

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

def listing(settings, words=""):
    """`config models [WORDS]`: the endpoint's models holding every word, those the settings name marked."""
    names = used(settings)
    found = [m for m in models(settings, os.getenv("OPENAI_API_KEY", ""))
             if all(w in m.casefold() for w in words.casefold().split())]
    if not found:
        return [f"no model at the endpoint holds {words!r}" if words else "the endpoint lists no models"]
    return [m + (f"  ({', '.join(names[m])})" if m in names else "") for m in found]
