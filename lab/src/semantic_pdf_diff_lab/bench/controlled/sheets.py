"""Drawing sheets for controlled documents (milestone 3c): a floor plan on an ARCH D sheet, its dimensions in feet
and inches, its rooms tagged, its doors scheduled, under knobs of rising difficulty.

From the scenario catalogue: small dimension text read wrong from an overview ("2'-9 1/2\\" read as 2'-3\\""),
rotated sheets, values bound to the wrong room or grid line, title blocks and revision tables read as all there
is, schedules on drawing sheets. Values are drawn as a drafter would: dimension strings between ticks, room tags
with areas, a door schedule; the facts are the rooms' sizes and areas, the doors' sizes, and which room each door
serves.
"""
import re
from dataclasses import dataclass, field
from semantic_pdf_diff.values import FEET_INCHES, INCH, _inch, ft_in, inches  # noqa: F401 (values.py)

SHEET_KNOBS = ("clean", "small", "vertical", "rotated", "all")
ARCH_D = (2592.0, 1728.0)       # 36 x 24 in, landscape
SCALE = 9.0                     # points per foot: 1/8" = 1'-0"
@dataclass
class Room:
    number: str
    name: str
    x: float                    # feet from grid line A
    y: float                    # feet from grid line 1 (south is +)
    width: float                # inches, east-west
    depth: float                # inches, north-south
    door: str = ""              # its door's tag
    door_side: str = "south"    # the wall its door is on

@dataclass
class Plan:
    grid_x: list                # feet, A, B, C...
    grid_y: list                # feet, 1, 2, 3...
    rooms: list
    doors: dict                 # tag: (width in, height in)
    notes: list = field(default_factory=list)

def floor_plan(d):
    """Hall C's meeting rooms: a row of rooms north of a corridor, a row south, each its own size."""
    bays = [d.rng.choice((28, 30, 32, 34)) for _ in range(5)]
    grid_x = [sum(bays[:k]) for k in range(6)]
    grid_y = [0, 34, 46, 80]
    rooms, x = [], 2.0
    names = ("MEETING", "MEETING", "MEETING", "MEETING")
    used = set()

    def size(lo, hi):
        for _ in range(200):
            v = d.rng.randrange(lo * 2, hi * 2 + 1) * 6  # whole feet and half feet, in inches
            if v not in used:
                used.add(v)
                return v
        raise ValueError("no unused size")

    for k, name in enumerate(names):  # north row: doors on the corridor (south) side
        w, dp = size(22, 38), size(22, 31)
        rooms.append(Room(f"{101 + k}", name, x, 32 - dp / 12, w, dp, f"D{101 + k}", "south"))
        x += w / 12 + 1
    x = 2.0
    for k, name in enumerate(("STORAGE", "ELECTRICAL", "MECHANICAL")):  # south row: doors north
        w, dp = size(12, 30), size(14, 30)
        rooms.append(Room(f"{110 + k}", name, x, 48, w, dp, f"D{110 + k}", "north"))
        x += w / 12 + 1
    doors = {}
    widths, heights = (36, 42, 48, 72), (84, 90, 96)
    for r in rooms:
        doors[r.door] = (d.rng.choice(widths), d.rng.choice(heights))
    notes = ["ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE.",
             "SEE MECHANICAL SHEETS FOR DUCT AND DIFFUSER LOCATIONS.",
             "VERIFY ALL CONDITIONS IN THE FIELD BEFORE STARTING WORK.",
             "ROOM AREAS ARE NET, MEASURED TO FACE OF FINISH."]
    return Plan(grid_x, grid_y, rooms, doors, notes)

