"""A PDF table's structure, asked of a model as rules where the heuristics leave suspects (the one table model's
structure rules; the owner, 2026-10-07: "comprehensible suggestions/rules about how to work around confusing
formatting, with feedback similar to how we approach claims rules").

After the heuristics (tables.ruled_rows, tables.pdf_parts), each line of a table part is tagged with the signals
that it may not be a row of its own (SIGNALS). A part with a suspect line is asked once (STRUCTURE), with the
table's image: the model answers with rules from a closed vocabulary (a condition built from the signals, or lines
named, and an action: ACTIONS) and two or three lines as it reads them in the image, one of them the worst suspect
(the image check, aimed). The rules are applied mechanically, so cells are only regrouped, never retyped; the
examples are compared with what the rules give, a mismatch is shown back once, and the outcome is reviewed ("is this
your final answer", up to table_review times) as claims rules are. Failing, the heuristics' parts are kept.
"""
import hashlib
import re
import statistics

from pydantic import Field, field_validator

from .models import DerivationStep, Lenient, coverage_row

UNIT = re.compile(r"^[(\[]?\s*(µm|μm|nm|mm|cm|m|km|in|ft|mas|%|°|°c|°f|k|w|kw|mw|hp|gpm|psi|psig|rpm|kg|lb|s|ms|hz|khz|"
                  r"mhz|v|kv|a|db)\s*[)\]]?$", re.I)

# The signals, each a condition a rule may name. "first cell empty" alone, in a line without a digit, is settled by
# the heuristics (pdf_grid joins it to the line above) and isn't a suspect by itself.
SIGNALS = ("no rule above", "first cell empty", "only its first cell", "units only", "words under numbers",
           "half height", "a word cut by a column line")
CUT = "a word cut by a column line"
COLUMN_ACTIONS = ("split column", "join columns")  # acting on columns, in every row
ACTIONS = ("join above", "join header", "section", "new table", "not table", "keep") + COLUMN_ACTIONS

def _filled(row):
    return [c for c in row if c is not None and str(c).strip()]

def _digit(row):
    return any(ch.isdigit() for c in _filled(row) for ch in str(c))

def signals(header, body, boxes, styles=None, rules=None, cuts=None):
    """For each body line, the signals that it continues the line above (the header, for the first) rather than
    being a row, or that its cells aren't the image's. styles: each line's look (tables.Marks.styles), a line styled
    unlike most being a section row, not a stray label; rules: the y of the drawn rules, used when the part's
    boundaries are mostly ruled; cuts: {line: the column boundaries a word in it is cut by} (tables.Marks.cuts; 0
    the header)."""
    lines = [header] + list(body)
    tops = [b[1] if b else None for b in boxes]
    ruled = None
    if rules is not None and tops and None not in tops:
        ruled = [any(abs(t - y) <= 1.5 for y in rules) for t in tops]
        if sum(ruled) < max(3, 0.4 * len(ruled)) or all(ruled):
            ruled = None
    heights = [b[3] - b[1] for b in boxes if b]
    usual = statistics.median(heights) if heights else 0
    seen = [s for s in styles or [] if s is not None]
    common = max(seen, key=seen.count) if seen else None
    out = []
    for i, row in enumerate(body):
        above, cells, tags = lines[i], _filled(row), []
        if ruled is not None and not ruled[i]:
            tags.append("no rule above")
        if cells and not _filled(row[:1]):
            tags.append("first cell empty")
        lone = len(cells) == 1 and bool(_filled(row[:1])) and len(row) > 2
        if lone and not (styles and i < len(styles) and styles[i] is not None and styles[i] != common):
            tags.append("only its first cell")  # unless styled as a section row
        if cells and all(UNIT.match(str(c).strip()) for c in cells):
            tags.append("units only")
        elif cells and not lone and not _digit(row) and _digit(above) and len(cells) < len(_filled(above)):
            tags.append("words under numbers")
        if usual and i < len(boxes) and boxes[i] and boxes[i][3] - boxes[i][1] < 0.6 * usual:
            tags.append("half height")
        if cuts and cuts.get(i + 1):
            tags.append(CUT)
        out.append(tags)
    return out

