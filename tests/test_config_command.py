"""A store's own settings and `pdf-semantic-diff config` (configuration.py, settinghelp.py; docs/plans/configuration-
in-the-store-2026-10-20.md, milestone 1). The owner, 2026-10-20: "User layer is fine. Snake case or kebab case is fine,
if consistent. Definitely will need navigation of settings and adequate help for each. Redo instead of refusing, yes."
"""
import stubs  # noqa: F401 (a clean environment)
import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import cli, configuration
from semantic_pdf_diff.settinghelp import GROUPS, HELP
from semantic_pdf_diff.settings import Settings
from semantic_pdf_diff.store import Store

def run(*argv):
    """(exit code, standard output, standard error) of the command line."""
    with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
        code = cli.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()

class Help(unittest.TestCase):
    def test_every_setting_has_its_help_in_a_group(self):
        self.assertEqual(set(HELP), set(Settings.model_fields) | set(configuration.RUN_OPTIONS))
        for name, h in HELP.items():
            self.assertIn(h.group, GROUPS, name)
            self.assertTrue(h.about and not h.about.endswith("."), name)
        for group in ("endpoint", "budget", "reading", "comparing", "report"):  # each group has basic settings
            self.assertTrue(any(h.basic and h.group == group for h in HELP.values()), group)

    def test_a_settings_help_says_what_changing_it_redoes(self):
        lines = configuration.help_lines("visual_text_layer", [])
        self.assertIn("  changing it redoes: documents read again (figure, overview, tile, vision)", lines)
        self.assertIn("  group: levers; lever: visual_text_layer", lines)
        self.assertIn("nothing", configuration.redoes("max_cost"))
        self.assertEqual(configuration.redoes("report_budget"), "the report only")

class Values(unittest.TestCase):
    def test_text_is_read_by_the_settings_type(self):
        parse = configuration.parse
        self.assertEqual([parse("max_cost", "2"), parse("vision", "off"), parse("split", "on"),
                          parse("report_budget", "40MB"), parse("aliases", '{"CHW": "chilled water"}'),
                          parse("table_rules", "none"), parse("rerank_threshold", "5"), parse("mode", "revisions")],
                         [2.0, False, True, 40_000_000, {"CHW": "chilled water"}, None, 5, "revisions"])

    def test_a_wrong_name_or_value_says_what_was_meant(self):
        for name, text, said in [("max-cost", "2", "did you mean max_cost?"),
                                 ("concurency", "4", "did you mean concurrency?"),
                                 ("rerank_threshold", "20", "less than or equal to 10"),
                                 ("mode", "both", "mode is proposals or revisions"),
                                 ("aliases", "CHW", "aliases is JSON")]:
            with self.assertRaises(ValueError) as caught:
                configuration.parse(name, text)
            self.assertIn(said, str(caught.exception))

