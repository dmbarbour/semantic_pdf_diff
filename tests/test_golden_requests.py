"""Requests for every role, golden: extraction, situating and comparison of synthetic documents under the
defaults, round 0's settings and a drawing sheet.

Recorded answers are found by what reached the model, so a refactor that changes a request's bytes makes every
recorded answer to it miss, and it is paid again. Judge prompts have their goldens (test_judge_prompts); these
cover the rest of the pipeline, so the architecture clean-up (docs/plans/architecture-cleanup-2026-10-02.md)
can show each step changed no request it didn't mean to. A golden holds one line per request (its role and a
hash of its prompt, image hashes and parameters) and each role's first prompt in full, so a change to a
template reads as a diff. After an intended change, regenerate with GOLDEN_UPDATE=1 and review the diff.

Image bytes depend on PyMuPDF's rendering, so a golden notes the version and is skipped under another.
"""
import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
import pymupdf
import stubs
from stubs import ROUND0
from semantic_pdf_diff import cli
from test_concurrency import jittery_model
from test_settings import document

GOLDEN = Path(__file__).resolve().parent / "golden"
UPDATE = bool(os.environ.get("GOLDEN_UPDATE"))
PROFILES = {"defaults": ({}, False), "round0": (ROUND0, False), "defaults-sheet": ({}, True)}

def transcript(settings, sheet):
    """The golden text of one comparison's requests."""
    with tempfile.TemporaryDirectory() as d, jittery_model() as (url, state):
        root = Path(d)
        a, b = document(root / "a.pdf", 10, sheet), document(root / "b.pdf", 12, sheet)
        (root / "settings.json").write_text(json.dumps(settings))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cli.main([str(a), str(b), "--out", str(root / "out"), "--base-url", url,
                      "--config", str(root / "settings.json")])
    lines, first = [], {}
    for role, prompt, images, params in state["transcript"]:
        digest = hashlib.sha256(json.dumps({"prompt": prompt, "images": images, "params": params},
                                           sort_keys=True).encode()).hexdigest()
        lines.append(f"{role} {digest} images={len(images)}")
        first[role] = min(first.get(role, prompt), prompt)  # the first in sorted order, whatever order they came
    out = [f"# PyMuPDF {pymupdf.VersionBind}", f"# {len(lines)} requests", ""] + sorted(lines) + [""]
    for role in sorted(first):
        out += [f"=== the first {role} prompt", first[role], ""]
    return "\n".join(out)

class GoldenRequests(unittest.TestCase):
    def test_every_role_under_each_profile(self):
        for name, (settings, sheet) in PROFILES.items():
            with self.subTest(profile=name):
                text = transcript(settings, sheet)
                path = GOLDEN / f"requests-{name}.txt"
                if UPDATE:
                    path.write_text(text, encoding="utf-8")
                self.assertTrue(path.exists(), f"{path}: no golden (run with GOLDEN_UPDATE=1)")
                golden = path.read_text(encoding="utf-8")
                recorded_with = golden.split("\n", 1)[0]
                if recorded_with != f"# PyMuPDF {pymupdf.VersionBind}":
                    self.skipTest(f"golden {recorded_with[2:]}; images differ under PyMuPDF {pymupdf.VersionBind}")
                self.assertEqual(text, golden, f"{name}: requests changed, so recorded answers to them would miss")

if __name__ == "__main__":
    unittest.main()
