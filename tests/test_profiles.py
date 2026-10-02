"""Vision profiles: predictions scale with what reaches the model, and plans are the cheapest that read."""
import stubs  # noqa: F401 (a clean environment)
import unittest
from semantic_pdf_diff import profiles
from semantic_pdf_diff.profiles import Profile

BUDGET = {(512, 512): 8.8, (768, 768): 7.4, (1024, 1024): 6.8, (1536, 1536): 6.5, (2048, 2048): 7.7}  # gemma-4-like
NATIVE = {(512, 512): 11.9, (768, 768): 7.3, (1024, 1024): 5.7, (1536, 1536): 3.9, (2048, 2048): 3.0}  # Qwen3-VL-like

class Profiles(unittest.TestCase):
    def test_predictions_follow_the_image(self):
        p = Profile("m", BUDGET)
        tile = profiles.card_prediction(p, 420, 420, 768)
        self.assertAlmostEqual(profiles.card_prediction(p, 840, 840, 768), 2 * tile, places=6)  # twice the area per pixel
        native = Profile("n", NATIVE)
        # a native-resolution model gains from a larger render; a fixed-budget one much less
        gain = lambda q: profiles.card_prediction(q, 420, 420, 768) / profiles.card_prediction(q, 420, 420, 1536)
        self.assertGreater(gain(native), gain(p))

    def test_the_ceiling_is_the_largest_glyph_read_below_the_first_that_fails(self):
        self.assertIsNone(Profile("m", BUDGET, {24.0: 1.0, 32.0: 0.97, 48.0: 0.95}).ceiling_px)
        self.assertEqual(Profile("m", BUDGET, {24.0: 1.0, 32.0: 0.95, 48.0: 0.6, 64.0: 0.9}).ceiling_px, 32.0)
        self.assertEqual(Profile("m", BUDGET, {24.0: 0.5}).ceiling_px, 16.0)

    def test_plans_are_the_cheapest_that_read_the_smallest_text(self):
        p = Profile("m", BUDGET)
        letter = profiles.plan(p, 612, 792, smallest_pt=10, renders=(768,))
        self.assertEqual(letter["tiles"], 1)  # large text: the whole page
        small = profiles.plan(p, 612, 792, smallest_pt=4, renders=(768,))
        self.assertGreater(small["tiles"], 1)
        self.assertLessEqual(small["predicted_pt"], 0.9 * 4)
        tighter = profiles.plan(p, 612, 792, smallest_pt=3, renders=(768,))
        self.assertGreaterEqual(tighter["tiles"], small["tiles"])
        self.assertIsNone(profiles.plan(p, 612, 792, smallest_pt=0.5, renders=(768,)))  # nothing reads it

    def test_a_ceiling_rules_out_over_magnified_large_text(self):
        free = Profile("n", NATIVE)
        capped = Profile("n", NATIVE, {24.0: 1.0, 32.0: 0.95, 48.0: 0.5})
        chosen = profiles.plan(free, 612, 792, smallest_pt=4, largest_pt=48, renders=(768, 1536))
        careful = profiles.plan(capped, 612, 792, smallest_pt=4, largest_pt=48, renders=(768, 1536))
        self.assertIsNotNone(chosen)
        self.assertTrue(careful is None or careful["largest_cap_px"] <= 32)

    def test_calibration_skips_uninformative_plans(self):
        p = Profile("m", BUDGET)
        pooled = {"archd": {"static": {
            "t864-768": {"min_pt": 7.2}, "t576-768": {"min_pt": 4.8}, "t864-1536": {"min_pt": 6.5},
            "t576-1536": {"min_pt": 4.7}, "t288-768": {"min_pt": 4.0},  # at the smallest font tested: no information
            "whole-768": {"min_pt": None}}}}
        ratio, used = profiles.calibrate(p, pooled)
        self.assertEqual(used, 4)
        self.assertLess(ratio, 1.0)
        self.assertEqual(profiles.calibrate(p, {"archd": {"static": {"t864-768": {"min_pt": 7.2}}}}), (1.0, 1))

if __name__ == "__main__":
    unittest.main()
