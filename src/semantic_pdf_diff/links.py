"""Links: subjects of two sources possibly one, kept apart (docs/plans/tentative-matches-2026-11-07.md, milestone 2;
the owner, 2026-11-07: "we probably first need a viable model for "possibly relevant or a match, not sure,
investigate further and see if things fit when tied together" instead of all-or-nothing"; "Three levels is a start";
plausible matches "should feed links and topics for now").

- **A match is a hypothesis:** its relation (the same item, the corresponding element, a state of it) and its level
  (firm, plausible, possible). A firm match joins two subjects into one (indexes.matched); a plausible or possible one
  is a link between two subjects that stay apart, never chained (A~B and B~C don't make A~C), each subject's
  LINKS at most, the most evidenced first.
- **Asked of each pair** of subjects alone in two sources sharing a name word or a property's name, or paired by the
  findings, alignment's groupings or the model's answers (crossmatch.py): its signals, each evidence, none deciding:
  - `name`: name words in common (not stop words nor generic ones: "data", "item"), counted where one is rare among
    the subjects' names (RARE at most: the turbine pair's "blade" and "turbine" name dozens) or most of their words
    are (NAME_SHARE), or two names spelled alike (their letters' trigrams, SPELLED: "flocculators", "flocculation";
    milestone 3);
  - `meaning`: two names alike in meaning (their embeddings' cosine, MEANING at least, each the other's likest: the
    link_meaning lever's, with an embedding model; milestone 3);
  - `reranked`: the reranker's likest for a subject, scoring RERANKED at least (rerank.subjects: the link_rerank
    lever's, with a reranker; it reads names and properties together, so it's evidence of its own; milestone 3);
  - `properties`: property names in common;
  - `values`: values in common (alignment's value_key);
  - `judged`: the judge's verdicts on their claims paired, by relation;
  - `grouped`: alignment's grouping of them (ambiguous, a split or merge candidate);
  - `model`: the model's answer naming one the other's counterpart (same, corresponding, state), taken or not.
  Between revisions, identifiers that differ ("Room 104", "Room 105") rule a pair out; not between proposals, whose
  corresponding elements differ by their numbers too (NREL's 5 MW turbine and IEA's 15 MW: milestone 3).
- **The rubric** (RUBRIC; a view of the signals, by mode, the owner having chosen two weighings: revisions' and
  proposals' evidence means other things): a signal counts for a pair where
  - names share a rare word, or most of their words; two properties or more are in common;
  - (revisions) a value is in common, the judge paired their claims (any relation but unrelated), alignment grouped
    them; (proposals) the judge called a pair of their claims equivalent, different or complementary (values in
    common, and "uncertain", are coincidence and doubt between two designs);
  - the model named one the other's counterpart; names alike in meaning.
  Names alike by their words, their spelling or their meaning are one family of evidence (they're all the names':
  the turbine pair's "Rotor Speed" and "rotor-speed error" alike by both), and a model's reading of the two another
  (the reranker's, the model's match, its pick over a decoy); two families or more: plausible; one: possible. The
  level is worked out from the signals each time a report is written: a new rubric changes what's shown, never what
  was asked.
- **Tested, where the link_tests lever says** (its setting as the report's run had it; milestone 4; the owner,
  2026-11-07: "let's just adapt the normal levers approaches"):
  - *distinct properties:* properties in common count only where this pair's are more than either subject has in
    common with any other candidate. Siblings share theirs: the controlled proposals' three pumps each linked to the
    other design's three, and the coaster's elements to each other's, all plausible by properties alone.
  - *values that fit* (between proposals): a property both give, its values of one kind of unit and within FIT
    times of each other; a pair whose values don't fit is possible at most (a height isn't a frequency).
- **Read by the model, where the link_read lever ran** (crossmatch.read_links): a link shown against a decoy, the model
  picking its counterpart: picked, evidence of its own (`read`); the decoy or neither, possible at most.
- **Levels from numbers, where the link_levels setting says "weights"** (milestone 6; the owner, 2026-11-07: "Perhaps we
  start with a three-levels rubric then figure out how to analyze or evidence a fuzzy, weighted, or probabilistic
  numeric match"): a pair's features banded (bands()), each band's Fellegi-Sunter weight (log2 of its share among
  matches over its share among non-matches) summed into its score, its level by the table's thresholds
  (link_weights.json: fitted by the lab on the controlled proposals pairs, linkfit.py; proposals only, revisions
  keeping the rubric: their subjects left alone hold too few counterparts to fit). The model's read only raises: a
  possible link it picks over its decoy is plausible; "neither" lowers nothing (on seeds 2 and 3, read as a test it
  lowered 10 plausible links, every one right: siblings the reads can't tell apart, which the weights already weigh).
  Links are ordered by score for the cap. A link says its score and the share of matches it says (`likely`).
- **Keyed alike, kept apart, where the keyed_links setting says** (milestone 14; indexes.firm_keyed): between
  proposals, two subjects keyed alike (a tag, the same words, other names) whose properties say otherwise (either
  has more in common with another subject) aren't one; they're a link (`keyed`, of the names' family), plausible
  however little else is said (the owner, 2026-11-09: "A plausible link is good."), its tests and the model's read
  lowering it as any link's.
- **Kept in the index** (indexes.built: each subject's "links"), shown as links and in topics, never in the merged
  index's values nor its gaps, never a finding.
"""
import math
import re
from collections import Counter, defaultdict

from .align import DOCUMENT_PARTS, GENERIC, STOP, identifiers, series, unit, value_key, words
from .schema import Evidence

