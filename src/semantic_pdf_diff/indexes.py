"""A report's indexes (docs/plans/indexes-and-glossaries-2026-10-29.md, milestone 1): its subjects, their properties,
and its figures and tables, built from what was read, with no model requests; one source's, or a comparison's merged.
The owner, 2026-10-29: "building indexes and glossaries, e.g. of claims, diagrams, subjects. Even for a single
document that would be useful, and it seems deeply related to the problem of comparing things regardless."

- **Subjects** are alignment's items (align.Side), a source's at a time: a tag in the entity (P-101B), else the
  entity's words; a claim named by position joins the tagged item whose values it repeats. A subject is named as its
  claims most often name it, and lists its properties, each with every value given and where.
- **In a comparison,** the sources' subjects are matched, and each is listed once with each source's values beside
  the others' (the owner: "One merged index"). Revisions: where the findings pair their claims (the most pairs first,
  one to one; alignment decided the items, the findings follow it), else where they're keyed alike. Proposals: where
  they're keyed alike or named as other names of one thing, never by the findings alone (a judge's verdicts are
  about values, not identity: the turbine pair's tower went to a mode of the other's by three uncertain verdicts;
  single-document analysis, milestone 7, the owner answering its design's question D, 2026-11-07: "All four
  recommendations look good as a start."). Then, where the match_subjects lever ran (crossmatch.py), the model's
  matches of what's left. A subject's properties are one where they're named alike or the findings pair their claims
  ("seating capacity" and "rider capacity"). A property one source gives a matched subject and another doesn't is
  left blank there, and is a gap (below). Subjects possibly one, by weaker evidence, are linked and kept apart
  (links.py: plausible or possible; docs/plans/tentative-matches-2026-11-07.md): never merged, never a gap.
- **Figures and tables:** situating's figures (PDFs, when it ran: labels, captions, titles, "abouts", the prose
  citing them, the claims inside), and the tables read by rules (their records' titles and columns).
- **Other names** (milestone 3): the names one thing goes by, as the run found them (a glossary term reaching its
  document and its meaning, "AHU" and "air handling unit"; the model's other names, search_names), join a source's
  subjects so named, match subjects across sources the findings left apart, and join a subject's properties
  ("NPSH" and "net positive suction head").
- **Kinds** (the owner, 2026-10-30, of items or kinds: "I think we should have indices for both, where feasible."):
  tagged items by their tag's letters (P-101 and P-102 are the P items), named by the word their names most share
  ("pump"); items named with a number by the name without it ("Room 104" and "Room 105": Room); a kind of two items
  or more, with how many of its items give each property (what one of them leaves out shows: siblings' gaps).
  Grouped by what their items are (milestone 3, 2026-11-01; the owner: "Let's try your recommendations on the
  decisions."): a drawing set's sheets one kind, "sheet", by the shape its title blocks print their numbers in
  (G-001: letters, a dash, three digits), whatever their letters; a claim naming several items as rows read as one
  ("A-102 A-201") counted for none of them, and a subject whose claims all do left out of kinds and marked; a list's
  ("SRB0, SRB1 and SRB3": a statement about each) counted for each, an item named only in it a subject of its own;
  two of a kind's properties one where three of its items or more give both, alike each time ("sheet name" and
  "drawing title"). Where the confirm_kinds lever ran (kindcheck.py), the model's names and moves.
- **The glossary** (glossary.py, when read): each term once, its meanings with where each is given; in a comparison
  each source's, a term the sources define differently marked.
- **What it doesn't give** (gaps; docs/plans/single-document-analysis-2026-10-28.md, milestone 5, by code): in a
  comparison, a property another source gives a matched subject that a source describing it doesn't (milestone 7;
  the owner's clearest kind: "Project A tells you a bunch about Bob including his favorite food, while Project B
  tells you about Bob but did not mention his favorite food"); a property most of an item's siblings give that it
  doesn't (each source's own); a figure, table or sheet cited and not found
  (situating's unresolved references); a value given as a placeholder ("TBD", "to be confirmed"); and, where the
  second pass ran (dossiers.py), what it says a subject likely lacks. Each weak: where it was expected and why, never
  a finding.
- **Inconsistencies** (milestone 4): two claims of one subject the second pass says contradict each other (other
  values for the same thing under the same conditions), each with both claims and its reason.
"""
import os
import re
from collections import Counter, defaultdict

from .align import Side, shape
from .glossary import natural
from .terms import fold
from .schema import Evidence
from .values import singular

# The relations a finding pairs two claims of one subject by: unrelated pairs say they aren't.
PAIRING = ("different", "equivalent", "complementary", "uncertain")
# The model's matches of subjects across sources (crossmatch.py) that make them one, as the index says it: a state of
# one item stays apart.
MATCHED = {"same": "the same item", "corresponding": "the corresponding element"}
# Where in its file a claim is, as each format names it (report.py's PLACES, without a PDF's box).
PLACES = {"pdf": lambda loc: f"page {loc['page']}",
          "text": lambda loc: f"lines {loc['lines'][0]}–{loc['lines'][1]}",
          "docx": lambda loc: f"paragraphs {loc['paragraphs'][0]}–{loc['paragraphs'][1]}",
          "pptx": lambda loc: f"slide {loc['page']}",
          "xlsx": lambda loc: f"sheet {loc['sheet']}, cells {loc['cells']}",
          "csv": lambda loc: f"lines {loc['file_lines'][0]}–{loc['file_lines'][1]}"}

def plain(text):
    return " ".join(str(text).split())

class Where:
    """Where a claim was read, in words a reader finds it by: "spec.pdf, page 3", "notes.md, lines 4–6" (its file's
    first path)."""
    def __init__(self, data):
        self.path, self.source = {}, {}
        for f in sorted(data.get("files", []), key=lambda f: (f["source"], f["path"])):
            self.path.setdefault(f["content"], f["path"])
            self.source.setdefault(f["content"], f["source"])

    def __call__(self, e):
        loc = e["locator"]
        try:
            place = PLACES[loc.get("format", "pdf")](loc)
        except (KeyError, IndexError, TypeError):
            place = ""
        return self.path.get(e["content"], e["content"]) + (f", {place}" if place else "")

def subjects_of(claims):
    """One source's subjects: [(key, display name, [claims])], alignment's items."""
    if not claims:
        return []
    side = Side([Evidence.model_validate(c) for c in claims])
    return [(key, side.display(key), [claims[i] for i in idx]) for key, idx in side.items.items()]

def alias_key(name):
    return fold(name).rstrip(".")

NAMES = ("document", "discipline")  # the reaches a glossary term is another name at: not a sheet's symbol alone

