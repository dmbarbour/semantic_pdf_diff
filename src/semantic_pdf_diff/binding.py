"""A store's binding to its interpreters (decision 0004): what differs from the interpreter a run brings, whether going
ahead can cost a model call, and what it clears to read again, and asks again at most. A changed interpreter redoes
what it affects, never refused since 2026-10-20 (the owner: "Redo instead of refusing, yes."); a reset starts the store
over. Policy over the store's operations (Store.interpreter, save_interpreter, clear_extraction, clear_situating,
logged_queries): split from store.py (code review 2026-10-08, C5).
"""
from .levers import ALL_REGIONS, REGISTRY, declared, setting_regions
from .schema import Interpreter
from .settings import Settings

# Extraction regions that a changed extraction setting affects (levers.Declared regions); anything not listed
# (model, prompts, library versions, sampling and output options) affects them all.
SETTING_REGIONS = setting_regions(Settings)

KIND_EFFECT = {"shaping": "shapes what's asked", "selecting": "changes which requests are made",
               "post": "post-processes answers"}

def _kind(key):
    """A difference's kind of setting ("shaping", "post", ...), or "" for the model, prompts and versions."""
    name = key.split(".", 1)[1] if key.startswith("settings.") else None
    return declared(Settings, name).kind if name in Settings.model_fields else ""

def _post_only(lever):
    """Whether a lever's settings all only post-process answers."""
    return lever in REGISTRY and all(declared(Settings, name).kind == "post" for name in REGISTRY[lever].model_fields
                                     if name in Settings.model_fields)

def _levers_moved(a, b, old, new, post=False):
    """Whether the levers added (b's, not a's) or dropped (a's, not b's), the rest in order, are each off on the side
    that has them, or (post) a lever that only post-processes answers."""
    moved = [(lever, new) for lever in b if lever not in a] + [(lever, old) for lever in a if lever not in b]
    off = lambda lever, side: bool(REGISTRY[lever].off) and all(  # noqa: E731
        (side or {}).get("settings", {}).get(s, OFF[s]) == OFF[s] for s in REGISTRY[lever].off)
    return [x for x in a if x in b] == [x for x in b if x in a] and all(
        lever in REGISTRY and (off(lever, side) or post and _post_only(lever)) for lever, side in moved)

def free(differences, old=None, new=None):
    """Whether no difference can cost a model call: each a setting that only post-processes answers, or levers
    added or dropped each off or only post-processing."""
    def one(key, a, b):
        if key == "settings.levers" and isinstance(a, list) and isinstance(b, list):
            return _levers_moved(a, b, old, new, post=True)
        return _kind(key) == "post"
    return all(one(key, a, b) for key, (a, b) in differences.items())

def describe(key, old, new):
    """One difference, plainly: "claims_per_request: 20 -> 25 (shapes what's asked)"; lists by what came and went."""
    name = key.split(".", 1)[1] if key.startswith("settings.") else key
    if isinstance(old, list) and isinstance(new, list):
        moves = [f"+{x}" for x in new if x not in old] + [f"-{x}" for x in old if x not in new]
        shown = ", ".join(moves) or "reordered"
    else:
        shown = f"{old!r} -> {new!r}"
    effect = KIND_EFFECT.get(_kind(key)) or {"model": "another model: every request is asked again",
                                              "prompt_hash": "the prompts: every request changes",
                                              "settings.levers": "the levers in use"}.get(key,
                                                                                          "may change every request")
    return f"{name}: {shown} ({effect})"

def redone(role, counts):
    """The log's line for a rebinding (bind's summary): what changed, and what's read again or recomputed."""
    changed = "; ".join(counts["changed"])
    if counts.get("free"):
        return f"Changed settings that only post-process answers ({changed}): what they affect is recomputed from " \
               "cached answers"
    if role == "triage":
        what = f"situating done again ({counts['situated_content']:,} items)"
    else:
        what = (f"{', '.join(counts['regions'])} extraction read again ({counts['tasks']:,} tasks, "
                f"{counts['evidence']:,} claim sightings), then situating")
    estimate = counts.get("estimate") or {}
    asked = (f", at most {estimate['requests']:,} asked again (about {estimate['text_bytes'] // 4:,} tokens of text "
             f"and {estimate['images']:,} images)" if estimate.get("requests") else "")
    return (f"Changed {'situating' if role == 'triage' else 'extraction'} settings ({changed}): {what}. Queries that "
            f"didn't change are answered from the cache{asked}")


