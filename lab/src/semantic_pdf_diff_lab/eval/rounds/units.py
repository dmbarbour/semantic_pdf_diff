"""A round's units: the runs' claims collected per page region, large units cut into bands, units sampled where
the variant's answers differ, and the batch judges and people see. Split from rounds.py (architecture clean-up,
milestone 8).
"""
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from semantic_pdf_diff.pages import native, shown_by_matrix
from semantic_pdf_diff.regions import FAMILY, region_of

MAX_CLAIMS = 25     # claims shown per side (sampled when there are more)
PAGE_TEXT = 6000    # characters of the page's text layer shown to judges

def _ident(c):
    """A claim's identity (see collect); batches from before 2026-09-30 carry none: their exact text."""
    return c.get("_id") or tuple(str(c.get(k, "")) for k in ("entity", "attribute", "value", "unit", "conditions", "quote"))

def private_slices(runs, manifest):
    """The slices behind these runs (by run name, as in scripts/slices.json) not marked public. Rounds and
    spot checks commit page images, page text and claims, so they refuse any: a sensitive document must
    never reach the repository."""
    slices = {s["name"]: s for s in manifest["slices"]}
    names = {n for r in manifest["runs"] if r["name"] in set(runs) for n in r["slices"]} | (set(runs) & set(slices))
    unknown = sorted(set(runs) - {r["name"] for r in manifest["runs"]} - set(slices))
    return sorted(n for n in names if not slices.get(n, {}).get("public")) + unknown

def _reader(runs_dir):
    """Evidence as the runs present it: the store says whether readings are merged; stores from
    before it recorded that (rounds 6–8) fall back to settings.json beside the runs."""
    path = Path(runs_dir) / "settings.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    return lambda store, content: store.evidence(content, reconcile=True if settings.get("reconcile") else None)

UNIT_CLAIMS = "own readings, quoted"  # how collect words and identifies a unit's claims (batches record it)

def collect(runs_dir, unit="family"):
    """{(run, content, page, family): {"claims": {id: claim}, "tasks": n}} for every store under runs_dir.

    unit="page" merges a page's kinds into one unit ("page"): for variants that move claims
    between kinds (e.g. dropping false tables whose facts the tiles also read).

    With readings of one fact merged, a unit shows each merged claim once, as its own tasks read
    it: the first sighting in the unit, in that sighting's own words and under that reading's ID.
    Until 2026-09-28 a unit showed the merged claim's representative wording (often a text
    reading's), so a text lever changed visual units whose readings hadn't changed (the audit:
    4-7 of 9-14 visual units in r09's batches), and counted one change in two units.

    A claim's identity in a unit (its key, and `_id`) is its reading's ID and its quote: what judges
    and people are shown, so a lever that changes only quotes changes its units. `_claim` is the
    merged claim's ID (the evidence it belongs to). The meta-audit found three identities in use."""
    family_of = (lambda region: FAMILY.get(region)) if unit == "family" else (lambda region: "page" if region in FAMILY else None)
    from semantic_pdf_diff.store import Store
    units = defaultdict(lambda: {"claims": {}, "tasks": 0})
    read = _reader(runs_dir)
    for folder in sorted(Path(runs_dir).iterdir()):
        if not (folder / "store.sqlite").exists():
            continue
        with Store.open(folder) as store:
            contents = sorted({f.content for f in store.files() if f.content.endswith(".pdf")})
            for content in contents:
                for row in store.coverage(content):
                    family = family_of(region_of(row["task"]))
                    if family and row.get("page"):
                        units[(folder.name, content, row["page"], family)]["tasks"] += 1
                from semantic_pdf_diff.readings import wording
                merged = read(store, content)
                readings = {}  # (task, quote, wording) -> the reading as its task gave it
                for r in (store.evidence(content, reconcile=False) if any(e.occurrences for e in merged) else merged):
                    for o in r.occurrences or [r]:
                        readings.setdefault((o.locator.task, o.quote, wording(r)), r)
                for e in merged:
                    seen = set()  # units this claim already appears in
                    for o in e.occurrences or [e]:
                        family = family_of(o.locator.region)
                        key = (folder.name, content, o.locator.page, family)
                        if not family or key in seen:
                            continue
                        seen.add(key)
                        own = readings.get((o.locator.task, o.quote, o.wording or wording(e)), e)
                        claim = {k: getattr(own, k) for k in ("entity", "attribute", "value", "unit", "conditions")}
                        claim["quote"] = o.quote
                        claim["_box"] = list(o.locator.bbox)  # where it was read (splitting units)
                        claim["_task"] = o.locator.task       # which request read it (its input, for reviewers)
                        claim["_id"] = identity = own.id + "~" + hashlib.sha256(o.quote.encode()).hexdigest()[:8]
                        claim["_claim"] = e.id
                        units[key]["claims"][identity] = claim
    return dict(units)

