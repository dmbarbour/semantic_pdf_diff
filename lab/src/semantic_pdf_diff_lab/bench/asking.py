"""Calibration: does a tile's answer ask for another tiling when the tile cuts content? (docs/research/
tilings-2026-10-12.md, milestone 7.)

The page tests' warning (2026-10-01): prompted only to zoom "as needed", neither model did, because a model doesn't
know what it can't read. So before the another_tiling lever's said and asked modes are trusted, tiles whose cuts are
known are read as the product reads a tile (extract.PdfReading's image tasks, under the controlled corpus's settings,
refinement off), and their answers scored on whether they ask.

The tiles, on each page of the controlled corpus with a known-good tiling (calibration.good):
- **whole:** the known-good tiling's tiles, which cut no line or figure
- **cut:** tiles of three known-bad tilings (calibration's midline, shifted and figure split) that the measures find
  cutting a line or a figure (tiling.cut_by), with the edges they cut it at: the one cutting most of each kind, up to
  CUT_TILES a page

The arms (ARMS):
- **today:** today's prompt (another_tiling off). Does the answer say it's cut (retiling.says_cut), or call itself
  partial?
- **asked:** with the rule (another_tiling asked). Does it name an edge, and the edges the measures find?

The lever acts only where the measures find a cut, so an ask about a whole tile costs nothing; what an arm is worth is
how often it asks about tiles that cut content (PASS, set before the run).
"""
import contextlib
import hashlib
from pathlib import Path

import pymupdf

from . import calibration

CUT_KINDS = ("midline", "shifted", "figure split")
CUT_TILES = 3  # cut tiles a page, at most
ARMS = {"today": "off", "asked": "asked"}  # the another_tiling setting each arm reads with
# set by judgement before the run: an arm is worth using if it asks about half the tiles cutting content, and about
# few of the whole ones (which the measures would veto in any case)
PASS = {"asks_when_cut": 0.5, "asks_when_whole": 0.2}

def tiles(p):
    """[{"kind", "rect", "edges", "cut"}] for a page (calibration.Page): its whole tiles, then its cut ones; cut,
    how many lines and figures the tile cuts. [] without a known-good tiling."""
    from semantic_pdf_diff.tiling import _inked, cut_by
    found = calibration.tilings(p)
    if not found:
        return []
    lines = [tuple(b) for b, _ in p.lines]
    figures = [_inked(tuple(f), lines, [tuple(g) for g in p.content]) for f in p.figures]
    whole, seen = [], set()
    for r in found["good"]:
        edges, cut = cut_by(tuple(r), lines + figures)
        if not cut:
            whole.append({"kind": "good", "rect": [round(v, 1) for v in r], "edges": [], "cut": 0})
            seen.add(tuple(round(v, 1) for v in r))
    cut_tiles = []
    for kind in CUT_KINDS:
        best = None
        for r in found.get(kind, ()):
            edges, cut = cut_by(tuple(r), lines + figures)
            rect = [round(v, 1) for v in r]
            if cut and tuple(rect) not in seen and (best is None or len(cut) > best["cut"]):
                best = {"kind": kind, "rect": rect, "edges": edges, "cut": len(cut)}
        if best:
            seen.add(tuple(best["rect"]))
            cut_tiles.append(best)
    return whole + cut_tiles[:CUT_TILES]

def cases(corpus, only=None):
    """{pdf path: {page index: [tiles' dicts]}} over the corpus's PDFs; only: page ids (lcc-s1-clean-p1) to keep."""
    out = {}
    for path in sorted(Path(corpus).glob("*.pdf")):
        with pymupdf.open(path) as doc:
            for number in range(len(doc)):
                if only and f"{path.stem}-p{number + 1}" not in only:
                    continue
                found = tiles(calibration.Page(path.name, doc, number))
                if found:
                    out.setdefault(path, {})[number] = found
    return out

@contextlib.contextmanager
def only_tiles(chosen):
    """A PDF read for its chosen tiles alone: each page's image tasks are those tiles ("tile:p<n>:<i>", by their
    order), and nothing else is read. chosen: {pdf file name: {page index: [rect]}}."""
    from semantic_pdf_diff.extract import PdfReading
    step = PdfReading.page

    def reading(self, number, page):
        rects = chosen.get(Path(self.doc.name).name, {}).get(page.number, ())
        self.regions[number] = [(f"tile:{i}", pymupdf.Rect(r), "") for i, r in enumerate(rects)]
        self.vision(number, page)
    PdfReading.page = reading
    try:
        yield
    finally:
        PdfReading.page = step