class Command(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Path(temp.name) / "store"

    def test_set_makes_a_store_and_show_marks_its_own_settings(self):
        self.assertFalse(self.store.exists())
        code, out, _ = run("config", "set", "max_pairs", "5000", "--store", self.store)
        self.assertEqual(code, 0)
        self.assertEqual(out, "max_pairs = 5000; the next run redoes: the comparison judged again\n")
        self.assertEqual(Store.settings_of(self.store), {"max_pairs": 5000})
        _, shown, _ = run("config", "show", "--store", self.store)
        self.assertIn("max_pairs         5000 (store)", shown)
        self.assertIn("environment variables (not the store's):", shown)
        _, comparing, _ = run("config", "show", "comparing", "--store", self.store)
        self.assertIn("min_score", comparing)  # not a basic one: shown in its group
        self.assertNotIn("max_cost", comparing)
        _, every, _ = run("config", "show", "--all", "--store", self.store)
        self.assertTrue(all(name in every for name in HELP))
        _, found, _ = run("config", "find", "holder", "column", "--store", self.store)
        self.assertIn("table_holders", found)
        self.assertNotIn("max_pairs", found)
        code, out, _ = run("config", "unset", "max_pairs", "--store", self.store)
        self.assertEqual((code, out), (0, "max_pairs = 1000 (the default); the next run redoes: the comparison "
                                          "judged again\n"))
        self.assertEqual(Store.settings_of(self.store), {})

    def test_a_wrong_setting_changes_nothing(self):
        run("config", "set", "max_cost", "2", "--store", self.store)
        code, _, err = run("config", "set", "rerank-threshold", "5", "--store", self.store)
        self.assertEqual(code, 1)
        self.assertIn("did you mean rerank_threshold?", err)
        self.assertEqual(Store.settings_of(self.store), {"max_cost": 2.0})

    def test_export_and_import_move_a_stores_settings_all_or_nothing(self):
        run("config", "set", "max_cost", "2", "--store", self.store)
        run("config", "set", "mode", "revisions", "--store", self.store)
        code, out, _ = run("config", "export", "--store", self.store)
        self.assertEqual(json.loads(out), {"format": 1, "settings": {"max_cost": 2.0, "mode": "revisions"}})
        other = self.store.parent / "other"
        file = self.store.parent / "settings.json"
        file.write_text(out)
        self.assertEqual(run("config", "import", file, "--store", other)[0], 0)
        self.assertEqual(Store.settings_of(other), Store.settings_of(self.store))
        file.write_text(json.dumps({"format": 1, "settings": {"max_cost": None, "top_k": 6, "concurency": 4,
                                                              "vision": "maybe"}}))
        code, _, err = run("config", "import", file, "--store", other)
        self.assertEqual(code, 1)
        self.assertIn("no setting 'concurency'", err)
        self.assertIn("vision", err)
        self.assertIn("nothing was changed", err)
        self.assertEqual(Store.settings_of(other), {"max_cost": 2.0, "mode": "revisions"})
        file.write_text(json.dumps({"format": 1, "settings": {"max_cost": None, "top_k": 6}}))  # null unsets
        run("config", "import", file, "--store", other)
        self.assertEqual(Store.settings_of(other), {"mode": "revisions", "top_k": 6})

class Layers(unittest.TestCase):
    def test_a_stores_settings_lie_under_a_config_file_and_the_flags(self):
        parser = argparse.ArgumentParser()
        cli.add_run_options(parser)
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / "c.json"
            config.write_text(json.dumps({"max_pairs": 2000}))
            layer = {"max_pairs": 5000, "top_k": 6, "mode": "revisions"}
            stored = cli.load_settings(parser.parse_args([]), layer)
            filed = cli.load_settings(parser.parse_args(["--config", str(config)]), layer)
            flagged = cli.load_settings(parser.parse_args(["--config", str(config), "--max-pairs", "10"]), layer)
        self.assertEqual((stored.max_pairs, stored.top_k), (5000, 6))
        self.assertEqual((filed.max_pairs, filed.top_k), (2000, 6))
        self.assertEqual(flagged.max_pairs, 10)

    def test_the_mode_and_the_reports_settings_come_from_the_store_unless_a_flag_says(self):
        from semantic_pdf_diff.pipeline import RunOptions
        parser = cli.compare_parser()
        layer = {"mode": "revisions", "report_budget": 1_000_000, "split": True}
        kept = RunOptions.from_args(parser.parse_args(["a", "b"]), layer)
        self.assertEqual((kept.mode, kept.report_budget, kept.split), ("revisions", 1_000_000, True))
        flagged = RunOptions.from_args(parser.parse_args(["a", "b", "--mode", "proposals", "--report-budget", "5MB",
                                                          "--no-split"]), layer)
        self.assertEqual((flagged.mode, flagged.report_budget, flagged.split), ("proposals", 5_000_000, False))
        plain = RunOptions.from_args(parser.parse_args(["a", "b"]))
        self.assertEqual((plain.mode, plain.report_budget, plain.split), ("proposals", 20_000_000, False))

if __name__ == "__main__":
    unittest.main()
