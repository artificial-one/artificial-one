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
    def test_real_commission_per_visitor_outranks_empty_click_volume(self):
        offers = [
            {"id": "clicky", "name": "Clicky", "featured": False},
            {"id": "payer", "name": "Payer", "featured": False},
        ]
        ranking = optimizer.rank_offers(
            offers,
            clicks={"by_offer": {"clicky": 40, "payer": 4}},
            impressions={"by_offer": {"clicky": 500, "payer": 50}},
            commission_cents=Counter({"payer": 2500}),
        )
        self.assertEqual(ranking[0], "payer")
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
        self.assertEqual(strategy["money_clusters"], ["one", "two"])
        self.assertEqual(strategy["growth_targets"]["affiliate_click_goal"], 100)

    def test_program_names_map_to_offer_ids(self):
        offers = [{"id": "seamless", "name": "Seamless.AI"}]
        partnerships = [{"key": "part_1", "company": {"name": "Seamless"}}]
        self.assertEqual(
            optimizer.offer_program_map(offers, partnerships),
            {"part_1": "seamless"},
        )

    def test_private_program_terms_create_cold_start_prior(self):
        partnership = {
            "offers": [{"commission_percent": "30", "cookie_days": 60, "free_trial": True, "deep_link_url": "https://example.com"}]
        }
        self.assertGreater(optimizer.economic_prior(partnership), 1.0)


if __name__ == "__main__":
    unittest.main()
