import stubs  # noqa: F401 (a clean environment)
import tempfile
import unittest
from pathlib import Path
from semantic_pdf_diff.extract import Job, run_jobs

class Recorder(stubs.Recorder):
    def __init__(self):
        super().__init__(vision=False)
        self.order = []
    def record(self, prompt, schema, images, key):
        self.order.append((key[2], key[3]))  # (content, task)

def pdf(path, pages):
    return stubs.text_pdf(path, [f'{path.stem} page {i + 1}' for i in range(pages)], width=200, at=(20, 20))

class FairShare(unittest.TestCase):
    def test_sources_advance_together(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            a1, a2 = pdf(root / 'a1.pdf', 3), pdf(root / 'a2.pdf', 2)
            b1 = pdf(root / 'b1.pdf', 4)
            client, done = Recorder(), []
            job = lambda path: Job(f'sha256:{path.stem}.pdf', lambda: path, on_done=lambda ev, cov: done.append(path.stem))
            run_jobs([[job(a1), job(a2)], [job(b1)]], root, client)
            sources = ['a' if content.startswith('sha256:a') else 'b' for content, _ in client.order]
            # One worker, yet pages alternate between sources while both have work left.
            self.assertEqual(sources[:8], ['a', 'b'] * 4)
            self.assertEqual(sources[8:], ['a'])
            self.assertEqual(sorted(done), ['a1', 'a2', 'b1'])
            self.assertEqual(len(client.order), 3 + 2 + 4)

if __name__ == '__main__':
    unittest.main()
