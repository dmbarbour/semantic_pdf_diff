"""Word documents (.docx; docs/plans/multi-format-adapters-2026-09-23.md, milestone 2), read through the text reader
(textdocs.py): a .docx becomes a TextDocument whose "lines" are its paragraphs and table rows in order, so sections,
grouping, the context levers and the task core work unchanged, and a claim's locator names its paragraphs.

- **Text:** each paragraph's text as currently written: tracked insertions in, deletions out (w:delText isn't
  text), tabs and breaks as spaces and new lines.
- **Headings:** paragraphs whose style is "Heading N", at level N; a "Title" is text. A table of contents (styles
  "toc N") is left out, as it repeats the headings.
- **Tables:** row by row with the first row as header; a cell merged across columns (one w:tc) is read once.
- **Pictures:** each picture (a drawing's image, or an embedded object's preview, often an EMF or WMF) is kept with
  its paragraph, displayed size and caption (the next paragraph in a caption style or starting "Figure ...", else
  the one before), for pictures.py to read.
- **Footnotes:** each placed as a line ("Footnote 1: ...") after the paragraph (or table) citing it, the citation
  marked "[1]" where it stands.
- **Numbered lists:** Word writes their numbers ("Condition 3:", "a)", "iv."), not the text: they're written from the
  numbering definitions (levels, formats, label text, a style's own numbering) before each item's text.
- **Not read yet:** charts and other drawings without a picture, each recorded as not read; comments; text boxes
  (their text is read where they're anchored).

Needs python-docx (the `office` extra).
"""
import io
import re

from .textdocs import Block, Picture, TextDocument

