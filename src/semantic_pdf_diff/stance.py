"""Stance found mechanically (docs/plans/claim-context-2026-10-14.md, milestone 5): who holds a claim, where the
document's structure says so.

- **A table's holder column:** a column headed Company, Source, Proponent, Organization (and the like) names who
  holds every claim read from its row, as feature leads' summaries tabulate companies' proposals and views
  ("Company | Proposals", "Company | Y/N | Comments"). The row's cell is the holder, its reference marks left out
  ("Spreadtrum [1]"); a column of proposals makes the attitude "proposes", else it's left unsaid (a "Y/N" column
  holds a view in its value).
"""
import re

from .schema import Link

HOLDER_HEADER = re.compile(r"^\s*(?:compan(?:y|ies)|sources?|proponents?|organi[sz]ations?|part(?:y|ies)|vendors?|"
                           r"submitted by|contributors?|authors?)\s*:?\s*$", re.I)
PROPOSALS = re.compile(r"\bproposals?\b", re.I)
REFERENCE = re.compile(r"\s*\[\s*\d+(?:\s*[-–,]\s*\d+)*\s*\]")  # "Spreadtrum [1]", "[3, 5]", "[2–4]"

def table_holder(header, row):
    """(the Link a table row's claims are held by,) or () when its table has no holder column or the row's cell is
    empty. header and row: the table's column headers and the row's cells (None for a missing cell)."""
    names = [str(h or "") for h in header]
    col = next((k for k, h in enumerate(names) if HOLDER_HEADER.match(h.rsplit(" > ", 1)[-1])), None)
    if col is None or col >= len(row):
        return ()
    holder = " ".join(REFERENCE.sub("", str(row[col] or "")).split())
    if not holder:
        return ()
    attitude = "proposes" if any(PROPOSALS.search(h) for k, h in enumerate(names) if k != col) else ""
    return (Link(holder=holder[:120], attitude=attitude),)
