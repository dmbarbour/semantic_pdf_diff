"""Refinement measured where it happens: every tile of a document refined once, whatever its answer.

A tile is refined in halves only when its answer is partial or failed, which is rare in a run (36 tiles in the slices
fixture): too few to judge a change to how tiles are halved. So the lab forces it. `forced()` marks every answer to
an unrefined tile partial, as it reaches the task, and a run with `refinement_depth` 1 then asks each tile's two
halves once. The product has no such setting (review-bugs-2026-10-09, item 6; the owner: "seems reasonable").

Each half is then counted from the run's store: its claims, whether it found none, and against a controlled
document's key, its right and misbound claims (controlled.score). Checks without a key (`checks`, `against`): what
the halves lost and gained from their tile; their complaints ("fragment", "cropped"); quotes not in the page's text
or cut mid-word; how their values agree with the text tasks' (a reader, not the truth: a tile is shown its text
layer); and, between two runs, the claims each run's halves alone found.
"""
import contextlib
import json
import re
import sqlite3
from pathlib import Path

COMPLAINT = re.compile(r"fragment|crop|cut off|truncat|partial (?:view|image|section)|incomplete (?:view|image|text)"
                       r"|illegib|unreadable|blank", re.I)

@contextlib.contextmanager
def forced(fresh_halves=False):
    """Every answer to an unrefined tile's extraction taken as partial, so the tile is refined; with fresh_halves,
    the halves are asked afresh, as another sample of each query (the noise floor: a run against itself)."""
    from semantic_pdf_diff.dispatch import Dispatcher
    from semantic_pdf_diff.fixtures import Replayer
    from semantic_pdf_diff.recipes import Recipe
    from semantic_pdf_diff.regions import region_of
    submit, sample = Dispatcher.submit, Replayer.sample

    def tile(key, refined):
        recipe = Recipe(key or ())
        return recipe.role == "extract" and region_of(recipe.task) == "tile" and ("-r" in recipe.task) == refined

    def forcing(self, prompt, schema, images, key, finish):
        if tile(key, refined=False):
            inner = finish

            def finish(value, error):
                inner(value.model_copy(update={"complete": False}) if value is not None else None, error)
        return submit(self, prompt, schema, images, key, finish)
    def fresh(self, key):
        return 1 if tile(key, refined=True) else sample(self, key)
    Dispatcher.submit = forcing
    if fresh_halves:
        Replayer.sample = fresh
    try:
        yield
    finally:
        Dispatcher.submit, Replayer.sample = submit, sample

def halves(store):
    """{parent tile's task: {half's task: [claims]}} from a run's store; a half's continuations count as the half."""
    with contextlib.closing(sqlite3.connect(f"file:{store}?mode=ro", uri=True)) as db:
        tasks = [t for (t,) in db.execute("SELECT task FROM task WHERE task LIKE 'tile:%'")]
        claims = {}
        for task, data in db.execute("SELECT task, data FROM evidence WHERE task LIKE 'tile:%'"):
            claims.setdefault(task, []).append(json.loads(data))
    out = {}
    for task in tasks:
        parent, _, rest = task.partition("-r")
        if rest:
            half = f"{parent}-r{rest.split('-')[0]}"
            out.setdefault(parent, {}).setdefault(half, []).extend(claims.get(task, []))
    return out

def summary(store, key=None):
    """Counts over a run's halves: parents, halves, empty halves, claims, and with a key, outcomes of their claims."""
    found = halves(store)
    every = [c for parts in found.values() for cs in parts.values() for c in cs]
    out = {"parents": len(found), "halves": sum(len(parts) for parts in found.values()),
           "empty": sum(1 for parts in found.values() for cs in parts.values() if not cs), "claims": len(every)}
    if key is not None:
        from .controlled import score
        result = score(key, every)
        out["outcomes"] = result["outcomes"]
        out["facts_right"] = result["found_right"]
    return out

def compare(before, after, keys=None):
    """{document: {"before": summary, "after": summary}} for runs under two folders of per-document stores."""
    keys = keys or {}
    out = {}
    for store in sorted(Path(after).glob("*/store.sqlite")):
        name = store.parent.name
        other = Path(before) / name / "store.sqlite"
        if other.exists():
            key = json.loads(keys[name].read_text(encoding="utf-8")) if name in keys else None
            out[name] = {"before": summary(other, key), "after": summary(store, key)}
    return out

