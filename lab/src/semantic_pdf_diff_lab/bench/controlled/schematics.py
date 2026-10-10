"""Schematics and concept diagrams for controlled documents (milestone 3b): systems of named parts and the
relations between them, drawn as figures and stated in prose, under knobs of rising difficulty.

Spot check sc01 items 5 and 9 (HabEx's optical layouts) are what this reproduces. The owner: "things like the
figures and concept drawings in items 5 and 9 of the spotcheck. These are full of useful claims and often have
references to them"; "a lot of control docs that present relations in different ways, with varying levels of
difficulty."

A system is its parts (each with names and a symbol), its main path in order, the parts hung off it (a motor
under its fan, a controller above), enclosures (the parts of an air handler inside its casing), and links: each
link a relational fact (relations.RELATIONS) drawn in its kind of line, or as a note beside its part.
"""
import math
from dataclasses import dataclass, field


# --- the model ---------------------------------------------------------------------------------------

@dataclass
class Part:
    id: str
    name: str
    aliases: tuple = ()
    symbol: str = "box"      # drawn as, with leaders: box, damper, filter, coil, fan, duct, zone, motor, panel,
                             # controller, sensor, input, mirror, dichroic, stop, wheel, grism, detector, camera
    anchor: str = ""         # off the path: the path part it hangs from
    offset: int = 0          # rows above (-) or below (+) its anchor
    dx: float = 0.0          # columns along from its anchor
    note: str = ""           # printed beside it (a number, say "124 hp")

@dataclass
class Link:
    subject: str             # a part id
    relation: str            # relations.RELATIONS
    object: str              # a part id, or a literal (a place, a state)
    kind: str = "flow"       # drawn as: flow (solid arrow), signal (dashed arrow), power (dotted arrow),
                             # drive (double line), member (an enclosure), note (words beside the part)
    accepts: tuple = ()      # other relations that state it fairly (a part drawn inside its whole: within)
    aliases: tuple = ()      # a literal object's other names ("pupil", "pupil plane")
    mode: str = ""           # a condition ("guide mode")

@dataclass
class System:
    id: str
    caption: str
    medium: str              # what flows: "air", "light"
    parts: list
    path: list               # part ids, in order
    links: list
    enclosures: list = field(default_factory=list)   # [(the whole's part id, [member ids])]
    intro: list = field(default_factory=list)        # the description: [(text, the link it states, or None)]

    def part(self, pid):
        return next(p for p in self.parts if p.id == pid)

# --- two systems --------------------------------------------------------------------------------------

def air_handler(d):
    """AHU-3, serving Hall C: an air path that loops back through a return fan, a casing round four of its parts,
    a motor and its panel, a controller, and a sensor on the duct."""
    P = Part
    parts = [
        P("oad", "outdoor air damper", ("OA damper", "outside air damper", "OAD", "damper")),
        P("mix", "mixing box", ("mixing plenum", "mixing section")),
        P("flt", "filter bank", ("filters", "filter section", "filter")),
        P("coil", "cooling coil", ("chilled water coil", "CHW coil", "coil")),
        P("sf", "supply fan", ("SF-3", "fan")),
        P("duct", "supply duct", ("supply air duct", "duct")),
        P("hall", "Hall C", ("exhibit hall C", "the hall", "zone")),
        P("rf", "return fan", ("RF-3",), "fan", anchor="mix", offset=2, dx=0.5),  # the return path runs below
        P("ahu", "AHU-3", ("air handling unit 3", "AHU 3", "air handler", "air handling unit", "AHU")),
        # placed so no line crosses a box: the motor and its panel above the fan, the controller above the filters,
        # the sensor under its duct
        P("mtr", "motor M-3", ("M-3", "supply fan motor", "fan motor", "motor"), "motor", anchor="sf", offset=-1,
          note=f"{d.number(60, 200)} hp"),
        P("pnl", "panel LP-2", ("LP-2", "power panel", "panel"), "panel", anchor="sf", offset=-2),
        P("ddc", "controller DDC-3", ("DDC-3", "controller", "DDC controller"), "controller", anchor="flt", offset=-1),
        P("ts", "sensor TS-1", ("TS-1", "temperature sensor", "supply air temperature sensor", "sensor"), "sensor",
          anchor="duct", offset=1, note=f"{d.number(52, 58)} °F"),
    ]
    path = ["oad", "mix", "flt", "coil", "sf", "duct", "hall"]
    links = [Link(a, "precedes", b) for a, b in zip(path, path[1:])]
    links += [Link("hall", "precedes", "rf"), Link("rf", "precedes", "mix")]
    links += [Link(m, "part of", "ahu", "member", accepts=("within",)) for m in ("mix", "flt", "coil", "sf")]
    # a signal line is fairly read as control; a sensor on a duct as in it, or measuring it
    links += [Link("mtr", "drives", "sf", "drive"), Link("pnl", "powers", "mtr", "power"),
              Link("ddc", "controls", "oad", "signal", accepts=("signals",)),
              Link("ddc", "controls", "mtr", "signal", accepts=("signals",)),
              Link("ts", "signals", "ddc", "signal", accepts=("linked", "controls")),
              Link("ts", "mounted on", "duct", "note", accepts=("within", "measures"))]
    links += [Link("ahu", "serves", "hall", "intro")]  # said in the description: "AHU-3, which conditions Hall C"
    return System("ahu3", "Figure 1. AHU-3 air system schematic", "air", parts, path, links,
                  [("ahu", ["mix", "flt", "coil", "sf"])],
                  intro=[("This note describes the arrangement of air handling unit AHU-3, ", None),
                         ("which conditions Hall C", len(links) - 1),
                         (", and the devices that drive, power and control it.", None)])

