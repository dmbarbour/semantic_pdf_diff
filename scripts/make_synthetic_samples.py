#!/usr/bin/env python3
"""Generate deliberately messy synthetic spreadsheets, with answer keys.

Real spreadsheets often hold several tables plopped down on one sheet, titles
and stray notes, multi-row headers, value/uncertainty column pairs, formulas
without cached values, hidden superseded sheets and long lists that must not
be sampled. This script writes such files into samples/synthetic/ together
with <name>.expected.json describing the true layout, for testing table
detection and interpretation.

    pip install openpyxl
    python scripts/make_synthetic_samples.py

The content is invented. Output is deterministic for a given openpyxl version.
"""
import argparse
import csv
import io
import json
import math
import re
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

try:
    import openpyxl
    from openpyxl.styles import Font
    from openpyxl.worksheet.table import Table
except ImportError:
    sys.exit("openpyxl is required: pip install openpyxl")

DEFAULT_DEST = Path(__file__).resolve().parent.parent / "samples" / "synthetic"
FIXED_TIME = datetime(2026, 8, 14, 12, 0, 0)
BOLD = Font(bold=True)

def put(ws, top_left, rows, bold_rows=()):
    """Write rows of values starting at a cell like 'B4'; None leaves a cell empty."""
    origin = ws[top_left]
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if value is not None:
                cell = ws.cell(origin.row + r, origin.column + c, value)
                if r in bold_rows:
                    cell.font = BOLD

def summary_sheet(ws):
    ws["A1"] = "Pump Station PS-3 — Design Summary"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:K1")
    ws["A2"] = "Rev C, 2026-08-14. Values marked TBC are provisional."
    ws["M2"] = "TBC per vendor quote"
    # Design basis: key/value table with a formula that has no cached value
    # (files written by tools other than Excel often lack one).
    put(ws, "B4", [
        ["Parameter", "Value", "Unit"],
        ["Design flow", 120, "L/s"],
        ["Static head", 18, "m"],
        ["Friction head", 7.5, "m"],
        ["Total dynamic head", "=C6+C7", "m"],
        ["Fluid temperature", 12, "°C"],
        ["Redundancy", "2 duty + 1 standby", None],
    ], bold_rows=(0,))
    # Pump schedule, beside the design basis with two blank columns between.
    put(ws, "G4", [
        ["Tag", "Duty", "Flow (L/s)", "Head (m)", "Motor power (kW)"],
        ["P-301", "Duty", 60, 25.5, 22],
        ["P-302", "Duty", 60, 25.5, 22],
        ["P-303", "Standby", 60, 25.5, 22],
    ], bold_rows=(0,))
    # Commissioning results: two-row header, measured value with its
    # uncertainty in the adjacent column, compared with design values.
    put(ws, "B13", [
        ["Parameter", "Measured", None, "Design", "Notes"],
        [None, "value", "±", None, None],
        ["Flow at duty point (L/s)", 118, 3, 120, "Within tolerance"],
        ["Total head (m)", 24.1, 0.4, 25.5, None],
        ["Motor power (kW)", 23.8, None, 22, "± not recorded"],
    ], bold_rows=(0, 1))
    ws.merge_cells("C13:D13")
    ws["B20"] = "Checked: JM"
    ws["A22"] = "Note: pump curves in Appendix B."
    return [
        {"range": "A1:K1", "kind": "title"},
        {"range": "A2", "kind": "note"},
        {"range": "M2", "kind": "note"},
        {"range": "B4:D10", "kind": "table", "name": "Design basis", "header_rows": [4], "strategy": "iterate",
         "claims_per_row": 1, "notes": ["C8 is a formula (=C6+C7) with no cached value; its value is unknown to readers that don't evaluate formulas",
                                        "C10 is a text value; D10 (unit) is empty"]},
        {"range": "G4:K7", "kind": "table", "name": "Pump schedule", "header_rows": [4], "strategy": "iterate",
         "claims_per_row": 3, "notes": ["units are embedded in headers", "row label is the pump tag in column G"]},
        {"range": "B13:F17", "kind": "table", "name": "Commissioning results", "header_rows": [13, 14], "strategy": "iterate",
         "composite_columns": [["C", "D"]],
         "notes": ["C13:D13 is a merged header over value and ± columns", "units are embedded in row labels",
                   "measured (C) and design (E) values have different bases: measured vs specified",
                   "D17 is empty: no uncertainty given, as F17 says"]},
        {"range": "B20", "kind": "note"},
        {"range": "A22", "kind": "note"},
    ]

