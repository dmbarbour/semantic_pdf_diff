"""Snapshot every query the pipeline builds, to prove a refactor changed none (or show which).

Replays every slice run under a few settings (the defaults, round 0's levers, and every optional
lever on), offline against the local master fixture, and records each task's query hash from the
runs' query logs. Answers the fixture lacks don't matter: queries are logged before they're looked
up. Two snapshots compare task by task.

    python scripts/query_snapshot.py take /tmp/before.json
    # ...refactor...
    python scripts/query_snapshot.py take /tmp/after.json
    python scripts/query_snapshot.py compare /tmp/before.json /tmp/after.json
"""
import argparse
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))
import record_runs  # noqa: E402

ROUND0 = {k: v for k, v in json.loads((ROOT / "benchmarks/round0.json").read_text()).items()
          if k not in ("claims_per_request", "output_tokens")}
CONFIGS = {  # name: (settings over the recording's base, whole pipeline or extraction only)
    "defaults": ({}, True),
    "round0": (ROUND0, False),
    "all-levers": ({"references": True, "tile_locator": True, "sheet_details": True, "table_filter": True,
                    "visual_rules": ["Read a chart's axes before its values."], "extract_rules": ["Keep units."]}, False),
}

def take(target, fixture):
    from semantic_pdf_diff import cli
    from semantic_pdf_diff.store import Store
    manifest = json.loads(record_runs.MANIFEST.read_text())
    snapshot = {}
    with tempfile.TemporaryDirectory(prefix="snapshot-") as d:
        for name, (levers, whole) in CONFIGS.items():
            config = Path(d) / f"{name}.json"
            config.write_text(json.dumps({**record_runs.BASE_SETTINGS, **levers}))
            runs = ([(r["name"], r["slices"]) for r in manifest["runs"]] if whole
                    else [(s["name"], [s["name"], s["name"]]) for s in manifest["slices"]])
            for run, slices in runs:
                out = Path(d) / name / run
                command = [str(ROOT / "samples/slices" / f"{s}.pdf") for s in slices] + [
                    "--config", str(config), "-q", "--out", str(out), "--fixture", str(fixture),
                    "--fixture-mode", "replay", "--base-url", "http://127.0.0.1:9/v1"] + ([] if whole else ["--no-situate"])
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    cli.main(command)
                with Store(out) as store:
                    for q in store.queries():
                        snapshot[f"{name}|{run}|{q['role']}|{q['content'][7:19]}|{q['task']}"] = q["hash"]
                print(f"{name} {run}: {sum(1 for k in snapshot if k.startswith(f'{name}|{run}|'))} queries", flush=True)
    Path(target).write_text(json.dumps(snapshot, indent=0, sort_keys=True) + "\n")
    return snapshot

def compare(before, after):
    a, b = json.loads(Path(before).read_text()), json.loads(Path(after).read_text())
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    gone, new = sorted(set(a) - set(b)), sorted(set(b) - set(a))
    for label, keys in (("changed", changed), ("only before", gone), ("only after", new)):
        print(f"{label}: {len(keys)}")
        for k in keys[:15]:
            print("  ", k)
    return not (changed or gone or new)

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("take")
    t.add_argument("target", type=Path)
    t.add_argument("--fixture", type=Path, default=ROOT / "tests/fixtures/slices.sqlite")
    c = sub.add_parser("compare")
    c.add_argument("before", type=Path)
    c.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    if args.command == "take":
        print(f"{len(take(args.target, args.fixture))} queries -> {args.target}")
        return 0
    return 0 if compare(args.before, args.after) else 1

if __name__ == "__main__":
    sys.exit(main())
