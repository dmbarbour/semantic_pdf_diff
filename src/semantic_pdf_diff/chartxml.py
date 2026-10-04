"""Charts stored as chart XML (DrawingML charts in Word documents, and later PowerPoint's; the adapters plan: "chart
XML, which holds the actual series data ... Chart XML beats estimating values from pixels"; the owner, 2026-10-04:
"Please proceed with Word charts next.").

A chart part keeps, beside its drawing instructions, the values it shows (a cache of the workbook it was made from).
Each chart is read from that cache as tables:

- **Categories by series:** a row per category, a column per series, for column, bar, line, area, pie, doughnut,
  radar, stock and surface charts, a combination's groups side by side.
- **Points:** a row per point ("Series | X | Y", and the bubble's size), for scatter and bubble charts.
- **Values as shown:** each in its series' number format ("#,##0" gives 1,750; "0.0%" gives 12.5%; a date format, an
  ISO date); "General", the shortest exact form.
- **What it says of itself:** its title, its kind ("clustered column chart"), its axes' titles: the label that
  precedes its tables.

Not read: the workbook itself (the cache is what the chart shows), and charts of the newer kinds (chartex:
waterfall, histogram, treemap, sunburst), which callers record as not read.
"""
import datetime
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
FALLBACK = "{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback"
POINTS = ("scatterChart", "bubbleChart")
KINDS = {"barChart": "bar", "bar3DChart": "bar", "lineChart": "line", "line3DChart": "line", "areaChart": "area",
         "area3DChart": "area", "pieChart": "pie", "pie3DChart": "pie", "ofPieChart": "pie of pie",
         "doughnutChart": "doughnut", "radarChart": "radar", "scatterChart": "scatter", "bubbleChart": "bubble",
         "stockChart": "stock", "surfaceChart": "surface", "surface3DChart": "surface"}
GROUPING = {"clustered": "clustered", "stacked": "stacked", "percentStacked": "100% stacked"}

@dataclass
class Series:
    name: str
    group: str                   # the chart group's tag ("barChart")
    categories: dict = field(default_factory=dict)  # point index: label (or x, for points)
    values: dict = field(default_factory=dict)      # point index: value as shown (or y, for points)
    sizes: dict = field(default_factory=dict)       # a bubble's size by point

@dataclass
class Chart:
    title: str
    kinds: list                  # "clustered column chart", "line chart", in the plot's order
    category_axis: str           # the axes' titles ("" untitled)
    value_axes: list
    series: list
    tables: list = field(default_factory=list)      # [(header, rows)]

    def label(self, caption=""):
        """The line preceding the chart's tables: "Chart: Monthly use (clustered column chart); values: MWh"."""
        kinds = " and ".join(self.kinds) or "chart"
        parts = [f"Chart: {self.title} ({kinds})" if self.title else f"Chart ({kinds})"]
        if self.category_axis:
            parts.append(f"categories: {self.category_axis}")
        if self.value_axes:
            parts.append("values: " + ", ".join(self.value_axes))
        if caption:
            parts.append(f"caption: {caption}")
        return "; ".join(parts)

def _children(element):
    """An element's children, without the copies kept for older readers (mc:Fallback); mc:Choice read through."""
    for child in element:
        if child.tag == FALLBACK:
            continue
        if child.tag.endswith("}AlternateContent") or child.tag.endswith("}Choice"):
            yield from _children(child)
        else:
            yield child

def _find(element, tag):
    return next((c for c in _children(element) if c.tag == C + tag), None) if element is not None else None

def _rich(element):
    """A title's text, its runs joined ("Readiness for a WI" + " (%)")."""
    if element is None:
        return ""
    paragraphs = ["".join(t.text or "" for t in p.iter(A + "t")) for p in element.iter(A + "p")]
    text = " ".join(p.strip() for p in paragraphs if p.strip())
    if not text:  # a title taken from a cell: its cached text
        text = " ".join(v.text or "" for v in element.iter(C + "v")).strip()
    return " ".join(text.split())