REQUIREMENT_TEMPLATES = [
    ("The pumping station shall deliver {n} L/s at the design head.", "Performance", "Test"),
    ("Each pump shall be removable without draining the wet well (item {n}).", "Maintainability", "Inspection"),
    ("Motor enclosures shall be rated IP{n}.", "Environmental", "Inspection"),
    ("The control system shall log discharge pressure every {n} minutes.", "Controls", "Demonstration"),
    ("Noise at the site boundary shall not exceed {n} dB(A).", "Environmental", "Test"),
    ("Standby pump changeover shall complete within {n} s.", "Performance", "Test"),
    ("Spare parts shall be stocked for {n} years of operation.", "Logistics", "Analysis"),
]

def requirements_sheet(ws, count=150):
    ws["A1"] = "Requirements register — PS-3"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = "Exported from the requirements tool 2026-08-10"
    rows = [["ID", "Requirement", "Type", "Verification", "Status"]]
    statuses = ["Agreed", "Agreed", "Proposed", "Agreed", "Deleted"]
    for i in range(count):
        text, kind, method = REQUIREMENT_TEMPLATES[i % len(REQUIREMENT_TEMPLATES)]
        rows.append([f"REQ-{i + 1:03d}", text.format(n=10 + (i * 7) % 90), kind, method, statuses[i % len(statuses)]])
    put(ws, "A4", rows, bold_rows=(0,))
    last = f"E{4 + count}"
    ws.add_table(Table(displayName="Requirements", ref=f"A4:{last}"))
    return [
        {"range": "A1", "kind": "title"},
        {"range": "A2", "kind": "note"},
        {"range": f"A4:{last}", "kind": "table", "name": "Requirements", "header_rows": [4], "strategy": "iterate",
         "claims_per_row": 1, "notes": ["an Excel defined table named 'Requirements' covers this range",
                                        f"{count} rows; every row is a distinct requirement and must not be sampled",
                                        "rows with Status 'Deleted' are still rows; interpretation should note them"]},
    ]

def flow_log_sheet(ws, count=2000):
    rows = [["Timestamp", "Flow (L/s)", "Discharge pressure (kPa)", "Pumps running"]]
    start = datetime(2026, 7, 1)
    for i in range(count):
        t = i / 288  # days, at 5-minute intervals
        flow = round(95 + 20 * math.sin(2 * math.pi * t) + 3 * math.sin(37 * t), 1)
        pressure = round(245 + 0.8 * (flow - 95) + 2 * math.sin(11 * t), 1)
        rows.append([start + timedelta(minutes=5 * i), flow, pressure, 2 if flow > 100 else 1])
    put(ws, "A1", rows, bold_rows=(0,))
    return [
        {"range": f"A1:D{count + 1}", "kind": "table", "name": "Flow log", "header_rows": [1], "strategy": "summarize",
         "notes": [f"{count} rows of 5-minute samples; statistics over columns B-D are the useful claims"]},
    ]

def scratch_sheet(ws):
    # Two tables touching diagonally with no blank row or column between them,
    # so blank-separation heuristics see one irregular block.
    put(ws, "A1", [
        ["Option", "Capex (k$)", "Opex (k$/yr)"],
        ["A: refurbish", 850, 64],
        ["B: replace", 1400, 41],
        ["C: new station", 2600, 35],
    ])
    put(ws, "D2", [
        ["Year", "Energy (MWh)"],
        [2023, 412],
        [2024, 398],
        [2025, 405],
        [2026, 389],
    ])
    ws["B8"] = 0.07
    ws["C8"] = "discount rate?"
    return [
        {"range": "A1:E6", "kind": "ambiguous", "expected": "skipped: ambiguous sheet layout",
         "notes": ["really two tables, A1:C4 (options) and D2:E6 (energy by year), touching diagonally at C4/D2 without separation"]},
        {"range": "B8:C8", "kind": "note", "notes": ["an unlabeled parameter with a question as its label"]},
    ]

