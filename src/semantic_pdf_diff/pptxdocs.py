"""Slide decks (.pptx; docs/plans/multi-format-adapters-2026-09-23.md, milestone 3), read through the text reader as
Word documents are (docxdocs.py): a deck becomes a TextDocument whose pages are its slides and whose lines are its
shapes' paragraphs, table rows and speaker notes, so sections, grouping, the context levers and the task core work
unchanged, and a claim's locator names its slide and lines.

The owner (2026-10-04), choosing to read slides as Word documents are rather than drawing them (no renderer is
assumed): "This looks good to me, including the recommendation to read slides like Word docs."

- **Slides in the deck's order,** each a page. Its title is its heading; failing a title placeholder, its subtitle
  (some decks title every slide so), or a text box near the top holding one short paragraph; failing all, "Slide 3".
  So each slide is a section. A hidden slide is read, marked "(Hidden slide)".
- **Shapes in reading order:** the title, then the rest top to bottom and left to right, a group's shapes together.
  A placeholder without a position of its own takes its layout's (or master's). Each paragraph is a line; an
  automatically numbered one is written with its number ("2.", "b)").
- **Tables** on their grid, as Word's are: a cell merged across asked under its columns' labels, one merged down
  repeated in each row it covers, two header rows labelling columns by their path.
- **Charts** read from the values they cache (chartxml.py): a line naming the chart, then its tables.
- **Pictures** read as a Word document's are (pictures.py), each with its slide's title as its caption; an embedded
  object by its preview.
- **Speaker notes** after the slide's content, the first paragraph marked "Speaker notes:".
- **Recorded as not read:** a slide's arrangement of shapes joined by connectors (a diagram drawn with shapes: its
  text is read, not which box an arrow joins), SmartArt, media, an object without a preview; comments.

Needs lxml (with the `office` extra).
"""
import io
import posixpath
import re
import zipfile
from dataclasses import dataclass

from . import chartxml
from .docxdocs import Cell, _format, _header_rows, _joined, _labels
from .textdocs import Block, Picture, TextDocument

P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
TABLE = "http://schemas.openxmlformats.org/drawingml/2006/table"
DIAGRAM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
RELS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
EMU_PER_POINT = 12700
TITLES = ("title", "ctrTitle")
BANDS = 24  # reading order: a slide's height in bands, shapes read band by band, left to right within one
TOP = 0.15  # a text box starting this near the top (a share of the slide's height) may be an untitled slide's title
TITLE_CHARS = 100
NUMBERS = {"arabic": "decimal", "alphaLc": "lowerLetter", "alphaUc": "upperLetter", "romanLc": "lowerRoman",
           "romanUc": "upperRoman"}

class Package:
    """A zip of parts with relationships (Open Packaging Conventions): enough to follow a deck's parts."""
    def __init__(self, data):
        self.zip = zipfile.ZipFile(io.BytesIO(bytes(data)))
        self.names = set(self.zip.namelist())

    def read(self, name):
        return self.zip.read(name)

    def xml(self, name):
        from lxml import etree
        return etree.fromstring(self.read(name))

    def rels(self, name):
        """{relationship id: (its type's last word, the target part's name)}; external targets left out."""
        folder, base = posixpath.split(name)
        rels = posixpath.join(folder, "_rels", base + ".rels")
        if rels not in self.names:
            return {}
        out = {}
        for rel in self.xml(rels):
            if rel.get("TargetMode") == "External":
                continue
            target = posixpath.normpath(posixpath.join(folder, rel.get("Target")))
            out[rel.get("Id")] = (rel.get("Type").rsplit("/", 1)[-1], target.lstrip("/"))
        return out

    def related(self, name, kind):
        return next((target for rel, target in self.rels(name).values() if rel == kind), None)

@dataclass
class Item:
    """One thing on a slide, placed: a shape's paragraphs, a table, a chart, a picture, or a group of them."""
    kind: str      # "text", "title", "table", "chart", "picture", "group", "connector", "unread"
    box: tuple     # (x, y, width, height) in EMU on the slide
    payload: object = None