RUBRIC = "rubric/1"
# What candidates() makes, versioned: a weight table fitted on another version is stale (weights). candidates/1 until
# keyed_links (2026-11-09) added pairs keyed alike and kept apart; candidates/2 since; candidates/3 since each pair's
# evidence was also kept as numbers (features; evidence combined numerically, milestone 1, 2026-11-11); candidates/4
# since identifiers differing, each side's property count and place joined them (milestones 4, 6 and 10); candidates/5
# since units of two series (align.series) were marked; candidates/6 since a document's parts' words ("sheet",
# "detail") left proposals' names' words and spelling (2026-11-12)
CANDIDATES = "candidates/6"
LINKS = 3  # a subject's links, at most: the most evidenced first
RARE = 4  # subjects whose names hold a word, at most, for a name word in common to count
NAME_SHARE = 0.5  # or the share of two names' words in common, at least
SPELLED = 0.5  # or two names' letters' trigrams in common, their share at least
MEANING = 0.8  # two names' embeddings' cosine, at least, for names alike in meaning (the turbine pair: its two
# turbines 0.86, wrong pairs mostly under 0.8)
# signals of one family, counted once toward a level: the names' (words, spelling, meaning), and a model's reading of
# the two (the reranker's, the model's match, its pick over a decoy: the turbine pair's IEA "15-MW turbine" and NREL's
# "Region 2½" were plausible by the reranker and the read alone)
FAMILY = {"meaning": "name", "reranked": "model", "read": "model", "keyed": "name"}
FIT = 10  # times apart, at most, two designs' values of one property may be for their items to correspond
RERANKED = 0.8  # the reranker's score, at least, of a subject's likest for it to count (the turbine pair: its right
# pair 0.98, but wrong ones as high: it scores relevance, not identity; those under 0.8 mostly wrong)
LEVELS = ("plausible", "possible")
RELATION = {"revisions": "same", "proposals": "corresponding"}  # a link's relation where the model gave none
STRONG = {"revisions": ("equivalent", "different", "complementary", "uncertain"),  # the judge's verdicts that count
          "proposals": ("equivalent", "different", "complementary")}

def stable(data):
    """A report's data as the topics count links: without the model's other names and its log (asked after the
    topics, the other names a request a topic), so what's built from it is the same whenever."""
    return {k: v for k, v in data.items() if k not in ("synonyms", "commentary")}

INCH = 0.0254  # metres: alignment keys a length in feet and inches as inches

def measured(claim, kinds=False):
    """A claim's value key (align.value_key); with kinds (the unit_kinds lever; tentative matches, milestone 15; the
    gotchas review, item 3: "150 psi and 1,034 kPa never meet"), a number whose unit the product's table doesn't know
    keyed by the search's (values.search_unit): its kind and its size in the kind's base, as the product's units are,
    so 5,151 gpm and 325 L/s are one kind; a length in inches in metres. Alignment keeps its own keys."""
    from .values import search_unit
    key = value_key(claim)
    if not kinds or key is None or len(key) < 2 or not isinstance(key[1], (int, float)):
        return key
    if key[0] == "in":
        return ("length", round(key[1] * INCH, 9)) + key[2:]
    said = (claim.unit or "").strip()
    found = search_unit(said) if said and not unit(said) else None
    return (found[0], round(key[1] * found[1], 9)) + key[2:] if found else key

def _by_property(subject, evidence, kinds=False):
    """{a property's key (its names' words): [its values' keys]} (measured)."""
    out = defaultdict(list)
    for p in subject["properties"]:
        keys = {" ".join(sorted(words(n))) for n in p.get("names", [p["name"]])} - {""}
        for v in p["values"]:
            e = evidence.get(v["claim"])
            key = measured(Evidence.model_validate(e), kinds) if e is not None else None
            if key is not None:
                for k in keys:
                    out[k].append(key)
    return out

def _fits(a, b, common):
    """Whether two subjects' values of the properties in common fit (FIT): of one kind of unit, within FIT times of
    each other; text and unknown units aren't weighed."""
    for k in common:
        for x in a.get(k, []):
            for y in b.get(k, []):
                if x[0] == "text" or y[0] == "text" or len(x) < 2 or len(y) < 2:
                    continue
                if not isinstance(x[1], (int, float)) or not isinstance(y[1], (int, float)):
                    continue
                if x[0] != y[0]:
                    return False
                small, large = sorted((abs(x[1]), abs(y[1])))
                if small and large / small > FIT:
                    return False
    return True

def _fit_measure(a, b, common):
    """What _fits weighs, as numbers: {"ratio": the largest ratio of two values of one kind of unit (None where none
    are weighed), "differ": how many pairs of values are of other kinds}."""
    ratio, differ = None, 0
    for k in common:
        for x in a.get(k, []):
            for y in b.get(k, []):
                if x[0] == "text" or y[0] == "text" or len(x) < 2 or len(y) < 2:
                    continue
                if not isinstance(x[1], (int, float)) or not isinstance(y[1], (int, float)):
                    continue
                if x[0] != y[0]:
                    differ += 1
                    continue
                small, large = sorted((abs(x[1]), abs(y[1])))
                if small:
                    ratio = max(ratio or 1.0, large / small)
    return {"ratio": round(ratio, 3) if ratio is not None else None, "differ": differ}

def _name_words(subject):
    return {w for n in subject["names"] for w in words(n)} - STOP - GENERIC

def property_keys(subject):
    """A subject's properties as links count them in common: each name's words, sorted (plurals folded, stop words
    out)."""
    return {" ".join(sorted(words(n))) for p in subject["properties"] for n in p.get("names", [p["name"]])} - {""}

_properties = property_keys

def _values(subject, evidence):
    out = set()
    for p in subject["properties"]:
        for v in p["values"]:
            e = evidence.get(v["claim"])
            if e is not None:
                key = value_key(Evidence.model_validate(e))
                if key is not None:
                    out.add(key)
    return out

def _trigrams(name):
    letters = "".join(c for c in name.casefold() if c.isalnum() or c == " ")
    return {letters[k:k + 3] for k in range(len(letters) - 2)} - {""}

def _bare(name):
    """A name without its generic words or a document's parts' ("Grid Line 4": "4"; "Bedroom Section (A1)": "Bedroom
    A1"): between proposals, what spells a thing of its own (align.DOCUMENT_PARTS)."""
    kept = re.sub(r"[A-Za-z0-9]+", lambda w: "" if words(w[0]) <= GENERIC | DOCUMENT_PARTS else w[0], name)
    return " ".join(kept.split())  # the rest as written

def _spelling(a, b, bare=False):
    """Two subjects' names' spelling alike, as a number: the largest share of trigrams in common of any two of their
    names (0 where none); bare: their names without generic words (_bare)."""
    best = 0.0
    for x in a["names"]:
        tx = _trigrams(_bare(x) if bare else x)
        for y in b["names"]:
            ty = _trigrams(_bare(y) if bare else y)
            if tx and ty:
                best = max(best, len(tx & ty) / len(tx | ty))
    return best

def _spelled(a, b, bare=False):
    """Whether two subjects have names spelled alike (their trigrams' share in common, SPELLED at least)."""
    return _spelling(a, b, bare) >= SPELLED

