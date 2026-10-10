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
- a message inserted into a procedure diagram, the steps after it renumbered (TS 38.300's procedure diagrams, read
  as pictures: the revision comparison plan)

And the confounders the "why different" pass met in real specifications (the revision comparison plan, milestone 4),
on the link protocol's specification: a value changed beside its look-alikes (an extended short format beside the
short; a field beside its length field), a list's member replaced and another added, a numbered condition inserted
(the rest renumbered), a lead-in's conditions changed with the sentences under it kept word for word, and a value's
conditions reworded without changing their meaning.
"""
import re
from dataclasses import dataclass, replace

from semantic_pdf_diff.values import parse_number

from .corpus import CHART_PROJECTS, PROJECTS, PROSE_PROJECTS, TABLE_PROJECTS, render
from .model import Draw, Fact
from .procedures import PROCEDURE_PROJECTS
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
    if not count and fact.drawn not in ("chart", "figure"):
        raise ValueError(f"{project.id}: {fact_id}'s value {fact.value} isn't printed in its blocks")
    project.edits.append({"kind": "changed", "fact": fact_id, "from": fact.value, "to": value})
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
    project.edits.append({"kind": "removed", "facts": [f.id for f in project.facts if f.value in dropped]})
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
                before = len(project.facts)
                new = [rename(name(row))] + [copy(c) for c in cells(row)]
                where = next(k for k, r in enumerate(rows) if at.search(name(r)))
                rows.insert(where + 1, (new[0], new[1:]) if isinstance(row, tuple) else new)
                project.edits.append({"kind": "added", "facts": [f.id for f in project.facts[before:]]})
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
    dropped = [f for f in project.facts if not f.relation and _pattern(f.value).search(gone)]
    project.edits.append({"kind": "removed", "facts": [f.id for f in dropped]})
    project.facts[:] = [f for f in project.facts if f not in dropped]

def add_sentence(project, after_fact, template, fact):
    """A sentence stating a new fact ({v} its value), after the sentence printing another's."""
    blocks, i, sentences, k = _paragraph(project, after_fact)
    sentences.insert(k + 1, template.format(v=fact.value))
    blocks[i] = ("p", " ".join(sentences))
    project.facts.append(fact)
    project.edits.append({"kind": "added", "facts": [fact.id]})

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

def rename_row(project, old, new):
    """A row's thing renamed (P-101B becomes P-201B), its values kept."""
    pattern, renamed = _pattern(old), {}
    for rows, name, cells in _rows(project):
        for k, row in enumerate(rows):
            if pattern.search(name(row)):
                rows[k] = (pattern.sub(new, name(row)), cells(row)) if isinstance(row, tuple) else \
                          [pattern.sub(new, name(row))] + list(cells(row))
                for f in project.facts:
                    if f.value in cells(row):
                        renamed[f.id] = f.id.replace(old, new)
                        f.id, f.entity = renamed[f.id], pattern.sub(new, f.entity)
                        f.aliases = tuple(pattern.sub(new, a) for a in f.aliases)
    if not renamed:
        raise ValueError(f"{project.id}: no row named {old}")
    project.edits.append({"kind": "renamed", "facts": renamed})

def move_row(project, tag, after):
    """A row moved within its table, to after the row named `after` (rows reordered; nothing else changes)."""
    pattern, at = _pattern(tag), _pattern(after)
    for rows, name, cells in _rows(project):
        k = next((k for k, r in enumerate(rows) if pattern.search(name(r))), None)
        if k is not None and any(at.search(name(r)) for r in rows):
            row = rows.pop(k)
            rows.insert(next(j for j, r in enumerate(rows) if at.search(name(r))) + 1, row)
            project.edits.append({"kind": "moved", "facts": [f.id for f in project.facts if f.value in cells(row)]})
            return
    raise ValueError(f"{project.id}: no table with rows {tag} and {after}")

def restate(project, fact_id, old, new, conditions):
    """A fact's conditions changed, its value kept: a passage rewritten (printed once) and the key's conditions."""
    rewrite(project, old, new)
    fact = project.fact(fact_id)
    project.edits.append({"kind": "conditions", "fact": fact_id, "from": fact.conditions, "to": conditions})
    fact.conditions = conditions

