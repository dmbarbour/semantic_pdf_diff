"""Answers shared by test stub models."""
import re

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
