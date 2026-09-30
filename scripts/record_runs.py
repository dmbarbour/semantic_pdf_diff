"""Record (or replay) the slice runs listed in scripts/slices.json, for a responder and a query variant.

Resumable: answers already in the fixture are replayed, so rerunning after a pause (e.g. the
provider balance ran out: exit code 3) only pays for what's missing. Every paid response is
tagged in the ledger.

    python scripts/record_runs.py --fixture tests/fixtures/slices.sqlite --set dev \\
        --ledger benchmarks/ledger.jsonl --tag round=r00 --tag step=record-baseline
    python scripts/record_runs.py --replay --fixture tests/fixtures/replay-slices.zip --out benchmarks/runs/baseline
"""
import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).with_name("slices.json")
# The settings every recording shares (they shape the queries, so they decide which answers replay).
BASE_SETTINGS = {"claims_per_request": 20, "output_tokens": 4000, "context_tokens": 262144, "image_tokens": 300}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--set", choices=["dev", "heldout", "all"], default="all")
    parser.add_argument("--run", action="append", help="only these runs (repeatable)")
    parser.add_argument("--variant", type=Path, help="settings JSON of a query variant, merged over the base settings")
    parser.add_argument("--responder", help="default: the configured model")
    parser.add_argument("--fresh-regions", default="",
                        help="A/A control: extraction for these regions (comma-separated) answered afresh, recorded apart")
    parser.add_argument("--out", type=Path, default=ROOT / "benchmarks/runs/scratch", help="folder for the runs' stores")
    parser.add_argument("--replay", action="store_true", help="replay only (no model calls); fails on anything unrecorded")
    parser.add_argument("--retry-failures", action="store_true",
                        help="ask recorded failures again (default: replay them, so variants differ only where they change requests)")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--max-cost", type=float)
    parser.add_argument("--plan", action="store_true", help="estimate calls and tokens without calling the model")
    parser.add_argument("--extract-only", action="store_true",
                        help="extraction only: each slice on its own, without situating or comparisons")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(ROOT / "src"))
    from semantic_pdf_diff import cli

    manifest = json.loads(MANIFEST.read_text())
    runs = [r for r in manifest["runs"] if (args.set == "all" or r["set"] == args.set) and (not args.run or r["name"] in args.run)]
    settings = dict(BASE_SETTINGS)
    if args.variant:
        settings.update(json.loads(args.variant.read_text()))
    # Every setting that can change a query, resolved (defaults and environment filled in): a replay
    # then means the same thing after defaults move. Rounds 1-9 saved only the settings they changed,
    # so the 2026-09-28 promotion silently changed what their settings.json meant.
    from semantic_pdf_diff.models import SETTING_CLASSES, Settings
    resolved = Settings.from_env(**settings).model_dump(mode="json")
    settings = {k: v for k, v in resolved.items() if SETTING_CLASSES[k] != "endpoint"}
    args.out.mkdir(parents=True, exist_ok=True)
    config = args.out / "settings.json"
    config.write_text(json.dumps(settings, indent=2))
    if args.extract_only:  # each slice once, paired with itself: nothing to compare
        seen = []
        for run in runs:
            for name in run["slices"]:
                if name not in seen:
                    seen.append(name)
        runs = [{"name": name, "slices": [name, name]} for name in seen]
    worst = 0
    from semantic_pdf_diff import ledger
    tags = dict(t.split("=", 1) for t in args.tag)
    spent_before = ledger.spent(args.ledger, **tags) if args.ledger and args.ledger.exists() else 0.0
    for run in runs:
        a, b = (ROOT / "samples/slices" / f"{name}.pdf" for name in run["slices"])
        command = [str(a), str(b), "--config", str(config), "-q"] + (["--no-situate"] if args.extract_only else [])
        if args.plan:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                cli.main(command + ["--plan"])
            print(run["name"], json.dumps(json.loads(buffer.getvalue())["total"]))
            continue
        command += ["--out", str(args.out / run["name"]), "--fixture", str(args.fixture),
                    "--fixture-mode", "replay" if args.replay else "replay-or-record" if args.retry_failures else "record-new"]
        if args.replay:
            command += ["--base-url", "http://127.0.0.1:9/v1"]
        if args.responder:
            command += ["--responder", args.responder]
        if args.fresh_regions:
            command += ["--fresh-regions", args.fresh_regions]
        if args.ledger:
            command += ["--ledger", str(args.ledger)] + [f"--ledger-tag={t}" for t in args.tag + [f"run={run['name']}"]]
        if args.max_cost:  # a cap for the whole recording, not per slice (each run's client starts at 0)
            spent = (ledger.spent(args.ledger, **tags) - spent_before) if args.ledger and args.ledger.exists() else 0.0
            left = args.max_cost - spent
            if left <= 0:
                print(f"{run['name']}: cap of ${args.max_cost} reached", flush=True)
                return 3
            command += ["--max-cost", f"{left:.4f}"]
        code = cli.main(command)
        print(f"{run['name']}: exit {code}", flush=True)
        if code == 3:  # out of budget: stop; rerunning resumes
            return 3
        worst = max(worst, code)
    return worst

if __name__ == "__main__":
    sys.exit(main())
