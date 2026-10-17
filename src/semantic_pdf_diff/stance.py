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
- **A yes-or-no column read without the model** (the view_rows lever): in a table with a holder column and a column
  of yes and no ("Company | Y/N | Comments"), a row's yes or no is its holder's view of the item the text above the
  table last names ("Proposal 2.2", "Question 4"), read even where the reader gives no claim of it (a bare "Y"
  row, or a "N" row whose comment holds a counter-proposal).
- **A hedge apart from scope** (the hedges_apart lever): a hedge a reader put in a claim's conditions ("tentative",
  "working assumption", "preliminary estimates", "expected") is the source's stated uncertainty, not the claim's
  scope: moved to its uncertainty, where a hedge on the document's own claim lives for now (the owner, 2026-10-16).
- **The reader's links** (the read_holders lever asks for them): a row's holder column still names the holder, the
  reader adding an attitude the row doesn't give; elsewhere the reader's holders, their reference marks left out.
"""
import re

from .schema import DerivationStep, Link

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

def merged(row, read):
    """A claim's stance from its row's holder column (row) and the reader's answer (read): the row's holders, each
    given the reader's first attitude where it has none (the reader names a holder as printed, "Xiaomi [12]", and a
    summary renumbers its references); without a row's, the reader's, reference marks left out."""
    if row:
        attitude = next((x.attitude for x in read if x.attitude), "")
        return [x.model_copy(update={"attitude": attitude}) if attitude and not x.attitude else x for x in row]
    return [x.model_copy(update={"holder": " ".join(REFERENCE.sub("", x.holder).split()) or x.holder}) for x in read]

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

VIEW_HEADER = re.compile(r"^\s*(?:y\s*/\s*n|yes\s*/\s*no|support(?:ed)?|agree(?:d|ment)?|accept(?:ed|ance)?)\s*\??\s*$",
                         re.I)
YES_NO = {"y": "Y", "yes": "Y", "n": "N", "no": "N"}
# A claim's derivation step where its table row's yes or no was read without the model (the view_rows lever)
VIEW_COLUMN = DerivationStep(step="view-column", detail="the row's yes or no as its holder's view of the item named "
                                                        "above the table, read without the model")
# An item a table of views is about: a label and its number, the last the text above the table names ("Proposal
# 3.1.1", "Question 4", "Observation 2"); a table's or a figure's own number isn't one.
ITEM = re.compile(r"\b(?P<item>(?:Proposal|Question|Item|Issue|Observation|Recommendation|Option|Agreement|"
                  r"Conclusion|Topic)\s+\d+(?:\.\d+)*[a-z]?)\b")

def is_yes_no(value):
    """Whether a value is a bare yes or no ("Y", "No")."""
    return _fold(value) in YES_NO

def view_of(header, row, context):
    """The view a table row's yes-or-no cell states, as a claim (entity: the item the text above names; attribute
    "support"; value: the cell), or None: no holder column, no yes-or-no column, a cell that's neither, or no item
    named above (context: the row's context lines, "Above the table: ..." among them)."""
    from .schema import Claim
    if not table_holder(header, row):
        return None
    names = [" ".join(str(h or "").rsplit(" > ", 1)[-1].split()) for h in header]
    col = next((k for k, h in enumerate(names) if VIEW_HEADER.match(h)), None)
    cell = str(row[col] or "").strip() if col is not None and col < len(row) else ""
    above = next((line for line in str(context or "").splitlines() if line.startswith("Above the table:")), "")
    items = ITEM.findall(above)
    if not is_yes_no(cell) or not items:
        return None
    return Claim(entity=items[-1][:160], attribute="support", value=cell, kind="table", quote=cell, confidence=0.9)

# A hedge as readers put it in conditions: the phrase, with a "status" or "per" before it ("status: Working
# assumption", "per preliminary estimates")
HEDGE = re.compile(r"(?:\bstatus\s*(?:is|:)?\s*)?\b(working assumption|tentative(?:ly)?|preliminary(?: estimates?)?|"
                   r"provisional(?:ly)?|expected|likely|TBD|TBC|FFS)\b", re.I)

def hedges_apart(claim):
    """The claim with the hedges its conditions hold moved to its uncertainty (after any it states), the
    conditions' leftover separators tidied; a claim with none as it is."""
    found = [m.group(1) for m in HEDGE.finditer(claim.conditions)]
    if not found:
        return claim
    rest = HEDGE.sub(" ", claim.conditions)
    rest = re.sub(r"\s*([,;:])\s*(?=[,;:]|$)", "", rest)  # a separator left with nothing after it
    rest = re.sub(r"^\s*[,;:]\s*", "", " ".join(rest.split()))
    said = "; ".join(x for x in [claim.uncertainty, *found] if x)
    return claim.model_copy(update={"conditions": rest.strip(), "uncertainty": said[:200]})
