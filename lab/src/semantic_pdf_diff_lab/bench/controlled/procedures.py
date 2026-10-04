"""Procedures drawn as message sequence charts: a claim-heavy diagram for the controlled corpus (the adapters plan,
"Pictures in Word documents", diagrams decisions). The owner (2026-10-04): "We'll need to ensure some claim-heavy
diagrams and charts are in our control docs."

- **The diagram:** four lifelines and 24 numbered messages, each carrying one parameter with its value ("7. Admission
  Grant (granted rate 12,345 kbit/s)"): more claims than one request returns (claims_per_request 20), and attributes
  of one shape on many messages (four lifetimes, three intervals, two timeouts), so a value must be bound to its
  message.
- **One layout, two drawers:** the layout is a list of shapes in points; the PDF drawer puts them on the page (as
  vector drawing, or as an image under the raster knob), and the WMF writer encodes the same shapes as a Windows
  metafile, the picture a Word document carries (as Visio and Msc-generator pictures reach Word in real
  specifications).
- **Markdown** can't carry the diagram: its caption stays, marked as not shown, and its facts are listed absent.
- **Placement:** each value is logged where it's drawn (form "figure"), and each step number as a structure number.
"""
import struct
from dataclasses import dataclass

from .corpus import Draw, Fact, Project

PROCEDURE_KNOBS = ("clean", "raster")
SIZE = 7.5          # the labels' font size, points
ROW = 2.6 * SIZE    # one message a row
HEAD = 2.6 * SIZE   # the lifelines' name boxes
HEAD_FILL = (0.87, 0.91, 0.96)
DARK = (0.12, 0.23, 0.36)

@dataclass
class Procedure:
    caption: str
    lifelines: list     # names, left to right
    steps: list         # [(sender, receiver, message, Fact)]: lifeline indexes, the message's name, its parameter
    legend_words: str = ""

    @property
    def height(self):
        return 2 + HEAD + ROW * (len(self.steps) + 0.6)

    @property
    def series(self):  # as a chart's, for the representations' keys
        return [("messages", [fact for *_, fact in self.steps])]

    def label(self, k):
        """Step k's label, and the part before its value: "7. Admission Grant (granted rate 12,345 kbit/s)"."""
        _, _, message, fact = self.steps[k]
        before = f"{k + 1}. {message} ({fact.attribute} "
        return before + fact.value + (f" {fact.unit}" if fact.unit else "") + ")", before

# The attach procedure: (sender, receiver, message, attribute, synonyms, low, high, decimals, unit). Lifelines: 0 the
# terminal, 1 the access point, 2 the gateway, 3 the directory.
ATTACH = (
    (0, 1, "Probe Request", "probe interval", ("interval",), 60, 200, 0, "ms"),
    (1, 0, "Probe Response", "beacon period", ("beacon interval", "period"), 210, 400, 0, "ms"),
    (0, 1, "Association Request", "listen interval", ("interval",), 25, 59, 0, "beacons"),
    (1, 2, "Admission Query", "queue depth", ("queue size", "depth"), 64, 250, 0, "frames"),
    (2, 3, "Profile Lookup", "lookup timeout", ("timeout",), 300, 900, 0, "ms"),
    (3, 2, "Profile Record", "profile size", ("record size", "size"), 260, 1500, 0, "bytes"),
    (2, 1, "Admission Grant", "granted rate", ("rate", "admitted rate"), 2000, 20000, 0, "kbit/s"),
    (1, 0, "Association Response", "maximum idle period", ("idle period", "idle timeout"), 30, 299, 0, "s"),
    (0, 1, "Key Request", "nonce length", ("nonce size",), 64, 255, 0, "bits"),
    (1, 2, "Key Relay", "relay delay budget", ("delay budget", "relay delay"), 26, 95, 0, "ms"),
    (2, 3, "Credential Check", "check timeout", ("timeout",), 200, 800, 0, "ms"),
    (3, 2, "Credential Result", "credential lifetime", ("lifetime",), 3600, 86400, 0, "s"),
    (2, 1, "Key Confirm", "key lifetime", ("lifetime",), 600, 3599, 0, "s"),
    (1, 0, "Key Install", "install deadline", ("deadline",), 100, 500, 0, "ms"),
    (0, 1, "Session Request", "requested window", ("window", "window size"), 32, 128, 0, "packets"),
    (1, 2, "Session Setup", "setup timer", ("timer",), 500, 2000, 0, "ms"),
    (2, 1, "Session Accept", "granted window", ("window", "window size"), 32, 128, 0, "packets"),
    (1, 0, "Session Confirm", "keepalive interval", ("interval", "keepalive"), 25, 60, 0, "s"),
    (0, 2, "Route Registration", "route lifetime", ("lifetime",), 300, 1800, 0, "s"),
    (2, 3, "Route Publish", "publish interval", ("interval",), 30, 120, 0, "s"),
    (3, 2, "Route Acknowledge", "cache lifetime", ("lifetime",), 60, 600, 0, "s"),
    (2, 0, "Registration Accept", "refresh interval", ("interval",), 120, 900, 0, "s"),
    (0, 1, "Measurement Report", "report period", ("period", "reporting period"), 100, 1000, 0, "ms"),
    (1, 0, "Report Configuration", "hysteresis", ("hysteresis margin",), 1.0, 6.0, 1, "dB"),
)

