"""Scoring extraction against a controlled document's key: each claim classed (right, loose, misbound, wrong unit,
misread, hallucinated, ...), facts found and missed, conditions kept, relations read. Split from controlled.py
(architecture clean-up, milestone 8).
"""
import re
import unicodedata

from semantic_pdf_diff.values import DATE, parse_number, printed_value, same_number, unit_kind

from .corpus import Fact

# --- scoring -----------------------------------------------------------------------------------

# Not "a": single letters name things (Option A, Module B, detail B4).
STOP = {"the", "an", "of", "for", "per", "each", "at", "in", "on", "to", "and", "with", "is", "value", "by", "its"}
# Words a reader may fairly use for one another (domain-neutral; a project's own synonyms are in its facts).
SAME = {"weight": "mass", "number": "count", "quantity": "count", "qty": "count", "velocity": "speed",
        "seating": "seat", "rider": "seat", "tonnage": "ton", "max": "maximum", "min": "minimum", "avg": "average",
        "dia": "diameter", "temp": "temperature", "rated": "rating"}

def tokens(text):
    """A name's words: case-folded, hyphens split, stop words dropped, plurals and synonyms folded."""
    text = unicodedata.normalize("NFKC", str(text)).casefold().replace("-", " ")
    out = set()
    for t in re.findall(r"[a-z0-9]+", text):
        if t in STOP:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.add(SAME.get(t, t))
    return out

def vocabulary(fact):
    """Every word naming a fact: its entity and aliases, attribute and synonyms, and conditions."""
    return set().union(*(tokens(o) for o in (fact.entity, fact.attribute, fact.conditions) + tuple(fact.aliases)
                         + tuple(fact.synonyms)))

FIT_WEIGHTS = {"attribute": 2.0, "entity": 1.0, "conditions": 0.25}  # conditions only break ties
# A reference to where a value was read isn't a name: "Figure 1" mustn't pick "Option 1".
REFERENCE = re.compile(r"\b(?:figure|fig\.?|table|section|page|sheet)\s*[-.]?\s*\d+[a-z]?\b", re.I)

def fit(claim, fact, weights):
    """How well a claim's names describe a fact: the rare-word-weighted share of its attribute's words, entity's
    words and conditions' words found among the fact's words (all of them, however the claim split its names),
    the attribute counting most and the conditions least (a model may put a table's section name there)."""
    vocab = vocabulary(fact)
    score = 0.0
    for part, weight in FIT_WEIGHTS.items():
        words = tokens(REFERENCE.sub(" ", str(claim.get(part, ""))))
        total = sum(weights.get(w, weights[None]) for w in words)
        if total:
            score += weight * sum(weights.get(w, weights[None]) for w in words & vocab) / total
    return score

def rarity(facts):
    """{word: weight}: log(1 + facts / facts using the word); None for words no fact uses."""
    import math
    counts = {}
    for f in facts:
        for w in vocabulary(f):
            counts[w] = counts.get(w, 0) + 1
    n = len(facts)
    return {**{w: math.log(1 + n / c) for w, c in counts.items()}, None: math.log(1 + n)}

def holds(fact, number):
    """Whether a value is the fact's: the same number, or within its tolerance (a bar read against an axis)."""
    return same_number(fact.number, number) or bool(fact.tolerance and abs(fact.number - number) <= fact.tolerance)

INEXACT_STEPS = 10  # how many tolerances off a reading bound to a bar may be and still count as that bar's, misread

UNIT_AFTER = re.compile(r"^\s*(?:about|approx\.?|approximately|~|≈|[-+±<>≤≥]=?)?\s*[-+±]?\$?\d[\d,]*(?:\.\d+)?\s*(.*?)\s*$")

def claimed_unit(claim):
    """A claim's unit: its own field, or what follows the number in its value ("63.3 mph")."""
    unit = str(claim.get("unit", "") or "").strip()
    if unit:
        return unit
    m = UNIT_AFTER.match(str(claim.get("value", "")))
    return m.group(1) if m else ""