def _box(element, placeholders=None):
    """An element's (x, y, cx, cy) from its xfrm, or its placeholder's on the layout or master; None if neither."""
    xfrm = next((x for x in element.iter(A + "xfrm", P + "xfrm") if x.getparent().getparent() is element
                 or x.getparent() is element), None)
    if xfrm is not None and xfrm.find(A + "off") is not None:
        off, ext = xfrm.find(A + "off"), xfrm.find(A + "ext")
        return (int(off.get("x")), int(off.get("y")), int(ext.get("cx", 0)), int(ext.get("cy", 0)))
    ph, known = _placeholder(element), placeholders or {}
    if not ph:
        return None
    return known.get(ph[0]) if ph[0] in TITLES else known.get(ph[1]) or known.get(ph[0])

def _placeholder(element):
    """(type, idx) of a placeholder shape, or None."""
    ph = next(element.iter(P + "ph"), None)
    return (ph.get("type", "body"), ph.get("idx", "0")) if ph is not None else None

def _placeholders(package, slide):
    """{type or idx: box} of the slide's layout's placeholders, its master's under them."""
    out = {}
    layout = package.related(slide, "slideLayout")
    master = package.related(layout, "slideMaster") if layout else None
    for part in filter(None, (master, layout)):
        for shape in package.xml(part).iter(P + "sp"):
            ph, box = _placeholder(shape), _box(shape)
            if ph and box:
                out[ph[0]] = out[ph[1]] = box
    return out

def _children(element):
    """A tree's children, Word's copies for older readers (mc:Fallback) left out, mc:Choice read through."""
    for child in element:
        if child.tag == MC + "AlternateContent":
            choice = child.find(MC + "Choice")
            yield from _children(choice if choice is not None else child.find(MC + "Fallback"))
        else:
            yield child

def _paragraph_text(p):
    out = []
    for node in p.iter(A + "t", A + "br", A + "tab"):
        out.append(node.text or "" if node.tag == A + "t" else "\n" if node.tag == A + "br" else "\t")
    return "".join(out).strip()

def _paragraphs(body):
    """A text body's paragraphs as text, an automatically numbered one with its number ("2.", "b)")."""
    out, counts = [], {}
    for p in body.iter(A + "p"):
        text = _paragraph_text(p)
        props = p.find(A + "pPr")
        level = int(props.get("lvl", 0)) if props is not None else 0
        auto = props.find(A + "buAutoNum") if props is not None else None
        if auto is not None and text:
            counts = {k: v for k, v in counts.items() if k <= level}
            counts[level] = counts.get(level, int(auto.get("startAt", 1)) - 1) + 1
            text = f"{_number(counts[level], auto.get('type', 'arabicPeriod'))} {text}"
        elif text:
            counts = {k: v for k, v in counts.items() if k < level}
        out.append(text)
    return out

def _number(n, kind):
    """An automatic number as its type writes it: arabicPeriod 3 is "3.", alphaLcParenR is "c)"."""
    style = next((s for s in NUMBERS if kind.startswith(s)), "arabic")
    shown = _format(n, NUMBERS[style])
    rest = kind[len(style):]
    return {"Period": f"{shown}.", "ParenR": f"{shown})", "ParenBoth": f"({shown})"}.get(rest, shown)

def _grid(table):
    """[(row, [Cell])]: a table's cells on its grid. A cell merged across spans its columns (the cells it covers,
    hMerge, are left out); one merged down repeats its text in the rows it covers (vMerge)."""
    rows, above = [], {}
    for tr in table.iter(A + "tr"):
        cells = []
        for column, tc in enumerate(tc for tc in tr if tc.tag == A + "tc"):
            if tc.get("hMerge") in ("1", "true"):
                continue
            span = int(tc.get("gridSpan", 1))
            if tc.get("vMerge") in ("1", "true") and column in above:
                cells.append(Cell(above[column].text, column, column + span - 1, continued=True))
                continue
            body = tc.find(A + "txBody")
            cell = Cell(" ".join(t for t in _paragraphs(body) if t) if body is not None else "", column,
                        column + span - 1)
            if int(tc.get("rowSpan", 1)) > 1:
                above[column] = cell
            else:
                above.pop(column, None)
            cells.append(cell)
        rows.append((tr, cells))
    return rows