def suspect(tags, row):
    return bool(tags) and not (tags == ["first cell empty"] and not _digit(row))

def _texts(value):
    """Numbers given where text is asked for (a line as 7, a cell as 1024), as text."""
    if isinstance(value, list):
        return [v if isinstance(v, str) else str(v) for v in value]
    return value if isinstance(value, str) or value is None else str(value)

class StructureRule(Lenient):
    action: str = Field(default="", max_length=20)
    when: list[str] = Field(default_factory=list, max_length=6)
    lines: list[str] = Field(default_factory=list, max_length=60)
    column: str = Field(default="", max_length=4)
    into: list[str] = Field(default_factory=list, max_length=6)
    why: str = Field(default="", max_length=200)

    _numbers = field_validator("lines", "into", "column", mode="before")(lambda cls, v: _texts(v))

class LineExample(Lenient):
    line: str = Field(default="", max_length=10)
    cells: list[str] = Field(default_factory=list, max_length=30)

    _numbers = field_validator("line", "cells", mode="before")(lambda cls, v: _texts(v))

class Structure(Lenient):
    """A model's answer to the structure query (STRUCTURE)."""
    rules: list[StructureRule] = Field(default_factory=list, max_length=20)
    examples: list[LineExample] = Field(default_factory=list, max_length=6)
    why: str = Field(default="", max_length=400)

class StructureReview(Lenient):
    """A model's review of what its structure rules gave (REVIEWING)."""
    verdict: str = Field(default="", max_length=20)
    problems: list[str] = Field(default_factory=list, max_length=10)
    structure: Structure | None = None

STRUCTURE = """These are the lines of one table from a PDF, as a parser read its text layer into lines and cells. The
parser can be wrong about where a row ends: a cell's text over two lines may come out as two rows, a header over two
lines as a header and a row, a label as a row of its own. The table's image is attached: read its rows there.

THE LINES (numbered; H is the header; cells parted by " | "). Tags in [brackets] are signals that a line may not be
a row of its own:
{lines}

Answer with rules that regroup the lines into the table's real rows. A rule has an action and says which lines it
acts on: "when", signals that must all hold for a line, and/or "lines", line numbers. The signals: {signals}.
A line named in a rule's "lines" follows that rule; any other line follows the first rule whose "when" all hold; a line no rule
fits stays a row. Actions:
- "join above": the line's cells join the line above's, cell by cell (a wrapped cell, a unit under its value)
- "join header": the line joins the header, cell by cell (a header over two lines)
- "section": the line names a section of the rows under it
- "new table": the line is the header of another table under this one
- "not table": the line isn't part of the table (a note, a caption)
- "keep": the line is a row of its own (said of a suspect line to settle it)
- "split column": "column" (a letter, A first) holds two or more values in each cell; "into" names the new columns
- "join columns": "column" and the one after it ("C"), or a range ("C:E"), are one column in the image: their cells
  joined in every row, without a space where a column line cut a word (lines tagged with where they're cut)
Cells are never retyped: rules only regroup them.

Also copy two or three rows from the image as they read after your rules, empty cells left out, one of them the
row holding line {worst}: "examples": [{{"line": "<the number of its first line, or H>", "cells": ["...", "..."]}}].
They are checked against what your rules give.

Return JSON only: {{"rules": [{{"action": "join above", "when": ["first cell empty"], "lines": [], "why": "..."}}],
"examples": [...], "why": "<one sentence>"}}. If every line is a row as it is: "rules": [].
"""

