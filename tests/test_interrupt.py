"""Ctrl+C ends a run cleanly, saying how to resume, and the run resumes where it was (cli.interrupted). The owner,
2026-10-21: "these processes can run a long time and resume cleanly. But, currently, ctrl+c just leaves a mess of
exception info in the terminal. Please capture it and exit cleanly, with a short message about how to resume."

Each runs the command in its own process, as a user does: Ctrl+C is a signal to the terminal's foreground process
group."""
import stubs  # noqa: F401 (the environment: a user config naming a model)
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import pyte

from semantic_pdf_diff import checkup, interrupts
from semantic_pdf_diff.settings import Settings
from stubs import Recorder, chat_answer, prompt_of, request_body, serving, source_data, summed, text_pdf

PAGES = 30
MESSAGE = 'Interrupted: rerun the same command to resume; finished work is kept.'

@contextlib.contextmanager
def endpoint(interrupt_at):
    """A stub endpoint answering a claim for each page's power in kW, equivalence for comparisons. Once interrupt_at
    requests have come, it sends Ctrl+C's signal to the process group in state['group'] (once: at the first request
    from interrupt_at on with the group known, or by run() as it learns the group, if the requests came first), and
    holds every later request unanswered until the block ends (or state['release'] is set): requests in flight the
    run mustn't wait for. (Sent only at request interrupt_at exactly, a run whose group the test hadn't yet set by then
    would never be interrupted. The timeouts under the full suite's load, 2026-10-29, 10-30 and 11-09, were blamed on
    that; the 11-09 log showed the run's Ctrl+C swallowed by PyMuPDF's find_tables, the product's bug: interrupts.)"""
    state = {'requests': 0, 'group': None, 'release': threading.Event(), 'lock': threading.Lock(), 'sent': False,
             'at': interrupt_at}

    def post(handler):
        prompt = prompt_of(request_body(handler)['messages'][1]['content'])
        if summed(handler, prompt):  # the run's ping, before anything else
            return
        with state['lock']:
            state['requests'] += 1
            n = state['requests']
            if n >= interrupt_at and state['group'] is not None and not state['sent']:
                state['sent'], state['sent_at'] = True, time.monotonic()
                os.killpg(state['group'], signal.SIGINT)
        if n >= interrupt_at:
            state['release'].wait(60)
        answer = {'claims': [], 'complete': True, 'issues': []}
        if 'Compare exactly' in prompt:
            answer = {'relation': 'equivalent', 'rationale': 'stub', 'confidence': .9, 'same_conditions': True}
        elif 'SOURCE DATA:\n' in prompt and 'kW' in source_data(prompt):
            value = source_data(prompt).split(' kW')[0].split()[-1]
            answer['claims'] = [{'entity': 'pump', 'attribute': 'rated power', 'value': value, 'unit': 'kW',
                                 'kind': 'text', 'quote': f'{value} kW', 'confidence': .9}]
        with contextlib.suppress(OSError):  # the run may have gone
            chat_answer(handler, answer)
    with serving(post, threaded=True) as url:
        try:
            yield url, state
        finally:
            state['release'].set()

