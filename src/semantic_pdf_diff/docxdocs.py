"""Word documents (.docx; docs/plans/multi-format-adapters-2026-09-23.md, milestone 2), read through the text reader
(textdocs.py): a .docx becomes a TextDocument whose "lines" are its paragraphs and table rows in order, so sections,
grouping, the context levers and the task core work unchanged, and a claim's locator names its paragraphs.

- **Text:** each paragraph's text as currently written: tracked insertions in, deletions out (w:delText isn't
  text), tabs and breaks as spaces and new lines.
- **Headings:** paragraphs whose style is "Heading N", at level N; a "Title" is text. A table of contents (styles
  "toc N") is left out, as it repeats the headings.
- **Tables** (the adapters plan, "Merged and nested cells"; the owner, 2026-10-04: "Go ahead with the initial
  design based on your recommendations, heuristic for layout tables. This will provide a foundation for improving
  things later."):
  - **The grid:** each row's cells placed on the table's columns. A cell merged down repeats its text in every row
    it covers, so a row keeps its subject; a cell merged across is one cell, read under its columns' labels joined
    ("Stroke time (s) > Open / Close").
  - **Headers:** the rows marked to repeat as a header, else the first row, and the next too when the first has a
    cell merged across (or down into it) and it holds no number. Under several header rows a column is labelled
    by its path ("Rated point > Capacity (gpm)").
  - **Nested tables:** one of up to NESTED_INLINE_ROWS rows is written into its cell ("Flow: 450 gpm; Head: 85 ft"),
    so its values stay in their row; a larger one is read as a table of its own after the outer table, under a
    line naming its place ("Table in P-101A, Rating:").
  - **Layout tables:** a table not marked with a header row holds content rather than data when it has one row or
    one column (a boxed note or proposal), or when its first row doesn't look like a header (each cell filled, at
    most HEADER_CHARS characters) and a cell holds a heading or the cells average LAYOUT_CHARS characters. Its
    cells are read in order as the document's own paragraphs and tables. (A table of companies' comments has a
    header row, long cells and the odd pasted heading: data.)
  - Content controls and custom markup around rows, cells and paragraphs are read through.
- **Pictures:** each picture (a drawing's image, or an embedded object's preview, often an EMF or WMF) is kept with
  its paragraph, displayed size and caption (the next paragraph in a caption style or starting "Figure ...", else
  the one before), for pictures.py to read.
- **Footnotes:** each placed as a line ("Footnote 1: ...") after the paragraph (or table) citing it, the citation
  marked "[1]" where it stands.
- **Numbered lists:** Word writes their numbers ("Condition 3:", "a)", "iv."), not the text: they're written from the
  numbering definitions (levels, formats, label text, a style's own numbering) before each item's text.
- **Text boxes** (DrawingML shapes, and VML in older documents): a paragraph's own text leaves its text boxes out;
  each box's paragraphs and tables follow the paragraph anchoring it, read as the document's own. In a table cell a
  box's text joins the cell's. A copy Word keeps for older readers (mc:Fallback) is never read: its text, pictures
  and footnote marks would repeat the shape's. A plain text box isn't a picture; a drawing of grouped shapes is
  recorded as one whose text is read but not its arrangement.
- **Charts** (chart XML; chartxml.py): each read from the values it caches, as a line naming it ("Chart: Monthly use
  (clustered column chart); values: MWh; caption: Figure 2: ...", its caption the nearest caption paragraph) and
  tables of categories by series, after the paragraph anchoring it (after its table, in a cell). Charts of the
  newer kinds (chartex) are recorded as not read.
- **Equations** (Office Math): written as plain text where they stand, in a linear form: K_offset, (a+b)/(c),
  x^(2), √(x), ∑_(i=1)^(N) x_i, sin(θ), [a b; c d].
- **Comments:** each placed as a line after the paragraph (or table) holding its reference, naming its author and
  the text it comments on: 'Comment by Ana on "the design flow": Check against the 2025 census.'
- **Not read yet:** other drawings without a picture, each recorded as not read.

Needs python-docx (the `office` extra).
"""
import io
import re
from dataclasses import dataclass, field

