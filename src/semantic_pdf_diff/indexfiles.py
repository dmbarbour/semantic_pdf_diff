"""A report's indexes as files beside it (docs/plans/indexes-and-glossaries-2026-10-29.md; the owner, 2026-10-29,
choosing Markdown, CSV and JSON, and "An excel file is also a good representation for indices. We already output
excel workbooks of claims, but not really designed as an indexing model."):

- **index.md:** subjects A to Z, each with its properties and every value with where it's said (in a comparison, each
  source's beside the others'); then properties, each with the subjects giving it; then figures and tables.
- **index/*.csv:** subjects, properties, claims, figures: a row a value (or claim, or figure), for filtering.
- **index.xlsx:** a sheet per index, its header frozen and filtered. Subjects is an outline: a subject's row, its
  values beneath it, grouped so a subject collapses to its row (Excel's outline, the 1 and 2 at the left). Written
  as OOXML here, the same bytes for the same index (no workbook library: openpyxl is the office extra's, for reading).
"""
import csv
import io
import re
import zipfile
from xml.sax.saxutils import escape

from .indexes import properties

FIXED_TIME = (2026, 1, 1, 0, 0, 0)  # every member's, so the same index gives the same bytes
# A value printed as a plain number, stored as one so it sorts and filters as one; not one with a leading zero (a
# tag, "007") nor of more digits than Excel keeps (15).
NUMBER = re.compile(r"-?(?:0|[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)(?:\.\d+)?")

def said(v):
    """A value as written: its value, unit (none for "-") and conditions."""
    unit = "" if v["unit"] in ("", "-") else v["unit"]
    return " ".join(x for x in (str(v["value"]), unit) if x) + (f" ({v['conditions']})" if v["conditions"] else "")

def counted(n, one, many=None):
    """ "1 claim", "2 claims"."""
    return f"{n} {one if n == 1 else many or one + 's'}"

def title(index):
    return " ↔ ".join(index["sources"]) or "(no source)"

# --- index.md ------------------------------------------------------------------------------------------------------

def markdown(index):
    """index.md's text."""
    sources, many = index["sources"], len(index["sources"]) > 1
    lines = [f"# Index: {title(index)}", "",
             f"{len(index['subjects'])} subjects, {len(properties(index))} properties, "
             f"{sum(len(c) for s in index['subjects'] for c in s['claims'].values())} claims, "
             f"{len(index['figures'])} figures and tables. Read by a model: check a value against its place before "
             "relying on it." + (" A source giving nothing for a subject or property another gives is marked “—”: "
                                 "not saying isn't evidence of absence." if many else ""), "", "## Subjects", ""]
    for s in index["subjects"]:
        names = [n for n in s["names"] if n.casefold() != s["name"].casefold()]
        lines.append(f"### {s['name']}" + (f" (also {', '.join(names[:5])})" if names else ""))
        if many:
            lines.append("Claims: " + "; ".join(f"{src} {len(s['claims'].get(src, []))}" for src in sources)
                         + (f" (matched by {s['matched_by']})" if s["matched_by"] else ""))
        lines.append("")
        for p in s["properties"]:
            if many:
                by = {src: [v for v in p["values"] if v["source"] == src] for src in sources}
                lines.append(f"- **{p['name']}**: " + "; ".join(
                    f"{src}: " + (", ".join(f"{said(v)} ({v['where']})" for v in by[src]) if by[src] else "—")
                    for src in sources))
            else:
                lines.append(f"- **{p['name']}**: " + "; ".join(f"{said(v)} ({v['where']})" for v in p["values"]))
        lines.append("")
    lines += ["## Properties", ""]
    for p in properties(index):
        lines.append(f"- **{p['name']}**: " + "; ".join(
            f"{x['subject']} " + ", ".join(said(v) + (f" ({v['source']})" if many else "") for v in x["values"])
            for x in p["subjects"]))
    lines += ["", "## Figures and tables", ""]
    for f in index["figures"]:
        name = " ".join(x for x in (f["label"], f"“{f['title']}”" if f["title"] else "") if x) or f["kind"]
        place = (f"{f['source']}: " if many else "") + f["file"] + (f", page {f['page']}" if f["page"] else "")
        lines.append(f"- **{name}** ({place})" + (f": {f['about'].rstrip('.')}" if f["about"] else "")
                     + (f"; {counted(len(f['claims']), 'claim')}" if f["claims"] else "")
                     + ("; cited once" if f["cited"] == 1 else f"; cited {f['cited']} times" if f["cited"] else ""))
    return "\n".join(lines).rstrip() + "\n"

