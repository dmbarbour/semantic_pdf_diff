"""Alignment for revisions mode (docs/plans/revision-comparison-2026-10-02.md; the research behind it is
docs/research/correspondence-without-a-model-2026-10-02.md): which items correspond across two revisions is decided
over the whole of both before any value is judged, from cheap signals, so the judge sees only what they leave open.

- **Items:** a revision's claims grouped by the thing they describe: a tag in the entity (P-101B, AHU-3, D103),
  else the entity's words. A claim named by position ("blower 5") joins the tagged item whose values it repeats,
  when one clearly does, so a shifted row number doesn't decide its identity.
- **Item correspondence:** shared values (a value with its unit; rare ones count more), the name (its identifiers
  must agree: "Room 104" isn't "Room 105"), and the attributes. Most of a revision is unchanged, so an item's
  values identify it best, whatever it's called; a changed value is outvoted by its item's unchanged ones.
- **Assignment:** best first, one counterpart each, and only with a margin over the next candidate. Near-ties
  are ambiguous and go to the judge (the plan's decision 10). Below a floor an item has no counterpart: it was
  added or removed, and its claims aren't compared.
- **Claims within an aligned item:** equal values under agreeing conditions are settled as equivalent, without a
  model; the rest are paired by attribute and conditions, best first, for the judge (a changed value among them).

- **Groupings, as alignment sees them** (decision 12): every group it formed, matched, renamed, attached, ambiguous,
  unaligned, and split or merge candidates (leftover items whose names share a stem, one on one side and two or
  more on the other, with whether their values add up), each with its evidence. The report shows them as they are:
  regroupings can be messy, and candidates are only candidates.

The weights and thresholds were set by inspection on the controlled revision pairs (decision 7: early development
by eye); calibrated confidences come later.
"""
from collections import Counter
import re
from collections import defaultdict
from dataclasses import dataclass, field

from .values import inches, printed_value, unit

TAG = re.compile(r"\b[A-Z]{1,4}-?\d{1,4}[A-Z]?\b")
# Not "a": single letters name things (Option A, Revision A, valve A).
STOP = {"the", "an", "of", "for", "per", "each", "at", "in", "on", "to", "and", "with", "is", "by", "its", "value",
        "no"}

VALUES, NAME, ATTRIBUTES = 0.6, 0.3, 0.1  # an item pair's score: the evidence's shares
FLOOR = 0.3       # below it, an item has no counterpart
MARGIN = 0.15     # a counterpart must lead the next candidate by this much
PAIRING = 0.5     # claims within an item: the attribute and conditions similarity to pair them
JOINING = 0.6     # a positional claim joins a tagged item holding this share of its item's values
WORDING = 0.5     # claims left without a partner: the share of their words in common to pair them

@dataclass
class Correspondence:
    """Which claims are compared: pairs for the judge [(i, j, score)], pairs settled as equivalent without one
    [(i, j, score)], the claims whose items have no counterpart (indices in each side), a summary for the report,
    and the groupings alignment formed ({kind, earlier, later (names), earlier_claims, later_claims (indices),
    score, evidence}). Claims in a split or merge candidate are in `regrouped` (indices in each side)."""
    judge: list
    settled: list = field(default_factory=list)
    unaligned: tuple = ((), ())
    summary: dict = field(default_factory=dict)
    groups: list = field(default_factory=list)
    regrouped: tuple = ((), ())

SAME = {"number": "count", "quantity": "count", "qty": "count", "no": "count"}  # "number of inversions", "inversion count"

