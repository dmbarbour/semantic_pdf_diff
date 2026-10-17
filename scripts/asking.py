"""Asking calibration: does a tile's answer ask for another tiling when the tile cuts content?
(lab/src/semantic_pdf_diff_lab/bench/asking.py; docs/plans/tile-selection-2026-10-10.md, milestone 7.)

    set -a; . ./.env; set +a
    python scripts/asking.py run --model google/gemma-4-31B-it --max-cost 1
    python scripts/asking.py run --model google/gemma-4-31B-it --max-cost 0.05 --arm asked --page lcc-s1-clean-p1
    python scripts/asking.py report     # results.json from recorded answers, offline

Tiles are built from the controlled corpus (benchmarks/controlled/docs) and read as the product reads a tile; answers
are recorded by query in benchmarks/asking/replay.zip, which `report` replays for every model it holds.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/asking"
CORPUS = ROOT / "benchmarks/controlled/docs"
SETTINGS = ROOT / "benchmarks/controlled/settings.json"  # the corpus's settings, as a tile is read there
from semantic_pdf_diff_lab.bench import recording  # noqa: E402
LEDGER = recording.ledger(ROOT)

def main(argv=None):
    from semantic_pdf_diff_lab.bench import asking
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="read every case tile under each arm (records answers)")
    run.add_argument("--model", action="append", required=True)
    run.add_argument("--max-cost", type=float, required=True, help="for the whole command (every model), in dollars")
    run.add_argument("--arm", action="append", choices=sorted(asking.ARMS), help="only these arms (default: all)")
    run.add_argument("--page", action="append", help="only these pages (ids such as lcc-s1-clean-p1)")
    run.add_argument("--concurrency", type=int, default=16)
    sub.add_parser("report", help="score what's recorded; write results.json (offline)")
    args = parser.parse_args(argv)
    import pymupdf
    from semantic_pdf_diff import ledger
    from semantic_pdf_diff.progress import setup_logging
    from semantic_pdf_diff_lab.bench import eyetest
    from semantic_pdf_diff_lab.eval.clients import Budget, folder_client
    setup_logging(quiet=True)
    FOLDER.mkdir(parents=True, exist_ok=True)
    base = json.loads(SETTINGS.read_text(encoding="utf-8"))
    found = asking.cases(CORPUS, set(args.page or ()) if args.command == "run" else None)
    if args.command == "run":
        budget = Budget(args.max_cost)
        for model in args.model:
            for arm in args.arm or asking.ARMS:
                if budget.exhausted():
                    print(f"Paused: cost cap of ${args.max_cost:.2f} reached before {model} {arm}")
                    return 3
                before = ledger.spent(LEDGER, round="calibration", judge=model)
                s = asking.settings(model, arm, base).model_copy(update={**budget.settings(),
                                                                          "concurrency": args.concurrency})
                with folder_client(FOLDER, s) as client:
                    client.ledger = ledger.Ledger(LEDGER, round="calibration", step=f"asking-{arm}", judge=model)
                    client.fixture.note("pymupdf", pymupdf.VersionBind)
                    read = asking.read_all(FOLDER, client, found)
                budget.add(client)
                print(f"{model} {arm}: {json.dumps(asking.score(read, arm), indent=1)}", flush=True)
                print(f"{model} {arm}: ${ledger.spent(LEDGER, round='calibration', judge=model) - before:.3f}",
                      flush=True)
                if client.out_of_budget:
                    print(f"Paused: {client.out_of_budget}")
                    return 3
        return 0
    data = {"models": {}}
    for model in eyetest.responders(FOLDER):
        for arm in asking.ARMS:
            s = asking.settings(model, arm, base).model_copy(update={"base_url": "http://127.0.0.1:9/v1"})
            with folder_client(FOLDER, s, mode="replay", responder=model) as client:
                read = asking.read_all(FOLDER, client, found)
            if asking.answered(read):
                profile = asking.score(read, arm)
                profile["missed"] = sorted(k for k, t in asking.answered(read).items()
                                           if t["kind"] != "good" and not asking.asking(t, arm))
                profile["asked_when_whole"] = sorted(k for k, t in asking.answered(read).items()
                                                     if t["kind"] == "good" and asking.asking(t, arm))
                data["models"].setdefault(model, {})[arm] = profile
    (FOLDER / "results.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({m: {a: {k: v for k, v in p.items() if k not in ("missed", "asked_when_whole")}
                          for a, p in arms.items()} for m, arms in data["models"].items()}, indent=1))
    return 0

if __name__ == "__main__":
    sys.exit(main())
