"""Plain text and Markdown files (textdocs.py; the adapters plan, milestone 1): read as pages of lines, with sections
from their headings, paragraphs and pipe tables as text and table tasks, and claims located by lines."""
import stubs  # noqa: F401 (a clean environment)
import re
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import textdocs
from semantic_pdf_diff.extract import ExtractQuery, Job, reader_for, run_jobs
from semantic_pdf_diff.models import Extraction, Settings, TextLocator

MARKDOWN = """# Harrow Creek WTP

Intro text without numbers.

## Design Basis

The plant is sized for a design flow of 25.9 MGD.

![Process flow diagram](flow.png)

### Pumps

| Tag | Capacity (gpm) | TDH (ft) |
|---|---|---|
| P-101A | 5,151 | 96.8 |
| P-101B | 5,590 | 64.9 |

```
  raw water --> rapid mix --> flocculation
```

Chlorine Feed
-------------

Chlorine is fed at 3.3 mg/L.
"""

RFC = ("RFC 9000                    QUIC Transport                  May 2021\n\n"
       "1.  Overview\n\n   QUIC is a transport.\n\n"
       "Iyengar & Thomson           Standards Track                    [Page 1]\n\f"
       "RFC 9000                    QUIC Transport                  May 2021\n\n"
       "2.  Streams\n\n   A stream has a limit of 100 streams.\n\n"
       "2.1.  Stream Types\n\n   Four types are defined.\n\n"
       "Iyengar & Thomson           Standards Track                    [Page 2]\n\f"
       "RFC 9000                    QUIC Transport                  May 2021\n\n"
       "   More text on page three.\n\n"
       "Iyengar & Thomson           Standards Track                    [Page 3]\n")

class Model:
    """Claims every number with its unit in what it's shown, quoted as written; records each query."""
    def __init__(self, **settings):
        self.s = Settings(**settings)
        self.calls, self.cache_hits, self.usage, self.queries = 0, 0, {}, []

    def ask(self, prompt, schema, images=(), key=None):
        query = ExtractQuery.read(prompt)
        self.queries.append(query)
        claims = [{"entity": "plant", "attribute": "value", "value": number, "unit": unit, "kind": "text",
                   "quote": f"{number} {unit}".strip() if query.region == "text" else number, "confidence": 0.9}
                  for number, unit in re.findall(r"(?<![\w-])(\d[\d,]*(?:\.\d+)?)\s?(MGD|mg/L|streams)?", query.data)]
        return Extraction(claims=claims[:5], complete=True)

def extract(name, text, **settings):
    """(evidence, coverage, sections, the model) of one text file read by its reader."""
    model = Model(**settings)
    found = {}
    with tempfile.TemporaryDirectory() as d:
        job = Job("sha256:" + "a" * 64 + Path(name).suffix, lambda: text.encode(),
                  on_sections=lambda s: found.update(sections=s), reader=reader_for(Path(name).suffix))
        run_jobs([[job]], Path(d), model)
    evidence, coverage = job.state["result"]
    return evidence, coverage, found["sections"], model

class Parsing(unittest.TestCase):
    def test_markdown_has_headings_tables_code_and_images(self):
        doc = textdocs.parse(MARKDOWN, markdown=True)
        self.assertEqual([(level, title) for _, _, level, title in doc.headings],
                         [(1, "Harrow Creek WTP"), (2, "Design Basis"), (3, "Pumps"), (2, "Chlorine Feed")])
        table = next(b for b in doc.blocks if b.kind == "table")
        self.assertEqual(table.rows, [["Tag", "Capacity (gpm)", "TDH (ft)"], ["P-101A", "5,151", "96.8"],
                                      ["P-101B", "5,590", "64.9"]])
        code = next(b for b in doc.blocks if b.kind == "code")
        self.assertEqual(code.text, "  raw water --> rapid mix --> flocculation")  # as laid out
        self.assertEqual([(alt, target) for _, _, alt, target in doc.images], [("Process flow diagram", "flow.png")])

    def test_plain_text_has_rfc_headings_pages_and_no_running_furniture(self):
        doc = textdocs.parse(RFC, markdown=False)
        self.assertEqual(doc.pages, 3)
        self.assertEqual([(page, level, title) for page, _, level, title in doc.headings],
                         [(1, 1, "1. Overview"), (2, 1, "2. Streams"), (2, 2, "2.1. Stream Types")])
        text = "\n".join(b.text for b in doc.blocks)
        self.assertNotIn("Standards Track", text)
        self.assertNotIn("QUIC Transport", text)
        self.assertIn("   A stream has a limit of 100 streams.", text)  # indentation kept

    def test_sections_carry_their_heading_paths(self):
        doc = textdocs.parse(MARKDOWN, markdown=True)
        sections, index = textdocs.text_sections(doc, 2, 20)
        self.assertEqual([s.heading_path for s in sections],
                         [["Harrow Creek WTP"], ["Harrow Creek WTP", "Design Basis"],
                          ["Harrow Creek WTP", "Chlorine Feed"]])
        pumps = next(b for b in doc.blocks if b.kind == "table")
        self.assertEqual(index.box(pumps.page, pumps.box).heading_path, ["Harrow Creek WTP", "Design Basis"])