def superseded_sheet(ws):
    put(ws, "A1", [
        ["Parameter", "Value", "Unit"],
        ["Design flow", 110, "L/s"],
        ["Static head", 18, "m"],
        ["Friction head", 9, "m"],
    ], bold_rows=(0,))
    ws.sheet_state = "hidden"
    return [
        {"range": "A1:C4", "kind": "table", "name": "Superseded design basis", "header_rows": [1], "strategy": "iterate",
         "notes": ["the sheet is hidden and its name says it is superseded; its values conflict with Summary (110 vs 120 L/s)",
                   "expected: extracted but marked as coming from a hidden sheet, never silently merged with current values"]},
    ]

def deterministic_zip(data):
    """Rewrite an OOXML zip with fixed timestamps so identical content gives identical bytes.

    openpyxl stamps docProps/core.xml with the save time, so that is pinned too.
    """
    stamp = FIXED_TIME.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            if info.filename == "docProps/core.xml":
                content = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*", rb"\g<1>" + stamp, content)
            fixed = zipfile.ZipInfo(info.filename, FIXED_TIME.timetuple()[:6])
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = 0o644 << 16
            dst.writestr(fixed, content)
    return out.getvalue()

def make_workbook(path):
    wb = openpyxl.Workbook()
    wb.properties.creator = "synthetic sample generator"
    wb.properties.created = wb.properties.modified = FIXED_TIME
    sheets = {}
    ws = wb.active
    ws.title = "Summary"
    sheets["Summary"] = {"hidden": False, "regions": summary_sheet(ws)}
    sheets["Requirements"] = {"hidden": False, "regions": requirements_sheet(wb.create_sheet("Requirements"))}
    sheets["Flow log"] = {"hidden": False, "regions": flow_log_sheet(wb.create_sheet("Flow log"))}
    sheets["Scratch"] = {"hidden": False, "regions": scratch_sheet(wb.create_sheet("Scratch"))}
    sheets["Rev B (superseded)"] = {"hidden": True, "regions": superseded_sheet(wb.create_sheet("Rev B (superseded)"))}
    buffer = io.BytesIO()
    wb.save(buffer)
    path.write_bytes(deterministic_zip(buffer.getvalue()))
    return {"file": path.name, "sheets": sheets}

def make_csv(path):
    lines = [
        ["# Exported by SCADA historian"],
        ["Site: PS-3", "Interval: daily"],
        [],
        ["Date", "Volume pumped (m3)", "Energy (kWh)"],
        ["2026-07-01", 8420, 1712],
        ["2026-07-02", 8390, 1705],
        ["2026-07-03", 8515, 1738],
        ["2026-07-04", 8102, 1650],
        ["2026-07-05", 8277, 1689],
        [],
        ["Alarm", "Count", "Longest (min)"],
        ["High wet-well level", 2, 14],
        ["Pump trip", 1, 0],
        ["Comms loss", 5, 42],
    ]
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(lines)
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return {"file": path.name, "sheets": {"(csv)": {"hidden": False, "regions": [
        {"rows": [1, 2], "kind": "note", "notes": ["preamble lines, one of them with two fields"]},
        {"rows": [4, 9], "kind": "table", "name": "Daily totals", "header_rows": [4], "strategy": "iterate"},
        {"rows": [11, 14], "kind": "table", "name": "Alarm summary", "header_rows": [11], "strategy": "iterate",
         "notes": ["a second table with a different header, separated by one blank line"]},
    ]}}}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="output folder (default: samples/synthetic/)")
    args = parser.parse_args(argv)
    args.dest.mkdir(parents=True, exist_ok=True)
    for name, make in [("messy-workbook.xlsx", make_workbook), ("messy-export.csv", make_csv)]:
        path = args.dest / name
        key = make(path)
        key["description"] = "Synthetic, invented content. Ranges are Excel A1 notation (CSV: 1-based line numbers)."
        path.with_suffix(".expected.json").write_text(json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path)
    return 0

if __name__ == "__main__":
    sys.exit(main())
