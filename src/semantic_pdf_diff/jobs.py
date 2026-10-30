"""Extraction jobs: the scheduler feeding every source's documents a page at a time (run_jobs), and the readers by
extension with their versions. Split from extract.py (code review 2026-10-08, A12).
"""
import contextlib
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from .dispatch import Dispatcher
from .extract import _pdf_job
from .pages import PYMUPDF_ERRORS
from .progress import NoProgress, working
from .schema import coverage_row

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
    label: str = ""                  # its name on a progress bar (its file's); the content's without
    bar: object = None               # its source's bar of files, if it has one
    terms: object = None             # its content's glossary (terms.Terms), for the reader_glossary lever

def run_jobs(queues, output, client, dispatcher=None, progress=None, labels=()):
    """Run extraction jobs with fair share: one queue per source, pages fed round-robin
    across sources so compared sources advance together.

    Model requests run on the dispatcher's worker threads; everything else here. A job
    whose pages are all fed keeps its document open until its own pending requests
    (which may queue refinement) finish, while its source moves on to the next job.

    progress: a bar of files for each source of more than one (labels: the sources' names); each reader shows its
    file's pages.
    """
    own = dispatcher is None
    dispatch = dispatcher or Dispatcher(client)
    progress = progress or NoProgress()
    queues = [deque(q) for q in queues]
    for i, queue in enumerate(queues):
        if len(queue) > 1:
            bar = progress.bar(labels[i] if i < len(labels) else f"source {i + 1}", len(queue), "files")
            for job in queue:
                job.bar = bar
    active, draining = [None] * len(queues), []

    def done(job):
        if job.on_done:
            job.on_done(*job.state["result"])
        if job.bar is not None:
            job.bar.tick()

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
                            job.steps = (job.reader or _pdf_job)(loaded, job, output, client, dispatch, progress)
                        active[i] = job
                    job = active[i]
                    if job is None:
                        break
                    dispatch.make_room()  # pages fed only while few requests are pending
                    step = next(job.steps, "done")
                    working(None)  # what a reader asks between its steps is its page's, not the next reader's
                    fed = True
                    if step == "page":
                        break
                    active[i] = None
                    if step == "waiting":
                        draining.append(job)
                    else:
                        done(job)
            for job in list(draining):
                if job.state["pending"] == 0:
                    step = next(job.steps, "done")
                    working(None)
                    if step == "done":
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

# Readers by normalized extension, chosen by extension only, never by sniffing content (decision 0002).
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
READERS = {".pdf": "pdf/11",  # pdf/2: tables asked how they're read; 3: two-line headers merged, stacked tables split;
           # 4: a part the model reads as no table read as a figure; 5: columns joined where words are cut; 6: a
           # structure answer's new tables tagged apart, a structure asked again recorded once (review A2, B7); 7: rows
           # read by themselves as the grid holds them, notes confirmed and read, the structure rules' union said (B2);
           # 8: a table of two columns asked whether it's a key-value list (B5); 9: a partial tile refined in halves
           # cut between lines or columns, grown to whole lines, its text by whole lines (trials finding 5); 10: a
           # section row right under the header kept a row, not the header's next line; 11: claims marked on their
           # crops, a rules task's rows recording its table's crop (portable reports, milestone 4; the owner,
           # 2026-10-20: "Yes, update the version.")
           ".txt": "text/2", ".md": "text/1",  # text/2: "A pump ..." isn't a heading (review B4)
           ".docx": "docx/9",  # docx/2: equations, comments; docx/3: tables asked how they're read; 4-5: headers;
           # 6: late table answers on their own page, pictures sharing a line tagged apart (review B1, A1); 7: a
           # table's notes confirmed and read, its rows without rules read from its grid (review B2); 8: as pdf/8; 9: a
           # picture's partial tiles refined as pdf/9
           ".pptx": "pptx/8",  # pptx/2: tables asked how they're read; 3-4: a header's name and group; 5: as docx/6;
           # 6: as docx/7; 7: as docx/9; 8: as docx/8 (a table of two columns asked whether it's a key-value list)
           ".xlsx": "xlsx/12", ".xlsm": "xlsx/12",  # xlsx/7: vague conditions guarded against; 8-9: header name,
           # group; 10: late table answers on their own sheet (review B1); 11: as docx/7; 12: as docx/8
           ".csv": "csv/8", ".tsv": "csv/8",  # csv/6: as xlsx/10; csv/7: as xlsx/11; csv/8: as xlsx/12
           **{extension: "image/2" for extension in IMAGE_EXTENSIONS}}  # image/2: as pdf/11

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
        from .textjob import text_job
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
