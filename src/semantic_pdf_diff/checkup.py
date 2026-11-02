"""`semantic-pdf-diff config test`, `config checks` and `config models` (decision 0032, as cameo_ingest's): the
endpoint, the key and each model the settings name (or a candidate, --model) checked for a few cents, the checks
remembered shown and forgotten, and the endpoint's models listed, those checked marked.

The checks ask for real: never the answers cache, so a check passes only when the model answers now. The image check
is an eye-test card: a random code drawn large, which can't be guessed, read back exactly (the lab's eye tests measure
how small a model can read: lab/src/semantic_pdf_diff_lab/bench/eyetest.py).
"""
import difflib
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

# A host's tag saying what a model serves, as its mode (LiteLLM's word: chat, embedding, rerank, image_generation...)
MODE_TAGS = {"chat": "chat", "embed": "embedding", "embedding": "embedding", "rerank": "rerank", "reranker": "rerank",
             "image-gen": "image_generation", "video-gen": "video_generation", "tts": "audio_speech",
             "stt": "audio_transcription"}
CHATTING = ("chat", "completion", "responses")  # the modes a chat model is listed in
ROLES = {"model": ("--model", "a chat model", CHATTING), "rerank_model": ("--rerank", "a reranker", ("rerank",)),
         "embed_model": ("--embed", "an embedding model", ("embedding",))}  # a setting: config test's flag, its mode

@dataclass(frozen=True)
class Listed:
    """A model as the endpoint lists it, with what the endpoint says of it, where it says (the owner, 2026-10-20: "We
    could let people know what's available."): its mode (what it serves: chat, embedding, rerank...), its context
    window in tokens, the most it answers with, its price in dollars a million tokens in and out, and its tags
    (DeepInfra's: chat, vision, embed and more; vision too where OpenRouter lists images among its inputs, or LiteLLM
    says it supports them)."""
    id: str
    context: int | None = None
    price_in: float | None = None
    price_out: float | None = None
    tags: tuple = ()
    mode: str = ""
    output: int | None = None

    @property
    def reads_images(self):
        return "vision" in self.tags or "vlm" in self.tags

    def described(self):
        """[its mode, its context, its price, its other tags], each "" where the endpoint doesn't say."""
        prices = [f"${p:.2f} {way}" if p >= 0.01 or not p else f"${p:.2g} {way}"
                  for p, way in ((self.price_in, "in"), (self.price_out, "out")) if p is not None]
        out = f" ({self.output:,} out)" if self.output and self.context and self.output < self.context else ""
        return [self.mode, f"{self.context:,} tokens{out}" if self.context else "",
                ", ".join(prices) + " a million" if prices else "",
                ", ".join(t for t in self.tags if MODE_TAGS.get(t) != self.mode)]

    def said(self):
        """What it serves, in words: "an embedding model"."""
        return next((said for _, said, modes in ROLES.values() if self.mode in modes),
                    f"a {self.mode.replace('_', ' ')} model")

def _count(*values):
    return next((int(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0), None)

def _price(value, scale=1.0):
    try:
        return round(float(value) * scale, 6) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None

def described(item):
    """A /models item as Listed: DeepInfra's metadata (context_length; max_tokens; pricing in dollars a million
    tokens; tags, one saying its mode), vLLM's max_model_len, OpenRouter's fields (context_length; pricing in dollars
    a token; architecture's input modalities; top_provider's max_completion_tokens), or LiteLLM's model_info where
    /model/info gave it (mode; max_input_tokens and max_output_tokens; costs a token; supports_vision)."""
    get = lambda d, k: d.get(k) if isinstance(d, dict) else None  # noqa: E731
    meta, top, arch, info = (get(item, k) or {} for k in ("metadata", "top_provider", "architecture", "model_info"))
    context = _count(get(meta, "context_length"), get(item, "context_length"), get(item, "max_model_len"),
                     get(top, "context_length"), get(info, "max_input_tokens"))
    output = _count(get(meta, "max_tokens"), get(top, "max_completion_tokens"), get(info, "max_output_tokens"))
    if isinstance(get(meta, "pricing"), dict):
        price_in, price_out = (_price(get(meta["pricing"], k)) for k in ("input_tokens", "output_tokens"))
    elif isinstance(get(item, "pricing"), dict):
        price_in, price_out = (_price(get(item["pricing"], k), 1e6) for k in ("prompt", "completion"))
    else:
        price_in, price_out = (_price(get(info, k), 1e6) or None  # LiteLLM's 0: a model its price map lacks
                               for k in ("input_cost_per_token", "output_cost_per_token"))
    tags = [str(x) for x in (get(meta, "tags") or get(item, "tags") or []) if isinstance(x, str)]
    if "image" in (get(arch, "input_modalities") or []) or get(info, "supports_vision") is True:
        tags.append("vision")
    mode = get(info, "mode") or next((MODE_TAGS[t] for t in tags if t in MODE_TAGS), "")
    return Listed(str(item["id"]), context, price_in, price_out, tuple(dict.fromkeys(tags)), str(mode), output)

def _fetched(url, api_key, timeout):
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + api_key} if api_key else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)

