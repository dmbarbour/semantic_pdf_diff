"""The controlled corpus as slide decks (.pptx; the adapters plan, milestone 3; from the closed evaluation benchmarks
plan: "the controlled corpus written as slides too, scored by the same keys"), and the decks' own difficulties.

- **A slide per section:** the document's title on a title slide; each section a slide titled by its heading, its
  paragraphs one text box's paragraphs, a bold caption its own text box, each table a table, each chart a chart
  (chart XML caching its series, as the Word knob writes them), a procedure diagram a picture (its WMF), a chart's
  or diagram's caption a text box under it.
- **notes** (a knob): sentences stating facts moved into their slide's speaker notes.
- **The decks are minimal:** presentation, slides, notes, charts and media parts, enough for the reader (and any
  reader of the format) but without the slide masters, layouts and theme PowerPoint needs to open one.
- **The key** is placed by the reader's own lines (pptx_key), as a Word document's is.

Byte for byte the same each time (representations.FIXED_TIME).
"""
import io
import re
import zipfile
from xml.sax.saxutils import escape

from .representations import FIXED_TIME

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
TABLE = "http://schemas.openxmlformats.org/drawingml/2006/table"
NAMESPACES = f'xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"'
TYPES = {"slide": f"{R}/slide", "notesSlide": f"{R}/notesSlide", "chart": f"{R}/chart", "image": f"{R}/image"}
CONTENT = {"presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
           "slide": "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
           "notesSlide": "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml",
           "chart": "application/vnd.openxmlformats-officedocument.drawingml.chart+xml"}
MEDIA = {"png": "image/png", "wmf": "image/x-wmf", "emf": "image/x-emf", "jpeg": "image/jpeg"}
WIDTH, HEIGHT = 12192000, 6858000      # a 16:9 slide, EMU
MARGIN, TOP = 457200, 1371600          # left margin; where a slide's body starts, under its title
LINE, ROW = 457200, 370840             # a text line's and a table row's height
EMU_PER_POINT = 12700
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

def _paragraphs(texts, numbered=False):
    number = '<a:pPr marL="342900" indent="-342900"><a:buAutoNum type="arabicPeriod"/></a:pPr>' if numbered else ""
    return "".join(f'<a:p>{number}<a:r><a:rPr lang="en-US"/><a:t>{escape(t)}</a:t></a:r></a:p>' for t in texts)

