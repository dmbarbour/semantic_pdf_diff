"""Excel workbooks (.xlsx, .xlsm; docs/plans/multi-format-adapters-2026-09-23.md, milestone 5, "Excel, in detail"),
read through the text reader as Word documents are: a workbook becomes a TextDocument whose pages are its sheets and
whose lines are its regions' rows and cells, each line placed by its sheet and cell range.

The owner (2026-10-04): "Let's do Excel next. 99% of my spreadsheets are Excel."

- **Cells as Excel shows them:** a cell's cached value in its number format (chartxml.format_number), a date as an
  ISO date. A formula without a cached value is never evaluated: its cell reads "[formula =C6+C7, not calculated]".
- **Sheets in the workbook's order,** each a page and a section titled by its name; a hidden sheet is read, marked
  "(Hidden sheet)".
- **Regions:** Excel's defined tables first; then blocks of filled cells parted by blank rows and columns, a lone cell
  heading a wider block split off as its title, and narrow leading rows (a label and its value, "Reynolds |
  8100000", over a wider table, as the IEA workbooks stack them) split off as pairs, each a line ("Reynolds:
  8100000"). A region of one row or one column is text (titles, notes): each
  cell a line. The rest are tables on the Word reader's grid: a merged cell spans, its header rows labelled by path
  (a defined table's own count; else the first row, and the next when the first has merged cells and the next no
  number).
- **The sheet map** (TextDocument.regions): each region's sheet, range, kind and size, for the rules query.
- **An ambiguous region is skipped, never silently** (the plan's contract): a table with a column, past its first,
  that holds values under no header, as two tables pressed together do. It's recorded as "skipped: ambiguous sheet
  layout", with its range.
- **Tables are read row by row up to READ_ROWS rows,** for now: a larger one is recorded as not read yet (awaiting
  the rules query, the plan's step 5), never silently; its header row is kept as a line.
- **Comments** on cells are content, as Word's: after the region holding them ('Comment by Ana on B5: ...').
- **Charts** are read from their data (chartxml.py), and pictures as a Word document's are, after the sheet's
  regions.
- **Not followed or read:** external links, pivot caches, macros; a chart sheet is recorded as not read.

Needs openpyxl (the `office` extra).
"""
import datetime
import io
import posixpath
from dataclasses import dataclass, field

from . import chartxml
from .docxdocs import Cell, _header_rows, _joined, _labels
from .textdocs import Block, Picture, TextDocument

READ_ROWS = 50  # a table this long is read row by row for now; a longer one awaits the rules query
XDR = "{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
EMU_PER_POINT = 12700

@dataclass
class Region:
    """A block of a sheet: its bounds (rows and columns, from 1), its kind ("table" or "text"), for a table its header
    rows and the defined table naming it, and the lines it was read into."""
    sheet: str
    top: int
    left: int
    bottom: int
    right: int
    kind: str = "table"
    header_rows: int = 0  # 0: found by the heuristic
    name: str = ""
    lines: list = field(default_factory=list)

    @property
    def ref(self):
        corner = f"{_letter(self.left)}{self.top}"
        return corner if (self.bottom, self.right) == (self.top, self.left) else \
            f"{corner}:{_letter(self.right)}{self.bottom}"

    @property
    def rows(self):
        return self.bottom - self.top + 1

def _letter(column):
    out = ""
    while column:
        column, rest = divmod(column - 1, 26)
        out = chr(65 + rest) + out
    return out

def shown(cell, formula=None):
    """A cell's value as Excel shows it: its number format applied, a date as an ISO date, an error as written; a
    formula without a cached value marked, not evaluated."""
    value = cell.value
    if value is None:
        return f"[formula {formula}, not calculated]" if isinstance(formula, str) and formula.startswith("=") else ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime.datetime):
        return value.date().isoformat() if value.time() == datetime.time() else value.isoformat(" ")
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, (int, float)):
        return chartxml.format_number(repr(value) if isinstance(value, float) else str(value), cell.number_format)
    return " ".join(str(value).split())

