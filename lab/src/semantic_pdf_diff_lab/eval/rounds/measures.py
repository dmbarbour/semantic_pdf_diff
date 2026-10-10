"""What a round measures without judges (from the replay stores and the fixture), the gains named in its
criteria, and the history report. Split from rounds.py (milestone 8).
"""
from collections import defaultdict
from pathlib import Path

from semantic_pdf_diff.regions import FAMILY, region_of
from ..documents import contents
from .units import _reader

def gains(baseline_dir, variant_dir, fixture=None):
    """Measured relative changes a named gain can refer to (models.Gain): "claims" (distinct claims)
    and, given the fixture the runs were replayed from, "tokens" (prompt and completion tokens of the
    queries the runs made). None where it can't be measured."""
    from semantic_pdf_diff import fixtures
    from semantic_pdf_diff.store import Store
    def claims(runs_dir):
        return mechanical(runs_dir).get("all", {}).get("distinct_claims")
    def tokens(runs_dir):
        if not fixture or not Path(fixture).exists():
            return None
        queries = set()
        for folder in (p for p in Path(runs_dir).iterdir() if (p / "store.sqlite").exists()):
            with Store.open(folder) as store:
                queries |= {q["hash"] for q in store.queries()}
        total = 0
        with fixtures.open(fixture, "read") as answers:
            for query in queries:
                usage = answers.usage(query)
                if usage is not None:
                    total += int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
        return total
    out = {}
    for metric, measure in (("claims", claims), ("tokens", tokens)):
        try:
            a, b = measure(baseline_dir), measure(variant_dir)
        except Exception:  # stores from before a schema change, for instance
            a = b = None
        out[metric] = round((b - a) / a, 4) if a and b is not None else None
    return out

# --- mechanical figures (free: from the replay stores and the fixture) ---------------------

def mechanical(runs_dir):
    """Figures that need no reviewer: task outcomes, claims per task, verified quotes, by family."""
    from semantic_pdf_diff.store import Store
    stats = defaultdict(lambda: defaultdict(float))
    read = _reader(runs_dir)
    for folder in sorted(Path(runs_dir).iterdir()):
        if not (folder / "store.sqlite").exists():
            continue
        with Store.open(folder) as store:
            for content in contents(store):  # every format a reader reads (PDFs alone before: review E3)
                for row in store.coverage(content):
                    family = FAMILY.get(region_of(row["task"]))
                    if not family:
                        continue
                    for key in (family, "all"):
                        stats[key]["tasks"] += 1
                        stats[key][row["status"]] += 1
                        stats[key]["claims"] += row.get("claims", 0)
                for e in read(store, content):
                    family = FAMILY.get(e.locator.region)
                    if family:  # distinct claims, as presented (merged readings count once)
                        for key in (family, "all"):
                            stats[key]["distinct_claims"] += 1
                    for o in e.occurrences or [e]:
                        family = FAMILY.get(o.locator.region)
                        if family and o.quote_verified is not None:
                            for key in (family, "all"):
                                stats[key]["checked_quotes"] += 1
                                stats[key]["verified_quotes"] += bool(o.quote_verified)
    out = {}
    for key, s in stats.items():
        tasks = s["tasks"] or 1
        out[key] = {"tasks": int(s["tasks"]), "failed_rate": round(s["failed"] / tasks, 4),
                    "partial_rate": round(s["partial"] / tasks, 4), "claims_per_task": round(s["claims"] / tasks, 3),
                    "distinct_claims": int(s["distinct_claims"]),
                    "verified_quote_rate": round(s["verified_quotes"] / s["checked_quotes"], 4) if s["checked_quotes"] else None}
    return out

# --- the report ------------------------------------------------------------------------------

