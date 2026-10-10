"""Tables read by rules a model writes (docs/plans/multi-format-adapters-2026-09-23.md, "Excel, in detail", step 5;
docs/plans/one-table-model-2026-09-30.md, item 4): one query per table, whatever its length, rather than one a row.

The owner (2026-10-04): "ask a model how to handle the table. We should give the model the headers and samples of the
rows, report number of claims and our own heuristic opinion (summary vs. point per claim) based on size and a short
analysis of rows (whether they're mostly text, numbers, etc..), then ask the model how to handle it, i.e. whether how
to produce claims from rows or how to summarize things within a few known templates."

- **What the model is shown** (question): the table's place and title, and the context a row would be given (the
  text above the table, its headings); each column's header and a mechanical analysis of its cells (analyse:
  numbers, dates, text and empty cells counted, distinct values, the range, an order and an even step, prose);
  sample rows (the first, some from the middle and the end, and rows unlike the rest); the table's size and the
  claims a point per value cell would give; and our heuristic opinion (opinion), labelled a guess, a summary weighed
  by size without a cut-off.
- **What it answers** (Rules), one reading:
  - rules: the claims a row gives, as templates of its cells, applied to every row mechanically (row_claims)
  - rows: each row read by itself, as a table's rows are without rules
  - summary: a known template (series, log, list) over named columns, its statistics computed (summarise)
- **Binding** (2026-10-05, measured on the controlled workbooks): the prompt says how a claim is bound, as in any
  extraction (the attribute the property measured, never an option's or a series' name; the entity the thing with
  the value, an item or an alternative compared; conditions the circumstances, never the document's own details;
  columns that are alternatives of one quantity name the entity), with three worked examples from outside the
  controlled corpus (alternatives as columns, operating points, a table turned sideways: one to four were measured
  on two seeds of the corpus, three read best), and the model first writes what the values measure, what has them
  and under what ("binding", kept in the coverage record). A circumstance every row shares stays a condition, a vague
  setting doesn't (the owner, 2026-10-05: "Trying to avoid vague conditions"; "never a setting every value shares"
  was tried first, and lost real conditions that a table's lead-in names).
- **Checked** (problems): the templates must give the model's own example claims for the rows it chose (values and
  units); a value marked a number must be one; a summary's columns must exist and hold what its template needs. A row
  the templates don't fit is read by itself. An answer with problems, or rules failing a fifth of the rows, is asked
  for once more, the problems shown; failing again, every row is read by itself.
- **Claims made mechanically** quote the cells they came from, and their derivation names the rules ("table-rules")
  or the template ("table-summary"; a mean or a count is computed, its quote the column's header).
"""
import datetime
import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field, replace

from pydantic import Field, field_validator

from .schema import DerivationStep, Evidence, Lenient, claim_id, coverage_row

SAMPLE_FIRST, SAMPLE_MIDDLE, SAMPLE_LAST, SAMPLE_ODD = 5, 3, 2, 3  # the sample rows shown
SHOWN_CELL = 120    # characters of a sample cell shown
LONG_TEXT = 60      # a column of text averaging this many characters is prose
SENTENCE = 6        # or this many words: sentences (requirements, titles), whose claims are in their words
FEW_ROWS, MANY_ROWS = 20, 100  # our opinion of a summary: graded, weak under FEW_ROWS, strong from MANY_ROWS
CATEGORIES = 12     # a category's values counted one by one; the rest counted together
RETRY_SHARE = 0.2   # rules failing more of the rows than this are asked for again
CONFIDENCE = 0.9    # a claim made by rules: as sure as the rules

NUMBER = re.compile(r"^[-+−]?[$€£¥]?(?=\.?\d)(?:\d{1,3}(?:,\d{3})+|\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?%?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?$")
PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
NOT_APPLICABLE = {"n/a", "na", "n.a.", "-", "–", "—", "not applicable"}  # a value cell saying there's no value
BRACKETED = re.compile(r"[(\[]([^()\[\]]{1,24})[)\]]")

RULES = '''This is one table from an engineering document. Decide how its rows become claims: atomic facts a reader
might rely on (entity, attribute, value, unit, conditions), as an extraction of the table would give them. Choose one
reading:
- "rules": every row gives its claims the same way. Write the claims a row gives as templates; they're applied to
  every row mechanically. Placeholders: {B} the row's cell in column B; {B.header} column B's header; {B.name} the
  header's own name without its unit; {B.group} the group a header sits under ("Pressure" for
  "Pressure (bar) > Inlet": the group may be the attribute and the header's own name a condition, or the
  group a category and the name the attribute); {B.unit} the unit in the header's brackets ("Flow (L/s)" gives L/s); {B.cell_name} and
  {B.cell_unit} split the row's own cell the same way (a row label "Capital cost ($M)" gives Capital cost and $M);
  {section} the section row above the row; {title} the table's title; {subject} your subject. A template with
  "columns": "C:F" is applied to each of those columns in turn, {*} standing for the column's cell ({*.header},
  {*.name} and {*.unit} likewise). Set "number": true when the value must be a number: a row whose cell isn't one is
  read by itself instead. An empty value, or n/a, gives no claim. A value is a cell's own value (a number, a name, a
  short code), never a sentence. A column of tolerances or uncertainties beside a value's ("±", "tol.") gives no
  claims of its own: write it into that value's template as "uncertainty" ("± {D} {C.unit}"). Columns that only keep
  the document's own records (who submitted a row and their ID, when it was entered or reserved, a sort order) give
  no claims: leave them out. A condition the text around the table names for every row (a load case, a date,
  a state) belongs in the templates' conditions. Write out the claims two or three of the rows shown give (no
  placeholders) as examples: they check the templates.
- "rows": the cells need reading: sentences (a requirement, a note, a description: their claims are in their words),
  several values in one cell, rows unlike each other. Each row is read by itself.
- "summary": the rows are samples of the same few quantities, and what matters is their overall shape, not each
  row. Name a template and its columns; its statistics are computed from every row:
  - "series": quantities against an input (a polar, a curve, a sweep): "input" the input's column, "quantities"
    theirs, "points" a few input values (as shown) that matter on their own, such as zero or a design point, at
    which each quantity is reported too (none if none does). Gives the input's range and step, and each quantity's
    minimum and maximum and where they fall.
  - "log": quantities sampled over time: "input" the time's column, "quantities" theirs. Gives the span and count,
    and each quantity's minimum, maximum, mean and last value.
  - "list": many records of one kind (a register, a document list): "categories" the columns to count rows by. Gives
    the count, and the counts by each category's values.
  Don't summarise rows that are each a fact someone would check on its own (requirements, design values, schedules).
"subject" names what the table describes: a summary's entity.
How a claim is bound, as in any extraction:
- the attribute names the property a value measures (cooling energy, peak load, flow), never an option's or a
  series' name
- the entity is the thing that has the value: an item (a pump, a zone) or an alternative being compared (a design
  option, a unit size); never a parameter's name
- conditions are the circumstances the value holds under (a month, an operating point, a load case, a location),
  never the document's own details (its revision, its date of issue); a circumstance every row shares (a load case,
  a state named before the table) is a condition, but a vague setting ("in the plant", "in the process") isn't, nor
  is the heading or slide title the table sits under (what it's about, not a circumstance)
- when the columns are alternatives or series of one quantity (Option 1, Option 2), each column names the entity
  or a condition, the quantity is the attribute (from the title, the caption or the text above), and the row's
  label (a month, a case) is a condition
For example:
- a table "Annual heating demand" with columns Year | Design A (MWh) | Design B (MWh): one template over columns
  B:C, entity {*.name}, attribute "heating demand", value {*}, unit {*.unit}, conditions {A}
- a table "Rotor performance" with columns Wind speed (m/s) | Power (kW) | Thrust (kN): one template over columns
  B:C, entity {subject} (the rotor), attribute {*.name}, value {*}, unit {*.unit}, conditions "at wind speed {A} m/s"
- a table "Motor options" with row labels such as "Rated power (kW)" and columns Motor A | Motor B: one template
  over columns B:C, entity {*.header}, attribute {A.cell_name}, value {*}, unit {A.cell_unit}
Return JSON:
{"binding":"what the values measure (the attribute), what has them (the entity), under what (the conditions)", "reading":"rules|rows|summary", "why":"one sentence", "subject":"...",
"claims":[{"columns":"", "entity":"...", "attribute":"...", "value":"...", "unit":"...", "conditions":"...", "uncertainty":"", "number":true}],
"examples":[{"row":"5", "claims":[{"entity":"...", "attribute":"...", "value":"...", "unit":"...", "conditions":"..."}]}],
"template":"series|log|list", "input":"A", "quantities":["B"], "categories":["C"], "points":["0"]}
Leave out what your reading doesn't use.
'''

