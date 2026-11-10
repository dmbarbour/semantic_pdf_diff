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
from collections import Counter, defaultdict

from .align import GENERIC, STOP, identifiers, unit, value_key, words
from .schema import Evidence

RUBRIC = "rubric/1"
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

def _spelled(a, b):
    """Whether two subjects have names spelled alike (their trigrams' share in common, SPELLED at least)."""
    for x in a["names"]:
        tx = _trigrams(x)
        for y in b["names"]:
            ty = _trigrams(y)
            if tx and ty and len(tx & ty) >= SPELLED * len(tx | ty):
                return True
    return False

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
    Counter, "grouped": [kinds], "model": [(relation, taken)]}} (i, j: subjects' indices, the first source's first)."""
    out = defaultdict(lambda: {"judged": Counter(), "grouped": [], "model": []})
    for f in data.get("findings", []):
        a, b = owner.get(f.get("a")), owner.get(f.get("b"))
        if a is not None and b is not None and a != b:
            out[tuple(sorted((a, b)))]["judged"][f.get("relation", "")] += 1
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

_WEIGHTS = {}

def weights():
    """The weight table (link_weights.json), read once."""
    if not _WEIGHTS:
        import json
        from pathlib import Path
        _WEIGHTS.update(json.loads((Path(__file__).with_name("link_weights.json")).read_text(encoding="utf-8")))
    return _WEIGHTS

def scored(table, candidate, mode):
    """(a pair's score: its bands' weights summed, a band the table hasn't seen weighing nothing; the share of
    matches it says, with the table's prior)."""
    s = sum(table["weights"].get(f, {}).get(b, 0.0) for f, b in bands(candidate, mode).items())
    p = table["prior"]
    odds = (p / (1 - p)) * 2 ** s if 0 < p < 1 else 0.0
    return round(s, 3), round(odds / (1 + odds), 3)

def candidates(data, index):
    """Every pair of subjects alone in the two sources that a link may join, with what's known of it, whatever the
    settings: [{"i", "j" (the subjects' indices, the lower first), "evidence" (as a link shows it), "alike" (names
    alike: a rare word, most words, or the spelling), "distinct" (two properties or more in common, more than either
    has with any other candidate), "fits" (proposals: the values of the properties in common fit; None where none are
    weighed), "read" (the model's read against a decoy, or None), "keyed" (keyed alike, kept apart: index["keyed"])}],
    A to Z by the pair. A level is worked out from
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
    keyed = {p for p in index.get("keyed", ()) if all(len(subjects[x]["claims"]) == 1 for x in p)}  # keyed alike,
    # kept apart (indexes.firm_keyed: the keyed_links lever's)
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
    # candidates sharing a name word or a property's name, besides those named
    by = defaultdict(set)
    for j, t in alone.get(sources[1], []):
        for w in _name_words(t) | {("property", p) for p in _properties(t)}:
            by[w].add(j)
    held = Counter(w for s in subjects for w in _name_words(s))  # how many subjects' names hold each word
    pairs = set(paired) | keyed
    pairs |= _spelled_pairs(alone, sources)
    likest = _meaning(data, subjects, alone, sources)  # names alike in meaning: {(i, j): cosine}, mutual likest
    pairs |= set(likest)
    ranked = _ranked(data, subjects, alone)  # the reranker's likest: {(i, j): score}
    pairs |= set(ranked)
    for i, s in alone.get(sources[0], []):
        for w in _name_words(s) | {("property", p) for p in _properties(s)}:
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
    out = []
    for i, j in sorted(pairs):
        s, t = subjects[i], subjects[j]
        if list(s["claims"]) == list(t["claims"]):  # one source's two subjects: not this milestone's
            continue
        ids = [identifiers({w for n in x["names"] for w in words(n)}) for x in (s, t)]
        if mode == "revisions" and ids[0] and ids[1] and not ids[0] & ids[1]:  # Room 104 isn't Room 105
            continue
        said = paired.get((i, j), {"judged": Counter(), "grouped": [], "model": []})
        ev = {"name": sorted(_name_words(s) & _name_words(t)), "properties": sorted(_properties(s) & _properties(t)),
              "values": len(values_of(i) & values_of(j)),
              "judged": dict(sorted(said["judged"].items())), "grouped": sorted(set(said["grouped"])),
              "model": [r for r, _ in said["model"]]}
        names = (_name_words(s), _name_words(t))
        alike = bool(any(held[w] <= RARE for w in ev["name"]) or (
            ev["name"] and len(ev["name"]) >= NAME_SHARE * len(names[0] | names[1])) or _spelled(s, t))
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
        out.append({"i": i, "j": j, "evidence": ev, "alike": alike,
                    "distinct": len(ev["properties"]) >= 2 and distinct(i, j), "fits": fits, "read": reads.get((i, j)),
                    "keyed": (i, j) in keyed})
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
    found = []
    for c in candidates(data, index):
        i, j, ev = c["i"], c["j"], dict(c["evidence"])
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
SIGNALS = {"name": "names", "keyed": "a tag or name both give",
           "meaning": "names alike in meaning", "reranked": "the reranker's likest",
           "read": "the model's pick over a decoy",
           "properties": "properties in common",
           "values": "values in common",
           "judged": "claims the judge paired", "grouped": "grouped by alignment", "model": "the model's match"}

def link_said(link):
    """A link as the index and the page say it: "possibly the counterpart of Alum (a.pdf; plausible: properties in
    common, claims the judge paired)"."""
    return (f"possibly {SAID.get(link['relation'], 'the same as')} {link['other']} ({link['source']}; {link['level']}: "
            + ", ".join(SIGNALS.get(x, x) for x in link["signals"]) + ")")


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