def aliases(data):
    """The names one thing goes by, as the run found them: each glossary term reaching its document (or a
    discipline's sheets) with its meaning (a mark described, or a meaning of more than 80 characters, isn't a name),
    and the model's other names (the search_names lever's groups), a property's joined only where every two of the
    names joined can be one property (kin). Between proposals, where the other_names_fit setting says (tentative
    matches, milestone 16), the model's groups don't chain two names one source gives into one unless a group holds
    both (seeds 9 and 11: "Option B: chlorine contact" and "chlorine", each grouped with the other design's "sodium
    hypochlorite", became one subject). A function giving a name its group's first name (folded, the least A to Z),
    or None for a name in no group."""
    from .terms import drawn
    parent, members = {}, {}
    apart = None
    if (data.get("settings") or {}).get("other_names_fit") and data.get("mode") == "proposals":
        where, given = Where(data), defaultdict(set)
        for e in data.get("evidence", []):
            given[alias_key(e["entity"])].add(where.source.get(e["content"], ""))
        grouped = {frozenset((alias_key(x), alias_key(y))) for group in (data.get("synonyms") or {}).get("items", [])
                   for x in group for y in group}
        apart = lambda x, y: (x == y or not given.get(x, set()) & given.get(y, set())  # noqa: E731
                              or frozenset((x, y)) in grouped)

    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(a, b, may=None):
        ra, rb = sorted((root(a), root(b)), key=natural)
        if ra == rb or may and not all(may(x, y) for x in members.get(ra, {ra}) for y in members.get(rb, {rb})):
            return
        parent[rb] = ra
        members[ra] = members.get(ra, {ra}) | members.pop(rb, {rb})
    for t in (data.get("glossary") or {}).get("terms", []):
        if t.get("reach", "document") in NAMES and not drawn(t["term"]) and len(t["meaning"]) <= 80:
            join(alias_key(t["term"]), alias_key(t["meaning"]))
    for kind in ("items", "properties"):
        for group in (data.get("synonyms") or {}).get(kind, []):
            for name in group[1:]:
                join(alias_key(group[0]), alias_key(name), kin if kind == "properties" else apart)
    return lambda name: root(alias_key(name)) if alias_key(name) in parent else None

def words_of(name):
    return {singular(w) for w in re.findall(r"[a-z0-9]+", fold(name))}

def kin(a, b):
    """Whether two property names the model gave as other names can be one property: names in other words ("rated
    output", "nominal power"), or the same words written otherwise ("SIZE W", "size width"; "transmit timing",
    "transmission timing"); not a name and a more general one ("pressure", "maximum transient pressure"), nor two
    adding words of their own to those they share ("maximum transient pressure", "minimum transient pressure"; "DRB
    connection target", "SRB connection target"), though the model is asked for neither (synonyms.PROMPT): joined,
    planted reports' maximum and minimum pressures were one property whose values differed."""
    x, y = words_of(a), words_of(b)
    mine, theirs = x - y, y - x
    if not x & y or not mine and not theirs:
        return True
    if not mine or not theirs or len(mine) != len(theirs):
        return False
    stem = lambda p, q: p.startswith(q) or q.startswith(p) or len(os.path.commonprefix([p, q])) >= 5  # noqa: E731
    return all(any(stem(p, q) for q in theirs) for p in mine)

def renamed(subjects, alias):
    """One source's subjects, those named as other names of one thing joined (the first's key and name, their claims
    together)."""
    out, at = [], {}
    for key, name, cs in subjects:
        a = alias(name) or next((alias(c["entity"]) for c in cs if alias(c["entity"])), None)
        if a is not None and a in at:
            k, n, prior = out[at[a]]
            out[at[a]] = (k, n, prior + cs)
            continue
        if a is not None:
            at[a] = len(out)
        out.append((key, name, cs))
    return out

def matched(found, findings, sources, alias=lambda name: None, by_findings=True, matches=(), firm=None, rank=None):
    """The sources' subjects matched across them: [{source: (key, name, claims)}], each subject once. Two sources'
    subjects are one where the findings pair their claims (by_findings: revisions), the most pairs first and one to
    one; else where they're keyed alike (a tag, or the same words), or named as other names of one thing (alias);
    then as the model matched them (matches: [((source, name), (source, name), relation)], crossmatch.py), each alone
    till then; the rest alone. firm: whether two sources' subjects keyed alike are one ((source, (key, name, claims))
    each; the keyed_links and other_names_fit levers', firm_keyed): those it says aren't stay alone, each saying the
    other's (source, key) as "keyed". rank: the subjects keyed alike, in the order they're taken (a source's first
    joins, the rest stand apart)."""
    of = {c["id"]: (source, key) for source in sources for key, _, claims in found[source] for c in claims}
    by = {(source, key): (key, name, claims) for source in sources for key, name, claims in found[source]}
    links = Counter()
    for f in findings if by_findings else ():
        a, b = of.get(f.get("a")), of.get(f.get("b"))
        if f.get("relation") in PAIRING and a and b and a[0] != b[0]:
            links[tuple(sorted((a, b)))] += 1
    merged, joined = [], {}
    for (a, b), _ in sorted(links.items(), key=lambda x: (-x[1], natural(x[0][0][1]), natural(x[0][1][1]))):
        if a in joined or b in joined:
            continue
        group = {a[0]: by[a], b[0]: by[b], "matched_by": "findings"}
        joined[a] = joined[b] = group
        merged.append(group)
    keyed = defaultdict(list)
    for source in sources:
        for key, name, _ in found[source]:
            if (source, key) not in joined:
                keyed[alias(name) or key].append((source, key))
    for members in keyed.values():
        members = rank(members) if rank else members
        apart = []
        group = {"matched_by": ("name" if len({k for _, k in members}) == 1 else "other names")
                 if len({s for s, _ in members}) > 1 else ""}
        for source, k in members:  # one a source: a second one alike stands apart (named alike, or other names)
            if source in group:
                apart.append({source: by[(source, k)], "matched_by": ""})
            else:
                group[source] = by[(source, k)]
        two = [source for source in sources if source in group]
        if firm is not None and len(two) == 2 and not firm(*((source, group[source]) for source in two)):
            a, b = two  # keyed alike alone: apart, a link's (links: "keyed"), the model's to match
            merged += [{a: group[a], "matched_by": "", "keyed": (b, group[b][0])},
                       {b: group[b], "matched_by": "", "keyed": (a, group[a][0])}, *apart]
            continue
        merged += [group, *apart]
    named = {(source, name): k for source in sources for k, name, _ in found[source]}
    for a, b, relation in matches:
        ka, kb = named.get(a), named.get(b)
        if ka is None or kb is None or a[0] == b[0]:
            continue
        ga, gb = (next((g for g in merged if g.get(x[0], (None,))[0] == k), None) for x, k in ((a, ka), (b, kb)))
        if ga is None or gb is None or ga["matched_by"] or gb["matched_by"]:
            continue  # each alone till then
        if ga.get("keyed") == (b[0], kb):
            continue  # keyed alike and kept apart (firm): the model, shown the key, says nothing more
        ga.update({k: v for k, v in gb.items() if k not in ("matched_by", "keyed")},
                  matched_by=f"model: {MATCHED[relation]}")
        ga.pop("keyed", None)
        merged.remove(gb)
    return merged

