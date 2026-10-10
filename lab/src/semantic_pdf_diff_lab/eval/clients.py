"""The clients evaluating models use (judges, query checkers, the post-mortem's analyst, the eye and page tests):
their fixed settings, each folder's own fixture, one cost cap for a command. Moved from the product, which never
used them (code review 2026-10-08, C15: evaluation helpers in product modules).
"""
from contextlib import contextmanager

from semantic_pdf_diff.fixtures import folder_fixture
from semantic_pdf_diff.llm import Client
from semantic_pdf_diff.settings import SETTING_CLASSES, Settings

# What every evaluating model (judges, query checkers, the post-mortem's analyst) is asked with.
# Its answers are recorded by query, so these must be the same wherever a folder is judged; the
# transport (concurrency, timeouts, retries, caps) varies by caller and never changes a query.
EVALUATOR_SETTINGS = {"context_tokens": 262144, "output_tokens": 16000, "image_tokens": 3000}

def evaluator_settings(model, base=None, **runtime):
    """Settings for a judge, checker or analyst. What shapes its queries is fixed (`base`, by default
    EVALUATOR_SETTINGS) and never read from the environment: an exported PDF_DIFF_RESPONSE_FORMAT or
    PDF_DIFF_SEED would otherwise change every judge query, every recorded verdict would miss, and judging would
    be paid again (code review 2026-10-01, item 2). Only endpoint settings (URL, timeouts, concurrency, rate
    limits, cost cap) come from the environment, and `runtime` may set only those."""
    shaping = sorted(k for k in runtime if SETTING_CLASSES[k] != "endpoint")
    if shaping:
        raise ValueError(f"evaluator runtime settings must be endpoint settings, not {shaping}")
    endpoint_names = {k for k, kind in SETTING_CLASSES.items() if kind == "endpoint" and k != "model"}
    # only the endpoint's variables read: a profile's PDF_DIFF_CONTEXT_TOKENS made every judge's settings invalid
    env = Settings.from_env(only=endpoint_names, model=model)  # (code review 2026-10-08, C9)
    endpoint = {k: getattr(env, k) for k in endpoint_names}
    return Settings(**{**endpoint, **(EVALUATOR_SETTINGS if base is None else base), **runtime, "model": model})

class Budget:
    """One cost cap for a whole command, shared by the clients it makes one after another (one per model): the
    cap was once each client's, so a command with three models could spend three times it."""
    def __init__(self, cap):
        if cap is not None and cap <= 0:
            raise ValueError("a cost cap must be more than $0 (leave it unset for none)")
        self.cap, self.spent = cap, 0.0

    def left(self):
        """Dollars left, or None for no cap."""
        return None if self.cap is None else max(self.cap - self.spent, 0.0)

    def exhausted(self):
        return self.cap is not None and self.left() <= 0

    def settings(self):
        """The `max_cost` keyword for the next client: what's left, or nothing without a cap."""
        return {} if self.cap is None else {"max_cost": self.left()}

    def add(self, client):
        self.spent += client.cost

@contextmanager
def folder_client(folder, settings, mode="replay-or-record", responder=None):
    """A client whose answers are recorded in a folder's own fixture (fixtures.folder_fixture):
    judges, the post-mortem's analyst and query checkers, each folder apart from the main fixture.
    Answers already recorded are served; the rest are asked (in replay mode: fail as unrecorded).
    responder: whose answers they are (default: the model's name), e.g. a model at another host."""
    client = Client(settings, None, fixture=folder_fixture(folder), mode=mode, responder=responder)
    try:
        yield client
    finally:
        client.close()
