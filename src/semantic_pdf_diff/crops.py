"""A report's crops, inside its one file (docs/plans/portable-reports-2026-10-19.md): which claims' crops are worth
embedding, in what order, how each is encoded, and what a byte budget leaves out. The owner, 2026-10-19: "Unless we
can filter the crops based on where they'll provide the best value to a reader (e.g. figures and charts, small
tables), I fear we'll swiftly blow past any reasonable budgets."
"""
import base64
import io
import math
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

# The report file's size, in bytes (the owner, 2026-10-19: "20MB or even a fair bit more is acceptable").
DEFAULT_BUDGET = 20_000_000
QUALITY = 60  # WebP's (JPEG's without Pillow): at the model's resolution, small text stays legible

# What a claim is shown in, in the order its crop is worth embedding; a claim shown in several takes its best.
GROUPS = ("different or uncertain", "complementary, or possibly added or removed", "equivalent, unmatched or shared",
          "unrelated")
RELATION_GROUP = {"different": 0, "uncertain": 0, "complementary": 1, "equivalent": 2, "unrelated": 3}
# Within a group, claims whose crop is their evidence first: read from a picture of a chart, diagram or table, or
# quoted in words the page's text doesn't have.
PICTURED = ("chart", "diagram", "table")

@dataclass
class Crop:
    """One crop a report shows: its image in the store, the best group and order of the claims showing it, and
    what it costs embedded (base64 in a JSON list)."""
    image: str                # its path under the store's folder, as claims name it ("assets/...")
    group: int                # GROUPS' index
    pictured: bool            # a claim showing it is pictured, or its quote unfound
    order: int                # where its first claim is shown in the report
    label: str                # where it is and what a claim showing it says, for people
    content: str = ""         # the file it's from (its content)
    turn: int = 0             # its file's turn within its group: each file's first crop, then each one's second...
    data: str = ""            # the encoded image, base64
    size: int = 0             # bytes in the page: data, its quotes and a comma

    @property
    def key(self):
        return (self.group, not self.pictured, self.order)

@dataclass
class Account:
    """What a budget did to a report's crops: the page's size without them, every crop wanted in order, the ones
    embedded, and the file's size with them."""
    budget: int
    page: int = 0             # bytes of the page with no crops embedded
    wanted: list = field(default_factory=list)   # Crop, in priority order
    chosen: set = field(default_factory=set)     # the embedded crops' images
    names: dict = field(default_factory=dict)    # {content: its file as people know it}
    size: int = 0             # the written file's bytes

    @property
    def cut(self):
        return [c for c in self.wanted if c.image not in self.chosen]

def groups(findings, unmatched, shared):
    """{claim id: GROUPS' index} for every claim a report shows; findings in the order shown."""
    best = {}
    def put(eid, g):
        best[eid] = min(g, best.get(eid, g))
    for f in findings:
        g = RELATION_GROUP.get(f["relation"], 3)
        put(f["a"], g)
        put(f["b"], g)
    for u in unmatched:
        put(u["id"], 1 if u.get("status") == "unaligned" else 2)
    for eid in shared:
        put(eid, 2)
    return best

def wanted(evidence, findings, unmatched, shared, label, exists, crop_of=lambda e: e.get("image")):
    """Every crop the report's claims show, in the order they're embedded: by group, then the files taking turns
    (so one large drawing set can't take a group's share), each file's pictured claims first, then the report's order.
    evidence: {id: claim dict}; label(claim): how people find it; exists(image): whether the store still has it (a
    crop it lost is shown missing, never wanted); crop_of(claim): its crop (its image, or its task's)."""
    best = groups(findings, unmatched, shared)
    order = {}
    for eid in [x for f in findings for x in (f["a"], f["b"])] + [u["id"] for u in unmatched] + list(shared):
        order.setdefault(eid, len(order))
    crops = {}
    for eid, g in best.items():
        e = evidence.get(eid)
        image = crop_of(e) if e else None
        if not image or not exists(image):
            continue
        pictured = e["kind"] in PICTURED or e.get("quote_verified") is not True
        c = crops.get(image)
        mine = Crop(image, g, pictured, order[eid], label(e), e["content"])
        if c is None or mine.key < c.key:
            crops[image] = mine
    turns = Counter()
    for c in sorted(crops.values(), key=lambda c: c.key):
        c.turn = turns[c.group, c.content]
        turns[c.group, c.content] += 1
    return sorted(crops.values(), key=lambda c: (c.group, c.turn, c.key))

