"""Where a region sits in a document's structure: the numbered items and headings above it (stems), the
abbreviations a document defines, and the figures and tables a text cites. Split from extract.py (milestone 7).
"""
import re

from .pages import display_y, reading_dict_blocks

# Numbered markers, from outer to inner: "Contest 9.", "9-2." or "3.1", "c.", "(iii)", "4.".
STEM = re.compile(r"^\s*(Contest \d+\.|\d+-\d+\.|\d+(?:\.\d+)+\.?|[a-z]\.|\((?:[ivx]+|\d+|[a-z])\)\.?|\d+\.)(?=\s|$)")

TITLED = re.compile(r"\s*[-–—:]?\s*[A-Z]")  # a title: a capitalised word, after any dash or colon

def _section(marker):
    """(3, 2, 1) for "3.2.1", or None when the marker isn't digits and dots with at least one inner dot."""
    return tuple(int(n) for n in marker.rstrip(".").split(".")) if re.fullmatch(r"\d+(?:\.\d+)+\.?", marker) else None

def _follows(number, before):
    """Whether section `number` can come next after `before`: its first child (3.2 → 3.2.1), or the next at
    some level, then first children (3.2.1 → 3.2.2, 3.3, 4.1; a first child may be numbered 0 or 1)."""
    return any(number[:k] == before[:k] and number[k] == before[k] + 1 and all(n in (0, 1) for n in number[k + 1:])
               for k in range(min(len(number), len(before)))) or (
        len(number) == len(before) + 1 and number[:-1] == before and number[-1] in (0, 1))

def _numbered(marker, title, styled=False, before=()):
    """Whether digits and dots ("3.2", "12.") start a numbered item with this title, rather than being
    a value in a table ("3.83 -43.73E+6", "0.6 s", "1.35 Partial safety factor"), where the next cell
    would become the item's "title". A list item ("4.") takes any word. A section number takes a
    capitalised title, never starts at 0, and is set as a heading (`styled`) or follows one of the
    section numbers `before` (the ones it sits under, and the last one seen). Other markers ("c.",
    "(ii)") always count."""
    number = _section(marker)
    if number is None:
        return not re.fullmatch(r"\d+\.", marker) or bool(re.match(r"\s*[-–—:]?\s*[^\W\d_]", title))
    return (number[0] > 0 and bool(TITLED.match(title))
            and (styled or any(_follows(number, b) for b in before)))

def _stem_level(marker):
    if marker.startswith("Contest"):
        return 0
    if re.match(r"\d+-\d+\.|\d+(\.\d+)+", marker):
        return 1
    if re.match(r"[a-z]\.", marker):
        return 2
    return 3 if marker.startswith("(") else 4

def stem_index(doc):
    """{page: [(displayed y, parents)]}: for each line, the numbered items and headings it sits
    under (research round 1), so a list item keeps its parents across page breaks. Lines that
    repeat at the same height on most pages (headers, footers) are skipped."""
    from collections import Counter
    def key(line):
        return re.sub(r"\d+", "#", "".join(s["text"] for s in line["spans"]).strip()), round(line["bbox"][1] / 5)
    pages = [reading_dict_blocks(page) for page in doc]
    seen, sizes = Counter(), Counter()
    for blocks in pages:
        keys = set()
        for block in blocks:
            for line in block.get("lines", ()):
                keys.add(key(line))
                for span in line["spans"]:
                    sizes[round(span["size"])] += len(span["text"])
        seen.update(keys)
    margins = {k for k, n in seen.items() if n >= max(2, len(doc) // 2) and k[0]}
    body = sizes.most_common(1)[0][0] if sizes else 10
    stack, pending, last, index = [], None, None, {}
    def push(level, marker, title):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, marker, title))
    for number, (page, blocks) in enumerate(zip(doc, pages), 1):
        rows = index.setdefault(number, [])
        for block in blocks:
            for line in block.get("lines", ()):
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text or key(line) in margins:
                    continue
                first = line["spans"][0]
                heading = (first["size"] > body + 0.5 or (first["flags"] & 16 and len(text) < 60)) and len(text) < 90
                styled = heading and first["size"] > body - 0.5  # not a chart's axis labels
                before = [n for n in (*(_section(m) for _, m, _ in stack), last) if n]
                match = STEM.match(text)
                if match and text[match.end():].strip():
                    if not _numbered(match.group(1), text[match.end():], styled, before):
                        match = None
                    last = _section(STEM.match(text).group(1)) or last
                if pending is not None and _numbered(pending[1], text, pending[2] or styled, before):
                    # A marker alone on its line opens its item once the next line shows it's one: a title
                    # ("3.2.2" / "Insulation Analysis"). A lone value ("23.47" / "-125.30E+6") closes nothing.
                    push(pending[0], pending[1], "" if match else text)
                pending = None
                if match:
                    level = _stem_level(match.group(1))
                    level = 1 if heading and level > 1 else level
                    rest = text[match.end():].strip()
                    if rest:
                        push(level, match.group(1), rest)
                    else:
                        pending = (level, match.group(1), styled)
                        last = _section(match.group(1)) or last
                rows.append((display_y(page, line["bbox"]), [f"{m} {t[:70]}".strip() for _, m, t in stack]))
    return index