def uv_channel(d):
    """The Kestrel spectrograph's UV channel: a light path through mirrors to a detector, a guide-mode branch at the
    dichroic, places on the path (focal and pupil planes), movable parts, and a field stop of two sizes."""
    P = Part
    parts = [
        P("in", "input beam", ("collimated input", "input from the FSM", "FSM input", "input"), "input"),
        P("fm", "fold mirror FM1", ("FM1", "fold mirror"), "mirror"),
        P("dc", "dichroic D1", ("D1", "dichroic", "dichroic mirror", "beam splitter"), "dichroic"),
        P("oap", "OAP1", ("off-axis parabola", "off-axis paraboloid", "OAP", "paraboloidal mirror", "OAP1 mirror"),
          "mirror"),
        P("fs", "field stop", ("FS", "stop"), "stop"),
        P("em", "ellipsoidal mirror EM1", ("EM1", "ellipsoidal mirror", "ellipse"), "mirror"),
        P("fw", "filter wheel", ("FW", "filters", "filter"), "wheel"),
        P("gr", "grism G1", ("G1", "grism"), "grism"),
        P("det", "EMCCD", ("detector", "EMCCD detector", "camera", "UV camera"), "detector"),
        P("gc", "guide camera", ("guide detector", "guider"), "camera", anchor="dc", offset=-1, dx=0.6),
        P("uv", "UV channel", ("ultraviolet channel", "UV arm", "channel")),
        P("wide", "wide stop", ("wide field stop", "wide aperture", "wide"), "stop", anchor="fs", offset=1, dx=-0.55),
        P("narrow", "narrow stop", ("narrow field stop", "pinhole", "narrow aperture", "narrow"), "stop", anchor="fs",
          offset=1, dx=0.55),
    ]
    path = ["in", "fm", "dc", "oap", "fs", "em", "fw", "gr", "det"]
    links = [Link(a, "precedes", b) for a, b in zip(path, path[1:])]
    links += [Link("dc", "precedes", "gc", mode="guide mode")]
    focal, pupil = ("focal plane", "focus", "intermediate focus"), ("pupil plane", "pupil", "exit pupil")
    movable = ("movable", "moveable", "motorized", "can be moved", "on a stage", "rotates", "rotating",
               "insertable", "retractable", "removable", "translatable", "withdrawn", "selectable")
    links += [Link("fs", "located at", "focal plane", "note", aliases=focal),
              Link("fw", "located at", "pupil plane", "note", aliases=pupil),
              Link("gr", "located at", "pupil plane", "note", aliases=pupil),
              Link("fw", "state", "movable", "note", aliases=movable),
              Link("gr", "state", "movable", "note", aliases=movable),
              Link("fs", "has option", "wide", "option"), Link("fs", "has option", "narrow", "option")]
    links += [Link(m, "part of", "uv", "member", accepts=("within",)) for m in ("oap", "fs", "em", "fw", "gr", "det")]
    return System("uvch", "Figure 1. UV channel optical layout", "light", parts, path, links,
                  [("uv", ["oap", "fs", "em", "fw", "gr", "det"])],
                  intro=[("This note describes the optical layout of the Kestrel spectrograph's ultraviolet channel, "
                          "from the beam it receives to its detector, and the guide camera that shares its input.",
                          None)])

# --- prose ------------------------------------------------------------------------------------------------

def _the(name):
    """"the supply fan", but "AHU-3", "Hall C", "OAP1", "motor M-3" as they are."""
    first = name.split()[0]
    return name if any(ch.isdigit() for ch in first) or first[0].isupper() else f"the {name}"

def _cap(text):
    return text[0].upper() + text[1:]

