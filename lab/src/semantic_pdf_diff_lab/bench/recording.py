"""What the lab's recording scripts share (code review 2026-10-08, E4: the scripts copied each other): the settings
every recording's queries are shaped with, where the repository's spending ledger is, and which runs can't be scored.
"""
import contextlib
import json
import sqlite3
from pathlib import Path

# The settings recordings share (scripts/record_runs.py, controlled.py, real_pairs.py): they shape the queries, so they
# decide what replays. One definition, so recordings can't drift apart.
BASE_SETTINGS = {"claims_per_request": 20, "output_tokens": 4000, "context_tokens": 262144, "image_tokens": 300}

# the spending ledger, relative to the repository's root (ledger.spent: 0 without one)
LEDGER = "benchmarks/ledger.jsonl"

def main_checkout(root):
    """The repository's main working folder, from any of its worktrees (root itself outside git, or in the main
    one): a frozen worktree's runs spend into, and read answers from, the main checkout's ledger and archives, so
    nothing needs folding back before the worktree goes (recording tooling, 2026-10-17)."""
    import subprocess
    done = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True)
    return Path(done.stdout.strip()).parent if done.returncode == 0 else Path(root)

def ledger(root):
    """The spending ledger every run writes: the main checkout's."""
    return main_checkout(root) / LEDGER

def cut(folder):
    """Why a run's results can't be scored, or None: a cap cut it (its report says it paused), or tasks weren't
    reached (a cap, or a replay without their answers). Which work was cut followed the order answers came in, so the
    lab doesn't score it: the run is resumed instead (the owner, 2026-10-12: "Paused, not a result."; the determinism
    review, D6)."""
    folder = Path(folder)
    report = folder / "report.json"
    if report.exists():
        paused = json.loads(report.read_text(encoding="utf-8")).get("paused")
        if paused:
            return f"paused: {paused}"
    store = folder / "store.sqlite"
    if store.exists():
        with contextlib.closing(sqlite3.connect(f"file:{store}?mode=ro", uri=True)) as db:
            unreached = sum(json.loads(row)["status"] == "not_reached" for (row,) in db.execute("SELECT row FROM task"))
        if unreached:
            return f"{unreached} tasks not reached"
    return None

def forked(work, items, jobs):
    """work(item) for each item, yielded as each finishes: in this process when jobs <= 1, else in `jobs` forked
    processes taking items by their index (nothing pickled but indices and results, so `work` may be a script's own
    function, loaded under any name). Each item runs in a process of its own (a run's state, its caches and open
    files, doesn't outlive it)."""
    items = list(items)
    if jobs <= 1 or len(items) <= 1:
        yield from map(work, items)
        return
    import multiprocessing
    context = multiprocessing.get_context("fork")
    taken, done = context.Value("i", 0), context.Queue()  # the next item's index; results
    def worker():
        while True:
            with taken.get_lock():
                i, taken.value = taken.value, taken.value + 1
            if i >= len(items):
                return
            child = context.Process(target=lambda i=i: done.put((i, work(items[i]))))
            child.start()
            child.join()
            if child.exitcode:
                done.put((i, None))  # it died before answering
    workers = [context.Process(target=worker) for _ in range(min(jobs, len(items)))]
    for w in workers:
        w.start()
    for _ in items:
        i, result = done.get()
        if result is None:
            raise RuntimeError(f"a worker process died on {items[i]!r}")
        yield result
    for w in workers:
        w.join()
