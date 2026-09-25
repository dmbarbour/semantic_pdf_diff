import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from semantic_pdf_diff.llm import Client
from semantic_pdf_diff.models import Extraction, RateRule, Settings
from semantic_pdf_diff.throttle import AdaptiveGate, RateLimiter, rule_applies

EMPTY = json.dumps({'claims': [], 'complete': True, 'issues': []})

class Rules(unittest.TestCase):
    def test_days_and_hours(self):
        weekday_day = datetime(2026, 9, 24, 10, 0)    # Thursday
        weekday_night = datetime(2026, 9, 24, 23, 0)
        saturday = datetime(2026, 9, 26, 10, 0)
        business = RateRule(days='mon-fri', hours='08:00-18:00', tokens_per_minute=1)
        self.assertTrue(rule_applies(business, weekday_day))
        self.assertFalse(rule_applies(business, weekday_night))
        self.assertFalse(rule_applies(business, saturday))
        self.assertTrue(rule_applies(RateRule(days='fri-mon', tokens_per_minute=1), saturday))  # wraps past sunday
        overnight = RateRule(hours='22:00-06:00', tokens_per_minute=1)
        self.assertTrue(rule_applies(overnight, weekday_night))
        self.assertFalse(rule_applies(overnight, weekday_day))
        self.assertTrue(rule_applies(RateRule(tokens_per_minute=1), saturday))
        with self.assertRaises(ValueError):
            RateRule(days='weekdays')

class Limiter(unittest.TestCase):
    def setUp(self):
        self.t = 1000.0
        self.clock = lambda: self.t

    def test_tokens_requests_and_time_of_day(self):
        now = {'value': datetime(2026, 9, 24, 10, 0)}
        rules = [RateRule(days='mon-fri', hours='08:00-18:00', tokens_per_minute=100),
                 RateRule(tokens_per_minute=250, requests_per_minute=3)]
        limiter = RateLimiter(rules, clock=self.clock, now=lambda: now['value'])
        limiter.acquire(60)
        with limiter.lock:
            self.assertGreater(limiter.delay(60), 0)     # 120 > 100 in business hours
        now['value'] = datetime(2026, 9, 24, 20, 0)
        with limiter.lock:
            self.assertEqual(limiter.delay(60), 0)       # 120 <= 250 after hours
        limiter.acquire(60); limiter.acquire(60)
        with limiter.lock:
            self.assertGreater(limiter.delay(1), 0)      # 3 requests per minute
        self.t += 60.5
        with limiter.lock:
            self.assertEqual(limiter.delay(1), 0)        # the window moved on

    def test_oversized_alone_and_settling(self):
        limiter = RateLimiter([RateRule(tokens_per_minute=100)], clock=self.clock)
        entry = limiter.acquire(500)                     # larger than the budget, but alone
        with limiter.lock:
            self.assertGreater(limiter.delay(1), 0)
        limiter.settle(entry, 40)                        # the server reported fewer tokens
        with limiter.lock:
            self.assertEqual(limiter.delay(50), 0)

    def test_acquire_waits_for_the_window(self):
        waits = []
        def sleep(seconds):
            waits.append(seconds)
            self.t += seconds
        limiter = RateLimiter([RateRule(tokens_per_minute=100)], clock=self.clock)
        limiter.acquire(80)
        limiter.acquire(80, sleep=sleep)
        self.assertEqual(len(waits), 1)
        self.assertAlmostEqual(waits[0], 60.0)

class Gate(unittest.TestCase):
    def test_halves_on_throttling_and_grows_back(self):
        gate = AdaptiveGate(8, growth_after=2)
        gate.acquire(); gate.release(throttled=True)
        gate.acquire(); gate.release(throttled=True)
        self.assertEqual(gate.limit, 2)
        for _ in range(4):
            gate.acquire(); gate.release()
        self.assertEqual(gate.limit, 4)

    def test_latency_spike_counts_as_throttling(self):
        gate = AdaptiveGate(8)
        for latency in (0.1, 0.1, 0.1):
            gate.acquire(); gate.release(latency=latency)
        gate.acquire(); gate.release(latency=5.0)
        self.assertEqual(gate.limit, 4)

class ConcurrentClient(unittest.TestCase):
    def serve(self, handler_state):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                with handler_state['lock']:
                    handler_state['active'] += 1
                    handler_state['peak'] = max(handler_state['peak'], handler_state['active'])
                    handler_state['count'] += 1
                    throttle = handler_state['count'] <= handler_state.get('throttle_first', 0)
                delay, generated = handler_state.get('answer', lambda n: (handler_state.get('delay', 0.2), 5))(
                    handler_state['count'])
                time.sleep(delay)
                with handler_state['lock']:
                    handler_state['active'] -= 1
                if throttle:
                    self.send_response(429); self.send_header('Retry-After', '0'); self.end_headers()
                    return
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': EMPTY}}],
                                             'usage': {'prompt_tokens': 10, 'completion_tokens': generated}}).encode())
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        self.addCleanup(lambda: (server.shutdown(), server.server_close(), thread.join()))
        return f'http://127.0.0.1:{server.server_port}/v1'

    def test_parallel_requests_respect_the_cap(self):
        state = {'lock': threading.Lock(), 'active': 0, 'peak': 0, 'count': 0}
        url = self.serve(state)
        with tempfile.TemporaryDirectory() as d:
            client = Client(Settings(base_url=url, concurrency=4, retries=0), Path(d))
            requests = [client.prepare(f'prompt {i}', Extraction) for i in range(12)]
            started = time.monotonic()
            with ThreadPoolExecutor(12) as pool:
                results = list(pool.map(client.send, requests))
            elapsed = time.monotonic() - started
        self.assertEqual(len(results), 12)
        self.assertEqual(state['peak'], 4)
        self.assertLess(elapsed, 12 * 0.2 / 2)           # far faster than sequential
        self.assertEqual((client.calls, client.usage), (12, {'prompt_tokens': 120, 'completion_tokens': 60}))

    def test_long_answers_are_not_read_as_load(self):
        # Every fourth answer is ten times longer, and takes ten times as long: same speed per token.
        state = {'lock': threading.Lock(), 'active': 0, 'peak': 0, 'count': 0,
                 'answer': lambda n: (0.4, 400) if n % 4 == 0 else (0.04, 40)}
        url = self.serve(state)
        with tempfile.TemporaryDirectory() as d:
            client = Client(Settings(base_url=url, concurrency=4, retries=0), Path(d))
            requests = [client.prepare(f'prompt {i}', Extraction) for i in range(16)]
            with ThreadPoolExecutor(4) as pool:
                list(pool.map(client.send, requests))
        self.assertEqual(client.gate.limit, 4)

    def test_throttling_shrinks_concurrency(self):
        state = {'lock': threading.Lock(), 'active': 0, 'peak': 0, 'count': 0, 'throttle_first': 4, 'delay': 0.05}
        url = self.serve(state)
        with tempfile.TemporaryDirectory() as d:
            client = Client(Settings(base_url=url, concurrency=8, retries=2), Path(d))
            requests = [client.prepare(f'prompt {i}', Extraction) for i in range(4)]
            with ThreadPoolExecutor(4) as pool:
                list(pool.map(client.send, requests))
        self.assertLess(client.gate.limit, 8)

if __name__ == '__main__':
    unittest.main()
