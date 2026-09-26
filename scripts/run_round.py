"""Run (or resume) one query-improvement round: record, replay, measure, compare, judge, decide, report.

A round is a folder, e.g. benchmarks/rounds/r01/, holding round.json:

    {"name": "r01", "baseline": "variants/baseline.json",
     "variants": {"neighbours": "variants/neighbours.json"},
     "set": "dev", "units": 60, "cap": 15.0,
     "judges": ["google/gemini-3.1-pro", "Qwen/Qwen3.5-397B-A17B", "XiaomiMiMo/MiMo-V2.6-Pro"]}

Variant files are settings (query levers) merged over the recording's base settings.
Every step is checkpointed in state.json and records its figures in benchmarks/history.jsonl.
When the provider balance or the round's cap runs out, the step pauses (exit 3); running the
same command again resumes without repeating paid work. See docs/plans/query-improvement-2026-09-26.md.

    python scripts/run_round.py benchmarks/rounds/r01
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

FIXTURE = ROOT / "tests/fixtures/slices.sqlite"
LEDGER = ROOT / "benchmarks/ledger.jsonl"
HISTORY = ROOT / "benchmarks/history.jsonl"
REPORT = ROOT / "benchmarks/report.html"

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("round", type=Path)
    parser.add_argument("--only", choices=["record", "replay", "measure", "pairs", "judge", "decide", "report"])
    args = parser.parse_args(argv)
    from semantic_pdf_diff import ledger, rounds
    import record_runs

    folder = args.round.resolve()
    spec = json.loads((folder / "round.json").read_text())
    name = spec["name"]
    state_path = folder / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"steps": {}}

    def save_state():
        state["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        state_path.write_text(json.dumps(state, indent=2) + "\n")

    def done(step):
        return state["steps"].get(step) == "done"

    def mark(step, status):
        state["steps"][step] = status
        save_state()

    def remaining():
        return max(0.0, float(spec.get("cap", 15.0)) - ledger.spent(LEDGER, round=name))

    def figure(metric, value, **fields):
        ledger.figure(HISTORY, metric=metric, value=value, round=name, **fields)

    def spent_figure(step):
        figure("spent", ledger.spent(LEDGER, round=name, step=step), step=step)

    # A variant is a settings path, or {"settings": path, "unit": "page"} for variants that move claims between kinds.
    settings_of = lambda value: value["settings"] if isinstance(value, dict) else value
    unit_of = lambda value: value.get("unit", "family") if isinstance(value, dict) else "family"
    variants = {"baseline": settings_of(spec["baseline"]), **{v: settings_of(x) for v, x in spec["variants"].items()}}
    extract = ["--extract-only"] if spec.get("extract_only", True) else []
    runs_root = ROOT / "benchmarks/runs" / name

    def wanted(step):
        return args.only in (None, step)

    # 1. Record each variant (the baseline is usually already recorded: then this only replays).
    for v, path in variants.items():
        step = f"record:{v}"
        if wanted("record") and not done(step):
            if remaining() <= 0:
                mark(step, "paused: round cap reached")
                return 3
            code = record_runs.main(extract + ["--fixture", str(FIXTURE), "--set", spec.get("set", "dev"),
                                     "--variant", str(folder / path),
                                     "--out", str(runs_root / "record" / v), "--ledger", str(LEDGER),
                                     "--tag", f"round={name}", "--tag", "step=record", "--tag", f"variant={v}",
                                     "--max-cost", f"{remaining():.4f}"])
            if code == 3:
                mark(step, "paused: budget")
                return 3
            mark(step, "done")
            spent_figure("record")

    # 2. Replay into clean stores (offline), so every variant is measured the same way.
    for v, path in variants.items():
        step = f"replay:{v}"
        if wanted("replay") and not done(step):
            code = record_runs.main(extract + ["--replay", "--fixture", str(FIXTURE), "--set", spec.get("set", "dev"),
                                     "--variant", str(folder / path), "--out", str(runs_root / v)])
            mark(step, "done" if code in (0, 2) else f"failed: exit {code}")

    # 3. Free, mechanical figures.
    for v in variants:
        step = f"measure:{v}"
        if wanted("measure") and not done(step) and done(f"replay:{v}"):
            for stratum, values in rounds.mechanical(runs_root / v).items():
                for metric, value in values.items():
                    figure(metric, value, variant=v, stratum=stratum, step="measure")
            mark(step, "done")

    judges = spec.get("judges", [])
    for v in spec["variants"]:
        batch = folder / f"pairs-{v}"
        # 4. Sample units where the variant's answers differ from the baseline's.
        if wanted("pairs") and not done(f"pairs:{v}") and done(f"replay:{v}") and done("replay:baseline"):
            built = rounds.build_batch(runs_root / "baseline", runs_root / v, batch, n=int(spec.get("units", 60)),
                                       unit=unit_of(spec["variants"][v]))
            figure("units_changed", built["units"]["units"] - built["units"]["unchanged"], variant=v, step="pairs")
            figure("units_total", built["units"]["units"], variant=v, step="pairs")
            mark(f"pairs:{v}", "done")
        # 5. Panel judging, within what's left of the round's cap.
        if wanted("judge") and done(f"pairs:{v}"):
            from semantic_pdf_diff.llm import Client
            from semantic_pdf_diff.ledger import Ledger
            from semantic_pdf_diff.models import Settings
            for model in judges:
                step = f"judge:{v}:{model}"
                if done(step):
                    continue
                if remaining() <= 0:
                    mark(step, "paused: round cap reached")
                    return 3
                settings = Settings.from_env(model=model, context_tokens=262144, output_tokens=16000, image_tokens=3000,
                                             concurrency=16, timeout=600, retries=2, max_cost=remaining())
                client = Client(settings, batch / ".judge-cache")
                client.ledger = Ledger(LEDGER, round=name, step="judge", variant=v, judge=model)
                _, count, failures = rounds.judge_pairs(batch, client, model)
                if client.out_of_budget:
                    mark(step, f"paused: {client.out_of_budget}")
                    return 3
                state.setdefault("failures", {})[step] = len(failures)  # e.g. malformed answers; the rest counts
                mark(step, "done")
            spent_figure("judge")
        # 6. Decide.
        if wanted("decide") and all(done(f"judge:{v}:{m}") for m in judges) and judges and not done(f"decide:{v}"):
            result = rounds.decide(batch)
            (batch / "decision.json").write_text(json.dumps(result, indent=2) + "\n")
            if result["overall"]:
                figure("win_rate", result["overall"], variant=v, stratum="all", step="decide", units=result["units_judged"])
            for stratum, value in result["strata"].items():
                if value:
                    figure("win_rate", value, variant=v, stratum=stratum, step="decide")
            figure("decision", result["decision"], variant=v, step="decide")
            mark(f"decide:{v}", "done")

    # 7. Report.
    if wanted("report"):
        figure("spent_total", ledger.spent(LEDGER, round=name), step="report")
        rounds.report(HISTORY, REPORT)
        print(f"Report: {REPORT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