from . import chartxml, tablerules
from .textdocs import Block, Picture, TextDocument

HEADING = re.compile(r"^(?:Heading|heading)\s*(\d)$")
# A caption: a paragraph in a caption style (Word's "Caption"; 3GPP's "TF", a figure's title), or one naming a figure
CAPTION_STYLES = ("caption", "tf")
FIGURE_TITLE = re.compile(r"^(?:Figure|Fig\.?|Diagram|Chart)\s*[A-Z]?[\d.\-\u2010-\u2013]+\w*", re.I)
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
V = "{urn:schemas-microsoft-com:vml}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
ANCHOR_CHARS = 100  # a comment's anchored text, at most this long (then "…")
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
CHARTEX = "http://schemas.microsoft.com/office/drawing/2014/chartex"
SHAPES = ("{http://schemas.microsoft.com/office/word/2010/wordprocessingGroup}wgp",   # grouped shapes
          "{http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas}wpc",  # a drawing canvas
          V + "group")
NESTED_INLINE_ROWS = 6  # a nested table this small is written into its cell; a larger one is read on its own
LAYOUT_CHARS = 200      # cells averaging this much text make a table without a header row a layout table
HEADER_CHARS = 40       # a header row's cells are filled and at most this long
WRAPPERS = ("w:sdt", "w:sdtContent", "w:customXml")  # content controls and custom markup: read through
DIGIT = re.compile(r"\d")
EMU_PER_POINT = 12700
LENGTH = re.compile(r"(width|height)\s*:\s*([\d.]+)\s*(pt|in|cm|mm|px)?", re.I)
POINTS_PER = {"pt": 1.0, "in": 72.0, "cm": 72 / 2.54, "mm": 72 / 25.4, "px": 0.75, None: 0.75}

def _qn(tag):
    from docx.oxml.ns import qn
    return qn(tag)

def _walk(element, boxes=False):
    """An element's descendants in order, without the copies Word keeps for older readers (mc:Fallback) and, unless
    boxes, without its text boxes' content."""
    skip = {MC + "Fallback"} | (set() if boxes else {_qn("w:txbxContent")})
    for child in element:
        if child.tag in skip:
            continue
        yield child
        if child.tag != M + "oMath":  # an equation is read whole (_math)
            yield from _walk(child, boxes)

def _boxes(element):
    """The text boxes an element anchors (not those inside them), in order."""
    for node in _walk(element):
        for child in node:
            if child.tag == _qn("w:txbxContent"):
                yield child

def paragraph_text(p, notes=None, boxes=False):
    """A paragraph's text with tracked insertions applied and deletions left out; with notes ({footnote id: its
    number}), each footnote reference marked "[n]". Its text boxes' text is left out, or with boxes, put after it."""
    out = []
    for node in _walk(p):
        tag = node.tag
        if tag == _qn("w:t"):
            out.append(node.text or "")
        elif tag in (_qn("w:tab"),):
            out.append("\t")
        elif tag in (_qn("w:br"), _qn("w:cr")):
            out.append("\n")
        elif notes is not None and tag == _qn("w:footnoteReference") and node.get(_qn("w:id")) in notes:
            out.append(f"[{notes[node.get(_qn('w:id'))]}]")
        elif tag == M + "oMath":
            out.append(_math(node))
    if boxes:
        out += [" " + _box_text(box, notes) for box in _boxes(p)]
    return "".join(out)

