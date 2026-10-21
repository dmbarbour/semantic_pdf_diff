"""The model labels a page's regions (docs/research/tilings-2026-10-12.md, milestone 6).

One shrunk image of the page as it is, then the page with its regions outlined, washed and numbered, what no region
holds greyed out (tilechoice.sketch, as calibrated for the tiling question). The model labels each region from a
closed list (LABELS): what it holds, or that it makes no sense read on its own (nonsense: the owner, 2026-10-10: "A
tiling that does not make sense, e.g. cut lines or part of a figure."), or something the list doesn't name (other:
"another distinct label for items of interest that aren't in the expected type list", with a few words naming it).

Calibration asks it about regions whose labels are known (lab: bench/labelling.py) before any answer is trusted.

The region_labels lever (levers.py) asks it about the tiles a page sends, once a page (Platform.sent_tiles), and acts
on the answer by rule (act): tiles of text (the text tasks read it, except on a drawing sheet: milestone 3), decoration
or blank space aren't sent, where the measures agree that they hold no graphic that counts; a nonsense tile is joined
to the neighbour it touches most; the rest are sent, and other's words are kept with the page's record. The labels the
measures can see (text alone, decoration alone, blank) are checked against them.
"""
import json

import pymupdf

from pydantic import Field

from .schema import Lenient
from .tilechoice import SKETCH_SIDE, sketch

LABELS = ("text", "table", "chart", "drawing", "photo or scan", "decoration", "blank", "mixed", "nonsense", "other")
MEANINGS = {
    "text": "paragraphs, headings, lists or notes",
    "table": "rows and columns of values",
    "chart": "a graph or plot of data",
    "drawing": "a plan, diagram, schematic or technical drawing",
    "photo or scan": "a photograph, or a scanned page or picture",
    "decoration": "only rules, borders, logos, page furniture or a background",
    "blank": "nothing, or next to nothing",
    "mixed": "two or more of the above, each a large part of the region",
    "nonsense": "makes no sense read on its own: its edges cut through lines of text, or through a figure",
    "other": "something else worth reading: say what, in a few words",
}
SYNONYMS = {"photo": "photo or scan", "scan": "photo or scan", "photograph": "photo or scan", "image": "photo or scan",
            "graph": "chart", "plot": "chart", "diagram": "drawing", "plan": "drawing", "schematic": "drawing",
            "empty": "blank", "paragraph": "text", "heading": "text", "prose": "text"}
SKIPPED = ("text", "decoration", "blank")  # not sent: the text tasks read text; the rest holds nothing to read
SEEN = {"text": "text_only", "decoration": "decoration_only", "blank": "blank"}  # labels the measures can see

def prompt(count, dimmed=True):
    """The question, for `count` regions numbered from 1 on the second image."""
    example = {"regions": {str(i): {"label": "...", "what": ""} for i in range(1, min(count, 2) + 1)}}
    return (
        f"The first image is a page of a document, shrunk. The second shows the same page with {count} "
        f"region{'s' if count > 1 else ''} outlined in colour, lightly shaded and numbered beside a corner. The "
        "outlines, shading and numbers are drawn on to show the regions: they aren't part of the page."
        + (" What no region holds is greyed out." if dimmed else "") + "\n"
        "Each region will be read on its own, close up. Label each one by what it holds, with one of these:\n"
        + "".join(f'- "{label}": {MEANINGS[label]}\n' for label in LABELS)
        + "You can't read the page's text at this size, and needn't: judge what each region holds.\n"
        f"Return only JSON, every region by its number, \"what\" a few words for \"other\" and empty otherwise: "
        f"{json.dumps(example)}")

class Labels(Lenient):
    regions: dict = Field(default_factory=dict)

def label_of(said):
    """One of LABELS from what an answer said (a label, a synonym, a label with words around it), or None."""
    text = " ".join(str(said).lower().replace("_", " ").split()).strip(" .:\"'")
    if text in LABELS:
        return text
    if text in SYNONYMS:
        return SYNONYMS[text]
    found = [x for x in LABELS if x in text]
    return found[0] if len(found) == 1 else None

def labels(answer, count):
    """{number (1-based): (label, words)} for each region the answer labels: label one of LABELS, or None where the
    answer's isn't one; words, what it said a region labelled "other" holds."""
    out = {}
    for key, value in (answer.regions or {}).items():
        digits = "".join(c for c in str(key) if c.isdigit())
        if not digits or not 1 <= int(digits) <= count:
            continue
        said, words = (value.get("label", ""), value.get("what", "")) if isinstance(value, dict) else (value, "")
        out[int(digits)] = (label_of(said), " ".join(str(words or "").split())[:120])
    return out

