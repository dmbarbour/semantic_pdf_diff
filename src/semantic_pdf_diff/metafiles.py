"""Pictures drawn as Windows metafiles (WMF, EMF, EMF+), drawn into a PDF page (docs/plans/multi-format-adapters-
2026-09-23.md, "Pictures in Word documents").

The vendored metafile_render (vendor/README.md) plays a picture's records back into drawing commands; this module
draws the commands into a one-page PDF, in order:
- **paths** as vector paths, filled and stroked as the records say, clipped to the region their clip operations make
  (each distinct stack's region computed once, as polygons, with pyclipper: GDI's clips replace, intersect, unite,
  exclude and xor, and PDF's only intersect)
- **text** as text, in a PDF's built-in fonts (Helvetica, Times or Courier, by the record's face), measured with their
  metrics: the picture's labels are a text layer, and the page draws alike on every machine, whatever its fonts
- **bitmaps** as images, where they fall in the drawing order
The page is the picture's size in points (a metafile's logical inch is 72 points). What can't be drawn faithfully is
counted in the result's `skipped`, never silently: raster operations other than copying, pattern and hatch brushes
drawn solid, characters a built-in font can't encode.
"""
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

from .vendor.metafile_render.backends.bitmap import _crop_destination, _crop_source, _decode_dib
from .vendor.metafile_render.backends.mapping import _document_matrix, _mapped_rect
from .vendor.metafile_render.commands import ClearCommand, DrawImageCommand, DrawPathCommand, DrawTextCommand
from .vendor.metafile_render.context import ReplayContext
from .vendor.metafile_render.geometry import FlattenBudget, flatten_path, transform_path
from .vendor.metafile_render.parser import parse_metafile

DPI = 72               # device pixels are points
COPY_PEN = 13          # R2_COPYPEN: a path drawn as it is
NOP = 11               # R2_NOP: nothing drawn
SRCCOPY = 0x00CC0020   # a bitmap copied as it is
# Bitmaps combined with what's under them, as masks draw icons: ANDed (white leaves the page as it was) and ORed or
# XORed (black does): each drawn with that colour transparent, so a mask and its image together draw the icon
SRCAND, SRCPAINT, SRCINVERT = 0x008800C6, 0x00EE0086, 0x00660046
TRANSPARENT_WHERE = {SRCAND: (255, 255, 255), SRCPAINT: (0, 0, 0), SRCINVERT: (0, 0, 0)}
CLIP_SCALE = 100       # pyclipper's integer grid: hundredths of a point
FLATNESS = 0.05        # how far a clip path's flattened curve may stray, in points
# GDI's cell, as the faces metafiles name most (Arial's): its top lies this far above the baseline, its bottom below
ASCENT, DESCENT = 0.905, 0.212

@dataclass
class Picture:
    """A metafile drawn into a page: the PDF's bytes, its size in points, and what wasn't drawn as recorded."""
    pdf: bytes
    width: float
    height: float
    source_format: str           # emf or wmf
    emfplus_mode: str            # none, dual (EMF+ with a GDI fallback) or only
    drawn: Counter = field(default_factory=Counter)
    skipped: Counter = field(default_factory=Counter)
    diagnostics: tuple = ()

def draw(data):
    """A metafile's Picture (raises the vendored MetafileError, or ValueError, for one that can't be read)."""
    context = ReplayContext()
    document = parse_metafile(data, dpi=DPI, context=context)
    width, height = float(document.width), float(document.height)
    doc = pymupdf.open()
    page = doc.new_page(width=width, height=height)
    writer = _Writer(page, _document_matrix(document), width, height)
    for command in document.commands:
        writer.command(command)
    writer.finish(doc)
    return Picture(doc.tobytes(garbage=3, deflate=True), width, height, document.source_format,
                   document.emfplus_mode, writer.drawn, writer.skipped,
                   tuple(f"{d.code}: {d.message}" for d in document.diagnostics))

def _number(value):
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text

def _color(color, stroke=False):
    rgb = " ".join(_number(c / 255) for c in (color.red, color.green, color.blue))
    return f"{rgb} {'RG' if stroke else 'rg'}"

def _escape(raw):
    out = bytearray()
    for b in raw:
        out += b"\\" + bytes([b]) if b in b"()\\" else f"\\{b:03o}".encode() if b < 32 or b > 126 else bytes([b])
    return out.decode("ascii")

# The built-in fonts by face and style: (regular, bold, italic, bold italic)
FONTS = {"sans": ("helv", "hebo", "heit", "hebi"), "serif": ("tiro", "tibo", "tiit", "tibi"),
         "mono": ("cour", "cobo", "coit", "cobi")}
