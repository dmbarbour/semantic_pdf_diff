"""Ctrl+C ends a run cleanly, saying how to resume, and the run resumes where it was (cli.interrupted). The owner,
2026-10-21: "these processes can run a long time and resume cleanly. But, currently, ctrl+c just leaves a mess of
exception info in the terminal. Please capture it and exit cleanly, with a short message about how to resume."

Each runs the command in its own process, as a user does: Ctrl+C is a signal to the terminal's foreground process
group."""
import stubs  # noqa: F401 (the environment: a user config naming a model)
import contextlib
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

from semantic_pdf_diff import checkup
from semantic_pdf_diff.settings import Settings
from stubs import chat_answer, prompt_of, request_body, serving, source_data, text_pdf

PAGES = 30
MESSAGE = 'Interrupted: rerun the same command to resume; finished work is kept.'

@contextlib.contextmanager
def endpoint(interrupt_at):
    """A stub endpoint answering a claim for each page's power in kW, equivalence for comparisons. Once interrupt_at
    requests have come, it sends Ctrl+C's signal to the process group in state['group'], and holds every later request
    unanswered until the block ends (or state['release'] is set): requests in flight the run mustn't wait for."""
    state = {'requests': 0, 'group': None, 'release': threading.Event(), 'lock': threading.Lock()}

    def post(handler):
        prompt = prompt_of(request_body(handler)['messages'][1]['content'])
        with state['lock']:
            state['requests'] += 1
            n = state['requests']
        if n == interrupt_at and state['group'] is not None:
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
        group['group'] = process.pid
    try:
        if on_terminal:
            code = process.wait(timeout=120)
        else:
            written.append(process.communicate(timeout=120)[0])
            code = process.returncode
    finally:
        if process.poll() is None:
            process.kill()
        if on_terminal:
            os.close(slave)
            reader.join(10)
            os.close(master)
    took = time.monotonic() - started
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
            self.assertLess(took, 20)  # the requests held unanswered weren't waited for
            self.assertEqual(rows[-1], MESSAGE)
            self.assertFalse([r for r in rows if 'Traceback' in r or 'KeyboardInterrupt' in r], rows)
            self.assertFalse([r for r in rows if '█' in r or '░' in r or ' waiting' in r], rows)  # no bars left
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

if __name__ == '__main__':
    unittest.main()
