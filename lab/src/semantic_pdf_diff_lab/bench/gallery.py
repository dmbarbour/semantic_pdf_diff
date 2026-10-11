"""A gallery of the worst pages' tilings, on an offline page (docs/plans/tile-selection-2026-10-10.md, milestone 2).

Pages are picked by the measures of a run (bench/tiling.py): for each failure, the pages highest on its measure, at
most one per document so one drawing set doesn't fill a row, from the development pages only (a path holding
"heldout/" is never picked). Named cases join them (NAMED: pages met by eye in the trials and the bug plan).

Each page is drawn under each configuration given (today's settings, and later the candidate levers), its tiles
outlined and numbered and its figure tasks dashed, beside that configuration's measures. The page and its pictures go
into one folder; nothing is sent to a model.
"""
from pathlib import Path

import pymupdf

from semantic_pdf_diff.html_pages import esc, page as html_page

def _low_graphics(r):
    return sum(1 for t in r["per_tile"] if 0 < t["graphics_share"] < 0.05)

def _cut_share(r):  # pages up to 1,000 points wide (slides, landscape, wider than Letter) with 10 lines or more
    return (round(r["lines_cut_sideways"] / r["lines"], 2) if r.get("lines", 0) >= 10 and r.get("width", 0) <= 1000
            else 0)

# (key, the failure it shows, how many pages, the page's value): counts favour large pages (drawings, posters), so
# the share of a page's lines cut ranks slides and landscape text too; lines cut across are a band page's failure
FAILURES = (
    ("lines_cut_sideways", "Lines cut sideways (grid tiles down the middle of lines)", 6, None),
    ("cut_share", "Pages up to 1,000 points wide: lines cut sideways per line on the page (a line cut by two tiles "
     "counts twice)", 6, _cut_share),
    ("lines_cut_across", "Band pages: lines cut across (a band's edge through a line)", 4,
     lambda r: r["lines_cut_across"] if r["mode"] == "bands" else 0),
    ("text_only", "Text-only tiles (they repeat the text tasks)", 4, None),
    ("lines_read_twice", "Lines read twice (tiles overlapping)", 4, None),
    ("low_graphics", "Tiles sent for a sliver of graphics (under 5% of the tile)", 4, _low_graphics),
    ("figures_not_whole", "Figures no tile or figure task holds whole", 4, None),
)

# (path under the samples folder, page, why): pages met by eye
NAMED = (
    ("nasa-flagship-concepts/habex/HabEx-final-report.pdf", 4, "Trials finding 5: logo, rules and side bars send "
     "every band; the old refinement cut every line"),
    ("nasa-flagship-concepts/independent-assessment/LCIT-final-report-2019.pdf", 27, "Trials finding 5: a text-only "
     "slide sent as four tiles, each cutting every line"),
    ("solar-decathlon-2013/teams/calg/jury/eng_calg.pdf", 1, "A page slightly wider than Letter (712 points): a grid"),
    ("solar-decathlon-2013/teams/calg/calg_cd.pdf", 21, "A drawing sheet among the most text-only tiles; the old "
     "refinement cut did better on a calg table"),
)

COLOURS = ((0.85, 0.20, 0.20), (0.15, 0.45, 0.85), (0.10, 0.60, 0.30), (0.80, 0.50, 0.05), (0.55, 0.25, 0.75),
           (0.05, 0.60, 0.65))
SIDE = 1100  # pixels: a picture's longer side

def pick(rows, failures=FAILURES):
    """{measure: [rows]}: each failure's worst development pages, one per document."""
    out = {}
    for measure, _, n, value in failures:
        value = value or (lambda r, measure=measure: r[measure])
        seen, chosen = set(), []
        for r in sorted((r for r in rows if "heldout/" not in r["file"]), key=lambda r: (-value(r), r["file"], r["page"])):
            if value(r) <= 0 or r["file"] in seen:
                continue
            seen.add(r["file"])
            chosen.append({**r, "value": value(r)})
            if len(chosen) == n:
                break
        out[measure] = chosen
    return out

