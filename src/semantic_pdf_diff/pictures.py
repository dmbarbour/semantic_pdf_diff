"""A Word document's pictures, read as a PDF's figures are (docs/plans/multi-format-adapters-2026-09-23.md, "Pictures
in Word documents"; the owner: "we'll want similar context as what PDF pics get", and "Every pic.").

Each picture becomes a page of a pictures document, at its displayed size: an EMF or WMF drawn by metafiles.py
(vector, its labels a text layer), a raster image as it is. The page gets a PDF page's image tasks (visual_regions:
the whole picture, and tiles when it's large; extract.Visuals), each with the picture's caption as its source text,
the page's text layer as a check on quotes and as context, and its section's headings. Its claims are located at the
picture's paragraph (DocxLocator), each with the crop it was read from.
"""
import re
from collections import Counter

import pymupdf

from .models import DerivationStep, coverage_row

METAFILES = (".emf", ".wmf")
RASTER = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")
RASTER_DPI = 96  # a raster picture without a displayed size is shown at this resolution

class PictureError(Exception):
    """A picture that can't be drawn into a page (its reason is recorded in the coverage)."""

def page_of(picture):
    """A one-page PDF of a picture at its displayed size (raises PictureError)."""
    extension, size = picture.extension, picture.size
    if extension in METAFILES:
        try:
            from .metafiles import draw
        except ImportError as error:  # Pillow or pyclipper missing
            raise PictureError(f"needs the office extra (pip install 'semantic-pdf-diff[office]'): {error}") from error
        try:
            source = pymupdf.open("pdf", draw(picture.data).pdf)
        except Exception as error:  # the vendored renderer's MetafileError, or a malformed file
            raise PictureError(f"{picture.name}: not drawn ({type(error).__name__}: {error})") from error
    elif extension in RASTER:
        try:
            image = pymupdf.open(stream=picture.data, filetype=extension[1:])
            pixels = image[0].rect
            source = pymupdf.open("pdf", image.convert_to_pdf())
        except Exception as error:
            raise PictureError(f"{picture.name}: unreadable image ({type(error).__name__}: {error})") from error
        if not size:
            size = (pixels.width * 72 / RASTER_DPI, pixels.height * 72 / RASTER_DPI)
    else:
        raise PictureError(f"{picture.name}: a picture of a kind not read ({extension})")
    width, height = size if size and size[0] > 1 and size[1] > 1 else (source[0].rect.width, source[0].rect.height)
    out = pymupdf.open()
    out.new_page(width=width, height=height).show_pdf_page(pymupdf.Rect(0, 0, width, height), source, 0)
    return out

