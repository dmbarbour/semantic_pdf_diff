"""Holders' yes-or-no views, scored by names (the claim context plan, milestone 5: the view_attitudes lever).

A view is keyed apart from the facts (corpus.proposals_polled: Project.views): a holder, a proposition, a yes or a
no ("Avelin | Proposal 2.1 | Y", Avelin supports it). Its value names no fact: a poll's every "Y" prints alike, so a
claim is bound by the names it gives, wherever it gives them: the holder in its stance, entity, attribute or
conditions ("Avelin | support for Proposal 2.1 | Y" and "Proposal 2.1 | support | Y" held by Avelin alike), the
proposition anywhere ("Proposal 2.1"), the yes or no in its value. Each reading is classed:
- right: a keyed holder's view of a keyed proposition, its yes or no as keyed
- flipped: the holder's view of the proposition, read the other way round
- misbound: a holder and a proposition named, but no such view keyed (another company's row, another table's)
- no holder, no proposition: a yes or a no whose holder or proposition the claim doesn't name

Of the views found right, how many hold their holder in the claim's stance (not only in its entity or conditions),
and with the keyed attitude (supports, opposes).

Echoes (corpus.proposals_echoed: Project.echoes): the document's own proposals (a moderator's) in a holder's words
and value, keyed apart since the value names the holder's fact too; a claim reads one when it names its label
("Proposal 3.1", in its quote or words) and gives its value.

On a revision pair, each claim of a view (right or flipped) is bound to it, and each claim of an echo to it, and
each classed by what the report's findings say of its claims, as comparison.py classes facts: a view turned round
(an echo's value changed) reported (a "different" finding), called equivalent, uncertain, other, unpaired,
unextracted; one kept confirmed (equivalent), a false change (different), and so on.
"""
import re
from collections import Counter, defaultdict

YES = {"y", "yes", "support", "supports", "supported", "agree", "agrees", "agreed", "accept", "accepts",
       "accepted", "ok", "fine", "true"}
NO = {"n", "no", "oppose", "opposes", "opposed", "object", "objects", "objected", "disagree", "disagrees",
      "disagreed", "reject", "rejects", "rejected", "not supported", "does not support", "false"}
PROPOSITION = re.compile(r"\bproposal\s*(\d+(?:\.\d+)*[a-z]?)", re.IGNORECASE)
ATTITUDE = {"Y": "supports", "N": "opposes"}

def _fold(text):
    return " ".join(re.sub(r"[^\w\s]", " ", str(text or "")).casefold().split())

def said(value):
    """"Y" or "N" for a value saying yes or no ("Y", "Yes", "Supported", "N (prefers 400 ms)"), else None."""
    text = _fold(value)
    if text in YES or text in NO:
        return "Y" if text in YES else "N"
    first = text.split()[0] if text else ""
    return {"y": "Y", "yes": "Y", "n": "N", "no": "N"}.get(first)

def _named(claim, holders):
    """(holders, propositions) a claim names: holders from its stance and words, propositions from its words."""
    stance = [_fold(re.sub(r"\[[^\]]*\]", "", link.get("holder", ""))) for link in claim.get("stance") or ()]
    words = " ".join(str(claim.get(k, "") or "") for k in ("entity", "attribute", "conditions", "frame"))
    folded = f" {_fold(words)} "
    named = {h for h in holders if _fold(h) in stance or f" {_fold(h)} " in folded}
    props = {f"Proposal {m.group(1)}" for m in PROPOSITION.finditer(words + " " + str(claim.get("value", "")))}
    return named, props

def classify(claim, views):
    """(outcome, view id or None) for a claim saying yes or no; None for a claim that doesn't."""
    yes_no = said(claim.get("value", ""))
    if yes_no is None:
        return None
    keyed = {(v["holder"], v["proposition"]): v for v in views}
    holders, props = _named(claim, {v["holder"] for v in views})
    if not holders:
        return "no holder", None
    if not props:
        return "no proposition", None
    bound = [keyed[(h, p)] for h in sorted(holders) for p in sorted(props) if (h, p) in keyed]
    if not bound:
        return "misbound", None
    right = [v for v in bound if v["value"] == yes_no]
    return ("right", right[0]["id"]) if right else ("flipped", bound[0]["id"])

def _held(claim, view):
    """(the view's holder in the claim's stance, with the keyed attitude)."""
    links = [link for link in claim.get("stance") or ()
             if _fold(re.sub(r"\[[^\]]*\]", "", link.get("holder", ""))) == _fold(view["holder"])]
    return bool(links), any(link.get("attitude", "") == view["attitude"] for link in links)

