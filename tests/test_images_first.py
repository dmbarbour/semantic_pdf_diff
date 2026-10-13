"""The images_first lever: a request's images before its text, named apart from the same request with them after."""
import stubs  # noqa: F401 (a clean environment)
import json
import tempfile
import unittest
from pathlib import Path

from semantic_pdf_diff.llm import build_request
from semantic_pdf_diff.schema import Extraction
from semantic_pdf_diff.settings import Settings

class ImagesFirst(unittest.TestCase):
    def test_the_images_come_first_and_the_query_is_named_apart(self):
        with tempfile.TemporaryDirectory() as d:
            image = Path(d) / "tile.png"
            image.write_bytes(b"\x89PNG not really")
            after = build_request(Settings(images_first=False), "Read the tile.", Extraction, [image])
            first = build_request(Settings(images_first=True), "Read the tile.", Extraction, [image])
            kinds = lambda r: [part["type"] for part in json.loads(r.body())["messages"][1]["content"]]
            self.assertEqual(kinds(after), ["text", "image_url"])
            self.assertEqual(kinds(first), ["image_url", "text"])
            self.assertNotEqual(after.query, first.query)

    def test_a_request_without_images_is_unchanged(self):
        after = build_request(Settings(images_first=False), "Read the text.", Extraction)
        first = build_request(Settings(images_first=True), "Read the text.", Extraction)
        self.assertEqual((after.query, after.body()), (first.query, first.body()))

if __name__ == "__main__":
    unittest.main()
