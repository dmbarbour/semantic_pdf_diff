"""Word documents (.docx; docs/plans/multi-format-adapters-2026-09-23.md, milestone 2), read through the text reader
(textdocs.py): a .docx becomes a TextDocument whose "lines" are its paragraphs and table rows in order, so sections,
grouping, the context levers and the task core work unchanged, and a claim's locator names its paragraphs.

- **Text:** each paragraph's text as currently written: tracked insertions in, deletions out (w:delText isn't
  text), tabs and breaks as spaces and new lines.
- **Headings:** paragraphs whose style is "Heading N", at level N; a "Title" is text. A table of contents (styles
  "toc N") is left out, as it repeats the headings.
- **Tables:** row by row with the first row as header; a cell merged across columns (one w:tc) is read once.
- **Not read yet:** embedded pictures and objects (drawings, charts, equations as images), each recorded as not
  read; comments.

Needs python-docx (the `office` extra).
"""
import io
import re

from .textdocs import Block, TextDocument

HEADING = re.compile(r"^(?:Heading|heading)\s*(\d)$")

def _qn(tag):
    from docx.oxml.ns import qn
    return qn(tag)

def paragraph_text(p):
    """A paragraph's text with tracked insertions applied and deletions left out."""
    out = []
    for node in p.iter():
        tag = node.tag
        if tag == _qn("w:t"):
            out.append(node.text or "")
        elif tag in (_qn("w:tab"),):
            out.append("\t")
        elif tag in (_qn("w:br"), _qn("w:cr")):
            out.append("\n")
    return "".join(out)

def _style(paragraph_element, styles):
    ppr = paragraph_element.find(_qn("w:pPr"))
    sid = None
    if ppr is not None:
        ps = ppr.find(_qn("w:pStyle"))
        if ps is not None:
            sid = ps.get(_qn("w:val"))
    return styles.get(sid, sid or "Normal")

def _pictures(element):
    return len(element.findall(".//" + _qn("w:drawing"))) + len(element.findall(".//" + _qn("w:object"))) + \
           len(element.findall(".//" + _qn("w:pict")))

def read_docx(data):
    """A .docx's TextDocument: paragraphs and table rows as lines, headings by style, pictures noted."""
    import docx
    document = docx.Document(io.BytesIO(bytes(data)))
    styles = {s.style_id: s.name for s in document.styles}
    lines, blocks, headings, images = [], [], [], []

    def line(text):
        lines.append((1, text))
        return len(lines)
    for child in document.element.body.iterchildren():
        if child.tag == _qn("w:p"):
            style = _style(child, styles)
            text = paragraph_text(child).strip()
            n = line(text)
            for _ in range(_pictures(child)):
                images.append((1, n, style, "an embedded picture or object"))
            if not text or style.lower().startswith("toc"):
                continue
            match = HEADING.match(style)
            if match:
                level = int(match.group(1))
                title = " ".join(text.split())
                headings.append((1, n, level, title))
                blocks.append(Block(1, n, n, title))
            else:
                blocks.append(Block(1, n, n, text))
        elif child.tag == _qn("w:tbl"):
            rows, row_lines = [], []
            for tr in child.iter(_qn("w:tr")):
                cells = []
                for tc in tr.iter(_qn("w:tc")):  # a cell merged across columns is one w:tc (w:gridSpan)
                    cells.append(" ".join(paragraph_text(p).strip() for p in tc.iter(_qn("w:p"))).strip())
                rows.append(cells)
                row_lines.append(line(" | ".join(cells)))
            if rows:
                blocks.append(Block(1, row_lines[0], row_lines[-1], "\n".join(t for _, t in lines[row_lines[0] - 1:]),
                                    "table", rows, row_lines))
                n = row_lines[0]
                for _ in range(_pictures(child)):
                    images.append((1, n, "table", "an embedded picture or object in a table"))
    return TextDocument(1, lines, blocks, headings, images)
