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

class Sheets(unittest.TestCase):
    def test_a_sheets_title_block_is_a_record_naming_the_sheet(self):
        # the sheet_records lever: two halls' sheets alike but for their title blocks
        from semantic_pdf_diff.records import sheet_record
        from semantic_pdf_diff.schema import Figure
        sheet = Figure(id="fig:p2:0", page=2, bbox=(0, 0, 2592, 1728), kind="sheet", label="sheet A-202",
                       title="HALL D FLOOR PLAN - MEETING ROOMS", label_source="title block")
        record = sheet_record(2, sheet)
        self.assertEqual((record.id, record.kind, record.label, record.text, record.gives),
                         ("sheet:p2:sheet A-202", "sheet", "sheet A-202", "HALL D FLOOR PLAN - MEETING ROOMS",
                          ["subject", "scope"]))
        self.assertIsNone(sheet_record(2, sheet.model_copy(update={"label": None})))
        self.assertIsNone(sheet_record(2, None))

    def test_the_sheet_record_is_kept_only_when_on(self):
        from semantic_pdf_diff.schema import Figure
        sheet = Figure(id="fig:p1:0", page=1, bbox=(0, 0, 10, 10), kind="sheet", label="sheet A-201", title="HALL C")
        page = blocks("GENERAL NOTES", "1. ALL DIMENSIONS ARE TO FACE OF FINISH.")
        kinds = lambda s: [r.kind for r in s.page_structure(1, page, lambda: sheet)[1]]
        self.assertEqual(kinds(Settings()), ["note"])
        self.assertEqual(kinds(Settings(sheet_records=True)), ["note", "sheet"])
        self.assertEqual(Settings(sheet_records=True).page_structure(1, page, lambda: None)[1], [])  # no sheet

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
        off, on = Settings(records=False), Settings()
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

class Reported(unittest.TestCase):
    def test_a_claims_card_shows_its_name_as_printed_its_position_and_the_notes_reaching_it(self):
        from semantic_pdf_diff.report import Cards
        from test_pipeline import ev
        e = ev("A-1", position=Position(label="Condition 2", list="list:p1:0"), records=["list:p1:0", "note:p1:0"],
               printed="acknowledgement timeout")
        records = [{"content": e.content, "id": "list:p1:0", "kind": "list", "label": "", "text": LEAD},
                   {"content": e.content, "id": "note:p1:0", "kind": "note", "label": "GENERAL NOTES",
                    "text": "1. ALL DIMENSIONS ARE TO FACE OF FINISH."}]
        card = Cards({"evidence": [e.model_dump()], "files": [], "records": records}, lambda x: x)("A-1")
        self.assertIn("As printed: acknowledgement timeout", card)
        self.assertIn(f"Position: Condition 2 of “{LEAD}”", card)
        self.assertIn("Note: GENERAL NOTES — 1. ALL DIMENSIONS ARE TO FACE OF FINISH.", card)
        plain = Cards({"evidence": [ev("B-1").model_dump()], "files": []}, lambda x: x)("B-1")
        self.assertNotIn("As printed", plain)

    def test_reports_without_records_are_written_as_before(self):
        from semantic_pdf_diff.schema import EvidenceDocument
        document = EvidenceDocument(sources=[], files=[], interpreters={}, evidence=[], coverage=[], sections=[],
                                    situation={}, scan_issues=[])
        self.assertNotIn("records", document.model_dump())

class Editorial(unittest.TestCase):
    def test_a_renumbered_claim_is_an_editorial_change(self):
        from semantic_pdf_diff.report import finding_html, kinds_html
        from test_pipeline import ev
        a = ev("A-1", position=Position(label="Condition 2"))
        b = ev("B-1", position=Position(label="Condition 3"))
        self.assertEqual(Settings(editorial=True).editorial_notes(a, b), ["renumbered: Condition 2 → Condition 3"])
        self.assertEqual(Settings(editorial=False).editorial_notes(a, b), [])
        self.assertEqual(Settings(editorial=True).editorial_notes(a, ev("C-1", position=Position(label="Condition 2"))),
                         [])
        self.assertEqual(Settings(editorial=True).editorial_notes(a, ev("D-1")), [])  # no position: nothing to say
        finding = {"a": "A-1", "b": "B-1", "relation": "equivalent", "rationale": "same", "confidence": 0.9,
                   "retrieval_score": 1.0, "editorial": ["renumbered: Condition 2 → Condition 3"]}
        self.assertIn("Editorial: renumbered: Condition 2 → Condition 3", finding_html(finding, lambda i: ""))
        self.assertIn("<b>Editorial changes</b> (1): renumbered 1", kinds_html([finding], lambda x: x))