def firm_keyed(found, data, sources, contest=True, fit=False):
    """(firm, rank) for matched: whether two proposals' subjects keyed alike are one, and the order a key's subjects
    are taken in (tentative matches, milestones 14 and 16).

    - contest (the keyed_links lever; the gotchas review, item 2: "P-101 in two designs is a numbering habit, not
      identity"): one unless their properties say otherwise, either having more properties in common with another of
      the other source's subjects than with the other, two or more (one alike is too little, as for a link). A tag,
      the same words or other names are the names' evidence; the judge and the model, shown the two because they're
      keyed alike or by names that hold the key, add nothing of their own (Birch Hollow's knob, 2026-11-09: each of
      its wrong groups held by the judge's "different", then by the model picking the tag it was shown over a decoy);
      a second family required of every group split right ones too (seed 1, offline: Pine Ridge's 57 right groups
      19).
    - fit (the other_names_fit lever; the gotchas review, item 1: other names chain and ignore disagreement): two
      subjects joined by other names alone (their keys differ) one only where they share a property, by name or
      alike (links' property names); and of a source's subjects one key holds, the one sharing the most properties
      with the other source's taken first. On seeds 1 and 8 to 11 every right group by other names shared one (288);
      the wrong ones shared none (3: the model calling a chlorine contact basin "sodium hypochlorite") or were the
      key's wrong subject of two (2: the chlorine feed beside it).

    Those firm says aren't stay apart, a plausible link (the owner, 2026-11-09, asked whether plausible or possible:
    "A plausible link is good."), each alone for the model's match to another."""
    from .links import _name_alike
    properties = {source: {key: {plain(c["attribute"]) for c in cs} for key, _, cs in found[source]}
                  for source in sources}

    def alike(p, q):
        return bool(p & q) or any(_name_alike([x], [y]) for x in p for y in q)

    def firm(a, b):
        (sa, (ka, _, _)), (sb, (kb, _, _)) = a, b
        mine, theirs = properties[sa][ka], properties[sb][kb]
        if fit and ka != kb and mine and theirs and not alike(mine, theirs):
            return False
        common = len(mine & theirs)
        sides = ((mine, properties[sb], kb), (theirs, properties[sa], ka))
        return not (contest and any(len(own & q) > max(common, 1) for own, others, k0 in sides
                                    for k, q in others.items() if k != k0))

    def rank(members):
        if not fit:
            return members
        shared = lambda m: max((len(properties[m[0]][m[1]] & properties[o[0]][o[1]])  # noqa: E731
                                for o in members if o[0] != m[0]), default=0)
        return sorted(members, key=lambda m: -shared(m))  # stable: ties as they were
    return firm, rank

LISTING = re.compile(r"\s*(?:,\s*(?:and|or)|,|;|&|and|or)\s*", re.IGNORECASE)  # between a list's items

def _named(entity):
    """(the items a name names, where it names two or more: their tags; "rows" or "list"), else ([], ""). Rows read as
    one ("A-102 A-201", "H-101 TITLE S-001 TITLE"): tags of one shape, apart by spaces or their titles; a list ("SRB0,
    SRB1 and SRB3"): tags apart by commas, "and" or "or". Not one thing's name holding two tags ("L2 U2N Relay UE",
    "L1/L2 Triggered Mobility": tags of other shapes, or joined by a slash), which TS 38.300's are."""
    from .align import TAG
    text = str(entity)
    found = list(TAG.finditer(text))
    tags = list(dict.fromkeys(m[0] for m in found))
    if len(tags) < 2:
        return [], ""
    between = [text[a.end():b.start()] for a, b in zip(found, found[1:])]
    if all(LISTING.fullmatch(gap) for gap in between):
        return tags, "list"
    if len({shape(t) for t in tags}) == 1 and not any("/" in gap for gap in between):
        return tags, "rows"
    return [], ""

def several(entity):
    """The items a name names where it's rows read as one ("A-102 A-201"): their tags, else []. Such a claim is
    counted for none of them in kinds: each row would give the other's title (_named)."""
    tags, how = _named(entity)
    return tags if how == "rows" else []

def listing(entity):
    """The items a list names ("SRB0, SRB1, SRB3 and other MAC CEs", "Pumps P-101 and P-102"): their tags, else [].
    A statement about each, so its claims are counted for each (listed; indexes plan, design question 6's follow-up:
    the owner, 2026-11-02, "Let's go with your recommendations on the low-hanging fruit.")."""
    tags, how = _named(entity)
    return tags if how == "list" else []

def listed(subjects, by_tag, said):
    """Each claim of a list (listing) given to every item it names, besides the one alignment keyed it by (its first):
    its value under the property its attribute names (a new one where the item has none), the item made a subject of
    its own where no claim names it alone. by_tag: {tag: the subject's index}; said: {claim id: its attribute}."""
    for i in range(len(subjects)):
        for p in subjects[i]["properties"]:
            for v in p["values"]:
                for tag in v.get("listed", []):
                    if by_tag.get(tag) == i:
                        continue
                    if tag not in by_tag:
                        by_tag[tag] = len(subjects)
                        subjects.append({"name": tag, "names": [tag], "matched_by": "", "claims": {},
                                         "properties": []})
                    other = subjects[by_tag[tag]]
                    if v["claim"] in other["claims"].get(v["source"], []):
                        continue
                    other["claims"].setdefault(v["source"], []).append(v["claim"])
                    name = said.get(v["claim"], p["name"])
                    into = next((q for q in other["properties"] if name in q["names"]), None)
                    if into is None:
                        into = {"name": name, "names": [name], "values": []}
                        other["properties"].append(into)
                        other["properties"].sort(key=lambda q: natural(q["name"]))
                    into["values"].append(dict(v))