class Slide:
    """One slide's shapes, stacked down the slide from under its title, and its speaker notes."""
    def __init__(self, deck, number, title, hidden=False):
        self.deck, self.number, self.hidden = deck, number, hidden
        self.shapes, self.rels, self.notes = [], [], []
        self.y = TOP
        if title:
            self.shapes.append(self._sp(f'<p:nvPr><p:ph type="title"/></p:nvPr>', (MARGIN, 365125, WIDTH - 2 * MARGIN,
                                                                                    TOP - 457200), [title]))

    def _id(self):
        return len(self.shapes) + 2

    def _sp(self, props, box, texts, numbered=False):
        x, y, cx, cy = box
        return (f'<p:sp><p:nvSpPr><p:cNvPr id="{self._id()}" name="Shape {self._id()}"/><p:cNvSpPr/>{props}'
                f'</p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
                f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr><p:txBody><a:bodyPr wrap="square"/>'
                f'<a:lstStyle/>{_paragraphs(texts, numbered)}</p:txBody></p:sp>')

    def _place(self, height):
        box = (MARGIN, self.y, WIDTH - 2 * MARGIN, height)
        self.y += height + 91440
        return box

    def _rel(self, kind, target):
        rid = f"rId{len(self.rels) + 1}"
        self.rels.append((rid, kind, target))
        return rid

    def text(self, paragraphs, numbered=False):
        """A text box of paragraphs, under what's above it."""
        height = LINE * sum(1 + len(t) // 110 for t in paragraphs)
        self.shapes.append(self._sp('<p:nvPr/>', self._place(height), paragraphs, numbered))

    def table(self, rows, merges=()):
        """A table; merges [(row, column, last row, last column)] as PowerPoint writes them: the first cell spans
        (gridSpan, rowSpan), the cells it covers are kept, marked hMerge or vMerge."""
        columns = max(len(r) for r in rows)
        x, y, cx, cy = self._place(ROW * len(rows))
        grid = "".join(f'<a:gridCol w="{cx // columns}"/>' for _ in range(columns))
        marks = {}
        for r0, c0, r1, c1 in merges:
            marks[(r0, c0)] = (f' gridSpan="{c1 - c0 + 1}"' if c1 > c0 else "") + \
                              (f' rowSpan="{r1 - r0 + 1}"' if r1 > r0 else "")
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if (r, c) != (r0, c0):
                        marks[(r, c)] = ' hMerge="1"' if r == r0 or c > c0 else ' vMerge="1"'
        body = "".join(f'<a:tr h="{ROW}">' + "".join(
            f'<a:tc{marks.get((r, c), "")}><a:txBody><a:bodyPr/><a:lstStyle/>{_paragraphs([text])}</a:txBody>'
            '<a:tcPr/></a:tc>' for c, text in enumerate(row + [""] * (columns - len(row)))) + "</a:tr>"
            for r, row in enumerate(rows))
        self.shapes.append(self._frame("Table", (x, y, cx, cy), f'<a:graphicData uri="{TABLE}"><a:tbl>'
                                       f'<a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>{body}'
                                       f'</a:tbl></a:graphicData>'))

    def chart(self, xml):
        name = self.deck.part("ppt/charts/chart{}.xml", xml)
        rid = self._rel("chart", f"../charts/{name.rsplit('/', 1)[1]}")
        self.shapes.append(self._frame("Chart", self._place(3200400), f'<a:graphicData uri="{C}"><c:chart '
                                       f'xmlns:c="{C}" r:id="{rid}"/></a:graphicData>'))

    def picture(self, data, extension, size):
        """A picture at its size (points), as large as the slide allows."""
        name = self.deck.part("ppt/media/image{}." + extension, data)
        rid = self._rel("image", f"../media/{name.rsplit('/', 1)[1]}")
        width = min(WIDTH - 2 * MARGIN, round(size[0] * EMU_PER_POINT))
        x, y, cx, cy = self._place(round(width * size[1] / size[0]))
        self.shapes.append(f'<p:pic><p:nvPicPr><p:cNvPr id="{self._id()}" name="Picture {self._id()}"/><p:cNvPicPr/>'
                           f'<p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/>'
                           f'</a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{width}" '
                           f'cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')

    def _frame(self, kind, box, data):
        x, y, cx, cy = box
        return (f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{self._id()}" name="{kind} {self._id()}"/>'
                f'<p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="{x}" y="{y}"/>'
                f'<a:ext cx="{cx}" cy="{cy}"/></p:xfrm><a:graphic>{data}</a:graphic></p:graphicFrame>')

    def xml(self):
        hidden = ' show="0"' if self.hidden else ""
        return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<p:sld {NAMESPACES}{hidden}><p:cSld>'
                f'<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>'
                f'{"".join(self.shapes)}</p:spTree></p:cSld></p:sld>')

class Deck:
    """A minimal deck: slides in order, their parts (charts, media) numbered as added."""
    def __init__(self):
        self.slides, self.parts = [], {}  # parts: name -> bytes

    def slide(self, title=None, hidden=False):
        self.slides.append(Slide(self, len(self.slides) + 1, title, hidden))
        return self.slides[-1]

    def part(self, template, data):
        name = template.format(sum(1 for n in self.parts if n.startswith(template.split("{")[0])) + 1)
        self.parts[name] = data if isinstance(data, bytes) else data.encode()
        return name

    def save(self):
        files = {}
        rels = lambda items: ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="'
                              'http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(
                                  f'<Relationship Id="{i}" Type="{TYPES.get(k, k)}" Target="{t}"/>' for i, k, t in items)
                              + "</Relationships>")
        files["_rels/.rels"] = rels([("rId1", f"{R}/officeDocument", "ppt/presentation.xml")])
        ids = "".join(f'<p:sldId id="{255 + s.number}" r:id="rId{s.number}"/>' for s in self.slides)
        files["ppt/presentation.xml"] = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<p:presentation '
                                         f'{NAMESPACES}><p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="{WIDTH}" '
                                         f'cy="{HEIGHT}"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
        files["ppt/_rels/presentation.xml.rels"] = rels([(f"rId{s.number}", "slide", f"slides/slide{s.number}.xml")
                                                         for s in self.slides])
        overrides = [("/ppt/presentation.xml", CONTENT["presentation"])]
        for s in self.slides:
            items = list(s.rels)
            if s.notes:
                notes = f"ppt/notesSlides/notesSlide{s.number}.xml"
                files[notes] = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<p:notes {NAMESPACES}>'
                                '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
                                '</p:nvGrpSpPr><p:grpSpPr/><p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes"/><p:cNvSpPr/>'
                                '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr><p:spPr/><p:txBody>'
                                f'<a:bodyPr/><a:lstStyle/>{_paragraphs(s.notes)}</p:txBody></p:sp></p:spTree>'
                                '</p:cSld></p:notes>')
                files[f"ppt/notesSlides/_rels/notesSlide{s.number}.xml.rels"] = rels(
                    [("rId1", "slide", f"../slides/slide{s.number}.xml")])
                items.append((f"rId{len(items) + 1}", "notesSlide", f"../notesSlides/notesSlide{s.number}.xml"))
                overrides.append((f"/{notes}", CONTENT["notesSlide"]))
            files[f"ppt/slides/slide{s.number}.xml"] = s.xml()
            files[f"ppt/slides/_rels/slide{s.number}.xml.rels"] = rels(items)
            overrides.append((f"/ppt/slides/slide{s.number}.xml", CONTENT["slide"]))
        for name, data in self.parts.items():
            files[name] = data
            if name.startswith("ppt/charts/"):
                overrides.append((f"/{name}", CONTENT["chart"]))
        defaults = "".join(f'<Default Extension="{e}" ContentType="{t}"/>' for e, t in
                           [("rels", "application/vnd.openxmlformats-package.relationships+xml"),
                            ("xml", "application/xml")] + sorted(MEDIA.items()))
        files["[Content_Types].xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/'
            f'package/2006/content-types">{defaults}' + "".join(f'<Override PartName="{n}" ContentType="{t}"/>'
                                                                for n, t in overrides) + "</Types>")
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ["[Content_Types].xml"] + sorted(n for n in files if n != "[Content_Types].xml"):
                z.writestr(zipfile.ZipInfo(name, FIXED_TIME), files[name], compress_type=zipfile.ZIP_DEFLATED)
        return out.getvalue()

