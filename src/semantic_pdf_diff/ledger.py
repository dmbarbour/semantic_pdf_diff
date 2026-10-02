"""Spending and figures: append-only JSON-lines files that make work resumable and graphable.

The ledger records what every model response cost (as the provider reports it), tagged
with where it was spent (round, step, stage), so budgets can be enforced and audited. The
history records every measured figure, so each step of an improvement round can be graphed
even if a later step is paused.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _append(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

def read(path, archives=False):
    """A ledger's records; with archives, its rotated months' first (see rotate)."""
    path = Path(path)
    paths = (sorted(path.parent.glob(f"{path.stem}-????-??{path.suffix}")) if archives else []) + [path]
    return [json.loads(line) for p in paths if p.exists() for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]

def rotate(path, before):
    """Move records older than `before` (an ISO time) into monthly archives beside the ledger (ledger-2026-09.jsonl):
    spend checks read only the live file, which once held 32,000 records re-read on every check (code review
    2026-10-01). Rotate between rounds: a round's cap counts what the live file holds. Returns the records moved."""
    path = Path(path)
    keep, moved = [], {}
    for line in (path.read_text(encoding="utf-8").splitlines() if path.exists() else ()):
        if line.strip():
            when = json.loads(line).get("time", "")
            (moved.setdefault(when[:7], []) if when and when < before else keep).append(line)
    for month, lines in sorted(moved.items()):
        with path.with_name(f"{path.stem}-{month}{path.suffix}").open("a", encoding="utf-8") as f:
            f.write("".join(line + "\n" for line in lines))
    path.write_text("".join(line + "\n" for line in keep), encoding="utf-8")
    return sum(len(v) for v in moved.values())

class Ledger:
    """Appends one line per model response: time, model, tokens, reported cost, and tags."""

    def __init__(self, path, **tags):
        self.path, self.tags = Path(path), {k: v for k, v in tags.items() if v is not None}
        self.lock = threading.Lock()

    def add(self, model, kind, usage):
        """usage as the server reported it; empty for a response that came without one (a stream
        cut off before its last chunk): recorded as "unpriced", since it may still be billed."""
        record = {"time": _now(), "model": model, "kind": kind, **self.tags,
                  "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                  "completion_tokens": int(usage.get("completion_tokens") or 0),
                  "cost": float(usage.get("estimated_cost") or 0.0)}
        if "estimated_cost" not in usage:
            record["unpriced"] = True
        with self.lock:
            _append(self.path, record)

def unpriced(path, archives=False, **match):
    """How many ledger records matching the given tags came without a reported cost."""
    return sum(1 for r in read(path, archives) if r.get("unpriced") and all(r.get(k) == v for k, v in match.items()))

def spent(path, archives=False, **match):
    """Total reported cost of ledger records matching the given tags (unpriced ones count 0: see unpriced); with
    archives, the rotated months' too (a full accounting rather than a cap's)."""
    return round(sum(r.get("cost", 0.0) for r in read(path, archives) if all(r.get(k) == v for k, v in match.items())), 6)

def figure(path, *, metric, value, **fields):
    """Record one measured figure (a metric's value with its context) in a history file."""
    _append(path, {"time": _now(), "metric": metric, "value": value, **fields})
