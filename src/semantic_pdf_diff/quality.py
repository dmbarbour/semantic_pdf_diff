"""How well a run read each page (the run-quality report, milestone 1, docs/plans/run-quality-2026-11-06.md; the owner,
2026-10-09: "I'm beginning to believe that having some sort of quality heuristics spot-check for runtime behavior would
be useful for both confidence decisions and part of the report."). What the run recorded of its own reading, counted
by file and page, each kind apart: no model asked, and no score made of them (no rater is absolute; a count is a
place to look, not a verdict).
"""
import re

from .retiling import CUT_NOTE, says_cut
from .tablerules import ALONE
from .tablestructure import AS_LEFT
from .tasks import REJECTED, UNQUOTED

# each kind counted: (key, its column, what it counts)
KINDS = (
    ("failed", "Failed", "requests that failed after their retries (of the page's requests): nothing was read there"),
    ("unread", "Not read", "requests not sent, the run stopped before them (of the page's requests)"),
    ("short", "Cut short", "answers the model said were incomplete (of the page's requests)"),
    ("dropped", "Quotes not found", "claims dropped, their quote not in the text they were read from (of the claims "
                                    "its text gave, kept or dropped)"),
    ("unverified", "Quotes unverified", "claims kept, their quote not in the page's text layer (a picture's) or in "
                                        "their text (unquoted) (of the page's claims checked)"),
    ("cut", "Text cut", "image tiles whose answer said text was cut at their edges (of the page's images)"),
    ("tables", "Tables as mended", "table parts read without the model's structure, or rows without its rules"),
    ("doubted", "Doubted", "claims the second pass suspected misread, about another subject or out of place (of the "
                           "page's claims)"),
    ("reread", "Read again otherwise", "claims whose place, read again by the second pass, gave something else (of "
                                       "the page's claims)"),
)
NAMES = {key: name for key, name, _ in KINDS}
# what each kind is counted of, on its page: its requests, its image tiles, the claims its text gave (kept or
# dropped), its pictures' claims checked against the text layer, its claims kept
OF = {"failed": "requests", "unread": "requests", "short": "requests", "cut": "images", "dropped": "from text",
      "unverified": "checked", "doubted": "claims", "reread": "claims"}
TABLE_NOTE = re.compile(rf"^(?:{re.escape(AS_LEFT)}|every row {ALONE}|Row .* {ALONE}): ")

def _row_counts(r):
    """{kind: n} for one coverage row."""
    issues, out = r.get("issues") or [], {}
    dropped = sum(1 for i in issues if i == REJECTED)
    if dropped:
        out["dropped"] = dropped
    if r["status"] == "failed":
        out["failed"] = 1
    elif r["status"] == "not_reached":
        out["unread"] = 1
    elif r["status"] == "partial" and not dropped and not any(i.startswith("Continued: ") or i == UNQUOTED
                                                              for i in issues):
        out["short"] = 1  # a row a quote failed made partial is counted as its drops (the two aren't told apart)
    if says_cut(issues) or any(i.startswith(CUT_NOTE) for i in issues):
        out["cut"] = 1
    tables = sum(1 for i in issues if TABLE_NOTE.match(i))
    if tables:
        out["tables"] = tables
    return out

def pages(data):
    """Each page the run read, with what went wrong there: [{"content", "page", "counts": {kind: n}, "claims": n,
    "of": {what a kind is counted of (OF): n}}], in the files' order, then the pages'; a page of a file without pages
    is None."""
    found = {}

    def at(content, page):
        return found.setdefault((content, page), {"content": content, "page": page, "counts": {}, "claims": 0,
                                                  "of": {}})

    def add(place, counts):
        for kind, n in counts.items():
            place["counts"][kind] = place["counts"].get(kind, 0) + n
    def base(place, *names):
        for name in names:
            place["of"][name] = place["of"].get(name, 0) + 1
    for r in data.get("coverage", []):
        place = at(r["content"], r.get("page"))
        counts = _row_counts(r)
        add(place, counts)
        base(place, "requests", *(["images"] if r.get("image") else []))
        place["of"]["from text"] = place["of"].get("from text", 0) + counts.get("dropped", 0)
    evidence = {e["id"]: e for e in data.get("evidence", [])}
    for e in evidence.values():
        place = at(e["content"], e["locator"].get("page"))
        place["claims"] += 1
        base(place, "claims", *(["checked"] if e.get("quote_verified") is not None else []),
             *(["from text"] if not e.get("image") else []))
        if e.get("quote_verified") is False:
            add(place, {"unverified": 1})
    for c in (data.get("commentary") or {}).get("entries", []):
        kind = ("doubted" if c["kind"] == "suspicion" else
                "reread" if c["kind"] == "reread" and c.get("relation") != "as_claimed" else None)
        for claim in c["claims"][:1] if kind else ():  # the claim it's about
            e = evidence.get(claim)
            if e is not None:
                add(at(e["content"], e["locator"].get("page")), {kind: 1})
    order = {}
    for f in sorted(data.get("files", []), key=lambda f: (f["source"], f["path"])):
        order.setdefault(f["content"], len(order))
    return sorted(found.values(), key=lambda p: (order.get(p["content"], len(order)), p["content"],
                                                 p["page"] is None, p["page"] or 0))

def said(p, kind):
    """A page's count of a kind, with what it's counted of: "4 of 12"; "" for none."""
    n = p["counts"].get(kind)
    if not n:
        return ""
    of = p["of"].get(OF.get(kind, ""))
    return f"{n} of {of}" if of else str(n)

def totals(found):
    """{kind: n} over pages, and how many pages had any."""
    out = {}
    for p in found:
        for kind, n in p["counts"].items():
            out[kind] = out.get(kind, 0) + n
    return out, sum(1 for p in found if p["counts"])

def lines(data):
    """What a run's reading went wrong at, in a line, for the log as it ends; none where nothing did."""
    found = pages(data)
    counted, troubled = totals(found)
    if not troubled:
        return []
    said = ", ".join(f"{NAMES[k].lower()} {counted[k]}" for k, _, _ in KINDS if counted.get(k))
    return [f"Read with problems: {troubled} of {len(found)} pages ({said}): the report's Reading view lists them"]
