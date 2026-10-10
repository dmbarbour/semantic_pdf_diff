"""The controlled corpus's model: a fact as its key states it (Fact), the seeded values documents are drawn with (Draw),
a project's facts and knobs (Project), and where each fact is printed once a document is rendered (locate). Split
from corpus.py, which the documents' drawers imported for these while it imported them (code review 2026-10-08,
E8: the lab's import cycles).
"""
import functools
import random
import re
from dataclasses import dataclass, field

from semantic_pdf_diff.values import parse_number, printed_value

# Knobs not in "all" (corpus.PROSE_KNOBS), so the documents made before them stay as they were.
ALONE = ("decorated", "landscape")

@dataclass
class Fact:
    id: str
    entity: str                       # as the document names it
    aliases: tuple                    # other fair names for the entity
    attribute: str
    synonyms: tuple                   # other fair names for the attribute
    value: str                        # as printed
    unit: str = ""
    conditions: str = ""
    basis: str = "proposed"           # required, proposed, measured, calculated
    role: str = "fact"                # fact, or distractor (a superseded value, say)
    forms: list = field(default_factory=list)  # where it's printed: [{"form", "page", "box"}]
    drawn: str = ""                   # the form it was drawn in, when fixed ("table" for a schedule's cells)
    tolerance: float = 0.0            # a value read against a chart's axis: how far off still counts (else exact)
    relation: str = ""                # a relational fact (relations.RELATIONS): entity, relation, value (the object)
    object_aliases: tuple = ()        # the object's other names
    accepts: tuple = ()               # other relations that state it fairly

    @property
    def number(self):
        return None if self.relation else _parsed(self.value)

@functools.lru_cache(maxsize=1 << 14)
def _parsed(value):
    """A value's number, parsed once per value: the scorer asks each fact's for every claim (code review 2026-10-08,
    E1). By value, not on the fact: a revision changes a fact's value in place."""
    return parse_number(value)

class Draw:
    """Seeded values, each printed string unique within a document (so a value names one fact)."""
    def __init__(self, seed):
        self.rng, self.used = random.Random(seed), set()

    def number(self, lo, hi, decimals=0):
        for _ in range(1000):
            x = self.rng.uniform(lo, hi)
            text = f"{x:,.{decimals}f}" if decimals else f"{round(x):,}"
            if decimals and text.endswith("0"):
                continue  # no trailing zeros: 1250.5, not 1250.50
            if text not in self.used and parse_number(text) not in {parse_number(u) for u in self.used}:
                self.used.add(text)
                return text
        raise ValueError(f"no unused value in {lo}..{hi}")

    def pick(self, options):
        return self.rng.choice(list(options))

    def slot(self, near, grid):
        """The unused multiple of `grid` nearest to `near` (bars read against an axis, to half its step)."""
        base = round(near / grid)
        for k in sorted(range(-40, 41), key=abs):
            v = (base + k) * grid
            text = f"{v:,g}"
            if v > 0 and text not in self.used:
                self.used.add(text)
                return text
        raise ValueError(f"no unused slot near {near}")

# --- projects ----------------------------------------------------------------------------------

@dataclass
class Project:
    id: str
    title: str
    facts: list
    sections: list    # [(heading, [blocks])]; a block is ("p", text), ("table", caption, header, rows), ("datasheet",
                      # caption, rows: a key-value list, no header) or ("schedule", Schedule)
    knob: str = "clean"  # how schedules are drawn (TABLE_KNOBS), or prose, pages and charts (kinds)
    texts: dict = None   # {name: (plain, trap)} phrasings, filled from values
    values: dict = None
    kinds: tuple = ()    # the knobs a prose, chart or schematic project is drawn under
    things: list = None  # the named parts a schematic shows: [(name, aliases)]
    edits: list = field(default_factory=list)  # a revision's edits from its base (revisions.py), in the key
    revision_of: str = ""                      # the base document's id, for a revision

    def has(self, knob):
        """Whether a prose, layout or chart knob applies: "all" applies every knob of the project's kind but those
        named only alone (ALONE); knobs joined by "+" apply together."""
        return knob in self.kinds and (knob in self.knob.split("+") or self.knob == "all" and knob not in ALONE)

    def fact(self, fact_id):
        return next(f for f in self.facts if f.id == fact_id)

def locate(project, doc, placed=None, drawn=None):
    """Find each fact's printed value on its pages (setting fact.forms), and log every number on the pages with
    its role: fact or distractor (by id), or structure (section, table and page numbers, anything else)."""
    by_value = {}
    for f in project.facts:
        if not f.relation:  # relations are placed by their drawer and their sentences, not found by number
            by_value.setdefault(printed_value(f.value), []).append(f)
        f.forms = []
    log = []
    for n, page in enumerate(doc, 1):
        table_boxes = [t.bbox for t in page.find_tables().tables] + list((placed or {}).get(n, []))
        chart_boxes = []
        for box, bars, numbers, form in (drawn or {}).get(n, []):  # figures: placed and logged as drawn
            if box is not None:
                chart_boxes.append(box)
            for fact, bar in bars:
                fact.forms.append({"form": form, "page": n, "box": [round(v, 1) for v in bar]})
            for text, facts, _ in numbers:
                log.append({"text": text, "page": n, "role": facts[0].role if facts else "structure",
                            "facts": [f.id for f in facts]})
        for w in page.get_text("words"):
            if any(b[0] - 1 <= w[0] and w[2] <= b[2] + 1 and b[1] - 1 <= w[1] and w[3] <= b[3] + 1 for b in chart_boxes):
                continue
            text = w[4].strip(",.;:()°")
            number = printed_value(text) if re.search(r"[0-9]", text) else None  # "ft²" is a unit, not a 2
            if number is None:
                continue
            facts = by_value.get(number, []) if re.match(r"[-+±$]?\d", text) else []  # "$15.2M" is printed money
            inside_table = any(b[0] - 1 <= w[0] and w[2] <= b[2] + 1 and b[1] - 1 <= w[1] and w[3] <= b[3] + 1
                               for b in table_boxes)
            for f in facts:
                f.forms.append({"form": f.drawn or ("table" if inside_table else "prose"), "page": n,
                                "box": [round(v, 1) for v in w[:4]]})
            log.append({"text": text, "page": n, "role": facts[0].role if facts else "structure",
                        "facts": [f.id for f in facts]})
    missing = [f.id for f in project.facts if not f.forms]
    if missing:
        raise ValueError(f"{project.id}: facts not found on the page: {missing}")
    return log
