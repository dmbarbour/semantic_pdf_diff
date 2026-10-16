"""Each fact's context in the key, by kind (docs/plans/claim-context-2026-10-14.md, milestone 2; Measurement, layer 2).

A fact's `conditions` stay as they were (the scorer's "conditions kept" and the comparisons read them); its
`context` says what kind each part is, where the document gives it, and what the page leaves unknowable:

- **By kind:** scope (when the value holds), frame (how it's read), subject (what it's about), provenance (where it
  was recorded), bound (a limit: "maximum", part of the value), and sibling (another property of the subject given
  as a condition: a revision row's description beside its date). The conditions the generator writes are a closed
  set, each classed below; the frames and scopes a document declares once (a lead-in, a sheet's general notes) are
  added for the facts they reach, though the generator never wrote them as conditions.
- **Sources:** where the document gives a fact's context: the heading it sits under, a lead-in before it, a list
  label, the label printed beside its value (a row's tag and a column's header), a caption, a note.
- **Knowability:** `named_by` when a fact's name rests on a convention the page doesn't print (the plan's room widths
  and depths: no north arrow).

The surveys of what each family prints (2026-10-14) found the generator knows all of this; nothing was kept per fact.
"""
import re

from semantic_pdf_diff.values import printed_value

MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|December")
# Every condition the generator writes, by kind (a new one must be classed here: tests/test_controlled.py checks)
KINDS = [
    (rf"^(?:{MONTHS})$|^(?:cooling )?season$|^year$", "scope"),
    (r"^at (?:design|peak) flow$|^(?:average|maximum) day$|^with (?:all filters in service|one filter out of "
     r"service)$|^link (?:congested|idle|lightly loaded)$|^guide mode$|^chilled beam design$|^runout point$",
     "scope"),
    (r"^3-second gust$|^9[59]th percentile$|^in 95% of monthly samples$", "frame"),
    (r"^(?:maximum|minimum)$", "bound"),
    (r"^Hall C$|^across the four halls$", "subject"),
    (r"^revision [A-Z]$", "provenance"),  # the lift hill as revision A had it: superseded, by the document's account
    # a revision row's description, given as its date's condition: another property of the revision, not context
    (r"^ISSUED FOR (?:PERMIT|REVIEW)$|^REVISED PER COMMENTS$|ENLARGED|WIDENED", "sibling"),
]

def kind_of(conditions):
    """The kind a generated condition is, or None for one not classed yet."""
    return next((kind for pattern, kind in KINDS if re.search(pattern, conditions)), None)

# Frames and scopes a document states once, for the facts they reach: {project family: [(the fact's id pattern, kind,
# what it says, the text that says it)]}. Each applies where its text is printed: a counterfactual revision states
# another (revisions.py: the plan's dimensions to centreline, the coaster's heights above grade)
DECLARED = {
    "lcc-plan": [
        (r"^room\d+\.(?:width|depth)$", "frame", "to face of finish",
         "ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE."),
        (r"^room\d+\.(?:width|depth)$", "frame", "to centerline of stud",
         "ALL DIMENSIONS ARE TO CENTERLINE OF STUD UNLESS NOTED OTHERWISE."),
        (r"^room\d+\.area$", "frame", "net, measured to face of finish",
         "ROOM AREAS ARE NET, MEASURED TO FACE OF FINISH."),
    ],
    "lcc-plans": [  # the plan sheet's notes on each of the set's sheets; each sheet's hall, from its title block
        (r"^hall[cd]\.room\d+\.(?:width|depth)$", "frame", "to face of finish",
         "ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE."),
        (r"^hall[cd]\.room\d+\.area$", "frame", "net, measured to face of finish",
         "ROOM AREAS ARE NET, MEASURED TO FACE OF FINISH."),
        (r"^hallc\.", "subject", "Hall C", "HALL C"),
        (r"^halld\.", "subject", "Hall D", "HALL D"),
    ],
    "coaster-tables": [
        (r"^E\d\.height$", "frame", "above the station platform",
         "Element heights are above the station platform; speeds are design values at the element's entry."),
        (r"^E\d\.height$", "frame", "above grade",
         "Element heights are above grade; speeds are design values at the element's entry."),
        # the speeds' scope, said in the same lead-in: another column's context, kept out of every other value's
        (r"^(?:E\d|BR\d|C-\d+)\.(?!.*speed)", "sibling", "at the element's entry",
         "speeds are design values at the element's entry."),
    ],
    "wtp-tables": [
        (r"^(?:P|B)-\d+[A-C]?\.(?:capacity|total dynamic head|airflow|discharge pressure)$", "scope", "rated point",
         "The schedules below list the plant's pumps, blowers and valves at their rated points."),
    ],
}
# Names resting on a convention the page doesn't print: {family: [(the fact's id pattern, what it would take)]}
CONVENTIONS = {"lcc-plan": [(r"^room\d+\.(?:width|depth)$", "orientation: no north arrow")],
               "lcc-plans": [(r"^hall[cd]\.room\d+\.(?:width|depth)$", "orientation: no north arrow")]}