def _items(package, slide, tree, placeholders, transform=None):
    """The things on a slide (or in a group), each placed on the slide."""
    out = []
    place = transform or (lambda box: box)
    for element in _children(tree):
        tag = element.tag
        if tag in (P + "nvGrpSpPr", P + "grpSpPr"):
            continue
        box = _box(element, placeholders)
        box = place(box) if box else (0, 0, 0, 0)
        if tag == P + "sp":
            body = element.find(P + "txBody")
            if body is None:
                continue
            ph = _placeholder(element)
            kind = "title" if ph and ph[0] in TITLES else "subtitle" if ph and ph[0] == "subTitle" else "text"
            out.append(Item(kind, box, _paragraphs(body)))
        elif tag == P + "grpSp":
            out.append(Item("group", box, _items(package, slide, element, placeholders, _group(element, place))))
        elif tag == P + "cxnSp":
            out.append(Item("connector", box))
        elif tag == P + "pic":
            out.append(_picture(package, slide, element, box))
        elif tag == P + "graphicFrame":
            data = next(element.iter(A + "graphicData"), None)
            uri = data.get("uri") if data is not None else ""
            if uri == TABLE:
                out.append(Item("table", box, next(data.iter(A + "tbl"))))
            elif uri == CHART:
                reference = next(data.iter("{%s}chart" % CHART), None)
                target = package.rels(slide).get(reference.get(R + "id")) if reference is not None else None
                out.append(Item("chart", box, target[1] if target else None))
            elif next(data.iter(A + "blip"), None) is not None if data is not None else False:  # an object's preview
                out.append(_picture(package, slide, data, box))
            else:
                what = "SmartArt" if uri == DIAGRAM else "an embedded object or medium without a preview"
                out.append(Item("unread", box, what))
    return out