def _norm(text):
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()

def _value(claim):
    return _norm(claim.get("value")), _norm(claim.get("unit"))

def _parent(task):
    return task.partition("-r")[0].partition("-c")[0]

def _stored(store):
    """(task rows, claims by task, the document's path on disk) from a run's store."""
    with contextlib.closing(sqlite3.connect(f"file:{store}?mode=ro", uri=True)) as db:
        rows = {t: json.loads(r) for t, r in db.execute("SELECT task, row FROM task")}
        claims = {}
        for task, data in db.execute("SELECT task, data FROM evidence"):
            claims.setdefault(task, []).append(json.loads(data))
        disk = db.execute("SELECT disk FROM file LIMIT 1").fetchone()
    return rows, claims, (json.loads(disk[0])[0] if disk else None)

def _page_words(path):
    """{page number: (its text, its words)} from a PDF."""
    import pymupdf
    from semantic_pdf_diff.quotes import terms
    out = {}
    with pymupdf.open(path) as doc:
        for number, page in enumerate(doc, 1):
            text = page.get_text()
            out[number] = (text, terms(text, True))
    return out

def checks(store):
    """Counts over a run's halves without a key."""
    from semantic_pdf_diff.quotes import terms
    from .controlled.score import tokens
    rows, claims, disk = _stored(store)
    pages = _page_words(disk) if disk and Path(disk).exists() else {}
    out = dict.fromkeys(("claims", "parent values lost", "values gained", "complaints", "quotes not in page",
                         "quotes cut mid-word", "value in text tasks", "binding same", "binding near",
                         "binding other", "value not in text tasks"), 0)
    texts = {}
    for task, found in claims.items():
        if not task.startswith(("tile:", "overview", "figure")):
            for c in found:
                texts.setdefault(_value(c), []).append(tokens(f"{c.get('entity', '')} {c.get('attribute', '')}"))
    by_parent = {}
    for task, row in rows.items():
        if not task.startswith("tile:"):
            continue
        parent = _parent(task)
        mine = by_parent.setdefault(parent, {"parent": set(), "halves": set(), "refined": False})
        values = {_value(c) for c in claims.get(task, [])}
        if "-r" in task:
            mine["halves"] |= values
            mine["refined"] = True
            out["complaints"] += bool(COMPLAINT.search(" ".join(row.get("issues", []))))
        else:
            mine["parent"] |= values
    for parent in by_parent.values():
        if parent["refined"]:
            out["parent values lost"] += len(parent["parent"] - parent["halves"])
            out["values gained"] += len(parent["halves"] - parent["parent"])
    for task, found in claims.items():
        if not (task.startswith("tile:") and "-r" in task):
            continue
        for c in found:
            out["claims"] += 1
            text, words = pages.get(c.get("locator", {}).get("page"), ("", set()))
            quote = terms(c.get("quote", ""), True)
            if words and quote and not quote <= words:
                out["quotes not in page"] += 1
                said = re.findall(r"[a-z0-9]+", _norm(c.get("quote")))
                ends = [w for w in (said[:1] + said[-1:]) if w not in words]
                if any(re.search(rf"\w{re.escape(w)}|{re.escape(w)}\w", text.casefold()) for w in ends):
                    out["quotes cut mid-word"] += 1
            known = texts.get(_value(c))
            if known is None:
                out["value not in text tasks"] += 1
                continue
            out["value in text tasks"] += 1
            mine = tokens(f"{c.get('entity', '')} {c.get('attribute', '')}")
            best = max((len(mine & k) / len(mine | k) if mine | k else 1.0) for k in known)
            out["binding same" if best == 1.0 else "binding near" if best >= 0.5 else "binding other"] += 1
    return out

def against(before, after):
    """Values only one run's halves found, per tile, summed: (only before, only after, both)."""
    one, other = (_stored(s)[1] for s in (before, after))

    def by_parent(claims):
        out = {}
        for task, found in claims.items():
            if task.startswith("tile:") and "-r" in task:
                out.setdefault(_parent(task), set()).update(_value(c) for c in found)
        return out
    a, b = by_parent(one), by_parent(other)
    shared = set(a) & set(b)
    return {"only before": sum(len(a[p] - b[p]) for p in shared), "only after": sum(len(b[p] - a[p]) for p in shared),
            "both": sum(len(a[p] & b[p]) for p in shared)}

