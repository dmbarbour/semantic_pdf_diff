"""Tilings measured without the model: every page of a folder's PDFs and images, tiled as a configuration tiles it
(lab/src/semantic_pdf_diff_lab/bench/tiling.py; docs/research/tilings-2026-10-12.md, milestone 1).

    python scripts/tiling.py measure samples --first 40 --out runs/tiling-default.json
    python scripts/tiling.py measure samples --first 40 --set tiling=grid --out runs/tiling-grid.json
    python scripts/tiling.py report runs/tiling-default.json --worst lines_cut_sideways
    python scripts/tiling.py compare runs/tiling-default.json runs/tiling-grid.json
    python scripts/tiling.py gallery runs/tiling-samples.json --samples samples --out benchmarks/tiling/gallery \
        --config today --config "grid:tiling=grid"
    python scripts/tiling.py read benchmarks/controlled/docs/lcc-s1-slide.pdf --config today \
        --config "cut:tile_cut=xycut;decoration=true" --max-cost 0.05
    python scripts/tiling.py complaints benchmarks/runs/controlled/recorded

`complaints` counts recorded runs' tiles as a run does (retiling.tile_counts): by path, and those whose answers say
their text was cut (docs/plans/text-cut-by-tiles-2026-10-28.md, milestone 1), each run and in total.

No model calls but `read`'s, which reads each document under each configuration with the configured model (the
corpus's settings, benchmarks/controlled/settings.json, unless --base), recording into benchmarks/tiling/fixture.sqlite
and scoring against an answer key beside the document. `--set` overrides a setting (its value read as JSON where it
parses, else as text); `--config` is a label and its overrides, "label:name=value;name=value".
"""
import argparse
import json
import sys
from pathlib import Path

from semantic_pdf_diff_lab.bench import tiling

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "benchmarks/tiling/fixture.sqlite"  # the candidates' recorded answers (git-ignored, as runs are)

def _setting(text):
    name, _, value = text.partition("=")
    try:
        return name, json.loads(value)
    except ValueError:
        return name, value

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    go = sub.add_parser("measure", help="measure every page's tiling (no model calls)")
    go.add_argument("folder")
    go.add_argument("--out", required=True, help="the measures, as JSON")
    go.add_argument("--first", type=int, help="only each document's first n pages")
    go.add_argument("--set", action="append", default=[], type=_setting, metavar="NAME=VALUE")
    go.add_argument("--exclude", action="append", default=[], metavar="TEXT",
                    help='leave out files whose path holds this, such as "heldout/"')
    show = sub.add_parser("report", help="a run's totals by tiling mode, and its worst pages")
    show.add_argument("run")
    show.add_argument("--worst", action="append", default=[], metavar="MEASURE",
                      help=f"one of {', '.join(tiling.COUNTS)}")
    show.add_argument("-n", type=int, default=10)
    both = sub.add_parser("compare", help="two runs over the same pages, page by page")
    both.add_argument("before")
    both.add_argument("after")
    show = sub.add_parser("gallery", help="the worst development pages drawn under each configuration, as a page")
    show.add_argument("run", help="a measure run over the samples folder")
    show.add_argument("--samples", default="samples", help="the folder the run measured")
    show.add_argument("--out", required=True)
    show.add_argument("--config", action="append", default=[], metavar="LABEL[:NAME=VALUE;...]")
    said = sub.add_parser("complaints", help="recorded runs' tiles counted: by path, and those saying they're cut")
    said.add_argument("folders", nargs="+", help="folders holding runs (each a folder with report.json)")
    said.add_argument("--json", action="store_true")
    read = sub.add_parser("read", help="documents read with the model under each configuration, scored by their keys")
    read.add_argument("documents", nargs="+")
    read.add_argument("--config", action="append", default=[], metavar="LABEL[:NAME=VALUE;...]")
    read.add_argument("--out", default=str(ROOT / "benchmarks/tiling/read"))
    read.add_argument("--base", default=str(ROOT / "benchmarks/controlled/settings.json"))
    read.add_argument("--max-cost", type=float, required=True)
    read.add_argument("--fixture", default=str(FIXTURE), help="where answers are recorded and replayed from")
    args = parser.parse_args(argv)
    given = getattr(args, "config", None) or ["today"]
    configurations = {label: dict(_setting(o) for o in overrides.split(";") if o)
                      for label, _, overrides in (text.partition(":") for text in given)}
    if args.command == "complaints":
        found = tiling.complaints(args.folders)
        if args.json:
            print(json.dumps(found, indent=1))
            return 0
        print(f"{'run':40} {'tiles':>5} {'said cut':>8} {'empty':>5} {'no text':>7}  paths")
        for run, c in found.items():
            if c["tiles"] or run == "total":
                print(f"{run[:40]:40} {c['tiles']:5} {sum(c['said_cut'].values()):8} {c['said_cut_empty']:5} "
                      f"{c['no_text']:7}  " + ", ".join(f"{k} {n}" for k, n in c["paths"].items())
                      + (f" ({c['middle']} down the middle)" if c["middle"] else ""))
        return 0
    if args.command == "read":
        from semantic_pdf_diff_lab.bench import recording
        found, spent = tiling.read(args.documents, configurations, args.out, args.base, Path(args.fixture),
                                   args.max_cost, recording.ledger(ROOT), {"round": "tiling"})
        Path(args.out).mkdir(parents=True, exist_ok=True)
        (Path(args.out) / "results.json").write_text(json.dumps(found, indent=1))
        for label, documents in found.items():
            for name, a in documents.items():
                tile = a.get("tile", {})
                print(f"{label:12} {name:28} tiles {tile.get('tasks', 0):3} empty {tile.get('empty', 0):3} "
                      f"claims {tile.get('claims', 0):3} tile outcomes {a.get('tile outcomes', {})} "
                      f"tile facts {a.get('tile facts right', '-')} "
                      f"facts {a.get('facts right', '-')}/{a.get('facts', '-')}")
        print(f"spent ${spent:.3f}")
        return 0
    if args.command == "gallery":
        from semantic_pdf_diff.settings import Settings
        from semantic_pdf_diff_lab.bench import gallery
        configurations = {label: Settings(**overrides) for label, overrides in configurations.items()}
        n = gallery.build(args.samples, tiling.load(args.run), configurations, args.out)
        print(f"{n} pages drawn: {args.out}/index.html")
        return 0
    if args.command == "measure":
        from semantic_pdf_diff.settings import Settings
        errors = []
        rows = tiling.run(args.folder, Settings(**dict(args.set)), args.first, errors, args.exclude)
        tiling.save(rows, args.out)
        print(json.dumps(tiling.summary(rows), indent=1))
        for e in errors:
            print("unreadable:", e, file=sys.stderr)
        return 0
    if args.command == "report":
        rows = tiling.load(args.run)
        print(json.dumps(tiling.summary(rows), indent=1))
        for name in args.worst:
            print(f"\nmost {name}:")
            for r in tiling.worst(rows, name, args.n):
                print(f"  {r[name]:6}  {r['file']} p{r['page']} ({r['mode']}, {r['width']} x {r['height']})")
        return 0
    found = tiling.compare(tiling.load(args.before), tiling.load(args.after))
    for name, (a, b) in found["totals"].items():
        print(f"{name:20} {a:8} {b:8}")
    print(f"pages changed: {len(found['pages_changed'])}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
