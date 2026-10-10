"""The PDF job: a PDF read a page at a time, its text, tables, figures and tiles made into tasks for the task core
(tasks.TaskCore). The scheduler and readers are jobs.py's, the image tasks visuals.py's, the extraction prompt
tasks.py's (code review 2026-10-08, A12: this module held all five).
"""
import json
import re
from functools import partial
from pathlib import Path

import pymupdf

from . import keyvalue
from .context import Context
from .pages import native, native_page, reading_blocks, shown
from .regions import crop_name, crop_stem
from .schema import DerivationStep, PdfLocator, coverage_row
from .sections import pdf_sections
from .tables import Marks, column_edges, cut_columns, pdf_grid, pdf_parts, row_boxes, ruled_rows, same_form, split_cuts
from .tasks import TaskCore, split_utf8
from .visuals import Visuals, render

def text_pieces(page, text_bytes):
    pieces = []
    for bi, block in enumerate(reading_blocks(page)):
        if block[6] != 0:
            continue
        for ci, chunk in enumerate(split_utf8(block[4].strip(), text_bytes)):
            if chunk.strip():
                pieces.append((f"{bi}.{ci}", tuple(block[:4]), chunk))
    return pieces

def text_groups(page, text_bytes, section_of=None):
    """Consecutive text blocks grouped up to the byte budget (oversized blocks split),
    never across a section boundary (section_of(bbox) names a block's section).

    Returns [(ids, [(bbox, text)])], where ids like '3.0-5.0' name the blocks grouped.
    """
    pieces = text_pieces(page, text_bytes)
    part = section_of or (lambda bbox: None)
    groups, group, size = [], [], 0
    for piece in pieces + [None]:
        extra = len(piece[2].encode()) + 2 if piece else 0
        if group and (piece is None or size + extra > text_bytes or part(piece[1]) != part(group[-1][1])):
            ids = group[0][0] + (f"-{group[-1][0]}" if len(group) > 1 else "")
            groups.append((ids, [(b, t) for _, b, t in group]))
            group, size = [], 0
        if piece:
            group.append(piece)
            size += extra
    return groups

UNIT = re.compile(r"\d\s?(?:[kMG]?W|kWh|[kM]?Pa|bar|psi|mm|cm|km|m²|m2|m³|m3|kg|L/s|l/s|L/min|°C|°F|K|%|Hz|kV|V|kVA|A|rpm|dB)\b")
REQUIREMENT = re.compile(r"\b(?:shall|must|required|requirement)\b", re.IGNORECASE)

def page_signals(page, tables, drawings=None):
    """Cheap triage signals for one page; summed per section. drawings: the page's, if already fetched."""
    text = page.get_text("text")
    drawings = page.get_cdrawings() if drawings is None else drawings
    return {"numbers": len(re.findall(r"\d+(?:[.,]\d+)?", text)), "units": len(UNIT.findall(text)),
            "requirements": len(REQUIREMENT.findall(text)), "tables": tables, "images": len(page.get_images()),
            "drawings": len(drawings), "characters": len(text.strip())}

def pdf_locator(page, bbox, region, task):
    return PdfLocator(page=page, bbox=bbox, region=region, task=task)

# How each extraction pass gets from PDF bytes to a claim.
DERIVATION = {
    "text": [DerivationStep(step="pdf-text-layer", detail="grouped text blocks"), DerivationStep(step="model-extraction")],
    "table": [DerivationStep(step="pdf-table-detection", detail="row with provisional header"), DerivationStep(step="model-extraction")],
    "tile": [DerivationStep(step="pdf-render", detail="page tile"), DerivationStep(step="model-extraction", detail="vision")],
    "figure": [DerivationStep(step="pdf-render", detail="detected figure with its caption"),
               DerivationStep(step="model-extraction", detail="vision")],
    "overview": [DerivationStep(step="pdf-render", detail="whole page"), DerivationStep(step="model-extraction", detail="vision")],
}

def continues(rows, displayed, page_rect, continuing, first):
    """Whether a table read on a page continues the one carried from the page before (continuing: its header and
    width): the page's first table, at its top (within a fifth of the page), as wide, and its first row the carried
    header repeated or not a header of the same form (a new table, e.g. the next day's schedule)."""
    width = max(len(r) for r in rows)
    return bool(first and continuing and continuing[1] == width and displayed.y0 - page_rect.y0 < 0.2 * page_rect.height
                and (rows[0] == continuing[0] or not same_form(rows[0], continuing[0])))