def words(text):
    """A name's words: case-folded, stop words dropped, plurals and a few synonyms folded."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", str(text).casefold()):
        if w not in STOP:
            w = w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
            out.add(SAME.get(w, w))
    return frozenset(out)

def identifiers(name):
    """The words that tell one thing from another of its kind: numbers, tags, single letters."""
    return frozenset(w for w in name if len(w) == 1 or any(c.isdigit() for c in w))

def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0

# Words that name no property in particular: an attribute of only these (and identifiers) is unnamed.
GENERIC = {"dimension", "size", "measurement", "data", "figure", "amount", "parameter", "property", "spec",
           "specification", "item", "entry", "field", "column", "row", "line"}

def attribute(claim):
    """An attribute's words without its identifiers or generic words: "dimension 1" and "dimension 2" are positions
    a reader gave, which shift between revisions, so the values decide between them. Empty: unnamed."""
    w = words(claim.attribute)
    return w - identifiers(w) - GENERIC

def fits(x, y):
    """Two claims of one value name the same property: most words shared, one's words within the other's ("date" and
    "revision A date"), or either unnamed (the value decides). Not when both name identifiers and they differ:
    "95th percentile turbidity" isn't "99th percentile turbidity", though its value may be."""
    a, b = attribute(x), attribute(y)
    if not a or not b:
        return True
    ia, ib = identifiers(words(x.attribute)), identifiers(words(y.attribute))
    if ia and ib and ia != ib:
        return False
    return jaccard(a, b) >= 0.5 or a <= b or b <= a

# One number, perhaps signed or approximate, perhaps followed by a unit's word ("63.3 mph"): a range ("0..160",
# "66 to 75") or a list is a value in words.
NUMERIC = re.compile(r"^\s*(?:about|approx\.?|approximately|~|≈|[-+±<>≤≥]=?)?\s*[-+±]?\$?\d[\d,]*(?:\.\d+)?\s*[^\d\s.,]*\s*$")

def value_key(claim):
    """A value comparable across revisions: in its unit's base where the unit is known (1.2 MW is 1,200 kW), else
    with its unit as written; lengths in inches, dates as dates, a tag as itself ("D103"); a value in words as its
    words, case, spacing and punctuation folded (a specification's claims are mostly words: "MUST close the
    connection"). A number inside words ("ROOM 102 ENLARGED") is part of the words, not the value."""
    text = str(claim.value).strip()
    if TAG.fullmatch(text):
        return ("id", text)
    marks = qualifier(text)
    length = inches(text[PREFIX.match(text).end():], claim.unit or "")  # 33.5", 33.5 in, 2'-9½": all inches
    if length is not None:  # (code review 2026-10-08, D11: keyed as '"' and 'in' apart)
        return ("in", round(length, 9)) + ((marks,) if marks else ())
    v = printed_value(text)
    if isinstance(v, tuple):  # ("in", 33.5), ("date", "2026-01-10")
        return v
    if v is None or not NUMERIC.match(text):
        folded = " ".join(re.findall(r"[^\W_]+", text.casefold()))
        unit_words = " ".join(re.findall(r"[^\W_]+", str(claim.unit or "").casefold()))
        return ("text", f"{folded} {unit_words}".strip()) if folded else None
    said = (claim.unit or "").strip() or re.sub(r"^[^\d]*[\d,.]+\s*", "", text)  # "63.3 mph": the unit in the value
    known = unit(said)
    key = (known[0], round(v * float(known[1]), 9)) if known else (re.sub(r"\s", "", said).casefold(), round(v, 9))
    return key + (marks,) if marks else key

# What a number's prefix says beyond the number: a bound, a tolerance, a currency. "≤ 5" isn't "≥ 5", "±0.5" isn't
# 0.5, "$5" isn't 5 (code review 2026-10-08, D1: they settled as equivalent without a model). "About" and "~" stay
# folded: an approximation restated exactly is the same value.
PREFIX = re.compile(r"^\s*(?:about|approx\.?|approximately|~|≈)?\s*([<>≤≥]=?)?\s*(±)?\s*[-+]?\s*(\$)?")
BOUNDS = {"<=": "≤", ">=": "≥"}

def qualifier(text):
    """The marks of a number's prefix that change its meaning, normalised ("<=" is "≤"); "" for none."""
    bound, tolerance, money = PREFIX.match(text).groups()
    return BOUNDS.get(bound, bound or "") + ("±" if tolerance else "") + ("$" if money else "")

