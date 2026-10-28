"""A store's own settings and `semantic-pdf-diff config` (configuration.py, settinghelp.py; decision 0032).
The owner, 2026-10-20: "User layer is fine. Snake case or kebab case is fine,
if consistent. Definitely will need navigation of settings and adequate help for each. Redo instead of refusing, yes."
"""
import stubs  # a clean environment
import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from semantic_pdf_diff import cli, configuration
from semantic_pdf_diff.pipeline import settings_from
from semantic_pdf_diff.settinghelp import GROUPS, HELP
from semantic_pdf_diff.settings import Settings, user_settings
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
        self.assertIn("environment variables (neither the user's nor the store's):", shown)
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

    def test_the_users_settings_lie_under_every_stores(self):
        from semantic_pdf_diff.settings import save_user_settings, user_path, user_settings
        user_path().unlink()  # (the tests' own, stubs.USER, put back after)
        self.addCleanup(save_user_settings, stubs.USER)
        code, out, _ = run("config", "set", "--user", "concurrency", "32", "--store", self.store)
        self.assertEqual((code, out), (0, "concurrency = 32; the next run redoes: nothing (it changes how requests "
                                          "travel, never what is asked)\n"))
        self.assertFalse(self.store.exists())  # the user's: no store made
        run("config", "set", "--user", "top_k", "6")
        run("config", "set", "top_k", "8", "--store", self.store)
        self.assertEqual(user_settings(), {"concurrency": 32, "top_k": 6})
        _, shown, _ = run("config", "show", "--store", self.store)
        self.assertIn("concurrency       32 (user)", shown)
        self.assertIn("top_k             8 (store)", shown)
        self.assertEqual(json.loads(run("config", "export", "--user")[1]),
                         {"format": 1, "settings": {"concurrency": 32, "top_k": 6}})
        code, out, _ = run("config", "unset", "--user", "top_k", "--store", self.store)
        self.assertEqual(out, "top_k = 8 (the store's)\n")  # the store's still applies: nothing redone
        run("config", "unset", "--user", "concurrency")
        self.assertEqual(user_settings(), {})

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

class EndpointUrl(unittest.TestCase):
    """The endpoint's URL is the environment's and the user's, never a store's (docs/plans/endpoint-setup-2026-10-28.md,
    milestone 1; the owner, 2026-10-28: "Endpoint URL in environment and user settings is sufficient. I'd hate to
    complicate things too much on the user's end.")."""
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = Path(temp.name) / "store"

    def test_a_store_refuses_it_and_the_user_keeps_it(self):
        code, _, err = run("config", "set", "base_url", "https://store.example/v1", "--store", self.store)
        self.assertEqual(code, 1)
        self.assertIn("base_url is the user's, never a store's", err)
        file = self.store.parent / "settings.json"
        file.write_text(json.dumps({"format": 1, "settings": {"base_url": "https://store.example/v1", "top_k": 6}}))
        self.assertEqual(run("config", "import", file, "--store", self.store)[0], 1)
        self.assertEqual(Store.settings_of(self.store), {})
        with stubs.user_settings(stubs.USER):
            code, out, _ = run("config", "set", "--user", "base_url", "https://user.example/v1")
            self.assertEqual(code, 0)
            self.assertEqual(user_settings()["base_url"], "https://user.example/v1")
            with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://env.example/v1"}):
                _, shown, _ = run("config", "help", "base_url", "--store", self.store)
            self.assertIn("now: https://env.example/v1 (environment)", shown)

    def test_the_variable_then_the_users_a_flag_over_both_and_a_stores_left_out(self):
        with Store(self.store) as kept:  # kept before 2026-10-28, when a store could
            kept.save_own_settings({"base_url": "https://store.example/v1", "top_k": 6})
        with self.assertLogs("semantic_pdf_diff", "WARNING") as warned:
            own = Store.settings_of(self.store)
        self.assertEqual(own, {"top_k": 6})
        self.assertIn("config unset base_url", warned.output[0])
        parser = cli.compare_parser()
        with stubs.user_settings({**stubs.USER, "base_url": "https://user.example/v1"}):
            layer = {**user_settings(), **own}  # as a run reads them (cli.compare_command)
            def url(*flags):
                return cli.load_settings(parser.parse_args(["a", "b", *flags]), layer).base_url
            with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://env.example/v1"}):
                self.assertEqual(url(), "https://env.example/v1")
                self.assertEqual(url("--base-url", "https://flag.example/v1"), "https://flag.example/v1")
            self.assertEqual(url(), "https://user.example/v1")
            self.assertEqual(cli.load_settings(parser.parse_args(["a", "b"]), layer).top_k, 6)

    def test_a_config_file_gives_it_for_the_run_as_the_flag_does(self):
        file = self.store.parent / "c.json"
        file.write_text(json.dumps({"base_url": "https://file.example/v1"}))
        with patch.dict(os.environ, {"OPENAI_BASE_URL": "https://env.example/v1"}):
            self.assertEqual(settings_from(file).base_url, "https://file.example/v1")

if __name__ == "__main__":
    unittest.main()