def attach_procedure(seed=1):
    """The link protocol's attach procedure: a scope, the sequence chart, and failure handling in words."""
    d = Draw(f"attach-{seed}")
    d.used |= {str(n) for n in range(1, len(ATTACH) + 1)}  # the step numbers: printed, so no fact takes one
    F, steps = [], []
    for k, (sender, receiver, message, attribute, synonyms, lo, hi, decimals, unit) in enumerate(ATTACH, 1):
        fact = Fact(f"msg{k}.{attribute.split()[-1]}", message, (message.lower(), f"{message} message"), attribute,
                    synonyms, d.number(lo, hi, decimals), unit, basis="required", drawn="figure")
        F.append(fact)
        steps.append((sender, receiver, message, fact))
    procedure = ("Attach procedure", ("attach", "the procedure", "attach procedure"))
    deadline = Fact("attach.deadline", *procedure, "completion deadline", ("deadline", "time limit", "timeout"),
                    d.number(25, 45), "s", basis="required")
    attempts = Fact("attach.attempts", "Terminal", ("the terminal", "terminal"), "attach attempts per hour",
                    ("attach attempts", "maximum attach attempts", "attempts"), d.number(30, 60), "", basis="required")
    F += [deadline, attempts]
    chart = Procedure("Figure 1. Attach procedure", ["Terminal", "Access point", "Gateway", "Directory"], steps)
    plain = {"failure": "The terminal abandons the attach procedure if it is not complete within {t} s, and makes at "
                        "most {n} attach attempts in any hour. A procedure abandoned at any step starts again from "
                        "the probe."}
    sections = [
        ("1 Scope", [("p", "This clause specifies the attach procedure of the link protocol: the messages a terminal, "
                           "an access point, the gateway and the directory exchange to admit the terminal, secure its "
                           "link, open its session and register its route. Figure 1 gives the messages in order, "
                           "each with the parameter it carries.")]),
        ("2 Procedure", [("procedure", chart)]),
        ("3 Failure Handling", [("text", "failure")]),
    ]
    return Project(f"attach-s{seed}", "Link Protocol: Attach Procedure", F, sections,
                   texts={k: (v, v) for k, v in plain.items()}, values=dict(t=deadline.value, n=attempts.value),
                   kinds=PROCEDURE_KNOBS)

PROCEDURE_PROJECTS = {"attach": attach_procedure}

# --- layout --------------------------------------------------------------------------------------

def _width(text, bold=False):
    import pymupdf
    return pymupdf.get_text_length(text, fontname="hebo" if bold else "helv", fontsize=SIZE)

