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

The weights and thresholds were set by inspection on the controlled revision pairs (decision 7: early development
by eye); calibrated confidences, splits and merges come later.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field

from .values import printed_value, unit

TAG = re.compile(r"\b[A-Z]{1,4}-?\d{1,4}[A-Z]?\b")
# Not "a": single letters name things (Option A, Revision A, valve A).
STOP = {"the", "an", "of", "for", "per", "each", "at", "in", "on", "to", "and", "with", "is", "by", "its", "value",
        "no"}

VALUES, NAME, ATTRIBUTES = 0.6, 0.3, 0.1  # an item pair's score: the evidence's shares
FLOOR = 0.3       # below it, an item has no counterpart
MARGIN = 0.15     # a counterpart must lead the next candidate by this much
PAIRING = 0.5     # claims within an item: the attribute and conditions similarity to pair them
JOINING = 0.6     # a positional claim joins a tagged item holding this share of its item's values

@dataclass
class Correspondence:
    """Which claims are compared: pairs for the judge [(i, j, score)], pairs settled as equivalent without one
    [(i, j, score)], the claims whose items have no counterpart (indices in each side), and a summary for the
    report."""
    judge: list
    settled: list = field(default_factory=list)
    unaligned: tuple = ((), ())
    summary: dict = field(default_factory=dict)

def words(text):
    """A name's words: case-folded, stop words dropped, plurals folded."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", str(text).casefold()):
        if w not in STOP:
            out.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
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

NUMERIC = re.compile(r"^\s*(?:about|approx\.?|approximately|~|≈|[-+±<>≤≥]=?)?\s*[-+±]?\$?\d")

def value_key(claim):
    """A value comparable across revisions: in its unit's base where the unit is known (1.2 MW is 1,200 kW), else
    with its unit as written; lengths in inches, dates as dates, a tag as itself ("D103"). None for anything else:
    a number inside words ("ROOM 102 ENLARGED") isn't the value."""
    text = str(claim.value).strip()
    if TAG.fullmatch(text):
        return ("id", text)
    v = printed_value(text)
    if isinstance(v, tuple):  # ("in", 33.5), ("date", "2026-01-10")
        return v
    if v is None or not NUMERIC.match(text):
        return None
    known = unit(claim.unit or "")
    if known:
        return (known[0], round(v * float(known[1]), 9))
    return (re.sub(r"\s", "", claim.unit or "").casefold(), round(v, 9))

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
    """{(ka, kb): score} above the floor, among item pairs sharing a value or a name word (no others can reach it)."""
    by_value, by_word = defaultdict(set), defaultdict(set)
    for kb in b.items:
        for v in b.item_values[kb]:
            by_value[v].add(kb)
        for w in b.names[kb]:
            by_word[w].add(kb)
    out = {}
    for ka in a.items:
        near = set().union(*(by_value[v] for v in a.item_values[ka]), *(by_word[w] for w in a.names[ka]))
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

def _within(a, b, ia, ib, settle):
    """Claim pairs within two corresponding items. Claims of one value (the same value under a fitting attribute)
    are a group: readers phrase conditions differently ("Door Schedule", "face of finish"), so a group is unchanged
    when any of its readings agree on conditions across the revisions, and is settled (if settle) with one pair per
    claim; a group with none agreeing goes to the judge (its conditions may have changed). The rest pair by
    attribute and conditions, best first, for the judge. Returns (to judge, settled)."""
    judge, settled, done_a, done_b = [], [], set(), set()
    groups = defaultdict(lambda: ([], []))
    for i in ia:
        if a.values[i] is not None:
            groups[a.values[i]][0].append(i)
    for j in ib:
        if b.values[j] is not None and b.values[j] in groups:
            groups[b.values[j]][1].append(j)
    for value, (ga, gb) in sorted(groups.items(), key=lambda x: str(x[0])):
        # a tag as the value ("D103") points at one thing, whatever the attribute calls the pointing
        pairs = [(i, j) for i in ga for j in gb if value[0] == "id" or fits(a.claims[i], b.claims[j])]
        if not pairs:
            continue
        ranked = sorted(pairs, key=lambda p: (-_conditions(a.claims[p[0]], b.claims[p[1]]), p))
        agreed = settle and _conditions(a.claims[ranked[0][0]], b.claims[ranked[0][1]]) >= 0.5
        covered_a, covered_b = set(), set()
        for i, j in ranked:  # one pair per claim, best conditions first
            if i in covered_a and j in covered_b:
                continue
            (settled if agreed else judge).append((i, j, 1.0))
            covered_a.add(i)
            covered_b.add(j)
        done_a |= covered_a
        done_b |= covered_b
    similarity = lambda i, j: (jaccard(attribute(a.claims[i]), attribute(b.claims[j]))
                               + 0.5 * jaccard(words(a.claims[i].conditions), words(b.claims[j].conditions)))
    named = lambda i, j: jaccard(attribute(a.claims[i]), attribute(b.claims[j])) > 0  # unnamed: only by value
    best_a, best_b = {}, {}
    for s, i, j in sorted(((similarity(i, j), i, j) for i in ia if i not in done_a for j in ib if j not in done_b
                           if named(i, j)), key=lambda x: (-x[0], x[1], x[2])):
        if s < PAIRING:
            break
        # each claim with its best partners (ties kept: two readings of a changed value both pair)
        if s >= best_a.get(i, s) or s >= best_b.get(j, s):
            judge.append((i, j, round(s / 1.5, 4)))
            best_a.setdefault(i, s)
            best_b.setdefault(j, s)
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

