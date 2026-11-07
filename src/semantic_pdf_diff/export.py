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
- **A chunk a subject** of two claims or more (or a part of one; the owner, 2026-10-31: "Your recommended path seems
  reasonable"): everything the source says about it, from every file and section, by property, and what it doesn't
  give; **a chunk a kind**, its items by property as a Markdown table (the index's kinds).
- **The second pass's notes** (dossiers.py) under each claim they're about, in its section's and its subject's
  chunks (a topic's leave them to those): what it's restated or contradicted by, suspected, inferred, and what its
  place gave read again; ours, and said so.
- **Discovery chunks:** the subjects A to Z, the figures and tables, the glossary, what the source doesn't give and,
  where the second pass found any, its inconsistencies, each pointing to the chunks holding what it names.
- **Named by content:** each file's name is its text's hash, so an unchanged chunk keeps its name from one export to
  the next and a changed one gets a new one (the user manages the corpus: decision of 2026-09-23). The folder holds
  one export alone: an earlier export's chunks this one doesn't hold are removed, and a folder holding other files
  refused (the owner, 2026-10-31: "Each export or report should be logically fresh from the sources, not
  history-dependent.").
- **index.md:** every chunk with its title, and how the export was made (the tool's version, the report's date and
  mode, its models, its coverage).
- **chunks.json, asked for** (`--json`; the owner, 2026-11-02: "Let's go with your recommendations on the low-hanging
  fruit."): every chunk as an object, its front matter's fields apart from its text, for a system ingesting JSON (the
  ingest tool takes JSON, not JSONL); the same chunks, so its names are the files'.
- **A delta, asked for** (`--since FOLDER`, an earlier export's): only the chunks the earlier one doesn't hold, and in
  index.md (and chunks.json) the names of its chunks this one doesn't: what a corpus holding the earlier needs added
  and removed to hold this one. Chunks are named by their text, so a chunk unchanged is in neither.
"""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from .indexfiles import GAP_TITLES, KIND_COLUMNS, cell_md, kind_cell, kind_property

CHUNK = 1600     # characters of a chunk's claims, about (~400 tokens; the ingest tool cuts 512 with 128 overlapping)
EXCERPT = 120    # characters of a claim's quote shown, at most

def name_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] + ".md"

NAMED = re.compile(r"[0-9a-f]{16}\.md")  # a chunk's name (name_of)
JSON = "chunks.json"  # every chunk as JSON, where asked for (as_json)
LISTED = re.compile(r"^- \[(.*)\]\(([0-9a-f]{16}\.md)\)$", re.MULTILINE)  # a chunk's line in index.md

def written(out, files):
    """files ({name: text}) written into out, an empty folder or an earlier export's, and the earlier export's chunks
    this one doesn't hold removed: an export is made from its report alone, never from what an earlier one left (the
    owner, 2026-10-31: "Each export or report should be logically fresh from the sources, not history-dependent.").
    A folder holding a file no export writes is refused, nothing written; hidden files are left alone. Returns how
    many were removed."""
    out.mkdir(parents=True, exist_ok=True)
    index = out / "index.md"
    foreign = sorted(p.name for p in out.iterdir() if not p.name.startswith(".") and not (
        p.is_file() and (NAMED.fullmatch(p.name) or p.name in ("index.md", JSON))))
    if index.is_file() and not index.read_text(encoding="utf-8").startswith("# Export\n"):
        foreign.append(index.name)
    if foreign:
        raise ValueError(f"{out} holds files an export doesn't write ({', '.join(foreign[:3])}"
                         f"{', ...' if len(foreign) > 3 else ''}): export into an empty folder, or an earlier "
                         "export's; nothing was written")
    stale = [p for p in out.iterdir() if (NAMED.fullmatch(p.name) or p.name == JSON) and p.name not in files]
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    for p in stale:
        p.unlink()
    return len(stale)

def chunks_of(files):
    """[(name, title)] of an export's chunks, in its index.md's order."""
    return [(name, title) for title, name in LISTED.findall(files.get("index.md", ""))]

def as_json(files, version="", gone=()):
    """chunks.json's text: {"format", "made_by", "chunks": [{"name", "title", "fields": the front matter's, "text":
    below it}], and "gone" in a delta}."""
    chunks = []
    for name, title in chunks_of(files):
        head, body, fields = "", files[name], {}
        if body.startswith("---\n"):
            head, _, body = body[4:].partition("---\n")
        for line in head.splitlines():
            key, _, value = line.partition(": ")
            fields[key] = json.loads(value)
        chunks.append({"name": name, "title": title, "fields": fields, "text": body})
    return json.dumps({"format": 1, "made_by": f"semantic-pdf-diff {version}".strip(), "chunks": chunks,
                       **({"gone": list(gone)} if gone else {})}, indent=1, ensure_ascii=False) + "\n"

def earlier(folder):
    """The chunks an earlier export holds: the names its index.md lists, and its chunks' files."""
    folder = Path(folder)
    index = folder / "index.md"
    if not folder.is_dir() or not (index.is_file() and index.read_text(encoding="utf-8").startswith("# Export\n")):
        raise ValueError(f"{folder} isn't an export's folder (no index.md an export wrote)")
    listed = {name for _, name in LISTED.findall(index.read_text(encoding="utf-8"))}
    return listed | {p.name for p in folder.iterdir() if NAMED.fullmatch(p.name)}

def delta(files, before, since):
    """{file name: text}: the chunks of files an earlier export (before: its chunks' names, from the folder since)
    doesn't hold, and an index.md listing them, then the earlier's chunks gone; and the names gone."""
    new = [(name, title) for name, title in chunks_of(files) if name not in before]
    gone = sorted(before - set(files))
    head = files["index.md"].split("## Chunks\n", 1)[0].rstrip("\n")
    index = (head + f"\n- A delta against the export in {since}: {len(new)} chunks new, {len(gone)} of its "
             "chunks gone; the chunks it holds alike aren't here\n\n"
             + "## Chunks\n\n" + "".join(f"- [{title}]({name})\n" for name, title in new)
             + ("\n## Gone\n\nThe earlier export's chunks this one doesn't hold: remove them from a corpus holding "
                "it.\n\n" + "".join(f"- {name}\n" for name in gone) if gone else ""))
    return {**{name: files[name] for name, _ in new}, "index.md": index}, gone

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

def claim_line(e, where=None, notes=()):
    """A claim as a chunk says it: its property and value, its qualifiers, where it's read (where: as given, its
    files named where a chunk holds several files' claims; "" for none), a short excerpt; then the second pass's notes
    about it, one below it each."""
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
            + (f" — “{excerpt}”" if excerpt else "") + "".join(f"\n  - {n}" for n in notes))

