"""Run model requests on worker threads; everything else stays on the calling thread.

Workers only send HTTP requests. Preparing requests (reading crops), cache lookups,
saving responses and handling results (which may queue refinement requests) happen
on the calling thread, which owns the PDF document and the store connection.
"""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from .llm import ModelFailure

class Dispatcher:
    def __init__(self, client, workers=None):
        self.client = client
        self.workers = workers or getattr(getattr(client, "s", None), "concurrency", 1)
        # Clients without the prepare/send split (e.g. simple test doubles) run inline.
        self.split = all(hasattr(client, m) for m in ("prepare", "cached", "send", "save"))
        self.pool = ThreadPoolExecutor(self.workers, thread_name_prefix="model") if self.workers > 1 and self.split else None
        self.inflight = {}

    def submit(self, prompt, schema, images, key, finish):
        """Ask for `schema`; finish(value, error) is called on this thread, now or later."""
        if not self.split:
            try:
                value = self.client.ask(prompt, schema, images, key=key)
            except ModelFailure as e:
                finish(None, e)
                return
            finish(value, None)
            return
        try:
            request = self.client.prepare(prompt, schema, images, key)
            value = self.client.cached(request)
        except ModelFailure as e:
            finish(None, e)
            return
        if value is not None:
            finish(value, None)
        elif self.pool is None:
            self._complete(request, finish, self.client.send, request)
        else:
            self.inflight[self.pool.submit(self.client.send, request)] = (request, finish)

    def _complete(self, request, finish, call, *args):
        try:
            value = call(*args)
        except ModelFailure as e:
            finish(None, e)
            return
        self.client.save(request, value)
        finish(value, None)

    def pending(self):
        return len(self.inflight)

    def wait_one(self):
        """Handle at least one finished request (results may queue more)."""
        done, _ = wait(list(self.inflight), return_when=FIRST_COMPLETED)
        for future in done:
            request, finish = self.inflight.pop(future)
            self._complete(request, finish, future.result)

    def drain(self):
        while self.inflight:
            self.wait_one()

    def close(self, cancel=False):
        if self.pool is not None:
            self.pool.shutdown(wait=not cancel, cancel_futures=cancel)
            self.pool = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *rest):
        self.close(cancel=exc_type is not None)
