"""A store's own settings and what `pdf-semantic-diff config` does with them (docs/plans/configuration-in-the-store-
2026-10-20.md): values given as text parsed by their setting's type and checked; settings listed by group with what
each does (settinghelp.py), found by words, explained one by one; a layer exported and imported as JSON, in
cameo_ingest's format. The owner, 2026-10-08: "Other configuration items should be adjusted in the store via the CLI,
e.g. `pdf-semantic-diff config (set|unset|import|export|show|test)...` with import/export using JSON."

A setting's name is its field's, in snake case, everywhere: in `config`, in exported files, in `--config` files and in
report.json (the owner, 2026-10-20: "Snake case or kebab case is fine, if consistent"). Flags keep their dashes.

Layers, each above the last: the defaults, then the store's own (`config set`, kept in store.sqlite's meta), then a
`--config` file and a run's flags, which are never saved.
"""
import difflib
import json
import re
import shlex
from typing import get_args, get_origin

from .crops import DEFAULT_BUDGET
from .levers import REGISTRY, declared
from .settinghelp import GROUPS, HELP

# Options of a run kept as settings too: the comparison's mode and the report's.
RUN_OPTIONS = {"mode": "proposals", "report_budget": DEFAULT_BUDGET, "split": False}
EXPORT_FORMAT = 1  # of `config export`'s JSON
SWITCH = {"on": True, "true": True, "yes": True, "1": True, "off": False, "false": False, "no": False, "0": False}

def settings_class():
    from .settings import Settings
    return Settings

def names():
    """Every setting `config` knows, in its groups' order, then as declared."""
    order = {g: i for i, g in enumerate(GROUPS)}
    return sorted(HELP, key=lambda k: order[HELP[k].group])

def lever_of(name):
    """The lever a setting belongs to, or "" (the platform's, the endpoint's, a run's)."""
    return next((lever for lever, cls in REGISTRY.items() if name in cls.model_fields), "")

def unknown(name):
    """The error for a name no setting has, with the likeliest ones."""
    hint = name.replace("-", "_")
    close = [hint] if hint in HELP else difflib.get_close_matches(name, list(HELP), n=3, cutoff=0.6)
    return ValueError(f"no setting {name!r}" + (f": did you mean {' or '.join(close)}?" if close else
                                                "; `config find WORDS` searches them"))

def size(text):
    """A size in bytes, from "20MB", "500KB", "1.5GB" or a bare number of megabytes."""
    found = re.fullmatch(r"\s*(\d+(?:\.\d*)?)\s*([kmg]?b?)\s*", str(text), re.IGNORECASE)
    if not found:
        raise ValueError(f"{text!r} isn't a size (e.g. 20MB, 500KB)")
    unit = found.group(2).lower().rstrip("b") if found.group(2).lower() != "b" else "b"
    return int(float(found.group(1)) * {"": 1e6, "b": 1, "k": 1e3, "m": 1e6, "g": 1e9}[unit])

def parse(name, text):
    """A setting's value from text, as `config set` and the environment give it, checked against its type and
    bounds: a JSON-ready value; ValueError saying what's allowed."""
    if name not in HELP:
        raise unknown(name)
    raw = str(text).strip()
    if name == "mode":
        if raw not in ("proposals", "revisions"):
            raise ValueError(f"mode is proposals or revisions, not {raw!r}")
        return raw
    if name == "report_budget":
        return size(raw)
    if name == "split":
        if raw.lower() not in SWITCH:
            raise ValueError(f"split is on or off, not {raw!r}")
        return SWITCH[raw.lower()]
    field = settings_class().model_fields[name]
    shaped = get_origin(field.annotation) in (list, dict) or field.annotation in (list, dict)
    if shaped:
        try:
            value = json.loads(raw)
        except ValueError as e:
            raise ValueError(f"{name} is JSON: {HELP[name].example or 'a list or an object'}") from e
    elif raw.casefold() in ("none", "null") and type(None) in get_args(field.annotation):
        value = None
    else:
        value = raw
    return checked({name: value})[name]

def checked(values):
    """Values as their settings hold them (JSON-ready), checked together; ValueError naming every fault."""
    from pydantic import ValidationError
    fields = {k: v for k, v in values.items() if k not in RUN_OPTIONS and k != "levers"}
    try:
        settings = settings_class().configured(values.get("levers"), **fields)
    except ValidationError as e:
        faults = "; ".join(f"{'.'.join(map(str, x['loc'])) or 'levers'}: {x['msg']}" for x in e.errors())
        raise ValueError(faults) from None
    dumped = settings.model_dump(mode="json")
    out = {k: dumped[k] for k in fields}
    out.update({k: v for k, v in values.items() if k in RUN_OPTIONS})
    if "levers" in values:
        out["levers"] = list(values["levers"])
    return out

def shown(name, value):
    """A value as people read it: on and off, sizes, none, JSON for lists and objects."""
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "on" if value else "off"
    if name == "report_budget":
        return f"{value / 1e6:g}MB" if value >= 1e6 or value == 0 else f"{value / 1e3:g}KB"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)