def holds_as(fact, number, unit):
    """Whether a value with its unit is the fact's (holds), compared in the fact's unit when both units are known.
    None when the number is the fact's but the units are of two kinds or sizes: a wrong unit."""
    mine, theirs = unit_kind(unit), unit_kind(fact.unit)
    if mine is None or theirs is None or mine == theirs:
        return holds(fact, number)
    if mine[0] == theirs[0]:  # converted: within the rounding of a conversion
        converted = number * mine[1] / theirs[1]
        if holds(fact, converted) or abs(converted - fact.number) <= 0.005 * max(abs(fact.number), 1e-9):
            return True
    return None if holds(fact, number) else False

def classify(claim, facts, printed):
    """(outcome, fact id or None) for one claim.

    A printed value names one fact (values are unique in a document), so the question is the binding: which fact
    the claim's names describe best. Right: the value's own fact fits best, alone. Loose: it ties for best (a bare
    "pump" among three pumps), or no name fits at all. Misbound: another fact fits better (the value filed under
    another entity or attribute). Distractor: a superseded or otherwise wrong value, bound to its own fact.
    Wrong unit: right or loose but for its unit, of another kind or size than the fact's (UNIT_KINDS).
    Misread: a printed number that isn't a fact (a page or section number). Hallucinated: printed nowhere.
    Inexact: a bar's value read against the axis, outside its tolerance, the bar named alone. Text: a value
    without a number, not scored yet.

    Read against an axis, a claim naming one bar is judged against that bar (a height read wrong and another
    bar's height read look alike); otherwise several bars may hold a value, and the names choose among them."""
    number = parse_number(claim.get("value", ""))
    if number is None:
        return "text", None
    from .sheets import inches
    value, unit = str(claim.get("value", "")), str(claim.get("unit", "") or "")
    length = inches(value, unit)
    if length is None and unit.strip().startswith("'"):
        length = inches(value + unit)  # "26" with "'-6\"" as its unit
    date = DATE.match(value) and value.strip()
    said = claimed_unit(claim)
    typed = {}  # fact id: holds_as (None: the fact's number, in a unit of another kind or size)
    if date:  # a date: the same date
        holders = [f for f in facts if f.value.strip() == date]
    elif length is not None and any(f.unit == "ft-in" for f in facts):  # a length: lengths, in inches
        holders = [f for f in facts if f.unit == "ft-in" and abs(inches(f.value) - length) < 0.01]
    else:
        typed = {f.id: holds_as(f, number, said) for f in facts if f.unit != "ft-in" and not DATE.match(f.value)}
        typed = {i: v for i, v in typed.items() if v is not False}
        holders = [f for f in facts if f.id in typed]
    # the right fact's number in another unit ("63.3 m/s" for 63.3 mph): bound well, read wrong
    unit_checked = lambda outcome, fid: (("wrong unit" if outcome in ("right", "loose") and typed.get(fid, True) is None
                                          else outcome), fid)
    weights = rarity(facts) if holders or any(f.tolerance for f in facts) else None
    scores = {f.id: fit(claim, f, weights) for f in facts} if weights else {}
    if any(f.tolerance for f in facts):  # read against an axis: the names pick the bar, its height is checked
        best = max(scores.values())
        top = [f for f in facts if scores[f.id] == best]
        if best > 0 and len(top) == 1 and top[0].tolerance:
            bar = top[0]
            held = holds_as(bar, number, said)
            if held:
                return "right", bar.id
            if held is None:
                return "wrong unit", bar.id
            if abs(bar.number - number) <= INEXACT_STEPS * bar.tolerance:
                return "inexact", bar.id  # its height misjudged, or another bar's read: alike to the eye
    if holders:
        holder = max(holders, key=lambda f: scores[f.id])  # the first, of equals
        best = max(scores.values())
        top = [i for i, v in scores.items() if v == best]
        by_id = {f.id: f for f in facts}
        if holder.id in top and all((by_id[i].entity, by_id[i].attribute) == (holder.entity, holder.attribute)
                                    for i in top):
            top = [holder.id]  # facts named alike (a superseded value and its successor): the value decides
        if best == 0 or (holder.id in top and len(top) > 1):
            return unit_checked("loose", holder.id)
        if top == [holder.id]:
            return unit_checked("right" if holder.role == "fact" else "distractor", holder.id)
        said = tokens(claim.get("entity", ""))
        named = lambda f: any(tokens(n) and tokens(n) <= said for n in (f.entity,) + tuple(f.aliases))
        rivals = [by_id[i] for i in top]
        if named(holder) and all(f.entity != holder.entity and named(f) for f in rivals):
            return unit_checked("loose", holder.id)  # two things named, the value's own among them ("D104 MEETING 104")
        return "misbound", holder.id
    if date:
        return ("misread", None) if any(printed_value(p["text"]) == ("date", date) for p in printed) else ("hallucinated", None)
    if length is not None and any(f.unit == "ft-in" for f in facts):
        if any(printed_value(p["text"]) == ("in", length) for p in printed):
            return "misread", None
        return "hallucinated", None
    if any(same_number(parse_number(p["text"]), number) for p in printed):
        return "misread", None
    return "hallucinated", None