# --- the table as the rules see it

@dataclass
class Grid:
    """A table as its rules see it: columns named by letter, each with its header label; body rows aligned to the
    columns, each named (a sheet's row number), placed (its line in the document), with its section (a section row's
    label above it, or "") and its index among the table's body rows (keys, for reading it by itself); the table's
    title and place ("Polar!A3:C334")."""
    columns: list
    labels: list
    rows: list = field(default_factory=list)
    names: list = field(default_factory=list)
    lines: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    keys: list = field(default_factory=list)
    title: str = ""
    place: str = ""
    boxes: list = field(default_factory=list)  # each row's box on its page (a PDF's), where rows aren't lines
    section_rows: list = field(default_factory=list)  # [SectionRow], in order
    joined: set = field(default_factory=set)  # keys of rows joined from several lines (a PDF's wrapped cells)

@dataclass
class SectionRow:
    """A row holding only its first cell: a label for the rows below it, from row `at` of the grid on (or a note
    stating facts, which possible_notes proposes and the model confirms). key: as Grid.keys; name, line, box: as a
    row's."""
    key: int
    text: str
    name: str
    line: int
    box: tuple | None
    at: int

def possible_notes(g):
    """Section rows holding a number: possibly notes stating facts ("Note: P-2 is rated 95 L/s ..."), not labels.
    Our proposal; the rules query asks the model which are (code review 2026-10-08, B2: a note was a label, its facts
    never read, the rows below filed under it)."""
    return [r for r in g.section_rows if re.search(r"\d", r.text)]

def noted(g, names):
    """(the grid with the possible notes named (by row) as notes labelling nothing, those notes): the rows below a
    note take the section above it."""
    names = {str(n).strip() for n in names or ()}
    notes = [r for r in possible_notes(g) if r.name in names]
    if not notes:
        return g, []
    labels = [r for r in g.section_rows if r not in notes]
    sections = [next((r.text for r in reversed(labels) if r.at <= i), "") for i in range(len(g.rows))]
    return replace(g, sections=sections), notes

def grid(columns, labels, rows, names, lines, title="", place="", boxes=None):
    """A Grid from a table's body rows (aligned to its columns). A row holding only its first cell, in a table of
    three columns or more, is a section row, labelling the rows below it; an empty row is left out."""
    g, section = Grid(list(columns), list(labels), title=title, place=place), ""
    boxes = boxes or [None] * len(rows)
    for key, (row, name, line, box) in enumerate(zip(rows, names, lines, boxes)):
        row = [row[k] if k < len(row) else "" for k in range(len(columns))]
        filled = [k for k, text in enumerate(row) if text]
        if len(columns) > 2 and filled == [0]:
            section = row[0]
            g.section_rows.append(SectionRow(key, row[0], str(name), line, box, len(g.rows)))
        elif filled:
            g.rows.append(row)
            g.names.append(str(name))
            g.lines.append(line)
            g.sections.append(section)
            g.keys.append(key)
            if box is not None:
                g.boxes.append(box)
    return g

def letter(column):
    """A column's letter as a spreadsheet names it, from 1 ("A", ..., "Z", "AA")."""
    out = ""
    while column:
        column, rest = divmod(column - 1, 26)
        out = chr(65 + rest) + out
    return out

def from_cells(rows, heads, labels, lines, title="", place=""):
    """A Grid from a reader's table grid (Word's, a deck's: [(row, [Cell])], each cell with its first and last
    column and its text), its header rows' count, its column labels and its body rows' lines; columns named A, B, ...
    and rows by their number within the table."""
    width = max([len(labels)] + [c.last + 1 for _, cells in rows for c in cells])
    aligned = []
    for _, cells in rows[heads:]:
        aligned.append([""] * width)
        for c in cells:
            aligned[-1][c.first] = c.text
    return grid([letter(k) for k in range(1, width + 1)], list(labels) + [""] * (width - len(labels)), aligned,
                [str(k) for k in range(heads + 1, len(rows) + 1)], lines, title, place)

def number(text):
    """A cell's number as shown ("1,750", "12.5%", "$1,200", "−3"), or None."""
    if not NUMBER.match(text):
        return None
    return float(re.sub(r"[,$€£¥%]", "", text).replace("−", "-"))

def moment(text):
    """A date or date and time as shown, or None."""
    try:
        return datetime.datetime.fromisoformat(text) if DATE.match(text) else None
    except ValueError:
        return None

def kind(text):
    return "empty" if not text else "number" if NUMBER.match(text) else "date" if DATE.match(text) else "text"

def header_unit(label):
    """The unit in a header's last brackets ("Flow (L/s)" → "L/s", "alpha [deg]" → "deg"), or ""."""
    found = BRACKETED.findall(label)
    return found[-1].strip() if found else ""

