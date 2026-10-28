"""`semantic-pdf-diff config test` and `config models` (decision 0032, as cameo_ingest's): the endpoint, the key and
each model the settings name checked for a few cents, and the endpoint's models listed.

The checks ask for real: never the answers cache, so a check passes only when the model answers now. The image check
is an eye-test card: a random code drawn large, which can't be guessed, read back exactly (the lab's eye tests measure
how small a model can read: lab/src/semantic_pdf_diff_lab/bench/eyetest.py).
"""
import json
import math
import os
import random
import re
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import Field

from .schema import Lenient

LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O or Q, as drawings avoid them
FAILED = 5  # the exit code when a check fails (cameo_ingest's)
REFUSED = re.compile(r"\bHTTP(?: Error)? (401|403)\b")  # the endpoint turning the key away, as a check's failure says

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
    measured: dict = field(default_factory=dict)  # what it measured, for calibrate: context_tokens, image_tokens

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

SHOWN = 15  # the models a missing model's error lists at most

def unset_model(settings):
    """What a run needing the model says when none is set: how to set one, and the endpoint's models reading images
    (all its models, where it says nothing of what they read), as `config models` lists them."""
    from .llm import redact_url
    said = ["No model is set: `semantic-pdf-diff config set --user model NAME` names one for every store "
            "(`config set model NAME` for one store, --model for one run)."]
    where = f"The endpoint at {redact_url(settings.base_url)}"
    try:
        found = listed(settings, os.getenv("OPENAI_API_KEY", ""))
    except (OSError, ValueError) as e:
        failure = f"{type(e).__name__}: {e}"
        hint = (" It refused the key: OPENAI_API_KEY holds the one it takes." if REFUSED.search(failure) else
                f" {WHERE}." if _unreachable(failure) else "")
        return "\n".join(said + [f"{where} can't be asked for its models ({failure}).{hint} `semantic-pdf-diff "
                                 "config test` checks it."])
    seeing = [m for m in found if m.reads_images]
    shown = seeing or found
    if not found:
        return "\n".join(said + [f"{where} lists no models."])
    said.append(f"{where} lists {len(found)} models" + (f"; these {len(seeing)} read images:" if seeing else ":"))
    said += ["  " + line for line in table(shown[:SHOWN])]
    if len(shown) > SHOWN:
        said.append(f"  and {len(shown) - SHOWN} more: `semantic-pdf-diff config models{' vision' if seeing else ''}`")
    return "\n".join(said)

def used(settings):
    """{model id: the settings naming it}: what the configuration asks."""
    out = {settings.model: ["model"]}
    if settings.rerank_model:
        out.setdefault(settings.rerank_model, []).append("rerank_model")
    if settings.embed_model:
        out.setdefault(settings.embed_model, []).append("embed_model")
    return out

CODE = ('The image shows one code: letters, a dash and digits. Return only the JSON object {"code": "..."} with the '
        'code exactly as written.')

def card(folder, rng, side=None):
    """(an eye-test card's PNG path, its code): a random code ("HXR-4027") drawn large on white; side: on a square of
    that many pixels, as large as an image is sent (image_side), so its tokens are an image's most."""
    import pymupdf
    code = "".join(rng.choices(LETTERS, k=3)) + "-" + "".join(rng.choices("0123456789", k=4))
    doc = pymupdf.open()
    if side:
        page = doc.new_page(width=side, height=side)
        page.insert_text((side * 0.1, side * 0.55), code, fontsize=side / 8, fontname="helv")
        pixmap = page.get_pixmap(dpi=72)
    else:
        page = doc.new_page(width=300, height=90)
        page.insert_text((24, 60), code, fontsize=40, fontname="helv")
        pixmap = page.get_pixmap(dpi=96)
    path = Path(folder) / "card.png"
    pixmap.save(path)
    doc.close()
    return path, code

def _timed(name, check, measured=None):
    """A check run: (ok, said), or (ok, said, what it measured); measured: what it measured otherwise (a dict, read
    once it's run)."""
    started = time.monotonic()
    found = {}
    try:
        ok, said, *more = check()
        found = more[0] if more else {}
    except Exception as e:  # noqa: BLE001 (a check's failure is its result, whatever it is)
        ok, said = False, f"{type(e).__name__}: {e}"
    return Check(name, ok, said, time.monotonic() - started, {**(measured or {}), **found})

