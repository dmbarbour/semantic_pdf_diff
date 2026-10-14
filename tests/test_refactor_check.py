"""scripts/refactor_check.py: two trees' reports compared whole, but for when and where they were made."""
import stubs  # noqa: F401 (a clean environment)
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import refactor_check  # noqa: E402

def write(folder, run, **report):
    path = folder / run / "report.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(report))

class RefactorCheck(unittest.TestCase):
    def test_reports_differ_only_in_what_they_say(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            before, after = Path(a), Path(b)
            write(before, "rules", created_at="2026-10-13", files=[f"{a}/samples/rules.pdf"], evidence=[1, 2])
            write(after, "rules", created_at="2026-10-14", files=[f"{b}/samples/rules.pdf"], evidence=[1, 2])
            write(before, "lcit", evidence=[1], coverage=["tile:0"])
            write(after, "lcit", evidence=[1], coverage=["tile:1"])
            write(before, "gone", evidence=[])
            linked = str(refactor_check.ROOT / "samples/lcit.pdf")  # a worktree's samples/ leads to this checkout's
            write(before, "linked", sources=[linked])
            write(after, "linked", sources=[f"{b}/samples/lcit.pdf"])
            found = refactor_check.differences(refactor_check.reports(before, before),
                                               refactor_check.reports(after, after))
            self.assertEqual(found, [("gone/report.json", "only before"), ("lcit/report.json", "coverage")])

if __name__ == "__main__":
    unittest.main()
