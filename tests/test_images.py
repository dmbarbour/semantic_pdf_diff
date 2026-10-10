"""Images as sources: read as one-page documents by the PDF reader's vision tasks (extract.image_pdf)."""
import tempfile
import unittest
from pathlib import Path

import pymupdf

import stubs  # noqa: F401 (a clean environment)
from semantic_pdf_diff.jobs import IMAGE_EXTENSIONS, Job, image_pdf, reader_for, reader_version, run_jobs
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.settings import Settings
from stubs import situating_answer

def png(width, height, dpi=None):
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, width, height), False)
    pix.clear_with(255)
    if dpi:
        pix.set_dpi(dpi, dpi)
    return pix.tobytes("png")

class Layout(unittest.TestCase):
    def test_a_scan_keeps_its_paper_size_and_a_screen_image_its_pixels(self):
        s = Settings()
        scan = pymupdf.open("pdf", image_pdf(png(2550, 3300, dpi=300), ".png", s))
        self.assertEqual((round(scan[0].rect.width), round(scan[0].rect.height)), (612, 792))  # letter
        for dpi in (None, 72):  # no resolution (read as 96 dpi) or a screen's: a tile shows its pixels one to one
            page = pymupdf.open("pdf", image_pdf(png(2000, 1000, dpi=dpi), ".png", s))[0]
            self.assertAlmostEqual(page.rect.width, 2000 * s.tile_points / s.image_side, places=1)
            self.assertEqual(len(page.get_images()), 1)
        self.assertEqual(image_pdf(b"not an image", ".png", s), b"")

    def test_every_image_extension_has_a_reader_and_a_version(self):
        for extension in IMAGE_EXTENSIONS:
            self.assertIsNotNone(reader_for(extension))
            self.assertEqual(reader_version(extension), "image/1")

class Read(unittest.TestCase):
    class Client:
        def __init__(self):
            self.s = Settings(vision=True)
            self.calls, self.cache_hits, self.usage, self.asked = 0, 0, {}, []

        def ask(self, prompt, schema, images=(), key=None):
            self.asked.append((key[3], len(images)))
            if situating_answer(prompt):
                return schema.model_validate(situating_answer(prompt))
            return Extraction(claims=[], complete=True)

    def read(self, data, extension=".png"):
        with tempfile.TemporaryDirectory() as d:
            client = self.Client()
            job = Job("sha256:image" + extension, lambda: data, reader=reader_for(extension))
            run_jobs([[job]], Path(d), client)
            return client.asked, job.state["result"][1]

    def test_an_image_is_read_by_vision_tasks(self):
        asked, coverage = self.read(png(1600, 1200))
        tasks = {task.split(":")[0] for task, images in asked if images}
        self.assertIn("overview", tasks)
        self.assertIn("tile", tasks)
        self.assertFalse([task for task, _ in asked if task.startswith(("text:", "table:"))])  # no text layer

    def test_an_unreadable_image_is_recorded_and_skipped(self):
        asked, coverage = self.read(b"not an image")
        self.assertEqual(asked, [])
        self.assertEqual([(row["task"], row["status"]) for row in coverage], [("open", "failed")])

if __name__ == "__main__":
    unittest.main()
