"""Research sketches for docs/research/correspondence-without-a-model-2026-10-02.md: cheap correspondence signals on
the controlled revision pairs' recorded comparisons, offline (no model calls). Throwaway: the revision comparison
plan's milestone 2 rebuilds alignment in the lab, with tests.

    python scripts/alignment_sketch.py claims   # claim-level signals combined Fellegi-Sunter style, leave one pair out
    python scripts/alignment_sketch.py items    # items first (shared values, a margin), then claims within items

Truth is the keys' facts: two claims correspond when the scorer binds both to the same fact. Needs the pairs' runs
(scripts/controlled.py run --replay).
"""
import collections
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
DOCS = ROOT / "benchmarks/controlled/docs"
RUNS = ROOT / "benchmarks/runs/controlled-pairs"
BOUND = ("right", "loose", "wrong unit", "inexact")
TAG = re.compile(r"\b[A-Z]{1,4}-?\d{2,4}[A-Z]?\b")
MARGIN = 0.15  # items: the best counterpart must lead the next by this much (dice units)

def value_key(claim):
    from semantic_pdf_diff.values import parse_number, printed_value
    v = str(claim["value"]).strip()
    p = printed_value(v)
    if p is None:
        n = parse_number(v)
        p = None if n is None else round(n, 6)
    return None if p is None else (p, re.sub(r"\s", "", str(claim.get("unit") or "")).casefold())

def jaccard(a, b):
    from semantic_pdf_diff_lab.bench.controlled.score import tokens
    a, b = tokens(a), tokens(b)
    return len(a & b) / len(a | b) if a | b else 1.0

def load(pair, which="recorded"):
    """(earlier claims, later claims, each claim's bound facts per side, the keys' changes)."""
    from semantic_pdf_diff_lab.bench.controlled import comparison
    from semantic_pdf_diff_lab.bench.controlled.score import classify, key_facts, ranges
    report = json.loads((RUNS / which / pair.id / "report.json").read_text(encoding="utf-8"))
    keys = [json.loads((DOCS / f"{d}.key.json").read_text(encoding="utf-8")) for d in (pair.earlier, pair.later)]
    side = comparison.sides(report)
    facts = [[f for f in key_facts(k) if not f.relation] for k in keys]
    claims = [[e for e in report["evidence"] if side[e["id"]] == s] for s in (0, 1)]
    bound = [[{fid for o, fid in (classify(p, facts[s], keys[s]["printed"]) for p in ranges([e])) if o in BOUND}
              for e in claims[s]] for s in (0, 1)]
    return claims, bound, comparison.changes(*keys)

