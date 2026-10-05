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

    def test_an_ambiguous_region_is_recorded_and_a_long_table_kept_whole(self):
        from semantic_pdf_diff.xlsxdocs import read_xlsx
        doc = read_xlsx(workbook())
        unread = [what for *_, what in doc.images]
        self.assertTrue(any(w.startswith("skipped: ambiguous sheet layout (Polar!A8:E11)") for w in unread))
        long = next(b for b in doc.blocks if b.kind == "table" and b.grid.place == "Polar!A14:C74")
        self.assertEqual((len(long.rows), long.grid.place, long.grid.columns), (61, "Polar!A14:C74", ["A", "B", "C"]))
        self.assertEqual((long.grid.names[0], long.grid.rows[0], long.grid.labels), ("15", ["R-001", "Requirement 1", "3"],
                                                                                      ["ID", "Requirement", "Value"]))

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

class RulesModel:
    """The text tests' model, answering a table's rules query with the given rules (keyed by the table's place)."""
    def __init__(self, answers, **settings):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from test_textdocs import Model
        self.base, self.answers, self.asked = Model(**settings), answers, []
        self.s = self.base.s

    def __getattr__(self, name):
        return getattr(self.base, name)

    def ask(self, prompt, schema, images=(), key=None):
        from semantic_pdf_diff.tablerules import Rules
        if schema is not Rules:
            return self.base.ask(prompt, schema, images, key)
        self.asked.append(prompt)
        place = prompt.split("TABLE: ", 1)[1].split(";", 1)[0].split("\n", 1)[0]
        return Rules.model_validate(self.answers[place])

REQUIREMENTS = {"reading": "rules", "subject": "requirements",
                "claims": [{"entity": "{A}", "attribute": "{C.header}", "value": "{C}", "number": True}],
                "examples": [{"row": "15", "claims": [{"entity": "R-001", "attribute": "Value", "value": "3"}]}]}

@unittest.skipIf(openpyxl is None, "python-docx and openpyxl aren't installed (the office extra)")
class Rules(unittest.TestCase):
    def extract(self, answers, **settings):
        import tempfile
        from pathlib import Path
        from semantic_pdf_diff.extract import Job, reader_for, run_jobs
        model = RulesModel(answers, **settings)
        data = workbook()
        with tempfile.TemporaryDirectory() as d:
            job = Job("sha256:" + "a" * 64 + ".xlsx", lambda: data, reader=reader_for(".xlsx"))
            run_jobs([[job]], Path(d), model)
        evidence, coverage = job.state["result"]
        return evidence, coverage, model

    def test_a_long_table_is_read_by_rules_in_one_query(self):
        evidence, coverage, model = self.extract({"Polar!A14:C74": REQUIREMENTS})
        self.assertEqual(len(model.asked), 1)
        self.assertIn("SIZE: 60 rows, 3 columns", model.asked[0])
        ruled = [e for e in evidence if e.derivation[-1].step == "table-rules"]
        self.assertEqual(len(ruled), 60)
        first = next(e for e in ruled if e.entity == "R-001")
        self.assertEqual((first.attribute, first.value, first.quote, first.quote_verified), ("Value", "3", "R-001 | 3", True))
        self.assertEqual((first.locator.sheet, first.locator.cells), ("Polar", "A15:C15"))
        row, = [r for r in coverage if r["task"].startswith("rules:")]
        self.assertEqual((row["status"], row["claims"]), ("complete", 60))
        self.assertFalse([r for r in coverage if r["task"].startswith("table:p2:1:")])  # no row asked by itself

    def test_rules_that_miss_their_examples_are_asked_again_then_rows_read(self):
        wrong = {**REQUIREMENTS, "examples": [{"row": "15", "claims": [{"value": "4"}]}]}
        evidence, coverage, model = self.extract({"Polar!A14:C74": wrong})
        self.assertEqual(len(model.asked), 2)
        self.assertIn("ITS PROBLEMS:\n- row 15: the templates give 3, not 4", model.asked[1])
        tasks = [r["task"] for r in coverage]
        self.assertIn("rules:p2:1:again", tasks)
        self.assertEqual(sum(t.startswith("table:p2:1:") for t in tasks), 60)  # every row read by itself

    def test_every_table_by_rules_or_none(self):
        summary = {"reading": "rows"}
        _, coverage, model = self.extract({"Polar!A14:C74": REQUIREMENTS, "Summary!A4:D8": summary,
                                           "Polar!A3:C5": summary, "Rev B (superseded)!A1:B2": summary}, table_rules=0)
        self.assertEqual(len(model.asked), 4)
        _, coverage, model = self.extract({}, table_rules=None)
        self.assertEqual(model.asked, [])
        self.assertEqual(sum(r["task"].startswith("table:p2:1:") for r in coverage), 60)

if __name__ == "__main__":
    unittest.main()
