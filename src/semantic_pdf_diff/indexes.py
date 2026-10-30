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
- **The glossary** (glossary.py, when read): each term once, its meanings with where each is given; in a comparison
  each source's, a term the sources define differently marked.
"""
from collections import Counter, defaultdict

from .align import Side
from .glossary import fold, natural
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

def matched(found, findings, sources):
    """The sources' subjects matched across them: [{source: (key, name, claims)}], each subject once. Two sources'
    subjects are one where the findings pair their claims, the most pairs first and one to one; else where they're
    keyed alike (a tag, or the same words); the rest alone."""
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
        for key, _, _ in found[source]:
            if (source, key) not in joined:
                keyed[key].append((source, key))
    for key, members in keyed.items():
        group = {"matched_by": "name" if len({s for s, _ in members}) > 1 else ""}
        for source, k in members:  # (a source's items are keyed once each: Side)
            group[source] = by[(source, k)]
        merged.append(group)
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
    found = {source: subjects_of(claims[source]) for source in sources}
    paired = [(f["a"], f["b"]) for f in data.get("findings", []) if f.get("relation") in PAIRING]
    subjects = []
    for group in matched(found, data.get("findings", []), sources):
        mine = [(source, group[source]) for source in sources if source in group]
        names = Counter(c["entity"] for _, (_, _, cs) in mine for c in cs)
        properties = joined([c for _, (_, _, cs) in mine for c in cs], paired)
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
    return {"sources": sources, "subjects": subjects, "figures": figures(data, where), "glossary": terms(data)}

def term_key(term):
    """A term as terms are told apart: case and a closing full stop folded ("TYP." is "typ")."""
    return " ".join(term.split()).casefold().rstrip(".")

def terms(data):
    """The glossary index: each term once, A to Z: {"term", "kind", "meanings": [{source, meaning, where, how,
    block}], "differs" where two sources' meanings share none}."""
    by = defaultdict(list)
    for t in (data.get("glossary") or {}).get("terms", []):
        by[term_key(t["term"])].append(t)
    out = []
    for _, ts in sorted(by.items(), key=lambda x: natural(x[0])):
        said = defaultdict(set)
        for t in ts:
            said[t["source"]].add(fold(t["meaning"]).rstrip("."))
        differs = len(said) > 1 and not set.intersection(*said.values())
        out.append({"term": Counter(t["term"] for t in ts).most_common(1)[0][0],
                    "kind": Counter(t["kind"] for t in ts).most_common(1)[0][0],
                    "meanings": [{k: t[k] for k in ("source", "meaning", "where", "how", "block")} for t in ts],
                    **({"differs": True} if differs else {})})
    return out

def joined(claims, paired):
    """A subject's claims by property: {its first name, folded: [claims]}, a property's names one where the findings
    pair claims of both (paired: [(claim id, claim id)])."""
    key = {c["id"]: plain(c["attribute"]).casefold() for c in claims}
    parent = {k: k for k in key.values()}
    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k
    for a, b in paired:
        if a in key and b in key:
            ra, rb = sorted((root(key[a]), root(key[b])), key=natural)
            parent[rb] = ra
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
