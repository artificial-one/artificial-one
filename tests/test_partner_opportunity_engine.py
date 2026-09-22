import json
from pathlib import Path
import tempfile
import unittest

from scripts import partner_opportunity_engine as scout


class PartnerOpportunityEngineTests(unittest.TestCase):
    def test_public_reference_strips_bearer_style_parameters(self):
        self.assertEqual(
            scout.public_reference_url("https://example.com/terms?token=private&locale=en#part"),
            "https://example.com/terms?locale=en",
        )

    def test_parses_public_partnerstack_state(self):
        state = {"company": {"companies": {"example": {
            "name": "Example AI", "slug": "example", "enriched_description": "AI software for marketing teams",
            "offer": "Earn 30% recurring commission", "links_enabled": True, "revenue_share": True,
            "sub_id_enabled": True, "materials": True, "tos": "https://example.com/terms", "website": "example.com",
            "tags": [{"name": "Artificial Intelligence"}, {"name": "Affiliates"}],
        }}}}
        html = f"<script>window.__INITIAL_STATE__ = {json.dumps(state)};</script>"
        rows = scout.parse_partnerstack_directory(html)
        self.assertEqual(rows[0]["name"], "Example AI")
        self.assertEqual(
            rows[0]["application_url"],
            "https://dash.partnerstack.com/marketplace/all/details/example?company=example&gref=marketplace",
        )
        score, matches = scout.relevance_score(rows[0])
        self.assertGreaterEqual(score, 70)
        self.assertIn("artificial intelligence", matches)

    def test_policy_parser_extracts_restrictions(self):
        original = scout.fetch_text
        try:
            scout.fetch_text = lambda *_args, **_kwargs: "Affiliates must not bid on our trademark. A 45-day attribution cookie applies. Affiliate disclosure required."
            result = scout.inspect_policy("https://example.com/terms")
            self.assertEqual(result["status"], "reviewed")
            self.assertEqual(result["cookie_days"], 45)
            self.assertTrue(result["signals"]["trademark_bidding_restricted"])
            self.assertTrue(result["signals"]["disclosure_required"])
        finally:
            scout.fetch_text = original

    def test_all_qualifying_candidates_advance_without_quota(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/partner_offers.json").write_text('{"offers": []}', encoding="utf-8")
            (root / "data/partnerstack_program_audit.json").write_text('{"programs": []}', encoding="utf-8")
            original = scout.inspect_policy
            try:
                scout.inspect_policy = lambda _url: {"status": "reviewed", "signals": {}, "cookie_days": 30}
                rows = []
                for index in range(30):
                    rows.append({
                        "id": f"partnerstack:tool-{index}", "network": "partnerstack", "name": f"AI Tool {index}", "slug": f"tool-{index}",
                        "description": "AI software for marketing automation", "offer": "Earn commission", "tags": ["Artificial Intelligence"],
                        "application_url": f"https://market.partnerstack.com/tool-{index}", "terms_url": "https://example.com/terms",
                        "waitlist": False, "archived": False, "links_enabled": True, "materials": True,
                        "sub_id_enabled": True, "revenue_share": True,
                    })
                result = scout.prepare_opportunities(rows, root, {})
                self.assertEqual(len(result), 30)
                self.assertTrue(all(item["state"] == "ready_for_owner_application" for item in result))
                self.assertTrue(all(item["application_url"].startswith("https://dash.partnerstack.com/marketplace/all/details/") for item in result))
            finally:
                scout.inspect_policy = original

    def test_known_program_is_not_reapplied_to(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/partner_offers.json").write_text('{"offers": [{"name": "Known AI"}]}', encoding="utf-8")
            (root / "data/partnerstack_program_audit.json").write_text('{"programs": []}', encoding="utf-8")
            row = {"id": "partnerstack:known", "name": "Known AI", "description": "AI software", "offer": "Commission", "tags": ["AI"], "application_url": "https://example.com", "waitlist": False, "archived": False, "links_enabled": True}
            result = scout.prepare_opportunities([row], root, {})
            self.assertEqual(result[0]["state"], "existing_active")

    def test_owner_queue_contains_every_candidate_and_is_noindex(self):
        payload = {"updated_at": "2026-09-22", "summary": {}, "opportunities": [
            {"name": f"Tool {index}", "state": "ready_for_owner_application", "network": "partnerstack", "score": 80, "description": "AI software", "offer": "20% commission", "tags": ["AI"], "application_url": f"https://example.com/{index}", "policy": {"signals": {}}}
            for index in range(25)
        ]}
        html = scout.render_queue_page(payload)
        self.assertIn('name="robots" content="noindex,nofollow"', html)
        self.assertEqual(html.count("data-card "), 25)
        self.assertIn("https://example.com/24", html)

    def test_approved_partner_with_link_enters_offer_pipeline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/partner_offers.json").write_text('{"version":1,"offers":[]}', encoding="utf-8")
            (root / "data/partnerstack_program_audit.json").write_text('{"version":1,"programs":[],"summary":{}}', encoding="utf-8")
            opportunity = {
                "name": "New AI", "slug": "new-ai", "description": "AI workflow automation software for business teams.",
                "tags": ["Artificial Intelligence"], "website": "https://example.com/", "terms_url": "https://example.com/terms",
                "source": "https://market.partnerstack.com/", "policy": {"status": "reviewed"}, "state": "existing_active",
            }
            original = scout.partnerstack_links
            try:
                scout.partnerstack_links = lambda *_args: ["https://example.com/ref/artificial-one"]
                added = scout.merge_auto_offers(root, [opportunity], {"newai": {"key": "part_1", "status": "approved"}}, "key")
                self.assertEqual(added, ["New AI"])
                registry = json.loads((root / "data/partner_offers.json").read_text(encoding="utf-8"))
                self.assertEqual(registry["offers"][0]["status"], "published")
                audit = json.loads((root / "data/partnerstack_program_audit.json").read_text(encoding="utf-8"))
                self.assertEqual(audit["summary"]["trackable_links_confirmed"], 1)
            finally:
                scout.partnerstack_links = original


if __name__ == "__main__":
    unittest.main()