def plan_sheet(seed=1):
    """A controlled project whose one page is the floor plan sheet."""
    from .corpus import Draw, Fact, Project
    d = Draw(f"lcc-plan-{seed}")
    plan = floor_plan(d)
    facts = []
    for r in plan.rooms:
        room = f"{r.name.title()} {r.number}"
        aliases = (f"Room {r.number}", f"{r.name.title()} Room {r.number}", r.number, f"{r.name} {r.number}")
        facts.append(Fact(f"room{r.number}.width", room, aliases, "width", ("east-west dimension", "room width"),
                          ft_in(r.width), "ft-in", drawn="drawing"))
        facts.append(Fact(f"room{r.number}.depth", room, aliases, "depth", ("north-south dimension", "room depth"),
                          ft_in(r.depth), "ft-in", drawn="drawing"))
        area = round(r.width * r.depth / 144)
        facts.append(Fact(f"room{r.number}.area", room, aliases, "floor area", ("area", "net area", "room area"),
                          f"{area:,}", "ft²", drawn="drawing"))
        w, h = plan.doors[r.door]
        door = f"Door {r.door}"
        facts.append(Fact(f"{r.door}.width", door, (r.door,), "width", ("door width", "opening width"), ft_in(w),
                          "ft-in", drawn="table"))
        facts.append(Fact(f"{r.door}.height", door, (r.door,), "height", ("door height", "opening height"), ft_in(h),
                          "ft-in", drawn="table"))
        facts.append(Fact(f"{r.door}.part-of.room{r.number}", door, (r.door,), "part of", (), room, "",
                          relation="part of", object_aliases=aliases, accepts=("within", "linked", "serves", "leads to"),
                          drawn="table"))
    for rev, date, what in REVISIONS:  # the revision table's dates: fair claims, so facts
        facts.append(Fact(f"rev{rev}.date", f"Revision {rev}", (f"Rev {rev}", f"Rev. {rev}"), "date",
                          ("issue date", "revision date", "issued", "date issued"), date, "", what, drawn="table"))
    project = Project(f"lcc-plan-s{seed}", "Lakeshore Hall C: Meeting Rooms Floor Plan", facts, [], kinds=SHEET_KNOBS,
                      things=[(f"{r.name.title()} {r.number}", (f"Room {r.number}", f"{r.name.title()} Room {r.number}",
                                                                 r.number, f"{r.name} {r.number}")) for r in plan.rooms] +
                             [(f"Door {r.door}", (r.door,)) for r in plan.rooms] +
                             [("Corridor C-100", ("C-100", "corridor"))])  # named on the sheet, though in no fact
    project.sheet = plan
    return project

SHEET_PROJECTS = {"lcc-plan": plan_sheet}
REVISIONS = (("A", "2026-01-10", "ISSUED FOR REVIEW"), ("B", "2026-02-20", "REVISED PER COMMENTS"),
             ("C", "2026-03-14", "ISSUED FOR PERMIT"))

# --- drawing --------------------------------------------------------------------------------------------

