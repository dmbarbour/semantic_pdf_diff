"""A report's claims as Markdown chunks for a RAG system's ingest (docs/plans/single-source-outputs-2026-09-23.md,
feature 2, milestone 2): `semantic-pdf-diff export`. The target ingest tool keeps little metadata and cuts its text into
512-token chunks, so each chunk is sized under that and says in its own words where it came from.

- **A chunk a section** (or a part of one, CHUNK characters at most): front matter (title, source, file, pages), a
  line saying where it came from (source, file, pages, section, a short content id), the section's "about", then its
  claims by subject, each with its conditions, basis, hedges and where it's read, and a short verbatim excerpt.
- **A chunk a topic** (or a part of one; the owner, 2026-10-31: "The proposed next steps seem good to me. Please
  proceed."): the topics the report is browsed by, each its claims by subject, from every file and section, each
  claim naming its file and place.
- **A comparison's findings:** a chunk of findings at a time, by what was found (they differ, uncertain, they
  complement each other, they agree), each with both claims and where each is read, the judge's reason and the
  explanation; then each source's claims with no counterpart in the other.
- **Discovery chunks:** the subjects A to Z, the figures and tables, the glossary, what the source doesn't give and,
  where the second pass found any, its inconsistencies, each pointing to the chunks holding what it names.
- **Named by content:** each file's name is its text's hash, so an unchanged chunk keeps its name from one export to
  the next and a changed one gets a new one; nothing is deleted (the user manages the corpus: decision of 2026-09-23).
- **index.md:** every chunk with its title, and how the export was made (the tool's version, the report's date and
  mode, its models, its coverage).
"""
import hashlib
import json
from collections import defaultdict

CHUNK = 1600     # characters of a chunk's claims, about (~400 tokens; the ingest tool cuts 512 with 128 overlapping)
EXCERPT = 120    # characters of a claim's quote shown, at most

def name_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] + ".md"

def front(**fields):
    return "---\n" + "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in fields.items() if v) + "---\n"

# A format's places, and the locator's key holding them: (one, many, key); a PDF's pages by default
PLACES = {"pdf": ("page", "pages", "page"), "pptx": ("slide", "slides", "page"),
          "docx": ("paragraph", "paragraphs", "paragraphs"), "text": ("line", "lines", "lines"),
          "csv": ("line", "lines", "file_lines")}

def numbers(loc):
    at = loc.get(PLACES.get(loc.get("format", "pdf"), PLACES["pdf"])[2])
    return [n for n in (at if isinstance(at, (list, tuple)) else [at]) if isinstance(n, int)]

def order(e):
    loc = e["locator"]
    return ((numbers(loc) or [0])[0], tuple(loc.get("bbox") or ()), e["id"])

def span(claims):
    """Where claims are, as their format names it: "pages 3–5", "paragraph 1044", "lines 12–30", "sheet Pumps"."""
    if not claims:
        return ""
    loc = claims[0]["locator"]
    if loc.get("format") == "xlsx":
        sheets = list(dict.fromkeys(str(c["locator"].get("sheet", "")) for c in claims))
        return ("sheet " if len(sheets) == 1 else "sheets ") + ", ".join(sheets)
    one, many, _ = PLACES.get(loc.get("format", "pdf"), PLACES["pdf"])
    found = sorted({n for c in claims for n in numbers(c["locator"])})
    if not found:
        return ""
    return f"{one} {found[0]}" if found[0] == found[-1] else f"{many} {found[0]}–{found[-1]}"

def claim_line(e, where=None):
    """A claim as a chunk says it: its property and value, its qualifiers, where it's read (where: as given, its
    files named where a chunk holds several files' claims; "" for none), a short excerpt."""
    unit = e["unit"] if e.get("unit") not in ("", "-", None) else ""
    said = f"{e['attribute']}: {e['value']}" + (f" {unit}" if unit else "")
    qualifiers = [x for x in (e.get("conditions"), f"basis: {e['basis']}" if e.get("basis") not in (None, "", "unknown")
                              else "", "approximate" if e.get("approximate") else "",
                              f"uncertainty: {e['uncertainty']}" if e.get("uncertainty") else "",
                              "quote not found in the source" if e.get("quote_verified") is False else "") if x]
    quote = " ".join(e.get("quote", "").split())
    excerpt = (quote if len(quote) <= EXCERPT else quote[:EXCERPT - 1].rstrip() + "…") if quote and \
        quote.casefold() not in said.casefold() else ""  # a quote that only says its value again: none
    at = span([e]) if where is None else where
    return (f"- {said}" + (f" ({'; '.join(qualifiers)})" if qualifiers else "") + (f" [{at}]" if at else "")
            + (f" — “{excerpt}”" if excerpt else ""))

