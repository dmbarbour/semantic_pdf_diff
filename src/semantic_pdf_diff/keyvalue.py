"""Key-value blocks (code review 2026-10-08, B5): a block of two columns may be a key-value list, as on a form or a
data sheet ("Pump | P-2", "Flow | 95 L/s", "Head | 30 m"), not a table headed by its first row. Read as a table,
its first pair was the header: "P-2" never read as a value, the other rows read under the labels "Pump" and "P-2".

Our heuristic proposes, the model confirms (as decision 0023; the owner, 2026-10-09: "you should still be asking a
model (likely vision) to confirm the proposed 'rule' for reading a table"):
- **Candidates** (candidate): two columns, the left one (its header included) holding no number or date, the header
  not marked as one (a sheet's defined table, Word's repeated header rows) and both its cells filled, and a row
  below it.
- **The key-value check:** one small query a candidate, showing its rows and the context a table row is given, and
  a PDF's crop of it; answered {"reading": "key-value" | "table", "why"}.
- **The outcome:** "key-value", its rows read as "key: value" lines by a text task; "table", read as a table, as
  before; a failed check (or an answer naming neither), our proposal used (key-value) and the check recorded partial;
  not reached (the call limit, an answer a replay lacks), recorded so and asked on the next run, the block unread.
- **Traced:** each claim's derivation has a "key-value-check" step saying what the model answered, or that it didn't.
"""
import hashlib

from pydantic import Field

from .schema import DerivationStep, Lenient, coverage_row
from .tablegrid import kind
from .tablerules import SHOWN_CELL

SHOWN_ROWS = 12  # the rows a check shows; the rest counted

KEY_VALUE = '''This is a block of two columns from an engineering document. Decide how it's read.
- "key-value": a key-value list, as on a form or a data sheet. Each row is a key (column A) and its value (column B),
  the first row included.
- "table": a table. Its first row is a header naming the two columns, and each row below holds data under those
  names.
Our proposal, a guess from its layout (two columns, no numbers in column A): a key-value list. Decide yourself.
Return JSON only: {"reading":"key-value|table", "why":"one sentence"}
'''

IMAGED = "The image shows the block as laid out on its page."

class Check(Lenient):
    """A model's answer to the key-value check (KEY_VALUE)."""
    reading: str = Field(default="", max_length=20)
    why: str = Field(default="", max_length=400)

def candidate(g, marked=False):
    """Whether a table's grid (tablegrid.Grid) is proposed as a key-value list: two columns, column A holding no
    number or date (its header included), the header not marked as one and both its cells filled, and a row below."""
    if g is None or marked or len(g.columns) != 2 or all(row == g.labels for row in g.rows):
        return False  # no row below: a PDF table of one row is read with that row as its body, its header repeated
                      # (most often a header cell PyMuPDF detects as a tiny table of its own: "Rating | (psi)")
    if not all(label.strip() for label in g.labels) or g.labels[0] == g.labels[1]:
        return False  # a header cell merged across both columns: a title, not a pair
    return all(kind(text) not in ("number", "date") for text in [g.labels[0]] + [row[0] for row in g.rows])

def pairs(g):
    """The block's rows as "key: value" lines, its header's first: [text] (a row with one cell filled, that cell)."""
    return [": ".join(t for t in row if t) for row in [g.labels] + g.rows]

def question(g, context="", image=False):
    """The check's text; context: the context lines a row of the table is given (its lead-in, its headings)."""
    cut = lambda text: (text[:SHOWN_CELL] + "…" if len(text) > SHOWN_CELL else text).replace("|", "/")
    rows = [g.labels] + g.rows
    lines = [f"BLOCK: {g.place}" + (f"; title: {g.title}" if g.title else "")] + ([context] if context else []) + [
             f"ROWS ({len(rows)}; the row's number, then its cells, A | B):"]
    lines += [f"{k} | {cut(a)} | {cut(b)}" for k, (a, b) in enumerate(rows[:SHOWN_ROWS], 1)]
    if len(rows) > SHOWN_ROWS:
        lines.append(f"... ({len(rows) - SHOWN_ROWS} more rows not shown)")
    return KEY_VALUE + "\n" + "\n".join(lines) + ("\n" + IMAGED if image else "")

def read(core, page, g, task, boxes, as_table, as_pairs, image=None):
    """Ask the key-value check for a candidate grid, then read it: as_table(step) as a table, or as_pairs(step,
    context) as a key-value list; step: the "key-value-check" derivation step; context: the context lines a table
    row is given (the text above it, its caption; a text block's context doesn't hold them). boxes: the header's
    box, then each grid row's (the check's span). image: the block's crop (a PDF's), sent with the check."""
    from .failures import CallLimitReached, NotRecorded
    span = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    context = core.reader.for_table(page, span, " ".join(g.labels))
    prompt = question(g, context, bool(image))
    key = ("key-value", "table", core.content, task, hashlib.sha256(prompt.encode()).hexdigest())

    def record(status, issue):
        core.record(coverage_row(content=core.content, page=page, bbox=list(span), task=task, status=status,
                                 issues=[issue[:500]]))
        core.progress.finish(status)

    def finish(answer, error):
        core.state["pending"] -= 1
        if isinstance(error, (CallLimitReached, NotRecorded)):  # nothing learnt: the next run asks again
            return record("not_reached", str(error))
        reading = answer.reading.strip().lower() if error is None else ""
        why = f" ({answer.why})" if error is None and answer.why else ""
        if reading == "table":
            record("complete", f"Read as a table, the model's reading{why}")
            return as_table(DerivationStep(step="key-value-check", detail=f"a table, the model's reading{why}"[:300]))
        if reading == "key-value":
            record("complete", f"Read as a key-value list, the model's reading{why}")
            return as_pairs(DerivationStep(step="key-value-check",
                                           detail=f"a key-value list, the model's reading{why}"[:300]), context)
        said = str(error) if error is not None else f"an answer naming neither reading: {answer.reading!r}"
        record("partial", f"Read as a key-value list, our proposal, not confirmed ({said})")
        as_pairs(DerivationStep(step="key-value-check", detail="a key-value list, our proposal, not confirmed"), context)

    core.progress.add()
    core.state["pending"] += 1
    core.dispatch.submit(prompt, Check, [core.output / image] if image else [], key, finish)
