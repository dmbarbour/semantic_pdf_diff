"""Context records found mechanically on a page (docs/plans/claim-context-2026-10-14.md, milestone 3): the parts of
a document that give claims context, stored once and referenced by the claims they hold or reach (schema.
ContextRecord, Evidence.records).

- **Lists** (positions.found_lists): a numbered sequence's lead-in and its items' labels. Its items' claims take
  the list's record, and their positions point at it rather than copying the lead-in.
- **Tables** read by rules (tablerules): a table's title, its columns' headers, and the context its rows are given
  (its lead-in, the headings and numbered items it's under). Its claims take the table's record, and each its name as
  printed: its row's label and its value's header (tablerules.printed_name).
- **Notes and legends** on a drawing sheet: a block headed GENERAL NOTES, SHEET NOTES, KEYNOTES, LEGEND or
  ABBREVIATIONS, with the numbered notes under it. A sheet's notes reach the whole sheet ("ALL DIMENSIONS ARE TO FACE
  OF FINISH UNLESS NOTED OTHERWISE"), so every claim on the page takes them. On other pages a "Notes" heading is
  often a table's or a section's, whose reach the layout doesn't settle: not taken there.
- **Names as printed** (Evidence.printed): a table claim's row label and value's header; a text claim's words before
  its value in its verified quote (printed_before).
"""
import re

from .context import CONTEXT_NOTE
from .positions import found_lists, label_of
from .schema import ContextRecord, Position

NOTE_HEADING = re.compile(r"^\s*(?:(?:general|sheet|construction|drawing|plan|key|demolition|structural|electrical|"
                          r"mechanical|plumbing|fire protection|site)\s+)?(?:notes?|keynotes)\s*:?\s*$", re.I)
LEGEND_HEADING = re.compile(r"^\s*(?:legend|abbreviations|symbols(?: legend)?|symbol legend)\s*:?\s*$", re.I)
MAX_NOTE_BLOCKS = 20     # blocks taken under a heading, at most
TEXT_CHARS = 2000        # ContextRecord.text's bound

def _union(boxes):
    boxes = list(boxes)
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))

def _heading(text):
    """("note" or "legend", the heading as printed) when a block's first line heads a sheet's notes, else None."""
    first = text.strip().split("\n", 1)[0]
    if NOTE_HEADING.match(first):
        return "note", first.strip().rstrip(":")
    if LEGEND_HEADING.match(first):
        return "legend", first.strip().rstrip(":")
    return None

def list_records(page_no, blocks, positions):
    """(the page's list records, its positions pointing at them): each list's lead-in as its text, its labels as its
    items; an item's Position keeps its label and names its list, its lead-in left to the record."""
    records, pointed = [], dict(positions)
    for i, found in enumerate(found_lists(blocks)):
        boxes = [box for box, _ in found["items"]]
        if not any(box in positions for box in boxes):
            continue  # the positions hook didn't place these (positions: conditions)
        rid = f"list:p{page_no}:{i}"
        records.append(ContextRecord(id=rid, kind="list", gives=["scope"] if found["lead"] else [],
                                     text=found["lead"], items=[label.rstrip(".") for _, label in found["items"]],
                                     page=page_no, bbox=_union(boxes)))
        for box in boxes:
            if box in positions:
                pointed[box] = Position(label=positions[box].label, list=rid)
    return records, pointed

def note_records(page_no, blocks):
    """A drawing sheet's notes and legends: each heading block with the numbered notes under it."""
    records, taken = [], set()
    for i, (box, text) in enumerate(blocks):
        found = _heading(text)
        if not found or i in taken:
            continue
        kind, label = found
        parts, boxes = [text.strip().split("\n", 1)[1].strip()] if "\n" in text.strip() else [], [tuple(box)]
        for j in range(i + 1, min(len(blocks), i + 1 + MAX_NOTE_BLOCKS)):
            other_box, other = blocks[j]
            if _heading(other) or not label_of(other) and parts:
                break  # another heading, or an unnumbered block once notes have begun
            parts.append(other.strip())
            boxes.append(tuple(other_box))
            taken.add(j)
        text_of = " ".join(" ".join(p.split()) for p in parts if p)[:TEXT_CHARS]
        if not text_of:
            continue
        records.append(ContextRecord(id=f"{kind}:p{page_no}:{len(records)}", kind=kind,
                                     gives=["frame"] if kind == "legend" else ["frame", "scope"], label=label,
                                     text=text_of, page=page_no, bbox=_union(boxes)))
    return records