def sections_of(data):
    """[(file, section or None, [claims])] in the files' and their pages' order, each section's claims together."""
    files = {}
    for f in sorted(data.get("files", []), key=lambda f: (f["source"], f["path"])):
        files.setdefault(f["content"], f)
    sections = {(s["content"], s["id"]): s for s in data.get("sections", [])}
    grouped = defaultdict(list)
    for e in data.get("evidence", []):
        grouped[e["content"], e.get("section", "")].append(e)
    first = lambda key: (files[key[0]]["source"], files[key[0]]["path"],  # noqa: E731
                         min(order(e) for e in grouped[key]))
    return [(files[c], sections.get((c, sid)), sorted(claims, key=order))
            for (c, sid), claims in sorted(grouped.items(), key=lambda x: first(x[0])) if c in files]

def detail_chunks(data, size=CHUNK):
    """[(title, text, [subjects in it])]: a chunk a section's part."""
    out = []
    for f, section, claims in sections_of(data):
        heading = " > ".join(section["heading_path"]) if section and section.get("heading_path") else ""
        about = (section or {}).get("about", "")
        by_subject = defaultdict(list)
        for e in claims:
            by_subject[" ".join(e["entity"].split())].append(e)
        blocks = []  # (subject, its text, its claims): a subject of more than a chunk's claims cut into several
        for subject, es in by_subject.items():
            current = []
            for e in es:
                if current and sum(len(claim_line(x)) + 1 for x in current) + len(claim_line(e)) > size:
                    blocks.append((subject, current))
                    current = []
                current.append(e)
            blocks.append((subject, current))
        blocks = [(subject, f"### {subject}\n\n" + "\n".join(claim_line(e) for e in es) + "\n", es)
                  for subject, es in blocks]
        parts, current = [], []
        for block in blocks:
            if current and sum(len(b[1]) for b in current) + len(block[1]) > size:
                parts.append(current)
                current = []
            current.append(block)
        if current:
            parts.append(current)
        for k, part in enumerate(parts, 1):
            pages = span([e for _, _, es in part for e in es])
            title = (heading or f["path"]) + (f" ({k} of {len(parts)})" if len(parts) > 1 else "")
            named = f["path"] if f["source"] == f["path"] else f"{f['source']} / {f['path']}"
            where = (f"Source: {named}" + (f", {pages}" if pages else "") + "."
                     + (f" Section: {heading}." if heading else "") + f" Content {f['content'][:23]}…")
            text = (front(title=f"{title} — {f['path']}" + (f", {pages}" if pages else ""), source=f["source"],
                          file=f["path"], pages=pages) + f"# {title}\n\n{where}\n\n"
                    + (f"{about}\n\n" if about and k == 1 else "") + "\n".join(b for _, b, _ in part))
            out.append((title, text, [s for s, _, _ in part]))
    return out

def place(e, files):
    """Where a claim is read, its file named: a topic's or a finding's claims come from several."""
    f = files.get(e["content"])
    return ", ".join(x for x in (f["path"] if f else "", span([e])) if x)

def placed_line(e, files):
    return claim_line(e, place(e, files))

def cut(blocks, size):
    """Blocks (text) in parts of about size characters, a block never split."""
    parts, current = [], []
    for block in blocks:
        if current and sum(len(b) + 1 for b in current) + len(block) > size:
            parts.append(current)
            current = []
        current.append(block)
    if current:
        parts.append(current)
    return parts

def by_subject(claims, files, size=CHUNK):
    """Claims as blocks, a block a subject's ("### name" and its lines), in their files' and places' order; a
    subject of more than a chunk's claims cut into several."""
    grouped = defaultdict(dict)  # a subject's: a line said (its places apart): the claim and its places
    for e in sorted(claims, key=lambda e: (files[e["content"]]["path"] if e["content"] in files else "", order(e))):
        said = grouped[" ".join(e["entity"].split())].setdefault(claim_line(e, ""), (e, []))
        said[1].append(place(e, files))  # said alike in several places (two revisions): one line, every place
    return [f"### {subject}\n\n" + "\n".join(part) + "\n" for subject, lines in grouped.items()
            for part in cut([claim_line(e, "; ".join(places)) for e, places in lines.values()], size)]