def _filled(ws, formulas):
    """{(row, column): text} of a sheet's cells that show something. Only stored cells are visited: a sheet formatted
    down to row 1,048,576 stores few, and visiting every formatted row would take minutes."""
    out = {}
    for (row, column), cell in ws._cells.items():
        text = shown(cell, formulas.get((row, column)))
        if text:
            out[(row, column)] = text
    return out

def _merges(ws):
    """{(row, column): (top, left, bottom, right)} for every cell inside a merged range."""
    out = {}
    for merged in ws.merged_cells.ranges:
        bounds = (merged.min_row, merged.min_col, merged.max_row, merged.max_col)
        for r in range(bounds[0], bounds[2] + 1):
            for c in range(bounds[1], bounds[3] + 1):
                out[(r, c)] = bounds
    return out

def regions(ws, cells, merges):
    """A sheet's regions: its defined tables; then blocks of filled (or merged-over) cells joined through shared edges
    (two tables touching only at a corner stay two), blocks whose bounds overlap merged into one (a list's sparse
    columns); a lone cell heading a wider block split off as its title."""
    from openpyxl.utils.cell import range_boundaries
    found, taken = [], set()
    for table in ws.tables.values():  # (openpyxl's items() gives each table's range, not the table)
        left, top, right, bottom = range_boundaries(table.ref)
        found.append(Region(ws.title, top, left, bottom, right, "table", max(1, table.headerRowCount or 0),
                            table.displayName or table.name))
        taken |= {(r, c) for r in range(top, bottom + 1) for c in range(left, right + 1)}
    occupied, boxes = (set(cells) | set(merges)) - taken, []
    while occupied:
        start = min(occupied)
        block, todo = {start}, [start]
        while todo:
            r, c = todo.pop()
            for n in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if n in occupied and n not in block:
                    block.add(n)
                    todo.append(n)
        occupied -= block
        boxes.append([min(r for r, _ in block), min(c for _, c in block), max(r for r, _ in block),
                      max(c for _, c in block)])
    merged = True
    while merged:  # blocks whose bounds overlap are one region
        merged = False
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                    boxes[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    del boxes[j]
                    merged = True
                    break
            if merged:
                break
    for top, left, bottom, right in boxes:
        while top < bottom and right > left:  # a lone first-row cell over a wider block: its title
            first = [c for c in range(left, right + 1) if (top, c) in cells]
            if len(first) != 1:
                break
            found.append(Region(ws.title, top, first[0], top, first[0], "text"))
            top += 1
            while top < bottom and not any((top, c) in cells for c in range(left, right + 1)):
                top += 1  # rows under the title merged over, empty: skipped
        pairs = top
        while pairs < bottom and right > left + 1 and all(c <= left + 1 for c in range(left, right + 1)
                                                            if (pairs, c) in cells):
            pairs += 1  # narrow leading rows (a label and its value) over a wider table: pairs
        if pairs > top and any((r, c) in cells for r in range(pairs, bottom + 1) for c in range(left + 2, right + 1)):
            found.append(Region(ws.title, top, left, pairs - 1, left + 1, "pairs"))
            top = pairs
        held = [c for (r, c) in set(cells) | set(merges) if top <= r <= bottom and left <= c <= right]
        left, right = min(held, default=left), max(held, default=right)  # what's left, without the split rows' width
        kind = "text" if top == bottom or left == right else "table"
        found.append(Region(ws.title, top, left, bottom, right, kind))
    return sorted(found, key=lambda g: (g.top, g.left))

def _grid(region, cells, merges):
    """[(row number, [Cell])]: a table region's rows on its columns (counted from 0). A merged cell spans its columns;
    below its first row its text repeats, continued (as a cell merged down in Word)."""
    rows = []
    for r in range(region.top, region.bottom + 1):
        out, c = [], region.left
        while c <= region.right:
            merged = merges.get((r, c))
            if merged and merged[1] != c:  # covered from the left: the spanning cell holds it
                c += 1
                continue
            right = min(merged[3], region.right) if merged else c
            if merged and merged[0] != r:
                out.append(Cell(cells.get(merged[:2], ""), c - region.left, right - region.left, continued=True))
            else:
                out.append(Cell(cells.get((r, c), ""), c - region.left, right - region.left))
            c = right + 1
        rows.append((r, out))
    return rows

def _unheaded(grid, heads):
    """Whether a column past the first holds values under no header (two tables pressed together)."""
    labelled = {k for _, row in grid[:heads] for c in row if c.text for k in range(c.first, c.last + 1)}
    used = {c.first for _, row in grid[heads:] for c in row if c.text}
    return any(k not in labelled for k in used if k > 0)

def _sheet_parts(package):
    """{sheet name: its worksheet part's name}, from the workbook's own list."""
    book = "xl/workbook.xml"
    rels = package.rels(book)
    return {s.get("name"): rels[s.get(R + "id")][1] for s in package.xml(book).iter(S + "sheet")
            if s.get(R + "id") in rels}

def read_xlsx(data):
    """A workbook's TextDocument: sheets as pages, regions' rows and cells as lines (each placed by its sheet and
    range), each sheet's name its heading; the sheet map in .regions."""
    import openpyxl
    from .pptxdocs import Package
    raw = bytes(data)
    book = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    written = openpyxl.load_workbook(io.BytesIO(raw), data_only=False)  # the formulas, for cells left uncalculated
    package = Package(raw)
    parts = _sheet_parts(package)
    lines, blocks, headings, images, pictures, places, mapped = [], [], [], [], [], {}, []

    def line(page, text, place):
        lines.append((page, text))
        places[len(lines)] = place
        return len(lines)

    def table(page, sheet, region, cells, merges):
        grid = _grid(region, cells, merges)
        heads = min(region.header_rows or _header_rows(grid, marked=0), len(grid))
        row_ref = lambda r: f"{_letter(region.left)}{r}:{_letter(region.right)}{r}"
        if not region.name and _unheaded(grid, heads):
            region.kind = "ambiguous"
            images.append((page, len(lines), "sheet", f"skipped: ambiguous sheet layout ({sheet}!{region.ref}): a column "
                                                     "holds values under no header, as tables pressed together do"))
            return
        if region.rows - heads > READ_ROWS:
            r, header = grid[0]
            n = line(page, " | ".join(c.text for c in header), (sheet, row_ref(r)))
            region.lines.append(n)
            images.append((page, n, "sheet", f"a table of {region.rows - heads} rows ({sheet}!{region.ref}), not read "
                                             "yet: it awaits the rules query"))
            return
        labels = _labels(grid, heads)
        header_lines = [line(page, " | ".join(c.text for c in row), (sheet, row_ref(r))) for r, row in grid[:heads]]
        rows, row_lines, row_headers = [labels], [header_lines[0]], []
        for r, row in grid[heads:]:
            rows.append([c.text for c in row])
            row_headers.append([_joined(labels[c.first:c.last + 1]) for c in row])
            row_lines.append(line(page, " | ".join(c.text for c in row), (sheet, row_ref(r))))
        first = header_lines[0]
        blocks.append(Block(page, first, len(lines), "\n".join(t for _, t in lines[first - 1:]), "table", rows,
                            row_lines, row_headers))
        region.lines += list(range(first, len(lines) + 1))

    def drawings(page, sheet):
        """A sheet's charts (read from their data) and pictures (read as a Word document's), after its regions."""
        part = parts.get(sheet)
        drawing = package.related(part, "drawing") if part else None
        if not drawing:
            return
        for anchor in package.xml(drawing):
            for frame in anchor.iter(XDR + "graphicFrame"):
                reference = next(frame.iter("{%s}chart" % CHART), None)
                target = package.rels(drawing).get(reference.get(R + "id")) if reference is not None else None
                try:
                    found = chartxml.read(package.read(target[1]))
                    if not found.tables:
                        raise ValueError("no series")
                except Exception as error:  # a damaged or unexpected part: noted, the rest read
                    images.append((page, len(lines), "sheet", f"a chart whose data couldn't be read "
                                                             f"({type(error).__name__}: {error})"))
                    continue
                label = found.label()
                m = line(page, label, (sheet, "chart"))
                blocks.append(Block(page, m, m, label))
                for header, rows in found.tables:
                    first = line(page, " | ".join(header), (sheet, "chart"))
                    row_lines = [first] + [line(page, " | ".join(row), (sheet, "chart")) for row in rows]
                    blocks.append(Block(page, first, len(lines), "\n".join(t for _, t in lines[first - 1:]), "table",
                                        [header] + rows, row_lines, source="chart"))
            for pic in anchor.iter(XDR + "pic"):
                blip = next(pic.iter(A + "blip"), None)
                target = package.rels(drawing).get(blip.get(R + "embed")) if blip is not None else None
                if not target or target[1] not in package.names:
                    images.append((page, len(lines), "sheet", "a picture whose image isn't in the workbook"))
                    continue
                ext = next(pic.iter(A + "ext"), None)
                size = (int(ext.get("cx")) / EMU_PER_POINT, int(ext.get("cy")) / EMU_PER_POINT) \
                    if ext is not None and ext.get("cx") else None
                m = line(page, "", (sheet, "picture"))
                name = target[1]
                pictures.append(Picture(m, package.read(name), posixpath.splitext(name)[1].lower(), size, sheet,
                                        posixpath.basename(name), page))

    for page, ws in enumerate(book.worksheets, 1):
        formulas = {key: cell.value for key, cell in written[ws.title]._cells.items()
                    if isinstance(cell.value, str) and cell.value.startswith("=")}
        cells, merges = _filled(ws, formulas), _merges(ws)
        n = line(page, ws.title, (ws.title, "A1"))
        headings.append((page, n, 1, ws.title))
        blocks.append(Block(page, n, n, ws.title))
        if ws.sheet_state != "visible":
            n = line(page, "(Hidden sheet)", (ws.title, "A1"))
            blocks.append(Block(page, n, n, "(Hidden sheet)"))
        comments = {(cell.row, cell.column): cell.comment for cell in ws._cells.values() if cell.comment}
        for region in regions(ws, cells, merges):
            mapped.append(region)
            if region.kind == "pairs":  # a label and its value: one line each
                for r in range(region.top, region.bottom + 1):
                    shown_ = [cells[(r, c)] for c in (region.left, region.left + 1) if (r, c) in cells]
                    if shown_:
                        text = ": ".join(shown_)
                        m = line(page, text, (ws.title, f"{_letter(region.left)}{r}:{_letter(region.left + 1)}{r}"))
                        blocks.append(Block(page, m, m, text))
                        region.lines.append(m)
            elif region.kind == "text":
                for r in range(region.top, region.bottom + 1):
                    for c in range(region.left, region.right + 1):
                        if (r, c) in cells:
                            m = line(page, cells[(r, c)], (ws.title, f"{_letter(c)}{r}"))
                            blocks.append(Block(page, m, m, cells[(r, c)]))
                            region.lines.append(m)
            else:
                table(page, ws.title, region, cells, merges)
            for (r, c), note in sorted(comments.items()):
                if region.top <= r <= region.bottom and region.left <= c <= region.right:
                    text = (f"Comment by {note.author or 'an unnamed author'} on {_letter(c)}{r}: "
                            f"{' '.join(note.text.split())}")
                    m = line(page, text, (ws.title, f"{_letter(c)}{r}"))
                    blocks.append(Block(page, m, m, text))
        drawings(page, ws.title)
    for sheet in book.chartsheets:
        images.append((1, len(lines), "workbook", f"a chart sheet ({sheet.title}), not read yet"))
    return TextDocument(max(1, len(book.worksheets)), lines, blocks, headings, images, pictures, places, mapped)
