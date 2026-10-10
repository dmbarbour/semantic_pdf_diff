"""A PDF table continued over a page break (extract._pdf_job): a table at the top of a page, as wide as one that
ended at the bottom of the page before, is read under that one's header, unless its first row is a header of the
same form. No test covered it (code review 2026-10-08, A19)."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import stubs  # noqa: F401 (a clean environment)

HEADER = ["Tag", "Service", "Flow (L/s)"]
FIRST = [HEADER, ["P-1", "Chilled water", "120"], ["P-2", "Condenser", "95"]]
NEXT = [["P-3", "Make-up", "4"], ["P-4", "Fire", "40"]]
BOTTOM, TOP = (20, 200, 280, 290), (20, 20, 280, 70)  # on 300-point pages: ending past 80%, starting within 20%

def read(second, first=FIRST, at=(BOTTOM, TOP)):
    """{task: its request's data} and the evidence, for a two-page PDF whose pages hold the tables given."""
    import pymupdf
    from semantic_pdf_diff.extract import ExtractQuery, extract_pdf
    from semantic_pdf_diff.schema import Extraction
    from semantic_pdf_diff.settings import Settings
    from semantic_pdf_diff.provenance import content_id
    from stubs import situating_answer
    pages = {0: (at[0], first), 1: (at[1], second)}

    class Client:
        s = Settings(vision=False, table_structure=False, table_rules=None, refinement_depth=0)
        calls, cache_hits, usage = 0, 0, {}

        def __init__(self):
            self.rows = {}

        def ask(self, prompt, schema, images=(), key=None):
            if situating_answer(prompt):
                return schema.model_validate(situating_answer(prompt))
            if prompt.startswith("This is a block of two columns"):  # the key-value check (B5): a table
                return schema.model_validate({"reading": "table", "why": "stub"})
            data = ExtractQuery.read(prompt).data
            if not key[3].startswith("table:"):  # the pages' text
                return Extraction(claims=[], complete=True)
            self.rows[key[3]] = data
            row = json.loads(data.split("Row: ", 1)[1].split("\n", 1)[0])
            return Extraction(claims=[{"entity": row[0], "attribute": "flow", "value": row[-1], "unit": "L/s",
                                       "kind": "table", "quote": row[-1], "confidence": 0.9}], complete=True)

    def find(page, *args, **kwargs):
        bbox, rows = pages[page.number]
        table = type("Table", (), {"bbox": bbox, "cells": [], "extract": lambda self: [list(r) for r in rows]})
        return type("Found", (), {"tables": [table()]})()

    def boxes(table, rows):
        return [(table.bbox[0], table.bbox[1] + 12 * k, table.bbox[2], table.bbox[1] + 12 * (k + 1))
                for k in range(len(rows))]

    with contextlib.ExitStack() as stack, tempfile.TemporaryDirectory() as d:
        stack.enter_context(patch.object(pymupdf.Page, "find_tables", find))
        stack.enter_context(patch("semantic_pdf_diff.extract.Marks", lambda page: None))
        stack.enter_context(patch("semantic_pdf_diff.extract.row_boxes", boxes))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        doc = pymupdf.open()
        for number in range(2):  # each row's text where its box is, so quotes are found in the page's text
            page = doc.new_page(width=300, height=300)
            bbox, rows = pages[number]
            for k, row in enumerate(rows):
                page.insert_text((bbox[0] + 2, bbox[1] + 12 * k + 10), "  ".join(row), fontsize=8)
        path = Path(d) / "t.pdf"
        doc.save(path)
        client = Client()
        evidence, _ = extract_pdf(path, content_id(path.read_bytes(), path.name), Path(d), client)
    return client.rows, evidence

def page_two(rows):
    return {task: data for task, data in rows.items() if task.startswith("table:p2:")}

class Continuation(unittest.TestCase):
    def test_a_table_at_the_top_of_the_next_page_is_read_under_the_header_before(self):
        rows, evidence = read(NEXT)
        second = page_two(rows)
        self.assertEqual(len(second), 2)  # both its rows: neither taken for a header
        self.assertTrue(all(data.startswith(f"Header: {as_json(HEADER)}") for data in second.values()))
        p3 = next(e for e in evidence if e.entity == "P-3")
        self.assertIn("continued from page 1", " ".join(step.detail for step in p3.derivation))

    def test_a_repeated_header_is_skipped(self):
        rows, evidence = read([HEADER] + NEXT)
        second = page_two(rows)
        self.assertEqual(len(second), 2)
        p3 = next(e for e in evidence if e.entity == "P-3")  # continued, not a new table under the same header
        self.assertIn("continued from page 1", " ".join(step.detail for step in p3.derivation))
        self.assertTrue(all(f"Header: {as_json(HEADER)}" in data and "Row: [\"Tag\"" not in data
                            for data in second.values()))

    def test_a_header_of_the_same_form_starts_a_new_table(self):
        other = ["Tag", "Service", "Flow (m3/h)"]  # the next schedule: its own units
        second = page_two(read([other] + NEXT)[0])
        self.assertTrue(all(data.startswith(f"Header: {as_json(other)}") for data in second.values()))

    def test_no_continuation_down_the_page_across_widths_or_from_mid_page(self):
        for name, args in (("not at the top", dict(at=(BOTTOM, (20, 100, 280, 150)))),
                           ("ended mid-page", dict(at=((20, 40, 280, 130), TOP))),
                           ("another width", dict(second=[r[:2] for r in NEXT]))):
            with self.subTest(name):
                second = page_two(read(**{"second": NEXT, **args})[0])
                self.assertTrue(second)
                self.assertTrue(all(not data.startswith(f"Header: {as_json(HEADER)}") for data in second.values()))
                self.assertEqual(len(second), 1)  # its first row its header

def as_json(row):
    return json.dumps(row)

if __name__ == "__main__":
    unittest.main()
