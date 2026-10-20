"""Run model requests on worker threads; everything else stays on the calling thread.

Workers only send HTTP requests. Preparing requests (reading crops), cache lookups,
saving responses and handling results (which may queue refinement requests) happen
on the calling thread, which owns the PDF document and the store connection.

A cached or replayed answer is handled at once, so a replay sees answers in the order they
were asked, while a live run sees them as they arrive. With SEMANTIC_PDF_DIFF_ANSWER_ORDER set to a
seed (tests only), cached and replayed answers (and replayed failures) are held and handled in
an order drawn from it instead, as a live run's might be: what a run writes must not depend on that order (the
determinism review, 2026-10-12).
"""
import copy
import os
import random
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from .failures import ModelFailure

ANSWER_ORDER = "SEMANTIC_PDF_DIFF_ANSWER_ORDER"

class Dispatcher:
    def __init__(self, client, workers=None):
        self.client = client
        self.workers = workers or getattr(getattr(client, "s", None), "concurrency", 1)
        # Clients without the prepare/send split (e.g. simple test doubles) run inline.
        self.split = all(hasattr(client, m) for m in ("prepare", "cached", "send", "save"))
        self.pool = (ThreadPoolExecutor(self.workers, thread_name_prefix="model") if self.workers > 1 and self.split
                     else None)
        self.inflight = {}
        # Queries asked again while the same query is in flight (the same page in two documents):
        # they wait for its answer rather than being sent (and paid for) twice.
        self.waiting = {}
        # Each query's outcome, its answer or its failure: asked again later in the run, it gets the same as one
        # asked while it was in flight (the determinism review, D5)
        self.outcomes = {}
        seed = os.environ.get(ANSWER_ORDER)
        self.shuffle = random.Random(seed) if seed and self.split else None
        self.held = []  # with a shuffle: answers at hand, handled in its order

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
        except ModelFailure as e:  # one preparing
            self._failed_early(finish, e)
            return
        self.submit_request(request, finish)

    def _failed_early(self, finish, error):
        if self.shuffle is not None:
            self.held.append((None, finish, None, error))
        else:
            finish(None, error)

    def submit_request(self, request, finish):
        """A prepared request (another endpoint's too: a reranker's, rerank.request) looked up, then sent if it must
        be; finish(value, error) is called on this thread, now or later."""
        try:
            value = self.client.cached(request)
        except ModelFailure as e:  # a recorded failure
            self._failed_early(finish, e)
            return
        if value is not None and self.shuffle is None:
            finish(value, None)
            return
        same = self._same(request)
        if value is None and same in self.outcomes:  # its lookup counted it already
            value, error = self.outcomes[same]
            finish(None, error) if error is not None else finish(copy.deepcopy(value), None)
            return
        if same is not None and same in self.waiting:
            self.waiting[same].append((request, finish))
            return
        if hasattr(self.client, "admit"):  # counted under the caps as asked, here, not on a worker (review, D6)
            try:
                self.client.admit(request)
            except ModelFailure as e:
                if same is not None:
                    self.outcomes[same] = (None, e)
                finish(None, e)
                return
        if same is not None:
            self.waiting[same] = []
        if self.shuffle is not None and (value is not None or getattr(request, "unrecorded", False)):
            self.held.append((request, finish, value, None))
        elif self.pool is None:
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

    def _noted(self, request):
        """A request answered by another's query: noted as a cache hit's is (its recipe, in a fixture)."""
        if hasattr(self.client, "noted"):
            self.client.noted(request)

    def _complete(self, request, finish, call, *args, cached=False):
        same = self._same(request)
        waiting = self.waiting.pop(same, [])
        try:
            value = call(*args)
        except ModelFailure as e:
            if hasattr(self.client, "failed"):
                self.client.failed(request, e)
            if same is not None:
                self.outcomes[same] = (None, e)
            for done in [finish] + [done for _, done in waiting]:
                done(None, e)
            return
        if not cached:
            self.client.save(request, value)
        if same is not None:
            self.outcomes[same] = (copy.deepcopy(value), None)
        finish(value, None)
        for other, done in waiting:  # each its own copy: a callback may change what it's given (the review, D4)
            self._noted(other)
            done(copy.deepcopy(value), None)

    def pending(self):
        return len(self.inflight) + len(self.held)

    def make_room(self):
        """Wait while as many requests are pending as the bound (twice the workers, at least 4), so prepared requests,
        which hold image data, stay bounded however much is fed."""
        while self.pending() >= max(4, 2 * self.workers):
            self.wait_one()

    def wait_one(self):
        """Handle at least one finished request (results may queue more)."""
        if self.held and (not self.inflight or self.shuffle.random() < 0.5):
            request, finish, value, error = self.held.pop(self.shuffle.randrange(len(self.held)))
            if error is not None:
                finish(None, error)
            elif value is not None:
                self._complete(request, finish, lambda: value, cached=True)
            else:  # unrecorded: sending fails as it would have
                self._complete(request, finish, self.client.send, request)
            return
        done, _ = wait(list(self.inflight), return_when=FIRST_COMPLETED)
        for future in done:
            request, finish = self.inflight.pop(future)
            self._complete(request, finish, future.result)

    def drain(self):
        while self.inflight or self.held:
            self.wait_one()

    def close(self, cancel=False):
        if self.pool is not None:
            self.pool.shutdown(wait=not cancel, cancel_futures=cancel)
            self.pool = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *rest):
        self.close(cancel=exc_type is not None)