class PdfReading:
    """One PDF's reading, the state its pages share: the task core, the reader's context, the image tasks, the page
    regions worked out once. Each page is read in steps: its text, its tables detected and read (PdfTable), its
    signals, its image tasks (code review 2026-10-08, A9: _pdf_job did all of it in one loop of 218 lines)."""

    def __init__(self, core, doc, s, content, assets, stem, owner):
        self.core, self.doc, self.s, self.content, self.assets, self.stem, self.owner = (
            core, doc, s, content, assets, stem, owner)
        self.record = core.record
        self.context_of = Context(doc, s, assets, stem)  # the task functions read it when they run
        self.visuals = Visuals(core, self.context_of, assets, stem, s)
        self.regions = {}  # page -> its image tasks' regions, worked out once (the vision step; tables read as figures)
        self.signals = {}
        self.carried = None  # (header, width) of a table that ended near the bottom of the previous page

    def regions_of(self, number, page):
        if number not in self.regions:
            self.regions[number] = list(self.s.visual_regions(self.context_of, page, number))
        return self.regions[number]

    def as_figure(self, number, page, rect, tag):
        """A region parsed as a table that the model reads as no table (a chart, a floor plan): read by a figure
        task, unless the overview, a figure task or one tile already sees it whole. What happened, in words."""
        if abs(rect & page.rect) >= 0.9 * abs(page.rect):
            return "seen whole by the page's overview"
        for region_tag, region, _ in self.regions_of(number, page):
            kind = region_tag.partition(":")[0]
            if kind == "figure" and abs(region & rect) >= 0.8 * abs(rect):
                return "seen whole by a figure task"
            if kind == "tile" and region.contains(rect):
                return "seen whole by a tile"
        self.visuals.task(number, page, f"figure:p{number}:{tag}", rect, derivation=[
            DerivationStep(step="pdf-render", detail="a region parsed as a table, read as a figure (the model "
                                                     "reads no table there)"),
            DerivationStep(step="model-extraction", detail="vision")])
        return "read by a figure task"

    def page(self, number, page):
        """Read one page: its text, tables, signals and image tasks."""
        self.text(number, page)
        found, marks = self.detect(number, page)
        self.tables(number, page, found, marks)
        self.page_signals(number, page, found)
        self.vision(number, page)

    def text(self, number, page):
        # Native coordinates stay unrotated (PDF point coordinates). Consecutive
        # blocks are grouped up to the byte budget; oversized blocks are split.
        for ids, segments in text_groups(page, self.s.text_bytes, lambda b, n=number: self.owner.box(n, b).id):
            self.core.text_task(number, segments, f"text:p{number}:{ids}")

    def detect(self, number, page):
        """The page's tables as detected and mended: ([(bbox, rows, boxes, styles, rules, edges)], its drawn marks)."""
        s, content, record = self.s, self.content, self.record
        # Table detection works in displayed coordinates; locators are unrotated. Only PyMuPDF's calls are
        # detection failures (it raises assorted internal errors); our mending's errors are named as ours, and the
        # table read as detected (code review 2026-10-08, A4: both dropped the page's tables as "detection").
        unrotated = lambda b: tuple(native(page, b)) if b else None
        found = []
        try:
            detected = [(table, table.extract()) for table in page.find_tables().tables]
        except Exception as e:  # noqa: BLE001 (PyMuPDF's)
            detected = []
            record(coverage_row(content=content, page=number, bbox=list(native_page(page)),
                                task=f"table-detection:p{number}", status="failed",
                                issues=[type(e).__name__ + ": " + str(e)]))
        marks = Marks(page) if page.rotation == 0 and detected else None  # drawn rules and styles (unrotated)
        for ti_found, (table, rows) in enumerate(detected):
            if not s.keep_table(self.context_of, page, table, rows):
                continue
            boxes, styles, rules, edges = row_boxes(table, rows), None, None, None
            if marks is not None and boxes:  # lines of one row parted by shading, joined (ruled_rows)
                try:
                    rules = marks.rules(table.bbox)
                    mended, mended_boxes, _ = ruled_rows(rows, boxes, rules)
                    mended, edges, _ = cut_columns(mended, mended_boxes, column_edges(table), marks)
                    styles = marks.styles(table.bbox, mended_boxes)
                    rows, boxes = mended, mended_boxes
                except Exception as e:  # noqa: BLE001 (a bug of ours: the table is still read, as detected)
                    rules = styles = edges = None
                    record(coverage_row(content=content, page=number, bbox=list(native(page, table.bbox)),
                                        task=f"table-detection:p{number}:{ti_found}:mending", status="partial",
                                        issues=[f"Table mending failed (a bug: {type(e).__name__}: {e}); "
                                                "the table read as detected"]))
            found.append((unrotated(table.bbox), rows, [unrotated(b) for b in boxes], styles, rules, edges))
        return found, marks

    def tables(self, number, page, found, marks):
        """Each table read (PdfTable); the last one ending near the page's bottom carried to the next page."""
        continuing, self.carried = self.carried, None
        self.context_of.tables_on[number] = [found_[0] for found_ in found]
        for ti, (bbox, rows, boxes, styles, rules, edges) in enumerate(found):
            if not rows:
                continue
            table = PdfTable(self, number, page, ti, bbox, rows, boxes, styles, rules, edges, marks, continuing)
            table.read()
            if table.displayed.y1 - page.rect.y0 > 0.8 * page.rect.height:
                self.carried = (table.header, table.width)
            else:
                self.carried = None

    def page_signals(self, number, page, found):
        section = self.owner[number].id
        for name_, value in page_signals(page, len(found), self.context_of.drawings(page)).items():
            self.signals.setdefault(section, {}).setdefault(name_, 0)
            self.signals[section][name_] += value

    def vision(self, number, page):
        if self.s.vision:
            for tag, rect, note in self.regions_of(number, page):
                # Task tags are unique within content: "<region>:p<page>[:<index>]".
                region, _, index = tag.partition(":")
                tag = f"{region}:p{number}" + (f":{index}" if index else "")
                # A figure's caption, or a sheet detail's titles, as source text.
                self.visuals.task(number, page, tag, rect, text=note)
        else:
            self.record(coverage_row(content=self.content, page=number, bbox=list(native_page(page)),
                                     task=f"vision:p{number}", status="skipped",
                                     issues=["Visual extraction disabled; charts, diagrams and scans may be missed"]))

