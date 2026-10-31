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
- **The glossary** (glossary.py, when read): each term once, its meanings with where each is given; in a comparison
  each source's, a term the sources define differently marked.
- **What it doesn't give** (gaps; docs/plans/single-document-analysis-2026-10-28.md, milestone 5, by code): a property
  most of an item's siblings give that it doesn't (each source's own); a figure, table or sheet cited and not found
  (situating's unresolved references); a value given as a placeholder ("TBD", "to be confirmed"). Each weak: where
  it was expected and why, never a finding.
"""
import re
from collections import Counter, defaultdict

from .align import Side
from .glossary import natural
from .terms import fold
from .schema import Evidence

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
    and the model's other names (the
    search_names lever's groups). A function giving a name its group's first name (folded, the least A to Z), or None
    for a name in no group."""
    from .terms import drawn
    parent = {}

    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def join(a, b):
        ra, rb = sorted((root(a), root(b)), key=natural)
        parent[rb] = ra
    for t in (data.get("glossary") or {}).get("terms", []):
        if t.get("reach", "document") in NAMES and not drawn(t["term"]) and len(t["meaning"]) <= 80:
            join(alias_key(t["term"]), alias_key(t["meaning"]))
    for kind in ("items", "properties"):
        for group in (data.get("synonyms") or {}).get(kind, []):
            for name in group[1:]:
                join(alias_key(group[0]), alias_key(name))
    return lambda name: root(alias_key(name)) if alias_key(name) in parent else None

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
    subjects = []
    for group in matched(found, data.get("findings", []), sources, alias):
        mine = [(source, group[source]) for source in sources if source in group]
        names = Counter(c["entity"] for _, (_, _, cs) in mine for c in cs)
        properties = joined([c for _, (_, _, cs) in mine for c in cs], paired, alias)
        subjects.append({
            "name": mine[0][1][1], "names": sorted(names, key=lambda n: (-names[n], natural(n))),
            "matched_by": group["matched_by"],
            "claims": {source: [c["id"] for c in cs] for source, (_, _, cs) in mine},
            "properties": [{"name": Counter(plain(c["attribute"]) for c in cs).most_common(1)[0][0],
                            "names": sorted({plain(c["attribute"]) for c in cs}, key=natural),
                            "values": [{"source": where.source.get(c["content"], ""), "value": c["value"],
                                        "unit": c["unit"], "conditions": c.get("conditions", ""), "claim": c["id"],
                                        "where": where(c)} for c in cs]}
                           for _, cs in sorted(properties.items(), key=lambda x: natural(x[0]))]})
    subjects.sort(key=lambda s: (natural(s["name"]), s["names"]))
    found_kinds = kinds(subjects)
    return {"sources": sources, "subjects": subjects, "figures": figures(data, where), "glossary": terms(data),
            "kinds": found_kinds, "gaps": gaps(data, subjects, found_kinds, where)}

# An item named with a number: its kind's name before the number ("Room 104", "blower 3", "Pump No. 2").
NUMBERED_NAME = re.compile(r"^(.*?[A-Za-z][A-Za-z ./&'-]*?)[\s#-]*(?:no\.?\s*)?\d+[A-Za-z]?$", re.IGNORECASE)

def kind_of(subject):
    """A subject's kind's key: ("tag", its tag's letters) for a tagged item, ("name", the name without its number)
    for one named with a number, else None."""
    from .align import TAG
    for name in [subject["name"], *subject["names"]]:
        tag = TAG.search(name)
        if tag:
            return "tag", re.match(r"[A-Z]+", tag[0])[0]
    found = NUMBERED_NAME.match(" ".join(subject["name"].split()))
    return ("name", found[1].strip(" .#-").casefold()) if found and found[1].strip(" .#-") else None

def kinds(subjects):
    """The kinds of the subjects (A to Z): {"kind": its name, "subjects": [their indices in subjects], "properties":
    [{"name", "given": how many of its items give it}], the most given first}, each of two items or more."""
    from .align import TAG, words
    by = defaultdict(list)
    for i, s in enumerate(subjects):
        key = kind_of(s)
        if key:
            by[key].append(i)
    out = []
    for (how, key), members in by.items():
        if len(members) < 2:
            continue
        if how == "tag":
            said = Counter(w for i in members for n in subjects[i]["names"] for w in words(TAG.sub(" ", n))
                           if not any(c.isdigit() for c in w))
            name = f"{said.most_common(1)[0][0]} ({key})" if said else f"{key}-"
        else:
            name = Counter(NUMBERED_NAME.match(" ".join(subjects[i]["name"].split()))[1].strip(" .#-")
                           for i in members).most_common(1)[0][0]
        given = Counter(p["name"].casefold() for i in members for p in subjects[i]["properties"])
        named = {p["name"].casefold(): p["name"] for i in members for p in subjects[i]["properties"]}
        out.append({"kind": name, "subjects": members,
                    "properties": [{"name": named[k], "given": n}
                                   for k, n in sorted(given.items(), key=lambda x: (-x[1], natural(x[0])))]})
    return sorted(out, key=lambda k: natural(k["kind"]))

SIBLINGS = 3  # a kind's items in a source, at least, for one lacking what most of them give to be a gap
# A value that holds a place for one not given ("N/A" says it doesn't apply, not that it's missing)
PLACEHOLDER = re.compile(r"^\W*(?:TBD|TBC|TBA|TBV|TBR|to be (?:determined|confirmed|provided|advised|verified|decided|"
                         r"agreed|supplied|issued))\b", re.IGNORECASE)
GAP_KINDS = ("siblings", "reference", "placeholder")

def gaps(data, subjects, found_kinds, where):
    """What the sources don't give, found by code (single-document analysis, milestone 5): [{"kind": "siblings",
    "reference" or "placeholder", "source", "subject", "property", "where": where it was expected, "why", "claims"}].
    A sibling's gap is each source's own: of a kind's items in it (SIBLINGS or more), a property more than half of
    them give and this one doesn't; where expected, where its other values are. Each is weak: saying nothing isn't
    evidence of absence, and the reader may have missed what's there."""
    out = []
    for k in found_kinds:
        for source in data_sources(data):
            members = [i for i in k["subjects"] if subjects[i]["claims"].get(source)]
            if len(members) < SIBLINGS:
                continue
            gives, named = {}, {}
            for i in members:
                mine = [p for p in subjects[i]["properties"] if any(v["source"] == source for v in p["values"])]
                gives[i] = {p["name"].casefold() for p in mine}
                named.update({p["name"].casefold(): p["name"] for p in mine})
            given = Counter(name for names in gives.values() for name in names)
            for name, n in sorted(given.items(), key=lambda x: natural(x[0])):
                if not n * 2 > len(members) or n == len(members):
                    continue
                others = [subjects[i]["name"] for i in members if name in gives[i]]
                for i in members:
                    if name in gives[i]:
                        continue
                    at = [v for p in subjects[i]["properties"] for v in p["values"] if v["source"] == source]
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
    for e in data.get("evidence", []):
        if PLACEHOLDER.match(str(e["value"])):
            out.append({"kind": "placeholder", "source": where.source.get(e["content"], ""), "subject": e["entity"],
                        "property": e["attribute"], "where": where(e), "why": f"given as “{e['value']}”",
                        "claims": [e["id"]]})
    return sorted(out, key=lambda g: (GAP_KINDS.index(g["kind"]), g["source"], natural(g["subject"]),
                                      natural(g["property"]), natural(g["where"])))

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
