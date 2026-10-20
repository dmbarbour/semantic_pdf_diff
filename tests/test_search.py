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
    hits, _, _ = search.search(index, search.parse(q), claims, findings, view, paired=paired)
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
        self.assertEqual(len(found("-valve")), 11)

    def test_fields_pages_numbers(self):
        self.assertEqual(set(found("entity:pump")), {"A-pump", "A-motor", "B-pump", "B-gearbox"})
        self.assertEqual(set(found("page:4-5")), {"A-valve", "B-valve", "A-motor"})
        self.assertEqual(found("section:feed"), ["A-pump"])
        self.assertEqual(found("pdf"), [])
        self.assertEqual(set(found("file:b")), {"B-pump", "B-valve", "B-gearbox", "B-heater", "B-drive", "B-limit",
                                                 "B-blade"})
        self.assertEqual(found("75"), ["A-pump"])
        self.assertEqual(set(found("1,000")), {"A-valve", "B-valve"})
        self.assertEqual(set(found("15")), {"A-heater", "B-heater"})
        self.assertEqual(set(found("cafe")), {"A-heater", "B-heater"})

    def test_values_across_units(self):
        self.assertEqual(set(found(">70 kW")), {"A-pump", "B-pump", "B-drive"})
        self.assertEqual(found("value:0.075MW"), ["A-pump"])
        self.assertEqual(found("value:55L/s"), ["A-blower"])
        self.assertEqual(found("<40dBA"), ["B-limit"])
        self.assertEqual(found(">1000"), ["A-motor", "B-blade"])
        self.assertEqual(search.unknown(search.parse(">1mw")), ["mw"])
        self.assertEqual(search.parse("value:3.5:1")[0]["terms"][0]["words"], ["3.5", "1"])  # stays words

    def test_the_models_other_names(self):
        self.assertEqual(found("drive", paired=True), ["B-drive", "A-motor"])
        self.assertEqual(found("pump motor", paired=True)[-1], "B-drive")
        groups = search.parse("pump motor")
        self.assertTrue(search.names(groups, "pump motor"))
        self.assertFalse(search.names(groups, "pump"))  # it doesn't ask for every word the query has
        self.assertFalse(search.names(search.parse("motor"), "pump motor"))  # nor the query every word it has
        self.assertEqual(search.other_names(search.parse("like:A-pump"), {"items": [["a", "b"]]}), [])

    def test_counterparts_names_and_like(self):
        self.assertEqual(found("output", paired=True), ["B-pump", "A-pump"])
        index = search.Index()
        claims, findings = search.report_items(search_report(), index)
        _, names, _ = search.search(index, search.parse("output"), claims, findings)
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
                _, names, others = search.search(index, search.parse(q), claims, findings)
                self.assertEqual([f'"{name}"' for name, _ in names] + [f'"{name}"' for name in others], result["also"])

class Values(unittest.TestCase):
    """A claim's value and a search's units (values.py): what milestone 3 compares."""
    def test_numbers_ranges_bounds_and_units_written_in_the_value(self):
        from semantic_pdf_diff.values import value_range
        for value, unit, expected in [("75", "kW", (75.0, 75.0, "kW")), ("1,000", "mm", (1000.0, 1000.0, "mm")),
                                      ("7.85E3", "kg/m^3", (7850.0, 7850.0, "kg/m^3")),
                                      ("50–60", "L/s", (50.0, 60.0, "L/s")), ("1.2 to 3", "m", (1.2, 3.0, "m")),
                                      ("≤ 39", "dBA", (None, 39.0, "dBA")), ("> 5", "", (5.0, None, "")),
                                      ("approximately 5", "m", (5.0, 5.0, "m")), ("75 kW", "", (75.0, 75.0, "kW")),
                                      ("-5", "°C", (-5.0, -5.0, "°C")), ("3.5:1", "", None), ("open", "", None)]:
            with self.subTest(value=value):
                self.assertEqual(value_range(value, unit), expected)

    def test_units_in_their_kinds_base_and_spellings_that_mean_two_things(self):
        from semantic_pdf_diff.values import search_unit
        self.assertEqual(search_unit("kW"), ("power", 1000.0))
        self.assertEqual(search_unit("kw"), ("power", 1000.0))
        self.assertIsNone(search_unit("mw"))  # mW or MW
        self.assertEqual(search_unit("g"), ("mass", 0.001))  # the product's gram, not the scorer's g-force
        self.assertAlmostEqual(search_unit("ft")[1], 0.3048, places=4)  # the scorer's inches, in metres
        self.assertAlmostEqual(search_unit("psi")[1], 6894.76, places=1)
        self.assertEqual(search_unit("m²"), search_unit("m2"))
        # the search's own units, spelled as documents spell them
        for spelling in ("N.m^2", "N•m2", "N*m^2"):
            self.assertEqual(search_unit(spelling), ("bending stiffness", 1.0))
        self.assertEqual(search_unit("MN-m"), ("moment", 1e6))
        self.assertEqual(search_unit("kN·m"), ("moment", 1e3))
        self.assertEqual(search_unit("º"), search_unit("°"))  # an ordinal for a degree
        self.assertAlmostEqual(search_unit("RPM")[1], 0.10472, places=5)  # rad/s, folded
        self.assertAlmostEqual(search_unit("kips")[1], 4448.22, places=1)  # the scorer's, in newtons

