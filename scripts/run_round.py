"""Run (or resume) one query-improvement round: record, replay, measure, compare, judge, decide, report.

A round is a folder, e.g. benchmarks/rounds/r01/, holding round.json:

    {"name": "r09", "baseline": "variants/baseline.json",
     "variants": {"neighbours": "variants/neighbours.json",
                  "aa": {"settings": "variants/baseline.json", "fresh": ["tile", "figure", "overview"]}},
     "set": "dev", "units": 32, "cap": 10.0,     # every variant judged to "units" and decided once
     "judge_timeout": 450, "judge_retries": 0,   # a stalled judge otherwise holds a chunk for 30 minutes
     "rubric": "v6",                             # judging rubric (rounds.RUBRICS); default v1
     "query_checks": {"sample": 30, "cap": 2.0}, # strong models check what each variant changed first
                                                 # (models: QUERY_CHECKERS unless given); held until accepted
     "postmortem": {"units": 5},                 # every lever's post-mortem (defaults: analyst Gemini, $0.25)
     "criteria": {"role": "development",         # how the round decides (models.Criteria), set before
                  "gain": {"metric": "tokens", "change": -0.10}},  # judging and locked once it starts
     "escalate": ["Qwen/Qwen3.5-397B-A17B"],     # second opinions on units the main judges leave unsettled
     "confirm_judges": [], "confirm_units": 16,  # expensive judges for accepted variants, when wanted
     "judges": ["XiaomiMiMo/MiMo-V2.6-Pro"]}    # the main judges see every unit

Variant files are settings (query levers) merged over the recording's base settings.
Every step is checkpointed in state.json and records its figures in benchmarks/history.jsonl.
When the provider balance or the round's cap runs out, the step pauses (exit 3); running the
same command again resumes without repeating paid work. When checkers flag queries, the round is
held before sampling and judging (exit 4) until they're fixed or accepted (--accept-checks).
See docs/plans/query-improvement-2026-09-26.md.

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
# Checkers of each round's queries (query_checks in round.json): two families, both reading images,
# with Claude reading the dump. Gemini shares Google with the extractor (gemma), which matters little
# for checking queries our code builds. Chosen by Claude, who the owner left the choice to: in a trial
# (2026-09-28) Gemini answered all 20 queries at $0.011 each, while Qwen3.5-397B and Kimi-K3 reasoned
# past their output budget on most ($0.012 and $0.053 a call, mostly lost); MiMo judges at $0.004.
QUERY_CHECKERS = ["google/gemini-3.1-pro", "XiaomiMiMo/MiMo-V2.6-Pro"]
REPORT = ROOT / "benchmarks/report.html"

class Paused(Exception):
    """A step stopped for money: the round's cap, a step's cap, or the provider's balance."""