def split_row(project, tag, tags, d, column):
    """A row's thing split in two (one pump replaced by two smaller ones): the column `column`'s value divided
    between them so the parts sum to the whole, the other values drawn near the old ones."""
    pattern = _pattern(tag)
    for rows, name, cells in _rows(project):
        k = next((k for k, r in enumerate(rows) if pattern.search(name(r))), None)
        if k is None:
            continue
        row = rows.pop(k)
        old = [f for f in project.facts if f.value in cells(row)]
        whole = next(f for f in old if f.attribute == column)
        decimals = len(whole.value.split(".")[1]) if "." in whole.value else 0
        for _ in range(100):
            part = d.number(whole.number * 0.35, whole.number * 0.65, decimals)
            rest = f"{whole.number - parse_number(part):,.{decimals}f}"
            if rest not in d.used and parse_number(rest) > 0:
                d.used.add(rest)
                break
        else:
            raise ValueError(f"{project.id}: no split of {whole.value}")
        new_facts = []
        for n, new_tag in enumerate(tags):
            rename = lambda text: pattern.sub(new_tag, text)
            values = {}
            for f in old:
                value = (part if n == 0 else rest) if f is whole else near(d, f.value, -0.05, 0.05)
                g = replace(f, id=f.id.replace(tag, new_tag), entity=rename(f.entity),
                            aliases=tuple(map(rename, f.aliases)), value=value, forms=[])
                new_facts.append(g)
                values[f.value] = value
            new_row = [rename(name(row))] + [values.get(c, c) for c in cells(row)]
            rows.insert(k + n, (new_row[0], new_row[1:]) if isinstance(row, tuple) else new_row)
        project.facts[:] = [f for f in project.facts if f not in old] + new_facts
        project.edits.append({"kind": "split", "from": [f.id for f in old], "to": [g.id for g in new_facts],
                              "sum": {"column": column, "whole": whole.value, "parts": [part, rest]}})
        return
    raise ValueError(f"{project.id}: no row named {tag}")

def replace_paragraph(project, fact_id, text, fact):
    """A paragraph (a list's member) replaced by another stating a new fact ({v} its value): one gone, one new."""
    blocks, i, _, _ = _paragraph(project, fact_id)
    old = project.fact(fact_id)
    blocks[i] = ("p", text.format(v=fact.value))
    project.facts[:] = [f for f in project.facts if f is not old] + [fact]
    project.edits += [{"kind": "removed", "facts": [old.id]}, {"kind": "added", "facts": [fact.id]}]

def add_paragraph(project, after_fact, text, fact):
    """A paragraph stating a new fact ({v} its value), after the paragraph printing another's."""
    blocks, i, _, _ = _paragraph(project, after_fact)
    blocks.insert(i + 1, ("p", text.format(v=fact.value)))
    project.facts.append(fact)
    project.edits.append({"kind": "added", "facts": [fact.id]})

def insert_numbered(project, label, first_fact, text, fact):
    """A numbered paragraph ("Condition 1: ...") inserted first among its numbered siblings, which are renumbered
    after it: the new one stating a new fact ({v} its value). Renumbering changes no fact."""
    blocks, i, _, _ = _paragraph(project, first_fact)
    numbered = re.compile(rf"^{re.escape(label)} (\d+):")
    labels = {}
    for k, block in enumerate(blocks):
        m = block[0] == "p" and numbered.match(block[1])
        if m:
            n = int(m.group(1))
            labels[f"{label} {n}"] = f"{label} {n + 1}"
            blocks[k] = ("p", numbered.sub(f"{label} {n + 1}:", block[1]))
    blocks.insert(i, ("p", text.format(v=fact.value)))
    project.facts.append(fact)
    project.edits += [{"kind": "added", "facts": [fact.id]}, {"kind": "renumbered", "labels": labels}]

def insert_message(project, after_fact, sender, receiver, message, fact):
    """A message inserted into a procedure diagram after the one carrying `after_fact`, the steps after it renumbered
    (their messages and values kept): its parameter a new fact."""
    procedure = next(b[1] for _, blocks in project.sections for b in blocks if b[0] == "procedure")
    k = next(i for i, step in enumerate(procedure.steps) if step[3].id == after_fact)
    procedure.steps.insert(k + 1, (sender, receiver, message, fact))
    project.facts.append(fact)
    project.edits += [{"kind": "added", "facts": [fact.id]},
                      {"kind": "renumbered", "labels": {str(n): str(n + 1) for n in range(k + 2, len(procedure.steps))}}]

