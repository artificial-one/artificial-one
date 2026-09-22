import json
from pathlib import Path
import tempfile
import unittest

from scripts import impact_appsumo_scout as scout


class ImpactAppSumoScoutTests(unittest.TestCase):
    def test_product_slug_accepts_only_appsumo_product_pages(self):
        self.assertEqual(scout.product_slug("https://appsumo.com/products/example-ai/"), "example-ai")
        self.assertEqual(scout.product_slug("https://example.com/products/example-ai/"), "")
        self.assertEqual(scout.product_slug("https://fakeappsumo.com/products/example-ai/"), "")
        self.assertEqual(scout.product_slug("https://appsumo.com/collections/ai/"), "")

    def test_all_product_ads_are_retained_without_quota(self):
        ads = [{
            "Id": str(index), "Name": f"AI Product {index} Text Link", "Description": "AI workflow automation",
            "CampaignId": 7443, "Type": "TEXT_LINK", "TrackingLink": f"https://appsumo.8odi.net/link{index}",
            "LandingPageUrl": f"https://appsumo.com/products/ai-product-{index}/", "DealState": "ACTIVE",
        } for index in range(75)]
        offers, created = scout.normalize_ads(ads, "sid", "token")
        self.assertEqual(len(offers), 75)
        self.assertEqual(created, 0)
        self.assertTrue(all(item["ai_relevant"] for item in offers))
        self.assertTrue(all(item["editorial_url"].startswith("appsumo-guides/") for item in offers))

    def test_duplicate_assets_collapse_to_one_product(self):
        ads = [
            {"Id": "1", "Name": "Example Banner", "LandingPageUrl": "https://appsumo.com/products/example/", "TrackingLink": "https://appsumo.8odi.net/one", "Type": "BANNER", "DealState": "ACTIVE"},
            {"Id": "2", "Name": "Example AI Text Link", "Description": "AI automation", "LandingPageUrl": "https://appsumo.com/products/example/", "TrackingLink": "https://appsumo.8odi.net/two", "Type": "TEXT_LINK", "DealState": "ACTIVE"},
        ]
        offers, _created = scout.normalize_ads(ads, "sid", "token")
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["impact_ad_id"], "2")

    def test_missing_tracking_link_is_created(self):
        ads = [{"Id": "9", "Name": "AI Helper", "Description": "AI writing", "LandingPageUrl": "https://appsumo.com/products/ai-helper/", "Type": "TEXT_LINK", "DealState": "ACTIVE"}]
        original = scout.create_tracking_link
        scout.create_tracking_link = lambda *_args: "https://appsumo.8odi.net/newlink"
        try:
            offers, created = scout.normalize_ads(ads, "sid", "token")
        finally:
            scout.create_tracking_link = original
        self.assertEqual(created, 1)
        self.assertEqual(offers[0]["tracking_url"], "https://appsumo.8odi.net/newlink")

    def test_generated_guide_is_disclosed_and_tracked(self):
        offer = {"id": "impact-ad-1", "name": "Example AI", "slug": "example-ai", "description": "AI workflow software.", "category": "Business software", "tracking_url": "https://appsumo.8odi.net/example", "editorial_url": "appsumo-guides/example-ai.html"}
        page = scout.render_guide(offer)
        self.assertIn("Source-based overview", page)
        self.assertIn('rel="nofollow sponsored noopener"', page)
        self.assertIn('data-affiliate-network="impact"', page)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(scout.write_guides([offer], Path(folder)), 1)
            self.assertTrue((Path(folder) / "appsumo-guides/example-ai.html").exists())

    def test_policy_summary_never_publishes_contract_text(self):
        contracts = [{"CampaignId": "7443", "Status": "ACTIVE", "Terms": {"SpecialTermsList": [{"TermsContent": "No coupon or incentivized traffic."}]}}]
        result = scout.policy_summary(contracts)
        self.assertEqual(result["contract_status"], "ACTIVE")
        self.assertTrue(result["coupon_restriction_detected"])
        self.assertNotIn("TermsContent", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
