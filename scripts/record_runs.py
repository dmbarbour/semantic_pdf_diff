"""Record (or replay) the slice runs listed in scripts/slices.json, for a responder and a query variant.

Resumable: answers already in the fixture are replayed, so rerunning after a pause (e.g. the
provider balance ran out: exit code 3) only pays for what's missing. Every paid response is
tagged in the ledger.

    python scripts/record_runs.py --fixture tests/fixtures/slices.sqlite --set dev \\
        --ledger benchmarks/ledger.jsonl --tag round=r00 --tag step=record-baseline
    python scripts/record_runs.py --replay --fixture tests/fixtures/replay-slices.zip --out benchmarks/runs/baseline
    python scripts/record_runs.py --fixture tests/fixtures/slices.sqlite --set dev \\
        --pack tests/fixtures/replay-slices.zip

--pack exports the zip from the fixture (an archive keeping every answer recorded): the runs go into fresh stores in a
temporary folder, and every answer they're served or record is copied into a new fixture, which is packed. Nothing
is pruned. A recording's spend goes to the repository's ledger unless --ledger names another.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = Path(__file__).with_name("slices.json")
# The settings every recording shares (they shape the queries, so they decide which answers replay).
from semantic_pdf_diff_lab.bench.recording import BASE_SETTINGS, LEDGER  # noqa: E402 (every recording's)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--set", choices=["dev", "heldout", "all"], default="all")
    parser.add_argument("--run", action="append", help="only these runs (repeatable)")
    parser.add_argument("--variant", type=Path, help="settings JSON of a query variant, merged over the base settings")
    parser.add_argument("--responder", help="default: the configured model")
    parser.add_argument("--fresh-regions", default="",
                        help="A/A control: extraction for these regions (comma-separated) answered afresh, "
                             "recorded apart")
    parser.add_argument("--out", type=Path, help="folder for the runs' stores (default: benchmarks/runs/scratch)")
    parser.add_argument("--replay", action="store_true",
                        help="replay only (no model calls); fails on anything unrecorded")
    parser.add_argument("--retry-failures", action="store_true",
                        help="ask recorded failures again "
                             "(default: replay them, so variants differ only where they change requests)")
    parser.add_argument("--ledger", type=Path, default=ROOT / LEDGER, help="default: the repository's ledger")
    parser.add_argument("--pack", type=Path, metavar="ZIP",
                        help="export what the runs are served or record into this zip (fresh stores in a "
                             "temporary folder: not with --out)")
    parser.add_argument("--tag", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--max-cost", type=float)
    parser.add_argument("--jobs", type=int, default=1,
                        help="runs at once, in processes sharing the fixture (the cap is checked as each starts)")
    parser.add_argument("--extract-only", action="store_true",
                        help="extraction only: each slice on its own, without situating or comparisons")
    args = parser.parse_args(argv)
    if args.pack and args.out:
        parser.error("--pack replays into fresh stores of its own: not with --out")
    if args.pack:
        import tempfile
        from semantic_pdf_diff import fixtures
        with tempfile.TemporaryDirectory(prefix="record-runs-") as d:
            export = Path(d) / "export" / packed_name(args.pack)
            export.parent.mkdir()
            code = record(args, Path(d) / "runs", export)
            if code in (0, 2):
                fixtures.pack(export, args.pack)
                print(f"packed {args.pack}", flush=True)
            return code
    return record(args, args.out or ROOT / "benchmarks/runs/scratch")

def packed_name(target):
    """The name of the fixture inside a zip (kept, so unchanged answers pack to the same bytes)."""
    import zipfile
    if Path(target).exists():
        with zipfile.ZipFile(target) as z:
            names = [n for n in z.namelist() if n.endswith(".sqlite")]
            if len(names) == 1:
                return names[0]
    return "fixture.sqlite"

def record(args, out, export=None):
    """Each run recorded (or replayed) into stores under `out`; exit status the worst run's."""
    args.out = out
    sys.path.insert(0, str(ROOT / "src"))
    if args.replay and not args.responder:  # the responder the fixture holds, whatever the environment says
        from semantic_pdf_diff import fixtures
        with fixtures.open(args.fixture, "read") as f:
            held = f.responders(answered=True)
        if len(held) != 1:
            print(f"the fixture holds {held}: name one with --responder")
            return 1
        args.responder = held[0]
    from semantic_pdf_diff import pipeline
    from semantic_pdf_diff.progress import setup_logging
    setup_logging(quiet=True)

    manifest = json.loads(MANIFEST.read_text())
    runs = [r for r in manifest["runs"]
            if (args.set == "all" or r["set"] == args.set) and (not args.run or r["name"] in args.run)]
    settings = dict(BASE_SETTINGS)
    if args.variant:
        settings.update(json.loads(args.variant.read_text()))
    # Every setting that can change a query, resolved (defaults and environment filled in): a replay
    # then means the same thing after defaults move. Rounds 1-9 saved only the settings they changed,
    # so the 2026-09-28 promotion silently changed what their settings.json meant.
    from semantic_pdf_diff.settings import Settings
    settings = Settings.from_env(**settings).configuration()  # its levers in order, and every setting they shape
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
    from semantic_pdf_diff import ledger
    from semantic_pdf_diff_lab.bench.recording import forked
    tags = dict(t.split("=", 1) for t in args.tag) or {"round": "slices"}
    spent_before = ledger.spent(args.ledger, **tags) if args.ledger else 0.0

    def one(run):
        """(the run's name, its exit code, or None when the cap was reached before it started)."""
        a, b = (ROOT / "samples/slices" / f"{name}.pdf" for name in run["slices"])
        overrides = {"situate": False} if args.extract_only else {}
        if args.replay:
            overrides["base_url"] = pipeline.NO_MODEL
        if args.max_cost:  # a cap for the whole recording, not per slice (each run's client starts at 0)
            spent = (ledger.spent(args.ledger, **tags) - spent_before) if args.ledger else 0.0
            left = args.max_cost - spent
            if left <= 0:
                return run["name"], None
            overrides["max_cost"] = round(left, 4)
        options = pipeline.RunOptions(
            fixture=args.fixture, responder=args.responder,
            fixture_mode="replay" if args.replay else "replay-or-record" if args.retry_failures else "record-new",
            fresh_regions=tuple(r for r in (args.fresh_regions or "").split(",") if r),
            ledger=None if args.replay else args.ledger, export=export,
            ledger_tags={**tags, "run": run["name"]} if args.ledger and not args.replay else {})
        return run["name"], pipeline.attempt(pipeline.compare_paths, a, b, args.out / run["name"],
                                             pipeline.settings_from(config, **overrides), options)

    worst = 0
    for name, code in forked(one, runs, args.jobs):
        print(f"{name}: " + (f"cap of ${args.max_cost} reached" if code is None else f"exit {code}"), flush=True)
        worst = max(worst, 3 if code is None else code)  # 3: out of budget; rerunning resumes
    return worst

if __name__ == "__main__":
    sys.exit(main())