def reword(project, passages, facts):
    """Passages rewritten without changing what they state (conditions in other words): the facts unchanged."""
    for old, new in passages:
        rewrite(project, old, new)
    project.edits.append({"kind": "reworded", "facts": list(facts)})

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
    p.edits += [{"kind": "removed", "facts": [old.id]},
                {"kind": "changed", "fact": lift.id, "from": lift.value, "to": old.value}]
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
    before = {f.id: f.value for f in p.facts}
    p.facts[:] = sheet_project(plan, p.id).facts
    p.edits += [{"kind": "changed", "fact": f.id, "from": before[f.id], "to": f.value}
                for f in p.facts if f.id in before and before[f.id] != f.value]
    p.edits.append({"kind": "added", "facts": [f.id for f in p.facts if f.id not in before]})

def renamed_later(p, d):
    """Pump P-101B renamed P-201B, its values kept: the same pump under a new tag (alignment by its values)."""
    rename_row(p, "P-101B", "P-201B")

def reordered_later(p, d):
    """Rows reordered, nothing else: a valve moved down its schedule, across the split tables, and a blower up."""
    move_row(p, "V-303", "V-317")
    move_row(p, "B-403", "B-401")

def conditions_later(p, d):
    """Two values kept under new conditions: the filtration rate now with all filters in service, the raw water
    turbidity now a 99th percentile (a change a value comparison alone can't see)."""
    restate(p, "filters.rate", "With one filter out of service, the filtration rate is",
            "With all filters in service, the filtration rate is", "with all filters in service")
    raw = p.fact("plant.raw_turbidity")
    for old in ("(95th percentile)", "the 95th percentile raw water turbidity"):
        if any(old in block[1] for _, blocks in p.sections for block in blocks if block[0] == "p"):
            rewrite(p, old, old.replace("95th", "99th"))
    p.edits.append({"kind": "conditions", "fact": raw.id, "from": raw.conditions, "to": "99th percentile"})
    raw.conditions = "99th percentile"

def split_later(p, d):
    """Pump P-101C replaced by two, P-101E and P-101F, whose capacities sum to its own."""
    split_row(p, "P-101C", ("P-101E", "P-101F"), d, "capacity")

def reworded_later(p, d):
    """Two values' conditions said in other words, meaning the same: the filtration rate with "a single" filter out
    of service, and alum dosed "for an average day" and "for a maximum day" (no change)."""
    reword(p, [("With one filter out of service, the filtration rate is",
                "With a single filter out of service, the filtration rate is"),
               ("mg/L on the average day and up to", "mg/L for an average day and up to"),
               ("mg/L on the maximum day.", "mg/L for a maximum day.")],
           ["filters.rate", "chem.alum", "chem.alum_max"])

def spec_later(p, d):
    """Revision B of the link protocol: values changed beside their look-alikes (the extended short report's field
    beside the short report's, the Session ID's maximum beside the Session ID Length field) and a numbered condition's
    count; the report's members, the conditions and the link states' lead-ins kept word for word."""
    change(p, "ext.field", d.number(14, 40))  # the small field lengths near it are all taken
    for fid in ("hdr.sid", "fail.retx"):
        change(p, fid, near(d, p.fact(fid).value, -0.25, 0.25))

def members_later(p, d):
    """The measurement report's beam index replaced by the battery level, in its place, and the transmit power added
    last: members of one list, each a length in bits, none of them another changed."""
    report = ("Measurement report", ("measurement report", "the report", "report contents"))
    member = lambda fid, what, value: Fact(fid, *report, f"{what} length", (what, f"{what} size", f"{what} field"),
                                           value, "bits")
    ta = p.fact("meas.ta")
    replace_paragraph(p, "meas.beam", "– the battery level, {v} bits;", member("meas.battery", "battery level", d.number(6, 30)))
    rewrite(p, f"the timing advance, {ta.value} bits.", f"the timing advance, {ta.value} bits;")
    add_paragraph(p, "meas.ta", "– the transmit power, {v} bits.", member("meas.power", "transmit power", d.number(6, 30)))

def renumbered_later(p, d):
    """A new first condition for declaring a link failure, the others renumbered after it (2, 3, 4), their values
    kept: a numbered condition's number is its place, not its identity."""
    insert_numbered(p, "Condition", "fail.ack", "Condition 1: the peer reports a fatal error within {v} ms of setup.",
                    Fact("fail.fatal", "Link failure detection",
                         ("link failure", "failure detection", "link failure declaration"), "fatal error window",
                         ("fatal error timeout", "error window"), d.number(1000, 5000), "ms", basis="required"))

