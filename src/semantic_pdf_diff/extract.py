import contextlib
import json
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from .dispatch import Dispatcher
from .models import DerivationStep, PdfLocator, coverage_row
from .pages import PYMUPDF_ERRORS, lines as _lines, native, native_page, reading_blocks, shown  # noqa: F401 (_lines, for callers)
from .progress import NoProgress
from .regions import crop_name, crop_stem, region_of
# The pieces extraction is made of (architecture clean-up, milestone 7), and the names callers import from here.
from .context import CONTEXT_NOTE, LEVER_MARKS, Context, lever_notes  # noqa: F401
from .quotes import FOLD, covered, excerpted, quoted  # noqa: F401
from .sections import SectionIndex, heading_y, pdf_sections, section_text  # noqa: F401
from .segmentation import grown, sheet_details, tiles  # noqa: F401
from .stems import _long_form, glossary, stem_index  # noqa: F401
from .tables import (Marks, column_edges, cut_columns, pdf_grid, pdf_parts, real_table,  # noqa: F401
                     row_boxes, ruled_rows, same_form, split_cuts)
from .tasks import MIN_REFINE_BYTES, TaskCore, split_utf8, union  # noqa: F401 (callers import them from here)

# Bump when prompt assembly or task construction changes, not only the template text;
# it is part of the extraction interpreter. 2: section heading path in prompts.
# 3: exactly repeated table rows follow their first occurrence. 4: claims per request configurable.
# 5: headings by position on the page; table rows located by their own box.
# 6: rules for unfamiliar charts, attributes free of conditions, parts of a whole; figure tasks.
PROMPT_VERSION = 6

EXTRACT = '''Extract atomic engineering claims from this one source. Return JSON:
{"claims":[{"entity":"component/system", "attribute":"property or directed relationship",
"value":"literal value or target", "unit":"literal unit or empty", "conditions":"load, scenario, time, tolerances, scope",
"kind":"text|table|chart|diagram", "quote":"short exact supporting text or visible labels",
"confidence":0.0, "approximate":false}], "complete":true, "issues":[]}
Maximum {max_claims} claims. Set complete=false if content is clipped, ambiguous, unreadable, or more claims remain.
For tables associate row labels, column headers and units. For charts preserve series, axes, units,
operating point and trend; estimated plotted readings MUST be approximate. For diagrams extract
labeled components and directed connections; never invent direction on unmarked edges.
Preserve negation, requirements versus proposed capabilities, ranges and inequality signs.
Extract evidence only, not commentary. Use a short canonical entity and attribute; keep numeric value separate from unit.
The attribute names the property only: put conditions (e.g. "at theta = 0", "at rated speed") in conditions.
If a value is one of several parts (one layer, one material, one member), say what it is part of in the attribute
(e.g. "spar cap material"), not "composition".
If you are not sure how to read a chart, diagram or drawing convention, say so in issues, lower confidence, and mark
readings approximate; do not guess what an unexplained symbol, colour or line style means.
'''

@dataclass(frozen=True)
class ExtractQuery:
    """An extraction request's text in parts: the one owner of its layout (code review 2026-10-01, A1: prompts were
    assembled inline and parsed back at markers in three places). prompt() is the bytes sent; read() takes a logged
    prompt back into its parts, so no reader splits at markers of its own."""
    instructions: str  # the template with its claim cap filled, then the rules (the configuration's, the region's)
    region: str
    heading: str = ""  # the headings the region falls under
    context: str = ""  # CONTEXT_NOTE and the levers' lines
    data: str = ""     # the source data: text, a table row, or an image task's note and text layer
    continuation: str = ""  # CONTINUATION_NOTE and the claims earlier requests for this task returned

    def prompt(self):
        return (self.instructions + "\nSource type: " + self.region + (f"\nSection: {self.heading}" if self.heading else "")
                + (f"\n{self.context}" if self.context else "")
                + (f"\n{self.continuation}" if self.continuation else "") + "\nSOURCE DATA:\n" + self.data)

    @property
    def request(self):
        """The part after the instructions: what this task, not every task, was given."""
        return self.prompt()[len(self.instructions) + 1:]

    @classmethod
    def read(cls, prompt):
        instructions, _, rest = prompt.partition("\nSource type: ")
        head, _, data = rest.partition("\nSOURCE DATA:\n")
        region, _, tail = head.partition("\n")
        heading = ""
        if tail.startswith("Section: "):
            heading, _, tail = tail[len("Section: "):].partition("\n")
        context, mark, continued = tail.partition(CONTINUATION_NOTE)
        return cls(instructions, region, heading, context.rstrip("\n") if mark else tail, data,
                   mark + continued if mark else "")

