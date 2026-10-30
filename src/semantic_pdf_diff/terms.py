"""A glossary's terms as words (docs/plans/indexes-and-glossaries-2026-10-29.md): text folded as found, and a term
that describes a mark drawn. Pure: what reads glossaries (the index, the report) imports it without the glossary's
reading (glossary.py), which reaches the store and the scanner.
"""

def fold(text):
    """Text as found: case, spacing, dashes and quotes folded."""
    text = str(text).casefold().translate(str.maketrans("–—‐‑’‘“”", "----''\"\""))
    return " ".join(text.split())

def drawn(term):
    """Whether a term describes a mark drawn ("[circle with M]"), not a name printed."""
    return term.startswith("[") and term.endswith("]") and len(term) > 2