class Side:
    """One revision's items: {key: [claim indices]}, each item's values, attributes and name words."""
    def __init__(self, claims):
        self.claims = claims
        self.values = [value_key(c) for c in claims]
        items = defaultdict(list)
        for i, c in enumerate(claims):
            tags = TAG.findall(c.entity)
            items[tags[0] if tags else " ".join(sorted(words(c.entity))) or "(unnamed)"].append(i)
        self.items = dict(items)
        self._join_positional()
        self.item_values = {k: {self.values[i] for i in idx} - {None} for k, idx in self.items.items()}
        self.item_attributes = {k: frozenset().union(*(attribute(claims[i]) for i in idx))
                                for k, idx in self.items.items()}
        self.names = {k: words(k) for k in self.items}
        self.holders = defaultdict(int)  # value: how many items hold it
        for vals in self.item_values.values():
            for v in vals:
                self.holders[v] += 1

    def display(self, key):
        """An item's name as its claims most often give it."""
        return Counter(self.claims[i].entity for i in self.items[key]).most_common(1)[0][0]

    def numbers(self, key):
        """An item's numeric values by claim: [(claim index, unit kind, number)]."""
        out = []
        for i in self.items[key]:
            v = self.values[i]
            if v is not None and v[0] not in ("date", "id") and isinstance(v[1], (int, float)):
                out.append((i, v[0], v[1]))
        return out

    def _join_positional(self):
        """An untagged item whose values are mostly one tagged item's, and clearly that one's, joins it: the image
        reader's "blower 5" is B-402 when it repeats B-402's values."""
        tagged = {k for k in self.items if TAG.fullmatch(k)}
        vals = {k: {self.values[i] for i in idx} - {None} for k, idx in self.items.items()}
        for k in sorted(set(self.items) - tagged):
            if len(vals[k]) < 2:
                continue
            shares = sorted(((len(vals[k] & vals[t]) / len(vals[k]), t) for t in tagged), reverse=True)
            if shares and shares[0][0] >= JOINING and (len(shares) == 1 or shares[0][0] - shares[1][0] >= MARGIN):
                self.items[shares[0][1]] += self.items.pop(k)

def _name(a, b, ka, kb):
    if ka == kb:
        return 1.0
    na, nb = a.names[ka], b.names[kb]
    ia, ib = identifiers(na), identifiers(nb)
    if ia and ib and ia != ib:  # two of a kind: Option 1 and Option 2, Revision C and Revision D
        return 0.0
    return jaccard(na, nb)

def _score(a, b, ka, kb):
    va, vb = a.item_values[ka], b.item_values[kb]
    size = len(va) + len(vb)
    shared = sum(1 / max(a.holders[v], b.holders[v]) for v in va & vb)
    values = 2 * shared / size if size else 0.0
    return VALUES * values + NAME * _name(a, b, ka, kb) + ATTRIBUTES * jaccard(a.item_attributes[ka],
                                                                                b.item_attributes[kb])

def _candidates(a, b):
    """{(ka, kb): score} above the floor, among item pairs sharing a value or a name word (no others can reach it).
    A pair sharing only name words whose names hold different identifiers ("Room 101", "Room 102") can't either: its
    name scores 0, so it scores at most ATTRIBUTES, under the floor. So name words are looked up among the items
    whose identifiers are the same or none (code review 2026-10-08, D3: every room against every room)."""
    by_value, by_word = defaultdict(set), defaultdict(lambda: defaultdict(set))  # by_word[word][identifiers]
    for kb in b.items:
        for v in b.item_values[kb]:
            by_value[v].add(kb)
        for w in b.names[kb]:
            by_word[w][identifiers(b.names[kb])].add(kb)
    none = frozenset()
    out = {}
    for ka in a.items:
        ids = identifiers(a.names[ka])
        named = (by_word[w].values() if not ids or ATTRIBUTES >= FLOOR else (by_word[w][ids], by_word[w][none])
                 for w in a.names[ka])
        near = set().union(*(by_value[v] for v in a.item_values[ka]), *(kbs for sets in named for kbs in sets))
        for kb in near:
            s = _score(a, b, ka, kb)
            if s >= FLOOR:
                out[ka, kb] = s
    return out

