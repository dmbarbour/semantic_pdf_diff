"""The documents a store read, as the lab shows them: every format a reader reads (code review 2026-10-08, E3: rounds
and review batches read PDFs, and the rounds text formats, so levers acting on images, Word, decks or sheets were
measured on PDFs alone).

- **A PDF:** its pages.
- **An image:** the PDF its reader made of it (extract.image_pdf, under the store's own settings), so crops are of the
  page the model's tiles were cut from.
- **A text format** (plain text, Markdown, Word, decks, sheets, CSV): its lines as its reader reads them. Its claims
  are placed by line (a locator's box is (0, first line, 1, last line + 1)), so it's shown as text, not as an image.
"""
from pathlib import Path
from types import SimpleNamespace

from semantic_pdf_diff.extract import IMAGE_EXTENSIONS, READERS, image_pdf
from semantic_pdf_diff.settings import Settings

def extension(content):
    """A content ID's extension ("sha256:<hex>.pdf" → ".pdf")."""
    return Path(content).suffix.lower()

def contents(store):
    """Every content the store holds that a reader reads, sorted."""
    return sorted({f.content for f in store.files() if extension(f.content) in READERS})

def layout(store):
    """The settings an image's page was laid out by: the store's bound extraction settings, else the defaults."""
    bound = (store.interpreter("extract") or {}).get("settings", {})
    return SimpleNamespace(**{name: bound.get(name, Settings.model_fields[name].default)
                              for name in ("tile_points", "image_side")})

class Document:
    """One document as the lab shows it: `pdf` (a PDF's or an image's pages, open) or `text` (a TextDocument)."""

    def __init__(self, data, content, settings=None):
        import pymupdf
        self.content, self.pdf, self.text = content, None, None
        ext = extension(content)
        if ext == ".pdf":
            self.pdf = pymupdf.open(stream=data, filetype="pdf")
        elif ext in IMAGE_EXTENSIONS:
            self.pdf = pymupdf.open(stream=image_pdf(data, ext, settings or layout_defaults()), filetype="pdf")
        else:
            from semantic_pdf_diff.textdocs import read_text
            self.text = read_text(data, ext)

    @classmethod
    def of(cls, store, content):
        """The document behind a content ID, from wherever the store found it."""
        from semantic_pdf_diff.scan import read_origin
        file = next(f for f in store.files() if f.content == content)
        return cls(read_origin(store.origin(file.source, file.path)), content, layout(store))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self.pdf is not None:
            self.pdf.close()

    @property
    def pages(self):
        return len(self.pdf) if self.pdf is not None else self.text.pages

    def lines(self, page, box=None):
        """[(line number, text)] of a text format's page, within a locator's box (its lines) if given."""
        first, last = (int(box[1]), max(int(box[1]), int(box[3]) - 1)) if box is not None else (1, len(self.text.lines))
        return [(n, text) for n, (p, text) in enumerate(self.text.lines, 1) if p == page and first <= n <= last]

    def page_text(self, page, box=None):
        """A page's text: a PDF's text layer (within a box in unrotated points, if given), or a text format's lines
        (within a box of lines)."""
        if self.pdf is not None:
            return self.pdf[page - 1].get_text("text", clip=box)
        return "\n".join(text for _, text in self.lines(page, box))

    def headings(self, page, line):
        """A text format's headings above a line, outermost first: what the line sits under."""
        path = []
        for p, at, level, title in self.text.headings:
            if (p, at) > (page, line):
                break
            path = [h for h in path if h[0] < level] + [(level, title)]
        return [title for _, title in path]

def layout_defaults():
    return SimpleNamespace(**{name: Settings.model_fields[name].default for name in ("tile_points", "image_side")})
