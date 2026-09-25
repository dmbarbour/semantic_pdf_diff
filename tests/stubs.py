"""Answers shared by test stub models."""

def situating_answer(prompt):
    """A situating answer derived from the prompt, or None if it isn't a situating request."""
    if 'Situate one figure' in prompt:
        caption = prompt.split('Caption: ', 1)[1].split('\n', 1)[0]
        return {'about': f'stub figure: {caption[:40]}', 'role': '', 'keywords': ['stub']}
    if 'Describe one section' in prompt:
        heading = prompt.split('Heading path: ', 1)[1].split('\n', 1)[0]
        return {'about': f'stub section: {heading}', 'type': 'other', 'density': 'low', 'keywords': ['stub']}
    return None
