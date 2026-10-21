"""Runs at once (lab bench/recording.forked; docs/samples-and-testing.md, Runs at once): the controlled
corpus's re-record of 2026-10-17 took about 3 hours in hand-split processes; controlled.py and record_runs.py now
spread their runs over forked processes sharing the fixture."""
import stubs  # noqa: F401 (a clean environment)
from stubs import needs_lab
import os
import unittest


class Forked(unittest.TestCase):
    def setUp(self):
        needs_lab()
        from semantic_pdf_diff_lab.bench.recording import forked
        self.forked = forked

    def test_every_item_once_whatever_the_order_in_other_processes(self):
        here = os.getpid()
        def work(item):  # a closure: nothing but indices and results crosses processes
            return item, item * item, os.getpid()
        for _ in range(20):  # the first version lost results now and then (a queue's thread across forks)
            results = list(self.forked(work, range(12), 4))
            self.assertEqual(sorted((i, sq) for i, sq, _ in results), [(i, i * i) for i in range(12)])
            pids = {pid for *_, pid in results}
            self.assertLessEqual(len(pids), 4)
            self.assertNotIn(here, pids)

    def test_one_job_runs_here_in_order(self):
        self.assertEqual(list(self.forked(lambda i: (i, os.getpid()), [3, 1, 2], 1)),
                         [(3, os.getpid()), (1, os.getpid()), (2, os.getpid())])

    def test_a_process_that_dies_is_reported(self):
        def work(item):
            if item == 2:
                os._exit(9)
            return item
        with self.assertRaises(RuntimeError) as caught:
            list(self.forked(work, range(4), 2))
        self.assertIn("died on 2", str(caught.exception))

    def test_workers_end_when_the_caller_stops_reading(self):
        import multiprocessing
        import time
        def work(item):
            time.sleep(0.05)
            return item
        results = self.forked(work, range(40), 3)
        next(results)
        results.close()
        self.assertEqual(multiprocessing.active_children(), [])


if __name__ == "__main__":
    unittest.main()
