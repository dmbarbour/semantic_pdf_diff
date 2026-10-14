"""Arms compared document by document on the controlled corpus: a lever judged by what it changes, against arms
that change the same queries to no purpose (docs/samples-and-testing.md, "Judging a lever").

Arms read the same documents from copies of one fixture, so a query a lever leaves alone gets its recorded answer
and moves nothing: only the queries a lever changes can move a document's scores. gemma-4 answers a changed query
anew, and a reworded prompt differently even at temperature 0, so a lever changing every image query moves facts both
ways (a rule meant to do nothing moved the corpus's relations read right 416 -> 444 on 2026-10-14, as far as the
arrow rule it was controlling for). Totals can't tell that churn from a gain; pairs of documents can:

- **A measure's change per document,** summed, with a 90% interval from resampling the documents.
- **A sign-flip test:** with no effect, either arm is as likely to be ahead on any document, so the documents' changes
  are given random signs and the share of sums at least as far from zero is the p-value (exact up to 16 documents
  changed; else 20,000 seeded draws). Documents are the unit because one query moves several of a document's facts.
- **Null arms:** a lever changing many queries is judged against arms changing the same queries to no purpose (a
  do-nothing rule), each a rewording's own draw, as well as against the base.

The verdict (`judge`) is set before the arms are read: a lever names its target measure (what it should improve:
reversed relations for an arrow rule) and guards (facts read right). It's "better" when the target improves on the
base and on every null arm, each at p < 0.1, and no guard is worse on the base at p < 0.1; "worse" when the target
or a guard is worse on the base and on every null arm; otherwise "no different".
"""
import contextlib
import itertools
import json
import random
import sqlite3
from pathlib import Path

# Each measure's better direction: +1 higher is better, -1 lower is better, 0 neither.
CLAIM_OUTCOMES = ("right", "loose", "misbound", "inexact", "wrong unit", "misread", "hallucinated", "text",
                  "distractor")
RELATION_OUTCOMES = ("right", "implied", "reversed", "wrong", "invented", "unscored")
DIRECTION = {"facts right": 1, "facts found": 1, "claims right": 1, "relations right": 1, "relations unscored": 0,
             **{f"claims {o}": -1 for o in CLAIM_OUTCOMES if o != "right"},
             **{f"relations {o}": -1 for o in RELATION_OUTCOMES if o not in ("right", "unscored")}}
LEVEL = 0.1      # a change counts at p below this, two-sided
DRAWS = 20_000   # sign-flip draws beyond exact enumeration
EXACT = 16       # documents changed up to which every sign pattern is enumerated
RESAMPLES = 2_000

def measures(key, claims):
    """({measure: count}, {fact id: "right" or "loose"}) for one document's claims against its key."""
    from .controlled.score import _scored
    result, found = _scored(key, claims)
    out = {"facts right": result["found_right"], "facts found": len(found)}
    out.update({f"claims {o}": result["outcomes"].get(o, 0) for o in CLAIM_OUTCOMES})
    if "relations" in result:
        out.update({f"relations {o}": result["relations"].get(o, 0) for o in RELATION_OUTCOMES})
    return out, found

def claims_of(store):
    """A run's claims, as its store holds them (by task and id, whatever order tasks finished in)."""
    with contextlib.closing(sqlite3.connect(f"file:{store}?mode=ro", uri=True)) as db:
        return [json.loads(data) for (data,) in db.execute("SELECT data FROM evidence ORDER BY task, id")]

KEYS = {".md": "docs-md", ".docx": "docs-docx", ".pptx": "docs-pptx", ".xlsx": "docs-xlsx"}

def key_of(corpus, run):
    """A run's key in the controlled corpus's folder: "<id>.md" in docs-md, and so on; a PDF's in docs."""
    for suffix, folder in KEYS.items():
        if run.endswith(suffix):
            return Path(corpus) / folder / f"{run[:-len(suffix)]}.key.json"
    return Path(corpus) / "docs" / f"{run}.key.json"

def arm(folder, corpus):
    """{document: (measures, facts found)} for an arm's runs under folder (one per document, each with its
    store.sqlite), scored by their keys in the controlled corpus's folder. A run a cap cut is left out (resumed, not
    scored: recording.cut), so it's compared in neither arm."""
    from .recording import cut
    out = {}
    for run in sorted(Path(folder).iterdir()):
        if (run / "store.sqlite").exists() and not cut(run):
            key = json.loads(key_of(corpus, run.name).read_text(encoding="utf-8"))
            out[run.name] = measures(key, claims_of(run / "store.sqlite"))
    return out