def built(data):
    """The report's index: {"sources", "subjects", "figures"} (as report.json keeps it under "index"). Each subject:
    its name, its names as printed, how it was matched across sources, its claims by source, and its properties,
    each with every value given: {source, value, unit, conditions, claim, where}."""
    sources = [s["name"] for s in data.get("sources", [])]
    where = Where(data)
    claims = defaultdict(list)
    for e in data.get("evidence", []):
        claims[where.source.get(e["content"], "")].append(e)
    alias = aliases(data)
    found = {source: renamed(subjects_of(claims[source]), alias) for source in sources}
    paired = [(f["a"], f["b"]) for f in data.get("findings", []) if f.get("relation") in PAIRING]
    subjects, by_tag = [], {}
    matches = [((c["source"], c["subject"]), (c["other_source"], c["other"]), c["relation"])
               for c in (data.get("commentary") or {}).get("entries", [])
               if c["kind"] == "match" and c.get("relation") in MATCHED and not c.get("taken")]
    settings = data.get("settings") or {}
    firm, rank = (firm_keyed(found, data, sources, bool(settings.get("keyed_links")),
                             bool(settings.get("other_names_fit")))
                  if data.get("mode") == "proposals" and len(sources) == 2
                  and (settings.get("keyed_links") or settings.get("other_names_fit")) else (None, None))
    halves = {}  # (source, key): (its subject, the other half's (source, key)): kept apart, keyed alike (firm)
    for group in matched(found, data.get("findings", []), sources, alias, data.get("mode") != "proposals", matches,
                         firm, rank):
        mine = [(source, group[source]) for source in sources if source in group]
        names = Counter(c["entity"] for _, (_, _, cs) in mine for c in cs)
        properties = joined([c for _, (_, _, cs) in mine for c in cs], paired, alias)
        name = mine[0][1][1]  # alignment's (its claims' most given), else the most given naming it alone
        if several(name) or listing(name):  # else a list's first item by its tag, alignment's key
            name = next((n for n in sorted(names, key=lambda n: (-names[n], natural(n)))
                         if not several(n) and not listing(n)), mine[0][1][0] if listing(name) else name)
        for _, (key, _, _) in mine:
            by_tag.setdefault(key, len(subjects))
        subjects.append({
            "name": name, "names": sorted(names, key=lambda n: (-names[n], natural(n))),
            **({"several": several(name)} if several(name) else {}),
            "matched_by": group["matched_by"],
            "claims": {source: [c["id"] for c in cs] for source, (_, _, cs) in mine},
            "properties": [{"name": Counter(plain(c["attribute"]) for c in cs).most_common(1)[0][0],
                            "names": sorted({plain(c["attribute"]) for c in cs}, key=lambda n: (natural(n), n)),
                            "values": [{"source": where.source.get(c["content"], ""), "value": c["value"],
                                        "unit": c["unit"], "conditions": c.get("conditions", ""), "claim": c["id"],
                                        "where": where(c),
                                        **({"several": several(c["entity"])} if several(c["entity"]) else {}),
                                        **({"listed": listing(c["entity"])} if listing(c["entity"]) else {})}
                                       for c in cs]}
                           for _, cs in sorted(properties.items(), key=lambda x: natural(x[0]))]})
        if group.get("keyed"):
            halves[mine[0][0], mine[0][1][0]] = (subjects[-1], group["keyed"])
    listed(subjects, by_tag, {e["id"]: plain(e["attribute"]) for e in data.get("evidence", [])})
    subjects.sort(key=lambda s: (natural(s["name"]), s["names"]))
    at = {id(s): i for i, s in enumerate(subjects)}
    keyed = {tuple(sorted((at[id(s)], at[id(halves[other][0])]))) for s, other in halves.values()
             if other in halves and id(s) in at and id(halves[other][0]) in at}
    from .links import linked  # subjects possibly one, kept apart (tentative matches, milestone 2)
    for i, found in linked(data, {"sources": sources, "subjects": subjects, "keyed": keyed}).items():
        subjects[i]["links"] = found
    if (data.get("settings") or {}).get("linked_values"):  # a plausible link's other subject's values beside it,
        by = {(next(iter(s["claims"])), s["name"]): s for s in subjects if len(s["claims"]) == 1}  # kept apart
        for s in subjects:
            for link in s.get("links", []):
                other = by.get((link["source"], link["other"]))
                if link["level"] == "plausible" and other is not None:
                    link["values"] = [{"property": p["name"], "said": said(v), "where": v["where"], "claim": v["claim"]}
                                      for p in other["properties"] for v in p["values"][:1]]
    regroup = None
    if data.get("kind_check"):  # the model's names and moves (the confirm_kinds lever, kindcheck.py)
        regroup = lambda groups: regrouped(groups, subjects, data["kind_check"])  # noqa: E731
    found_kinds = kinds(subjects, sheet_shapes(data), regroup)
    return {"sources": sources, "subjects": subjects, "figures": figures(data, where), "glossary": terms(data),
            "kinds": found_kinds, "gaps": gaps(data, subjects, found_kinds, where),
            "inconsistencies": inconsistencies(data, where)}

# An item named with a number: its kind's name before the number ("Room 104", "blower 3", "Pump No. 2").
NUMBERED_NAME = re.compile(r"^(.*?[A-Za-z][A-Za-z ./&'-]*?)[\s#-]*(?:no\.?\s*)?\d+[A-Za-z]?$", re.IGNORECASE)

# An item named by a sheet's number alone: "A-101", "Sheet G-101", "DWG. NO. S-201"
SHEET_NAME = re.compile(r"^(?:(?i:sheet|drawing|dwg)\.?\s*(?:(?i:no)\.?\s*)?)?([A-Z]{1,4}-?\d{1,4}[A-Z]?)$")
JOIN_ITEMS = 3  # a kind's items giving two properties, at least, alike each time, for them to be one

def sheet_shapes(data):
    """The shapes of the sheet numbers the sources' title blocks print (situating's sheets, labelled "sheet G-001")."""
    from .align import TAG
    out = set()
    for s in (data.get("situation") or {}).values():
        for f in s.get("figures", []):
            found = TAG.search(f.get("label") or "") if f.get("kind") == "sheet" else None
            if found:
                out.add(shape(found[0]))
    return out

def given(subject, source=None):
    """{a property's name, case folded: (its name, its values' words)}: what a subject gives (in a source), from
    claims naming it alone (several)."""
    out = {}
    for p in subject["properties"]:
        values = [v for v in p["values"] if not v.get("several") and (source is None or v["source"] == source)]
        if values:
            out[p["name"].casefold()] = (p["name"], {" ".join(re.findall(r"[^\W_]+", str(v["value"]).casefold()))
                                                     for v in values} - {""})
    return out

