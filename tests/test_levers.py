"""Levers as mixins on a platform class (levers.py; architecture clean-up, milestone 3): composition from data,
hooks chained or chosen, assumptions on the final type, configurations and their binding."""
import stubs  # noqa: F401 (a clean environment)
from stubs import needs_lab
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from pydantic import ValidationError
from semantic_pdf_diff import levers as L
from semantic_pdf_diff.settings import Settings, settings_class
from semantic_pdf_diff.provenance import extraction_interpreter

ROOT = Path(__file__).resolve().parent.parent

class Lines(L.Composable):
    """A platform with one hook of each kind."""
    @L.chained
    def lines(self):
        return []

    @L.chosen
    def tiler(self):
        return "grid"

class Before(L.Lever):
    lever_name = "before"
    before: str = "B"
    def lines(self):
        return super().lines() + [self.before]

class After(L.Lever):
    lever_name = "after"
    def lines(self):
        return super().lines() + ["A"]

class Hiding(L.Lever):
    lever_name = "hiding"
    def lines(self):
        return ["only mine"]

class Bands(L.Lever):
    lever_name = "bands"
    def tiler(self):
        return "bands"

class Details(L.Lever):
    lever_name = "details"
    def tiler(self):
        return "details"

class Growing(L.Lever):
    lever_name = "growing"
    grow: bool = True
    def assumptions(self):
        if self.grow and self.tiler() != "grid":
            yield "growing tiles needs grid tiles"

class Composition(unittest.TestCase):
    def test_a_lists_order_is_its_parts_order(self):
        self.assertEqual(L.compose((Before, After), Lines)().lines(), ["B", "A"])
        self.assertEqual(L.compose((After, Before), Lines)().lines(), ["A", "B"])
        self.assertEqual(L.compose((Before, After), Lines)(before="b").lines(), ["b", "A"])  # its settings, validated
        with self.assertRaises(ValidationError):
            L.compose((After,), Lines)(before="b")  # a setting whose lever isn't there

    def test_a_chosen_hook_has_one_provider(self):
        self.assertEqual(L.compose((), Lines)().tiler(), "grid")  # the platform's default
        self.assertEqual(L.compose((Bands,), Lines)().tiler(), "bands")
        with self.assertRaisesRegex(ValueError, "tiler is chosen by one lever"):
            L.compose((Bands, Details), Lines)

    def test_a_chained_provider_calls_super(self):
        with self.assertRaisesRegex(ValueError, "hiding's lines doesn't call super"):
            L.compose((Before, Hiding), Lines)

    def test_assumptions_run_on_the_final_type(self):
        L.compose((Growing,), Lines)()
        with self.assertRaisesRegex(ValidationError, "growing tiles needs grid tiles"):
            L.compose((Growing, Bands), Lines)()  # each lever fine alone: the conflict is the final type's
        L.compose((Growing, Bands), Lines)(grow=False)

    def test_explain(self):
        text = L.compose((Before, After, Bands), Lines).explain()
        self.assertIn("hook lines (chained): platform -> before -> after", text)
        self.assertIn("hook tiler (chosen): bands", text)
        self.assertTrue(text.startswith("before (lever): before"))