SERIF = ("times", "serif", "roman", "georgia", "cambria", "garamond", "book antiqua", "palatino", "century")
MONO = ("courier", "mono", "consolas", "lucida console", "menlo")

def font_name(font):
    """The built-in font standing in for a record's face: its family by name, its style by weight and slant."""
    face = font.face_name.casefold()
    family = "mono" if any(m in face for m in MONO) else "serif" if any(s in face for s in SERIF) else "sans"
    return FONTS[family][(font.weight >= 600) + 2 * bool(font.italic)]

class _Writer:
    """One page's content stream, built command by command (device coordinates, y down)."""
    def __init__(self, page, matrix, width, height):
        self.page, self.matrix, self.width, self.height = page, matrix, width, height
        self.ops = [f"q 1 0 0 -1 0 {_number(height)} cm"]  # y down, as the device draws
        self.fonts, self.alphas, self.images = set(), {}, {}
        self.regions = {}  # clip stack: its region's polygons (None: nothing visible)
        self.drawn, self.skipped = Counter(), Counter()

    # --- commands

    def command(self, command):
        clip = self._clip(command.clip)
        if clip is None:
            self.skipped["clipped away"] += 1
            return
        if isinstance(command, DrawPathCommand):
            body = self._path(command)
        elif isinstance(command, DrawTextCommand):
            body = self._text(command)
        elif isinstance(command, DrawImageCommand):
            body = self._image(command)
        elif isinstance(command, ClearCommand):
            body = self._clear(command)
        else:
            self.skipped[type(command).__name__] += 1
            return
        if body:
            self.ops.append("q " + clip + body + " Q")

    def _path(self, command):
        if command.rop2 == NOP:
            return ""
        if command.rop2 != COPY_PEN:
            self.skipped[f"path raster operation {command.rop2}"] += 1
            return ""
        stroke = command.stroke and not command.pen.null
        fill = command.fill and command.brush.kind != "null"
        if not stroke and not fill:
            return ""
        parts = [self._segments(transform_path(command.path, self.matrix))]
        if fill:
            if command.brush.kind in ("hatch", "pattern"):
                self.skipped[f"{command.brush.kind} brush drawn solid"] += 1
            parts.insert(0, _color(command.brush.color))
        if stroke:
            parts.insert(0, self._pen(command.pen, command.miter_limit))
        alpha = self._alpha(command.brush.color.alpha if fill else 255, command.pen.color.alpha if stroke else 255)
        operator = ("B" if stroke else "f") if fill else "S"
        if fill and command.fill_rule == "evenodd":
            operator += "*"
        self.drawn["path"] += 1
        return alpha + " ".join(parts) + " " + operator

    def _pen(self, pen, miter_limit):
        scale = (abs(self.matrix.a) + abs(self.matrix.d)) / 2
        width = pen.width if pen.cosmetic else pen.width * scale
        cap = {"flat": 0, "round": 1, "square": 2}[pen.cap]
        join = {"miter": 0, "round": 1, "bevel": 2}[pen.join]
        out = f"{_color(pen.color, stroke=True)} {_number(max(width, 0.25))} w {cap} J {join} j {_number(max(miter_limit, 1))} M"
        if pen.dashes:
            dash = 1 if pen.cosmetic else scale
            out += " [" + " ".join(_number(max(d * dash, 0.1)) for d in pen.dashes) + "] 0 d"
        return out

    def _segments(self, path):
        out = []
        for segment in path.segments:
            if segment.verb == "Z":
                out.append("h")
            else:
                points = " ".join(f"{_number(x)} {_number(y)}" for x, y in segment.points)
                out.append(points + {"M": " m", "L": " l", "C": " c"}[segment.verb])
        return " ".join(out)

    def _clear(self, command):
        if command.color.alpha == 0:
            return ""
        rect = _mapped_rect(command.bounds, self.matrix).normalized()
        self.drawn["clear"] += 1
        return (self._alpha(command.color.alpha, 255) + _color(command.color) +
                f" {_number(rect.left)} {_number(rect.top)} {_number(rect.width)} {_number(rect.height)} re f")

    def _text(self, command):
        name = font_name(command.font)
        self.fonts.add(name)
        size = max(command.font_height * max(abs(self.matrix.d), 1e-9), 0.5)
        positions = [self.matrix.transform_point(p) for p in (command.positions or (command.origin,))]
        texts = tuple(command.text) if command.positions else (command.text,)
        horizontal = command.alignment.horizontal
        if command.positions and command.advance_end is not None:  # a positioned run aligned as a whole
            factor = {"left": 0.0, "center": 0.5, "right": 1.0}[horizontal]
            start, end = self.matrix.transform_point(command.origin), self.matrix.transform_point(command.advance_end)
            positions = [(x - (end[0] - start[0]) * factor, y - (end[1] - start[1]) * factor) for x, y in positions]
            horizontal = "left"
        rise = {"top": ASCENT, "baseline": 0.0, "bottom": -DESCENT}[command.alignment.vertical] * size
        cos, sin = _rotation(command.rotation)
        out = []
        if command.opaque:
            out.append(self._background(command, positions, texts, name, size, rise, cos, sin))
        out.append(self._alpha(command.color.alpha, 255) + _color(command.color) + f" BT /{name} {_number(size)} Tf")
        narrow = _fit(command.text, positions, name, size) if command.positions else 1.0
        if narrow < 0.97:  # the record's advances are tighter than the built-in font: narrow its glyphs to them
            out.append(f"{_number(narrow * 100)} Tz")
            self.drawn["text narrowed to its advances"] += 1
        for (x, y), text in zip(positions, texts):
            raw = text.encode("cp1252", errors="replace")
            missing = sum(1 for ch in text if not ch.encode("cp1252", errors="ignore"))
            if missing:
                self.skipped["characters a built-in font can't show"] += missing
            shift = {"left": 0.0, "center": 0.5, "right": 1.0}[horizontal] * pymupdf.get_text_length(
                raw.decode("cp1252"), fontname=name, fontsize=size)
            # the baseline's start: back along the baseline by the alignment's share, down to it from the anchor
            bx, by = x - shift * cos - rise * sin, y + shift * sin + rise * cos
            out.append(f"{_number(cos)} {_number(-sin)} {_number(-sin)} {_number(-cos)} {_number(bx)} {_number(by)} Tm "
                       f"({_escape(raw)}) Tj")
        out.append("ET")
        self.drawn["text"] += 1
        return " ".join(out)

    def _background(self, command, positions, texts, name, size, rise, cos, sin):
        if command.bounds is not None:
            r = _mapped_rect(command.bounds, self.matrix).normalized()
            left, top, width, height = r.left, r.top, r.width, r.height
        else:  # the text's cell, unturned (a turned one with an opaque background is rare)
            left, y = positions[0]
            width = sum(pymupdf.get_text_length(t, fontname=name, fontsize=size) for t in texts)
            top, height = y + rise - ASCENT * size, (ASCENT + DESCENT) * size
        return (self._alpha(command.background_color.alpha, 255) + _color(command.background_color) +
                f" {_number(left)} {_number(top)} {_number(width)} {_number(height)} re f ")

    def _image(self, command):
        if command.rop not in (SRCCOPY, 0) and command.rop not in TRANSPARENT_WHERE:
            self.skipped[f"bitmap raster operation {command.rop:#x}"] += 1
            return ""
        from io import BytesIO
        image, fraction = _crop_source(_decode_dib(command, None), command.source)
        if image is None:
            self.skipped["bitmap unreadable"] += 1
            return ""
        if command.rop in TRANSPARENT_WHERE:
            image = _keyed(image.convert("RGBA"), TRANSPARENT_WHERE[command.rop])
            self.drawn["bitmap combined as a mask"] += 1
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        corners = [self.matrix.transform_point(p) for p in _crop_destination(command.destination, fraction)]
        xs, ys = [p[0] for p in corners], [p[1] for p in corners]
        rect = pymupdf.Rect(min(xs), min(ys), max(xs), max(ys))
        if rect.is_empty:
            return ""
        xref = self.page.insert_image(rect, stream=buffer.getvalue(), keep_proportion=False)
        name = next(i[7] for i in self.page.get_images(full=True) if i[0] == xref)
        self.drawn["image"] += 1
        # the unit square's bottom-left at the rectangle's bottom (y down), its top at the rectangle's top
        return f"{_number(rect.width)} 0 0 {_number(-rect.height)} {_number(rect.x0)} {_number(rect.y1)} cm /{name} Do"

    def _alpha(self, fill, stroke):
        if fill == 255 and stroke == 255:
            return ""
        key = (fill, stroke)
        self.alphas.setdefault(key, f"GS{fill}_{stroke}")
        return f"/{self.alphas[key]} gs "

    # --- clipping

    def _clip(self, clip):
        """The operators clipping to a stack's region ("" for none), or None when it leaves nothing."""
        if not clip:
            return ""
        if clip not in self.regions:
            self.regions[clip] = _region(clip, self.matrix, self.width, self.height)
        polygons = self.regions[clip]
        if polygons is None:
            return None
        return " ".join(" ".join(f"{_number(x / CLIP_SCALE)} {_number(y / CLIP_SCALE)} {'m' if i == 0 else 'l'}"
                                 for i, (x, y) in enumerate(polygon)) + " h" for polygon in polygons) + " W n "

    def finish(self, doc):
        self.ops.append("Q")
        for name in sorted(self.fonts):
            self.page.insert_font(fontname=name)
        if self.alphas:
            resources = doc.xref_get_key(self.page.xref, "Resources")
            target = int(resources[1].split()[0]) if resources[0] == "xref" else self.page.xref
            prefix = "" if resources[0] == "xref" else "Resources/"
            for (fill, stroke), name in sorted(self.alphas.items(), key=lambda x: x[1]):
                doc.xref_set_key(target, f"{prefix}ExtGState/{name}",
                                 f"<</Type/ExtGState/ca {_number(fill / 255)}/CA {_number(stroke / 255)}>>")
        xref = doc.get_new_xref()
        doc.update_object(xref, "<<>>")
        doc.update_stream(xref, "\n".join(self.ops).encode("ascii"))
        self.page.set_contents(xref)

