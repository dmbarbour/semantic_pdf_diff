"""The complete_by_image lever: an image task's completeness is the image's, not its text layer's cuts."""
import stubs  # noqa: F401 (a clean environment)
import unittest

from semantic_pdf_diff.levers import LAYER_RULE
from semantic_pdf_diff.settings import Settings

class CompleteByImage(unittest.TestCase):
    def test_image_tasks_are_told_and_text_tasks_arent(self):
        on, off = Settings(complete_by_image=True), Settings()
        for region in ("tile", "figure", "overview"):
            self.assertIn(LAYER_RULE, on.region_rules(region))
            self.assertNotIn(LAYER_RULE, off.region_rules(region))
        for region in ("text", "table"):
            self.assertEqual(on.region_rules(region), off.region_rules(region))

if __name__ == "__main__":
    unittest.main()
