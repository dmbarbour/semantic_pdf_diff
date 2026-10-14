"""Context records (docs/plans/claim-context-2026-10-14.md, milestone 3; records.py, the records lever): lists,
tables and a sheet's notes kept once and referenced by their claims, and claims' names as printed."""
import stubs  # noqa: F401 (a clean environment)
import unittest
from types import SimpleNamespace

from semantic_pdf_diff.records import list_records, note_records, printed_before, table_record
from semantic_pdf_diff.schema import Position
from semantic_pdf_diff.settings import Settings

LEAD = "A link failure is declared when any of the following conditions holds."

def blocks(*texts):
    return [((0, i, 1, i + 1), t) for i, t in enumerate(texts)]

class Lists(unittest.TestCase):
    def test_a_list_is_kept_once_and_its_items_point_at_it(self):
        page = blocks(LEAD, "Condition 1: no acknowledgement in 856 ms.", "Condition 2: 21 retransmissions fail.")
        positions = {(0, 1, 1, 2): Position(label="Condition 1", lead=LEAD),
                     (0, 2, 1, 3): Position(label="Condition 2", lead=LEAD)}
        records, pointed = list_records(4, page, positions)
        self.assertEqual([(r.id, r.kind, r.text, r.items, r.gives) for r in records],
                         [("list:p4:0", "list", LEAD, ["Condition 1", "Condition 2"], ["scope"])])
        self.assertEqual(pointed[(0, 2, 1, 3)], Position(label="Condition 2", list="list:p4:0"))
        self.assertNotIn("list", Position(label="Condition 2").model_dump())  # positions without records as before

    def test_no_positions_no_list_records(self):
        page = blocks(LEAD, "Condition 1: a.", "Condition 2: b.")
        self.assertEqual(list_records(1, page, {}), ([], {}))

class Notes(unittest.TestCase):
    def test_a_sheets_notes_and_legend(self):
        page = blocks("MEETING 101", "GENERAL NOTES", "1. ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE.",
                      "2. ROOM AREAS ARE NET.", "MEETING 102", "LEGEND\nDF  DRINKING FOUNTAIN")
        notes = note_records(1, page)
        self.assertEqual([(r.id, r.kind, r.label, r.gives) for r in notes],
                         [("note:p1:0", "note", "GENERAL NOTES", ["frame", "scope"]),
                          ("legend:p1:1", "legend", "LEGEND", ["frame"])])
        self.assertIn("FACE OF FINISH", notes[0].text)
        self.assertNotIn("MEETING 102", notes[0].text)  # an unnumbered block ends the notes
        self.assertEqual(notes[1].text, "DF DRINKING FOUNTAIN")

class Tables(unittest.TestCase):
    def test_a_table_record_is_named_by_its_rules_task(self):
        grid = SimpleNamespace(title="Table 1. Pumps", place="page 2, table 1", labels=["Tag", "Capacity (gpm)"])
        r = table_record(2, "rules:p2:0", grid, "CONTEXT (for reference only: do not extract claims from it):\n"
                                                "Above the table: ...at their rated points.", (0, 0, 9, 9))
        self.assertEqual((r.id, r.label, r.items, r.text), ("table:p2:0", "Table 1. Pumps",
                                                             ["Tag", "Capacity (gpm)"],
                                                             "Above the table: ...at their rated points."))

    def test_a_rule_claims_name_as_printed(self):
        from semantic_pdf_diff.tablerules import printed_name
        grid = SimpleNamespace(rows=[["P-101A", "7,824", "134.8"]], sections=["Raw water pumps"],
                               labels=["Tag", "Rated point > Capacity (gpm)", "TDH (ft)"])
        self.assertEqual(printed_name(grid, 0, [0, 1], "7,824"),
                         "Raw water pumps | P-101A | Rated point > Capacity (gpm)")
        self.assertEqual(printed_name(grid, 0, [0, 1], "9,999"), "")

class Printed(unittest.TestCase):
    def test_the_words_before_a_value(self):
        cases = [("The retransmission timer is 709 ms.", "709", "retransmission timer"),
                 ("Keep-alive interval: 1,250 ms", "1250", "Keep-alive interval"),
                 ("the signal-to-noise ratio stays below 4.3 dB for 60 s", "4.3", "signal-to-noise ratio"),
                 ("the signal-to-noise ratio stays below 4.3 dB for 60 s", "60", ""),  # after another value: none
                 ("709 ms", "709", ""), ("The timer is 709 ms.", "856", "")]
        for quote, value, name in cases:
            with self.subTest(quote=quote, value=value):
                self.assertEqual(printed_before(quote, value), name)

class Lever(unittest.TestCase):
    def test_off_nothing_is_kept_on_lists_and_notes(self):
        page = blocks("GENERAL NOTES", "1. ALL DIMENSIONS ARE TO FACE OF FINISH.", "2. AREAS ARE NET.")
        off, on = Settings(), Settings(records=True)
        self.assertEqual(off.page_structure(1, page, lambda: True)[1], [])
        self.assertEqual([r.kind for r in on.page_structure(1, page, lambda: True)[1]], ["list", "note"])
        self.assertEqual([r.kind for r in on.page_structure(1, page, lambda: False)[1]], ["list"])  # not a sheet
        claim = SimpleNamespace(quote="The timer is 709 ms.", value="709")
        self.assertEqual((off.printed_name(claim), on.printed_name(claim)), ("", "timer"))

    def test_a_document_read_with_records(self):
        # the spec's conditions: one list record, each condition's claims pointing at it with their names as printed
        from test_positions import SPEC, Model
        from test_textdocs import extract
        import test_textdocs
        model_class, test_textdocs.Model = test_textdocs.Model, Model
        try:
            evidence, _, _, _ = extract("spec.md", SPEC, records=True)
        finally:
            test_textdocs.Model = model_class
        found = {e.value: e for e in evidence}
        self.assertEqual(found["856"].records, [found["856"].position.list])
        self.assertTrue(found["856"].position.list.startswith("list:"))
        self.assertEqual(found["10"].records, [])  # "Pump 1: rated at 10 kW." is a name, not a list item

class Stored(unittest.TestCase):
    def test_a_run_keeps_each_record_once_beside_the_claims_that_reference_it(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from semantic_pdf_diff import cli
        from semantic_pdf_diff.store import Store
        from test_concurrency import jittery_model
        spec = (f"# Loads\n\n{LEAD}\n\nCondition 1: the heater draws 12 kW.\n\nCondition 2: the fan draws 3 kW.\n\n"
                "Pump 1: rated at 10 kW.\n")  # the stub reads each "N kW"
        with tempfile.TemporaryDirectory() as d, jittery_model() as (url, _):
            doc, config = Path(d) / "spec.md", Path(d) / "settings.json"
            doc.write_text(spec)
            config.write_text(json.dumps({"records": True}))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main(["compare", str(doc), str(doc), "--store", str(Path(d) / "out"), "--base-url", url,
                          "--no-situate", "--config", str(config)])
            with Store.open(Path(d) / "out") as store:
                content = store.files()[0].content
                records = store.records(content)
                referenced = {r for e in store.evidence(content) for r in e.records}
        self.assertEqual([(r.kind, r.text) for r in records.values()],
                         [("list", "A link failure is declared when any of the following conditions holds.")])
        self.assertLessEqual(referenced, set(records))

if __name__ == "__main__":
    unittest.main()
