"""Run the test suite one module per process, several at once (code review 2026-10-08, E9: about 9 minutes one
module at a time, four modules taking 61%). The slowest modules start first, so the run ends near the longest one.

    python scripts/run_tests.py                 # every module, one process per CPU
    python scripts/run_tests.py -j 4 test_align test_store
    QUICK=1 python scripts/run_tests.py         # skips the tests marked @slow, as with unittest

Each module's output is shown only when it fails. Exit status 1 if any module fails.
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


def run(name):
    started = time.monotonic()
    # as `unittest discover -s tests` runs them: the tests folder on the path (for `stubs`), the root as cwd
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(TESTS), os.environ.get("PYTHONPATH")]))}
    done = subprocess.run([sys.executable, "-m", "unittest", name], cwd=ROOT, env=env, capture_output=True, text=True)
    return name, done.returncode, done.stdout + done.stderr, time.monotonic() - started


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("modules", nargs="*", help="test modules (default: every tests/test_*.py)")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    args = parser.parse_args(argv)
    names = [m.removesuffix(".py") for m in args.modules] or sorted(p.stem for p in TESTS.glob("test_*.py"))
    names.sort(key=lambda n: SLOW_FIRST.index(n) if n in SLOW_FIRST else len(SLOW_FIRST))
    started, failed, ran = time.monotonic(), [], 0
    with ThreadPoolExecutor(args.jobs) as pool:
        for name, code, output, seconds in pool.map(run, names):
            summary = [line for line in output.splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
            ran += sum(int(line.split()[1]) for line in summary if line.startswith("Ran "))
            print(f"{name:32} {seconds:6.1f}s  {' '.join(summary[-1:]) or f'exit {code}'}", flush=True)
            if code:
                failed.append((name, output))
    for name, output in failed:
        print(f"\n===== {name} =====\n{output}")
    print(f"\n{ran} tests in {len(names)} modules, {time.monotonic() - started:.0f}s: "
          + (f"{len(failed)} module(s) failed: {', '.join(n for n, _ in failed)}" if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