class RoundRunner:
    """One round's steps, resumable from state.json (code review 2026-10-01, A3: this was one closure in main). Each
    step returns an exit code to stop at (2 refused, 3 paused, 4 held) or None to go on. The paths, the manifest and
    the recorder are attributes, so tests point them at temporary folders and stubs."""
    fixture, ledger_path, history, report_path, documents = FIXTURE, LEDGER, HISTORY, REPORT, DOCUMENTS
    runs_base = ROOT / "benchmarks/runs"
    query_checkers = QUERY_CHECKERS

    def __init__(self, folder, only=None, accept_checks=False):
        from semantic_pdf_diff.models import RoundSpec
        self.folder, self.only, self.accept_checks = Path(folder).resolve(), only, accept_checks
        # Validated: a mistyped key fails here rather than taking a default. Kept as a dict (with every default filled
        # in) for the steps below.
        self.spec = RoundSpec.model_validate_json((self.folder / "round.json").read_text()).model_dump()
        self.name = self.spec["name"]
        self.state_path = self.folder / "state.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"steps": {}}
        spec = self.spec
        # A variant is a settings path, or {"settings": path, "unit": "page"} for variants that move claims between
        # kinds; an A/A control, {"settings": <the baseline's>, "fresh": ["tile", "figure", "overview"]}, re-asks those
        # regions' requests afresh, to measure how much re-asking alone moves a comparison.
        settings_of = lambda value: value["settings"] if isinstance(value, dict) else value
        fresh_of = lambda value: ",".join(value.get("fresh", ())) if isinstance(value, dict) else ""
        self.fresh = {"baseline": "", **{v: fresh_of(x) for v, x in spec["variants"].items()}}
        self.variants = {"baseline": settings_of(spec["baseline"]),
                         **{v: settings_of(x) for v, x in spec["variants"].items()}}
        self.extract = ["--extract-only"] if spec.get("extract_only", True) else []
        self.runs_root = self.runs_base / self.name
        self.judges = spec.get("judges", [])
        self.chunk, self.target = int(spec.get("chunk", 8)), int(spec.get("units", 60))
        self.minimum = int(spec.get("min_units", 16))
        self.rubric, self.escalate = spec.get("rubric", "v1"), spec.get("escalate", [])
        self.early = bool(spec.get("early_stop", False))
        self.measured = {}
        self.criteria = None

    # --- what the steps share

    def unit_of(self, v):
        value = self.spec["variants"][v]
        return value.get("unit", "family") if isinstance(value, dict) else "family"

    def record_runs(self, argv):
        """Record or replay a variant's runs (scripts/record_runs.py)."""
        import record_runs
        return record_runs.main(argv)

    def manifest(self):
        import record_runs
        return json.loads(record_runs.MANIFEST.read_text())

    def save_state(self):
        self.state["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.state_path.write_text(json.dumps(self.state, indent=2) + "\n")

    def done(self, step):
        return self.state["steps"].get(step) == "done"

    def mark(self, step, status):
        self.state["steps"][step] = status
        self.save_state()

    def remaining(self):
        from semantic_pdf_diff import ledger
        return max(0.0, float(self.spec.get("cap", 15.0)) - ledger.spent(self.ledger_path, round=self.name))

    def figure(self, metric, value, **fields):
        from semantic_pdf_diff import ledger
        ledger.figure(self.history, metric=metric, value=value, round=self.name, **fields)

    def spent_figure(self, step):
        from semantic_pdf_diff import ledger
        self.figure("spent", ledger.spent(self.ledger_path, round=self.name, step=step), step=step)
        if (n := ledger.unpriced(self.ledger_path, round=self.name, step=step)):  # responses whose cost wasn't reported
            self.figure("unpriced_responses", n, step=step)

    def wanted(self, step):
        return self.only in (None, step)

    def pause(self, why):
        self.state["paused"] = why
        self.save_state()
        print(f"Paused: {why}")
        return 3

    # --- the steps, in order

    def run(self):
        for step in (self.refuse_private, self.record, self.replay, self.measure, self.check, self.pairs, self.judge,
                     self.leftovers, self.report):
            code = step()
            if code is not None:
                return code
        return 0

    def refuse_private(self):
        """0. Rounds commit page images, page text and claims (pairs-*/, replay fixtures), so they run on slices marked
        public only: a sensitive document must never reach the repository."""
        from semantic_pdf_diff import rounds
        manifest = self.manifest()
        wanted_set = self.spec.get("set", "dev")
        private = rounds.private_slices([r["name"] for r in manifest["runs"] if wanted_set == "all" or r["set"] == wanted_set],
                                        manifest)
        if private:
            print(f"Refusing: slices not marked public in the slices manifest: {', '.join(private)}")
            return 2

    def record(self):
        """1. Record each variant (the baseline is usually already recorded: then this only replays)."""
        for v, path in self.variants.items():
            step = f"record:{v}"
            if self.wanted("record") and not self.done(step):
                if self.remaining() <= 0:
                    self.mark(step, "paused: round cap reached")
                    return 3
                code = self.record_runs(self.extract + [
                    "--fixture", str(self.fixture), "--set", self.spec.get("set", "dev"), "--variant", str(self.folder / path),
                    "--fresh-regions", self.fresh[v], "--out", str(self.runs_root / "record" / v),
                    "--ledger", str(self.ledger_path), "--tag", f"round={self.name}", "--tag", "step=record",
                    "--tag", f"variant={v}", "--max-cost", f"{self.remaining():.4f}"])
                if code == 3:
                    self.mark(step, "paused: budget")
                    return 3
                self.mark(step, "done")
                self.spent_figure("record")

    def replay(self):
        """2. Replay into clean stores (offline), so every variant is measured the same way."""
        for v, path in self.variants.items():
            step = f"replay:{v}"
            if self.wanted("replay") and not self.done(step):
                code = self.record_runs(self.extract + [
                    "--replay", "--fixture", str(self.fixture), "--set", self.spec.get("set", "dev"),
                    "--variant", str(self.folder / path), "--fresh-regions", self.fresh[v], "--out", str(self.runs_root / v)])
                self.mark(step, "done" if code in (0, 2) else f"failed: exit {code}")

    def measure(self):
        """3. Free, mechanical figures."""
        from semantic_pdf_diff import rounds
        for v in self.variants:
            step = f"measure:{v}"
            if self.wanted("measure") and not self.done(step) and self.done(f"replay:{v}"):
                for stratum, values in rounds.mechanical(self.runs_root / v).items():
                    for metric, value in values.items():
                        self.figure(metric, value, variant=v, stratum=stratum, step="measure")
                self.mark(step, "done")

    def check(self):
        """3b. Queries checked before any money goes on judging (docs/plans/content-addressed-queries): a sample of
        what each variant changed is dumped (queries-<variant>/index.html) for people and Claude to look over, and
        strong models from other families check it for obvious errors. A flagged query holds the round until it's
        fixed or the flags are accepted (--accept-checks)."""
        from semantic_pdf_diff import ledger
        checks = self.spec.get("query_checks")
        if checks and self.wanted("check"):
            from semantic_pdf_diff import queries
            from semantic_pdf_diff.ledger import Ledger
            from semantic_pdf_diff.llm import evaluator_settings
            cap = float(checks.get("cap", 2.0))
            for v in self.spec["variants"]:
                step = f"check:{v}"
                if self.done(step) or not (self.done(f"replay:{v}") and self.done("replay:baseline")):
                    continue
                dump_dir = self.folder / f"queries-{v}"
                summary = queries.dump(self.runs_root / v, dump_dir, against=self.runs_root / "baseline",
                                       sample=int(checks.get("sample", 30)))
                for model in checks.get("models") or self.query_checkers:
                    left = min(self.remaining(), cap - ledger.spent(self.ledger_path, round=self.name, step="check"))
                    if left <= 0:
                        return self.pause(f"the query checks' cap (${cap:.2f}) reached while checking {v}")
                    settings = evaluator_settings(model, concurrency=4, timeout=600, retries=1, max_cost=left)
                    with self.client_for(dump_dir, settings) as client:
                        client.ledger = Ledger(self.ledger_path, round=self.name, step="check", variant=v, judge=model)
                        _, _, failures = queries.check(dump_dir, client, model)
                    if failures:
                        self.state.setdefault("failure_notes", {})[f"check:{v}:{model}"] = [f[:300] for f in failures]
                    if client.out_of_budget:
                        return self.pause(f"{client.out_of_budget} while checking {v}")
                flags = queries.flagged(dump_dir, in_change=True)  # what the variant changed; older problems are leads
                self.state.setdefault("query_flags", {})[v] = sorted(flags)
                self.figure("query_flags", len(flags), variant=v, step="check", shown=summary["shown"],
                            changed=summary["candidates"], flagged_before=len(queries.flagged(dump_dir)) - len(flags))
                self.mark(step, "done")
            self.spent_figure("check")
        if self.accept_checks:
            self.state["checks_accepted"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            self.save_state()
        held = [v for v, flags in self.state.get("query_flags", {}).items() if flags]
        if checks and held and not self.state.get("checks_accepted") and (self.wanted("pairs") or self.wanted("judge")):
            print("Held: checkers flagged queries in " + ", ".join(f"{v} ({len(self.state['query_flags'][v])})" for v in held)
                  + ". Look them over in " + ", ".join(str(self.folder / f"queries-{v}" / "index.html") for v in held)
                  + "; fix the lever, or rerun with --accept-checks.")
            return 4

    def pairs(self):
        """4. Sample units where each variant's answers differ from the baseline's."""
        from semantic_pdf_diff import rounds
        for v in self.spec["variants"]:
            batch = self.folder / f"pairs-{v}"
            if self.done(f"pairs:{v}"):  # "units" raised past the sample: resample (the first units stay the same)
                built = json.loads((batch / "pairs.json").read_text())
                if len(built["items"]) < min(self.target, built["units"]["units"] - built["units"]["unchanged"]):
                    self.state["steps"].pop(f"pairs:{v}")
            if self.wanted("pairs") and not self.done(f"pairs:{v}") and self.done(f"replay:{v}") \
                    and self.done("replay:baseline"):
                built = rounds.build_batch(self.runs_root / "baseline", self.runs_root / v, batch, n=self.target,
                                           unit=self.unit_of(v), documents=self.documents)
                checks = built["units"]["checks"]
                self.state.setdefault("batch_checks", {})[v] = checks
                for problem, found in (("unique claims hidden by sampling", checks["hidden_unique_claims"]),
                                       ("changed units outside the lever's reach", checks["changed_out_of_scope"]),
                                       ("runs of no document family", len(checks.get("without_family", [])))):
                    if found:
                        print(f"{v}: {found} {problem} (pairs-{v}/pairs.json: units.checks)")
                if rounds.rubric_of(self.rubric).whole():  # the whole page and every claim (v6)
                    rounds.add_context(batch, self.runs_root / "baseline", self.runs_root / v, n=self.target,
                                       unit=self.unit_of(v))
                self.figure("units_changed", built["units"]["units"] - built["units"]["unchanged"], variant=v, step="pairs")
                self.figure("units_total", built["units"]["units"], variant=v, step="pairs")
                self.mark(f"pairs:{v}", "done")

    def judge(self):
        """5. Judge in chunks, round-robin over variants, so that at the cap every variant has about the same number of
        units judged. Every variant is judged to its full sample and decided once (fixed n): stopping as soon as an
        interval cleared, at 16, 24 and 32 units, accepted a lever with no effect 12-18% of the time instead of about
        6-9% (overall review, 2026-09-28). "early_stop": true restores that for rounds 1-8's records. The main judges
        see every unit; "escalate" judges only units the main judges leave unsettled (a failed verdict, a flip with the
        order, disagreement); failed verdicts are asked once more when a variant's sample is done. "confirm_judges"
        (expensive) judge the first "confirm_units" units of an accepted variant, as a separate check. The criteria
        are set in advance: fixed when judging starts, and a later change is refused."""
        from semantic_pdf_diff import rounds
        from semantic_pdf_diff.models import Criteria
        if self.judges and self.wanted("judge"):
            try:
                rounds.lock_criteria(self.state, self.spec["criteria"])
            except ValueError as e:
                print(f"Refusing: {e}")
                return 2
            self.save_state()
        self.criteria = Criteria.model_validate(self.state.get("criteria") or self.spec["criteria"])
        judged = self.state.setdefault("judged", {})    # variant -> units judged by every judge
        stopped = self.state.setdefault("stopped", {})  # variant -> why judging stopped
        for v in self.spec["variants"]:  # rounds judged before chunking: all judges done means complete
            if self.judges and all(self.done(f"judge:{v}:{m}") for m in self.judges) and v not in stopped:
                judged[v] = min(self.target, len(json.loads((self.folder / f"pairs-{v}" / "pairs.json").read_text())["items"]))
                stopped[v] = f"complete at {judged[v]}"
        for v in list(stopped):  # "units" raised since a variant completed: judge on
            pairs = self.folder / f"pairs-{v}" / "pairs.json"
            if stopped[v].startswith("complete at") and pairs.exists() \
                    and judged.get(v, 0) < min(self.target, len(json.loads(pairs.read_text())["items"])):
                stopped.pop(v)
                self.state["steps"].pop(f"decide:{v}", None)
        self.save_state()
        if not (self.wanted("judge") and self.judges):
            return None
        try:
            active = [v for v in self.spec["variants"] if self.done(f"pairs:{v}") and v not in stopped]
            while active:
                for v in list(active):
                    batch = self.folder / f"pairs-{v}"
                    available = len(json.loads((batch / "pairs.json").read_text())["items"])
                    upto = min(judged.get(v, 0) + self.chunk, self.target, available)
                    for model in self.judges:
                        self.ask(v, model, upto)
                    self.settle(v, upto)
                    judged[v] = upto
                    self.state.pop("paused", None)
                    self.save_state()
                    result = rounds.decide(batch, upto, documents=self.documents, criteria=self.criteria,
                                           gains=self.gains_of(v))
                    if result["overall"]:
                        self.figure("win_rate_interim", result["overall"], variant=v, stratum="all", step="judge",
                                    units=upto)
                    if self.early and upto >= self.minimum and result["decision"].startswith(("accepted", "rejected")):
                        self.finish_variant(v, f"stopped early at {upto} units: clear result")
                    elif upto >= min(self.target, available):
                        for model in self.judges:  # failed verdicts, once more
                            self.ask(v, model, upto, retry_failed=True)
                        self.settle(v, upto, retry_failed=True)
                        self.finish_variant(v, f"complete at {upto} units")
                    if v in stopped:
                        active.remove(v)
            for v in self.spec["variants"]:
                if self.done(f"decide:{v}"):
                    self.confirm(v)
        except Paused as why:
            self.state["paused"] = str(why)
            self.save_state()
            self.spent_figure("judge")
            return 3
        self.spent_figure("judge")

    def leftovers(self):
        """Variants finished in an earlier run, before chunked judging; post-mortems for variants decided before
        post-mortems existed (--only postmortem)."""
        judged, stopped = self.state.get("judged", {}), self.state.get("stopped", {})
        for v in self.spec["variants"]:
            if v in stopped and not self.done(f"decide:{v}") and judged.get(v):
                self.finish_variant(v, stopped[v])
        if self.only == "postmortem":
            for v in self.spec["variants"]:
                if self.done(f"decide:{v}") and not (self.folder / f"pairs-{v}" / "postmortem.json").exists():
                    self.postmortem_of(v)

    def report(self):
        """7. Report."""
        if self.wanted("report"):
            from semantic_pdf_diff import insights, ledger, rounds
            self.figure("spent_total", ledger.spent(self.ledger_path, round=self.name), step="report")
            rounds.report(self.history, self.report_path)
            print(f"Report: {self.report_path}")
            for v in self.spec["variants"]:  # rounds decided before analyses existed
                if self.done(f"decide:{v}") and not (self.folder / f"pairs-{v}" / "analysis.json").exists():
                    insights.analyse(self.folder / f"pairs-{v}", self.state.get("judged", {}).get(v))
            print(f"Insights: {insights.page(self.folder)}")

    # --- judging's parts

    def gains_of(self, v):
        """Measured once per variant, for a gain named in the criteria."""
        from semantic_pdf_diff import rounds
        if v not in self.measured:
            self.measured[v] = (rounds.gains(self.runs_root / "baseline", self.runs_root / v, self.fixture)
                                if self.criteria.gain else {})
        return self.measured[v]

    def client_for(self, folder, settings):
        """A model client over a folder's own fixture (llm.folder_client); tests answer with stubs instead."""
        from semantic_pdf_diff.llm import folder_client
        return folder_client(folder, settings)

    def ask(self, v, model, upto, only=None, retry_failed=False, step="judge", verdicts_dir="verdicts"):
        """One judge over a variant's first `upto` units; raises Paused at the cap or out of budget."""
        from semantic_pdf_diff.judgements import ModelJudge
        from semantic_pdf_diff.ledger import Ledger
        from semantic_pdf_diff.llm import evaluator_settings
        batch = self.folder / f"pairs-{v}"
        if self.remaining() <= 0:
            raise Paused(f"round cap reached while judging {v} ({model}, units to {upto})")
        settings = evaluator_settings(model, concurrency=16, timeout=int(self.spec.get("judge_timeout", 600)),
                                      retries=int(self.spec.get("judge_retries", 2)), max_cost=self.remaining())
        with self.client_for(batch, settings) as client:
            client.ledger = Ledger(self.ledger_path, round=self.name, step=step, variant=v, judge=model)
            judge = ModelJudge(client, model, self.rubric, verdicts_dir)
            judge.rate(batch, limit=upto, only=only, retry_failed=retry_failed)
            failures = judge.errors
        # Failed verdicts over the whole round, not the last call's (the audit, 2026-09-28: each call overwrote the
        # count, so an escalation judge's failures read 0).
        key = f"{step}:{v}:{model}"
        self.state.setdefault("failures", {})[key] = self.state["failures"].get(key, 0) + len(failures)
        if failures:  # why, for diagnosis (a judge that times out on long units, say)
            notes = self.state.setdefault("failure_notes", {})
            notes[key] = (notes.get(key, []) + [f[:300] for f in failures])[-50:]
        if client.out_of_budget:
            raise Paused(f"{client.out_of_budget} while judging {v}")

    def settle(self, v, upto, retry_failed=False):
        """Second opinions where the main judges leave units unsettled; retry_failed asks the second judges' failed
        verdicts once more, as the main judges' are (these are the long, hard units)."""
        from semantic_pdf_diff import rounds
        if self.escalate:
            only = rounds.unsettled(self.folder / f"pairs-{v}", self.judges, upto)
            self.state.setdefault("escalated", {})[v] = sorted(only)
            for model in self.escalate:
                if only:
                    self.ask(v, model, upto, only=only, retry_failed=retry_failed)

    def finish_variant(self, v, reason):
        from semantic_pdf_diff import insights, rounds
        batch = self.folder / f"pairs-{v}"
        judged = self.state["judged"]
        self.state["stopped"][v] = reason
        result = rounds.decide(batch, judged[v], documents=self.documents, criteria=self.criteria, gains=self.gains_of(v))
        (batch / "decision.json").write_text(json.dumps({**result, "stopped": reason}, indent=2) + "\n")
        insights.analyse(batch, judged[v])  # the clues to why: agreement, changes, issues, tags, remarks
        self.postmortem_of(v)
        if result["overall"]:
            self.figure("win_rate", result["overall"], variant=v, stratum="all", step="decide", units=result["units_judged"])
        for stratum, value in result["strata"].items():
            if value:
                self.figure("win_rate", value, variant=v, stratum=stratum, step="decide", units=result["units_judged"])
        self.figure("decision", f"{result['decision']} ({reason})", variant=v, step="decide")
        self.mark(f"decide:{v}", "done")

    def postmortem_of(self, v):
        """Every lever's post-mortem after its round (the owner, 2026-09-30): samples of wins and losses, partitions,
        and the analyst's reading; Claude writes the round's review from it."""
        from semantic_pdf_diff import ledger, postmortem
        from semantic_pdf_diff.ledger import Ledger
        from semantic_pdf_diff.llm import evaluator_settings
        batch, pm = self.folder / f"pairs-{v}", self.spec["postmortem"]
        left = min(self.remaining(), pm["cap"] - ledger.spent(self.ledger_path, round=self.name, step="postmortem"))
        if pm["analyst"] and left > 0:
            settings = evaluator_settings(pm["analyst"], concurrency=1, timeout=600, retries=1, max_cost=left)
            with self.client_for(batch, settings) as client:
                client.ledger = Ledger(self.ledger_path, round=self.name, step="postmortem", variant=v,
                                       judge=pm["analyst"])
                postmortem.write(batch, self.documents, client, units=pm["units"])
        else:
            postmortem.write(batch, self.documents, None, units=pm["units"])
        print(f"Post-mortem: {batch / 'postmortem.html'}")

    def confirm(self, v):
        """Expensive judges on an accepted variant's first units: a separate check, recorded apart."""
        from semantic_pdf_diff import rounds
        judges = self.spec.get("confirm_judges", [])
        batch = self.folder / f"pairs-{v}"
        decision = json.loads((batch / "decision.json").read_text())
        if not judges or self.done(f"confirm:{v}") or not decision["decision"].startswith("accepted"):
            return
        units = min(int(self.spec.get("confirm_units", 16)), self.state["judged"][v])
        for model in judges:
            self.ask(v, model, units, step="confirm", verdicts_dir="verdicts-confirm")
        result = rounds.decide(batch, units, verdicts_dir="verdicts-confirm", documents=self.documents,
                               criteria=self.criteria, gains=self.gains_of(v))
        (batch / "decision-confirm.json").write_text(json.dumps({**result, "judges": judges}, indent=2) + "\n")
        if result["overall"]:
            self.figure("win_rate_confirm", result["overall"], variant=v, stratum="all", step="confirm", units=units)
        self.mark(f"confirm:{v}", "done")

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("round", type=Path)
    parser.add_argument("--only", choices=["record", "replay", "measure", "check", "pairs", "judge", "decide", "postmortem",
                                           "report"])
    parser.add_argument("--accept-checks", action="store_true",
                        help="the query checks' flags were looked over and accepted: go on to sampling and judging")
    args = parser.parse_args(argv)
    return RoundRunner(args.round, args.only, args.accept_checks).run()

if __name__ == "__main__":
    sys.exit(main())