class Aligned(unittest.TestCase):
    def test_one_printed_label_is_one_property_however_readers_name_it(self):
        from semantic_pdf_diff.align import align, printed_property
        from test_pipeline import ev
        def pump(eid, attribute, value, printed):
            return ev(eid, entity="Pump P-101A", attribute=attribute, value=value, unit="gpm", conditions="",
                      printed=printed)
        earlier = [pump("A-1", "rated flow", "7,824", "P-101A | Capacity (gpm)"),
                   pump("A-2", "head", "134.8", "P-101A | TDH (ft)")]
        later = [pump("B-1", "duty point output", "7,900", "P-101A | Capacity (gpm)"),
                 pump("B-2", "head", "134.8", "P-101A | TDH (ft)")]
        self.assertEqual(align(earlier, later).judge, [])  # as read: no property in common, the change missed
        self.assertEqual([(i, j) for i, j, _ in align(earlier, later, printed=True).judge], [(0, 0)])
        self.assertEqual(printed_property("P-101A | Rated point > Capacity (gpm)").split(), ["Rated", "point",
                                                                                               "Capacity"])
        self.assertEqual(printed_property("lift hill rises"), "")  # a text claim's: not a label

class Restated(unittest.TestCase):
    def note(self, text, rid="note:p1:0"):
        from semantic_pdf_diff.schema import ContextRecord
        return ContextRecord(id=rid, kind="note", gives=["frame", "scope"], label="GENERAL NOTES", text=text, page=1)

    def test_a_restated_note_is_reported_once_with_the_claims_it_reaches(self):
        from semantic_pdf_diff.records import changed_records
        from test_pipeline import ev
        face = self.note("1. ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE.")
        stud = self.note("1. ALL DIMENSIONS ARE TO CENTERLINE OF STUD UNLESS NOTED OTHERWISE.")
        left = [ev("A-1", records=["note:p1:0"]), ev("A-2")]
        right = [ev("B-1", records=["note:p1:0"]).model_copy(update={"content": "later"})]
        found = changed_records({left[0].content: {face.id: face}}, {"later": {stud.id: stud}}, left, right)
        self.assertEqual([(c["kind"], c["label"], c["claims"]) for c in found],
                         [("note", "GENERAL NOTES", ["A-1", "B-1"])])
        self.assertEqual(changed_records({left[0].content: {face.id: face}}, {"later": {face.id: face}}, left, right),
                         [])
        # numbers aside: a value changed in a note is a value change, reported as one
        renumbered = self.note("2. ALL DIMENSIONS ARE TO FACE OF FINISH UNLESS NOTED OTHERWISE.")
        self.assertEqual(changed_records({left[0].content: {face.id: face}}, {"later": {face.id: renumbered}},
                                         left, right), [])
        off = Settings(record_changes=False)
        self.assertEqual(off.changed_records({"a": {face.id: face}}, {"b": {stud.id: stud}}, left, right), [])
        on = Settings()  # the default
        self.assertEqual(len(on.changed_records({"a": {face.id: face}}, {"b": {stud.id: stud}}, left, right)), 1)

    def test_an_item_inserted_or_a_window_moved_is_no_restatement(self):
        from semantic_pdf_diff.records import changed_records
        from semantic_pdf_diff.schema import ContextRecord
        from test_pipeline import ev
        lead = "A link failure is declared when any of the following conditions holds."
        three = ContextRecord(id="list:p1:0", kind="list", text=lead, items=["Condition 1", "Condition 2"])
        four = three.model_copy(update={"items": ["Condition 1", "Condition 2", "Condition 3"]})
        left, right = [ev("A-1", records=["list:p1:0"])], [ev("B-1", records=["list:p1:0"])]
        found = lambda a, b: changed_records({left[0].content: {a.id: a}}, {right[0].content: {b.id: b}}, left, right)
        self.assertEqual(found(three, four), [])  # labels are positions: an item inserted renumbers them
        self.assertEqual(len(found(three, four.model_copy(update={"text": "When the link is idle:"}))), 1)
        table = lambda text, rid="table:p1:0", label="page 1, table 1": ContextRecord(
            id=rid, kind="table", label=label, text="Above the table: ..." + text, items=["Tag", "Capacity (gpm)"])
        before = table("Creek WTP: Equipment. Table 1a. Raw water pumps P-101A 7,824 P-101B 8,837. Heights are above "
                       "the station platform. Table 1b. Blowers")
        moved = table("eek WTP: Equipment. Table 1a. Raw water pumps P-101A 7,824 P-101B 8,837 P-101C 7,650. Heights "
                      "are above the station platform. Table 1b. Blowers")
        self.assertEqual(found(before, moved), [])  # cut elsewhere, a row added above: the same lead-in
        regraded = table("Creek WTP: Equipment. Table 1a. Raw water pumps P-101A 7,824 P-101B 8,837. Heights are "
                         "above grade. Table 1b. Blowers")
        self.assertEqual(len(found(before, regraded)), 1)
        # an untitled table pairs by its headers, wherever it now sits
        third = table("Heights are above grade.", "table:p1:2", "page 1, table 3")
        self.assertEqual([c["later"]["id"] for c in found(before, third)], ["table:p1:2"])

    def test_the_report_lists_it_and_marks_the_findings_it_reaches(self):
        from semantic_pdf_diff.report import finding_html, record_changes_html
        change = {"kind": "note", "label": "GENERAL NOTES", "claims": ["A-1", "B-1"],
                  "earlier": {"text": "1. ALL DIMENSIONS ARE TO FACE OF FINISH.", "items": []},
                  "later": {"text": "1. ALL DIMENSIONS ARE TO CENTERLINE OF STUD.", "items": []}}
        html = record_changes_html([change], lambda x: x)
        self.assertIn("Context changes (1)", html)
        self.assertIn("“1. ALL DIMENSIONS ARE TO FACE OF FINISH.” → “1. ALL DIMENSIONS ARE TO CENTERLINE OF STUD.”; "
                      "reaches 2 claims", html)
        self.assertEqual(record_changes_html([], lambda x: x), "")
        finding = {"a": "A-1", "b": "B-1", "relation": "equivalent", "rationale": "same", "confidence": 0.9,
                   "retrieval_score": 1.0, "context_changed": ["GENERAL NOTES"]}
        self.assertIn("Context changed: GENERAL NOTES", finding_html(finding, lambda i: ""))

