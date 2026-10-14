"""The command line's help: everything a newcomer on another machine has without the docs (the owner, 2026-10-14:
"I don't feel the `pdf-semantic-diff --help` is providing the details I need to actually use it")."""
import stubs  # noqa: F401 (a clean environment)
import argparse
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from semantic_pdf_diff import cli

COMMANDS = ("compare", "source", "show", "report", "gc", "settings", "fixtures")

def parsers():
    """Every parser and subparser the command line builds: [(prog, parser)]."""
    tops = [cli.shortcut_parser(), cli.compare_parser(), cli.source_parser(), cli.fixtures_parser(),
            cli.settings_parser(), *(cli.store_parser(c) for c in ("show", "gc", "report"))]
    out = []
    def walk(parser):
        out.append((parser.prog, parser))
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for sub in action.choices.values():
                    walk(sub)
    for parser in tops:
        walk(parser)
    return out

def run(argv, env=None):
    """(exit code, standard output) of the command line."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()), \
            mock.patch.dict(os.environ, env or {}):
        try:
            code = cli.main(argv)
        except SystemExit as e:  # argparse's --help
            code = e.code
    return code, out.getvalue()

class Help(unittest.TestCase):
    def test_every_argument_says_what_it_is(self):
        for prog, parser in parsers():
            for action in parser._actions:
                if isinstance(action, (argparse._HelpAction, argparse._VersionAction, argparse._SubParsersAction)):
                    continue
                with self.subTest(prog=prog, argument=action.dest):
                    self.assertTrue(action.help, f"{prog} {action.option_strings or action.dest} has no help")
            with self.subTest(prog=prog):
                self.assertTrue(parser.description, f"{prog} has no description")

    def test_the_top_level_help_names_every_command_and_how_to_start(self):
        code, text = run(["--help"])
        self.assertEqual(code, 0)
        for name in COMMANDS:
            self.assertRegex(text, rf"\n  {name} +\S", name)
        for needed in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", "source add", "Exit codes"):
            self.assertIn(needed, text)
        self.assertEqual(run([]), (1, text + "\n"))  # no arguments: the same, as an error

    def test_help_command_is_the_commands_own_help(self):
        self.assertEqual(run(["help", "source", "add"]), run(["source", "add", "--help"]))
        code, text = run(["help", "source", "add"])
        self.assertEqual(code, 0)
        for option in ("--store", "--path", "--meta", "Examples:"):
            self.assertIn(option, text)

class SettingsCommand(unittest.TestCase):
    def test_the_settings_a_run_would_use_and_the_changed_ones_alone(self):
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / "settings.json"
            config.write_text(json.dumps({"concurrency": 6}))
            env = {"OPENAI_MODEL": "provider/vision", "OPENAI_API_KEY": "sk-secret",
                   "OPENAI_BASE_URL": "https://user:pass@provider.example/v1"}
            code, text = run(["settings", "--config", str(config)], env)
            self.assertEqual(code, 0)
            shown = json.loads(text)
            self.assertEqual(list(shown)[:2], ["model", "base_url"])
            self.assertEqual((shown["model"], shown["concurrency"]), ("provider/vision", 6))
            self.assertIn("levers", shown)
            self.assertNotIn("sk-secret", text)
            self.assertNotIn("pass", shown["base_url"])
            _, changed = run(["settings", "--config", str(config), "--changed"], {"OPENAI_MODEL": "provider/vision"})
            self.assertEqual(json.loads(changed), {"model": "provider/vision", "concurrency": 6})

if __name__ == "__main__":
    unittest.main()
