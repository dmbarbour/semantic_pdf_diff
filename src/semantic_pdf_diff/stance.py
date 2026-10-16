"""Stance found mechanically (docs/plans/claim-context-2026-10-14.md, milestone 5): who holds a claim, where the
document's structure says so.

- **A table's holder column:** a column headed Company, Source, Proponent, Organization (and the like) names who
  holds every claim read from its row, as feature leads' summaries tabulate companies' proposals and views
  ("Company | Proposals", "Company | Y/N | Comments"). The row's cell is the holder, its reference marks left out
  ("Spreadtrum [1]"); a column of proposals makes the attitude "proposes", else it's left unsaid (a "Y/N" column
  holds a view in its value).
- **A holder given once** (the carried_holders lever): a company named on its first row only, the rows under it
  blank, as merged cells print; a blank holder cell takes the nearest one above it.
- **A view as the holder's stance** (the view_attitudes lever): a held claim whose value is a yes or a no ("CMCC |
  support for Proposal 3.2.4 | Y") is the holder's view of a proposition, not a value of the holder: the attitude
  supports or opposes, the proposition the entity, the attribute "support", the holder out of both names.
"""
import re

from .schema import Link

HOLDER_HEADER = re.compile(r"^\s*(?:compan(?:y|ies)|sources?|proponents?|organi[sz]ations?|part(?:y|ies)|vendors?|"
                           r"submitted by|contributors?|authors?)\s*:?\s*$", re.I)
PROPOSALS = re.compile(r"\bproposals?\b", re.I)
REFERENCE = re.compile(r"\s*\[\s*\d+(?:\s*[-–,]\s*\d+)*\s*\]")  # "Spreadtrum [1]", "[3, 5]", "[2–4]"

def _cell(row, col):
    """A row's holder cell as a name: its reference marks left out, its spaces tidied ("" when it has none)."""
    return " ".join(REFERENCE.sub("", str(row[col] or "") if col < len(row) else "").split())

def table_holder(header, row, above=(), carried=False):
    """(the Link a table row's claims are held by,) or () when its table has no holder column or the row's cell is
    empty (with carried, and a row above names one: the nearest above's). header and row: the table's column headers
    and the row's cells (None for a missing cell); above: the rows over it, nearest last."""
    names = [str(h or "") for h in header]
    col = next((k for k, h in enumerate(names) if HOLDER_HEADER.match(h.rsplit(" > ", 1)[-1])), None)
    if col is None or col >= len(row):
        return ()
    holder = _cell(row, col) or (next((h for h in (_cell(r, col) for r in reversed(above)) if h), "")
                                 if carried else "")
    if not holder:
        return ()
    attitude = "proposes" if any(PROPOSALS.search(h) for k, h in enumerate(names) if k != col) else ""
    return (Link(holder=holder[:120], attitude=attitude),)

YES = {"y", "yes", "support", "supported", "supports", "agree", "agreed", "ok"}
NO = {"n", "no", "not supported", "not support", "object", "objects", "disagree", "oppose", "opposed"}
VIEW = r"(?:support(?:ed)?|agreement|agree|view|position|stance|acceptance)(?:\s+status)?"
VIEW_OF = re.compile(rf"^\s*(?:the\s+)?{VIEW}(?:\s+(?:for|with|of|on|to))?\s+(?P<what>\S.*?)\s*$", re.I)
VIEW_AFTER = re.compile(rf"^\s*(?P<what>\S.*?)\s+{VIEW}\s*$", re.I)
VIEW_ALONE = re.compile(rf"^\s*{VIEW}\s*$", re.I)

def _fold(text):
    return " ".join(re.findall(r"\w+", str(text).casefold()))

def _without(text, holder):
    """text with the holder's name taken out ("KDDI support status" -> "support status")."""
    if not holder:
        return text
    out = re.sub(rf"(?i)(?<!\w){re.escape(holder)}(?!\w)(?:'s)?", " ", text)
    return " ".join(out.split())

def as_view(claim):
    """A held claim whose value is a yes or a no, as its holder's view of the proposition (the module's notes); any
    other claim as it is."""
    if not claim.stance:
        return claim
    value = _fold(claim.value)
    attitude = "supports" if value in YES else "opposes" if value in NO else ""
    if not attitude:
        return claim
    link = claim.stance[0]
    entity, attribute = _without(claim.entity, link.holder), _without(claim.attribute, link.holder)
    if not _fold(entity):  # the holder as the entity: the proposition is in the attribute
        m = VIEW_OF.match(attribute) or VIEW_AFTER.match(attribute)
        entity, attribute = ((m.group("what"), "support") if m else
                             (claim.entity, "support" if VIEW_ALONE.match(attribute) else attribute))
    elif VIEW_ALONE.match(attribute) or not _fold(attribute):
        attribute = "support"
    stance = [link.model_copy(update={"attitude": attitude}), *claim.stance[1:]]
    return claim.model_copy(update={"entity": entity[:160], "attribute": attribute[:160] or "support",
                                    "stance": stance})