def header_name(label):
    """A header's own name: the last part of its path, without its unit's brackets ("Hydraulics > Capacity (gpm)" →
    "Capacity"; the group stays in {B.header})."""
    label = label.rsplit(" > ", 1)[-1]
    found = list(BRACKETED.finditer(label))
    if found:
        label = label[:found[-1].start()] + label[found[-1].end():]
    return " ".join(label.split()).strip(" ,;:")

def _shown(value):
    return format(value, ".10g")

# --- the analysis and our opinion

@dataclass
class Column:
    """What a column's cells hold, counted mechanically."""
    letter: str
    label: str
    numbers: int = 0
    dates: int = 0
    texts: int = 0
    empty: int = 0
    distinct: int = 0
    low: str = ""
    high: str = ""
    order: str = ""     # "rising" or "falling", every step
    step: str = ""      # the even step between neighbours ("1", "5 min"), when there is one
    mostly: bool = False  # the step holds for most neighbours, not all
    length: float = 0.0   # the mean characters of its filled cells
    words: float = 0.0    # and words, of its text cells
    common: list = field(default_factory=list)

    @property
    def filled(self):
        return self.numbers + self.dates + self.texts

    @property
    def prose(self):
        return self.texts > self.filled / 2 and (self.length >= LONG_TEXT or self.words >= SENTENCE)

def _step(diffs, unit=""):
    """(the step, whether only mostly) when four fifths of the differences are one value."""
    if not diffs:
        return "", False
    rounded = Counter(round(d, 9) for d in diffs)
    step, count = rounded.most_common(1)[0]
    if count < 0.8 * len(diffs) or step == 0:
        return "", False
    return _shown(abs(step)) + unit, count < len(diffs)

def analyse(g):
    """Each column's Column."""
    out = []
    for k, letter in enumerate(g.columns):
        c = Column(letter, g.labels[k] if k < len(g.labels) else "")
        cells = [row[k] for row in g.rows]
        filled = [t for t in cells if t]
        counted = Counter(kind(text) for text in cells)
        c.numbers, c.dates, c.texts, c.empty = (counted[k] for k in ("number", "date", "text", "empty"))
        c.distinct = len(set(filled))
        c.length = sum(map(len, filled)) / len(filled) if filled else 0.0
        texts = [t for t in filled if kind(t) == "text"]
        c.words = sum(len(t.split()) for t in texts) / len(texts) if texts else 0.0
        values = []
        if filled and c.numbers == len(filled):
            values = [(number(t), t) for t in filled]
            diffs, unit = [b[0] - a[0] for a, b in zip(values, values[1:])], ""
        elif filled and c.dates == len(filled) and all(moment(t) for t in filled):
            values = [(moment(t), t) for t in filled]
            diffs = [(b[0] - a[0]).total_seconds() for a, b in zip(values, values[1:])]
            seconds = Counter(round(d) for d in diffs).most_common(1)[0][0] if diffs else 0
            scale = next(((s, u) for s, u in ((86400, " d"), (3600, " h"), (60, " min")) if seconds and seconds % s == 0),
                         (1, " s"))
            diffs, unit = [d / scale[0] for d in diffs], scale[1]
        if values:
            c.low, c.high = min(values)[1], max(values)[1]
            if diffs and all(d > 0 for d in diffs):
                c.order = "rising"
            elif diffs and all(d < 0 for d in diffs):
                c.order = "falling"
            c.step, c.mostly = _step(diffs, unit) if len(values) > 2 else ("", False)
        if c.texts:
            c.common = Counter(t for t in filled if kind(t) == "text").most_common(3)
        out.append(c)
    return out

def describe(c):
    """A column's line: "B: Flow (L/s): numbers 330; 85.2 to 118; rising; steps of 0.5"."""
    counts = ", ".join(f"{name} {n}" for name, n in (("numbers", c.numbers), ("dates", c.dates), ("text", c.texts),
                                                    ("empty", c.empty)) if n)
    notes = []
    if c.low:
        notes.append(f"{c.low} to {c.high}" if c.low != c.high else f"all {c.low}")
    if c.order:
        notes.append(c.order)
    if c.step:
        notes.append(f"{'mostly ' if c.mostly else ''}in steps of {c.step}")
    if c.filled > 1:
        notes.append("all distinct" if c.distinct == c.filled else f"{c.distinct} distinct")
    if c.texts and c.distinct < c.filled:
        notes.append("most common " + ", ".join(f'"{t[:40]}" ×{n}' for t, n in c.common))
    if c.prose:
        notes.append(f"prose: {round(c.words)} words, {round(c.length)} characters on average")
    return f"{c.letter}: {c.label or '(no header)'}: {counts}" + ("; " + "; ".join(notes) if notes else "")

def point_claims(g, cols):
    """The claims a point per value cell would give: the filled cells past the row-label column."""
    return sum(c.filled for c in cols[1:]) if len(cols) > 1 else sum(c.filled for c in cols)

def opinion(g, cols):
    """Our heuristic opinion of how the table should be read, from its size and the analysis. A summary is weighed
    by size, graded rather than cut off (the owner, 2026-10-05: "stats might be the more useful view even for tables
    of 30 items, it's difficult to set a hard boundary")."""
    n, claims = len(g.rows), point_claims(g, cols)
    filled = sum(c.filled for c in cols) or 1
    measured = sum(c.numbers + c.dates for c in cols)
    prose = [c for c in cols if c.prose]
    inputs = [c for c in cols if c.order]
    categories = [c for c in cols if c.texts and 1 < c.distinct <= CATEGORIES and c.distinct < c.filled]
    per = f"{claims / n:.1f}".rstrip("0").rstrip(".") if n else "0"
    by = ", ".join(c.letter for c in categories)
    text = sum(c.length * c.filled for c in cols) or 1  # prose decides the reading where it's much of the table's text
    worded = sum(c.length * c.filled for c in prose) / text
    if prose and worded >= 0.3:
        return (f"rows of prose (column {prose[0].letter}: {round(prose[0].words)} words on average): each row read by "
                "itself" + (f"; or, if the records matter only together, a summary (list) counting them by column {by}"
                            if n >= FEW_ROWS and categories else ""))
    aside = (f"; column {prose[0].letter} holds prose ({round(prose[0].words)} words on average): rows read by "
             "themselves if its words hold claims") if prose else ""
    shape = None
    if inputs and measured >= 0.8 * filled:
        x = inputs[0]
        shape = ("log" if x.dates else "series", "log" if x.dates else "series",
                 f"mostly numbers, column {x.letter} {x.order}"
                 + (f" {'mostly ' if x.mostly else ''}in steps of {x.step}" if x.step else ""))
    elif measured >= 0.8 * filled and n > 2 and len(cols) > 1:
        shape = ("set of points", "series", "mostly numbers, no column in order: a shape's coordinates, samples?")
    elif categories and measured < 0.5 * filled:  # records of text, sorted into a few kinds
        shape = ("list", "list", f"records that column {by} sorts into a few kinds")
    if shape is None:
        return f"claims from rows by rules: about {claims} claims, {per} a row" + aside
    name, template, why = shape
    if n >= MANY_ROWS:
        return f"a {name} ({why}): a summary ({template}) may serve better than {claims} claims" + aside
    if n >= FEW_ROWS:
        return (f"a {name} ({why}): a summary ({template}) or claims from rows by rules (about {claims}): a summary if "
                "the rows are samples rather than facts each worth checking" + aside)
    return (f"claims from rows by rules: about {claims} claims, {per} a row (a {name}, {why}; with {n} rows a summary "
            "would save little)" + aside)

