"""Run the test suite one module per process, several at once (code review 2026-10-08, E9: about 9 minutes one
module at a time, four modules taking 61%). The slowest modules start first, so the run ends near the longest one.

    python scripts/run_tests.py                 # every module, one process per CPU
    python scripts/run_tests.py -j 4 test_align test_store
    QUICK=1 python scripts/run_tests.py         # skips the tests marked @slow, as with unittest

Each module's output is shown only when it fails. Exit status 1 if any module fails. A run over every module that
passes records a pass for the tree it tested, for the commit gate (scripts/gate.py), unless --no-record
(or GATE_NO_RECORD, set by the gate's own runs).

How busy the machine is (its CPUs' busy share, and the load average) is said before the run, and measured during
each module. A module that failed with the CPUs at least BUSY busy is run again alone after the rest, the machine
measured again: one that passes then counts as passing, said to be flaky under load; one that fails again fails
(the owner, 2026-10-30, of test_interrupt timing out twice beside other work: "If there's an easy way to check how
busy the computer is, perhaps test it before and after the flaky test to support a diagnostic and a decision to
retry.").
"""
import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
# Measured 2026-10-08 (seconds, serial); the rest take under 20.
SLOW_FIRST = ["test_controlled", "test_fixtures", "test_settings", "test_replay_slices", "test_pipeline",
              "test_concurrency", "test_golden_requests"]


TIMEOUT = 900  # seconds a module may take (the slowest takes about 2 minutes): a hang fails, it doesn't stall
BUSY = 0.85    # the CPUs' busy share during a failed module from which it's run again alone


def cpu_times():
    """(busy, total) time of every CPU so far, from /proc/stat (Linux); None elsewhere."""
    try:
        fields = [int(x) for x in Path("/proc/stat").read_text().split("\n", 1)[0].split()[1:]]
    except (OSError, ValueError, IndexError):
        return None
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle, and waiting on the disk
    return sum(fields) - idle, sum(fields)


def busy_between(before, after):
    """The CPUs' busy share between two readings of cpu_times(), or None."""
    if not before or not after or after[1] <= before[1]:
        return None
    return (after[0] - before[0]) / (after[1] - before[1])


def machine(sample=1.0):
    """How busy the machine is now, in words: its CPUs' busy share over a second, and the 1-minute load average."""
    before = cpu_times()
    time.sleep(sample)
    share = busy_between(before, cpu_times())
    load = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    return described(share, load)


def described(share, load):
    parts = ([f"CPUs {share:.0%} busy"] if share is not None else []) + (
        [f"load {load:.1f} on {os.cpu_count()} CPUs"] if load is not None else [])
    return ", ".join(parts) or "not measured"


def run(name, timeout=TIMEOUT):
    """(name, exit code, output, seconds, the CPUs' busy share while it ran or None)."""
    started, before = time.monotonic(), cpu_times()
    # as `unittest discover -s tests` runs them: the tests folder on the path (for `stubs`), the root as cwd
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(TESTS), os.environ.get("PYTHONPATH")]))}
    try:
        done = subprocess.run([sys.executable, "-m", "unittest", name], cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        said = (e.stdout or b"").decode(errors="replace") + (e.stderr or b"").decode(errors="replace")
        return (name, 1, f"{said}\ntimed out after {timeout}s", time.monotonic() - started,
                busy_between(before, cpu_times()))
    return name, done.returncode, done.stdout + done.stderr, time.monotonic() - started, busy_between(before,
                                                                                                    cpu_times())


def retried(failed, again, now=machine, say=print):
    """The failures retried: each that failed with the CPUs at least BUSY busy is run again alone (again(name)), the
    machine measured first; one passing then counts as passing, flaky under load. failed: [(name, output, busy)].
    Returns (the failures that stand, [(name, why)] those that passed alone)."""
    stand, flaky = [], []
    for name, output, busy in failed:
        if busy is None or busy < BUSY:
            stand.append((name, output))
            continue
        quiet = now()
        say(f"{name} failed with the {described(busy, None)}: run again alone ({quiet})")
        _, code, again_said, seconds, busy_alone = again(name)
        alone = described(busy_alone, None)
        if code == 0:
            say(f"{name} passed alone in {seconds:.1f}s ({alone}): counted as passing, flaky under load")
            flaky.append((name, f"failed with the {described(busy, None)}, passed alone ({alone})"))
        else:
            say(f"{name} failed alone too ({alone})")
            stand.append((name, output + f"\n----- run again alone ({alone}) -----\n" + again_said))
    return stand, flaky


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("modules", nargs="*", help="test modules (default: every tests/test_*.py)")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--no-record", action="store_true", help="record no pass for the commit gate")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="seconds a module may take before it fails")
    args = parser.parse_args(argv)
    import gate
    record = not (args.modules or args.no_record or os.environ.get("GATE_NO_RECORD"))
    tree = gate.working_tree() if record and gate.in_repository() else None
    names = [m.removesuffix(".py") for m in args.modules] or sorted(p.stem for p in TESTS.glob("test_*.py"))
    names.sort(key=lambda n: SLOW_FIRST.index(n) if n in SLOW_FIRST else len(SLOW_FIRST))
    print(f"before the run: {machine()}", flush=True)
    started, failed, ran = time.monotonic(), [], 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for name, code, output, seconds, busy in pool.map(lambda name: run(name, args.timeout), names):
            summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
            ran += sum(int(line.split()[1]) for line in summary if line.startswith("Ran "))
            print(f"{name:32} {seconds:6.1f}s  {' '.join(summary[-1:]) or f'exit {code}'}"
                  + (f"  ({described(busy, None)})" if code else ""), flush=True)
            if code:
                failed.append((name, output, busy))
    failed, flaky = retried(failed, lambda name: run(name, args.timeout))
    for name, output in failed:
        print(f"\n===== {name} =====\n{output}")
    print(f"\n{ran} tests in {len(names)} modules, {time.monotonic() - started:.0f}s: "
          + (f"{len(failed)} module(s) failed: {', '.join(n for n, _ in failed)}" if failed else "OK")
          + (f"; flaky under load, passed alone: {'; '.join(f'{n} ({why})' for n, why in flaky)}" if flaky else ""))
    if tree and not failed:
        if gate.working_tree() == tree:
            gate.record(tree, "quick" if os.environ.get("QUICK") else "full", ran)
            print(f"pass recorded for tree {tree[:12]} (the commit gate)")
        else:
            print("the tree changed during the run: no pass recorded")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