def _assign(candidates, of_a, of_b):
    """Best first, one counterpart each, with a margin over the next candidate either item has left. Returns
    ({ka: kb}, ambiguous item pairs)."""
    aligned, ambiguous, taken_a, taken_b = {}, [], set(), set()
    for (ka, kb), s in sorted(candidates.items(), key=lambda x: (-x[1], x[0])):
        if ka in taken_a or kb in taken_b:
            continue
        rivals = [v for k, v in of_a[ka].items() if k != kb and k not in taken_b] + \
                 [v for k, v in of_b[kb].items() if k != ka and k not in taken_a]
        if rivals and s - max(rivals) < MARGIN:
            ambiguous.append((ka, kb))
            continue
        aligned[ka] = kb
        taken_a.add(ka)
        taken_b.add(kb)
    return aligned, ambiguous

def _conditions(x, y):
    a, b = words(x.conditions), words(y.conditions)
    return 1.0 if not a and not b else jaccard(a, b)

def _conflict(x, y):
    """Two readings name different identifiers, wherever they put them: "turbidity, 95th percentile" against
    "99th percentile turbidity" (a reader may move a condition into the attribute)."""
    ia = identifiers(words(x.attribute) | words(x.conditions))
    ib = identifiers(words(y.attribute) | words(y.conditions))
    return bool(ia and ib and ia != ib)

def _one_property(side, claims):
    """Whether a value's readings in an item all name one property (each pair fits): then the value identifies it."""
    return all(fits(side.claims[i], side.claims[j]) for i in claims for j in claims if i < j)

