"""Ctrl+C, where a library swallows it: cli.first_interrupt marks that it came (arrived), and a run checks the mark
where a call that may have swallowed it returns (checked). Raised where Python can't raise it (a weakref's callback, a
__del__, during garbage collection), it isn't printed (unraisable): marked, the run ends where it next checks.

PyMuPDF's find_tables catches every Exception and returns None, printing "find_tables: exception occurred"; the
KeyboardInterrupt raised while its C calls run comes out of them as SystemError, so a Ctrl+C during table detection
was taken for a detection failure and the run went on (the commit gate, 2026-11-09: test_interrupt's run didn't end
within 120 s, its log holding that line)."""
import sys
import threading

_arrived = threading.Event()

def arrived():
    """Ctrl+C came (cli.first_interrupt marks it as it raises the interrupt)."""
    _arrived.set()

def checked():
    """KeyboardInterrupt, raised again where Ctrl+C came and was swallowed; nothing otherwise."""
    if _arrived.is_set():
        raise KeyboardInterrupt

def unraisable(hook):
    """sys.unraisablehook: Ctrl+C's interrupt, raised where Python can't raise it, not printed (the full suite,
    2026-11-09: "Exception ignored in: <function WeakSet.__init__.<locals>._remove", a traceback and
    "KeyboardInterrupt:" above the resume note); anything else as Python prints it."""
    if hook.exc_type is not None and issubclass(hook.exc_type, KeyboardInterrupt):
        return
    sys.__unraisablehook__(hook)
