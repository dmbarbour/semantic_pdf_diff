"""List positions (docs/plans/claim-context-2026-10-14.md, milestone 1): the labels a source gives the items of a
sequence ("Condition 2:", "Step 3.", "(b)"), found among a page's text blocks without a model, so a claim made in an
item records where it sits instead of taking the label as one of its conditions.

The controlled spec prints "Condition 1: no acknowledgement is received within 856 ms."; its readers said
"conditions: Condition 1", and a revision inserting a condition renumbered the rest, so the same timeout read as
"Condition 2" against "Condition 3" was judged uncertain (2026-10-14). Word writes its numbering's labels into the
text (docxdocs.Numbering) and Markdown keeps its lists', so one rule serves PDF, Word and Markdown text.
"""
import re

from .schema import Position

# A label opening a block: a word and a number or letter, then a delimiter ("Condition 2:", "Step 3.", "Item 4 -");
# or a number, letter or roman numeral alone, closed by "." or ")" ("2.", "b)", "(iv)"). A heading's "4 Link
# Failure Detection" has no delimiter, and a clause's "7.2." is followed by more of its number, so neither is one.
WORDED = re.compile(r"(?P<label>(?P<word>[A-Za-z]+) (?P<n>\d{1,3}|[A-Za-z]))"
                    r"\s*[:.)–—-]\s")
BARE = re.compile(r"(?P<label>\(?(?P<n>\d{1,3}|[A-Za-z]|[ivxIVX]{1,5})[.)])\s")
# Words naming a sequence's items generically: their numbers are positions. Any other word numbered names a thing
# ("Pump 2", "Figure 3", "Option B", "Load Case 3"): its number is identity, and stays where the reader put it.
POSITIONAL = {"condition", "step", "item", "note", "point", "requirement", "criterion", "rule", "stage", "task",
              "action", "bullet", "paragraph", "para", "question", "issue", "comment", "remark", "finding",
              "recommendation", "observation", "proposal", "conclusion", "exception", "assumption", "constraint",
              "objective", "goal"}
ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11,
         "xii": 12, "xiii": 13, "xiv": 14, "xv": 15}
LEAD_CHARS = 300

def _ordinals(n):
    """The ordinals a label's number may stand for: {kind: ordinal} ("c" a letter, "iv" roman, "i" either)."""
    n = n.casefold()
    if n.isdigit():
        return {"number": int(n)}
    out = {"roman": ROMAN[n]} if n in ROMAN else {}
    if len(n) == 1:
        out["letter"] = ord(n) - ord("a") + 1
    return out

def label_of(text):
    """(label as printed, form, ordinals) for a block opening with an item's label, else None. The form tells lists
    apart: a word's ("condition"), or a bare label's punctuation ("1.", "(1)", "1)")."""
    head = text.lstrip()[:60] + " "
    found = WORDED.match(head)
    if found and found.group("word").casefold() in POSITIONAL:
        return found.group("label"), found.group("word").casefold(), _ordinals(found.group("n"))
    found = BARE.match(head)
    if found:
        label = found.group("label")
        form = ("(" if label.startswith("(") else "") + label[-1]
        return label, form, _ordinals(found.group("n"))
    return None

def list_positions(blocks):
    """{box: Position} for a page's text blocks [(box, text)] in reading order: a block opening with a label is a
    list's item when another block opens with a label of the same form numbered next, before or after it (a lone
    "Option B:" is a name). Blocks between items (an item's further paragraphs) are allowed. An item's position
    gives the list's lead-in: the block before its first item, if that isn't an item itself. A block split in
    pieces (one box) is placed by its first."""
    labelled, first_text = [], {}
    for box, text in blocks:
        box = tuple(box)
        if box in first_text:
            continue
        first_text[box] = text
        found = label_of(text)
        if found:
            labelled.append((box, *found))
    order = list(first_text)
    lists = []  # each: {"form", "kind", "last", "items": [(box, label)]}
    for box, label, form, ordinals in labelled:
        home = next((x for x in reversed(lists) if x["form"] == form and any(
            ordinals.get(kind) == x["last"].get(kind, -1) + 1 for kind in ordinals)), None)
        if home is None:
            lists.append({"form": form, "last": ordinals, "items": [(box, label)]})
            continue
        home["last"] = {k: v for k, v in ordinals.items() if v == home["last"].get(k, -1) + 1}
        home["items"].append((box, label))
    out = {}
    for found in lists:
        if len(found["items"]) < 2:
            continue
        start = order.index(found["items"][0][0])
        before = first_text[order[start - 1]] if start else ""
        lead = "" if not before or label_of(before) else " ".join(before.split())[:LEAD_CHARS]
        for box, label in found["items"]:
            out[box] = Position(label=label.rstrip("."), lead=lead)
    return out

GENERIC = r"(?:item|note|step|point|no\.?|number|#|condition|case|clause|requirement|criterion|rule)"

def without_label(conditions, position):
    """conditions with the item's label taken out: a part ("Condition 3; duration 60 s") that is the label alone, or
    a part opening with it ("Condition 3: SNR below 4.3 dB"). A bare label ("2") goes only as a whole part, alone
    or after a generic word ("item 2", "note 2"): a number in a condition is usually a value ("at 2 bar")."""
    label = position.label.strip("()")
    words = label.split()
    if len(words) > 1:
        pattern = r"\s+".join(map(re.escape, words))
        whole = re.compile(rf"^\s*{pattern}\s*$", re.I)
        opening = re.compile(rf"^\s*{pattern}\s*[:–—-]\s*", re.I)
    else:
        whole = re.compile(rf"^\s*(?:{GENERIC}\s*)?\(?{re.escape(label)}[.)]?\s*$", re.I)
        opening = None
    parts = re.split(r"\s*;\s*|\s*,\s*", conditions)
    kept = [opening.sub("", part) if opening else part for part in parts if part and not whole.match(part)]
    if kept == [part for part in parts if part]:
        return conditions  # no label in it: as the reader wrote it
    separator = "; " if ";" in conditions else ", "
    return separator.join(p for p in kept if p)
