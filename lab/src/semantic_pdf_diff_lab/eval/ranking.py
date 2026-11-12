"""Measures of a ranking of pairs, each labelled a match or not (evidence combined numerically, milestone 2): its
average precision, its probabilities' log loss and calibration. Shared by the controlled corpus's scorer
(comparison), the fitting (linkfit) and the review panel's links (review.link_scores); in evaluation, which the
benches may use and which reaches into none of them."""
import math
from collections import defaultdict

def average_precision(scored):
    """The precision of a ranking averaged over its matches (scored: [(score, label)]): at each distinct score from the
    top, the precision of every pair scoring as much or more, weighted by the share of the matches it adds; ties count
    together, whatever order they come in. None without a match (evidence combined numerically, milestone 2)."""
    matches = sum(1 for _, label in scored if label)
    if not matches:
        return None
    by = defaultdict(lambda: [0, 0])  # score: [matches, pairs]
    for s, label in scored:
        by[s][0] += bool(label)
        by[s][1] += 1
    out = right = total = 0
    for s in sorted(by, reverse=True):
        right += by[s][0]
        total += by[s][1]
        out += (by[s][0] / matches) * (right / total)
    return round(out, 4)

def log_loss(scored, floor=0.001):
    """The mean log loss of probabilities (scored: [(probability, label)]), each kept within floor of 0 and 1."""
    if not scored:
        return None
    total = 0.0
    for p, label in scored:
        p = min(max(p, floor), 1 - floor)
        total -= math.log(p if label else 1 - p)
    return round(total / len(scored), 4)

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
