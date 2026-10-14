"""The repeated_text lever: a PDF page's text tasks leave out a block saying exactly what blocks in the same place said
on two earlier pages (a watermark, a title block's stamp), read where it was first."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from semantic_pdf_diff import cli
from test_concurrency import jittery_model

STAMP = "PRODUCED BY AN AUTODESK STUDENT PRODUCT 5 kW"

def stamped(path, pages=4):
    """Pages each with its own paragraph and the same stamp in the same place, far from it."""
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 100), f"Pump P-{n} is rated {10 * n} kW at 1450 rpm.", fontsize=10)
        page.insert_text((60, 800), STAMP, fontsize=8)
    doc.set_metadata({})
    doc.save(path, no_new_id=True)
    return path

def stamped_doc():
    with tempfile.TemporaryDirectory() as d:
        return pymupdf.open(stream=stamped(Path(d) / "a.pdf").read_bytes())

def run(setting):
    """The text queries a comparison of the document with itself sent, and its report's text coverage."""
    with tempfile.TemporaryDirectory() as d, jittery_model() as (url, state):
        root = Path(d)
        pdf = stamped(root / "a.pdf")
        (root / "settings.json").write_text(json.dumps({"repeated_text": setting, "vision": False}))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cli.main([str(pdf), str(pdf), "--out", str(root / "out"), "--base-url", url, "--no-situate",
                      "--config", str(root / "settings.json")])
        report = json.loads((root / "out" / "report.json").read_text())
    asked = [prompt for role, prompt, *_ in state["transcript"] if role == "extract"]
    return asked, [r for r in report["coverage"] if r["task"].startswith("text")], report["evidence"]

class RepeatedText(unittest.TestCase):
    def test_a_stamp_is_read_on_its_first_pages_and_left_out_once_its_repetition_is_proven(self):
        kept, _, _ = run("keep")
        first, rows, _ = run("first")
        stamps = lambda asked: sum(STAMP in prompt.split("SOURCE DATA:")[-1] for prompt in asked)
        self.assertEqual((stamps(kept), stamps(first)), (4, 2))
        self.assertEqual(len(kept), len(first))  # the paragraphs it shares a task with, each asked
        self.assertTrue(all(f"P-{n} is rated" in "".join(first) for n in range(1, 5)))
        self.assertTrue(all(r["status"] == "complete" for r in rows))

    def test_text_said_in_another_place_isnt_a_repeat(self):
        from semantic_pdf_diff.context import Context
        from semantic_pdf_diff.settings import Settings
        doc = pymupdf.open()
        for n in range(4):
            doc.new_page(width=595, height=842).insert_text((60, 800 - 40 * n), STAMP, fontsize=8)
        self.assertEqual([Context(doc, Settings()).repeated(n) for n in range(1, 5)], [[], [], [], []])
        self.assertEqual(len(Context(stamped_doc(), Settings()).repeated(3)), 1)

if __name__ == "__main__":
    unittest.main()
