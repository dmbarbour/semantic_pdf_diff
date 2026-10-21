"""Region labels calibration: can a model label a page's regions? (lab/src/semantic_pdf_diff_lab/bench/labelling.py;
docs/research/tilings-2026-10-12.md, milestone 6.)

    set -a; . ./.env; set +a
    python scripts/labelling.py run --model google/gemma-4-31B-it --max-cost 0.5
    python scripts/labelling.py run --model google/gemma-4-31B-it --max-cost 0.05 --page lcc-s1-clean-p1
    python scripts/labelling.py report     # results.json and report.html from recorded answers, offline

Questions are built from the controlled corpus (benchmarks/controlled/docs); answers are recorded by query in
benchmarks/labelling/replay.zip, which `report` replays for every model it holds.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/labelling"
CORPUS = ROOT / "benchmarks/controlled/docs"
from semantic_pdf_diff_lab.bench import recording  # noqa: E402
LEDGER = recording.ledger(ROOT)

def main(argv=None):
    from semantic_pdf_diff_lab.bench import labelling
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="ask every question in both numberings (records answers)")
    run.add_argument("--model", action="append", required=True)
    run.add_argument("--max-cost", type=float, required=True, help="for the whole command (every model), in dollars")
    run.add_argument("--page", action="append", help="only these pages (ids such as lcc-s1-clean-p1)")
    run.add_argument("--base-url")
    run.add_argument("--responder")
    run.add_argument("--concurrency", type=int, default=8)
    sub.add_parser("report", help="score what's recorded; write results.json and report.html (offline)")
    args = parser.parse_args(argv)
    import pymupdf
    from semantic_pdf_diff import ledger
    from semantic_pdf_diff.settings import Settings
    from semantic_pdf_diff_lab.bench import eyetest
    from semantic_pdf_diff_lab.eval.clients import Budget, evaluator, folder_client
    FOLDER.mkdir(parents=True, exist_ok=True)
    if args.command == "run":
        budget = Budget(args.max_cost)
        for model in args.model:
            name = args.responder or model
            if budget.exhausted():
                print(f"Paused: cost cap of ${args.max_cost:.2f} reached before {name}")
                return 3
            before = ledger.spent(LEDGER, round="calibration", judge=name)
            with evaluator(FOLDER, model, budget, labelling.SETTINGS, ledger.Ledger(LEDGER, round="calibration",
                           step="labels", judge=name), name, concurrency=args.concurrency, timeout=300, retries=2,
                           **({"base_url": args.base_url} if args.base_url else {})) as client:
                client.fixture.note("pymupdf", pymupdf.VersionBind)
                asked = labelling.ask_all(FOLDER, client, CORPUS, set(args.page or ()))
                print(f"{name}: {len(asked)} questions", flush=True)
                print(json.dumps(labelling.score(asked), indent=1))
            print(f"{name}: ${ledger.spent(LEDGER, round='calibration', judge=name) - before:.3f}", flush=True)
            if client.out_of_budget:
                print(f"Paused: {client.out_of_budget}")
                return 3
        return 0
    data, asked_by_model = {"models": {}}, {}
    for model in eyetest.responders(FOLDER):
        settings = Settings(model=model, base_url="http://127.0.0.1:9/v1", **labelling.SETTINGS)
        with folder_client(FOLDER, settings, mode="replay", responder=model) as client:
            asked = labelling.ask_all(FOLDER, client, CORPUS)
        asked = {k: q for k, q in asked.items() if not any(
            a and a["error"] and a["error"].startswith("No recorded answer") for a in q["answers"])}
        if asked:
            asked_by_model[model] = asked
            data["models"][model] = labelling.score(asked)
    (FOLDER / "results.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=1))
    print(f"{len(data['models'])} models -> {labelling.page(FOLDER, data, asked_by_model)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