def tfidf(left, right):
    """Today's retrieval score (compare.candidates), for every pair."""
    from semantic_pdf_diff.compare import words
    docs = [collections.Counter(words(f"{e['entity']} {e['entity']} {e['attribute']} {e['attribute']} {e['conditions']} "
                                      f"{e['value']}", {})) for e in left + right]
    df = collections.Counter(t for d in docs for t in d)
    vectors = []
    for d in docs:
        v = {t: (1 + math.log(n)) * (1 + math.log((len(docs) + 1) / (df[t] + 1))) for t, n in d.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        vectors.append({t: x / norm for t, x in v.items()})
    L, R = vectors[:len(left)], vectors[len(left):]
    return [[sum(w * R[j].get(t, 0) for t, w in L[i].items()) for j in range(len(right))] for i in range(len(left))]

SIGNALS = ("value", "attribute", "entity", "tag", "conditions", "tfidf")

def claim_rows(pair):
    claims, bound, kinds = load(pair)
    A, B = claims
    S = tfidf(A, B)
    rows = []
    for i, a in enumerate(A):
        for j, b in enumerate(B):
            signal = {"value": value_key(a) is not None and value_key(a) == value_key(b),
                      "attribute": jaccard(a["attribute"], b["attribute"]) >= 0.5,
                      "entity": jaccard(a["entity"], b["entity"]) >= 0.5,
                      "tag": bool(set(TAG.findall(a["entity"])) & set(TAG.findall(b["entity"]))),
                      "conditions": jaccard(a["conditions"], b["conditions"]) >= 0.5,
                      "tfidf": S[i][j] >= 0.5}
            same = bound[0][i] & bound[1][j]
            rows.append((i, signal, bool(same), bool(same & set(kinds["changed"]))))
    return rows

def claims_sketch(pairs):
    """Binary agreement signals per claim pair, weighted log2(m/u) from the other five pairs (labels from the keys)."""
    data = [(p.id, claim_rows(p)) for p in pairs]
    total = collections.Counter()
    for k, (name, rows) in enumerate(data):
        m, u, nt, nf = collections.Counter(), collections.Counter(), 0, 0
        for _, other in data[:k] + data[k + 1:]:
            for _, signal, true, _ in other:
                if true:
                    nt += 1
                    m.update(s for s in SIGNALS if signal[s])
                else:
                    nf += 1
                    u.update(s for s in SIGNALS if signal[s])
        mp = {s: (m[s] + 0.5) / (nt + 1) for s in SIGNALS}
        up = {s: (u[s] + 0.5) / (nf + 1) for s in SIGNALS}
        prior = math.log2(nt / nf)
        post = lambda signal: 1 / (1 + 2 ** -(prior + sum(math.log2(mp[s] / up[s]) if signal[s]
                                                          else math.log2((1 - mp[s]) / (1 - up[s])) for s in SIGNALS)))
        scored = [(post(signal), true, changed) for _, signal, true, changed in rows]
        sure = [t for p, t, _ in scored if p >= 0.95]
        middle = [t for p, t, _ in scored if 0.05 <= p < 0.95]
        changed = [p for p, t, c in scored if c]
        lost = sum(p < 0.05 for p in changed)
        print(f"{name:22s} pairs {len(scored):6d}  sure (p>=0.95) {len(sure):4d}, true {sum(sure):4d}  middle {len(middle):4d}  "
              f"changed facts' pairs below 0.05: {lost}/{len(changed)}")
        total.update(sure=len(sure), sure_true=sum(sure), middle=len(middle), changed=len(changed), lost=lost)
    print(dict(total))

def items_sketch(pairs):
    """Items (a tag, else the folded entity) aligned by dice over shared values, rare values counting more, greedy with
    a margin; then claims within aligned items: equal values, then attribute and conditions, best first."""
    from semantic_pdf_diff_lab.bench.controlled.score import tokens
    total = collections.Counter()
    for pair in pairs:
        claims, bound, kinds = load(pair)
        changed = set(kinds["changed"])
        key = lambda e: (TAG.findall(e["entity"]) or [" ".join(sorted(tokens(e["entity"])))])[0]
        items = [collections.defaultdict(list) for _ in (0, 1)]
        for s in (0, 1):
            for i, e in enumerate(claims[s]):
                items[s][key(e)].append(i)
        values = [{k: {value_key(claims[s][i]) for i in idx} - {None} for k, idx in items[s].items()} for s in (0, 1)]
        holders = [collections.Counter(v for vs in values[s].values() for v in vs) for s in (0, 1)]

        def dice(ka, kb):
            shared = values[0][ka] & values[1][kb]
            weight = sum(1 / max(holders[0][v], holders[1][v]) for v in shared)
            size = len(values[0][ka]) + len(values[1][kb])
            return 2 * weight / size if size else 0.0
        score = {(ka, kb): max(dice(ka, kb), 0.6 if ka == kb else 0.0) for ka in items[0] for kb in items[1]}
        aligned, ambiguous, used = {}, [], (set(), set())
        for (ka, kb), sc in sorted(score.items(), key=lambda x: -x[1]):
            if sc < 0.3 or ka in used[0] or kb in used[1]:
                continue
            rivals = [v for (x, y), v in score.items() if (x == ka) != (y == kb) and x not in used[0] and y not in used[1]]
            if rivals and sc - max(rivals) < MARGIN:
                ambiguous.append((ka, kb))
                continue
            aligned[ka] = kb
            used[0].add(ka)
            used[1].add(kb)
        pairs_ = set()
        for ka, kb in aligned.items():
            A, B = items[0][ka], items[1][kb]
            done = (set(), set())
            for i in A:
                for j in B:
                    if value_key(claims[0][i]) is not None and value_key(claims[0][i]) == value_key(claims[1][j]):
                        pairs_.add((i, j))
                        done[0].add(i)
                        done[1].add(j)
            sim = lambda i, j: (jaccard(claims[0][i]["attribute"], claims[1][j]["attribute"])
                                + 0.5 * jaccard(claims[0][i]["conditions"], claims[1][j]["conditions"]))
            best = ({}, {})
            for sc, i, j in sorted(((sim(i, j), i, j) for i in A if i not in done[0] for j in B if j not in done[1]),
                                   reverse=True):
                if sc < 0.5:
                    break
                if i not in best[0] or sc >= best[0][i] - 1e-9 or j not in best[1] or sc >= best[1][j] - 1e-9:
                    pairs_.add((i, j))
                    best[0].setdefault(i, sc)
                    best[1].setdefault(j, sc)
        truth = {(i, j) for i in range(len(claims[0])) for j in range(len(claims[1])) if bound[0][i] & bound[1][j]}
        of_fact = collections.defaultdict(set)
        for i, j in truth:
            for f in bound[0][i] & bound[1][j]:
                of_fact[f].add((i, j))
        covered = {f for f, ps in of_fact.items() if ps & pairs_}
        gone = set(kinds["added"]) | set(kinds["removed"])
        leaked = sum(1 for i, j in pairs_ if (bound[0][i] | bound[1][j]) & gone)
        equal = {(i, j) for i, j in pairs_ if value_key(claims[0][i]) is not None
                 and value_key(claims[0][i]) == value_key(claims[1][j])}
        judge = pairs_ - equal
        print(f"{pair.id:22s} items {len(items[0])}/{len(items[1])}, aligned {len(aligned)}, ambiguous {len(ambiguous)} | "
              f"pairs {len(pairs_)}: equal values {len(equal)}, to judge {len(judge)} (false {len(judge - truth)}) | "
              f"changed facts covered {len(covered & changed)}/{len(set(of_fact) & changed)}, unchanged "
              f"{len(covered - changed)}/{len(set(of_fact) - changed)} | pairs touching added or removed facts {leaked}")
        total.update(pairs=len(pairs_), equal=len(equal), judge=len(judge), judge_false=len(judge - truth),
                     ambiguous=len(ambiguous), leaked=leaked)
    print(dict(total))

def main(argv=None):
    from semantic_pdf_diff_lab.bench.controlled import revisions
    which = (argv or sys.argv[1:] or ["items"])[0]
    {"claims": claims_sketch, "items": items_sketch}[which](revisions.pairs())

if __name__ == "__main__":
    main()
