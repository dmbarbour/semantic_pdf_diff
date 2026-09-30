"""Page tests: reading whole pages by slicing or shrinking them, and by asking for close-ups
(src/semantic_pdf_diff/pagetest.py).

    set -a; . ./.env; set +a
    python scripts/page_test.py run --model google/gemma-4-31B-it --max-cost 0.5
    python scripts/page_test.py report       # results.json and report.html from recorded answers, offline

Answers are recorded by query in benchmarks/pagetest/replay.zip. The "informed" close-up runs use
each model's reading threshold from the eye test (benchmarks/eyetest/results.json).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/pagetest"
EYES = ROOT / "benchmarks/eyetest/results.json"
LEDGER = ROOT / "benchmarks/ledger.jsonl"

def read_all(client, model, only=("static", "zoom")):
    from semantic_pdf_diff import pagetest
    threshold = pagetest.acuity(EYES, model)
    static, zooms = {}, {}
    for sheet in pagetest.sheets():
        if "static" in only:
            static[sheet.id] = pagetest.run_static(FOLDER, client, sheet)
        if "zoom" in only:
            zooms[sheet.id] = {v: pagetest.run_zoom(FOLDER, client, sheet, v, threshold) for v in pagetest.VARIANTS}
    return static, zooms, threshold

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="read every sheet under every plan (records answers)")
    run.add_argument("--model", action="append", required=True)
    run.add_argument("--max-cost", type=float, default=0.5, help="per model, in dollars")
    run.add_argument("--only", choices=["static", "zoom"])
    run.add_argument("--base-url")
    run.add_argument("--responder")
    sub.add_parser("report", help="score what's recorded; write results.json and report.html (offline)")
    args = parser.parse_args(argv)
    import pymupdf
    from semantic_pdf_diff import eyetest, ledger, pagetest
    from semantic_pdf_diff.llm import folder_client
    from semantic_pdf_diff.models import Settings
    if args.command == "run":
        for model in args.model:
            name = args.responder or model
            before = ledger.spent(LEDGER, round="pagetest", judge=name)
            settings = Settings.from_env(model=model, **eyetest.EYE_SETTINGS, concurrency=8, timeout=300, retries=2,
                                         max_cost=args.max_cost, **({"base_url": args.base_url} if args.base_url else {}))
            with folder_client(FOLDER, settings, responder=name) as client:
                client.fixture.note("pymupdf", pymupdf.VersionBind)
                client.ledger = ledger.Ledger(LEDGER, round="pagetest", step=args.only or "all", judge=name)
                read_all(client, name, (args.only,) if args.only else ("static", "zoom"))
            print(f"{name}: ${ledger.spent(LEDGER, round='pagetest', judge=name) - before:.3f}", flush=True)
            if client.out_of_budget:
                print(f"Paused: {client.out_of_budget}")
                return 3
        return 0
    data = {"models": {}}
    for model in eyetest.responders(FOLDER):
        settings = Settings(model=model, base_url="http://127.0.0.1:9/v1", **eyetest.EYE_SETTINGS)
        with folder_client(FOLDER, settings, mode="replay", responder=model) as client:
            static, zooms, threshold = read_all(client, model)
        result = pagetest.results(static, zooms, pagetest.usage(FOLDER, model), threshold)
        data["models"][model] = {**result, "pooled": pagetest.pooled(result)}
    (FOLDER / "results.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(data['models'])} models -> {pagetest.page(FOLDER, data)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
