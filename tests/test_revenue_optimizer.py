import importlib.util
from collections import Counter
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "optimize_revenue.py"
SPEC = importlib.util.spec_from_file_location("optimize_revenue", MODULE_PATH)
optimizer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(optimizer)


class RevenueOptimizerTests(unittest.TestCase):
    def test_signup_signal_outranks_clicks(self):
        offers = [
            {"id": "clicky", "name": "Clicky", "featured": False},
            {"id": "buyer", "name": "Buyer", "featured": False},
        ]
        ranking = optimizer.rank_offers(
            offers,
            clicks={"by_offer": {"clicky": 8, "buyer": 1}},
            impressions={"by_offer": {"clicky": 40, "buyer": 10}},
            signups=Counter({"buyer": 1}),
        )
        self.assertEqual(ranking[0], "buyer")

    def test_low_data_offer_keeps_exploration_chance(self):
        offers = [
            {"id": "seen", "name": "Seen", "featured": False},
            {"id": "new", "name": "New", "featured": False},
        ]
        ranking = optimizer.rank_offers(
            offers,
            clicks={"by_offer": {"seen": 0}},
            impressions={"by_offer": {"seen": 200}},
        )
        self.assertEqual(ranking[0], "new")

    def test_strategy_contains_no_metrics(self):
        strategy = optimizer.build_strategy(["one", "two"])
        encoded = str(strategy)
        self.assertNotIn("clicks", encoded)
        self.assertNotIn("signups", encoded)
        self.assertEqual(strategy["featured"], ["one", "two"])

    def test_program_names_map_to_offer_ids(self):
        offers = [{"id": "seamless", "name": "Seamless.AI"}]
        partnerships = [{"key": "part_1", "company": {"name": "Seamless"}}]
        self.assertEqual(
            optimizer.offer_program_map(offers, partnerships),
            {"part_1": "seamless"},
        )


if __name__ == "__main__":
    unittest.main()
