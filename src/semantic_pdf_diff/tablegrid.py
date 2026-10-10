"""A table as rules see it, the one owner of its grid (code review 2026-10-08, architecture 6: tablerules owned the
grid, and the deck and workbook readers borrowed Word's private cell helpers): Grid and its constructors, section
rows and possible notes, column letters, cells' values as shown, header labels and units; the readers' cells placed
on a grid (Cell) and their header rows and labels; rows' cells filled and joined.
"""
import datetime
import re
import unicodedata
from dataclasses import dataclass, field, replace

NUMBER = re.compile(r"^[-+−]?[$€£¥]?(?=\.?\d)(?:\d{1,3}(?:,\d{3})+|\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?%?$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?)?$")
BRACKETED = re.compile(r"[(\[]([^()\[\]]{1,24})[)\]]")
DIGIT = re.compile(r"\d")

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

@dataclass
class Cell:
    """A table cell placed on the grid: its text (small nested tables written in), the columns it covers, whether
    it continues a cell merged down from the row above, and its larger nested tables (read after the table)."""
    text: str
    first: int
    last: int
    continued: bool = False
    nested: list = field(default_factory=list)

def header_rows(grid, marked=0):
    """How many rows head a table: those marked to repeat as a header (marked: their count); else the first, and the
    next while the row above has a cell merged across (or one merged down into it) and the row holds no number (three
    at most)."""
    if marked:
        return min(marked, len(grid))
    n = 1
    while n < min(len(grid) - 1, 3):
        before, row = grid[n - 1][1], grid[n][1]
        merged = any(c.last > c.first for c in before) or any(c.continued for c in row)
        if not merged or any(DIGIT.search(c.text) for c in row) or not any(c.text for c in row):
            break
        n += 1
    return n

def header_labels(grid, heads):
    """Each column's label: its header cells' texts top to bottom, a merged cell's once ("Rated point > TDH (ft)")."""
    width = max((c.last + 1 for _, cells in grid for c in cells), default=0)
    out = []
    for column in range(width):
        path = []
        for _, cells in grid[:heads]:
            cell = next((c for c in cells if c.first <= column <= c.last), None)
            if cell is not None and cell.text and (not path or path[-1] != cell.text):
                path.append(cell.text)
        out.append(" > ".join(path))
    return out

def joined_labels(labels):
    """One label for a cell merged across columns: their shared path once, then each leaf ("A > B / C")."""
    labels = list(dict.fromkeys(label for label in labels if label))
    if len(labels) < 2:
        return labels[0] if labels else ""
    paths = [label.split(" > ") for label in labels]
    shared = 0
    while all(len(p) > shared + 1 and p[shared] == paths[0][shared] for p in paths):
        shared += 1
    leaves = " / ".join(" > ".join(p[shared:]) for p in paths)
    return " > ".join(paths[0][:shared] + [leaves])

def filled(row):
    """A row's cells that hold something."""
    return [c for c in row if c is not None and str(c).strip()]

def joined(upper, lower):
    """Two rows' cells joined, column by column: lines of one row."""
    out = []
    for k in range(max(len(upper), len(lower))):
        a = upper[k] if k < len(upper) else None
        b = lower[k] if k < len(lower) else None
        texts = [" ".join(str(t).split()) for t in (a, b) if t is not None and str(t).strip()]
        out.append(" ".join(texts) if texts else (a if a is not None else b))
    return out

def plain(text):
    """A cell's text folded for comparing transcriptions: case, width and punctuation but . - + % /."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return "".join(ch for ch in text if ch.isalnum() or ch in ".-+%/")