def draw(page, regions, path, side=SIDE):
    """The page as displayed with its tiles outlined and numbered and its figure tasks dashed, as a PNG."""
    rect = page.rect
    zoom = side / max(rect.width, rect.height)
    with pymupdf.open() as out:
        sheet = out.new_page(width=rect.width, height=rect.height)
        # the page as rendered (its /Rotate applied, as the tiles' coordinates are); show_pdf_page draws it unrotated
        sheet.insert_image(sheet.rect, pixmap=page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False))
        width = max(1.0, max(rect.width, rect.height) / side * 2.5)
        tiles = [(tag, r) for tag, r, _ in regions if tag.startswith("tile")]
        for i, (tag, r) in enumerate(tiles):
            colour = COLOURS[i % len(COLOURS)]
            sheet.draw_rect(r, color=colour, fill=colour, width=width, fill_opacity=0.08, stroke_opacity=0.9)
        for i, (tag, r) in enumerate(tiles):  # labels last, so no tile's wash covers another's number
            size = max(8.0, max(rect.width, rect.height) / side * 14)
            label = pymupdf.Rect(r.x0, r.y0, r.x0 + size * (0.7 * len(tag.split(":")[1]) + 0.8), r.y0 + size * 1.2)
            sheet.draw_rect(label, color=None, fill=COLOURS[i % len(COLOURS)], fill_opacity=0.9)
            sheet.insert_text((label.x0 + size * 0.3, label.y1 - size * 0.3), tag.split(":")[1], fontsize=size,
                              color=(1, 1, 1))
        for tag, r, _ in regions:
            if tag.startswith("figure"):
                sheet.draw_rect(r, color=(0.1, 0.1, 0.1), width=width, dashes=f"[{3 * width}] 0")
        sheet.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).save(str(path))

SHOWN = ("tiles", "lines_cut_sideways", "lines_cut_across", "words_cut", "text_only", "lines_read_twice", "overlap",
         "figures_not_whole", "graphics_missed")

def build(samples, rows, configurations, out, named=NAMED):
    """Write out/index.html and its pictures. samples: the folder rows' paths are under; rows: a run's measures
    (bench/tiling.run); configurations: {label: Settings}. Returns the number of pages drawn."""
    from semantic_pdf_diff.context import Context
    from .tiling import measure_page
    out = Path(out)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    picked = pick(rows)
    sections = [(title, [(r["file"], r["page"], f"{measure.replace('_', ' ')}: {r['value']}") for r in picked[measure]])
                for measure, title, _, _ in FAILURES]
    present = [(f, p, why) for f, p, why in named if (Path(samples) / f).exists()]
    sections.insert(0, ("Named cases (met by eye)", present))
    body, drawn = ["<h1>Tile selection: the worst pages</h1>",
                   f"<p class='muted'>Development pages only; configurations: {esc(', '.join(configurations))}. "
                   "Tiles outlined and numbered; figure tasks dashed; the overview isn't drawn.</p>"], 0
    for title, pages in sections:
        body.append(f"<h2>{esc(title)}</h2>")
        for file, number, why in pages:
            with pymupdf.open(Path(samples) / file) as doc:
                page = doc[number - 1]
                cells = []
                for label, settings in configurations.items():
                    reader = Context(doc, settings)
                    regions = settings.visual_regions(reader, page, number - 1)
                    measured = measure_page(settings, reader, page, number - 1)["page"]
                    name = f"{drawn:03d}-{len(cells)}.png"
                    draw(page, regions, out / "pages" / name)
                    figures = ", ".join(f"{k.replace('_', ' ')} {measured[k]}" for k in SHOWN if measured.get(k))
                    cells.append(f"<figure><a href='pages/{name}'><img src='pages/{name}' loading='lazy' alt=''></a>"
                                 f"<figcaption><b>{esc(label)}</b> ({esc(measured['mode'])}): {esc(figures)}"
                                 "</figcaption></figure>")
                size = f"{round(page.rect.width)} × {round(page.rect.height)} pt"
                drawn += 1
            body.append(f"<section><h3>{esc(file)}, page {number} ({size})</h3><p class='muted'>{esc(why)}</p>"
                        f"<div class='row'>{''.join(cells)}</div></section>")
    style = ("body{font:15px/1.45 system-ui,sans-serif;margin:0 auto;max-width:1400px;padding:16px}"
             ".muted{color:var(--muted)}section{background:var(--card);border:1px solid var(--line);"
             "border-radius:8px;padding:12px;margin:12px 0}h3{margin:0 0 4px;font-size:15px}"
             ".row{display:flex;gap:12px;flex-wrap:wrap}figure{margin:0;flex:1 1 420px;min-width:0}"
             "img{width:100%;height:auto;border:1px solid var(--line);background:#fff}figcaption{font-size:13px}")
    (out / "index.html").write_text(html_page("Tile selection gallery", "".join(body), style))
    return drawn
