"""The controlled corpus in other representations (the controlled documents plan, decision 4; the adapters plan,
milestone 1): the same projects written as Markdown, scored by the same facts.

The owner (2026-10-02): "When we do add the alternative readers, we'll implicitly get a new form of control tests:
same facts across two or more representations, within constraints of being unable to effectively represent all
media."

- **What Markdown carries:** headings, paragraphs (the plain or trap phrasing, as the project's knob says), and
  tables as pipe tables (a schedule's sections as tables of their own, a split schedule whole).
- **What it doesn't:** charts, schematics and drawing sheets. A chart's caption stays, marked as not shown; the
  facts only it held are listed in the key as absent, so they're neither found nor missed.
- **The key:** the facts printed, each placed by line; every printed number logged with its role, as a PDF's are.
"""
import re

from semantic_pdf_diff.values import printed_value

from .corpus import key as pdf_key

def _row(cells):
    return "| " + " | ".join(str(c).replace("|", "\\|") for c in cells) + " |"

def _table(caption, header, rows):
    return [f"**{caption}**", "", _row(header), _row(["---"] * len(header)), *(_row(r) for r in rows), ""]

def markdown(project):
    """A project as Markdown lines, or None for one Markdown can't carry (a sheet, a schematic)."""
    if getattr(project, "sheet", None) or getattr(project, "schematic", None):
        return None
    out = [f"# {project.title}", ""]
    for heading, blocks in project.sections:
        out += [f"## {heading}", ""]
        for block in blocks:
            kind = block[0]
            if kind == "p":
                out += [block[1], ""]
            elif kind == "text":
                plain, trap = project.texts[block[1]]
                out += [(trap if project.has("traps") else plain).format(**project.values), ""]
            elif kind == "table":
                _, caption, header, rows = block
                out += _table(caption, header, rows)
            elif kind == "rooms":
                _, (caption_trap, caption_plain), header, rows = block
                trap = project.has("traps")
                shown = rows if trap else [[f"Hall C {row[0].lower()}"] + row[1:] for row in rows]
                out += _table(caption_trap if trap else caption_plain, header, shown)
            elif kind == "schedule":
                sched = block[1]
                number, _, name = sched.caption.partition(". ")
                parts = sched.sections
                for k, (title, _, columns, rows) in enumerate(parts):
                    caption = f"{number}{'abcdefgh'[k]}. {title}" if len(parts) > 1 else sched.caption
                    out += _table(caption, [title] + [c.label for c in columns], [[tag, *cells] for tag, cells in rows])
            elif kind == "chart":
                out += [f"*{block[1].caption} (a chart, not shown in this representation)*", ""]
            else:
                return None  # a schematic's parts: not carried
    return out

def _numbers(line):
    """The printed numbers in a line, as words stripped of punctuation (as corpus.locate reads a page)."""
    for word in line.replace("|", " ").split():
        text = word.strip(",.;:()°*")
        if re.search(r"[0-9]", text) and printed_value(text) is not None:
            yield text

def key(project, lines):
    """The Markdown's key: the PDF key's facts that the lines print, each placed by line ("md-prose", "md-table"), the
    others listed as absent; every printed number logged with its role."""
    by_value = {}
    for f in project.facts:
        if not f.relation and f.drawn != "chart":  # a chart's facts: absent, though a total may print the same number
            by_value.setdefault(printed_value(f.value), []).append(f)
        f.forms = []
    log = []
    for n, line in enumerate(lines, 1):
        form = "md-table" if line.startswith("|") else "md-prose"
        for text in _numbers(line):
            facts = by_value.get(printed_value(text), []) if re.match(r"[-+±$]?\d", text) else []
            for f in facts:
                f.forms.append({"form": form, "page": 1, "line": n})
            log.append({"text": text, "page": 1, "role": facts[0].role if facts else "structure",
                        "facts": [f.id for f in facts]})
    absent = [f.id for f in project.facts if not f.relation and not f.forms]
    out = pdf_key(project, log)
    out["facts"] = [f for f in out["facts"] if f["id"] not in absent and not f.get("relation")]
    out["absent"] = absent
    out["representation"] = "markdown"
    return out

# Layout knobs (page furniture, columns, page breaks, rasters) mean nothing in Markdown: only the clean documents
# and the prose traps are written, with the revisions of those.
MARKDOWN_KNOBS = ("clean", "traps")

def corpus(seeds=(1,)):
    """[(project, Markdown lines)]: every corpus document Markdown carries, revisions included."""
    from .corpus import corpus as projects
    out = []
    for project in projects(seeds, knobs=True, revisions=True):
        lines = markdown(project) if project.knob in MARKDOWN_KNOBS else None
        if lines is not None:
            out.append((project, lines))
    return out

def write(project, lines, folder):
    """Write <id>.md and <id>.key.json into folder; returns the Markdown's path."""
    import json
    from pathlib import Path
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{project.id}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / f"{project.id}.key.json").write_text(json.dumps(key(project, lines), indent=1, ensure_ascii=False) + "\n",
                                                   encoding="utf-8")
    return path