class Reading(unittest.TestCase):
    def test_a_markdown_file_becomes_located_evidence(self):
        evidence, coverage, sections, model = extract("basis.md", MARKDOWN)
        values = {e.value: e for e in evidence}
        self.assertEqual(set(values), {"25.9", "5,151", "96.8", "5,590", "64.9", "3.3"})
        flow = values["25.9"]
        self.assertIsInstance(flow.locator, TextLocator)
        self.assertEqual(MARKDOWN.splitlines()[flow.locator.lines[0] - 1], "The plant is sized for a design flow of 25.9 MGD.")
        self.assertEqual(values["5,151"].locator.region, "table")
        self.assertEqual(MARKDOWN.splitlines()[values["5,151"].locator.lines[0] - 1], "| P-101A | 5,151 | 96.8 |")
        rows = [q for q in model.queries if q.region == "table"]
        self.assertEqual(rows[0].data, 'Header: ["Tag", "Capacity (gpm)", "TDH (ft)"]\nRow: ["P-101A", "5,151", "96.8"]')
        self.assertTrue(all(q.heading for q in model.queries))
        self.assertIn("raw water --> rapid mix", "\n".join(q.data for q in model.queries))
        self.assertEqual([r["status"] for r in coverage if r["task"].startswith("image")], ["skipped"])

    def test_context_levers_read_text_files_too(self):
        _, _, _, model = extract("basis.md", MARKDOWN)
        table = next(q for q in model.queries if q.region == "table")
        self.assertIn("Above the table: ...", table.context)
        self.assertIn("Within: Harrow Creek WTP > Design Basis > Pumps", table.context)

    def test_a_plain_text_file_is_read_by_page(self):
        evidence, coverage, sections, model = extract("rfc.txt", RFC)
        limit = next(e for e in evidence if e.value == "100")
        self.assertEqual((limit.locator.page, limit.locator.region), (2, "text"))
        self.assertTrue(all("Standards Track" not in q.data for q in model.queries))
        self.assertEqual([s.heading_path for s in sections][-2:], [["2. Streams"], ["2. Streams", "2.1. Stream Types"]])

class Pipeline(unittest.TestCase):
    """Two revisions of a Markdown file compared end to end: a store, a report, and a second run from the store."""
    def test_markdown_revisions_compare_and_reload(self):
        import contextlib, io, json, sys
        sys.path.insert(0, str(Path(__file__).parent))
        from test_concurrency import jittery_model
        from semantic_pdf_diff import cli
        a = "# Plant\n\n## Pumps\n\nPump P-1 draws 120 kW.\n\nPump P-2 draws 80 kW.\n"
        b = "# Plant\n\n## Pumps\n\nPump P-1 draws 120 kW.\n\nPump P-2 draws 90 kW.\n"
        with tempfile.TemporaryDirectory() as d, jittery_model() as (url, state):
            root = Path(d)
            (root / "a.md").write_text(a)
            (root / "b.md").write_text(b)
            args = [str(root / "a.md"), str(root / "b.md"), "--out", str(root / "out"), "--base-url", url,
                    "--mode", "revisions", "-q"]
            reports = []
            for _ in range(2):  # the second run reads both files' evidence from the store
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(cli.main(args), 0)
                reports.append(json.loads((root / "out" / "report.json").read_text()))
            html = (root / "out" / "report.html").read_text()
        first, second = reports
        self.assertEqual(first["evidence"], second["evidence"])
        self.assertEqual({e["locator"]["format"] for e in first["evidence"]}, {"text"})
        self.assertEqual({s["origin"] for s in first["sections"]}, {"headings"})
        self.assertEqual(sorted(e["value"] for e in first["evidence"]), ["120", "120", "80", "90"])
        self.assertEqual([f["relation"] for f in first["findings"] if f.get("settled")], ["equivalent"])
        self.assertIn("lines 5–5", html)

if __name__ == "__main__":
    unittest.main()
