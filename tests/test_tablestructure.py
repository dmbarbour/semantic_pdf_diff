"""A PDF table's structure asked as rules where the heuristics leave suspect lines (tablestructure.py)."""
import unittest
from types import SimpleNamespace

import stubs  # noqa: F401 (a clean environment)
from semantic_pdf_diff import tablestructure as ts

HEADER = ["Camera", "UV", "IR"]
BODY = [["FOV", "10.2", "3.8"], ["Detector", "1×1", "1×1"], ["", "CCD201", "LMAPD"], ["Spectrometer", "7", "40"],
        ["resolution", "", ""], ["Bands", "0.2–0.45", "0.9–1.8"], ["", "µm", "µm"]]
BOXES = [(0, 10 * k, 100, 10 * k + 10) for k in range(1, 8)]

def answer(**fields):
    return ts.Structure.model_validate(fields)

class Signals(unittest.TestCase):
    def test_each_line_tagged_with_why_it_may_not_be_a_row(self):
        rules = [10, 20, 40, 60, 80]  # no rule above lines 3, 5 and 7
        tags = ts.signals(HEADER, BODY, BOXES, None, rules)
        self.assertEqual(tags[2], ["no rule above", "first cell empty"])
        self.assertEqual(tags[4], ["no rule above", "only its first cell"])
        self.assertEqual(tags[6], ["no rule above", "first cell empty", "units only"])
        self.assertEqual(tags[0], [])
        self.assertEqual(ts.signals(HEADER, BODY, BOXES, None, [10, 80])[2], ["first cell empty"])  # too few rules

    def test_a_styled_lone_label_is_a_section_not_a_suspect(self):
        body = [["FOV", "1", "2"], ["Spectrometers", "", ""], ["FOV", "3", "4"], ["Width", "5", "6"]]
        plain, dark = (None, False), ((0.1, 0.2, 0.4), True)
        tags = ts.signals(HEADER, body, BOXES[:4], [plain, dark, plain, plain])
        self.assertEqual(tags[1], [])
        self.assertEqual(ts.signals(HEADER, body, BOXES[:4])[1], ["only its first cell"])

    def test_an_empty_first_cell_without_a_digit_is_left_to_the_heuristics(self):
        self.assertFalse(ts.suspect(["first cell empty"], ["", "transfer", ""]))
        self.assertTrue(ts.suspect(["first cell empty"], ["", "CCD201", ""]))

