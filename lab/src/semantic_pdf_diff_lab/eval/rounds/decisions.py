"""Deciding a round: unit scores with clustered intervals, overall and per stratum, against criteria set before
judging. Split from rounds.py (milestone 8).
"""
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from .. import judgements

def _t_quantile(level, df):
    """t with P(|T| < t) = level for Student's t with integer df, by bisection on the closed-form
    distribution (Abramowitz & Stegun 26.7.3–4)."""
    def inside(t):
        theta = math.atan(t / math.sqrt(df))
        c2, s = math.cos(theta) ** 2, math.sin(theta)
        term = total = 1.0
        if df % 2:
            if df == 1:
                return 2 * theta / math.pi
            for k in range(1, (df - 1) // 2):
                term *= c2 * 2 * k / (2 * k + 1)
                total += term
            return 2 / math.pi * (theta + s * math.cos(theta) * total)
        for k in range(1, df // 2):
            term *= c2 * (2 * k - 1) / (2 * k)
            total += term
        return s * total
    low, high = 0.0, 1000.0
    for _ in range(100):
        mid = (low + high) / 2
        low, high = (mid, high) if inside(mid) < level else (low, mid)
    return (low + high) / 2

def interval(values, clusters=None, level=0.90):
    """(mean, low, high): the mean with a cluster-robust t interval (CR1: G/(G-1) correction, t with
    G-1 degrees of freedom, G the number of clusters); None for no values. It replaced a percentile
    bootstrap (2026-09-28): with 20-30 regions of which few hold several bands, the bootstrap's
    interval moved by 0.03 with how those bands happened to split (r09h), and percentile intervals
    run narrow at such sizes. Clusters are page regions: bands cut from one region share a crop,
    a reading and often a judge's mood. Bounded to [0, 1]; one cluster says nothing: (mean, 0, 1)."""
    if not values:
        return None
    groups = defaultdict(lambda: [0.0, 0])
    for value, key in zip(values, clusters or range(len(values))):
        groups[key][0] += value
        groups[key][1] += 1
    n, g = len(values), len(groups)
    mean = sum(values) / n
    if g < 2:
        return (mean, 0.0, 1.0)
    variance = g / (g - 1) * sum((total - mean * k) ** 2 for total, k in groups.values()) / n ** 2
    half = _t_quantile(level, g - 1) * math.sqrt(variance)
    return (mean, max(0.0, mean - half), min(1.0, mean + half))

def region(unit):
    """The page region a unit was cut from: its id without the band ("…-p4-table-b2of4" → "…-p4-table")."""
    return re.sub(r"-b\d+of\d+$", "", unit)

def unsettled(folder, reviewers, limit=None, verdicts_dir="verdicts"):
    """Units (of the first `limit`) that the given judges leave unsettled, for a second judge:
    one of them lacks an order (a failed verdict), flipped with the order, or they disagree."""
    folder = Path(folder)
    batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
    verdicts = judgements.UnitVerdicts.read(folder, verdicts_dir, raters=set(reviewers))
    return {i["id"] for i in batch["items"][:limit] if verdicts.unsettled(i["id"], reviewers)}

def unit_scores(folder, limit=None, verdicts_dir="verdicts"):
    """{unit id: score in [0, 1]} (judgements.UnitVerdicts), of the batch's first `limit` units
    (the ones every judge has seen when judging proceeds in chunks)."""
    folder = Path(folder)
    batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
    return judgements.UnitVerdicts.read(folder, verdicts_dir).scores([i["id"] for i in batch["items"][:limit]])

# Acceptance (docs/plans/query-improvement): win clearly overall, lose clearly nowhere; the thresholds
# are a round's criteria (models.Criteria), set in round.json before judging.

def decide(folder, limit=None, verdicts_dir="verdicts", documents=None, criteria=None, gains=None):
    """Win rates with intervals, overall and per stratum, and the decision under `criteria` (over the
    first `limit` units when judging is still in progress): decide_scores on a batch's files.

    Strata are the kinds of region (text, table, visual) and, given `documents` ({slice name:
    family}, from scripts/slices.json), the document families (reports, drawings, ...), as the
    plan stratifies; either kind of stratum can block. gains: measured changes, for a named gain."""
    folder = Path(folder)
    batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
    scores = unit_scores(folder, limit, verdicts_dir)
    family = {i["id"]: i["family"] for i in batch["items"]}
    document = {i["id"]: (documents or {}).get(i.get("run")) for i in batch["items"]}
    return decide_scores(scores, family, document, batch["units"], criteria, gains)

def decide_scores(scores, family, document, units, criteria=None, gains=None):
    """The decision on unit scores ({unit id: score}), pure: family and document give each unit's
    strata, units the batch's counts (units, unchanged, changed_by_kind), gains the measured
    relative changes by metric. tests/test_decisions.py simulates it under the null."""
    from ..models import Criteria
    c = criteria or Criteria()
    overall = interval(list(scores.values()), clusters=[region(u) for u in scores])
    strata, sizes = {}, {}
    for f in sorted(set(family.values())) + sorted({d for d in document.values() if d}):
        ids = [u for u in scores if f in (family.get(u), document.get(u))]
        if ids:
            strata[f], sizes[f] = interval([scores[u] for u in ids], clusters=[region(u) for u in ids]), len(ids)
    losing = [f for f, (_, _, high) in strata.items() if high < c.stratum_loss_high and sizes[f] >= c.stratum_min_units]
    gain = None
    if c.gain is not None and (gains or {}).get(c.gain.metric) is not None:
        measured = gains[c.gain.metric]
        gain = {"metric": c.gain.metric, "change": measured,
                "met": measured <= c.gain.change if c.gain.change < 0 else measured >= c.gain.change}
    if overall is None:
        verdict = "no data"
    elif losing:
        verdict = "rejected: loses in " + ", ".join(losing)
    elif c.role == "held-out":
        verdict = ("accepted: holds out" if overall[0] > c.held_out_mean and overall[1] >= c.held_out_low
                   else f"rejected: doesn't hold out (mean {overall[0]:.3f}, low {overall[1]:.3f})")
    elif overall[1] > c.win_low:
        verdict = "accepted: wins"
    elif overall[1] >= c.noninferior_low:
        verdict = (f"accepted: no worse, with its gain ({gain['metric']} {gain['change']:+.1%})" if gain and gain["met"]
                   else "no worse: accept only with a gain named in advance")
    elif overall[2] < c.win_low:
        verdict = "rejected: loses"
    else:
        verdict = "inconclusive"
    # A bound this close to a threshold could fall either side with a few more units, another
    # judge or another interval method: such calls are reported, not trusted on their own.
    near = lambda x, threshold: abs(x - threshold) < c.borderline
    borderline = [] if overall is None else (
        [f"overall low {overall[1]:.3f} near {t}" for t in (c.win_low, c.noninferior_low) if near(overall[1], t)]
        + ([f"overall high {overall[2]:.3f} near {c.win_low}"] if near(overall[2], c.win_low) else [])
        + [f"{f} high {high:.3f} near {c.stratum_loss_high}" for f, (_, _, high) in strata.items()
           if sizes[f] >= c.stratum_min_units and near(high, c.stratum_loss_high)])
    # Strata that don't block but lean to a loss on enough units to look into (the stratum rule has
    # little power: a stratum at 0.35-0.40 is blocked only 14-25% of the time at 6-13 units).
    watch = [f for f, (mean, _, _) in strata.items() if mean < c.stratum_loss_high and sizes[f] >= c.watch_min_units
             and f not in losing]
    # Sampling is round-robin over kinds, so small kinds are over-represented; this weighs each kind's
    # mean by how many of its units changed, as an estimate over all changed units.
    by_kind = units.get("changed_by_kind") or {}
    kinds = {f: strata[f][0] for f in set(family.values()) if f in strata and by_kind.get(f)}
    weighted = (sum(by_kind[f] * m for f, m in kinds.items()) / sum(by_kind[f] for f in kinds)) if kinds else None
    fmt = lambda t: None if t is None else {"mean": round(t[0], 3), "low": round(t[1], 3), "high": round(t[2], 3)}
    changed = units["units"] - units["unchanged"]
    # Win rates are over changed units only: coverage says how much of the output a lever touches.
    return {"units_judged": len(scores), "regions_judged": len({region(u) for u in scores}), "overall": fmt(overall),
            "strata": {f: fmt(t) for f, t in strata.items()},
            "strata_units": sizes, "decision": verdict, "accepted": verdict.startswith("accepted"),
            "role": c.role, "gain": gain, "borderline": borderline, "watch": watch,
            "overall_weighted_by_changed": None if weighted is None else round(weighted, 3), "units": units,
            "coverage": round(changed / units["units"], 3) if units["units"] else None}

def lock_criteria(state, criteria):
    """Criteria are fixed when judging starts (the owner's decision A: set in advance): the first call
    records them in the round's state, later ones refuse any change (ValueError)."""
    fixed = state.get("criteria")
    if fixed is None:
        state["criteria"] = criteria
    elif fixed != criteria:
        changed = sorted(k for k in set(fixed) | set(criteria) if fixed.get(k) != criteria.get(k))
        raise ValueError(f"the round's criteria changed after judging started ({', '.join(changed)}); "
                         "they're set in advance: start a new round to decide by others")
    return state["criteria"]