def _prompted(client, prompt, schema, images, quietly=False):
    """(the answer, the prompt's tokens as the endpoint reported them, or 0): quietly, an answer that fails is None,
    its tokens counted still."""
    before = client.usage["prompt_tokens"]
    try:
        got = client.ask(prompt, schema, images=images)
    except Exception:  # noqa: BLE001
        if not quietly:
            raise
        got = None
    return got, client.usage["prompt_tokens"] - before

def run(settings, rng=None, only=None):
    """Every check, in order (only: those named, of json, image, reranker and embedding; the endpoint's listing with
    the chat model's): [Check], and what they cost (dollars, as the provider reports it). The chat check measures the
    model's context window, where the listing gives it, and the image check an image's tokens at image_side (calibrate
    keeps them)."""
    from .llm import Client, is_local
    from . import embed
    from .rerank import request as rerank_request
    rng = rng or random.Random()
    wanted = set(only) if only is not None else {"json", "image", "reranker", "embedding"}
    client = Client(settings, None)
    key = client.api_key
    checks = []
    ids = []  # the endpoint's models
    chat = {}  # what the listing says of the model, for the chat check's measures

    def endpoint():  # the chat model only: a reranker or an embedding model may be served apart, and is asked below
        found = listed(settings, key)
        ids.extend(m.id for m in found)
        if not settings.model:
            return bool(ids), f"{len(ids)} models listed"
        if settings.model not in ids:
            return False, (f"{len(ids)} models listed, not {settings.model} (`config models WORDS` lists those "
                           "like it)")
        context = next(m.context for m in found if m.id == settings.model)
        if context:
            chat["context_tokens"] = context
        return True, f"{len(ids)} models listed, {settings.model} among them" + (
            f" ({context:,} tokens of context)" if context else "")
    if wanted & {"json", "image"}:
        checks.append(_timed("endpoint", endpoint))
        if checks[-1].ok is False and not ids and _unreachable(checks[-1].said):
            return checks + [Check(name, None, "skipped: the endpoint isn't reachable") for name in
                             ("json", "image", "reranker", "embedding") if name in wanted], client.cost
        if checks[-1].ok is False and not ids and not REFUSED.search(checks[-1].said):  # reachable, but listing
            # no models (some servers don't); one turning the key away fails, and the key check says why
            checks[-1] = Check("endpoint", None, "lists no models: " + checks[-1].said, checks[-1].seconds)
        if not key and not is_local(settings.base_url):
            checks.append(Check("key", None, "OPENAI_API_KEY isn't set (a local server may need none)"))
        if not settings.model:
            checks.append(Check("model", False, "none set: `config set --user model NAME` names one (`config models "
                                                "vision` lists those reading images)"))

    def answer():
        a, b = rng.randint(11, 89), rng.randint(11, 89)
        got = client.ask(f'Add {a} and {b}. Return only the JSON object {{"sum": N}}.', Sum)
        return got.sum == a + b, f"{a} + {b} = {got.sum}" + ("" if got.sum == a + b else f", not {a + b}")
    if "json" in wanted:
        checks.append(Check("json", None, "skipped: no model is set") if not settings.model else
                      _timed("json", answer, chat))

    def image():
        measured = {}
        with tempfile.TemporaryDirectory(prefix="semantic-pdf-diff-check-") as folder:
            path, code = card(folder, rng, side=settings.image_side)  # as large as an image is sent
            got, shown = _prompted(client, CODE, Code, (path,))
            _, alone = _prompted(client, CODE, Code, (), quietly=True)  # the same prompt, its image's tokens apart
        if shown and alone and shown > alone:
            measured["image_tokens"] = shown - alone
        read = "".join(got.code.split()).upper()
        said = f'read "{got.code}"' + ("" if read == code else f', not "{code}"')
        if measured:
            said += f"; an image {settings.image_side} px square is {measured['image_tokens']:,} tokens"
        return read == code, said, measured
    if "image" in wanted:
        checks.append(Check("image", None, "skipped: no model is set") if not settings.model else
                      _timed("image", image) if settings.vision else Check("image", None, "not checked: vision is off"))

    def reranker():
        ranking = _asked(rerank_request(settings, "The rated power of the feed pump.",
                                        ["The feed pump is rated at 75 kW.",
                                         "The door of the control room is painted blue."]),
                         "rerank_api and rerank_url")(client.transport)
        first, second = ranking.scores
        return first > second, f"scores {first:.2f} for the counterpart, {second:.2f} for the unrelated claim"
    if "reranker" in wanted:
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
    if "embedding" in wanted:
        checks.append(_timed("embedding", embedding) if settings.embed_model else
                      Check("embedding", None, "none set (embed_model)"))
    refused = next((REFUSED.search(c.said) for c in checks if c.ok is False and "balance" not in c.said), None)
    if refused:  # 401 or 403: the key isn't one the endpoint takes (a provider's balance exhausted aside)
        checks = [c for c in checks if c.name != "key"]
        at = 1 if checks and checks[0].name == "endpoint" else 0
        checks.insert(at, Check("key", False, f"refused (HTTP {refused.group(1)}): OPENAI_API_KEY "
                                + ("isn't set" if not key else "isn't a key this endpoint takes")))
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

