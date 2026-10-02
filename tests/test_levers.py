"""Levers as mixins on a platform class (levers.py; architecture clean-up, milestone 3): composition from data,
hooks chained or chosen, assumptions on the final type, configurations and their binding."""
import stubs  # noqa: F401 (a clean environment)
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from pydantic import ValidationError
from semantic_pdf_diff import levers as L
from semantic_pdf_diff.models import Settings, settings_class
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

    def test_any_order_composes_but_every_lever_is_needed_until_behaviour_moves(self):
        backwards = settings_class(tuple(reversed(L.DEFAULT_LEVERS)))
        self.assertEqual(backwards().context_before, 400)
        with self.assertRaisesRegex(ValidationError, "levers the pipeline still reads directly are missing: extract_prompt"):
            settings_class(L.DEFAULT_LEVERS[1:])()
        with self.assertRaisesRegex(ValueError, "unknown levers: knobs"):
            settings_class(("knobs",))
        with self.assertRaisesRegex(ValueError, "listed twice"):
            settings_class(L.DEFAULT_LEVERS + ("tiling",))

    def test_the_context_must_leave_room(self):
        with self.assertRaisesRegex(ValidationError, "Context must leave room"):
            Settings(context_tokens=4096, output_tokens=4000)

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

class Binding(unittest.TestCase):
    """Levers were bound only when they differed from the defaults of the day, so a moved default went
    unnoticed and old evidence was served as current (code review 2026-10-01, item 4)."""
    def test_every_resolved_setting_and_the_order_are_bound(self):
        from semantic_pdf_diff.store import affected_regions, interpreter_differences
        bound = extraction_interpreter(Settings()).settings
        self.assertEqual(bound["context_before"], 400)  # at its default, still bound
        self.assertEqual(bound["levers"], list(L.DEFAULT_LEVERS))
        backwards = extraction_interpreter(settings_class(tuple(reversed(L.DEFAULT_LEVERS)))()).model_dump()
        differences = interpreter_differences(extraction_interpreter(Settings()).model_dump(), backwards)
        self.assertEqual(set(differences), {"settings.levers"})
        self.assertEqual(affected_regions(differences), L.ALL_REGIONS)  # a new order can move any prompt line
        moved = extraction_interpreter(Settings(context_before=300)).model_dump()
        differences = interpreter_differences(extraction_interpreter(Settings()).model_dump(), moved)
        self.assertEqual(affected_regions(differences), L.TEXTUAL)

if __name__ == "__main__":
    unittest.main()
