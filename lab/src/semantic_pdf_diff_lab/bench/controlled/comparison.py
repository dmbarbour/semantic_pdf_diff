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
Holders' yes-or-no views, keyed apart (a poll's), are scored by names (views.py).

A revision's key logs its edits from its base (revisions.py), read in the direction of the comparison:
- **renamed facts** (P-101B now P-201B, values kept) are the same facts, scored as unchanged or changed
- **a conditions change with the value kept** is classed apart: settled (the comparison saw no change: missed),
  else the relations the judge gave
- **a context change with value and conditions kept** (a note or lead-in restated: the counterfactual pairs) is
  classed apart: reported when a record change the report lists (`record_changes`, the record_changes lever) reaches
  one of its claims; else as a conditions change
- **a split** (one item become two) is reported as its removed and added facts, how the report's groupings viewed
  it (a split candidate, or apart), and whether the old item's claims were compared with the new items' at all

**Gaps another revision fills** (single-document analysis, milestone 7; indexes.given_elsewhere): an added or
removed fact of an item the revision lacking it still gives OTHER_CLAIMS facts or more of is a planted gap there. The
report's index (as the run wrote it) is read for its gaps of that kind: right (its claims bound to a planted
gap, on the side lacking it), both give it (a fact both revisions give: the reader's miss, or a property named two
ways), another fact, or unbound; with what each look found, where the look_gaps lever ran.

