"""Tilings measured without the model (docs/plans/tile-selection-2026-10-10.md, milestone 1).

Every page of a folder's PDFs and images, tiled as a configuration's visual_regions tiles it, measured by the
product's tiling.measure: lines and words cut, text-only and blank tiles, graphics share, lines read twice, overlap,
figures not seen whole, graphics missed. A page's tiling mode is noted (bands, grid, or details), so the trials
review's table can be read off a run (`summary`). Two runs over the same pages compare page by page (`compare`).
"""
import json
from collections import defaultdict
from pathlib import Path

import pymupdf

from semantic_pdf_diff.jobs import IMAGE_EXTENSIONS, image_pdf
from semantic_pdf_diff.pages import PYMUPDF_ERRORS, shown
from semantic_pdf_diff.tiling import measure, words

COUNTS = ("tiles", "images", "lines_cut_sideways", "lines_cut_across", "words_cut", "text_only", "decoration_only",
          "blank", "lines_read_twice", "figures_not_whole")

def documents(folder, first=None):
    """(name, an open PDF) for each PDF and image under folder, sorted by path; first: only the first n pages are
    measured (the trials review measured the first 40 of each)."""
    for path in sorted(Path(folder).rglob("*")):
        extension = path.suffix.lower()
        if extension != ".pdf" and extension not in IMAGE_EXTENSIONS:
            continue
        try:
            doc = (pymupdf.open(path) if extension == ".pdf"
                   else pymupdf.open("pdf", image_pdf(path, extension, _settings())))
        except PYMUPDF_ERRORS:
            continue
        yield str(path.relative_to(folder)), doc

_DEFAULT = []
def _settings():
    if not _DEFAULT:
        from semantic_pdf_diff.settings import Settings
        _DEFAULT.append(Settings())
    return _DEFAULT[0]

def mode(settings, page):
    """How the configuration tiles a page: "bands", "grid", or "one" (no larger than a tile)."""
    if max(page.rect.width, page.rect.height) <= settings.tile_points:
        return "one"
    if getattr(settings, "tiling", "grid") == "bands" and page.rect.width <= 1.6 * settings.tile_points:
        return "bands"
    return "grid"

def measure_page(settings, reader, page, number):
    """One page's measures under settings, with its mode and size."""
    regions = settings.visual_regions(reader, page, number)
    figures = [shown(page, f.bbox) for f in reader.figures(page, number) if f.region]
    result = measure(page, regions, reader.lines(page), reader.graphics(page), words(page), figures)
    result["page"].update(mode=mode(settings, page), width=round(page.rect.width), height=round(page.rect.height))
    return result

def run(folder, settings=None, first=None, errors=None):
    """[{"file", "page", **measures}] for every page under folder (per-tile measures under "per_tile")."""
    from semantic_pdf_diff.context import Context
    settings = settings or _settings()
    rows = []
    for name, doc in documents(folder, first):
        with doc:
            reader = Context(doc, settings)
            _figures_once(reader)
            for number, page in enumerate(doc):
                if first is not None and number >= first:
                    break
                try:
                    result = measure_page(settings, reader, page, number)
                except PYMUPDF_ERRORS as e:  # a page MuPDF can't interpret
                    if errors is not None:
                        errors.append(f"{name} p{number + 1}: {e}")
                    continue
                rows.append({"file": name, "page": number + 1, **result["page"], "per_tile": result["tiles"]})
    return rows

def _figures_once(reader):
    """A page's figures found once: the figure tasks and the measure both ask (Context doesn't keep them)."""
    found, find = {}, reader.figures

    def figures(page, number):
        if number not in found:
            found[number] = find(page, number)
        return found[number]
    reader.figures = figures

def summary(rows):
    """{mode: {"pages", "pages with cuts", sums of COUNTS, "low graphics" (tiles under 5% graphics, not text only
    or blank)}}, and "all"."""
    out = defaultdict(lambda: defaultdict(float))
    for row in rows:
        for key in (row["mode"], "all"):
            s = out[key]
            s["pages"] += 1
            s["pages_with_cuts"] += row["lines_cut_sideways"] > 0
            for count in COUNTS:
                s[count] += row[count]
            s["low_graphics"] += sum(1 for t in row["per_tile"] if 0 < t["graphics_share"] < 0.05)
    return {k: {n: int(v) for n, v in s.items()} for k, s in sorted(out.items())}

def compare(before, after):
    """Page by page, the counts that changed: [{"file", "page", count: [before, after]}], and the totals."""
    index = {(r["file"], r["page"]): r for r in before}
    changed, totals = [], {c: [0, 0] for c in COUNTS}
    for row in after:
        old = index.get((row["file"], row["page"]))
        if old is None:
            continue
        diff = {c: [old[c], row[c]] for c in COUNTS if old[c] != row[c]}
        for c in COUNTS:
            totals[c][0] += old[c]
            totals[c][1] += row[c]
        if diff:
            changed.append({"file": row["file"], "page": row["page"], **diff})
    return {"totals": totals, "pages_changed": changed}

def worst(rows, measure_name, n=10):
    """The n pages highest on a measure (ties by file and page)."""
    return sorted((r for r in rows if r[measure_name]), key=lambda r: (-r[measure_name], r["file"], r["page"]))[:n]

def save(rows, path):
    Path(path).write_text(json.dumps(rows))

def load(path):
    return json.loads(Path(path).read_text())