WHERE = ("$OPENAI_BASE_URL names the endpoint, else the user's base_url (`semantic-pdf-diff config set --user base_url "
         "URL`); --base-url for one run")

def advice(checks):
    """What to set, where the checks found the endpoint out of reach or its key refused: [line]."""
    out = []
    if any(c.name == "endpoint" and c.ok is False and _unreachable(c.said) for c in checks):
        out.append(f"the endpoint can't be reached: {WHERE}")
    if any(c.name == "key" and c.ok is False for c in checks):
        out.append("the endpoint refused the key: OPENAI_API_KEY holds the one it takes")
    return out

def lines(settings, checks, cost):
    """`config test`'s report: what was checked, each check, what to set where the endpoint is out of reach or its
    key refused (advice), what it cost, and how many failed."""
    from .llm import redact_url
    out = [f"checking {settings.model or 'no model'} at {redact_url(settings.base_url)}"]
    out += [c.line() for c in checks]
    failed = [c.name for c in checks if c.ok is False]
    out += advice(checks)
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

# --- first use: each model checked before a run's first request, unless remembered as passing

MEMORY = "endpoints.json"  # the record of checks passed, beside the answers cache's answers.sqlite

class Unchecked(RuntimeError):
    """A model the settings name failed its first-use check: nothing was asked (exit 5, as `config test`'s)."""

def memory_of(cache):
    """The record of checks passed kept beside an answers cache (its file): a project with a cache of its own keeps
    its own, and nothing about its endpoint reaches another's."""
    return Path(cache).parent / MEMORY

def recalled(path):
    """{check's key: what it passed with ({"at": when, and what it measured})}; none without the file, or with one
    unreadable (a record of checks, which are asked again)."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    passed = data.get("passed") if isinstance(data, dict) else None
    return passed if isinstance(passed, dict) else {}

def _kept(path, passed):
    """The record written whole, owner-only as the cache beside it is."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps({"format": 1, "passed": passed}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temp, 0o600)
    os.replace(temp, path)

def keys(settings):
    """{check: its key, what its passing depends on}, for the checks the settings call for: the chat model's by the
    endpoint and the model; the image check's by those and image_side, at which it measures an image; the reranker's
    and the embedding model's by their URL, model and API. URLs are redacted: no credential is kept."""
    from .llm import redact_url
    from . import embed, rerank
    base = redact_url(settings.base_url.rstrip("/"))
    out = {"json": f"chat {base} {settings.model}"}
    if settings.vision:
        out["image"] = f"image {base} {settings.model} {settings.image_side}"
    if settings.rerank_model:
        try:
            where = redact_url(rerank.endpoint(settings))
        except ValueError:  # its check says why
            where = base
        out["reranker"] = f"reranker {where} {settings.rerank_model} {settings.rerank_api}"
    if settings.embed_model:
        out["embedding"] = f"embedding {redact_url(embed.endpoint(settings))} {settings.embed_model}"
    return out

def record(path, settings, checks):
    """The record updated from checks run: each passed remembered, with what it measured; each failed forgotten."""
    wanted, passed = keys(settings), recalled(path)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for c in checks:
        if c.name not in wanted:
            continue
        if c.ok:
            passed[wanted[c.name]] = {"at": now, **c.measured}
        elif c.ok is False:
            passed.pop(wanted[c.name], None)
    if any(c.name == "endpoint" and c.ok is False for c in checks):  # the model isn't listed
        passed.pop(wanted["json"], None)
    _kept(path, passed)