def _within(a, b, ia, ib, settle):
    """Claim pairs within two corresponding items. Claims of one value (the same value under a fitting attribute)
    are a group: readers phrase conditions differently ("Door Schedule", "face of finish"), so a group is unchanged
    when any of its readings agree on conditions across the revisions, and is settled (if settle) with one pair per
    claim; a group with none agreeing goes to the judge (its conditions may have changed). The rest pair by
    attribute and conditions, best first, for the judge. Returns (to judge, settled)."""
    judge, settled, done_a, done_b, unsure_a, unsure_b = [], [], set(), set(), set(), set()
    groups = defaultdict(lambda: ([], []))
    for i in ia:
        if a.values[i] is not None:
            groups[a.values[i]][0].append(i)
    for j in ib:
        if b.values[j] is not None and b.values[j] in groups:
            groups[b.values[j]][1].append(j)
    for value, (ga, gb) in sorted(groups.items(), key=lambda x: str(x[0])):
        # a tag as the value ("D103") points at one thing, whatever the attribute calls the pointing; so does a value
        # each item holds under one property only ("number of inversions", "inversion count")
        pairs = [(i, j) for i in ga for j in gb if value[0] == "id" or fits(a.claims[i], b.claims[j])]
        if not pairs and _one_property(a, ga) and _one_property(b, gb):
            pairs = [(i, j) for i in ga for j in gb]
        if not pairs:
            continue
        ranked = sorted(pairs, key=lambda p: (-_conditions(a.claims[p[0]], b.claims[p[1]]), p))
        best = (a.claims[ranked[0][0]], b.claims[ranked[0][1]])
        agreed = settle and _conditions(*best) >= 0.5 and not any(_conflict(a.claims[i], b.claims[j]) for i, j in pairs)
        covered_a, covered_b = set(), set()
        for i, j in ranked:  # one pair per claim, best conditions first
            if i in covered_a and j in covered_b:
                continue
            (settled if agreed else judge).append((i, j, 1.0))
            covered_a.add(i)
            covered_b.add(j)
        done_a |= covered_a
        done_b |= covered_b
        if not agreed:  # judged, not settled: still open to a leftover reading
            unsure_a |= covered_a
            unsure_b |= covered_b
    # each claim's words once, not once per pair: a large item paired its claims by the million (code review
    # 2026-10-08, D4)
    attr_a, attr_b = {i: attribute(a.claims[i]) for i in ia}, {j: attribute(b.claims[j]) for j in ib}
    cond_a, cond_b = {i: words(a.claims[i].conditions) for i in ia}, {j: words(b.claims[j].conditions) for j in ib}
    best_a, best_b = {}, {}
    # each reading left over pairs with its best partner, left over too or in a value group sent to the judge: a later
    # revision may print the superseded value beside the new one ("raised from 178 ft to 230 ft"), and the old
    # reading paired with the old value under other conditions
    free_a = lambda i: i not in done_a or i in unsure_a
    free_b = lambda j: j not in done_b or j in unsure_b
    said_a, said_b = {i: words(a.claims[i].attribute) for i in ia}, {j: words(b.claims[j].attribute) for j in ib}
    same = lambda i, j: said_a[i] == said_b[j]  # with a judged reading: only
    # pairs whose attributes share a word (an unnamed reading pairs only by value), found by word, each scored by
    # its attributes' and conditions' similarity; sorted below, so found in any order
    by_word = defaultdict(list)
    for j in ib:
        for w in attr_b[j]:
            by_word[w].append(j)
    candidates = [(jaccard(attr_a[i], attr_b[j]) + 0.5 * jaccard(cond_a[i], cond_b[j]), i, j)
                  for i in ia if free_a(i) for j in {j for w in attr_a[i] for j in by_word[w]}
                  if (i not in done_a or j not in done_b) and free_b(j)
                  and (a.values[i] is None or a.values[i] != b.values[j])
                  and ((i not in done_a and j not in done_b) or same(i, j))]
    for s, i, j in sorted(candidates, key=lambda x: (-x[0], x[1], x[2])):
        if s < PAIRING:
            break
        # each claim with its best partners (ties kept: two readings of a changed value both pair)
        if s >= best_a.get(i, s) or s >= best_b.get(j, s):
            judge.append((i, j, round(s / 1.5, 4)))
            best_a.setdefault(i, s)
            best_b.setdefault(j, s)
    # still without a partner: by all their words, best first, one each (a statement reworded, its attribute named
    # otherwise by another reading)
    left_a = [i for i in ia if i not in done_a and i not in best_a]
    left_b = [j for j in ib if j not in done_b and j not in best_b]
    whole = lambda c: words(f"{c.entity} {c.attribute} {c.value} {c.unit} {c.conditions}")
    whole_a, whole_b = {i: whole(a.claims[i]) for i in left_a}, {j: whole(b.claims[j]) for j in left_b}
    open_a, open_b = set(left_a), set(left_b)
    for s, i, j in sorted(((jaccard(whole_a[i], whole_b[j]), i, j) for i in left_a for j in left_b),
                          key=lambda x: (-x[0], x[1], x[2])):
        if s < WORDING:
            break
        if i in open_a and j in open_b:
            judge.append((i, j, round(s, 4)))
            open_a.remove(i)
            open_b.remove(j)
    return judge, settled

def _homes(src, dst, key):
    """The other revision's items a leftover item belongs to, if clear (one counterpart is favoured, not assumed: a
    reader may split one thing into two items, "Ridgeback" and "Ridgeback roller coaster", or file three revisions'
    dates under one). By values no other item there holds: the item holding most of them, else the items that
    together hold most of them (a group); failing values, the item of its exact name, if none of its values
    points elsewhere."""
    values = src.item_values[key]
    if values:
        shares = defaultdict(int)
        for v in values:
            owners = [k for k, vals in dst.item_values.items() if v in vals]
            if len(owners) == 1:
                shares[owners[0]] += 1
        ranked = sorted(((n / len(values), k) for k, n in shares.items()), reverse=True)
        if ranked and ranked[0][0] >= 0.5 and (len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= MARGIN):
            return [ranked[0][1]]
        if sum(n for n, _ in ranked) >= JOINING:
            return sorted(k for _, k in ranked)
    if key in dst.items and not any(v in vals for k, vals in dst.item_values.items() if k != key for v in values):
        return [key]
    return []

