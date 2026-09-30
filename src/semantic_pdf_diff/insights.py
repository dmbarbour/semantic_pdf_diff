"""Why a variant won or lost: per-unit analysis of a pairwise batch, and a browsable page per round.

A decision says how often a variant won; this module keeps the clues to why, so refinement isn't
blind (the owner, 2026-09-27):
- agreement: each judge's score in each order, whether judges agree and whether a judge flipped
  with the order (split units are the ambiguous ones, worth a look);
- what changed: claims only in the baseline, only in the variant, and shared;
- the model's own issue notes, per side (e.g. "the image is blank", "only administrative metadata");
- the judges' notes, their problem tags per side and their remarks for the maintainers (rubric v2).

    analyse(batch_folder, limit)  -> writes analysis.json beside pairs.json
    page(round_folder)            -> writes insights.html in the round folder
"""
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from . import judgements
from .rounds import FAMILY

def _issues(runs_dir, run, content, page, family):
    """{issue: tasks} the model reported for one unit's tasks, from a replay store."""
    from .store import Store, StoreError
    folder = Path(runs_dir) / run
    if not (folder / "store.sqlite").exists():
        return {}
    found = Counter()
    try:
        store = Store(folder)
    except StoreError:  # a store kept at an older schema (rounds before 2026-09-28): no issues to show
        return {}
    with store:
        for row in store.coverage(content):
            region = FAMILY.get(row["task"].split(":")[0])
            if row.get("page") == page and region and family in (region, "page"):
                for issue in row.get("issues") or ():
                    found[" ".join(str(issue).split())[:300]] += 1
    return dict(found)

def _claim_key(c):
    """A claim's identity, as rounds.collect gives it; batches from before 2026-09-30 carry none."""
    return c.get("_id") or (c["entity"].casefold(), c["attribute"].casefold(), str(c["value"]).casefold(),
                            c.get("unit", ""), c.get("conditions", "").casefold())