def _keyed(image, color):
    """An RGBA image with one colour made transparent."""
    from PIL import Image, ImageChops
    rgb = image.convert("RGB")
    key = ImageChops.difference(rgb, Image.new("RGB", rgb.size, color)).convert("L").point(lambda v: 255 if v else 0)
    image.putalpha(ImageChops.multiply(image.getchannel("A"), key))
    return image

def _fit(text, positions, name, size):
    """How much narrower than the built-in font a positioned run's advances are (1: as wide or wider; at least
    0.5): a face narrower than Helvetica (Calibri), or spacing the drawing tightened."""
    if len(positions) < 2:
        return 1.0
    advance = sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(positions, positions[1:]))
    width = pymupdf.get_text_length(text[:len(positions) - 1].encode("cp1252", "replace").decode("cp1252"),
                                    fontname=name, fontsize=size)
    return 1.0 if width <= 0 else max(min(advance / width, 1.0), 0.5)

def _rotation(degrees):
    """(cos, sin) of a text's turn, counter-clockwise as seen (GDI's escapement); the vendored command holds it
    clockwise, as it draws with y down."""
    from math import cos, radians, sin
    angle = radians(-degrees)
    return cos(angle), sin(angle)

def _polygons(path, matrix):
    """A clip path's closed subpaths, flattened, on pyclipper's integer grid; degenerate ones (no area) left out."""
    import pyclipper
    flat = flatten_path(transform_path(path, matrix), flatness=FLATNESS, budget=FlattenBudget(limit=50_000_000))
    polygons = [[(round(x * CLIP_SCALE), round(y * CLIP_SCALE)) for x, y in points] for points, _ in flat]
    polygons = pyclipper.CleanPolygons([p for p in polygons if len(p) >= 3])
    return [p for p in polygons if len(p) >= 3 and pyclipper.Area(p) != 0]

