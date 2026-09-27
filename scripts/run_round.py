"""Run (or resume) one query-improvement round: record, replay, measure, compare, judge, decide, report.

A round is a folder, e.g. benchmarks/rounds/r01/, holding round.json:

    {"name": "r01", "baseline": "variants/baseline.json",
     "variants": {"neighbours": "variants/neighbours.json"},
     "set": "dev", "units": 60, "cap": 15.0,
     "judge_timeout": 300, "judge_retries": 0,   # optional; a stalled judge otherwise holds a chunk for 30 minutes
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
    chunk, target, minimum = int(spec.get("chunk", 8)), int(spec.get("units", 60)), int(spec.get("min_units", 16))

    # 4. Sample units where each variant's answers differ from the baseline's.
    for v in spec["variants"]:
        batch = folder / f"pairs-{v}"
        if wanted("pairs") and not done(f"pairs:{v}") and done(f"replay:{v}") and done("replay:baseline"):
            built = rounds.build_batch(runs_root / "baseline", runs_root / v, batch, n=int(spec.get("units", 60)),
                                       unit=unit_of(spec["variants"][v]))
            figure("units_changed", built["units"]["units"] - built["units"]["unchanged"], variant=v, step="pairs")
            figure("units_total", built["units"]["units"], variant=v, step="pairs")
            mark(f"pairs:{v}", "done")

    # 5. Judge in chunks, round-robin over variants and judges, so that at the cap every variant
    #    has about the same number of units judged. A variant stops early once its result is clear;
    #    state records how far each got, and raising "units" later resumes (paid verdicts are cached).
    judged = state.setdefault("judged", {})    # variant -> units judged by every judge
    stopped = state.setdefault("stopped", {})  # variant -> why judging stopped
    for v in spec["variants"]:  # rounds judged before chunking: all judges done means complete
        if judges and all(done(f"judge:{v}:{m}") for m in judges) and v not in stopped:
            judged[v] = min(target, len(json.loads((folder / f"pairs-{v}" / "pairs.json").read_text())["items"]))
            stopped[v] = f"complete at {judged[v]}"
    save_state()

    def finish_variant(v, reason):
        batch = folder / f"pairs-{v}"
        stopped[v] = reason
        result = rounds.decide(batch, judged[v])
        (batch / "decision.json").write_text(json.dumps({**result, "stopped": reason}, indent=2) + "\n")
        if result["overall"]:
            figure("win_rate", result["overall"], variant=v, stratum="all", step="decide", units=result["units_judged"])
        for stratum, value in result["strata"].items():
            if value:
                figure("win_rate", value, variant=v, stratum=stratum, step="decide", units=result["units_judged"])
        figure("decision", f"{result['decision']} ({reason})", variant=v, step="decide")
        mark(f"decide:{v}", "done")

    if wanted("judge") and judges:
        from semantic_pdf_diff.llm import Client
        from semantic_pdf_diff.ledger import Ledger
        from semantic_pdf_diff.models import Settings
        active = [v for v in spec["variants"] if done(f"pairs:{v}") and v not in stopped]
        while active:
            for v in list(active):
                batch = folder / f"pairs-{v}"
                available = len(json.loads((batch / "pairs.json").read_text())["items"])
                upto = min(judged.get(v, 0) + chunk, target, available)
                for model in judges:
                    if remaining() <= 0:
                        state["paused"] = f"round cap reached while judging {v} (units {judged.get(v, 0)}->{upto})"
                        save_state()
                        spent_figure("judge")
                        return 3
                    settings = Settings.from_env(model=model, context_tokens=262144, output_tokens=16000,
                                                 image_tokens=3000, concurrency=16,
                                                 timeout=int(spec.get("judge_timeout", 600)),
                                                 retries=int(spec.get("judge_retries", 2)),
                                                 max_cost=remaining())
                    client = Client(settings, batch / ".judge-cache")
                    client.ledger = Ledger(LEDGER, round=name, step="judge", variant=v, judge=model)
                    _, _, failures = rounds.judge_pairs(batch, client, model, limit=upto)
                    state.setdefault("failures", {})[f"judge:{v}:{model}"] = len(failures)
                    if failures:  # why, for diagnosis (a judge that times out on long units, say)
                        state.setdefault("failure_notes", {})[f"judge:{v}:{model}"] = [f[:300] for f in failures]
                    if client.out_of_budget:
                        state["paused"] = f"{client.out_of_budget} while judging {v}"
                        save_state()
                        spent_figure("judge")
                        return 3
                judged[v] = upto
                state.pop("paused", None)
                save_state()
                result = rounds.decide(batch, upto)
                if result["overall"]:
                    figure("win_rate_interim", result["overall"], variant=v, stratum="all", step="judge", units=upto)
                clear = result["decision"].startswith(("accepted", "rejected"))
                if upto >= minimum and clear:
                    finish_variant(v, f"stopped early at {upto} units: clear result")
                elif upto >= min(target, available):
                    finish_variant(v, f"complete at {upto} units")
                if v in stopped:
                    active.remove(v)
        spent_figure("judge")
    for v in spec["variants"]:  # variants finished in an earlier run, before chunked judging
        if v in stopped and not done(f"decide:{v}") and judged.get(v):
            finish_variant(v, stopped[v])

    # 7. Report.
    if wanted("report"):
        figure("spent_total", ledger.spent(LEDGER, round=name), step="report")
        rounds.report(HISTORY, REPORT)
        print(f"Report: {REPORT}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
