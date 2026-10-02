"""Revision pairs (controlled documents, milestone 4): a corpus document and a revision of it with known changes, so
a comparison in revisions mode is scored exactly (comparison.py).

A revision is its base project edited: a value changed wherever it's printed, a table row added like its neighbour
or dropped, a sentence dropped or added or rewritten, a drawing's plan altered. The base is the corpus's own
document, byte for byte, so its recorded answers serve the pair; only the revision is new.

The changes are those revisions make, met in documents and reviews:
- a value revised in prose, in a table cell, in a chart (with the totals that follow it), on a drawing
- an item added to a schedule or removed from it, the rows below moving up or down
- a requirement tightened, behind a trap phrasing
- a room renumbered: one row dropped and another added, not one row changed
- a drawing's revision table gaining a row
- a change the later revision narrates, printing the superseded value beside the new one (the roller coaster's
  lift hill: the corpus's document is that later revision, so its earlier one is generated)
"""
import re
from dataclasses import dataclass, replace

from .corpus import (CHART_PROJECTS, Draw, Fact, PROJECTS, PROSE_PROJECTS, TABLE_PROJECTS, parse_number, render)
from .sheets import SHEET_PROJECTS, sheet_project

@dataclass
class Pair:
    id: str          # the pair: its base document's id
    earlier: str     # the documents' ids, the earlier revision first
    later: str

# --- edits -------------------------------------------------------------------------------------

def _pattern(text):
    """A printed value or tag as a whole token: not part of a longer number, a tag ("P-101A") or a word ("3-second")."""
    return re.compile(r"(?<![\w.,-])" + re.escape(text) + r"(?![\w-]|[.,]\d)")

SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

def _rewrite(project, edit):
    """Apply edit (str -> str) to every string the project prints from its blocks: paragraphs, table and schedule
    cells, and the values its templated texts are filled with. Charts and sheets draw from facts, so follow them."""
    for _, blocks in project.sections:
        for i, block in enumerate(blocks):
            if block[0] == "p":
                blocks[i] = ("p", edit(block[1]))
            elif block[0] == "schedule":
                for s, (title, kind, columns, rows) in enumerate(block[1].sections):
                    block[1].sections[s] = (title, kind, columns, [(tag, [edit(c) for c in cells]) for tag, cells in rows])
            elif block[0] in ("table", "rooms"):
                block[3][:] = [[edit(c) for c in row] for row in block[3]]
    if project.values:
        project.values = {k: edit(v) for k, v in project.values.items()}

def drawer(project):
    """New values for a revision: seeded by the project, and unused by any of its facts (a value names one fact)."""
    d = Draw(f"{project.id}-revision")
    d.used |= {f.value for f in project.facts}
    return d

def near(d, value, low=-0.15, high=0.15):
    """A new value within a share of an old one, printed alike (as many decimals)."""
    x = parse_number(value)
    return d.number(x * (1 + low), x * (1 + high), len(value.split(".")[1]) if "." in value else 0)

def change(project, fact_id, value):
    """A fact's value revised, wherever it's printed (a chart draws it from the fact)."""
    fact, count = project.fact(fact_id), 0
    pattern = _pattern(fact.value)

    def edit(text):
        nonlocal count
        text, n = pattern.subn(value, text)
        count += n
        return text
    _rewrite(project, edit)
    if not count and fact.drawn != "chart":
        raise ValueError(f"{project.id}: {fact_id}'s value {fact.value} isn't printed in its blocks")
    fact.value = value

def _rows(project):
    """Every table's rows, as (rows list, the row's name, its cells): schedules hold (tag, cells), tables lists."""
    for _, blocks in project.sections:
        for block in blocks:
            if block[0] == "schedule":
                for _, _, _, rows in block[1].sections:
                    yield rows, (lambda row: row[0]), (lambda row: row[1])
            elif block[0] in ("table", "rooms"):
                yield block[3], (lambda row: row[0]), (lambda row: row[1:])

def drop_row(project, tag):
    """A table row dropped (its first cell names tag), with the facts printed in it."""
    pattern, dropped = _pattern(tag), []
    for rows, name, cells in _rows(project):
        dropped += [c for row in rows if pattern.search(name(row)) for c in cells(row)]
        rows[:] = [row for row in rows if not pattern.search(name(row))]
    if not dropped:
        raise ValueError(f"{project.id}: no row named {tag}")
    project.facts[:] = [f for f in project.facts if f.value not in dropped]