HEADING = re.compile(r"^(?:Heading|heading)\s*(\d)$")
# A caption: a paragraph in a caption style (Word's "Caption"; 3GPP's "TF", a figure's title), or one naming a figure
CAPTION_STYLES = ("caption", "tf")
FIGURE_TITLE = re.compile(r"^(?:Figure|Fig\.?|Diagram|Chart)\s*[A-Z]?[\d.\-\u2010-\u2013]+\w*", re.I)
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
V = "{urn:schemas-microsoft-com:vml}"
EMU_PER_POINT = 12700
LENGTH = re.compile(r"(width|height)\s*:\s*([\d.]+)\s*(pt|in|cm|mm|px)?", re.I)
POINTS_PER = {"pt": 1.0, "in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4, "px": 0.75, None: 0.75}

def _qn(tag):
    from docx.oxml.ns import qn
    return qn(tag)

def paragraph_text(p, notes=None):
    """A paragraph's text with tracked insertions applied and deletions left out; with notes ({footnote id: its
    number}), each footnote reference marked "[n]"."""
    out = []
    for node in p.iter():
        tag = node.tag
        if tag == _qn("w:t"):
            out.append(node.text or "")
        elif tag in (_qn("w:tab"),):
            out.append("\t")
        elif tag in (_qn("w:br"), _qn("w:cr")):
            out.append("\n")
        elif notes is not None and tag == _qn("w:footnoteReference") and node.get(_qn("w:id")) in notes:
            out.append(f"[{notes[node.get(_qn('w:id'))]}]")
    return "".join(out)

def _footnotes(document):
    """{footnote id: its text} from the document's footnotes part (none: {}); separators left out."""
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import parse_xml
    part = next((r.target_part for r in document.part.rels.values() if r.reltype == RT.FOOTNOTES and not r.is_external),
                None)
    if part is None:
        return {}
    root = parse_xml(part.blob)
    out = {}
    for note in root.iter(_qn("w:footnote")):
        if note.get(_qn("w:type")) in ("separator", "continuationSeparator", "continuationNotice"):
            continue
        out[note.get(_qn("w:id"))] = " ".join(paragraph_text(p).strip() for p in note.iter(_qn("w:p"))).strip()
    return out

class Numbering:
    """Word's list numbering: each numbered paragraph's label ("Condition 3:", "a)"), counted as Word counts them
    (by list and level; a level restarts when one above it advances)."""
    FORMATS = {"decimal", "decimalZero", "lowerLetter", "upperLetter", "lowerRoman", "upperRoman", "bullet", "none"}

    def __init__(self, document):
        self.levels, self.lists, self.counts = {}, {}, {}
        self.styles = {}  # style id: (numId, ilvl) its paragraphs are numbered by
        part = getattr(document.part, "numbering_part", None) if self._has_numbering(document) else None
        if part is not None:
            root = part.element
            for abstract in root.iter(_qn("w:abstractNum")):
                levels = {}
                for level in abstract.iter(_qn("w:lvl")):
                    value = lambda tag, default: (level.find(_qn(tag)).get(_qn("w:val"))
                                                  if level.find(_qn(tag)) is not None else default)
                    levels[int(level.get(_qn("w:ilvl")))] = (int(value("w:start", "1")), value("w:numFmt", "decimal"),
                                                            value("w:lvlText", ""))
                self.levels[abstract.get(_qn("w:abstractNumId"))] = levels
            for num in root.iter(_qn("w:num")):
                ref = num.find(_qn("w:abstractNumId"))
                starts = {int(o.get(_qn("w:ilvl"))): int(o.find(_qn("w:startOverride")).get(_qn("w:val")))
                          for o in num.iter(_qn("w:lvlOverride")) if o.find(_qn("w:startOverride")) is not None}
                if ref is not None:
                    self.lists[num.get(_qn("w:numId"))] = (ref.get(_qn("w:val")), starts)
        for style in document.styles.element.iter(_qn("w:style")):
            found = self._numbered(style.find(_qn("w:pPr")))
            if found:
                self.styles[style.get(_qn("w:styleId"))] = found

    @staticmethod
    def _has_numbering(document):
        try:
            return document.part.numbering_part is not None
        except (KeyError, NotImplementedError):
            return False

    def _numbered(self, ppr):
        numbering = ppr.find(_qn("w:numPr")) if ppr is not None else None
        if numbering is None:
            return None
        num, level = numbering.find(_qn("w:numId")), numbering.find(_qn("w:ilvl"))
        return (num.get(_qn("w:val")) if num is not None else None, int(level.get(_qn("w:val"))) if level is not None else 0)

    def label(self, paragraph):
        """A paragraph's label, counted ("" when it isn't numbered)."""
        ppr = paragraph.find(_qn("w:pPr"))
        found = self._numbered(ppr)
        if found is None and ppr is not None and ppr.find(_qn("w:pStyle")) is not None:
            found = self.styles.get(ppr.find(_qn("w:pStyle")).get(_qn("w:val")))
        if not found or found[0] in (None, "0") or found[0] not in self.lists:
            return ""
        num, level = found
        abstract, starts = self.lists[num]
        levels = self.levels.get(abstract, {})
        if level not in levels:
            return ""
        counts = self.counts.setdefault(num, {})
        start = lambda k: starts.get(k, levels.get(k, (1,))[0])
        counts[level] = counts[level] + 1 if level in counts else start(level)
        for deeper in [k for k in counts if k > level]:
            del counts[deeper]
        _, form, text = levels[level]
        if form == "bullet":
            return "•"
        def number(match):
            k = int(match.group(1)) - 1
            return _format(counts.get(k, start(k)), levels.get(k, (1, "decimal", ""))[1])
        return re.sub(r"%(\d)", number, text).strip()

def _format(n, form):
    if form == "decimalZero":
        return f"{n:02d}"
    if form in ("lowerLetter", "upperLetter"):
        letters = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            letters = chr(97 + r) + letters
        return letters.upper() if form == "upperLetter" else letters
    if form in ("lowerRoman", "upperRoman"):
        out = ""
        for value, numeral in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
                               (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
            while n >= value:
                out, n = out + numeral, n - value
        return out.upper() if form == "upperRoman" else out
    return "" if form == "none" else str(n)

def _style(paragraph_element, styles):
    ppr = paragraph_element.find(_qn("w:pPr"))
    sid = None
    if ppr is not None:
        ps = ppr.find(_qn("w:pStyle"))
        if ps is not None:
            sid = ps.get(_qn("w:val"))
    return styles.get(sid, sid or "Normal")

def _pictures(element, part):
    """[(the picture's part, its displayed size in points or None) or (None, what it is)] for each drawing,
    embedded object and VML picture in an element."""
    out = []
    for node in element.iter(_qn("w:drawing"), _qn("w:object"), _qn("w:pict")):
        if node.tag == _qn("w:drawing"):
            blip = next(node.iter(A + "blip"), None)
            rid = blip.get(R + "embed") if blip is not None else None
            extent = next(node.iter(WP + "extent"), None)
            size = (int(extent.get("cx")) / EMU_PER_POINT, int(extent.get("cy")) / EMU_PER_POINT) \
                if extent is not None and extent.get("cx") and extent.get("cy") else None
            what = "a chart or drawing without a picture"
        else:
            data = next(node.iter(V + "imagedata"), None)
            rid = data.get(R + "id") if data is not None else None
            shape = next(node.iter(V + "shape"), None)
            found = dict((k.lower(), float(v) * POINTS_PER[(u or "").lower() or None])
                         for k, v, u in LENGTH.findall(shape.get("style", "") if shape is not None else ""))
            size = (found["width"], found["height"]) if "width" in found and "height" in found else None
            what = "an embedded object without a preview"
        target = part.related_parts.get(rid) if rid else None
        out.append((target, size) if target is not None else (None, what))
    return out

def read_docx(data):
    """A .docx's TextDocument: paragraphs and table rows as lines, headings by style, pictures noted."""
    import docx
    document = docx.Document(io.BytesIO(bytes(data)))
    styles = {s.style_id: s.name for s in document.styles}
    lines, blocks, headings, images, found = [], [], [], [], []
    styles_of = {}  # line: its paragraph's style

    def line(text):
        lines.append((1, text))
        return len(lines)

    def note(element, n, where):
        for target, detail in _pictures(element, document.part):
            if target is None:
                images.append((1, n, where, detail))
            else:
                name = str(target.partname).rsplit("/", 1)[-1]
                found.append((n, target.blob, "." + name.rsplit(".", 1)[-1].lower(), detail, name))
    notes = _footnotes(document)
    numbers = {}  # footnote id: its number, in the order the body cites them

    def cited(element):
        """The footnote ids an element cites, numbered as they're met."""
        ids = [r.get(_qn("w:id")) for r in element.iter(_qn("w:footnoteReference")) if r.get(_qn("w:id")) in notes]
        for i in ids:
            numbers.setdefault(i, len(numbers) + 1)
        return ids

    def footnote_lines(ids):
        for i in ids:
            m = line(f"Footnote {numbers[i]}: {notes[i]}")
            blocks.append(Block(1, m, m, f"Footnote {numbers[i]}: {notes[i]}"))
    listing = Numbering(document)
    for child in document.element.body.iterchildren():
        if child.tag == _qn("w:p"):
            style = _style(child, styles)
            ids = cited(child)
            text = paragraph_text(child, numbers).strip()
            label = listing.label(child)
            if label and text:
                text = f"{label} {text}"
            n = line(text)
            styles_of[n] = style
            note(child, n, style)
            if ids and not text:
                footnote_lines(ids)
                continue
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
            footnote_lines(ids)
        elif child.tag == _qn("w:tbl"):
            rows, row_lines = [], []
            ids = cited(child)
            for tr in child.iter(_qn("w:tr")):
                cells = []
                for tc in tr.iter(_qn("w:tc")):  # a cell merged across columns is one w:tc (w:gridSpan)
                    cells.append(" ".join(paragraph_text(p, numbers).strip() for p in tc.iter(_qn("w:p"))).strip())
                rows.append(cells)
                row_lines.append(line(" | ".join(cells)))
            if rows:
                blocks.append(Block(1, row_lines[0], row_lines[-1], "\n".join(t for _, t in lines[row_lines[0] - 1:]),
                                    "table", rows, row_lines))
                note(child, row_lines[0], "table")
            footnote_lines(ids)
    pictures = [Picture(n, data, extension, size, _caption(n, lines, styles_of), name)
                for n, data, extension, size, name in found]
    return TextDocument(1, lines, blocks, headings, images, pictures)

def _caption(n, lines, styles_of):
    """A picture's caption: the next paragraph (within two) in a caption style or naming a figure, else the one
    before; "" when neither is."""
    def caption(k):
        text = lines[k - 1][1].strip() if 0 < k <= len(lines) else ""
        style = styles_of.get(k, "").casefold()
        return text if text and (style in CAPTION_STYLES or "caption" in style or FIGURE_TITLE.match(text)) else ""
    for k in (n, n + 1, n + 2, n - 1):
        if k == n and lines[n - 1][1].strip():  # the picture's own paragraph holds text: a caption beside it
            if caption(k):
                return caption(k)
            continue
        if caption(k):
            return caption(k)
    return ""