def align(left, right):
    """The Correspondence of two revisions' claims (left the earlier, right the later)."""
    a, b = Side(left), Side(right)
    candidates = _candidates(a, b)
    of_a, of_b = defaultdict(dict), defaultdict(dict)
    for (ka, kb), s in candidates.items():
        of_a[ka][kb] = s
        of_b[kb][ka] = s
    aligned, ambiguous = _assign(candidates, of_a, of_b)
    judge, settled = [], []
    for ka, kb in sorted(aligned.items()):
        j, s = _within(a, b, a.items[ka], b.items[kb], settle=True)
        judge += j
        settled += s
    # ambiguous items: each with the candidates it had left, for the judge to decide (nothing settled)
    open_a = {ka for ka, _ in ambiguous} - set(aligned)
    open_b = {kb for _, kb in ambiguous} - set(aligned.values())
    pairs = {(ka, kb) for ka in open_a for kb in of_a[ka] if kb not in aligned.values()} | \
            {(ka, kb) for kb in open_b for ka in of_b[kb] if ka not in aligned}
    for ka, kb in sorted(pairs):
        judge += _within(a, b, a.items[ka], b.items[kb], settle=False)[0]
    # leftover items with a clear home on the other side: a second counterpart, compared like the first
    attached = set()
    for ka in sorted(k for k in a.items if k not in aligned and k not in open_a):
        attached |= {(ka, kb) for kb in _homes(a, b, ka) if kb not in open_b}
    taken_b = set(aligned.values())
    for kb in sorted(k for k in b.items if k not in taken_b and k not in open_b):
        attached |= {(ka, kb) for ka in _homes(b, a, kb) if ka not in open_a}
    for ka, kb in sorted(attached):
        j, s = _within(a, b, a.items[ka], b.items[kb], settle=True)
        judge += j
        settled += s
    homed_a, homed_b = {ka for ka, _ in attached}, {kb for _, kb in attached}
    lone_a = [k for k in a.items if k not in aligned and k not in open_a and k not in homed_a]
    lone_b = [k for k in b.items if k not in taken_b and k not in open_b and k not in homed_b]
    unaligned_a = sorted(i for k in lone_a for i in a.items[k])
    unaligned_b = sorted(i for k in lone_b for i in b.items[k])
    judge = sorted(set(judge), key=lambda x: (-x[2], x[0], x[1]))
    summary = {"strategy": "items aligned across revisions by shared values, names and attributes, best first with "
                           "a margin; equal values in aligned items settled without a model",
               "items": [len(a.items), len(b.items)], "aligned_items": len(aligned),
               "ambiguous_items": [len(open_a), len(open_b)],
               "attached_items": len(attached), "unaligned_items": [len(lone_a), len(lone_b)],
               # items matched under another tag: P-101B now P-201B (by its values)
               "renamed_items": sorted([ka, kb] for ka, kb in list(aligned.items()) + sorted(attached)
                                       if ka != kb and TAG.fullmatch(ka) and TAG.fullmatch(kb)),
               "settled_pairs": len(settled)}
    return Correspondence(judge, sorted(settled), (unaligned_a, unaligned_b), summary)
