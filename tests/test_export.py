"""`semantic-pdf-diff export`: a report's claims as Markdown chunks for a RAG system's ingest
(docs/plans/single-source-outputs-2026-09-23.md, feature 2; the owner, 2026-10-31: "Please proceed in recommended
order"; then per topic and per finding: "The proposed next steps seem good to me. Please proceed.")."""
import stubs  # noqa: F401 (a clean environment)
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from semantic_pdf_diff import export, indexes
from stubs import serving
from test_analyze import asked, plant, run
from test_indexes import claim, report

def pumps(n=3):
    found = report([claim(f"A-{k}{j}", "ca", f"P-10{k} pump", attribute, value, unit, page=k)
                    for k in range(1, n + 1) for j, (attribute, value, unit) in enumerate(
                        (("rated power", f"{70 + k}", "kW"), ("head", f"{40 + k}", "m")))],
                   sections=[{"content": "ca", "id": "s1", "heading_path": ["4 Pumps"], "about": "The feed pumps."}],
                   created_at="2026-10-31T00:00:00", mode="analysis", unmatched=[])
    for e in found["evidence"]:
        e["section"] = "s1"
    return found

class Chunks(unittest.TestCase):
    def test_a_sections_claims_by_subject_saying_where_they_came_from(self):
        data = pumps()
        files = export.exported(data, indexes.built(data), "0.18.0")
        self.assertEqual(files, export.exported(data, indexes.built(data), "0.18.0"))  # the same names for the same
        names = [n for n in files if n != "index.md"]
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{16}\.md", n) for n in names))
        (detail,) = [t for t in files.values() if "Source: " in t]
        self.assertTrue(detail.startswith('---\ntitle: "4 Pumps — a.pdf, pages 1–3"\nsource: "a"\nfile: "a.pdf"\n'))
        self.assertIn("Source: a / a.pdf, pages 1–3. Section: 4 Pumps.", detail)
        self.assertIn("The feed pumps.", detail)
        self.assertIn("### P-101 pump\n\n- rated power: 71 kW [page 1]\n- head: 41 m [page 1]", detail)
        self.assertIn("- Made by semantic-pdf-diff 0.18.0 from the report of 2026-10-31T00:00:00", files["index.md"])
        self.assertIn("- [Subjects A to Z](", files["index.md"])
        subjects = next(t for t in files.values() if t.startswith('---\ntitle: "Subjects A to Z"'))
        self.assertIn(f"- **P-101 pump**: head, rated power — in {[n for n in names if files[n] == detail][0]}",
                      subjects)  # each subject pointing to the chunk holding its claims

    def test_a_long_section_in_parts_each_saying_where(self):
        data = pumps(9)
        files = export.exported(data, indexes.built(data), "", size=120)
        parts = [t for t in files.values() if "Source: " in t]
        self.assertGreater(len(parts), 3)
        self.assertTrue(all("Section: 4 Pumps." in t for t in parts))
        self.assertIn("# 4 Pumps (1 of ", parts[0])

    def test_a_chunk_a_topic_its_claims_naming_their_files(self):
        data = pumps(4)
        data["files"].append({"source": "a", "path": "b.pdf", "content": "cb"})
        data["evidence"].append(claim("B-1", "cb", "P-101 pump", "speed", "1480", "rpm", page=2))
        placed = {e["id"]: (0 if e["attribute"] != "head" else 1) for e in data["evidence"]}
        with mock.patch("semantic_pdf_diff.report.browsing", return_value=(object(), placed, ["Power", "Head"])):
            files = export.exported(data, indexes.built(data), "")
        (power,) = [t for t in files.values() if t.startswith('---\ntitle: "Topic: Power"')]
        self.assertIn("### P-101 pump\n\n- rated power: 71 kW [a.pdf, page 1]\n- speed: 1480 rpm [b.pdf, page 2]",
                      power)
        self.assertIn("- [Topic: Head](", files["index.md"])

    def test_a_comparisons_findings_by_what_was_found(self):
        data = report([claim("A-1", "ca", "P-101 pump", "head", "42", "m", page=2),
                       claim("B-1", "cb", "P-101 pump", "head", "45", "m", page=3),
                       claim("B-2", "cb", "P-102 pump", "head", "40", "m", page=4)],
                      findings=[{"a": "A-1", "b": "B-1", "relation": "different", "confidence": .9,
                                 "rationale": "The head rose.", "explanation": {"kind": "changed",
                                                                                "rationale": "Revised."}}],
                      sources=("a", "b"), unmatched=[{"id": "B-2", "status": "unaligned"}])
        files = export.exported(data, indexes.built(data), "")
        (differ,) = [t for t in files.values() if t.startswith('---\ntitle: "They differ: a against b"')]
        self.assertIn("### P-101 pump — head\n\n- a: head: 42 m [a.pdf, page 2]\n- b: head: 45 m [b.pdf, page 3]\n"
                      "- They differ (confidence 0.9): The head rose.\n- Why it differs: changed: Revised.", differ)
        (only,) = [t for t in files.values() if t.startswith('---\ntitle: "Only in b: a against b"')]
        self.assertIn("### P-102 pump\n\n- head: 40 m [b.pdf, page 4]", only)

class Command(unittest.TestCase):
    def test_an_analysis_exported_beside_its_store(self):
        state = {"embedded": [], "names": 0}
        with tempfile.TemporaryDirectory() as d, serving(asked(state)) as url:
            root = Path(d)
            config = root / "settings.json"
            config.write_text(json.dumps({"search_names": False, "topic_names": False}))
            run("analyze", plant(root / "plant"), "--store", root / "out", "--base-url", url, "--config", config,
                "--no-situate")
            asked_before = len(state.get("prompts", []))
            code, out, _ = run("export", "--store", root / "out")
            written = sorted(p.name for p in (root / "out" / "export").iterdir())
            index = (root / "out" / "export" / "index.md").read_text()
        self.assertEqual(code, 0)
        self.assertEqual(len(state.get("prompts", [])), asked_before)  # no model calls
        self.assertIn("chunks and index.md)", out)
        self.assertIn("index.md", written)
        self.assertIn("- [Blowers](", index)  # a chunk a section: the blowers' file's heading

if __name__ == "__main__":
    unittest.main()