def family(project_id):
    """A project's family: its id before the seed ("lcc-plan-s1-rotated": "lcc-plan")."""
    return re.sub(r"-s\d+.*$", "", project_id)

def _value(text, value):
    """Whether text prints value as a number of its own (not "12" inside "120" or "1.25")."""
    return re.search(rf"(?<![\d.,]){re.escape(str(value))}(?![\d]|[.,]\d)", text) is not None

LABEL = re.compile(r"^((?:Condition|Step|Item|Note) \d+|\d+\.)\s*:?\s")

def sources(project):
    """{fact id: {source: text}}: the heading, lead-in, list label, printed label and caption each fact has."""
    by_value = {}
    for f in project.facts:
        if not f.relation:
            by_value.setdefault(printed_value(f.value), []).append(f)
    out = {}
    def note(f, **found):
        mine = out.setdefault(f.id, {})
        for k, v in found.items():
            if v and k not in mine:
                mine[k] = v
    for heading, blocks in project.sections or ():
        lead = ""
        for block in blocks:
            if block[0] == "p":
                text = block[1]
                label = LABEL.match(text)
                for f in (f for fs in by_value.values() for f in fs if _value(text, f.value)):
                    note(f, heading=heading, position=label.group(1).rstrip(".") if label else "",
                         lead=lead if label or lead.endswith(":") or "following" in lead else "")
                if not label:
                    lead = text
            elif block[0] == "table":
                _, caption, header, rows = block
                for row in rows:
                    for c, cell in enumerate(row):
                        for f in by_value.get(printed_value(str(cell)), []):
                            note(f, heading=heading, caption=caption, lead=lead,
                                 label=f"{row[0]} | {header[c]}" if c < len(header) else str(row[0]))
            elif block[0] == "datasheet":
                _, caption, rows = block
                for row in rows:
                    for cell in row[1:]:
                        for f in by_value.get(printed_value(str(cell)), []):
                            note(f, heading=heading, caption=caption, label=str(row[0]))
            elif block[0] == "schedule":
                schedule = block[1]
                for title, _, columns, rows in schedule.sections:
                    for tag, cells in rows:
                        for col in columns:
                            fid = f"{tag}.{col.attribute}"
                            if any(f.id == fid for f in project.facts):
                                header = f"{col.group} > {col.label}" if col.group else col.label
                                note(project.fact(fid), heading=heading, caption=schedule.caption, lead=lead,
                                     label=f"{tag} | {header}", table=title)
    return out

def declared_texts(project):
    """The texts a project prints that may declare context: its paragraphs, and its sheets' notes and the halls
    their title blocks name."""
    texts = {block[1] for _, blocks in project.sections or () for block in blocks if block[0] == "p"}
    return texts | {text for sheet in getattr(project, "sheets", None) or () for text in (*sheet.notes,
                                                                                            f"HALL {sheet.hall}")}

def contexts(project):
    """{fact id: context}: each fact's conditions by kind, what its document declares for it, its sources, and what
    its name rests on; facts with none are left out."""
    fam = family(project.id)
    found = sources(project)
    printed = declared_texts(project)
    out = {}
    for f in project.facts:
        ctx = {}
        if f.conditions:
            ctx[kind_of(f.conditions) or "unclassed"] = f.conditions
        for pattern, kind, says, text in DECLARED.get(fam, ()):
            if re.search(pattern, f.id) and any(text in t for t in printed):  # a paragraph may say more
                ctx[kind] = f"{ctx[kind]}; {says}" if kind in ctx else says
                if kind != "sibling":  # another fact's context, not declared for this one
                    ctx.setdefault("declared", text)
        for pattern, needs in CONVENTIONS.get(fam, ()):
            if re.search(pattern, f.id):
                ctx["named_by"] = needs
        if found.get(f.id):
            ctx["sources"] = found[f.id]
        if ctx:
            out[f.id] = ctx
    return out