# A limit, however it's put: a requirement ("shall not exceed"), a negation ("not rated above"), a bound.
BOUNDS = {"maximum": ("maximum", "max", "not exceed", "not to exceed", "no more than", "at most", "up to", "limit",
                      "not rated above", "not rated for", "no higher", "or less", "upper"),
          "minimum": ("minimum", "min", "at least", "no less than", "not less than", "or more", "lower")}

SIGNS = {"maximum": ("<", "≤", "⩽"), "minimum": (">", "≥", "⩾")}

def bounds(text):
    """The bounds a text states ({"maximum"}, {"minimum"}, both or neither), in words or signs ("<= 39 psf")."""
    raw = str(text)
    text = " ".join(unicodedata.normalize("NFKC", raw).casefold().replace("-", " ").split())
    return {bound for bound, phrases in BOUNDS.items()
            if any(re.search(rf"\b{p}\b", text) for p in phrases) or any(sign in raw for sign in SIGNS[bound])}

NUMBER = r"[-+]?\d[\d,]*(?:\.\d+)?"
RANGE = re.compile(rf"^\s*({NUMBER})\s*(?:[^\d\s'\"]{{0,4}}\s+)?(?:to|–|—|and|-)\s*({NUMBER})(?!\s*/)\s*(\D*)$")

def ranges(claims):
    """Claims as scored: one whose value is a range ("66 to 75 °F") stands for its two bounds, a minimum and a
    maximum, each a claim of its own (feet and inches, "2'-9 1/2\"", aren't ranges)."""
    for c in claims:
        m = RANGE.match(str(c.get("value", "")))
        low, high = (parse_number(m.group(1)), parse_number(m.group(2))) if m else (None, None)
        if low is None or high is None or not low < high:
            yield c
            continue
        for bound, value in (("minimum", m.group(1)), ("maximum", m.group(2))):
            yield {**c, "value": f"{value} {m.group(3).strip()}".strip(),
                   "attribute": f"{bound} {c.get('attribute', '')}".strip()}

def distinctive(fact, facts):
    """The words of a fact's conditions that tell it from its neighbours: not in the conditions of other facts
    about the same entity, nor in its own name and attribute; failing that, not in the neighbours' conditions; failing that,
    all of them. A condition is kept when a claim says one (code review 2026-10-01, item 10: "maximum day" kept
    "average day" by the word "day", and a claim naming "Filters" kept "with one filter out of service")."""
    words = tokens(fact.conditions)
    neighbours = set().union(*(tokens(f.conditions) for f in facts if f.entity == fact.entity and f.id != fact.id))
    # its own name and attribute, not the entity's aliases: an alias may carry a scope ("four halls")
    names = set().union(*(tokens(n) for n in (fact.entity, fact.attribute) + tuple(fact.synonyms)))
    return (words - neighbours - names) or (words - neighbours) or words