# What a continued request is told (tasks.TaskCore.consume): the claims returned so far, not to be repeated.
CONTINUATION_NOTE = ("ALREADY EXTRACTED from this same source by an earlier request (do not repeat these; extract the "
                     "claims that remain):")

def continuation(claims):
    """A continued request's note: the claims earlier requests returned, one a line, by entity, attribute and value
    only: enough not to repeat them, and conditions listed were copied onto the claims that followed (a valve's
    stroke time given the "rated point" of the flow coefficients listed before it)."""
    rows = [" | ".join(x for x in (c.entity, c.attribute, f"{c.value} {c.unit}".strip()) if x) for c in claims]
    return CONTINUATION_NOTE + "".join("\n- " + r for r in rows)

def extraction_template(s):
    """The extraction instructions in force: the baseline, or a variant's (with {max_claims} unfilled)."""
    return s.instructions(EXTRACT)

# Visual refinement stops at crops narrower than this (PDF points).
MIN_REFINE_POINTS = 100

def render(page, rect, target, max_side):
    # clip is in rotated page coordinates, as used by Page.get_pixmap.
    scale = min(2.5, max_side / max(rect.width, rect.height))
    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=rect, alpha=False).save(target)

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

def page_signals(page, tables):
    """Cheap triage signals for one page; summed per section."""
    text = page.get_text("text")
    drawings = page.get_cdrawings()
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

@dataclass
class Job:
    """Extraction of one PDF content item, fed a page at a time by run_jobs."""
    content: str
    load: object                     # () -> path or bytes, called when the job starts
    on_task: object = None           # (row, evidence) as each task finishes
    on_sections: object = None       # (sections) once known
    on_done: object = None           # (evidence, coverage) when the job is complete
    state: dict = field(default_factory=lambda: {"pending": 0, "result": None})
    steps: object = None
    reader: object = None            # the job's generator by format (reader_for); None: a PDF

def run_jobs(queues, output, client, dispatcher=None, progress=None):
    """Run extraction jobs with fair share: one queue per source, pages fed round-robin
    across sources so compared sources advance together.

    Model requests run on the dispatcher's worker threads; everything else here. A job
    whose pages are all fed keeps its document open until its own pending requests
    (which may queue refinement) finish, while its source moves on to the next job.
    """
    own = dispatcher is None
    dispatch = dispatcher or Dispatcher(client)
    # Pages are fed only while few requests are pending, so prepared requests
    # (which hold image data) stay bounded however large the documents.
    bound = max(4, 2 * dispatch.workers)
    queues = [deque(q) for q in queues]
    active, draining = [None] * len(queues), []

    def done(job):
        if job.on_done:
            job.on_done(*job.state["result"])

    with (dispatch if own else contextlib.nullcontext()):
        while True:
            fed = False
            for i, queue in enumerate(queues):
                # Each source feeds one page per turn; a job that has run out of pages
                # hands over to the source's next job within the same turn.
                while True:
                    if active[i] is None and queue:
                        job = queue.popleft()
                        try:
                            loaded = job.load()
                        except OSError as error:  # moved or unreadable since the scan: one failed row, retried
                            job.steps = _unloadable(job, error)
                        else:
                            job.steps = (job.reader or _pdf_job)(loaded, job, output, client, dispatch,
                                                                 progress or NoProgress())
                        active[i] = job
                    job = active[i]
                    if job is None:
                        break
                    while dispatch.pending() >= bound:
                        dispatch.wait_one()
                    step = next(job.steps, "done")
                    fed = True
                    if step == "page":
                        break
                    active[i] = None
                    if step == "waiting":
                        draining.append(job)
                    else:
                        done(job)
            for job in list(draining):
                if job.state["pending"] == 0 and next(job.steps, "done") == "done":
                    draining.remove(job)
                    done(job)
            if not fed:
                if not draining and not any(queues) and not any(active):
                    break
                if not dispatch.pending():
                    raise RuntimeError("extraction scheduler stalled: jobs wait on requests that aren't pending")
                dispatch.wait_one()