def add_row(project, like, tag, d, after=None):
    """A row added like another (its first cell names `like`): its facts copied under the new tag, their values
    drawn near the other's. Placed after the row named `after` (default: the one it's like)."""
    pattern, at = _pattern(like), _pattern(after or like)
    rename = lambda text: pattern.sub(tag, text)
    by_value = {f.value: f for f in project.facts}

    def copy(cell):
        f = by_value.get(cell)
        if f is None:  # "n/a", say
            return cell
        new = replace(f, id=f.id.replace(like, tag), entity=rename(f.entity), aliases=tuple(map(rename, f.aliases)),
                      value=near(d, f.value), forms=[])
        project.facts.append(new)
        return new.value
    for rows, name, cells in _rows(project):
        for row in rows:
            if pattern.search(name(row)):
                new = [rename(name(row))] + [copy(c) for c in cells(row)]
                where = next(k for k, r in enumerate(rows) if at.search(name(r)))
                rows.insert(where + 1, (new[0], new[1:]) if isinstance(row, tuple) else new)
                return
    raise ValueError(f"{project.id}: no row named {like}")

def _paragraph(project, fact_id):
    """(blocks, index, sentences, the sentence's index) of the paragraph sentence printing a fact's value."""
    pattern = _pattern(project.fact(fact_id).value)
    for _, blocks in project.sections:
        for i, block in enumerate(blocks):
            if block[0] == "p" and pattern.search(block[1]):
                sentences = SENTENCE.split(block[1])
                return blocks, i, sentences, next(k for k, s in enumerate(sentences) if pattern.search(s))
    raise ValueError(f"{project.id}: {fact_id} isn't printed in a paragraph")

def drop_sentence(project, fact_id):
    """The sentence printing a fact dropped from its paragraph, with every fact it printed."""
    blocks, i, sentences, k = _paragraph(project, fact_id)
    gone = sentences.pop(k)
    blocks[i] = ("p", " ".join(sentences))
    project.facts[:] = [f for f in project.facts if f.relation or not _pattern(f.value).search(gone)]

def add_sentence(project, after_fact, template, fact):
    """A sentence stating a new fact ({v} its value), after the sentence printing another's."""
    blocks, i, sentences, k = _paragraph(project, after_fact)
    sentences.insert(k + 1, template.format(v=fact.value))
    blocks[i] = ("p", " ".join(sentences))
    project.facts.append(fact)

def rewrite(project, old, new):
    """A passage of a paragraph rewritten (printed exactly once)."""
    found = 0
    for _, blocks in project.sections:
        for i, block in enumerate(blocks):
            if block[0] == "p" and old in block[1]:
                found += block[1].count(old)
                blocks[i] = ("p", block[1].replace(old, new))
    if found != 1:
        raise ValueError(f"{project.id}: {old!r} is printed {found} times")

# --- the revisions -----------------------------------------------------------------------------

def wtp_later(p, d):
    """Revision B of the treatment plant's design basis: a fourth raw water pump; the design flow, one pump's
    capacity, the maximum alum dose and UV's capital cost revised; chlorine feed no longer given."""
    for fid in ("plant.design_flow", "P-101B.capacity", "chem.alum_max", "optA.cost"):
        change(p, fid, near(d, p.fact(fid).value))
    add_row(p, "P-101C", "P-101D", d)
    drop_sentence(p, "chem.chlorine")

def coaster_earlier(p, d):
    """The roller coaster before revision B raised its lift hill (the corpus's document is revision B, which says
    so and prints the old height): the lift hill at its old height, the train's mass, the hourly capacity and the
    loop's entry speed as they were, no helix yet, and a station platform length that revision B no longer gives."""
    old, lift = p.fact("ride.lift_old"), p.fact("ride.lift")
    rewrite(p, f"In revision B the lift hill was raised from {old.value} ft to {lift.value} ft.",
            f"The lift hill rises {old.value} ft.")
    p.facts.remove(old)
    lift.value, lift.conditions = old.value, ""
    for fid in ("trains.mass", "ride.capacity", "el.Vertical loop.speed"):
        change(p, fid, near(d, p.fact(fid).value, -0.1, 0.1))
    drop_row(p, "Helix")
    add_sentence(p, "struct.wind", "The station platform is {v} ft long.",
                 Fact("station.length", "Station", ("station platform", "platform", "the station"), "platform length",
                      ("length", "station length", "platform"), d.number(90, 140), "ft"))

def wtp_tables_later(p, d):
    """Revision B of the equipment schedules: pump P-101D added under P-101C; valve V-314 removed, so the valves
    below it move up across the split tables; one pump's power, one blower's pressure and one valve's Cv revised."""
    for fid in ("P-101B.motor power", "B-402.discharge pressure", "V-306.flow coefficient"):
        change(p, fid, near(d, p.fact(fid).value))
    add_row(p, "P-101C", "P-101D", d)
    drop_row(p, "V-314")