def stem(key):
    """What related names share: a tag less its final letter (P-101C, P-101E: P-101); a name's words less its
    identifiers, with the identifiers' leading digits (Room 104, Room 104A: room 104)."""
    if TAG.fullmatch(key):
        return key.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    w = words(key)
    digits = sorted(m.group() for x in identifiers(w) for m in [re.match(r"\d+", x)] if m)
    return " ".join(sorted(w - identifiers(w)) + digits) if digits else None

def _sums(one, many, keys):
    """The attributes whose value in one item is the sum of the others' (within rounding): [(attribute, whole,
    parts)]. one, many: (side, key); keys: the others' keys."""
    side, key = one
    out = []
    for i, kind, x in side.numbers(key):
        parts = []
        for k in keys:
            match = [(j, n) for j, kd, n in many.numbers(k) if kd == kind and fits(side.claims[i], many.claims[j])]
            if not match:
                break
            parts.append(match[0])
        if len(parts) == len(keys) and abs(sum(n for _, n in parts) - x) <= 0.005 * max(abs(x), 1e-9):
            out.append((side.claims[i].attribute, side.claims[i].value, [many.claims[j].value for j, _ in parts]))
    return out

def _regroup(a, b, lone_a, lone_b):
    """Split and merge candidates among leftover items: one item on one side, two or more on the other, their names
    sharing a stem. [(kind, earlier keys, later keys, evidence)]; candidates only, by names and values."""
    out, used_a, used_b = [], set(), set()
    for kind, src, dst, lone_src, lone_dst in (("split", a, b, lone_a, lone_b), ("merge", b, a, lone_b, lone_a)):
        for key in sorted(lone_src):
            if key in (used_a if src is a else used_b) or stem(key) is None:
                continue
            parts = [k for k in sorted(lone_dst) if k not in (used_b if src is a else used_a) and stem(k) == stem(key)]
            if len(parts) < 2:
                continue
            sums = _sums((src, key), dst, parts)
            evidence = {"stem": stem(key), "sums": [{"attribute": at, "whole": w, "parts": ps} for at, w, ps in sums],
                        "shared_attributes": sorted(src.item_attributes[key] & frozenset().union(
                            *(dst.item_attributes[k] for k in parts)))}
            (used_a if src is a else used_b).add(key)
            (used_b if src is a else used_a).update(parts)
            out.append((kind, [key], parts, evidence) if kind == "split" else (kind, parts, [key], evidence))
    return out

def align(left, right):
    """The Correspondence of two revisions' claims (left the earlier, right the later)."""
    return Alignment(left, right).correspondence()