def layout(procedure, width):
    """The diagram's shapes in points from its top left: ("rect", box, fill, stroke), ("line", start, end, color,
    width, dashed), ("polygon", points, fill), ("text", x, baseline, text, bold); and where each step's numbers fell:
    [(fact, value box, number box)]."""
    shapes, placed = [], []
    n = len(procedure.lifelines)
    column = width / n
    x = [column * (i + 0.5) for i in range(n)]
    bottom = procedure.height - 4
    for i, name in enumerate(procedure.lifelines):
        shapes.append(("line", (x[i], 2 + HEAD), (x[i], bottom), (0.55, 0.55, 0.55), 0.6, True))
    for i, name in enumerate(procedure.lifelines):
        shapes.append(("rect", (x[i] - column / 2 + 8, 2, x[i] + column / 2 - 8, 2 + HEAD), HEAD_FILL, DARK))
        shapes.append(("text", x[i] - _width(name, True) / 2, 2 + HEAD / 2 + SIZE * 0.35, name, True))
    for k, (sender, receiver, _, fact) in enumerate(procedure.steps):
        y = 2 + HEAD + ROW * (k + 1)
        text, before = procedure.label(k)
        left, base = (x[sender] + x[receiver]) / 2 - _width(text) / 2, y - 3
        shapes.append(("rect", (left - 2, base - SIZE, left + _width(text) + 2, base + 2), (1, 1, 1), None))
        shapes.append(("text", left, base, text, False))
        tip = x[receiver] - (3 if receiver > sender else -3)  # short of the lifeline, as drawn by hand
        back = 6 if receiver > sender else -6
        shapes.append(("line", (x[sender], y), (tip - back, y), (0, 0, 0), 0.8, False))
        shapes.append(("polygon", [(tip, y), (tip - back, y - 2.5), (tip - back, y + 2.5)], (0, 0, 0)))
        number = f"{k + 1}"
        value_at = left + _width(before)
        placed.append((fact, (value_at, base - SIZE, value_at + _width(fact.value), base),
                       (left, base - SIZE, left + _width(number), base)))
    return shapes, placed

def draw_procedure(page, rect, procedure):
    """Draw the diagram into rect on a PyMuPDF page. Returns [(fact, box)] and the numbers drawn: [(text, facts,
    box)], as corpus.draw_chart does."""
    import pymupdf
    at = lambda px, py: (rect.x0 + px, rect.y0 + py)
    shapes, placed = layout(procedure, rect.width)
    for shape in shapes:
        kind = shape[0]
        if kind == "text":
            _, px, py, text, bold = shape
            page.insert_text(at(px, py), text, fontname="hebo" if bold else "helv", fontsize=SIZE)
            continue
        drawing = page.new_shape()
        if kind == "rect":
            _, (x0, y0, x1, y1), fill, stroke = shape
            drawing.draw_rect(pymupdf.Rect(*at(x0, y0), *at(x1, y1)))
            drawing.finish(color=stroke, fill=fill, width=0.8 if stroke else 0)
        elif kind == "line":
            _, start, end, color, width, dashed = shape
            drawing.draw_line(at(*start), at(*end))
            drawing.finish(color=color, width=width, dashes="[3 2] 0" if dashed else None, closePath=False)
        else:
            _, points, fill = shape
            drawing.draw_polyline([at(*p) for p in points])
            drawing.finish(color=None, fill=fill, width=0, closePath=True)
        drawing.commit()
    box = lambda b: pymupdf.Rect(*at(b[0], b[1]), *at(b[2], b[3]))
    facts, numbers = [], []
    for k, (fact, value, number) in enumerate(placed, 1):
        facts.append((fact, box(value)))
        numbers += [(fact.value, [fact], box(value)), (str(k), [], box(number))]
    return facts, numbers

# --- a Windows metafile (WMF) of the same shapes --------------------------------------------------

TWIPS = 20  # logical units a point: the metafile's inch is 1440

