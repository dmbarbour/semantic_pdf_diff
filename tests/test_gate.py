"""The commit gate (scripts/gate.py; docs/plans/recording-tooling-2026-10-17.md, milestone 1): on 2026-10-17 a commit
went in after a test command that named a module that doesn't exist. A commit now needs a recorded pass of the tree
it commits, or the quick suite run on that tree."""
import stubs  # noqa: F401 (a clean environment)
import importlib.util
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("gate", ROOT / "scripts/gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

# a staged tree's own "suite": passes when its checked-out verdict file says so; like an older suite, it takes no
# arguments (the gate's first run passed a flag the staged tree's suite didn't know)
SUITE = ("import sys; from pathlib import Path\n"
         "sys.exit(0 if Path('verdict').read_text() == 'pass' and len(sys.argv) == 1 else 1)\n")


class Gate(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.patch = mock.patch.dict(os.environ, env, clear=True)
        self.patch.start()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            gate.git(*args, cwd=self.repo)
        (self.repo / ".gitignore").write_text("ignored.txt\n")
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts/run_tests.py").write_text(SUITE)
        (self.repo / "verdict").write_text("pass")
        gate.git("add", "-A", cwd=self.repo)
        gate.git("commit", "-q", "-m", "start", cwd=self.repo)

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_the_working_tree_is_hashed_as_it_would_be_committed(self):
        clean = gate.working_tree(self.repo)
        self.assertEqual(clean, gate.staged_tree(self.repo))
        (self.repo / "ignored.txt").write_text("x")
        self.assertEqual(gate.working_tree(self.repo), clean)  # ignored files don't count
        (self.repo / "new.txt").write_text("x")
        changed = gate.working_tree(self.repo)
        self.assertNotEqual(changed, clean)  # untracked ones do
        self.assertEqual(gate.staged_tree(self.repo), clean)  # and the real index is left alone
        gate.git("add", "new.txt", cwd=self.repo)
        self.assertEqual(gate.staged_tree(self.repo), changed)

    def test_a_pass_is_recorded_for_its_tree_only(self):
        tree = gate.working_tree(self.repo)
        self.assertIsNone(gate.passed(tree, self.repo))
        gate.record(tree, "full", 3, self.repo)
        self.assertEqual(gate.passed(tree, self.repo)["kind"], "full")
        self.assertIsNone(gate.passed("0" * 40, self.repo))

    def test_the_hook_lets_a_recorded_pass_through_without_running_tests(self):
        gate.record(gate.staged_tree(self.repo), "full", 3, self.repo)
        with mock.patch.object(gate, "test_staged", side_effect=AssertionError("ran tests")):
            self.assertEqual(gate.hook(self.repo, out=io.StringIO()), 0)

    def test_the_hook_runs_the_staged_trees_own_tests_and_blocks_on_failure(self):
        out = io.StringIO()
        (self.repo / "verdict").write_text("fail")  # the working tree fails; the staged tree is the commit
        self.assertEqual(gate.hook(self.repo, out=out), 0, out.getvalue())
        self.assertIsNotNone(gate.passed(gate.staged_tree(self.repo), self.repo))
        gate.git("add", "verdict", cwd=self.repo)
        self.assertEqual(gate.hook(self.repo, out=io.StringIO()), 1)
        self.assertIsNone(gate.passed(gate.staged_tree(self.repo), self.repo))

    def test_the_installed_hook_blocks_a_commit(self):
        gate.git("config", "core.hooksPath", str(ROOT / "scripts/hooks"), cwd=self.repo)
        (self.repo / "scripts/gate.py").write_text((ROOT / "scripts/gate.py").read_text())
        (self.repo / "verdict").write_text("fail")
        gate.git("add", "-A", cwd=self.repo)
        done = subprocess.run(["git", "commit", "-q", "-m", "bad"], cwd=self.repo, capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("commit blocked", done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