def _math(e):
    """An equation (Office Math) as linear text: fractions (a)/(b), scripts x_(i) and x^(2), roots √(x), sums and
    integrals ∑_(i=1)^(N) x, delimiters, functions, matrices [a b; c d]; an argument of one symbol unbracketed."""
    tag = e.tag[len(M):] if isinstance(e.tag, str) and e.tag.startswith(M) else ""
    part = lambda name: next((c for c in e if c.tag == M + name), None)
    text = lambda x: _math(x) if x is not None else ""
    arg = lambda x: (lambda t: t if len(t) <= 1 or t.replace(".", "").isalnum() else f"({t})")(text(x))
    prop = lambda holder, name, default: next((c.get(M + "val", default) for c in (part(holder) if part(holder) is not
                                                                                   None else ()) if c.tag == M + name),
                                               default)
    if tag == "t":
        return e.text or ""
    if tag.endswith("Pr") or tag == "ctrlPr":
        return ""
    if tag == "f":
        return f"{arg(part('num'))}/{arg(part('den'))}"
    if tag in ("sSup", "sSub", "sSubSup", "sPre"):
        sub = f"_{arg(part('sub'))}" if part("sub") is not None else ""
        sup = f"^{arg(part('sup'))}" if part("sup") is not None else ""
        return f"{sub}{sup}{text(part('e'))}" if tag == "sPre" else f"{text(part('e'))}{sub}{sup}"
    if tag == "rad":
        degree = text(part("deg"))
        return f"√{arg(part('e'))}" if not degree else f"root({degree})({text(part('e'))})"
    if tag == "d":
        begin, end, between = prop("dPr", "begChr", "("), prop("dPr", "endChr", ")"), prop("dPr", "sepChr", "|")
        return begin + between.join(text(c) for c in e if c.tag == M + "e") + end
    if tag == "nary":
        sign = prop("naryPr", "chr", "∫")
        sub = f"_{arg(part('sub'))}" if text(part("sub")) else ""
        sup = f"^{arg(part('sup'))}" if text(part("sup")) else ""
        return f"{sign}{sub}{sup} {text(part('e'))}"
    if tag == "func":
        body = text(part("e"))
        return text(part("fName")) + (body if body.startswith("(") else f"({body})")
    if tag in ("limLow", "limUpp"):
        return f"{text(part('e'))}{'_' if tag == 'limLow' else '^'}{arg(part('lim'))}"
    if tag == "eqArr":
        return "; ".join(text(c) for c in e if c.tag == M + "e")
    if tag == "m":
        rows = [" ".join(text(c) for c in row if c.tag == M + "e") for row in e if row.tag == M + "mr"]
        return "[" + "; ".join(rows) + "]"
    return "".join(_math(c) for c in e)

def _box_text(box, notes=None):
    """A text box's text on one line: its paragraphs and its tables' paragraphs, boxes within it included."""
    paragraphs = [q for child in _children(box, "w:p", "w:tbl")
                  for q in ([child] if child.tag == _qn("w:p") else [n for n in _walk(child) if n.tag == _qn("w:p")])]
    return " ".join(t for t in (paragraph_text(q, notes, True).strip() for q in paragraphs) if t)

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
        out[note.get(_qn("w:id"))] = " ".join(paragraph_text(p, boxes=True).strip() for p in _walk(note)
                                              if p.tag == _qn("w:p")).strip()
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

def _comments(document):
    """{comment id: (author, its text)} from the document's comments part (none: {})."""
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    from docx.oxml import parse_xml
    part = next((r.target_part for r in document.part.rels.values() if r.reltype == RT.COMMENTS and not r.is_external),
                None)
    if part is None:
        return {}
    root = parse_xml(part.blob)
    return {c.get(_qn("w:id")): (c.get(_qn("w:author")) or "an unnamed author",
                                 " ".join(t for t in (paragraph_text(p, boxes=True).strip() for p in _walk(c)
                                                      if p.tag == _qn("w:p")) if t))
            for c in root.iter(_qn("w:comment"))}

