"""The linter's rules (pyproject.toml, [tool.ruff]) hold over the tree, so its findings are always new ones. Ruff is
run as installed, or through uv; without either the test is skipped."""
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def _ruff():
    if shutil.which("ruff"):
        return ["ruff"]
    if shutil.which("uvx"):
        return ["uvx", "ruff"]
    return None

class Lint(unittest.TestCase):
    def test_ruff_finds_nothing(self):
        command = _ruff()
        if command is None:
            self.skipTest("neither ruff nor uvx is installed")
        done = subprocess.run([*command, "check", "--output-format", "concise", "."], cwd=ROOT, capture_output=True,
                              text=True, timeout=300)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

if __name__ == "__main__":
    unittest.main()
