"""Eye tests for vision models: known answers that can't be guessed in context (lab/src/semantic_pdf_diff_lab/bench/eyetest.py).

    set -a; . ./.env; set +a                   # the endpoint and key (git-ignored)
    python scripts/eye_test.py run --model google/gemma-4-31B-it --max-cost 0.5
    python scripts/eye_test.py report          # results.json and report.html from recorded answers, offline

    # a model at another OpenAI-compatible host (its key in OPENAI_API_KEY), named apart from DeepInfra's:
    python scripts/eye_test.py run --model meta-llama/Llama-3.2-11B-Vision-Instruct \
        --base-url https://llm.example.org/v1 --responder llama-3.2-11b-vision@example --suite quick

Answers are recorded by query in benchmarks/eyetest/replay.zip, so running again (or the report) pays
only for what's missing.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/eyetest"
LEDGER = ROOT / "benchmarks/ledger.jsonl"

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="ask models the suite's cards (records answers)")
    run.add_argument("--model", action="append", required=True)
    run.add_argument("--suite", default="standard", choices=["standard", "quick"])
    run.add_argument("--max-cost", type=float, default=0.5, help="for the whole command (every model), in dollars")
    run.add_argument("--concurrency", type=int, default=8)
    run.add_argument("--base-url", help="another OpenAI-compatible endpoint (default: OPENAI_BASE_URL)")
    run.add_argument("--responder", help="whose answers these are (default: the model name); name a model at "
                                         "another host apart, since hosts can serve one model differently")
    report = sub.add_parser("report", help="score what's recorded and write results.json and report.html (offline)")
    report.add_argument("--suite", default="standard", choices=["standard", "quick"])
    args = parser.parse_args(argv)
    from semantic_pdf_diff_lab.bench import eyetest
    from semantic_pdf_diff import ledger
    from semantic_pdf_diff.llm import Budget, evaluator_settings, folder_client
    from semantic_pdf_diff.settings import Settings
    from semantic_pdf_diff.progress import Progress
    import pymupdf
    cards = eyetest.suite(args.suite)
    if args.command == "run":
        if args.responder and len(args.model) > 1:
            parser.error("--responder names one model's answers: give one --model with it")
        budget = Budget(args.max_cost)  # for the whole command, not each model (code review 2026-10-08, E2)
        for model in args.model:
            name = args.responder or model
            if budget.exhausted():
                print(f"Paused: cost cap of ${args.max_cost:.2f} reached before {name}")
                return 3
            before = ledger.spent(LEDGER, round="eyetest", judge=name)
            settings = evaluator_settings(model, eyetest.EYE_SETTINGS, concurrency=args.concurrency, timeout=300,
                                         retries=2, **budget.settings(),
                                         **({"base_url": args.base_url} if args.base_url else {}))
            with folder_client(FOLDER, settings, responder=name) as client:
                client.fixture.note("pymupdf", pymupdf.VersionBind)  # images are drawn by it: replays need the same
                client.ledger = ledger.Ledger(LEDGER, round="eyetest", step=args.suite, judge=name)
                progress = Progress(f"eye test {name}", client, heartbeat=settings.heartbeat_seconds)
                answers = eyetest.ask(FOLDER, client, cards, progress)
                progress.close()
            budget.add(client)
            failed = [a["error"] for a in answers.values() if "error" in a]
            print(f"{name}: {len(answers) - len(failed)} answered, {len(failed)} failed, "
                  f"${ledger.spent(LEDGER, round='eyetest', judge=name) - before:.3f}", flush=True)
            for f in failed[:3]:
                print("  ", f)
            if client.out_of_budget:
                print(f"Paused: {client.out_of_budget}")
                return 3
        return 0
    data = {"suite": args.suite, "cards": {}, "models": {}}
    for card in cards:
        _, truth, prompt = eyetest.render(card, image=False)
        data["cards"][card.id] = {"family": card.family, "truth": truth}
    eyetest.images(FOLDER, cards)
    for model in eyetest.responders(FOLDER):
        settings = Settings(model=model, base_url="http://127.0.0.1:9/v1", **eyetest.EYE_SETTINGS)
        with folder_client(FOLDER, settings, mode="replay", responder=model) as client:
            answers = eyetest.ask(FOLDER, client, cards)
        answers = {k: v for k, v in answers.items() if not v.get("error", "").startswith("No recorded answer")}
        if answers:
            truths = {i: c["truth"] for i, c in data["cards"].items()}
            data["models"][model] = eyetest.results(cards, answers, eyetest.prompt_tokens(FOLDER, model), truths)
    (FOLDER / "results.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(data['models'])} models -> {eyetest.page(FOLDER, data)}")
    for model, r in data["models"].items():
        s = r["summary"]
        print(f"  {model}: " + ", ".join(f"{f} {v['score']}" for f, v in s["families"].items())
              + f"; thresholds {s['thresholds']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