def titled(title, lead, parts, **fields):
    """[(title, text)]: a list's parts as chunks, each titled (k of n) and led alike."""
    out = []
    for k, part in enumerate(parts, 1):
        named = title + (f" ({k} of {len(parts)})" if len(parts) > 1 else "")
        out.append((named, front(title=named, **fields) + f"# {named}\n\n{lead}\n\n" + "\n".join(part)))
    return out

def topic_chunks(data, files, size=CHUNK):
    """[(title, text)]: a chunk a topic the report is browsed by (report.browsing: the model's names where it chose
    them), or a part of one: its claims by subject, across the files and sections they come from."""
    from .report import browsing
    _, placed, names = browsing(data)
    if not placed:
        return []
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    claims = defaultdict(list)
    for cid, t in placed.items():
        if cid in evidence:
            claims[t].append(evidence[cid])
    out = []
    for t, name in enumerate(names):
        if claims[t]:
            out += titled(f"Topic: {name}", f"Claims on {name}, as the report's browsing groups them, from every file "
                          "and section; each says where it's read.", cut(by_subject(claims[t], files, size), size),
                          topic=name)
    return out

FINDINGS = ("different", "uncertain", "complementary", "equivalent")
FINDING_SAID = {"different": "They differ", "uncertain": "Uncertain", "complementary": "They complement each other",
                "equivalent": "They agree"}

def alike(a, b):
    """Two claims that say the same, word for word (the report folds such agreements: report.SAME's)."""
    said = lambda e: tuple(" ".join(str(e.get(k) or "").split()).casefold()  # noqa: E731
                           for k in ("entity", "attribute", "value", "unit", "conditions", "quote"))
    return said(a) == said(b)

def finding_chunks(data, files, size=CHUNK):
    """([(title, text)], n left out): a comparison's findings, by what was found (different, uncertain,
    complementary, equivalent), each with both claims, where each is read, the judge's reason and the explanation;
    then what each source says that the other doesn't (unmatched). Agreements whose two claims say the same, word for
    word, left out and counted: the other chunks hold the claim. None for an analysis."""
    findings = data.get("findings") or []
    sources = [s["name"] for s in data.get("sources", [])]
    if not findings and not data.get("unmatched") or len(sources) != 2:
        return [], 0
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    side = lambda e: files[e["content"]]["source"] if e["content"] in files else ""  # noqa: E731
    against = f"{sources[0]} against {sources[1]}"
    out, same = [], 0
    for relation in FINDINGS:
        blocks = []
        for x in findings:
            if x.get("relation") != relation or x["a"] not in evidence or x["b"] not in evidence:
                continue
            a, b = evidence[x["a"]], evidence[x["b"]]
            if relation == "equivalent" and alike(a, b):
                same += 1
                continue
            explained = x.get("explanation") or {}
            blocks.append(f"### {' '.join(a['entity'].split())} — {a['attribute']}\n\n"
                          + f"- {side(a)}: {placed_line(a, files)[2:]}\n- {side(b)}: {placed_line(b, files)[2:]}\n"
                          + f"- {FINDING_SAID[relation]} (confidence {x.get('confidence', 0):.2g}): "
                          + " ".join(str(x.get("rationale", "")).split()) + "\n"
                          + (f"- Why it differs: {explained['kind'].replace('_', ' ')}: "
                             + " ".join(str(explained.get("rationale", "")).split()) + "\n"
                             if explained.get("kind") else ""))
        if blocks:
            out += titled(f"{FINDING_SAID[relation]}: {against}", f"Findings of comparing {against}: two claims, "
                          "one from each, judged by a model; check both against their places.", cut(blocks, size),
                          compared=against)
    unmatched = [evidence[u["id"]] for u in data.get("unmatched", []) if u.get("id") in evidence]
    for name in sources:
        mine = [e for e in unmatched if side(e) == name]
        if mine:
            other = next(s for s in sources if s != name)
            out += titled(f"Only in {name}: {against}", f"Claims of {name} with no counterpart found in {other}: "
                          "possibly added, removed or said otherwise; weak, as an absence is.",
                          cut(by_subject(mine, files, size), size), compared=against)
    return out, same