def sign_flip(changes, seed=0):
    """Two-sided p-value of the changes' sum under random signs (exact up to EXACT nonzero changes)."""
    changes = [c for c in changes if c]
    total = abs(sum(changes))
    if not changes or not total:
        return 1.0
    if len(changes) <= EXACT:
        hits = sum(abs(sum(s * c for s, c in zip(signs, changes))) >= total
                   for signs in itertools.product((1, -1), repeat=len(changes)))
        return hits / 2 ** len(changes)
    rng = random.Random(seed)
    draws = DRAWS  # read when called, so tests may lower it
    hits = sum(abs(sum(c if rng.random() < 0.5 else -c for c in changes)) >= total for _ in range(draws))
    return (hits + 1) / (draws + 1)

def interval(changes, seed=0):
    """A 90% interval for the changes' sum, resampling documents (percentiles of RESAMPLES seeded resamples)."""
    if not changes:
        return (0, 0)
    rng, resamples = random.Random(seed), RESAMPLES
    sums = sorted(sum(rng.choices(changes, k=len(changes))) for _ in range(resamples))
    return (sums[int(0.05 * resamples)], sums[int(0.95 * resamples) - 1])

def compare(before, after, measure, seed=0):
    """One measure from arm `before` to arm `after`, over the documents both read: totals, change, the documents it
    moved, interval, p, and "better", "worse" or None (not at p < LEVEL, or a measure with no better direction).
    For facts, also how many each arm alone had right."""
    docs = sorted(set(before) & set(after))
    changes = [after[d][0].get(measure, 0) - before[d][0].get(measure, 0) for d in docs]
    p = sign_flip(changes, seed)
    change = sum(changes)
    direction = DIRECTION.get(measure, 0) * (change > 0) - DIRECTION.get(measure, 0) * (change < 0)
    out = {"measure": measure, "documents": len(docs), "before": sum(before[d][0].get(measure, 0) for d in docs),
           "after": sum(after[d][0].get(measure, 0) for d in docs), "change": change,
           "moved": sum(1 for c in changes if c), "interval": interval(changes, seed), "p": round(p, 4),
           "verdict": None if p >= LEVEL or not direction else ("better" if direction > 0 else "worse")}
    if measure == "facts right":
        right = lambda arm, d: {f for f, how in arm[d][1].items() if how == "right"}  # noqa: E731
        out["gained"] = sum(len(right(after, d) - right(before, d)) for d in docs)
        out["lost"] = sum(len(right(before, d) - right(after, d)) for d in docs)
    return out

def judge(lever, base, nulls=(), target="facts right", guards=("facts right",), seed=0):
    """The verdict on a lever's arm against the base and each null arm (see the module's docstring), with every
    comparison made: {"verdict", "target", "against base", "against nulls", "nulls against base", "guards"}."""
    on_base = compare(base, lever, target, seed)
    on_nulls = [compare(null, lever, target, seed) for null in nulls]
    guarded = [compare(base, lever, g, seed) for g in guards if g != target]
    if on_base["verdict"] == "better" and all(c["verdict"] == "better" for c in on_nulls) \
            and not any(g["verdict"] == "worse" for g in guarded):
        verdict = "better"
    elif any(c["verdict"] == "worse" and all(compare(null, lever, c["measure"], seed)["verdict"] == "worse"
                                               for null in nulls) for c in (on_base, *guarded)):
        verdict = "worse"
    else:
        verdict = "no different"
    return {"verdict": verdict, "target": target, "against base": on_base, "against nulls": on_nulls,
            "nulls against base": [compare(base, null, target, seed) for null in nulls], "guards": guarded}

def table(rows):
    """Comparisons as Markdown rows: measure, totals, change, interval, documents moved, p, verdict."""
    lines = ["| arms | measure | before | after | change | 90% interval | documents moved | p | verdict |",
             "|---|---|---|---|---|---|---|---|---|"]
    for label, c in rows:
        flips = f" (+{c['gained']} / -{c['lost']})" if "gained" in c else ""
        lines.append(f"| {label} | {c['measure']} | {c['before']} | {c['after']} | {c['change']:+d}{flips} | "
                     f"{c['interval'][0]:+d} to {c['interval'][1]:+d} | {c['moved']} of {c['documents']} | "
                     f"{c['p']:.3f} | {c['verdict'] or '-'} |")
    return "\n".join(lines)
