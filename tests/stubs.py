"""Answers shared by test stub models, and round 0's settings for tests of pipeline mechanics."""
import importlib.util
import json
import os
import re
import unittest
from pathlib import Path

# Tests run with a clean environment: PDF_DIFF_* and OPENAI_* exported in a shell (the scripts say to source .env)
# would otherwise change what the CLI's Settings.from_env reads, and so what tests send and expect. Every test
# module imports this module.
for _name in [n for n in os.environ if n.startswith(("PDF_DIFF_", "OPENAI_"))]:
    del os.environ[_name]

# A quick run for iterating (QUICK=1 python -m unittest discover -s tests): the slowest tests skipped, about two thirds
# of the time (docs/plans/quick-wins-2026-10-02.md). Every commit is still checked by the full suite.
QUICK = bool(os.environ.get("QUICK"))

def slow(item):
    """Mark a test, or a class whose setup is the slow part, to be skipped in a quick run."""
    return unittest.skipIf(QUICK, "slow: skipped in a quick run (QUICK=1)")(item)

def needs_lab():
    """Skip a product test whose input the lab's generators build, where the lab isn't installed (a plain install of
    the diff tool; code review 2026-10-08, E18). Called before the lab's import."""
    if importlib.util.find_spec("semantic_pdf_diff_lab") is None:
        raise unittest.SkipTest("needs the lab (pip install -e lab)")

# The query settings before the improvement rounds' champion became the defaults (2026-09-28):
# tests of mechanics (refinement, tiling, prompt layout) that don't depend on the levers use these.
ROUND0 = json.loads((Path(__file__).resolve().parent.parent / 'benchmarks' / 'round0.json').read_text())

def situating_answer(prompt):
    """A situating answer derived from the prompt, or None if it isn't a situating request."""
    if 'Situate one figure' in prompt:
        found = re.search(r'^(?:Caption|Title): (.*)$', prompt, re.MULTILINE)
        name = found.group(1) if found else 'unlabelled'
        answer = {'about': f'stub figure: {name[:40]}', 'role': '', 'keywords': ['stub']}
        printed = re.search(r'PRINTED LABEL (\S+ \S+)', prompt)  # lets tests plant a label only the "image" shows
        if printed:
            answer['label'] = printed.group(1)
        return answer
    if 'Describe one section' in prompt:
        heading = prompt.split('Heading path: ', 1)[1].split('\n', 1)[0]
        return {'about': f'stub section: {heading}', 'type': 'other', 'density': 'low', 'keywords': ['stub']}
    return None
