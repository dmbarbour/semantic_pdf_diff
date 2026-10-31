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
        own = next(n for n in names if files[n].startswith('---\ntitle: "Subject: P-101 pump"'))
        self.assertIn(f"- **P-101 pump**: head, rated power — in {own}, {[n for n in names if files[n] == detail][0]}",
                      subjects)  # each subject pointing to its own chunk, then the chunks holding its claims

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

    def test_a_subject_its_claims_from_every_place_and_what_it_doesnt_give(self):
        data = pumps(4)
        data["evidence"] = [e for e in data["evidence"] if (e["entity"], e["attribute"]) != ("P-104 pump", "head")]
        data["files"].append({"source": "a", "path": "b.pdf", "content": "cb"})
        data["evidence"].append(claim("B-1", "cb", "P-104 pump", "speed", "1480", "rpm", page=2))
        files = export.exported(data, indexes.built(data), "")
        (p104,) = [t for t in files.values() if t.startswith('---\ntitle: "Subject: P-104 pump"')]
        self.assertIn('subject: "P-104 pump"', p104)
        self.assertIn("What a says about P-104 pump, from every file and section, by property", p104)
        self.assertIn("- rated power: 74 kW [a.pdf, page 4]\n- speed: 1480 rpm [b.pdf, page 2]\n"
                      "What it doesn't give (weak: it may be said elsewhere, or missed by the reader):\n"
                      "- Missing among siblings: head (", p104)
        self.assertNotIn("Read together", p104)  # no second pass: no notes, nor the line saying what they are
        data["commentary"] = {"entries": [{"kind": "looked", "source": "a", "subject": "P-104 pump", "claims": [],
                                           "relation": "not_given", "text": "head", "where": "a.pdf, page 4"}]}
        files = export.exported(data, indexes.built(data), "")
        (p104,) = [t for t in files.values() if t.startswith('---\ntitle: "Subject: P-104 pump"')]
        self.assertIn("; looked for on a.pdf, page 4: not given", p104)  # where the gap was looked for

    def test_the_second_passs_notes_under_the_claims_they_are_about(self):
        data = pumps(2)
        data["evidence"].append(claim("A-15", "ca", "P-101 pump", "head", "45", "m", page=5))
        data["evidence"][-1]["section"] = "s1"
        data["commentary"] = {"entries": [
            {"kind": "relation", "source": "a", "subject": "P-101 pump", "claims": ["A-11", "A-15"],
             "relation": "contradicts", "why": "the datasheet gives another head", "key": []},
            {"kind": "reread", "source": "a", "subject": "P-101 pump", "claims": ["A-15"], "relation": "otherwise",
             "text": "44 m", "key": []}]}
        files = export.exported(data, indexes.built(data), "")
        (detail,) = [t for t in files.values() if "Source: " in t]
        self.assertIn(export.NOTED, detail)
        self.assertIn("- head: 41 m [page 1]\n  - Read together, contradicts 45 m (a.pdf, page 5): the datasheet "
                      "gives another head\n", detail)
        self.assertIn("- head: 45 m [page 5]\n  - Read together, contradicts 41 m (a.pdf, page 1): the datasheet "
                      "gives another head\n  - Read again from its place: it gives 44 m", detail)
        (p101,) = [t for t in files.values() if t.startswith('---\ntitle: "Subject: P-101 pump"')]
        self.assertIn("- head: 45 m [a.pdf, page 5]\n  - Read together, contradicts 41 m (a.pdf, page 1)", p101)
        (p102,) = [t for t in files.values() if t.startswith('---\ntitle: "Subject: P-102 pump"')]
        self.assertNotIn(export.NOTED, p102)  # said only where a chunk has notes

    def test_a_kind_its_items_by_property_as_a_table(self):
        data = pumps(3)
        files = export.exported(data, indexes.built(data), "")
        (kind,) = [t for t in files.values() if t.startswith('---\ntitle: "Kind: pump (P)"')]
        self.assertIn("The 3 items of the kind pump (P), by property, the most given first; “—” where an item gives "
                      "none. Given by: head 3 of 3; rated power 3 of 3.", kind)
        self.assertIn("| Item | head | rated power |\n|---|---|---|\n| P-101 pump | 41 m | 71 kW |\n"
                      "| P-102 pump | 42 m | 72 kW |", kind)
        parts = [t for t in export.exported(data, indexes.built(data), "", size=40).values()
                 if t.startswith('---\ntitle: "Kind: pump (P) (')]
        self.assertEqual(len(parts), 3)  # a row a part at this size, each under the table's header again
        self.assertTrue(all("| Item | head | rated power |\n|---|---|---|\n| P-10" in t for t in parts))

class Command(unittest.TestCase):
    def test_a_document_table_as_a_markdown_table_its_parts_under_its_header(self):
        """A table read by rules, from its record's cells (the owner, 2026-10-31: "Proceed with items 3, 4 and 5")."""
        found = pumps(3)
        found["records"] = [{"content": "ca", "id": "table:p2:0", "kind": "table", "label": "Pump schedule", "page": 2,
                             "cells": [["Tag", "Capacity | gpm"], *[[f"P-{k}", f"{k},318"] for k in range(300, 340)]]}]
        files = export.exported(found, indexes.built(found), size=400)
        tables = sorted((t for t in files.values() if t.startswith("---\ntitle: \"Table: ")), key=lambda t: int(
            re.search(r"\((\d+) of", t).group(1)))
        self.assertGreater(len(tables), 1)  # a long table in parts
        first = tables[0]
        self.assertIn("# Table: a.pdf, page 2, “Pump schedule” (1 of", first)
        self.assertIn("A table of 40 rows, from a.pdf, page 2, “Pump schedule”", first)
        self.assertIn("| Tag | Capacity \\| gpm |\n|---|---|\n| P-300 | 300,318 |", first)
        self.assertTrue(all("| Tag | Capacity \\| gpm |\n|---|---|\n" in t for t in tables))  # its header again
        self.assertIn("source: \"a\"", first)

    def test_an_export_replaces_the_last_one_in_its_folder(self):
        """Each made fresh (the owner, 2026-10-31: "Each export or report should be logically fresh from the
        sources, not history-dependent.")."""
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "export"
            first = export.exported(pumps(3), indexes.built(pumps(3)))
            self.assertEqual(export.written(out, first), 0)
            (out / ".hidden").write_text("a viewer's")
            second = export.exported(pumps(2), indexes.built(pumps(2)))
            removed = export.written(out, second)
            files = sorted(p.name for p in out.iterdir() if p.name != ".hidden")
            (out / "notes.txt").write_text("mine")
            with self.assertRaisesRegex(ValueError, r"holds files an export doesn't write \(notes\.txt\)"):
                export.written(out, first)
            after = sorted(p.name for p in out.iterdir() if p.name not in (".hidden", "notes.txt"))
        self.assertEqual(files, sorted(second))  # the folder this export alone
        self.assertEqual(removed, len(set(first) - set(second)))
        self.assertGreater(removed, 0)
        self.assertEqual(after, files)  # refused: nothing written

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
