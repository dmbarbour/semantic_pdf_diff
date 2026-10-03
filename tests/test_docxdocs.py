"""Word documents (docxdocs.py; the adapters plan, milestone 2): read through the text reader, paragraphs and table
rows as lines, headings by style, tracked changes applied, contents and pictures left out."""
import stubs  # noqa: F401 (a clean environment)
import io
import unittest

try:
    import docx
except ImportError:  # the office extra
    docx = None

def build():
    """A small document: a title, two heading levels, prose, a table, a contents entry, a tracked insertion and
    deletion, and a picture."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    d = docx.Document()
    d.add_heading("Harrow Creek WTP", level=0)
    toc = d.add_paragraph("1 Design Basis ..... 3")
    toc.style = d.styles.add_style("toc 1", 1)
    d.add_heading("1 Design Basis", level=1)
    p = d.add_paragraph("The design flow is ")
    ins = OxmlElement("w:ins")  # tracked: "25.9 MGD" inserted, "24.0 MGD" deleted
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "25.9 MGD"
    run.append(text)
    ins.append(run)
    p._p.append(ins)
    gone = OxmlElement("w:del")
    run = OxmlElement("w:r")
    deleted = OxmlElement("w:delText")
    deleted.text = "24.0 MGD"
    run.append(deleted)
    gone.append(run)
    p._p.append(gone)
    d.add_heading("1.1 Pumps", level=2)
    table = d.add_table(rows=3, cols=3)
    for r, cells in enumerate([["Tag", "Capacity (gpm)", "TDH (ft)"], ["P-101A", "5,151", "96.8"],
                               ["P-101B", "5,590", "64.9"]]):
        for c, value in enumerate(cells):
            table.cell(r, c).text = value
    figure = d.add_paragraph()
    figure._p.append(OxmlElement("w:drawing"))
    raw = io.BytesIO()
    d.save(raw)
    return raw.getvalue()

@unittest.skipIf(docx is None, "python-docx isn't installed (the office extra)")
class Reading(unittest.TestCase):
    def test_a_word_document_becomes_lines_blocks_and_headings(self):
        from semantic_pdf_diff.docxdocs import read_docx
        doc = read_docx(build())
        self.assertEqual([(level, title) for _, _, level, title in doc.headings],
                         [(1, "1 Design Basis"), (2, "1.1 Pumps")])
        text = "\n".join(b.text for b in doc.blocks)
        self.assertIn("The design flow is 25.9 MGD", text)  # the insertion in, the deletion out
        self.assertNotIn("24.0", text)
        self.assertNotIn(".....", text)                      # the contents left out
        table = next(b for b in doc.blocks if b.kind == "table")
        self.assertEqual(table.rows, [["Tag", "Capacity (gpm)", "TDH (ft)"], ["P-101A", "5,151", "96.8"],
                                      ["P-101B", "5,590", "64.9"]])
        self.assertEqual(len(doc.images), 1)

    def test_a_word_document_is_extracted_with_paragraph_locators(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from test_textdocs import extract
        from semantic_pdf_diff.models import DocxLocator
        data = build()
        evidence, coverage, sections, model = extract("basis.docx", data)
        values = {e.value: e for e in evidence}
        self.assertLessEqual({"25.9", "5,151", "96.8", "5,590", "64.9"}, set(values))  # (and the headings' numbers)
        self.assertIsInstance(values["25.9"].locator, DocxLocator)
        self.assertEqual(values["5,151"].locator.region, "table")
        self.assertEqual([s.heading_path for s in sections][-1], ["1 Design Basis", "1.1 Pumps"])
        self.assertEqual([r["status"] for r in coverage if r["task"].startswith("image")], ["skipped"])

if __name__ == "__main__":
    unittest.main()