class Reading:
    """A Word document's pictures being read: the pictures document (each picture a page, open until their tasks are
    done; refinement renders from it later) and each picture's own words, for the label check (labels())."""
    def __init__(self, kind="docx"):
        self.doc, self.kind = pymupdf.open(), kind  # kind: the document's format ("docx", "pptx")
        self.words = {}  # a picture's line: (its page, the words of its text layer)

    def tasks(self, core, settings, pictures, content, output):
        """Generator feeding each picture's image tasks, yielding "page" between pictures (fair share). Every picture
        is drawn into the document before any task is fed: adding a page invalidates the pages loaded before it, and
        a tile refined later renders from its page."""
        from .extract import Context, Visuals
        from .regions import crop_stem
        s, doc = settings, self.doc
        assets = output / "assets"
        assets.mkdir(exist_ok=True, parents=True)
        stem = crop_stem(content)
        context_of = Context(doc, s, assets, stem)
        visuals = Visuals(core, context_of, assets, stem, s)
        drawn_pages = []  # (picture, its name in tags, its page's number)
        for picture, ident in zip(pictures, picture_idents(pictures)):
            yield "page"
            box = (0.0, float(picture.line), 1.0, float(picture.line + 1))
            task = f"picture:p{picture.page}:{ident}"
            if not s.vision:
                core.record(coverage_row(content=content, page=picture.page, bbox=list(box), task=task, status="skipped",
                                         issues=["Visual extraction disabled; pictures aren't read"]))
                continue
            try:
                single = page_of(picture)
            except PictureError as error:
                core.record(coverage_row(content=content, page=picture.page, bbox=list(box), task=task, status="skipped",
                                         issues=[str(error)]))
                continue
            doc.insert_pdf(single)
            drawn_pages.append((picture, ident, len(doc)))
        for picture, ident, number in drawn_pages:
            yield "page"
            box = (0.0, float(picture.line), 1.0, float(picture.line + 1))
            page = doc[number - 1]
            self.words[(picture.page, ident)] = (picture.line, words(page.get_text()))
            drawn = "a metafile drawn as vector" if picture.extension in METAFILES else "an image"
            note = f"Caption: {picture.caption}" if picture.caption else ""
            for tag, rect, _ in s.visual_regions(context_of, page, number):
                region, _, index = tag.partition(":")
                tag = f"{region}:p{picture.page}:pic{ident}" + (f":{index}" if index else "")
                derivation = [DerivationStep(step=f"{self.kind}-picture", detail=f"{picture.name}, {drawn}"),
                              DerivationStep(step="picture-region", detail=region),
                              DerivationStep(step="model-extraction")]
                visuals.task(picture.page, page, tag, rect, text=note, box=box, derivation=derivation)

    def labels(self, core, content):
        """The label check, a coverage row per picture with a text layer ("labels:p1:pic<line>"): the share of the
        picture's own words that some claim read from it mentions, and those none does. A quality measure,
        never applied: a low share says the picture may be read incompletely (the owner: "better applied as a
        quality and confidence check")."""
        said = {}
        for e in core.evidence:
            mentions = words(" ".join((e.entity, e.attribute, e.value, e.unit, e.conditions, e.quote)))
            for o in e.occurrences or [e]:
                match = PICTURE_TASK.search(o.locator.task)
                if match:
                    said.setdefault((int(match.group(1)), match.group(2)), set()).update(mentions)
        for (page, ident), (line, own) in sorted(self.words.items(), key=lambda x: (x[0][0], x[1][0], x[0][1])):
            if len(own) < MIN_LABEL_WORDS:
                continue
            missing = sorted(own - said.get((page, ident), set()))
            share = 1 - len(missing) / len(own)
            note = f"Label coverage {share:.0%}: {len(missing)} of the picture's {len(own)} words in no claim"
            core.record(coverage_row(content=content, page=page, bbox=[0.0, float(line), 1.0, float(line + 1)],
                                     task=f"labels:p{page}:pic{ident}", status="complete",
                                     issues=[note + (f" ({', '.join(missing[:LISTED])})" if missing else "")]))

    def close(self):
        self.doc.close()

PICTURE_TASK = re.compile(r":p(\d+):pic(\d+(?:\.\d+)?)")  # a picture's page and name in a task's tag

def picture_idents(pictures):
    """Each picture's name in its tasks' tags: its line ("pic12"), and after the first picture at a line (two in one
    paragraph, or in one table row) an ordinal too ("pic12.1"), so tags stay distinct and the first keeps its old
    tag (code review 2026-10-08, A1: the second picture's crops and claims replaced the first's)."""
    seen, out = Counter(), []
    for picture in pictures:
        n = seen[(picture.page, picture.line)]
        seen[(picture.page, picture.line)] += 1
        out.append(f"{picture.line}" + (f".{n}" if n else ""))
    return out
WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-]{2,}")
MIN_LABEL_WORDS = 3   # a picture with fewer words of its own isn't checked
LISTED = 15           # the uncovered words a row lists

# Words that label nothing: a figure's sentences ("the following steps are the same") aren't labels to be covered
FUNCTION_WORDS = frozenset(
    "the and are for from with that this these those not but all any can may its into than then them they was were "
    "has have had will shall should would could been being each per via also only same following other such".split())

def words(text):
    """A text's words for the label check: three letters or more, case folded, function words left out."""
    return {w.casefold() for w in WORD.findall(text)} - FUNCTION_WORDS
