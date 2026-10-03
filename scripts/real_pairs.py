"""Real revision pairs (docs/plans/revision-comparison-2026-10-02.md, milestone 3): public revision series compared in
revisions mode, recorded into a fixture, and rated by raters none of which is absolute (a mechanical text diff; a
draft's change log), by bench/real_pairs.py.

    set -a; . ./.env; set +a
    python scripts/real_pairs.py run --max-cost 2     # read and compare, recorded (resumable)
    python scripts/real_pairs.py run --replay         # again from the packed fixture, offline
    python scripts/real_pairs.py score                # results.json from the runs' reports

The samples are public (scripts/fetch_samples.py) and stay in samples/; only measurements are committed.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/real-pairs"
WORKING = FOLDER / "fixture.sqlite"   # recorded answers (git-ignored); packed into replay.zip
PACKED = FOLDER / "replay.zip"
SETTINGS = FOLDER / "settings.json"   # every setting that shapes a query, resolved when first recorded (committed)
RUNS = ROOT / "benchmarks/runs/real-pairs"
LEDGER = ROOT / "benchmarks/ledger.jsonl"
SAMPLES = ROOT / "samples"
# The settings recordings share (scripts/record_runs.py, scripts/controlled.py).
BASE_SETTINGS = {"claims_per_request": 20, "output_tokens": 4000, "context_tokens": 262144, "image_tokens": 300}
# pair: (earlier, later), paths under samples/
PAIRS = {
    "quic-34-rfc9000": ("ietf-quic-transport/draft-ietf-quic-transport-34.txt", "ietf-quic-transport/rfc9000.txt"),
    # 3GPP TS 38.300 v19.2.0 and v19.3.0, each a zipped .docx: a small-difference pair
    "ts38300-j20-j30": ("3gpp-ts38300-revisions/38300-j20.zip", "3gpp-ts38300-revisions/38300-j30.zip"),
}

def settings_file():
    from semantic_pdf_diff.models import Settings
    if not SETTINGS.exists():
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(Settings.from_env(**BASE_SETTINGS).configuration(), indent=2) + "\n")
    return SETTINGS

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="compare every pair (recorded; answers already recorded are free)")
    run.add_argument("--replay", action="store_true", help="from the packed fixture, without calling a model")
    run.add_argument("--max-cost", type=float, default=2.0)
    run.add_argument("--only", action="append", help="pairs to run (default: all)")
    sub.add_parser("score", help="rate each pair's report (offline)")
    args = parser.parse_args(argv)
    if args.command == "run":
        from semantic_pdf_diff import fixtures, ledger, pipeline
        from semantic_pdf_diff.progress import setup_logging
        setup_logging(quiet=True)
        config = settings_file()
        before = ledger.spent(LEDGER, round="real-pairs") if LEDGER.exists() else 0.0
        out = RUNS / ("replay" if args.replay else "recorded")
        responder = None
        if args.replay:
            with fixtures.open(PACKED, "read") as f:
                responder = f.db.execute("SELECT DISTINCT responder FROM response").fetchone()[0]
        worst = 0
        for name, (earlier, later) in PAIRS.items():
            if args.only and name not in args.only:
                continue
            options = pipeline.RunOptions(mode="revisions", fixture=PACKED if args.replay else WORKING,
                                          fixture_mode="replay" if args.replay else "record-new", responder=responder)
            if args.replay:
                settings = pipeline.settings_from(config, base_url=pipeline.NO_MODEL)
            else:
                left = args.max_cost - (ledger.spent(LEDGER, round="real-pairs") - before)
                if left <= 0:
                    print(f"cap of ${args.max_cost} reached")
                    return 3
                settings = pipeline.settings_from(config, max_cost=round(left, 4))
                options.ledger, options.ledger_tags = LEDGER, {"round": "real-pairs", "run": name}
            code = pipeline.attempt(pipeline.compare_paths, SAMPLES / earlier, SAMPLES / later, out / name, settings, options)
            print(f"{name}: exit {code}", flush=True)
            worst = max(worst, code)
        if not args.replay:
            fixtures.pack(WORKING, PACKED)
            print(f"packed {PACKED}; spent ${ledger.spent(LEDGER, round='real-pairs') - before:.3f}")
        return worst
    from semantic_pdf_diff_lab.bench import real_pairs
    results = {}
    for which in ("recorded", "replay"):
        for name, (earlier, later) in PAIRS.items():
            report = RUNS / which / name / "report.json"
            if report.exists():
                docs = [real_pairs.document(SAMPLES / p) for p in (earlier, later)]
                results.setdefault(which, {})[name] = real_pairs.rate(json.loads(report.read_text(encoding="utf-8")),
                                                                      *docs)
    (FOLDER / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    for which, pairs in results.items():
        for name, r in pairs.items():
            print(f"{which} {name}: " + json.dumps({k: v for k, v in r.items() if k != "examples"}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
