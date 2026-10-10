"""Tables read by rules a model writes (tablerules.py; the adapters plan, "Excel, in detail", step 5): the analysis and
our opinion the model is shown, its rules applied to every row, checked against its own examples, and the summary
templates computed."""
import stubs  # noqa: F401 (a clean environment)
import datetime
import unittest
from types import SimpleNamespace

from semantic_pdf_diff import tablegrid as tg, tablerules as tr

def pumps():
    """A schedule: tags, two quantities with units in their headers, a section row, a provisional value."""
    rows = [["Duty pumps", "", ""], ["P-1", "118", "24.1"], ["P-2", "120", "25.5"],
            ["Standby", "", ""], ["P-3", "TBC", "25.5"]]
    return tg.grid(["B", "C", "D"], ["Tag", "Flow (L/s)", "Head [m]"], rows, range(5, 10), range(11, 16),
                   "Pump schedule", "Summary!B4:D9")

def polar(n=331):
    rows = [[str(a), f"{0.11 * a:.3f}", f"{0.006 + 0.0001 * a * a:.4f}"] for a in range(-165, -165 + n)]
    return tg.grid(["A", "B", "C"], ["alpha [deg]", "c_l", "c_d"], rows, range(4, 4 + n), range(10, 10 + n),
                   "FFA-W3-211", "Polar!A3:C334")