def model_info(base, api_key, timeout):
    """{model: LiteLLM's model_info} from a LiteLLM proxy's /model/info (its deployments' merged, the first saying
    each): what its bare /models listing leaves out. {} where it can't be had (another server, a key it refuses)."""
    try:
        data = _fetched(base + "/model/info", api_key, timeout)
    except Exception:  # noqa: BLE001 (only a proxy has it, and the listing stands without it)
        return {}
    out = {}
    for d in (data.get("data") if isinstance(data, dict) else None) or []:
        if isinstance(d, dict) and isinstance(d.get("model_info"), dict) and d.get("model_name"):
            merged = out.setdefault(str(d["model_name"]), {})
            merged.update({k: v for k, v in d["model_info"].items() if merged.get(k) is None})
    return out

def listed(settings, api_key="", timeout=30):
    """The endpoint's models (GET {base_url}/models, the OpenAI format) as Listed, sorted by id (case aside); OSError
    or ValueError when they can't be listed (timeout: seconds at most, under the settings' own). A listing saying
    nothing of any model but its name (a LiteLLM proxy's) is completed from /model/info, where the endpoint has it."""
    base, timeout = settings.base_url.rstrip("/"), min(settings.timeout, timeout)
    data = _fetched(base + "/models", api_key, timeout)
    items = data.get("data") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError("the endpoint's /models answer holds no list of models")
    found = {str(m["id"]): described(m) for m in items if isinstance(m, dict) and m.get("id")}
    if found and not any(m.context or m.tags or m.mode or m.price_in is not None for m in found.values()):
        info = model_info(base, api_key, timeout)
        found = {k: described({"id": k, "model_info": info[k]}) if k in info else m for k, m in found.items()}
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

# A model a feature needs, none by default (configuration.OPTIONAL_MODELS): the feature, and what it does
FEATURES = {"rerank_model": ("reranking", "A reranker scores each claim's candidates, and those below "
                             "rerank_threshold aren't judged.", "rerank"),
            "embed_model": ("search by meaning", "An embedding model finds the claims most like a claim or a phrase "
                            "(near:ID, meaning:\"...\").", "embedding")}

def unconfigured(settings, mode="proposals"):
    """The models a run's features need that no layer names, nor goes without ("none": levers.declined): [setting].
    The reranker is asked in proposals mode alone (reranks)."""
    named = settings.model_fields_set
    return [name for name in FEATURES if name in type(settings).model_fields and not getattr(settings, name)
            and name not in named and (name != "rerank_model" or mode == "proposals")]

def unnamed(settings, name):
    """A check's line for a model a feature needs that isn't set: not configured, or none chosen."""
    if name in settings.model_fields_set:
        return f"none: {name} is none, so {FEATURES[name][0]} is off"
    return (f"not configured, so {FEATURES[name][0]} is off: `config set --user {name} NAME` names one (`config "
            f"models {FEATURES[name][2]}` lists the endpoint's), `none` goes without")