REVIEWING = """You wrote structure rules for a table from a PDF; below is what they gave. Is this your final answer?
Compare it with the table's image. Answer "keep" if the rows are right; else "revise", with the problems and your
revised answer in full ("structure": the same form as before).
Return JSON only: {"verdict": "keep" | "revise", "problems": ["..."], "structure": {...}}
"""

def _letter(k):
    return chr(ord("A") + k) if k < 26 else f"A{chr(ord('A') + k - 26)}"

def _line(row):
    return " | ".join("" if c is None else " ".join(str(c).split()) for c in row)

def show_lines(header, body, tags, cuts=None):
    width = max(len(r) for r in [header] + list(body))
    cut = lambda i: (f" (cut at {', '.join(f'{_letter(k)}|{_letter(k + 1)}' for k in sorted(cuts[i]))})"
                     if cuts and cuts.get(i) else "")
    out = ["    " + " | ".join(_letter(k) for k in range(width)),
           f"H:  {_line(header)}" + (f"   [{CUT}]{cut(0)}" if cuts and cuts.get(0) else "")]
    for i, (row, t) in enumerate(zip(body, tags), 1):
        out.append(f"{i}:  {_line(row)}" + (f"   [{'; '.join(t)}]" if t else "") + cut(i))
    return "\n".join(out)

def _span(column, width):
    """A "join columns" rule's columns: "C" (C and D) or "C:E", as (first, last) indices, or None."""
    letters = [_letter(c) for c in range(width)]
    a, _, b = column.strip().upper().partition(":")
    if a not in letters or (b and b not in letters):
        return None
    first, last = letters.index(a), letters.index(b) if b else letters.index(a) + 1
    return (first, last) if first < last < width else None

def _joined(upper, lower):
    out = []
    for k in range(max(len(upper), len(lower))):
        a = upper[k] if k < len(upper) else None
        b = lower[k] if k < len(lower) else None
        texts = [" ".join(str(t).split()) for t in (a, b) if t is not None and str(t).strip()]
        out.append(" ".join(texts) if texts else (a if a is not None else b))
    return out

def _box(a, b):
    if a is None or b is None:
        return a or b
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))

def _plain(text):
    import unicodedata
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return "".join(ch for ch in text if ch.isalnum() or ch in ".-+%/")

def _number(text):
    text = str(text).strip()
    return int(text) if text.isdigit() else None

NO_ROWS = "the rules leave no rows"

class Applied:
    """What structure rules gave: parts [(header, rows, boxes)], each row's lines (origins, numbered from 1; 0 the
    header), lines read apart ("not table"), and what each rule did."""
    def __init__(self):
        self.parts, self.origins, self.heads, self.apart, self.did, self.misfits = [], [], [], [], {}, []
        self.unsupported = []  # joins of a body row's separate values, no word cut between them

    def holding(self, number, body):
        """The row (or header) a line ended up in; 0 is the header."""
        if number == 0:
            return self.parts[0][0] if self.parts else None
        if number - 1 in self.apart:
            return body[number - 1]
        for (head, rows, _), origins, heads in zip(self.parts, self.origins, self.heads):
            if number in heads:
                return head
            for row, lines in zip(rows, origins):
                if number in lines:
                    return row
        return None

def _example_line(example):
    line = re.sub(r"(?i)^\s*line\s*", "", example.line).strip()
    return 0 if line.upper() == "H" else _number(line)

