"""A table's rows read by themselves as its grid holds them, and its notes (code review 2026-10-08, B2): a wrapped
row was read as its raw first line, and a one-cell note was a section label, never read, labelling the rows below."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stubs  # noqa: F401 (a clean environment)
from semantic_pdf_diff import tablegrid, tablerules
from semantic_pdf_diff.tables import pdf_grid

HEADER = ["Tag", "Service", "Flow (L/s)", "Head (m)"]
BODY = [["P-1", "Chilled water", "120", "30"],
        ["Standby", "", "", ""],  # a section row (not first: under the header, it's taken for a header's second line)
        ["P-2", "Condenser water,", "95", "28"],
        ["", "standby duty", "", ""],
        ["Note: P-2 is rated 95 L/s at 28 m with both cells running", None, None, None],
        ["P-3", "Make-up", "4", "12"]]
BOXES = [(20, 40 + 12 * k, 280, 52 + 12 * k) for k in range(len(BODY) + 1)]  # the header's first

class Grid(unittest.TestCase):
    def test_section_rows_kept_and_possible_notes_proposed(self):
        g = pdf_grid(HEADER, BODY, BOXES[1:])
        self.assertEqual(g.keys, [0, 2, 5])
        self.assertEqual(g.joined, {2})
        self.assertEqual(g.rows[1][1], "Condenser water, standby duty")
        self.assertEqual([(r.key, r.text[:5]) for r in g.section_rows], [(1, "Stand"), (4, "Note:")])
        self.assertEqual(g.sections[2], BODY[4][0])  # P-3 filed under the note, as the heuristic has it
        note, = tablegrid.possible_notes(g)
        self.assertEqual(note.key, 4)
        noted, notes = tablegrid.noted(g, [note.name])
        self.assertEqual(notes, [note])
        self.assertEqual(noted.sections, ["", "Standby", "Standby"])  # a note labels nothing
        self.assertEqual(tablegrid.noted(g, ["99"]), (g, []))  # only possible notes can be named
        self.assertIn(f"POSSIBLE NOTES (section rows holding a number: a note states facts, where a section row only "
                      f"names the rows below it): row {note.name}: Note: P-2", tablerules.question(g))
        plain = pdf_grid(HEADER, BODY[:3], BOXES[1:4])
        self.assertNotIn("POSSIBLE NOTES", tablerules.question(plain))  # no other table's query changes

class Pdf(unittest.TestCase):
    """The PDF job's table path, on a detected table (find_tables patched)."""
    def extract(self, rules=None, answer=None):
        import pymupdf
        from semantic_pdf_diff.jobs import extract_pdf
        from semantic_pdf_diff.llm import ModelFailure
        from semantic_pdf_diff.schema import Extraction
        from semantic_pdf_diff.settings import Settings
        from semantic_pdf_diff.provenance import content_id
        from semantic_pdf_diff.tasks import ExtractQuery
        from stubs import situating_answer

        class Table:
            bbox, cells = (20, 40, 280, 40 + 12 * (len(BODY) + 1)), []
            def extract(self): return [HEADER] + [list(r) for r in BODY]

        class Client:
            s = Settings(vision=False, table_structure=False, table_rules=rules, refinement_depth=0)
            calls, cache_hits, usage = 0, 0, {}

            def __init__(self):
                self.rows, self.asked = {}, []

            def ask(self, prompt, schema, images=(), key=None):
                if situating_answer(prompt):
                    return schema.model_validate(situating_answer(prompt))
                if schema is tablerules.Rules:
                    self.asked.append(prompt)
                    if answer is None:
                        raise ModelFailure("the rules query failed")
                    return tablerules.Rules.model_validate(answer)
                if schema is tablerules.Review:
                    return tablerules.Review(verdict="keep")
                self.rows[key[3]] = ExtractQuery.read(prompt).data
                return Extraction(claims=[], complete=True)

        find = lambda page, *a, **k: type("T", (), {"tables": [Table()]})()
        with contextlib.ExitStack() as stack, tempfile.TemporaryDirectory() as d:
            stack.enter_context(patch.object(pymupdf.Page, "find_tables", find))
            stack.enter_context(patch("semantic_pdf_diff.extract.Marks", lambda page: None))
            stack.enter_context(patch("semantic_pdf_diff.extract.row_boxes", lambda table, rows: BOXES))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            doc = pymupdf.open()
            doc.new_page(width=300, height=300)
            path = Path(d) / "t.pdf"
            doc.save(path)
            client = Client()
            _, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
        return client, coverage

    def rows(self, client):
        return {int(task.rsplit(":", 1)[1]): data for task, data in client.rows.items() if task.startswith("table:")}

    def test_without_rules_the_grids_rows_and_possible_notes_are_read(self):
        client, _ = self.extract(rules=None)
        rows = self.rows(client)
        self.assertEqual(sorted(rows), [0, 2, 4, 5])  # not "Standby", not P-2's second line alone
        self.assertIn(json.dumps(["P-2", "Condenser water, standby duty", "95", "28"]), rows[2])  # read whole
        self.assertIn("Row: " + json.dumps(BODY[0]), rows[0])  # an unwrapped row's request as before
        self.assertIn("Note: P-2 is rated 95 L/s", rows[4])

    def test_a_note_the_model_confirms_is_read_and_one_it_doesnt_stays_a_label(self):
        name = tablegrid.possible_notes(pdf_grid(HEADER, BODY, BOXES[1:]))[0].name
        client, coverage = self.extract(rules=0, answer={"reading": "rows", "notes": [name]})
        self.assertIn("POSSIBLE NOTES", client.asked[0])
        rows = self.rows(client)
        self.assertEqual(sorted(rows), [0, 2, 4, 5])
        self.assertIn(json.dumps(["P-2", "Condenser water, standby duty", "95", "28"]), rows[2])
        rules = next(r for r in coverage if r["task"] == "rules:p1:0")
        self.assertIn(f"notes read by themselves: rows {name}", rules["issues"][0])
        client, _ = self.extract(rules=0, answer={"reading": "rows"})
        self.assertEqual(sorted(self.rows(client)), [0, 2, 5])  # not confirmed: a label

    def test_without_an_answer_the_proposal_stands(self):
        client, coverage = self.extract(rules=0, answer=None)
        self.assertEqual(sorted(self.rows(client)), [0, 2, 4, 5])
        self.assertEqual(next(r for r in coverage if r["task"] == "rules:p1:0")["status"], "failed")

    def test_rules_bind_rows_under_the_section_above_a_confirmed_note(self):
        name = tablegrid.possible_notes(pdf_grid(HEADER, BODY, BOXES[1:]))[0].name
        rules = {"reading": "rules", "notes": [name], "claims": [
            {"entity": "{A}", "attribute": "flow", "value": "{C}", "unit": "L/s", "conditions": "{section}",
             "number": True}], "examples": [  # P-3 under "Standby": checked against the grid without the note's label
            {"row": "2", "claims": [{"entity": "P-1", "attribute": "flow", "value": "120", "unit": "L/s"}]},
            {"row": "6", "claims": [{"entity": "P-3", "attribute": "flow", "value": "4", "unit": "L/s",
                                     "conditions": "Standby"}]}]}
        client, coverage = self.extract(rules=0, answer=rules)
        self.assertEqual(sorted(self.rows(client)), [4])  # the note alone read by itself
        rules_row = next(r for r in coverage if r["task"] == "rules:p1:0")
        self.assertEqual(rules_row["claims"], 3)