class PdfTable:
    """One table detected on a PDF page, read: its parts (tables.pdf_parts), each asked first how its suspect lines
    group into rows (the structure query), then read by rules where its rows are many, else row by row, two columns
    perhaps as a key-value list. What its readings use is bound when it's made, and each part's values with
    functools.partial: an answer coming pages later reads this table (code review 2026-10-08, A9: callbacks bound by
    default arguments, a missed one B1's bug)."""

    def __init__(self, reading, number, page, ti, bbox, rows, boxes, styles, rules, edges, marks, continuing):
        self.reading, self.number, self.page, self.ti = reading, number, page, ti
        self.bbox, self.rows, self.boxes, self.rules, self.edges, self.marks = bbox, rows, boxes, rules, edges, marks
        self.displayed = shown(page, bbox)  # continuation is judged as displayed
        self.header, self.body, self.derivation = rows[0], rows[1:] or rows, None
        self.body_boxes = boxes[1:] if len(rows) > 1 else boxes
        self.body_styles = None if styles is None else styles[1:] if len(rows) > 1 else styles
        self.width = max(len(r) for r in rows)
        # A table continuing the one that ended at the bottom of the previous page is read under its header; an
        # identical first row is a repeated header, skipped.
        if continues(rows, self.displayed, page.rect, continuing, ti == 0):
            if rows[0] != continuing[0]:
                self.body, self.body_boxes, self.body_styles = rows, boxes, styles
            self.header = continuing[0]
            self.derivation = [DerivationStep(step="pdf-table-detection",
                                              detail=f"row with header continued from page {number - 1}"),
                               DerivationStep(step="model-extraction")]
        # Repaired into parts: a header over two lines merged, stacked tables split (tables.pdf_parts).
        self.parts = pdf_parts(self.header, self.body, self.body_boxes, self.body_styles)
        self.look = {tuple(b): st for b, st in zip(self.body_boxes, self.body_styles or []) if b and st is not None}
        self.crop = None
        # the header's box, where it's the table's first line (a key-value list's first pair, B5)
        self.head = tuple(boxes[0]) if self.header is rows[0] and len(rows) > 1 and boxes and boxes[0] else None

    def image(self):
        """The table's crop, rendered once when first asked for."""
        r = self.reading
        if self.crop is None:
            self.crop = crop_name(r.stem, f"rules:p{self.number}:{self.ti}")
            render(self.page, self.displayed, r.assets / self.crop, r.s.image_side, r.context_of)
        return f"assets/{self.crop}"

    def read(self):
        """Each part asked how its lines group into rows, where the configuration asks, then read (proceed)."""
        r, number = self.reading, self.number
        for pi, (part_header, part_body, part_boxes) in enumerate(self.parts):
            base = f"{self.ti}" if pi == 0 else f"{self.ti}.{pi}"
            label = f", part {pi + 1}" if len(self.parts) > 1 else ""
            if r.s.asks_structure():  # a part with suspect lines asked how they group into rows
                from . import tablestructure
                cuts = None
                if self.marks is not None and self.edges:  # words a column line splits, by line (0: the header)
                    cuts = {i + 1: split_cuts(row, b, self.edges, self.marks) for i, (row, b) in
                            enumerate(zip(part_body, part_boxes))}
                    if pi == 0 and self.header is self.rows[0] and self.boxes:
                        cuts[0] = split_cuts(self.header, self.boxes[0], self.edges, self.marks)
                tablestructure.read(
                    r.core, number, f"structure:p{number}:{base}", part_header, part_body, part_boxes,
                    [self.look.get(tuple(b)) if b else None for b in part_boxes] if self.look else None,
                    self.rules, lambda: [self.image()],
                    partial(self.proceed, base=base, original=(part_header, part_body, part_boxes), label=label), cuts)
            else:
                self.proceed([(part_header, part_body, part_boxes)], None, [], base=base, original=None, label=label)

    def proceed(self, parts, step, apart, table=True, *, base, original, label):
        """Each part read: by rules where tables are, else row by row; lines apart read by themselves; a part the
        model reads as no table, as a figure (with vision)."""
        r, number, page = self.reading, self.number, self.page
        if not table and r.s.vision:
            said = r.as_figure(number, page, self.displayed, f"t{base}")
            r.record(coverage_row(content=r.content, page=number, bbox=list(native(page, self.displayed)),
                                  task=f"structure:p{number}:{base}:figure", status="complete",
                                  issues=[f"Not read as a table (the model reads none there): {said}"]))
            return
        limit = r.s.rules_from()
        steps = self.derivation
        if step is not None:  # the structure the rows come from, in each claim's derivation
            provisional = DerivationStep(step="pdf-table-detection", detail="row with provisional header")
            steps = [*(self.derivation or [provisional, DerivationStep(step="model-extraction")])]
            steps.insert(len(steps) - 1, step)
        for pi, part in enumerate(parts):
            self.read_part(pi, part, len(parts), base, label, step, steps, limit)
        for i in apart:  # lines the structure rules say aren't the table's: each read by itself
            header_, body_, boxes_ = original
            row_box = boxes_[i] if i < len(boxes_) and boxes_[i] else tuple(self.bbox)
            r.core.table_task(number, tuple(row_box), f"table:p{number}:{base}:x{i}", header_, body_[i],
                              list(range(self.width)), derivation=steps)

    def read_part(self, pi, part, count, base, label, step, steps, limit):
        """One part read as a table, or perhaps as a key-value list (two columns), asked with the table's crop."""
        r, number = self.reading, self.number
        part_header, part_body, part_boxes = part
        # a structure answer's new tables: "+" apart from pdf_parts' ".", or its part 1 ("0.1") would be the tag of
        # pdf_parts' part 1 (code review 2026-10-08, A2)
        tag = base if pi == 0 else f"{base}+{pi}"
        place = f"page {number}, table {self.ti + 1}{label}" + (f", part {pi + 1}" if count > 1 else "")
        # its rows as the rules see them, read so on every path (code review 2026-10-08, B2: rows read by themselves
        # were the raw lines, a wrapped cell's second line lost or read alone)
        ruled = pdf_grid(part_header, part_body, part_boxes, "", place)
        by_itself = partial(self.read_row, tag=tag, header=part_header, body=part_body, body_boxes=part_boxes,
                            ruled=ruled, steps=steps)
        as_table = partial(self.as_table, tag=tag, part_body=part_body, ruled=ruled, by_itself=by_itself, steps=steps,
                           step=step, limit=limit)
        if not keyvalue.candidate(ruled):
            as_table()
            return
        # two columns, perhaps a key-value list, asked with its crop (code review 2026-10-08, B5)
        pairs_boxes = [self.head if pi == 0 and self.head and base == f"{self.ti}" else tuple(self.bbox)] + ruled.boxes
        keyvalue.read(r.core, number, ruled, f"key-value:p{number}:{tag}", pairs_boxes, as_table,
                      partial(self.as_pairs, tag=tag, ruled=ruled, pairs_boxes=pairs_boxes), image=self.image())

    def read_row(self, ri, *, tag, header, body, body_boxes, ruled, steps):
        """One of a part's rows read by itself, as the grid holds it."""
        number = self.number
        row = body[ri]
        row_box = body_boxes[ri] if ri < len(body_boxes) and body_boxes[ri] else tuple(self.bbox)
        if ruled is not None and ri in ruled.joined:  # its lines joined, as the grid holds it
            at = ruled.keys.index(ri)
            row, row_box = ruled.rows[at], ruled.boxes[at]
        # Rows with no content (common where drawing geometry is detected as a
        # table) cost a model call and can't yield a claim.
        if all(c is None or not str(c).strip() for c in row):
            return
        # Exactly repeated rows (same header and cells, same table position) follow their
        # first occurrence from the third sighting on; text is never de-duplicated.
        key = ("table", json.dumps([header, row], ensure_ascii=False, default=str),
               tuple(round(v / 2) * 2 for v in self.bbox))
        self.reading.core.table_task(number, tuple(row_box), f"table:p{number}:{tag}:{ri}", header, row,
                                     list(range(max(self.width, len(header), len(row)))), derivation=steps,
                                     repeat_key=key)

    def as_table(self, checked=None, *, tag, part_body, ruled, by_itself, steps, step, limit):
        """A part read as a table (checked: the key-value check's step, when it was asked)."""
        from . import tablegrid, tablerules
        r, number = self.reading, self.number
        read = by_itself
        if checked is not None:  # the check's step before the model's, in each claim's derivation
            checked_steps = list(steps or DERIVATION["table"])
            checked_steps.insert(len(checked_steps) - 1, checked)
            read = partial(by_itself, steps=checked_steps)
        if ruled is not None and ruled.rows and limit is not None and len(part_body) > limit:
            # asked how it's read, with its image (the one table model)
            detail = "the table's cells, on its grid" + (f"; its structure {step.detail}" if step else "")
            source = DerivationStep(step="pdf-table-detection", detail=detail[:400])
            tablerules.read(r.core, number, ruled, f"rules:p{number}:{tag}", read,
                            source if checked is None else [source, checked], image=self.image())
        elif ruled is not None and ruled.rows:  # without rules: the grid's rows, and possible notes
            for key in ruled.keys + [row.key for row in tablegrid.possible_notes(ruled)]:
                read(key)
        else:
            for ri in range(len(part_body)):
                read(ri)

    def as_pairs(self, checked, context, *, tag, ruled, pairs_boxes):
        """A part read as a key-value list, a key and its value a line, as the model confirmed it."""
        pairs = DerivationStep(step="pdf-table-detection", detail="a key and its value a line")
        self.reading.core.text_task(self.number, list(zip(pairs_boxes, keyvalue.pairs(ruled))),
                                    f"text:p{self.number}:kv{tag}",
                                    derivation=[pairs, checked, DerivationStep(step="model-extraction")],
                                    context=context)