def problems(answer, n, width, tags):
    """What's wrong with structure rules, before they're applied: unknown actions, signals, lines or columns."""
    wrong = []
    for k, rule in enumerate(answer.rules, 1):
        action = rule.action.strip().lower()
        if action not in ACTIONS:
            wrong.append(f"rule {k}: unknown action {rule.action!r}")
            continue
        unknown = [w for w in rule.when if w.strip().lower() not in SIGNALS]
        if unknown:
            wrong.append(f"rule {k}: unknown signals {unknown} (known: {', '.join(SIGNALS)})")
        bad = [x for x in rule.lines
               if x.strip().upper() != "H" and (_number(x) is None or not 1 <= _number(x) <= n)]  # H: ignored
        if bad:
            wrong.append(f"rule {k}: no lines {bad} (the lines are 1 to {n})")
        if action == "split column":
            col = rule.column.strip().upper()
            if col not in [_letter(c) for c in range(width)] or len(rule.into) < 2:
                wrong.append(f"rule {k}: a split names a column (A to {_letter(width - 1)}) and two or more new columns")
        elif action == "join columns":
            if _span(rule.column, width) is None:
                wrong.append(f"rule {k}: a join names a column with one after it (\"C\"), or a range (\"C:E\"), within A to "
                             f"{_letter(width - 1)}")
        elif not rule.when and not rule.lines:
            wrong.append(f"rule {k}: it says neither \"when\" nor \"lines\"")
    return wrong

def apply(answer, header, body, boxes, tags, cuts=None):
    """Structure rules applied to a part's lines. cuts: as signals takes them, to join cut words without a space."""
    out = Applied()
    act, named = {}, {}
    for rule in answer.rules:
        action = rule.action.strip().lower()
        if action in COLUMN_ACTIONS:
            continue
        for x in rule.lines:
            if _number(x) is not None and _number(x) not in named:
                named[_number(x)] = (action, rule)
    for i in range(1, len(body) + 1):
        if i in named:
            act[i] = named[i]
            continue
        for rule in answer.rules:
            when = [w.strip().lower() for w in rule.when]
            if rule.action.strip().lower() not in COLUMN_ACTIONS and when and all(w in tags[i - 1] for w in when):
                act[i] = (rule.action.strip().lower(), rule)
                break
    head, rows, bxs, origins, heads = list(header), [], [], [], []
    header_open = True

    def close():
        if rows:
            out.parts.append((head, rows, bxs))
            out.origins.append(origins)
            out.heads.append(heads)

    for i, row in enumerate(body, 1):
        action, rule = act.get(i, ("keep", None))
        box = boxes[i - 1] if i - 1 < len(boxes) else None
        if action == "join above" and not rows and header_open:
            action = "join header"
        if action == "join header" and not header_open:
            out.misfits.append(f"line {i}: joins the header, but rows come before it; kept a row")
            action = "keep"
        if action == "join above" and not rows:
            action = "keep"
        if rule is not None:
            out.did.setdefault(id(rule), (rule, []))[1].append(i)
        if action == "join header":
            head = _joined(head, row)
            heads.append(i)
        elif action == "join above":
            rows[-1] = _joined(rows[-1], row)
            bxs[-1] = _box(bxs[-1], box)
            origins[-1].append(i)
        elif action == "new table":
            close()
            head, rows, bxs, origins, heads, header_open = list(row), [], [], [], [i], True
        elif action == "not table":
            out.apart.append(i - 1)
        elif action == "section":
            rows.append([" ".join(_filled(row))] + [""] * (len(row) - 1))
            bxs.append(box)
            origins.append([i])
            header_open = False
        else:
            rows.append(list(row))
            bxs.append(box)
            origins.append([i])
            header_open = False
    close()
    width = max(len(r) for r in [header] + list(body))
    index = list(range(width))  # each column's place after joins (splits name columns as they were shown)
    joins = [(rule, _span(rule.column, width)) for rule in answer.rules
             if rule.action.strip().lower() == "join columns" and _span(rule.column, width)]
    for rule, (first, last) in sorted(joins, key=lambda j: -j[1][0]):  # columns joined, in every part
        joined_rows = []

        def join(row, lines, body_row=True):
            cut = set().union(*((cuts or {}).get(line, set()) for line in lines))
            text, pieces, before = "", 0, None
            for k in range(first, last + 1):
                piece = " ".join(str(row[k]).split()) if k < len(row) and row[k] is not None else ""
                if piece:  # no space where a boundary between this piece and the one before cut a word
                    glued = before is not None and any(j in cut for j in range(before, k))
                    if before is not None and not glued and body_row and cuts is not None:
                        out.unsupported.append(f"columns {rule.column.upper()} hold separate values in the row of "
                                               f"line {lines[0]} ({row[before]!r}, {piece!r}; no word cut between "
                                               "them): join only columns a word is cut across")
                    text += ("" if not text or glued else " ") + piece
                    pieces, before = pieces + 1, k
            return list(row[:first]) + [text] + list(row[last + 1:]), pieces > 1

        parts = []
        for p, ((head_, rows_, bxs_), origins, heads) in enumerate(zip(out.parts, out.origins, out.heads)):
            head_, _ = join(head_, ([0] if p == 0 else []) + heads, body_row=False)
            new = []
            for row, lines in zip(rows_, origins):
                row, both = join(row, lines)
                new.append(row)
                if both:
                    joined_rows.append(row[0])
            parts.append((head_, new, bxs_))
        out.parts = parts
        out.did[id(rule)] = (rule, joined_rows)
        index = [i if i <= first else first if i <= last else i - (last - first) for i in index]
    for rule in answer.rules:  # columns split, in every part
        if rule.action.strip().lower() != "split column":
            continue
        letters = [_letter(c) for c in range(width)]
        if rule.column.strip().upper() not in letters:
            continue
        k, into, split_rows = index[letters.index(rule.column.strip().upper())], [t.strip() for t in rule.into], []
        parts = []
        for head_, rows_, bxs_ in out.parts:
            head_ = list(head_[:k]) + into + list(head_[k + 1:])
            new = []
            for row in rows_:
                cell = str(row[k] or "") if k < len(row) else ""
                pieces = cell.split(" / ") if len(cell.split(" / ")) == len(into) else cell.split()
                if len(pieces) != len(into):
                    pieces = [cell] + [""] * (len(into) - 1)
                    if cell.strip():
                        out.misfits.append(f"{row[0]}: column {rule.column} not split ({cell!r})")
                else:
                    split_rows.append(row[0])
                new.append(list(row[:k]) + pieces + list(row[k + 1:]))
            parts.append((head_, new, bxs_))
        out.parts = parts
        out.did[id(rule)] = (rule, split_rows)
    return out