def keys_of(k):
    """{a kind's property's name, case folded: the name it's counted under}: its names joined (properties)."""
    return {n.casefold(): p["name"].casefold() for p in k["properties"] for n in p.get("names", [p["name"]])}

def gives(subject, k, source=None):
    """The kind's properties (keys_of's) a subject gives, in a source."""
    keys = keys_of(k)
    return {keys.get(n, n) for n in given(subject, source)}

def kind_of(subject, shapes=()):
    """A subject's kind's key: ("sheet", "sheet") for an item named by a sheet's number alone in a shape the set's
    title blocks print (shapes: sheet_shapes); ("tag", its tag's letters) for a tagged item; ("name", the name without
    its number) for one named with a number; else None. Its names naming several items aren't asked."""
    from .align import TAG
    names = _alone(subject)
    if not names:
        return None
    sheets = [SHEET_NAME.match(" ".join(n.split())) for n in names]
    if shapes and all(m and shape(m[1]) in shapes for m in sheets):
        return "sheet", "sheet"
    for name in names:
        tag = TAG.search(name)
        if tag:
            return "tag", re.match(r"[A-Z]+", tag[0])[0]
    found = NUMBERED_NAME.match(" ".join(names[0].split()))
    return ("name", found[1].strip(" .#-").casefold()) if found and found[1].strip(" .#-") else None

def _alone(subject):
    """A subject's names naming it alone (not several), its name first."""
    return [n for n in dict.fromkeys([subject["name"], *subject["names"]]) if not several(n)]

def _alike(a, b):
    """Two properties' values on one item said alike: the same words, or one's within the other's, or one the
    other's start cut short in a word (_cut); not numbers alone, which two properties can share by chance."""
    from .align import NUMERIC
    if any(NUMERIC.match(x) for x in a | b):
        return False
    return any(x == y or f" {x} " in f" {y} " or f" {y} " in f" {x} " or _cut(x, y) or _cut(y, x)
               for x in a for y in b)

def _cut(x, y):
    """Whether x is y cut short within a word, two words or more of it: a title cut at a tile's edge ("hardwired
    equipment electrica" of "hardwired equipment electrical plan"; scical's sheet index, once its rows read as one
    were parted, 2026-11-02: 20 sheets' index titles and their tiles' cut ones unjoined)."""
    return len(x.split()) >= 2 and len(x) < len(y) and y.startswith(x)

def _joins(gives_):
    """{a property's name: the name it's joined under}: a kind's two properties one where JOIN_ITEMS of its items or
    more give both, alike each time (gives_: {item: given()})."""
    names = sorted({n for g in gives_.values() for n in g})
    root = {n: n for n in names}

    def find(n):
        while root[n] != n:
            n = root[n]
        return n
    for a_, a in enumerate(names):
        for b in names[a_ + 1:]:
            both = [g for g in gives_.values() if a in g and b in g]
            if len(both) >= JOIN_ITEMS and all(_alike(g[a][1], g[b][1]) for g in both):
                root[find(b)] = find(a)
    return {n: find(n) for n in names}

def _kind(name, members, subjects):
    """A kind as the index keeps it: {"kind", "subjects", "properties": [{"name", "names", "given"}]}, the most
    given first; a property named several ways (_joins) once, under the name its items most give."""
    gives_ = {i: given(subjects[i]) for i in members}
    root = _joins(gives_)
    count = Counter(n for g in gives_.values() for n in g)
    group = defaultdict(set)
    for n, r in root.items():
        group[r].add(n)
    shown = {n: next(g[n][0] for g in gives_.values() if n in g) for n in count}
    properties = []
    for r, names in group.items():
        # names alike but for case ("Height", "height") tie on natural: the name itself decides, not a set's order
        first = max(sorted(names, key=lambda n: (natural(n), n)), key=lambda n: count[n])
        properties.append({"name": shown[first], "names": [shown[n] for n in sorted(names, key=lambda n: (-count[n],
                                                                                                    natural(n), n))],
                           "given": sum(1 for g in gives_.values() if names & set(g))})
    properties.sort(key=lambda p: (-p["given"], natural(p["name"])))
    return {"kind": name, "subjects": members, "properties": properties}

def regrouped(groups, subjects, check):
    """The rules' kinds ([(name, [subject indices])]) as the model named them (check: "kind_check"): each named as it
    said, an item it moved in the kind so named (its own, where none is), kinds it named alike one. A kind it said
    nothing of keeps its rules' name. In the rules' order."""
    said = {k["rule"]: k for k in check.get("kinds", [])}
    out = {}
    for name, members in groups:
        k = said.get(name, {})
        for i in members:
            to = k.get("moved", {}).get(subjects[i]["name"]) or k.get("name") or name
            out.setdefault(fold(to), [to, []])[1].append(i)
    return [(name, sorted(set(members))) for name, members in out.values()]

def kinds(subjects, shapes=(), regroup=None):
    """The kinds of the subjects (A to Z): {"kind": its name, "subjects": [their indices in subjects], "properties":
    [{"name", "names", "given": how many of its items give it}], the most given first}, each of two items or more.
    A subject giving nothing from claims naming it alone (several) is of none. shapes: the set's sheet numbers'
    (sheet_shapes); regroup: [(name, members)] -> [(name, members)], the model's (regrouped)."""
    from .align import TAG, words
    by = defaultdict(list)
    for i, s in enumerate(subjects):
        key = kind_of(s, shapes) if given(s) else None
        if key:
            by[key].append(i)
    groups = []
    for (how, key), members in by.items():
        if len(members) < 2:
            continue
        if how == "sheet":
            name = "sheet"
        elif how == "tag":
            said = Counter(w for i in members for n in subjects[i]["names"] if not several(n)
                           for w in words(TAG.sub(" ", n)) if not any(c.isdigit() for c in w))
            # the most said word, A to Z among ties (words() gives a set, whose order the hash seed sets)
            name = f"{min(said, key=lambda w: (-said[w], w))} ({key})" if said else f"{key}-"
        else:
            name = Counter(NUMBERED_NAME.match(" ".join(_alone(subjects[i])[0].split()))[1].strip(" .#-")
                           for i in members).most_common(1)[0][0]
        groups.append((name, members))
    if regroup:
        groups = regroup(groups)
    out = [_kind(name, members, subjects) for name, members in groups if len(members) >= 2]
    return sorted(out, key=lambda k: natural(k["kind"]))

SIBLINGS = 3  # a kind's items in a source, at least, for one lacking what most of them give to be a gap
# A value that holds a place for one not given ("N/A" says it doesn't apply, not that it's missing)
PLACEHOLDER = re.compile(r"^\W*(?:TBD|TBC|TBA|TBV|TBR|to be (?:determined|confirmed|provided|advised|verified|decided|"
                         r"agreed|supplied|issued))\b", re.IGNORECASE)