SHORT_FORM = re.compile(r"\(([A-Za-z][A-Za-z0-9&/.-]{1,9})\)")

def _long_form(short, before):
    """The words before "(short)" that spell it out (Schwartz and Hearst, 2003): the short
    form's letters are matched right to left, its first letter at a word's start; None if none."""
    words = before.split()[-min(len(short) + 5, 2 * len(short)):]
    text = " ".join(words)
    letters = [c.lower() for c in short if c.isalnum()]
    i = len(text) - 1
    for k in range(len(letters) - 1, -1, -1):
        while i >= 0 and (text[i].lower() != letters[k] or (k == 0 and i > 0 and text[i - 1].isalnum())):
            i -= 1
        if i < 0:
            return None
        i -= 1
    found = text[text.rfind(" ", 0, i + 1) + 1:].strip(" ,;:")
    return found if len(found) > len(short) and short.lower() not in found.lower() else None

def glossary(doc):
    """{abbreviation: long form} for "long form (ABBR)" anywhere in the document (first one wins)."""
    out = {}
    for page in doc:
        text = " ".join(page.get_text("text").split())
        for match in SHORT_FORM.finditer(text):
            short = match.group(1).rstrip(".")
            if short in out or not any(c.isupper() for c in short) or short.isdigit():
                continue
            found = _long_form(short, text[max(0, match.start() - 200):match.start()])
            if found:
                out[short] = found
    return out

MAX_REFERENCES = 3  # definitions, and cited figures or tables, added per chunk

def references(text, terms, figures):
    """Context lines for what a chunk cites but doesn't hold: abbreviations defined elsewhere in
    the document, and the captions of the figures and tables it mentions (research round 1)."""
    from .figures import MENTION, label_key, label_of, targets
    lines = []
    defined = [f"{short} = {long}" for short, long in terms.items()
               if f"({short})" not in text and re.search(rf"\b{re.escape(short)}s?\b", text)]
    if defined:
        lines.append("Defined elsewhere: " + "; ".join(defined[:MAX_REFERENCES]))
    by_label = {}
    for figure in figures:
        if figure.label:
            by_label.setdefault(label_key(figure.label), []).append(figure)
    cited = []
    for match in MENTION.finditer(text):
        label = label_of(*match.groups())
        found = targets(by_label, label)
        name = label[0].upper() + label[1:]
        if found and found[0].caption and found[0].caption[:60] not in " ".join(text.split()):
            entry = f"{found[0].caption[:150]} (page {found[0].page})"
        elif found:
            continue  # the chunk is the caption, or the figure has none
        else:
            entry = f"{name}: not found in this document"
        if entry not in cited:
            cited.append(entry)
    if cited:
        lines.append("Cited: " + "; ".join(cited[:MAX_REFERENCES]))
    return "\n".join(lines)