class Alignment:
    """Two revisions' items aligned, step by step, each step's outcome kept for the next (code review 2026-10-08, D7:
    loose locals, the report's groupings built from 13 parameters): items matched best first with a margin; the
    matched items' claims compared, and the ambiguous items' with each candidate they had left; leftover items
    attached to a clear home; the claims left over paired across items; split and merge candidates among the items
    still alone."""

    def __init__(self, left, right):
        self.a, self.b = Side(left), Side(right)
        self.judge, self.settled = [], []
        self.match()
        self.compare_matched()
        self.compare_ambiguous()
        self.attach()
        self.leftovers()

    def match(self):
        a, b = self.a, self.b
        self.candidates = _candidates(a, b)
        self.of_a, self.of_b = defaultdict(dict), defaultdict(dict)
        for (ka, kb), s in self.candidates.items():
            self.of_a[ka][kb] = s
            self.of_b[kb][ka] = s
        self.aligned, self.ambiguous = _assign(self.candidates, self.of_a, self.of_b)

    def compare(self, ka, kb, settle):
        j, s = _within(self.a, self.b, self.a.items[ka], self.b.items[kb], settle=settle)
        self.judge += j
        if settle:
            self.settled += s

    def compare_matched(self):
        for ka, kb in sorted(self.aligned.items()):
            self.compare(ka, kb, settle=True)

    def compare_ambiguous(self):
        """Ambiguous items: each with the candidates it had left, for the judge to decide (nothing settled)."""
        aligned = self.aligned
        self.open_a = {ka for ka, _ in self.ambiguous} - set(aligned)
        self.open_b = {kb for _, kb in self.ambiguous} - set(aligned.values())
        pairs = {(ka, kb) for ka in self.open_a for kb in self.of_a[ka] if kb not in aligned.values()} | \
                {(ka, kb) for kb in self.open_b for ka in self.of_b[kb] if ka not in aligned}
        for ka, kb in sorted(pairs):
            self.compare(ka, kb, settle=False)

    def attach(self):
        """Leftover items with a clear home on the other side: a second counterpart, compared like the first."""
        a, b, aligned, open_a, open_b = self.a, self.b, self.aligned, self.open_a, self.open_b
        self.attached = set()
        for ka in sorted(k for k in a.items if k not in aligned and k not in open_a):
            self.attached |= {(ka, kb) for kb in _homes(a, b, ka) if kb not in open_b}
        self.taken_b = set(aligned.values())
        for kb in sorted(k for k in b.items if k not in self.taken_b and k not in open_b):
            self.attached |= {(ka, kb) for ka in _homes(b, a, kb) if ka not in open_a}
        for ka, kb in sorted(self.attached):
            self.compare(ka, kb, settle=True)

    def leftovers(self):
        """The items still alone: their claims left over paired with strays across items, then split and merge
        candidates among them; the rest unaligned."""
        a, b = self.a, self.b
        homed_a, homed_b = {ka for ka, _ in self.attached}, {kb for _, kb in self.attached}
        lone_a = [k for k in a.items if k not in self.aligned and k not in self.open_a and k not in homed_a]
        lone_b = [k for k in b.items if k not in self.taken_b and k not in self.open_b and k not in homed_b]
        self.judge += _strays(a, b, self.judge + self.settled, lone_a, lone_b)
        self.regroupings = _regroup(a, b, lone_a, lone_b)
        self.regrouped_a = {k for _, ka, _, _ in self.regroupings for k in ka}
        self.regrouped_b = {k for _, _, kb, _ in self.regroupings for k in kb}
        self.lone_a = [k for k in lone_a if k not in self.regrouped_a]
        self.lone_b = [k for k in lone_b if k not in self.regrouped_b]

    def summary(self):
        a, b, aligned = self.a, self.b, self.aligned
        return {"strategy": "items aligned across revisions by shared values, names and attributes, best first with "
                            "a margin; equal values in aligned items settled without a model",
                "items": [len(a.items), len(b.items)], "aligned_items": len(aligned),
                "ambiguous_items": [len(self.open_a), len(self.open_b)],
                "attached_items": len(self.attached), "unaligned_items": [len(self.lone_a), len(self.lone_b)],
                # items matched under another tag: P-101B now P-201B (by its values)
                "renamed_items": sorted([ka, kb] for ka, kb in list(aligned.items()) + sorted(self.attached)
                                        if ka != kb and TAG.fullmatch(ka) and TAG.fullmatch(kb)),
                "regrouped_items": [len(self.regrouped_a), len(self.regrouped_b)],
                "settled_pairs": len(self.settled)}

    def correspondence(self):
        a, b = self.a, self.b
        unaligned_a = sorted(i for k in self.lone_a for i in a.items[k])
        unaligned_b = sorted(i for k in self.lone_b for i in b.items[k])
        judge = sorted(set(self.judge), key=lambda x: (-x[2], x[0], x[1]))
        regrouped = (sorted(i for k in self.regrouped_a for i in a.items[k]),
                     sorted(i for k in self.regrouped_b for i in b.items[k]))
        return Correspondence(judge, sorted(self.settled), (unaligned_a, unaligned_b), self.summary(), _groups(self),
                              regrouped)