def _pdf_job(path, job, output, client, dispatch, progress):
    """Generator doing one PDF's extraction: yields "page" before feeding each page, then
    "waiting" while its requests are pending; job.state["result"] is set at the end."""
    content, on_sections, state = job.content, job.on_sections, job.state
    s = client.s
    stem = crop_stem(content)
    assets = output / "assets"
    assets.mkdir(exist_ok=True, parents=True)
    name = content if isinstance(path, (bytes, bytearray)) else Path(path).name
    core = TaskCore(job, output, client, dispatch, progress, name, pdf_locator, DERIVATION,
                    oversized="Table row exceeds text budget; inspect visual tiles")

    try:
        opened = pymupdf.open(stream=path, filetype="pdf") if isinstance(path, (bytes, bytearray)) else pymupdf.open(path)
        problem = ("encrypted; it needs to be decrypted before comparison" if opened.needs_pass
                   else "not a nonempty PDF" if not opened.is_pdf or not len(opened) else None)
    except (RuntimeError, ValueError) as error:  # corrupt, or not a PDF at all
        opened, problem = None, f"unreadable ({error})"
    if problem:  # one failed row, and the run goes on with the other documents; the next run tries it again
        if opened is not None:
            opened.close()
        core.record(coverage_row(content=content, task="open", status="failed", issues=[f"{name}: {problem}"]))
        state["result"] = ([], core.coverage)
        return
    with opened as doc:
        sections, owner = pdf_sections(doc, s.section_depth, s.section_pages)
        reading = PdfReading(core, doc, s, content, assets, stem, owner)
        core.reader, core.sections = reading.context_of, owner
        if on_sections:
            on_sections(sections)
        for number, page in enumerate(doc, 1):
            yield "page"
            reading.page(number, page)
        if on_sections:
            on_sections([x.model_copy(update={"signals": reading.signals.get(x.id, {})}) for x in sections])
        while state["pending"]:  # refinement may still render crops from this document
            yield "waiting"
    state["result"] = core.result(lambda r: (r["page"] or 0, r["task"]))
