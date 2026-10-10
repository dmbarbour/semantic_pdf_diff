"""What Word documents, slide decks and workbooks share: the package their parts are zipped in (Open Packaging
Conventions), the XML namespaces they all use, their unit of length (EMU), and list numbers in a numbering format.
Split from the readers, which borrowed one another's (code review 2026-10-08, architecture 6: pptxdocs.Package used
by the workbook reader, Word's number format by the deck reader).
"""
import io
import posixpath
import zipfile

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
CHART = "http://schemas.openxmlformats.org/drawingml/2006/chart"
EMU_PER_POINT = 12700

class Package:
    """A zip of parts with relationships (Open Packaging Conventions): enough to follow a deck's parts."""
    def __init__(self, data):
        self.zip = zipfile.ZipFile(io.BytesIO(bytes(data)))
        self.names = set(self.zip.namelist())

    def read(self, name):
        return self.zip.read(name)

    def xml(self, name):
        from lxml import etree
        return etree.fromstring(self.read(name))

    def rels(self, name):
        """{relationship id: (its type's last word, the target part's name)}; external targets left out."""
        folder, base = posixpath.split(name)
        rels = posixpath.join(folder, "_rels", base + ".rels")
        if rels not in self.names:
            return {}
        out = {}
        for rel in self.xml(rels):
            if rel.get("TargetMode") == "External":
                continue
            target = posixpath.normpath(posixpath.join(folder, rel.get("Target")))
            out[rel.get("Id")] = (rel.get("Type").rsplit("/", 1)[-1], target.lstrip("/"))
        return out

    def related(self, name, kind):
        return next((target for rel, target in self.rels(name).values() if rel == kind), None)

def number_format(n, form):
    """A list item's number in a numbering format (Word's names: decimalZero, lowerLetter, upperRoman, ...)."""
    if form == "decimalZero":
        return f"{n:02d}"
    if form in ("lowerLetter", "upperLetter"):
        letters = ""
        while n > 0:
            n, r = divmod(n - 1, 26)
            letters = chr(97 + r) + letters
        return letters.upper() if form == "upperLetter" else letters
    if form in ("lowerRoman", "upperRoman"):
        out = ""
        for value, numeral in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"),
                               (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
            while n >= value:
                out, n = out + numeral, n - value
        return out.upper() if form == "upperRoman" else out
    return "" if form == "none" else str(n)
