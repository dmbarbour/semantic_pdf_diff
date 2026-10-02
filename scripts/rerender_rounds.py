"""Make development rounds' crops and page text again from the public slices (they aren't committed: the owner,
2026-10-02, "we should not be committing images ... for development rounds"). Needed before judging a batch again
or opening its pages; byte for byte what the round saw, under the same PyMuPDF.

    python scripts/fetch_samples.py && python scripts/make_slices.py   # the public slices, if not yet made
    python scripts/rerender_rounds.py                                  # every round's batches
    python scripts/rerender_rounds.py benchmarks/rounds/r09h           # one round's
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("rounds", nargs="*", type=Path, help="round folders (default: every one in benchmarks/rounds)")
    parser.add_argument("--slices", type=Path, default=ROOT / "samples/slices")
    args = parser.parse_args(argv)
    from semantic_pdf_diff_lab.eval import rounds
    folders = [p.resolve() for p in args.rounds] or sorted(p for p in (ROOT / "benchmarks/rounds").iterdir() if p.is_dir())
    for folder in folders:
        for batch in sorted(p.parent for p in folder.glob("pairs-*/pairs.json")):
            print(f"{batch.relative_to(ROOT)}: {len(rounds.rerender(batch, args.slices))} images", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