# --- judging: the two runs' halves compared by the rounds' pairwise judge (rubric v5, its claims marked one by one),
# and each half's claims checked against the half's own image

def _claim(c):
    return {k: c.get(k, "") for k in ("entity", "attribute", "value", "unit", "conditions", "quote")}

def _unique(claims):
    seen, out = set(), []
    for c in claims:
        ident = (_norm(c.get("entity")), _norm(c.get("attribute")), _value(c))
        if ident not in seen:
            seen.add(ident)
            out.append(_claim(c))
    return out

def pairs(before, after, folder, grown=False, image_side=None):
    """Write a pairwise batch (pairs.json and the tiles' images) into folder: a unit per tile both runs refined, its
    image and text layer the tile's, the before run's halves' claims as the baseline and the after run's as the
    variant. Returns the number of units.

    With grown, only tiles whose halves reach past them, shown grown to every half of both runs (rendered at
    image_side), its text layer by whole lines: halves grown to whole lines, their text by whole lines, read text a
    grid tile cuts off, and a judge shown only the tile took those claims for invented (the bug plan's item 6,
    2026-10-09)."""
    import shutil
    import pymupdf
    folder = Path(folder)
    (folder / "images").mkdir(parents=True, exist_ok=True)
    items = []
    for store in sorted(Path(after).glob("*/store.sqlite")):
        other = Path(before) / store.parent.name / "store.sqlite"
        if not (other.exists() and (other.parent / "report.json").exists() and (store.parent / "report.json").exists()):
            continue
        (rows, new, disk), (_, old, _) = _stored(store), _stored(other)
        with pymupdf.open(disk) as doc:
            for task, row in rows.items():
                if not task.startswith("tile:") or "-r" in task or "-c" in task:
                    continue
                sides = [[c for t, cs in claims.items() if t.startswith(task + "-r") for c in cs] for claims in (old, new)]
                if not any(t.startswith(task + "-r") for t in rows):
                    continue
                image = f"images/{store.parent.name}-{Path(row['image']).name}"
                page = doc[row["page"] - 1]
                shown = pymupdf.Rect(row["bbox"])
                if grown:
                    assert not page.rotation, "a rotated page's boxes would need turning"
                    for rect in (pymupdf.Rect(r["bbox"]) for r in [*rows.values(), *_stored(other)[0].values()]
                                 if r.get("task", "").startswith(task + "-r")):
                        shown |= rect
                    if shown.width <= pymupdf.Rect(row["bbox"]).width + 2 and shown.height <= pymupdf.Rect(row["bbox"]).height + 2:
                        continue
                    from semantic_pdf_diff.extract import render
                    render(page, shown, folder / image, image_side)
                else:
                    shutil.copyfile(store.parent / row["image"], folder / image)
                if grown:  # whole lines, as a refined half's text layer is taken
                    from semantic_pdf_diff.pages import lines
                    text = "\n".join(line for box, line in lines(page) if (box.tl + box.br) / 2 in shown)
                else:
                    text = page.get_text(clip=shown).strip()
                items.append({"id": f"{store.parent.name}|{task}", "page": row["page"], "family": "document",
                              "image": image, "page_text": text,
                              "baseline": _unique(sides[0]), "variant": _unique(sides[1])})
    (folder / "pairs.json").write_text(json.dumps({"items": items}, indent=1) + "\n", encoding="utf-8")
    return len(items)

HALF_CHECK = """This image is part of a page from an engineering document. Below are claims a reader extracted from it, one per line, \
numbered. Check each claim against the image (and the text layer below it) only.

Mark each claim:
- "supported": the image shows this value, for this entity and attribute, with these conditions.
- "misbound": the value is shown, but it belongs to another entity, attribute or condition than the claim says.
- "misread": the claim names something shown, but its value is read wrongly.
- "not shown": the image doesn't show this value at all (it may be elsewhere on the page; that doesn't count here).

Answer JSON: {{"claims": [{{"n": 1, "mark": "supported"}}, ...]}}, one entry for every claim.

TEXT LAYER OF THIS PART:
{layer}

CLAIMS:
{claims}"""

MARKS = ("supported", "misbound", "misread", "not shown")

