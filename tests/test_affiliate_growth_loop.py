import json
import tempfile
import unittest
from pathlib import Path

from scripts import affiliate_catalog as catalog
from scripts import build_affiliate_growth_loop as growth
from scripts import optimize_revenue as optimizer
from scripts import search_revenue_engine as search


ROOT = Path(__file__).resolve().parents[1]


class AffiliateGrowthLoopTests(unittest.TestCase):
    def test_complete_monetized_catalog_has_exact_links_and_guides(self):
        tools = catalog.monetized_tools(ROOT / "data" / "tool_intelligence.json")
        self.assertGreaterEqual(len(tools), 290)
        self.assertEqual(len({item["offer_id"] for item in tools}), len(tools))
        self.assertTrue(all(item["affiliate_url"].startswith("https://") for item in tools))
        self.assertTrue(all(item["profile_path"].endswith(".html") for item in tools))

    def test_category_pages_have_no_arbitrary_product_cap(self):
        tools = [
            {
                "offer_id": f"offer-{index}", "name": f"Offer {index}",
                "affiliate_url": f"https://example.com/{index}",
                "profile_path": f"guides/offer-{index}.html",
                "cluster_label": "Automation & Productivity",
                "category": "Automation", "summary": "Automates a repeatable workflow.",
                "best_for": "Teams with recurring work.", "monetization": {"network": "test"},
            }
            for index in range(75)
        ]
        page = growth.render_category("automation-productivity", "Automation & Productivity", tools)
        self.assertEqual(page.count("data-affiliate-offer"), 75)
        self.assertIn("https://example.com/74", page)
        self.assertIn("../guides/offer-74.html", page)
        self.assertIn("data-growth-search", page)

    def test_default_revenue_optimizer_uses_unified_catalog(self):
        offers = optimizer.published_offers()
        self.assertGreaterEqual(len(offers), 290)
        self.assertTrue(any(str(item["id"]).startswith("impact-ad-") for item in offers))

    def test_search_mapping_covers_partnerstack_and_appsumo_guides(self):
        mapping = search.offer_ids_by_path()
        self.assertTrue(any(path.startswith("/partner-offers/") for path in mapping))
        self.assertTrue(any(path.startswith("/appsumo-guides/") for path in mapping))

    def test_custom_partner_registry_remains_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "offers.json"
            path.write_text(json.dumps({"offers": [
                {"id": "one", "name": "One", "status": "published"},
                {"id": "two", "name": "Two", "status": "draft"},
            ]}), encoding="utf-8")
            self.assertEqual([item["id"] for item in optimizer.published_offers(path)], ["one"])


if __name__ == "__main__":
    unittest.main()
