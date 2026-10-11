"""Tilings measured without the model: every page of a folder's PDFs and images, tiled as a configuration tiles it
(lab/src/semantic_pdf_diff_lab/bench/tiling.py; docs/plans/tile-selection-2026-10-10.md, milestone 1).

    python scripts/tiling.py measure samples --first 40 --out runs/tiling-default.json
    python scripts/tiling.py measure samples --first 40 --set tiling=grid --out runs/tiling-grid.json
    python scripts/tiling.py report runs/tiling-default.json --worst lines_cut_sideways
    python scripts/tiling.py compare runs/tiling-default.json runs/tiling-grid.json
    python scripts/tiling.py gallery runs/tiling-samples.json --samples samples --out benchmarks/tiling/gallery \
        --config today --config "grid:tiling=grid"

No model calls. `--set` overrides a setting (its value read as JSON where it parses, else as text); a gallery's
`--config` is a label and its overrides, "label:name=value;name=value" (bench/gallery.py).
"""
import argparse
import json
import sys

from semantic_pdf_diff_lab.bench import tiling

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
    show = sub.add_parser("report", help="a run's totals by tiling mode, and its worst pages")
    show.add_argument("run")
    show.add_argument("--worst", action="append", default=[], metavar="MEASURE", help=f"one of {', '.join(tiling.COUNTS)}")
    show.add_argument("-n", type=int, default=10)
    both = sub.add_parser("compare", help="two runs over the same pages, page by page")
    both.add_argument("before")
    both.add_argument("after")
    show = sub.add_parser("gallery", help="the worst development pages drawn under each configuration, as a page")
    show.add_argument("run", help="a measure run over the samples folder")
    show.add_argument("--samples", default="samples", help="the folder the run measured")
    show.add_argument("--out", required=True)
    show.add_argument("--config", action="append", default=[], metavar="LABEL[:NAME=VALUE;...]")
    args = parser.parse_args(argv)
    if args.command == "gallery":
        from semantic_pdf_diff.settings import Settings
        from semantic_pdf_diff_lab.bench import gallery
        configurations = {}
        for text in args.config or ["today"]:
            label, _, overrides = text.partition(":")
            configurations[label] = Settings(**dict(_setting(o) for o in overrides.split(";") if o))
        n = gallery.build(args.samples, tiling.load(args.run), configurations, args.out)
        print(f"{n} pages drawn: {args.out}/index.html")
        return 0
    if args.command == "measure":
        from semantic_pdf_diff.settings import Settings
        errors = []
        rows = tiling.run(args.folder, Settings(**dict(args.set)), args.first, errors)
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