def _points(element, date1904):
    """{point index: text as shown} from a string, number or multi-level cache (or literal values)."""
    if element is None:
        return {}
    out = {}
    multi = next(element.iter(C + "multiLvlStrCache"), None)
    if multi is not None:  # several levels of labels: the outer ones last, joined from the outermost
        levels = [{int(pt.get("idx")): (pt.findtext(C + "v") or "") for pt in lvl.iter(C + "pt")}
                  for lvl in multi.iter(C + "lvl")]
        for i in sorted(levels[0]) if levels else ():  # the first level is the innermost: each label's own
            names = []
            for level in reversed(levels):  # outer groups start at an index and run to the next
                below = [k for k in level if k <= i]
                if below and level[max(below)]:
                    names.append(level[max(below)])
            out[i] = " > ".join(names)
        return out
    for cache in element.iter(C + "strCache", C + "numCache", C + "strLit", C + "numLit"):
        code = cache.findtext(C + "formatCode") or "General"
        number = cache.tag in (C + "numCache", C + "numLit")
        for pt in cache.iter(C + "pt"):
            raw = pt.findtext(C + "v") or ""
            out[int(pt.get("idx", 0))] = format_number(raw, pt.get("formatCode") or code, date1904) if number else raw
        return out
    return out

def _name(series, index):
    tx = _find(series, "tx")
    if tx is not None:
        cached = [v.text or "" for v in tx.iter(C + "v")]
        if cached and cached[0].strip():
            return cached[0].strip()
    return f"Series {index + 1}"

def _kind(group):
    tag = group.tag[len(C):]
    name = KINDS.get(tag, tag)
    if name == "bar":
        direction = _find(group, "barDir")
        name = "column" if direction is None or direction.get("val") == "col" else "bar"
    grouping = _find(group, "grouping")
    prefix = GROUPING.get(grouping.get("val"), "") if grouping is not None else ""
    if prefix == "clustered" and not tag.startswith("bar"):
        prefix = ""
    return f"{prefix} {name} chart".strip()

def read(blob):
    """A chart part's bytes as a Chart, its tables made."""
    from lxml import etree
    root = etree.fromstring(blob)
    date1904 = (_find(root, "date1904") is not None and _find(root, "date1904").get("val") in ("1", "true"))
    chart = _find(root, "chart")
    if chart is None:
        raise ValueError("no chart in the chart part")
    plot = _find(chart, "plotArea")
    groups = [g for g in _children(plot) if g.tag[len(C):] in KINDS] if plot is not None else []
    axes = {}  # id: (kind, title, position)
    for axis in (_children(plot) if plot is not None else ()):
        if axis.tag in (C + "catAx", C + "valAx", C + "dateAx", C + "serAx") and _find(axis, "axId") is not None:
            position = _find(axis, "axPos")
            axes[_find(axis, "axId").get("val")] = (axis.tag[len(C):], _rich(_find(axis, "title")),
                                                    position.get("val") if position is not None else "")
    series = []
    for group in groups:
        tag = group.tag[len(C):]
        for ser in (s for s in _children(group) if s.tag == C + "ser"):
            order = _find(ser, "order")
            k = int(order.get("val")) if order is not None else len(series)
            s = Series(_name(ser, k), tag)
            if tag in POINTS:
                s.categories, s.values = _points(_find(ser, "xVal"), date1904), _points(_find(ser, "yVal"), date1904)
                s.sizes = _points(_find(ser, "bubbleSize"), date1904)
            else:
                s.categories, s.values = _points(_find(ser, "cat"), date1904), _points(_find(ser, "val"), date1904)
            series.append(s)
    title = _rich(_find(chart, "title"))
    deleted = _find(chart, "autoTitleDeleted")
    if not title and len(series) == 1 and not (deleted is not None and deleted.get("val") in ("1", "true")):
        title = series[0].name  # as Word shows a lone series' chart
    used = [axes[a] for a in dict.fromkeys(ax.get("val") for g in groups for ax in _children(g) if ax.tag == C + "axId")
            if a in axes]
    across = [t for kind, t, position in used if kind in ("catAx", "dateAx")]
    if not across and any(g.tag[len(C):] in POINTS for g in groups):  # a scatter's x: the value axis lying flat
        across = [t for kind, t, position in used if kind == "valAx" and position in ("b", "t")]
    category = next((t for t in across if t), "")
    values = list(dict.fromkeys(t for kind, t, position in used if kind == "valAx" and t and t != category))
    out = Chart(title, list(dict.fromkeys(_kind(g) for g in groups)), category, values, series)
    out.tables = _tables(out)
    return out

