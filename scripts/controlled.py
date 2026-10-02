"""Controlled documents: generate the corpus, read it with the pipeline, and score extraction exactly
(src/semantic_pdf_diff/controlled.py; docs/plans/controlled-documents-2026-10-01.md).

    python scripts/controlled.py generate                    # PDFs and answer keys into benchmarks/controlled/docs
    set -a; . ./.env; set +a
    python scripts/controlled.py run --max-cost 0.2          # extraction, recorded into a fixture (resumable)
    python scripts/controlled.py score                       # results.json from the runs' stores, offline
    python scripts/controlled.py run --replay                # read again from the packed fixture, offline

The same seed gives the same PDFs, so the pipeline asks the same queries and recorded answers replay.
"""
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/controlled"
DOCS = FOLDER / "docs"
WORKING = FOLDER / "fixture.sqlite"   # recorded answers (git-ignored); packed into replay.zip
PACKED = FOLDER / "replay.zip"
RUNS = ROOT / "benchmarks/runs/controlled"
LEDGER = ROOT / "benchmarks/ledger.jsonl"
# The settings recordings share (scripts/record_runs.py): they shape the queries, so they decide what replays.
BASE_SETTINGS = {"claims_per_request": 20, "output_tokens": 4000, "context_tokens": 262144, "image_tokens": 300}

SETTINGS = FOLDER / "settings.json"  # every setting that shapes a query, resolved when first recorded (committed)