def example_mismatches(answer, applied, body, worst=None):
    """Each example against what the rules gave for the row (or header) holding its line, and the row holding the
    worst suspect among them."""
    wrong = []
    rows = [applied.holding(_example_line(e), body) for e in answer.examples if _example_line(e) is not None]
    if worst is not None and not any(r is not None and r is applied.holding(worst, body) for r in rows):
        wrong.append(f"the row holding line {'H' if worst == 0 else worst} isn't among the examples: copy it from "
                     "the image")
    for example in answer.examples:
        number = _example_line(example)
        if number is None or not 0 <= number <= len(body):
            wrong.append(f"example line {example.line!r} isn't a line of the table")
            continue
        got = applied.holding(number, body)
        if got is None:  # a part left without rows
            continue
        mine, theirs = [str(c) for c in got if c and str(c).strip()], [c for c in example.cells if str(c).strip()]
        if _plain("".join(mine)) != _plain("".join(theirs)):
            wrong.append(f"line {number}: your rules give {' | '.join(mine)[:160]}; your example "
                         f"{' | '.join(theirs)[:160]}")
    return wrong

def cells_parted_otherwise(answer, applied, body):
    """Examples whose text agrees with the rules' row but whose cells are parted otherwise (the image's column lines
    against the parser's): noted with the outcome."""
    out = []
    for example in answer.examples:
        number = _example_line(example)
        got = applied.holding(number, body) if number is not None and 0 <= number <= len(body) else None
        if got is None:
            continue
        mine, theirs = [str(c) for c in got if c and str(c).strip()], [c for c in example.cells if str(c).strip()]
        if [_plain(c) for c in mine] != [_plain(c) for c in theirs]:
            out.append(f"line {number}'s cells parted otherwise in the image: {' | '.join(theirs)[:120]}")
    return out

