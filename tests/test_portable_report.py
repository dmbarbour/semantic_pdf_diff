"""Portable reports (docs/plans/portable-reports-2026-10-19.md): report.html is one file that travels alone, its parts
gzipped inside it and its crops embedded under a byte budget in order of value (crops.py). The owner, 2026-10-19: "I
need a report that is easily migrated"; then "consider providing a command-line option and a mode that provides some
feedback about some items that will be cut under that budget"."""
import stubs  # noqa: F401 (a clean environment)
import base64
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from semantic_pdf_diff import crops
from semantic_pdf_diff.report import unpacked, write_report
from semantic_pdf_diff.schema import FileRef, Source
from test_pipeline import ev

def noise(path, side, seed=0):
    """A PNG of noise, side pixels square: incompressible, so its crop's size grows with its area."""
    import pymupdf
    samples = random.Random(seed).randbytes(side * side * 3)
    path.parent.mkdir(parents=True, exist_ok=True)
    pymupdf.Pixmap(pymupdf.csRGB, side, side, samples, False).save(str(path))
    return f"assets/{path.name}"

def finding(a, b, relation):
    return {"a": a.id, "b": b.id, "relation": relation, "rationale": "as judged", "confidence": 0.9,
            "retrieval_score": 0.5}

def report(claims, findings, unmatched=()):
    """A report document: two sources, the claims, their findings and unmatched claims."""
    return {"mode": "proposals", "findings": findings, "unmatched": list(unmatched), "shared": [],
            "evidence": [c.model_dump() for c in claims], "coverage": [], "retrieval": {},
            "sources": [Source(name="A").model_dump(), Source(name="B").model_dump()],
            "files": [FileRef(source="A", path="a.pdf", content=ev("A-1").content).model_dump(),
                      FileRef(source="B", path="b.pdf", content=ev("B-1").content).model_dump()]}