def settings_file():
    """The corpus's settings: written once, then kept, so replays ask exactly the recorded queries."""
    from semantic_pdf_diff.models import Settings
    if not SETTINGS.exists():
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(Settings.from_env(**BASE_SETTINGS).configuration(), indent=2) + "\n")
    return SETTINGS

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="write the corpus's PDFs and answer keys")
    gen.add_argument("--seed", type=int, action="append", help="default: 1")
    run = sub.add_parser("run", help="extract every document (recorded; answers already recorded are free)")
    run.add_argument("--replay", action="store_true", help="from the packed fixture, without calling a model")
    run.add_argument("--responder", help="default: the configured model")
    run.add_argument("--max-cost", type=float, default=0.2)
    sub.add_parser("score", help="score each run against its key (offline)")
    args = parser.parse_args(argv)
    from semantic_pdf_diff import controlled, fixtures
    if args.command == "generate":
        for project in controlled.corpus(tuple(args.seed or (1,)), knobs=True):
            print(f"{controlled.write(project, DOCS)}: {len(project.facts)} facts")
        return 0
    if args.command == "run":
        from semantic_pdf_diff import cli, ledger
        out = RUNS / ("replay" if args.replay else "recorded")
        if args.replay and not args.responder:  # the responder the fixture holds, whatever the environment says
            import tempfile
            with tempfile.TemporaryDirectory() as d, fixtures.Fixture(fixtures.unpack(PACKED, d)) as f:
                held = [r for (r,) in f.db.execute("SELECT DISTINCT responder FROM response")]
            if len(held) != 1:
                parser.error(f"the fixture holds {held}: name one with --responder")
            args.responder = held[0]
        config = settings_file()
        before = ledger.spent(LEDGER, round="controlled") if LEDGER.exists() else 0.0
        worst = 0
        for pdf in sorted(DOCS.glob("*.pdf")):
            command = [str(pdf), str(pdf), "--config", str(config), "-q", "--no-situate", "--out", str(out / pdf.stem),
                       "--fixture", str(PACKED if args.replay else WORKING),
                       "--fixture-mode", "replay" if args.replay else "record-new"]
            if args.replay:
                command += ["--base-url", "http://127.0.0.1:9/v1"]
            else:
                left = args.max_cost - (ledger.spent(LEDGER, round="controlled") - before)
                if left <= 0:
                    print(f"cap of ${args.max_cost} reached")
                    return 3
                command += ["--max-cost", f"{left:.4f}", "--ledger", str(LEDGER), "--ledger-tag=round=controlled",
                            f"--ledger-tag=run={pdf.stem}"]
            if args.responder:
                command += ["--responder", args.responder]
            code = cli.main(command)
            print(f"{pdf.stem}: exit {code}", flush=True)
            worst = max(worst, code)
        if not args.replay:
            fixtures.pack(WORKING, PACKED)
            print(f"packed {PACKED}; spent ${ledger.spent(LEDGER, round='controlled') - before:.3f}")
        return worst
    from semantic_pdf_diff import rounds
    results = {}
    for which in ("recorded", "replay"):
        runs = RUNS / which
        if not runs.exists():
            continue
        claims = {}
        for (run, _, page, family), unit in rounds.collect(runs).items():
            for c in unit["claims"].values():
                claims.setdefault(run, []).append({**c, "_family": family})
        for run, found in sorted(claims.items()):
            key = json.loads((DOCS / f"{run}.key.json").read_text(encoding="utf-8"))
            result = controlled.score(key, found)
            readers = {f: controlled.score(key, [c for c in found if c["_family"] == f])
                       for f in sorted({c["_family"] for c in found})}
            result["by_reader"] = {f: r["recall"] for f, r in readers.items()}
            result["outcomes_by_reader"] = {f: r["outcomes"] for f, r in readers.items()}
            result["conditions_by_reader"] = {f: r["conditions_kept"] for f, r in readers.items()}
            results.setdefault(which, {})[run] = result
    (FOLDER / "results.json").write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    from semantic_pdf_diff import sheets
    knobbed = [(p, controlled.TABLE_KNOBS) for p in controlled.TABLE_PROJECTS] + \
              [(p, controlled.PROSE_KNOBS) for p in controlled.PROSE_PROJECTS] + \
              [(p, controlled.CHART_KNOBS) for p in controlled.CHART_PROJECTS] + \
              [(p, sheets.SHEET_KNOBS) for p in sheets.SHEET_PROJECTS]
    for which, runs in results.items():  # each knobbed project's knobs beside its clean version
        for project, knobs in knobbed:
            mine = {run[len(project) + 2:].partition("-")[2]: r for run, r in runs.items()
                    if run.startswith(project + "-s") and run[len(project) + 2:].partition("-")[0].isdigit()}
            if not mine:
                continue
            print(f"\n{which} {project}: knob      recall  right  loose  misbound  inexact  wrong unit  misread  hallucinated  claims"
                  "  conditions   misbound by reader; conditions kept by reader")
            for knob in knobs:
                r = mine.get(knob)
                if r:
                    o = r["outcomes"]
                    print(f"  {knob:12s} {r['recall']:7.3f} {r['found_right']:6d} {o.get('loose', 0):6d} "
                          f"{o.get('misbound', 0):9d} {o.get('inexact', 0):8d} {o.get('wrong unit', 0):11d} {o.get('misread', 0):8d} "
                          f"{o.get('hallucinated', 0):13d} {r['claims']:7d}"
                          f"  {r['conditions_kept']:>10s}   "
                          + " ".join(f"{f} {x.get('misbound', 0)}" for f, x in r["outcomes_by_reader"].items())
                          + ("; " + " ".join(f"{f} {k}" for f, k in r["conditions_by_reader"].items())
                             if r["conditions_kept"] != "0/0" else ""))
    from semantic_pdf_diff import schematics
    for which, runs in results.items():  # schematics: relations and numbers apart
        for project in schematics.SCHEMATIC_PROJECTS:
            mine = {run[len(project) + 2:].partition("-")[2]: r for run, r in runs.items()
                    if run.startswith(project + "-s") and run[len(project) + 2:].partition("-")[0].isdigit()}
            if not mine:
                continue
            print(f"\n{which} {project}: knob      relations found  numbers found   right  implied  reversed  wrong  "
                  "invented  unscored   number outcomes")
            for knob in schematics.SCHEMATIC_KNOBS:
                r = mine.get(knob)
                if r:
                    o, k = r["relations"], r["recall_by_kind"]
                    number = "-" if k["number"] is None else f"{k['number']:.3f}"
                    print(f"  {knob:12s} {k['relation']:15.3f} {number:>14s} {o.get('right', 0):7d} "
                          f"{o.get('implied', 0):8d} {o.get('reversed', 0):9d} {o.get('wrong', 0):6d} "
                          f"{o.get('invented', 0):9d} {o.get('unscored', 0):9d}   {r['outcomes']}")
    print()
    for which, runs in results.items():
        for run, r in runs.items():
            print(f"{which} {run}: recall {r['recall']} ({r['found']}/{r['facts']}, {r['found_right']} right) "
                  f"by form {r['recall_by_form']} by reader {r['by_reader']}; claims {r['claims']} {r['outcomes']}; "
                  f"conditions kept {r['conditions_kept']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