GAP_KINDS = ("other_source", "siblings", "blank", "reference", "placeholder", "likely", "if_one_item")
OTHER_CLAIMS = 2  # a source's claims of a matched subject, at least, for what another source gives it to be a gap
BLANK_ROWS = 3  # a table's rows, at least, for a cell left blank to say anything
# a gap looked for, in a kind: the reader's misses first, then what the place leaves blank, those not looked for,
# and last those the place has no place for or doesn't show (dossiers.looks)
LOOKED = {"given": 0, "not_given": 1, "no_place": 3, "not_shown": 4}

def gaps(data, subjects, found_kinds, where):
    """What the sources don't give, found by code (single-document analysis, milestone 5): [{"kind": "siblings",
    "blank", "reference", "placeholder" or "likely", "source", "subject", "property", "where": where it was expected,
    "why", "claims"}]. A table's cell left blank: blanks.
    A sibling's gap is each source's own: of a kind's items in it (SIBLINGS or more), a property more than half of
    them give and this one doesn't; where expected, where its other values are. Each is weak: saying nothing isn't
    evidence of absence, and the reader may have missed what's there. A gap looked for where it would be
    (dossiers.looks) also has "looked" (where, and what was found there) and "look" (dossiers.LOOKS), and comes in its
    kind in LOOKED's order."""
    out = given_elsewhere(data, subjects, found_kinds)
    if (data.get("settings") or {}).get("link_gaps"):  # what a plausible link's other subject gives (tentative
        out += if_one_item(subjects)  # matches, milestone 7)
    if (data.get("settings") or {}).get("property_links"):  # a property possibly given under another name
        out = given_otherwise(data, subjects, out)  # (tentative matches, milestone 8)
    for k in found_kinds:
        for source in data_sources(data):
            members = [i for i in k["subjects"] if given(subjects[i], source)]
            if len(members) < SIBLINGS:
                continue
            mine = {i: gives(subjects[i], k, source) for i in members}
            named = {p["name"].casefold(): p["name"] for p in k["properties"]}
            counted = Counter(name for names in mine.values() for name in names)
            for name, n in sorted(counted.items(), key=lambda x: natural(x[0])):
                if not n * 2 > len(members) or n == len(members):
                    continue
                others = [subjects[i]["name"] for i in members if name in mine[i]]
                for i in members:
                    if name in mine[i]:
                        continue
                    at = [v for p in subjects[i]["properties"] for v in p["values"]
                          if v["source"] == source and not v.get("several")]
                    out.append({"kind": "siblings", "source": source, "subject": subjects[i]["name"],
                                "property": named[name], "where": at[0]["where"] if at else "",
                                "why": f"{n} of its {len(members)} {k['kind']} items give it: "
                                       + ", ".join(others[:4]) + (", …" if len(others) > 4 else ""),
                                "claims": [v["claim"] for v in at[:1]]})
    files = {}
    for f in sorted(data.get("files", []), key=lambda f: (f["source"], f["path"])):
        files.setdefault(f["content"], f)
    for content, s in sorted((data.get("situation") or {}).items()):
        f = files.get(content)
        for u in s.get("unresolved", []):
            out.append({"kind": "reference", "source": f["source"] if f else "", "subject": u.get("label", ""),
                        "property": "", "where": (f["path"] if f else content) + f", page {u['page']}",
                        "why": "cited, not found in the document: “" + " ".join(u.get("text", "").split())[:120]
                               + "”", "claims": list(u.get("evidence") or [])})
    for r in data.get("records", []):
        out += blanks(r, files.get(r["content"]))
    first = {}  # (source, subject): where its first value is given
    for s in subjects:
        for p in s["properties"]:
            for v in p["values"]:
                first.setdefault((v["source"], s["name"]), v["where"])
    for c in (data.get("commentary") or {}).get("entries", []):
        if c["kind"] == "missing":
            out.append({"kind": "likely", "source": c["source"], "subject": c["subject"], "property": c["text"],
                        "where": first.get((c["source"], c["subject"]), ""),
                        "why": "read together: " + (c.get("why") or "its dossier suggests it"), "claims": []})
    from .dossiers import looked_said
    looked = {(c["source"], fold(c["subject"]), fold(c["text"])): c
              for c in (data.get("commentary") or {}).get("entries", []) if c["kind"] == "looked"}
    for g in out:  # what a look where it would be found (dossiers.looks)
        c = looked.get((g["source"], fold(g["subject"]), fold(g["property"])))
        if c:
            g["looked"], g["look"] = looked_said(c), c.get("relation", "")
    for e in data.get("evidence", []):
        if PLACEHOLDER.match(str(e["value"])):
            out.append({"kind": "placeholder", "source": where.source.get(e["content"], ""), "subject": e["entity"],
                        "property": e["attribute"], "where": where(e), "why": f"given as “{e['value']}”",
                        "claims": [e["id"]]})
    # another source's: where its source gives the property for the subject's siblings first (it gives that kind of
    # property elsewhere)
    rank = {id(g): 0 if g.pop("siblings_give", True) else 1 for g in out}
    return sorted(out, key=lambda g: (GAP_KINDS.index(g["kind"]), LOOKED.get(g.get("look"), 2), rank[id(g)],
                                      g["source"], natural(g["subject"]), natural(g["property"]), natural(g["where"])))

def given_otherwise(data, subjects, gaps):
    """The gaps another source fills, and "if one item", less those whose property the lacking side plausibly gives
    under another name (links.property_alike: two families of names, values and the judge's pairing); one possibly
    given (a family) kept, its why saying so (the property_links setting's; tentative matches, milestone 8)."""
    from .links import property_alike, property_evidence
    keys, judged = property_evidence(data)
    by_name = defaultdict(list)
    for s in subjects:
        by_name[s["name"]].append(s)
    out = []
    for g in gaps:
        if g["kind"] not in ("other_source", "if_one_item"):
            out.append(g)
            continue
        mine = [p for s in by_name.get(g["subject"], []) for p in s["properties"]
                if any(v["source"] == g["source"] for v in p["values"])]
        given = g["claims"]  # the other side's claims of the property
        best = None
        for q in mine:
            level, families = property_alike([g["property"]], given, q.get("names", [q["name"]]),
                                             [v["claim"] for v in q["values"] if v["source"] == g["source"]],
                                             keys, judged)
            if level and (best is None or (level == "plausible" and best[0] != "plausible")):
                best = (level, families, q["name"])
        if best and best[0] == "plausible":
            continue  # given under another name, plausibly
        if best:
            g = {**g, "why": g["why"] + f"; possibly given as {best[2]} ({', '.join(best[1])})"}
        out.append(g)
    return out