class Analysis(unittest.TestCase):
    def test_columns_counted_and_section_rows_kept_apart(self):
        g = pumps()
        self.assertEqual(g.names, ["6", "7", "9"])
        self.assertEqual(g.sections, ["Duty pumps", "Duty pumps", "Standby"])
        self.assertEqual(g.keys, [1, 2, 4])
        tag, flow, head = tr.analyse(g)
        self.assertEqual((flow.numbers, flow.texts, flow.low, flow.high), (2, 1, "", ""))  # TBC: not all numbers
        self.assertEqual((head.numbers, head.low, head.high, head.distinct), (3, "24.1", "25.5", 2))
        self.assertIn("text 3; all distinct", tr.describe(tag))

    def test_a_headers_own_name_and_unit(self):
        self.assertEqual((tg.header_name("Hydraulics > Capacity (gpm)"), tg.header_unit("Hydraulics > Capacity (gpm)")),
                         ("Capacity", "gpm"))
        self.assertEqual(tg.header_name("alpha [deg]"), "alpha")
        g = tg.grid(["A", "B"], ["Valve", "Pressure (bar) > Inlet"], [["V-1", "6.2"]], [3], [5])
        self.assertEqual(tr._fill("{B.group} | {B.name} | {B.unit}", g, 0)[0], "Pressure | Inlet | bar")

    def test_a_series_is_seen_and_summarising_suggested(self):
        g = polar()
        alpha = tr.analyse(g)[0]
        self.assertEqual((alpha.order, alpha.step, alpha.low, alpha.high), ("rising", "1", "-165", "165"))
        self.assertEqual(tr.opinion(g, tr.analyse(g)), "a series (mostly numbers, column A rising in steps of 1): a "
                                                        "summary (series) may serve better than 662 claims")

    def test_a_shape_of_points_suggests_a_summary_too(self):
        import math
        rows = [[f"{math.cos(k / 20):.4f}", f"{0.1 * math.sin(k / 20):.4f}"] for k in range(126)]
        g = tg.grid(["A", "B"], ["x/c", "y/c"], rows, range(5, 131), range(5, 131))
        self.assertTrue(tr.opinion(g, tr.analyse(g)).startswith("a set of points (mostly numbers, no column in order"))

    def test_sentences_are_prose_read_row_by_row(self):
        rows = [[f"REQ-{k:03d}", f"The pumping station shall deliver {k} L/s at the design head.",
                 ["Performance", "Controls"][k % 2]] for k in range(150)]
        g = tg.grid(["A", "B", "C"], ["ID", "Requirement", "Type"], rows, range(5, 155), range(5, 155))
        cols = tr.analyse(g)
        self.assertEqual([c.prose for c in cols], [False, True, False])  # 11 words, under 60 characters
        said = tr.opinion(g, cols)
        self.assertTrue(said.startswith("rows of prose (column B: 11 words on average): each row read by itself; "))
        self.assertTrue(said.endswith("a summary (list) counting them by column C"))
        self.assertIn("B: Requirement: text 150; all distinct; prose: 11 words", tr.question(g, cols))

    def test_a_short_notes_column_is_an_aside(self):
        rows = [[f"M{k}"] + [f"{k + c}.25" for c in range(12)] + ["see note 4 of annex B"] for k in range(8)]
        g = tg.grid([chr(65 + c) for c in range(14)], ["Material"] + [f"P{c}" for c in range(12)] + ["Notes"], rows,
                    range(2, 10), range(2, 10))
        said = tr.opinion(g, tr.analyse(g))
        self.assertTrue(said.startswith("claims from rows by rules: about 104 claims"))
        self.assertTrue(said.endswith("; column N holds prose (6 words on average): rows read by themselves if its "
                                      "words hold claims"))

    def test_a_log_steps_in_minutes(self):
        start = datetime.datetime(2026, 7, 1)
        rows = [[(start + datetime.timedelta(minutes=5 * i)).isoformat(" "), f"{95 + i % 7}.5"] for i in range(200)]
        g = tg.grid(["A", "B"], ["Timestamp", "Flow (L/s)"], rows, range(2, 202), range(2, 202))
        time = tr.analyse(g)[0]
        self.assertEqual((time.dates, time.order, time.step), (200, "rising", "5 min"))
        self.assertTrue(tr.opinion(g, tr.analyse(g)).startswith("a log (mostly numbers, column A rising in steps of "
                                                                 "5 min): a summary (log) may serve better"))

    def test_a_summary_is_weighed_by_size_without_a_cut_off(self):
        said = {n: tr.opinion(polar(n), tr.analyse(polar(n))) for n in (10, 30, 331)}
        self.assertEqual(said[10], "claims from rows by rules: about 20 claims, 2 a row (a series, mostly numbers, column"
                                   " A rising in steps of 1; with 10 rows a summary would save little)")
        self.assertEqual(said[30], "a series (mostly numbers, column A rising in steps of 1): a summary (series) or "
                                   "claims from rows by rules (about 60): a summary if the rows are samples rather than "
                                   "facts each worth checking")
        self.assertIn("may serve better than 662 claims", said[331])

    def test_the_question_shows_samples_size_and_our_opinion(self):
        asked = tr.question(polar())
        self.assertIn("TABLE: Polar!A3:C334; title: FFA-W3-211", asked)
        self.assertIn("SIZE: 331 rows, 3 columns; a claim per value cell would give about 662 claims", asked)
        self.assertIn("A: alpha [deg]: numbers 331; -165 to 165; rising; in steps of 1; all distinct", asked)
        self.assertIn("4 | -165 | -18.150 | 2.7285", asked)
        self.assertIn("... (rows 9 to 85 not shown)", asked)
        self.assertIn("OUR HEURISTIC OPINION (a guess", asked)
        self.assertIn("SECTIONS (section rows label the rows below them): Duty pumps (rows 6 to 7); Standby (rows 9 "
                      "to 9)", tr.question(pumps()))

