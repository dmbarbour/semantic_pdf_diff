"""Progress and logging, so users can see long runs moving.

On a terminal, a tqdm progress bar per stage; otherwise (redirected output,
background jobs, log files) periodic heartbeat lines with the same numbers.
Totals grow as refinement adds tasks.
"""
import logging
import sys
import time

log = logging.getLogger("semantic_pdf_diff")
# Per-request detail, enabled by -vv.
requests_log = logging.getLogger("semantic_pdf_diff.requests")

def setup_logging(verbosity=0, quiet=False, log_file=None):
    """-q: warnings only; default: progress and summaries; -v: tasks; -vv: requests."""
    level = logging.WARNING if quiet else logging.DEBUG if verbosity >= 1 else logging.INFO
    for handler in list(log.handlers):  # close, don't just drop: a log file would leak
        log.removeHandler(handler)
        handler.close()
    log.setLevel(logging.DEBUG)
    log.propagate = False
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(console)
    if log_file:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
    requests_log.setLevel(logging.DEBUG if verbosity >= 2 else logging.INFO)

class Progress:
    """Counts tasks queued and finished for one stage of a run."""

    def __init__(self, stage, client=None, bar=None, heartbeat=30.0, clock=time.monotonic):
        self.stage, self.client, self.heartbeat, self.clock = stage, client, heartbeat, clock
        self.total = self.done = self.failed = 0
        self.started = self.last_beat = clock()
        self.tokens_at_start = self._tokens()
        if bar is None:
            bar = sys.stderr.isatty() and log.handlers and log.handlers[0].level <= logging.INFO
        self.bar = None
        if bar:
            from tqdm import tqdm
            self.bar = tqdm(total=0, desc=stage, unit="task", dynamic_ncols=True, leave=True)

    def _tokens(self):
        usage = getattr(self.client, "usage", None) or {}
        return sum(usage.values())

    def add(self, n=1):
        self.total += n
        if self.bar is not None:
            self.bar.total = self.total
            self.bar.refresh()

    def finish(self, status="complete"):
        self.done += 1
        self.failed += status == "failed"
        if self.bar is not None:
            self.bar.update(1)
            self.bar.set_postfix(self.rates(), refresh=False)
        elif self.clock() - self.last_beat >= self.heartbeat:
            self.last_beat = self.clock()
            log.info(self.line())

    def rates(self):
        minutes = max(self.clock() - self.started, 1e-6) / 60
        tokens = (self._tokens() - self.tokens_at_start) / minutes
        remaining = self.total - self.done
        eta = remaining / (self.done / minutes) if self.done else None
        return {"tokens/min": int(tokens), "eta_min": round(eta, 1) if eta is not None else "?"}

    def line(self):
        r = self.rates()
        failed = f", {self.failed} failed" if self.failed else ""
        return (f"{self.stage}: {self.done}/{self.total} tasks{failed}, {r['tokens/min']} tokens/min, "
                f"about {r['eta_min']} min left")

    def close(self):
        if self.bar is not None:
            self.bar.close()
        log.info(f"{self.stage}: {self.done} tasks done" + (f", {self.failed} failed" if self.failed else "")
                 + f" in {self.clock() - self.started:.0f}s")

class NoProgress:
    def add(self, n=1): pass
    def finish(self, status="complete"): pass
    def close(self): pass