NOTED = ("Notes under a claim, read together or read again, are a second reading's: ours, not the document's; check "
         "them against the places named.")

QUIET = ("restates", "corroborates")  # relations whose reason a chunk leaves out

def value_said(e):
    unit = e["unit"] if e.get("unit") not in ("", "-", None) else ""
    return " ".join(x for x in (str(e["value"]), unit) if x)

def notes_of(data, files):
    """{claim id: [lines]}: what the second pass said about each claim (dossiers.py), as a chunk says it under the
    claim: the cards' notes (report.Cards.noted) in words; a restatement's or corroboration's reason, and a re-read's
    where it's as read, left out (QUIET), since they only say the values agree."""
    from .dossiers import reread_said, sum_said
    from .report import RELATION_SAID, SUSPICION_SAID
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    out = defaultdict(list)
    for c in (data.get("commentary") or {}).get("entries", []):
        why = " ".join(str(c.get("why") or "").split())
        for eid in c["claims"]:
            others = [evidence[x] for x in c["claims"] if x != eid and x in evidence]
            if c["kind"] == "context":
                line = f"Read together, {c['adds']}: {c['text']} — “{c['quote']}”"
            elif c["kind"] == "relation" and others and c.get("relation") in RELATION_SAID:
                said = RELATION_SAID[c["relation"]][0 if c["claims"][0] == eid else 1].lower()
                line = (f"Read together, {said} {value_said(others[0])} ({place(others[0], files)})"
                        + (f": {why}" if why and c["relation"] not in QUIET else ""))
            elif c["kind"] == "suspicion" and c.get("relation") in SUSPICION_SAID:
                line = f"Read together, suspected {SUSPICION_SAID[c['relation']]}" + (f": {why}" if why else "")
            elif c["kind"] == "inference":
                line = f"Read together, inferred: {c['text']}{sum_said(c)}"
            elif c["kind"] == "reread":
                line = (f"Read again from its place: {reread_said(c)}"
                        + (f" ({why})" if why and c.get("relation") != "as_claimed" else ""))
            else:
                continue
            out[eid].append(line)
    return out

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