def run(root, url, store, cache, on_terminal=True, group=None):
    """(exit code, seconds taken, the screen's rows, or the output without a terminal) for a compare run in its own
    process; group: the state whose 'group' is set to its process group, for the endpoint's Ctrl+C."""
    import pty
    import struct
    import termios
    from fcntl import ioctl
    checkup._kept(checkup.memory_of(cache / 'answers.sqlite'),  # the stub's models remembered as checked
                  {k: {'at': 'then'} for k in checkup.keys(Settings(base_url=url, model='gemma-4')).values()})
    command = [sys.executable, '-m', 'semantic_pdf_diff', 'compare', str(root / 'a.pdf'), str(root / 'b.pdf'),
               '--store', str(store), '--base-url', url, '--no-situate', '--log-file', str(store) + '.log']
    env = {**os.environ, 'SEMANTIC_PDF_DIFF_CACHE': str(cache)}
    written = []
    if on_terminal:
        master, slave = pty.openpty()
        ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 160, 0, 0))
        reader = threading.Thread(target=read, args=(master, written))
        reader.start()
        out = slave
    else:
        out = subprocess.PIPE
    started = time.monotonic()
    process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                               start_new_session=True)  # its own process group, as a terminal's foreground job
    if group is not None:
        with group['lock']:  # the endpoint may have had its requests before it knew whom to interrupt
            group['group'] = process.pid
            if group['requests'] >= group['at'] and not group['sent']:
                group['sent'], group['sent_at'] = True, time.monotonic()
                os.killpg(process.pid, signal.SIGINT)
    try:
        if on_terminal:
            code = process.wait(timeout=120)
        else:
            written.append(process.communicate(timeout=120)[0])
            code = process.returncode
    except subprocess.TimeoutExpired as e:  # what it said, and its log, kept for the failure (it timed out twice
        # beside other work, 2026-10-29 and 30, and passed alone)
        process.kill()
        said = b''.join(written).decode(errors='replace') + (e.output or b'').decode(errors='replace')
        log = Path(str(store) + '.log')
        raise AssertionError(f"the run didn't end within 120 s; it said: {said[-1500:]}\nits log: "
                             + (log.read_text()[-1500:] if log.exists() else "none")) from None
    finally:
        if process.poll() is None:
            process.kill()
        if on_terminal:
            os.close(slave)
            reader.join(10)
            os.close(master)
    took = time.monotonic() - started
    if group is not None and group['sent']:
        group['ended'] = time.monotonic()
    text = b''.join(written).decode(errors='replace')
    if not on_terminal:
        return code, took, text.splitlines()
    screen = pyte.Screen(160, 30)
    pyte.Stream(screen).feed(text)
    return code, took, [row.rstrip() for row in screen.display if row.strip()]

def read(master, written):
    while True:
        try:
            chunk = os.read(master, 65536)
        except OSError:  # the other end closed
            return
        if not chunk:
            return
        written.append(chunk)

def answered(rows):
    """{stage: (requests answered, from the cache)} as each stage's closing line says."""
    import re
    found = (re.match(r'^(\w+): ([\d,]+) requests answered(?: \(([\d,]+) from cache\))?', r) for r in rows)
    return {m[1]: (int(m[2].replace(',', '')), int((m[3] or '0').replace(',', ''))) for m in found if m}

def claims(store):
    """The claims a store's evidence.json holds, as (value, page) pairs, and its coverage's statuses."""
    data = json.loads((store / 'evidence.json').read_text())
    return (sorted((e['value'], e['locator']['page']) for e in data['evidence']),
            sorted(r['status'] for r in data['coverage']))