# --- the tables: CSV and the workbook's sheets ---------------------------------------------------------------------

def tables(index, evidence):
    """{name: (header, rows)}: subjects, properties, claims and figures, a row a value, claim or figure. evidence:
    the report's claims, by id."""
    subject_of = {cid: s["name"] for s in index["subjects"] for ids in s["claims"].values() for cid in ids}
    value = lambda v: [v["value"], v["unit"], v["conditions"], v["source"], v["where"], v["claim"]]
    subjects = [[s["name"], p["name"], *value(v)] for s in index["subjects"] for p in s["properties"]
                for v in p["values"]]
    props = [[p["name"], x["subject"], *value(v)] for p in properties(index) for x in p["subjects"]
             for v in x["values"]]
    claims = [[e["id"], subject_of.get(e["id"], ""), e["entity"], e["attribute"], e["value"], e["unit"],
               e.get("conditions", ""), e["kind"], e.get("quote", "")] for e in evidence.values()]
    figures = [[f["source"], f["file"], f["page"] if f["page"] is not None else "", f["kind"], f["label"], f["title"],
                f["about"], len(f["claims"]), f["cited"]] for f in index["figures"]]
    tail = ["Value", "Unit", "Conditions", "Source", "Where", "Claim"]
    return {"subjects": (["Subject", "Property", *tail], subjects),
            "properties": (["Property", "Subject", *tail], props),
            "claims": (["Claim", "Subject", "Item", "Property", "Value", "Unit", "Conditions", "Read as", "Quote"],
                       claims),
            "figures": (["Source", "File", "Page", "Kind", "Label", "Title", "About", "Claims", "Cited"], figures)}

def csv_text(header, rows):
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()

# --- index.xlsx ----------------------------------------------------------------------------------------------------

WIDTHS = {"Subject": 32, "Property": 28, "Value": 14, "Unit": 9, "Conditions": 24, "Source": 14, "Where": 30,
          "Claim": 14, "Item": 28, "Read as": 9, "Quote": 50, "File": 30, "Page": 6, "Kind": 8, "Label": 16,
          "Title": 40, "About": 60, "Claims": 8, "Cited": 7}
BOLD, MUTED = 1, 2  # the styles' indexes (STYLES)

def column(i):
    name = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        name = chr(65 + r) + name
    return name

def cell(ref, v, style=0):
    s = f' s="{style}"' if style else ""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f'<c r="{ref}"{s}><v>{v}</v></c>'
    text = str(v)
    if NUMBER.fullmatch(text) and sum(ch.isdigit() for ch in text) <= 15:
        return f'<c r="{ref}"{s}><v>{text.replace(",", "")}</v></c>'
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)[:32767]
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'

