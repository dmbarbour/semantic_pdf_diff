"""The text_spans lever: a page's text blocks grouped up to the byte budget across section boundaries ("page"), or each
task one section's ("section")."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import cli
from semantic_pdf_diff.settings import Settings

DOCUMENT = """# Link Specification

## 4 Link Failure Detection

A link failure is declared when any of the following conditions holds.

Condition 1: no acknowledgement is received within 856 ms.

## 5 Timers by Link State

The retransmission timer is 709 ms.
"""

class TextSpans(unittest.TestCase):
    def test_on_a_page_no_block_is_parted_by_its_section(self):
        section_of = lambda box: box[1] // 100  # noqa: E731
        self.assertIs(Settings(text_spans="section").text_section_of(section_of), section_of)
        together = Settings(text_spans="page").text_section_of(section_of)
        self.assertEqual({together((0, y, 1, y + 1)) for y in (0, 150, 300)}, {None})

    def test_a_markdown_documents_sections_share_a_task(self):
        from test_concurrency import jittery_model
        sources = {}
        for spans in ("section", "page"):
            with tempfile.TemporaryDirectory() as d, jittery_model() as (url, state):
                doc, config = Path(d) / "spec.md", Path(d) / "settings.json"
                doc.write_text(DOCUMENT)
                config.write_text(json.dumps({"text_spans": spans}))
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cli.main([str(doc), str(doc), "--out", str(Path(d) / "out"), "--base-url", url, "--no-situate",
                              "--config", str(config)])
            sources[spans] = [p.split("SOURCE DATA:\n")[-1] for role, p, *_ in state["transcript"]
                              if role == "extract" and "SOURCE DATA:" in p]
        apart = [s for s in sources["section"] if "856 ms" in s or "709 ms" in s]
        self.assertEqual(len(apart), 2)
        self.assertFalse(any("856 ms" in s and "709 ms" in s for s in apart))
        together = [s for s in sources["page"] if "856 ms" in s and "709 ms" in s]
        self.assertEqual(len(together), 1)
        self.assertIn("5 Timers by Link State", together[0])

if __name__ == "__main__":
    unittest.main()
