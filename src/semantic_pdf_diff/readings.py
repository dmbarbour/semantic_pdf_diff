"""Readings of one fact: sightings from different extraction tasks (tiles, the overview, a
figure, the text) that state the same fact in different words become one claim.

Claim identity is exact wording, so two readings of one handrail note, "handrails / material /
2x4 cedar" and "handrail / material/dimension / 2x4 cedar", are two claims; on the development
slices a third of claims had such a twin, nearly all from overlapping regions
(docs/research/duplicate-claims-2026-09-27.md). Reconciling keeps every sighting as an
occurrence, with its own wording, so the number of agreeing readings stays visible.

Conservative by design. Two claims are one fact when they
- were seen on the same page, in overlapping regions;
- give the same value and unit (spacing, commas, case and quote marks aside);
- have compatible conditions (equal, one empty, or one's words within the other's);
- name the same entity and attribute: for each, one's words within the other's after light
  normalization ("railing posts" and "Railing Post", "W2" and "Window W2", "material" and
  "material/size"; not "West Module" and "East Module", nor "fore-aft stiffness" and
  "side-to-side stiffness").
Every reading in a cluster must agree on conditions with every other.
Clustering is greedy against each cluster's representative (the most local reading), so
chains of near-matches don't merge distinct facts.
"""
import re
from functools import lru_cache
from .models import Occurrence, representative_rank
from .values import unit

# Not "a": single letters name modules, details and grid lines ("Module A" and "Module B" are two
# things; round 8 merged them when "a" was dropped as an article).
STOPWORDS = {"the", "of", "for", "and", "or", "in", "on", "at", "to", "by", "with", "per", "from", "as",
             "is", "are", "value", "values", "total"}
QUOTES = str.maketrans({"’": "'", "‘": "'", "′": "'", "″": '"', "“": '"', "”": '"', "×": "x", "−": "-", "–": "-",
                        "—": "-"})

THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")  # "1,250": a separator; "12,50" keeps its decimal comma
NUMBER_THEN = re.compile(r"^([-+±~≈<>≤≥=]*\d[\d.]*)(.+)$")

def _stated(e):
    """A claim's value and unit as stated, for telling readings of one fact: spacing, quote forms and thousands
    separators folded, and case, except a known unit's (5 MW isn't 5 mW: decision 0005), which is named by its kind
    and size (code review 2026-10-08, D9: every comma and every unit's case were folded)."""
    text = re.sub(r"\s", "", THOUSANDS.sub("", f"{e.value}{e.unit}".translate(QUOTES)))
    split = NUMBER_THEN.match(text)
    known = unit(split.group(2)) if split else None
    return f"{split.group(1)}[{known[0]}:{known[1]}]" if known else text.casefold()

@lru_cache(maxsize=1 << 16)
def _words(text):
    """A text's words, lightly normalized (cached: reconcile compares each claim's names many times)."""
    words = set()
    for w in re.findall(r"[a-z0-9]+", text.translate(QUOTES).casefold()):
        if w in STOPWORDS:
            continue
        words.add(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return frozenset(words)

def _conditions_agree(a, b):
    x, y = _words(a.conditions), _words(b.conditions)
    return not x or not y or x <= y or y <= x

def _near(a, b):
    """Some sighting of each on one page, in overlapping regions."""
    for p in a.occurrences or [a]:
        for q in b.occurrences or [b]:
            la, lb = p.locator, q.locator
            if la.page == lb.page and la.bbox[0] <= lb.bbox[2] and lb.bbox[0] <= la.bbox[2] \
                    and la.bbox[1] <= lb.bbox[3] and lb.bbox[1] <= la.bbox[3]:
                return True
    return False

def _named_alike(a, b):
    """One's words within the other's, for entity and attribute: "West Module" and "East Module"
    are two things, and so are a tower's "fore-aft stiffness" and "side-to-side stiffness"."""
    for x, y in ((_words(a.entity), _words(b.entity)), (_words(a.attribute), _words(b.attribute))):
        if not (x and y and (x <= y or y <= x)):
            return False
    return True

def same_fact(a, b):
    if a.approximate != b.approximate or _stated(a) != _stated(b) or not _conditions_agree(a, b):
        return False
    return _named_alike(a, b) and _near(a, b)

def wording(e):
    return " | ".join(x for x in [e.entity, e.attribute, f"{e.value} {e.unit}".strip(), e.conditions] if x)

def sightings(e):
    """A claim's occurrences; a single sighting keeps none, so make it one."""
    return list(e.occurrences) or [Occurrence(locator=e.locator, section=e.section, kind=e.kind, quote=e.quote,
                                              quote_verified=e.quote_verified, confidence=e.confidence,
                                              image=e.image, derivation=e.derivation)]

def reconcile(evidence):
    """Claims (occurrences already merged by ID) with readings of one fact merged into one."""
    # The most local reading represents a fact: text or table before a tile, a tile before the
    # overview. Round 7 tried the most informative reading instead (most condition words): wide
    # regions attach context from elsewhere on the page ("Structure South Elevation - Main" on a
    # sheet without it), and judges tagged three times as many claims invented. Round 6's one
    # case the other way (a local reading lacking "isolated tower") is the cheaper error.
    claims = sorted(evidence, key=lambda e: (representative_rank(e), e.id))
    clusters = []  # [representative, [members]], in the order they were started
    # A fact has one stated value and is seen near its representative, on one of its pages, so a claim is compared
    # only with the clusters stating its value whose representative was seen on a page of the claim's: the same
    # clusters, in the same order, as comparing with all of them, without the quadratic cost (code review
    # 2026-10-08, D5: 4,000 claims of one value took 33 s).
    by_value = {}  # (approximate, stated value): {page: [the indices of clusters whose representative was seen there]}
    for e in claims:
        pages = {o.locator.page for o in e.occurrences or [e]}
        group = by_value.setdefault((e.approximate, _stated(e)), {})
        for n in sorted({n for page in pages for n in group.get(page, ())}):
            cluster = clusters[n]
            # Every reading must agree with every other, not only with the representative: a generic
            # one ("beam", no conditions) would otherwise gather "Floor Beam @ Grid 4" and "@ Grid 5",
            # or "at rated speed" and "at cut-in". (The value is the group's: same_fact without it.)
            if _conditions_agree(cluster[0], e) and _named_alike(cluster[0], e) and _near(cluster[0], e) \
                    and all(_conditions_agree(m, e) and _named_alike(m, e) for m in cluster[1]):
                cluster[1].append(e)
                break
        else:
            clusters.append([e, []])
            for page in pages:
                group.setdefault(page, []).append(len(clusters) - 1)
    out = []
    for head, members in clusters:
        if not members:
            out.append(head)
            continue
        occurrences = sightings(head)
        for m in members:
            words = wording(m) if wording(m) != wording(head) else ""
            occurrences += [o.model_copy(update={"wording": words}) for o in sightings(m)]
        occurrences.sort(key=lambda o: (o.locator.page, o.locator.task))
        out.append(head.model_copy(update={"occurrences": occurrences,
                                           "confidence": max([head.confidence] + [m.confidence for m in members])}))
    return sorted(out, key=lambda e: (e.locator.page, e.locator.task, e.id))
