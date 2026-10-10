"""How a model request fails: the failure classes callers catch, and which recorded failures were the service's
rather than the model's (transient). Split from llm.py, so the fixture, which records failures, needn't import the
client that replays it (code review 2026-10-08, C14: the llm and fixtures import cycle).
"""
import re

class ModelFailure(RuntimeError):
    pass

class BudgetExceeded(ModelFailure):
    pass

class CallLimitReached(BudgetExceeded):
    """max_calls was reached: the work wasn't attempted, as opposed to failing."""

class OutOfBudget(CallLimitReached):
    """The provider's balance ran out, or the run's cost cap was reached: work not attempted,
    to be resumed after a top-up (like the call limit, never recorded as a model failure)."""

# Failures of the service rather than of the model's answer: replay re-asks them when recording
# only new requests (record-new), instead of reproducing a timeout forever.
TRANSIENT = re.compile(r"TimeoutError|timed out|HTTP (?:408|429|5\d\d)|Connection|IncompleteRead|RemoteDisconnected|"
                       r"URLError|OSError")

def transient(error):
    return bool(TRANSIENT.search(error or ""))

class Truncated(ModelFailure):
    """The answer hit the output limit. Not retried: at temperature 0 it would stop at the same place, and every
    attempt is billed. Refinement asks again in smaller pieces."""

class Invalid(ModelFailure):
    """The answer isn't the JSON its schema asks for. Not retried, like Truncated: at temperature 0 the same request
    gets the same answer, and every attempt is billed (code review 2026-10-08, C10: each was asked three times)."""

class NotRecorded(ModelFailure):
    """Replay found no recorded answer for a request."""