class DefaultConfiguration(unittest.TestCase):
    def test_settings_compose_every_lever_in_the_canonical_order(self):
        self.assertEqual(Settings.levers, L.DEFAULT_LEVERS)
        self.assertLessEqual(set(L.lever_settings()), set(Settings.model_fields))
        self.assertIn("neighbours (context): context_before [shaping], context_after [shaping]", Settings.explain())

    def test_any_levers_in_any_order_compose(self):
        backwards = settings_class(tuple(reversed(L.DEFAULT_LEVERS)))
        self.assertEqual(backwards().context_before, 400)
        bare = settings_class(())()  # the platform alone
        self.assertEqual((bare.reconciles(), bare.instructions("built-in")), (False, "built-in"))
        with self.assertRaises(ValidationError):
            settings_class(())(context_before=10)  # its lever isn't there
        with self.assertRaisesRegex(ValueError, "unknown levers: knobs"):
            settings_class(("knobs",))
        with self.assertRaisesRegex(ValueError, "listed twice"):
            settings_class(L.DEFAULT_LEVERS + ("tiling",))

    def test_the_context_must_leave_room(self):
        with self.assertRaisesRegex(ValidationError, "Context must leave room"):
            Settings(context_tokens=4096, output_tokens=4000)

    def test_each_lever_says_what_leaving_it_out_means(self):
        for lever in L.LEVER_CLASSES:
            self.assertEqual(set(lever.off), set(lever.model_fields), lever.lever_name)
            lever.model_validate(lever.off)  # valid values

    def test_order_is_the_order_of_context_lines(self):
        from semantic_pdf_diff.context import CONTEXT_NOTE, Context
        import pymupdf
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((50, 60), "3.1 Pumps", fontsize=11)
        page.insert_text((50, 90), "The pumps listed below serve the loop.", fontsize=9)
        page.insert_text((50, 120), "Pump P-1 is rated 10 kW.", fontsize=9)
        page.insert_text((50, 150), "Pump P-2 is rated 12 kW.", fontsize=9)
        blocks = Context(doc, Settings()).page_blocks(1)
        segment = [b for b in blocks if "P-1" in b[1]]
        lines = lambda order: Context(doc, settings_class(order)()).for_text(1, segment, segment[0][1]).splitlines()
        canonical = lines(L.DEFAULT_LEVERS)
        self.assertEqual(canonical[0], CONTEXT_NOTE)
        self.assertEqual([x.split(":")[0] for x in canonical[1:]], ["Before", "After", "Within"])
        swapped = list(L.DEFAULT_LEVERS)
        i, j = swapped.index("neighbours"), swapped.index("stem_context")
        swapped[i], swapped[j] = swapped[j], swapped[i]
        self.assertEqual([x.split(":")[0] for x in lines(tuple(swapped))[1:]], ["Within", "Before", "After"])
        doc.close()

class Configurations(unittest.TestCase):
    def test_a_configuration_is_data_and_hashes_as_data(self):
        s = Settings()
        data = s.configuration()
        self.assertEqual(data["levers"], list(L.DEFAULT_LEVERS))
        self.assertNotIn("timeout", data)  # endpoint settings stay outside it
        self.assertEqual(Settings(timeout=5).digest(), s.digest())
        self.assertNotEqual(Settings(context_before=10).digest(), s.digest())
        backwards = settings_class(tuple(reversed(L.DEFAULT_LEVERS)))
        self.assertNotEqual(backwards().digest(), s.digest())  # order is part of it
        self.assertEqual(Settings.configured(**data).configuration(), data)  # and it round-trips
        self.assertEqual(Settings(**data).configuration(), data)
        with self.assertRaisesRegex(ValidationError, "build them with Settings.configured"):
            Settings(**backwards().configuration())

    def test_a_settings_file_names_its_levers(self):
        from semantic_pdf_diff.cli import load_settings
        order = list(reversed(L.DEFAULT_LEVERS))
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / "settings.json"
            config.write_text(json.dumps({"levers": order, "context_before": 10}))
            s = load_settings(Namespace(config=config))
        self.assertEqual((list(type(s).levers), s.context_before), (order, 10))

    def test_round_0_and_the_champion_are_named_configurations(self):
        round0 = json.loads((ROOT / "benchmarks/round0.json").read_text())
        champion = json.loads((ROOT / "benchmarks/champion.json").read_text())
        for data in (round0, champion):
            self.assertEqual(data["levers"], list(L.DEFAULT_LEVERS))  # pinned, so a new default order can't move them
        # The defaults are the champion: a default moved without a round fails here.
        self.assertEqual(Settings.configured(**champion).configuration(), Settings().configuration())
        self.assertEqual(Settings.configured(**round0).tiling, "grid")