def ask(reader, page, rects, key):
    """The question asked about a page's regions ([Rect], numbered in order): {"labels": [label or None per region],
    "other": {number: words}, "issues"}; None where it can't be asked."""
    from .failures import ModelFailure
    from .regions import crop_name
    if reader.ask is None or reader.assets is None or not rects:
        return None
    zoom = SKETCH_SIDE / max(page.rect.width, page.rect.height)
    pixmap = reader.pixmap(page, pymupdf.Matrix(zoom, zoom))
    tag = f"vision:p{page.number}:labels"
    images = [reader.assets / crop_name(reader.stem, tag, suffix) for suffix in ("-page", "-regions")]
    images[0].write_bytes(sketch(page, pixmap=pixmap))
    images[1].write_bytes(sketch(page, rects, pixmap=pixmap, dimmed=True, title="Regions"))
    out = {"labels": [None] * len(rects), "other": {}, "issues": []}
    try:
        answer = reader.ask(prompt(len(rects)), Labels, images, key)
    except ModelFailure as e:
        out["issues"].append(f"The labels question failed ({e}); every tile sent")
        return out
    for number, (label, words) in labels(answer, len(rects)).items():
        out["labels"][number - 1] = label
        if label == "other":
            out["other"][number] = words
    missing = [str(i + 1) for i, x in enumerate(out["labels"]) if x is None]
    if missing:
        out["issues"].append(f"No label for region{'s' if len(missing) > 1 else ''} {', '.join(missing)}: sent")
    return out

def _neighbour(rect, others):
    """The index of the region in others that `rect` touches most (their shared edge or overlap, within 6 points),
    or None."""
    near = rect + (-6, -6, 6, 6)
    best, found = 0.0, None
    for i, o in enumerate(others):
        shared = near & o
        if shared.is_empty:
            continue
        reach = max(shared.width, shared.height)
        if reach > best:
            best, found = reach, i
    return found

def act(regions, found, measured=None, skipped=SKIPPED):
    """The tiles sent ([(tag, Rect, note)]) after the labels (found: ask's), and what was done: {"dropped": [tag],
    "joined": {tag: into tag}, "issues"}. measured: per tile, tiling.measure_tile's: a tile is skipped only where
    they find no graphic that counts in it (text alone, decoration alone, or nothing), and the labels they can see
    are checked against them. skipped: the labels not sent (a drawing sheet's text is: label_tiles)."""
    kept, dropped, joined, issues = [], [], {}, []
    measured = list(measured) if measured else [None] * len(regions)
    for (tag, rect, note), label, m in zip(regions, found["labels"], measured):
        if label in skipped and (m is None or any(m.get(field) for field in SEEN.values())):
            dropped.append(tag)
            continue
        if label in skipped:  # the corpus's plan sheets: small print, shrunk, looked blank (milestone 6)
            issues.append(f"{tag}: \"{label}\", but the measures find a graphic that counts: sent")
        kept.append([tag, pymupdf.Rect(rect), note, label])
    for item in [k for k in kept if k[3] == "nonsense"]:
        others = [k for k in kept if k is not item]
        i = _neighbour(item[1], [k[1] for k in others])
        if i is None:
            issues.append(f"{item[0]}: nonsense, with no neighbour to join: sent")
            continue
        others[i][1] |= item[1]
        joined[item[0]] = others[i][0]
        kept.remove(item)
    for (tag, _, _), label, m in zip(regions, found["labels"], measured):
        if m is None:
            continue
        seen = {x for x, field in SEEN.items() if m.get(field)}
        if label in SEEN and seen and label not in seen:
            issues.append(f"{tag}: \"{label}\", but the measures find " + (", ".join(sorted(seen)) or "more than that"))
        elif label not in SEEN and label is not None and seen and label not in ("nonsense", "mixed", "other"):
            issues.append(f"{tag}: \"{label}\", but the measures find {', '.join(sorted(seen))} alone")
    return [(tag, rect, note) for tag, rect, note, _ in kept], {"dropped": dropped, "joined": joined,
                                                                 "issues": issues}

def label_tiles(settings, reader, page, regions):
    """A page's tiles as sent with labels (region_labels "model"): asked once a page, the record kept in
    reader.page_labels; every tile sent where the question can't be asked or fails."""
    from .tiling import measure_tile, words
    if page.number in reader.page_labels:
        return reader.page_labels[page.number]["sent"]
    rects = [r for _, r, _ in regions]
    found = ask(reader, page, rects, ("regionlabels", f"p{page.number}", reader.stem))
    record = {"tags": [t for t, _, _ in regions], "found": found, "sent": regions, "dropped": [], "joined": {},
              "issues": []}
    reader.page_labels[page.number] = record
    if found is None:
        return regions
    lines = [(tuple(b), t) for b, t in reader.lines(page)]
    graphics = [tuple(g) for g in reader.graphics(page)]
    decoration = set(map(tuple, reader.decoration(page)))  # what the detector finds, the lever on or off
    word_boxes = [tuple(w) for w in words(page)]
    measured = [measure_tile(tuple(r), lines, word_boxes, graphics, decoration) for r in rects]
    sheet = any(f.kind == "sheet" for f in reader.figures(page, page.number))
    text_sent = sheet or not reader.text_read  # no text task reads a picture's labels
    sent, done = act(regions, found, measured, tuple(x for x in SKIPPED if x != "text") if text_sent else SKIPPED)
    record.update(sent=sent, dropped=done["dropped"], joined=done["joined"], issues=found["issues"] + done["issues"])
    return sent