MAX_BANDS = 4  # a unit is cut into at most this many bands
BANDS = "as displayed"  # how a band's y0, y1 are measured (batches record it; before 2026-10-02, unrotated)

def rotations(runs_dir):
    """rotation(run, content, page): the page's rotation matrix (None: upright), from the document
    the run's store read; each document is opened once."""
    import pymupdf
    from semantic_pdf_diff.scan import read_origin
    from semantic_pdf_diff.store import Store
    cache = {}
    def rotation(run, content, page):
        if (run, content) not in cache:
            with Store.open(Path(runs_dir) / run) as store:
                file = next(f for f in store.files() if f.content == content)
                data = read_origin(store.origin(file.source, file.path))
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                cache[(run, content)] = [p.rotation_matrix if p.rotation else None for p in doc]
        return cache[(run, content)][page - 1]
    return rotation

def band_region(page, band):
    """The part of a page a band shows: its y0..y1 as displayed, padded, across the page, in
    unrotated coordinates (what render and get_text clip by)."""
    import pymupdf
    full = page.rect
    return native(page, pymupdf.Rect(full.x0, max(full.y0, band[2] - 12), full.x1, min(full.y1, band[3] + 12)))

def split_units(base, var, limit=MAX_CLAIMS, rotation=None):
    """Units with more than `limit` claims on either side, cut into bands of the page by where the
    claims were read (the meta-analysis of rounds 1–8: half of all units, three quarters of visual
    ones, had more, and gave weaker verdicts). Keys gain a band (index, count, y0, y1), measured as
    the page is displayed (rotation: see `rotations`; none, every page upright), so a turned sheet
    is cut across as it's read (code review 2026-10-01, item 15); unchanged bands then drop out like
    unchanged units."""
    out_a, out_b = {}, {}
    for key in set(base) | set(var):
        a = base.get(key, {"claims": {}, "tasks": 0})
        b = var.get(key, {"claims": {}, "tasks": 0})
        size = max(len(a["claims"]), len(b["claims"]))
        # Positions are where claims were read: a tile's box for an image claim. Cut only where both
        # sides read the same regions; a tiling lever (grid against bands) would otherwise compare
        # different parts of the page in each band. Uncut, judges see a declared sample instead.
        boxes = lambda side: {tuple(c["_box"]) for c in side["claims"].values()}
        # An empty side reads nothing to compare, so bands follow the other (either way round).
        comparable = not boxes(a) or not boxes(b) or len(boxes(a) & boxes(b)) >= 0.5 * min(len(boxes(a)), len(boxes(b)))
        if size <= limit or not comparable:
            if key in base:
                out_a[key] = a
            if key in var:
                out_b[key] = b
            continue
        # Where each claim was read; a claim both sides have takes the same position either way
        # round (the lesser box), so bands don't depend on which side is the baseline.
        turn = rotation(*key[:3]) if rotation else None
        position = {}
        for side in (a, b):
            for i, c in side["claims"].items():
                box = tuple(shown_by_matrix(turn, c["_box"]))
                position[i] = min(position[i], box) if i in position else box
        centre = lambda i: (position[i][1] + position[i][3]) / 2
        order = sorted(position, key=lambda i: (centre(i), i))
        k = min(MAX_BANDS, -(-size // limit))
        for part in range(k):
            ids = order[part * len(order) // k:(part + 1) * len(order) // k]
            if not ids:
                continue
            y0 = min(position[i][1] for i in ids)
            y1 = max(position[i][3] for i in ids)
            band = key + ((part, k, round(y0, 1), round(y1, 1)),)
            out_a[band] = {"claims": {i: a["claims"][i] for i in ids if i in a["claims"]}, "tasks": a["tasks"]}
            out_b[band] = {"claims": {i: b["claims"][i] for i in ids if i in b["claims"]}, "tasks": b["tasks"]}
    return out_a, out_b

def lever_scope(baseline_dir, variant_dir, unit="family"):
    """The kinds of unit the settings that differ between two runs' folders can change (from
    store.SETTING_REGIONS), or None when none differ (an A/A control, a code change) or a folder
    has no settings.json."""
    from semantic_pdf_diff.store import ALL_REGIONS, SETTING_REGIONS
    paths = [Path(d) / "settings.json" for d in (baseline_dir, variant_dir)]
    if not all(p.exists() for p in paths):
        return None
    a, b = (json.loads(p.read_text()) for p in paths)
    differing = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    if not differing:
        return None
    regions = set().union(*(SETTING_REGIONS.get(k, ALL_REGIONS) for k in differing))
    families = {FAMILY[r] for r in regions if r in FAMILY}
    return ({"page"} if families else set()) if unit == "page" else families

def _unit_of(task, unit):
    region = region_of(task)
    return FAMILY.get(region) if unit == "family" else ("page" if region in FAMILY else None)

def pair_units(baseline_dir, variant_dir, n, seed=1, families=("text", "table", "visual", "page"), changed_only=True,
               unit="family", limit=MAX_CLAIMS):
    """Sample up to n units present in both, stratified by family (round-robin), keeping only
    units whose claims differ (identical answers can't prefer either side).

    counts["checks"]: what must hold of the units (the meta-audit: invariants checked when a batch
    is built). Swapping the sides gives the same units; every claim was read by a task of its
    unit's kind; and changed units stay within what the differing settings can touch."""
    base_units, var_units = collect(baseline_dir, unit), collect(variant_dir, unit)
    rotation = rotations(baseline_dir)
    base, var = split_units(base_units, var_units, limit, rotation)
    mirror_var, mirror_base = split_units(var_units, base_units, limit, rotation)
    scope = lever_scope(baseline_dir, variant_dir, unit)
    checks = {"asymmetric_units": len(set(base) ^ set(mirror_base)) + len(set(var) ^ set(mirror_var)),
              "foreign_readings": sum(1 for units in (base_units, var_units) for k, u in units.items()
                                      for c in u["claims"].values() if _unit_of(c.get("_task"), unit) != k[3]),
              "scope": sorted(scope) if scope is not None else None}
    keys = sorted(k for k in set(base) | set(var) if k[3] in families and (k in base or k in var))
    rng = random.Random(seed)
    groups = defaultdict(list)
    for k in keys:
        a, b = base.get(k, {"claims": {}}), var.get(k, {"claims": {}})
        if changed_only and set(a["claims"]) == set(b["claims"]):
            continue
        groups[k[3]].append(k)
    for g in groups.values():
        rng.shuffle(g)
    picked = []
    while len(picked) < n and any(groups.values()):
        for family in sorted(groups):
            if groups[family] and len(picked) < n:
                picked.append(groups[family].pop())
    same = sum(1 for k in keys if set(base.get(k, {"claims": {}})["claims"]) == set(var.get(k, {"claims": {}})["claims"]))
    changed_by_kind = {f: len(g) + sum(k[3] == f for k in picked) for f, g in groups.items()}
    checks["changed_out_of_scope"] = 0 if scope is None else sum(n for f, n in changed_by_kind.items() if f not in scope)
    return [(k, base.get(k, {"claims": {}})["claims"], var.get(k, {"claims": {}})["claims"]) for k in picked], \
        {"units": len(keys), "unchanged": same, "changed_by_kind": changed_by_kind, "checks": checks}

def shown(a, b, rng, limit=MAX_CLAIMS):
    """Claim IDs of each side to show judges, at most `limit` each: every claim only one side has
    (sampled if there are too many), then the same sample of shared claims on both sides. Sampling
    each side separately (before round 7) showed judges different subsets of mostly shared claims,
    so on large units they compared samples rather than the lever."""
    only_a, only_b = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    shared = sorted(set(a) & set(b))
    pick = lambda ids, k: ids if len(ids) <= k else sorted(rng.sample(ids, k))
    only_a, only_b = pick(only_a, limit), pick(only_b, limit)
    common = pick(shared, max(0, limit - max(len(only_a), len(only_b))))
    return sorted(only_a + common), sorted(only_b + common)

LEAD = 400  # characters of text before a unit shown to judges (as the extractor's neighbouring context)

def _lead(doc, page, region, cache, key):
    """(text just before the region, the numbered items and headings it sits under), as the
    extractor saw them in its context (neighbouring text, "Within:" stems): the stems from the
    extractor's own provider (extract.Context.stem_path)."""
    from semantic_pdf_diff.extract import Context, stem_index
    from semantic_pdf_diff.pages import display_y, reading_blocks
    if key + ("stems",) not in cache:  # the document is opened afresh per unit; its stem index is kept
        cache[key + ("stems",)] = stem_index(doc)
    context = Context(doc, None)  # only its stem path is used
    context.stems = cache[key + ("stems",)]
    here = doc[page - 1]
    top = display_y(here, tuple(region))
    above = [b[4] for b in reading_blocks(here) if b[6] == 0 and display_y(here, tuple(b[:4])) < top - 1]
    if not above and page > 1:
        above = [b[4] for b in reading_blocks(doc[page - 2]) if b[6] == 0]
    before = " ".join(" ".join(above).split())[-LEAD:]
    return before, " > ".join(context.stem_path(page, tuple(region)))

# A batch's page text (what judges and people read beside each crop) is the document's content, so like its images
# it isn't committed (the owner, 2026-10-02): pairs.json holds the rest, and PAGES (git-ignored) the text, restored
# from the public slices by rerender.
PAGES = "pages.json"
PAGE_FIELDS = ("page_text", "page_text_full")

def save_batch(folder, batch):
    """pairs.json without page text, and the text in PAGES beside it."""
    folder = Path(folder)
    pages = {i["id"]: {k: i[k] for k in PAGE_FIELDS if k in i} for i in batch["items"]}
    lean = {**batch, "items": [{k: v for k, v in i.items() if k not in PAGE_FIELDS} for i in batch["items"]]}
    (folder / "pairs.json").write_text(json.dumps(lean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (folder / PAGES).write_text(json.dumps(pages, indent=0, ensure_ascii=False) + "\n", encoding="utf-8")

def load_batch(folder):
    """pairs.json with its page text merged back in, where PAGES holds it."""
    folder = Path(folder)
    batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
    if (folder / PAGES).exists():
        pages = json.loads((folder / PAGES).read_text(encoding="utf-8"))
        for item in batch["items"]:
            item.update(pages.get(item["id"], {}))
    return batch

def build_batch(baseline_dir, variant_dir, folder, n=60, seed=1, unit="family", limit=MAX_CLAIMS, documents=None):
    """Write a pairwise batch: pairs.json (with which side is the baseline) and page images.

    Its checks (batch["units"]["checks"]; see pair_units) raise when units depend on which side is
    the baseline or hold claims read by another kind of task: those are bugs. Others are recorded:
    unique claims a sample hides, changed units a lever shouldn't touch, units of no document family
    (documents: {slice name: family})."""
    from ..review import render
    from semantic_pdf_diff.store import Store
    from semantic_pdf_diff.scan import read_origin
    import pymupdf
    folder = Path(folder)
    (folder / "images").mkdir(parents=True, exist_ok=True)
    picked, counts = pair_units(baseline_dir, variant_dir, n, seed, unit=unit, limit=limit)
    checks = counts["checks"]
    if checks["asymmetric_units"] or checks["foreign_readings"]:
        raise ValueError(f"batch checks failed for {folder}: {checks['asymmetric_units']} units depend on which side "
                         f"is the baseline, {checks['foreign_readings']} claims sit in units of another kind")
    rng = random.Random(seed + 1)
    items = []
    docs = {}
    hidden_unique = 0  # claims only one side has that a unit's sample leaves out (rubric v4 says there are none)
    for (run, content, page, family, *band), a, b in picked:
        if (run, content) not in docs:
            with Store.open(Path(baseline_dir) / run) as store:
                file = next(f for f in store.files() if f.content == content)
                docs[(run, content)] = read_origin(store.origin(file.source, file.path))
                docs[(run, content, "sections")] = store.sections(content)
        headings = [" > ".join(x.heading_path) for x in docs[(run, content, "sections")]
                    if x.heading_path and x.first_page <= page <= x.last_page]
        with pymupdf.open(stream=docs[(run, content)], filetype="pdf") as doc:
            part, parts, y0, y1 = band[0] if band else (0, 1, None, None)
            region = band_region(doc[page - 1], band[0]) if band else None
            # a band's crop is its own: a text and a visual unit cut into bands of the same number once shared one, so
            # one of them was judged on the other's crop (rounds 9, 9b and 9h; found 2026-10-02)
            name = f"{run}-{content.split(':')[1][:8]}-p{page}" + (f"-{family}-b{part}of{parts}" if band else "") + ".jpg"
            if not (folder / "images" / name).exists():  # a band is shown as its own crop, at full size
                (folder / "images" / name).write_bytes(render(doc, page, region, None, 1400))
            text = doc[page - 1].get_text("text", clip=region)[:PAGE_TEXT]
            before, within = _lead(doc, page, region or native(doc[page - 1], doc[page - 1].rect), docs, (run, content))
        shown_a, shown_b = shown(a, b, rng, limit)
        shared = set(a) & set(b)
        hidden_unique += len((set(a) - set(b)) - set(shown_a)) + len((set(b) - set(a)) - set(shown_b))
        items.append({"id": f"u-{run}-{content.split(':')[1][:8]}-p{page}-{family}" + (f"-b{part}of{parts}" if band else ""),
                      "run": run, "content": content, "page": page, "family": family,
                      "band": [part, parts, y0, y1] if band else None,
                      "image": f"images/{name}", "page_text": text, "sections": headings,
                      "before": before, "within": within,
                      "baseline": [a[i] for i in shown_a], "variant": [b[i] for i in shown_b],
                      "hidden_shared": len(shared - set(shown_a)),
                      "counts": {"baseline": len(a), "variant": len(b), "shared": len(shared)}})
    checks["hidden_unique_claims"] = hidden_unique
    if documents is not None:
        checks["without_family"] = sorted({i["run"] for i in items if not documents.get(i["run"])})
    batch = {"format": "semantic-pdf-diff-pairwise-batch", "version": 1, "baseline": str(baseline_dir),
             "variant": str(variant_dir), "seed": seed, "unit_claims": UNIT_CLAIMS, "bands": BANDS, "units": counts,
             "items": items}
    save_batch(folder, batch)
    return batch

def add_context(folder, baseline_dir, variant_dir, n, seed=1, limit=MAX_CLAIMS, unit="family"):
    """Give a batch's units what a reviewer needs to judge them (the owner, 2026-09-28: a band of
    a table without its header can't be judged; "missing" can't be judged from a sample):
    - every claim of both sets, the unshown ones appended after those shown (so marks already
      made on the shown ones stay attached to the same claims);
    - the whole page with the unit's region outlined, and the page's whole text layer;
    - for text and table claims, the input their request was given (from each side's own run store).
    Units are recomputed exactly as build_batch sampled them."""
    import pymupdf
    from ..review import render
    from semantic_pdf_diff.scan import read_origin
    from semantic_pdf_diff.store import Store
    folder = Path(folder)
    batch = load_batch(folder)
    if batch.get("unit_claims") != UNIT_CLAIMS:  # units recomputed another way wouldn't match the batch's
        raise ValueError(f"{folder}'s units were built by an earlier collect ({batch.get('unit_claims', 'merged wording')}); "
                         "rebuild the batch to add context")
    picked, _ = pair_units(baseline_dir, variant_dir, n, seed, unit=unit, limit=limit)
    sources, docs = {}, {}

    def source(side_dir, run, content, task):
        """The input a text or table task was given, from that side's run store (its query log)."""
        if not task or not task.startswith(("text", "table")):
            return None
        if (side_dir, run, content) not in sources:
            with Store.open(Path(side_dir) / run) as store:
                sources[(side_dir, run, content)] = {q["task"]: q["prompt"] for q in store.queries(content=content,
                                                                                                    role="extract")}
        prompt = sources[(side_dir, run, content)].get(task)
        from semantic_pdf_diff.extract import ExtractQuery
        return ExtractQuery.read(prompt).data.strip() if prompt else None

    by_id = {i["id"]: i for i in batch["items"]}
    for (run, content, page, family, *band), a, b in picked:
        item = by_id.get(f"u-{run}-{content.split(':')[1][:8]}-p{page}-{family}"
                         + (f"-b{band[0][0]}of{band[0][1]}" if band else ""))
        if item is None:
            continue
        for side, claims in (("baseline", a), ("variant", b)):
            full = {_ident(c): c for c in claims.values()}
            shown = {_ident(c) for c in item[side]}
            for c in item[side]:  # the task each shown claim was read by
                c.setdefault("_task", full.get(_ident(c), {}).get("_task"))
            item[side] += [c for key, c in full.items() if key not in shown]
        item["hidden_shared"] = 0
        item["counts"] = {"baseline": len(item["baseline"]), "variant": len(item["variant"]),
                          "shared": len({_ident(c) for c in item["baseline"]} & {_ident(c) for c in item["variant"]})}
        item["sources"] = {side: {c["_task"]: text for c in item[side]
                                  if (text := source(side_dir, run, content, c.get("_task")))}
                           for side, side_dir in (("baseline", baseline_dir), ("variant", variant_dir))}
        if (run, content) not in docs:
            with Store.open(Path(baseline_dir) / run) as store:
                file = next(f for f in store.files() if f.content == content)
                docs[(run, content)] = read_origin(store.origin(file.source, file.path))
        with pymupdf.open(stream=docs[(run, content)], filetype="pdf") as doc:
            if band and doc[page - 1].rotation and batch.get("bands") != BANDS:
                raise ValueError(f"{folder}'s bands were cut by unrotated y; rebuild the batch to add context")
            region = band_region(doc[page - 1], band[0]) if band else None
            name = item["image"].replace(".jpg", "-page.jpg")
            (folder / name).write_bytes(render(doc, page, None, region, 1400))
            item["page_image"] = name
            item["page_text_full"] = doc[page - 1].get_text("text")[:PAGE_TEXT]
    save_batch(folder, batch)
    return batch

def rerender(folder, slices, target=None):
    """A batch's images and page text made again from the PDFs its runs read (`slices`: a folder of them, the public
    slices): the images into `target` (default: the batch's own images folder, and then the text into PAGES), what
    build_batch and add_context wrote, byte for byte under the same PyMuPDF. Development rounds' images aren't committed (the owner, 2026-10-02: "we should not be
    committing images ... for development rounds"); this brings them back. Returns the image names written."""
    import pymupdf
    from semantic_pdf_diff.pages import native_page
    from semantic_pdf_diff.provenance import content_id
    from ..review import render
    folder = Path(folder)
    target = Path(target) if target else folder / "images"
    target.mkdir(parents=True, exist_ok=True)
    batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
    pdfs = {content_id(p.read_bytes(), p.name): p for p in sorted(Path(slices).glob("*.pdf"))}
    written, pages = [], {}
    for item in batch["items"]:
        source = pdfs.get(item["content"])
        if source is None:
            raise FileNotFoundError(f"{item['content']} ({item['run']}): not among {slices}'s PDFs")
        with pymupdf.open(source) as doc:
            page = doc[item["page"] - 1]
            band = item.get("band")
            if band and batch.get("bands") == BANDS:
                region = band_region(page, band)
            elif band:  # cut by unrotated y, before 2026-10-02
                whole = native_page(page)
                region = pymupdf.Rect(whole.x0, max(whole.y0, band[2] - 12), whole.x1, min(whole.y1, band[3] + 12))
            else:
                region = None
            pages[item["id"]] = {"page_text": page.get_text("text", clip=region)[:PAGE_TEXT],
                                 **({"page_text_full": page.get_text("text")[:PAGE_TEXT]} if item.get("page_image") else {})}
            name = Path(item["image"]).name
            if name not in written:  # as build_batch did: the first unit to name an image renders it
                (target / name).write_bytes(render(doc, item["page"], region, None, 1400))
                written.append(name)
            page_name = Path(item.get("page_image") or "").name
            if page_name and page_name not in written:
                (target / page_name).write_bytes(render(doc, item["page"], None, region, 1400))
                written.append(page_name)
    if target == folder / "images":
        (folder / PAGES).write_text(json.dumps(pages, indent=0, ensure_ascii=False) + "\n", encoding="utf-8")
    return written
