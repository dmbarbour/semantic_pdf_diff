"""Progress: stacked bars of fixed size, a status line, log lines above them
(docs/plans/progress-display-2026-10-20.md), read as a terminal shows them: pyte, a terminal emulator, takes what was
written and gives the screen's rows. The owner, 2026-10-20: "How are you testing progress bar rendering in any
case?"."""
import stubs
import contextlib
import io
import logging
import sys
import tempfile
import unittest
from pathlib import Path

import pyte

from semantic_pdf_diff import cli, progress as module
from semantic_pdf_diff.progress import Progress, carried, log, requests_log, setup_logging, within

sys.path.insert(0, str(Path(__file__).parent))
from test_sources import pdf_bytes  # noqa: E402
from test_store import model_server  # noqa: E402

class Terminal:
    """A terminal's screen (pyte's), written to as standard error is: a newline is a carriage return and a line feed,
    as a terminal's line discipline makes it."""

    def __init__(self, columns=80, lines=12):
        self.screen = pyte.Screen(columns, lines)
        self.stream = pyte.Stream(self.screen)
        self.columns = columns

    def write(self, text):
        self.stream.feed(text.replace("\n", "\r\n"))

    def flush(self):
        pass

    def isatty(self):
        return True

    def rows(self):
        """The screen's rows, down to the last holding anything."""
        rows = [row.rstrip() for row in self.screen.display]
        while rows and not rows[-1]:
            rows.pop()
        return rows

class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

def staged(terminal, clock=None, client=None):
    """A stage drawing on the terminal, its log lines too (setup_logging's Console, on that stream)."""
    setup_logging()
    log.handlers[0].setStream(terminal)
    return Progress('extract', client, bar=True, clock=clock or Clock(), stream=terminal,
                    width=lambda: terminal.columns)

class Bars(unittest.TestCase):
    def tearDown(self):
        module._board = None
        setup_logging()

    def test_bars_stack_each_of_a_fixed_total_with_the_status_below(self):
        term, clock = Terminal(), Clock()
        client = type('C', (), {'usage': {'prompt_tokens': 0, 'completion_tokens': 0}, 'cost': 0.42})()
        stage = staged(term, clock, client)
        pages = stage.bar('nrel-5mw.pdf', 561, 'pages')
        files = stage.bar('team-b', 3, 'files')
        stage.add(5)
        for _ in range(4):
            stage.finish()
        clock.now = 60.0
        client.usage['prompt_tokens'] = 120_000
        pages.tick(97)
        files.tick()
        stage.board.redraw()
        self.assertEqual(term.rows(), [
            "extract  nrel-5mw.pdf ███████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  97/561 pages",
            "         team-b       █████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░   1/3   files",
            "         4 answered, 0 in flight, 1 queued",  # too long for one line at 80 columns: two
            "         120k tokens/min · $0.42 · about 5 min left"])  # the slowest bar's rate

    def test_log_lines_print_above_the_bars(self):
        term = Terminal()
        stage = staged(term)
        stage.bar('a.pdf', 10, 'pages').tick(3)
        stage.board.redraw()
        log.info("Scanned team-a: 2 files")
        log.warning("Situating a.pdf: 1 request(s) failed")
        rows = term.rows()
        self.assertEqual(rows[:2], ["Scanned team-a: 2 files", "Situating a.pdf: 1 request(s) failed"])
        self.assertTrue(rows[2].startswith("extract  a.pdf ███"), rows)
        self.assertEqual(len(rows), 4)  # the bar and its status, once: no copy left above

    def test_what_else_is_printed_there_prints_above_too(self):
        term = Terminal()
        with contextlib.redirect_stdout(term), contextlib.redirect_stderr(term):  # both the terminal, as a user's are
            stage = staged(term)
            stage.bar('a.pdf', 10, 'pages').tick(3)
            stage.board.redraw()
            print('Consider using a package:', end=' ')  # a print's text and its newline come apart
            print('a library\'s notice')
            sys.stderr.write('a warning, written to stderr\n')
            rows = term.rows()
            stage.close()
            self.assertIs(sys.stdout, term)  # put back
        self.assertEqual(rows[:2], ["Consider using a package: a library's notice", 'a warning, written to stderr'])
        self.assertTrue(rows[2].startswith('extract  a.pdf ███'), rows)
        self.assertEqual(len(rows), 4)

    def test_a_finished_file_leaves_and_bars_finish_in_any_order(self):
        term = Terminal()
        stage = staged(term)
        source = stage.bar('team-a', 2, 'files')
        first = stage.bar('a.pdf', 2, 'pages', keep=False)
        second = stage.bar('b.pdf', 3, 'pages', keep=False)
        second.fill()
        source.tick()
        stage.board.redraw()
        labels = lambda: [row[9:].split()[0] for row in term.rows()[:-1]]  # noqa: E731 (past the stage's column)
        self.assertEqual(labels(), ['team-a', 'a.pdf'])
        first.tick(2)
        source.tick()
        stage.board.redraw()
        self.assertEqual(labels(), ['team-a'])
        self.assertIn('2/2 files', term.rows()[0])

    def test_lines_are_cut_to_a_narrow_terminal(self):
        term = Terminal(columns=40)
        stage = staged(term)
        stage.bar('a-file-with-a-long-name-indeed.pdf', 561, 'pages').tick(200)
        stage.add(3000)
        with module.handling(True):
            for _ in range(1000):
                stage.finish()
        stage.board.redraw()
        rows = term.rows()
        self.assertEqual(len(rows), 3)  # the bar, the counts, the rates: nothing wrapped onto another row
        self.assertTrue(all(len(r) <= 39 for r in rows), rows)
        self.assertIn('200/561', rows[0])
        self.assertTrue(rows[1].endswith('…'))
        self.assertEqual(rows[2], '         0 tokens/min · about 1 s left')

    def test_a_status_too_long_for_a_line_takes_two_and_keeps_them(self):
        term = Terminal(columns=100)
        client = type('C', (), {'usage': {'prompt_tokens': 0, 'completion_tokens': 0}, 'cost': 1.23})()
        stage = staged(term, client=client)
        stage.bar('a.pdf', 561, 'pages').tick(97)
        stage.board.redraw()
        self.assertEqual(len(term.rows()), 2)  # it fits
        stage.add(12_000)
        for answer in range(11_790):
            with module.handling(answer < 11_000):
                stage.finish()
        stage.board.redraw()
        self.assertEqual(term.rows()[1:], ['         11,790 answered (11,000 from cache), 0 in flight, 210 queued',
                                           '         0 tokens/min · $1.23 · about 1 s left'])
        stage.add(-11_000)  # shorter again: still two lines, so the bars don't jump about
        stage.board.redraw()
        self.assertEqual(len(term.rows()), 3)

    def test_closing_leaves_the_summary_and_no_bars(self):
        term = Terminal()
        stage = staged(term)
        stage.bar('a.pdf', 2, 'pages').tick()
        stage.add(2)
        stage.finish()
        stage.finish('failed')
        stage.close()
        self.assertEqual(term.rows(), ["extract: 2 requests answered, 1 failed in 0s"])