def default(name):
    if name in RUN_OPTIONS:
        return RUN_OPTIONS[name]
    return settings_class().model_fields[name].get_default(call_default_factory=True)

def resolved(layers):
    """{name: (value, the layer giving it)} for every setting: layers as [(name, {setting: value})], lowest first,
    over the defaults."""
    out = {name: (default(name), "default") for name in HELP}
    for layer, values in layers:
        for name, value in values.items():
            if name in out:
                out[name] = (value, layer)
    return out

def redoes(name):
    """What changing a setting changes: the store's work its next run redoes (docs/plans/content-addressed-queries:
    each setting's class says what it can change)."""
    if name in RUN_OPTIONS:
        return "the comparison and its report" if name == "mode" else "the report only"
    d = declared(settings_class(), name)
    roles = [r for r in d.roles if r in ("extract", "triage", "compare")]
    if d.kind == "endpoint":
        return ("every answer: what's read is read again, asked of the new model" if name == "model"
                else "nothing (it changes how requests travel, never what is asked)")
    if d.kind == "post":
        return "what's made of the answers, from them, without asking the model again"
    work = {"extract": "documents read again" + (f" ({', '.join(sorted(d.regions))})"
                                                 if len(d.regions) < 5 else ""),
            "triage": "figures and sections situated again", "compare": "the comparison judged again"}
    return "; ".join(work[r] for r in roles) or "which sources and files are read"

def help_lines(name, layers):
    """`config help NAME`: everything about one setting."""
    if name not in HELP:
        raise unknown(name)
    h, (value, layer) = HELP[name], resolved(layers)[name]
    lever = lever_of(name)
    lines = [f"{name}: {h.about}", f"  now: {shown(name, value)} ({layer})" + (
        f"; default {shown(name, default(name))}" if layer != "default" else "")]
    if h.more:
        lines.append(f"  {h.more}")
    if h.example:
        lines.append(f"  example: pdf-semantic-diff config set {name} {shlex.quote(h.example)}")
    lines.append(f"  group: {h.group}" + (f"; lever: {lever}" if lever else ""))
    lines.append(f"  changing it redoes: {redoes(name)}")
    return lines

def show_lines(layers, group=None, everything=False, find=None):
    """`config show`: settings listed by group, each with its value, the layer giving it, and what it does: the basic
    ones (none named), a group's, every one (everything), or those whose name or help holds the words (find)."""
    values = resolved(layers)
    if group is not None and group not in GROUPS:
        raise ValueError(f"no group {group!r}; the groups are {', '.join(GROUPS)}")
    words = (find or "").casefold().split()

    def chosen(name):
        h = HELP[name]
        if words:
            text = f"{name} {h.about} {h.more} {lever_of(name)}".casefold()
            return all(w in text for w in words)
        if group:
            return h.group == group
        return everything or h.basic

    picked = [n for n in names() if chosen(n)]
    width = max((len(n) for n in picked), default=0)
    lines = []
    for g in GROUPS:
        mine = [n for n in picked if HELP[n].group == g]
        if not mine:
            continue
        lines.append(f"{g}: {GROUPS[g]}")
        for n in mine:
            value, layer = values[n]
            mark = "" if layer == "default" else f" ({layer})"
            lines.append(f"  {n:<{width}}  {shown(n, value) + mark:<22} {HELP[n].about}")
    if not lines:
        lines.append(f"no setting holds {find!r}" if words else "no setting to show")
    return lines

def exported(values):
    """A layer as `config export` writes it: {"format": 1, "settings": {...}}; an explicit none as "none" (null
    unsets on import)."""
    return {"format": EXPORT_FORMAT, "settings": {k: ("none" if v is None else v) for k, v in values.items()}}

def imported(data):
    """The changes `config import` makes, {name: value, or None to unset}, from `exported`'s JSON; ValueError naming
    every fault when anything is wrong, so that nothing changes."""
    if not isinstance(data, dict) or not isinstance(data.get("settings"), dict):
        raise ValueError('expected {"format": 1, "settings": {NAME: VALUE, ...}}, as `config export` writes')
    if data.get("format", EXPORT_FORMAT) != EXPORT_FORMAT:
        raise ValueError(f"format {data.get('format')!r}; this version reads format {EXPORT_FORMAT}")
    changes, faults = {}, []
    for name, value in data["settings"].items():
        try:
            if name == "levers":
                changes[name] = list(value) if value is not None else None
            elif value is None:
                if name not in HELP:
                    raise unknown(name)
                changes[name] = None
            else:
                text = json.dumps(value) if isinstance(value, (list, dict)) else (
                    ("on" if value else "off") if isinstance(value, bool) else str(value))
                changes[name] = parse(name, text)
        except ValueError as e:
            faults.append(f"{name}: {e}" if not str(e).startswith(("no setting", name)) else str(e))
    if faults:
        raise ValueError("; ".join(faults))
    return changes

def applied(values, changes):
    """A layer with changes made (None unsets), checked whole."""
    out = dict(values)
    for name, value in changes.items():
        if value is None:
            out.pop(name, None)
        else:
            out[name] = value
    return checked(out) if out else {}
