"""Probe batteries: does the model use the context it's given? (lab bench/probes.py;
docs/plans/claim-context-2026-10-14.md, milestone 2, Measurement layer 4.)

    set -a; . ./.env; set +a
    python scripts/probes.py run                     # ask what isn't recorded (cents), into the working fixture
    python scripts/probes.py run --replay            # from the packed answers, offline
    python scripts/probes.py pack                    # replay.zip: the answers the battery replays

Reader probes are tiny Markdown documents read by the product's extraction; judge probes are claim pairs put to its
judge in both orders. Results go into benchmarks/probes/results.json under the responder that answered, so models and
backends are compared probe by probe. The settings are written once (settings.json) and kept, so replays ask exactly
the recorded queries; the battery's runs go into benchmarks/runs/probes/<responder> (local).
"""
import argparse
import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FOLDER = ROOT / "benchmarks/probes"
WORKING = FOLDER / "fixture.sqlite"  # recorded answers (git-ignored); packed into replay.zip
PACKED = FOLDER / "replay.zip"
SETTINGS = FOLDER / "settings.json"
RUNS = ROOT / "benchmarks/runs/probes"

def settings_file():
    """The battery's settings: written once from the defaults (situating off: no figures to place), then kept."""
    from semantic_pdf_diff.settings import Settings
    if not SETTINGS.exists():
        FOLDER.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(Settings.from_env(situate=False).configuration(), indent=2) + "\n")
    return SETTINGS

def run(replay, responder, max_cost, fixture=None, out=None, keep=True):
    """Both batteries, recorded (or replayed): results.json updated under the responder (keep); returns 0."""
    from semantic_pdf_diff import pipeline
    from semantic_pdf_diff_lab.bench import probes
    overrides = {"base_url": pipeline.NO_MODEL} if replay else {"max_cost": max_cost}
    if responder:
        overrides["model"] = responder
    settings = pipeline.settings_from(settings_file(), **overrides)
    name = responder or settings.model
    fixture = fixture or (PACKED if replay else WORKING)
    options = pipeline.RunOptions(fixture=fixture, responder=name,
                                  fixture_mode="replay" if replay else "record-new")
    folder = out or RUNS / name.replace("/", "_")
    if folder.exists():
        shutil.rmtree(folder)  # fresh stores: every answer from the fixture, none from a store's cache
    outcomes = probes.run_reader(folder, settings, options) + probes.run_judge(folder, settings, options)
    if not keep:
        return 0
    results = json.loads((FOLDER / "results.json").read_text()) if (FOLDER / "results.json").exists() else {}
    judge = [o for o in outcomes if o.check in ("A, B", "B, A")]
    # the battery's own settings, then each judge arm's (its judge probes alone)
    mine = [o for o in outcomes if not o.arm]
    results[name] = {**probes.summary(mine), "judge_consistent": probes.consistency([o for o in judge if not o.arm]),
                     "judge_arms": {arm: {**probes.summary(asked), "judge_consistent": probes.consistency(asked)}
                                    for arm in probes.JUDGE_ARMS if arm
                                    for asked in [[o for o in judge if o.arm == arm]]},
                     "outcomes": [asdict(o) for o in outcomes]}
    (FOLDER / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in results[name].items() if k != "outcomes"}, indent=1))
    for o in outcomes:
        print(f"{'pass' if o.passed else 'FAIL'}  {o.arm or '-':13s} {o.kind:10s} {o.property:11s} {o.probe}: "
              f"{o.check}  {o.read[:2]}")
    return 0

def pack():
    """replay.zip: the battery replayed from fresh stores against a copy of the working fixture, which marks the
    answers it uses, and only those packed."""
    import contextlib
    import io
    from datetime import datetime, timezone
    from semantic_pdf_diff import fixtures
    with tempfile.TemporaryDirectory() as d:
        copy = Path(d) / "fixture.sqlite"
        shutil.copy(WORKING, copy)
        with fixtures.open(copy, "read") as f:
            responders = f.responders()
        start = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with contextlib.redirect_stdout(io.StringIO()):
            for responder in responders:
                run(True, responder, None, fixture=copy, out=Path(d) / "runs" / responder.replace("/", "_"),
                    keep=False)
        with fixtures.open(copy, "record") as f:
            dropped = f.prune(start, force=True)["answers_removed"]
        fixtures.pack(copy, PACKED)
    print(f"packed {PACKED}: {dropped} answers the battery doesn't use left out")
    return 0

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    running = sub.add_parser("run", help="ask both batteries (recorded; answers already recorded are free)")
    running.add_argument("--replay", action="store_true", help="from the packed answers, without calling a model")
    running.add_argument("--responder", help="the model to ask or replay (default: the configured model)")
    running.add_argument("--max-cost", type=float, default=0.1)
    sub.add_parser("pack", help="pack the answers the battery replays into replay.zip (offline)")
    args = parser.parse_args(argv)
    if args.command == "pack":
        return pack()
    return run(args.replay, args.responder, args.max_cost)

if __name__ == "__main__":
    sys.exit(main())
