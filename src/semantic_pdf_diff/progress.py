"""Progress and logging, so users can see long runs moving (docs/plans/progress-display-2026-10-20.md).

A stage (extract, situate, compare) counts its requests, and shows bars of what's known when each appears: a file's
pages, a source's files, the pairs to judge. A bar's total never changes (the owner, 2026-10-20: "it's very awkward to
have say 97/100 items followed by 98/115. [...] I'd prefer to have multiple stacked progress bars that are each stable
size."). On a terminal the bars are drawn stacked, a status line below them and log lines printed above; otherwise
(redirected output, background jobs, log files) heartbeat lines give the same numbers.

A page is done once every request asked for it is answered, follow-ups included. A request belongs to the item being
worked on when it's asked (within); the dispatcher runs each answer's handler within the item it was asked for
(carried), so a follow-up the handler asks belongs to its parent's page. All of it runs on the calling thread, as the
handlers do.

The status counts the answers that came from the cache (a fixture's, in a replay) rather than the model: the dispatcher
says which each answer is as its handler runs (handling). The owner, 2026-10-21: "it would be convenient if we also
mention how many were answered from cache, e.g. 1234 answered (1179 from cache) or similar".
"""
import contextlib
import logging
import os
import shutil
import sys
import threading
import time

log = logging.getLogger("semantic_pdf_diff")
# Per-request detail, enabled by -vv.
requests_log = logging.getLogger("semantic_pdf_diff.requests")

DONE, LEFT = "█", "░"
EVERY = 0.1  # seconds between redraws at most

_current = None  # the item being worked on (the calling thread's)
_board = None    # the terminal's bars, while a stage draws them
_cached = False  # whether the answer being handled came from the cache, not the model (handling)

def setup_logging(verbosity=0, quiet=False, log_file=None):
    """-q: warnings only; default: progress and summaries; -v: tasks; -vv: requests."""
    level = logging.WARNING if quiet else logging.DEBUG if verbosity >= 1 else logging.INFO
    for handler in list(log.handlers):  # close, don't just drop: a log file would leak
        log.removeHandler(handler)
        handler.close()
    log.setLevel(logging.DEBUG)
    log.propagate = False
    console = Console(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(console)
    if log_file:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        log.addHandler(handler)
    requests_log.setLevel(logging.DEBUG if verbosity >= 2 else logging.INFO)
    try:  # PyMuPDF's messages in the log, printed above any bars: it writes them to the standard output it found
        import pymupdf  # when imported, past the bars' guard (Guarded), which print()s do reach
        pymupdf.set_messages(pylogging_logger=log, pylogging_level=logging.INFO)
    except (ImportError, AttributeError):
        pass

class Console(logging.StreamHandler):
    """Log lines on the terminal, printed above the bars, which are drawn again below them."""

    def emit(self, record):
        board = _board
        if board is None or board.stream is not self.stream:
            return super().emit(record)
        with board.lock:
            board.erase()
            super().emit(record)
            board.redraw()

@contextlib.contextmanager
def within(item):
    """Requests asked in the block belong to item (None: to none); it's settled after."""
    global _current
    outer, _current = _current, item
    try:
        yield item
    finally:
        _current = outer
        if item is not None:
            item.settle()

def working(item):
    """Requests asked from now on belong to item, until the next call (a reader's generator, between its yields;
    run_jobs clears it after each step). The item is settled when it's left."""
    global _current
    left, _current = _current, item
    if left is not None and left is not item:
        left.settle()

def carried(finish):
    """finish, run within the item being worked on now (the dispatcher's wrapper for an answer's handler)."""
    item = _current
    if item is None:
        return finish

    def run(*args):
        with within(item):
            return finish(*args)
    return run

@contextlib.contextmanager
def handling(cached):
    """An answer's handler run (the dispatcher's): cached, whether the answer came from the cache (a fixture's too) or
    from another request for the same query, rather than from the model, as the status counts it (Progress.finish).
    Set for every answer, so a handler that waits on others (make_room) leaves each its own."""
    global _cached
    outer, _cached = _cached, cached
    try:
        yield
    finally:
        _cached = outer

class Item:
    """One thing a bar counts (a page): done once it's closed and none of its requests is waiting."""
    __slots__ = ("bar", "open", "closed", "done")

    def __init__(self, bar):
        self.bar, self.open, self.closed, self.done = bar, 0, False, False

    def close(self):
        self.closed = True
        self.settle()

    def settle(self):
        if self.closed and self.open <= 0 and not self.done:
            self.done = True
            self.bar.tick()

class Bar:
    """A count of what's known when it appears (a file's pages, the pairs to judge): its total never changes. keep:
    whether it stays on the screen once full (a source's does; a file's leaves)."""

    def __init__(self, progress, label, total, unit, keep=True):
        self.progress, self.label, self.total, self.unit, self.keep = progress, label, max(0, total), unit, keep
        self.done, self.started = 0, progress.clock()

    @property
    def full(self):
        return self.done >= self.total

    def item(self):
        return Item(self)

    def tick(self, n=1):
        self.done = min(self.total, self.done + n)
        self.progress.changed(now=self.full)

    def fill(self):
        """Every item done: the work it counts is (a file's job finished, whatever its requests' counts said)."""
        if not self.full:
            self.done = self.total
            self.progress.changed(now=True)

    def left(self, now):
        """Seconds left at its rate so far, or None."""
        if not self.done or self.full:
            return None
        return (now - self.started) / self.done * (self.total - self.done)

class Guarded:
    """A standard stream written to while bars are drawn on its terminal: the bars erased first, and drawn again below
    once a line ends (a print's text and its newline come apart)."""

    def __init__(self, stream, board):
        self._stream, self._board = stream, board

    def write(self, text):
        board = self._board
        with board.lock:
            board.erase()
            written = self._stream.write(text)
            self._stream.flush()
            board.held = not text.endswith("\n")
            if not board.held:
                board.redraw()
            return written

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)