def _record(function, payload=b""):
    payload += b"\0" * (len(payload) % 2)
    return struct.pack("<IH", 3 + len(payload) // 2, function) + payload

def _color(rgb):
    r, g, b = (round(c * 255) for c in rgb)
    return r | g << 8 | b << 16

def _pen(style, width, rgb):
    return _record(0x02FA, struct.pack("<HhhI", style, width, 0, _color(rgb)))  # META_CREATEPENINDIRECT

def _brush(style, rgb=(0, 0, 0)):
    return _record(0x02FC, struct.pack("<HIH", style, _color(rgb), 0))  # META_CREATEBRUSHINDIRECT

def _font(bold):
    face = b"Arial".ljust(32, b"\0")
    return _record(0x02FB, struct.pack("<hhhhhBBBBBBBB", -round(SIZE * TWIPS), 0, 0, 0, 700 if bold else 400,
                                       0, 0, 0, 0, 0, 0, 0, 0) + face)  # META_CREATEFONTINDIRECT

def wmf(procedure, width):
    """The diagram as a placeable WMF's bytes, `width` points wide, in twips: the shapes `layout` gives the PDF,
    drawn with GDI's pens, brushes, polygons and TEXTOUT in Arial."""
    shapes, _ = layout(procedure, width)
    t = lambda v: round(v * TWIPS)
    w, h = t(width), t(procedure.height)
    objects = {}  # (kind, key): index, created in first use's order (GDI takes the lowest free index)
    head, body = [], []

    def select(kind, key, make):
        if (kind, key) not in objects:
            objects[(kind, key)] = len(objects)
            head.append(make())
        body.append(_record(0x012D, struct.pack("<H", objects[(kind, key)])))  # META_SELECTOBJECT

    select("pen", "null", lambda: _pen(5, 0, (0, 0, 0)))  # PS_NULL
    for shape in shapes:
        kind = shape[0]
        if kind == "rect":
            _, (x0, y0, x1, y1), fill, stroke = shape
            select("brush", fill, lambda: _brush(0, fill))
            select("pen", stroke or "null", lambda: _pen(0, t(0.8), stroke) if stroke else _pen(5, 0, (0, 0, 0)))
            body.append(_record(0x041B, struct.pack("<hhhh", t(y1), t(x1), t(y0), t(x0))))  # META_RECTANGLE
        elif kind == "line":
            _, (x0, y0), (x1, y1), color, line_width, dashed = shape
            select("pen", (color, line_width, dashed),
                   lambda: _pen(1, 0, color) if dashed else _pen(0, t(line_width), color))  # PS_DASH is one pixel
            body.append(_record(0x0214, struct.pack("<hh", t(y0), t(x0))))  # META_MOVETO
            body.append(_record(0x0213, struct.pack("<hh", t(y1), t(x1))))  # META_LINETO
        elif kind == "polygon":
            _, points, fill = shape
            select("brush", fill, lambda: _brush(0, fill))
            select("pen", "null", None)
            body.append(_record(0x0324, struct.pack("<h", len(points)) +
                                b"".join(struct.pack("<hh", t(px), t(py)) for px, py in points)))  # META_POLYGON
        else:
            _, px, py, text, bold = shape
            select("font", bold, lambda: _font(bold))
            raw = text.encode("cp1252")
            body.append(_record(0x0521, struct.pack("<h", len(raw)) + raw + b"\0" * (len(raw) % 2) +
                                struct.pack("<hh", t(py), t(px))))  # META_TEXTOUT
    setup = [_record(0x0103, struct.pack("<H", 8)),            # META_SETMAPMODE: anisotropic
             _record(0x020B, struct.pack("<hh", 0, 0)),         # META_SETWINDOWORG
             _record(0x020C, struct.pack("<hh", h, w)),         # META_SETWINDOWEXT
             _record(0x0102, struct.pack("<H", 1)),             # META_SETBKMODE: transparent
             _record(0x012E, struct.pack("<H", 24)),            # META_SETTEXTALIGN: left, baseline
             _record(0x0209, struct.pack("<I", 0))]             # META_SETTEXTCOLOR: black
    records = setup + head + body + [_record(0x0000)]          # META_EOF
    data = b"".join(records)
    placeable = struct.pack("<IHhhhhHI", 0x9AC6CDD7, 0, 0, 0, w, h, 72 * TWIPS, 0)
    checksum = 0
    for (word,) in struct.iter_unpack("<H", placeable):
        checksum ^= word
    standard = struct.pack("<HHHIHIH", 1, 9, 0x0300, (18 + len(data)) // 2, len(objects),
                           max(len(r) for r in records) // 2, 0)
    return placeable + struct.pack("<H", checksum) + standard + data