def table_record(page_no, task, grid, context, box):
    """A table read by rules, as a record: its title as its label, its headers as its items, the context its rows
    are given as its text; named by the rules task ("rules:p2:0" is "table:p2:0")."""
    where = task.split(":", 1)[1] if task.startswith("rules:") else task
    text = " ".join(context.replace(CONTEXT_NOTE, "").split())[:TEXT_CHARS]
    return ContextRecord(id=f"table:{where}"[:120], kind="table", gives=["subject"] + (["scope"] if text else []),
                         label=(grid.title or grid.place)[:200], text=text,
                         items=[label[:200] for label in grid.labels if label], page=page_no, bbox=tuple(box))

# Words that link a name to its value ("the timer is 709 ms", "a limit of 21"): trimmed from a name's end; articles
# from its start.
LINKS = {"is", "are", "was", "were", "be", "been", "being", "of", "at", "to", "within", "by", "shall", "should",
         "must", "will", "may", "can", "equals", "equal", "approximately", "about", "up", "than", "less", "more",
         "not", "exceed", "exceeds", "from", "between", "and", "set", "reaches", "reach", "stays", "below", "above",
         "under", "over", "for", "with", "has", "have", "had", "a", "an", "the", "=", ":", "-", "–", "—", "~", "≈",
         "≤", "≥", "<", ">"}
ARTICLES = {"the", "a", "an"}
NAME_WORDS = 6  # a name as printed: at most this many words before its value

def printed_before(quote, value):
    """A text claim's name as printed: the words before its value in its quote, back to the clause's start or an
    earlier number, without the words linking it to the value ("the retransmission timer is 709 ms": "retransmission
    timer"; "Keep-alive interval: 1,250 ms": "Keep-alive interval"); "" when the value isn't in the quote as printed
    (its digits, with or without thousands separators), or nothing names it there."""
    digits = value.strip()
    if not digits:
        return ""
    pattern = ",?".join(re.escape(c) for c in digits.replace(",", ""))
    found = re.search(rf"(?<![\w.,]){pattern}(?![\d])", quote)
    if not found:
        return ""
    before = re.split(r"[;!?()\[\]]|\.(?=\s|$)|,\s", quote[:found.start()])[-1]
    words = before.split()
    numbered = [i for i, w in enumerate(words) if re.search(r"\d", w)]
    if numbered:
        words = words[numbered[-1] + 1:]  # an earlier value and its unit aren't this one's name
    while words and words[-1].casefold().strip(",:") in LINKS | {""}:
        words.pop()
    words = words[-NAME_WORDS:]
    while words and words[0].casefold() in ARTICLES:
        words.pop(0)
    name = " ".join(words).rstrip(":")
    return "" if len(name) <= 3 else name[:200]

# --- records compared between revisions (the record_changes lever; the plan's milestone 4, design question 6) -------

def _wording(text):
    """A record's words, numbers aside: a value changed in a lead-in is a value change, reported as one."""
    return re.findall(r"[^\W\d_]+", text.casefold())

def _keyed(found):
    """{(kind, label): [(content, record)]} in page order: a note or table by its heading or title, a list by none.
    found: {content: {id: ContextRecord}}."""
    out = {}
    pairs = sorted(((c, r) for c, records in found.items() for r in records.values()),
                   key=lambda x: (x[0], x[1].page or 0, x[1].id))
    for content, r in pairs:
        out.setdefault((r.kind, " ".join(_wording(r.label))), []).append((content, r))
    return out

def changed_records(earlier, later, left, right):
    """The context records restated between two revisions, each once with the claims it reaches on either side:
    [{"kind", "label", "earlier": {content, id, text, items}, "later": {...}, "claims": [claim ids]}]. earlier,
    later: {content: {id: ContextRecord}} of each side's own content (shared content is the same on both); left,
    right: each side's claims. Records pair by kind and heading or title, in order; a pair is restated when its
    words differ, numbers aside (a table's headers too)."""
    a_side, b_side = _keyed(earlier), _keyed(later)
    out = []
    for key in sorted(a_side.keys() & b_side.keys()):
        for (ca, a), (cb, b) in zip(a_side[key], b_side[key]):
            headers = [_wording(i) for i in a.items], [_wording(i) for i in b.items]
            if _wording(a.text) == _wording(b.text) and headers[0] == headers[1]:
                continue
            claims = [e.id for e in left if e.content == ca and a.id in e.records] + \
                     [e.id for e in right if e.content == cb and b.id in e.records]
            out.append({"kind": a.kind, "label": a.label or b.label,
                        "earlier": {"content": ca, "id": a.id, "text": a.text, "items": a.items},
                        "later": {"content": cb, "id": b.id, "text": b.text, "items": b.items}, "claims": claims})
    return out