def _unloadable(job, error):
    """The steps of a job whose content can't be loaded: an "open" row, failed (code review 2026-10-08, C1: a file
    moved since the scan aborted the run)."""
    row = coverage_row(content=job.content, task="open", status="failed",
                       issues=[f"unreadable ({type(error).__name__}: {error})"])
    if job.on_task:
        job.on_task(row, [])
    job.state["result"] = ([], [row])
    return
    yield  # a generator, as a reader's steps are

# Readers by normalized extension (the adapters plan: chosen by extension only, no sniffing).
TEXT_EXTENSIONS = (".txt", ".md", ".docx", ".pptx", ".xlsx", ".xlsm", ".csv", ".tsv")
# Images read as one-page documents (a TIFF's frames as pages) by the PDF reader's vision tasks (image_pdf)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif")
SCAN_DPI = 150  # an image recording this resolution or more is a scan: it keeps its paper size

def office_installed(workbook=False):
    """Whether the office extra's libraries are installed: python-docx (and with workbook, openpyxl)."""
    try:
        import docx  # noqa: F401
        if workbook:
            import openpyxl  # noqa: F401
    except ImportError:
        return False
    return True

# Each reader's version: raised whenever what it sends the model changes without a setting or prompt changing (its
# parsing, its tasks). A store re-reads content its reader has changed since; unchanged queries replay from cache.
READERS = {".pdf": "pdf/6",  # pdf/2: tables asked how they're read; 3: two-line headers merged, stacked tables split;
           # 4: a part the model reads as no table read as a figure; 5: columns joined where words are cut; 6: a
           # structure answer's new tables tagged apart, a structure asked again recorded once (review A2, B7)
           ".txt": "text/2", ".md": "text/1",  # text/2: "A pump ..." isn't a heading (review B4)
           ".docx": "docx/6",  # docx/2: equations, comments; docx/3: tables asked how they're read; 4-5: headers;
           # 6: late table answers on their own page, pictures sharing a line tagged apart (review B1, A1)
           ".pptx": "pptx/5",  # pptx/2: tables asked how they're read; 3-4: a header's name and group; 5: as docx/6
           ".xlsx": "xlsx/10", ".xlsm": "xlsx/10",  # xlsx/7: vague conditions guarded against; 8-9: header name,
           # group; 10: late table answers on their own sheet (review B1)
           ".csv": "csv/6", ".tsv": "csv/6",  # csv/6: as xlsx/10
           **{extension: "image/1" for extension in IMAGE_EXTENSIONS}}

def reader_version(extension):
    """The version of what reads content of this extension ("docx/1"); "unsupported" where nothing reads it yet."""
    return READERS.get(extension, "unsupported") if reader_for(extension) is not None else "unsupported"

def reader_for(extension):
    """The job generator reading content of this extension, or None if none reads it (a .docx needs the office
    extra)."""
    if extension == ".pdf":
        return _pdf_job
    if extension in IMAGE_EXTENSIONS:
        return lambda data, job, output, client, dispatch, progress: _pdf_job(
            image_pdf(data, extension, client.s), job, output, client, dispatch, progress)
    if extension in TEXT_EXTENSIONS and (extension not in (".docx", ".pptx", ".xlsx", ".xlsm") or
                                         office_installed(workbook=extension in (".xlsx", ".xlsm"))):
        from .textdocs import text_job
        return lambda data, job, output, client, dispatch, progress: text_job(data, job, output, client, dispatch,
                                                                              progress, extension)
    return None

