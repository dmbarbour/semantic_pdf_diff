"""A Word document's pictures, read as a PDF's figures are (docs/plans/multi-format-adapters-2026-09-23.md, "Pictures
in Word documents"; the owner: "we'll want similar context as what PDF pics get", and "Every pic.").

Each picture becomes a page of a pictures document, at its displayed size: an EMF or WMF drawn by metafiles.py
(vector, its labels a text layer), a raster image as it is. The page gets a PDF page's image tasks (visual_regions:
the whole picture, and tiles when it's large; extract.Visuals), each with the picture's caption as its source text,
the page's text layer as a check on quotes and as context, and its section's headings. Its claims are located at the
picture's paragraph (DocxLocator), each with the crop it was read from.
"""
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

def tasks(core, settings, pictures, content, output, keep):
    """Generator feeding each picture's image tasks (yielding "page" between pictures, for fair share). keep: a
    list the pictures document is appended to, for the caller to close once its tasks are done (refinement renders
    crops from it later). Every picture is drawn into the document before any task is fed: adding a page invalidates
    the pages loaded before it, and a tile refined later renders from its page."""
    from .extract import Context, Visuals
    from .regions import crop_stem
    s = settings
    assets = output / "assets"
    assets.mkdir(exist_ok=True, parents=True)
    stem = crop_stem(content)
    doc = pymupdf.open()
    keep.append(doc)
    context_of = Context(doc, s, assets, stem)
    visuals = Visuals(core, context_of, assets, stem, s)
    drawn_pages = []  # (picture, its page's number)
    for picture in pictures:
        yield "page"
        box = (0.0, float(picture.line), 1.0, float(picture.line + 1))
        task = f"picture:p1:{picture.line}"
        if not s.vision:
            core.record(coverage_row(content=content, page=1, bbox=list(box), task=task, status="skipped",
                                     issues=["Visual extraction disabled; pictures aren't read"]))
            continue
        try:
            single = page_of(picture)
        except PictureError as error:
            core.record(coverage_row(content=content, page=1, bbox=list(box), task=task, status="skipped",
                                     issues=[str(error)]))
            continue
        doc.insert_pdf(single)
        drawn_pages.append((picture, len(doc)))
    for picture, number in drawn_pages:
        yield "page"
        box = (0.0, float(picture.line), 1.0, float(picture.line + 1))
        page = doc[number - 1]
        drawn = "a metafile drawn as vector" if picture.extension in METAFILES else "an image"
        note = f"Caption: {picture.caption}" if picture.caption else ""
        for tag, rect, _ in s.visual_regions(context_of, page, number):
            region, _, index = tag.partition(":")
            tag = f"{region}:p1:pic{picture.line}" + (f":{index}" if index else "")
            derivation = [DerivationStep(step="docx-picture", detail=f"{picture.name}, {drawn}"),
                          DerivationStep(step="picture-region", detail=region),
                          DerivationStep(step="model-extraction")]
            visuals.task(1, page, tag, rect, text=note, box=box, derivation=derivation)