def context_later(p, d):
    """The congested state's lead-in now names a lightly loaded link: the two values under it keep their sentence
    word for word, but their conditions changed (a quote alike in both revisions, its meaning not)."""
    rewrite(p, "When the link is congested, the following values apply.",
            "When the link is lightly loaded, the following values apply.")
    for fid in ("timer.congested", "window.congested"):
        fact = p.fact(fid)
        p.edits.append({"kind": "conditions", "fact": fid, "from": fact.conditions, "to": "link lightly loaded"})
        fact.conditions = "link lightly loaded"

def attach_later(p, d):
    """Revision B of the attach procedure: a Key Challenge inserted after the Key Request, the 15 steps after it
    renumbered; the lookup timeout (before the insertion) and the setup timer (after it, so renumbered too)
    revised."""
    for fid in ("msg5.timeout", "msg16.timer"):
        change(p, fid, near(d, p.fact(fid).value))
    insert_message(p, "msg9.length", 1, 0, "Key Challenge",
                   Fact("challenge.timeout", "Key Challenge", ("key challenge", "Key Challenge message"),
                        "response timeout", ("timeout", "challenge timeout"), d.number(100, 900), "ms",
                        basis="required", drawn="figure"))

# base maker, its knob (None: the clean corpus), the edit, whether the generated document is the earlier one, and
# the revision's name (the first revision of a base is "revised"; its pair is named after the base)
PAIRS = ((PROJECTS["wtp"], None, wtp_later, False, "revised"),
         (PROJECTS["coaster"], None, coaster_earlier, True, "earlier"),
         (TABLE_PROJECTS["wtp-tables"], "clean", wtp_tables_later, False, "revised"),
         (PROSE_PROJECTS["lcc"], "traps", lcc_later, False, "revised"),
         (CHART_PROJECTS["lcc-energy"], "clean", energy_later, False, "revised"),
         (SHEET_PROJECTS["lcc-plan"], "clean", plan_later, False, "revised"),
         # knobs for alignment (the revision comparison plan, design item 7)
         (TABLE_PROJECTS["wtp-tables"], "clean", renamed_later, False, "renamed"),
         (TABLE_PROJECTS["wtp-tables"], "clean", reordered_later, False, "reordered"),
         (PROJECTS["wtp"], None, conditions_later, False, "conditions"),
         (TABLE_PROJECTS["wtp-tables"], "clean", split_later, False, "split"),
         # knobs from the "why different" pass's misses (the revision comparison plan, milestone 4)
         (PROJECTS["wtp"], None, reworded_later, False, "reworded"),
         (PROJECTS["spec"], None, spec_later, False, "revised"),
         (PROJECTS["spec"], None, members_later, False, "members"),
         (PROJECTS["spec"], None, renumbered_later, False, "renumbered"),
         (PROJECTS["spec"], None, context_later, False, "context"),
         # a claim-heavy diagram (the adapters plan, "Pictures in Word documents")
         (PROCEDURE_PROJECTS["attach"], "clean", attach_later, False, "revised"))

def _base(make, knob, seed):
    p = make(seed)
    if knob:
        p.id, p.knob = f"{p.id}-{knob}", knob
    return p

def pairs(seed=1):
    """Each pair's documents, by id (nothing generated)."""
    out = []
    for make, knob, edit, earlier, name in PAIRS:
        base = _base(make, knob, seed).id
        mine = f"{base}-{name}"
        out.append(Pair(base if name in ("revised", "earlier") else mine, *((mine, base) if earlier else (base, mine))))
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
    names |= {w for e in project.edits if e["kind"] == "conditions" for w in e["to"].split()}  # "99th percentile"
    names |= {w for e in project.edits if e["kind"] == "renumbered" for label in e["labels"].values()
              for w in label.split()}  # "Condition 4"
    stray = structure(after) - structure(before) - names - {str(p["page"]) for p in after}
    if stray:
        raise ValueError(f"{project.id}: numbers printed that are neither the base's nor facts: {sorted(stray)}")

def revised(seed=1, only=None):
    """[(Pair, the generated project)]: each pair's generated document (or only those of the pairs named), checked
    against its base."""
    out = []
    for (make, knob, edit, _, _), pair in zip(PAIRS, pairs(seed)):
        if only is not None and pair.id not in only:
            continue
        project = _base(make, knob, seed)
        edit(project, drawer(project))
        project.revision_of = project.id
        project.id = pair.earlier if pair.later == project.id else pair.later
        check(_base(make, knob, seed), project)
        out.append((pair, project))
    return out