def settings(model, arm, base):
    """The reading's settings: the corpus's (base), refinement and situating off, the arm's another_tiling."""
    from semantic_pdf_diff_lab.eval.clients import evaluator_settings
    return evaluator_settings(model, {**base, "refinement_depth": 0, "situate": False, "another_tiling": ARMS[arm]})

def read_all(folder, client, found):
    """{tile id (lcc-s1-clean-p1-t0): {**tile, "page", "status", "issues", "claims", "said", "named"}} for every
    case tile read with client (its settings an arm's): said, its issues say it's cut; named, the edges its answer
    names. Crops go to folder/reads/assets."""
    from semantic_pdf_diff.jobs import Job, run_jobs
    from semantic_pdf_diff.retiling import CUT_NOTE, says_cut
    from semantic_pdf_diff.schema import edges
    out, jobs = {}, {}
    for path in found:
        content = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}.pdf"
        jobs[path] = Job(content, lambda path=path: path)
    with only_tiles({path.name: {n: [t["rect"] for t in ts] for n, ts in pages.items()}
                     for path, pages in found.items()}):
        run_jobs([[job] for job in jobs.values()], Path(folder) / "reads", client)  # every document at once
        for path, pages in found.items():
            rows = {r["task"]: r for r in jobs[path].state["result"][1]}
            for n, ts in pages.items():
                for i, t in enumerate(ts):
                    row = rows.get(f"tile:p{n + 1}:{i}", {"status": "missing", "issues": [], "claims": 0})
                    issues = row.get("issues") or []
                    named = [e for x in issues if x.startswith(CUT_NOTE) for e in edges(x)]
                    out[f"{path.stem}-p{n + 1}-t{i}"] = {
                        **t, "page": f"{path.stem}-p{n + 1}", "status": row["status"], "issues": issues,
                        "claims": row.get("claims", 0), "said": says_cut(issues),
                        "named": named}
    return out

# --- scoring ------------------------------------------------------------------------------------

def _share(a, b):
    return round(a / b, 3) if b else None

def answered(read):
    """The tiles whose answer came back (unrecorded ones, in a replay, left out)."""
    return {k: t for k, t in read.items() if t["status"] in ("complete", "partial")}

def asking(t, arm):
    return t["said"] or (arm == "asked" and bool(t["named"]))

def score(read, arm):
    """An arm's profile from read_all's tiles."""
    done = answered(read)
    whole = [t for t in done.values() if t["kind"] == "good"]
    cut = [t for t in done.values() if t["kind"] != "good"]
    out = {"tiles": len(read), "answered": len(done), "whole": len(whole), "cut": len(cut),
           "asks_when_cut": _share(sum(asking(t, arm) for t in cut), len(cut)),
           "asks_when_whole": _share(sum(asking(t, arm) for t in whole), len(whole)),
           "partial_when_cut": _share(sum(t["status"] == "partial" for t in cut), len(cut)),
           "partial_when_whole": _share(sum(t["status"] == "partial" for t in whole), len(whole)),
           "said_when_cut": _share(sum(t["said"] for t in cut), len(cut)),
           "said_when_whole": _share(sum(t["said"] for t in whole), len(whole))}
    if arm == "asked":
        naming = [t for t in cut if t["named"]]
        out["named_when_cut"] = _share(len(naming), len(cut))
        out["named_when_whole"] = _share(sum(bool(t["named"]) for t in whole), len(whole))
        out["an_edge_right"] = _share(sum(bool(set(t["named"]) & set(t["edges"])) for t in naming), len(naming))
        named = [e for t in naming for e in t["named"]]
        out["edges_named_not_cut"] = _share(sum(e not in t["edges"] for t in naming for e in t["named"]), len(named))
    out["by_kind"] = {k: {"tiles": len(ts), "asks": _share(sum(asking(t, arm) for t in ts), len(ts)),
                          "partial": _share(sum(t["status"] == "partial" for t in ts), len(ts))}
                      for k in ("good", *CUT_KINDS) for ts in [[t for t in done.values() if t["kind"] == k]] if ts}
    whole_asks = out["asks_when_whole"] if out["asks_when_whole"] is not None else 1
    out["passes"] = (out["asks_when_cut"] or 0) >= PASS["asks_when_cut"] and whole_asks <= PASS["asks_when_whole"]
    return out