def image_pdf(data, extension, settings):
    """An image (a path or its bytes) as a PDF's bytes, a page per frame, for the PDF reader: no text layer, so its
    vision tasks read it. A scan recording SCAN_DPI or more keeps its paper size; any other image (a screenshot, a
    photo, one without a resolution, which reads as 96 dpi) is laid out so a tile (tile_points) shows its pixels one
    to one at image_side. b"" if it can't be read (recorded as unreadable)."""
    try:
        data = data if isinstance(data, (bytes, bytearray)) else Path(data).read_bytes()
        with pymupdf.open(stream=data, filetype=extension.lstrip(".")) as frames:
            dpi = pymupdf.Pixmap(data).xres or 96
            per_point = 1.0 if dpi >= SCAN_DPI else dpi / 72 * settings.tile_points / settings.image_side
            with pymupdf.open("pdf", frames.convert_to_pdf()) as pages, pymupdf.open() as out:
                for number, page in enumerate(pages):
                    rect = page.rect * per_point  # the frame's own size, in points of the page it becomes
                    out.new_page(width=rect.width, height=rect.height).show_pdf_page(
                        pymupdf.Rect(0, 0, rect.width, rect.height), pages, number)
                return out.tobytes()
    except (OSError, *PYMUPDF_ERRORS):  # an image PyMuPDF can't decode, or a file gone
        return b""

def extract_pdf(path, content, output, client, on_task=None, on_sections=None, dispatcher=None, progress=None):
    """Extract evidence from one PDF (a path or its bytes), identified by its content ID.

    Returns (evidence, coverage), both independent of the order in which tasks finish.
    on_task(row, evidence) is called as each task finishes, so a store can persist
    results task by task; on_sections(sections) is called once sections are known.
    """
    job = Job(content, lambda: path, on_task, on_sections)
    run_jobs([[job]], output, client, dispatcher, progress)
    return job.state["result"]