class OnATerminal(unittest.TestCase):
    """The command run on a pseudo-terminal, as a user runs it: what the screen shows after."""

    def test_a_comparison_leaves_its_log_and_no_bars(self):
        import os
        import pty
        import struct
        import subprocess
        import termios
        import threading
        from fcntl import ioctl
        from semantic_pdf_diff import checkup
        from semantic_pdf_diff.settings import Settings
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cache = root / 'cache'  # its own, the stub's models remembered as passing their checks
            checkup._kept(checkup.memory_of(cache / 'answers.sqlite'),
                          {k: {'at': 'then'} for k in checkup.keys(Settings(base_url=url, model='gemma-4')).values()})
            for name, power in (('a.pdf', 10), ('b.pdf', 12)):
                (root / name).write_bytes(pdf_bytes(f'Pump rated power {power} kW'))
            master, slave = pty.openpty()
            ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 240, 0, 0))  # wide: log lines don't wrap
            written = []
            reader = threading.Thread(target=self.read, args=(master, written))
            reader.start()
            try:  # its own process: the environment stubs made (a model named), no stand-ins
                code = subprocess.run([sys.executable, '-m', 'semantic_pdf_diff', 'compare', str(root / 'a.pdf'),
                                       str(root / 'b.pdf'), '--store', str(root / 'out'), '--base-url', url,
                                       '--no-situate', '--log-file', str(root / 'run.log')],
                                      env={**os.environ, 'SEMANTIC_PDF_DIFF_CACHE': str(cache)},
                                      stdin=subprocess.DEVNULL, stdout=slave, stderr=slave, timeout=120).returncode
            finally:
                os.close(slave)
                reader.join(10)
                os.close(master)
            logged = [line.split(': ', 1)[1] for line in (root / 'run.log').read_text().splitlines()
                      if ' INFO ' in line or ' WARNING ' in line]
        self.assertIn(code, (0, 2))
        raw = b''.join(written).decode()
        self.assertIn('answered, ', raw)  # the status was drawn...
        screen = pyte.Screen(240, 40)
        pyte.Stream(screen).feed(raw)
        rows = [row.rstrip() for row in screen.display if row.strip()]
        self.assertFalse([r for r in rows if '█' in r or '░' in r or 'answered, ' in r and ' · ' in r], rows)
        shown = [r for r in rows if not r.startswith(('Report:', 'Consider using'))]  # stdout's, not the log's
        self.assertEqual(shown, logged)  # ...and the log reads as it was written, every line whole, once

    @staticmethod
    def read(master, written):
        import os
        while True:
            try:
                chunk = os.read(master, 65536)
            except OSError:  # the other end closed
                return
            if not chunk:
                return
            written.append(chunk)