class OneFile(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = self.root / "store" / "assets"

    def test_a_report_written_elsewhere_holds_its_crops_and_links_nothing(self):
        a = ev("A-1", kind="chart", image=noise(self.assets / "a-tile-p1-0.png", 60))
        data = report([a, ev("B-1")], [finding(a, ev("B-1"), "different")])
        write_report(data, self.root / "reports" / "r1", assets=self.assets)
        page = (self.root / "reports" / "r1" / "report.html").read_text()
        self.assertNotIn("assets/", page.replace("store/assets", ""))  # nothing linked
        held = json.loads(page.split('id="report-crops">', 1)[1].split("</script>", 1)[0])
        self.assertEqual(held["type"], "image/webp")
        self.assertEqual(base64.b64decode(held["data"][0])[8:12], b"WEBP")
        shown = unpacked(page)
        self.assertIn('<img class="crop" data-crop="0"', shown)
        self.assertIn("primary pump", shown)
        self.assertEqual(json.loads((self.root / "reports" / "r1" / "report.json").read_text()),
                         json.loads(json.dumps(data)))

    def test_the_same_report_is_written_byte_for_byte(self):
        a = ev("A-1", kind="chart", image=noise(self.assets / "a.png", 40))
        data = report([a, ev("B-1")], [finding(a, ev("B-1"), "uncertain")])
        for name in ("one", "two"):
            write_report(data, self.root / name, assets=self.assets)
        self.assertEqual((self.root / "one" / "report.html").read_bytes(),
                         (self.root / "two" / "report.html").read_bytes())

    def claims(self):
        """Four crops: two in a different finding (one of a chart), one complementary, one equivalent."""
        text = ev("A-1", image=noise(self.assets / "text.png", 150, 1), quote_verified=True)  # group 0, second
        chart = ev("A-2", kind="chart", image=noise(self.assets / "chart.png", 60, 2))      # group 0, first
        compl = ev("A-3", kind="table", image=noise(self.assets / "table.png", 60, 3))      # group 1
        equal = ev("A-4", kind="diagram", image=noise(self.assets / "diagram.png", 40, 4))  # group 2
        b = [ev(f"B-{i}") for i in range(1, 5)]
        findings = [finding(equal, b[3], "equivalent"), finding(compl, b[2], "complementary"),
                    finding(text, b[0], "different"), finding(chart, b[1], "different")]
        return report([text, chart, compl, equal, *b], findings)

    def test_crops_fill_the_budget_in_order_of_value(self):
        data = self.claims()
        every = write_report(data, self.root / "out", assets=self.assets, write=False)
        self.assertEqual([c.image for c in every.wanted],
                         ["assets/chart.png", "assets/text.png", "assets/table.png", "assets/diagram.png"])
        self.assertEqual([c.group for c in every.wanted], [0, 0, 1, 2])
        size = {c.image: c.size for c in every.wanted}
        self.assertGreater(size["assets/text.png"], size["assets/table.png"] + size["assets/diagram.png"])
        # room for all but the big one: it's left out, and the smaller ones after it still go in
        budget = every.page + size["assets/chart.png"] + size["assets/table.png"] + size["assets/diagram.png"] + 200
        account = write_report(data, self.root / "out", assets=self.assets, budget=budget)
        self.assertEqual([c.image for c in account.cut], ["assets/text.png"])
        self.assertLessEqual(account.size, budget)
        self.assertEqual(account.size, (self.root / "out" / "report.html").stat().st_size)
        shown = unpacked((self.root / "out" / "report.html").read_text())
        self.assertIn("Crop left out for the report's size budget (text:0)", shown)
        self.assertIn("1 of 4 crops left out", shown)
        self.assertIn("Crops left out (1)", shown)

    def test_a_crop_two_claims_show_is_paid_for_once_at_the_better_place(self):
        image = noise(self.assets / "shared.png", 40)
        a, c = ev("A-1", image=image), ev("A-2", attribute="flow", image=image)
        b, d = ev("B-1"), ev("B-2")
        account = write_report(report([a, b, c, d], [finding(a, b, "equivalent"), finding(c, d, "uncertain")]),
                               self.root / "out", assets=self.assets, write=False)
        self.assertEqual([(x.image, x.group) for x in account.wanted], [(image, 0)])

    def test_a_budget_of_nothing_embeds_no_crop(self):
        account = write_report(self.claims(), self.root / "out", assets=self.assets, budget=0)
        self.assertEqual((account.chosen, len(account.cut)), (set(), 4))
        self.assertGreater(account.size, 0)  # the page is written all the same
        self.assertNotIn("data-crop=", unpacked((self.root / "out" / "report.html").read_text()))

    def test_feedback_says_what_each_group_costs_in_full(self):
        data = self.claims()
        every = write_report(data, self.root / "out", assets=self.assets, write=False)
        account = write_report(data, self.root / "out", assets=self.assets, budget=every.page, write=False)
        lines = crops.feedback(account)
        self.assertFalse((self.root / "out").exists())  # a dry run writes nothing
        self.assertIn("4 wanted", lines[1])
        in_full = account.page + sum(c.size for c in account.wanted if c.group == 0)
        self.assertRegex(lines[2], r"^  different or uncertain +2 crops, +\d+ KB: all left out; in full with "
                                   r"--report-budget \d+KB$")
        needed = crops.as_budget(in_full)
        self.assertTrue(lines[2].endswith(needed))
        from semantic_pdf_diff.cli import report_size
        self.assertGreaterEqual(report_size(needed), in_full)  # rounded up: that budget does include them
        self.assertIn("left out, the first 4 of 4 by priority:", lines)
        self.assertIn("a.pdf, page 1, text:0: primary pump — rated power", lines[-4])

    def test_a_crop_the_store_lost_is_shown_missing(self):
        a = ev("A-1", kind="chart", image="assets/gone.png")
        account = write_report(report([a, ev("B-1")], [finding(a, ev("B-1"), "different")]), self.root / "out",
                               assets=self.assets)
        self.assertEqual(account.wanted, [])
        self.assertIn("Crop not found in the store (assets/gone.png)",
                      unpacked((self.root / "out" / "report.html").read_text()))

    def test_without_pillow_crops_are_jpeg(self):
        path = self.root / "x.png"
        noise(path, 20)
        with mock.patch.dict(sys.modules, {"PIL": None}):
            mime, encode = crops.encoder()
            self.assertEqual(mime, "image/jpeg")
            self.assertEqual(encode(path)[:2], b"\xff\xd8")

    def test_the_header_says_how_many_candidate_pairs_went_unjudged(self):
        a, b = ev("A-1"), ev("B-1")
        data = report([a, b], [finding(a, b, "different")])
        data["retrieval"] = {"candidate_pairs": 1500, "attempted_pairs": 1000, "omitted_by_pair_limit": 500}
        write_report(data, self.root / "out")
        self.assertIn("500 of 1500 candidate pairs weren't judged: a comparison judges at most 1000, best first "
                      "(<code>--max-pairs</code>", unpacked((self.root / "out" / "report.html").read_text()))

    def test_run_metadata_leaves_out_what_the_page_shows_elsewhere(self):
        a, b = ev("A-1"), ev("B-1")
        data = report([a, b], [finding(a, b, "different")])
        data.update(groupings=[{"kind": "matched", "earlier": ["pump"], "later": ["pump"], "earlier_claims": [a.id],
                                "later_claims": [b.id], "evidence": {}, "outcome": {}}], settings={"top_k": 4})
        write_report(data, self.root / "out")
        shown = unpacked((self.root / "out" / "report.html").read_text())
        metadata = shown.split("Run metadata and limitations", 1)[1].split("<pre>", 1)[1].split("</pre>", 1)[0]
        self.assertIn("&quot;top_k&quot;: 4", metadata)
        self.assertNotIn("groupings", metadata)
        self.assertIn("How the revisions were grouped", shown)  # shown in its own place
        self.assertIn("PDF bbox [0.0, 0.0, 100.0, 100.0]", shown)

    def test_budgets_on_the_command_line(self):
        import argparse
        from semantic_pdf_diff.cli import report_size
        self.assertEqual([report_size(x) for x in ("20MB", "500kb", "1.5GB", "7", "0", "12B", "3 M")],
                         [20_000_000, 500_000, 1_500_000_000, 7_000_000, 0, 12, 3_000_000])
        with self.assertRaises(argparse.ArgumentTypeError):
            report_size("lots")

def two_files_a_side(assets):
    """Two sources of two files each, both pairs modified: a finding in each pair, one across them, and crops from
    the first pair's earlier file (three) and the second's (one)."""
    content = lambda name: "sha256:" + name * 64 + ".pdf"
    x1, x2 = content("1"), content("2")  # the first source's files
    y1, y2 = content("3"), content("4")  # the second's
    claim = lambda i, c, **kw: ev(f"{c[7]}-{i}", content=c, attribute=f"flow {i}", **kw)
    a = [claim(i, x1, kind="chart", image=noise(assets / f"x1-{i}.png", 30, i)) for i in range(3)]
    b = claim(9, x2, kind="chart", image=noise(assets / "x2.png", 30, 9))
    c, d, e = claim(0, y1), claim(1, y1), claim(2, y2)
    data = report(a + [b, c, d, e], [finding(a[0], c, "different"), finding(a[1], d, "different"),
                                     finding(b, e, "uncertain"), finding(a[2], e, "different")])
    data["sources"] = [Source(name="v1").model_dump(), Source(name="v2").model_dump()]
    data["files"] = [FileRef(source="v1", path="v1/p.pdf", content=x1).model_dump(),
                     FileRef(source="v1", path="v1/q.pdf", content=x2).model_dump(),
                     FileRef(source="v2", path="v2/p.pdf", content=y1).model_dump(),
                     FileRef(source="v2", path="v2/q.pdf", content=y2).model_dump()]
    data["file_difference"] = {"unchanged": [], "modified": [["v1/p.pdf", "v2/p.pdf"], ["v1/q.pdf", "v2/q.pdf"]],
                               "moved": [], "added": [], "removed": []}
    return data

class ManyFiles(unittest.TestCase):
    """Many files on each side (portable reports, milestone 2): browsed by file, crops shared between files."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.assets = self.root / "assets"

    def test_the_files_are_a_table_of_pairs_each_showing_its_findings(self):
        write_report(two_files_a_side(self.assets), self.root / "out", assets=self.assets)
        page = (self.root / "out" / "report.html").read_text()
        shown = unpacked(page)
        self.assertIn("<summary>Files: 2 modified</summary>", shown)
        self.assertIn("<td>v1/p.pdf → v2/p.pdf</td><td>3 different <small>(1 reaching other files)</small></td>"
                      "<td>0</td><td>3 of 3</td>", shown)
        self.assertIn("<td>v1/q.pdf → v2/q.pdf</td><td>1 different, 1 uncertain "
                      "<small>(1 reaching other files)</small>", shown)
        self.assertIn('<button class="pick" data-files="0,1">Show</button>', shown)  # files numbered pair by pair
        self.assertIn('<option value="2,3">v1/q.pdf → v2/q.pdf</option>', shown)
        import gzip
        import re
        parts = json.loads(gzip.decompress(base64.b64decode(re.search(r'id="report-data">([^<]*)<', page).group(1))))
        self.assertEqual([f["files"] for f in parts["findings"]], [[0, 1], [0, 1], [2, 3], [0, 3]])

    def test_files_added_or_removed_are_rows_of_their_own(self):
        data = two_files_a_side(self.assets)
        added = FileRef(source="v2", path="v2/new.pdf", content="sha256:" + "5" * 64 + ".pdf")
        data["files"].append(added.model_dump())
        data["file_difference"]["added"] = ["v2/new.pdf"]
        write_report(data, self.root / "out", assets=self.assets)
        shown = unpacked((self.root / "out" / "report.html").read_text())
        self.assertIn("<summary>Files: 2 modified, 1 added</summary>", shown)
        self.assertIn("<td>v2/new.pdf (added)</td><td>none</td><td>0</td><td>—</td><td></td>", shown)
        self.assertIn('<option value="4">v2/new.pdf (added)</option>', shown)

    def test_files_take_turns_for_crops_within_a_group(self):
        account = write_report(two_files_a_side(self.assets), self.root / "out", assets=self.assets, write=False)
        self.assertEqual([c.image for c in account.wanted],
                         ["assets/x1-0.png", "assets/x2.png", "assets/x1-1.png", "assets/x1-2.png"])
        lines = crops.feedback(account)
        self.assertIn("by file, most left out first (2 files with crops):", lines)

    def test_a_split_report_is_a_file_a_pair_and_an_index(self):
        account = write_report(two_files_a_side(self.assets), self.root / "out", assets=self.assets, split=True)
        folder = self.root / "out" / "report-split"
        self.assertEqual(sorted(x.name for x in folder.iterdir()), ["01-p.html", "02-q.html", "index.html"])
        self.assertFalse((self.root / "out" / "report.html").exists())
        self.assertTrue((self.root / "out" / "report.json").exists())
        index = (folder / "index.html").read_text()
        self.assertIn('<a href="01-p.html">Open</a>', index)
        self.assertIn("A split report: a file a pair of files, 2 in this folder", index)
        first = unpacked((folder / "01-p.html").read_text())
        self.assertIn('Part 1 of 2 of a split report (v1/p.pdf → v2/p.pdf): <a href="index.html">', first)
        self.assertIn("{&#x27;different&#x27;: 3}", first)  # its two, and the one reaching the other pair's file
        second = unpacked((folder / "02-q.html").read_text())
        self.assertIn("{&#x27;uncertain&#x27;: 1, &#x27;different&#x27;: 1}", second)
        self.assertEqual(account.size, sum(x.stat().st_size for x in folder.iterdir()))

    def test_one_pair_of_files_is_never_split(self):
        a = ev("A-1")
        write_report(report([a, ev("B-1")], [finding(a, ev("B-1"), "different")]), self.root / "out", split=True)
        self.assertTrue((self.root / "out" / "report.html").exists())
        self.assertFalse((self.root / "out" / "report-split").exists())

    def test_one_pair_of_files_keeps_the_files_summary_in_the_header(self):
        a = ev("A-1")
        data = report([a, ev("B-1")], [finding(a, ev("B-1"), "different")])
        data["file_difference"] = {"unchanged": [], "modified": [["a.pdf", "b.pdf"]], "moved": [], "added": [],
                                   "removed": []}
        write_report(data, self.root / "out")
        shown = unpacked((self.root / "out" / "report.html").read_text())
        self.assertIn("<details><summary>Files: 0 unchanged, 1 modified", shown)
        self.assertNotIn('id="file"', shown)

def parts_of(page):
    """The report's parts, as the page's script inflates them."""
    import gzip
    import re
    return json.loads(gzip.decompress(base64.b64decode(re.search(r'id="report-data">([^<]*)<', page).group(1))))

class SharedStructure(unittest.TestCase):
    """What a claim says written once however many claims say it, and equivalent findings whose claims say the same
    folded (the owner, 2026-10-19: "shared structure for subsets of identical claims")."""
    def test_claims_that_say_the_same_share_one_statement_and_their_finding_is_folded(self):
        a, b = ev("A-1"), ev("B-1")  # the same statement, in two files
        c, d = ev("A-2", value="12"), ev("B-2", value="14")
        data = report([a, b, c, d], [finding(a, b, "equivalent"), finding(c, d, "different")])
        with tempfile.TemporaryDirectory() as folder:
            write_report(data, Path(folder))
            page = (Path(folder) / "report.html").read_text()
        parts = parts_of(page)
        self.assertEqual(len(parts["said"]), 3)  # four claims, three statements: A-1 and B-1 say the same
        self.assertEqual(parts["cards"]["A-1"].count('<div data-said="'), 1)
        self.assertEqual([f["same"] for f in parts["findings"]], [True, False])
        shown = unpacked(page)
        self.assertIn("Fold the 1 equivalent findings whose two claims say the same", shown)
        self.assertEqual(shown.count("<b>primary pump — rated power</b><p>10 kW</p>"), 2)  # in both of its cards

BROWSERS = ("chromium", "chromium-browser", "google-chrome", "chrome")

class InABrowser(unittest.TestCase):
    """The page's script, run by a headless browser where one is installed (it inflates the parts, puts cards and
    crops in place, and shows findings a page at a time)."""
    def test_the_page_opens_with_its_first_findings_cards_and_crops(self):
        browser = next((b for b in map(shutil.which, BROWSERS) if b), None)
        if browser is None:
            self.skipTest("no headless browser installed (chromium)")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chart = ev("A-0", kind="chart", image=noise(root / "assets" / "chart.png", 40))
            claims = [chart] + [ev(f"A-{i}", attribute=f"flow {i}") for i in range(1, 150)]
            others = [ev(f"B-{i}", attribute=f"flow {i}") for i in range(150)]
            data = report(claims + others, [finding(a, b, "different") for a, b in zip(claims, others)])
            write_report(data, root / "out", assets=root / "assets")
            page = (root / "out" / "report.html").as_uri()
            flags = ["--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=10000", "--dump-dom"]
            done = subprocess.run([browser, *flags, page], capture_output=True, text=True, timeout=120)
        import re
        dom = re.sub(r"<script.*?</script>", "", done.stdout, flags=re.S)  # what's drawn, not the script's text
        self.assertNotIn("Opening the report", dom)
        self.assertIn("150 of 150 findings", dom)
        self.assertEqual(dom.count("<article"), 100)
        self.assertIn("Show 50 more (50 left)", dom)
        self.assertEqual(dom.count("<section><h3>"), 200)
        self.assertNotIn("data-card=", dom)
        self.assertNotIn("data-said=", dom)
        self.assertIn('src="data:image/webp;base64,', dom)

    def test_findings_that_say_the_same_are_folded_until_asked_for(self):
        browser = next((b for b in map(shutil.which, BROWSERS) if b), None)
        if browser is None:
            self.skipTest("no headless browser installed (chromium)")
        with tempfile.TemporaryDirectory() as d:
            a, b, c, e = ev("A-1"), ev("B-1"), ev("A-2", value="12"), ev("B-2", value="14")
            write_report(report([a, b, c, e], [finding(a, b, "equivalent"), finding(c, e, "different")]),
                         Path(d) / "out")
            page = (Path(d) / "out" / "report.html").as_uri()
            flags = ["--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=10000", "--dump-dom"]
            dom = subprocess.run([browser, *flags, page], capture_output=True, text=True, timeout=120).stdout
        self.assertIn("1 of 2 findings (1 that say the same in both folded)", dom)
        self.assertEqual(dom.count("<article"), 1)

if __name__ == "__main__":
    unittest.main()