class Rubrics(unittest.TestCase):
    """Judges' rubrics on the same model (rubrics.py; milestone 5): each version an ordered list of clauses. The
    versions' bytes are pinned by tests/golden/pairwise-*.txt (test_judge_prompts)."""
    def test_each_version_composes_from_its_clauses(self):
        needs_lab()
        from semantic_pdf_diff_lab.eval import rubrics as R
        v6 = R.rubric("v6")
        self.assertEqual((v6.tagged(), v6.numbered(), v6.whole()), (True, True, True))
        self.assertEqual((R.rubric("v2").numbered(), R.rubric("v1").tagged()), (False, False))
        self.assertIn("hook template (chained): platform -> tags -> claim_marks -> sections -> context -> whole",
                      type(v6).explain())

    def test_a_clause_out_of_order_or_alone_is_refused(self):
        needs_lab()
        from semantic_pdf_diff_lab.eval import rubrics as R
        for clauses, problem in (((R.Tags, R.Sections, R.Whole, R.Context), "whole needs claim_marks before it"),
                                 ((R.Context, R.Sections), "context needs sections before it"),
                                 ((R.Tags, R.HeadingNames), "heading_names needs sections before it"),
                                 ((R.ClaimMarks,), "claim_marks needs tags before it")):
            with self.subTest(clauses=[c.lever_name for c in clauses]):
                with self.assertRaisesRegex(ValidationError, problem):
                    L.compose(clauses, R.Rubric)()

    def test_a_change_that_misses_its_mark_says_so(self):
        needs_lab()
        from semantic_pdf_diff_lab.eval import rubrics as R
        with self.assertRaisesRegex(ValueError, "doesn't hold"):
            R._swap("PAGE {page}", "SET A:", "SET A ({a_note}):")

class Marks(unittest.TestCase):
    def test_a_detail_noted_without_a_sheet_label_is_found(self):
        from semantic_pdf_diff.settings import lever_notes  # the review: "Drawing sheet. Detail B4" was missed
        self.assertIn("sheet_details", lever_notes("SOURCE DATA:\nDrawing sheet. Detail B4: FOOTING PLAN"))
        self.assertIn("sheet_details", lever_notes("SOURCE DATA:\nSheet S-522 Deck Details. Detail C1: ELEVATION"))
        self.assertNotIn("sheet_details", lever_notes("SOURCE DATA:\nSee the detail on sheet S-522."))

class Comparison(unittest.TestCase):
    def test_retrieval_is_the_platforms_and_images_are_a_lever(self):
        from semantic_pdf_diff.compare import candidates
        from semantic_pdf_diff.schema import Evidence, PdfLocator
        ev = lambda i, v: Evidence(id=i, content="sha256:" + "a" * 64 + ".pdf", entity="pump", attribute="power",
                                   value=v, unit="kW", kind="table", quote=v, confidence=0.9, image="assets/x.png",
                                   locator=PdfLocator(page=1, bbox=(0, 0, 1, 1), region="table", task="table:0"))
        a, b = [ev("A-1", "10")], [ev("B-1", "12")]
        self.assertEqual(Settings().candidates(a, b), candidates(a, b, Settings()))
        self.assertEqual(Settings().comparison_images(a[0], Path("out")), [Path("out/assets/x.png")])
        self.assertEqual(Settings(verify_visuals=False).comparison_images(a[0], Path("out")), [])
        without = settings_class(tuple(n for n in L.DEFAULT_LEVERS if n != "verify_visuals"))()
        self.assertEqual(without.comparison_images(a[0], Path("out")), [])

class Binding(unittest.TestCase):
    """Levers were bound only when they differed from the defaults of the day, so a moved default went
    unnoticed and old evidence was served as current (code review 2026-10-01, item 4)."""
    def test_every_resolved_setting_and_the_order_are_bound(self):
        from semantic_pdf_diff.store import affected_regions, interpreter_differences
        bound = extraction_interpreter(Settings()).settings
        self.assertEqual(bound["context_before"], 400)  # at its default, still bound
        # extraction's: matching's merge and comparison's levers aren't
        self.assertEqual(bound["levers"], [n for n in L.DEFAULT_LEVERS if n not in ("reconcile", "align", "verify_visuals", "explain_differences")])
        backwards = extraction_interpreter(settings_class(tuple(reversed(L.DEFAULT_LEVERS)))()).model_dump()
        differences = interpreter_differences(extraction_interpreter(Settings()).model_dump(), backwards)
        self.assertEqual(set(differences), {"settings.levers"})
        self.assertEqual(affected_regions(differences), L.ALL_REGIONS)  # a new order can move any prompt line
        moved = extraction_interpreter(Settings(context_before=300)).model_dump()
        differences = interpreter_differences(extraction_interpreter(Settings()).model_dump(), moved)
        self.assertEqual(affected_regions(differences), L.TEXTUAL)

if __name__ == "__main__":
    unittest.main()
