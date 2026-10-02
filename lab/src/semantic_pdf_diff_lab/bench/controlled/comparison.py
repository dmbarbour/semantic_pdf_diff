"""Comparison scoring on revision pairs (controlled documents, milestone 4): a report's findings, in revisions mode,
against the key's changes.

Each revision's claims are bound to its own key's facts (score.classify; a range, "66 to 75 °F", to both its
bounds' facts, as score.ranges reads one), so a finding pairs two facts, or one fact read in both revisions. Each
fact is then classed by what the report says of it:
- **changed** (its value revised): reported (a "different" finding), called equivalent, uncertain, other
  (complementary or unrelated only), unpaired (never compared), or unextracted (no claim of it in a revision)
- **unchanged:** confirmed (equivalent), false change (different), uncertain, other, unpaired, unextracted
- **added or removed:** reported (a claim of it left without a counterpart, as the report lists them), as a change
  (paired as different with something), called equivalent, other (complementary only), unextracted

Every "different" and "equivalent" finding is classed too: a change, no change, a misreading (a claim bound to its
fact but read wrong), across facts (two facts' claims paired), or unscored (a claim bound to no fact).

Relations (a door's room) aren't compared yet: they're left out of the changes.
"""
from collections import Counter, defaultdict

from .score import classify, key_facts, ranges

BOUND = ("right", "loose")              # a claim of its fact, read right
READ_WRONG = ("wrong unit", "inexact")  # a claim of its fact, read wrong

def changes(earlier, later):
    """The facts' changes between two revisions' keys, by fact id (distractors and relations aside)."""
    facts = lambda key: {f["id"]: f for f in key["facts"] if f["role"] == "fact" and not f.get("relation")}
    a, b = facts(earlier), facts(later)
    both = a.keys() & b.keys()
    return {"changed": sorted(i for i in both if a[i]["value"] != b[i]["value"]),
            "added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()),
            "unchanged": sorted(i for i in both if a[i]["value"] == b[i]["value"])}

def sides(report):
    """{claim id: 0 (the earlier revision's) or 1 (the later's)}, by the source its file is in."""
    first = report["sources"][0]["name"]
    side = {}
    for f in report["files"]:
        side.setdefault(f["content"], set()).add(0 if f["source"] == first else 1)
    if any(len(s) > 1 for s in side.values()):
        raise ValueError("a file is in both revisions: its claims are shared, not compared")
    return {e["id"]: min(side[e["content"]]) for e in report["evidence"]}

def score_comparison(earlier, later, report):
    """A comparison report (report.json's data) scored against the two revisions' keys (see the module's note)."""
    side, keys = sides(report), (earlier, later)
    facts = [[f for f in key_facts(k) if not f.relation] for k in keys]
    bound = {}  # claim id: {fact id: outcome}, the facts it's bound to
    for e in report["evidence"]:
        s = side[e["id"]]
        read = [classify(part, facts[s], keys[s]["printed"]) for part in ranges([e])]
        bound[e["id"]] = {fid: outcome for outcome, fid in read if outcome in BOUND + READ_WRONG}
    kinds = changes(earlier, later)
    kind_of = {fid: kind for kind, ids in kinds.items() for fid in ids}
    claims_of = defaultdict(lambda: ([], []))  # fact id: its claims in each revision
    for claim, s in side.items():
        for fid in bound[claim]:
            claims_of[fid][s].append(claim)
    between = defaultdict(set)   # fact id: relations found between its claims in the two revisions
    of_claim = defaultdict(set)  # claim id: relations found with any claim of the other revision
    classes = {"different": Counter(), "equivalent": Counter()}
    for finding in report["findings"]:
        a, b = (finding["a"], finding["b"]) if side[finding["a"]] == 0 else (finding["b"], finding["a"])
        relation = finding["relation"]
        of_claim[a].add(relation)
        of_claim[b].add(relation)
        fa, fb = bound[a], bound[b]
        common = fa.keys() & fb.keys()
        for fid in common:
            between[fid].add(relation)
        if relation in classes:
            classes[relation]["unscored" if not fa or not fb else "across facts" if not common
                              else "misreading" if any(fa[f] in READ_WRONG or fb[f] in READ_WRONG for f in common)
                              else "change" if any(kind_of.get(f) == "changed" for f in common) else "no change"] += 1
    unmatched = {u["id"] for u in report["unmatched"]}
    detail = {}
    for kind, (different, equivalent) in (("changed", ("reported", "called equivalent")),
                                          ("unchanged", ("false change", "confirmed"))):
        for fid in kinds[kind]:
            found = between[fid]
            detail[fid] = ("unextracted" if not all(claims_of[fid]) else different if "different" in found
                           else equivalent if "equivalent" in found else "uncertain" if "uncertain" in found
                           else "other" if found else "unpaired")
    for kind, s in (("added", 1), ("removed", 0)):
        for fid in kinds[kind]:
            mine = claims_of[fid][s]
            found = set().union(*(of_claim[c] for c in mine))
            detail[fid] = ("unextracted" if not mine else "called equivalent" if "equivalent" in found
                           else "as a change" if "different" in found
                           else "reported" if any(c in unmatched for c in mine) else "other")
    count = lambda kind, status: sum(1 for f in kinds[kind] if detail[f] == status)
    differences = sum(classes["different"].values())
    return {"facts": {k: len(v) for k, v in kinds.items()},
            "changes_found": f"{count('changed', 'reported')}/{len(kinds['changed'])}",
            "additions_found": f"{count('added', 'reported')}/{len(kinds['added'])}",
            "removals_found": f"{count('removed', 'reported')}/{len(kinds['removed'])}",
            "unchanged_confirmed": f"{count('unchanged', 'confirmed')}/{len(kinds['unchanged'])}",
            "false_changes": count("unchanged", "false change"),
            "difference_precision": round(classes["different"]["change"] / differences, 4) if differences else None,
            **{kind: dict(sorted(Counter(detail[f] for f in kinds[kind]).items())) for kind in kinds},
            "different": dict(sorted(classes["different"].items())),
            "equivalent": dict(sorted(classes["equivalent"].items())),
            "findings": dict(sorted(Counter(f["relation"] for f in report["findings"]).items())),
            "unmatched": len(report["unmatched"]),
            "pairs": report["retrieval"]["attempted_pairs"], "omitted": report["retrieval"]["omitted_by_pair_limit"],
            "detail": dict(sorted(detail.items()))}
