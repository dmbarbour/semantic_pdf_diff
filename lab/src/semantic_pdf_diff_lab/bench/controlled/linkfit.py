"""Levels from numbers (docs/plans/tentative-matches-2026-11-07.md, milestone 6; the owner, 2026-11-07: "Perhaps we
start with a three-levels rubric then figure out how to analyze or evidence a fuzzy, weighted, or probabilistic
numeric match (Bayesian, BM25, etc.)").

- **A pair's features,** banded (bands()): from links.candidates, whatever the settings: names alike; names alike in
  meaning (none where no vectors were made, else by cosine); properties in common (0, 1, 2, 3 or more) and whether
  they set the pair apart from its siblings; whether their values fit; the judge's verdicts that count (0, 1, 2 or
  more); the model's match (none, the same or the corresponding, a state, taken). The model's read against a decoy
  isn't a feature: it's asked only of links already chosen, so its absence says "not chosen", not "no evidence"; it
  stays a test applied after (links.py).
- **Labelled by the keys** (labelled()): each side's claims bound to the keys' facts, a fact's role its id's; a match
  where each side's most bound item is one, a non-match where they differ, left out where a side is bound to none.
  A pair whose properties in common don't set it apart (siblings: the keys tell one design's pump from another's by
  their rows' order, which no feature sees) is flagged, and reported apart.
- **Fellegi-Sunter weights** (fitted()): for each feature's band, m (its share among matches) and u (among
  non-matches), smoothed (SMOOTH); its weight log2(m / u); a pair's score the sum. A band never seen ("absent") weighs
  nothing. A logistic regression with an L2 penalty on the same bands beside it (logistic()): the features overlap
  (names and meaning), which the sum counts twice.
- **Calibrated** (calibration()): the share of matches in each band of scores against what the score says (its
  posterior, with the training set's share of matches as the prior).
- **Proposals only:** revisions' subjects left alone hold too few counterparts to fit (the split revision's two).
"""
import math
from collections import Counter, defaultdict

SMOOTH = 0.5  # added to each band's count
FEATURES = ("alike", "meaning", "properties", "distinct", "fits", "judged", "model")

def bands(candidate, mode):
    """A candidate pair's features, banded: the product's (links.bands), so what's fitted is what's read."""
    from semantic_pdf_diff.links import bands as product
    return product(candidate, mode)

def labelled(report, keys, mode):
    """Each candidate pair of a report, banded and labelled by the keys: [{"bands", "label": True (a match), False,
    "sibling": its properties in common don't set it apart, "pair": (subject, other)}]; pairs a side of which is bound
    to no fact are left out."""
    from semantic_pdf_diff import indexes, links

    from . import comparison
    side = comparison.sides(report)
    bound = comparison._bound(report, side, keys, {})
    facts = [{f["id"]: f for f in k["facts"] if f["role"] == "fact" and not f.get("relation")} for k in keys]
    item = comparison._items(facts)

    def most(claims):
        found = Counter(item(fid) for c in claims for fid in bound.get(c, {}) if fid in facts[0] or fid in facts[1])
        top = max(found.values(), default=0)
        return {i for i, n in found.items() if n == top} if top else set()
    index = indexes.built(report)
    subjects = index["subjects"]
    out = []
    for c in links.candidates(report, index):
        a = most(next(iter(subjects[c["i"]]["claims"].values())))
        b = most(next(iter(subjects[c["j"]]["claims"].values())))
        if not a or not b:
            continue
        out.append({"bands": bands(c, mode), "label": bool(a & b),
                    "sibling": len(c["evidence"]["properties"]) >= 2 and not c["distinct"],
                    "pair": (subjects[c["i"]]["name"], subjects[c["j"]]["name"])})
    return out

def fitted(rows):
    """Fellegi-Sunter weights from labelled rows: {"weights": {feature: {band: log2(m / u)}}, "prior": the share of
    matches, "matches", "pairs"}."""
    m, u = defaultdict(Counter), defaultdict(Counter)
    matches = sum(1 for r in rows if r["label"])
    others = len(rows) - matches
    for r in rows:
        for f, b in r["bands"].items():
            (m if r["label"] else u)[f][b] += 1
    weights = {}
    for f in FEATURES:
        seen = sorted(set(m[f]) | set(u[f]))
        k = len(seen) or 1
        weights[f] = {b: 0.0 if b == "absent" else round(math.log2(
            ((m[f][b] + SMOOTH) / (matches + k * SMOOTH)) / ((u[f][b] + SMOOTH) / (others + k * SMOOTH))), 3)
            for b in seen}
    return {"weights": weights, "prior": matches / len(rows) if rows else 0.0, "matches": matches,
            "pairs": len(rows)}

def score(table, row_bands):
    """A pair's score: its bands' weights summed (a band the table hasn't seen weighs nothing)."""
    return sum(table["weights"].get(f, {}).get(b, 0.0) for f, b in row_bands.items())

def posterior(table, s):
    """The share of matches a score says: its likelihood ratio over the prior odds."""
    p = table["prior"]
    if p <= 0 or p >= 1:
        return p
    odds = (p / (1 - p)) * 2 ** s
    return odds / (1 + odds)

def logistic(rows, l2=1.0, steps=3000, rate=0.1):
    """A logistic regression with an L2 penalty over the bands one-hot ({"weights": {feature: {band: w}}, "bias"}):
    gradient descent, plain Python (the rows are few)."""
    keys = sorted({(f, b) for r in rows for f, b in r["bands"].items()})
    w = dict.fromkeys(keys, 0.0)
    bias = 0.0
    n = len(rows) or 1
    for _ in range(steps):
        grad, gb = Counter(), 0.0
        for r in rows:
            z = bias + sum(w[(f, b)] for f, b in r["bands"].items())
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            d = p - (1.0 if r["label"] else 0.0)
            gb += d
            for f, b in r["bands"].items():
                grad[(f, b)] += d
        bias -= rate * gb / n
        for key in keys:
            w[key] -= rate * (grad[key] / n + l2 * w[key] / n)
    out = defaultdict(dict)
    for (f, b), x in w.items():
        out[f][b] = round(x, 3)
    return {"weights": dict(out), "bias": round(bias, 3)}

def logit_p(model, row_bands):
    z = model["bias"] + sum(model["weights"].get(f, {}).get(b, 0.0) for f, b in row_bands.items())
    return 1 / (1 + math.exp(-max(-30, min(30, z))))

def threshold(scored, precision):
    """The lowest score whose pairs at or above it are right in this share or more, keeping the most right ones:
    (threshold, right, of); None where no threshold reaches it. scored: [(score, label)]."""
    best = None
    ordered = sorted(scored, key=lambda x: -x[0])
    right = total = 0
    for k, (s, label) in enumerate(ordered):
        right += label
        total += 1
        last = k + 1 == len(ordered) or ordered[k + 1][0] < s
        if last and right / total >= precision and (best is None or right > best[1]):
            best = (s, right, total)
    return best

def calibration(scored, edges=(0.1, 0.3, 0.5, 0.7, 0.9)):
    """[(band, pairs, matches, mean predicted)]: pairs by predicted share of matches, against the share observed.
    scored: [(predicted, label)]."""
    out = []
    lows = (0.0,) + tuple(edges)
    highs = tuple(edges) + (1.01,)
    for lo, hi in zip(lows, highs):
        mine = [(p, label) for p, label in scored if lo <= p < hi]
        if mine:
            out.append((f"{lo:.1f}-{min(hi, 1.0):.1f}", len(mine), sum(label for _, label in mine),
                        round(sum(p for p, _ in mine) / len(mine), 3)))
    return out
