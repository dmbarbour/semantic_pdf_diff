"""Excel workbooks (xlsxdocs.py; the adapters plan, milestone 5, "Excel, in detail"): sheets as pages, regions found,
cells as Excel shows them, tables on the grid, claims placed by sheet and cells."""
import stubs  # noqa: F401 (a clean environment)
import io
import unittest

try:
    import docx  # noqa: F401 (the office extra)
    import openpyxl
except ImportError:
    openpyxl = None

def workbook():
    """A workbook: a sheet with a merged title, a note, a table with a two-row header (one cell merged across), a
    formula left uncalculated and a comment; a sheet of label/value pairs over a table, two tables pressed together
    and a defined table too long to read row by row; and a hidden sheet."""
    from openpyxl.comments import Comment
    from openpyxl.worksheet.table import Table
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Pump Station PS-3 Design Summary"
    ws.merge_cells("A1:E1")
    ws["A2"] = "Values marked TBC are provisional."
    for r, row in enumerate([["Parameter", "Measured", None, "Design"], [None, "value", "±", None],
                             ["Flow (L/s)", 118, 3, 120], ["Head (m)", 24.1, 0.4, 25.5]], 4):
        for c, value in enumerate(row, 1):
            if value is not None:
                ws.cell(r, c, value)
    ws.merge_cells("B4:C4")
    ws["A8"], ws["B8"] = "Total head (m)", "=B6+B7"  # never calculated: openpyxl stores no cached value
    ws["B7"].number_format = "0.00"
    ws["A6"].comment = Comment("Retested in June.", "Ana")
    two = wb.create_sheet("Polar")
    for r, row in enumerate([["Configuration", "default"], ["Reynolds", 8100000],
                             ["alpha [deg]", "c_l", "c_d"], [-10, -0.82, 0.0123], [0, 0.31, 0.0071]], 1):
        for c, value in enumerate(row, 1):
            two.cell(r, c, value)
    for r, row in enumerate([["Option", "Capex (k$)", "Opex (k$/yr)"], ["A", 410, 22], ["B", 380, 30, "Year", "MWh"],
                             [None, None, None, 2025, 410]], 8):  # a second table pressed against the first
        for c, value in enumerate(row, 1):
            if value is not None:
                two.cell(r, c, value)
    rows = [["ID", "Requirement", "Value"]] + [[f"R-{k:03d}", f"Requirement {k}", k * 3] for k in range(1, 61)]
    for r, row in enumerate(rows, 14):
        for c, value in enumerate(row, 1):
            two.cell(r, c, value)
    two.add_table(Table(displayName="Requirements", ref=f"A14:C{13 + len(rows)}"))
    old = wb.create_sheet("Rev B (superseded)")
    old["A1"], old["B1"] = "Design flow (L/s)", 110
    old["A2"], old["B2"] = "Static head (m)", 18
    old.sheet_state = "hidden"
    raw = io.BytesIO()
    wb.save(raw)
    return raw.getvalue()

@unittest.skipIf(openpyxl is None, "python-docx and openpyxl aren't installed (the office extra)")
class Reading(unittest.TestCase):
    def test_sheets_regions_and_cells_as_excel_shows_them(self):
        from semantic_pdf_diff.xlsxdocs import read_xlsx
        doc = read_xlsx(workbook())
        self.assertEqual([title for _, _, _, title in doc.headings], ["Summary", "Polar", "Rev B (superseded)"])
        found = [(g.sheet, g.ref, g.kind) for g in doc.regions]
        self.assertEqual(found[:4], [("Summary", "A1", "text"), ("Summary", "A2", "text"), ("Summary", "A4:D8", "table"),
                                     ("Polar", "A1:B2", "pairs")])
        summary = next(b for b in doc.blocks if b.kind == "table")
        self.assertEqual(summary.rows[0], ["Parameter", "Measured > value", "Measured > ±", "Design"])
        self.assertEqual(summary.rows[1], ["Flow (L/s)", "118", "3", "120"])
        self.assertEqual(summary.rows[2], ["Head (m)", "24.10", "0.4", "25.5"])  # its number format: two decimals
        self.assertEqual(summary.rows[3][:2], ["Total head (m)", "[formula =B6+B7, not calculated]"])
        texts = [t for _, t in doc.lines]
        self.assertIn("Comment by Ana on A6: Retested in June.", texts)
        self.assertIn("Reynolds: 8100000", texts)  # a label and its value over the table
        self.assertIn("(Hidden sheet)", texts)
        polar = [b for b in doc.blocks if b.kind == "table"][1]
        self.assertEqual(polar.rows[0], ["alpha [deg]", "c_l", "c_d"])

    def test_what_isnt_read_yet_is_recorded(self):
        from semantic_pdf_diff.xlsxdocs import read_xlsx
        doc = read_xlsx(workbook())
        unread = [what for *_, what in doc.images]
        self.assertTrue(any(w.startswith("skipped: ambiguous sheet layout (Polar!A8:E11)") for w in unread))
        self.assertIn("a table of 60 rows (Polar!A14:C74), not read yet: it awaits the rules query", unread)

    def test_a_workbook_is_extracted_with_cell_locators(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from test_textdocs import extract
        from semantic_pdf_diff.models import XlsxLocator
        evidence, coverage, sections, _ = extract("book.xlsx", workbook())
        values = {e.value: e for e in evidence}
        located = values["118"].locator
        self.assertIsInstance(located, XlsxLocator)
        self.assertEqual((located.page, located.sheet, located.cells, located.region), (1, "Summary", "A6:D6", "table"))
        self.assertEqual(values["110"].locator.sheet, "Rev B (superseded)")
        self.assertEqual([s.heading_path for s in sections], [["Summary"], ["Polar"], ["Rev B (superseded)"]])

if __name__ == "__main__":
    unittest.main()
