"""Whether a claim's quote is in its source: exactly, word for word across table cells, or (with the quote_match
lever) as fragments or in-order excerpts. Split from extract.py (architecture clean-up, milestone 7).
"""
import re
import unicodedata

def normalize(text):
    return " ".join(text.split())

def terms(text, fold=False):
    return set(re.findall(r"\w+(?:[.,/]\w+)*", text.casefold() if fold else text))

def quoted(quote, text):
    """The quote appears verbatim in text, up to whitespace."""
    return normalize(quote) in normalize(text)

FOLD = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-", "’": "'", "‘": "'", "“": '"',
                      "”": '"', "·": "•", "∙": "•", "×": "x"})
ELLIPSIS = re.compile(r"\s*(?:\.\s?\.\s?\.|…|\s\|\s)\s*")  # "a ... b", and table cells "a | b"

LINE_HYPHEN = re.compile(r"(\w)-\s+(?=\w)")  # "linear-\nspring": a compound broken at a line end

def _folded(text):
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "").translate(FOLD)
    return " ".join(LINE_HYPHEN.sub(r"\1-", text).casefold().split())

def excerpted(quote, text, in_order=True):
    """The quote is excerpts of text: its parts between ellipses ("...", "…") or cell bars
    (" | ") each appear in order, up to case, whitespace, Unicode forms, line-end hyphenation
    ("linear-\nspring") and dash, quote-mark and bullet variants; with in_order, a part may also
    be words read in order across a pseudo-table (a header and its value), within about three
    times its length (round 9: that window let chart-axis labels through as values).
    A third of text claims were rejected by the verbatim check for such quotes (overall review,
    2026-09-28); paraphrases and quotes from the context still fail."""
    parts = [p for p in (_folded(p) for p in ELLIPSIS.split(quote)) if p]
    if not parts:
        return False
    haystack, at = _folded(text), 0
    for part in parts:
        found = haystack.find(part, at)
        end = found + len(part) if found >= 0 else (_in_order(part.split(), haystack, at, 3 * len(part) + 40)
                                                     if in_order else None)
        if end is None:
            return False
        at = end
    return True

def _in_order(words, haystack, start, span):
    """End of the first place after `start` where the words appear in order within `span`
    characters (a row header and its value read across a pseudo-table), or None."""
    begin = haystack.find(words[0], start)
    while begin >= 0:
        at = begin + len(words[0])
        for word in words[1:]:
            at = haystack.find(word, at)
            if at < 0 or at - begin > span:
                break
            at += len(word)
        else:
            return at
        begin = haystack.find(words[0], begin + 1)
    return None

def covered(quote, text, fold=False):
    """Every word of the quote occurs in text; tolerates quotes spanning table cells."""
    words = terms(quote, fold)
    return bool(words) and words <= terms(text, fold)