class Judged(unittest.TestCase):
    """The judge_context lever: each claim's context records shown to the judge, subject, scope and frame ruled on
    apart (the claim context plan's milestone 4)."""
    def records(self):
        from semantic_pdf_diff.schema import ContextRecord
        return {"note:p1:0": ContextRecord(id="note:p1:0", kind="note", label="GENERAL NOTES", page=1,
                                           text="1. ALL DIMENSIONS ARE TO FACE OF FINISH."),
                "list:p1:0": ContextRecord(id="list:p1:0", kind="list", text="Clear widths:", parent="note:p1:0"),
                "table:p1:0": ContextRecord(id="table:p1:0", kind="table", label="Room schedule",
                                            items=["Room", "Width"])}

    def test_a_claims_records_as_the_judge_sees_them(self):
        from semantic_pdf_diff.records import context_shown
        from test_pipeline import ev
        shown = context_shown(ev("A-1", records=["list:p1:0", "table:p1:0", "note:p1:0"]), self.records())
        self.assertEqual(shown, {"context": ["note: GENERAL NOTES: 1. ALL DIMENSIONS ARE TO FACE OF FINISH.",
                                             "list: Clear widths:", "table: Room schedule: (columns: Room | Width)"]})
        self.assertEqual(context_shown(ev("A-2"), self.records()), {})
        self.assertEqual(context_shown(ev("A-3", records=["gone"]), self.records()), {})

    def test_the_judges_request_shows_context_and_asks_for_rulings_only_when_on(self):
        from semantic_pdf_diff.compare import RULINGS, pair_request
        from semantic_pdf_diff.schema import Judgment, RuledJudgment
        from test_pipeline import ev
        a, b = ev("A-1", records=["note:p1:0"]), ev("B-1", records=["note:p1:0"])
        records = {a.content: self.records(), b.content: self.records()}
        off, on = Settings(), Settings(judge_context=True)
        prompt, _, payload, _ = pair_request(off, "revisions", a, b, records=records)
        self.assertNotIn("FACE OF FINISH", prompt)
        self.assertNotIn(RULINGS, prompt)
        self.assertEqual(off.judging(), ("", Judgment))
        prompt, _, shown, _ = pair_request(on, "revisions", a, b, records=records)
        self.assertEqual(prompt.count("note: GENERAL NOTES: 1. ALL DIMENSIONS ARE TO FACE OF FINISH."), 2)
        self.assertIn(RULINGS, prompt)
        self.assertEqual(shown, payload)  # the fields returned (the explainer's) are the claims' own
        self.assertEqual(on.judging(), (RULINGS, RuledJudgment))

    def test_a_part_ruled_different_makes_a_confident_relation_uncertain(self):
        from semantic_pdf_diff.compare import vetoes
        from semantic_pdf_diff.schema import RuledJudgment
        from test_pipeline import ev
        a, b = ev("A-1"), ev("B-1")
        ruled = dict(rationale="r", confidence=0.9, same_conditions=True, same_subject="yes", same_scope="yes")
        self.assertEqual(vetoes(RuledJudgment(relation="equivalent", same_frame="no", **ruled), a, b, None),
                         ["The claims' frame differs"])
        self.assertEqual(vetoes(RuledJudgment(relation="equivalent", same_frame="unknown", **ruled), a, b, None), [])
        self.assertEqual(vetoes(RuledJudgment(relation="complementary", same_frame="no", **ruled), a, b, None), [])

    def test_the_comparison_interpreter_names_it(self):
        from semantic_pdf_diff.provenance import comparison_interpreter
        self.assertNotEqual(comparison_interpreter(Settings()).prompt_hash,
                            comparison_interpreter(Settings(judge_context=True)).prompt_hash)

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

    def test_revisions_with_a_restated_lead_in(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from semantic_pdf_diff import cli
        from test_concurrency import jittery_model
        items = "\n\nCondition 1: the heater draws 12 kW.\n\nCondition 2: the fan draws 3 kW.\n"
        later = "A link failure is declared when all of the following conditions hold."
        with tempfile.TemporaryDirectory() as d, jittery_model() as (url, _):
            a, b, config = Path(d) / "a" / "spec.md", Path(d) / "b" / "spec.md", Path(d) / "settings.json"
            for path, lead in ((a, LEAD), (b, later)):
                path.parent.mkdir()
                path.write_text(f"# Loads\n\n{lead}{items}")
            config.write_text(json.dumps({"record_changes": True}))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main(["compare", str(a.parent), str(b.parent), "--store", str(Path(d) / "out"), "--base-url",
                          url, "--no-situate", "--config", str(config), "--mode", "revisions"])
            report = json.loads((Path(d) / "out" / "report.json").read_text())
            html = (Path(d) / "out" / "report.html").read_text()
        (change,) = report["record_changes"]
        self.assertEqual((change["kind"], change["earlier"]["text"], change["later"]["text"]), ("list", LEAD, later))
        self.assertEqual(len(change["claims"]), 4)  # two conditions' claims on each side
        self.assertTrue(all(f.get("context_changed") == ["list"] for f in report["findings"]
                            if f["a"] in change["claims"]))
        self.assertIn("Context changes (1)", html)

if __name__ == "__main__":
    unittest.main()