def _spelled_pairs(alone, sources):
    """The pairs of subjects alone in the two sources whose names are spelled alike (_spelled), found through their
    trigrams in common."""
    by = defaultdict(set)
    for j, t in alone.get(sources[1], []):
        for n in t["names"]:
            for g in _trigrams(n):
                by[g].add(j)
    subject = dict(alone.get(sources[1], []))
    out = set()
    for i, s in alone.get(sources[0], []):
        shared = Counter(j for n in s["names"] for g in _trigrams(n) for j in by.get(g, ()))
        out |= {tuple(sorted((i, j))) for j, n in shared.items() if n >= 3 and _spelled(s, subject[j])}
    return out

def _alone(index):
    """{source: [(subject's index, subject)]}: the subjects with claims in one source only."""
    out = defaultdict(list)
    for i, s in enumerate(index.get("subjects", [])):
        if len(s["claims"]) == 1:
            out[next(iter(s["claims"]))].append((i, s))
    return out

def _paired(data, owner):
    """The pairs of subjects the findings, alignment's groupings and the model's answers name: {(i, j): {"judged":
    Counter, "grouped": [kinds], "model": [(relation, taken)], "verdicts": [(relation, the judge's confidence)]}}
    (i, j: subjects' indices, the first source's first)."""
    out = defaultdict(lambda: {"judged": Counter(), "grouped": [], "model": [], "verdicts": []})
    for f in data.get("findings", []):
        a, b = owner.get(f.get("a")), owner.get(f.get("b"))
        if a is not None and b is not None and a != b:
            out[tuple(sorted((a, b)))]["judged"][f.get("relation", "")] += 1
            out[tuple(sorted((a, b)))]["verdicts"].append((f.get("relation", ""), f.get("confidence")))
    for g in data.get("groupings", []):
        if g.get("kind") in ("ambiguous", "split candidate", "merge candidate"):
            for x in {owner[c] for c in g.get("earlier_claims", []) if c in owner}:
                for y in {owner[c] for c in g.get("later_claims", []) if c in owner}:
                    if x != y:
                        out[tuple(sorted((x, y)))]["grouped"].append(g["kind"])
    return out

def _meaning(data, subjects, alone, sources):
    """The pairs of subjects alone in the two sources whose names are alike in meaning: each the other's likest by
    their names' embeddings (data["name_vectors"]: embed.names), their cosine MEANING at least: {(i, j): cosine}."""
    import math
    from operator import mul
    from .embed import unpacked
    vectors = (data.get("name_vectors") or {}).get("vectors") or {}
    if not vectors:
        return {}
    kept = {}  # a name's vector and its length, unpacked once

    def of(s):
        out = []
        for n in s["names"]:
            if n in vectors and n not in kept:
                v = unpacked(vectors[n])
                kept[n] = (v, math.sqrt(sum(map(mul, v, v))) or 1.0)
            if n in kept:
                out.append(kept[n])
        return out
    near, theirs = {}, [(j, of(t)) for j, t in alone.get(sources[1], [])]
    for i, s in alone.get(sources[0], []):
        mine = of(s)
        for j, ys in theirs:
            if mine and ys:
                near[i, j] = max(sum(map(mul, a, b)) / (na * nb) for a, na in mine for b, nb in ys)
    best_a, best_b = {}, {}
    for (i, j), c in near.items():
        if c > best_a.get(i, (0, None))[0]:
            best_a[i] = (c, j)
        if c > best_b.get(j, (0, None))[0]:
            best_b[j] = (c, i)
    return {tuple(sorted((i, j))): c for i, (c, j) in best_a.items() if c >= MEANING and best_b[j][1] == i}

def _ranked(data, subjects, alone):
    """The reranker's likest subject for each subject it ranked, scoring RERANKED at least (data["subject_ranks"]:
    rerank.subjects): {(i, j): score}, by the subjects' names in their sources."""
    found = (data.get("subject_ranks") or {}).get("scores") or {}
    named = {(source, s["name"]): i for source, xs in alone.items() for i, s in xs}
    out = {}
    for source, ranks in found.items():
        other = next((x for x in alone if x != source), None)
        for name, scores in ranks.items():
            i = named.get((source, name))
            best = max(scores.items(), key=lambda x: (x[1], x[0]), default=None)
            if i is None or best is None or best[1] < RERANKED or (other, best[0]) not in named:
                continue
            out[tuple(sorted((i, named[other, best[0]])))] = best[1]
    return out

def bands(candidate, mode):
    """A candidate pair's features, banded, as the weights are fitted and read (linkfit.py): {feature: band}. The
    model's read isn't one: it's asked only of links already chosen."""
    ev = candidate["evidence"]
    meaning = ev.get("meaning")
    judged = sum(ev["judged"].get(r, 0) for r in STRONG[mode])
    model = ev["model"][0] if ev["model"] else ""
    return {"alike": "yes" if candidate["alike"] else "no",
            "meaning": "absent" if meaning is None else ("high" if meaning >= 0.85 else "mid"),
            "properties": str(min(len(ev["properties"]), 3)),
            "distinct": "yes" if candidate["distinct"] else "no",
            "fits": "absent" if candidate["fits"] is None else ("yes" if candidate["fits"] else "no"),
            "judged": str(min(judged, 2)),
            "model": {"": "none", "same": "match", "corresponding": "match"}.get(model, model)}

_WEIGHTS, _STALE = {}, []

def weights():
    """The weight table (link_weights.json), read once; None where it was fitted on what another version of
    candidates() made (its "candidates" isn't CANDIDATES): link_levels "weights" then keeps the rubric, a warning
    saying so once (evidence combined numerically, milestone 0: weights/1 was fitted on candidates/1, unchecked)."""
    if not _WEIGHTS:
        import json
        from pathlib import Path
        _WEIGHTS.update(json.loads((Path(__file__).with_name("link_weights.json")).read_text(encoding="utf-8")))
    if _WEIGHTS.get("candidates") != CANDIDATES:
        if not _STALE:
            import logging
            logging.getLogger("semantic_pdf_diff").warning(
                f"link_levels weights: link_weights.json ({_WEIGHTS.get('version')}) was fitted on "
                f"{_WEIGHTS.get('candidates')}, links are now {CANDIDATES}; the rubric decides instead")
            _STALE.append(True)
        return None
    return _WEIGHTS