def sentences(system, hard, draw, which=None):
    """[(text, [link indices])]: each link stated once, plainly or in a harder way (inverse, passive, possessive,
    narrated along the path, a place or state in a clause). `which`: the link indices to state (all by default)."""
    which = set(range(len(system.links))) if which is None else set(which)
    name = lambda pid: _the(system.part(pid).name) if pid in {p.id for p in system.parts} else pid
    out, done = [], set()
    medium = system.medium
    links = list(enumerate(system.links))
    path_links = [(i, l) for i, l in links if l.relation == "precedes" and not l.mode and i in which]
    if hard and len(path_links) >= 3:  # the path narrated: "passes the filter bank and the cooling coil before..."
        chunk = path_links[:max(3, len(path_links) // 2)]
        steps = [name(chunk[0][1].subject)] + [name(l.object) for _, l in chunk]
        out.append((f"{_cap(medium)} enters at {steps[0]}, passes {', '.join(steps[1:-1])} in turn, and reaches "
                    f"{steps[-1]}.", [i for i, _ in chunk]))
        done |= {i for i, _ in chunk}
    options = {}
    for i, l in links:
        if i in done or i not in which:
            continue
        s, o = name(l.subject), name(l.object)
        if l.relation == "has option":
            options.setdefault(l.subject, []).append((i, l))
            continue
        plain = {
            "precedes": f"From {s}, the {medium} passes to {o}" + (f" in {l.mode}" if l.mode else "") + ".",
            "part of": f"{_cap(s)} is part of {o}.",
            "drives": f"{_cap(s)} drives {o}.",
            "powers": f"{_cap(s)} powers {o}.",
            "controls": f"{_cap(s)} controls {o}.",
            "signals": f"{_cap(s)} is connected to {o}.",
            "mounted on": f"{_cap(s)} is mounted on {o}.",
            "located at": f"{_cap(s)} is located at a {l.object}.",
            "state": f"{_cap(s)} is {l.object}.",
        }[l.relation]
        variants = {
            "precedes": [f"{_cap(o)} receives the {medium} from {s}" + (f" in {l.mode}" if l.mode else "") + ".",
                         f"Downstream of {s} comes {o}" + (f", in {l.mode}" if l.mode else "") + "."],
            "part of": [f"{_cap(o)} houses {s}.", f"{_cap(s)} sits within {o}."],
            "drives": [f"{_cap(o)} is driven by {s}."],
            "powers": [f"{_cap(o)} is fed from {s}."],
            "controls": [f"{_cap(o)} is modulated by {s}."],
            "signals": [f"{_cap(s)} reports to {o}."],
            "mounted on": [f"{_cap(s)} sits on {o}."],
            "located at": [f"{_cap(s)} sits at a {l.aliases[1] if len(l.aliases) > 1 else l.object}."],
            "state": [f"{_cap(s)} can be {l.aliases[-1] if l.aliases else l.object} as needed."],
        }[l.relation]
        out.append((draw.pick(variants) if hard else plain, [i]))
    for subject, opts in options.items():
        names = [name(l.object) for _, l in opts]
        text = (f"Either {' or '.join(names)} can be selected for {name(subject)}." if hard else
                f"{_cap(name(subject))} has two options: {' and '.join(names)}.")
        out.append((text, [i for i, _ in opts]))
    return out

# --- layout and drawing ---------------------------------------------------------------------------------

UNIT, BOX_W, BOX_H, SYMBOL = 44.0, 64.0, 28.0, 16.0
STYLES = {"flow": dict(width=1.1, dashes=None, arrow=True), "signal": dict(width=0.8, dashes="[3 2] 0", arrow=True),
          "power": dict(width=0.9, dashes="[1 2] 0", arrow=True), "drive": dict(width=2.2, dashes=None, arrow=False)}
LEGEND = (("flow", "air or light"), ("signal", "control signal"), ("power", "power"), ("drive", "drive shaft"))
LINK_WORDS = {"drives": "drives", "powers": "powers", "controls": "controls", "signals": "signal"}

def _crosses(a, b, r):
    """Whether segment ab passes through rect r (x0, y0, x1, y1): Liang-Barsky clipping."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - r[0]), (dx, r[2] - x0), (-dy, y0 - r[1]), (dy, r[3] - y0)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True

_LAYOUTS = {}

def layout(system, width, folded):
    """Cached: the search is the slow part of drawing, and a system lays out the same whatever its values."""
    key = (system.id, tuple((p.id, p.anchor, p.offset, p.dx) for p in system.parts), width, folded)
    if key not in _LAYOUTS:
        _LAYOUTS[key] = _layout(system, width, folded)
    return _LAYOUTS[key]

def _layout(system, width, folded):
    """{part id: (x, y)} centres, and the height needed. The path runs left to right; folded, it snakes in rows
    of four, every other row right to left. Each part off the path takes the place nearest its anchor (its own
    offset first) where its box overlaps no other and no line crosses a box: so the figure never says, by
    accident, that a line runs through a part."""
    n = len(system.path)
    per_row = 4 if folded else n
    colw = width / per_row
    box_w = min(BOX_W, colw - 12)
    reach = max([abs(p.offset) for p in system.parts if p.anchor] + [1])
    band = (2 * reach + 1) * UNIT  # room above and below each path row for the parts hung off it
    pos = {}
    for k, pid in enumerate(system.path):
        row, col = divmod(k, per_row)
        if folded and row % 2:
            col = per_row - 1 - col
        pos[pid] = ((col + 0.5) * colw, row * band)
    ids = {p.id for p in system.parts}
    wholes = {whole for whole, _ in system.enclosures}
    lines = [(l.subject, l.object) for l in system.links if l.object in ids and l.kind != "member"]
    box = lambda c, pad=0: (c[0] - box_w / 2 - pad, c[1] - BOX_H / 2 - pad, c[0] + box_w / 2 + pad, c[1] + BOX_H / 2 + pad)
    apart = lambda r, q: r[2] < q[0] or q[2] < r[0] or r[3] < q[1] or q[3] < r[1]

    def along(a1, a2, b1, b2):
        """Whether two lines run along each other (nearly parallel, close, overlapping): a reader can't tell them
        apart."""
        dx1, dy1, dx2, dy2 = a2[0] - a1[0], a2[1] - a1[1], b2[0] - b1[0], b2[1] - b1[1]
        n1, n2 = math.hypot(dx1, dy1), math.hypot(dx2, dy2)
        if not n1 or not n2 or abs(dx1 * dy2 - dy1 * dx2) / (n1 * n2) > 0.06:
            return False
        if abs((b1[0] - a1[0]) * dy1 - (b1[1] - a1[1]) * dx1) / n1 > 5:
            return False
        t = sorted(((p[0] - a1[0]) * dx1 + (p[1] - a1[1]) * dy1) / n1 for p in (b1, b2))
        return min(t[1], n1) - max(t[0], 0) > 6

    def cost(pos):
        names = list(pos)
        c = sum(100 for i, a in enumerate(names) for b in names[i + 1:] if not apart(box(pos[a], 8), box(pos[b])))
        segs = [(a, b) for a, b in lines if a in pos and b in pos]
        c += sum(_crosses(pos[a], pos[b], box(pos[q], 3)) for a, b in segs for q in names if q not in (a, b))
        c += sum(along(pos[a], pos[b], pos[x], pos[y]) for i, (a, b) in enumerate(segs) for x, y in segs[i + 1:]
                 if not {a, b} & {x, y})
        for i, (a, b) in enumerate(segs):  # two lines leaving one part at nearly one angle: which goes where?
            for x, y in segs[i + 1:]:
                shared = {a, b} & {x, y}
                if len(shared) == 1:
                    o = shared.pop()
                    u, v = (b if a == o else a), (y if x == o else x)
                    angle = abs(math.atan2(pos[u][1] - pos[o][1], pos[u][0] - pos[o][0]) -
                                math.atan2(pos[v][1] - pos[o][1], pos[v][0] - pos[o][0]))
                    c += min(angle, 2 * math.pi - angle) < math.radians(12)
        return c

    off = [p for p in system.parts if p.anchor and p.id not in wholes]

    def spot(p, o, d):
        ax, ay = pos[p.anchor]
        k = system.path.index(p.anchor)
        x = ax + (-1 if folded and (k // per_row) % 2 else 1) * d * colw
        return None if not o or x < colw / 2 - 1 or x > width - colw / 2 + 1 else (x, ay + o * UNIT)

    for p in off:  # first, each where it was meant to be
        pos[p.id] = spot(p, p.offset, p.dx) or spot(p, p.offset, 0)
    def spots(p):
        out = []
        for o in dict.fromkeys((p.offset, -p.offset, *sorted(range(-reach, reach + 1), key=abs))):
            for d in dict.fromkeys((p.dx, 0, 0.5, -0.5, 1, -1, 1.5, -1.5, 2, -2, 2.5, -2.5)):
                c = spot(p, o, d)
                if c is not None:
                    out.append((c, 0.01 * (abs(o - p.offset) + abs(d - p.dx))))  # nearest its intended place
        return out

    pull = {p.id: 0.0 for p in off}
    score = lambda trial, pulls: (cost(trial), sum(pulls.values()))
    linked = [(a, b) for a, b in lines if a in pull and b in pull]
    for _ in range(6):  # each moved to its best place given the others; then linked pairs together; until none moves
        moved = False
        for p in off:
            best = (score(pos, pull), pos[p.id], pull[p.id])
            for c, pl in spots(p):
                trial = score({**pos, p.id: c}, {**pull, p.id: pl})
                if trial < best[0]:
                    best = (trial, c, pl)
            if best[1] != pos[p.id]:
                pos[p.id], pull[p.id], moved = best[1], best[2], True
        if not moved and cost(pos):
            for a, b in linked:
                pa, pb = system.part(a), system.part(b)
                best = (score(pos, pull), pos[a], pos[b], pull[a], pull[b])
                for ca, la in spots(pa):
                    for cb, lb in spots(pb):
                        trial = score({**pos, a: ca, b: cb}, {**pull, a: la, b: lb})
                        if trial < best[0]:
                            best = (trial, ca, cb, la, lb)
                if (best[1], best[2]) != (pos[a], pos[b]):
                    pos[a], pos[b], pull[a], pull[b] = best[1:]
                    moved = True
        if not moved:
            break
    top = min(y for _, y in pos.values()) - BOX_H / 2 - 22
    bottom = max(y for _, y in pos.values()) + BOX_H / 2 + 22
    return {k: (x, y - top) for k, (x, y) in pos.items()}, bottom - top

def figure_height(system, width, folded, legend):
    return layout(system, width, folded)[1] + (16 if legend else 0) + 6

def _border(rect, towards):
    """Where the line from rect's centre towards a point leaves the rect."""
    cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
    dx, dy = towards[0] - cx, towards[1] - cy
    if dx == 0 and dy == 0:
        return cx, cy
    t = min((rect.width / 2) / abs(dx) if dx else math.inf, (rect.height / 2) / abs(dy) if dy else math.inf)
    return cx + dx * t, cy + dy * t

def draw_system(page, rect, system, facts, notes=None, leaders=False, folded=False, legend=False, size=7.0):
    """Draw the system into rect: `facts` are the links' facts, in order; `notes` the numbers' facts by part id.
    Returns [(fact, box)], each fact where it's drawn, and the numbers drawn: [(text, facts, box)].

    Labels never overlap: each tries its places in turn (beside its symbol, along its line) and takes the first
    free one, so a reader is never asked to read what can't be read."""
    import pymupdf
    notes = notes or {}
    width = lambda t, s=size: pymupdf.get_text_length(t, fontname="helv", fontsize=s)
    centres, _ = layout(system, rect.width, folded)
    per_row = 4 if folded else len(system.path)
    box_w = min(BOX_W, rect.width / per_row - 12)  # boxes fit their columns, so arrows show between them
    centres = {k: (rect.x0 + x, rect.y0 + y) for k, (x, y) in centres.items()}
    wholes = {whole for whole, _ in system.enclosures}
    shapes, occupied, placements, numbers = {}, [], [], []
    free = lambda r: r.x0 >= rect.x0 - 1 and r.x1 <= rect.x1 + 1 and not any(r.intersects(o) for o in occupied)

    def text(x, y, t, s=size, color=(0, 0, 0)):
        page.insert_text((x, y), t, fontname="helv", fontsize=s, color=color)

    def wrap(t, w):
        lines, line = [], ""
        for word in t.split():
            trial = f"{line} {word}".strip()
            if line and width(trial) > w:
                lines.append(line)
                line = word
            else:
                line = trial
        return lines + [line]

    def place(lines, candidates, s=size):
        """Write lines at the first free candidate (x, y of the top-left corner); returns the rect used."""
        w, h = max(width(ln, s) for ln in lines), len(lines) * s * 1.15
        options = [pymupdf.Rect(x, y, x + w, y + h) for x, y in candidates]
        r = next((o for o in options if free(o)), options[0])
        for j, ln in enumerate(lines):
            text(r.x0, r.y0 + s * 0.85 + j * s * 1.15, ln, s)
        occupied.append(r)
        return r

    def double_arrow(x, y0, y1):
        shape = page.new_shape()
        shape.draw_line((x, y0), (x, y1))
        shape.finish(color=(0, 0, 0), width=0.8, closePath=False)
        for tip, sgn in ((y0, 1), (y1, -1)):
            shape.draw_polyline([(x, tip), (x - 2, tip + 3 * sgn), (x + 2, tip + 3 * sgn), (x, tip)])
            shape.finish(color=(0, 0, 0), fill=(0, 0, 0), width=0.3, closePath=True)
        shape.commit()

    def line(a, b, kind, label=""):
        st = STYLES[kind]
        shape = page.new_shape()
        if kind == "drive":  # a shaft: two parallel lines
            nx, ny = b[1] - a[1], a[0] - b[0]
            n = math.hypot(nx, ny) or 1
            ox, oy = 1.4 * nx / n, 1.4 * ny / n
            shape.draw_line((a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy))
            shape.draw_line((a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy))
            shape.finish(color=(0, 0, 0), width=0.7, closePath=False)
        else:
            shape.draw_line(a, b)
            shape.finish(color=(0, 0, 0), width=st["width"], dashes=st["dashes"], closePath=False)
        if st["arrow"]:
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            left = (b[0] - 6 * math.cos(ang - 0.4), b[1] - 6 * math.sin(ang - 0.4))
            right = (b[0] - 6 * math.cos(ang + 0.4), b[1] - 6 * math.sin(ang + 0.4))
            shape.draw_polyline([b, left, right, b])
            shape.finish(color=(0, 0, 0), fill=(0, 0, 0), width=0.5, closePath=True)
        shape.commit()
        if label and not legend:  # along the line, clear of boxes and other labels
            spots = [(a[0] + (b[0] - a[0]) * t + dx, a[1] + (b[1] - a[1]) * t + dy)
                     for t in (0.5, 0.35, 0.65, 0.2, 0.8) for dx, dy in ((3, -9), (3, 2), (-3 - width(label, size - 1), -9))]
            place([label], spots, size - 1)
        return pymupdf.Rect(min(a[0], b[0]) - 2, min(a[1], b[1]) - 2, max(a[0], b[0]) + 2, max(a[1], b[1]) + 2)

    # the parts: boxes (or symbols) first, so labels keep clear of them
    for p in system.parts:
        if p.id in wholes:
            continue
        x, y = centres[p.id]
        half_w, half_h = (SYMBOL / 2, SYMBOL / 2) if leaders else (box_w / 2, BOX_H / 2)
        shapes[p.id] = pymupdf.Rect(x - half_w, y - half_h, x + half_w, y + half_h)
        occupied.append(shapes[p.id])
    for p in system.parts:
        if p.id in wholes:
            continue
        box = shapes[p.id]
        shape = page.new_shape()
        if leaders:
            _symbol(shape, p.symbol, box)
            shape.finish(color=(0, 0, 0), width=0.9, closePath=False)
            shape.commit()
            lines = wrap(p.name, BOX_W)
            w, h = max(width(ln) for ln in lines), len(lines) * size * 1.15
            r = place(lines, [(box.x1 + 8, box.y0 - h - 6), (box.x1 + 8, box.y1 + 6), (box.x0 - w - 8, box.y0 - h - 6),
                              (box.x0 - w - 8, box.y1 + 6), (box.x1 + 6, box.y0 - h / 2 + 8), (box.x0 - w - 6, box.y0)])
            near = (r.x0 - 1 if r.x0 > box.x1 else r.x1 + 1, r.y1 if r.y1 < box.y0 else r.y0)
            leader = page.new_shape()
            leader.draw_line(near, _border(box, near))
            leader.finish(color=(0.35, 0.35, 0.35), width=0.4, closePath=False)
            leader.commit()
        else:
            shape.draw_rect(box)
            shape.finish(color=(0, 0, 0), fill=(0.93, 0.95, 0.98), width=0.8)
            shape.commit()
            lines = wrap(p.name, box_w - 4)
            top = box.y0 + (BOX_H - len(lines) * size * 1.15) / 2 + size * 0.85
            for j, ln in enumerate(lines):
                text((box.x0 + box.x1) / 2 - width(ln) / 2, top + j * size * 1.15, ln)
    # enclosures: a dashed outline round the members in each row (a folded path breaks it), the whole named on each
    for whole, members in system.enclosures:
        rows = {}
        for m in members:
            rows.setdefault(round(centres[m][1]), []).append(shapes[m])
        outlines = []
        for _, boxes in sorted(rows.items()):
            pad_top = 14 if not leaders else 22
            r = pymupdf.Rect(min(b.x0 for b in boxes) - 6, min(b.y0 for b in boxes) - pad_top,
                             max(b.x1 for b in boxes) + 6, max(b.y1 for b in boxes) + (6 if not leaders else 22))
            shape = page.new_shape()
            shape.draw_rect(r)
            shape.finish(color=(0.2, 0.2, 0.2), width=0.7, dashes="[4 2] 0")
            shape.commit()
            name = system.part(whole).name
            w = width(name)
            place([name], [(r.x0 + 3, r.y0 + 2), (r.x1 - w - 3, r.y0 + 2), (r.x0 + 3, r.y1 - size - 3),
                           (r.x1 - w - 3, r.y1 - size - 3), (r.x0 + 3, r.y0 - size - 3)])
            outlines.append(r)
        shapes[whole] = outlines[0]
    # links
    for i, l in enumerate(system.links):
        f = facts[i]
        if l.kind == "intro":
            continue  # said in the description only
        box = shapes[l.subject]
        if l.kind == "member":
            placements.append((f, box))
        elif l.kind == "option":  # the options, small parts under their stop, joined to it by a dotted line
            ob = shapes[l.object]
            shape = page.new_shape()
            shape.draw_line(((ob.x0 + ob.x1) / 2, ob.y0), ((box.x0 + box.x1) / 2, box.y1))
            shape.finish(color=(0.4, 0.4, 0.4), width=0.5, dashes="[1 1] 0", closePath=False)
            shape.commit()
            placements.append((f, ob))
        elif l.kind == "note" and l.relation == "mounted on":  # the sensor's stem to the duct
            target = shapes[l.object]
            cx = (box.x0 + box.x1) / 2
            a, b = ((cx, box.y1), (cx, target.y0)) if box.y1 < target.y0 else ((cx, box.y0), (cx, target.y1))
            placements.append((f, _stem(page, a, b)))
        elif l.kind == "note" and l.relation == "state" and legend:  # movable: a double arrow, told in the legend
            double_arrow(box.x1 + 4, box.y0 - 2, box.y1 + 2)
            placements.append((f, pymupdf.Rect(box.x1 + 1, box.y0 - 2, box.x1 + 7, box.y1 + 2)))
        elif l.kind == "note":  # a place or a state, in words beside the part
            words = f"({l.object})" if l.relation == "located at" else l.object
            w = width(words, size - 0.5)
            cx = (box.x0 + box.x1) / 2
            r = place([words], [(cx - w / 2, box.y1 + 3), (cx - w / 2, box.y1 + 3 + size * 1.2),
                                (cx - w / 2, box.y0 - size * 1.3), (box.x1 + 3, box.y0), (box.x0 - w - 3, box.y0),
                                (cx - w / 2, box.y1 + 3 + 2 * size * 1.2)], size - 0.5)
            placements.append((f, r))
        else:
            ob = shapes[l.object]
            ca, cb = ((box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2), ((ob.x0 + ob.x1) / 2, (ob.y0 + ob.y1) / 2)
            placements.append((f, line(_border(box, cb), _border(ob, ca), l.kind,
                                       l.mode or LINK_WORDS.get(l.relation, ""))))
    # numbers beside their parts: logged, and placed as their facts
    for p in system.parts:
        if p.note:
            box = shapes[p.id]
            r = place([p.note], [(box.x1 + 3, box.y1 - size), (box.x1 + 3, box.y1 + 2), (box.x0 - width(p.note) - 3, box.y1 - size),
                                 (box.x1 + 3, box.y0 - size - 2)])
            fact = notes.get(p.id)
            numbers.append((p.note.split()[0], [fact] if fact else [], r))
            if fact:
                placements.append((fact, r))
    if legend:  # what each line means, and the double arrow
        y = rect.y1 - 6
        x = rect.x0
        for kind, words in LEGEND:
            line((x, y - 3), (x + 18, y - 3), kind)
            text(x + 22, y, words, size - 0.5)
            x += 26 + width(words, size - 0.5) + 12
        double_arrow(x + 2, y - 8, y + 1)
        text(x + 8, y, "movable", size - 0.5)
    return placements, numbers

def _stem(page, a, b):
    import pymupdf
    shape = page.new_shape()
    shape.draw_line(a, b)
    shape.draw_circle(b, 1.6)
    shape.finish(color=(0, 0, 0), fill=(0, 0, 0), width=0.7, closePath=False)
    shape.commit()
    return pymupdf.Rect(min(a[0], b[0]) - 2, min(a[1], b[1]) - 2, max(a[0], b[0]) + 2, max(a[1], b[1]) + 2)

def _symbol(shape, symbol, box):
    """A part drawn as a small symbol (with leaders, its name is written beside it)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    if symbol in ("mirror", "dichroic"):
        shape.draw_line((x0 + 2, y1), (x1 - 2, y0))
        if symbol == "dichroic":
            shape.draw_line((x0 + 5, y1), (x1 + 1, y0 + 3))
    elif symbol in ("fan", "wheel"):
        shape.draw_circle((cx, cy), (x1 - x0) / 2)
        if symbol == "fan":
            shape.draw_line((cx, cy), (x1, cy))
    elif symbol == "stop":
        shape.draw_line((cx, y0), (cx, cy - 3))
        shape.draw_line((cx, cy + 3), (cx, y1))
    elif symbol == "grism":
        shape.draw_polyline([(x0, y1), (x1, y1), (cx, y0), (x0, y1)])
    elif symbol == "coil":
        shape.draw_polyline([(x0, cy), (x0 + 3, y0), (x0 + 6, y1), (x0 + 9, y0), (x0 + 12, y1), (x1, cy)])
    elif symbol == "damper":
        shape.draw_rect(box)
        shape.draw_line((x0, y1), (x1, y0))
    elif symbol == "filter":
        shape.draw_rect(box)
        shape.draw_line((x0, y0), (x1, y1))
        shape.draw_line((x0, y1), (x1, y0))
    elif symbol == "sensor":
        shape.draw_circle((cx, cy), (x1 - x0) / 3)
    elif symbol == "motor":
        shape.draw_circle((cx, cy), (x1 - x0) / 2)
        shape.draw_line((cx - 4, cy + 3), (cx - 4, cy - 3))
        shape.draw_line((cx - 4, cy - 3), (cx, cy + 1))
        shape.draw_line((cx, cy + 1), (cx + 4, cy - 3))
        shape.draw_line((cx + 4, cy - 3), (cx + 4, cy + 3))
    elif symbol == "input":
        shape.draw_line((x0, cy - 3), (x1, cy - 3))
        shape.draw_line((x0, cy + 3), (x1, cy + 3))
    else:  # box, duct, zone, panel, controller, detector, camera
        shape.draw_rect(box)
        if symbol in ("detector", "panel"):
            shape.draw_line((x0, cy), (x1, cy))


# --- projects -------------------------------------------------------------------------------------------

SCHEMATIC_KNOBS = ("clean", "prose", "prose-hard", "figure-only", "leaders", "folded", "legend", "all")
NOTE_ATTRIBUTES = {"hp": ("motor power", ("power", "rating", "horsepower", "rated power")),
                   "°F": ("supply air temperature setpoint", ("setpoint", "temperature setpoint", "supply air temperature",
                                                             "set point"))}

def build(make, pid, title, seed):
    """A controlled project from a system: a fact per link and per number, prose and a figure, chosen by knob."""
    from .model import Draw, Fact, Project
    d = Draw(f"{pid}-{seed}")
    system = make(d)
    ids = {p.id for p in system.parts}
    facts = []
    for l in system.links:
        s = system.part(l.subject)
        o = system.part(l.object) if l.object in ids else None
        facts.append(Fact(f"{l.subject}.{l.relation.replace(' ', '-')}.{l.object}", s.name, tuple(s.aliases),
                          l.relation, (), o.name if o else l.object, "", l.mode, relation=l.relation,
                          object_aliases=tuple(o.aliases) if o else tuple(l.aliases), accepts=tuple(l.accepts)))
    notes = {}
    for p in system.parts:
        if p.note:
            value, unit = p.note.split(" ", 1)
            attribute, synonyms = NOTE_ATTRIBUTES[unit]
            notes[p.id] = Fact(f"{p.id}.{attribute.split()[-1]}", p.name, tuple(p.aliases), attribute, synonyms, value,
                               unit)
            facts.append(notes[p.id])
    drawable = [i for i, l in enumerate(system.links) if l.kind != "intro"]
    stated_in_all = sorted(d.rng.sample(drawable, len(drawable) // 2))
    sections = [("1 Description", [("intro", system)]),
                ("2 Arrangement", [("relations", system), ("schematic", system)])]
    project = Project(f"{pid}-s{seed}", title, facts, sections, kinds=SCHEMATIC_KNOBS,
                      things=[(p.name, tuple(p.aliases)) for p in system.parts])
    project.schematic = dict(system=system, notes=notes, stated_in_all=stated_in_all)
    return project

def ahu_drawing(seed=1):
    return build(air_handler, "ahu-schematic", "Lakeshore Hall C: AHU-3 Air System", seed)

def uv_layout(seed=1):
    return build(uv_channel, "uv-layout", "Kestrel Spectrograph: UV Channel Layout", seed)

def intro_html(system, esc):
    """The description, its facts (if any) in spans so layout places them."""
    return "<p>" + "".join(f"<span id='rel-{i}'>{esc(t)}</span>" if i is not None else esc(t)
                           for t, i in system.intro) + "</p>"

SCHEMATIC_PROJECTS = {"ahu-schematic": ahu_drawing, "uv-layout": uv_layout}

def figure_style(project):
    return dict(leaders=project.has("leaders"), folded=project.has("folded"), legend=project.has("legend"))

def has_figure(project):
    return project.knob not in ("prose", "prose-hard")

def prose_html(project, system, esc):
    """The arrangement in words: every link and number (clean, prose, prose-hard), half the links (all, in hard
    phrasing), or none, the figure cited instead. Each sentence is a span whose id names its links, so layout
    places their facts."""
    from .model import Draw
    knob = project.knob
    which = ([i for i, l in enumerate(system.links) if l.kind != "intro"] if knob in ("clean", "prose", "prose-hard")
             else project.schematic["stated_in_all"] if knob == "all" else [])
    which = list(which)
    hard = knob in ("prose-hard", "all")
    cite = "Figure 1 shows the arrangement." if has_figure(project) else ""
    if not which:
        return f"<p>{esc(cite)} Its parts are named on the figure.</p>"
    parts = []
    for text, links in sentences(system, hard, Draw(f"{system.id}-prose"), which):
        parts.append(f"<span id='rel-{'-'.join(map(str, links))}'>{esc(text)}</span>")
    for pid, fact in project.schematic["notes"].items():
        part = system.part(pid)
        parts.append(esc(f"{_cap(_the(part.name))} is rated {fact.value} {fact.unit}." if fact.unit == "hp" else
                         f"{_cap(_the(part.name))} holds the supply air at {fact.value} {fact.unit}."))
    return f"<p>{esc(cite)} " + " ".join(parts) + "</p>"