def _anchors(body):
    """{comment id: the text it comments on}, gathered in document order between its range marks."""
    open_, out = [], {}
    for node in _walk(body, boxes=True):
        if node.tag == _qn("w:commentRangeStart"):
            open_.append(node.get(_qn("w:id")))
            out.setdefault(open_[-1], [])
        elif node.tag == _qn("w:commentRangeEnd") and node.get(_qn("w:id")) in open_:
            open_.remove(node.get(_qn("w:id")))
        elif node.tag in (_qn("w:t"), M + "oMath") and open_:
            piece = node.text or "" if node.tag == _qn("w:t") else _math(node)
            for i in open_:
                out[i].append(piece)
    return {i: " ".join("".join(parts).split()) for i, parts in out.items()}

def _children(element, *tags):
    """An element's children with these tags, read through content controls and custom markup."""
    wanted, wrappers = {_qn(t) for t in tags}, {_qn(t) for t in WRAPPERS}
    for child in element:
        if child.tag in wanted:
            yield child
        elif child.tag in wrappers:
            yield from _children(child, *tags)

def _property(element, props, name):
    """A row's or cell's property element (w:trPr, w:tcPr), or None."""
    holder = element.find(_qn(props))
    return holder.find(_qn(name)) if holder is not None else None

def _number(element, props, name, default):
    found = _property(element, props, name)
    return int(found.get(_qn("w:val"), default)) if found is not None else default

@dataclass
class Cell:
    """A table cell placed on the grid: its text (small nested tables written in), the columns it covers, whether
    it continues a cell merged down from the row above, and its larger nested tables (read after the table)."""
    text: str
    first: int
    last: int
    continued: bool = False
    nested: list = field(default_factory=list)

def _grid(table, numbers):
    """[(w:tr, [Cell])]: each row's cells on the table's columns. A cell merged down repeats its text in the rows it
    covers; a deleted row (a tracked deletion) reads as empty."""
    rows, above = [], {}  # above: column -> the cell merged down into it
    for tr in _children(table, "w:tr"):
        deleted = _property(tr, "w:trPr", "w:del") is not None
        column, cells = _number(tr, "w:trPr", "w:gridBefore", 0), []
        for tc in _children(tr, "w:tc"):
            span = max(1, _number(tc, "w:tcPr", "w:gridSpan", 1))
            merge = _property(tc, "w:tcPr", "w:vMerge")
            restart = merge is not None and merge.get(_qn("w:val")) == "restart"
            if merge is not None and not restart and column in above and not deleted:
                cell = Cell(above[column].text, column, column + span - 1, continued=True)
            else:
                text, nested = ("", []) if deleted else _cell_text(tc, numbers)
                cell = Cell(text, column, column + span - 1, nested=nested)
                if restart:
                    above[column] = cell
                else:
                    above.pop(column, None)
            cells.append(cell)
            column += span
        rows.append((tr, cells))
    return rows

def _cell_text(tc, numbers):
    """(a cell's text, its larger nested tables): its paragraphs joined, each small nested table written in."""
    parts, nested = [], []
    for child in _children(tc, "w:p", "w:tbl"):
        if child.tag == _qn("w:p"):
            parts.append(paragraph_text(child, numbers, boxes=True).strip())
            continue
        grid = _grid(child, numbers)
        if len(grid) > NESTED_INLINE_ROWS:
            parts.append("(table below)")
            nested.append(child)
        else:
            parts.append("; ".join(_inline(cells) for _, cells in grid if any(c.text for c in cells)))
    return " ".join(parts).strip(), nested

def _inline(cells):
    """A small nested table's row as text: "Flow: 450 gpm" for a label and a value, else its cells by commas."""
    texts = [c.text for c in cells if c.text]
    return f"{texts[0]}: {texts[1]}" if len(texts) == 2 else ", ".join(texts)

def _header_rows(grid, marked=None):
    """How many rows head a table: those marked to repeat as a header (marked: their count, when the rows aren't Word's
    elements); else the first, and the next while the row above has a cell merged across (or one merged down into
    it) and the row holds no number (three at most)."""
    if marked is None:
        marked = 0
        for tr, _ in grid:
            if _property(tr, "w:trPr", "w:tblHeader") is None:
                break
            marked += 1
    if marked:
        return min(marked, len(grid))
    n = 1
    while n < min(len(grid) - 1, 3):
        before, row = grid[n - 1][1], grid[n][1]
        merged = any(c.last > c.first for c in before) or any(c.continued for c in row)
        if not merged or any(DIGIT.search(c.text) for c in row) or not any(c.text for c in row):
            break
        n += 1
    return n