def lcc_later(p, d):
    """Revision B of Hall C's design basis, in its trap phrasings: the noise limit tightened ("shall not exceed"),
    the roof's snow rating ("not rated for snow loads above") and the chilled beams' first cost (stated against the
    baseline's) revised, and meeting room 104 replaced by a room 105 (a renumbering: one row gone, another new)."""
    change(p, "hallc.noise", near(d, p.fact("hallc.noise").value, -0.15, -0.04))
    for fid in ("roof.snow", "opt1.cost"):
        change(p, fid, near(d, p.fact(fid).value))
    drop_row(p, "104")
    add_row(p, "103", "105", d)

def energy_later(p, d):
    """Revision B of the cooling energy study: two monthly bars remodelled (Option 1's July, Option 2's August),
    the season totals following them, and the exhibit floor's peak load revised (Figure 2)."""
    for fid, grid in (("opt1.july", 25), ("opt2.august", 25), ("zone.exhibit", 10)):
        change(p, fid, d.slot(p.fact(fid).number * d.rng.uniform(1.06, 1.15), grid))
    for option in ("opt1", "opt2"):
        months = [f for f in p.facts if f.id.startswith(option + ".") and f.drawn == "chart"]
        change(p, f"{option}.season", f"{sum(f.number for f in months):,.0f}")

def plan_later(p, d):
    """Revision D of the floor plan: meeting room 102 widened (its area follows, and the rooms east of it move),
    door D103 widened, and the revision table gains revision D."""
    plan = p.sheet
    room = next(r for r in plan.rooms if r.number == "102")
    sizes = {s for r in plan.rooms for s in (r.width, r.depth)}
    grow = next(g for g in (24, 30, 18, 36) if room.width + g not in sizes)
    for r in plan.rooms:
        if r.door_side == room.door_side and r.x > room.x:
            r.x += grow / 12
    room.width += grow
    width, height = plan.doors["D103"]
    plan.doors["D103"] = (next((w for w in (36, 42, 48, 72) if w > width), 48), height)
    plan.revisions = plan.revisions + (("D", "2026-04-02", "ROOM 102 ENLARGED, DOOR D103 WIDENED"),)
    p.facts[:] = sheet_project(plan, p.id).facts

# base maker, its knob (None: the clean corpus), the edit, whether the generated document is the earlier one
PAIRS = ((PROJECTS["wtp"], None, wtp_later, False),
         (PROJECTS["coaster"], None, coaster_earlier, True),
         (TABLE_PROJECTS["wtp-tables"], "clean", wtp_tables_later, False),
         (PROSE_PROJECTS["lcc"], "traps", lcc_later, False),
         (CHART_PROJECTS["lcc-energy"], "clean", energy_later, False),
         (SHEET_PROJECTS["lcc-plan"], "clean", plan_later, False))

def _base(make, knob, seed):
    p = make(seed)
    if knob:
        p.id, p.knob = f"{p.id}-{knob}", knob
    return p

def pairs(seed=1):
    """Each pair's documents, by id (nothing generated)."""
    out = []
    for make, knob, edit, earlier in PAIRS:
        base = _base(make, knob, seed).id
        mine = f"{base}-{'earlier' if earlier else 'revised'}"
        out.append(Pair(base, *((mine, base) if earlier else (base, mine))))
    return out

def check(base, project):
    """A revision's key is honest: its facts all placed (render raises otherwise), each value naming one fact (a
    sheet's door sizes repeat, as the base's do), and no number printed that the base doesn't print, but facts, the
    names of things added ("P-101D") and page numbers (an edit that missed a printed value would leave it as a
    stray number)."""
    _, before = render(base)
    _, after = render(project)
    values = [f.value for f in project.facts if not f.relation]
    if not getattr(project, "sheet", None) and len(values) != len(set(values)):
        raise ValueError(f"{project.id}: a value names two facts")
    structure = lambda log: {p["text"] for p in log if p["role"] == "structure"}
    old = {f.id for f in base.facts}
    names = {w for f in project.facts if f.id not in old for name in (f.entity, *f.aliases) for w in name.split()}
    stray = structure(after) - structure(before) - names - {str(p["page"]) for p in after}
    if stray:
        raise ValueError(f"{project.id}: numbers printed that are neither the base's nor facts: {sorted(stray)}")

def revised(seed=1, only=None):
    """[(Pair, the generated project)]: each pair's generated document (or only those of the pairs named), checked
    against its base."""
    out = []
    for (make, knob, edit, _), pair in zip(PAIRS, pairs(seed)):
        if only is not None and pair.id not in only:
            continue
        project = _base(make, knob, seed)
        edit(project, drawer(project))
        project.id = pair.earlier if pair.later == project.id else pair.later
        check(_base(make, knob, seed), project)
        out.append((pair, project))
    return out