class Applying(unittest.TestCase):
    RULES = {"reading": "rules", "subject": "PS-3 pumps",
             "claims": [{"columns": "C:D", "entity": "{B}", "attribute": "{*.name}", "value": "{*}", "unit": "{*.unit}",
                         "conditions": "{section}", "number": True}],
             "examples": [{"row": 6, "claims": [{"entity": "P-1", "attribute": "Flow", "value": "118", "unit": "L/s"},
                                                {"entity": "P-1", "attribute": "Head", "value": 24.1, "unit": "m"}]}]}

    def test_rules_give_every_rows_claims_and_a_misfit_is_named(self):
        g, rules = pumps(), tr.Rules.model_validate(self.RULES)
        made = tr.row_claims(rules, g, 0)
        self.assertEqual([(f["entity"], f["attribute"], f["value"], f["unit"], f["conditions"]) for f, _, _ in made],
                         [("P-1", "Flow", "118", "L/s", "Duty pumps"), ("P-1", "Head", "24.1", "m", "Duty pumps")])
        self.assertEqual(made[0][1], [0, 1])  # the cells it came from: B and C
        with self.assertRaisesRegex(tr.Misfit, "C9 isn't a number: 'TBC'"):
            tr.row_claims(rules, g, 2)
        self.assertEqual(tr.problems(rules, g), [])  # one row in three: read by itself, not a problem

    def test_rules_must_give_their_own_examples(self):
        g = pumps()
        wrong = tr.Rules.model_validate({**self.RULES, "examples": [{"row": "7", "claims": [{"value": "121",
                                                                                            "unit": "L/s"}]}]})
        self.assertEqual(tr.problems(wrong, g), ["row 7: the templates give 120 L/s; 25.5 m, not 121 L/s"])
        by_place = tr.Rules.model_validate({**self.RULES, "examples": [{"row": "2", "claims": [{"value": "120",
                                                                                                  "unit": "L/s"}]}]})
        self.assertEqual(tr.problems(by_place, g), [])  # row 7, the second shown, named by its place: still checked
        unknown = tr.Rules.model_validate({**self.RULES, "claims": [{"entity": "{B}", "attribute": "x",
                                                                     "value": "{Q}"}]})
        self.assertEqual(tr.problems(unknown, g), ["no column Q in the table"])
        self.assertTrue(tr.problems(tr.Rules(reading="sideways"), g)[0].startswith("unknown reading 'sideways'"))
        self.assertEqual(tr.problems(tr.Rules(reading="rows"), g), [])
        # the cell named {B.cell_value}; an example parting value and unit otherwise than the cell (10.2 and ")
        g = tg.grid(["A", "B"], ["", "UV"], [["FOV", '10.2"'], ["Pixel", '14.2"']], [2, 3], [0, 0])
        quoted = tr.Rules.model_validate({"reading": "rules", "claims": [{"entity": "{B.header}", "attribute": "{A}",
                                                                          "value": "{B.cell_value}"}],
                                          "examples": [{"row": 2, "claims": [{"value": "10.2", "unit": '"'}]}]})
        self.assertEqual(tr.problems(quoted, g), [])

    def test_a_tolerance_column_is_its_values_uncertainty(self):
        g = tg.grid(["A", "B", "C"], ["Parameter", "Measured (L/s)", "±"], [["Flow", "118", "3"], ["Head", "24.1", ""]],
                    [5, 6], [5, 6])
        rules = tr.Rules.model_validate({"reading": "rules", "claims": [
            {"entity": "pump", "attribute": "{A}", "value": "{B}", "unit": "{B.unit}", "uncertainty": "± {C} {B.unit}"}]})
        flow, = tr.row_claims(rules, g, 0)
        self.assertEqual((flow[0]["value"], flow[0]["uncertainty"]), ("118", "± 3 L/s"))
        self.assertEqual(flow[1], [0, 1, 2])  # the cells it came from, the tolerance's too
        head, = tr.row_claims(rules, g, 1)
        self.assertEqual(head[0]["uncertainty"], "")  # no tolerance given: none stated
        self.assertIn("uncertainty ± {C} {B.unit}", tr.describe_rule(rules.claims[0]))

    def test_a_sideways_table_and_units_outside_brackets(self):
        rows = [["Capital cost ($M)", "6.35", "2.82"], ["Annual energy use (MWh/yr)", "771", "n/a"]]
        g = tg.grid(["A", "B", "C"], ["", "Option A: UV", "Option B: chlorine"], rows, [5, 6], [11, 12])
        sideways = tr.Rules.model_validate({"reading": "rules", "claims": [{
            "columns": "B:C", "entity": "{*.header}", "attribute": "{A.cell_name}", "value": "{*.value}",
            "unit": "{A.cell_unit}", "number": True}], "examples": [{"row": "6", "claims": [
                {"value": "771", "unit": "MWh/yr"}, {"value": "n/a"}]}]})
        made = [(f["entity"], f["attribute"], f["value"], f["unit"]) for f, _, _ in tr.row_claims(sideways, g, 1)]
        self.assertEqual(made, [("Option A: UV", "Annual energy use", "771", "MWh/yr")])  # n/a: no claim
        self.assertEqual(tr.problems(sideways, g), [])  # an example's n/a: no claim by the templates' own rule
        g = tg.grid(["A", "B", "C"], ["Element", "Height (ft)", "Vertical g"], [["E1", "129", "2.58"]], [5], [11])
        unitless = tr.Rules.model_validate({"reading": "rules", "claims": [{
            "columns": "B:C", "entity": "{A}", "attribute": "{*.name}", "value": "{*}", "unit": "{*.unit}"}],
            "examples": [{"row": "5", "claims": [{"value": "129", "unit": "ft"}, {"value": "2.58", "unit": "g"}]}]})
        self.assertEqual(tr.problems(unitless, g), ['row 5: the templates give 129 ft; 2.58, not 2.58 g (column C\'s '
                                                    'header "Vertical g" has no unit in brackets for .unit to take: give '
                                                    'such columns a template of their own, the unit written out)'])

    def test_no_stray_words_and_no_unitless_twin(self):
        g = tg.grid(["A", "B"], ["Parameter", "Turbine"], [["Hub diameter [m]", "7.94"], ["Turbine class", "IB"]],
                    [2, 3], [5, 6])
        rules = tr.Rules.model_validate({"reading": "rules", "claims": [
            {"columns": "B", "entity": "{B.header}", "attribute": "{A.cell_name}", "value": "{*}", "unit": "{A.cell_unit}",
             "conditions": "in {title}"},
            {"columns": "B", "entity": "{B.header}", "attribute": "{A.cell_name}", "value": "{*}", "conditions": "in {title}"}]})
        made = [(f["attribute"], f["value"], f["unit"], f["conditions"]) for f, _, _ in tr.row_claims(rules, g, 0)]
        self.assertEqual(made, [("Hub diameter", "7.94", "m", "")])  # no "in", and the unitless twin left out
        self.assertEqual(len(tr.row_claims(rules, g, 1)), 1)  # a row with no unit: the two alike, kept once

    def test_an_example_of_a_row_read_by_itself_is_no_problem(self):
        g, rules = pumps(), tr.Rules.model_validate({**Applying.RULES, "examples": [{"row": "9", "claims": [
            {"value": "TBC"}]}]})
        self.assertEqual(tr.problems(rules, g), [])  # row 9's flow isn't a number: it's read by itself anyway

