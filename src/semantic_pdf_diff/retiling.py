"""A partial tile read again under another tiling (docs/plans/tile-selection-2026-10-10.md, milestone 7).

The owner, 2026-10-10: "models could feasibly request an alternative tiling as a refinement option", and "It isn't
necessarily a problem to combine claims from two different tilings of the same page." So a tile whose answer is
partial, and that asks, is read again as the page's next candidate cut holds it, not in halves: the tiles of that cut
holding whole the lines and figures the tile cuts. Both readings' claims are kept, as any two tasks' are.

When it asks (the another_tiling lever, levers.py):
- **measures:** always: the measures decide alone
- **said:** where its issues say it's cut ("cut off at the bottom", "truncated"; CUT_SAID), as today's prompt lets it
- **asked:** where it names the edges cutting content, in "cut" (schema.Extraction), when a rule for tiles (RULE) asks
  it to, or its issues say it's cut

The page tests' warning (2026-10-01): a model doesn't know what it can't read, so calibration measures how often an
answer asks about tiles that cut content, and about those that don't (lab: bench/asking.py).

Where nothing the tile cuts is held whole by the other cut, or the measures find nothing cut, the tile is halved as
before; and so is a tile whose answer was continued at the claim limit (ContinueReading), whatever the mode: it's
partial for holding more than an answer has room for, not for a cut, and its halves are more room (milestone 8:
HabEx p403's dense table lost 43 of 454 values read under the other cut).
"""
import re

RULE = ('This image may be one part of a page. If an edge of the image cuts through text, a table or a figure, so '
        'part of it lies outside the image, name those edges in "cut", e.g. "cut": ["bottom", "right"]; if no edge '
        'cuts anything, "cut": [].')
CUT_SAID = re.compile(r"\bcut (?:off|through|at|by)\b|\bcut-off\b|\bcrop|truncat|clipped|\bfragment"
                      r"|outside (?:the|this) "
                      r"(?:image|crop|view|frame)|(?:beyond|past|off) the (?:image|crop|edge|frame)|partial(?:ly)? "
                      r"(?:visible|shown|cut|view)", re.I)

CUT_NOTE = "Cut at the image's"  # the coverage row's note of the edges an answer names (tasks.TaskCore.consume)

def says_cut(issues):
    """Whether an answer's issues say it's cut (CUT_SAID), its edges' note (CUT_NOTE) aside."""
    return any(CUT_SAID.search(i) for i in issues if not i.startswith(CUT_NOTE))

def asks(done, mode):
    """Whether a tile's answer asks for another tiling (see the module's note): never one continued at the claim
    limit."""
    if re.search(r"-c\d+$", done["row"].get("task", "")):
        return False
    if mode == "measures":
        return True
    said = says_cut(done["row"].get("issues", ()))
    return said or (mode == "asked" and bool(done.get("cut")))

def other_cut(settings, reader, page):
    """{"how": the page's next candidate cut by the measures (tilechoice.MEASURES), the cuts it's read with left out;
    "rects": its tiles; "sent": those read so far, by number}, or None where there's none. Once a page
    (reader.page_retilings)."""
    if page.number not in reader.page_retilings:
        from .tilechoice import MEASURES, candidates
        how = settings.tiling_of(reader, page)
        default = reader.page_choices.get(page.number, {}).get("default", how)
        found = {h: v for h, v in candidates(settings, reader, page, default).items() if h not in how.split("+")}
        ranked = sorted(found, key=lambda h: tuple(found[h][1][m] for m in MEASURES))
        reader.page_retilings[page.number] = ({"how": ranked[0], "rects": found[ranked[0]][0], "sent": set(),
                                               "read": [r for _, r, _ in settings.tiles_for(reader, page, how)]}
                                              if ranked else None)
    return reader.page_retilings[page.number]

def retiled(settings, reader, page, tag, rect, done):
    """[(tag, Rect)] for a partial tile asking for another tiling: the other cut's tiles holding whole what the tile
    cuts, most first, each "tile:p<page>:<cut><n>" by its number in that cut and read once a page, whichever tile asks
    first (so the tags don't depend on the order answers come in); None where none holds any of it, or nothing's cut
    (it's halved). A tile of the other cut inside this one, or the same as a tile of the page's own cut, isn't read."""
    from .segmentation import inked_figures
    from .tiling import SLACK, _held, cut_by
    found = other_cut(settings, reader, page)
    if found is None:
        return None
    lines = [tuple(b) for b, _ in reader.lines(page)]
    figures = [tuple(f) for f in inked_figures(settings, reader, page)]
    cut = cut_by(tuple(rect), lines + figures)[1]

    def same(a, b):
        return _held(tuple(a), tuple(b)) and _held(tuple(b), tuple(a))
    near = tuple(rect) + (-SLACK, -SLACK, SLACK, SLACK)
    usable = [i for i, r in enumerate(found["rects"])
              if not _held(tuple(r), near) and not any(same(r, x) for x in found["read"])]
    chosen, left = [], list(cut)
    while left:
        holding = {i: [b for b in left if _held(b, tuple(found["rects"][i]))] for i in usable if i not in chosen}
        best = max(holding, key=lambda i: len(holding[i]), default=None)
        if best is None or not holding[best]:
            break
        chosen.append(best)
        left = [b for b in left if b not in holding[best]]
    if not chosen:
        return None
    new = [i for i in chosen if i not in found["sent"]]
    found["sent"].update(new)
    stem = tag.rpartition(":")[0]  # "tile:p3" of "tile:p3:2" (a PDF's), "tile" of "tile:2"
    return [(f"{stem}:{found['how']}{i}", found["rects"][i]) for i in new]