class Extraction(unittest.TestCase):
    """A comparison's extraction: a bar of pages for each file read, of files for each source of more than one."""

    def test_each_file_its_pages_each_source_its_files(self):
        from unittest.mock import patch
        made, filled = [], []
        real_bar, real_fill = Progress.bar, module.Bar.fill

        def bar(self, label, total, unit, keep=True):
            made.append((self.stage, label, total, unit))
            return real_bar(self, label, total, unit, keep)

        def fill(self):
            filled.append((self.label, self.done, self.total))  # what its answers had counted
            real_fill(self)
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, \
                patch.object(Progress, 'bar', bar), patch.object(module.Bar, 'fill', fill):
            root = Path(d)
            (root / 'team-a').mkdir()
            stubs.text_pdf(root / 'team-a' / 'one.pdf', [f'Pump {k} rated power {k} kW' for k in range(3)])
            stubs.text_pdf(root / 'team-a' / 'two.pdf', ['Fan rated power 2 kW'])
            stubs.text_pdf(root / 'b.pdf', ['Pump 0 rated power 1 kW', 'Pump 1 rated power 2 kW'])
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                cli.main(['compare', str(root / 'team-a'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                          '--base-url', url, '--no-vision', '--no-situate'])
        self.assertEqual(sorted(m for m in made if m[0] == 'extract'), [
            ('extract', 'b.pdf', 2, 'pages'), ('extract', 'one.pdf', 3, 'pages'), ('extract', 'team-a', 2, 'files'),
            ('extract', 'two.pdf', 1, 'pages')])
        self.assertEqual(sorted(filled), [('b.pdf', 2, 2), ('one.pdf', 3, 3), ('two.pdf', 1, 1)])

    def test_situating_and_comparing_have_bars_full_when_they_close(self):
        from unittest.mock import patch
        closed, real_close = [], Progress.close

        def close(self):
            closed.extend((self.stage, b.label, b.unit, b.done, b.total) for b in self.bars)
            real_close(self)
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d, patch.object(Progress, 'close', close):
            root = Path(d)
            for name, power in (('a.pdf', 10), ('b.pdf', 12)):
                stubs.text_pdf(root / name, [f'Pump rated power {power} kW', 'Fan rated power 2 kW'],
                               toc=[[1, 'Pumps', 1], [1, 'Fans', 2]])
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                cli.main(['compare', str(root / 'a.pdf'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                          '--base-url', url, '--no-vision'])
        situated = {(stage, label, unit) for stage, label, unit, done, total in closed if stage == 'situate'}
        self.assertEqual(situated, {('situate', 'PDFs', 'PDFs'), ('situate', 'a.pdf', 'sections'),
                                    ('situate', 'b.pdf', 'sections')})
        judged = [c for c in closed if c[0] == 'compare' and c[1] == 'judge']
        self.assertEqual(len(judged), 1)
        self.assertGreater(judged[0][4], 0)
        self.assertEqual([c for c in closed if c[3] != c[4]], [])  # every bar full at its stage's end

class Pages(unittest.TestCase):
    """A page is done once every request asked for it is answered, follow-ups included."""

    def test_a_follow_up_keeps_its_page_open(self):
        stage = Progress('extract', bar=False)
        pages = stage.bar('a.pdf', 2, 'pages')
        handlers = []

        def ask(then=None):  # as a task asks: counted, then its handler kept for its answer (as the dispatcher does)
            stage.add()
            handlers.append(carried(lambda: (stage.finish(), then and then())))

        first, second = pages.item(), pages.item()
        with within(first):
            ask(then=ask)  # its answer asks a follow-up (a refined half)
        first.close()
        with within(second):
            ask()
        second.close()
        self.assertEqual(pages.done, 0)
        handlers.pop(0)()  # page 1's answer: its follow-up is asked, so the page is still open
        self.assertEqual((pages.done, first.done), (0, False))
        handlers.pop(0)()  # page 2's
        self.assertEqual((pages.done, second.done), (1, True))
        handlers.pop(0)()  # the follow-up's: page 1 is done
        self.assertEqual((pages.done, first.done), (2, True))
        self.assertEqual((stage.total, stage.done), (3, 3))

    def test_a_page_with_no_request_is_done_once_closed(self):
        stage = Progress('extract', bar=False)
        pages = stage.bar('a.pdf', 1, 'pages')
        item = pages.item()
        with within(item):
            pass
        self.assertEqual(pages.done, 0)
        item.close()
        self.assertEqual(pages.done, 1)

class FromCache(unittest.TestCase):
    """The status counts the answers that came from the cache (the owner, 2026-10-21: "it would be convenient if we
    also mention how many were answered from cache, e.g. 1234 answered (1179 from cache) or similar")."""

    def setUp(self):
        setup_logging()
        self.addCleanup(setup_logging)

    def test_the_dispatcher_says_which_answers_were_cached(self):
        from types import SimpleNamespace
        from semantic_pdf_diff.dispatch import Dispatcher
        from semantic_pdf_diff.failures import ModelFailure

        class Client:  # a, b and the second ask of e are in its cache; c and d are asked; f fails
            s = SimpleNamespace(concurrency=1)
            known = {'a': 'cached a', 'b': 'cached b'}

            def prepare(self, prompt, schema, images, key):
                return SimpleNamespace(query=prompt, key=key, unrecorded=False, admitted=False)

            def cached(self, request):
                return self.known.get(request.query)

            def send(self, request):
                if request.query == 'f':
                    raise ModelFailure('HTTP 500')
                self.known[request.query] = 'asked ' + request.query
                return self.known[request.query]

            def save(self, request, value):
                pass
        stage = Progress('extract', None, bar=False, heartbeat=1e9)
        dispatch = Dispatcher(Client())

        def ask(query, then=()):
            stage.add()

            def finish(value, error):
                for follow_up in then:  # asked from its handler: the follow-up's own answer counted as its own
                    ask(follow_up)
                stage.finish('failed' if error else 'complete')
            dispatch.submit(query, None, (), None, finish)
        ask('a')
        ask('b', then=['c', 'f'])
        ask('d')
        ask('d')  # asked before: now in the cache
        dispatch.drain()
        self.assertEqual((stage.done, stage.cached, stage.failed), (6, 3, 1))
        self.assertEqual(stage.requests(), '6 answered (3 from cache), 0 in flight, 0 queued, 1 failed')
        with self.assertLogs('semantic_pdf_diff', level='INFO') as logs:
            stage.close()
        self.assertIn('extract: 6 requests answered (3 from cache), 1 failed in', logs.output[0])

    def test_a_run_asked_again_is_answered_from_the_cache(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, power in (('a.pdf', 10), ('b.pdf', 12)):
                (root / name).write_bytes(pdf_bytes(f'Pump rated power {power} kW'))
            said = []
            for again in ([], ['--reset']):  # everything read again, the cache kept (the store's, in tests)
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    cli.main(['compare', str(root / 'a.pdf'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                              '--base-url', url, '--no-situate', *again])
                said.append([line for line in err.getvalue().splitlines() if line.startswith('extract: ')])
        asked = said[0][0].split()[1]
        self.assertRegex(said[0][0], rf'^extract: {asked} requests answered in \d+s$')
        self.assertRegex(said[1][0], rf'^extract: {asked} requests answered \({asked} from cache\) in \d+s$')

class InFlight(unittest.TestCase):
    """The status's "in flight" is what the endpoint has open, never more than `concurrency`; "queued", what's asked
    and not yet sent (the owner, 2026-10-21: "I regularly seem to have "7 waiting" when I configure concurrency at 2,
    for example. My in-house setup has only a few servers for gemma-4, and I need to not be taking all of them")."""

    def test_a_comparison_has_at_most_concurrency_open_at_the_endpoint(self):
        import re
        import threading
        import time
        from unittest.mock import patch
        from stubs import chat_answer, prompt_of, request_body, serving, source_data, text_pdf
        state, lock, shown = {'open': 0, 'most': 0}, threading.Lock(), []

        def post(handler):
            prompt = prompt_of(request_body(handler)['messages'][1]['content'])
            with lock:
                state['open'] += 1
                state['most'] = max(state['most'], state['open'])
            time.sleep(0.05)
            with lock:
                state['open'] -= 1
            answer = {'claims': [], 'complete': True, 'issues': []}
            if 'Compare exactly' in prompt:
                answer = {'relation': 'equivalent', 'rationale': 'stub', 'confidence': .9, 'same_conditions': True}
            elif 'SOURCE DATA:\n' in prompt and 'kW' in source_data(prompt):
                value = source_data(prompt).split(' kW')[0].split()[-1]
                answer['claims'] = [{'entity': 'pump', 'attribute': 'rated power', 'value': value, 'unit': 'kW',
                                     'kind': 'text', 'quote': f'{value} kW', 'confidence': .9}]
            chat_answer(handler, answer)
        real = Progress.changed

        def changed(self, now=False):
            shown.append(self.requests())
            return real(self, now)
        with serving(post, threaded=True) as url, tempfile.TemporaryDirectory() as d, \
                stubs.user_settings({'model': 'gemma-4', 'concurrency': 2}), patch.object(Progress, 'changed', changed):
            root = Path(d)
            for name, power in (('a.pdf', 10), ('b.pdf', 50)):
                text_pdf(root / name, [f'Pump {k} rated power {power + k} kW' for k in range(12)])
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                cli.main(['compare', str(root / 'a.pdf'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                          '--base-url', url, '--no-situate'])
        counts = [tuple(map(int, re.search(r'(\d+) in flight, (\d+) queued', line).groups())) for line in shown]
        self.assertEqual(state['most'], 2)  # two at once, never more
        self.assertEqual(max(flying for flying, _ in counts), 2)
        self.assertGreater(max(queued for _, queued in counts), 0)  # what "waiting" counted besides

class Heartbeats(unittest.TestCase):
    def setUp(self):
        setup_logging()
        self.addCleanup(setup_logging)

    def test_heartbeat_lines_without_a_terminal(self):
        t = [0.0]
        client = type('C', (), {'usage': {'prompt_tokens': 0, 'completion_tokens': 0}})()
        stage = Progress('extract', client, bar=False, heartbeat=30, clock=lambda: t[0])
        with self.assertLogs('semantic_pdf_diff', level='INFO') as logs:
            pages = stage.bar('a.pdf', 4, 'pages')
            stage.add(4)
            stage.finish()
            stage.finish('failed')
            t[0] = 31
            client.usage['prompt_tokens'] = 3100
            pages.tick(2)  # past the heartbeat: said
            stage.close()
        self.assertEqual(len(logs.output), 2)
        # At the heartbeat: 2 of 4 pages in 31 s, so 31 s left; 3,100 tokens in 31 s.
        self.assertRegex(logs.output[0], r'extract: a\.pdf 2/4 pages; requests 2 answered, 0 in flight, 2 queued, '
                                         r'1 failed, (5,999|6,000) tokens/min, about 31 s left')
        self.assertIn('extract: 2 requests answered, 1 failed in 31s', logs.output[1])

class Verbosity(unittest.TestCase):
    def tearDown(self):
        setup_logging()

    def levels(self, **kw):
        setup_logging(**kw)
        return log.handlers[0].level, requests_log.getEffectiveLevel()

    def test_levels(self):
        self.assertEqual(self.levels(quiet=True)[0], logging.WARNING)
        self.assertEqual(self.levels(), (logging.INFO, logging.INFO))
        self.assertEqual(self.levels(verbosity=1), (logging.DEBUG, logging.INFO))
        self.assertEqual(self.levels(verbosity=2), (logging.DEBUG, logging.DEBUG))

    def test_cli_log_file_and_request_lines(self):
        with model_server() as (url, state), tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, power in (('a.pdf', 10), ('b.pdf', 12)):
                (root / name).write_bytes(pdf_bytes(f'Pump rated power {power} kW'))
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                cli.main(['compare', str(root / 'a.pdf'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                          '--base-url', url, '--no-vision', '-vv', '--log-file', str(root / 'run.log')])
            logged = (root / 'run.log').read_text()
            self.assertIn('Extraction', logged)
            self.assertIn('ok in', logged)
            self.assertIn('extract:', logged)
            with contextlib.redirect_stderr(io.StringIO()) as quiet, contextlib.redirect_stdout(io.StringIO()):
                cli.main(['compare', str(root / 'a.pdf'), str(root / 'b.pdf'), '--store', str(root / 'out'),
                          '--base-url', url, '--no-vision', '-q'])
            self.assertEqual(quiet.getvalue(), '')

if __name__ == '__main__':
    unittest.main()
