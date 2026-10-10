"""Answers shared by test stub models, and round 0's settings for tests of pipeline mechanics."""
import contextlib
import importlib.util
import json
import os
import re
import unittest
from pathlib import Path

# Tests run with a clean environment: PDF_DIFF_* and OPENAI_* exported in a shell (the scripts say to source .env)
# would otherwise change what the CLI's Settings.from_env reads, and so what tests send and expect. Every test
# module imports this module.
for _name in [n for n in os.environ if n.startswith(("PDF_DIFF_", "OPENAI_"))]:
    del os.environ[_name]

# A quick run for iterating (QUICK=1 python -m unittest discover -s tests): the slowest tests skipped, about two thirds
# of the time (docs/plans/quick-wins-2026-10-02.md). Every commit is still checked by the full suite.
QUICK = bool(os.environ.get("QUICK"))

def slow(item):
    """Mark a test, or a class whose setup is the slow part, to be skipped in a quick run."""
    return unittest.skipIf(QUICK, "slow: skipped in a quick run (QUICK=1)")(item)

def needs_lab():
    """Skip a product test whose input the lab's generators build, where the lab isn't installed (a plain install of
    the diff tool; code review 2026-10-08, E18). Called before the lab's import."""
    if importlib.util.find_spec("semantic_pdf_diff_lab") is None:
        raise unittest.SkipTest("needs the lab (pip install -e lab)")

# The query settings before the improvement rounds' champion became the defaults (2026-09-28):
# tests of mechanics (refinement, tiling, prompt layout) that don't depend on the levers use these.
ROUND0 = json.loads((Path(__file__).resolve().parent.parent / 'benchmarks' / 'round0.json').read_text())

def situating_answer(prompt):
    """A situating answer derived from the prompt, or None if it isn't a situating request."""
    if 'Situate one figure' in prompt:
        found = re.search(r'^(?:Caption|Title): (.*)$', prompt, re.MULTILINE)
        name = found.group(1) if found else 'unlabelled'
        answer = {'about': f'stub figure: {name[:40]}', 'role': '', 'keywords': ['stub']}
        printed = re.search(r'PRINTED LABEL (\S+ \S+)', prompt)  # lets tests plant a label only the "image" shows
        if printed:
            answer['label'] = printed.group(1)
        return answer
    if 'Describe one section' in prompt:
        heading = prompt.split('Heading path: ', 1)[1].split('\n', 1)[0]
        return {'about': f'stub section: {heading}', 'type': 'other', 'density': 'low', 'keywords': ['stub']}
    return None

# --- shared fakes (code review 2026-10-08, E10: seven recorders, six HTTP stubs, a builder per file) ---------------

def source_data(prompt):
    """What an extraction request reads: its text after "SOURCE DATA:"."""
    return prompt.split('SOURCE DATA:\n', 1)[1]

def stock_answer(prompt, schema):
    """The answer a fake gives a query its test doesn't answer itself, or None: comparisons equivalent, situating
    from the prompt (situating_answer), a table's rules query each row read by itself, a two-column block a table."""
    from semantic_pdf_diff.models import Judgment
    if schema is Judgment:
        return Judgment(relation='equivalent', rationale='fixture', confidence=.9, same_conditions=True)
    if situating_answer(prompt):
        return schema.model_validate(situating_answer(prompt))
    if schema.__name__ == 'Rules':  # a table's rules query: each row read by itself, as these tests read tables
        return schema(reading='rows')
    if schema.__name__ == 'Check':  # a block of two columns: a table, as these tests read it (B5)
        return schema(reading='table')
    return None

class Recorder:
    """A fake client for pipeline tests: settings and the counters the pipeline reads. ask records the request
    (record), gives the stock answer where there is one, and leaves the rest to answer (no claims, by default)."""
    def __init__(self, **settings):
        from semantic_pdf_diff.models import Settings
        self.s = Settings(**settings)
        self.calls, self.cache_hits, self.usage = 0, 0, {}

    def ask(self, prompt, schema, images=(), key=None):
        self.record(prompt, schema, images, key)
        found = stock_answer(prompt, schema)
        return found if found is not None else self.answer(prompt, schema, images, key)

    def record(self, prompt, schema, images, key):
        pass

    def answer(self, prompt, schema, images, key):
        from semantic_pdf_diff.models import Extraction
        return Extraction(claims=[], complete=True)

def text_pdf(path, pages, width=300, height=None, at=(40, 40), toc=None, metadata=None):
    """A PDF of pages (square unless a height is given), each with its text (none for an empty one) at one point;
    written to path, or returned as bytes when path is None."""
    import pymupdf
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(width=width, height=height or width)
        if text:
            page.insert_text(at, text)
    if toc:
        doc.set_toc(toc)
    if metadata:
        doc.set_metadata(metadata)
    if path is None:
        data = doc.tobytes()
        doc.close()
        return data
    doc.save(path)
    doc.close()
    return path

def request_body(handler):
    """A stub server's request, parsed."""
    return json.loads(handler.rfile.read(int(handler.headers['Content-Length'])))

def chat_answer(handler, content, finish='stop', usage=None):
    """A chat completion's reply holding content (a string, or JSON-encoded), with usage if given."""
    handler.send_response(200)
    handler.end_headers()
    text = content if isinstance(content, str) else json.dumps(content)
    handler.wfile.write(json.dumps({'choices': [{'finish_reason': finish, 'message': {'content': text}}],
                                    **({'usage': usage} if usage is not None else {})}).encode())

@contextlib.contextmanager
def serving(post, threaded=False):
    """A local endpoint for the block, on a free port: post(handler) answers each POST (a BaseHTTPRequestHandler,
    its headers, rfile and send_* methods). Yields the base URL, ending in /v1."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            post(self)
    server = (ThreadingHTTPServer if threaded else HTTPServer)(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