def describe(applied):
    """The rules in words, each with the lines it acted on."""
    out = []
    for rule, lines in applied.did.values():
        action = rule.action.strip().lower()
        if action == "split column":
            what = f"column {rule.column.upper()} split into {', '.join(rule.into)}"
        elif action == "join columns":
            what = f"columns {rule.column.upper()} joined"
        else:
            cond = " and ".join(f'"{w}"' for w in rule.when)
            what = f"{cond + ': ' if cond else ''}{action}"
        out.append(f"{what} ({len(lines)}: {', '.join(map(str, lines[:12]))}{'...' if len(lines) > 12 else ''})")
    return "; ".join(out)

def review_question(asked, answer, applied, header, body, tags):
    shown_lines = asked[asked.index("THE LINES"):asked.index("Answer with")].rstrip()
    lines = [REVIEWING, "THE LINES (as you were shown them):", shown_lines, "YOUR ANSWER:", answer.model_dump_json(exclude_defaults=True), "WHAT IT GAVE:"]
    for p, ((head, rows, _), origins) in enumerate(zip(applied.parts, applied.origins), 1):
        lines.append(f"table {p}, header: {_line(head)}")
        shown = 0
        for row, origin in zip(rows, origins):
            changed = len(origin) > 1 or row != list(body[origin[0] - 1])
            doubtful = any(suspect(tags[i - 1], body[i - 1]) for i in origin)
            if (changed or doubtful) and shown < 12:
                lines.append(f"  lines {'+'.join(map(str, origin))}: {_line(row)}")
                shown += 1
    if applied.apart:
        lines.append("not part of the table: " + ", ".join(str(i + 1) for i in applied.apart))
    if applied.misfits:
        lines.append("not applied: " + "; ".join(applied.misfits[:6]))
    return "\n".join(lines)

