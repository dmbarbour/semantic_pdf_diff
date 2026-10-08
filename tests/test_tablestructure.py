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
                lambda parts, step, apart: out.update(parts=parts, step=step, apart=apart))
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
        self.assertEqual(out, {"parts": [(HEADER, BODY, BOXES)], "step": None, "apart": []})
        self.assertTrue(recorded[-1]["issues"][0].startswith("Structure as the heuristics left it: the rules failed twice"))

    def test_rules_leaving_no_rows_keep_the_heuristics_without_asking_again(self):
        none = {"rules": [{"action": "not table", "lines": [str(k) for k in range(1, 8)]}], "why": "a title block"}
        asked, recorded, out = self.run_with([none])
        self.assertEqual(len(asked), 1)
        self.assertEqual(out["parts"], [(HEADER, BODY, BOXES)])
        self.assertEqual(recorded[-1]["issues"], ["Structure as the heuristics left it: the rules leave no rows (a title block)"])

    def test_a_table_without_suspects_isnt_asked(self):
        out = {}
        ts.read(None, 1, "t", HEADER, BODY[:2], BOXES[:2], None, None, lambda: [],
                lambda parts, step, apart: out.update(parts=parts, step=step))
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

if __name__ == "__main__":
    unittest.main()