def samples(g):
    """The rows shown: the first, some from the middle and the end, and rows unlike the rest (a pattern of cell
    kinds few rows share)."""
    n = len(g.rows)
    picked = set(range(min(SAMPLE_FIRST, n))) | {n * (k + 1) // (SAMPLE_MIDDLE + 1) for k in range(SAMPLE_MIDDLE)}
    picked |= set(range(max(0, n - SAMPLE_LAST), n))
    pattern = lambda row: tuple(kind(t) for t in row)
    seen = Counter(pattern(row) for row in g.rows)
    odd = [i for i, row in enumerate(g.rows) if i not in picked and seen[pattern(row)] <= max(1, n // 50)]
    return sorted(i for i in picked | set(odd[:SAMPLE_ODD]) if 0 <= i < n)

def question(g, cols=None, context=""):
    """The rules query's text; context: the context lines a row of the table is given (its lead-in, its headings)."""
    cols = cols or analyse(g)
    n, claims = len(g.rows), point_claims(g, cols)
    cut = lambda text: (text[:SHOWN_CELL] + "…" if len(text) > SHOWN_CELL else text).replace("|", "/")
    lines = [f"TABLE: {g.place}" + (f"; title: {g.title}" if g.title else "")] + ([context] if context else []) + [
             f"SIZE: {n} rows, {len(cols)} columns; a claim per value cell would give about {claims} claims",
             "COLUMNS (letter: header: what its cells hold):"] + [describe(c) for c in cols]
    if any(g.sections):
        spans = []
        for i, section in enumerate(g.sections):
            if section and (not spans or spans[-1][0] != section):
                spans.append([section, g.names[i], g.names[i]])
            elif section:
                spans[-1][2] = g.names[i]
        lines.append("SECTIONS (section rows label the rows below them): "
                     + "; ".join(f"{s} (rows {a} to {b})" for s, a, b in spans[:20]))
    possible = possible_notes(g)
    if possible:  # only tables that have them are asked (their query alone changes)
        lines.append("POSSIBLE NOTES (section rows holding a number: a note states facts, where a section row only "
                     "names the rows below it): " + "; ".join(f"row {r.name}: {cut(r.text)}" for r in possible[:10])
                     + '. List any that are notes by row in "notes" (e.g. "notes":["' + possible[0].name
                     + '"]): a note is read by itself, and labels no rows.')
    lines += ["SAMPLE ROWS (the row's number, then its cells by column):", "row | " + " | ".join(g.columns)]
    last = -1
    for i in samples(g):
        if i > last + 1:
            lines.append(f"... (rows {g.names[last + 1]} to {g.names[i - 1]} not shown)")
        lines.append(g.names[i] + " | " + " | ".join(cut(t) for t in g.rows[i]))
        last = i
    if last < n - 1:
        lines.append(f"... (rows {g.names[last + 1]} to {g.names[-1]} not shown)")
    lines.append("OUR HEURISTIC OPINION (a guess from the size and the analysis above; decide yourself): "
                 + opinion(g, cols))
    return RULES + "\n" + "\n".join(lines)

# --- the answer

class RuleClaim(Lenient):
    columns: str = Field(default="", max_length=60)
    entity: str = Field(default="", max_length=200)
    attribute: str = Field(default="", max_length=200)
    value: str = Field(default="", max_length=200)
    unit: str = Field(default="", max_length=80)
    conditions: str = Field(default="", max_length=300)
    uncertainty: str = Field(default="", max_length=120)  # "± {D} {C.unit}": a tolerance column, the value's
    number: bool = False

class Written(Lenient):
    entity: str = Field(default="", max_length=200)
    attribute: str = Field(default="", max_length=200)
    value: str = Field(default="", max_length=300)
    unit: str = Field(default="", max_length=80)
    conditions: str = Field(default="", max_length=300)

    @field_validator("entity", "attribute", "value", "unit", "conditions", mode="before")
    @classmethod
    def _text(cls, value):
        return value if isinstance(value, str) else str(value)

class Example(Lenient):
    row: str = Field(default="", max_length=20)
    claims: list[Written] = Field(default_factory=list, max_length=60)

    @field_validator("row", mode="before")
    @classmethod
    def _text(cls, value):
        return value if isinstance(value, str) else str(value)

class Transcribed(Lenient):
    """A row copied from the table's image (a PDF's), to check its text layer."""
    row: str = Field(default="", max_length=20)
    cells: list[str] = Field(default_factory=list, max_length=60)

    @field_validator("row", mode="before")
    @classmethod
    def _text(cls, value):
        return value if isinstance(value, str) else str(value)

    @field_validator("cells", mode="before")
    @classmethod
    def _texts(cls, value):
        return [v if isinstance(v, str) else str(v) for v in value] if isinstance(value, list) else value

class Rules(Lenient):
    """A model's answer to the rules query (RULES)."""
    transcribed: Transcribed | None = None  # with a table's image: one row of values copied from it
    binding: str = Field(default="", max_length=400)  # what the values measure, what has them, under what
    reading: str = Field(default="", max_length=20)
    why: str = Field(default="", max_length=400)
    subject: str = Field(default="", max_length=160)
    claims: list[RuleClaim] = Field(default_factory=list, max_length=60)
    examples: list[Example] = Field(default_factory=list, max_length=6)
    template: str = Field(default="", max_length=20)
    input: str = Field(default="", max_length=10)
    quantities: list[str] = Field(default_factory=list, max_length=40)
    categories: list[str] = Field(default_factory=list, max_length=10)
    points: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=20)  # rows of POSSIBLE NOTES that are notes

    @field_validator("quantities", "categories", "points", "notes", mode="before")
    @classmethod
    def _texts(cls, value):
        return [v if isinstance(v, str) else str(v) for v in value] if isinstance(value, list) else value

REVIEWING = '''You wrote the rules below for a table. Here is what they give for some of its rows, applied mechanically.
Check each claim against its row as a careful reader would: is the value the row's own; does the attribute name what
the value measures; is the entity what has it; are the conditions the circumstances it holds under (nothing vague,
nothing missing that the row or the text around the table states)? If every claim is right, answer
{"verdict":"keep"}. If not, say what's wrong and give corrected rules, the same JSON as before:
{"verdict":"revise", "problems":["..."], "rules":{...}}.
'''

class Review(Lenient):
    """A model's review of what its rules gave (REVIEWING)."""
    verdict: str = Field(default="", max_length=20)
    problems: list[str] = Field(default_factory=list, max_length=10)
    rules: Rules | None = None

REVIEW = None  # None: the table_review setting decides; an int (or True, one review): an experiment's override

def review_question(asked, answer, g):
    """The review query: the table as shown, the rules, and what they gave for three rows (or a summary's claims)."""
    table = asked[asked.index("TABLE: "):asked.index("OUR HEURISTIC OPINION")] if "TABLE: " in asked else ""
    lines = [REVIEWING, "THE TABLE (as you were shown it):", table.rstrip(), "YOUR RULES:",
             answer.model_dump_json(exclude_defaults=True), "WHAT THEY GAVE:"]
    show = lambda f: f"  {f['entity']} | {f['attribute']} | {f['value']} {f['unit']}".rstrip() + \
        (f" | {f['conditions']}" if f["conditions"] else "")
    if answer.reading.strip().lower() == "summary":
        lines += [show(stat.fields) for stat in summarise(answer, g)[:30]]
    else:
        n = len(g.rows)
        for i in sorted({0, n // 2, n - 1}):
            lines.append(f"row {g.names[i]}: " + " | ".join(g.rows[i]))
            try:
                lines += [show(f) for f, _, _ in row_claims(answer, g, i)] or ["  (no claims)"]
            except (Misfit, Broken) as error:
                lines.append(f"  (read by itself: {error})")
    return "\n".join(lines)

IMAGED = """THE TABLE'S IMAGE is attached. The cells above are its text layer, which can be wrong (a symbol lost, a
cell split or joined). Also copy the cells of one sample row from the image as you read them there: a row of values
(a number in it), not a header line, by its number above, empty cells left out:
"transcribed": {"row": "<its number>", "cells": ["...", "..."]}.
"""

def _plain(text):
    import unicodedata
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return "".join(ch for ch in text if ch.isalnum() or ch in ".-+%/")

def transcription_mismatch(answer, g):
    """What a row copied from the image says against the text layer's cells: "" when they agree (folded for case,
    spaces, commas and dash and quote forms), when no row was copied, or when the row holds no value (no digit)."""
    t = answer.transcribed
    if t is None or not t.cells:
        return ""
    name = t.row.strip()
    name = name[4:].strip() if name.lower().startswith("row ") else name
    if name not in g.names:
        return f"the copied row {t.row!r} isn't a row of the table"
    layer = [c for c in g.rows[g.names.index(name)] if c]
    if not any(ch.isdigit() for c in layer for ch in str(c)):  # not a row of values (a lone header cell parsed as a
        return ""  # table of its own: "Raw | water | pumps"): nothing the claims rest on to check
    seen = [c for c in t.cells if str(c).strip()]
    if [_plain(c) for c in layer] != [_plain(c) for c in seen]:
        return (f"row {name}: the text layer reads {' | '.join(layer)[:150]}, the image "
                f"{' | '.join(seen)[:150]}")
    return ""

# --- applying rules

class Misfit(ValueError):
    """A row the rules don't fit (a value that isn't a number, an empty entity)."""

class Broken(ValueError):
    """Rules that can't be applied to any row (an unknown column or placeholder)."""

def _index(g, letter):
    letter = letter.strip().upper()
    if letter not in g.columns:
        raise Broken(f"no column {letter} in the table")
    return g.columns.index(letter)

def _columns(g, spec):
    """Column indices named "C:F", "C, E" or "C:E, H"."""
    out = []
    for part in re.split(r"[,;]\s*", spec.strip()):
        if not part:
            continue
        a, _, b = part.partition(":")
        first, last = _index(g, a), _index(g, b) if b else _index(g, a)
        out += list(range(min(first, last), max(first, last) + 1))
    return out

def _fill(template, g, i, star=None, subject=""):
    """(a template filled for row i, the columns whose cells it used)."""
    used = []

    def one(match):
        ref = match.group(1).strip()
        name, _, part = ref.partition(".")
        if not part and name in ("section", "title", "subject"):
            return {"section": g.sections[i], "title": g.title, "subject": subject}[name]
        if name == "*":
            if star is None:
                raise Broken("{*} in a template without columns")
            k = star
        else:
            k = _index(g, name)
        if not part or part in ("value", "cell", "text", "cell_value", "cell_text"):  # the cell, however it's named
            used.append(k)
            return g.rows[i][k]
        if part in ("cell_name", "cell_unit"):
            used.append(k)
            return header_name(g.rows[i][k]) if part == "cell_name" else header_unit(g.rows[i][k])
        label = g.labels[k] if k < len(g.labels) else ""
        if part not in ("header", "name", "unit", "group"):
            raise Broken(f"unknown placeholder {{{ref}}}")
        if part == "group":  # the header's group above its own name ("Stroke time" for "Stroke time (s) > Open")
            return header_name(label.rsplit(" > ", 1)[0]) if " > " in label else ""
        return label if part == "header" else header_name(label) if part == "name" else header_unit(label)

    return " ".join(PLACEHOLDER.sub(one, template).split()), used

def row_claims(rules, g, i):
    """[(claim fields, the columns its cells came from, its rule)] that the rules give row i; raises Misfit or
    Broken."""
    out = []
    for rule in rules.claims:
        for star in (_columns(g, rule.columns) if rule.columns.strip() else [None]):
            value, used = _fill(rule.value, g, i, star, rules.subject)
            if not value or value.casefold() in NOT_APPLICABLE:
                continue  # an empty cell gives no claim, nor one saying there's no value
            column = g.columns[used[0]] if used else "?"
            if rule.number and number(value) is None:
                raise Misfit(f"{column}{g.names[i]} isn't a number: {value[:40]!r}")
            fields = {"value": value}
            for name in ("entity", "attribute", "unit", "conditions", "uncertainty"):
                fields[name], more = _fill(getattr(rule, name), g, i, star, rules.subject)
                used += more
                if name in ("unit", "conditions", "uncertainty") and PLACEHOLDER.search(getattr(rule, name)) and \
                        all(not _fill("{" + ref + "}", g, i, star, rules.subject)[0]
                            for ref in PLACEHOLDER.findall(getattr(rule, name))):
                    fields[name] = ""  # its placeholders all empty: no stray words ("in" from "in {title}")
            if any(ch.isdigit() for ch in fields["uncertainty"]) is False or \
                    fields["uncertainty"].strip(" ±+-").casefold() in NOT_APPLICABLE:
                fields["uncertainty"] = ""  # "±" alone, or "± n/a": no uncertainty stated
            if not fields["entity"] or not fields["attribute"]:
                raise Misfit(f"row {g.names[i]} gives a claim with no {'entity' if not fields['entity'] else 'attribute'}")
            out.append((fields, sorted(set(used)), rule))
    # two templates giving one claim, one of them without its unit (as an overview's rules wrote): the one with it
    same = lambda f: (f["entity"], f["attribute"], f["value"], f["conditions"])
    united, kept, seen = {same(f) for f, _, _ in out if f["unit"]}, [], set()
    for c in out:
        if (c[0]["unit"] or same(c[0]) not in united) and (same(c[0]), c[0]["unit"]) not in seen:
            seen.add((same(c[0]), c[0]["unit"]))
            kept.append(c)
    return kept

def _fold(text):
    return " ".join(str(text).replace(",", "").split()).casefold()

def _same_value(a, b):
    x, y = number(a.strip()), number(b.strip())
    return x == y if x is not None and y is not None else _fold(a) == _fold(b)

def problems(rules, g, cols=None):
    """What's wrong with an answer, mechanically: [] when it can be used. Rules' misfit rows are not problems unless
    more than RETRY_SHARE of the rows."""
    reading = rules.reading.strip().lower()
    if reading not in ("rules", "rows", "summary"):
        return [f"unknown reading {rules.reading!r}: answer rules, rows or summary"]
    if reading == "rows":
        return []
    if reading == "summary":
        return summary_problems(rules, g, cols or analyse(g))
    if not rules.claims:
        return ["reading rules gives no claim templates"]
    out, misfits = [], []
    for i in range(len(g.rows)):
        try:
            row_claims(rules, g, i)
        except Broken as error:
            return [str(error)]
        except Misfit as error:
            misfits.append(str(error))
    if len(misfits) > RETRY_SHARE * len(g.rows) and len(misfits) >= 3:
        out.append(f"the templates don't fit {len(misfits)} of {len(g.rows)} rows (e.g. {misfits[0]})")
    if not rules.examples:
        out.append("no example claims given: write out the claims two or three of the rows shown give")
    shown = samples(g)
    for example in rules.examples:
        name = example.row.strip()
        name = name[4:].strip() if name.lower().startswith("row ") else name
        named = [g.names.index(name)] if name in g.names else []
        first = None  # a row named by its place among those shown (the sixth shown, "6") still checks the templates
        for i in named + [k for k in shown if k not in named]:
            missed = _missed(rules, g, i, example.claims)
            if missed is None or (i in named and missed.startswith("misfit: ")):  # read by itself in any case
                break
            first = first or (i, missed)
        else:
            if named:
                out.append(f"row {name}: {first[1]}")
            else:
                out.append(f"example row {example.row!r} isn't a row of the table, and no row shown gives its claims")
    return out

def _missed(rules, g, i, written):
    """None when the rules give row i every written claim (by value and unit), else what they give instead."""
    try:
        made = row_claims(rules, g, i)
    except Misfit as error:
        return f"misfit: {error}"
    every = list(made)
    for claim in written:
        if not claim.value.strip() or claim.value.strip().casefold() in NOT_APPLICABLE:
            continue  # no claim, by the templates' own rule
        match = next((m for m in made if _same_value(m[0]["value"], claim.value)
                      and _fold(m[0]["unit"]) == _fold(claim.unit)), None)
        if match is None:  # the same text parted differently between value and unit (10.2" against 10.2 and ")
            whole = _fold(claim.value + claim.unit).replace(" ", "")
            match = next((m for m in made if _fold(m[0]["value"] + m[0]["unit"]).replace(" ", "") == whole), None)
        if match is None:
            got = "; ".join(f"{m[0]['value']} {m[0]['unit']}".strip() for m in every) or "nothing"
            said = f"the templates give {got}, not {claim.value} {claim.unit}".rstrip()
            unitless = next((m for m in made if _same_value(m[0]["value"], claim.value) and not m[0]["unit"]
                             and ".unit}" in m[2].unit), None)
            if unitless:  # the unit was to come from a header with none in brackets: say how to mend it
                k = next((k for k in unitless[1] if g.rows[i][k] == unitless[0]["value"]), unitless[1][-1])
                said += (f" (column {g.columns[k]}'s header \"{g.labels[k]}\" has no unit in brackets for .unit to "
                         "take: give such columns a template of their own, the unit written out)")
            return said
        made.remove(match)
    return None

# --- summaries

def summary_problems(rules, g, cols):
    template = rules.template.strip().lower()
    if template not in ("series", "log", "list"):
        return [f"unknown template {rules.template!r}: series, log or list"]
    try:
        if template == "list":
            [_index(g, c) for c in rules.categories]  # none: the rows counted alone
            return []
        x = _index(g, rules.input)
        quantities = [_index(g, q) for q in rules.quantities]
    except Broken as error:
        return [str(error)]
    out = []
    if not quantities:
        out.append(f"a {template} needs quantities")
    measure = (lambda t: moment(t) or number(t)) if template == "log" else number
    if sum(measure(row[x]) is not None for row in g.rows) < 0.9 * len(g.rows):
        out.append(f"column {g.columns[x]} isn't an input {'time' if template == 'log' else 'number'} in most rows")
    for q in quantities:
        if sum(number(row[q]) is not None for row in g.rows) < 0.5 * len(g.rows):
            out.append(f"column {g.columns[q]} isn't numbers in most rows")
    return out

def _decimals(texts):
    return max((len(t.split(".")[1].rstrip("%")) for t in texts if "." in t), default=0)

@dataclass
class Statistic:
    """One claim of a summary: its fields, the rows and columns it was read from, whether it was computed (a mean, a
    count) rather than read from a cell, and its derivation detail."""
    fields: dict
    rows: list
    columns: list
    computed: bool
    detail: str

def summarise(rules, g):
    """The answer's template applied: [Statistic]."""
    template, subject = rules.template.strip().lower(), rules.subject or g.title or g.place
    claim = lambda attribute, value, unit="", conditions="": {"entity": subject, "attribute": attribute,
                                                              "value": value, "unit": unit, "conditions": conditions}
    out, n = [], len(g.rows)
    if template == "list":
        out.append(Statistic(claim("number of entries", str(n)), list(range(n)), [], True,
                             f"rows {g.names[0]} to {g.names[-1]} counted"))
        for c in (_index(g, c) for c in rules.categories):
            name = header_name(g.labels[c]) or g.columns[c]
            counts = Counter(row[c] or "(blank)" for row in g.rows).most_common()
            for value, count in counts[:CATEGORIES]:
                out.append(Statistic(claim("number of entries", str(count), "", f"{name} = {value}"),
                                     [i for i, row in enumerate(g.rows) if (row[c] or "(blank)") == value], [c], True,
                                     f"rows counted by column {g.columns[c]}"))
            if len(counts) > CATEGORIES:
                rest = counts[CATEGORIES:]
                out.append(Statistic(claim("number of entries", str(sum(k for _, k in rest)), "",
                                           f"{name}: {len(rest)} other values"), [], [c], True,
                                     f"rows counted by column {g.columns[c]}"))
        return out
    x = _index(g, rules.input)
    xname, xunit = header_name(g.labels[x]) or g.columns[x], header_unit(g.labels[x])
    at = lambda i: f"at {xname} = {g.rows[i][x]}" + (f" {xunit}" if xunit else "")
    if template == "series":
        held = [i for i in range(n) if number(g.rows[i][x]) is not None]
        low = min(held, key=lambda i: number(g.rows[i][x]))
        high = max(held, key=lambda i: number(g.rows[i][x]))
        step, mostly = _step([number(g.rows[b][x]) - number(g.rows[a][x]) for a, b in zip(held, held[1:])])
        out.append(Statistic(claim(f"{xname} range", f"{g.rows[low][x]} to {g.rows[high][x]}", xunit,
                                   f"{len(held)} points" + (f", {'mostly ' if mostly else ''}in steps of {step}"
                                                            if step else "")),
                             [low, high], [x], False, f"the range of column {g.columns[x]}"))
    else:
        held = [i for i in range(n) if (moment(g.rows[i][x]) or number(g.rows[i][x])) is not None]
        out.append(Statistic(claim(f"{xname} span", f"{g.rows[held[0]][x]} to {g.rows[held[-1]][x]}", xunit,
                                   f"{len(held)} samples"), [held[0], held[-1]], [x], False,
                             f"the span of column {g.columns[x]}"))
    for q in (_index(g, q) for q in rules.quantities):
        qname, qunit = header_name(g.labels[q]) or g.columns[q], header_unit(g.labels[q])
        rows = [i for i in held if number(g.rows[i][q]) is not None]
        if not rows:
            continue
        top = max(rows, key=lambda i: number(g.rows[i][q]))
        bottom = min(rows, key=lambda i: number(g.rows[i][q]))
        out.append(Statistic(claim(f"maximum {qname}", g.rows[top][q], qunit, at(top)), [top], [x, q], False,
                             f"the maximum of column {g.columns[q]}"))
        out.append(Statistic(claim(f"minimum {qname}", g.rows[bottom][q], qunit, at(bottom)), [bottom], [x, q], False,
                             f"the minimum of column {g.columns[q]}"))
        if template == "log":
            values = [number(g.rows[i][q]) for i in rows]
            places = _decimals([g.rows[i][q] for i in rows]) + 1
            out.append(Statistic(claim(f"mean {qname}", f"{sum(values) / len(values):.{places}f}", qunit,
                                       f"over {len(rows)} samples"), rows, [q], True,
                                 f"the mean of column {g.columns[q]}"))
            out.append(Statistic(claim(f"last {qname}", g.rows[rows[-1]][q], qunit, at(rows[-1])), [rows[-1]], [x, q],
                                 False, f"the last value of column {g.columns[q]}"))
        else:
            for point in rules.points:
                wanted = number(point.strip())
                i = next((i for i in rows if g.rows[i][x] == point.strip()
                          or (wanted is not None and number(g.rows[i][x]) == wanted)), None)
                if i is not None:
                    out.append(Statistic(claim(qname, g.rows[i][q], qunit, at(i)), [i], [x, q], False,
                                         f"column {g.columns[q]} at {xname} = {g.rows[i][x]}"))
    return out

# --- the task

def describe_rule(rule):
    """A rule's derivation detail: "value {C}; attribute {C.name}; entity {A}; unit {C.unit}"."""
    parts = [f"{name} {getattr(rule, name)}" for name in ("columns", "entity", "attribute", "value", "unit", "conditions",
                                                          "uncertainty") if getattr(rule, name)]
    return "; ".join(parts)[:300]

def read(core, page, g, task, by_itself, source, image=None):
    """Read a table by rules: ask for them, check them (once more if they fail), and apply them; by_itself(key) reads
    one of the table's rows (a grid row's key, or a section row's that is a note) as a table row without rules, as
    the grid holds it. Possible notes (possible_notes) are read by themselves where the model names them as notes,
    and where there's no answer to say. source: the reader's first derivation step (or its steps, as a list). image:
    the table's crop (a PDF's), sent with the query, which then copies a row from it to check the text layer."""
    from .llm import CallLimitReached, NotRecorded
    cols = analyse(g)
    if g.boxes:  # a PDF's rows: their own boxes
        span = (min(b[0] for b in g.boxes), min(b[1] for b in g.boxes), max(b[2] for b in g.boxes),
                max(b[3] for b in g.boxes))
        row_box = lambda i: tuple(g.boxes[i])
    else:
        first, last = g.lines[0], g.lines[-1]
        span = (0.0, float(first), 1.0, float(last + 1))
        row_box = lambda i: (0.0, float(g.lines[i]), 1.0, float(g.lines[i] + 1))
    images = [image] if image else []
    asked = question(g, cols, core.reader.for_table(page, span, " ".join(g.labels))) + ("\n" + IMAGED if image else "")

    def ask(prompt, attempt, then):
        name = task + (":again" if attempt else "")
        key = ("table-rules", "table", core.content, name, hashlib.sha256(prompt.encode()).hexdigest())

        def finish(answer, error):
            core.state["pending"] -= 1
            then(name, answer, error)

        core.progress.add()
        core.state["pending"] += 1
        core.dispatch.submit(prompt, Rules, [core.output / x for x in images], key, finish)

    def record(name, status, issues, found=()):
        row = coverage_row(content=core.content, page=page, bbox=list(span), task=name, status=status,
                           issues=issues, claims=len(found))
        core.evidence.extend(found)
        core.record(row, list(found))
        core.progress.finish(status)

    def everyone(name, why, notes=None):
        """Every row read by itself, and the notes (none named: our proposal, the possible notes)."""
        notes = possible_notes(g) if notes is None else notes
        for key in g.keys:
            by_itself(key)
        return f"every row read by itself: {why}" + read_notes(notes)

    def read_notes(notes):
        for r in notes:
            by_itself(r.key)
        return f"; notes read by themselves: rows {', '.join(r.name for r in notes)}" if notes else ""

    def first_answer(name, answer, error):
        if error is not None:
            return failed(name, error)
        g_, notes = noted(g, answer.notes)
        if image:  # the vision check (the one table model's decision 1): a row copied from the image
            mismatch = transcription_mismatch(answer, g)
            if mismatch:
                return record(name, "partial", [everyone(name, f"the image and the text layer disagree ({mismatch})",
                                                         notes)[:500]])
        wrong = problems(answer, g_, cols)
        if not wrong:
            return reviewed(name, answer)
        record(name, "partial", [f"The rules asked again: {'; '.join(wrong)}"[:500]])
        again = (asked + "\nYOUR EARLIER ANSWER:\n" + answer.model_dump_json(exclude_defaults=True)
                 + "\nITS PROBLEMS:\n" + "\n".join(f"- {w}" for w in wrong) + "\nAnswer again, mending them.")
        ask(again, 1, second_answer)

    def second_answer(name, answer, error):
        if error is not None:
            return failed(name, error)
        g_, notes = noted(g, answer.notes)
        wrong = problems(answer, g_, cols)
        if wrong:
            return record(name, "partial", [everyone(name, "the rules failed twice (" + "; ".join(wrong) + ")",
                                                     notes)[:500]])
        reviewed(name, answer)

    def reviewed(name, answer, round_=1, notes=()):
        """The rules' outcome shown to the model, again after each revision that passes the checks, until it keeps
        its rules or the cap (table_review) is reached; the last rules passing the checks are used (the owner,
        2026-10-07: "a cap of e.g. 10 will surely be safe ... just keeping the last revision")."""
        cap = int(REVIEW) if REVIEW is not None else core.s.reviews_tables()
        if round_ > cap or answer.reading.strip().lower() not in ("rules", "summary"):
            return use(name, answer, list(notes))
        prompt = review_question(asked, answer, noted(g, answer.notes)[0])
        suffix = ":review" + (str(round_) if round_ > 1 else "")
        key = ("table-review", "table", core.content, name + suffix, hashlib.sha256(prompt.encode()).hexdigest())
        revised = round_ - 1
        done = lambda: f"revised {revised} time{'s' if revised != 1 else ''}" if revised else "kept"

        def finish(result, error):
            core.state["pending"] -= 1
            core.progress.finish("failed" if error is not None else "complete")  # each review asked, finished once
            if error is not None or result is None:  # (code review 2026-10-08, B6: never, so totals never closed)
                return use(name, answer, list(notes) + [f"Not reviewed: {error}"[:300]], done() if revised else
                           "not reviewed")
            if result.verdict.strip().lower() != "revise" or result.rules is None:
                return use(name, answer, list(notes) + ["Reviewed: kept"], done())
            if not result.rules.notes:  # a revision silent on the notes keeps the ones named before
                result.rules.notes = answer.notes
            same = lambda r: r.model_dump(exclude={"why", "binding", "examples", "transcribed"})
            if same(result.rules) == same(answer):  # a revision changing nothing: shown again, it'd repeat itself
                return use(name, answer, list(notes) + [f"Reviewed: a revision changing nothing ({'; '.join(result.problems)}), "
                                                        "kept"[:400]], done())
            wrong = problems(result.rules, noted(g, result.rules.notes)[0], cols)
            if wrong:
                return use(name, answer, list(notes) + [f"Reviewed: a revision with problems ({'; '.join(wrong)}), "
                                                        "the last rules passing the checks kept"[:400]],
                           done() + ", its next revision failing the checks")
            note = f"Reviewed: revised ({'; '.join(result.problems)})"[:400]
            if round_ >= cap:
                return use(name, result.rules, list(notes) + [note, f"Review cap ({cap}) reached: the last revision used"],
                           f"revised {round_} time{'s' if round_ != 1 else ''}, the cap reached")
            reviewed(name, result.rules, round_ + 1, list(notes) + [note])

        core.progress.add()
        core.state["pending"] += 1
        core.dispatch.submit(prompt, Review, [core.output / x for x in images], key, finish)

    def failed(name, error):
        if isinstance(error, (CallLimitReached, NotRecorded)):  # nothing learnt: the next run asks again
            return record(name, "not_reached", [str(error)])
        record(name, "failed", [everyone(name, f"the rules query failed ({error})")[:500]])

    def use(name, answer, issues, review=""):
        reading = answer.reading.strip().lower()
        source_ = list(source) if isinstance(source, list) else [source]  # a list: a key-value check's step after it
        if review:  # the review's outcome, in each claim's derivation
            source_.append(DerivationStep(step="table-review", detail=review))
        why = f" ({answer.why})" if answer.why else ""
        if answer.binding:
            why += f" [binding: {answer.binding}]"
        g_, notes = noted(g, answer.notes)  # the notes it names: read by themselves, labelling no rows
        if reading == "rows":
            return record(name, "complete", [everyone(name, f"the model's reading{why}", notes)[:500]])
        found, misfits = [], []
        if reading == "summary":
            template = answer.template.strip().lower()
            for stat in summarise(answer, g_):
                if stat.computed:  # quoted by the headers it was computed under
                    quote, verified = " | ".join(g.labels[k] for k in stat.columns if g.labels[k]) or g.place, None
                else:
                    quote, verified = " | ".join(g.rows[i][k] for i in stat.rows for k in stat.columns), True
                box = row_box(stat.rows[0]) if len(stat.rows) == 1 else span
                found.append(_evidence(core, page, box, name, stat.fields, quote, verified, [
                    *source_, DerivationStep(step="table-summary", detail=f"{template} template: {stat.detail}"
                                                                         + (", computed" if stat.computed else ""))],
                    approximate=stat.computed and stat.fields["attribute"].startswith("mean ")))
            return record(name, "complete", issues + [f"Summarised by the {template} template: {len(g.rows)} rows, "
                                                      f"{len(found)} claims{why}{read_notes(notes)}"[:500]], found)
        for i in range(len(g.rows)):
            try:
                made = row_claims(answer, g_, i)
            except (Misfit, Broken) as error:
                misfits.append(i)
                issues.append(f"Row {g.names[i]} read by itself: {error}")
                continue
            for fields, used, rule in made:
                quote = " | ".join(g.rows[i][k] for k in used if g.rows[i][k]) or " | ".join(t for t in g.rows[i] if t)
                found.append(_evidence(core, page, row_box(i), name, fields, quote, True, [
                    *source_, DerivationStep(step="table-rules", detail=describe_rule(rule))]))
        for i in misfits:
            by_itself(g.keys[i])
        summary = (f"Read by rules: {len(g.rows) - len(misfits)} of {len(g.rows)} rows, {len(found)} claims"
                   + (f"; {len(misfits)} rows read by themselves" if misfits else "") + read_notes(notes) + why)
        record(name, "complete", [summary[:500]] + issues[:8], found)

    ask(asked, 0, first_answer)

def _evidence(core, page, box, task, fields, quote, verified, derivation, approximate=False):
    from .schema import Claim
    claim = Claim(entity=fields["entity"][:160], attribute=fields["attribute"][:160], value=fields["value"][:300],
                  unit=fields["unit"][:40], conditions=fields["conditions"][:300], kind="table", quote=quote[:400],
                  confidence=CONFIDENCE, approximate=approximate, uncertainty=fields.get("uncertainty", "")[:200])
    home = core.sections.box(page, box).id
    return Evidence(**claim.model_dump(), id=claim_id(core.content, claim), content=core.content, section=home,
                    locator=core.locator(page, box, "table", task), derivation=derivation, quote_verified=verified)