def scored(table, candidate, mode):
    """(a pair's score: its bands' weights summed, a band the table hasn't seen weighing nothing; the share of
    matches it says, with the table's prior)."""
    s = sum(table["weights"].get(f, {}).get(b, 0.0) for f, b in bands(candidate, mode).items())
    p = table["prior"]
    odds = (p / (1 - p)) * 2 ** s if 0 < p < 1 else 0.0
    return round(s, 3), round(odds / (1 + odds), 3)

COMBINED = "combined/1"  # the hand-set combiner's version (evidence combined numerically, milestone 3)
PRIOR = -1.2  # a candidate pair's log-odds of being one before its evidence (0.23; development's candidates are 729
# matches of 2,357, but most bear some evidence, so the prior sits lower: set by the calibration of 2026-11-11)
CLIP = 0.02  # a probability kept this far from 0 and 1 (the owner: "nothing should ever be pinned at 0% or 100%")
DECAY = 0.5  # within a family, each further point for counts this share of the one before it
FAMILY_CAP = 1.5  # a family's points for, at most: one family alone (names, or the model's readings) stays under
# plausible, as two families of evidence once did by rule (the turbine pair: "Rotor Speed" and "rotor-speed error" by
# their spelling, IEA's turbine and "Region 2½" by the reranker and the read)
FAMILY_CAPS = {"key": 2.6}  # but a key both give: near 0.8 alone (the owner: "Perhaps firm group is only 80% without
# corroborating evidence"; development's first pass, milestone 6: 1,749 of 1,876 keyed pairs one, 0.93)
# Proposals' firm groups: a pair joined from this probability (milestone 6), one to one, by MERGE_MARGIN over the next
# likeliest pair either side has. By analysis of development (182 units, firm groups right / wrong, items matched):
# 0.70: 1,842 / 12, 1,226; 0.75: 1,780 / 12, 1,164; the rubric 1,734 / 0, 1,158. A key alone (near 0.8) joins; a key
# with no property in common (0.62) doesn't
MERGE = 0.7
MERGE_MARGIN = 0.1
# A link's level from its probability, for consumers gating on one (until milestone 5): set by analysis of development's
# candidates (2026-11-11): from 0.35 up about 90% right, under it mostly a weak name; plausible above what one family
# alone reaches (FAMILY_CAP with the prior: 0.57)
SHOWN = {"plausible": 0.6, "possible": 0.35}
# Each consumer's cut on a combined link's probability (evidence combined numerically, milestone 5; Claude's, the owner:
# "You'll be the one tuning things based on measurement and initially by analysis"): link gaps from 0.6 (development:
# all 26 right ones from 0.5 to 0.8, the fewest wrong, 10, at 0.6 and 0.7); the rest as shown plausible for now
USES = {"link_gaps": 0.6, "linked_values": 0.6, "topics": 0.6}

def trusted(link, use):
    """Whether a consumer (USES) takes a link: a combined link by its probability against the consumer's cut, a
    rubric's by its level (plausible)."""
    if "probability" in link:
        return link["probability"] >= USES[use]
    return link["level"] == "plausible"

def contributions(c, mode):
    """A candidate pair's evidence as signed log-odds, by family (evidence combined numerically, milestone 3; hand-set
    and adjusted by eye, the owner: "we can start with hand-set weights adjusted by eye"): {family: [(point, weight)]}.
    Names: the rarest shared word, the words' share, the spelling, the meaning, a key both give (near 0.8 alone with
    the prior: the owner, "Perhaps firm group is only 80% without corroborating evidence"). The model: its match, its
    pick over a decoy, the decoy or neither picked (against), the reranker's score. Properties: in common, little
    where a rival shares as many (siblings), against where a rival shares more. Values: other kinds of unit, or
    magnitudes far apart (against), close (for); in common between revisions. The judge: its verdicts that count
    (its numeric confidence weighs nothing: the owner doubts models'). Alignment: its groupings."""
    # By eye, guided by development's candidates (seeds 1 and 8 to 15, 2,357 pairs): each point's share right against
    # 0.31 by chance, the weight about its log-likelihood ratio shrunk toward 0, the strongest capped (2026-11-11)
    f, out = c["features"], defaultdict(list)
    if f["name_idf"]:
        out["names"].append(("a rare word in common", round(min(f["name_idf"], 3.0) * 0.15, 3)))  # 0.38 right
    if f["name_share"]:
        out["names"].append(("words in common", round(0.6 * f["name_share"], 3)))
    if f["spelling"] >= 0.3:
        out["names"].append(("spelled alike", round(min(1.5, 3.0 * f["spelling"]), 3)))  # 160 of 160 right
        # on the controlled designs, capped lower: on the turbine pair, "Rotor Speed" and "rotor-speed error"
    if f["meaning"]:
        out["names"].append(("alike in meaning", round(max(0.0, (f["meaning"] - 0.7) * 10), 3)))
    if f["keyed"]:
        out["key"].append(("a key both give", 2.6))  # a family of its own: with the prior near 0.8 alone (the owner)
        if not f["properties"] and min(f.get("own", [0])) > 0:  # other_names_fit's rule as a weight: 187 of 302 such
            out["key"].append(("a key, no property in common", -0.9))  # keyed pairs one (0.62, against 0.93)
    for r in f["model"]:
        out["model"].append((f"the model's match ({r})", 2.0))
    out["model"] += {"picked": [("picked over a decoy", 1.5)], "decoy": [("the decoy picked", -2.5)],  # 0.95, 0
                     "neither": [("neither picked", -0.1)]}.get(f["read"], [])  # 0.29: near chance
    if f["reranked"] is not None:
        out["model"].append(("the reranker's likest", round(max(0.0, (f["reranked"] - 0.5) * 2), 3)))
    n, rival = f["properties"], f["rival"]
    if n and rival < n:
        out["properties"].append((f"{n} in common, no rival as many", round(min(2.5, n * 0.9), 3)))  # 0.93 right
    elif n:
        out["properties"].append((f"{n} in common, as a rival has", 0.0))  # 0.31: chance
    if rival > max(n, 1):
        out["properties"].append(("a rival shares more", round(-1.2 * min(rival - n, 2), 3)))  # 0.05 right
    if f["kinds_differ"]:
        out["values"].append(("values of other kinds of unit", -0.5))  # 0.21 right
    elif f["value_ratio"] is not None:
        if f["value_ratio"] > FIT:
            out["values"].append(("magnitudes far apart", -1.0))
        elif f["value_ratio"] <= 2:
            out["values"].append(("magnitudes close", 0.4))  # 0.95 right but between siblings
    if mode == "revisions" and f["values"]:
        out["values"].append(("values in common", 1.5))
    strong = [r for r, _ in f["verdicts"] if r in STRONG[mode]]
    if strong:
        out["judge"].append((f"the judge paired {len(strong)}", 0.8 if len(strong) > 1 else 0.6))  # 0.94, ditto
    if f["grouped"]:
        out["alignment"].append(("grouped by alignment", 1.0))
    # Evidence that follows from other evidence counts less (correlated, not independent): siblings' values and the
    # judge's pairings follow from what siblings share (0.31 right, chance, against 0.95 apart: a little still orders
    # siblings among themselves); a key both give put the two before the judge and the read, which count nothing (0.10
    # right: milestone 14, the read picking the tag it was shown)
    siblings = n and rival >= n
    for family, points in out.items():
        if f.get("series") and family in ("model", "judge", "names"):  # two series' units: the model's match, the
            # judge's pairings and the tags' spelling follow their numbering, which tells nothing of a bank's units
            # (Harrow Creek's P-101A and Pine Ridge's IP-1, paired by order: the owner, 2026-11-12, align.series);
            # their kind's words still count
            out[family] = [(name + ", units of two series", 0.0) if w > 0 and (family != "names" or name ==
                           "spelled alike") else (name, w) for name, w in points]
        elif f["keyed"] and family in ("judge", "model", "names"):
            out[family] = [(name + ", shown by the key", 0.0) if w > 0 and name != "a key both give" else (name, w)
                           for name, w in points]
        elif siblings and family in ("judge", "values"):
            out[family] = [(name + ", as siblings", round(w * 0.3, 3)) if w > 0 else (name, w) for name, w in points]
    return dict(out)

