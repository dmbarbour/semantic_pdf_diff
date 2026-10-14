"""The probe batteries (docs/plans/claim-context-2026-10-14.md, milestone 2; lab bench/probes.py) replay from their
packed answers as recorded: the harness reads, judges and scores as it did when the model answered."""
import stubs  # noqa: F401 (a clean environment)
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff import pipeline
from semantic_pdf_diff_lab.bench import probes

FOLDER = Path(__file__).resolve().parent.parent / "benchmarks/probes"

class Replay(unittest.TestCase):
    def test_the_battery_replays_as_recorded(self):
        recorded = json.loads((FOLDER / "results.json").read_text(encoding="utf-8"))
        for responder, result in recorded.items():
            settings = pipeline.settings_from(FOLDER / "settings.json", base_url=pipeline.NO_MODEL, model=responder)
            options = pipeline.RunOptions(fixture=FOLDER / "replay.zip", responder=responder, fixture_mode="replay")
            with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                outcomes = probes.run_reader(d, settings, options) + probes.run_judge(d, settings, options)
            with self.subTest(responder=responder):
                self.assertEqual([(o.probe, o.check, o.passed, o.model_passed) for o in outcomes],
                                 [(o["probe"], o["check"], o["passed"], o["model_passed"]) for o in result["outcomes"]])

class Checks(unittest.TestCase):
    def test_a_check_reads_only_its_values_claims(self):
        probe = next(p for p in probes.READER if p.id == "scope-lead-in")
        outcomes = probes.read_probe(probe, [{"value": "709", "conditions": "link idle"},
                                             {"value": "1250", "conditions": ""}])
        self.assertEqual([o.passed for o in outcomes], [True, False])  # "1,250" read as "1250" is found, unscoped
        self.assertFalse(probes.read_probe(probe, [])[0].passed)  # nothing read: no pass

if __name__ == "__main__":
    unittest.main()
