"""Prove a refactor changes nothing: replay the slices' development runs and the controlled corpus offline, in the
working tree and in a committed revision, and compare every report (decision 0027; docs/samples-and-testing.md).

    python scripts/refactor_check.py                  # the working tree against HEAD
    python scripts/refactor_check.py --against main~3 # against another revision
    python scripts/refactor_check.py --only slices    # one of the two (slices, controlled)

The revision is checked out into a temporary git worktree (samples/ linked into it). In each tree the slices'
development runs replay from its tests/fixtures/replay-slices.zip, and the controlled corpus's standard and
row-by-row runs from its benchmarks/controlled/replay.zip, all four at once. Nothing is asked of a model: a request
a replay doesn't hold fails that run, which alone shows a change reached the model. Every report is then compared
whole, but for when it was made (created_at) and the tree it was made in (its root's path).

Exit status: 0 when every run replayed and every report is the same, 1 otherwise (each difference listed). What the
replays don't cover is compared by hand (docs/samples-and-testing.md): renderings, the lab's pages, rewritten pure
functions.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLICES_FIXTURE = "tests/fixtures/replay-slices.zip"
# The controlled corpus's replays into folders of our own (scripts/controlled.py writes under benchmarks/runs).
CONTROLLED = """import sys
sys.path.insert(0, "scripts")
import controlled
from pathlib import Path
runs, pairs = Path(sys.argv[1]), Path(sys.argv[2])
code = controlled.run(True, None, 0, False, runs=runs, pair_runs=pairs)
code = max(code, controlled.run(True, None, 0, False, runs=runs, pair_runs=pairs, rows=True))
sys.exit(code)
"""

def replays(tree, out, only):
    """The commands replaying a tree's runs into out: [(name, argv, log)]."""
    python = sys.executable
    jobs = []
    if only in (None, "slices"):
        from semantic_pdf_diff import fixtures
        with fixtures.open(tree / SLICES_FIXTURE, "read") as f:
            (responder,) = f.responders()  # named, so a replay without .env doesn't empty the run
        jobs.append(("slices", [python, "scripts/record_runs.py", "--replay", "--set", "dev", "--fixture",
                                SLICES_FIXTURE, "--responder", responder, "--out", str(out / "slices")]))
    if only in (None, "controlled"):
        jobs.append(("controlled", [python, "-c", CONTROLLED, str(out / "controlled"), str(out / "pairs")]))
    return jobs

def run(tree, name, argv, log):
    """One replay in a tree, its output in log; its exit code (2, coverage incomplete, is a finished run)."""
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(tree / "src"), str(tree / "lab/src")])}
    with open(log, "w") as f:
        return subprocess.run(argv, cwd=tree, env=env, stdout=f, stderr=subprocess.STDOUT).returncode

def reports(folder, tree):
    """{relative path: report as JSON text} under folder, without created_at; the tree's root and this checkout's
    (where the worktree's samples/ leads) a placeholder."""
    found = {}
    for path in sorted(folder.rglob("report.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        report.pop("created_at", None)
        text = json.dumps(report, sort_keys=True, indent=1)
        for root in sorted({str(tree), str(tree.resolve()), str(ROOT)}, key=len, reverse=True):
            text = text.replace(root, "<tree>")
        found[str(path.relative_to(folder))] = text
    return found

def differences(before, after):
    """[(run, what differs)] between two trees' reports."""
    found = []
    for run in sorted(set(before) | set(after)):
        if run not in after or run not in before:
            found.append((run, "only before" if run not in after else "only after"))
            continue
        if before[run] != after[run]:
            a, b = json.loads(before[run]), json.loads(after[run])
            fields = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
            found.append((run, ", ".join(fields)))
    return found

def worktree(revision, folder):
    """A detached worktree of revision in folder, samples/ linked in."""
    subprocess.run(["git", "worktree", "add", "--detach", "--quiet", str(folder), revision], cwd=ROOT, check=True)
    if (ROOT / "samples").exists():
        (folder / "samples").symlink_to(ROOT / "samples")

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--against", default="HEAD", help="the revision to compare with (default: HEAD)")
    parser.add_argument("--only", choices=["slices", "controlled"])
    parser.add_argument("--out", type=Path, help="keep the replays here (default: a temporary folder)")
    args = parser.parse_args(argv)
    if args.out and args.out.exists() and any(args.out.iterdir()):
        parser.error(f"{args.out} isn't empty: its reports would be compared too")
    sys.path.insert(0, str(ROOT / "src"))
    with tempfile.TemporaryDirectory(prefix="refactor-check-") as temp:
        out = args.out or Path(temp)
        before_tree = Path(temp) / "tree"
        worktree(args.against, before_tree)
        try:
            jobs = []
            for side, tree in (("before", before_tree), ("after", ROOT)):
                (out / side).mkdir(parents=True, exist_ok=True)
                jobs += [(side, tree, name, argv, out / f"{side}-{name}.log")
                         for name, argv in replays(tree, out / side, args.only)]
            print(f"replaying {', '.join(sorted({j[2] for j in jobs}))} at {args.against} and in the working tree "
                  f"({len(jobs)} at once; logs in {out})", flush=True)
            with ThreadPoolExecutor(len(jobs)) as pool:
                codes = list(pool.map(lambda j: run(j[1], j[2], j[3], j[4]), jobs))
            failed = [(side, name, code, log) for (side, _, name, _, log), code in zip(jobs, codes)
                      if code not in (0, 2)]
            for side, name, code, log in failed:
                print(f"{side}: the {name} replay failed (exit {code}; {log})")
            before, after = reports(out / "before", before_tree), reports(out / "after", ROOT)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(before_tree)], cwd=ROOT, check=True)
    found = differences(before, after)
    for run_, what in found:
        print(f"  {run_}: {what}")
    print(f"{len(after)} reports compared: {len(found)} differ" + (f"; {len(failed)} replays failed" if failed else ""))
    return 1 if found or failed or not after else 0

if __name__ == "__main__":
    sys.exit(main())
