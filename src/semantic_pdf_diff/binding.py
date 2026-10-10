"""A store's binding to its interpreters (decision 0004): what differs from the interpreter a run brings, whether going
ahead can cost a model call, what it would clear and ask again, and the refusal that says so. Policy over the store's
operations (Store.interpreter, save_interpreter, clear_extraction, clear_situating, logged_queries): split from
store.py (code review 2026-10-08, C5).
"""
from .levers import ALL_REGIONS, declared, setting_regions
from .schema import Interpreter
from .settings import Settings
from .store import StoreError

# Extraction regions that a changed extraction setting affects (levers.Declared regions); anything not listed
# (model, prompts, library versions, sampling and output options) affects them all.
SETTING_REGIONS = setting_regions(Settings)

KIND_EFFECT = {"shaping": "shapes what's asked", "selecting": "changes which requests are made",
               "post": "post-processes answers"}

def _kind(key):
    """A difference's kind of setting ("shaping", "post", ...), or "" for the model, prompts and versions."""
    name = key.split(".", 1)[1] if key.startswith("settings.") else None
    return declared(Settings, name).kind if name in Settings.model_fields else ""

def free(differences):
    """Whether no difference can cost a model call: each a setting that only post-processes answers."""
    return all(_kind(key) == "post" for key in differences)

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
                                              "settings.levers": "the levers in use"}.get(key, "may change every request")
    return f"{name}: {shown} ({effect})"

class InterpreterMismatch(StoreError):
    """A run refused: the store was made with another interpreter. The message says what differs, what going ahead
    (--reset) would clear, and at most how many requests would be asked again."""
    def __init__(self, role, differences, regions, cleared=None, estimate=None):
        self.role, self.differences, self.regions = role, differences, regions
        what = {"extract": "extraction settings", "triage": "situating settings"}.get(role, f"{role} interpreter")
        lines = [f"This store was made with other {what}:"] + [f"  - {describe(k, a, b)}" for k, (a, b) in
                                                               differences.items()]
        if role == "triage":
            effect = "situating results (figures' and sections' \"about\" statements)"
        else:
            effect = (f"{', '.join(sorted(regions))} extraction" +
                      (f": {cleared['tasks']:,} tasks and {cleared['evidence']:,} claim sightings" if cleared else "") +
                      "; situating" + (f"; {cleared['comparisons']} saved comparisons" if cleared else "; comparisons"))
        lines.append(f"Going ahead clears what they affect ({effect}) and reads it again.")
        if estimate and estimate["requests"]:
            lines.append(f"Requests whose queries didn't change replay free from the store's cache; at most "
                         f"{estimate['requests']:,} would be asked again (about {estimate['text_bytes'] // 4:,} tokens "
                         f"of text and {estimate['images']:,} images), if every one changed.")
        else:
            lines.append("Requests whose queries didn't change replay free from the store's cache.")
        lines.append("To go ahead, rerun with --reset (--reset --dry-run shows what it clears), or use a new store.")
        super().__init__("\n".join(lines))


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

def affected_regions(differences):
    regions = set()
    for key in differences:
        name = key.split(".", 1)[1] if key.startswith("settings.") else None
        regions |= SETTING_REGIONS.get(name, ALL_REGIONS)
    return regions

def bind(store, interpreter: Interpreter, reset=False, dry_run=False):
    """Bind a store to an interpreter. Returns a summary of what was (or would be) cleared."""
    new = interpreter.model_dump()
    old = store.interpreter(interpreter.role)
    if old is None:
        if not dry_run:
            store.save_interpreter(interpreter.role, new)
        return {}
    differences = interpreter_differences(old, new)
    if not differences:
        return {}
    automatic = free(differences) and not reset  # can't cost a model call: applied without asking
    if interpreter.role == "triage":
        if not (reset or automatic):
            raise InterpreterMismatch("triage", differences, {"situating"},
                                      estimate=rerun_estimate(store, "triage", None))
        counts = store.clear_situating(dry_run=dry_run, rebind=None if dry_run else new)
    else:
        regions = affected_regions(differences)
        if not (reset or automatic):
            raise InterpreterMismatch(interpreter.role, differences, regions,
                                      store.clear_extraction(regions, dry_run=True),
                                      rerun_estimate(store, interpreter.role, regions))
        # a rebind nobody was asked about keeps the saved comparisons, self-contained records of earlier runs
        # (code review 2026-10-08, C24: deleted silently); a reset clears them, as it says (decision 0004)
        counts = store.clear_extraction(regions, dry_run=dry_run, rebind=None if dry_run else new,
                                        keep_comparisons=automatic)
    if automatic:
        counts["automatic"] = [describe(k, a, b) for k, (a, b) in differences.items()]
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