**Matching** (docs/plans/tentative-matches-2026-11-07.md, milestone 1): the report's index's subjects matched across
the revisions (as the run wrote them), each scored by the keys' items its claims are bound to: right where each
side's most bound item is the same, wrong where it isn't, unscorable where a side's claims are bound to none; and of
the items both revisions' claims give (OTHER_CLAIMS bound claims or more on each side), how many a right match holds.
Its links (links.py: subjects possibly one, kept apart; milestone 2) are scored alike, by level. And ranked
(evidence combined numerically, milestone 2): every firm group and every candidate pair of subjects left alone
(links.candidates), labelled by the keys as above (the unscorable left out), scored by its probability where the
report gives one, else by today's level (a firm group 3, a plausible link 2, a possible one 1, a candidate not linked
0: the null arm a combiner has to beat): the ranking's average precision, the precision of the pairs at plausible or
above and at possible or above, and where probabilities are given their log loss and calibration.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .corpus import BANKS
from .score import classify, key_facts, ranges
from .views import score_compared, score_echoes_compared

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
    removed, unchanged; and context (value and conditions kept, the note or lead-in declaring its context restated)
    and holder (value and conditions kept, the proposition credited to another: milestone 5), and hedge (value,
    conditions and holder kept, the hedge added or taken away), in pairs that have them."""
    renames, _ = edits(earlier, later)
    facts = lambda key, rename: {rename.get(f["id"], f["id"]): f for f in key["facts"]
                                 if f["role"] == "fact" and not f.get("relation")}
    a, b = facts(earlier, {}), facts(later, renames)
    both = a.keys() & b.keys()
    same = lambda x, y: " ".join(x.casefold().split()) == " ".join(y.casefold().split())
    value = lambda f: (f["value"], f.get("unit", ""))  # a unit restated, the number kept, is a changed value
    converted = {i for i in both if value(a[i]) != value(b[i]) and same(a[i].get("conditions", ""),
                                                                        b[i].get("conditions", ""))
                 and _converted(a[i], b[i])}
    kept = {i for i in both if value(a[i]) == value(b[i])
            and same(a[i].get("conditions", ""), b[i].get("conditions", ""))}
    declared = lambda f: (f.get("context") or {}).get("declared", "")
    holder = lambda f: f.get("holder", "")
    credited = {i for i in kept if not same(holder(a[i]), holder(b[i]))}  # the same proposition, another's
    kept -= credited
    hedged = {i for i in kept if not same(a[i].get("strength", ""), b[i].get("strength", ""))}  # firmer or weaker
    kept -= hedged
    restated = {i for i in kept if not same(declared(a[i]), declared(b[i]))}
    return {"changed": sorted(i for i in both if value(a[i]) != value(b[i]) and i not in converted),
            "conditions": sorted(i for i in both if value(a[i]) == value(b[i])
                                 and not same(a[i].get("conditions", ""), b[i].get("conditions", ""))),
            "added": sorted(b.keys() - a.keys()), "removed": sorted(a.keys() - b.keys()),
            "unchanged": sorted(kept - restated),
            **({"context": sorted(restated)} if restated else {}),
            **({"holder": sorted(credited)} if credited else {}),
            **({"hedge": sorted(hedged)} if hedged else {}),
            **({"converted": sorted(converted)} if converted else {})}

CONVERTED = 0.005  # a quantity restated in another unit of its kind: within this share, the conversion's rounding

def _converted(a, b):
    """Whether two facts' values are one quantity in two units of one kind (values.unit_kind): a converted value, no
    change (tentative matches, milestone 15)."""
    from semantic_pdf_diff.values import parse_number, unit_kind
    ka, kb = unit_kind(a.get("unit", "")), unit_kind(b.get("unit", ""))
    x, y = parse_number(str(a["value"])), parse_number(str(b["value"]))
    if not ka or not kb or ka[0] != kb[0] or a.get("unit") == b.get("unit") or x is None or y is None:
        return False
    x, y = x * ka[1], y * kb[1]
    return abs(x - y) <= CONVERTED * max(abs(x), abs(y))

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
    """A comparison report (report.json's data) scored against the two revisions' keys (see the module's note): the
    claims bound to their facts, the findings read, each fact's outcome, the splits, the explanations' kinds."""
    side, keys = sides(report), (earlier, later)
    renames, splits = edits(earlier, later)
    bound = _bound(report, side, keys, renames)
    kinds = changes(earlier, later)
    claims_of = defaultdict(lambda: ([], []))  # fact id: its claims in each revision
    for claim, s in side.items():
        for fid in bound[claim]:
            claims_of[fid][s].append(claim)
    read = _findings_read(report, side, bound, kinds, splits)
    detail = _outcomes(report, kinds, claims_of, read)
    count = lambda kind, status: sum(1 for f in kinds[kind] if detail[f] == status)
    classes = read.classes
    differences = sum(classes["different"].values())
    split_detail = [_split(report, old, new, claims_of, read.of_claim) for old, new in splits]
    return {"facts": {k: len(v) for k, v in kinds.items()},
            "changes_found": f"{count('changed', 'reported')}/{len(kinds['changed'])}",
            "additions_found": f"{count('added', 'reported')}/{len(kinds['added'])}",
            "removals_found": f"{count('removed', 'reported')}/{len(kinds['removed'])}",
            "unchanged_confirmed": f"{count('unchanged', 'confirmed')}/{len(kinds['unchanged'])}",
            "false_changes": count("unchanged", "false change"),
            **({"converted_confirmed": f"{count('converted', 'confirmed')}/{len(kinds['converted'])}",
                "converted_false_changes": count("converted", "false change")} if "converted" in kinds else {}),
            **({"context_found": f"{count('context', 'reported')}/{len(kinds['context'])}"}
               if "context" in kinds else {}),
            **({"holders_noticed": f"{len(kinds['holder']) - count('holder', 'settled')}/{len(kinds['holder'])}"}
               if "holder" in kinds else {}),
            **({"hedges_reported": f"{sum(1 for f in kinds['hedge'] if 'different' in detail[f])}/"
                                   f"{len(kinds['hedge'])}"} if "hedge" in kinds else {}),
            **({"record_changes": len(report["record_changes"])} if report.get("record_changes") else {}),
            "difference_precision": round(classes["different"]["change"] / differences, 4) if differences else None,
            **{kind: dict(sorted(Counter(detail[f] for f in kinds[kind]).items())) for kind in kinds},
            "different": dict(sorted(classes["different"].items())),
            "equivalent": dict(sorted(classes["equivalent"].items())),
            "findings": dict(sorted(Counter(f["relation"] for f in report["findings"]).items())),
            "unmatched": len(report["unmatched"]),
            "pairs": report["retrieval"]["attempted_pairs"], "omitted": report["retrieval"]["omitted_by_pair_limit"],
            **({"splits": split_detail} if splits else {}),
            **({"views": score_compared(earlier, later, report, side)} if earlier.get("views") else {}),
            **({"echoes": score_echoes_compared(earlier, later, report, side)} if earlier.get("echoes") else {}),
            **({"kinds": _explained(read.kinds_found)} if read.kinds_found else {}),
            **_gaps(report, side, keys, renames, kinds, bound),
            **_matching(report, side, keys, renames, bound, splits),
            "detail": dict(sorted(detail.items()))}

def _items(facts):
    """A fact's item as the earlier names it (fact ids: the two sides' facts, the later's renamed to the earlier's
    ids): a fact of both sides by the earlier's name; one of the later alone by the earlier's name for its item, where
    their facts in common say it (another design's "Flash mixer" is "Rapid mix basin"), else its own."""
    fold = lambda name: " ".join(name.casefold().split())  # noqa: E731
    named = {}
    for fid, f in facts[1].items():
        if fid in facts[0]:
            named.setdefault(fold(f["entity"]), fold(facts[0][fid]["entity"]))
    return lambda fid: (fold(facts[0][fid]["entity"]) if fid in facts[0]
                        else named.get(fold(facts[1][fid]["entity"]), fold(facts[1][fid]["entity"])))

def score_proposals(a, b, report):
    """A proposals comparison scored by role (proposals.py; docs/plans/tentative-matches-2026-11-07.md, milestone 5):
    the index's matches and the gaps another source fills, a fact's role its id (the two designs' facts of one role
    share it, as a renamed revision's are mapped to the earlier's), the findings' relations counted."""
    side, keys = sides(report), (a, b)
    bound = _bound(report, side, keys, {})
    kinds = changes(a, b)
    return {"facts": {k: len(v) for k, v in kinds.items()},
            **_matching(report, side, keys, {}, bound, banks=BANKS),
            **_gaps(report, side, keys, {}, kinds, bound),
            "findings": dict(sorted(Counter(f["relation"] for f in report["findings"]).items())),
            "unmatched": len(report["unmatched"])}

def _read(facts, item, splits=(), banks=None):
    """How a match's two sides read against the keys (each side's items): "right" where they share an item, where an
    item became two (splits: the keys' (earlier fact ids, later ones)), or where both are units of one bank (banks:
    {name: its units' role ids' prefixes}, corpus.BANKS: between proposals any of one design's raw water pumps with
    any of the other's); "unscorable" where a side has none."""
    related = {(item(a), item(b)) for old, new in splits for a in old for b in new if a in facts[0] and b in facts[1]}
    bank = {item(fid): name for name, units in (banks or {}).items() for side in facts for fid in side
            if fid.split(".")[0] in units}

    def read(x, y):
        return ("unscorable" if not x or not y else
                "right" if x & y or any((i, j) in related or bank.get(i) and bank.get(i) == bank.get(j)
                                        for i in x for j in y)
                else "wrong")
    return read, bank

def _matching(report, side, keys, renames, bound, splits=(), banks=None):
    """The index's subjects matched across the revisions, scored by the keys' items (see the module's note):
    {"matching": {"groups", "right", "wrong", "unscorable", "items", "matched", "links"}}, or nothing without an
    index. splits: the keys' (earlier fact ids, later ones), an item become two: a link between them is right; banks
    (proposals): units of one service, any of one side's with any of the other's right (_read)."""
    from semantic_pdf_diff import indexes
    subjects = (report.get("index") or {}).get("subjects")
    if not subjects:
        return {}
    facts = [{(renames.get(f["id"], f["id"]) if k else f["id"]): f for f in key["facts"]
              if f["role"] == "fact" and not f.get("relation")} for k, key in enumerate(keys)]
    item = _items(facts)
    items = [Counter(), Counter()]  # each side's bound claims by item
    for claim, fids in bound.items():
        for fid in fids:
            if fid in facts[0] or fid in facts[1]:
                items[side[claim]][item(fid)] += 1
    names = [x["name"] for x in report["sources"]]
    counts, matched, linked = Counter(), set(), defaultdict(Counter)

    def most(claims):  # the items a side's claims are most bound to
        found = Counter(item(fid) for c in claims for fid in bound.get(c, {}) if fid in facts[0] or fid in facts[1])
        top = max(found.values(), default=0)
        return {i for i, n in found.items() if n == top} if top else set()

    read, bank = _read(facts, item, splits, banks)
    by_name = {(next(iter(s["claims"])), s["name"]): s for s in subjects if len(s["claims"]) == 1}
    for s in subjects:
        for link in s.get("links", []):
            other = by_name.get((link["source"], link["other"]))
            if other is not None and names.index(next(iter(s["claims"]))) == 0:  # each pair once
                linked[link["level"]]["links"] += 1
                linked[link["level"]][read(most(next(iter(s["claims"].values()))),
                                          most(next(iter(other["claims"].values()))))] += 1
        if len(s["claims"]) < 2:
            continue
        counts["groups"] += 1
        sides = [most(s["claims"].get(name, [])) for name in names]
        counts[read(*sides)] += 1
        if sides[0] & sides[1]:
            matched |= sides[0] & sides[1]
        elif read(*sides) == "right":  # units of one bank: each side's matched
            matched |= {i for i in sides[0] | sides[1] if bank.get(i)}
    both = {i for i in items[0] if items[0][i] >= indexes.OTHER_CLAIMS and items[1][i] >= indexes.OTHER_CLAIMS}
    banks = Counter()  # banks linked as sets (links.sets): each side's members' items
    for x in (report.get("index") or {}).get("sets", []):
        sides_ = [set().union(*(most(subjects[i]["claims"].get(name, [])) for i in x["sources"][name]["subjects"]))
                  if name in x["sources"] else set() for name in names]
        banks["links"] += 1
        banks[read(*sides_)] += 1
    return {"matching": {**{k: counts[k] for k in ("groups", "right", "wrong", "unscorable")}, "items": len(both),
                         "matched": len(both & matched),
                         **({"links": {level: dict(sorted(c.items())) for level, c in sorted(linked.items())}}
                            if linked else {}),
                         **({"sets": dict(sorted(banks.items()))} if banks else {}),
                         **_ranking(report, subjects, names, most, read)}}

LEVEL_SCORE = {"firm": 3, "plausible": 2, "possible": 1}  # the null arm: today's levels as a score

def _ranking(report, subjects, names, most, read):
    """{"ranking": {"pairs", "matches", "average_precision", "candidates": the same of the candidate pairs alone (the
    links' own ranking, firm groups apart), "precision": {"plausible": share right of the pairs at plausible or above,
    "possible": ...}, and where the report gives probabilities "log_loss", "calibration"}} (see the module's note), or
    nothing without a scorable pair."""
    from semantic_pdf_diff import links

    from semantic_pdf_diff_lab.eval import ranking as measures
    scored, probable = [], []
    for s in subjects:
        if len(s["claims"]) == 2:
            right = read(*(most(s["claims"].get(name, [])) for name in names))
            if right != "unscorable":
                p = s.get("probability")
                scored.append((p if p is not None else LEVEL_SCORE["firm"], right == "right"))
                if p is not None:
                    probable.append((p, right == "right"))
    linked = {}  # (subject's index, its other's): its link
    at = {(next(iter(s["claims"])), s["name"]): i for i, s in enumerate(subjects) if len(s["claims"]) == 1}
    for i, s in enumerate(subjects):
        for link in s.get("links", []):
            j = at.get((link["source"], link["other"]))
            if j is not None:
                linked[tuple(sorted((i, j)))] = link
    alone = []  # the candidate pairs' alone: the links' own ranking, firm groups apart
    combining = (report.get("settings") or {}).get("link_levels") == "combined" and report.get("mode") == "proposals"
    for c in links.candidates(report, report["index"]):
        right = read(most(next(iter(subjects[c["i"]]["claims"].values()))),
                     most(next(iter(subjects[c["j"]]["claims"].values()))))
        if right == "unscorable":
            continue
        link = linked.get((c["i"], c["j"]))
        # every candidate's probability where the combiner gives one, linked or not (the whole range calibrated)
        p = links.combined(c, report["mode"])[0] if combining else link.get("probability") if link else None
        scored.append((p if p is not None else LEVEL_SCORE.get(link["level"], 0) if link else 0, right == "right"))
        alone.append(scored[-1])
        if p is not None:
            probable.append((p, right == "right"))
    if not scored:
        return {}
    at = links.SHOWN if combining else LEVEL_SCORE  # a level's cut: the combiner's probability, else the level's code
    cut = lambda level: [label for s, label in scored if s >= at[level]]  # noqa: E731
    out = {"pairs": len(scored), "matches": sum(1 for _, label in scored if label),
           "average_precision": measures.average_precision(scored),
           "candidates": {"pairs": len(alone), "matches": sum(1 for _, label in alone if label),
                          "average_precision": measures.average_precision(alone)},
           "precision": {level: round(sum(cut(level)) / len(cut(level)), 4) if cut(level) else None
                         for level in ("plausible", "possible")}}
    if probable:
        out.update(log_loss=measures.log_loss(probable), calibration=measures.calibration(probable))
    return {"ranking": out}

def _gaps(report, side, keys, renames, kinds, bound):
    """The gaps another revision fills, scored (see the module's note): {"gaps_found": "found/planted", "gaps": {how
    each reported one reads}, "gap_looks": {what each look found}}, or nothing where there's neither."""
    from semantic_pdf_diff import indexes
    facts = [{(renames.get(f["id"], f["id"]) if k else f["id"]): f for f in key["facts"]
              if f["role"] == "fact" and not f.get("relation")} for k, key in enumerate(keys)]
    item = _items(facts)
    items = [Counter(item(fid) for fid in fs) for fs in facts]
    planted = {fid: lacking for kind, lacking in (("added", 0), ("removed", 1)) for fid in kinds[kind]
               if items[lacking][item(fid)] >= indexes.OTHER_CLAIMS}
    gaps = (report.get("index") or {}).get("gaps", [])
    found = [g for g in gaps if g["kind"] == "other_source"]
    linked = [g for g in gaps if g["kind"] == "if_one_item"]  # a plausible link's (the link_gaps setting's)
    if not planted and not found and not linked:
        return {}
    names = [s["name"] for s in report["sources"]]
    both = set(kinds["unchanged"]) | set(kinds["changed"]) | set(kinds["conditions"]) | set(kinds.get("converted", ()))
    right, read = set(), Counter()
    for g in found:
        fids = {fid for c in g["claims"] for fid in bound.get(c, {})}
        hit = {fid for fid in fids if planted.get(fid) == names.index(g["source"])}
        right |= hit
        read["right" if hit else "both give it" if fids & both else "another fact" if fids else "unbound"] += 1
    looks = Counter(g["look"] for g in found if g.get("look"))
    out = {"gaps_found": f"{len(right)}/{len(planted)}", "gaps": dict(sorted(read.items())),
           **({"gap_looks": dict(sorted(looks.items()))} if looks else {})}
    if linked:
        more, read_linked = set(), Counter()
        for g in linked:
            fids = {fid for c in g["claims"] for fid in bound.get(c, {})}
            hit = {fid for fid in fids if planted.get(fid) == names.index(g["source"])}
            more |= hit
            read_linked["right" if hit else "both give it" if fids & both else "another fact" if fids
                        else "unbound"] += 1
        out["if_one_item"] = {**dict(sorted(read_linked.items())), "found_beside": len(more - right)}
    return out

def _bound(report, side, keys, renames):
    """{claim id: {fact id: outcome}}: the facts each claim is bound to, the later revision's renamed to the
    earlier's ids."""
    facts = [[f for f in key_facts(k) if not f.relation] for k in keys]
    bound = {}
    for e in report["evidence"]:
        s = side[e["id"]]
        read = [classify(part, facts[s], keys[s]["printed"]) for part in ranges([e])]
        bound[e["id"]] = {(renames.get(fid, fid) if s else fid): outcome for outcome, fid in read
                          if outcome in BOUND + READ_WRONG}
    return bound

@dataclass
class _Read:
    """What the findings say: the relations found between each fact's claims (between) and each claim's with any of
    the other revision's (of_claim), the "different" and "equivalent" findings classed, the kinds explanations named
    by what their claims are."""
    between: defaultdict = field(default_factory=lambda: defaultdict(set))
    of_claim: defaultdict = field(default_factory=lambda: defaultdict(set))
    classes: dict = field(default_factory=lambda: {"different": Counter(), "equivalent": Counter()})
    kinds_found: defaultdict = field(default_factory=lambda: defaultdict(Counter))

def _findings_read(report, side, bound, kinds, splits):
    kind_of = {fid: kind for kind, ids in kinds.items() for fid in ids}
    split_pairs = {(x, y) for old, new in splits for x in old for y in new}
    out = _Read()
    for finding in report["findings"]:
        a, b = (finding["a"], finding["b"]) if side[finding["a"]] == 0 else (finding["b"], finding["a"])
        relation = finding["relation"]
        out.of_claim[a].add(relation)
        out.of_claim[b].add(relation)
        fa, fb = bound[a], bound[b]
        common = fa.keys() & fb.keys()
        for fid in common:
            out.between[fid].add(relation)
        what = ("unscored" if not fa or not fb else "across facts" if not common
                else "misreading" if any(fa[f] in READ_WRONG or fb[f] in READ_WRONG for f in common)
                else "change" if any(kind_of.get(f) in ("changed", "conditions", "context", "holder", "hedge")
                                     for f in common)
                else "no change")
        if relation in out.classes:
            out.classes[relation][what] += 1
        if "explanation" in finding:
            if what == "change" and not any(kind_of.get(f) == "changed" for f in common):
                what = "conditions"
            elif what == "across facts" and any((x, y) in split_pairs for x in fa for y in fb):
                what = "split"
            out.kinds_found[what][finding["explanation"]["kind"]] += 1
    return out

def _outcomes(report, kinds, claims_of, read):
    """{fact id: what the report says of it}, by the fact's kind of change (see the module's note)."""
    between, of_claim = read.between, read.of_claim
    unmatched = {u["id"] for u in report["unmatched"]}
    settled = {(f["a"], f["b"]) for f in report["findings"] if f.get("settled")}
    detail = {}
    for fid in kinds["conditions"] + kinds.get("holder", []) + kinds.get("hedge", []):  # the value kept: settled
        # means it saw no change
        a, b = claims_of[fid]
        pairs = {(x, y) for x in a for y in b}
        detail[fid] = ("unextracted" if not a or not b
                       else "settled" if pairs & settled and not between[fid] - {"equivalent"}
                       else "judged " + "/".join(sorted(between[fid])) if between[fid] else "unpaired")
    # value and conditions kept, the record giving their context restated: reported when a record change the report
    # lists reaches a claim of it; else what the comparison made of its claims, as for conditions
    reached = {c for change in report.get("record_changes", []) for c in change["claims"]}
    for fid in kinds.get("context", ()):
        a, b = claims_of[fid]
        pairs = {(x, y) for x in a for y in b}
        detail[fid] = ("unextracted" if not a or not b else "reported" if reached & set(a + b)
                       else "settled" if pairs & settled and not between[fid] - {"equivalent"}
                       else "judged " + "/".join(sorted(between[fid])) if between[fid] else "unpaired")
    for kind, (different, equivalent) in (("changed", ("reported", "called equivalent")),
                                          ("unchanged", ("false change", "confirmed")),
                                          ("converted", ("false change", "confirmed"))):
        for fid in kinds.get(kind, ()):
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
    return detail

def _split(report, old, new, claims_of, of_claim):
    """A split: whether the old item was compared with its parts at all, and how the groupings viewed it."""
    olds = {c for f in old for c in claims_of[f][0]}
    news = {c for f in new for c in claims_of[f][1]}
    relations = sorted({r for c in olds for r in of_claim[c]} if olds else set())
    found = sorted({f["relation"] for f in report["findings"]
                    if (f["a"] in olds and f["b"] in news) or (f["b"] in olds and f["a"] in news)})
    viewed = [g["kind"] for g in report.get("groupings", [])
              if olds & set(g["earlier_claims"]) and news & set(g["later_claims"])]
    return {"from": old, "to": new, "viewed_as": sorted(set(viewed)), "compared": found,
            "old_claims": len(olds), "new_claims": len(news), "old_claims_relations": relations}

def _explained(kinds_found):
    """The explanations' kinds scored against what their claims are (EXPECTED), and the value changes' precision."""
    scored = {w: k for w, k in kinds_found.items() if w != "unscored"}
    named_changes = sum(n for k in scored.values() for kind, n in k.items() if kind in VALUE_CHANGES)
    return {"right": sum(n for w, k in scored.items() for kind, n in k.items() if kind in EXPECTED[w]),
            "scored": sum(sum(k.values()) for k in scored.values()),
            "value_change_precision": round(sum(n for w in ("change", "conditions") for kind, n in
                                                kinds_found.get(w, {}).items() if kind in VALUE_CHANGES)
                                            / named_changes, 4)
            if named_changes else None,
            "by_claims": {w: dict(sorted(k.items())) for w, k in sorted(kinds_found.items())}}