def encoder():
    """(the MIME type, encode(path) -> bytes): WebP through Pillow where it's installed (an optional dependency),
    else JPEG through PyMuPDF, about twice the size."""
    try:
        from PIL import Image
    except ImportError:
        import pymupdf
        def jpeg(path):
            pix = pymupdf.Pixmap(str(path))
            if pix.alpha:
                pix = pymupdf.Pixmap(pix, 0)
            if pix.colorspace is None or pix.colorspace.n not in (1, 3):
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            return pix.tobytes("jpeg", jpg_quality=QUALITY)
        return "image/jpeg", jpeg
    def webp(path):
        with Image.open(path) as im:
            out = io.BytesIO()
            im.convert("RGB").save(out, "WEBP", quality=QUALITY)
        return out.getvalue()
    return "image/webp", webp

def encode(crops, stored, encode):
    """Each crop encoded and sized (stored(image): its file), in threads (the encoders release the interpreter's
    lock)."""
    def one(c):
        c.data = base64.b64encode(encode(stored(c.image))).decode("ascii")
        c.size = len(c.data) + 3
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        list(pool.map(one, crops))

def choose(crops, room):
    """The crops embedded in `room` bytes: in priority order, each that still fits (smaller ones after one that
    didn't may)."""
    chosen = []
    for c in crops:
        if c.size <= room:
            chosen.append(c)
            room -= c.size
    return chosen

def sized(n):
    """A size for people: kilobytes under a megabyte."""
    return f"{n / 1e6:.1f} MB" if n >= 1e6 else f"{round(n / 1e3)} KB"

def as_budget(n):
    """n bytes as a --report-budget at least that large: tenths of a megabyte, or kilobytes under one."""
    return f"{math.ceil(n / 1e5) / 10:.1f}MB" if n >= 1e6 else f"{math.ceil(n / 1e3)}KB"

def feedback(account, shown=20):
    """What a budget includes and leaves out, as lines for people: by group, the budget each group needs in full,
    and the first crops left out."""
    a = account
    room = max(0, a.budget - a.page)
    lines = [f"report.html with a budget of {sized(a.budget)}: {sized(a.page)} without crops, "
             f"{sized(room)} left for them" + ("" if a.page <= a.budget else " (the page alone is over budget)")]
    total = sum(c.size for c in a.wanted)
    embedded = sum(c.size for c in a.wanted if c.image in a.chosen)
    lines.append(f"crops: {len(a.wanted)} wanted ({sized(total)}), {len(a.chosen)} embedded "
                 f"({sized(embedded)}), {len(a.cut)} left out")
    running = a.page
    for g, name in enumerate(GROUPS):
        mine = [c for c in a.wanted if c.group == g]
        if not mine:
            continue
        running += sum(c.size for c in mine)
        cut = sum(1 for c in mine if c.image not in a.chosen)
        state = "all embedded" if not cut else "all left out" if cut == len(mine) else (
            f"{len(mine) - cut} embedded, {cut} left out")
        lines.append(f"  {name:45} {len(mine):5} crops, {sized(sum(c.size for c in mine)):>8}: {state}; in full "
                     f"with --report-budget {as_budget(running)}")
    files = {}
    for c in a.wanted:
        mine = files.setdefault(c.content, [a.names.get(c.content, c.content), 0, 0])
        mine[1] += 1
        mine[2] += c.image in a.chosen
    if len(files) > 1:
        ranked = sorted(files.values(), key=lambda f: (f[2] - f[1], f[0]))  # most left out first
        lines.append(f"by file, most left out first ({len(files)} files with crops):")
        lines += [f"  {name}: {embedded} of {n} embedded" for name, n, embedded in ranked[:shown]]
    cut = a.cut
    if cut:
        lines.append(f"left out, the first {min(shown, len(cut))} of {len(cut)} by priority:")
        lines += [f"  {GROUPS[c.group]} · {sized(c.size)} · {c.label}" for c in cut[:shown]]
    return lines

def summary(account, store):
    """One line on what the budget left out, for a run's or a report's last words."""
    return (f"{len(account.cut)} of {len(account.wanted)} crops left out for the report's {sized(account.budget)} "
            f"budget: `pdf-semantic-diff report --store {store} --dry-run` lists them, and --report-budget sets "
            "another")