def sheet(header, rows, outline=None, widths=None):
    """A worksheet's XML: the header bold, frozen and filtered (no header: rows alone). outline: each row's (level,
    style), a subject's row 0 and its values 1, so a subject collapses to its row."""
    widths = widths or [WIDTHS.get(h, 14) for h in header]
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths))
    out = ['<row r="1">' + "".join(cell(f"{column(i)}1", h, BOLD) for i, h in enumerate(header)) + "</row>"
           ] if header else []
    first = 2 if header else 1
    for n, row in enumerate(rows, first):
        level, style = outline[n - first] if outline else (0, 0)
        attrs = f' outlineLevel="{level}"' if level else ""
        out.append(f'<row r="{n}"{attrs}>' + "".join(cell(f"{column(i)}{n}", v, style if i == 0 else 0)
                                                     for i, v in enumerate(row) if v != "") + "</row>")
    last = f"{column(len(header) - 1)}{max(1, len(rows) + 1)}" if header else ""
    frozen = ('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
              'state="frozen"/></sheetView></sheetViews>' if header else
              '<sheetViews><sheetView workbookViewId="0"/></sheetViews>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            + ('<sheetPr><outlinePr summaryBelow="0"/></sheetPr>' if outline else "") + frozen
            + ('<sheetFormatPr defaultRowHeight="15" outlineLevelRow="1"/>' if outline else "")
            + f"<cols>{cols}</cols><sheetData>{''.join(out)}</sheetData>"
            + (f'<autoFilter ref="A1:{last}"/>' if header else "") + "</worksheet>")

STYLES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
          '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font>'
          '<font><b/><sz val="11"/><name val="Calibri"/></font>'
          '<font><sz val="11"/><color rgb="FF808080"/><name val="Calibri"/></font></fonts>'
          '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/>'
          '</fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
          '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
          '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
          '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')

def workbook(index, evidence):
    """index.xlsx's bytes: About, Subjects (an outline), Properties, Claims and Figures sheets."""
    found = tables(index, evidence)
    header, rows = found["subjects"]
    outlined, outline = [], []
    for s in index["subjects"]:
        n = sum(len(c) for c in s["claims"].values())
        others = [x for x in s["names"] if x.casefold() != s["name"].casefold()]
        outlined.append([s["name"], f"{counted(len(s['properties']), 'property', 'properties')}, {counted(n, 'claim')}"
                         + (f"; also {', '.join(others)[:200]}" if others else "")])
        outline.append((0, BOLD))
        for p in s["properties"]:
            for v in p["values"]:
                outlined.append([s["name"], p["name"], v["value"], v["unit"], v["conditions"], v["source"],
                                 v["where"], v["claim"]])
                outline.append((1, MUTED))
    about = [["Index", title(index)], ["Subjects", len(index["subjects"])],
             ["Properties", len(properties(index))], ["Claims", len(evidence)], ["Figures and tables",
                                                                                 len(index["figures"])],
             ["Subjects sheet", "A subject's row, then its values: the 1 and 2 at the left collapse or open them all"],
             ["Caution", "Read by a model: check a value against its place (Where) before relying on it"]]
    sheets = [("About", sheet([], about, widths=[20, 90])), ("Subjects", sheet(header, outlined, outline))]
    sheets += [(name.title(), sheet(*found[name])) for name in ("properties", "claims", "figures")]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name, text):
            info = zipfile.ZipInfo(name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, text)
        put("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/'
                      'vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                      for i in range(1, len(sheets) + 1)) + "</Types>")
        put("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="xl/workbook.xml"/></Relationships>')
        put("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + "".join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheets, 1))
            + "</sheets></workbook>")
        put("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                      f'relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
            + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/styles" Target="styles.xml"/></Relationships>')
        put("xl/styles.xml", STYLES)
        for i, (_, xml) in enumerate(sheets, 1):
            put(f"xl/worksheets/sheet{i}.xml", xml)
    return out.getvalue()

def written(index, evidence, folder):
    """The index's files written into folder (a report's): index.md, index.xlsx and index/*.csv. Returns their
    paths."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "index.md").write_text(markdown(index), encoding="utf-8")
    (folder / "index.xlsx").write_bytes(workbook(index, evidence))
    paths = [folder / "index.md", folder / "index.xlsx"]
    (folder / "index").mkdir(exist_ok=True)
    for name, (header, rows) in tables(index, evidence).items():
        path = folder / "index" / f"{name}.csv"
        path.write_text(csv_text(header, rows), encoding="utf-8")
        paths.append(path)
    return paths