def _group(group, place):
    """How a group's children are placed on the slide: their own frame (chOff, chExt) mapped onto the group's."""
    xfrm = next(group.iter(A + "xfrm"), None)
    parts = {c.tag[len(A):]: c for c in xfrm} if xfrm is not None else {}
    if not all(k in parts for k in ("off", "ext", "chOff", "chExt")):
        return place
    ox, oy = int(parts["off"].get("x")), int(parts["off"].get("y"))
    cx, cy = int(parts["ext"].get("cx")) or 1, int(parts["ext"].get("cy")) or 1
    hx, hy = int(parts["chOff"].get("x")), int(parts["chOff"].get("y"))
    wx, wy = int(parts["chExt"].get("cx")) or 1, int(parts["chExt"].get("cy")) or 1
    return lambda b: place((ox + (b[0] - hx) * cx // wx, oy + (b[1] - hy) * cy // wy, b[2] * cx // wx, b[3] * cy // wy))

def _picture(package, slide, element, box):
    blip = next(element.iter(A + "blip"), None)
    target = package.rels(slide).get(blip.get(R + "embed")) if blip is not None else None
    if target is None or target[1] not in package.names:
        return Item("unread", box, "a picture whose image isn't in the deck")
    name = target[1]
    return Item("picture", box, (name, package.read(name)))

def _ordered(items, height):
    """Reading order: the title first, then band by band from the top, left to right within a band."""
    band = max(1, height // BANDS)
    key = lambda item: (item.kind not in ("title", "subtitle"), item.box[1] // band, item.box[0])
    return sorted(items, key=key)

def read_pptx(data):
    """A .pptx's TextDocument: slides as pages, shapes' paragraphs, table rows and speaker notes as lines, each
    slide's title its heading, pictures noted with their slide."""
    package = Package(data)
    presentation = "ppt/presentation.xml"
    root = package.xml(presentation)
    size = root.find(P + "sldSz")
    height = int(size.get("cy")) if size is not None else 6858000
    rels = package.rels(presentation)
    slides = [rels[s.get(R + "id")][1] for s in root.iter(P + "sldId") if s.get(R + "id") in rels]
    lines, blocks, headings, images, pictures = [], [], [], [], []

    def line(page, text):
        lines.append((page, text))
        return len(lines)

    for page, slide in enumerate(slides, 1):
        tree = package.xml(slide)
        items = _ordered(_items(package, slide, next(tree.iter(P + "spTree")), _placeholders(package, slide)), height)
        named = next((item for kind in ("title", "subtitle") for item in items if item.kind == kind), None) or next(
            (item for item in items if item.kind == "text" and item.box[1] < height * TOP
             and len([t for t in item.payload if t]) == 1 and len(next(t for t in item.payload if t)) <= TITLE_CHARS),
            None)
        title = " ".join(t for t in named.payload if t) if named else ""
        heading = " ".join(title.split()) or f"Slide {page}"
        n = line(page, heading)
        headings.append((page, n, 1, heading))
        blocks.append(Block(page, n, n, heading))
        if tree.get("show") in ("0", "false"):
            n = line(page, "(Hidden slide)")
            blocks.append(Block(page, n, n, "(Hidden slide)"))
        connectors = 0

        def emit(item):
            nonlocal connectors
            if item.kind == "group":
                for child in _ordered(item.payload, height):
                    emit(child)
            elif item.kind in ("text", "subtitle", "title"):
                for text in item.payload:
                    if text:
                        m = line(page, text)
                        blocks.append(Block(page, m, m, text))
            elif item.kind == "table":
                table(page, item.payload)
            elif item.kind == "chart":
                chart(page, item.payload)
            elif item.kind == "picture":
                name, data = item.payload
                m = line(page, "")  # the picture's place among the slide's lines
                size = (item.box[2] / EMU_PER_POINT, item.box[3] / EMU_PER_POINT) if item.box[2] else None
                pictures.append(Picture(m, data, "." + name.rsplit(".", 1)[-1].lower(), size,
                                        title, name.rsplit("/", 1)[-1], page))
            elif item.kind == "connector":
                connectors += 1
            elif item.kind == "unread":
                images.append((page, len(lines), "slide", item.payload))

        def table(page, element):
            grid = _grid(element)
            if not grid:
                return
            heads = _header_rows(grid)
            labels = _labels(grid, heads)
            header_lines = [line(page, " | ".join(c.text for c in cells)) for _, cells in grid[:heads]]
            rows, row_lines, row_headers = [labels], [header_lines[0]], []
            for _, cells in grid[heads:]:
                rows.append([c.text for c in cells])
                row_headers.append([_joined(labels[c.first:c.last + 1]) for c in cells])
                row_lines.append(line(page, " | ".join(c.text for c in cells)))
            first = header_lines[0]
            blocks.append(Block(page, first, len(lines), "\n".join(t for _, t in lines[first - 1:]), "table", rows,
                                row_lines, row_headers))

        def chart(page, part):
            try:
                found = chartxml.read(package.read(part))
                if not found.tables:
                    raise ValueError("no series")
            except Exception as error:  # a damaged or missing part: noted, the rest of the deck read
                images.append((page, len(lines), "slide", f"a chart whose data couldn't be read "
                                                          f"({type(error).__name__}: {error})"))
                return
            label = found.label()
            m = line(page, label)
            blocks.append(Block(page, m, m, label))
            for header, rows in found.tables:
                first = line(page, " | ".join(header))
                row_lines = [first] + [line(page, " | ".join(row)) for row in rows]
                blocks.append(Block(page, first, len(lines), "\n".join(t for _, t in lines[first - 1:]), "table",
                                    [header] + rows, row_lines, source="chart"))

        for item in items:
            if item is not named:
                emit(item)
        if connectors:
            images.append((page, len(lines), "slide", f"a diagram of shapes joined by {connectors} connector(s): "
                                                      "its text read, not its arrangement"))
        notes = package.related(slide, "notesSlide")
        if notes:
            said = [t for shape in package.xml(notes).iter(P + "sp")
                    if (_placeholder(shape) or ("",))[0] == "body" and shape.find(P + "txBody") is not None
                    for t in _paragraphs(shape.find(P + "txBody")) if t]
            for k, text in enumerate(said):
                text = f"Speaker notes: {text}" if k == 0 else text
                m = line(page, text)
                blocks.append(Block(page, m, m, text))
    return TextDocument(max(1, len(slides)), lines, blocks, headings, images, pictures)
