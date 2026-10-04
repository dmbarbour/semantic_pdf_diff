"""Word's own difficulties as knobs (the adapters plan, "Word's own difficulties as knobs"; the owner, 2026-10-03: "I do
want Word-specific knobs; we should definitely include some footnotes etc"; "For tracked changes, we'll generally
process the changes-applied version, but that must be tested if not already"): Word-only versions of corpus
documents, each with one feature of Word's a reader must handle, scored by the same facts (docx_key: placed by the
reader's own lines).

- **tracked:** a revision delivered as tracked changes. The earlier document carries the later one's edits as
  unaccepted insertions and deletions: words within paragraphs and cells, a table row added, a sentence dropped.
  Read as the changes-applied version, it's the later revision.
- **footnotes:** sentences stating facts moved into footnotes, each leaving its reference mark.
- **numbered:** numbered conditions as an auto-numbered list, Word writing "Condition 1:" from the list's label; in
  the renumbered revision, a condition inserted renumbers the rest with no change to their text.

Byte for byte the same each time (representations.FIXED_TIME).
"""
import datetime
import difflib
import io
import re
import zipfile

from .representations import FIXED_TIME

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
AUTHOR, DATE = "controlled corpus", "2026-01-01T00:00:00Z"
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
CONDITION = re.compile(r"^Condition (\d+): (.*)$")

def _qn(tag):
    from docx.oxml.ns import qn
    return qn(tag)

def _element(tag, **attributes):
    from docx.oxml import OxmlElement
    element = OxmlElement(tag)
    for name, value in attributes.items():
        element.set(_qn(name), value)
    return element

def blocks(lines):
    """Markdown lines (representations.markdown) as blocks: ("heading", level, text), ("p", text), ("bold", text),
    ("italic", text), ("table", rows)."""
    out, k = [], 0
    while k < len(lines):
        line = lines[k]
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            out.append(("heading", len(heading.group(1)) - 1, heading.group(2)))
        elif line.startswith("|"):
            rows = []
            while k < len(lines) and lines[k].startswith("|"):
                cells = [c.strip().replace("\\|", "|") for c in lines[k].strip().strip("|").split(" | ")]
                if not all(set(c) <= {"-"} for c in cells):
                    rows.append(cells)
                k += 1
            out.append(("table", rows))
            continue
        elif line.startswith("**") and line.endswith("**"):
            out.append(("bold", line.strip("*")))
        elif line.startswith("*") and line.endswith("*"):
            out.append(("italic", line.strip("*")))
        elif line.strip():
            out.append(("p", line))
        k += 1
    return out

