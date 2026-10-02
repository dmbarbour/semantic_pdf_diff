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

def requests(settings, sheet, logged=False):
    """One comparison's requests [(role, prompt, image hashes, params)], and (logged) its store's query log."""
    from semantic_pdf_diff.store import Store
    with tempfile.TemporaryDirectory() as d, jittery_model() as (url, state):
        root = Path(d)
        a, b = document(root / "a.pdf", 10, sheet), document(root / "b.pdf", 12, sheet)
        (root / "settings.json").write_text(json.dumps(settings))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cli.main([str(a), str(b), "--out", str(root / "out"), "--base-url", url,
                      "--config", str(root / "settings.json")])
        if logged:
            with Store(root / "out") as store:
                return state["transcript"], store.queries()
    return state["transcript"]

def transcript(settings, sheet):
    """The golden text of one comparison's requests."""
    lines, first = [], {}
    for role, prompt, images, params in requests(settings, sheet):
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

class Structure(unittest.TestCase):
    """A request's layout has one owner per role (code review 2026-10-01, A1): readers don't split at markers."""
    def test_every_extraction_prompt_reads_back_into_its_parts(self):
        from semantic_pdf_diff.extract import ExtractQuery
        from semantic_pdf_diff.llm import RECIPES, recipe_fields
        for name, (settings, sheet) in PROFILES.items():
            with self.subTest(profile=name):
                sent, logged = requests(settings, sheet, logged=True)
                prompts = [p for role, p, _, _ in sent if role == "extract"]
                self.assertTrue(prompts)
                for prompt in prompts:
                    asked = ExtractQuery.read(prompt)
                    self.assertEqual(asked.prompt(), prompt)
                    self.assertTrue(asked.request.startswith("Source type: " + asked.region))
                for q in logged:  # every recipe has its role's named fields
                    fields = recipe_fields(q["recipe"])
                    self.assertLessEqual(set(RECIPES.get(fields["role"], ())), set(fields), q["recipe"])
                    if fields["role"] == "extract":
                        self.assertEqual((fields["content"], fields["task"]), (q["content"], q["task"]))

class AbsentIsOff(unittest.TestCase):
    """Every lever acts through its hooks, so a configuration may leave it out, and a lever left out asks exactly
    what its `off` settings ask (levers.py; architecture clean-up, milestone 4)."""
    def golden(self, name):
        text = (GOLDEN / f"requests-{name}.txt").read_text(encoding="utf-8")
        if text.split("\n", 1)[0] != f"# PyMuPDF {pymupdf.VersionBind}":
            self.skipTest("golden recorded under another PyMuPDF")
        return text

    def test_round_0_without_its_levers_that_are_off(self):
        from semantic_pdf_diff.levers import REGISTRY
        from semantic_pdf_diff.models import Settings
        settings = Settings(**ROUND0)
        off = [n for n in ROUND0["levers"] if all(getattr(settings, f) == v for f, v in REGISTRY[n].off.items())]
        self.assertGreater(len(off), 10)
        fields = {f for n in off for f in REGISTRY[n].model_fields}
        lean = {"levers": [n for n in ROUND0["levers"] if n not in off],
                **{k: v for k, v in ROUND0.items() if k != "levers" and k not in fields}}
        self.assertEqual(transcript(lean, False), self.golden("round0"), f"without {off}")

    def test_every_lever_off_is_no_lever_at_all(self):
        from semantic_pdf_diff.levers import LEVER_CLASSES
        off = {f: v for lever in LEVER_CLASSES for f, v in lever.off.items()}
        for sheet in (False, True):
            with self.subTest(sheet=sheet):
                self.assertEqual(transcript({"levers": []}, sheet), transcript(off, sheet))

if __name__ == "__main__":
    unittest.main()