def detail_chunks(data, size=CHUNK, notes=None):
    """[(title, text, [subjects in it])]: a chunk a section's part."""
    notes = notes or {}
    line = lambda e: claim_line(e, notes=notes.get(e["id"], ()))  # noqa: E731
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
                if current and sum(len(line(x)) + 1 for x in current) + len(line(e)) > size:
                    blocks.append((subject, current))
                    current = []
                current.append(e)
            blocks.append((subject, current))
        blocks = [(subject, f"### {subject}\n\n" + "\n".join(line(e) for e in es) + "\n", es)
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
            noted = any(notes.get(e["id"]) for _, _, es in part for e in es)
            text = (front(title=f"{title} — {f['path']}" + (f", {pages}" if pages else ""), source=f["source"],
                          file=f["path"], pages=pages) + f"# {title}\n\n{where}" + (f" {NOTED}" if noted else "")
                    + "\n\n"
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

def said_lines(claims, files, notes):
    """Claims' lines, a claim said alike in several places (two revisions) one line naming every place, its claims'
    notes under it."""
    lines = {}  # a line said (its places apart): the claim, its places and its claims' notes
    for e in claims:
        said = lines.setdefault(claim_line(e, ""), (e, [], []))
        said[1].append(place(e, files))
        said[2].extend(n for n in notes.get(e["id"], ()) if n not in said[2])
    return [claim_line(e, "; ".join(places), noted) for e, places, noted in lines.values()]

def by_subject(claims, files, size=CHUNK):
    """Claims as blocks, a block a subject's ("### name" and its lines), in their files' and places' order; a
    subject of more than a chunk's claims cut into several."""
    grouped = defaultdict(list)
    for e in sorted(claims, key=lambda e: (files[e["content"]]["path"] if e["content"] in files else "", order(e))):
        grouped[" ".join(e["entity"].split())].append(e)
    return [f"### {subject}\n\n" + "\n".join(part) + "\n" for subject, es in grouped.items()
            for part in cut(said_lines(es, files, {}), size)]

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

def runs(numbers):
    """Numbers as a citation: "[1–3, 7]"."""
    out, ns = [], sorted(set(numbers))
    for n in ns:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return "[" + ", ".join(str(a) if a == b else f"{a}, {b}" if b == a + 1 else f"{a}–{b}" for a, b in out) + "]"

SUMMARY_KINDS = (("source", "the source"), ("files", "a file"), ("sections", "a part"), ("subjects", "an item"),
                 ("topics", "a topic"))

def summary_chunks(data, files, size=CHUNK):
    """[(title, text)]: a chunk a summary the report holds (summaries.py; the owner, 2026-11-06, of the export: "Yes,
    with provenance."): labelled as written by the model (which one, from which claims), its sentences each marked
    with the claims it cites ([1], [2]), one its claims don't bear out said so, then those claims with where each is
    read; a long list of them in parts, each led alike."""
    found = data.get("summaries") or {}
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    model = str((data.get("settings") or {}).get("model") or "")
    out = []
    for kind, what in SUMMARY_KINDS:
        for summary in found.get(kind, []):
            cited = list(dict.fromkeys(x for s in summary["sentences"] for x in s["claims"] if x in evidence))
            if not cited:
                continue
            number = {x: n for n, x in enumerate(cited, 1)}
            said = " ".join(s["text"] + (f" {runs(number[x] for x in s['claims'] if x in number)}"
                                         if any(x in number for x in s["claims"]) else "")
                            + (f" (not borne out by the claims it cites: {s['check']})" if s.get("check") else "")
                            for s in summary["sentences"])
            refs = [f"[{number[x]}] {evidence[x]['entity']} " + claim_line(evidence[x], place(evidence[x], files))[2:]
                    for x in cited]
            lead = (f"A summary of {what}, written by the model{f' ({model})' if model else ''} from the claims below "
                    "alone (ours, not the document's): each sentence cites the claims it rests on, and is checked "
                    "against them by code.")
            paths = list(dict.fromkeys(files[evidence[x]["content"]]["path"] for x in cited
                                       if evidence[x]["content"] in files))
            out += titled(f"Summary: {summary['title']}", lead, cut([said + "\n\nClaims cited:\n"] + refs, size),
                          kind="summary, written by the model", model=model, files=paths)
    return out

def subject_chunks(data, index, files, size=CHUNK, notes=None):
    """[(title, text, subject's name)]: a chunk a subject of two claims or more (the index's subjects, its names
    joined), or a part of one: its claims by property from every file and section, each saying where it's read
    (and, in a comparison, by which source), its notes under it; then what it doesn't give (the index's gaps)."""
    notes = notes or {}
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    many = len(index.get("sources", [])) > 1
    out = []
    for s in index.get("subjects", []):
        ids = [c for p in s["properties"] for c in dict.fromkeys(v["claim"] for v in p["values"]) if c in evidence]
        if len(ids) < 2:
            continue
        lines = []
        for p in s["properties"]:
            for source in index["sources"]:
                mine = [evidence[v["claim"]] for v in p["values"] if v["source"] == source and v["claim"] in evidence]
                mine.sort(key=lambda e: (files[e["content"]]["path"] if e["content"] in files else "", order(e)))
                lines += [(f"- {source}: " + x[2:]) if many else x for x in said_lines(mine, files, notes)]
        named = {n.casefold() for n in (s["name"], *s["names"])}
        missing = [g for g in index.get("gaps", []) if g["subject"].casefold() in named]
        if missing:  # one block, so a part never ends on its heading
            lines.append("\n".join(["What it doesn't give (weak: it may be said elsewhere, or missed by the reader):"]
                                   + [f"- {(g['source'] + ': ') if many else ''}{GAP_TITLES[g['kind']]}"
                                      + (f": {g['property']}" if g["property"] else "") + f" ({g['where']}"
                                      + (f"; {g['why']}" if g["why"] else "") + ")"
                                      + (f"; looked for on {g['looked']}" if g.get("looked") else "")
                                      for g in missing]))
        also = [n for n in s["names"] if n.casefold() != s["name"].casefold()]
        noted = any(notes.get(c) for c in ids)
        lead = (f"What {' and '.join(index['sources'])} {'say' if many else 'says'} about {s['name']}"
                + (f" (also {', '.join(also[:5])})" if also else "")
                + ", from every file and section, by property; each says where it's read."
                + (f" {NOTED}" if noted else ""))
        out += [(title, text, s["name"]) for title, text in
                titled(f"Subject: {s['name']}", lead, cut(lines, size), subject=s["name"])]
    return out

def table_chunks(data, files, size=CHUNK):
    """[(title, text)]: a chunk a table read by rules (its record's cells: records.table_record), or a part of a
    long one, its rows under the table's header again, a section's label a row of its own. A table read from a picture
    keeps no record: its claims are in its section's chunks."""
    from .indexes import table_place
    out = []
    for r in data.get("records", []):
        cells = r.get("cells") or []
        if r.get("kind") != "table" or len(cells) < 2:
            continue
        f = files.get(r["content"])
        width = max(len(row) for row in cells)
        line = lambda row, width=width: (  # noqa: E731
            "| " + " | ".join(cell_md(c) for c in row + [""] * (width - len(row))) + " |")
        header = line(cells[0]) + "\n|" + "---|" * width
        where = table_place(r, f)
        lead = (f"A table of {len(cells) - 1} rows, from {where}: its cells as the reader took them from the source; "
                "check a value against its place.")
        fields = {"source": f["source"], "file": f["path"]} if f else {}
        out += titled(f"Table: {where}", lead, [[header, *part] for part in cut([line(x) for x in cells[1:]], size)],
                      **fields)
    return out

def kind_chunks(index, size=CHUNK):
    """[(title, text)]: a chunk a kind of the index's (two items or more of one kind: "pump (P)"), or a part of
    one: its items by property as a Markdown table, the properties most given first (KIND_COLUMNS of them), "—" where
    an item gives none; a part's rows under the table's header again."""
    many = len(index.get("sources", [])) > 1
    out = []
    for k in index.get("kinds", []):
        shown, items = k["properties"][:KIND_COLUMNS], [index["subjects"][i] for i in k["subjects"]]
        header = ("| Item | " + " | ".join(cell_md(kind_property(p)) for p in shown) + " |\n|---|"
                  + "---|" * len(shown))
        rows = [f"| {cell_md(s['name'])} | " + " | ".join(cell_md(kind_cell(s, p, many)) for p in shown) + " |"
                for s in items]
        rest = k["properties"][KIND_COLUMNS:]
        lead = (f"The {len(items)} items of the kind {k['kind']}, by property, the most given first; “—” where an "
                "item gives none. Given by: " + "; ".join(f"{kind_property(p)} {p['given']} of {len(items)}"
                                                       for p in shown)
                + "." + (f" Also given, by fewer: {', '.join(p['name'] for p in rest)}." if rest else ""))
        out += titled(f"Kind: {k['kind']}", lead, [[header, *part] for part in cut(rows, size)], kind=k["kind"])
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
                   f"{g['why']})" + (f"; looked for on {g['looked']}" if g.get("looked") else "")
                   for g in index.get("gaps", [])]))
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
    files_of = {}
    for f in sorted(data.get("files", []), key=lambda f: (f["source"], f["path"])):
        files_of.setdefault(f["content"], f)
    notes = notes_of(data, files_of)
    for title, text, subjects in detail_chunks(data, size, notes):
        name = name_of(text)
        files[name] = text
        titles.append((name, title))
        for s in subjects:
            located[s].append(name)
    found, same = finding_chunks(data, files_of, size)
    mine = defaultdict(list)  # a subject's own chunks, first among those its line in Subjects A to Z points to
    for title, text, subject in subject_chunks(data, index, files_of, size, notes):
        name = name_of(text)
        files[name] = text
        titles.append((name, title))
        mine[subject].append(name)
    for subject, names in mine.items():
        located[subject] = names + [n for n in located[subject] if n not in names]
    for title, text in (summary_chunks(data, files_of, size) + topic_chunks(data, files_of, size) + found
                        + kind_chunks(index, size)
                        + table_chunks(data, files_of, size) + discovery_chunks(index, located, size)):
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