def interpreter_differences(old, new):
    """Flattened {field: (old, new)} for differing parts of two interpreter descriptions."""
    diff = {}
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if isinstance(a, dict) and isinstance(b, dict):
            diff.update({f"{key}.{k}": v for k, v in interpreter_differences(a, b).items()})
        elif a != b:
            diff[key] = (a, b)
    return diff

# Each lever setting's off value: what asks exactly what leaving its lever out asks (Lever.off)
OFF = {name: value for lever in REGISTRY.values() for name, value in lever.off.items()}

def _asks_alike(key, a, b, old, new):
    """Whether a difference asks nothing new: a setting one side doesn't have, at its lever's off value on the
    other, or levers added or dropped with every setting of theirs off (a lever built, off, after a store was made
    asks what the store's run asked)."""
    name = key.split(".", 1)[1] if key.startswith("settings.") else None
    if name == "levers" and isinstance(a, list) and isinstance(b, list):
        return _levers_moved(a, b, old, new)
    return name in OFF and (a is None or b is None) and (b if a is None else a) == OFF[name]

def affected_regions(differences):
    regions = set()
    for key in differences:
        name = key.split(".", 1)[1] if key.startswith("settings.") else None
        regions |= SETTING_REGIONS.get(name, ALL_REGIONS)
    return regions

def bind(store, interpreter: Interpreter, reset=False, dry_run=False):
    """Bind a store to an interpreter. What a changed one affects is cleared, to be read again (its unchanged queries
    answered from the cache); with reset, everything the role derived, to start the store over. Returns what was (or
    would be) cleared, as the store counts it, with "changed" (each difference, described: describe), "free" when no
    difference can cost a model call, and "estimate" (at most what reading again asks: rerun_estimate). Saved
    comparisons, self-contained records of earlier runs, are kept but by a reset (code review 2026-10-08, C24)."""
    new = interpreter.model_dump()
    old = store.interpreter(interpreter.role)
    if old is None:
        if not dry_run:
            store.save_interpreter(interpreter.role, new)
        return {}
    differences = {k: (a, b) for k, (a, b) in interpreter_differences(old, new).items()
                   if not _asks_alike(k, a, b, old, new)}
    if not differences and not reset:
        if old != new and not dry_run:
            store.save_interpreter(interpreter.role, new)  # only levers off that the store didn't know
        return {}
    costless = bool(differences) and free(differences, old, new) and not reset
    regions = ALL_REGIONS if reset else affected_regions(differences)
    estimate = None if costless else rerun_estimate(store, interpreter.role,
                                                    None if interpreter.role == "triage" or reset else regions)
    if interpreter.role == "triage":
        counts = store.clear_situating(dry_run=dry_run, rebind=None if dry_run else new)
    else:
        counts = store.clear_extraction(regions, dry_run=dry_run, rebind=None if dry_run else new,
                                        keep_comparisons=not reset)
    if differences:
        counts["changed"] = [describe(k, a, b) for k, (a, b) in differences.items()]
    if costless:
        counts["free"] = True
    elif estimate:
        counts["estimate"] = estimate
    return counts

def rerun_estimate(store, role, regions):
    """At most what reading again would ask: the role's logged queries (in these regions), their text's size and
    their images. An upper bound: queries that didn't change replay from the cache."""
    requests, text, images = 0, 0, 0
    for prompt, pictures in store.logged_queries(role, regions):
        requests += 1
        text += len((prompt or "").encode())
        images += len(pictures)
    return {"requests": requests, "text_bytes": text, "images": images}
