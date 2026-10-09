"""Refinement measured where it happens: every tile of a document refined once, whatever its answer.

A tile is refined in halves only when its answer is partial or failed, which is rare in a run (36 tiles in the slices
fixture): too few to judge a change to how tiles are halved. So the lab forces it. `forced()` marks every answer to
an unrefined tile partial, as it reaches the task, and a run with `refinement_depth` 1 then asks each tile's two
halves once. The product has no such setting (review-bugs-2026-10-09, item 6; the owner: "seems reasonable").

Each half is then counted from the run's store: its claims, whether it found none, and against a controlled
document's key, its right and misbound claims (controlled.score).
"""
import contextlib
import json
import sqlite3
from pathlib import Path

@contextlib.contextmanager
def forced():
    """Every answer to an unrefined tile's extraction taken as partial, so the tile is refined."""
    from semantic_pdf_diff.dispatch import Dispatcher
    from semantic_pdf_diff.regions import region_of
    submit = Dispatcher.submit

    def forcing(self, prompt, schema, images, key, finish):
        if key and key[0] == "extract" and region_of(key[3]) == "tile" and "-r" not in key[3]:
            inner = finish

            def finish(value, error):
                inner(value.model_copy(update={"complete": False}) if value is not None else None, error)
        return submit(self, prompt, schema, images, key, finish)
    Dispatcher.submit = forcing
    try:
        yield
    finally:
        Dispatcher.submit = submit

def halves(store):
    """{parent tile's task: {half's task: [claims]}} from a run's store; a half's continuations count as the half."""
    with contextlib.closing(sqlite3.connect(f"file:{store}?mode=ro", uri=True)) as db:
        tasks = [t for (t,) in db.execute("SELECT task FROM task WHERE task LIKE 'tile:%'")]
        claims = {}
        for task, data in db.execute("SELECT task, data FROM evidence WHERE task LIKE 'tile:%'"):
            claims.setdefault(task, []).append(json.loads(data))
    out = {}
    for task in tasks:
        parent, _, rest = task.partition("-r")
        if rest:
            half = f"{parent}-r{rest.split('-')[0]}"
            out.setdefault(parent, {}).setdefault(half, []).extend(claims.get(task, []))
    return out

def summary(store, key=None):
    """Counts over a run's halves: parents, halves, empty halves, claims, and with a key, outcomes of their claims."""
    found = halves(store)
    every = [c for parts in found.values() for cs in parts.values() for c in cs]
    out = {"parents": len(found), "halves": sum(len(parts) for parts in found.values()),
           "empty": sum(1 for parts in found.values() for cs in parts.values() if not cs), "claims": len(every)}
    if key is not None:
        from .controlled import score
        result = score(key, every)
        out["outcomes"] = result["outcomes"]
        out["facts_right"] = result["found_right"]
    return out

def compare(before, after, keys=None):
    """{document: {"before": summary, "after": summary}} for runs under two folders of per-document stores."""
    keys = keys or {}
    out = {}
    for store in sorted(Path(after).glob("*/store.sqlite")):
        name = store.parent.name
        other = Path(before) / name / "store.sqlite"
        if other.exists():
            key = json.loads(keys[name].read_text(encoding="utf-8")) if name in keys else None
            out[name] = {"before": summary(other, key), "after": summary(store, key)}
    return out
