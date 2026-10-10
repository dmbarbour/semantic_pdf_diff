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

**Kinds** (explain.py, revisions mode): an explained finding's kind is scored against what its claims are, per
the keys (EXPECTED): a changed value "changed", a conditions change "conditions", the same fact unchanged an
editorial kind (renamed, moved, restated), two facts' claims "not_same_item" (or "split_or_merge", the old item's and
a new one's of a split), a misreading "misread". The kinds named as value changes are also checked: of the
explanations saying "changed" or "conditions", the share whose claims are a change.

Relations (a door's room) aren't compared yet: they're left out of the changes.

A revision's key logs its edits from its base (revisions.py), read in the direction of the comparison:
- **renamed facts** (P-101B now P-201B, values kept) are the same facts, scored as unchanged or changed
- **a conditions change with the value kept** is classed apart: settled (the comparison saw no change: missed),
  else the relations the judge gave
- **a split** (one item become two) is reported as its removed and added facts, how the report's groupings viewed
  it (a split candidate, or apart), and whether the old item's claims were compared with the new items' at all
"""
from collections import Counter, defaultdict

from .score import classify, key_facts, ranges

BOUND = ("right", "loose")              # a claim of its fact, read right
READ_WRONG = ("wrong unit", "inexact")  # a claim of its fact, read wrong
# The kinds an explanation may rightly name, by what the keys say its finding's claims are.
EXPECTED = {"change": {"changed"}, "conditions": {"conditions"}, "no change": {"renamed", "moved", "restated"},
            "across facts": {"not_same_item"}, "split": {"split_or_merge"}, "misreading": {"misread"}}
VALUE_CHANGES = ("changed", "conditions")

def edits(earlier, later):
    """The edits between two revisions, from whichever key logs them, read from the earlier to the later:
    (renames {later id: earlier id}, splits [(earlier ids, later ids)])."""
    renames, splits = {}, []
    for key, other, forward in ((later, earlier, True), (earlier, later, False)):
        if key.get("revision_of") != other["project"]:
            continue
        for e in key.get("edits", []):
            if e["kind"] == "renamed":
                renames.update({new: old for old, new in e["facts"].items()} if forward else e["facts"])
            elif e["kind"] == "split":
                splits.append((e["from"], e["to"]) if forward else (e["to"], e["from"]))
    return renames, splits

def changes(earlier, later):
    """The facts' changes between two revisions' keys, by fact id (distractors and relations aside; renamed facts
    under their earlier ids): changed (the value), conditions (the value kept, its conditions changed), added,
    removed, unchanged."""
    renames, _ = edits(earlier, later)
    facts = lambda key, rename: {rename.get(f["id"], f["id"]): f for f in key["facts"]
                                 if f["role"] == "fact" and not f.get("relation")}
    a, b = facts(earlier, {}), facts(later, renames)
    both = a.keys() & b.keys()
    same = lambda x, y: " ".join(x.casefold().split()) == " ".join(y.casefold().split())
    return {"changed": sorted(i for i in both if a[i]["value"] != b[i]["value"]),
            "conditions": sorted(i for i in both if a[i]["value"] == b[i]["value"]
                                 and not same(a[i].get("conditions", ""), b[i].get("conditions", ""))),
            "added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()),
            "unchanged": sorted(i for i in both if a[i]["value"] == b[i]["value"]
                                and same(a[i].get("conditions", ""), b[i].get("conditions", "")))}

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
    renames, splits = edits(earlier, later)
    facts = [[f for f in key_facts(k) if not f.relation] for k in keys]
    bound = {}  # claim id: {fact id: outcome}, the facts it's bound to (the later's renamed to the earlier's ids)
    for e in report["evidence"]:
        s = side[e["id"]]
        read = [classify(part, facts[s], keys[s]["printed"]) for part in ranges([e])]
        bound[e["id"]] = {(renames.get(fid, fid) if s else fid): outcome for outcome, fid in read
                          if outcome in BOUND + READ_WRONG}
    kinds = changes(earlier, later)
    kind_of = {fid: kind for kind, ids in kinds.items() for fid in ids}
    claims_of = defaultdict(lambda: ([], []))  # fact id: its claims in each revision
    for claim, s in side.items():
        for fid in bound[claim]:
            claims_of[fid][s].append(claim)
    between = defaultdict(set)   # fact id: relations found between its claims in the two revisions
    of_claim = defaultdict(set)  # claim id: relations found with any claim of the other revision
    classes = {"different": Counter(), "equivalent": Counter()}
    split_pairs = {(x, y) for old, new in splits for x in old for y in new}
    kinds_found = defaultdict(Counter)  # what the claims are: the kinds explanations named
    for finding in report["findings"]:
        a, b = (finding["a"], finding["b"]) if side[finding["a"]] == 0 else (finding["b"], finding["a"])
        relation = finding["relation"]
        of_claim[a].add(relation)
        of_claim[b].add(relation)
        fa, fb = bound[a], bound[b]
        common = fa.keys() & fb.keys()
        for fid in common:
            between[fid].add(relation)
        what = ("unscored" if not fa or not fb else "across facts" if not common
                else "misreading" if any(fa[f] in READ_WRONG or fb[f] in READ_WRONG for f in common)
                else "change" if any(kind_of.get(f) in ("changed", "conditions") for f in common)
                else "no change")
        if relation in classes:
            classes[relation][what] += 1
        if "explanation" in finding:
            if what == "change" and not any(kind_of.get(f) == "changed" for f in common):
                what = "conditions"
            elif what == "across facts" and any((x, y) in split_pairs for x in fa for y in fb):
                what = "split"
            kinds_found[what][finding["explanation"]["kind"]] += 1
    unmatched = {u["id"] for u in report["unmatched"]}
    settled = {(f["a"], f["b"]) for f in report["findings"] if f.get("settled")}
    detail = {}
    for fid in kinds["conditions"]:  # the value kept: settled means the comparison saw no change
        a, b = claims_of[fid]
        pairs = {(x, y) for x in a for y in b}
        detail[fid] = ("unextracted" if not a or not b else "settled" if pairs & settled and not between[fid] - {"equivalent"}
                       else "judged " + "/".join(sorted(between[fid])) if between[fid] else "unpaired")
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
    split_detail = []
    for old, new in splits:  # was the old item compared with its parts at all?
        olds = {c for f in old for c in claims_of[f][0]}
        news = {c for f in new for c in claims_of[f][1]}
        relations = sorted({r for c in olds for r in of_claim[c]} if olds else set())
        found = sorted({f["relation"] for f in report["findings"]
                        if (f["a"] in olds and f["b"] in news) or (f["b"] in olds and f["a"] in news)})
        viewed = [g["kind"] for g in report.get("groupings", [])
                  if olds & set(g["earlier_claims"]) and news & set(g["later_claims"])]
        split_detail.append({"from": old, "to": new, "viewed_as": sorted(set(viewed)), "compared": found,
                             "old_claims": len(olds), "new_claims": len(news), "old_claims_relations": relations})
    scored = {w: k for w, k in kinds_found.items() if w != "unscored"}
    named_changes = sum(n for k in scored.values() for kind, n in k.items() if kind in VALUE_CHANGES)
    explained = {"right": sum(n for w, k in scored.items() for kind, n in k.items() if kind in EXPECTED[w]),
                 "scored": sum(sum(k.values()) for k in scored.values()),
                 "value_change_precision": round(sum(n for w in ("change", "conditions") for kind, n in
                                                     kinds_found.get(w, {}).items() if kind in VALUE_CHANGES)
                                                 / named_changes, 4)
                 if named_changes else None,
                 "by_claims": {w: dict(sorted(k.items())) for w, k in sorted(kinds_found.items())}}
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
            **({"splits": split_detail} if splits else {}),
            **({"kinds": explained} if kinds_found else {}),
            "detail": dict(sorted(detail.items()))}