class Sheet(unittest.TestCase):
    def test_a_sheets_note_is_proposed_and_read_when_confirmed(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest("openpyxl isn't installed (the office extra)")
        from test_xlsxdocs import RulesModel
        from semantic_pdf_diff.jobs import Job, reader_for, run_jobs
        book = openpyxl.Workbook()
        sheet = book.active
        sheet.title = "Pumps"
        for row in [["Tag", "Service", "Flow (L/s)"], ["P-1", "Chilled water", 120], ["P-2", "Condenser water", 95],
                    ["Note: P-2 is rated 95 L/s with both cells running"], ["P-3", "Make-up", 4]]:
            sheet.append(row)
        buffer = io.BytesIO()
        book.save(buffer)
        data = buffer.getvalue()
        for notes, read in (([], False), (["4"], True)):
            model = RulesModel({"Pumps!A1:C5": {"reading": "rows", "notes": notes}})
            with tempfile.TemporaryDirectory() as d:
                job = Job("sha256:" + "a" * 64 + ".xlsx", lambda: data, reader=reader_for(".xlsx"))
                run_jobs([[job]], Path(d), model)
            self.assertIn("POSSIBLE NOTES", model.asked[0])
            self.assertIn("row 4: Note: P-2", model.asked[0])  # its row on the sheet
            asked = [q.data for q in model.base.queries if q.region == "table"]
            self.assertEqual(any("Note: P-2" in q for q in asked), read)
            self.assertEqual(len(asked), 3 + read)

if __name__ == "__main__":
    unittest.main()
