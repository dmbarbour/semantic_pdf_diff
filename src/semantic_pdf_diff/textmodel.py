"""The text document every reader but the PDF's reads into (a TextDocument of pages, lines, blocks, headings and
pictures), so sections, the context levers and the task core work on all of them alike. Split from textdocs.py,
which reads plain text and Markdown into it (code review 2026-10-08, architecture 7).
"""
from dataclasses import dataclass, field

@dataclass
class Block:
    page: int
    first: int          # lines, counted from 1 through the whole file
    last: int
    text: str
    kind: str = "text"  # text, code or table
    rows: list = field(default_factory=list)  # a table's rows of cells, its header first
    row_lines: list = field(default_factory=list)
    row_headers: list = field(default_factory=list)  # each body row's own header labels (a Word table's merged
                                                     # cells); empty: every row is read under rows[0]
    source: str = ""    # where a table came from, if not a table: "chart" (a Word chart's data)
    grid: object = None  # a table's cells as its rules see them (tablegrid.Grid): a workbook's tables, for now
    key_value: bool = False  # proposed as a key-value list (keyvalue.candidate): the model asked before it's read

    @property
    def box(self):
        return (0.0, float(self.first), 1.0, float(self.last + 1))

@dataclass
class TextDocument:
    pages: int
    lines: list         # [(page, text)] by line number - 1
    blocks: list
    headings: list      # [(page, line, level, title)]
    images: list        # [(page, line, alt, target)]: images not read (a Markdown file's links, a Word chart)
    pictures: list = field(default_factory=list)  # [Picture]: a Word document's pictures, read
    places: dict = field(default_factory=dict)    # a workbook's lines' places: {line: (sheet, cell range)}
    regions: list = field(default_factory=list)   # a workbook's sheet map: [xlsxdocs.Region]

@dataclass
class Picture:
    """A picture in a Word document: at its paragraph (line), its bytes and format, its displayed size in points
    (None: unknown), and its caption."""
    line: int
    data: bytes
    extension: str      # ".emf", ".png"
    size: tuple | None
    caption: str
    name: str           # the part's name ("image12.emf")
    page: int = 1       # its page: a slide's number in a deck (a Word document is one page)
