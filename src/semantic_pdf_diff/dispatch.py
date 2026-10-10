"""Run model requests on worker threads; everything else stays on the calling thread.

Workers only send HTTP requests. Preparing requests (reading crops), cache lookups,
saving responses and handling results (which may queue refinement requests) happen
on the calling thread, which owns the PDF document and the store connection.
"""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from .failures import ModelFailure

class Dispatcher:
    def __init__(self, client, workers=None):
        self.client = client
        self.workers = workers or getattr(getattr(client, "s", None), "concurrency", 1)
        # Clients without the prepare/send split (e.g. simple test doubles) run inline.
        self.split = all(hasattr(client, m) for m in ("prepare", "cached", "send", "save"))
        self.pool = ThreadPoolExecutor(self.workers, thread_name_prefix="model") if self.workers > 1 and self.split else None
        self.inflight = {}
        # Queries asked again while the same query is in flight (the same page in two documents):
        # they wait for its answer rather than being sent (and paid for) twice.
        self.waiting = {}

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
            return
        same = self._same(request)
        if same is not None and same in self.waiting:
            self.waiting[same].append(finish)
            return
        if same is not None:
            self.waiting[same] = []
        if self.pool is None:
            self._complete(request, finish, self.client.send, request)
        else:
            self.inflight[self.pool.submit(self.client.send, request)] = (request, finish)

    def _same(self, request):
        """What makes two requests the same ask: the query, and which answer to it (the replay's sample: the A/A
        control's fresh regions want another). Code review 2026-10-08: this read a `Client._sample` long gone, so
        every merged query was sample 0."""
        query = getattr(request, "query", None)
        replay = getattr(self.client, "replay", None)
        return (query, replay.sample(request.key) if replay else 0) if query else None

    def _complete(self, request, finish, call, *args):
        waiting = self.waiting.pop(self._same(request), [])
        try:
            value = call(*args)
        except ModelFailure as e:
            if hasattr(self.client, "failed"):
                self.client.failed(request, e)
            for done in [finish] + waiting:
                done(None, e)
            return
        self.client.save(request, value)
        for done in [finish] + waiting:
            done(value, None)

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