def _tables(chart):
    """[(header, rows)]: categories by series; then points, one row each."""
    out = []
    by_category = [s for s in chart.series if s.group not in POINTS]
    if by_category:
        labels = {}
        for s in by_category:
            for i, label in s.categories.items():
                labels.setdefault(i, label)
        indexes = sorted(set(labels) | {i for s in by_category for i in s.values})
        header = [chart.category_axis or "Category"] + [s.name for s in by_category]
        rows = [[labels.get(i, str(i + 1))] + [s.values.get(i, "") for s in by_category] for i in indexes]
        out.append((header, rows))
    points = [s for s in chart.series if s.group in POINTS]
    if points:
        bubbles = any(s.sizes for s in points)
        header = ["Series", chart.category_axis or "X", (chart.value_axes or ["Y"])[0]] + (["Size"] if bubbles else [])
        rows = [[s.name, s.categories.get(i, str(i + 1)), s.values.get(i, "")] + ([s.sizes.get(i, "")] if bubbles else [])
                for s in points for i in sorted(set(s.values) | set(s.categories))]
        out.append((header, rows))
    return out

# --- number formats ---------------------------------------------------------------------------------------------

LITERAL = re.compile(r'"([^"]*)"|\\(.)|\[[^\]]*\]|_.|\*.')

def _literal(part):
    """A format's literal text: quoted strings and escaped characters kept, colours, spacing and fills dropped."""
    return LITERAL.sub(lambda m: m.group(1) if m.group(1) is not None else (m.group(2) or ""), part).replace("%", "")

def format_number(raw, code="General", date1904=False):
    """A cached number as its format's first section shows it (a negative number signed): thousands separators,
    decimals, percent, scientific notation, a currency or unit around it, a date; "General" (or a format not
    understood), its shortest exact form."""
    try:
        x = float(raw)
    except ValueError:
        return raw
    section = (code or "General").split(";")[0]
    bare = LITERAL.sub("", section)
    if not bare.strip() or bare.strip().lower() == "general":
        return _general(x)
    if re.search(r"[ymdhs]", bare.lower().replace("e+", "").replace("e-", "")):
        base = datetime.datetime(1904, 1, 1) if date1904 else datetime.datetime(1899, 12, 30)
        moment = base + datetime.timedelta(days=x)
        return moment.date().isoformat() if not re.search(r"[hs]", bare.lower()) else moment.isoformat(" ")
    digits = re.search(r"[#0?][#0?,]*(?:\.[#0?]*)?", bare)
    if digits is None:
        return _general(x)
    pattern = digits.group(0)
    decimals = len(pattern.split(".", 1)[1]) if "." in pattern else 0
    percent = "%" in bare
    if re.search(r"E[+-]", bare, re.I):
        text = f"{x:.{decimals}E}"
    else:  # the cached digits rounded half away from zero, as Office shows them
        exact = Decimal(raw.strip()) * (100 if percent else 1)
        rounded = exact.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
        text = f"{rounded:{',' if ',' in pattern.split('.')[0] else ''}.{decimals}f}"
    first = re.search(r"[#0?]", section)
    last = max(section.rfind(c) for c in "#0?")
    prefix, suffix = _literal(section[:first.start()]), _literal(section[last + 1:])
    if re.search(r"E[+-]", bare, re.I):
        suffix = re.sub(r"^[eE][+-]0*", "", suffix)
    return f"{prefix}{text}{'%' if percent else ''}{suffix}".strip()

def _general(x):
    return str(int(x)) if x == int(x) and abs(x) < 1e15 else f"{x:.15g}"