def _labels(grid, heads):
    """Each column's label: its header cells' texts top to bottom, a merged cell's once ("Rated point > TDH (ft)")."""
    width = max((c.last + 1 for _, cells in grid for c in cells), default=0)
    out = []
    for column in range(width):
        path = []
        for _, cells in grid[:heads]:
            cell = next((c for c in cells if c.first <= column <= c.last), None)
            if cell is not None and cell.text and (not path or path[-1] != cell.text):
                path.append(cell.text)
        out.append(" > ".join(path))
    return out

def _joined(labels):
    """One label for a cell merged across columns: their shared path once, then each leaf ("A > B / C")."""
    labels = list(dict.fromkeys(label for label in labels if label))
    if len(labels) < 2:
        return labels[0] if labels else ""
    paths = [label.split(" > ") for label in labels]
    shared = 0
    while all(len(p) > shared + 1 and p[shared] == paths[0][shared] for p in paths):
        shared += 1
    leaves = " / ".join(" > ".join(p[shared:]) for p in paths)
    return " > ".join(paths[0][:shared] + [leaves])

def _layout(table, styles):
    """Whether a table lays out content rather than holding data (see the module's notes)."""
    rows = list(_children(table, "w:tr"))
    if not rows or any(_property(tr, "w:trPr", "w:tblHeader") is not None for tr in rows):
        return False
    cells = [list(_children(tr, "w:tc")) for tr in rows]
    if len(rows) == 1 or max(len(r) for r in cells) == 1:
        return True
    text = lambda tc: " ".join(paragraph_text(p) for p in _children(tc, "w:p")).strip()
    if all(0 < len(text(tc)) <= HEADER_CHARS for tc in cells[0]):
        return False  # a header row: data, however long or headed its cells
    flat = [tc for r in cells for tc in r]
    if any(HEADING.match(_style(p, styles)) for tc in flat for p in _children(tc, "w:p")):
        return True
    filled = [len(t) for t in map(text, flat) if t]
    return bool(filled) and sum(filled) / len(filled) >= LAYOUT_CHARS

def _style(paragraph_element, styles):
    ppr = paragraph_element.find(_qn("w:pPr"))
    sid = None
    if ppr is not None:
        ps = ppr.find(_qn("w:pStyle"))
        if ps is not None:
            sid = ps.get(_qn("w:val"))
    return styles.get(sid, sid or "Normal")

def _charts(element, boxes=False):
    """The charts (c:chart, naming their part) an element's drawings hold, in order."""
    for node in _walk(element, boxes):
        if node.tag == A + "graphicData" and node.get("uri") == CHART:
            yield from (c for c in node if c.tag == "{%s}chart" % CHART)

def _is_caption(text, style):
    style = style.casefold()
    return bool(text) and (style in CAPTION_STYLES or "caption" in style or bool(FIGURE_TITLE.match(text)))

def _caption_near(element, styles):
    """The caption of a chart in this paragraph: the next paragraph within two, or the one before, in a caption style
    or naming a figure; "" when none is."""
    after = [e for e in element.itersiblings() if e.tag == _qn("w:p")][:2]
    before = [e for e in element.itersiblings(preceding=True) if e.tag == _qn("w:p")][:1]
    for p in after + before:
        text = paragraph_text(p).strip()
        if _is_caption(text, _style(p, styles)):
            return " ".join(text.split())
    return ""