def combined(c, mode):
    """(a candidate pair's probability of being one, {family: its log-odds}): each family's points for decaying
    (DECAY: one family's many points don't count as many families), its points against summed, the families and the
    prior (PRIOR) summed, the probability kept off 0 and 1 (CLIP)."""
    total, by = PRIOR, {}
    for family, points in contributions(c, mode).items():
        weights_for = sorted((w for _, w in points if w > 0), reverse=True)
        value = (min(FAMILY_CAPS.get(family, FAMILY_CAP), sum(w * DECAY ** k for k, w in enumerate(weights_for)))
                 + sum(w for _, w in points if w < 0))
        by[family] = round(value, 3)
        total += value
    p = 1 / (1 + math.exp(-max(-30.0, min(30.0, total))))
    return round(min(max(p, CLIP), 1 - CLIP), 3), by

def merges(data, index):
    """Proposals' firm groups by evidence (milestone 6): [(i, j, probability)] of the candidate pairs to join, one to
    one, the likeliest first: at MERGE or above, and by MERGE_MARGIN over the next likeliest pair either side has."""
    scored = sorted(((combined(c, data.get("mode", ""))[0], c["i"], c["j"]) for c in candidates(data, index)),
                    reverse=True)
    best = defaultdict(list)  # each subject's pairs' probabilities, the likeliest first
    for p, i, j in scored:
        best[i].append(p)
        best[j].append(p)
    out, taken = [], set()
    for p, i, j in scored:
        if p < MERGE:
            break
        if i in taken or j in taken:
            continue
        rival = max([q for q in best[i][1:]] + [q for q in best[j][1:]] + [0.0])  # each side's next likeliest
        if p - rival < MERGE_MARGIN:
            continue
        out.append((i, j, p))
        taken |= {i, j}
    return out

# Place by neighbours (milestone 10, a feature weighing nothing): a pair whose neighbours' counterparts are each
# other's neighbours. On development's first pass, half or more 0.56 right, some 0.19, none 0.01 (12 of 861); weighed
# (+0.8, −0.6, −2.5, or against only) it moved nothing on development or seeds 16 and 17: where it would help (Spruce
# Lake's decoy, in a section of its own), too few anchors are near to say (2026-11-11)
NEIGHBOURS = 3  # a subject's neighbours in its document: this many before it and after it

def _position(e):
    """A claim's place in its document's order, however it was read: (page, its line, paragraph or height)."""
    loc = e.get("locator") or {}
    offset = (loc.get("lines") or loc.get("paragraphs") or [None])[0]
    if offset is None:
        offset = (loc.get("bbox") or [0, 0])[1]
    return (loc.get("page") or 0, offset or 0)