def render(project):
    """(pdf bytes, the printed numbers' log), like controlled.render, for a sheet drawn directly."""
    import pymupdf
    from .corpus import locate
    plan = project.sheet
    small, vertical, rotated = (project.has(k) for k in ("small", "vertical", "rotated"))
    tag_size, dim_size = (6.0, 4.5) if small else (10.0, 8.0)
    door_of = {f.entity.split()[-1]: f for f in project.facts if f.relation}  # each door's room, as a fact
    in_table, on_plan = [], []  # where those facts are shown
    doc = pymupdf.open()
    page = doc.new_page(width=ARCH_D[0], height=ARCH_D[1])
    ox, oy = 260.0, 330.0  # where grid lines A and 1 cross
    X = lambda ft: ox + ft * SCALE
    Y = lambda ft: oy + ft * SCALE
    text = lambda x, y, t, s, rotate=0, font="helv": page.insert_text((x, y), t, fontsize=s, fontname=font, rotate=rotate)
    width = lambda t, s: pymupdf.get_text_length(t, fontname="helv", fontsize=s)

    def lines(points, w=0.6, color=(0, 0, 0), dashes=None):
        shape = page.new_shape()
        shape.draw_polyline(points)
        shape.finish(color=color, width=w, dashes=dashes, closePath=False)
        shape.commit()

    # the sheet: border, title block, revision table, notes
    border = pymupdf.Rect(36, 36, ARCH_D[0] - 36, ARCH_D[1] - 36)
    lines([border.tl, border.tr, border.br, border.bl, border.tl], 2.0)
    tb = pymupdf.Rect(ARCH_D[0] - 520, 36, ARCH_D[0] - 36, ARCH_D[1] - 36)
    lines([tb.tl, tb.bl], 1.5)
    rows = [("PROJECT", 9), ("LAKESHORE CONVENTION CENTER EXPANSION", 14), ("HALL C", 14), ("SHEET TITLE", 9),
            ("FLOOR PLAN - MEETING ROOMS", 14), ("SCALE", 9), ('1/8" = 1\'-0"', 12), ("SHEET", 9), ("A-201", 28)]
    y = ARCH_D[1] - 520
    for t, s in rows:
        y += s * 1.9
        text(tb.x0 + 20, y, t, s)
    lines([(tb.x0, ARCH_D[1] - 540), (tb.x1, ARCH_D[1] - 540)], 1.0)
    rev_y = ARCH_D[1] - 760  # the revision table, above the title
    text(tb.x0 + 20, rev_y, "REVISIONS", 10)
    for k, (rev, date, what) in enumerate(REVISIONS):
        yy = rev_y + 22 + k * 20
        text(tb.x0 + 20, yy, rev, 9)
        text(tb.x0 + 60, yy, date, 9)
        text(tb.x0 + 160, yy, what, 9)
        lines([(tb.x0 + 10, yy + 6), (tb.x1 - 10, yy + 6)], 0.4)
    text(tb.x0 + 20, 90, "GENERAL NOTES", 11)
    for k, note in enumerate(plan.notes):
        text(tb.x0 + 20, 118 + k * 18, f"{k + 1}. {note}", 7.5)
    # the door schedule, on the sheet
    sched_x, sched_y = tb.x0 + 20, 260.0
    text(sched_x, sched_y, "DOOR SCHEDULE", 11)
    cols = (("DOOR", 0), ("ROOM", 60), ("WIDTH", 170), ("HEIGHT", 240))
    for name, dx in cols:
        text(sched_x + dx, sched_y + 24, name, 8)
    lines([(sched_x - 4, sched_y + 30), (sched_x + 310, sched_y + 30)], 0.8)
    table_box = pymupdf.Rect(sched_x - 6, sched_y + 8, sched_x + 312, sched_y + 34 + 18 * len(plan.rooms))
    for k, r in enumerate(plan.rooms):
        yy = sched_y + 46 + k * 18
        w, h = plan.doors[r.door]
        for value, dx in ((r.door, 0), (f"{r.name} {r.number}", 60), (ft_in(w), 170), (ft_in(h), 240)):
            text(sched_x + dx, yy, value, 8)
        in_table.append((door_of[r.door], pymupdf.Rect(sched_x, yy - 8, sched_x + 170, yy + 2)))
        lines([(sched_x - 4, yy + 5), (sched_x + 310, yy + 5)], 0.3)
    lines([table_box.tl, table_box.tr, table_box.br, table_box.bl, table_box.tl], 0.8)
    # the grid: dashed lines, lettered and numbered bubbles
    for k, gx in enumerate(plan.grid_x):
        lines([(X(gx), Y(plan.grid_y[0]) - 70), (X(gx), Y(plan.grid_y[-1]) + 30)], 0.4, (0.5, 0.5, 0.5), "[12 4 2 4] 0")
        _bubble(page, X(gx), Y(plan.grid_y[0]) - 86, "ABCDEF"[k])
    for k, gy in enumerate(plan.grid_y):
        lines([(X(plan.grid_x[0]) - 70, Y(gy)), (X(plan.grid_x[-1]) + 30, Y(gy))], 0.4, (0.5, 0.5, 0.5), "[12 4 2 4] 0")
        _bubble(page, X(plan.grid_x[0]) - 86, Y(gy), str(k + 1))
    # the rooms: walls, tags, dimension strings, doors
    for r in plan.rooms:
        x0, y0, x1, y1 = X(r.x), Y(r.y), X(r.x + r.width / 12), Y(r.y + r.depth / 12)
        shape = page.new_shape()
        shape.draw_rect(pymupdf.Rect(x0, y0, x1, y1))
        shape.finish(color=(0, 0, 0), width=2.0)
        shape.commit()
        cx, cy = (x0 + x1) / 2 + 8, (y0 + y1) / 2 + 2.2 * tag_size  # the tag below the depth's label, clear of it
        name, area = f"{r.name} {r.number}", f"{round(r.width * r.depth / 144):,} SF"
        text(cx - width(name, tag_size) / 2, cy - tag_size * 0.3, name, tag_size)
        text(cx - width(area, tag_size * 0.85) / 2, cy + tag_size * 1.1, area, tag_size * 0.85)
        # width: a dimension string inside the room, along the wall away from its door (clear of grid lines)
        dy = y0 + 14 if r.door_side == "south" else y1 - 14
        _dimension(page, (x0, dy), (x1, dy), ft_in(r.width), dim_size, vertical=False)
        # depth: on the room's west side, inside; written sideways when the knob says
        _dimension(page, (x0 + 14, y0), (x0 + 14, y1), ft_in(r.depth), dim_size, vertical=vertical)
        # the door: a gap, a swing, a tag
        dx0 = x0 + (x1 - x0) * 0.6
        door_w = plan.doors[r.door][0] / 12 * SCALE
        wall_y = y1 if r.door_side == "south" else y0
        lines([(dx0, wall_y), (dx0 + door_w, wall_y)], 3.0, (1, 1, 1))
        swing = page.new_shape()
        sgn = -1 if r.door_side == "south" else 1
        swing.draw_line((dx0, wall_y), (dx0, wall_y + sgn * door_w))
        swing.draw_curve((dx0, wall_y + sgn * door_w), (dx0 + door_w, wall_y + sgn * door_w), (dx0 + door_w, wall_y))
        swing.finish(color=(0, 0, 0), width=0.5, closePath=False)
        swing.commit()
        tag_y = wall_y + (-10 if r.door_side == "south" else 16)  # inside the room, beside its door
        tag_x = dx0 - width(r.door, tag_size * 0.8) / 2 - 10
        _door_tag(page, tag_x, tag_y, r.door, tag_size * 0.8)
        on_plan.append((door_of[r.door], pymupdf.Rect(x0, y0, x1, y1)))
    # the corridor's name
    text(X(plan.grid_x[0]) + 40, Y(40) + 4, "CORRIDOR C-100", tag_size)
    text(X(0), Y(plan.grid_y[-1]) + 80, "FLOOR PLAN - MEETING ROOMS", 16)
    text(X(0), Y(plan.grid_y[-1]) + 100, 'SCALE: 1/8" = 1\'-0"', 9)
    if rotated:
        page.set_rotation(90)  # stored turned, as many sheets are
    doc.set_metadata({})
    data = doc.tobytes(garbage=3, deflate=True, no_new_id=True)
    log = locate(project, pymupdf.open("pdf", data), {1: [tuple(table_box)]},
                 {1: [(None, in_table, [], "table"), (None, on_plan, [], "drawing")]})
    return data, log