class Writer:
    """A Word document built block by block, with what the knobs need: tracked runs, footnotes, numbered lists."""
    def __init__(self):
        import docx
        self.document = docx.Document()
        props = self.document.core_properties
        props.created = props.modified = props.last_printed = datetime.datetime(*FIXED_TIME)
        props.author = props.last_modified_by = AUTHOR
        self.revision = 0
        self.footnotes = []  # their texts, numbered from 1
        self.lists = {}      # label: numId

    def mark(self, tag):
        self.revision += 1
        return _element(tag, **{"w:id": str(self.revision), "w:author": AUTHOR, "w:date": DATE})

    def run(self, text, deleted=False, bold=False, italic=False):
        run = _element("w:r")
        if bold or italic:
            props = _element("w:rPr")
            if bold:
                props.append(_element("w:b"))
            if italic:
                props.append(_element("w:i"))
            run.append(props)
        body = _element("w:delText" if deleted else "w:t", **{"xml:space": "preserve"})
        body.text = text
        run.append(body)
        return run

    def tracked(self, parent, before, after):
        """Runs into parent: the words of `before` changed into `after`, deletions and insertions tracked."""
        a, b = re.findall(r"\S+\s*", before), re.findall(r"\S+\s*", after)
        for op, i0, i1, j0, j1 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op == "equal":
                parent.append(self.run("".join(a[i0:i1])))
                continue
            if i1 > i0:
                gone = self.mark("w:del")
                gone.append(self.run("".join(a[i0:i1]), deleted=True))
                parent.append(gone)
            if j1 > j0:
                new = self.mark("w:ins")
                new.append(self.run("".join(b[j0:j1])))
                parent.append(new)

    def paragraph(self, text="", style=None, before=None, deleted=False, inserted=False, bold=False, italic=False):
        """A paragraph: plain, changed from `before` (tracked), or wholly deleted or inserted (tracked)."""
        p = self.document.add_paragraph(style=style)._p
        if before is not None:
            self.tracked(p, before, text)
        elif deleted or inserted:
            wrap = self.mark("w:del" if deleted else "w:ins")
            wrap.append(self.run(text, deleted=deleted, bold=bold, italic=italic))
            p.append(wrap)
        elif text:
            p.append(self.run(text, bold=bold, italic=italic))
        return p

    def heading(self, text, level):
        self.document.add_heading(text, level=level)

    def table(self, rows, earlier=None):
        """A table; with `earlier` (its rows before), rows matched, changed cells tracked word by word, rows added or
        dropped tracked as row insertions and deletions."""
        pairs = [(row, row, None) for row in rows] if earlier is None else _row_changes(earlier, rows)
        table = self.document.add_table(rows=len(pairs), cols=max(len(r or b) for r, b, _ in pairs))
        table.style = "Table Grid"
        for r, (row, old, kind) in enumerate(pairs):
            tr = table.rows[r]
            if kind in ("ins", "del"):
                tr._tr.get_or_add_trPr().append(self.mark(f"w:{kind}"))
            for c, cell in enumerate(tr.cells):
                p = cell.paragraphs[0]._p
                new, before = (row[c] if row and c < len(row) else ""), (old[c] if old and c < len(old) else "")
                if kind == "del":
                    wrap = self.mark("w:del")
                    wrap.append(self.run(before, deleted=True))
                    p.append(wrap)
                elif kind == "ins":
                    wrap = self.mark("w:ins")
                    wrap.append(self.run(new))
                    p.append(wrap)
                elif new != before:
                    self.tracked(p, before, new)
                elif new:
                    p.append(self.run(new))

    def footnote(self, paragraph, text):
        """A footnote reference at the end of `paragraph` (an element), its note `text`."""
        self.footnotes.append(text)
        run = _element("w:r")
        props = _element("w:rPr")
        props.append(_element("w:vertAlign", **{"w:val": "superscript"}))
        run.append(props)
        run.append(_element("w:footnoteReference", **{"w:id": str(len(self.footnotes))}))
        paragraph.append(run)

    def numbered(self, text, label):
        """A list item numbered by Word with `label` ("Condition %1:"), one list per label."""
        if label not in self.lists:
            self.lists[label] = self._list(label)
        p = self.document.add_paragraph()._p
        props = p.get_or_add_pPr()
        numbering = _element("w:numPr")
        numbering.append(_element("w:ilvl", **{"w:val": "0"}))
        numbering.append(_element("w:numId", **{"w:val": str(self.lists[label])}))
        props.append(numbering)
        p.append(self.run(text))

    def _list(self, label):
        root = self.document.part.numbering_part.element
        ids = [int(e.get(_qn("w:abstractNumId"))) for e in root.findall(f"{{{W}}}abstractNum")]
        nums = [int(e.get(_qn("w:numId"))) for e in root.findall(f"{{{W}}}num")]
        abstract_id, num_id = max(ids, default=0) + 1, max(nums, default=0) + 1
        abstract = _element("w:abstractNum", **{"w:abstractNumId": str(abstract_id)})
        level = _element("w:lvl", **{"w:ilvl": "0"})
        for tag, value in (("w:start", "1"), ("w:numFmt", "decimal"), ("w:lvlText", label), ("w:lvlJc", "left")):
            level.append(_element(tag, **{"w:val": value}))
        abstract.append(level)
        first_num = root.find(f"{{{W}}}num")  # abstractNums come before nums
        if first_num is not None:
            first_num.addprevious(abstract)
        else:
            root.append(abstract)
        num = _element("w:num", **{"w:numId": str(num_id)})
        num.append(_element("w:abstractNumId", **{"w:val": str(abstract_id)}))
        root.append(num)
        return num_id

    def save(self):
        if self.footnotes:
            self._footnotes_part()
        raw = io.BytesIO()
        self.document.save(raw)
        fixed = io.BytesIO()  # the same members, each dated FIXED_TIME
        with zipfile.ZipFile(io.BytesIO(raw.getvalue())) as source, zipfile.ZipFile(fixed, "w", zipfile.ZIP_DEFLATED) as out:
            for info in source.infolist():
                out.writestr(zipfile.ZipInfo(info.filename, FIXED_TIME), source.read(info.filename),
                             compress_type=zipfile.ZIP_DEFLATED)
        return fixed.getvalue()

    def _footnotes_part(self):
        from xml.sax.saxutils import escape
        from docx.opc.constants import CONTENT_TYPE as CT, RELATIONSHIP_TYPE as RT
        from docx.opc.packuri import PackURI
        from docx.opc.part import Part
        notes = ['<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>',
                 '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p>'
                 '</w:footnote>']
        for n, text in enumerate(self.footnotes, 1):
            notes.append(f'<w:footnote w:id="{n}"><w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'
                         f'<w:footnoteRef/></w:r><w:r><w:t xml:space="preserve"> {escape(text)}</w:t></w:r></w:p>'
                         '</w:footnote>')
        xml = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:footnotes xmlns:w="{W}">'
               + "".join(notes) + "</w:footnotes>")
        part = Part(PackURI("/word/footnotes.xml"), CT.WML_FOOTNOTES, xml.encode(), self.document.part.package)
        self.document.part.relate_to(part, RT.FOOTNOTES)