def guidance(settings, mode="proposals"):
    """What a run says of its settings before it starts (the owner, 2026-11-02: "always do a quick check on settings
    before starting, always let users know if they've missed an important one"): the models it asks, and where; each
    feature off for want of a model no layer names, with how to name one or go without. [line], logged as a run's
    progress is (-q quiets them)."""
    from .llm import redact_url
    roles = [f"{settings.model or 'no model'} at {redact_url(settings.base_url)}"]
    for name, said, env in (("rerank_model", "reranker", "rerank_key_env"),
                            ("embed_model", "embedding model", "embed_key_env")):
        if name not in type(settings).model_fields or (name == "rerank_model" and mode != "proposals"):
            continue
        value, variable = getattr(settings, name), getattr(settings, env, None)
        key = (f" (its key from ${variable}" + ("" if os.getenv(variable) else ", which isn't set: asked without a key")
               + ")") if variable and value else ""
        roles.append(f"{said} {value}{key}" if value else f"no {said}" + (
            " (none chosen)" if name in settings.model_fields_set else " (not configured)"))
    out = ["Models: " + "; ".join(roles)]
    for name in unconfigured(settings, mode):
        feature, does, listed_as = FEATURES[name]
        out.append(f"{feature[0].upper() + feature[1:]} is off: no {name} is configured. {does}")
        out.append(f"  `semantic-pdf-diff config set --user {name} NAME` names one (`config models {listed_as}` lists "
                   "the endpoint's), `none` goes without and stops this.")
    return out

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

# The acuity cards in flight at once: eight at once met Llama-4-Scout's "Model busy" at DeepInfra (HTTP 429) on every
# card, and an endpoint of a few servers (the owner's) would rather not be asked eight images at once by a check
CARDS_AT_ONCE = 2

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
    """Every check, in order (only: those named, of json, image, acuity, reranker and embedding; the endpoint's
    listing with the chat model's): [Check], and what they cost (dollars, as the provider reports it). The chat check
    measures the model's context window, where the listing gives it, and the image check an image's tokens at
    image_side (calibrate keeps them); acuity, the smallest capitals the model reads there (acuity.py)."""
    from .llm import Client, is_local
    from . import embed
    from .rerank import request as rerank_request
    rng = rng or random.Random()
    wanted = set(only) if only is not None else {"json", "image", "acuity", "reranker", "embedding"}
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
        mine = next(m for m in found if m.id == settings.model)
        if mine.context:
            chat["context_tokens"] = mine.context
        said = f"{len(ids)} models listed, {settings.model} among them" + (
            f" ({mine.context:,} tokens of context)" if mine.context else "")
        if mine.mode and mine.mode not in CHATTING:  # its checks say whether it chats all the same
            flag = next((flag for flag, _, modes in ROLES.values() if mine.mode in modes), "")
            said += f"; listed as {mine.said()}, not a chat model" + (
                f" (`config test {flag} {settings.model}` tries it as one)" if flag else "")
        return True, said
    if wanted & {"json", "image", "acuity"}:
        checks.append(_timed("endpoint", endpoint))
        if checks[-1].ok is False and not ids and _unreachable(checks[-1].said):
            return checks + [Check(name, None, "skipped: the endpoint isn't reachable") for name in
                             ("json", "image", "acuity", "reranker", "embedding") if name in wanted], client.cost
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

    def eye_test():  # a card a size, two at a time; a failed answer read nothing, as the eye test counts it
        from . import acuity as cards
        from .dispatch import Dispatcher
        from .tilechoice import LEGIBLE_PX
        shares, failures = {}, []
        with tempfile.TemporaryDirectory(prefix="semantic-pdf-diff-check-") as folder:
            drawn = cards.cards(folder, rng, settings.image_side)
            with Dispatcher(client, workers=CARDS_AT_ONCE) as dispatch:
                for size, path, lines in drawn:
                    def done(value, error, size=size, lines=lines):
                        shares[size] = cards.score(lines, value.lines) if error is None else 0.0
                        if error is not None:
                            failures.append(f"{type(error).__name__}: {error}")
                    dispatch.submit(cards.PROMPT, cards.Lines, (path,), ("acuity", size), done)
                dispatch.drain()
        if len(failures) == len(drawn):
            return False, f"no card answered: {failures[0]}"
        px = cards.threshold(shares.items())
        read = {str(size): round(share, 2) for size, share in sorted(shares.items())}
        if px is None:
            return False, (f"read no card's items at {cards.PASS:.0%}, up to capitals {cards.SIZES[-1]} px tall at "
                           f"{settings.image_side} px square: pages' text would be misread"), {"read": read}
        said = (f"capitals {px:g} px tall and up read at {settings.image_side} px square (pages are tiled for text "
                f"{LEGIBLE_PX:g} px and up)")
        if px > LEGIBLE_PX * 1.1:  # gemma-4 measured 7.0 to 7.4 at DeepInfra; gemma-3 8.0, Mistral-Small 8.3
            said += ": smaller text on pages may be misread"
        return True, said + (f"; {len(failures)} card(s) not answered" if failures else ""), {"legible_px": px,
                                                                                               "read": read}
    if "acuity" in wanted:
        checks.append(Check("acuity", None, "skipped: no model is set") if not settings.model else
                      _timed("acuity", eye_test) if settings.vision else
                      Check("acuity", None, "not checked: vision is off"))

    def reranker():
        ranking = _asked(rerank_request(settings, "The rated power of the feed pump.",
                                        ["The feed pump is rated at 75 kW.",
                                         "The door of the control room is painted blue."]),
                         "rerank_api and rerank_url")(client.transport)
        first, second = ranking.scores
        return first > second, f"scores {first:.2f} for the counterpart, {second:.2f} for the unrelated claim"
    if "reranker" in wanted:
        checks.append(_timed("reranker", reranker) if settings.rerank_model else
                      Check("reranker", None, unnamed(settings, "rerank_model")))

    def embedding():
        vectors = _asked(embed.request(settings, ["The rated power of the feed pump.",
                                                  "The feed pump is rated at 75 kW.",
                                                  "The door of the control room is painted blue."]),
                         "embed_url")(client.transport)
        query, near, far = (embed.unpacked(v) for v in vectors.vectors)
        a, b = embed.cosine(query, near), embed.cosine(query, far)
        size = (f"{len(query)} dimensions, the model's own" if not settings.embed_dimensions else
                f"{len(query)} dimensions" if len(query) == settings.embed_dimensions else
                f"{len(query)} dimensions, the model's own (not cut to {settings.embed_dimensions})")
        return a > b, f"cosine {a:.2f} with the counterpart, {b:.2f} with the unrelated claim; {size}"
    if "embedding" in wanted:
        checks.append(_timed("embedding", embedding) if settings.embed_model else
                      Check("embedding", None, unnamed(settings, "embed_model")))
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
    ran = {c.name for c in checks}
    named = [f"{model} ({said})" for model, said, check in
             ((settings.rerank_model, "reranker", "reranker"), (settings.embed_model, "embedding model", "embedding"))
             if model and check in ran]
    chat = [settings.model or "no model"] if ran - {"reranker", "embedding"} or not named else []
    out = [f"checking {', '.join(chat + named)} at {redact_url(settings.base_url)}"]
    out += [c.line() for c in checks]
    failed = [c.name for c in checks if c.ok is False]
    out += advice(checks)
    out.append(f"cost: ${cost:.4f}, as the provider reports it")
    out.append(f"{len(failed)} check(s) failed: {', '.join(failed)}" if failed else "every check passed")
    return out