def _places(subjects, evidence, sources, anchors):
    """Each subject's neighbours in each source it's given in ({(subject, source): its NEIGHBOURS nearest each side,
    in document order}), and each subject's counterparts by the anchors ({subject: {subjects}}: firm groups are
    their own, a keyed pair each other's)."""
    order = defaultdict(list)
    for i, s in enumerate(subjects):
        for source, ids in s["claims"].items():
            spots = sorted(_position(evidence[c]) for c in ids if c in evidence)
            if spots:
                order[source].append((spots[len(spots) // 2], i))
    near = {}
    for source, placed in order.items():
        placed.sort()
        for k, (_, i) in enumerate(placed):
            near[i, source] = {x for _, x in placed[max(0, k - NEIGHBOURS):k + NEIGHBOURS + 1] if x != i}
    counterpart = defaultdict(set)
    for i, s in enumerate(subjects):
        if len(s["claims"]) == 2:
            counterpart[i].add(i)  # a firm group: itself in each source
    for i, j in anchors:
        counterpart[i].add(j)
        counterpart[j].add(i)
    return near, counterpart

def _place(i, j, sources, near, counterpart):
    """(anchors near both of a pair, anchors near either): the pair's neighbours whose counterparts are the other's
    neighbours, of those with a counterpart in the other source (place, milestone 10)."""
    mine, theirs = near.get((i, sources[0]), set()) - {j}, near.get((j, sources[1]), set()) - {i}
    others = lambda x: counterpart.get(x, set()) - {i, j}  # noqa: E731 (the pair isn't its own anchor)
    shared = {x for x in mine if others(x) & theirs}
    return len(shared), max(sum(1 for x in mine if others(x)), sum(1 for y in theirs if others(y)))

def candidates(data, index):
    """Every pair of subjects alone in the two sources that a link may join, with what's known of it, whatever the
    settings: [{"i", "j" (the subjects' indices, the lower first), "evidence" (as a link shows it), "alike" (names
    alike: a rare word, most words, or the spelling), "distinct" (two properties or more in common, more than either
    has with any other candidate), "fits" (proposals: the values of the properties in common fit; None where none are
    weighed), "read" (the model's read against a decoy, or None), "keyed" (keyed alike, kept apart: index["keyed"]),
    "features" (the evidence as numbers, for a combiner: the rarest shared name word's IDF over the subjects' names,
    the names' words' share in common, their spelling's, the cosine and the reranker's score where asked, properties
    in common and the most either has with another candidate, the values' largest ratio of one unit kind and how many
    are of other kinds, values in common, keyed, the model's answers and read, the judge's verdicts with its
    confidence, alignment's groupings)}], A to Z by the pair. A level is worked out from
    these (linked: the rubric; tentative matches, milestone 6: numbers)."""
    subjects, mode = index.get("subjects", []), data.get("mode", "")
    sources = index.get("sources", [])
    if len(sources) != 2 or mode not in RELATION:
        return []
    kinds = bool((data.get("settings") or {}).get("unit_kinds"))
    alone = _alone(index)
    owner = {c: i for i, s in enumerate(subjects) if len(s["claims"]) == 1 for c in next(iter(s["claims"].values()))}
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    paired = _paired(data, owner)
    values = {}  # a subject's values, as they're first asked for

    def values_of(i):
        if i not in values:
            values[i] = _values(subjects[i], evidence)
        return values[i]
    # keyed alike, kept apart (indexes.firm_keyed: the keyed_links lever's); pairs, or lists read from a report
    keyed = {tuple(p) for p in index.get("keyed", ()) if all(len(subjects[x]["claims"]) == 1 for x in p)}
    reads = {}  # the model's reads of links against decoys (crossmatch.read_links): {(i, j): relation}
    # the model's answers (crossmatch.py), taken or not
    named = {(next(iter(s["claims"])), s["name"]): i for i, s in enumerate(subjects) if len(s["claims"]) == 1}
    for c in (data.get("commentary") or {}).get("entries", []):
        if c["kind"] == "match":
            a, b = named.get((c["source"], c["subject"])), named.get((c.get("other_source"), c.get("other")))
            if a is not None and b is not None:
                paired[tuple(sorted((a, b)))]["model"].append((c.get("relation", ""), bool(c.get("taken"))))
        elif c["kind"] == "link_read":
            a, b = named.get((c["source"], c["subject"])), named.get((c.get("other_source"), c.get("other")))
            if a is not None and b is not None:
                reads[tuple(sorted((a, b)))] = c.get("relation", "")
    # a name's words: between proposals not a document's parts' ("sheet", "detail": align.DOCUMENT_PARTS), which two
    # designs' documents share by habit (the first link panel on real pairs, 2026-11-12)
    bare = mode == "proposals"
    name_words = (lambda s: _name_words(s) - DOCUMENT_PARTS) if bare else _name_words  # noqa: E731
    # candidates sharing a name word or a property's name, besides those named
    by = defaultdict(set)
    for j, t in alone.get(sources[1], []):
        for w in name_words(t) | {("property", p) for p in _properties(t)}:
            by[w].add(j)
    held = Counter(w for s in subjects for w in name_words(s))  # how many subjects' names hold each word
    pairs = set(paired) | keyed
    pairs |= _spelled_pairs(alone, sources)
    likest = _meaning(data, subjects, alone, sources)  # names alike in meaning: {(i, j): cosine}, mutual likest
    pairs |= set(likest)
    ranked = _ranked(data, subjects, alone)  # the reranker's likest: {(i, j): score}
    pairs |= set(ranked)
    for i, s in alone.get(sources[0], []):
        for w in name_words(s) | {("property", p) for p in _properties(s)}:
            pairs |= {tuple(sorted((i, j))) for j in by.get(w, ())}
    common = {}  # each pair's properties in common, for the distinctness test
    for i, j in pairs:
        common[i, j] = _properties(subjects[i]) & _properties(subjects[j])
    most = Counter()  # each subject's largest overlap with any candidate, and how many candidates reach it
    for (i, j), c in common.items():
        for x in (i, j):
            if len(c) > most[x, "size"]:
                most[x, "size"], most[x, "count"] = len(c), 1
            elif len(c) == most[x, "size"]:
                most[x, "count"] += 1
    by_property = {}

    def distinct(i, j):
        n = len(common[i, j])
        return all(most[x, "size"] == n and most[x, "count"] == 1 for x in (i, j))
    overlaps = defaultdict(list)  # each subject's properties in common with each candidate: [(how many, the other)]
    for (i, j), c in common.items():
        overlaps[i].append((len(c), j))
        overlaps[j].append((len(c), i))

    def rival(x, partner):
        """The most properties x has in common with a candidate other than its partner."""
        return max((n for n, o in overlaps[x] if o != partner), default=0)

    def idf(w):
        return math.log(len(subjects) / held[w]) if held[w] else 0.0
    near, counterpart = _places(subjects, evidence, sources, keyed)
    # units of a series in their source (a bank's pumps), by their tags: two of two series are told apart by numbering
    tagged = series({(source, n) for source, alone_in in alone.items() for _, x in alone_in for n in x["names"]})
    unit_of = {i: {tag for (source, n), tag in tagged.items() if n in x["names"]}
               for alone_in in alone.values() for i, x in alone_in}
    out = []
    for i, j in sorted(pairs):
        s, t = subjects[i], subjects[j]
        if list(s["claims"]) == list(t["claims"]):  # one source's two subjects: not this milestone's
            continue
        ids = [identifiers({w for n in x["names"] for w in words(n)}) for x in (s, t)]
        if mode == "revisions" and ids[0] and ids[1] and not ids[0] & ids[1]:  # Room 104 isn't Room 105
            continue
        said = paired.get((i, j), {"judged": Counter(), "grouped": [], "model": []})
        ev = {"name": sorted(name_words(s) & name_words(t)), "properties": sorted(_properties(s) & _properties(t)),
              "values": len(values_of(i) & values_of(j)),
              "judged": dict(sorted(said["judged"].items())), "grouped": sorted(set(said["grouped"])),
              "model": [r for r, _ in said["model"]]}
        names = (name_words(s), name_words(t))
        alike = bool(any(held[w] <= RARE for w in ev["name"]) or (
            ev["name"] and len(ev["name"]) >= NAME_SHARE * len(names[0] | names[1])) or _spelled(s, t, bare))
        if (i, j) in likest:
            ev["meaning"] = round(likest[i, j], 3)
        if (i, j) in ranked:
            ev["reranked"] = ranked[i, j]
        if (i, j) in reads:
            ev["read"] = reads[i, j]
        fits = None
        if mode == "proposals" and ev["properties"]:
            for x in (i, j):
                if x not in by_property:
                    by_property[x] = _by_property(subjects[x], evidence, kinds)
            fits = _fits(by_property[i], by_property[j], ev["properties"])
        if (i, j) in keyed:
            ev["keyed"] = True
        if ev["properties"]:
            for x in (i, j):
                if x not in by_property:
                    by_property[x] = _by_property(subjects[x], evidence, kinds)
        measure = (_fit_measure(by_property[i], by_property[j], ev["properties"]) if ev["properties"]
                   else {"ratio": None, "differ": 0})
        union = names[0] | names[1]
        features = {  # the evidence as numbers, for a combiner (evidence combined numerically, milestone 1)
            "name_idf": round(max((idf(w) for w in ev["name"]), default=0.0), 3),
            "name_share": round(len(ev["name"]) / len(union), 3) if union else 0.0,
            "spelling": round(_spelling(s, t, bare), 3), "meaning": ev.get("meaning"), "reranked": ev.get("reranked"),
            "properties": len(ev["properties"]), "rival": max(rival(i, j), rival(j, i)),
            "value_ratio": measure["ratio"], "kinds_differ": measure["differ"], "values": ev["values"],
            "keyed": (i, j) in keyed, "model": [r for r, _ in said["model"]], "read": reads.get((i, j)),
            "verdicts": said.get("verdicts", []), "grouped": sorted(set(said["grouped"])),
            "ids_differ": bool(ids[0] and ids[1] and not ids[0] & ids[1]),
            "own": [len(_properties(s)), len(_properties(t))],
            "place": _place(i, j, sources, near, counterpart),
            "series": bool(mode == "proposals" and unit_of.get(i) and unit_of.get(j)
                           and not unit_of[i] & unit_of[j])}
        out.append({"i": i, "j": j, "evidence": ev, "alike": alike,
                    "distinct": len(ev["properties"]) >= 2 and distinct(i, j), "fits": fits, "read": reads.get((i, j)),
                    "keyed": (i, j) in keyed, "features": features})
    return out

def linked(data, index):
    """Each subject's links: {subject's index: [{"source", "other", "relation", "level", "signals", "evidence"}]},
    the other's source and name, the signals counted for it, and their evidence; both subjects of a pair hold it.
    Subjects alone in one source only, across two sources; each pair's level by the rubric (RUBRIC), its tests where
    the link_tests setting says."""
    subjects, mode = index.get("subjects", []), data.get("mode", "")
    tests = bool((data.get("settings") or {}).get("link_tests"))
    table = weights() if (data.get("settings") or {}).get("link_levels") == "weights" else None
    if table is not None and table["mode"] != mode:
        table = None  # revisions keep the rubric: the weights are proposals'
    combining = (data.get("settings") or {}).get("link_levels") == "combined" and mode == "proposals"
    found = []
    for c in candidates(data, index):
        i, j, ev = c["i"], c["j"], dict(c["evidence"])
        if combining:  # evidence combined numerically (milestone 3): a probability, its level only shown by it
            p, by = combined(c, mode)
            level = next((name for name, at in SHOWN.items() if p >= at), None)
            if level is None:
                continue
            signals = [family for family, value in by.items() if value > 0]
            relation = ev["model"][0] if ev["model"] else RELATION[mode]
            found.append(((p, 0), i, j, {"relation": relation, "level": level, "signals": signals, "evidence": ev,
                                         "probability": p, "contributions": by, "rubric": COMBINED}))
            continue
        if table is not None:
            s, likely = scored(table, c, mode)
            if s < table["thresholds"]["possible"] and not c["keyed"]:
                continue
            level = (LEVELS[0] if s >= table["thresholds"]["plausible"] or c["read"] == "picked" or c["keyed"]
                     else LEVELS[1])
            signals = [k for k, counts in (("name", c["alike"]), ("keyed", c["keyed"]), ("meaning", "meaning" in ev),
                                           ("properties", c["distinct"]), ("judged", any(
                                               ev["judged"].get(r) for r in STRONG[mode])),
                                           ("model", bool(ev["model"])), ("read", c["read"] == "picked")) if counts]
            relation = ev["model"][0] if ev["model"] else RELATION[mode]
            found.append(((s, 0), i, j, {"relation": relation, "level": level, "signals": signals,
                                                     "evidence": ev, "score": s, "likely": likely,
                                                     "rubric": table["version"]}))
            continue
        own = len(ev["properties"]) >= 2 and (not tests or c["distinct"])
        if tests and len(ev["properties"]) >= 2 and not own:
            ev["shared_by_siblings"] = True
        signals = [k for k, counts in (("name", c["alike"]), ("keyed", c["keyed"]), ("meaning", "meaning" in ev),
                                       ("reranked", "reranked" in ev),
                                       ("properties", own),
                                       ("values", mode == "revisions" and ev["values"] > 0),
                                       ("judged", any(ev["judged"].get(r) for r in STRONG[mode])),
                                       ("grouped", bool(ev["grouped"])), ("model", bool(ev["model"])),
                                       ("read", c["read"] == "picked")) if counts]
        if not signals:
            continue
        # two families plausible; keyed alike alone too (indexes.firm_keyed; the owner: "A plausible link is good.")
        level = LEVELS[0] if len({FAMILY.get(x, x) for x in signals}) >= 2 or c["keyed"] else LEVELS[1]
        if tests and mode == "proposals" and ev["properties"] and c["fits"] is False:
            ev["misfit"], level = True, LEVELS[1]  # values that don't fit: possible at most
        if c["read"] in ("decoy", "neither"):
            level = LEVELS[1]  # the model picked the decoy, or neither: possible at most
        relation = ev["model"][0] if ev["model"] else RELATION[mode]
        score = (len(signals), len(ev["properties"]) + len(ev["name"]) + ev["values"])
        found.append((score, i, j, {"relation": relation, "level": level, "signals": signals, "evidence": ev,
                                    "rubric": RUBRIC}))
    out = defaultdict(list)
    for score, i, j, link in sorted(found, key=lambda x: (-x[0][0], -x[0][1], x[1], x[2])):
        if len(out[i]) >= LINKS or len(out[j]) >= LINKS:
            continue
        for x, y in ((i, j), (j, i)):
            out[x].append({"source": next(iter(subjects[y]["claims"])), "other": subjects[y]["name"], **link})
    return dict(out)

SAID = {"same": "the same as", "corresponding": "the counterpart of", "state": "a state of"}  # how a link reads
SIGNALS = {"name": "names", "keyed": "a tag, name or other name both give",
           "meaning": "names alike in meaning", "reranked": "the reranker's likest",
           "read": "the model's pick over a decoy",
           "properties": "properties in common",
           "values": "values in common",
           "judged": "claims the judge paired", "grouped": "grouped by alignment", "model": "the model's match"}

FAMILIES = {"key": "a key both give", "names": "names", "model": "the model's readings", "properties": "properties",
            "values": "values", "judge": "the judge", "alignment": "alignment"}  # a combined link's families, as said

def link_said(link):
    """A link as the index and the page say it: "possibly the counterpart of Alum (a.pdf; plausible: properties in
    common, claims the judge paired)"; combined (link_levels "combined"), its probability and each family's part:
    "(a.pdf; 0.86: names +1.5, the model's readings +1.5, properties −1.2)" (evidence combined numerically, milestone
    4; the owner: "I think it's a good idea to report confidence scores numerically.")."""
    said = f"possibly {SAID.get(link['relation'], 'the same as')} {link['other']} ({link['source']}; "
    if "probability" in link:
        parts = [f"{FAMILIES.get(f, f)} {'+' if v > 0 else '−'}{abs(v):g}"
                 for f, v in sorted(link.get("contributions", {}).items(), key=lambda x: -abs(x[1])) if v]
        return said + f"{link['probability']:.2f}" + (": " + ", ".join(parts) if parts else "") + ")"
    return said + f"{link['level']}: " + ", ".join(SIGNALS.get(x, x) for x in link["signals"]) + ")"


# --- properties possibly one (tentative matches, milestone 8; the owner, 2026-11-09: "weighted/fuzzy joining of
# properties [...] as part of fitting things together"): two properties of a subject (or of a link's two subjects)
# named otherwise, by three families of evidence: their names (the same words, one's within the other's, most words
# shared, spelled alike), their values (numbers of one unit kind within FIT times of each other; another unit kind
# rules them out), and the judge's pairing of their claims. Two families: plausible; one: possible.

def property_evidence(data):
    """(each claim's value key (measured: by unit kind where the unit_kinds setting says), the pairs of claims the
    judge paired by a relation that counts)."""
    keys, kinds = {}, bool((data.get("settings") or {}).get("unit_kinds"))
    for e in data.get("evidence", []):
        key = measured(Evidence.model_validate(e), kinds)
        if key is not None:
            keys[e["id"]] = key
    strong = STRONG.get(data.get("mode", ""), STRONG["proposals"])
    judged = {frozenset((f["a"], f["b"])) for f in data.get("findings", []) if f.get("relation") in strong}
    return keys, judged

def _name_alike(a, b):
    """Two properties' names alike: a name's words equal, within the other's, most of them shared, or spelled alike."""
    for x in a:
        wx = set(words(x)) - STOP - GENERIC
        for y in b:
            wy = set(words(y)) - STOP - GENERIC
            if wx and wy and (wx <= wy or wy <= wx or len(wx & wy) >= NAME_SHARE * len(wx | wy)):
                return True
            tx, ty = _trigrams(x), _trigrams(y)
            if tx and ty and len(tx & ty) >= SPELLED * len(tx | ty):
                return True
    return False

def property_alike(p_names, p_claims, q_names, q_claims, keys, judged):
    """(level or None, its families) of two properties possibly one: names, values, the judge (see above)."""
    families = []
    if _name_alike(p_names, q_names):
        families.append("name")
    a = [keys[c] for c in p_claims if c in keys and len(keys[c]) >= 2 and isinstance(keys[c][1], (int, float))]
    b = [keys[c] for c in q_claims if c in keys and len(keys[c]) >= 2 and isinstance(keys[c][1], (int, float))]
    if a and b:
        if not {x[0] for x in a} & {y[0] for y in b}:
            return None, []  # numbers of other kinds: not one property
        if any(x[0] == y[0] and (x[1] == y[1] or (min(abs(x[1]), abs(y[1])) and max(abs(x[1]), abs(y[1]))
                                                  / min(abs(x[1]), abs(y[1])) <= FIT)) for x in a for y in b):
            families.append("values")
    if any(frozenset((c, d)) in judged for c in p_claims for d in q_claims):
        families.append("judged")
    if not families:
        return None, []
    return (LEVELS[0] if len(families) >= 2 else LEVELS[1]), families

PROPERTY_PRIOR = -1.5  # two properties of a subject, one from each source, being one before their evidence

def property_combined(p_names, p_claims, q_names, q_claims, keys, judged):
    """(the probability two properties are one, {family: its log-odds}): property_alike's evidence combined as links'
    is (combined; evidence combined numerically, milestone 4): names alike +1.5; values of one unit kind that fit
    +1.0, all far apart −1.0, only other kinds −2.5 (once a veto); the judge pairing their claims +1.5; a prior
    (PROPERTY_PRIOR), each family within FAMILY_CAP, kept off 0 and 1. Its level as links' (SHOWN): two families
    plausible, one possible, as the rubric said, but by weight."""
    by = {}
    if _name_alike(p_names, q_names):
        by["names"] = 1.5
    a = [keys[c] for c in p_claims if c in keys and len(keys[c]) >= 2 and isinstance(keys[c][1], (int, float))]
    b = [keys[c] for c in q_claims if c in keys and len(keys[c]) >= 2 and isinstance(keys[c][1], (int, float))]
    if a and b:
        if not {x[0] for x in a} & {y[0] for y in b}:
            by["values"] = -2.5
        elif any(x[0] == y[0] and (x[1] == y[1] or (min(abs(x[1]), abs(y[1])) and max(abs(x[1]), abs(y[1]))
                                                    / min(abs(x[1]), abs(y[1])) <= FIT)) for x in a for y in b):
            by["values"] = 1.0
        else:
            by["values"] = -1.0
    if any(frozenset((c, d)) in judged for c in p_claims for d in q_claims):
        by["judge"] = 1.5
    total = PROPERTY_PRIOR + sum(min(FAMILY_CAP, v) for v in by.values())
    p = 1 / (1 + math.exp(-total))
    return round(min(max(p, CLIP), 1 - CLIP), 3), by
