from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import partnerstack_content_marketplace as marketplace


class PartnerStackContentMarketplaceTests(unittest.TestCase):
    def test_pending_order_is_owner_action_not_public_campaign(self) -> None:
        order = marketplace.normalize_order({
            "key": "ord_pending",
            "status": "pending",
            "offer": {"name": "Sponsored Launch Brief"},
            "brand": {"name": "Example AI"},
        })
        self.assertEqual(order["status"], "pending")
        self.assertIn("requests/ord_pending", marketplace.order_url(order["key"]))

    def test_normalization_rejects_non_https_destination(self) -> None:
        order = marketplace.normalize_order({
            "id": "ord_1",
            "status": "accepted",
            "offer": {"title": "Visual Social Launch"},
            "buyer": {"company_name": "Bright Tool"},
            "description": "A practical creative tool.",
            "product_url": "javascript:alert(1)",
        })
        self.assertEqual(order["brand"], "Bright Tool")
        self.assertEqual(order["target_url"], "")

    def test_public_campaign_preserves_dates_across_runs(self) -> None:
        order = {
            "key": "ord_12345678", "status": "accepted", "brand": "Bright Tool",
            "offer_name": "AI Tool Launch Bundle", "brief": "Sponsor brief", "target_url": "https://example.com",
        }
        package = {
            "id": "ai-tool-launch-bundle",
            "deliverables": ["sponsored_page", "category_placement", "social_post", "social_followup"],
        }
        first = marketplace.public_campaign(order, package, None, date(2026, 9, 25))
        second = marketplace.public_campaign(order, package, first, date(2026, 9, 26))
        self.assertEqual(first["first_published"], second["first_published"])
        self.assertEqual(first["social_publish_dates"], ["2026-09-25", "2026-10-02"])
        self.assertEqual(second["social_publish_dates"], first["social_publish_dates"])
        self.assertEqual(first["spotlight_until"], "2026-10-25")

    def test_render_escapes_sponsor_content_and_labels_payment(self) -> None:
        campaign = {
            "id": "partnerstack-1", "brand": "<b>Brand</b>", "brief": "<script>alert(1)</script>",
            "target_url": "https://example.com", "page_url": "https://artificial.one/sponsored/brand.html",
            "disclosure": "Sponsored by the featured company.",
        }
        html = marketplace.render_campaign(campaign)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("Commercial disclosure", html)
        self.assertIn('rel="nofollow sponsored noopener"', html)

    def test_run_submits_only_accepted_live_campaign(self) -> None:
        orders = [
            {"key": "accepted-1", "status": "accepted", "offer": {"name": "Sponsored Launch Brief"}, "brand": {"name": "A"}, "product_url": "https://a.example", "brief": "A brief"},
            {"key": "pending-1", "status": "pending", "offer": {"name": "Sponsored Launch Brief"}, "brand": {"name": "B"}},
        ]
        submitted: list[tuple[str, str]] = []
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            with (
                patch.object(marketplace, "fetch_orders", return_value=orders),
                patch.object(marketplace, "PUBLIC_PATH", temp / "campaigns.json"),
                patch.object(marketplace, "HUB_PATH", temp / "sponsored.html"),
                patch.object(marketplace, "OUTPUT_DIR", temp / "sponsored"),
                patch.object(marketplace, "SITEMAP_PATH", temp / "sitemap.xml"),
                patch.object(marketplace, "INVENTORY_PATH", Path(__file__).parents[1] / "data" / "sponsorship_inventory.json"),
                patch.object(marketplace, "public_url_is_live", return_value=True),
                patch.object(marketplace, "submit_deliverable", side_effect=lambda key, order, url, base: submitted.append((order, url))),
            ):
                (temp / "sitemap.xml").write_text("<urlset>\n</urlset>\n", encoding="utf-8")
                status = marketplace.run("token", temp / "state.json", temp / "status.json", submit=True, today=date(2026, 9, 25))
                public = json.loads((temp / "campaigns.json").read_text(encoding="utf-8"))
        self.assertEqual(len(public["campaigns"]), 1)
        self.assertEqual(status["owner_actions"][0]["title"], "Review B — Sponsored Launch Brief")
        self.assertEqual(submitted[0][0], "accepted-1")


if __name__ == "__main__":
    unittest.main()
