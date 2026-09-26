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

def read(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

class Ledger:
    """Appends one line per model response: time, model, tokens, reported cost, and tags."""

    def __init__(self, path, **tags):
        self.path, self.tags = Path(path), {k: v for k, v in tags.items() if v is not None}
        self.lock = threading.Lock()

    def add(self, model, kind, usage):
        record = {"time": _now(), "model": model, "kind": kind, **self.tags,
                  "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                  "completion_tokens": int(usage.get("completion_tokens") or 0),
                  "cost": float(usage.get("estimated_cost") or 0.0)}
        with self.lock:
            _append(self.path, record)

def spent(path, **match):
    """Total reported cost of ledger records matching the given tags."""
    return round(sum(r.get("cost", 0.0) for r in read(path) if all(r.get(k) == v for k, v in match.items())), 6)

def figure(path, *, metric, value, **fields):
    """Record one measured figure (a metric's value with its context) in a history file."""
    _append(path, {"time": _now(), "metric": metric, "value": value, **fields})