def if_one_item(subjects):
    """What a subject's plausible links' other subjects give that it doesn't, were they one item (the link_gaps
    setting's; docs/plans/tentative-matches-2026-11-07.md, milestone 7: links in the index explored): of a subject
    alone with OTHER_CLAIMS of its own or more, each property its linked subject gives under no name it gives; where
    expected, its first place; why, the link and the other's value; its claims, the other's. The weakest kind, never
    looked for (the owner, 2026-11-07, of plausible matches: "links and topics for now")."""
    from .links import SAID, property_keys
    by = {(next(iter(s["claims"])), s["name"]): s for s in subjects if len(s["claims"]) == 1}
    out = []
    for s in subjects:
        if len(s["claims"]) != 1:
            continue
        source = next(iter(s["claims"]))
        own = [v for p in s["properties"] for v in p["values"] if not v.get("several")]
        if len(own) < OTHER_CLAIMS:
            continue
        mine = property_keys(s)  # as the link counts properties in common (Fable's review, 2026-11-09: a property
        # counted as the link's shared evidence was emitted as its gap, names compared exactly here)
        for link in s.get("links", []):
            other = by.get((link["source"], link["other"]))
            if link["level"] != "plausible" or other is None:
                continue
            for p in other["properties"]:
                if property_keys({"properties": [p]}) & mine:
                    continue
                given_ = [v for v in p["values"] if not v.get("several")]
                if not given_:
                    continue
                v = given_[0]
                out.append({"kind": "if_one_item", "source": source, "subject": s["name"], "property": p["name"],
                            "where": own[0]["where"],
                            "why": f"if it's {SAID.get(link['relation'], 'the same as')} {other['name']} "
                                   f"({link['source']}; plausible): it gives {said(v)} ({v['where']})",
                            "claims": [x["claim"] for x in given_[:3]]})
    return out

def given_elsewhere(data, subjects, found_kinds):
    """What another source gives a matched subject that a source describing it doesn't (milestone 7): of a subject
    with claims in two sources or more, each source with OTHER_CLAIMS of its own or more, each property it gives no
    value of, under any of its names, that another source does; where expected, the subject's first place in it; why,
    the other's value and where; its claims, the other's."""
    kind_of_ = {i: k for k in found_kinds for i in k["subjects"]}
    out = []
    for i, s in enumerate(subjects):
        mine = [src for src in data_sources(data) if src in s["claims"]]
        if len(mine) < 2:
            continue
        for src in mine:
            own = [v for p in s["properties"] for v in p["values"] if v["source"] == src and not v.get("several")]
            if len(own) < OTHER_CLAIMS:
                continue
            k = kind_of_.get(i)
            for p in s["properties"]:
                if any(v["source"] == src for v in p["values"]):
                    continue
                given_ = [v for v in p["values"] if not v.get("several")]
                if not given_:
                    continue
                v = given_[0]
                name = keys_of(k).get(p["name"].casefold(), p["name"].casefold()) if k else None
                out.append({"kind": "other_source", "source": src, "subject": s["name"], "property": p["name"],
                            "where": own[0]["where"], "why": f"{v['source']} gives {said(v)} ({v['where']})",
                            "claims": [x["claim"] for x in given_[:3]],
                            "siblings_give": bool(k) and any(name in gives(subjects[j], k, src)
                                                             for j in k["subjects"] if j != i)})
    return out

def table_place(r, f):
    """Where a table is (its record; f its file), in words a reader finds it by: "a.pdf, page 2, table 3", "a.pdf,
    page 2, “Pump schedule”", "spec.docx, “Table 4 Timers”"."""
    from .records import UNTITLED
    path = f["path"] if f else r["content"]
    label = " ".join(str(r.get("label", "")).split())
    page = f", page {r['page']}" if path.lower().endswith(".pdf") and r.get("page") else ""
    return f"{path}, {label}" if UNTITLED.match(label) else f"{path}{page}" + (f", “{label}”" if label else "")

def blanks(r, f):
    """A table's cells left blank, from its record's cells (records.table_record): of BLANK_ROWS rows or more, in a
    named column more than half of them fill, each row leaving it empty, the row named by its first cell. A row of one
    cell (a section's label, a note) and one without a name (a merged cell's continuation, likely) aren't counted;
    a cell merged across reads as blank too, so each is weak."""
    cells = r.get("cells") or []
    rows = [row for row in cells[1:] if row and row[0].strip() and sum(1 for c in row if c.strip()) >= 2]
    if r.get("kind") != "table" or len(rows) < BLANK_ROWS:
        return []
    where = table_place(r, f)
    out = []
    for k, head in enumerate(cells[0]):
        given = sum(1 for row in rows if k < len(row) and row[k].strip())
        if k == 0 or not head.strip() or not len(rows) < 2 * given < 2 * len(rows):
            continue
        for row in rows:
            if k >= len(row) or not row[k].strip():
                out.append({"kind": "blank", "source": f["source"] if f else "", "subject": row[0].strip(),
                            "property": " ".join(head.split()), "where": where,
                            "why": f"left blank in its table: {given} of its {len(rows)} rows give it", "claims": []})
    return out

def inconsistencies(data, where):
    """Two claims of one subject the second pass says contradict each other (dossiers.py): [{"source", "subject",
    "claims": [a, b], "said": [each one's value], "where": [each one's place], "why", "read again": [what each one's
    place gave, read again ("" where it wasn't)]}], in the log's order."""
    from .dossiers import reread_said
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    again = {c["claims"][0]: reread_said(c) for c in (data.get("commentary") or {}).get("entries", [])
             if c["kind"] == "reread"}
    out = []
    for c in (data.get("commentary") or {}).get("entries", []):
        if c["kind"] != "relation" or c.get("relation") != "contradicts" or not all(x in evidence for x in c["claims"]):
            continue
        claims = [evidence[x] for x in c["claims"]]
        out.append({"source": c["source"], "subject": c["subject"], "claims": c["claims"],
                    "said": [" ".join(x for x in (str(e["value"]), e["unit"] if e["unit"] not in ("", "-") else "",
                                                  f"({e['conditions']})" if e.get("conditions") else "") if x)
                             for e in claims],
                    "where": [where(e) for e in claims], "why": c.get("why", ""),
                    "read again": [again.get(x, "") for x in c["claims"]]})
    return out