# --- the corpus as decks ------------------------------------------------------------------------------------------

def deck(project, notes=()):
    """A project's Markdown representation as a deck's bytes; with notes (printed values), each sentence printing one
    moved into its slide's speaker notes."""
    from .corpus import charts
    from .procedures import Procedure, wmf
    from .representations import NOT_SHOWN, chart_pictures, markdown
    from .word import blocks, chart_xml
    by_caption = {c.caption: c for c in charts(project)}
    pictures = chart_pictures(project) if any(isinstance(c, Procedure) for c in by_caption.values()) else {}
    pattern = lambda v: re.compile(rf"(?<![\w.,]){re.escape(v)}(?![\w]|[.,]\d)")
    out, slide, text = Deck(), None, []

    def flush():
        if text:
            slide.text(list(text))
            text.clear()
    for block in blocks(markdown(project)):
        kind = block[0]
        if kind == "heading":
            flush()
            slide = out.slide(block[2])
            continue
        if slide is None:
            slide = out.slide()
        if kind == "p":
            kept = []
            for sentence in SENTENCE.split(block[1]):
                (slide.notes if any(pattern(v).search(sentence) for v in notes) else kept).append(sentence)
            if kept:
                text.append(" ".join(kept))
            continue
        flush()
        caption = NOT_SHOWN.sub("", block[1]) if kind == "italic" else None
        if caption in by_caption:
            figure = by_caption[caption]
            if isinstance(figure, Procedure):
                _, (width, height), _ = pictures[caption]
                slide.picture(wmf(figure, width), "wmf", (width, height))
            else:
                slide.chart(chart_xml(figure))
            slide.text([caption])
        elif kind == "table":
            slide.table(block[1])
        else:
            slide.text([block[1]])
    flush()
    return out.save()

def pptx_key(project, data):
    """A deck's key, placed by the reader's own lines: table rows, a chart's data rows ("pptx-chart"), and a
    procedure diagram's facts at its picture ("pptx-figure")."""
    from semantic_pdf_diff.pptxdocs import read_pptx
    from .corpus import charts
    from .procedures import Procedure
    from .representations import key
    doc = read_pptx(data)
    rows = {n for b in doc.blocks if b.kind == "table" for n in b.row_lines}
    charted = {n for b in doc.blocks if b.kind == "table" and b.source == "chart" for n in b.row_lines[1:]}
    drawn = iter(doc.pictures)
    pictures = {number: next(drawn).line for number, c in enumerate(charts(project), 1) if isinstance(c, Procedure)}
    return key(project, [t for _, t in doc.lines], rows, "pptx", pictures, charted)

# Facts whose sentences move into speaker notes (the notes knob): each beside another in its paragraph
NOTED = ("chem.chlorine", "plant.finished_turbidity")

def documents(seed=1):
    """[(project, deck bytes)]: the decks' own difficulties (the notes knob)."""
    from .corpus import water_treatment
    project = water_treatment(seed)
    noted = water_treatment(seed)
    noted.id = f"{project.id}-notes"
    return [(noted, deck(noted, [project.fact(f).value for f in NOTED]))]

def write(folder, project, data):
    """Write <id>.pptx and its key into folder; returns the deck's path."""
    import json
    from pathlib import Path
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{project.id}.pptx"
    path.write_bytes(data)
    (folder / f"{project.id}.key.json").write_text(json.dumps(pptx_key(project, data), indent=1, ensure_ascii=False)
                                                   + "\n", encoding="utf-8")
    return path
