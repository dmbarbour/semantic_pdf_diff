"""Run (or resume) one query-improvement round: record, replay, measure, compare, judge, decide, report.

A round is a folder, e.g. benchmarks/rounds/r01/, holding round.json:

    {"name": "r09", "baseline": "variants/baseline.json",
     "variants": {"neighbours": "variants/neighbours.json",
                  "aa": {"settings": "variants/baseline.json", "fresh": ["tile", "figure", "overview"]}},
     "set": "dev", "units": 32, "cap": 10.0,     # every variant judged to "units" and decided once
     "judge_timeout": 450, "judge_retries": 0,   # a stalled judge otherwise holds a chunk for 30 minutes
     "rubric": "v6",                             # judging rubric (rounds.RUBRICS); default v1
     "escalate": ["Qwen/Qwen3.5-397B-A17B"],     # second opinions on units the main judges leave unsettled
     "confirm_judges": [], "confirm_units": 16,  # expensive judges for accepted variants, when wanted
     "judges": ["XiaomiMiMo/MiMo-V2.6-Pro"]}    # the main judges see every unit

Variant files are settings (query levers) merged over the recording's base settings.
Every step is checkpointed in state.json and records its figures in benchmarks/history.jsonl.
When the provider balance or the round's cap runs out, the step pauses (exit 3); running the
same command again resumes without repeating paid work. See docs/plans/query-improvement-2026-09-26.md.

    python scripts/run_round.py benchmarks/rounds/r09
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
# Each slice's document family (reports, drawings, manuals, rules): strata alongside the kinds of region.
DOCUMENTS = {s["name"]: s.get("family") for s in json.loads((ROOT / "scripts/slices.json").read_text())["slices"]}
LEDGER = ROOT / "benchmarks/ledger.jsonl"
HISTORY = ROOT / "benchmarks/history.jsonl"
REPORT = ROOT / "benchmarks/report.html"

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("round", type=Path)
    parser.add_argument("--only", choices=["record", "replay", "measure", "pairs", "judge", "decide", "report"])
    args = parser.parse_args(argv)
    from semantic_pdf_diff import insights, ledger, rounds
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
        if (n := ledger.unpriced(LEDGER, round=name, step=step)):  # responses whose cost wasn't reported
            figure("unpriced_responses", n, step=step)

    # A variant is a settings path, or {"settings": path, "unit": "page"} for variants that move claims between kinds.
    settings_of = lambda value: value["settings"] if isinstance(value, dict) else value
    unit_of = lambda value: value.get("unit", "family") if isinstance(value, dict) else "family"
    # An A/A control: {"settings": <the baseline's>, "fresh": ["tile", "figure", "overview"]} re-asks
    # those regions' requests afresh, to measure how much re-asking alone moves a comparison.
    fresh_of = lambda value: ",".join(value.get("fresh", ())) if isinstance(value, dict) else ""
    fresh = {"baseline": "", **{v: fresh_of(x) for v, x in spec["variants"].items()}}
    variants = {"baseline": settings_of(spec["baseline"]), **{v: settings_of(x) for v, x in spec["variants"].items()}}
    extract = ["--extract-only"] if spec.get("extract_only", True) else []
    runs_root = ROOT / "benchmarks/runs" / name

    def wanted(step):
        return args.only in (None, step)

    # 0. Rounds commit page images, page text and claims (pairs-*/, judge caches), so they run on
    #    slices marked public only: a sensitive document must never reach the repository.
    manifest = json.loads(record_runs.MANIFEST.read_text())
    wanted_set = spec.get("set", "dev")
    in_set = {n for r in manifest["runs"] if wanted_set == "all" or r["set"] == wanted_set for n in r["slices"]}
    private = sorted(s["name"] for s in manifest["slices"] if s["name"] in in_set and not s.get("public"))
    if private:
        print(f"Refusing: slices not marked public in {record_runs.MANIFEST.name}: {', '.join(private)}")
        return 2

    # 1. Record each variant (the baseline is usually already recorded: then this only replays).
    for v, path in variants.items():
        step = f"record:{v}"
        if wanted("record") and not done(step):
            if remaining() <= 0:
                mark(step, "paused: round cap reached")
                return 3
            code = record_runs.main(extract + ["--fixture", str(FIXTURE), "--set", spec.get("set", "dev"),
                                     "--variant", str(folder / path), "--fresh-regions", fresh[v],
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
                                     "--variant", str(folder / path), "--fresh-regions", fresh[v],
                                     "--out", str(runs_root / v)])
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
        if done(f"pairs:{v}"):  # "units" raised past the sample: resample (the first units stay the same)
            built = json.loads((batch / "pairs.json").read_text())
            if len(built["items"]) < min(int(spec.get("units", 60)), built["units"]["units"] - built["units"]["unchanged"]):
                state["steps"].pop(f"pairs:{v}")
        if wanted("pairs") and not done(f"pairs:{v}") and done(f"replay:{v}") and done("replay:baseline"):
            built = rounds.build_batch(runs_root / "baseline", runs_root / v, batch, n=int(spec.get("units", 60)),
                                       unit=unit_of(spec["variants"][v]))
            if rounds.RUBRICS[spec.get("rubric", "v1")].get("whole"):  # the whole page and every claim (v6)
                rounds.add_context(batch, runs_root / "baseline", runs_root / v, n=int(spec.get("units", 60)),
                                   unit=unit_of(spec["variants"][v]))
            figure("units_changed", built["units"]["units"] - built["units"]["unchanged"], variant=v, step="pairs")
            figure("units_total", built["units"]["units"], variant=v, step="pairs")
            mark(f"pairs:{v}", "done")

    # 5. Judge in chunks, round-robin over variants, so that at the cap every variant has about
    #    the same number of units judged. Every variant is judged to its full sample and decided
    #    once (fixed n): stopping as soon as an interval cleared, at 16, 24 and 32 units, accepted
    #    a lever with no effect 12-18% of the time instead of about 6-9% (overall review,
    #    2026-09-28). "early_stop": true restores that for rounds 1-8's records.
    #    The main judges see every unit; "escalate" judges only units the main judges leave
    #    unsettled (a failed verdict, a flip with the order, disagreement); failed verdicts are
    #    asked once more when a variant's sample is done. "confirm_judges" (expensive) judge the
    #    first "confirm_units" units of an accepted variant, as a separate check.
    judged = state.setdefault("judged", {})    # variant -> units judged by every judge
    stopped = state.setdefault("stopped", {})  # variant -> why judging stopped
    rubric = spec.get("rubric", "v1")
    escalate = spec.get("escalate", [])
    early = bool(spec.get("early_stop", False))
    for v in spec["variants"]:  # rounds judged before chunking: all judges done means complete
        if judges and all(done(f"judge:{v}:{m}") for m in judges) and v not in stopped:
            judged[v] = min(target, len(json.loads((folder / f"pairs-{v}" / "pairs.json").read_text())["items"]))
            stopped[v] = f"complete at {judged[v]}"
    for v in list(stopped):  # "units" raised since a variant completed: judge on
        pairs = folder / f"pairs-{v}" / "pairs.json"
        if stopped[v].startswith("complete at") and pairs.exists() \
                and judged.get(v, 0) < min(target, len(json.loads(pairs.read_text())["items"])):
            stopped.pop(v)
            state["steps"].pop(f"decide:{v}", None)
    save_state()

    class Paused(Exception):
        pass

    def ask(v, model, upto, only=None, retry_failed=False, step="judge", verdicts_dir="verdicts"):
        """One judge over a variant's first `upto` units; raises Paused at the cap or out of budget."""
        from semantic_pdf_diff.llm import Client
        from semantic_pdf_diff.ledger import Ledger
        from semantic_pdf_diff.models import Settings
        batch = folder / f"pairs-{v}"
        if remaining() <= 0:
            raise Paused(f"round cap reached while judging {v} ({model}, units to {upto})")
        settings = Settings.from_env(model=model, context_tokens=262144, output_tokens=16000,
                                     image_tokens=3000, concurrency=16,
                                     timeout=int(spec.get("judge_timeout", 600)),
                                     retries=int(spec.get("judge_retries", 2)), max_cost=remaining())
        client = Client(settings, batch / ".judge-cache")
        client.ledger = Ledger(LEDGER, round=name, step=step, variant=v, judge=model)
        _, _, failures = rounds.judge_pairs(batch, client, model, limit=upto, rubric=rubric, only=only,
                                            retry_failed=retry_failed, verdicts_dir=verdicts_dir)
        # Failed verdicts over the whole round, not the last call's (the audit, 2026-09-28: each call
        # overwrote the count, so an escalation judge's failures read 0).
        key = f"{step}:{v}:{model}"
        state.setdefault("failures", {})[key] = state["failures"].get(key, 0) + len(failures)
        if failures:  # why, for diagnosis (a judge that times out on long units, say)
            notes = state.setdefault("failure_notes", {})
            notes[key] = (notes.get(key, []) + [f[:300] for f in failures])[-50:]
        if client.out_of_budget:
            raise Paused(f"{client.out_of_budget} while judging {v}")

    def settle(v, upto, retry_failed=False):
        """Second opinions where the main judges leave units unsettled; retry_failed asks the second
        judges' failed verdicts once more, as the main judges' are (these are the long, hard units)."""
        if escalate:
            only = rounds.unsettled(folder / f"pairs-{v}", judges, upto)
            state.setdefault("escalated", {})[v] = sorted(only)
            for model in escalate:
                if only:
                    ask(v, model, upto, only=only, retry_failed=retry_failed)

    def finish_variant(v, reason):
        batch = folder / f"pairs-{v}"
        stopped[v] = reason
        result = rounds.decide(batch, judged[v], documents=DOCUMENTS)
        (batch / "decision.json").write_text(json.dumps({**result, "stopped": reason}, indent=2) + "\n")
        insights.analyse(batch, judged[v])  # the clues to why: agreement, changes, issues, tags, remarks
        if result["overall"]:
            figure("win_rate", result["overall"], variant=v, stratum="all", step="decide", units=result["units_judged"])
        for stratum, value in result["strata"].items():
            if value:
                figure("win_rate", value, variant=v, stratum=stratum, step="decide", units=result["units_judged"])
        figure("decision", f"{result['decision']} ({reason})", variant=v, step="decide")
        mark(f"decide:{v}", "done")

    def confirm(v):
        """Expensive judges on an accepted variant's first units: a separate check, recorded apart."""
        judges_ = spec.get("confirm_judges", [])
        batch = folder / f"pairs-{v}"
        decision = json.loads((batch / "decision.json").read_text())
        if not judges_ or done(f"confirm:{v}") or not decision["decision"].startswith("accepted"):
            return
        units = min(int(spec.get("confirm_units", 16)), judged[v])
        for model in judges_:
            ask(v, model, units, step="confirm", verdicts_dir="verdicts-confirm")
        result = rounds.decide(batch, units, verdicts_dir="verdicts-confirm", documents=DOCUMENTS)
        (batch / "decision-confirm.json").write_text(json.dumps({**result, "judges": judges_}, indent=2) + "\n")
        if result["overall"]:
            figure("win_rate_confirm", result["overall"], variant=v, stratum="all", step="confirm", units=units)
        mark(f"confirm:{v}", "done")

    if wanted("judge") and judges:
        try:
            active = [v for v in spec["variants"] if done(f"pairs:{v}") and v not in stopped]
            while active:
                for v in list(active):
                    batch = folder / f"pairs-{v}"
                    available = len(json.loads((batch / "pairs.json").read_text())["items"])
                    upto = min(judged.get(v, 0) + chunk, target, available)
                    for model in judges:
                        ask(v, model, upto)
                    settle(v, upto)
                    judged[v] = upto
                    state.pop("paused", None)
                    save_state()
                    result = rounds.decide(batch, upto, documents=DOCUMENTS)
                    if result["overall"]:
                        figure("win_rate_interim", result["overall"], variant=v, stratum="all", step="judge", units=upto)
                    if early and upto >= minimum and result["decision"].startswith(("accepted", "rejected")):
                        finish_variant(v, f"stopped early at {upto} units: clear result")
                    elif upto >= min(target, available):
                        for model in judges:  # failed verdicts, once more
                            ask(v, model, upto, retry_failed=True)
                        settle(v, upto, retry_failed=True)
                        finish_variant(v, f"complete at {upto} units")
                    if v in stopped:
                        active.remove(v)
            for v in spec["variants"]:
                if done(f"decide:{v}"):
                    confirm(v)
        except Paused as why:
            state["paused"] = str(why)
            save_state()
            spent_figure("judge")
            return 3
        spent_figure("judge")
    for v in spec["variants"]:  # variants finished in an earlier run, before chunked judging
        if v in stopped and not done(f"decide:{v}") and judged.get(v):
            finish_variant(v, stopped[v])

    # 7. Report.
    if wanted("report"):
        figure("spent_total", ledger.spent(LEDGER, round=name), step="report")
        rounds.report(HISTORY, REPORT)
        print(f"Report: {REPORT}")
        for v in spec["variants"]:  # rounds decided before analyses existed
            if done(f"decide:{v}") and not (folder / f"pairs-{v}" / "analysis.json").exists():
                insights.analyse(folder / f"pairs-{v}", judged.get(v))
        print(f"Insights: {insights.page(folder)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