def _row_changes(earlier, later):
    """[(later row, earlier row, kind)]: rows matched in order; kind None (alike or changed), "ins" or "del"."""
    out = []
    key = lambda row: row[0] if row else ""
    matcher = difflib.SequenceMatcher(None, [key(r) for r in earlier], [key(r) for r in later], autojunk=False)
    for op, i0, i1, j0, j1 in matcher.get_opcodes():
        if op in ("equal", "replace") and i1 - i0 == j1 - j0:
            out += [(later[j], earlier[i], None) for i, j in zip(range(i0, i1), range(j0, j1))]
            continue
        out += [(None, earlier[i], "del") for i in range(i0, i1)]
        out += [(later[j], None, "ins") for j in range(j0, j1)]
    return out

def write_block(writer, block, before=None):
    kind = block[0]
    if kind == "heading":
        writer.heading(block[2], block[1])
    elif kind == "table":
        writer.table(block[1], earlier=before[1] if before else None)
    elif kind == "bold":
        writer.paragraph(block[1], bold=True)
    elif kind == "italic":
        writer.paragraph(block[1], italic=True)
    else:
        writer.paragraph(block[1], before=before[1] if before else None)

def tracked(earlier_lines, later_lines):
    """The later revision as tracked changes to the earlier: a Word document's bytes. Blocks are matched in order
    (_block_key); a matched pair that differs is tracked word by word (a table cell by cell, row by row), and a block
    only in one revision is a tracked deletion or insertion."""
    writer = Writer()
    a, b = blocks(earlier_lines), blocks(later_lines)
    matcher = difflib.SequenceMatcher(None, [_block_key(x) for x in a], [_block_key(x) for x in b], autojunk=False)
    for op, i0, i1, j0, j1 in matcher.get_opcodes():
        olds, news = a[i0:i1], b[j0:j1]
        for k in range(max(len(olds), len(news))):
            old = olds[k] if k < len(olds) else None
            new = news[k] if k < len(news) else None
            if old and new and old[0] == new[0] and old[0] in ("p", "table"):
                write_block(writer, new, before=old if old != new else None)
            elif old and new and old == new:
                write_block(writer, new)
            else:
                if old:
                    if old[0] == "table":
                        writer.table([], earlier=old[1])
                    else:
                        writer.paragraph(old[-1], deleted=True)
                if new:
                    if new[0] == "table":
                        writer.table(new[1], earlier=[])
                    else:
                        writer.paragraph(new[-1], inserted=True)
    return writer.save()