class Applying(unittest.TestCase):
    def setUp(self):
        self.tags = ts.signals(HEADER, BODY, BOXES, None, [10, 20, 40, 60, 80])

    def test_rules_regroup_lines_into_rows(self):
        a = answer(rules=[{"action": "join above", "when": ["no rule above"]}])
        got = ts.apply(a, HEADER, BODY, BOXES, self.tags)
        (head, rows, boxes), = got.parts
        self.assertEqual(rows, [["FOV", "10.2", "3.8"], ["Detector", "1×1 CCD201", "1×1 LMAPD"],
                                ["Spectrometer resolution", "7", "40"], ["Bands", "0.2–0.45 µm", "0.9–1.8 µm"]])
        self.assertEqual(got.origins, [[[1], [2, 3], [4, 5], [6, 7]]])
        self.assertEqual(boxes[1], (0, 20, 100, 40))
        self.assertEqual(ts.describe(got), '"no rule above": join above (3: 3, 5, 7)')

    def test_named_lines_header_sections_new_tables_and_lines_apart(self):
        body = [["", "Channel", "Channel"], ["FOV", "1", "2"], ["Note: see text", "", ""], ["Blowers", "Flow", "Power"],
                ["B-1", "900", "40"], ["Standby", "", ""], ["B-2", "800", "30"]]
        a = answer(rules=[{"action": "join header", "lines": ["1"]}, {"action": "not table", "lines": ["3"]},
                          {"action": "new table", "lines": ["4"]}, {"action": "section", "lines": ["6"]}])
        got = ts.apply(a, HEADER, body, BOXES, [[]] * 7)
        self.assertEqual([p[0] for p in got.parts], [["Camera", "UV Channel", "IR Channel"], ["Blowers", "Flow", "Power"]])
        self.assertEqual(got.parts[1][1], [["B-1", "900", "40"], ["Standby", "", ""], ["B-2", "800", "30"]])
        self.assertEqual((got.apart, got.heads), ([2], [[1], [4]]))
        self.assertEqual(got.holding(1, body), ["Camera", "UV Channel", "IR Channel"])

    def test_a_column_of_two_values_split(self):
        body = [["E1", "2.58 0.69"], ["E2", "1.9 / 0.4"], ["E3", "n/a"]]
        a = answer(rules=[{"action": "split column", "column": "B", "into": ["g vertical", "g lateral"]}])
        got = ts.apply(a, ["Element", "g (vertical / lateral)"], body, BOXES[:3], [[]] * 3)
        (head, rows, _), = got.parts
        self.assertEqual(head, ["Element", "g vertical", "g lateral"])
        self.assertEqual(rows, [["E1", "2.58", "0.69"], ["E2", "1.9", "0.4"], ["E3", "n/a", ""]])
        self.assertEqual(got.misfits, ["E3: column B not split ('n/a')"])

    def test_problems_before_applying(self):
        a = answer(rules=[{"action": "merge", "lines": ["2"]}, {"action": "join above", "when": ["odd"], "lines": ["99"]},
                          {"action": "keep"}, {"action": "split column", "column": "Q", "into": ["x"]}],
                   examples=[{"line": "1", "cells": ["FOV"]}])
        wrong = ts.problems(a, len(BODY), 3, self.tags)
        self.assertEqual(len(wrong), 5)
        self.assertIn("rule 1: unknown action 'merge'", wrong)

    def test_examples_checked_against_what_the_rules_give(self):
        a = answer(rules=[{"action": "join above", "when": ["first cell empty"]}],
                   examples=[{"line": "line 3", "cells": ["Detector", "1×1 CCD201", "1×1 LMAPD"]},
                             {"line": "5", "cells": ["Spectrometer resolution", "7", "40"]}])
        got = ts.apply(a, HEADER, BODY, BOXES, self.tags)
        self.assertEqual(ts.example_mismatches(a, got, BODY),
                         ["line 5: your rules give resolution; your example Spectrometer resolution | 7 | 40"])
        # the worst suspect's row among the examples: by its first line, or by any line it holds; H is the header
        a = answer(rules=[{"action": "join above", "when": ["first cell empty"]}],
                   examples=[{"line": "2", "cells": ["Detector", "1×1 CCD201", "1×1 LMAPD"]},
                             {"line": "H", "cells": ["Camera", "UV", "IR"]}])
        got = ts.apply(a, HEADER, BODY, BOXES, self.tags)
        self.assertEqual(ts.example_mismatches(a, got, BODY, worst=3), [])
        self.assertEqual(ts.example_mismatches(a, got, BODY, worst=7),
                         ["the row holding line 7 isn't among the examples: copy it from the image"])

    def test_numbers_given_for_lines_and_cells_are_read_as_text(self):
        a = answer(rules=[{"action": "join above", "lines": [3, 5]}], examples=[{"line": 2, "cells": ["Detector", 7]}])
        self.assertEqual((a.rules[0].lines, a.examples[0].line, a.examples[0].cells), (["3", "5"], "2", ["Detector", "7"]))

class Mended(unittest.TestCase):
    """What the development slices showed (2026-10-07): the header named among lines, rules leaving no rows, and
    cells parted otherwise in the image than by the parser."""
    def test_the_header_named_among_lines_is_ignored(self):
        a = answer(rules=[{"action": "keep", "lines": ["H", "1"]}])
        self.assertEqual(ts.problems(a, 2, 3, [[], []]), [])

    def test_examples_compared_by_their_rows_text_and_other_cells_noted(self):
        body = [["TEAM NAME: TEAM K", ""], ["LOT: 113", ""]]
        a = answer(rules=[{"action": "keep", "lines": ["1"]}],
                   examples=[{"line": "1", "cells": ["TEAM NAME:", "TEAM K"]}])
        got = ts.apply(a, ["", ""], body, BOXES[:2], [[], []])
        self.assertEqual(ts.example_mismatches(a, got, body, worst=1), [])
        self.assertEqual(ts.cells_parted_otherwise(a, got, body),
                         ["line 1's cells parted otherwise in the image: TEAM NAME: | TEAM K"])

