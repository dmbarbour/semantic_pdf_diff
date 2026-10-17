"""The commit gate (docs/plans/recording-tooling-2026-10-17.md, milestone 1): a commit needs a recorded pass of the
test suite on the exact tree it commits.

    python scripts/gate.py hook        # the pre-commit hook's check (scripts/hooks/pre-commit)
    python scripts/gate.py status      # whether the working tree and the staged tree have a recorded pass
    git config core.hooksPath scripts/hooks   # enables the hook in a checkout

scripts/run_tests.py, run over every module, records a pass for the working tree as git would commit it (untracked
files included, ignored ones not), hashed before and after the run so a tree edited mid-run isn't recorded. The hook
lets a commit through when its staged tree has a pass; otherwise it checks the staged tree out into a temporary
folder (the git-ignored samples linked in), runs the quick suite there (QUICK=1), records the pass, and blocks the
commit on a failure. Passes are kept in the repository's git folder (test-passes.jsonl), shared by its worktrees.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINKED = ("samples",)  # git-ignored inputs the tests read, linked into a staged tree's checkout


def git(*args, cwd=ROOT, env=None):
    done = subprocess.run(["git", *args], cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True)
    if done.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def passes_file(cwd=ROOT):
    """The repository's record of passes: in its common git folder, so a worktree's passes count in the main
    checkout."""
    return Path(cwd, git("rev-parse", "--git-common-dir", cwd=cwd)).resolve() / "test-passes.jsonl"


def in_repository(cwd=ROOT):
    try:
        return git("rev-parse", "--is-inside-work-tree", cwd=cwd) == "true"
    except (RuntimeError, OSError):
        return False


def working_tree(cwd=ROOT):
    """The tree git would commit from the working folder as it is (every change added, untracked files included,
    ignored ones not), by a copy of the index: the real one is left alone."""
    index = Path(cwd, git("rev-parse", "--git-path", "index", cwd=cwd))
    with tempfile.TemporaryDirectory(prefix="gate-") as d:
        temp = Path(d) / "index"
        if index.exists():
            shutil.copyfile(index, temp)  # its stat cache spares hashing unchanged files again
        env = {"GIT_INDEX_FILE": str(temp)}
        git("add", "-A", cwd=cwd, env=env)
        return git("write-tree", cwd=cwd, env=env)


def staged_tree(cwd=ROOT):
    return git("write-tree", cwd=cwd)


def record(tree, kind, tests, cwd=ROOT):
    """A pass of the suite (kind: quick or full) on a tree."""
    line = {"tree": tree, "kind": kind, "tests": tests,
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with passes_file(cwd).open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def passed(tree, cwd=ROOT):
    """The recorded pass of a tree, or None."""
    path = passes_file(cwd)
    if not path.exists():
        return None
    for line in reversed(path.read_text(encoding="utf-8").splitlines()):
        entry = json.loads(line)
        if entry["tree"] == tree:
            return entry
    return None


def test_staged(cwd=ROOT, python=sys.executable, out=sys.stdout):
    """Run the quick suite on the staged tree, checked out into a temporary folder; 0 if it passes."""
    with tempfile.TemporaryDirectory(prefix="gate-tree-") as d:
        tree = Path(d) / "tree"
        git("checkout-index", "-a", f"--prefix={tree}/", cwd=cwd)
        for name in LINKED:
            if (Path(cwd) / name).exists() and not (tree / name).exists():
                (tree / name).symlink_to(Path(cwd).resolve() / name)
        clean = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # a hook's index and folder
        env = {**clean, "QUICK": "1", "GATE_NO_RECORD": "1",  # the hook records it (older suites lack a flag)
               "PYTHONPATH": os.pathsep.join(filter(None, [str(tree / "src"), str(tree / "lab/src"),
                                                           os.environ.get("PYTHONPATH")]))}
        done = subprocess.run([python, str(tree / "scripts/run_tests.py")], cwd=tree, env=env,
                              capture_output=True, text=True)
        lines = done.stdout.strip().splitlines()
        out.write(done.stdout[-20000:] + done.stderr[-5000:] if done.returncode else (lines or [""])[-1] + "\n")
        return done.returncode


def hook(cwd=ROOT, out=sys.stdout):
    """The pre-commit check: a recorded pass of the staged tree, else the quick suite run on it."""
    tree = staged_tree(cwd)
    found = passed(tree, cwd)
    if found:
        out.write(f"gate: the staged tree passed the {found['kind']} suite at {found['time']}\n")
        return 0
    out.write("gate: no recorded pass of the staged tree; running the quick suite on it (about 3 minutes)\n")
    out.flush()
    code = test_staged(cwd, out=out)
    if code:
        out.write("gate: the staged tree fails its tests; commit blocked\n")
        return 1
    record(tree, "quick", "staged", cwd)
    out.write("gate: passed; recorded\n")
    return 0


def status(cwd=ROOT, out=sys.stdout):
    for name, tree in (("working tree", working_tree(cwd)), ("staged tree", staged_tree(cwd))):
        found = passed(tree, cwd)
        out.write(f"{name} {tree[:12]}: " + (f"passed ({found['kind']}, {found['time']})" if found else "no pass")
                  + "\n")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["hook"]:
        return hook()
    if argv[:1] == ["status"]:
        return status()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
