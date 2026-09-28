"""Answers shared by test stub models, and round 0's settings for tests of pipeline mechanics."""
import json
import re
from pathlib import Path

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
