"""A round's steps (scripts/run_round.py's RoundRunner; architecture clean-up, milestone 7): refusals, pauses, holds
and the recorder's calls, driven with stubs, without models or recordings."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_round  # noqa: E402

PUBLIC = {"runs": [{"name": "r1", "set": "dev", "slices": ["s1", "s1"]}],
          "slices": [{"name": "s1", "public": True}]}

class Runner(run_round.RoundRunner):
    """A runner over a temporary round: its manifest given, its recordings noted, not made."""
    manifest_data = PUBLIC

    def __init__(self, folder, **kw):
        self.ledger_path, self.history = folder / "ledger.jsonl", folder / "history.jsonl"
        self.report_path, self.runs_base = folder / "report.html", folder / "runs"
        self.recorded = []
        super().__init__(folder, **kw)

    def manifest(self):
        return self.manifest_data

    def record_runs(self, argv):
        self.recorded.append(argv)
        return 0

def round_folder(d, **spec):
    folder = Path(d)
    (folder / "round.json").write_text(json.dumps({
        "name": "t", "baseline": "b.json", "cap": 1.0,
        "variants": {"lever": "v.json", "aa": {"settings": "b.json", "fresh": ["tile", "figure"]}}, **spec}))
    return folder

def quietly(runner):
    with contextlib.redirect_stdout(io.StringIO()):
        return runner.run()

class Steps(unittest.TestCase):
    def test_a_private_slice_is_refused_before_anything_runs(self):
        with tempfile.TemporaryDirectory() as d:
            runner = Runner(round_folder(d))
            runner.manifest_data = {**PUBLIC, "slices": [{"name": "s1"}]}  # not marked public
            self.assertEqual(quietly(runner), 2)
            self.assertEqual(runner.recorded, [])

    def test_every_variant_is_recorded_then_replayed_with_its_settings(self):
        with tempfile.TemporaryDirectory() as d:
            runner = Runner(round_folder(d), only="replay")
            self.assertEqual(quietly(runner), 0)
            self.assertEqual([a[a.index("--variant") + 1].rsplit("/", 1)[1] for a in runner.recorded],
                             ["b.json", "v.json", "b.json"])
            fresh = [a[a.index("--fresh-regions") + 1] for a in runner.recorded]
            self.assertEqual(fresh, ["", "", "tile,figure"])  # the A/A control answers its regions afresh
            self.assertTrue(all("--replay" in a for a in runner.recorded))
            self.assertTrue(all(runner.done(f"replay:{v}") for v in ("baseline", "lever", "aa")))
            again = Runner(Path(d), only="replay")  # resumed: nothing repeated
            quietly(again)
            self.assertEqual(again.recorded, [])

    def test_recording_pauses_at_the_rounds_cap(self):
        with tempfile.TemporaryDirectory() as d:
            runner = Runner(round_folder(d, cap=0.0), only="record")
            self.assertEqual(quietly(runner), 3)
            self.assertEqual(runner.state["steps"]["record:baseline"], "paused: round cap reached")
            self.assertEqual(runner.recorded, [])

    def test_flagged_queries_hold_the_round_until_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            folder = round_folder(d, query_checks={"sample": 5, "cap": 1.0})
            (folder / "state.json").write_text(json.dumps({"steps": {}, "query_flags": {"lever": ["q1"]}}))
            self.assertEqual(quietly(Runner(folder, only="pairs")), 4)
            self.assertEqual(quietly(Runner(folder, only="pairs", accept_checks=True)), 0)

    def test_criteria_changed_after_judging_began_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            folder = round_folder(d, judges=["judge-a"])
            runner = Runner(folder, only="judge")
            quietly(runner)  # locks the criteria as judging starts
            spec = json.loads((folder / "round.json").read_text())
            spec["criteria"] = {"win_low": 0.4}
            (folder / "round.json").write_text(json.dumps(spec))
            self.assertEqual(quietly(Runner(folder, only="judge")), 2)

if __name__ == "__main__":
    unittest.main()