class Board:
    """Lines kept at the bottom of a terminal, drawn again as they change (at most every tenth of a second) and below
    each log line (Console) or anything else written there (Guarded). Each is cut to the terminal's width, so none
    wraps and the cursor knows where they are."""

    def __init__(self, stream, render, clock=time.monotonic, width=None):
        self.stream, self.render, self.clock, self.width = stream, render, clock, width
        self.lock = threading.RLock()
        self.drawn = 0
        self.last = None
        self.held = False  # a line written above isn't finished: the bars wait for its end
        self.guarded = {}

    def attach(self):
        """sys.stdout and sys.stderr guarded, where they're a terminal (Guarded)."""
        for name in ("stdout", "stderr"):
            stream = getattr(sys, name)
            if not isinstance(stream, Guarded) and getattr(stream, "isatty", lambda: False)():
                self.guarded[name] = stream
                setattr(sys, name, Guarded(stream, self))

    def detach(self):
        for name, stream in self.guarded.items():
            if isinstance(getattr(sys, name), Guarded):
                setattr(sys, name, stream)
        self.guarded = {}

    def columns(self):
        if self.width is not None:
            return self.width()
        try:
            return os.get_terminal_size(self.stream.fileno()).columns
        except (AttributeError, OSError, ValueError):
            return shutil.get_terminal_size().columns

    def show(self, now=False):
        with self.lock:
            if not self.held and (now or self.last is None or self.clock() - self.last >= EVERY):
                self.redraw()

    def redraw(self):
        with self.lock:
            width = max(10, self.columns() - 1)
            lines = [cut(line, width) for line in self.render(width)]
            self.stream.write(self._up() + "".join(line + "\n" for line in lines))
            self.stream.flush()
            self.drawn, self.last = len(lines), self.clock()

    def erase(self):
        with self.lock:
            if self.drawn:
                self.stream.write(self._up())
                self.stream.flush()
                self.drawn = 0

    def _up(self):
        """To the first line drawn, everything below it cleared."""
        return f"\r\x1b[{self.drawn}A\x1b[J" if self.drawn else "\r\x1b[J"

def cut(line, width):
    return line if len(line) <= width else line[:width - 1] + "…"

def bar_text(done, total, width):
    filled = round(width * done / total) if total else width
    return DONE * filled + LEFT * (width - filled)

def tokens(n):
    """A count of tokens, short: 9,500; 120k; 12M."""
    return f"{n:,}" if n < 10_000 else f"{n / 1000:.0f}k" if n < 10_000_000 else f"{n / 1_000_000:.0f}M"

def minutes(seconds):
    if seconds < 90:
        return f"about {max(1, round(seconds))} s left"
    if seconds < 5400:
        return f"about {round(seconds / 60)} min left"
    return f"about {seconds / 3600:.1f} h left"

