"""Vision profiles: what a model reads, measured, and the reading plans that follow from it.

The eye tests measure the smallest glyph a model reads at each image size, and the largest it
still reads; the page tests measure how that carries over to whole pages cut into tiles. A profile
holds both, and the planner picks, for a page and the sizes of its text, the cheapest way to cut it
up and render it that the profile says reads everything. The owner, 2026-09-30: "All these eye
tests are for a reason, so we must use them to select and adapt to models in some way."
"""
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

CAP = 0.718           # Helvetica's cap height per em: text layers give font sizes, the tests capitals
SIDES = (None, 1152, 864, 720, 576, 504, 420, 360, 288, 216, 144)  # tile sides tried (points; None: the whole page)
RENDERS = (768, 1024, 1536)  # render sizes tried (the long side, px)
MIN_PLANS = 4         # page-test plans needed before their calibration is trusted

@dataclass
class Profile:
    responder: str
    relative: dict = field(default_factory=dict)  # {(w, h): smallest glyph read, per 1000 px of the image's side}
    large: dict = field(default_factory=dict)     # {glyph px: share read} above the threshold fit's range
    calibration: float = 1.0                      # page reading / card prediction (below 1: pages read smaller)
    plans_measured: int = 0                       # page-test plans behind the calibration

    @property
    def ceiling_px(self):
        """The largest capitals (px) the model still reads reliably, or None when no measured size failed."""
        from .eyetest import PASS
        failing = [g for g, share in self.large.items() if share is not None and share < PASS]
        if not failing:
            return None
        passing = [g for g, share in self.large.items() if share is not None and share >= PASS and g < min(failing)]
        return max(passing) if passing else 16.0

    def threshold_px(self, w, h):
        """The smallest capitals (px) read at 90% in a w × h px image."""
        size = min(self.relative, key=lambda s: abs(math.log(s[0] * s[1] / (w * h))))
        return self.relative[size] * math.sqrt(w * h) / 1000

def card_prediction(profile, w_pt, h_pt, px):
    """The smallest font (points) the cards predict is read at 90% in a w × h point region rendered with its
    long side at px, before calibration."""
    scale = px / max(w_pt, h_pt)
    return profile.threshold_px(w_pt * scale, h_pt * scale) / scale / CAP

def smallest_font(profile, w_pt, h_pt, px):
    return card_prediction(profile, w_pt, h_pt, px) * profile.calibration

def load(responder, eyes, pages=None):
    """A responder's profile from the eye test's results.json and, if given, the page test's."""
    data = json.loads(Path(eyes).read_text(encoding="utf-8"))["models"].get(responder)
    if not data:
        return None
    summary = data["summary"]
    profile = Profile(responder,
                      {tuple(map(int, k.split("x"))): v for k, v in summary["relative"].items() if v},
                      {float(g): v for g, v in summary.get("large", {}).items()})
    if pages and Path(pages).exists():
        measured = json.loads(Path(pages).read_text(encoding="utf-8"))["models"].get(responder)
        if measured:
            profile.calibration, profile.plans_measured = calibrate(profile, measured["pooled"])
    return profile

def calibrate(profile, pooled):
    """(page reading / card prediction, plans used): the median ratio of the smallest font measured on pages
    to the cards' prediction, over plans where both are informative (not at the smallest font tested, not
    unread). 1.0 below MIN_PLANS."""
    from .pagetest import FONT_PT, PAGES, paper
    ratios = []
    for kind, parts in pooled.items():
        w, h = PAGES[paper(kind)]
        for name, result in parts.get("static", {}).items():
            measured = result.get("min_pt")
            side, px = _plan_of(name)
            predicted = card_prediction(profile, *((w, h) if side is None else (side, side)), px)
            if measured and measured > min(FONT_PT) + 0.01 and predicted > min(FONT_PT):
                ratios.append(measured / predicted)
    if len(ratios) < MIN_PLANS:
        return 1.0, len(ratios)
    ratios.sort()
    return round(ratios[len(ratios) // 2], 3), len(ratios)

def _plan_of(name):
    """(tile side or None, render px) from a page-test plan's name ("whole-768", "t420-1536")."""
    region, px = name.split("-")
    return (None if region == "whole" else int(region[1:])), int(px)

def plan(profile, page_w, page_h, smallest_pt, largest_pt=None, sides=SIDES, renders=RENDERS, margin=0.9):
    """The cheapest plan (fewest tiles, then the smallest render) whose predicted smallest font is at most
    margin × the page's smallest, and that doesn't magnify its largest text past the model's ceiling.
    Returns {"side", "px", "tiles", "predicted_pt", "largest_cap_px"}, or None when nothing qualifies."""
    import pymupdf
    from semantic_pdf_diff.segmentation import tiles
    page = pymupdf.Rect(0, 0, page_w, page_h)
    options = []
    for side in sides:
        if side is not None and side >= max(page_w, page_h):
            continue
        w, h = (page_w, page_h) if side is None else (min(side, page_w), min(side, page_h))
        count = 1 if side is None else len(list(tiles(page, side)))
        for px in renders:
            predicted = smallest_font(profile, w, h, px)
            biggest = None if largest_pt is None else largest_pt * CAP * px / max(w, h)
            ceiling = profile.ceiling_px
            if predicted <= margin * smallest_pt and (ceiling is None or biggest is None or biggest <= ceiling):
                options.append((count, px, side, predicted, biggest))
    if not options:
        return None
    count, px, side, predicted, biggest = min(options, key=lambda o: (o[0], o[1]))
    return {"side": side, "px": px, "tiles": count, "predicted_pt": round(predicted, 2),
            "largest_cap_px": None if biggest is None else round(biggest, 1)}