def read(core, page, task, header, body, boxes, styles, rules, images, then, cuts=None):
    """Ask a part's structure when a line is suspect, then call then(parts, step, apart, table): parts as
    tables.pdf_parts gives them, step a DerivationStep saying how the structure was settled (None: as the heuristics
    left it), apart the body lines read by themselves ("not table"), table False where the model reads no table
    (rules leaving no rows: a chart, a floor plan). images: a callable giving the table's crop(s), relative to the
    output folder, rendered only for a part that's asked."""
    from .llm import CallLimitReached, NotRecorded
    tags = signals(header, body, boxes, styles, rules, cuts)
    flagged = [i + 1 for i, (t, row) in enumerate(zip(tags, body)) if suspect(t, row)]
    if cuts and cuts.get(0):  # the header's words cut by a column line
        flagged.append(0)
    if not flagged:
        return then([(header, body, boxes)], None, [], True)
    worst = max(flagged, key=lambda i: (len(tags[i - 1]) if i else 1, -i))
    images = images()
    width = max(len(r) for r in [header] + list(body))
    asked = STRUCTURE.format(lines=show_lines(header, body, tags, cuts),
                             signals=", ".join(f'"{s}"' for s in SIGNALS), worst="H" if worst == 0 else worst)
    span = boxes and all(boxes) and (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
                                     max(b[3] for b in boxes))

    def ask(prompt, name, model, role, finish):
        key = (role, "table", core.content, name, hashlib.sha256(prompt.encode()).hexdigest())

        def done(answer, error):
            core.state["pending"] -= 1
            finish(answer, error)

        core.progress.add()
        core.state["pending"] += 1
        core.dispatch.submit(prompt, model, [core.output / x for x in images], key, done)

    def record(name, status, issues):
        core.record(coverage_row(content=core.content, page=page, bbox=list(span) if span else None, task=name,
                                 status=status, issues=issues, claims=0), [])
        core.progress.finish(status)

    def heuristic(name, status, why, table=True):
        record(name, status, [f"Structure as the heuristics left it: {why}"[:500]])
        then([(header, body, boxes)], None, [], table)

    def check(answer):
        wrong = problems(answer, len(body), width, tags)
        if wrong:
            return wrong, None
        applied = apply(answer, header, body, boxes, tags, cuts)
        if not applied.parts:
            return [NO_ROWS], None
        if applied.unsupported:  # a column join the page's words don't bear out
            return applied.unsupported[:3], None
        return example_mismatches(answer, applied, body, worst), applied

    def first(answer, error):
        if error is not None:
            return failed(task, error)
        wrong, applied = check(answer)
        if not wrong:
            return review(answer, applied)
        if wrong == [NO_ROWS]:  # the model reads no table here: asking again won't change that
            return heuristic(task, "complete", f"{NO_ROWS} ({answer.why or 'no reason given'})", table=False)
        again = (asked + "\nYOUR EARLIER ANSWER:\n" + answer.model_dump_json(exclude_defaults=True)
                 + "\nITS PROBLEMS:\n" + "\n".join(f"- {w}" for w in wrong) + "\nAnswer again, mending them.")
        record(task, "partial", [f"The structure asked again: {'; '.join(wrong)}"[:500]])
        ask(again, task + ":again", Structure, "table-structure", second)

    def second(answer, error):
        if error is not None:
            return failed(task + ":again", error)
        wrong, applied = check(answer)
        if wrong:
            return heuristic(task + ":again", "partial", "the rules failed twice (" + "; ".join(wrong) + ")")
        review(answer, applied)

    def review(answer, applied, round_=1, notes=()):
        cap = core.s.reviews_tables()
        if round_ > cap or not answer.rules:
            return use(answer, applied, list(notes))
        prompt = review_question(asked, answer, applied, header, body, tags)
        name = task + ":review" + (str(round_) if round_ > 1 else "")

        def finish(result, error):
            if error is not None or result is None:
                return use(answer, applied, list(notes) + [f"Not reviewed: {error}"[:300]])
            if result.verdict.strip().lower() != "revise" or result.structure is None:
                return use(answer, applied, list(notes) + ["Reviewed: kept"])
            same = lambda s: [r.model_dump(exclude={"why"}) for r in s.rules]
            if same(result.structure) == same(answer):
                return use(answer, applied, list(notes) + ["Reviewed: a revision changing nothing, kept"])
            wrong, revised = check(result.structure)
            if wrong:
                return use(answer, applied, list(notes) + [f"Reviewed: a revision with problems ({'; '.join(wrong)}), "
                                                           "the last rules passing the checks kept"[:400]])
            note = f"Reviewed: revised ({'; '.join(result.problems)})"[:400]
            if round_ >= cap:
                return use(result.structure, revised, list(notes) + [note, f"Review cap ({cap}) reached"])
            review(result.structure, revised, round_ + 1, list(notes) + [note])

        ask(prompt, name, StructureReview, "table-structure-review", finish)

    def failed(name, error):
        if isinstance(error, (CallLimitReached, NotRecorded)):
            record(name, "not_reached", [str(error)])
            return then([(header, body, boxes)], None, [], True)
        heuristic(name, "failed", f"the structure query failed ({error})")

    def use(answer, applied, notes):
        said = describe(applied) or "every line a row as it is"
        parted = cells_parted_otherwise(answer, applied, body)
        record(task, "complete", [f"Structure by rules: {said}"[:500]] + notes[:6] + applied.misfits[:4] + parted[:2])
        step = DerivationStep(step="table-structure", detail=f"by rules a model wrote: {said}"[:400])
        then(applied.parts, step, applied.apart, True)

    ask(asked, task, Structure, "table-structure", first)