class Interrupted(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for name, power in (('a.pdf', 10), ('b.pdf', 50)):
            text_pdf(self.root / name, [f'Pump {k} rated power {power + k} kW' for k in range(PAGES)])

    def test_ctrl_c_ends_a_run_at_once_and_it_resumes_where_it_was(self):
        store, cache = self.root / 'out', self.root / 'cache'
        with endpoint(interrupt_at=12) as (url, state):
            code, took, rows = run(self.root, url, store, cache, group=state)
            self.assertEqual(code, 130, rows)
            # the requests held unanswered weren't waited for: timed from Ctrl+C (from the start, a slow start under
            # the full suite's load counted: 98% busy, 2026-11-09)
            self.assertLess(state['ended'] - state['sent_at'], 20)
            self.assertEqual(rows[-1], MESSAGE)
            self.assertFalse([r for r in rows if 'Traceback' in r or 'KeyboardInterrupt' in r], rows)
            self.assertFalse([r for r in rows if '█' in r or '░' in r or ' queued' in r], rows)  # no bars left
            self.assertIn(MESSAGE, Path(str(store) + '.log').read_text())
            state['release'].set()
            before = state['requests']
            code, took, rows = run(self.root, url, store, cache)  # resumed
            self.assertIn(code, (0, 2), rows)
            resumed, sent = answered(rows), state['requests'] - before
            code, took, rows = run(self.root, url, self.root / 'straight', self.root / 'cache-2')  # never interrupted
            straight = answered(rows)
        self.assertGreater(resumed['extract'][1], 0)  # some answered before Ctrl+C, kept
        self.assertEqual(sent, sum(n - cached for n, cached in resumed.values()))  # only the rest asked
        self.assertEqual({stage: n for stage, (n, _) in resumed.items()}, {stage: n for stage, (n, _) in
                                                                           straight.items()})
        self.assertEqual(claims(store), claims(self.root / 'straight'))

    def test_without_a_terminal_too(self):
        with endpoint(interrupt_at=5) as (url, state):
            code, took, lines = run(self.root, url, self.root / 'out', self.root / 'cache', on_terminal=False,
                                    group=state)
        self.assertEqual(code, 130, lines)
        self.assertEqual(lines[-1], MESSAGE)
        self.assertFalse([r for r in lines if 'Traceback' in r], lines)

class FromInterrupt(unittest.TestCase):
    def test_an_interrupt_coming_out_of_a_c_extension_as_system_error_is_the_interrupt(self):
        from semantic_pdf_diff.cli import from_interrupt

        def c_call():  # as PyMuPDF's wrapper raises it: the interrupt the cause, twice over
            try:
                raise KeyboardInterrupt
            except KeyboardInterrupt as e:
                try:
                    raise SystemError("returned a result with an exception set") from e
                except SystemError as inner:
                    raise SystemError("returned a result with an exception set") from inner
        with self.assertRaises(SystemError) as raised:
            c_call()
        self.assertTrue(from_interrupt(raised.exception))
        self.assertFalse(from_interrupt(SystemError("a bug of its own")))

    def test_a_lock_left_untaken_as_the_interrupt_came_is_the_interrupt(self):
        # Ctrl+C while a wait takes its lock back leaves the lock released, and leaving its block raises RuntimeError
        # in the interrupt's place (the commit gate, 2026-11-03: "Error: release unlocked lock", exit 1)
        from semantic_pdf_diff.pipeline import attempt

        def waiting():
            try:
                raise KeyboardInterrupt
            except KeyboardInterrupt:
                raise RuntimeError("release unlocked lock")

        def failing():
            raise RuntimeError("a bug of its own")
        with self.assertRaises(KeyboardInterrupt):
            attempt(waiting)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(attempt(failing), 1)
        self.assertEqual(err.getvalue(), "Error: a bug of its own\n")

class Swallowed(unittest.TestCase):
    """Ctrl+C during a call that swallows it: PyMuPDF's find_tables catches every Exception and returns None (the
    commit gate, 2026-11-09: the run went on, test_interrupt timing out)."""
    def tearDown(self):
        interrupts._arrived.clear()

    def test_ctrl_c_during_table_detection_ends_the_run_not_the_page_tables(self):
        from unittest.mock import patch

        import pymupdf

        from semantic_pdf_diff.jobs import extract_pdf

        def swallowing(page, *a, **k):  # as find_tables does: the interrupt marked, raised, caught, None returned
            interrupts.arrived()
            return None
        rows = []
        with tempfile.TemporaryDirectory() as d, patch.object(pymupdf.Page, 'find_tables', swallowing):
            path = Path(d) / 't.pdf'
            text_pdf(path, ['Pump rated power 10 kW', 'Fan rated power 2 kW'])
            with self.assertRaises(KeyboardInterrupt):
                rows = extract_pdf(path, 'sha256:' + 'a' * 64 + '.pdf', Path(d), Recorder())
        self.assertEqual(rows, [])

    def test_no_mark_no_interrupt(self):
        interrupts.checked()

    def test_swallowed_anywhere_the_run_ends_where_it_waits_next(self):
        from semantic_pdf_diff.dispatch import Dispatcher
        interrupts.arrived()
        with self.assertRaises(KeyboardInterrupt):
            Dispatcher(Recorder()).wait_one()

if __name__ == '__main__':
    unittest.main()
