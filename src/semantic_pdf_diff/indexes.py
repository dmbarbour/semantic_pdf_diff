"""A report's indexes (docs/plans/indexes-and-glossaries-2026-10-29.md, milestone 1): its subjects, their properties,
and its figures and tables, built from what was read, with no model requests; one source's, or a comparison's merged.
The owner, 2026-10-29: "building indexes and glossaries, e.g. of claims, diagrams, subjects. Even for a single
document that would be useful, and it seems deeply related to the problem of comparing things regardless."

- **Subjects** are alignment's items (align.Side), a source's at a time: a tag in the entity (P-101B), else the
  entity's words; a claim named by position joins the tagged item whose values it repeats. A subject is named as its
  claims most often name it, and lists its properties, each with every value given and where.
- **In a comparison,** the sources' subjects are matched where the findings pair their claims (the most pairs first,
  one to one), else where they're keyed alike, and each is listed once with each source's values beside the others'
  (the owner: "One merged index"). A subject's properties are one where they're named alike or the findings pair
  their claims ("seating capacity" and "rider capacity"). A property one source gives a subject and another doesn't
  is left blank there: weak, never a finding.
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
- **What it doesn't give** (gaps; docs/plans/single-document-analysis-2026-10-28.md, milestone 5, by code): a property
  most of an item's siblings give that it doesn't (each source's own); a figure, table or sheet cited and not found
  (situating's unresolved references); a value given as a placeholder ("TBD", "to be confirmed"); and, where the
  second pass ran (dossiers.py), what it says a subject likely lacks. Each weak: where it was expected and why, never
  a finding.
- **Inconsistencies** (milestone 4): two claims of one subject the second pass says contradict each other (other
  values for the same thing under the same conditions), each with both claims and its reason.
"""
import os
import re
from collections import Counter, defaultdict

from .align import Side
from .glossary import natural
from .terms import fold
from .schema import Evidence
from .values import singular

# The relations a finding pairs two claims of one subject by: unrelated pairs say they aren't.
PAIRING = ("different", "equivalent", "complementary", "uncertain")
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
    names joined can be one property (kin). A function giving a name its group's first name (folded, the least A to
    Z), or None for a name in no group."""
    from .terms import drawn
    parent, members = {}, {}

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
                join(alias_key(group[0]), alias_key(name), kin if kind == "properties" else None)
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

def matched(found, findings, sources, alias=lambda name: None):
    """The sources' subjects matched across them: [{source: (key, name, claims)}], each subject once. Two sources'
    subjects are one where the findings pair their claims, the most pairs first and one to one; else where they're
    keyed alike (a tag, or the same words), or named as other names of one thing (alias); the rest alone."""
    of = {c["id"]: (source, key) for source in sources for key, _, claims in found[source] for c in claims}
    by = {(source, key): (key, name, claims) for source in sources for key, name, claims in found[source]}
    links = Counter()
    for f in findings:
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
        apart = []
        group = {"matched_by": ("name" if len({k for _, k in members}) == 1 else "other names")
                 if len({s for s, _ in members}) > 1 else ""}
        for source, k in members:  # one a source: a second one alike stands apart (named alike, or other names)
            if source in group:
                apart.append({source: by[(source, k)], "matched_by": ""})
            else:
                group[source] = by[(source, k)]
        merged += [group, *apart]
    return merged

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
    for group in matched(found, data.get("findings", []), sources, alias):
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
                            "names": sorted({plain(c["attribute"]) for c in cs}, key=natural),
                            "values": [{"source": where.source.get(c["content"], ""), "value": c["value"],
                                        "unit": c["unit"], "conditions": c.get("conditions", ""), "claim": c["id"],
                                        "where": where(c),
                                        **({"several": several(c["entity"])} if several(c["entity"]) else {}),
                                        **({"listed": listing(c["entity"])} if listing(c["entity"]) else {})}
                                       for c in cs]}
                           for _, cs in sorted(properties.items(), key=lambda x: natural(x[0]))]})
    listed(subjects, by_tag, {e["id"]: plain(e["attribute"]) for e in data.get("evidence", [])})
    subjects.sort(key=lambda s: (natural(s["name"]), s["names"]))
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

def shape(tag):
    """A tag's shape: its letters A, its digits 9 ("XA-501": "AA-999")."""
    return re.sub(r"\d", "9", re.sub(r"[A-Z]", "A", tag))

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
    """Two properties' values on one item said alike: the same words, or one's within the other's; not numbers
    alone, which two properties can share by chance."""
    from .align import NUMERIC
    if any(NUMERIC.match(x) for x in a | b):
        return False
    return any(x == y or f" {x} " in f" {y} " or f" {y} " in f" {x} " for x in a for y in b)

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
        first = max(sorted(names, key=natural), key=lambda n: count[n])
        properties.append({"name": shown[first], "names": [shown[n] for n in sorted(names, key=lambda n: (-count[n],
                                                                                                    natural(n)))],
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
            name = f"{said.most_common(1)[0][0]} ({key})" if said else f"{key}-"
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
GAP_KINDS = ("siblings", "blank", "reference", "placeholder", "likely")
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
    out = []
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
    return sorted(out, key=lambda g: (GAP_KINDS.index(g["kind"]), LOOKED.get(g.get("look"), 2), g["source"],
                                      natural(g["subject"]), natural(g["property"]), natural(g["where"])))

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