def forget(path, settings):
    """Every check the settings call for forgotten (their requests failed in a row): the next run checks again."""
    passed = recalled(path)
    gone = [k for k in keys(settings).values() if k in passed]
    if gone:
        for k in gone:
            passed.pop(k)
        _kept(path, passed)

def first_use(settings, cache):
    """Before a run's first request, each model the settings name checked as `config test` checks it, unless the
    record beside the answers cache remembers it passing (the owner, 2026-10-20: "we should always auto-test the model
    endpoint if it isn't tested in memory. Without verbose mode, we can get 13k bad requests without noticing.").
    Returns the settings calibrated from what the checks measured (calibrated); a check failing raises Unchecked, its
    lines logged."""
    from .progress import log
    path = memory_of(cache)
    wanted, passed = keys(settings), recalled(path)
    missing = [name for name, key in wanted.items() if key not in passed]
    if not missing:
        return calibrated(settings, path)
    log.info(f"First use: {', '.join(missing)} checked before anything is asked (remembered in {path})")
    checks, cost = run(settings, only=missing)
    for line in lines(settings, checks, cost)[1:]:
        log.info(line)
    record(path, settings, checks)
    failed = [c.name for c in checks if c.ok is False]
    if failed:
        raise Unchecked(f"{', '.join(failed)} failed {'its' if len(failed) == 1 else 'their'} check, so nothing was "
                        "asked: `semantic-pdf-diff config test` checks again")
    made = calibrated(settings, path)
    changed = [f"{k} {getattr(made, k):,}" for k in MEASURES if getattr(made, k) != getattr(settings, k)]
    if changed:
        log.info(f"Calibrated from what was measured: {', '.join(changed)} (`config show` marks them)")
    return made

# --- calibration: what the checks measured, used where no layer sets it

MARGIN = 1.1  # an image's measured tokens, with a tenth to spare: image_tokens is an upper bound
MEASURES = {"context_tokens": "json", "image_tokens": "image"}  # each setting measured, and the check measuring it

def measured(settings, path):
    """{setting: {"value", "raw", "at"}}: what the record's checks measured, for these settings' checks (keys): the
    model's context window, as the endpoint lists it; an image's tokens at image_side, a tenth added."""
    wanted, passed = keys(settings), recalled(path)
    out = {}
    for name, check in MEASURES.items():
        entry = passed.get(wanted.get(check)) or {}
        raw = entry.get(name)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
            value = math.ceil(raw * MARGIN) if name == "image_tokens" else raw
            out[name] = {"value": value, "raw": raw, "at": entry.get("at", "")}
    return out

def calibrated(settings, path):
    """The settings with what checks measured, where no layer sets it (the owner, 2026-10-20: "It isn't clear that we
    run any calibration on first use of an endpoint. I think we should."). A value a layer sets wins, warned of where
    the measure says it's unsafe: a context window larger than the model's, an image costing more than it allows."""
    from .progress import log
    found, given = measured(settings, path), settings.model_fields_set
    unsafe = {"context_tokens": lambda set_, raw: set_ > raw, "image_tokens": lambda set_, raw: set_ < raw}
    said = {"context_tokens": lambda raw: f"the endpoint gives {settings.model} {raw:,} tokens of context",
            "image_tokens": lambda raw: f"an image {settings.image_side} px square was {raw:,} tokens there"}
    for name, m in found.items():
        if name in given and unsafe[name](getattr(settings, name), m["raw"]):
            log.warning(f"{name} is {getattr(settings, name):,}, but {said[name](m['raw'])}: requests may be refused "
                        f"or cut. `semantic-pdf-diff config unset {name}` (with --user, if it's the user's) uses "
                        f"what was measured ({m['value']:,})")
    update = {name: m["value"] for name, m in found.items()
              if name not in given and getattr(settings, name) != m["value"]}
    if not update:
        return settings
    try:
        made = type(settings)(**{k: getattr(settings, k) for k in given}, **update)
    except ValueError as e:  # a window too small for the other budgets, say
        log.warning(f"What was measured ({', '.join(f'{k} {v:,}' for k, v in update.items())}) doesn't fit the other "
                    f"settings, so the defaults are kept: {e}")
        return settings
    log.debug("Calibrated: " + ", ".join(f"{k} {v:,}" for k, v in update.items()))
    return made