def _bubble(page, x, y, label, r=14):
    import pymupdf
    shape = page.new_shape()
    shape.draw_circle((x, y), r)
    shape.finish(color=(0, 0, 0), width=0.8)
    shape.commit()
    w = pymupdf.get_text_length(label, fontname="helv", fontsize=12)
    page.insert_text((x - w / 2, y + 4.5), label, fontsize=12, fontname="helv")

def _door_tag(page, x, y, label, size):
    import pymupdf
    w = pymupdf.get_text_length(label, fontname="helv", fontsize=size)
    shape = page.new_shape()
    shape.draw_rect(pymupdf.Rect(x - w / 2 - 3, y - size, x + w / 2 + 3, y + size * 0.4))
    shape.finish(color=(0, 0, 0), width=0.5)
    shape.commit()
    page.insert_text((x - w / 2, y), label, fontsize=size, fontname="helv")

def _dimension(page, a, b, label, size, vertical=False):
    """A dimension string: a line between ticks, extension marks, its value written along it."""
    import pymupdf
    shape = page.new_shape()
    shape.draw_line(a, b)
    for p in (a, b):  # oblique ticks, as architects draw them
        shape.draw_line((p[0] - 3, p[1] + 3), (p[0] + 3, p[1] - 3))
    shape.finish(color=(0, 0, 0), width=0.5, closePath=False)
    shape.commit()
    w = pymupdf.get_text_length(label, fontname="helv", fontsize=size)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    if a[0] == b[0]:  # a vertical dimension
        if vertical:
            page.insert_text((mx - 2, my + w / 2), label, fontsize=size, fontname="helv", rotate=90)
        else:
            page.insert_text((mx + 4, my + size / 3), label, fontsize=size, fontname="helv")
    else:
        page.insert_text((mx - w / 2, my - 2), label, fontsize=size, fontname="helv")