NUMERIC_VALUE = re.compile(r"^\s*(?:about|approx\.?|approximately|~|≈|[-+±<>≤≥$])?\s*[-+±]?\$?\d")

def score(key_data, claims):
    """Each claim classed, facts found and missed, and conditions kept, from a key and extracted claims (dicts
    with entity, attribute, value, unit, conditions)."""
    facts = [Fact(**{k: (tuple(v) if k in ("aliases", "synonyms") else v) for k, v in f.items()})
             for f in key_data["facts"]]
    by_id = {f.id: f for f in facts}
    numeric = [f for f in facts if not f.relation]
    related = [f for f in key_data["facts"] if f.get("relation")]
    outcomes, found, conditions, relation_outcomes = {}, {}, {}, {}
    if related:  # relations are scored by names (relations.py)
        from . import relations
        index = relations.Index(related)
        things = [relations.Thing(p["name"], tuple(p.get("aliases", ()))) for p in key_data.get("parts", [])]
        literal = {}
        for f in related:
            if relations.RELATIONS[f["relation"]].literal:
                literal.setdefault(f["value"], set()).update(f.get("object_aliases") or ())
        things += [relations.Thing(name, tuple(sorted(aliases)), True) for name, aliases in sorted(literal.items())]
    seen, seen_triples = {}, set()
    for c in ranges(claims):
        ident = (str(c.get("entity", "")).casefold(), str(c.get("attribute", "")).casefold(), str(c.get("value", "")))
        if related and not NUMERIC_VALUE.match(str(c.get("value", ""))):  # a relation: one outcome per triple
            if ident in seen:
                continue
            seen[ident] = None
            for outcome, fid, triple in relations.classify_claim(c, things, index):
                if triple is not None and triple in seen_triples:
                    continue  # read twice, by other readers or in other words
                seen_triples.add(triple)
                relation_outcomes[outcome] = relation_outcomes.get(outcome, 0) + 1
                if outcome == "right":
                    found[fid] = "right"
            continue
        # the same reading twice (overlapping tiles, other readers) counts once, but either may keep its conditions;
        # a value that repeats ("25 MWh" in June and in July) is two readings, told apart by the fact each names
        outcome, fid = classify(c, numeric, key_data["printed"])
        reading = (ident, fid or outcome, outcome == "wrong unit")  # "63.3 mph" and "63.3 m/s" are two readings
        if reading not in seen:
            seen[reading] = True
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        if outcome in ("right", "loose") and fid:
            found.setdefault(fid, outcome)
            if outcome == "right":
                found[fid] = "right"
            want = distinctive(by_id[fid], facts)
            if want and fid not in conditions or conditions.get(fid) is False:
                text = " ".join(str(c.get(k, "")) for k in ("conditions", "entity", "attribute", "value"))
                conditions[fid] = bool(want & (tokens(text) | bounds(text)))
    real = [f for f in facts if f.role == "fact"]
    by_form = {}
    for f in real:
        for form in {x["form"] for x in f.forms}:
            got = by_form.setdefault(form, [0, 0])
            got[0] += f.id in found
            got[1] += 1
    return {"facts": len(real), "found": sum(1 for f in real if f.id in found),
            "recall": round(sum(1 for f in real if f.id in found) / len(real), 4),
            "found_right": sum(1 for v in found.values() if v == "right"),
            "missed": sorted(f.id for f in real if f.id not in found),
            "claims": sum(outcomes.values()), "outcomes": dict(sorted(outcomes.items())),
            "conditions_kept": f"{sum(conditions.values())}/{len(conditions)}",
            "recall_by_form": {k: round(v[0] / v[1], 4) for k, v in sorted(by_form.items())},
            **({"relations": dict(sorted(relation_outcomes.items())),
                "recall_by_kind": {kind: round(sum(1 for f in mine if f.id in found) / len(mine), 4) if mine else None
                                   for kind, mine in (("number", [f for f in real if not f.relation]),
                                                      ("relation", [f for f in real if f.relation]))}}
               if related else {})}