def listing(settings, words="", as_json=False, memory=None):
    """`config models [WORDS]`: the endpoint's models whose name, mode or tags hold every word ("vision" those that
    read images, "embedding" or "rerank" those serving so, where the endpoint says), with what the endpoint says of
    each; those the settings name marked, and those whose checks the record at memory remembers passing at this
    endpoint (endpoint setup, milestone 3)."""
    names, checked = used(settings), checked_here(memory, settings) if memory else {}
    found = [m for m in listed(settings, os.getenv("OPENAI_API_KEY", ""))
             if all(w in " ".join((m.id, m.mode) + m.tags).casefold() for w in words.casefold().split())]
    if as_json:
        return [json.dumps([{"id": m.id, "mode": m.mode, "context": m.context, "output": m.output,
                             "price_in": m.price_in, "price_out": m.price_out,
                             "tags": list(m.tags), "named_by": names.get(m.id, []),
                             "checked": {c["check"]: {k: v for k, v in c.items()
                                                      if k not in ("check", "url", "model", "key")}
                                         for c in checked.get(m.id, [])}} for m in found], indent=1)]
    if not found:
        return [f"no model at the endpoint holds {words!r}" if words else "the endpoint lists no models"]
    return table(found, names, checked)

def table(found, names=None, checked=None):
    """Listed models a line each, in columns: the name (marked with the settings naming it), what the endpoint says
    of it (its mode, context, price and tags), and the checks remembered passing (checked: {model: [remembered's
    entries]})."""
    rows = [[m.id + (f"  ({', '.join(names[m.id])})" if names and m.id in names else "")] + m.described()
            + ([checked_said(checked.get(m.id, []))] if checked else []) for m in found]
    widths = [max(len(r[k]) for r in rows) for k in range(len(rows[0]))]
    return ["  ".join(cell.rjust(w) if k == 2 else cell.ljust(w)
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
        out["acuity"] = f"acuity {base} {settings.model} {settings.image_side}"
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

# a key's word: its check
KINDS = {"chat": "json", "image": "image", "acuity": "acuity", "reranker": "reranker", "embedding": "embedding"}

def _parts(key):
    """A remembered check's key (keys) as {"check", "url", "model"}, and image_side or rerank_api where it holds one;
    None for a key it doesn't know."""
    kind, _, rest = key.partition(" ")
    url, _, model = rest.partition(" ")
    if kind not in KINDS or not model:
        return None
    out = {"check": KINDS[kind], "url": url, "model": model}
    if kind in ("image", "acuity", "reranker") and " " in model:
        out["model"], extra = model.rsplit(" ", 1)
        out["api" if kind == "reranker" else "side"] = extra
    return out

def remembered(path):
    """The record's checks, each {"check", "url", "model", "key", "at", what it measured...}, by model, endpoint and
    check."""
    order = list(KINDS.values())
    out = [{**entry, **parts, "key": key} for key, entry in recalled(path).items()
           if (parts := _parts(key)) and isinstance(entry, dict)]
    return sorted(out, key=lambda c: (c["model"].casefold(), c["url"], order.index(c["check"])))

def checked_here(path, settings):
    """{model: [remembered's entries]}: the checks remembered passing at the settings' endpoint (a reranker's or an
    embedding model's URL under it)."""
    from .llm import redact_url
    base, out = redact_url(settings.base_url.rstrip("/")), {}
    for c in remembered(path):
        if c["url"] == base or c["url"].startswith(base + "/"):
            out.setdefault(c["model"], []).append(c)
    return out

def _when(at):
    return at.replace("T", " ")[:16] + " UTC" if at else "at a time not kept"

def _said(c):
    """What a remembered check measured, in words."""
    if c.get("image_tokens"):
        return f"an image {c.get('side', '?')} px square is {c['image_tokens']:,} tokens"
    if c.get("legible_px"):
        return f"capitals {c['legible_px']:g} px tall and up read at {c.get('side', '?')} px square"
    if c.get("context_tokens"):
        return f"{c['context_tokens']:,} tokens of context, as the endpoint lists it"
    return f"the {c['api']} API" if c.get("api") else ""

def checked_said(entries):
    """A model's checks remembered, for `config models`' last column: "checked: json, image (an image 258 tokens)"."""
    if not entries:
        return ""
    tokens = next((c["image_tokens"] for c in entries if c.get("image_tokens")), None)
    px = next((c["legible_px"] for c in entries if c.get("legible_px")), None)
    said = ([f"an image {tokens:,} tokens"] if tokens else []) + ([f"capitals {px:g} px read"] if px else [])
    return "checked: " + ", ".join(c["check"] for c in entries) + (f" ({'; '.join(said)})" if said else "")

def checks_lines(path, settings):
    """`config checks`: what the record remembers passing, by model and endpoint, the models the settings name marked;
    when each passed and what it measured; and how to forget them (endpoint setup, milestone 2)."""
    found = remembered(path)
    if not found:
        return [f"no check is remembered in {path}: a run checks each model before its first request, "
                "`semantic-pdf-diff config test` now"]
    names, in_use, groups = used(settings), set(keys(settings).values()), {}
    for c in found:
        groups.setdefault((c["model"], c["url"]), []).append(c)
    out = [f"checks remembered passing in {path}; a run checks a model first unless its checks are here"]
    for (model, url), checks in groups.items():
        mine = model in names and any(c["key"] in in_use for c in checks)
        out.append(f"{model} at {url}" + (f"  ({', '.join(names[model])})" if mine else ""))
        for c in checks:
            said = _said(c)
            out.append(f"  {c['check']:<9} passed {_when(c.get('at', ''))}" + (f"; {said}" if said else ""))
    out.append("`semantic-pdf-diff config checks --forget [MODEL]` forgets them: the next run checks again")
    return out

def forget_model(path, model=""):
    """Remembered checks forgotten: every one, or a model's at any endpoint, so the next run checks (and calibrates)
    again: how many."""
    passed = recalled(path)
    gone = [k for k in passed if not model or ((p := _parts(k)) and p["model"] == model)]
    if gone:
        for k in gone:
            passed.pop(k)
        _kept(path, passed)
    return len(gone)

def missing(settings, path):
    """The checks the settings call for that the record doesn't remember passing (keys' names)."""
    passed = recalled(path)
    return [name for name, key in keys(settings).items() if key not in passed]

def name_check(settings, name, setting="model", timeout=10):
    """What `config set` says of a model's name (setting: model, rerank_model or embed_model), the endpoint's listing
    asked (endpoint setup, milestone 3): [line]. It warns where the endpoint doesn't list the name, lists it as
    serving otherwise (an embedding model set as the chat model), or lists a chat model untagged as reading images
    where it tags others; it never refuses (an endpoint may serve a model it doesn't list), and says where the
    listing can't be had, or doesn't hold a model served apart (rerank_url, embed_url)."""
    from .llm import redact_url
    from . import embed, rerank
    flag, role, modes = ROLES[setting]
    where = redact_url(settings.base_url)
    apart = (settings.rerank_url or settings.rerank_api == "deepinfra" if setting == "rerank_model" else
             settings.embed_url if setting == "embed_model" else "")
    if apart:
        try:
            at = redact_url((rerank if setting == "rerank_model" else embed).endpoint(settings))
        except ValueError:
            at = "its own URL"
        return [f"not checked: {role} served apart, at {at}, isn't among the endpoint's models"]
    try:
        found = listed(settings, os.getenv("OPENAI_API_KEY", ""), timeout=timeout)
    except (OSError, ValueError) as e:
        return [f"not checked: the endpoint at {where} can't be asked for its models ({type(e).__name__}: {e})"]
    try_it = f"`semantic-pdf-diff config test {flag} {name}` tries it (a few cents)"
    by_id = {m.id: m for m in found}
    if name not in by_id:
        folded = {m.id.casefold(): m.id for m in found}
        close = [folded[k] for k in difflib.get_close_matches(name.casefold(), list(folded), n=3, cutoff=0.6)]
        like = f"; like it: {', '.join(close)}" if close else ""
        return [f"warning: the endpoint at {where} lists {len(found)} models, not {name}{like} (`config models WORDS` "
                f"lists them); {try_it}"]
    mine = by_id[name]
    if mine.mode and mine.mode not in modes:
        return [f"warning: the endpoint lists {name} as {mine.said()}, not {role} ({setting}): {try_it}"]
    if setting == "model" and settings.vision and not mine.reads_images and any(m.reads_images for m in found):
        return [f"warning: the endpoint doesn't tag {name} as reading images, and pages are read as images (vision): "
                + try_it]
    return []

def forget(path, settings):
    """Every check the settings call for forgotten (their requests failed in a row): the next run checks again."""
    passed = recalled(path)
    gone = [k for k in keys(settings).values() if k in passed]
    if gone:
        for k in gone:
            passed.pop(k)
        _kept(path, passed)

PING = ("json", "reranker", "embedding")  # asked each run, remembered or not: a small request a model

def first_use(settings, cache):
    """Before a run's first request, each model the settings name checked as `config test` checks it, unless the
    record beside the answers cache remembers it passing (the owner, 2026-10-20: "we should always auto-test the model
    endpoint if it isn't tested in memory. Without verbose mode, we can get 13k bad requests without noticing."); and
    each, remembered or not, asked a small request, so a run left overnight fails at once where an endpoint is down
    (the owner, 2026-11-02: "Even if the endpoints are tested in cache, do a lightweight ping to ensure the endpoints
    are up. This tool takes many hours to run, so it's something that is left to run overnight. Better to fail fast up
    front even if it costs a little."): the chat model's JSON check, the reranker's and the embedding model's; the
    image check, which measures, on first use alone. Returns the settings calibrated from what the checks measured
    (calibrated); a check failing raises Unchecked, its lines logged."""
    from .progress import log
    path = memory_of(cache)
    unchecked = missing(settings, path)
    asked = [name for name in keys(settings) if name in unchecked or name in PING]
    if unchecked:
        log.info(f"First use: {', '.join(unchecked)} checked before anything is asked (remembered in {path})")
    checks, cost = run(settings, only=asked)
    failed = [c.name for c in checks if c.ok is False]
    if unchecked or failed:
        for line in lines(settings, checks, cost)[1:]:
            log.info(line)
    else:
        log.info("The endpoint answers: " + ", ".join(f"{c.name} in {c.seconds:.1f} s" for c in checks
                                                      if c.ok and c.name in PING)
                 + f" (${cost:.5f}; asked each run, the first-use checks remembered in {path})")
    record(path, settings, checks)
    if failed:
        forget(path, settings)  # the endpoint changed or down: the next run checks (and calibrates) again
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