class CutWords(unittest.TestCase):
    """Columns the parser draws through words ("7. | 4"): the signal, and the join that mends them."""
    HEADER = ["Column", "Footing", "", "Load (k", "ips)"]
    BODY = [["C-18", "10.3", "", "255", ""], ["C-19", "7.", "4", "249", ""], ["C-20", "6.8", "", "224", ""]]
    CUTS = {0: {3}, 2: {1}}  # the header's "(kips)" cut between D and E; line 2's "7.4" between B and C

    def test_a_cut_word_is_a_signal_shown_with_where_it_is_cut(self):
        tags = ts.signals(self.HEADER, self.BODY, BOXES[:3], cuts=self.CUTS)
        self.assertEqual(tags, [[], [ts.CUT], []])
        shown = ts.show_lines(self.HEADER, self.BODY, tags, self.CUTS)
        self.assertIn("H:  Column | Footing |  | Load (k | ips)   [a word cut by a column line] (cut at D|E)", shown)
        self.assertIn("2:  C-19 | 7. | 4 | 249 |    [a word cut by a column line] (cut at B|C)", shown)

    def test_columns_joined_without_a_space_where_a_word_was_cut(self):
        a = answer(rules=[{"action": "join columns", "column": "B"}, {"action": "join columns", "column": "D:E"}])
        (head, rows, _), = ts.apply(a, self.HEADER, self.BODY, BOXES[:3], [[]] * 3, self.CUTS).parts
        self.assertEqual(head, ["Column", "Footing", "Load (kips)"])
        self.assertEqual(rows, [["C-18", "10.3", "255"], ["C-19", "7.4", "249"], ["C-20", "6.8", "224"]])
        # where no word was cut, cells are joined with a space; a split names columns as they were shown
        b = answer(rules=[{"action": "join columns", "column": "A"}, {"action": "split column", "column": "D",
                                                                      "into": ["x", "y"]}])
        got = ts.apply(b, ["A", "B", "C", "D"], [["Raw", "water", "1", "2 3"]], BOXES[:1], [[]])
        self.assertEqual(got.parts[0][1], [["Raw water", "1", "2", "3"]])
        # with cuts known, a body row's separate values joined where no word was cut is unsupported
        wrong = answer(rules=[{"action": "join columns", "column": "D"}])
        got = ts.apply(wrong, self.HEADER, self.BODY, BOXES[:3], [[]] * 3, self.CUTS)
        self.assertEqual(got.unsupported, [])  # D:E: "255" and "" (only one value in each row), the header free
        wrong = answer(rules=[{"action": "join columns", "column": "C:D"}])
        got = ts.apply(wrong, self.HEADER, self.BODY, BOXES[:3], [[]] * 3, self.CUTS)
        self.assertEqual(got.unsupported[0], "columns C:D hold separate values in the row of line 2 ('4', '249'; no "
                                             "word cut between them): join only columns a word is cut across")
        self.assertEqual(ts.problems(answer(rules=[{"action": "join columns", "column": "E"}]), 3, 5, [[]] * 3),
                         ['rule 1: a join names a column with one after it ("C"), or a range ("C:E"), within A to E'])

    def test_a_cut_header_is_asked_with_the_header_as_the_worst_suspect(self):
        asked = []

        def submit(prompt, model, images, key, finish):
            asked.append(prompt)
            finish(model.model_validate({"rules": [{"action": "join columns", "column": "D"}],
                                         "examples": [{"line": "H", "cells": ["Column", "Footing", "Load (kips)"]}]})
                   if model is ts.Structure else model.model_validate({"verdict": "keep"}), None)

        core = SimpleNamespace(content="c", output=__import__("pathlib").Path("/tmp"), state={"pending": 0},
                               progress=SimpleNamespace(add=lambda: None, finish=lambda status: None),
                               dispatch=SimpleNamespace(submit=submit), s=SimpleNamespace(reviews_tables=lambda: 0),
                               record=lambda row, claims: None)
        out = {}
        ts.read(core, 1, "structure:p1:0", self.HEADER, [self.BODY[0]], BOXES[:1], None, None, lambda: [],
                lambda parts, step, apart, table: out.update(parts=parts), {0: {3}, 1: set()})
        self.assertIn("row holding line H:", asked[0])
        self.assertEqual(out["parts"][0][0], ["Column", "Footing", "", "Load (kips)"])

