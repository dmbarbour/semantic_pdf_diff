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
    function, loaded under any name). Each worker sends its results down a pipe of its own, which blocks until read:
    no queue's background thread (the first version forked a process per item from workers holding a queue's thread,
    and lost results). A worker that dies is reported with the item it was on; workers left when the caller stops
    reading are ended."""
    items = list(items)
    if jobs <= 1 or len(items) <= 1:
        yield from map(work, items)
        return
    import multiprocessing
    from multiprocessing.connection import wait
    context = multiprocessing.get_context("fork")
    taken = context.Value("i", 0)  # the next item's index

    def worker(conn):
        while True:
            with taken.get_lock():
                i, taken.value = taken.value, taken.value + 1
            if i >= len(items):
                conn.close()
                return
            conn.send(("start", i))
            conn.send(("done", i, work(items[i])))

    workers, conns = [], []
    for _ in range(min(jobs, len(items))):
        receive, send = context.Pipe(duplex=False)
        process = context.Process(target=worker, args=(send,), daemon=True)
        process.start()
        send.close()  # the worker's end: its exit closes the pipe
        workers.append(process)
        conns.append(receive)
    on, remaining = {}, len(items)
    try:
        while remaining:
            for conn in wait(conns):
                try:
                    message = conn.recv()
                except EOFError:
                    conns.remove(conn)
                    if conn in on:
                        raise RuntimeError(f"a worker process died on {items[on[conn]]!r}") from None
                    continue
                if message[0] == "start":
                    on[conn] = message[1]
                else:
                    del on[conn]
                    remaining -= 1
                    yield message[2]
    finally:
        for process in workers:
            if process.is_alive():
                process.terminate()
            process.join()
