"""Raters for real revision pairs (docs/plans/revision-comparison-2026-10-02.md, milestone 3). None is absolute (no
ground truth); each sees one side of a comparison.

**A mechanical text diff.** Both files' blocks (textdocs.parse: page furniture dropped, whitespace folded) are
aligned by difflib; a block found in both is unchanged text.
- A "different" finding whose claims both sit in unchanged text is suspect: the text didn't change there, so the
  difference is the reading's, or the pairing's.
- A changed block whose numbers changed is a numeric change in the text. One that no finding (different or
  uncertain) and no claim without a counterpart touches is a possible miss.
- References aren't numbers that matter here: bracketed citations ("[RFC9001]") and section numbers ("Section 7.2")
  are left out of the comparison of a block's numbers.
- Explained findings (compare.explain) are counted by kind and by where their claims sit: a value change named in
  unchanged text is suspect, as a "different" finding there is.
"""
import difflib
import re
from collections import Counter

from semantic_pdf_diff.textdocs import parse

NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?(?![\w])")
REFERENCE = re.compile(r"\[[^\]]*\]|\b(?:Section|Sections|Appendix|Figure|Table|RFC|draft)[- ]?[\w.\-]*(?:\s*(?:and|,)\s*[\d.]+)*",
                       re.I)

def document(path):
    """A file's TextDocument as its reader sees it: plain text, Markdown, a Word document, or a zip holding one."""
    import zipfile
    from pathlib import Path
    path = Path(path)
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.endswith((".docx", ".txt", ".md")))
            return read(name, z.read(name))
    return read(path.name, path.read_bytes())

def read(name, data):
    if name.endswith(".docx"):
        from semantic_pdf_diff.docxdocs import read_docx
        return read_docx(data)
    return parse(data.decode("utf-8", errors="replace"), markdown=name.endswith(".md"))

def blocks(doc):
    """[(first line, last line, text with whitespace folded)] of a document's blocks (lines: a Word document's
    paragraphs)."""
    return [(b.first, b.last, " ".join(b.text.split())) for b in doc.blocks]

def numbers(text):
    return Counter(NUMBER.findall(REFERENCE.sub(" ", text)))

def diff(earlier, later):
    """(lines changed in the earlier, lines changed in the later, [(earlier blocks, later blocks)] replaced), of two
    TextDocuments."""
    a, b = blocks(earlier), blocks(later)
    matcher = difflib.SequenceMatcher(None, [t for *_, t in a], [t for *_, t in b], autojunk=False)
    changed_a, changed_b, replaced = set(), set(), []
    for op, i0, i1, j0, j1 in matcher.get_opcodes():
        if op == "equal":
            continue
        for first, last, _ in a[i0:i1]:
            changed_a.update(range(first, last + 1))
        for first, last, _ in b[j0:j1]:
            changed_b.update(range(first, last + 1))
        replaced.append((a[i0:i1], b[j0:j1]))
    return changed_a, changed_b, replaced

def rate(report, earlier, later):
    """A revisions report rated by the text diff (see the module's note): earlier and later, the two documents
    (document())."""
    from .controlled.comparison import sides
    changed = diff(earlier, later)
    side = sides(report)
    evidence = {e["id"]: e for e in report["evidence"]}
    span = lambda loc: loc.get("lines") or loc.get("paragraphs")  # a text file's lines, a Word document's paragraphs
    lines = lambda e: set(range(span(e["locator"])[0], span(e["locator"])[1] + 1)) if span(e["locator"]) else set()
    in_changed = lambda cid: bool(lines(evidence[cid]) & changed[side[cid]])
    findings, explained = Counter(), Counter()
    suspect = []
    for f in report["findings"]:
        where = "changed text" if in_changed(f["a"]) or in_changed(f["b"]) else "unchanged text"
        kind = "settled" if f.get("settled") else f["relation"]
        findings[f"{kind} in {where}"] += 1
        if "explanation" in f:
            explained[f"{f['explanation']['kind']} in {where}"] += 1
        if f["relation"] == "different" and where == "unchanged text":
            suspect.append(f)
    unmatched = Counter(f"{u['status']} in {'changed' if in_changed(u['id']) else 'unchanged'} text"
                        for u in report["unmatched"])
    touched = [set(), set()]  # lines a finding of note or a claim without a counterpart covers, by side
    for f in report["findings"]:
        if f["relation"] in ("different", "uncertain"):
            touched[side[f["a"]]] |= lines(evidence[f["a"]])
            touched[side[f["b"]]] |= lines(evidence[f["b"]])
    for u in report["unmatched"]:
        touched[side[u["id"]]] |= lines(evidence[u["id"]])
    numeric, unseen = 0, []
    for olds, news in changed[2]:
        before = sum((numbers(t) for *_, t in olds), Counter())
        after = sum((numbers(t) for *_, t in news), Counter())
        if before == after:
            continue
        numeric += 1
        spans = ({n for f, l, _ in olds for n in range(f, l + 1)}, {n for f, l, _ in news for n in range(f, l + 1)})
        if not (spans[0] & touched[0] or spans[1] & touched[1]):
            unseen.append({"earlier": " ".join(t for *_, t in olds)[:300], "later": " ".join(t for *_, t in news)[:300],
                           "numbers_gone": sorted((before - after).elements())[:10],
                           "numbers_new": sorted((after - before).elements())[:10]})
    show = lambda cid: {k: evidence[cid][k] for k in ("entity", "attribute", "value", "unit", "conditions")} | \
        {"lines": evidence[cid]["locator"].get("lines") or evidence[cid]["locator"].get("paragraphs")}
    return {"claims": [sum(1 for s in side.values() if s == 0), sum(1 for s in side.values() if s == 1)],
            "changed_blocks": len(changed[2]), "changed_lines": [len(changed[0]), len(changed[1])],
            "findings": dict(sorted(findings.items())), "unmatched": dict(sorted(unmatched.items())),
            **({"explained": dict(sorted(explained.items()))} if explained else {}),
            "suspect_differences": len(suspect), "numeric_changes": numeric,
            "numeric_changes_unseen": len(unseen),
            "pairs_judged": report["retrieval"]["attempted_pairs"],
            "settled": sum(1 for f in report["findings"] if f.get("settled")),
            "groupings": dict(sorted(Counter(g["kind"] for g in report.get("groupings", [])).items())),
            "examples": {"suspect": [{"a": show(f["a"]), "b": show(f["b"]), "rationale": f["rationale"][:200],
                                      **({"kind": f["explanation"]["kind"], "why": f["explanation"]["rationale"][:200]}
                                         if "explanation" in f else {})}
                                     for f in suspect[:15]],
                         "unseen": unseen[:15]}}