class Asked(unittest.TestCase):
    """The query, asked again on problems, reviewed, and the heuristics kept when it fails."""
    def run_with(self, answers, review=2):
        asked, recorded, out = [], [], {}

        def submit(prompt, model, images, key, finish):
            asked.append((key[0], key[3], prompt))
            finish(model.model_validate(answers.pop(0)), None)

        core = SimpleNamespace(content="c", output=__import__("pathlib").Path("/tmp"), state={"pending": 0},
                               progress=SimpleNamespace(add=lambda: None, finish=lambda status: None),
                               dispatch=SimpleNamespace(submit=submit), s=SimpleNamespace(reviews_tables=lambda: review),
                               record=lambda row, claims: recorded.append(row))
        ts.read(core, 4, "structure:p4:0", HEADER, BODY, BOXES, None, [10, 20, 40, 60, 80], lambda: ["assets/t.png"],
                lambda parts, step, apart, table: out.update(parts=parts, step=step, apart=apart, table=table))
        return asked, recorded, out

    def test_rules_reviewed_and_used(self):
        good = {"rules": [{"action": "join above", "when": ["no rule above"]}],
                "examples": [{"line": "7", "cells": ["Bands", "0.2–0.45 µm", "0.9–1.8 µm"]}]}
        asked, recorded, out = self.run_with([good, {"verdict": "keep"}])
        self.assertEqual([a[:2] for a in asked], [("table-structure", "structure:p4:0"),
                                                  ("table-structure-review", "structure:p4:0:review")])
        self.assertIn("7:   | µm | µm   [no rule above; first cell empty; units only]", asked[0][2])
        self.assertIn("one of the", asked[0][2])
        self.assertIn("row holding line 7:", asked[0][2])  # the worst suspect: the most signals
        self.assertIn("lines 2+3: Detector | 1×1 CCD201 | 1×1 LMAPD", asked[1][2])
        self.assertEqual(len(out["parts"][0][1]), 4)
        self.assertEqual(out["step"].step, "table-structure")
        self.assertIn("Reviewed: kept", recorded[-1]["issues"])

    def test_a_mismatched_example_asked_again_then_the_heuristics_kept(self):
        bad = {"rules": [{"action": "keep", "lines": ["3"]}], "examples": [{"line": "7", "cells": ["Bands", "x"]}]}
        asked, recorded, out = self.run_with([bad, bad])
        self.assertEqual([a[1] for a in asked], ["structure:p4:0", "structure:p4:0:again"])
        self.assertIn("ITS PROBLEMS:\n- line 7: your rules give µm | µm; your example Bands | x", asked[1][2])
        self.assertEqual(out, {"parts": [(HEADER, BODY, BOXES)], "step": None, "apart": [], "table": True})
        self.assertTrue(recorded[-1]["issues"][0].startswith("Structure as the heuristics left it: the rules failed twice"))

    def test_rules_leaving_no_rows_keep_the_heuristics_without_asking_again(self):
        none = {"rules": [{"action": "not table", "lines": [str(k) for k in range(1, 8)]}], "why": "a title block"}
        asked, recorded, out = self.run_with([none])
        self.assertEqual(len(asked), 1)
        self.assertEqual((out["parts"], out["table"]), ([(HEADER, BODY, BOXES)], False))  # read as no table
        self.assertEqual(recorded[-1]["issues"], ["Structure as the heuristics left it: the rules leave no rows (a title block)"])

    def test_a_table_without_suspects_isnt_asked(self):
        out = {}
        ts.read(None, 1, "t", HEADER, BODY[:2], BOXES[:2], None, None, lambda: [],
                lambda parts, step, apart, table: out.update(parts=parts, step=step))
        self.assertEqual(out, {"parts": [(HEADER, BODY[:2], BOXES[:2])], "step": None})

