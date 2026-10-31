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

# --- a claim's snippet: the source's text around its quote (report snippets, milestone 1) -------------------------

SNIPPET = 600  # characters of the source's text a claim's card shows, at most
# The pipeline's own notes in a task's text (levers.LAYER_NOTE, levers.TABLE_CUT_NOTE), never the source's
NOTES = re.compile(r"(?:TEXT LAYER OF THIS REGION|THIS REGION CUTS A TABLE)[^:\n]*(?::[^:\n]*)?:")
ROW = re.compile(r"^(?:Header|Row): (\[.*\])\s*$", re.MULTILINE)
SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+|\s*\n\s*")

def row_snippet(head, cells, limit=SNIPPET):
    """A table row as its card shows it: its header's cells over its own, " | " between."""
    lines = [" | ".join(str(c).strip() for c in row if c not in (None, "") and str(c).strip())
             for row in (head, cells) if row]
    out = "\n".join(line for line in lines if line)
    return out if len(out) <= limit else out[:limit - 1].rstrip() + "…"

def snippet(text, quote, limit=SNIPPET):
    """The source's text a claim was read from, as its card shows it: a table row's cells under its header; else the
    sentences (or lines) holding its quote, widened to about limit characters at sentence ends, "…" where cut;
    "" where the quote isn't found (a misread, a picture without a text layer)."""
    import json
    rows = []
    for m in ROW.finditer(text or ""):
        try:
            rows.append(json.loads(m.group(1)))
        except ValueError:
            return ""
    if rows:
        return row_snippet(rows[0] if len(rows) > 1 else [], rows[-1], limit)
    body = NOTES.sub("\n", text or "")
    fragments = sorted((f for f in ELLIPSIS.split(quote or "") if len(f.strip()) >= 3), key=len, reverse=True)
    found = None
    for fragment in fragments[:1]:
        words = fragment.split()
        found = re.search(r"\s+".join(map(re.escape, words)), body, re.IGNORECASE) if words else None
    if found is None:
        return ""
    pad = max(0, (limit - (found.end() - found.start())) // 2)
    start, end = max(0, found.start() - pad), min(len(body), found.end() + pad)
    ends = [m.end() for m in SENTENCE_END.finditer(body, start, found.start())]  # a sentence's start, the first
    start = ends[0] if ends and start > 0 else start
    after = [m.start() for m in SENTENCE_END.finditer(body, found.end(), min(len(body), end + 1))]  # the last's end
    end = after[-1] if after and end < len(body) else end
    said = " ".join(body[start:end].split())
    return ("…" if start > 0 and not ends else "") + said + ("…" if end < len(body) and not after else "")
