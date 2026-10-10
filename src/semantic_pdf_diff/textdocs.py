"""Plain text and Markdown documents (docs/plans/multi-format-adapters-2026-09-23.md, milestone 1), and Word
documents read into the same form (docxdocs.py, milestone 2).

A text file is read as pages of lines: a form feed starts a page (as in RFCs), else the file is one page. Where a
PDF task sits on a page in a box of points, a text task sits in lines: its box is (0, first line, 1, last line + 1),
so sections, the context levers and the task core work unchanged, and its claims get a TextLocator.

- **Blocks:** paragraphs between blank lines, kept as laid out (spacing intact: text written for a monospace font,
  arrows and simple structures, reaches the model as written; the owner, 2026-10-03), Markdown pipe tables (read
  row by row, as PDF tables are), and Markdown code blocks (kept whole).
- **Sections:** Markdown headings; in plain text, numbered headings in the RFC style ("7.2.  Stream Concurrency");
  failing those, fixed page ranges.
- **Page furniture:** a line repeated near the top or bottom of three or more pages (an RFC's running header and
  footer) is left out, as page furniture isn't content.
- **Not read:** images a Markdown file links (recorded as skipped), and drawings made of characters as figures.
"""
import re
from collections import defaultdict

from .textmodel import Block, TextDocument

MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
SETEXT = re.compile(r"^(=+|-+)\s*$")
# "7.2.  Stream Concurrency", "Appendix A.  Pseudocode", "A.1.  Details" at the left margin (an RFC's body is
# indented). A lone letter needs its dot: "A pump runs" and "I note" are sentences (code review 2026-10-08, B4).
RFC_HEADING = re.compile(r"^((?:\d+|Appendix [A-Z])(?:\.\d+)*|[A-Z](?:\.\d+)+|[A-Z](?=\.))\.?\s{1,4}(\S.{0,90})$")
FENCE = re.compile(r"^\s*(```|~~~)")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$")
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

def _cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]

def furniture(lines):
    """Line numbers of page furniture: a line, its digits aside, near the top or bottom of three or more pages."""
    by_page = defaultdict(list)
    for n, (page, text) in enumerate(lines, 1):
        if text.strip():
            by_page[page].append((n, text))
    edges = defaultdict(set)
    for page, rows in by_page.items():
        for n, text in rows[:2] + rows[-2:]:
            edges[re.sub(r"\d+", "#", " ".join(text.split()))].add((page, n))
    return {n for spots in edges.values() if len({p for p, _ in spots}) >= 3 for _, n in spots}

def parse(text, markdown):
    """A text file as pages, lines, blocks, headings and linked images."""
    lines, page = [], 1
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        while "\f" in raw:
            before, _, raw = raw.partition("\f")
            if before.strip():
                lines.append((page, before.rstrip()))
            page += 1
        lines.append((page, raw.rstrip()))
    skip = furniture(lines) if page >= 3 else set()
    blocks, headings, images = [], [], []
    current, fence = [], None

    def close():
        nonlocal current
        if current:
            n0, n1 = current[0][0], current[-1][0]
            blocks.append(Block(lines[n0 - 1][0], n0, n1, "\n".join(t for _, t in current)))
        current = []
    n = 0
    while n < len(lines):
        n += 1
        pg, line = lines[n - 1]
        if n in skip:
            close()
            continue
        if markdown and fence is not None:  # inside a code block: kept whole, as written
            if FENCE.match(line):
                blocks.append(Block(pg, fence[0], n, "\n".join(fence[1]), "code"))
                fence = None
            else:
                fence[1].append(line)
            continue
        if markdown and FENCE.match(line):
            close()
            fence = (n, [])
            continue
        if not line.strip() or (current and lines[current[-1][0] - 1][0] != pg):
            close()
            if not line.strip():
                continue
        if markdown:
            for alt, target in IMAGE.findall(line):
                images.append((pg, n, alt, target))
            heading = MD_HEADING.match(line)
            nxt = lines[n][1] if n < len(lines) else ""
            if heading or (line.strip() and not current and SETEXT.match(nxt) and "|" not in line):
                close()
                level, title = (len(heading.group(1)), heading.group(2)) if heading else (1 if nxt.startswith("=") else 2, line.strip())
                headings.append((pg, n, level, title))
                blocks.append(Block(pg, n, n, line.strip()))
                if not heading:
                    n += 1  # the underline
                continue
            if "|" in line and n < len(lines) and TABLE_RULE.match(lines[n][1]):
                close()
                rows, row_lines, first = [_cells(line)], [n], n
                n += 1  # the rule
                while n < len(lines) and "|" in lines[n][1] and lines[n][1].strip():
                    n += 1
                    rows.append(_cells(lines[n - 1][1]))
                    row_lines.append(n)
                blocks.append(Block(pg, first, n, "\n".join(lines[k - 1][1] for k in range(first, n + 1)), "table",
                                    rows, row_lines))
                continue
        else:
            heading = RFC_HEADING.match(line)
            if heading and not current and not line[0].isspace():
                close()
                headings.append((pg, n, heading.group(1).count(".") + 1, " ".join(line.split())))
                blocks.append(Block(pg, n, n, " ".join(line.split())))
                continue
        current.append((n, line))
    close()
    if fence is not None:  # an unclosed code block runs to the end
        blocks.append(Block(lines[fence[0] - 1][0], fence[0], len(lines), "\n".join(fence[1]), "code"))
    return TextDocument(page, lines, blocks, headings, images)
