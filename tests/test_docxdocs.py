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

@unittest.skipIf(docx is None, "python-docx isn't installed (the office extra)")
class WordFeatures(unittest.TestCase):
    """Footnotes and numbered lists: what Word holds outside a paragraph's own text (the Word knobs, word.py)."""
    def test_a_footnote_follows_the_paragraph_citing_it(self):
        from semantic_pdf_diff.docxdocs import read_docx
        from semantic_pdf_diff_lab.bench.controlled.word import Writer
        writer = Writer()
        writer.heading("1 Design Basis", 1)
        p = writer.paragraph("The plant serves 89,000 persons.")
        writer.footnote(p, "Chlorine is fed at 3.3 mg/L.")
        writer.paragraph("Alum is dosed at 38.8 mg/L.")
        doc = read_docx(writer.save())
        texts = [t for _, t in doc.lines if t]
        self.assertEqual(texts[1:], ["The plant serves 89,000 persons.[1]", "Footnote 1: Chlorine is fed at 3.3 mg/L.",
                                     "Alum is dosed at 38.8 mg/L."])
        self.assertIn("Footnote 1: Chlorine is fed at 3.3 mg/L.", [b.text for b in doc.blocks])

    def test_numbered_lists_are_written_as_word_numbers_them(self):
        from semantic_pdf_diff.docxdocs import Numbering, _format, read_docx
        from semantic_pdf_diff_lab.bench.controlled.word import Writer
        writer = Writer()
        for text in ("no acknowledgement within 856 ms", "21 retransmissions fail", "SNR below 4.3 dB"):
            writer.numbered(text, "Condition %1:")
        doc = read_docx(writer.save())
        self.assertEqual([t for _, t in doc.lines if t],
                         ["Condition 1: no acknowledgement within 856 ms", "Condition 2: 21 retransmissions fail",
                          "Condition 3: SNR below 4.3 dB"])
        self.assertEqual([_format(n, f) for n, f in ((3, "lowerLetter"), (28, "upperLetter"), (14, "lowerRoman"),
                                                      (9, "upperRoman"), (7, "decimalZero"))],
                         ["c", "AB", "xiv", "IX", "07"])
        # Word's own List Number and List Bullet styles: numbered by their style; a deeper level restarts
        d = docx.Document()
        for text, style in (("first", "List Number"), ("second", "List Number"), ("a point", "List Bullet")):
            d.add_paragraph(text, style=style)
        raw = io.BytesIO()
        d.save(raw)
        texts = [t for _, t in read_docx(raw.getvalue()).lines if t]
        self.assertEqual(texts, ["1. first", "2. second", "• a point"])

