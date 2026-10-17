"""Named variants of the controlled corpus (scripts/controlled.py run --variant; recording tooling, milestone 4): a
lever's arm was a hand-written script, a fixture copy and a runs folder in scratch; it is now a settings overlay with a
name, recorded into the archive and judged by scripts/paired.py by that name."""
import stubs  # noqa: F401 (a clean environment)
from stubs import needs_lab
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def script(name):
    needs_lab()
    spec = importlib.util.spec_from_file_location(f"{name}_script", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Variants(unittest.TestCase):
    def setUp(self):
        self.controlled = script("controlled")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        patch = mock.patch.object(self.controlled, "VARIANTS", self.root / "variants")
        patch.start()
        self.addCleanup(patch.stop)

    def define(self, data, name="arm.json"):
        path = self.root / name
        path.write_text(json.dumps(data))
        return path

    def test_a_variant_is_its_overlay_on_the_corpus_settings_written_beside_its_runs(self):
        name, config, only = self.controlled.variant(self.define(
            {"settings": {"hedge_rule": False, "extract_rules": ["Be brief."]}, "only": ["*.pdf", "views*"]}))
        self.assertEqual((name, only), ("arm", ("*.pdf", "views*")))
        settings = json.loads(config.read_text())
        corpus = json.loads(self.controlled.settings_file().read_text())
        self.assertEqual(settings, {**corpus, "hedge_rule": False, "extract_rules": ["Be brief."]})
        self.assertEqual(config.parent, self.root / "variants" / "arm")
        self.assertTrue((config.parent / "variant.json").exists())
        self.assertEqual(self.controlled.variant(self.define({"name": "null", "settings": {}}))[0], "null")

    def test_a_misspelt_key_is_refused(self):
        with self.assertRaises(SystemExit):
            self.controlled.variant(self.define({"setting": {"hedge_rule": False}}))

    def test_only_the_documents_named_are_read(self):
        seen = []
        def attempt(f, a, b, folder, settings, options):
            seen.append((a.name, options.mode))
            return 0
        with mock.patch("semantic_pdf_diff.pipeline.attempt", attempt):
            self.controlled.run(True, "m", 0, False, fixture=self.root / "f.sqlite", runs=self.root / "runs",
                                pair_runs=self.root / "pairs", only=("views-poll*",))
        self.assertTrue(seen)
        self.assertTrue(all(name.startswith("views-poll") for name, _ in seen))
        self.assertEqual({mode for _, mode in seen}, {"proposals", "revisions"})

    def test_paired_names_a_variant_by_its_runs(self):
        paired = script("paired")
        runs = self.root / "benchmarks/runs/controlled/variants/arm/replay"
        runs.mkdir(parents=True)
        with mock.patch("semantic_pdf_diff_lab.bench.recording.main_checkout", lambda root: self.root):
            self.assertEqual(paired.folder(Path("arm")), runs)
            with self.assertRaises(SystemExit):
                paired.folder(Path("nothing"))


    def test_a_worktree_spends_into_and_reads_from_the_main_checkout(self):
        import os
        import subprocess
        from semantic_pdf_diff_lab.bench import recording
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        main, tree = self.root / "main", self.root / "tree"
        main.mkdir()
        git = lambda *args, cwd=main: subprocess.run(["git", *args], cwd=cwd, env=env, check=True,  # noqa: E731
                                                     capture_output=True)
        git("init", "-q")
        git("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "start")
        git("worktree", "add", "-q", "--detach", str(tree))
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(recording.main_checkout(tree).resolve(), main.resolve())
            self.assertEqual(recording.main_checkout(main).resolve(), main.resolve())
            self.assertEqual(recording.ledger(tree).resolve(), (main / recording.LEDGER).resolve())
            outside = self.root / "outside"
            outside.mkdir()
            self.assertEqual(recording.main_checkout(outside), outside)

if __name__ == "__main__":
    unittest.main()
