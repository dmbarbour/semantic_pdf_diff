"""The lone_rows lever: a table row the same as its header (a one-row table) sent once, not as its own header too."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff import cli

from semantic_pdf_diff.settings import Settings

class LoneRows(unittest.TestCase):
    def test_a_row_that_is_its_own_header_is_sent_once(self):
        row = ["AC Rating", "6.4 kW"]
        self.assertEqual(Settings(lone_rows=True).row_text(row, list(row)), 'Row: ["AC Rating", "6.4 kW"]')
        self.assertEqual(Settings().row_text(row, list(row)),
                         'Header: ["AC Rating", "6.4 kW"]\nRow: ["AC Rating", "6.4 kW"]')

    def test_a_row_under_another_header_keeps_it(self):
        head, row = ["Item", "Power"], ["Pump P-1", "10 kW"]
        self.assertEqual(Settings(lone_rows=True).row_text(head, row), Settings().row_text(head, row))

    def test_a_one_row_tables_request_holds_its_row_once(self):
        from test_concurrency import jittery_model
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        xs, ys = [60, 250, 450], [100, 125]
        for x in xs:
            page.draw_line(pymupdf.Point(x, ys[0]), pymupdf.Point(x, ys[-1]))
        for y in ys:
            page.draw_line(pymupdf.Point(xs[0], y), pymupdf.Point(xs[-1], y))
        page.insert_text((64, 117), "AC Rating", fontsize=9)
        page.insert_text((254, 117), "6.4 kW", fontsize=9)
        rows = {}
        for on in (False, True):
            with tempfile.TemporaryDirectory() as d, jittery_model() as (url, state):
                pdf, config = Path(d) / "a.pdf", Path(d) / "settings.json"
                doc.save(pdf)
                config.write_text(json.dumps({"lone_rows": on}))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cli.main([str(pdf), str(pdf), "--out", str(Path(d) / "out"), "--base-url", url, "--no-situate",
                              "--config", str(config)])
            rows[on] = [p.split("SOURCE DATA:\n")[-1] for role, p, *_ in state["transcript"]
                        if role == "extract" and '"6.4 kW"]' in p]
        self.assertEqual(rows, {False: ['Header: ["AC Rating", "6.4 kW"]\nRow: ["AC Rating", "6.4 kW"]'],
                                True: ['Row: ["AC Rating", "6.4 kW"]']})

if __name__ == "__main__":
    unittest.main()