class Visuals:
    """Image tasks over a page's regions, for the PDF job and a Word document's pictures (pictures.py): the region
    rendered to a crop, its text layer a check on quotes and, by region_text, context; its context lines (for_tile);
    a partial tile refined in halves.

    A PDF's claims are located in the region and placed in their section by the text block quoting them. A Word
    picture's are at its paragraph: `box`, the locator's box and the section's place both; its caption (`text`)
    stays with the halves a tile is refined into (`derivation`: its steps, the region's otherwise)."""
    def __init__(self, core, context_of, assets, stem, settings):
        self.core, self.context_of, self.assets, self.stem, self.s = core, context_of, assets, stem, settings

    def task(self, page_no, page, tag, rect, depth=0, text="", box=None, derivation=None):
        s = self.s
        name = crop_name(self.stem, tag)
        render(page, rect, self.assets / name, s.image_side)
        native_rect = native(page, rect)
        layer = page.get_text("text", clip=native_rect)
        check = (lambda q: covered(q, layer, fold=True)) if layer.strip() else None
        if box is None:
            blocks = [(tuple(b[:4]), b[4]) for b in page.get_text("blocks", clip=native_rect) if b[6] == 0]

            def place(quote):  # the first text block in the region holding the quote
                return next((found for found, text in blocks if covered(quote, text, fold=True)), None)
        else:
            def place(quote):
                return box
        source = s.region_text(self.context_of, page, rect, layer, text)
        context, extra = self.context_of.for_tile(page, rect, tag)
        kept = text if box is not None else ""
        self.core.consume(page_no, native_rect if box is None else box, tag, source, "assets/" + name, check=check,
                          place=place, crop=(tuple(round(v, 3) for v in rect), s.image_side), context=context,
                          extra_images=extra, derivation=derivation,
                          then=lambda status: self.refine(page_no, page, tag, rect, depth, status, kept, box, derivation))

    def refine(self, page_no, page, tag, rect, depth, status, text, box, derivation):
        # Refine only local tiles; an overview or a whole figure may be incomplete because
        # it spans many facts, and all its areas already have tile coverage.
        s = self.s
        if (status not in ("partial", "failed") or region_of(tag) in ("overview", "figure") or depth >= s.refinement_depth
                or min(rect.width, rect.height) < MIN_REFINE_POINTS):
            return
        if rect.width > rect.height:
            mid = (rect.x0 + rect.x1) / 2
            children = [pymupdf.Rect(rect.x0, rect.y0, mid + 12, rect.y1), pymupdf.Rect(mid - 12, rect.y0, rect.x1, rect.y1)]
        else:
            mid = (rect.y0 + rect.y1) / 2
            children = [pymupdf.Rect(rect.x0, rect.y0, rect.x1, mid + 12), pymupdf.Rect(rect.x0, mid - 12, rect.x1, rect.y1)]
        for i, child in enumerate(children):
            self.task(page_no, page, f"{tag}-r{i}", child, depth + 1, text, box, derivation)

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
    record = core.record

    try:
        opened = pymupdf.open(stream=path, filetype="pdf") if isinstance(path, (bytes, bytearray)) else pymupdf.open(path)
        problem = ("encrypted; it needs to be decrypted before comparison" if opened.needs_pass
                   else "not a nonempty PDF" if not opened.is_pdf or not len(opened) else None)
    except (RuntimeError, ValueError) as error:  # corrupt, or not a PDF at all
        opened, problem = None, f"unreadable ({error})"
    if problem:  # one failed row, and the run goes on with the other documents; the next run tries it again
        if opened is not None:
            opened.close()
        record(coverage_row(content=content, task="open", status="failed", issues=[f"{name}: {problem}"]))
        state["result"] = ([], core.coverage)
        return
    with opened as doc:
        context_of = Context(doc, s, assets, stem)  # the task functions read it when they run
        visuals = Visuals(core, context_of, assets, stem, s)
        sections, owner = pdf_sections(doc, s.section_depth, s.section_pages)
        core.reader, core.sections = context_of, owner
        if on_sections:
            on_sections(sections)
        signals = {}
        regions = {}  # page -> its image tasks' regions, worked out once (the vision loop; tables read as figures)

        def regions_of(number, page):
            if number not in regions:
                regions[number] = list(s.visual_regions(context_of, page, number))
            return regions[number]

        def as_figure(number, page, rect, tag):
            """A region parsed as a table that the model reads as no table (a chart, a floor plan): read by a figure
            task, unless the overview, a figure task or one tile already sees it whole. What happened, in words."""
            if abs(rect & page.rect) >= 0.9 * abs(page.rect):
                return "seen whole by the page's overview"
            for region_tag, region, _ in regions_of(number, page):
                kind = region_tag.partition(":")[0]
                if kind == "figure" and abs(region & rect) >= 0.8 * abs(rect):
                    return "seen whole by a figure task"
                if kind == "tile" and region.contains(rect):
                    return "seen whole by a tile"
            visuals.task(number, page, f"figure:p{number}:{tag}", rect, derivation=[
                DerivationStep(step="pdf-render", detail="a region parsed as a table, read as a figure (the model "
                                                         "reads no table there)"),
                DerivationStep(step="model-extraction", detail="vision")])
            return "read by a figure task"

        # (header, width) of a table that ended near the bottom of the previous page
        carried = None
        for number, page in enumerate(doc, 1):
            yield "page"
            # Native coordinates stay unrotated (PDF point coordinates). Consecutive
            # blocks are grouped up to the byte budget; oversized blocks are split.
            for ids, segments in text_groups(page, s.text_bytes, lambda b, n=number: owner.box(n, b).id):
                core.text_task(number, segments, f"text:p{number}:{ids}")
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
                if not s.keep_table(context_of, page, table, rows):
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
            height = page.rect.height
            continuing, carried = carried, None
            context_of.tables_on[number] = [found_[0] for found_ in found]
            for ti, (bbox, rows, boxes, styles, rules, edges) in enumerate(found):
                if not rows:
                    continue
                displayed = shown(page, bbox)  # continuation is judged as displayed
                header, body, derivation = rows[0], rows[1:] or rows, None
                body_boxes = boxes[1:] if len(rows) > 1 else boxes
                body_styles = None if styles is None else styles[1:] if len(rows) > 1 else styles
                width = max(len(r) for r in rows)
                # A table at the top of a page, as wide as one that ended at the bottom of the
                # previous page, continues it, unless its first row is a header of the same
                # form (a new table, e.g. the next day's schedule). An identical first row is
                # a repeated header and is skipped.
                if (ti == 0 and continuing and continuing[1] == width and displayed.y0 - page.rect.y0 < 0.2 * height
                        and (rows[0] == continuing[0] or not same_form(rows[0], continuing[0]))):
                    if rows[0] != continuing[0]:
                        body, body_boxes, body_styles = rows, boxes, styles
                    header = continuing[0]
                    derivation = [DerivationStep(step="pdf-table-detection",
                                                 detail=f"row with header continued from page {number - 1}"),
                                  DerivationStep(step="model-extraction")]
                # Repaired into parts: a header over two lines merged, stacked tables split (tables.pdf_parts).
                parts = pdf_parts(header, body, body_boxes, body_styles)
                look = {tuple(b): st for b, st in zip(body_boxes, body_styles or []) if b and st is not None}
                crop = []

                def image(ti=ti, displayed=displayed, page=page, crop=crop, number=number):
                    if not crop:
                        crop.append(crop_name(stem, f"rules:p{number}:{ti}"))
                        render(page, displayed, assets / crop[0], s.image_side)
                    return f"assets/{crop[0]}"

                def proceed(parts, step, apart, base, original, label, table=True, ti=ti, bbox=bbox, width=width,
                            derivation=derivation, image=image, number=number, page=page, displayed=displayed):
                    """Each part read: by rules where tables are, else row by row; lines apart read by themselves; a
                    part the model reads as no table, as a figure (with vision)."""
                    if not table and s.vision:
                        said = as_figure(number, page, displayed, f"t{base}")
                        record(coverage_row(content=content, page=number, bbox=list(native(page, displayed)),
                                            task=f"structure:p{number}:{base}:figure", status="complete",
                                            issues=[f"Not read as a table (the model reads none there): {said}"]))
                        return
                    limit = s.rules_from()
                    steps = derivation
                    if step is not None:  # the structure the rows come from, in each claim's derivation
                        steps = [*(derivation or [DerivationStep(step="pdf-table-detection",
                                                                 detail="row with provisional header"),
                                                  DerivationStep(step="model-extraction")])]
                        steps.insert(len(steps) - 1, step)
                    for pi, (part_header, part_body, part_boxes) in enumerate(parts):
                        # a structure answer's new tables: "+" apart from pdf_parts' ".", or its part 1 ("0.1") would be
                        # the tag of pdf_parts' part 1 (code review 2026-10-08, A2)
                        tag = base if pi == 0 else f"{base}+{pi}"

                        def by_itself(ri, tag=tag, header=part_header, body=part_body, body_boxes=part_boxes):
                            row = body[ri]
                            # Rows with no content (common where drawing geometry is detected as a
                            # table) cost a model call and can't yield a claim.
                            if all(c is None or not str(c).strip() for c in row):
                                return
                            # Exactly repeated rows (same header and cells, same table position) follow their
                            # first occurrence from the third sighting on; text is never de-duplicated.
                            key = ("table", json.dumps([header, row], ensure_ascii=False, default=str),
                                   tuple(round(v / 2) * 2 for v in bbox))
                            row_box = body_boxes[ri] if ri < len(body_boxes) and body_boxes[ri] else tuple(bbox)
                            core.table_task(number, tuple(row_box), f"table:p{number}:{tag}:{ri}", header, row,
                                            list(range(max(width, len(header), len(row)))), derivation=steps,
                                            repeat_key=key)

                        place = f"page {number}, table {ti + 1}{label}" + (f", part {pi + 1}" if len(parts) > 1 else "")
                        ruled = pdf_grid(part_header, part_body, part_boxes, "", place) \
                            if limit is not None and len(part_body) > limit else None
                        if ruled is not None and ruled.rows:  # asked how it's read, with its image (the one table model)
                            from . import tablerules
                            detail = "the table's cells, on its grid" + (f"; its structure {step.detail}" if step else "")
                            tablerules.read(core, number, ruled, f"rules:p{number}:{tag}", by_itself,
                                            DerivationStep(step="pdf-table-detection", detail=detail[:400]),
                                            image=image())
                        else:
                            for ri in range(len(part_body)):
                                by_itself(ri)
                    for i in apart:  # lines the structure rules say aren't the table's: each read by itself
                        header_, body_, boxes_ = original
                        row_box = boxes_[i] if i < len(boxes_) and boxes_[i] else tuple(bbox)
                        core.table_task(number, tuple(row_box), f"table:p{number}:{base}:x{i}", header_, body_[i],
                                        list(range(width)), derivation=steps)

                for pi, (part_header, part_body, part_boxes) in enumerate(parts):
                    base = f"{ti}" if pi == 0 else f"{ti}.{pi}"
                    label = f", part {pi + 1}" if len(parts) > 1 else ""
                    if s.asks_structure():  # a part with suspect lines asked how they group into rows
                        from . import tablestructure
                        cuts = None
                        if marks is not None and edges:  # words a column line splits, by line (0: the header)
                            cuts = {i + 1: split_cuts(r, b, edges, marks) for i, (r, b) in
                                    enumerate(zip(part_body, part_boxes))}
                            if pi == 0 and header is rows[0] and boxes:
                                cuts[0] = split_cuts(header, boxes[0], edges, marks)
                        tablestructure.read(
                            core, number, f"structure:p{number}:{base}", part_header, part_body, part_boxes,
                            [look.get(tuple(b)) if b else None for b in part_boxes] if look else None,
                            rules, lambda image=image: [image()],
                            # bound now: the answer may come when the loop is pages further on
                            lambda parts_, step, apart, table, base=base, label=label, proceed=proceed,
                            original=(part_header, part_body, part_boxes): proceed(parts_, step, apart, base, original,
                                                                                   label, table), cuts)
                    else:
                        proceed([(part_header, part_body, part_boxes)], None, [], base, None, label)
                if displayed.y1 - page.rect.y0 > 0.8 * height:
                    carried = (header, width)
                else:
                    carried = None
            section = owner[number].id
            for name_, value in page_signals(page, len(found)).items():
                signals.setdefault(section, {}).setdefault(name_, 0)
                signals[section][name_] += value
            if s.vision:
                for tag, rect, note in regions_of(number, page):
                    # Task tags are unique within content: "<region>:p<page>[:<index>]".
                    region, _, index = tag.partition(":")
                    tag = f"{region}:p{number}" + (f":{index}" if index else "")
                    # A figure's caption, or a sheet detail's titles, as source text.
                    visuals.task(number, page, tag, rect, text=note)
            else:
                record(coverage_row(content=content, page=number, bbox=list(native_page(page)), task=f"vision:p{number}",
                                    status="skipped",
                                    issues=["Visual extraction disabled; charts, diagrams and scans may be missed"]))
        if on_sections:
            on_sections([x.model_copy(update={"signals": signals.get(x.id, {})}) for x in sections])
        while state["pending"]:  # refinement may still render crops from this document
            yield "waiting"
    state["result"] = core.result(lambda r: (r["page"] or 0, r["task"]))