def _region(clip, matrix, width, height):
    """A clip stack's region as polygons (None: empty), its operations applied in turn to the whole canvas."""
    import pyclipper
    modes = {"and": pyclipper.CT_INTERSECTION, "or": pyclipper.CT_UNION, "xor": pyclipper.CT_XOR,
             "diff": pyclipper.CT_DIFFERENCE}
    w, h = round(width * CLIP_SCALE), round(height * CLIP_SCALE)
    region = [[(0, 0), (w, 0), (w, h), (0, h)]]
    for operation in clip:
        incoming = _polygons(operation.path, matrix)
        rule = pyclipper.PFT_EVENODD if operation.fill_rule == "evenodd" else pyclipper.PFT_NONZERO
        if operation.mode == "copy" or not region:
            # a region replaced, or combined with nothing: what's left is the incoming area, or the region as it was
            if operation.mode in ("copy", "or", "xor"):
                region = _union(incoming, rule)
            continue
        if not incoming:  # combined with no area: an intersection leaves nothing; the rest leave the region
            if operation.mode == "and":
                region = []
            continue
        clipper = pyclipper.Pyclipper()
        clipper.AddPaths(region, pyclipper.PT_SUBJECT, True)
        clipper.AddPaths(incoming, pyclipper.PT_CLIP, True)
        region = clipper.Execute(modes[operation.mode], pyclipper.PFT_NONZERO, rule)
    return region or None

def _union(polygons, rule):
    """Polygons as one region, by a fill rule (none: empty)."""
    import pyclipper
    if not polygons:
        return []
    clipper = pyclipper.Pyclipper()
    clipper.AddPaths(polygons, pyclipper.PT_SUBJECT, True)
    return clipper.Execute(pyclipper.CT_UNION, rule, rule)