def tables():
    """A document of tables: a chiller table with a two-row header made of merged cells, a unit merged down over two
    rows and a value merged across two columns; a pump table with a small nested table in a cell; an area table with
    a large nested table; a one-row layout table holding a heading and paragraphs; and a table whose header row is
    marked to repeat, its rows inside a content control."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    d = docx.Document()
    chillers = d.add_table(rows=4, cols=3)
    chillers.cell(0, 0).text = "Unit"
    chillers.cell(0, 1).merge(chillers.cell(0, 2)).text = "Capacity (tons)"
    chillers.cell(0, 0).merge(chillers.cell(1, 0))
    chillers.cell(1, 1).text, chillers.cell(1, 2).text = "Summer", "Winter"
    chillers.cell(2, 0).merge(chillers.cell(3, 0)).text = "Chiller CH-1"
    chillers.cell(2, 1).text, chillers.cell(2, 2).text = "450", "300"
    chillers.cell(3, 1).merge(chillers.cell(3, 2)).text = "425"
    pumps = d.add_table(rows=2, cols=2)
    pumps.cell(0, 0).text, pumps.cell(0, 1).text = "Pump", "Rated point"
    pumps.cell(1, 0).text = "P-101A"
    point = pumps.cell(1, 1).add_table(rows=2, cols=2)
    for r, (label, value) in enumerate((("Flow", "450 gpm"), ("Head", "85 ft"))):
        point.cell(r, 0).text, point.cell(r, 1).text = label, value
    areas = d.add_table(rows=2, cols=2)
    areas.cell(0, 0).text, areas.cell(0, 1).text = "Area", "Valves"
    areas.cell(1, 0).text = "Intake"
    valves = areas.cell(1, 1).add_table(rows=8, cols=2)
    for r in range(8):
        valves.cell(r, 0).text = "Tag" if r == 0 else f"V-30{r}"
        valves.cell(r, 1).text = "Cv" if r == 0 else f"{600 + r}"
    layout = d.add_table(rows=1, cols=2)
    layout.cell(0, 0).add_paragraph("2 Notes", style="Heading 1")
    layout.cell(0, 0).add_paragraph("The basin holds 2.4 MG.")
    layout.cell(0, 1).add_paragraph("The weir is 140 ft long.")
    marked = d.add_table(rows=3, cols=2)
    for r, (tag, value) in enumerate((("Blower", "Airflow (scfm)"), ("B-401", "2,837"), ("B-402", "1,632"))):
        marked.cell(r, 0).text, marked.cell(r, 1).text = tag, value
    marked.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    row = marked.rows[2]._tr  # the last row inside a content control
    control, inside = OxmlElement("w:sdt"), OxmlElement("w:sdtContent")
    row.addprevious(control)
    inside.append(row)
    control.append(inside)
    raw = io.BytesIO()
    d.save(raw)
    return raw.getvalue()

@unittest.skipIf(docx is None, "python-docx isn't installed (the office extra)")
class WordTables(unittest.TestCase):
    """Merged and nested cells and layout tables (the adapters plan, "Merged and nested cells")."""
    def test_merged_cells_are_placed_on_the_grid(self):
        from semantic_pdf_diff.docxdocs import read_docx
        chillers = [b for b in read_docx(tables()).blocks if b.kind == "table"][0]
        self.assertEqual(chillers.rows, [["Unit", "Capacity (tons) > Summer", "Capacity (tons) > Winter"],
                                         ["Chiller CH-1", "450", "300"], ["Chiller CH-1", "425"]])  # the unit repeated
        self.assertEqual(chillers.row_headers[1], ["Unit", "Capacity (tons) > Summer / Winter"])    # one value, both

    def test_a_small_nested_table_is_written_into_its_cell_and_a_large_one_read_on_its_own(self):
        from semantic_pdf_diff.docxdocs import read_docx
        doc = read_docx(tables())
        found = [b for b in doc.blocks if b.kind == "table"]
        self.assertEqual(found[1].rows[1], ["P-101A", "Flow: 450 gpm; Head: 85 ft"])
        self.assertEqual(found[2].rows[1], ["Intake", "(table below)"])
        self.assertEqual(found[3].rows[0], ["Tag", "Cv"])
        self.assertEqual(found[3].rows[-1], ["V-307", "607"])
        self.assertEqual(doc.lines[found[3].first - 2][1], "Table in Intake, Valves:")  # where it sits, just above
        self.assertEqual(sum("Flow" in t for _, t in doc.lines), 1)  # read once, not as rows of the outer table

    def test_a_layout_table_is_read_as_content(self):
        from semantic_pdf_diff.docxdocs import read_docx
        doc = read_docx(tables())
        self.assertIn((1, "2 Notes"), [(level, title) for _, _, level, title in doc.headings])
        texts = [b.text for b in doc.blocks if b.kind == "text"]
        self.assertLess(texts.index("The basin holds 2.4 MG."), texts.index("The weir is 140 ft long."))
        self.assertEqual(len([b for b in doc.blocks if b.kind == "table"]), 5)  # the layout table isn't one

    def test_a_marked_header_row_and_rows_in_a_content_control(self):
        from semantic_pdf_diff.docxdocs import read_docx
        blowers = [b for b in read_docx(tables()).blocks if b.kind == "table"][-1]
        self.assertEqual(blowers.rows, [["Blower", "Airflow (scfm)"], ["B-401", "2,837"], ["B-402", "1,632"]])

    def test_each_row_is_asked_under_its_own_labels(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from test_textdocs import extract
        _, _, _, model = extract("tables.docx", tables())
        rows = [q.data for q in model.queries if q.region == "table"]
        self.assertIn('Header: ["Unit", "Capacity (tons) > Summer / Winter"]\nRow: ["Chiller CH-1", "425"]', rows)
        self.assertIn('Header: ["Pump", "Rated point"]\nRow: ["P-101A", "Flow: 450 gpm; Head: 85 ft"]', rows)
        self.assertFalse(any('"Flow"' in r for r in rows))  # the nested rows aren't asked under the outer header

if __name__ == "__main__":
    unittest.main()
