"""Tilings measured without the model (docs/plans/tile-selection-2026-10-10.md, milestone 1).

Every page of a folder's PDFs and images, tiled as a configuration's visual_regions tiles it, measured by the
product's tiling.measure: lines and words cut, text-only and blank tiles, graphics share, lines read twice, overlap,
figures not seen whole, graphics missed. A page's tiling mode is noted (bands, grid, or details), so the trials
review's table can be read off a run (`summary`). Two runs over the same pages compare page by page (`compare`).
With the model, a run's store says how its image tasks were answered (`answers`).
"""
import json
from collections import defaultdict
from pathlib import Path

import pymupdf

from semantic_pdf_diff.jobs import IMAGE_EXTENSIONS, image_pdf
from semantic_pdf_diff.pages import PYMUPDF_ERRORS, shown
from semantic_pdf_diff.tiling import detail, measure, words

COUNTS = ("tiles", "images", "lines_cut_sideways", "lines_cut_across", "words_cut", "text_only", "decoration_only",
          "blank", "lines_read_twice", "figures_not_whole")

def documents(folder, first=None, exclude=()):
    """(name, an open PDF) for each PDF and image under folder, sorted by path, but those whose path holds any of
    `exclude` (such as "heldout/"); first: only the first n pages are measured (the trials review measured the first
    40 of each)."""
    for path in sorted(Path(folder).rglob("*")):
        extension = path.suffix.lower()
        if extension != ".pdf" and extension not in IMAGE_EXTENSIONS:
            continue
        if any(part in str(path.relative_to(folder)) for part in exclude):
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
    """How the configuration tiles a page: "bands", the cut of a page not in bands ("grid", "snapped", "xycut"), or
    "one" (no larger than a tile)."""
    if max(page.rect.width, page.rect.height) <= settings.tile_points:
        return "one"
    if (getattr(settings, "tiling", "grid") == "bands"
            and page.rect.width <= getattr(settings, "band_width", 1.6) * settings.tile_points):
        return "bands"
    return getattr(settings, "tile_cut", "grid")

def measure_page(settings, reader, page, number):
    """One page's measures under settings, with its mode and size. Decoration is found whatever the settings
    (segmentation.decoration), so text-only tiles count alike in every configuration."""
    regions = settings.visual_regions(reader, page, number)
    figures = [shown(page, f.bbox) for f in reader.figures(page, number) if f.region]
    result = measure(page, regions, reader.lines(page), reader.graphics(page), words(page), figures,
                     reader.decoration(page))
    tiles = [r for tag, r, _ in regions if tag.startswith("tile")]
    for t, r in zip(result["tiles"], tiles):
        t["detail"] = detail(r, settings.render_side(r))
    result["page"].update(mode=mode(settings, page), width=round(page.rect.width), height=round(page.rect.height),
                          detail=min((t["detail"] for t in result["tiles"]), default=None))
    choice = reader.page_choices.get(page.number)  # tile_choice's: the cut chosen, and those no other beats
    if choice:
        result["page"]["choice"] = {k: choice[k] for k in ("default", "chosen", "front", "clear", "scores")}
        result["page"]["mode"] = choice["chosen"]
    return result

def run(folder, settings=None, first=None, errors=None, exclude=()):
    """[{"file", "page", **measures}] for every page under folder (per-tile measures under "per_tile")."""
    from semantic_pdf_diff.context import Context
    settings = settings or _settings()
    rows = []
    for name, doc in documents(folder, first, exclude):
        with doc:
            reader = Context(doc, settings)
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

IMAGE_KINDS = ("tile", "figure", "overview")

def answers(store, key=None):
    """The image tasks' answers in a run's store, by kind (tile, refined tile, figure, overview): tasks, those
    answered with no claim, those whose issues complain of fragments or crops (refinement.COMPLAINT), claims; with a
    controlled document's key, the tiles' claims scored (right, loose, misbound...; controlled.score)."""
    from .refinement import COMPLAINT, _stored, child
    rows, claims, _ = _stored(store)
    out = {}
    tile_claims = []
    for task, row in rows.items():
        kind = task.split(":")[0]
        if kind not in IMAGE_KINDS:
            continue
        kind += " refined" if child(task) else ""
        found = claims.get(task, [])
        c = out.setdefault(kind, dict.fromkeys(("tasks", "empty", "complaints", "claims"), 0))
        c["tasks"] += 1
        c["empty"] += not found
        c["complaints"] += bool(COMPLAINT.search(" ".join(row.get("issues", []))))
        c["claims"] += len(found)
        if kind.startswith("tile"):
            tile_claims += found
    if key is not None:
        from .controlled import score
        if tile_claims:
            result = score(key, tile_claims)
            out["tile outcomes"], out["tile facts right"] = result["outcomes"], result["found_right"]
        result = score(key, [c for found in claims.values() for c in found])
        out["outcomes"], out["facts right"], out["facts"] = (result["outcomes"], result["found_right"],
                                                             len(key["facts"]))
    return out

def read(paths, configurations, out, base, fixture, max_cost, ledger=None, tags=None):
    """Each document read alone (the same document both sides: extraction only) under each configuration, its answers
    recorded into `fixture` (only queries it doesn't hold are asked). paths: PDFs, each scored against the answer key
    beside it (NAME.key.json) if there is one; configurations: {label: overrides}; base: the settings file the
    overrides apply to, with the default levers (a candidate's lever is off when absent, so queries are the same).
    Returns {label: {document: answers}} and the spend, stopping when max_cost is reached."""
    from semantic_pdf_diff import ledger as ledgers, pipeline
    from semantic_pdf_diff.levers import DEFAULT_LEVERS
    found, spent = {}, 0.0
    for label, overrides in configurations.items():
        for path in map(Path, paths):
            left = max_cost - spent
            if left <= 0:
                return found, spent
            before = ledgers.spent(ledger, **(tags or {})) if ledger else 0.0
            settings = pipeline.settings_from(base, levers=list(DEFAULT_LEVERS), situate=False, max_cost=round(left, 4),
                                              **overrides)
            options = pipeline.RunOptions(mode="proposals", fixture=fixture, fixture_mode="record-new")
            if ledger:
                options.ledger, options.ledger_tags = ledger, {**(tags or {}), "run": f"{label}:{path.stem}"}
            folder = Path(out) / label / path.stem
            code = pipeline.attempt(pipeline.compare_paths, path, path, folder, settings, options)
            spent += (ledgers.spent(ledger, **(tags or {})) - before) if ledger else 0.0
            key_path = path.with_name(path.stem + ".key.json")
            key = json.loads(key_path.read_text()) if key_path.exists() else None
            from .recording import cut
            unfinished = cut(folder)  # cut by the cap: resumed, not scored (the determinism review, D6)
            found.setdefault(label, {})[path.stem] = ({"exit": code, "cut": unfinished} if unfinished else
                                                      {"exit": code, **answers(folder / "store.sqlite", key)})
    return found, spent

def save(rows, path):
    Path(path).write_text(json.dumps(rows))

def load(path):
    return json.loads(Path(path).read_text())