class Summaries(unittest.TestCase):
    def test_a_series_gives_its_range_extremes_and_points(self):
        rules = tr.Rules(reading="summary", template="series", subject="FFA-W3-211", input="A", quantities=["B"],
                         points=["0", "12"])
        g = polar()
        self.assertEqual(tr.problems(rules, g), [])
        found = [(s.fields["attribute"], s.fields["value"], s.fields["unit"], s.fields["conditions"], s.computed)
                 for s in tr.summarise(rules, g)]
        self.assertEqual(found, [("alpha range", "-165 to 165", "deg", "331 points, in steps of 1", False),
                                 ("maximum c_l", "18.150", "", "at alpha = 165 deg", False),
                                 ("minimum c_l", "-18.150", "", "at alpha = -165 deg", False),
                                 ("c_l", "0.000", "", "at alpha = 0 deg", False),
                                 ("c_l", "1.320", "", "at alpha = 12 deg", False)])

    def test_a_log_gives_span_extremes_mean_and_last(self):
        rows = [["2026-07-01 00:00:00", "95.0"], ["2026-07-01 00:05:00", "101.5"], ["2026-07-01 00:10:00", "98.0"]]
        g = tg.grid(["A", "B"], ["Timestamp", "Flow (L/s)"], rows, range(2, 5), range(2, 5))
        rules = tr.Rules(reading="summary", template="log", subject="PS-3", input="A", quantities=["B"])
        found = {s.fields["attribute"]: (s.fields["value"], s.fields["conditions"], s.computed)
                 for s in tr.summarise(rules, g)}
        self.assertEqual(found["Timestamp span"], ("2026-07-01 00:00:00 to 2026-07-01 00:10:00", "3 samples", False))
        self.assertEqual(found["maximum Flow"], ("101.5", "at Timestamp = 2026-07-01 00:05:00", False))
        self.assertEqual(found["mean Flow"], ("98.17", "over 3 samples", True))
        self.assertEqual(found["last Flow"][0], "98.0")

    def test_a_list_counts_its_rows_by_category(self):
        rows = [[f"R1-{k}", ["Agreed", "Agreed", "Noted"][k % 3]] for k in range(30)]
        g = tg.grid(["A", "B"], ["TDoc", "Status"], rows, range(2, 32), range(2, 32))
        rules = tr.Rules(reading="summary", template="list", subject="RAN1 contributions", categories=["B"])
        found = [(s.fields["value"], s.fields["conditions"]) for s in tr.summarise(rules, g)]
        self.assertEqual(found, [("30", ""), ("20", "Status = Agreed"), ("10", "Status = Noted")])



