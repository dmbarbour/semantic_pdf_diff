"""Context measures for any folder of runs, offline (lab bench/context.py; docs/plans/claim-context-2026-10-14.md,
milestone 2): per run, claims with conditions and a list position, context in the wrong field, conditions grounded
in what each request showed, and the requests' context and data in bytes. For documents without keys: the slices,
the real pairs.

    python scripts/context.py benchmarks/runs/scratch/slices           # the sums
    python scripts/context.py benchmarks/runs/scratch/slices --runs    # and each run's
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("runs", type=Path, help="a folder of run stores")
    parser.add_argument("--runs", dest="each", action="store_true", help="each run's measures too")
    args = parser.parse_args(argv)
    from semantic_pdf_diff_lab.bench import context
    measures = context.measure(args.runs)
    print(json.dumps({"totals": context.totals(measures), **({"runs": measures} if args.each else {})}, indent=1,
                     ensure_ascii=False))
    return 0

if __name__ == "__main__":
    sys.exit(main())