class OtherNames(unittest.TestCase):
    """The model's request for the documents' other names (synonyms.py), and its answers kept."""
    def claims(self):
        return [{"entity": "pump", "attribute": "rated output", "side": "A"},
                {"entity": "pump", "attribute": "rated output", "side": "A"},
                {"entity": "feed pump", "attribute": "nominal power", "side": "B"}]

    def test_the_request_lists_each_sides_names_with_their_counts(self):
        from semantic_pdf_diff import synonyms
        prompt = synonyms.prompt(self.claims(), ["A", "B"])
        self.assertIn("ITEMS:\nA: pump (2)\nB: feed pump (1)\nPROPERTIES:\nA: rated output (2)\nB: nominal power (1)",
                      prompt)

    def test_answers_keep_names_as_listed_and_groups_sharing_one_are_joined(self):
        from semantic_pdf_diff import synonyms
        from semantic_pdf_diff.schema import OtherNames
        asked = []

        def submit(prompt, i, finish):
            asked.append(i)
            finish(OtherNames(items=[["Pump", "feed  pump"], ["pump", "impeller"]],
                              properties=[["rated output", "NOMINAL POWER"], ["rated output"]]), None)
        kept = synonyms.named(self.claims(), {}, ["A", "B"], submit, lambda: None)
        self.assertEqual(kept, {"items": [["pump", "feed pump"]], "properties": [["rated output", "nominal power"]],
                                "requests": 1, "failed": 0})  # "impeller" isn't listed; a lone name isn't a group
        self.assertEqual(synonyms.joined([["a", "b"], ["c", "d"], ["b", "c"]]), [["a", "b", "c", "d"]])

    def test_a_failed_request_leaves_its_names_ungrouped(self):
        from semantic_pdf_diff import synonyms
        from semantic_pdf_diff.llm import ModelFailure
        kept = synonyms.named(self.claims(), {}, ["A", "B"], lambda p, i, finish: finish(None, ModelFailure("x")),
                              lambda: None)
        self.assertEqual(kept, {"items": [], "properties": [], "requests": 1, "failed": 1})

    def test_many_names_are_asked_a_topic_at_a_time(self):
        from semantic_pdf_diff import synonyms
        claims = [{"id": i, "entity": f"item {i}", "attribute": f"property {i}", "side": "AB"[i % 2]}
                  for i in range(300)]
        parts = synonyms.chunks(claims, {i: i % 3 for i in range(290)})
        self.assertEqual([len(p) for p in parts], [10, 97, 97, 96])  # those in no topic first, then each topic's

    def test_the_pipeline_asks_when_the_lever_is_on(self):
        from semantic_pdf_diff.pipeline import other_names
        from semantic_pdf_diff.schema import OtherNames

        class Model:
            asked = []

            def ask(self, prompt, schema, images=(), key=None):
                self.asked.append((schema, key))
                return OtherNames(items=[["pump motor", "drive"]])
        model = Model()
        kept = other_names(search_report(), model, "proposals", "label")
        self.assertEqual(kept["items"], [["pump motor", "drive"]])
        self.assertEqual(model.asked, [(OtherNames, ("names", "proposals", "label", "0"))])

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

    def test_values_across_units_and_a_unit_it_doesnt_know(self):
        code, out, _ = run("search", ">70", "kW", "--store", self.store)
        self.assertTrue(out.startswith("3 claims found"))
        self.assertIn("drive — shaft power = 0.08 MW", out)
        code, out, _ = run("search", ">1mw", "--store", self.store)
        self.assertEqual(out.splitlines()[0], "0 claims found (units the search doesn't know: mw)")

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