class Traced(unittest.TestCase):
    """How a table was read, in reports (the owner, 2026-10-05: "tracing/reporting how a table was read")."""
    def test_findings_between_tables_read_differently_are_flagged(self):
        from semantic_pdf_diff.report import how_read, tables_read
        rules = lambda conditions: {"derivation": [{"step": "xlsx-table"}, {"step": "table-rules",
                                                                           "detail": f"value {{B}}; conditions {conditions}"}]}
        row = {"derivation": [{"step": "xlsx-table"}, {"step": "model-extraction"}]}
        text = {"derivation": [{"step": "xlsx-cells"}, {"step": "model-extraction"}]}
        self.assertEqual(how_read(row), ("row", ""))
        self.assertIsNone(how_read(text))
        self.assertEqual(tables_read(row, rules("{A}")), {"a": "its row read by itself",
                                                          "b": "by rules a model wrote for its table (value {B}; conditions {A})"})
        self.assertIsNotNone(tables_read(rules("in the plant"), rules("{A}")))  # bound by different templates
        self.assertIsNone(tables_read(rules("{A}"), rules("{A}")))
        self.assertIsNone(tables_read(row, row))
        self.assertIsNone(tables_read(row, text))



class PdfTables(unittest.TestCase):
    """PDF tables on the grid (tables.pdf_grid) and the vision check (transcription_mismatch)."""
    def test_a_parsed_table_on_the_grid_with_simple_repairs(self):
        from semantic_pdf_diff.tables import pdf_grid
        g = pdf_grid(["Tag", "Service", None, "Flow (gpm)"],
                     [["P-1", "Raw water", "", "450"], ["", "transfer", "", None], ["Standby", "", "", ""],
                      ["P-2", "Backwash", "", "300"]], [(0, 10, 1, 20), (0, 20, 1, 30), (0, 30, 1, 40), (0, 40, 1, 50)])
        self.assertEqual(g.labels, ["Tag", "Service", "Service", "Flow (gpm)"])  # a merged header cell spans
        self.assertEqual(g.rows, [["P-1", "Raw water transfer", "", "450"], ["P-2", "Backwash", "", "300"]])
        self.assertEqual((g.sections, g.keys, g.boxes), (["", "Standby"], [0, 3], [(0, 10, 1, 30), (0, 40, 1, 50)]))
        self.assertIsNone(pdf_grid(["A", "B"], [["1", "2"]], [None]))  # rows without boxes: read row by row

    def test_a_parsed_table_repaired_into_parts(self):
        from semantic_pdf_diff.tables import pdf_parts
        box = lambda k: (0, k, 1, k + 1)
        # a header over two lines (a second level under merged cells), an empty row, then a stacked table
        parts = pdf_parts(["Tag", "Rated point", None],
                          [["", "", ""], ["", "Capacity (gpm)", "Head (ft)"], ["P-1", "450", "120"], ["P-2", "up to 173", "95"],
                           ["Blower", "Airflow (scfm)", "Power (hp)"], ["B-1", "900", "40"]], [box(k) for k in range(6)])
        self.assertEqual([p[0] for p in parts], [["Tag", "Rated point > Capacity (gpm)", "Rated point > Head (ft)"],
                                                 ["Blower", "Airflow (scfm)", "Power (hp)"]])
        self.assertEqual([p[1] for p in parts], [[["P-1", "450", "120"], ["P-2", "up to 173", "95"]], [["B-1", "900", "40"]]])
        self.assertEqual([p[2] for p in parts], [[box(2), box(3)], [box(5)]])
        # a wrapped header line, without merged cells, joins as the next line
        (head, body, _), = pdf_parts(["Ride", "Entry"], [["", "speed (mph)"], ["Coaster", "55"]], [box(0), box(1)])
        self.assertEqual((head, body), (["Ride", "Entry speed (mph)"], [["Coaster", "55"]]))
        # a table of words alone is left as it was
        self.assertEqual(pdf_parts(["Tag", "Service"], [["P-1", "Raw water"], ["P-2", "Backwash"]], [box(0), box(1)]),
                         [(["Tag", "Service"], [["P-1", "Raw water"], ["P-2", "Backwash"]], [box(0), box(1)])])

    def test_rows_joined_across_boundaries_without_a_rule(self):
        from semantic_pdf_diff.tables import ruled_rows
        box = lambda y0, y1: (0, y0, 100, y1)
        rows = [["", "UV", "IR"], ["Cameras", None, None], ["FOV", "10.2", "3.8"], ["Detector", "1×1", "1×1"],
                ["", "CCD201", "LMAPD"], ["Spectrometer", "7", "40"], ["resolution", "", ""], ["Width", "1024", "256"],
                ["Height", "512", "128"]]
        boxes = [box(0, 6), box(6, 12), box(12, 24), box(24, 30), box(30, 36), box(36, 42), box(42, 48), box(48, 60),
                 box(60, 72)]
        # rules under the header, FOV, Detector's two lines, Spectrometer's; none between Width and Height (both
        # labelled with numbers in the same column: they stay apart)
        joined, kept, n = ruled_rows(rows, boxes, [0, 12, 24, 36, 48, 72])
        self.assertEqual(n, 3)
        self.assertEqual(joined, [["Cameras", "UV", "IR"], ["FOV", "10.2", "3.8"], ["Detector", "1×1 CCD201", "1×1 LMAPD"],
                                  ["Spectrometer resolution", "7", "40"], ["Width", "1024", "256"], ["Height", "512", "128"]])
        self.assertEqual(kept[2], box(24, 36))
        self.assertEqual(ruled_rows(rows, boxes, [0, 72])[2], 0)  # too few rules to tell: unchanged
        self.assertEqual(ruled_rows(rows, boxes, [b[1] for b in boxes])[2], 0)  # every boundary ruled

    def test_drawn_rules_and_row_styles_read_from_the_page(self):
        import pymupdf
        from semantic_pdf_diff.tables import Marks
        doc = pymupdf.open()
        page = doc.new_page(width=300, height=200)
        page.draw_rect(pymupdf.Rect(10, 10, 210, 30), color=None, fill=(0.1, 0.2, 0.4))  # a header's fill
        page.insert_text((20, 24), "Pump", fontname="hebo")
        page.insert_text((120, 24), "Flow", fontname="hebo")
        page.insert_text((20, 44), "P-1", fontname="helv")
        page.insert_text((120, 44), "450", fontname="helv")
        for x0, x1 in ((10, 110), (110, 210)):  # a rule drawn in two segments
            page.draw_line((x0, 30), (x1, 30))
        page.draw_line((10, 50), (60, 50))  # too short to be a rule
        marks = Marks(page)
        self.assertEqual([round(y) for y in marks.rules((10, 10, 210, 50))], [30])
        head, row = marks.styles((10, 10, 210, 50), [(10, 10, 210, 30), (10, 30, 210, 50)])
        self.assertEqual(head, ((0.1, 0.2, 0.4), True))
        self.assertEqual(row, (None, False))

    def test_words_cut_by_a_column_line(self):
        import pymupdf
        from semantic_pdf_diff.tables import Marks, column_edges
        page = pymupdf.open().new_page(width=300, height=200)
        page.insert_text((20, 40), "C-19")
        page.insert_text((100, 40), "7.4 m")  # "7.4" crosses the boundary at x 108
        page.insert_text((150, 40), "249")
        cells = lambda: [(10, 30, 60, 45), (60, 30, 108, 45), (108, 30, 140, 45), (140, 30, 200, 45)]
        table = SimpleNamespace(rows=[SimpleNamespace(cells=cells()), SimpleNamespace(cells=cells())])
        edges = column_edges(table)
        self.assertEqual(edges, [60, 108, 140])
        self.assertEqual(Marks(page).cuts((10, 30, 200, 45), edges), {1})
        self.assertEqual(Marks(page).cuts((10, 30, 200, 45), [60, None, 140]), set())
        self.assertIsNone(column_edges(SimpleNamespace(rows=[])))

    def test_columns_joined_where_every_split_word_is_cut(self):
        from semantic_pdf_diff.tables import cut_columns, split_cuts

        class Marks:  # the boundaries a row's words are cut by, by the row's top
            def __init__(self, cuts): self.by_top = cuts
            def cuts(self, box, edges): return self.by_top.get(box[1], set())

        rows = [["Column", "Footing", None, "Base elev. (", "ft)"], ["C-18", "10.3", None, "716.7", None],
                ["C-19", "7.", "4", "719.3", None], ["C-20", "6.8", None, "756.", "7"]]
        boxes = [(0, k, 1, k + 1) for k in range(4)]
        marks = Marks({0: {3}, 2: {1}, 3: {3}})
        joined, edges, n = cut_columns(rows, boxes, [10, 20, 30, 40], marks)
        self.assertEqual(n, 2)
        self.assertEqual(joined, [["Column", "Footing", "Base elev. (ft)"], ["C-18", "10.3", "716.7"],
                                  ["C-19", "7.4", "719.3"], ["C-20", "6.8", "756.7"]])
        self.assertEqual(edges, [10, 30])
        # a boundary with two separate values in a row, uncut, stays
        rows[1][2] = "2"
        self.assertEqual(cut_columns(rows, boxes, [10, 20, 30, 40], marks)[2], 1)
        # a cut counts only where it parts text across two filled cells
        self.assertEqual(split_cuts(["C-11", "738.9", None], (0, 0, 1, 1), [10, 20], Marks({0: {1}})), set())
        self.assertEqual(split_cuts(["C-19", "7.", "4"], (0, 0, 1, 1), [10, 20], Marks({0: {1}})), {1})

    def test_a_stacked_header_needs_a_header_style_when_styles_are_known(self):
        from semantic_pdf_diff.tables import pdf_parts
        body = [["FOV", "10.2", "3.8"], ["Spectrometer type", "Slit", "IFS"], ["Width", "1024", "256"],
                ["Blower", "Airflow (scfm)", "Power (hp)"], ["B-1", "900", "40"]]
        plain, header = (None, False), ((0.1, 0.2, 0.4), True)
        parts = pdf_parts(["Camera", "UV", "IR"], body, [(0, k, 1, k + 1) for k in range(5)],
                          [plain, plain, plain, header, plain])
        self.assertEqual([p[0][0] for p in parts], ["Camera", "Blower"])  # "Spectrometer type" stays a row
        self.assertEqual(len(parts[0][1]), 3)

    def test_a_row_copied_from_the_image_checks_the_text_layer(self):
        g = tg.grid(["A", "B"], ["Tag", "Flow"], [["P-1", "1,450"], ["P-2", "Δp 3"]], [2, 3], [0, 0])
        same = tr.Rules.model_validate({"transcribed": {"row": 2, "cells": ["P-1", "1450"]}})
        self.assertEqual(tr.transcription_mismatch(same, g), "")  # commas and case folded
        lost = tr.Rules.model_validate({"transcribed": {"row": "row 3", "cells": ["P-2", "Δp 3"]}})
        g.rows[1] = ["P-2", "p 3"]  # a symbol the text layer lost
        self.assertTrue(tr.transcription_mismatch(lost, g).startswith("row 3: the text layer reads P-2 | p 3"))
        self.assertEqual(tr.transcription_mismatch(tr.Rules(), g), "")  # nothing copied: nothing to check
        words = tg.grid(["A", "B", "C"], ["", "", ""], [["Raw", "water", "pumps"]], [2], [0])
        header = tr.Rules.model_validate({"transcribed": {"row": 2, "cells": ["Raw water pumps"]}})
        self.assertEqual(tr.transcription_mismatch(header, words), "")  # no value in the row: nothing claims rest on

if __name__ == "__main__":
    unittest.main()