def report(history_path, target, title="Query improvement"):
    """A self-contained HTML page of every figure recorded in the history, as simple SVG charts."""
    from semantic_pdf_diff.html_pages import esc
    from semantic_pdf_diff.ledger import read
    records = read(history_path)
    rounds = sorted({r.get("round", "") for r in records})

    def chart(series, ylabel, lo=0.0, hi=1.0, height=220, band=None, legend=None):
        """series: {name: [(round, value, low, high)]} drawn over rounds; band draws a line at y.
        legend: a series' legend entry and colour, from its name (default: the name); series sharing
        one aren't joined by lines (the rounds report, item 14 of the 2026-10-01 code review)."""
        legend = legend or (lambda name: name)
        keys = sorted({legend(name) for name in series})
        width, left, bottom, top = 720, 48, 28, 26
        height = max(height, top + 14 * len(keys) + bottom)
        column = (width - left - 10) / max(len(rounds), 1)
        xs = {r: left + (i + 0.5) * column for i, r in enumerate(rounds)}
        y = lambda v: top + (height - bottom - top) * (1 - (v - lo) / ((hi - lo) or 1))
        # Series in the same round sit side by side, not on top of each other, within the round's column.
        present = {r: sorted(name for name, points in series.items() if any(p[0] == r for p in points)) for r in rounds}
        def shift(name, r):
            m = len(present[r])
            return (present[r].index(name) - (m - 1) / 2) * min(14, 0.8 * column / max(m, 1))
        colours = ["#1f6f9f", "#b3261e", "#1d7a46", "#8a6100", "#6b3fa0", "#00796b", "#c2185b", "#455a64"]
        parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(ylabel)}">',
                 f'<text x="4" y="12" class="axis">{esc(ylabel)}</text>']
        for tick in (lo, (lo + hi) / 2, hi):
            parts.append(f'<line x1="{left}" x2="{width - 10}" y1="{y(tick):.1f}" y2="{y(tick):.1f}" class="grid"/>'
                         f'<text x="{left - 6}" y="{y(tick) + 4:.1f}" class="axis" text-anchor="end">{tick:g}</text>')
        if band is not None:
            parts.append(f'<line x1="{left}" x2="{width - 10}" y1="{y(band):.1f}" y2="{y(band):.1f}" class="band"/>')
        for r, x in xs.items():
            parts.append(f'<text x="{x:.1f}" y="{height - 8}" class="axis" text-anchor="middle">{esc(r)}</text>')
        joined = len(keys) == len(series)
        for name, points in sorted(series.items()):
            colour = colours[keys.index(legend(name)) % len(colours)]
            pts = [(xs[r] + shift(name, r), y(v), None if a is None else y(a), None if b is None else y(b))
                   for r, v, a, b in points if r in xs]
            if joined and len(pts) > 1:
                parts.append('<polyline fill="none" stroke="%s" stroke-width="2" points="%s"/>'
                             % (colour, " ".join(f"{px:.1f},{py:.1f}" for px, py, _, _ in pts)))
            for px, py, a, b in pts:
                if a is not None and b is not None:
                    parts.append(f'<line x1="{px:.1f}" x2="{px:.1f}" y1="{a:.1f}" y2="{b:.1f}" stroke="{colour}" stroke-width="2"/>')
                parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{colour}"><title>{esc(name)}</title></circle>')
        for n, key in enumerate(keys):
            parts.append(f'<text x="{width - 12}" y="{top + 12 + 14 * n}" class="legend" text-anchor="end" '
                         f'style="fill:{colours[n % len(colours)]}">{esc(key)}</text>')
        return "".join(parts) + "</svg>"

    def series(metric, by="variant", where=None, per_round=False):
        """The latest value per series and round (steps may record a figure more than once).
        by: the field, or fields, naming a series.
        per_round: one series per round as well, since a variant's name in another round
        is measured against another baseline (joining them would draw a trend that isn't one)."""
        fields = (("round",) if per_round else ()) + ((by,) if isinstance(by, str) else tuple(by))
        latest = {}
        for r in records:
            if r["metric"] == metric and (where is None or where(r)) and r["value"] is not None:
                name = " ".join(str(r.get(f, "")) for f in fields)
                latest[(name, r.get("round", ""))] = r["value"]
        out = defaultdict(list)
        for (name, rnd), value in sorted(latest.items(), key=lambda kv: rounds.index(kv[0][1])):
            if isinstance(value, dict):
                out[name].append((rnd, value["mean"], value["low"], value["high"]))
            else:
                out[name].append((rnd, value, None, None))
        return out

    sections = [
        ("Variant win rate against the baseline (1 = variant always better; interval 90%)",
         chart(series("win_rate", where=lambda r: r.get("stratum") == "all", per_round=True), "win rate", band=0.5)),
        ("Win rate by kind of input (each point a round's variant; hover for its name)",
         chart(series("win_rate", by=("variant", "stratum"), where=lambda r: r.get("stratum") != "all", per_round=True),
               "win rate", band=0.5, legend=lambda name: name.rsplit(" ", 1)[-1])),
        ("Task outcomes (share partial)", chart(series("partial_rate", where=lambda r: r.get("stratum") == "all"), "partial")),
        ("Claims per task", chart(series("claims_per_task", where=lambda r: r.get("stratum") == "all"), "claims", hi=10)),
        ("Quotes verified against the text layer", chart(series("verified_quote_rate", where=lambda r: r.get("stratum") == "all"),
                                                         "verified")),
        ("Spend per round (US$)", chart(series("spent", by="step"), "$", hi=max([r["value"] for r in records
                                                                                 if r["metric"] == "spent"] or [1]) * 1.2)),
    ]
    decisions = [r for r in records if r["metric"] == "decision"]
    rows = "".join(f"<tr><td>{esc(r.get('round'))}</td><td>{esc(r.get('variant'))}</td><td>{esc(r['value'])}</td></tr>"
                   for r in decisions)
    from semantic_pdf_diff.html_pages import page as html_page
    style = """
body{margin:0;font:15px/1.45 system-ui,sans-serif}main{max-width:980px;margin:auto;padding:16px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:12px 0}
h1{font-size:22px}h2{font-size:15px;margin:0 0 8px}svg{width:100%;height:auto}
.axis,.legend{font-size:11px;fill:var(--muted)}.legend{font-weight:600}.grid{stroke:var(--line)}.band{stroke:var(--muted);stroke-dasharray:4 4}
table{border-collapse:collapse;width:100%}td{border-bottom:1px solid var(--line);padding:6px}
"""
    page = f"""<main><h1>{esc(title)}</h1><p>{len(records)} figures over {len(rounds)} round(s), from <code>{esc(Path(history_path).name)}</code>.</p>
{"".join(f"<section><h2>{esc(h)}</h2>{svg}</section>" for h, svg in sections)}
<section><h2>Decisions</h2><table>{rows or "<tr><td>none yet</td></tr>"}</table></section></main>"""
    page = html_page(title, page, style)
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    Path(target).write_text(page, encoding="utf-8")
    return target