def _pictures(element, part, boxes=False):
    """[(the picture's part, its displayed size in points or None) or (None, what it is)] for each drawing,
    embedded object and VML picture in an element (with boxes, those in its text boxes too); a plain text box is
    none."""
    out = []
    kinds = {_qn("w:drawing"), _qn("w:object"), _qn("w:pict")}
    for node in (n for n in _walk(element, boxes) if n.tag in kinds):
        own = list(_walk(node))  # the drawing itself, not what its text boxes hold
        has_text = any(True for _ in _boxes(node))
        shapes = any(n.tag in SHAPES for n in own)
        uris = {n.get("uri") for n in own if n.tag == A + "graphicData"}
        if CHART in uris:
            continue  # a chart: read from its data (_charts)
        if node.tag == _qn("w:drawing"):
            blip = next((n for n in own if n.tag == A + "blip"), None)
            rid = blip.get(R + "embed") if blip is not None else None
            extent = next((n for n in own if n.tag == WP + "extent"), None)
            size = (int(extent.get("cx")) / EMU_PER_POINT, int(extent.get("cy")) / EMU_PER_POINT) \
                if extent is not None and extent.get("cx") and extent.get("cy") else None
            what = ("a chart of a newer kind (chartex), not read yet" if CHARTEX in uris
                    else "a chart or drawing without a picture")
        else:
            data = next((n for n in own if n.tag == V + "imagedata"), None)
            rid = data.get(R + "id") if data is not None else None
            shape = next((n for n in own if n.tag == V + "shape"), None)
            found = dict((k.lower(), float(v) * POINTS_PER[(u or "").lower() or None])
                         for k, v, u in LENGTH.findall(shape.get("style", "") if shape is not None else ""))
            size = (found["width"], found["height"]) if "width" in found and "height" in found else None
            what = "an embedded object without a preview"
        target = part.related_parts.get(rid) if rid else None
        if target is None and has_text:
            if not shapes:
                continue  # a text box: its text is read
            what = "a drawing of shapes (its text read, not its arrangement)"
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

    def note(element, n, where, boxes=False):
        for target, detail in _pictures(element, document.part, boxes):
            if target is None:
                images.append((1, n, where, detail))
            else:
                name = str(target.partname).rsplit("/", 1)[-1]
                found.append((n, target.blob, "." + name.rsplit(".", 1)[-1].lower(), detail, name))
    notes = _footnotes(document)
    numbers = {}  # footnote id: its number, in the order the body cites them
    remarks, anchors, placed = _comments(document), _anchors(document.element.body), set()

    def comment_lines(element):
        """A line for each comment whose reference the element holds (once each), after it."""
        for node in _walk(element, boxes=element.tag == _qn("w:tbl")):
            i = node.get(_qn("w:id")) if node.tag == _qn("w:commentReference") else None
            if i is None or i not in remarks or i in placed:
                continue
            placed.add(i)
            author, said = remarks[i]
            anchor = anchors.get(i, "")
            if len(anchor) > ANCHOR_CHARS:
                anchor = anchor[:ANCHOR_CHARS].rstrip() + "…"
            text = f'Comment by {author} on "{anchor}": {said}' if anchor else f"Comment by {author}: {said}"
            m = line(text)
            blocks.append(Block(1, m, m, text))

    def cited(element):
        """The footnote ids an element cites, numbered as they're met."""
        ids = [r.get(_qn("w:id")) for r in _walk(element, boxes=element.tag == _qn("w:tbl"))
               if r.tag == _qn("w:footnoteReference") and r.get(_qn("w:id")) in notes]
        for i in ids:
            numbers.setdefault(i, len(numbers) + 1)
        return ids

    def footnote_lines(ids):
        for i in ids:
            m = line(f"Footnote {numbers[i]}: {notes[i]}")
            blocks.append(Block(1, m, m, f"Footnote {numbers[i]}: {notes[i]}"))
    listing = Numbering(document)

    def chart(element, n, where, caption=""):
        """A chart's label and tables as lines, after line n; one whose data can't be read, recorded as not read."""
        part = document.part.related_parts.get(element.get(R + "id"))
        try:
            data = chartxml.read(part.blob)
            if not data.tables:
                raise ValueError("no series")
        except Exception as error:  # a damaged or unexpected part: noted, the rest of the document read
            images.append((1, n, where, f"a chart whose data couldn't be read ({type(error).__name__}: {error})"))
            return
        label = data.label(caption)
        m = line(label)
        blocks.append(Block(1, m, m, label))
        for header, rows in data.tables:
            first = line(" | ".join(header))
            row_lines = [first] + [line(" | ".join(row)) for row in rows]
            blocks.append(Block(1, first, len(lines), "\n".join(t for _, t in lines[first - 1:]), "table",
                                [header] + rows, row_lines, source="chart"))

    def paragraph(child):
        style = _style(child, styles)
        ids = cited(child)
        text = paragraph_text(child, numbers).strip()
        label = listing.label(child)
        if label and text:
            text = f"{label} {text}"
        n = line(text)
        styles_of[n] = style
        note(child, n, style)
        match = HEADING.match(style)
        if text and match:
            level = int(match.group(1))
            title = " ".join(text.split())
            headings.append((1, n, level, title))
            blocks.append(Block(1, n, n, title))
        elif text and not style.lower().startswith("toc"):
            blocks.append(Block(1, n, n, text))
        footnote_lines(ids)
        comment_lines(child)
        for found in _charts(child):
            chart(found, n, style, _caption_near(child, styles))
        for box in _boxes(child):  # after the paragraph anchoring it, as the document's own paragraphs
            content(_children(box, "w:p", "w:tbl"))

    counted = [0]  # the document's tables, in order, each named "table N" for the rules query

    def table(child, place=None):
        """A data table's rows as lines, its larger nested tables after it; a layout table's cells as content. A
        nested table (`place`: the line naming where it sits) leaves pictures and footnotes to its outer table."""
        if place is None and _layout(child, styles):
            for tr in _children(child, "w:tr"):
                for tc in _children(tr, "w:tc"):
                    content(_children(tc, "w:p", "w:tbl"))
            return
        ids = cited(child) if place is None else []
        grid = _grid(child, numbers)
        if not grid:
            return
        if place:
            n = line(place)
            blocks.append(Block(1, n, n, place))
        heads = _header_rows(grid)
        labels = _labels(grid, heads)
        header_lines = [line(" | ".join(c.text for c in cells)) for _, cells in grid[:heads]]
        rows, row_lines, row_headers, inner = [labels], [header_lines[0]], [], []
        for _, cells in grid[heads:]:
            rows.append([c.text for c in cells])
            row_headers.append([_joined(labels[c.first:c.last + 1]) for c in cells])
            row_lines.append(line(" | ".join(c.text for c in cells)))
            inner += [(cells, c) for c in cells if c.nested]
        first = header_lines[0]
        counted[0] += 1
        ruled = tablerules.from_cells(grid, heads, labels, row_lines[1:], place.rstrip(":") if place else "",
                                      f"table {counted[0]}")
        blocks.append(Block(1, first, len(lines), "\n".join(t for _, t in lines[first - 1:]), "table", rows,
                            row_lines, row_headers, grid=ruled))
        if place is None:
            note(child, first, "table", boxes=True)
        if place is None:
            comment_lines(child)
            for found in _charts(child, boxes=True):  # a chart in a cell: after its table
                chart(found, first, "table")
        for cells, cell in inner:
            where = ", ".join(t for t in (cells[0].text if cells[0] is not cell else "",
                                          _joined(labels[cell.first:cell.last + 1])) if t)
            for nested in cell.nested:
                table(nested, f"Table in {where}:" if where else "Table:")
        footnote_lines(ids)

    def content(elements):
        for child in elements:
            if child.tag == _qn("w:p"):
                paragraph(child)
            elif child.tag == _qn("w:tbl"):
                table(child)
    content(child for child in document.element.body.iterchildren() if child.tag in (_qn("w:p"), _qn("w:tbl")))
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
