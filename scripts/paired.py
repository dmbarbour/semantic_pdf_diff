"""A lever's arm judged against the base and null arms on the controlled corpus, document by document
(lab/src/semantic_pdf_diff_lab/bench/paired.py; docs/samples-and-testing.md, "Judging a lever").

    python scripts/paired.py read/arrow --base read/base --null read/null --null read/null2 \\
        --target "relations reversed"
    python scripts/paired.py read/lone --base read/base --target "claims right" --all

Each folder holds an arm's runs, one per document (as `scripts/tiling.py read --out` writes them under the arm's
label, or `scripts/controlled.py run`), read from one archive so unchanged queries replay alike. An arm may also be
named as a variant (`controlled.py run --variant FILE`): its recorded runs, else its replayed ones. The target and
guards are named before the arms are read. Offline: only the runs' stores and the corpus's keys are read.

    python scripts/paired.py b62 --base base --null b64 --target "hedge said"

Exit status: 0 when the verdict is "better", 1 "worse", 3 "no different".
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
CORPUS = ROOT / "benchmarks/controlled"

def folder(arm):
    """An arm's folder: as given, or a variant's runs (recorded, else replayed) by its name."""
    if arm.exists():
        return arm
    from semantic_pdf_diff_lab.bench.recording import main_checkout
    variant = main_checkout(ROOT) / "benchmarks/runs/controlled/variants" / str(arm)
    for which in ("recorded", "replay"):
        if (variant / which).is_dir():
            return variant / which
    raise SystemExit(f"{arm}: no such folder, nor a variant's runs ({variant})")

def main(argv=None):
    from semantic_pdf_diff_lab.bench import paired
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("lever", type=Path, help="the lever's arm: a folder of runs")
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--null", type=Path, action="append", default=[], help="an arm changing the same queries "
                        "to no purpose (repeatable)")
    parser.add_argument("--target", default="facts right", choices=sorted(paired.DIRECTION))
    parser.add_argument("--guard", action="append", choices=sorted(paired.DIRECTION),
                        help="default: facts right")
    parser.add_argument("--all", action="store_true", help="every measure against the base too (not judged)")
    parser.add_argument("--corpus", type=Path, default=CORPUS, help="the controlled corpus's folder (its keys)")
    args = parser.parse_args(argv)
    arms = {path: paired.arm(folder(path), args.corpus) for path in [args.lever, args.base, *args.null]}
    lever, base, nulls = arms[args.lever], arms[args.base], [arms[n] for n in args.null]
    result = paired.judge(lever, base, nulls, args.target, tuple(args.guard or ("facts right",)))
    rows = [(f"{args.lever.name} on {args.base.name}", result["against base"])]
    rows += [(f"{args.lever.name} on {n.name}", c) for n, c in zip(args.null, result["against nulls"])]
    rows += [(f"{n.name} on {args.base.name}", c) for n, c in zip(args.null, result["nulls against base"])]
    rows += [(f"{args.lever.name} on {args.base.name} (guard)", c) for c in result["guards"]]
    print(paired.table(rows))
    if args.all:
        print("\nEvery measure, the lever on the base (not judged):\n")
        print(paired.table([(f"{args.lever.name} on {args.base.name}", paired.compare(base, lever, m))
                            for m in paired.DIRECTION]))
    print(f"\n{args.lever.name}: {result['verdict']} (target {args.target})")
    return {"better": 0, "worse": 1}.get(result["verdict"], 3)

if __name__ == "__main__":
    sys.exit(main())
