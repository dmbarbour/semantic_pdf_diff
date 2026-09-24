"""Throughput control for model requests: time-of-day rate limits and adaptive concurrency.

Configured limits are ceilings. The adaptive gate reacts to the server's actual
behaviour (throttling responses, rising latency), which also covers limits that
change without notice. Neither affects extraction output.
"""
import threading
import time
from collections import deque
from datetime import datetime

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def _days(spec):
    """'mon-fri', 'sat,sun' or 'tue' -> set of weekday numbers (Monday = 0)."""
    days = set()
    for part in spec.lower().replace(" ", "").split(","):
        first, _, last = part.partition("-")
        a, b = DAYS.index(first), DAYS.index(last or first)
        days.update(range(a, b + 1) if a <= b else [*range(a, 7), *range(0, b + 1)])
    return days

def _minutes(clock):
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)

def rule_applies(rule, now):
    if rule.days and now.weekday() not in _days(rule.days):
        return False
    if rule.hours:
        start, end = (_minutes(t) for t in rule.hours.split("-"))
        minute = now.hour * 60 + now.minute
        inside = start <= minute < end if start <= end else (minute >= start or minute < end)
        if not inside:
            return False
    return True

class RateLimiter:
    """Sliding one-minute window over tokens and requests; the first matching rule applies."""

    def __init__(self, rules, clock=time.monotonic, now=datetime.now, window=60.0):
        self.rules, self.clock, self.now, self.window = list(rules), clock, now, window
        self.events = deque()  # [time, tokens]
        self.lock = threading.Condition()

    def limits(self):
        for rule in self.rules:
            if rule_applies(rule, self.now()):
                return rule.tokens_per_minute, rule.requests_per_minute
        return None, None

    def delay(self, tokens):
        """Seconds to wait before `tokens` more fit, or 0. Caller holds the lock."""
        t = self.clock()
        while self.events and self.events[0][0] <= t - self.window:
            self.events.popleft()
        tpm, rpm = self.limits()
        used = sum(e[1] for e in self.events)
        # A single request larger than the whole budget still goes through, alone.
        tokens_ok = tpm is None or not self.events or used + tokens <= tpm
        requests_ok = rpm is None or len(self.events) < rpm
        if tokens_ok and requests_ok:
            return 0.0
        return max(0.01, self.events[0][0] + self.window - t)

    def acquire(self, tokens, sleep=None):
        """Block until `tokens` fit the current limits; returns a handle for settle()."""
        with self.lock:
            while True:
                wait = self.delay(tokens)
                if not wait:
                    entry = [self.clock(), tokens]
                    self.events.append(entry)
                    return entry
                if sleep:
                    self.lock.release()
                    try:
                        sleep(wait)
                    finally:
                        self.lock.acquire()
                else:
                    self.lock.wait(wait)

    def settle(self, entry, actual):
        """Replace an estimate with the tokens the server reported."""
        with self.lock:
            entry[1] = actual
            self.lock.notify_all()

class AdaptiveGate:
    """At most `limit` requests in flight: halves on throttling, grows by one after a run of successes."""

    def __init__(self, cap, growth_after=8, latency_factor=3.0):
        self.cap, self.limit, self.active = cap, cap, 0
        self.growth_after, self.latency_factor = growth_after, latency_factor
        self.streak, self.baseline, self.recent = 0, None, None
        self.lock = threading.Condition()

    def acquire(self):
        with self.lock:
            while self.active >= self.limit:
                self.lock.wait()
            self.active += 1

    def release(self, throttled=False, latency=None):
        with self.lock:
            self.active -= 1
            if latency is not None:
                self.recent = latency if self.recent is None else 0.7 * self.recent + 0.3 * latency
                self.baseline = self.recent if self.baseline is None else min(self.baseline, self.recent)
                if self.recent > self.latency_factor * self.baseline:
                    throttled = True
                    self.baseline = self.recent  # adapt, rather than shrink forever on a slower server
            if throttled:
                self.limit, self.streak = max(1, self.limit // 2), 0
            else:
                self.streak += 1
                if self.streak >= self.growth_after and self.limit < self.cap:
                    self.limit, self.streak = self.limit + 1, 0
            self.lock.notify_all()