def _block_key(block):
    """What blocks are matched by: a heading or bold caption by its text; a paragraph by its first words (a changed
    value leaves them); a table by its header."""
    if block[0] == "table":
        return ("table", tuple(block[1][0]) if block[1] else ())
    if block[0] == "p":
        return ("p", " ".join(block[1].split()[:4]))
    return (block[0], block[-1])

def footnoted(lines, values):
    """The document with each sentence stating one of `values` moved into a footnote (its mark at the end of the
    sentence before it, or of its paragraph): a Word document's bytes."""
    writer = Writer()
    for block in blocks(lines):
        if block[0] != "p" or not any(v in block[1] for v in values):
            write_block(writer, block)
            continue
        kept, notes = [], []
        for sentence in SENTENCE.split(block[1]):
            (notes if any(re.search(rf"(?<![\w.,]){re.escape(v)}(?![\w]|[.,]\d)", sentence) for v in values)
             else kept).append(sentence)
        p = writer.paragraph(" ".join(kept))
        for note in notes:
            writer.footnote(p, note)
    return writer.save()

def numbered(lines, label="Condition %1:"):
    """The document with its "Condition N: ..." paragraphs as an auto-numbered list (`label`): Word writes the
    numbers. A Word document's bytes."""
    writer = Writer()
    for block in blocks(lines):
        match = CONDITION.match(block[1]) if block[0] == "p" else None
        if match:
            writer.numbered(match.group(2), label)
        else:
            write_block(writer, block)
    return writer.save()

# --- the knobs' documents and pairs ----------------------------------------------------------------------------

# Facts whose sentences move into footnotes: each sentence stands beside another in its paragraph
FOOTNOTED = ("chem.chlorine", "floc.stages", "filters.rate")

def documents(seed=1):
    """[(project, document bytes)]: the Word-only documents, each project's id its document's, a revision's
    revision_of the document it revises."""
    from .corpus import link_protocol, water_treatment
    from .representations import markdown
    from .revisions import revised
    out = []
    base = water_treatment(seed)
    notes = water_treatment(seed)
    notes.id = f"{base.id}-footnotes"
    out.append((notes, footnoted(markdown(base), [base.fact(f).value for f in FOOTNOTED])))
    (_, later), = revised(seed, only=(base.id,))
    later.id, later.revision_of = f"{base.id}-tracked", base.id
    out.append((later, tracked(markdown(base), markdown(later))))
    spec = link_protocol(seed)
    lines = markdown(spec)
    spec.id = f"{spec.id}-numbered"
    out.append((spec, numbered(lines)))
    (_, renumbered), = revised(seed, only=(f"{link_protocol(seed).id}-renumbered",))
    lines = markdown(renumbered)
    renumbered.id, renumbered.revision_of = f"{renumbered.id}-numbered", spec.id
    out.append((renumbered, numbered(lines)))
    return out

def pairs(seed=1):
    """The Word-only revision pairs: (pair id, earlier, later), documents in docs-docx."""
    from .revisions import Pair
    base, spec = f"wtp-s{seed}", f"spec-s{seed}"
    return [Pair(f"{base}-tracked", base, f"{base}-tracked"),
            Pair(f"{spec}-numbered", f"{spec}-numbered", f"{spec}-renumbered-numbered")]

def write(folder, seed=1):
    """Write each Word-only document and its key (representations.docx_key) into folder; returns their paths."""
    import json
    from pathlib import Path
    from .representations import docx_key
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for project, data in documents(seed):
        path = folder / f"{project.id}.docx"
        path.write_bytes(data)
        (folder / f"{project.id}.key.json").write_text(
            json.dumps(docx_key(project, data), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        paths.append(path)
    return paths
