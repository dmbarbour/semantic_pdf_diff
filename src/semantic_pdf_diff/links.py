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
  the turbine pair's "Rotor Speed" and "rotor-speed error" alike by both); two families or more: plausible; one:
  possible. The level is worked out from the signals each time a report is
  written: a new rubric changes what's shown, never what was asked.
- **Kept in the index** (indexes.built: each subject's "links"), shown as links and in topics, never in the merged
  index's values nor its gaps, never a finding.
"""
from collections import Counter, defaultdict

from .align import GENERIC, STOP, identifiers, value_key, words
from .schema import Evidence

RUBRIC = "rubric/1"
LINKS = 3  # a subject's links, at most: the most evidenced first
RARE = 4  # subjects whose names hold a word, at most, for a name word in common to count
NAME_SHARE = 0.5  # or the share of two names' words in common, at least
SPELLED = 0.5  # or two names' letters' trigrams in common, their share at least
MEANING = 0.8  # two names' embeddings' cosine, at least, for names alike in meaning (the turbine pair: its two
# turbines 0.86, wrong pairs mostly under 0.8)
FAMILY = {"meaning": "name"}  # signals of one family, counted once toward a level
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

def _name_words(subject):
    return {w for n in subject["names"] for w in words(n)} - STOP - GENERIC

def _properties(subject):
    return {" ".join(sorted(words(n))) for p in subject["properties"] for n in p.get("names", [p["name"]])} - {""}

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

def linked(data, index):
    """Each subject's links: {subject's index: [{"source", "other", "relation", "level", "signals", "evidence"}]},
    the other's source and name, the signals counted for it, and their evidence; both subjects of a pair hold it.
    Subjects alone in one source only, across two sources."""
    subjects, mode = index.get("subjects", []), data.get("mode", "")
    sources = index.get("sources", [])
    if len(sources) != 2 or mode not in RELATION:
        return {}
    alone = _alone(index)
    owner = {c: i for i, s in enumerate(subjects) if len(s["claims"]) == 1 for c in next(iter(s["claims"].values()))}
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    paired = _paired(data, owner)
    values = {}  # a subject's values, as they're first asked for

    def values_of(i):
        if i not in values:
            values[i] = _values(subjects[i], evidence)
        return values[i]
    # the model's answers (crossmatch.py), taken or not
    named = {(next(iter(s["claims"])), s["name"]): i for i, s in enumerate(subjects) if len(s["claims"]) == 1}
    for c in (data.get("commentary") or {}).get("entries", []):
        if c["kind"] == "match":
            a, b = named.get((c["source"], c["subject"])), named.get((c.get("other_source"), c.get("other")))
            if a is not None and b is not None:
                paired[tuple(sorted((a, b)))]["model"].append((c.get("relation", ""), bool(c.get("taken"))))
    # candidates sharing a name word or a property's name, besides those named
    by = defaultdict(set)
    for j, t in alone.get(sources[1], []):
        for w in _name_words(t) | {("property", p) for p in _properties(t)}:
            by[w].add(j)
    held = Counter(w for s in subjects for w in _name_words(s))  # how many subjects' names hold each word
    pairs = set(paired)
    pairs |= _spelled_pairs(alone, sources)
    likest = _meaning(data, subjects, alone, sources)  # names alike in meaning: {(i, j): cosine}, mutual likest
    pairs |= set(likest)
    ranked = _ranked(data, subjects, alone)  # the reranker's likest: {(i, j): score}
    pairs |= set(ranked)
    for i, s in alone.get(sources[0], []):
        for w in _name_words(s) | {("property", p) for p in _properties(s)}:
            pairs |= {tuple(sorted((i, j))) for j in by.get(w, ())}
    found = []
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
        said_alike = any(held[w] <= RARE for w in ev["name"]) or (
            ev["name"] and len(ev["name"]) >= NAME_SHARE * len(names[0] | names[1])) or _spelled(s, t)
        if (i, j) in likest:
            ev["meaning"] = round(likest[i, j], 3)
        if (i, j) in ranked:
            ev["reranked"] = ranked[i, j]
        signals = [k for k, counts in (("name", said_alike), ("meaning", (i, j) in likest),
                                       ("reranked", (i, j) in ranked),
                                       ("properties", len(ev["properties"]) >= 2),
                                       ("values", mode == "revisions" and ev["values"] > 0),
                                       ("judged", any(said["judged"][r] for r in STRONG[mode])),
                                       ("grouped", bool(ev["grouped"])), ("model", bool(ev["model"]))) if counts]
        if not signals:
            continue
        level = LEVELS[0] if len({FAMILY.get(x, x) for x in signals}) >= 2 else LEVELS[1]
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
SIGNALS = {"name": "names", "meaning": "names alike in meaning", "reranked": "the reranker's likest",
           "properties": "properties in common",
           "values": "values in common",
           "judged": "claims the judge paired", "grouped": "grouped by alignment", "model": "the model's match"}

def link_said(link):
    """A link as the index and the page say it: "possibly the counterpart of Alum (a.pdf; plausible: properties in
    common, claims the judge paired)"."""
    return (f"possibly {SAID.get(link['relation'], 'the same as')} {link['other']} ({link['source']}; {link['level']}: "
            + ", ".join(SIGNALS.get(x, x) for x in link["signals"]) + ")")
