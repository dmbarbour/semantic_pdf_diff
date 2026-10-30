"""The test runner's retry of a module that failed while the machine was busy (scripts/run_tests.py; the owner,
2026-10-30: "If there's an easy way to check how busy the computer is, perhaps test it before and after the flaky
test to support a diagnostic and a decision to retry.")."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("run_tests", ROOT / "scripts/run_tests.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Retried(unittest.TestCase):
    def retried(self, failed, results):
        asked, said = [], []

        def again(name):
            asked.append(name)
            code, busy = results[name]
            return name, code, f"{name} alone", 2.0, busy
        stand, flaky = runner.retried(failed, again, now=lambda: "CPUs 10% busy", say=said.append)
        return stand, flaky, asked, said

    def test_a_failure_with_the_machine_busy_run_again_alone(self):
        stand, flaky, asked, said = self.retried([("test_slow", "timed out", 0.97)], {"test_slow": (0, 0.12)})
        self.assertEqual((stand, asked), ([], ["test_slow"]))
        self.assertEqual(flaky, [("test_slow", "failed with the CPUs 97% busy, passed alone (CPUs 12% busy)")])
        self.assertEqual(said, ["test_slow failed with the CPUs 97% busy: run again alone (CPUs 10% busy)",
                                "test_slow passed alone in 2.0s (CPUs 12% busy): counted as passing, flaky under "
                                "load"])

    def test_one_failing_alone_too_stands_with_both_outputs(self):
        stand, flaky, _, _ = self.retried([("test_bad", "AssertionError", 0.9)], {"test_bad": (1, 0.1)})
        self.assertEqual(flaky, [])
        self.assertEqual(stand, [("test_bad", "AssertionError\n----- run again alone (CPUs 10% busy) -----\n"
                                              "test_bad alone")])

    def test_a_failure_with_the_machine_quiet_or_unmeasured_isnt_retried(self):
        stand, flaky, asked, _ = self.retried([("test_a", "x", 0.4), ("test_b", "y", None)], {})
        self.assertEqual((stand, flaky, asked), ([("test_a", "x"), ("test_b", "y")], [], []))

    def test_how_busy(self):
        self.assertEqual(runner.busy_between((10, 100), (55, 150)), 0.9)
        self.assertIsNone(runner.busy_between(None, (1, 2)))
        self.assertIsNone(runner.busy_between((1, 2), (1, 2)))


if __name__ == "__main__":
    unittest.main()
