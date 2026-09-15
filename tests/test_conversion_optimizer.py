import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "optimize_conversion.py"
SPEC = importlib.util.spec_from_file_location("optimize_conversion", MODULE_PATH)
conversion = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(conversion)


class ConversionOptimizerTests(unittest.TestCase):
    def test_placement_totals_are_reduced_to_variants(self):
        aggregate = {"by_placement": {"offer-sticky-cro-a": 120, "other-cro-a": 10, "offer-sticky-cro-b": 140}}
        self.assertEqual(conversion.variant_totals(aggregate), {"a": 130, "b": 140})

    def test_requires_minimum_sample(self):
        self.assertIsNone(conversion.statistically_preferred({"a": 20, "b": 2}, {"a": 99, "b": 99}))

    def test_selects_clear_ctr_winner(self):
        winner = conversion.statistically_preferred({"a": 30, "b": 10}, {"a": 200, "b": 200})
        self.assertEqual(winner, "a")

    def test_public_strategy_contains_no_counts(self):
        strategy = conversion.build_strategy("b")
        self.assertEqual(strategy["sticky"]["winner"], "b")
        self.assertNotIn("impressions", str(strategy))


if __name__ == "__main__":
    unittest.main()