class Progress:
    """One stage of a run: its requests counted as they're asked and answered (add, finish), and its bars."""

    def __init__(self, stage, client=None, bar=None, heartbeat=30.0, clock=time.monotonic, stream=None, width=None):
        self.stage, self.client, self.heartbeat, self.clock = stage, client, heartbeat, clock
        self.total = self.done = self.failed = self.cached = 0
        self.wrapped = False  # the status in two lines, once it didn't fit one (lines)
        self.started = self.last_beat = clock()
        self.tokens_at_start = self._tokens()
        self.bars = []
        stream = stream or sys.stderr
        if bar is None:
            bar = stream.isatty() and bool(log.handlers) and log.handlers[0].level <= logging.INFO
        self.board = Board(stream, self.lines, clock, width) if bar else None
        if self.board is not None:
            global _board
            _board = self.board
            self.board.attach()

    def _tokens(self):
        usage = getattr(self.client, "usage", None) or {}
        return sum(usage.values())

    def bar(self, label, total, unit, keep=True):
        """A bar of total units (its total fixed), shown from now."""
        made = Bar(self, label, total, unit, keep)
        self.bars.append(made)
        self.changed(now=True)
        return made

    def add(self, n=1):
        """n requests asked, belonging to the item being worked on."""
        self.total += n
        if _current is not None:
            _current.open += n
        self.changed()

    def finish(self, status="complete"):
        """A request answered (or failed), in its handler: its item's; from the cache, if the dispatcher says so."""
        self.done += 1
        self.failed += status == "failed"
        self.cached += _cached and status != "failed"
        if _current is not None:
            _current.open -= 1
        self.changed()

    def changed(self, now=False):
        if self.board is not None:
            self.board.show(now)
        elif self.clock() - self.last_beat >= self.heartbeat:
            self.last_beat = self.clock()
            log.info(self.line())

    def rates(self):
        minutes_ = max(self.clock() - self.started, 1e-6) / 60
        return {"tokens/min": int((self._tokens() - self.tokens_at_start) / minutes_)}

    def left(self):
        """Seconds left, by the slowest bar's rate, or None."""
        now = self.clock()
        known = [s for s in (b.left(now) for b in self.bars) if s is not None]
        return max(known) if known else None

    def shown(self):
        """The bars on the screen: those not full, and the full ones kept."""
        self.bars = [b for b in self.bars if b.keep or not b.full]
        return self.bars

    def lines(self, width):
        """The stage's bars, then its status line."""
        bars = self.shown()
        label = min(max((len(b.label) for b in bars), default=0), max(8, width // 3))
        counts = max((len(f"{b.total:,}") for b in bars), default=1)
        units = max((len(b.unit) for b in bars), default=0)
        room = width - 9 - label - 1 - 1 - (2 * counts + 1) - 1 - units
        cells = max(5, min(40, room))
        out = []
        for i, b in enumerate(bars):
            name = b.label if len(b.label) <= label else b.label[:label - 1] + "…"
            out.append(f"{self.stage if not i else '':<8} {name:<{label}} {bar_text(b.done, b.total, cells)} "
                       f"{b.done:>{counts},}/{b.total:<{counts},} {b.unit}".rstrip())
        status = self.status()
        if 9 + len(" · ".join(status)) > width:  # the counts on one line, the rates on the next: none cut off, and
            self.wrapped = True                    # kept so for the stage, so the bars don't jump as numbers change
        out += [" " * 9 + " · ".join(part) for part in ([status[:1], status[1:]] if self.wrapped else [status])]
        return out

    def requests(self):
        """The requests answered (those from the cache among them), waiting and failed."""
        cached = f" ({self.cached:,} from cache)" if self.cached else ""
        return (f"{self.done:,} answered{cached}, {self.total - self.done:,} waiting"
                + (f", {self.failed:,} failed" if self.failed else ""))

    def status(self):
        """The status's parts: the requests (counts, with no total: theirs grows as answers ask more); tokens a minute;
        cost; time left."""
        parts = [self.requests(), f"{tokens(self.rates()['tokens/min'])} tokens/min"]
        cost = getattr(self.client, "cost", 0) or 0
        if cost:
            parts.append(f"${cost:.2f}")
        left = self.left()
        if left is not None:
            parts.append(minutes(left))
        return parts

    def line(self):
        """The heartbeat line: the bars' counts, then the status."""
        bars = ", ".join(f"{b.label} {b.done:,}/{b.total:,} {b.unit}" for b in self.bars if not b.full)
        return f"{self.stage}: " + (bars + "; " if bars else "") + "requests " + ", ".join(self.status())

    def close(self):
        global _board
        if self.board is not None:
            self.board.erase()
            self.board.detach()
            if _board is self.board:
                _board = None
            self.board = None
        cached = f" ({self.cached:,} from cache)" if self.cached else ""
        failed = f", {self.failed:,} failed" if self.failed else ""
        log.info(f"{self.stage}: {self.done:,} requests answered{cached}{failed} in {self.clock() - self.started:.0f}s")

class NoBar:
    """A bar counting nothing (NoProgress's)."""
    total = done = 0
    full = True

    def item(self):
        return Item(self)

    def tick(self, n=1): pass
    def fill(self): pass

class NoProgress:
    def add(self, n=1): pass
    def finish(self, status="complete"): pass
    def close(self): pass
    def bar(self, label, total, unit, keep=True): return NoBar()
