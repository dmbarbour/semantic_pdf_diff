"""`semantic-pdf-diff search` and search.py (docs/plans/search-2026-10-20.md, milestone 2): a store's claims searched
as a report's search box searches them. The page's search (search.js) and this one are held to the same answers: the
same cases, run by both (the owner, 2026-10-20: "it would be convenient to have an easily searchable database of
claims even without the comparisons"; then "I like all the ideas for search.")."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff import cli, search
from semantic_pdf_diff.store import Store
import test_portable_report as page_tests  # the module, not its classes: they'd run here again
from test_portable_report import search_report

def found(q, view="claims", paired=False, side=None):
    """The card ids a query finds in search_report, in the order shown."""
    index = search.Index()
    claims, findings = search.report_items(search_report(), index)
    hits, _ = search.search(index, search.parse(q), claims, findings, view, paired=paired)
    if view == "findings":
        return [card for i, _, _ in hits for card in findings[i]["cards"]]
    return [claims[i]["card"] for i, _, _ in hits if side is None or claims[i]["side"] == side]

class Engine(unittest.TestCase):
    """The page's answers (test_portable_report.SearchInABrowser), from Python."""
    def test_words_phrases_exclusions_either(self):
        self.assertEqual(set(found("pump feed")), {"A-pump", "B-pump", "A-tank"})
        self.assertEqual(found("pump feed")[-1], "A-tank")
        self.assertEqual(found('"feed pump"'), ["A-tank"])
        self.assertEqual(set(found("pump -gearbox")), {"A-pump", "A-motor", "A-tank", "B-pump"})
        self.assertEqual(set(found("gearbox OR motor")), {"A-motor", "B-gearbox"})
        self.assertEqual(found("power of the pump"), ["A-pump"])
        self.assertEqual(len(found("-valve")), 7)

    def test_fields_pages_numbers(self):
        self.assertEqual(set(found("entity:pump")), {"A-pump", "A-motor", "B-pump", "B-gearbox"})
        self.assertEqual(set(found("page:4-5")), {"A-valve", "B-valve", "A-motor"})
        self.assertEqual(found("section:feed"), ["A-pump"])
        self.assertEqual(found("pdf"), [])
        self.assertEqual(set(found("file:b")), {"B-pump", "B-valve", "B-gearbox", "B-heater"})
        self.assertEqual(found("75"), ["A-pump"])
        self.assertEqual(set(found("1,000")), {"A-valve", "B-valve"})
        self.assertEqual(set(found("15")), {"A-heater", "B-heater"})
        self.assertEqual(set(found("cafe")), {"A-heater", "B-heater"})

    def test_counterparts_names_and_like(self):
        self.assertEqual(found("output", paired=True), ["B-pump", "A-pump"])
        index = search.Index()
        claims, findings = search.report_items(search_report(), index)
        _, names = search.search(index, search.parse("output"), claims, findings)
        self.assertEqual(names, [("rated power", 1)])
        self.assertEqual(found("like:A-pump", side=1)[0], "B-pump")

class SameAsThePage(unittest.TestCase):
    """Every case the browser ran, answered alike by search.py: the same items in the same order, the same names."""
    @classmethod
    def setUpClass(cls):
        page_tests.SearchInABrowser.setUpClass()  # skips without a headless browser
        cls.page = page_tests.SearchInABrowser.results

    def test_every_case(self):
        self.assertGreater(len(self.page), 15)
        for (view, label), result in self.page.items():
            q = label.removesuffix(" +counterparts").removeprefix("(offered) ")
            paired = label.endswith(" +counterparts") or view in ("opened",) or label.startswith("(offered)")
            side = int(result["side"]) if result.get("side") not in (None, "all") else None
            shown = [card for item in result["items"] for card in item]
            with self.subTest(view=view, q=label):
                self.assertEqual(found(q, "findings" if view == "findings" else "claims", paired, side), shown)
                index = search.Index()
                claims, findings = search.report_items(search_report(), index)
                _, names = search.search(index, search.parse(q), claims, findings)
                self.assertEqual([f'"{name}"' for name, _ in names], result["also"])

def run(*argv):
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()

class Command(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = self.root / "store"
        with Store(self.store) as store:
            store.save_comparison("2026-10-20T00:00:00", search_report())

    def test_claims_found_most_relevant_first_with_their_counterparts(self):
        code, out, _ = run("search", "output", "--store", self.store)
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "2 claims found (1 as counterparts): 1 in B; 1 in A")
        self.assertEqual(lines[1], 'The other source\'s names for it: "rated power" (1)')
        self.assertEqual(lines[2], "  1. pump, feed water — rated output = 80 kW (design load)")
        self.assertIn("B / b.pdf, page 3 · B-pump", lines[3])
        self.assertEqual(lines[4], "     “output 80 kW”")
        self.assertEqual(lines[5], "  2. feed water pump — rated power = 75 kW (design load)  [counterpart]")
        self.assertIn("§ Plant > Feed system · A-pump", lines[6])
        code, out, _ = run("search", "output", "--store", self.store, "--alone")
        self.assertTrue(out.startswith("1 claims found: 1 in B\n"))

    def test_a_word_left_out_needs_no_quoting_and_a_mistyped_option_is_refused(self):
        code, out, _ = run("search", "pump", "-gearbox", "--store", self.store, "--limit", "2")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("4 claims found"))
        self.assertIn("… 2 more (--limit 0 shows every one)", out)
        self.assertNotIn("gearbox —", out)
        with self.assertRaises(SystemExit) as refused:
            run("search", "pump", "--limt", "2", "--store", self.store)
        self.assertEqual(refused.exception.code, 1)

    def test_findings_sides_and_json(self):
        code, out, _ = run("search", "pump", "--findings", "--store", self.store)
        self.assertIn("1 findings found", out)
        self.assertIn("  1. different", out)
        code, out, _ = run("search", "heater", "--side", "b", "--store", self.store, "--json")
        data = json.loads(out)
        self.assertEqual([(x["id"], x["source"], x["value"]) for x in data["items"]], [("B-heater", "B", "15")])
        self.assertEqual(data["found"], 1)
        with self.assertRaises(SystemExit):
            run("search", "heater", "--side", "C", "--store", self.store)

    def test_several_stores_and_like_by_a_claims_id(self):
        other = self.root / "other"
        with Store(other) as store:
            store.save_comparison("2026-10-20T00:00:00", search_report())
        code, out, _ = run("search", "valve", "--store", self.store, "--store", other, "--json")
        data = json.loads(out)
        self.assertEqual(sorted({x["store"] for x in data["items"]}), sorted([str(self.store), str(other)]))
        self.assertEqual(data["found"], 4)
        code, out, _ = run("search", "like:A-pump", "--store", self.store, "--store", other, "--side", "B")
        self.assertIn("B-pump", out.splitlines()[2])

    def test_refusals(self):
        with self.assertRaises(SystemExit):
            run("search", "the", "--store", self.store)  # nothing to search for
        code, _, err = run("search", "pump", "--store", self.root / "empty")
        self.assertEqual(code, 1)
        self.assertIn("no such store", err)
        with Store(self.root / "new"):
            pass
        code, _, err = run("search", "pump", "--store", self.root / "new")
        self.assertIn("no comparisons yet", err)

if __name__ == "__main__":
    unittest.main()