def _strays(a, b, pairs, lone_a, lone_b):
    """Claims left without a partner in items that have counterparts, paired with the one such claim on the other side
    holding the same value under a fitting attribute: a reader may file a fact under another entity in one revision
    ("first drop" for the ride's maximum acceleration). For the judge, not settled: the entities differ."""
    done = ({i for i, _, _ in pairs}, {j for _, j, _ in pairs})
    lone = (set(), set())
    for side, keys, out in ((a, lone_a, lone[0]), (b, lone_b, lone[1])):
        for k in keys:
            out.update(side.items[k])
    stray_a = [i for i in range(len(a.claims)) if i not in done[0] and i not in lone[0] and a.values[i] is not None]
    stray_b = defaultdict(list)
    for j in range(len(b.claims)):
        if j not in done[1] and j not in lone[1] and b.values[j] is not None:
            stray_b[b.values[j]].append(j)
    out = []
    for i in stray_a:
        matches = [j for j in stray_b.get(a.values[i], []) if fits(a.claims[i], b.claims[j])]
        if len(matches) == 1 and sum(a.values[k] == a.values[i] for k in stray_a) == 1:
            out.append((i, matches[0], 0.5))
    return out

def _groups(alignment):
    """The groupings as alignment formed them, for the report: each with its items' names, claims and evidence."""
    a, b, candidates = alignment.a, alignment.b, alignment.candidates
    aligned, attached = alignment.aligned, alignment.attached
    open_a, open_b, of_a, of_b = alignment.open_a, alignment.open_b, alignment.of_a, alignment.of_b
    lone_a, lone_b, regroupings = alignment.lone_a, alignment.lone_b, alignment.regroupings
    def group(kind, ka, kb, score=None, evidence=None):
        return {"kind": kind, "earlier": [a.display(k) for k in ka], "later": [b.display(k) for k in kb],
                "earlier_claims": sorted(i for k in ka for i in a.items[k]),
                "later_claims": sorted(j for k in kb for j in b.items[k]),
                "score": None if score is None else round(score, 3), "evidence": evidence or {}}
    def shared(ka, kb):
        return {"shared_values": len(a.item_values[ka] & b.item_values[kb]),
                "names": "same" if ka == kb else "related" if _name(a, b, ka, kb) > 0 else "different"}
    out = []
    for ka, kb in sorted(aligned.items()):
        renamed = ka != kb and TAG.fullmatch(ka) and TAG.fullmatch(kb)
        out.append(group("renamed" if renamed else "matched", [ka], [kb], candidates[ka, kb], shared(ka, kb)))
    for ka, kb in sorted(attached):
        out.append(group("attached", [ka], [kb], None, {**shared(ka, kb), "note": "a second counterpart: one thing "
                                                         "read as two items in one revision"}))
    for ka in sorted(open_a):
        later = sorted(k for k in of_a[ka] if k not in aligned.values())
        out.append(group("ambiguous", [ka], later, None, {"candidates": {b.display(k): round(of_a[ka][k], 3)
                                                                          for k in later}}))
    for kb in sorted(open_b - {k for ka in open_a for k in of_a[ka]}):
        earlier = sorted(k for k in of_b[kb] if k not in aligned)
        out.append(group("ambiguous", earlier, [kb], None, {"candidates": {a.display(k): round(of_b[kb][k], 3)
                                                                            for k in earlier}}))
    for kind, ka, kb, evidence in regroupings:
        out.append(group(kind + " candidate", ka, kb, None, evidence))
    out += [group("unaligned", [k], []) for k in sorted(lone_a)] + [group("unaligned", [], [k]) for k in sorted(lone_b)]
    return out