class Extracted(unittest.TestCase):
    """The structure query in a PDF's extraction."""
    def test_a_late_answer_reads_its_own_pages_table(self):
        # The structure answer for page 1's table comes after the page loop has moved on to page 2's; its rows must
        # still be read as page 1's (once, a callback looked its continuation up by name, and read page 2's table).
        import re
        import tempfile
        import threading
        from pathlib import Path
        from unittest.mock import patch
        import pymupdf
        from semantic_pdf_diff.extract import extract_pdf
        from semantic_pdf_diff.models import Extraction, Settings
        from semantic_pdf_diff.provenance import content_id
        from stubs import situating_answer

        tables = {0: [((20, 20, 280, 120), [["Tag", "Model"], ["P-1", "X1"], ["", "CCD201"], ["P-2", "X2"]])],
                  1: [((20, 20, 280, 120), [["Fan", "Flow"], ["F-1", "10"], ["F-2", "12"]])]}

        class Table:
            def __init__(self, bbox, rows): self.bbox, self.rows_ = bbox, rows
            def extract(self): return self.rows_

        def find_tables(page, *a, **k):
            return type("T", (), {"tables": [Table(b, r) for b, r in tables.get(page.number, [])]})()

        page2_read = threading.Event()

        class Client:  # answers on worker threads (the dispatcher's prepare/send split), so they can come late
            s = Settings(vision=False, concurrency=4)
            calls, cache_hits, usage = 0, 0, {}
            asked = []

            def prepare(self, prompt, schema, images, key):
                return SimpleNamespace(prompt=prompt, schema=schema, key=key, query=None)

            def cached(self, request):
                return None

            def save(self, request, value):
                pass

            def send(self, request):
                return self.ask(request.prompt, request.schema, key=request.key)

            def ask(self, prompt, schema, images=(), key=None):
                self.asked.append((key[3], prompt))
                if schema is ts.StructureReview:
                    return ts.StructureReview(verdict="keep")
                if schema is ts.Structure:
                    self.late = page2_read.wait(5)  # answered only once page 2's table has been read
                    worst = re.search(r"row holding line\s+(\d+)", prompt).group(1)
                    line = re.search(rf"^{worst}:  (.*?)(   \[.*\])?$", prompt, re.M).group(1)
                    return ts.Structure.model_validate({"rules": [{"action": "join above", "lines": [worst]}],
                                                        "examples": [{"line": str(int(worst) - 1),
                                                                      "cells": ["P-1", "X1", line.strip(" |")]}]})
                if situating_answer(prompt):
                    return schema.model_validate(situating_answer(prompt))
                if schema.__name__ == "Rules":
                    return schema(reading="rows")
                if key[3].startswith("table:p2"):
                    page2_read.set()
                return Extraction(claims=[], complete=True)

        with tempfile.TemporaryDirectory() as d, patch.object(pymupdf.Page, "find_tables", find_tables):
            doc = pymupdf.open()
            for _ in range(2):
                doc.new_page(width=300, height=300)
            path = Path(d) / "t.pdf"
            doc.save(path)
            client = Client()
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
        rows = {task: prompt.split("SOURCE DATA:\n")[1] for task, prompt in client.asked if task.startswith("table:")}
        page1 = {task: text for task, text in rows.items() if task.startswith("table:p1:")}
        self.assertTrue(client.late)  # the answer did come after page 2's table was read
        self.assertEqual(len(page1), 2)  # P-1 (with CCD201 joined) and P-2
        self.assertTrue(all('"Tag"' in text for text in page1.values()))
        self.assertTrue(any("X1 CCD201" in text for text in page1.values()))
        self.assertFalse(any('"Tag"' in text for task, text in rows.items() if task.startswith("table:p2:")))

    def test_a_part_read_as_no_table_goes_to_a_figure_task(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import pymupdf
        from semantic_pdf_diff.extract import extract_pdf
        from semantic_pdf_diff.models import Extraction, Settings
        from semantic_pdf_diff.provenance import content_id
        from stubs import situating_answer

        rows = [["Room", "Size"], ["", "25'-0\""], ["MEETING 102", "732 SF"]]  # a floor plan's labels, parsed

        class Table:
            bbox = (20, 20, 280, 120)
            def extract(self): return rows

        find_tables = lambda page, *a, **k: type("T", (), {"tables": [Table()]})()

        class Client:
            s = Settings(vision=True)
            calls, cache_hits, usage = 0, 0, {}
            asked = []

            def ask(self, prompt, schema, images=(), key=None):
                self.asked.append(key[3])
                if schema is ts.Structure:
                    return ts.Structure.model_validate({"rules": [{"action": "not table", "lines": ["1", "2"]}],
                                                        "why": "a floor plan"})
                if situating_answer(prompt):
                    return schema.model_validate(situating_answer(prompt))
                return Extraction(claims=[], complete=True)

        with tempfile.TemporaryDirectory() as d, patch.object(pymupdf.Page, "find_tables", find_tables):
            doc = pymupdf.open()
            doc.new_page(width=300, height=300)
            path = Path(d) / "t.pdf"
            doc.save(path)
            client = Client()
            _, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
        self.assertIn("figure:p1:t0", client.asked)
        self.assertFalse([task for task in client.asked if task.startswith(("table:", "rules:"))])
        note = next(row for row in coverage if row["task"] == "structure:p1:0:figure")
        self.assertEqual(note["issues"], ["Not read as a table (the model reads none there): read by a figure task"])

class NewTables(unittest.TestCase):
    def test_a_new_tables_rows_are_tagged_apart_from_pdf_parts(self):
        # code review 2026-10-08, A2: a structure answer's new table was tagged "0.1", pdf_parts' part 1's tag
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import pymupdf
        from semantic_pdf_diff.extract import extract_pdf
        from semantic_pdf_diff.models import Extraction, Settings
        from semantic_pdf_diff.provenance import content_id
        from stubs import situating_answer

        # pdf_parts parts it at "Blowers" (a line of labels: part 1, "0.1"); the model starts a new table at "Fan set 2"
        rows = [["Tag", "Model"], ["", "X0"], ["P-1", "X1"], ["Fan set 2", "Flow"], ["F-1", "10"], ["Blowers", "Power"],
                ["B-1", "5"]]

        class Table:
            bbox = (20, 20, 280, 120)
            def extract(self): return rows

        find_tables = lambda page, *a, **k: type("T", (), {"tables": [Table()]})()

        class Client:
            s = Settings(vision=False)
            calls, cache_hits, usage = 0, 0, {}
            asked = []

            def ask(self, prompt, schema, images=(), key=None):
                self.asked.append(key[3])
                if schema is ts.Structure:
                    return ts.Structure.model_validate({"rules": [{"action": "new table", "lines": ["3"]}],
                                                        "examples": [{"line": "1", "cells": ["", "X0"]}]})
                if schema is ts.StructureReview:
                    return ts.StructureReview(verdict="keep")
                if situating_answer(prompt):
                    return schema.model_validate(situating_answer(prompt))
                if schema.__name__ == "Rules":
                    return schema(reading="rows")
                return Extraction(claims=[], complete=True)

        with tempfile.TemporaryDirectory() as d, patch.object(pymupdf.Page, "find_tables", find_tables):
            doc = pymupdf.open()
            doc.new_page(width=300, height=300)
            path = Path(d) / "t.pdf"
            doc.save(path)
            client = Client()
            extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
        self.assertIn("structure:p1:0", client.asked)
        tables = sorted(t for t in client.asked if t.startswith("table:"))
        self.assertIn("table:p1:0+1:0", tables)  # F-1, under the new table's header
        self.assertIn("table:p1:0.1:0", tables)  # B-1, in pdf_parts' part 1
        self.assertEqual(len(tables), len(set(tables)))

class Detection(unittest.TestCase):
    """Table detection's failures in a PDF's extraction (code review 2026-10-08, A3 and A4)."""
    def extract(self, tables, ask=None, patches=()):
        import contextlib
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import pymupdf
        from semantic_pdf_diff.extract import extract_pdf
        from semantic_pdf_diff.models import Extraction, Settings
        from semantic_pdf_diff.provenance import content_id
        from stubs import situating_answer

        class Table:
            def __init__(self, bbox, rows): self.bbox, self.rows_, self.cells = bbox, rows, []
            def extract(self): return self.rows_

        def find_tables(page, *a, **k):
            if tables is None:
                raise RuntimeError("PyMuPDF's own")
            return type("T", (), {"tables": [Table(b, r) for b, r in tables]})()

        class Client:
            s = Settings(vision=False, table_structure=False, table_rules=None, refinement_depth=1)
            calls, cache_hits, usage = 0, 0, {}
            asked = []

            def ask(self, prompt, schema, images=(), key=None):
                self.asked.append(key[3])
                if situating_answer(prompt):
                    return schema.model_validate(situating_answer(prompt))
                said = ask(key[3]) if ask else None
                return said or Extraction(claims=[], complete=True)

        with contextlib.ExitStack() as stack, tempfile.TemporaryDirectory() as d:
            stack.enter_context(patch.object(pymupdf.Page, "find_tables", find_tables))
            for target, value in patches:
                stack.enter_context(patch(target, value))
            doc = pymupdf.open()
            doc.new_page(width=300, height=300)
            path = Path(d) / "t.pdf"
            doc.save(path)
            client = Client()
            _, coverage = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
        return client.asked, coverage

    def test_an_unreached_row_isnt_split_by_column(self):
        from semantic_pdf_diff.llm import CallLimitReached
        rows = [["Tag", "Flow", "Head", "Power"], ["P-1", "120", "25", "40"]]

        def ask(task):
            if task.startswith("table:"):
                raise CallLimitReached("the call limit")
        asked, coverage = self.extract([((20, 20, 280, 120), rows)], ask)
        self.assertEqual([t for t in asked if t.startswith("table:")], ["table:p1:0:0"])
        self.assertEqual(next(r for r in coverage if r["task"] == "table:p1:0:0")["status"], "not_reached")

    def test_a_partial_row_is_still_split_by_column(self):
        from semantic_pdf_diff.models import Extraction
        rows = [["Tag", "Flow", "Head", "Power"], ["P-1", "120", "25", "40"]]
        partial = lambda task: Extraction(claims=[], complete=False) if task == "table:p1:0:0" else None
        asked, _ = self.extract([((20, 20, 280, 120), rows)], partial)
        self.assertEqual([t for t in asked if t.startswith("table:")], ["table:p1:0:0", "table:p1:0:0:c0", "table:p1:0:0:c1"])

    def test_a_mending_bug_is_named_ours_and_the_table_read_as_detected(self):
        rows = [["Tag", "Flow"], ["P-1", "120"]]
        def broken(*a, **k):
            raise TypeError("ours")
        asked, coverage = self.extract([((20, 20, 280, 120), rows), ((20, 150, 280, 250), rows)],
                                       patches=[("semantic_pdf_diff.extract.cut_columns", broken),
                                                ("semantic_pdf_diff.extract.row_boxes",
                                                 lambda table, rows: [(20, 20 + 20 * i, 280, 40 + 20 * i)
                                                                      for i in range(len(rows))])])
        self.assertEqual(sorted(t for t in asked if t.startswith("table:")), ["table:p1:0:0", "table:p1:1:0"])
        mending = [r for r in coverage if r["task"].endswith(":mending")]
        self.assertEqual(len(mending), 2)
        self.assertIn("a bug: TypeError: ours", mending[0]["issues"][0])
        self.assertFalse([r for r in coverage if r["task"] == "table-detection:p1"])

    def test_pymupdfs_own_failure_is_a_detection_failure(self):
        asked, coverage = self.extract(None)
        row = next(r for r in coverage if r["task"] == "table-detection:p1")
        self.assertEqual((row["status"], row["issues"]), ("failed", ["RuntimeError: PyMuPDF's own"]))

if __name__ == "__main__":
    unittest.main()
