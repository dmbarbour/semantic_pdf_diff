"""The table_cuts lever: an image region cutting a detected table is sent the table's first row and the rows it
touches, whole, as the PDF's text has them."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff import cli
from semantic_pdf_diff.levers import TABLE_CUT_NOTE
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.tables import cut_by

HEADER = ["DOOR", "ROOM", "WIDTH", "HEIGHT"]
ROWS = [[f"D10{i}", f"MEETING 10{i}", "3'-0\"", "7'-0\""] for i in range(1, 7)]

def schedule(top=100.0, height=20.0, left=60.0, right=400.0):
    """A door schedule's (box, rows, row boxes), one row per `height` points from `top`."""
    rows = [HEADER, *ROWS]
    boxes = [(left, top + i * height, right, top + (i + 1) * height) for i in range(len(rows))]
    return (left, top, right, top + len(rows) * height), rows, boxes

class CutBy(unittest.TestCase):
    def test_a_region_cutting_a_table_gets_its_first_row_and_the_rows_it_touches(self):
        note = cut_by((50, 185, 300, 600), [schedule()], 1500)  # rows 4 to 6 (y 180 to 240), the right columns cut
        self.assertEqual(note.splitlines(), ["DOOR | ROOM | WIDTH | HEIGHT",
                                             "D104 | MEETING 104 | 3'-0\" | 7'-0\"",
                                             "D105 | MEETING 105 | 3'-0\" | 7'-0\"",
                                             "D106 | MEETING 106 | 3'-0\" | 7'-0\""])

    def test_a_region_holding_the_table_whole_or_missing_it_gets_nothing(self):
        self.assertEqual(cut_by((0, 0, 500, 500), [schedule()], 1500), "")
        self.assertEqual(cut_by((0, 400, 500, 800), [schedule()], 1500), "")

    def test_whole_rows_as_many_as_fit(self):
        note = cut_by((50, 165, 300, 600), [schedule()], 80)  # rows 3 to 6, room for one
        self.assertEqual(note.splitlines(), ["DOOR | ROOM | WIDTH | HEIGHT", "D103 | MEETING 103 | 3'-0\" | 7'-0\""])

class Hook(unittest.TestCase):
    def test_on_the_note_follows_the_regions_text_and_off_nothing_changes(self):
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        reader = type("Reader", (), {"table_rows_on": {1: [schedule()]}})()
        off, on = Settings(table_cuts=False, visual_text_layer=0), Settings(table_cuts=True, visual_text_layer=0)
        rect = pymupdf.Rect(50, 185, 300, 600)
        self.assertEqual(off.region_text(reader, page, rect, "", "Figure 2"), "Figure 2")
        said = on.region_text(reader, page, rect, "", "Figure 2")
        self.assertTrue(said.startswith("Figure 2\n" + TABLE_CUT_NOTE + "\nDOOR | ROOM | WIDTH | HEIGHT\nD104"), said)
        self.assertEqual(on.region_text(reader, page, pymupdf.Rect(0, 0, 500, 500), "", ""), "")

class Requests(unittest.TestCase):
    def test_a_tile_cutting_a_ruled_table_is_sent_its_header(self):
        """A ruled schedule across a tile's edge: with the lever, an image request holding the note names the schedule's
        header and a door its rows hold; without, none has the note."""
        from test_concurrency import jittery_model
        doc = pymupdf.open()
        page = doc.new_page(width=1200, height=842)
        xs, top, step = [60, 160, 360, 480, 600], 330, 24
        ys = [top + step * i for i in range(len(ROWS) + 2)]
        for x in xs:
            page.draw_line(pymupdf.Point(x, ys[0]), pymupdf.Point(x, ys[-1]))
        for y in ys:
            page.draw_line(pymupdf.Point(xs[0], y), pymupdf.Point(xs[-1], y))
        for row, y in zip([HEADER, *ROWS], ys):
            for cell, x in zip(row, xs):
                page.insert_text((x + 4, y + 16), cell, fontsize=9)
        page.draw_circle(pymupdf.Point(900, 300), 120)  # a drawing beside it: the page is tiled
        notes = {}
        for on in (False, True):
            with tempfile.TemporaryDirectory() as d, jittery_model() as (url, state):
                pdf, config = Path(d) / "a.pdf", Path(d) / "settings.json"
                doc.save(pdf)
                config.write_text(json.dumps({"table_cuts": on, "tiling": "grid", "tile_points": 300}))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cli.main([str(pdf), str(pdf), "--out", str(Path(d) / "out"), "--base-url", url, "--no-situate",
                              "--config", str(config)])
            notes[on] = [p.split(TABLE_CUT_NOTE + "\n", 1)[1] for role, p, *_ in state["transcript"]
                         if role == "extract" and TABLE_CUT_NOTE in p]
        self.assertEqual(notes[False], [])
        self.assertTrue(notes[True])
        for note in notes[True]:
            self.assertTrue(note.startswith("DOOR | ROOM | WIDTH | HEIGHT\nD10"), note)

if __name__ == "__main__":
    unittest.main()