def said(v):
    """A value as written: its value, unit (none for "-") and conditions; a claim naming several items says so."""
    unit = "" if v["unit"] in ("", "-") else v["unit"]
    return (" ".join(x for x in (str(v["value"]), unit) if x) + (f" ({v['conditions']})" if v["conditions"] else "")
            + (f" [of {', '.join(v['several'])}]" if v.get("several") else "")
            + (f" [said of {', '.join(v['listed'])}]" if v.get("listed") else ""))

def data_sources(data):
    return [s["name"] for s in data.get("sources", [])]

def term_key(term):
    """A term as terms are told apart: case and a closing full stop folded ("TYP." is "typ")."""
    return " ".join(term.split()).casefold().rstrip(".")

def terms(data):
    """The glossary index: each term once, A to Z: {"term", "kind", "reach", "meanings": [{source, meaning, where,
    how, block, reach[, sheet][, discipline]}], "differs" where two sources' meanings reaching their documents (or the
    same discipline's sheets) share none, "consistent": n where a sheet's term means the same on n sheets (two or
    more)}. A term reaches its document if any of its meanings does, else its disciplines' sheets, else its sheets: a
    sheet's symbol says little beyond it unless it's consistent (the owner, 2026-10-30: "a legend that is `[red
    square] = Foo` isn't much useful beyond that diagram unless unusually consistent")."""
    by = defaultdict(list)
    for t in (data.get("glossary") or {}).get("terms", []):
        by[term_key(t["term"])].append(t)
    out = []
    for _, ts in sorted(by.items(), key=lambda x: natural(x[0])):
        said = defaultdict(lambda: defaultdict(set))  # its scope (None: the document): source: meanings
        for t in ts:
            if t.get("reach", "document") in NAMES:
                said[t.get("discipline")][t["source"]].add(fold(t["meaning"]).rstrip("."))
        differs = any(len(by) > 1 and not set.intersection(*by.values()) for by in said.values())
        sheets = defaultdict(set)
        for t in ts:
            if t.get("reach") == "sheet":
                sheets[fold(t["meaning"]).rstrip(".")].add((t["content"], t["where"]))
        alike = max(map(len, sheets.values()), default=0)
        reaches = {t.get("reach", "document") for t in ts}
        reach = next(r for r in ("document", "discipline", "sheet") if r in reaches)
        out.append({"term": Counter(t["term"] for t in ts).most_common(1)[0][0],
                    "kind": Counter(t["kind"] for t in ts).most_common(1)[0][0], "reach": reach,
                    "meanings": [{k: t[k] for k in ("source", "meaning", "where", "how", "block", "reach", "sheet",
                                                    "discipline")
                                  if k in t} | {"reach": t.get("reach", "document")} for t in ts],
                    **({"differs": True} if differs else {}),
                    **({"consistent": alike} if reach == "sheet" and alike >= 2 else {})})
    return out

def reach_said(t):
    """Where a term holds, in words, beside its meanings: "" for its document; "S sheets only"; "alike on 3 sheets";
    "sheet E-201 only"."""
    if t.get("reach", "document") == "document":
        return ""
    if t["reach"] == "discipline":
        return ", ".join(dict.fromkeys(f"{m['discipline']} sheets" for m in t["meanings"] if m.get("discipline"))) \
            + " only"
    if t.get("consistent"):
        return f"alike on {t['consistent']} sheets"
    return ", ".join(dict.fromkeys(m.get("sheet", "") for m in t["meanings"])) + " only"

def where_said(m):
    """Where a meaning is given, and the sheets it holds for where that's its discipline's: "set.pdf, page 23; S
    sheets"."""
    return m["where"] + (f"; {m['discipline']} sheets" if m.get("reach") == "discipline" else "")

def joined(claims, paired, alias=lambda name: None):
    """A subject's claims by property: {its first name, folded: [claims]}, a property's names one where the findings
    pair claims of both (paired: [(claim id, claim id)]), or where they're other names of one thing (alias)."""
    key = {c["id"]: plain(c["attribute"]).casefold() for c in claims}
    parent = {k: k for k in key.values()}
    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    def join(a, b):
        ra, rb = sorted((root(a), root(b)), key=natural)
        parent[rb] = ra
    for a, b in paired:
        if a in key and b in key:
            join(key[a], key[b])
    named = {}  # a group of other names: the first property so named
    for c in claims:
        a = alias(c["attribute"])
        if a is not None:
            join(named.setdefault(a, key[c["id"]]), key[c["id"]])
    out = defaultdict(list)
    for c in claims:
        out[root(key[c["id"]])].append(c)
    return out

def figures(data, where):
    """The report's figures and tables: situating's figures, and the tables read by rules its figures don't list (by
    page and label), in file and page order."""
    out, seen = [], set()
    for content, x in sorted(data.get("situation", {}).items()):
        for f in x.get("figures", []):
            seen.add((content, f["page"], (f.get("label") or "").casefold()))
            out.append({"source": where.source.get(content, ""), "file": where.path.get(content, content),
                        "content": content, "page": f["page"], "kind": f.get("kind", "figure"),
                        "label": f.get("label") or "", "title": f.get("title") or f.get("caption") or "",
                        "about": f.get("about", ""), "claims": list(f.get("claims", [])),
                        "cited": len(f.get("references", []))})
    tables = defaultdict(list)
    for e in data.get("evidence", []):
        for r in e.get("records", []):
            tables[e["content"], r].append(e["id"])
    for r in data.get("records", []):
        if r["kind"] != "table":
            continue
        key = (r["content"], r.get("page"), (r.get("label") or "").casefold())
        if key in seen:
            continue
        seen.add(key)
        out.append({"source": where.source.get(r["content"], ""), "file": where.path.get(r["content"], r["content"]),
                    "content": r["content"], "page": r.get("page"), "kind": "table", "label": r.get("label") or "",
                    "title": ", ".join(r.get("items", [])[:8]), "about": "", "claims": tables[r["content"], r["id"]],
                    "cited": 0})
    out.sort(key=lambda f: (f["source"], natural(f["file"]), f["page"] if f["page"] is not None else -1,
                            natural(f["label"])))
    return out

def properties(index):
    """The properties index: each property name (as subjects' properties name it), the subjects giving it and their
    values: [{"name", "subjects": [{"subject", "values"}]}], A to Z."""
    by = defaultdict(list)
    for s in index["subjects"]:
        for p in s["properties"]:
            by[p["name"].casefold()].append((p["name"], s["name"], p["values"]))
    return [{"name": Counter(n for n, _, _ in rows).most_common(1)[0][0],
             "subjects": [{"subject": subject, "values": values} for _, subject, values in rows]}
            for _, rows in sorted(by.items(), key=lambda x: natural(x[0]))]