def half_checks(runs, folder):
    """Write the per-half checks' requests (checks.json and the halves' images) into folder, for every half with
    claims in each named run: runs is {name: folder of per-document stores}. Returns the number of requests."""
    import shutil
    import pymupdf
    folder = Path(folder)
    (folder / "images").mkdir(parents=True, exist_ok=True)
    items = []
    finished = [{s.parent.name for s in Path(d).glob("*/report.json")} for d in runs.values()]
    common = set.intersection(*finished)  # documents every run finished
    for name, runs_dir in runs.items():
        for store in sorted(Path(runs_dir).glob("*/store.sqlite")):
            if store.parent.name not in common:
                continue
            rows, claims, disk = _stored(store)
            with pymupdf.open(disk) as doc:
                for task, row in rows.items():
                    found = _unique(claims.get(task, []))
                    if not (task.startswith("tile:") and "-r" in task and found and row.get("image")):
                        continue
                    image = f"images/{name}-{store.parent.name}-{Path(row['image']).name}"
                    shutil.copyfile(store.parent / row["image"], folder / image)
                    layer = doc[row["page"] - 1].get_text(clip=pymupdf.Rect(row["bbox"])).strip()
                    items.append({"id": f"{name}|{store.parent.name}|{task}", "run": name, "image": image,
                                  "layer": layer, "claims": found})
    (folder / "checks.json").write_text(json.dumps({"items": items}, indent=1) + "\n", encoding="utf-8")
    return len(items)

def check_halves(folder, client, rater):
    """Ask a model to mark each half's claims (checks.json); {run: {mark: count}} written to marks-<rater>.json."""
    from pydantic import Field
    from semantic_pdf_diff.models import Lenient
    from semantic_pdf_diff_lab.eval.judgements import rate

    class Mark(Lenient):
        n: int = 0
        mark: str = ""

    class Marks(Lenient):
        claims: list[Mark] = Field(default_factory=list)
    folder = Path(folder)
    items = json.loads((folder / "checks.json").read_text(encoding="utf-8"))["items"]

    def requests():
        for item in items:
            lines = "\n".join(f"{k}. {c['entity']} | {c['attribute']} | {c['value']}{' ' + c['unit'] if c['unit'] else ''}"
                              f"{' | conditions: ' + c['conditions'] if c['conditions'] else ''} | quote: {c['quote']}"
                              for k, c in enumerate(item["claims"], 1))
            yield (item["id"], HALF_CHECK.format(layer=item["layer"] or "(none)", claims=lines), Marks,
                   [folder / item["image"]], ("half-check", item["id"]))
    answers, errors = rate(client, requests())
    out = {}
    for item in items:
        counts = out.setdefault(item["run"], {m: 0 for m in (*MARKS, "unmarked", "failed")})
        answer = answers.get(item["id"])
        if answer is None:
            counts["failed"] += len(item["claims"])
            continue
        marked = {m.n: m.mark for m in answer.claims if m.mark in MARKS}
        for k in range(1, len(item["claims"]) + 1):
            counts[marked.get(k, "unmarked")] += 1
    (folder / f"marks-{rater.replace('/', '_')}.json").write_text(json.dumps({"marks": out, "errors": errors}, indent=1)
                                                                  + "\n", encoding="utf-8")
    return out

def verdicts(folder, rater):
    """A judge's verdicts on a pairwise batch, summed: per tile, the after run's halves better, worse or the same (both
    orders agreeing; otherwise split), the mean score for the after run, and each side's claims marked ok and wrong."""
    from semantic_pdf_diff_lab.eval.review import reviewer_file
    found = json.loads((Path(folder) / "verdicts" / f"{reviewer_file(rater)}.json").read_text(encoding="utf-8"))
    units = found.get("verdicts", found)
    out = {"tiles": 0, "after better": 0, "before better": 0, "same": 0, "split": 0, "score": 0.0,
           "before ok": 0, "before wrong": 0, "after ok": 0, "after wrong": 0}
    scores = []
    for orders in units.values():
        if not isinstance(orders, dict) or len(orders) < 2:
            continue
        out["tiles"] += 1
        both = [v["score"] for v in orders.values()]
        scores += both
        out["after better" if min(both) == 1 else "before better" if max(both) == 0 else
            "same" if both == [0.5, 0.5] else "split"] += 1
        for v in orders.values():
            for side, name in (("baseline", "before"), ("variant", "after")):
                for mark in (v.get("claims") or {}).get(side, []):
                    if mark["mark"] in ("ok", "wrong"):
                        out[f"{name} {mark['mark']}"] += 1
    out["score"] = round(sum(scores) / len(scores), 3) if scores else None
    return out