def analyse(folder, limit=None):
    """Per-unit clues for a batch (the first `limit` units); writes and returns analysis.json."""
    folder = Path(folder)
    batch = json.loads((folder / "pairs.json").read_text(encoding="utf-8"))
    items = batch["items"][:limit]
    verdicts = judgements.by_rater(judgements.read(folder))
    units = []
    for item in items:
        by_judge = {j: v[item["id"]] for j, v in verdicts.items() if item["id"] in v}
        scores = {j: {o: x["score"] for o, x in orders.items()} for j, orders in by_judge.items()}
        flat = [s for orders in scores.values() for s in orders.values()]
        if not flat:
            continue
        leaning = {j: (sum(o.values()) / len(o) > 0.5) - (sum(o.values()) / len(o) < 0.5) for j, o in scores.items()}
        flipped = sorted(j for j, o in scores.items() if len(o) == 2 and len({s for s in o.values()}) > 1
                         and 0.5 not in o.values())
        base_keys = {_claim_key(c): c for c in item["baseline"]}
        var_keys = {_claim_key(c): c for c in item["variant"]}
        problems = {"baseline": Counter(), "variant": Counter()}
        remarks, notes = [], []
        for judge, orders in by_judge.items():
            for order, x in orders.items():
                notes.append({"judge": judge, "order": order, "score": x["score"], "note": x.get("note", "")})
                for side in ("baseline", "variant"):
                    problems[side].update(x.get(f"{side}_problems") or ())
                if x.get("remarks"):
                    remarks.append({"judge": judge, "order": order, "remark": x["remarks"]})
        issues = {side: _issues(batch[side], item["run"], item["content"], item["page"], item["family"])
                  for side in ("baseline", "variant")}
        units.append({
            "id": item["id"], "run": item["run"], "page": item["page"], "family": item["family"],
            "image": item["image"], "score": round(sum(flat) / len(flat), 3), "scores": scores,
            "judges_disagree": len({v for v in leaning.values() if v}) > 1, "order_flipped": flipped,
            "counts": item.get("counts", {}),
            "only_baseline": [c for k, c in base_keys.items() if k not in var_keys],
            "only_variant": [c for k, c in var_keys.items() if k not in base_keys],
            "problems": {side: dict(c) for side, c in problems.items()},
            "issues": {"baseline": {k: v for k, v in issues["baseline"].items() if k not in issues["variant"]},
                       "variant": {k: v for k, v in issues["variant"].items() if k not in issues["baseline"]}},
            "notes": notes, "remarks": remarks})
    summary = {"units": len(units),
               "by_document": _means(units, "run"), "by_family": _means(units, "family"),
               "problems": {side: dict(sum((Counter(u["problems"][side]) for u in units), Counter()))
                            for side in ("baseline", "variant")},
               "split": [u["id"] for u in units if u["judges_disagree"] or u["order_flipped"]],
               "remarks": sum(len(u["remarks"]) for u in units)}
    result = {"batch": folder.name, "summary": summary, "units": units}
    (folder / "analysis.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result

def _means(units, field):
    groups = defaultdict(list)
    for u in units:
        groups[u[field]].append(u["score"])
    return {k: {"units": len(v), "mean": round(sum(v) / len(v), 3)} for k, v in sorted(groups.items())}

# --- the page -----------------------------------------------------------------------------------

STYLE = """
:root { --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6a64; --line:#dedbd2; --card:#ffffff; --win:#2f7d4f; --loss:#b23b3b;
        --even:#8a7a35; --accent:#2c5d8f; }
@media (prefers-color-scheme: dark) { :root { --bg:#17181a; --fg:#e9e7e1; --muted:#9d9b94; --line:#34363a;
        --card:#202226; --win:#63b884; --loss:#e07a7a; --even:#cdb85f; --accent:#7fb0e0; } }
body { background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; margin:0 auto; max-width:1100px;
       padding:16px; }
h1 { font-size:1.5rem; } h2 { font-size:1.2rem; margin-top:2rem; border-top:1px solid var(--line); padding-top:1rem; }
h3 { font-size:1rem; } .muted { color:var(--muted); } table { border-collapse:collapse; margin:.5rem 0; }
td, th { border-bottom:1px solid var(--line); padding:3px 10px 3px 0; text-align:left; vertical-align:top; }
details { background:var(--card); border:1px solid var(--line); border-radius:6px; margin:6px 0; padding:6px 10px; }
summary { cursor:pointer; } .win { color:var(--win); } .loss { color:var(--loss); } .even { color:var(--even); }
.tag { display:inline-block; border:1px solid var(--line); border-radius:10px; padding:0 7px; margin:1px; font-size:.85em; }
.bar { display:inline-block; height:9px; vertical-align:middle; } .claims { font-size:.9em; }
img { max-width:100%; border:1px solid var(--line); } .grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width:700px) { .grid { grid-template-columns:1fr; } }
"""

def _score_class(s):
    return "win" if s > 0.5 else "loss" if s < 0.5 else "even"

def _claims(claims):
    esc = html.escape
    return "".join(f"<li>{esc(c['entity'])} | {esc(c['attribute'])} | <b>{esc(str(c['value']))} {esc(c.get('unit', ''))}</b>"
                   + (f" | {esc(c['conditions'])}" if c.get("conditions") else "") + "</li>" for c in claims) or "<li>none</li>"

def page(round_folder):
    """insights.html for a round: per variant, its decision, where it won and lost, why (tags,
    notes, the model's issues), what changed, and the judges' remarks."""
    round_folder = Path(round_folder)
    spec = json.loads((round_folder / "round.json").read_text())
    esc = html.escape
    out = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>Round {esc(spec['name'])} insights</title><style>{STYLE}</style></head><body>",
           f"<h1>Round {esc(spec['name'])}: why variants won or lost</h1><p class='muted'>{esc(spec.get('note', ''))}</p>"]
    for variant in spec["variants"]:
        batch = round_folder / f"pairs-{variant}"
        if not (batch / "analysis.json").exists():
            continue
        a = json.loads((batch / "analysis.json").read_text(encoding="utf-8"))
        decision = json.loads((batch / "decision.json").read_text()) if (batch / "decision.json").exists() else {}
        s = a["summary"]
        o = decision.get("overall") or {}
        out.append(f"<h2>{esc(variant)}</h2><p><b>{esc(decision.get('decision', 'not decided'))}</b>"
                   + (f": {o['mean']:.2f} ({o['low']:.2f}–{o['high']:.2f})" if o else "")
                   + f" over {s['units']} units; {len(s['split'])} split (judges disagree or flip with order);"
                     f" {s['remarks']} remark(s).</p>")
        out.append("<div class='grid'><div><h3>By document</h3><table>" + "".join(
            f"<tr><td>{esc(k)}</td><td>{v['units']}</td><td class='{_score_class(v['mean'])}'>{v['mean']:.2f}</td></tr>"
            for k, v in s["by_document"].items()) + "</table><h3>By kind</h3><table>" + "".join(
            f"<tr><td>{esc(k)}</td><td>{v['units']}</td><td class='{_score_class(v['mean'])}'>{v['mean']:.2f}</td></tr>"
            for k, v in s["by_family"].items()) + "</table></div>")
        tags = sorted(set(s["problems"]["baseline"]) | set(s["problems"]["variant"]))
        if tags:
            top = max(max(s["problems"]["baseline"].values(), default=1), max(s["problems"]["variant"].values(), default=1))
            out.append("<div><h3>Problems judges tagged</h3><table><tr><th>tag</th><th>baseline</th><th>variant</th></tr>"
                       + "".join(f"<tr><td>{esc(t)}</td>"
                                 + "".join(f"<td><span class='bar' style='width:{60 * s['problems'][side].get(t, 0) / top:.0f}px;"
                                           f"background:var(--{'loss' if side == 'variant' else 'accent'})'></span> "
                                           f"{s['problems'][side].get(t, 0)}</td>" for side in ("baseline", "variant"))
                                 + "</tr>" for t in tags) + "</table></div></div>")
        else:
            out.append("<div><h3>Problems judges tagged</h3><p class='muted'>No tags: judged with rubric v1.</p></div></div>")
        issues = {side: Counter() for side in ("baseline", "variant")}
        for u in a["units"]:
            for side in issues:
                issues[side].update(u["issues"][side])
        for side in ("variant", "baseline"):
            if issues[side]:
                out.append(f"<h3>The model's issue notes only on the {side} side</h3><ul class='claims'>" + "".join(
                    f"<li>{esc(k)} <span class='muted'>×{n}</span></li>" for k, n in issues[side].most_common(12)) + "</ul>")
        remarks = [(u["run"], u["page"], r) for u in a["units"] for r in u["remarks"]]
        if remarks:
            out.append("<h3>Judges' remarks for us</h3><ul class='claims'>" + "".join(
                f"<li><span class='muted'>{esc(run)} p{p}, {esc(r['judge'].split('/')[-1])}:</span> {esc(r['remark'])}</li>"
                for run, p, r in remarks) + "</ul>")
        out.append("<h3>Units, losses first</h3>")
        for u in sorted(a["units"], key=lambda u: (u["score"], u["id"])):
            flags = ("<span class='tag'>judges disagree</span>" if u["judges_disagree"] else "") + \
                    ("<span class='tag'>order flip: " + esc(", ".join(j.split('/')[-1] for j in u["order_flipped"])) + "</span>"
                     if u["order_flipped"] else "")
            tags = "".join(f"<span class='tag'>{side[0]}: {esc(t)} ×{n}</span>" for side in ("baseline", "variant")
                           for t, n in sorted(u["problems"][side].items()))
            out.append(
                f"<details><summary><b class='{_score_class(u['score'])}'>{u['score']:.2f}</b> {esc(u['run'])} p{u['page']}"
                f" {esc(u['family'])} {flags}</summary><p>{tags}</p>"
                + "".join(f"<p><span class='muted'>{esc(n['judge'].split('/')[-1])}, {esc(n['order'])},"
                          f" <span class='{_score_class(n['score'])}'>{n['score']}</span>:</span> {esc(n['note'])}</p>"
                          for n in u["notes"])
                + "".join(f"<p><span class='muted'>model issue ({side} only):</span> {esc(k)}</p>"
                          for side in ("baseline", "variant") for k in u["issues"][side])
                + f"<div class='grid'><div><b>Only in baseline</b> <span class='muted'>(of the claims shown to judges)</span>"
                  f"<ul class='claims'>{_claims(u['only_baseline'])}</ul></div><div><b>Only in variant</b>"
                  f"<ul class='claims'>{_claims(u['only_variant'])}</ul></div></div>"
                + f"<p><a href='pairs-{esc(variant)}/{esc(u['image'])}'>page image</a></p></details>")
    out.append("</body></html>")
    target = round_folder / "insights.html"
    target.write_text("\n".join(out), encoding="utf-8")
    return target
