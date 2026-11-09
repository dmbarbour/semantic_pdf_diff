"""Ctrl+C, where a library swallows it: cli.first_interrupt marks that it came (arrived), and a run checks the mark
where a call that may have swallowed it returns (checked).

PyMuPDF's find_tables catches every Exception and returns None, printing "find_tables: exception occurred"; the
KeyboardInterrupt raised while its C calls run comes out of them as SystemError, so a Ctrl+C during table detection
was taken for a detection failure and the run went on (the commit gate, 2026-11-09: test_interrupt's run didn't end
within 120 s, its log holding that line)."""
import threading

_arrived = threading.Event()

def arrived():
    """Ctrl+C came (cli.first_interrupt marks it as it raises the interrupt)."""
    _arrived.set()

def checked():
    """KeyboardInterrupt, raised again where Ctrl+C came and was swallowed; nothing otherwise."""
    if _arrived.is_set():
        raise KeyboardInterrupt