def discovery_chunks(index, located, size=CHUNK):
    """[(title, text)]: the subjects A to Z (each with the chunks holding its claims), figures and tables, the
    glossary, the gaps and inconsistencies; each list cut into chunks of about size characters."""
    lists = []
    lists.append(("Subjects A to Z", "Each subject the source describes, its properties, and the chunks holding its "
                  "claims.", [f"- **{s['name']}**: " + ", ".join(p["name"] for p in s["properties"][:12])
                              + (f" — in {', '.join(located.get(s['name'], [])[:4])}" if located.get(s["name"]) else "")
                              for s in index.get("subjects", [])]))
    lists.append(("Figures and tables", "The figures, drawing sheets and tables, where each is and what it's about.",
                  [f"- **{x['label'] or x['kind']}**" + (f" “{x['title']}”" if x.get("title") else "")
                   + f" ({x['file']}" + (f", page {x['page']}" if x.get("page") else "") + ")"
                   + (f": {x['about']}" if x.get("about") else "") for x in index.get("figures", [])]))
    lists.append(("Glossary", "The abbreviations, defined terms, symbols and conventions the source defines.",
                  [f"- **{t['term']}**: " + "; ".join(f"{m['meaning']} ({m['where']})" for m in t["meanings"])
                   for t in index.get("glossary", [])]))
    lists.append(("What it doesn't give", "Gaps found by code, each weak: where it was expected and why; the source "
                  "may say it elsewhere, and a reader may have missed it.",
                  [f"- **{g['subject']}**" + (f": {g['property']}" if g["property"] else "") + f" ({g['where']}; "
                   f"{g['why']})" for g in index.get("gaps", [])]))
    lists.append(("Inconsistencies", "Two claims of one subject that a second reading says contradict each other; "
                  "check both against their places.",
                  [f"- **{x['subject']}**: {x['said'][0]} ({x['where'][0]}) against {x['said'][1]} ({x['where'][1]})"
                   + (f"; {x['why']}" if x["why"] else "") for x in index.get("inconsistencies", [])]))
    out = []
    for title, lead, lines in lists:
        parts, current = [], []
        for line in lines:
            if current and sum(len(x) + 1 for x in current) + len(line) > size:
                parts.append(current)
                current = []
            current.append(line)
        if current:
            parts.append(current)
        for k, part in enumerate(parts, 1):
            named = title + (f" ({k} of {len(parts)})" if len(parts) > 1 else "")
            out.append((named, front(title=named) + f"# {named}\n\n{lead}\n\n" + "\n".join(part) + "\n"))
    return out

def exported(data, index, version="", size=CHUNK):
    """{file name: text}: a report's chunks and index.md."""
    files = {}
    located = defaultdict(list)
    titles = []
    for title, text, subjects in detail_chunks(data, size):
        name = name_of(text)
        files[name] = text
        titles.append((name, title))
        for s in subjects:
            located[s].append(name)
    files_of = {}
    for f in sorted(data.get("files", []), key=lambda f: (f["source"], f["path"])):
        files_of.setdefault(f["content"], f)
    found, same = finding_chunks(data, files_of, size)
    for title, text in topic_chunks(data, files_of, size) + found + discovery_chunks(index, located, size):
        name = name_of(text)
        files[name] = text
        titles.append((name, title))
    coverage = defaultdict(int)
    for r in data.get("coverage", []):
        coverage[r["status"]] += 1
    models = sorted({str(i.get("settings", {}).get("model", "")) for i in (data.get("interpreters") or {}).values()
                     if isinstance(i, dict)} - {""})
    files["index.md"] = (
        "# Export\n\n"
        + f"{len(titles)} chunks of {', '.join(s['name'] for s in data.get('sources', []))}: claims read by a model, "
          "each with where it's read; check a value against its place before relying on it.\n\n"
        + f"- Made by semantic-pdf-diff {version}" + (f" from the report of {data['created_at']}"
                                                         if data.get("created_at") else "") + "\n"
        + (f"- Models: {', '.join(models)}\n" if models else "")
        + "- Coverage: " + ", ".join(f"{n} tasks {status}" for status, n in sorted(coverage.items())) + "\n"
        + (f"- Left out: {same} agreements whose two claims say the same, word for word (the claim is in the other "
           "chunks)\n" if same else "") + "\n"
        + "## Chunks\n\n" + "".join(f"- [{title}]({name})\n" for name, title in titles))
    return files