def score_views(views, claims):
    """A key's views against extracted claims (dicts with entity, attribute, value, conditions, stance): each
    reading classed once, the views found, and how many of them hold their holder in a stance, with its attitude."""
    by_id = {v["id"]: v for v in views}
    outcomes, found, in_stance, attitude, seen = Counter(), set(), set(), set(), set()
    for c in claims:
        classed = classify(c, views)
        if classed is None:
            continue
        outcome, vid = classed
        reading = (_fold(c.get("entity")), _fold(c.get("attribute")), _fold(c.get("value")),
                   tuple(sorted(_fold(link.get("holder", "")) for link in c.get("stance") or ())), outcome)
        if reading not in seen:
            seen.add(reading)
            outcomes[outcome] += 1
        if outcome == "right":
            found.add(vid)
            held, right_attitude = _held(c, by_id[vid])
            if held:
                in_stance.add(vid)
            if right_attitude:
                attitude.add(vid)
    return {"views": len(views), "found": len(found), "missed": sorted(set(by_id) - found),
            "outcomes": dict(sorted(outcomes.items())), "holder_in_stance": len(in_stance),
            "attitude_in_stance": len(attitude)}

def _echo_of(claim, echoes):
    """The echo (the document's own proposal repeating a holder's value) a claim reads, by its label in the claim's
    quote or words and its value, or None."""
    from semantic_pdf_diff.values import parse_number
    said = " ".join(str(claim.get(k, "") or "") for k in ("quote", "entity", "attribute", "conditions"))
    number = parse_number(str(claim.get("value", "")))
    for e in echoes:
        if re.search(rf"(?<![\w.]){re.escape(e['proposition'])}(?![\w.]|\.\d)", said, re.I) \
                and number is not None and number == parse_number(e["value"]):
            return e["id"]
    return None

def score_echoes(echoes, claims):
    """The echoes a run's claims read (bound by label and value), of the key's."""
    found = {_echo_of(c, echoes) for c in claims} - {None}
    return {"echoes": len(echoes), "found": len(found), "missed": sorted({e["id"] for e in echoes} - found)}

def score_echoes_compared(earlier, later, report, side):
    """A revision pair's echoes against the report's findings, as score_compared classes views: an echo whose value
    changed reported (a "different" finding between its claims), called equivalent, ...; one kept confirmed."""
    keys = (earlier, later)
    echoes = [{e["id"]: e for e in k.get("echoes", [])} for k in keys]
    changed = sorted(i for i in echoes[0].keys() & echoes[1].keys() if echoes[0][i]["value"] != echoes[1][i]["value"])
    kept = sorted(i for i in echoes[0].keys() & echoes[1].keys() if i not in changed)
    bound = {e["id"]: _echo_of(e, list(echoes[side[e["id"]]].values())) for e in report["evidence"]}
    return _classed(report, side, bound, changed, kept)

def score_compared(earlier, later, report, side):
    """A revision pair's views (both keys' "views") against the report's findings (see the module's note); side:
    {claim id: 0 or 1}, as comparison.sides gives it."""
    keys = (earlier, later)
    views = [{v["id"]: v for v in k.get("views", [])} for k in keys]
    changed = sorted(i for i in views[0].keys() & views[1].keys() if views[0][i]["value"] != views[1][i]["value"])
    kept = sorted(i for i in views[0].keys() & views[1].keys() if i not in changed)
    bound = {}
    for e in report["evidence"]:
        classed = classify(e, list(views[side[e["id"]]].values()))
        bound[e["id"]] = classed[1] if classed and classed[0] in ("right", "flipped") else None
    return _classed(report, side, bound, changed, kept)

def _classed(report, side, bound, changed, kept):
    """Each keyed item (a view, an echo) classed by the findings between its claims ({claim id: item id or None})."""
    claims_of = defaultdict(lambda: ([], []))
    for claim, vid in bound.items():
        if vid:
            claims_of[vid][side[claim]].append(claim)
    between = defaultdict(set)
    for f in report["findings"]:
        if bound.get(f["a"]) and bound.get(f["a"]) == bound.get(f["b"]):
            between[bound[f["a"]]].add(f["relation"])
    detail = {}
    for ids, (different, equivalent) in ((changed, ("reported", "called equivalent")),
                                         (kept, ("false change", "confirmed"))):
        for vid in ids:
            found = between[vid]
            detail[vid] = ("unextracted" if not all(claims_of[vid]) else different if "different" in found
                           else equivalent if "equivalent" in found else "uncertain" if "uncertain" in found
                           else "other" if found else "unpaired")
    count = lambda ids, status: sum(1 for i in ids if detail[i] == status)  # noqa: E731
    return {"changes_found": f"{count(changed, 'reported')}/{len(changed)}",
            "unchanged_confirmed": f"{count(kept, 'confirmed')}/{len(kept)}",
            "false_changes": count(kept, "false change"), "detail": dict(sorted(detail.items()))}
