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
