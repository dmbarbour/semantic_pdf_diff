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
    are (NAME_SHARE);
  - `properties`: property names in common;
  - `values`: values in common (alignment's value_key);
  - `judged`: the judge's verdicts on their claims paired, by relation;
  - `grouped`: alignment's grouping of them (ambiguous, a split or merge candidate);
  - `model`: the model's answer naming one the other's counterpart (same, corresponding, state), taken or not.
  Identifiers that differ ("Room 104", "Room 105") rule a pair out.
- **The rubric** (RUBRIC; a view of the signals, by mode, the owner having chosen two weighings: revisions' and
  proposals' evidence means other things): a signal counts for a pair where
  - names share a rare word, or most of their words; two properties or more are in common;
  - (revisions) a value is in common, the judge paired their claims (any relation but unrelated), alignment grouped
    them; (proposals) the judge called a pair of their claims equivalent, different or complementary (values in
    common, and "uncertain", are coincidence and doubt between two designs);
  - the model named one the other's counterpart.
  Two signals or more: plausible; one: possible. The level is worked out from the signals each time a report is
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
LEVELS = ("plausible", "possible")
RELATION = {"revisions": "same", "proposals": "corresponding"}  # a link's relation where the model gave none
STRONG = {"revisions": ("equivalent", "different", "complementary", "uncertain"),  # the judge's verdicts that count
          "proposals": ("equivalent", "different", "complementary")}

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
    for i, s in alone.get(sources[0], []):
        for w in _name_words(s) | {("property", p) for p in _properties(s)}:
            pairs |= {tuple(sorted((i, j))) for j in by.get(w, ())}
    found = []
    for i, j in sorted(pairs):
        s, t = subjects[i], subjects[j]
        if list(s["claims"]) == list(t["claims"]):  # one source's two subjects: not this milestone's
            continue
        ids = [identifiers({w for n in x["names"] for w in words(n)}) for x in (s, t)]
        if ids[0] and ids[1] and not ids[0] & ids[1]:  # Room 104 isn't Room 105
            continue
        said = paired.get((i, j), {"judged": Counter(), "grouped": [], "model": []})
        ev = {"name": sorted(_name_words(s) & _name_words(t)), "properties": sorted(_properties(s) & _properties(t)),
              "values": len(values_of(i) & values_of(j)),
              "judged": dict(sorted(said["judged"].items())), "grouped": sorted(set(said["grouped"])),
              "model": [r for r, _ in said["model"]]}
        names = (_name_words(s), _name_words(t))
        said_alike = any(held[w] <= RARE for w in ev["name"]) or (
            ev["name"] and len(ev["name"]) >= NAME_SHARE * len(names[0] | names[1]))
        signals = [k for k, counts in (("name", said_alike), ("properties", len(ev["properties"]) >= 2),
                                       ("values", mode == "revisions" and ev["values"] > 0),
                                       ("judged", any(said["judged"][r] for r in STRONG[mode])),
                                       ("grouped", bool(ev["grouped"])), ("model", bool(ev["model"]))) if counts]
        if not signals:
            continue
        level = LEVELS[0] if len(signals) >= 2 else LEVELS[1]
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
SIGNALS = {"name": "names", "properties": "properties in common", "values": "values in common",
           "judged": "claims the judge paired", "grouped": "grouped by alignment", "model": "the model's match"}

def link_said(link):
    """A link as the index and the page say it: "possibly the counterpart of Alum (a.pdf; plausible: properties in
    common, claims the judge paired)"."""
    return (f"possibly {SAID.get(link['relation'], 'the same as')} {link['other']} ({link['source']}; {link['level']}: "
            + ", ".join(SIGNALS.get(x, x) for x in link["signals"]) + ")")
