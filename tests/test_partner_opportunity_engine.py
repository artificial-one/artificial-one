import json
from pathlib import Path
import tempfile
import unittest

from scripts import partner_opportunity_engine as scout


class PartnerOpportunityEngineTests(unittest.TestCase):
    def test_authenticated_partnership_missing_from_marketplace_is_synthesized(self):
        rows = scout.merge_authenticated_partnerstack([], [{
            "key": "part_123", "status": "active",
            "company": {"name": "API Only AI", "slug": "api-only-ai", "website": "https://example.com"},
        }])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "API Only AI")
        self.assertTrue(rows[0]["approved"])
        self.assertTrue(rows[0]["authenticated_relationship"])

    def test_authenticated_partnership_enriches_public_record(self):
        public = [{"network": "partnerstack", "name": "Example AI", "slug": "example", "description": "Rich public description"}]
        rows = scout.merge_authenticated_partnerstack(public, [{
            "key": "part_1", "approved_status": "approved", "company": {"name": "Example AI"},
        }])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["description"], "Rich public description")
        self.assertTrue(rows[0]["approved"])

    def test_explicit_terms_gate_is_not_published(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/partner_offers.json").write_text('{"version":1,"offers":[]}', encoding="utf-8")
            (root / "data/partnerstack_program_audit.json").write_text('{"version":1,"programs":[],"summary":{}}', encoding="utf-8")
            item = {
                "network": "partnerstack", "name": "Terms AI", "slug": "terms-ai", "approved": True,
                "authenticated_relationship": True, "terms_required": True, "source": "https://partnerstack.com/",
                "policy": {"status": "not_reviewed"},
            }
            added = scout.merge_auto_offers(root, [item], {"termsai": {"key": "part_1", "status": "active"}}, "key")
            self.assertEqual(added, [])
            self.assertEqual(item["relationship_state"], "terms_required")

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

    def test_latest_report_email_links_to_the_complete_queue(self):
        payload = {
            "summary": {},
            "opportunities": [
                {"state": "ready_for_owner_application"},
                {"state": "policy_review_required"},
                {"state": "not_qualified"},
            ],
        }
        subject, text, html = scout.render_email(payload, [], "https://github.com/example/run")
        self.assertIn("2 require review", subject)
        self.assertIn("https://artificial.one/partner-opportunities.html", text)
        self.assertIn("Open the complete opportunity queue", html)

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

    def test_authenticated_partner_with_link_does_not_depend_on_public_policy_page(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/partner_offers.json").write_text('{"version":1,"offers":[]}', encoding="utf-8")
            (root / "data/partnerstack_program_audit.json").write_text('{"version":1,"programs":[],"summary":{}}', encoding="utf-8")
            opportunity = {
                "network": "partnerstack", "name": "API Only AI", "slug": "api-only-ai",
                "approved": True, "authenticated_relationship": True,
                "source": "https://dash.partnerstack.com/home", "application_url": "https://dash.partnerstack.com/home",
                "policy": {"status": "missing"}, "tags": ["Software"],
            }
            original = scout.partnerstack_links
            try:
                scout.partnerstack_links = lambda *_args: ["https://example.com/ref/artificial-one"]
                added = scout.merge_auto_offers(root, [opportunity], {"apionlyai": {"key": "part_1", "status": "active"}}, "key")
                self.assertEqual(added, ["API Only AI"])
                registry = json.loads((root / "data/partner_offers.json").read_text(encoding="utf-8"))
                self.assertEqual(registry["offers"][0]["tracking_url"], "https://example.com/ref/artificial-one")
            finally:
                scout.partnerstack_links = original

    def test_connected_network_record_replaces_unmonetized_direct_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/partner_offers.json").write_text('{"offers": []}', encoding="utf-8")
            (root / "data/partnerstack_program_audit.json").write_text('{"programs": []}', encoding="utf-8")
            direct = {
                "id": "direct:example", "network": "direct-vendor", "name": "Example AI", "slug": "example-ai",
                "description": "AI software for marketing teams", "offer": "Affiliate program", "tags": ["AI"],
                "application_url": "https://example.com/affiliates", "terms_url": "https://example.com/terms",
                "website": "https://example.com", "waitlist": False, "archived": False, "links_enabled": True,
            }
            monetized = {**direct, "id": "sovrn:example", "network": "sovrn", "approved": True,
                         "tracking_url": "https://sovrn.co/example"}
            original = scout.inspect_policy
            try:
                scout.inspect_policy = lambda _url: {"status": "reviewed", "signals": {}, "cookie_days": None}
                result = scout.prepare_opportunities([direct, monetized], root, {})
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]["network"], "sovrn")
                self.assertEqual(result[0]["state"], "approved_ready_for_auto_onboarding")
            finally:
                scout.inspect_policy = original

    def test_connected_network_tracking_link_enters_offer_pipeline(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "data").mkdir()
            (root / "data/partner_offers.json").write_text('{"version":1,"offers":[]}', encoding="utf-8")
            (root / "data/partnerstack_program_audit.json").write_text('{"version":1,"programs":[],"summary":{}}', encoding="utf-8")
            opportunity = {
                "network": "sovrn", "approved": True, "tracking_url": "https://sovrn.co/example",
                "name": "Example AI", "slug": "example-ai", "description": "AI workflow software for business teams.",
                "tags": ["Artificial Intelligence"], "website": "https://example.com/", "terms_url": "https://sovrn.com/terms",
                "source": "https://developer.sovrn.com/", "policy": {"status": "reviewed"},
            }
            added = scout.merge_auto_offers(root, [opportunity], {}, "")
            self.assertEqual(added, ["Example AI"])
            registry = json.loads((root / "data/partner_offers.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["offers"][0]["tracking_url"], "https://sovrn.co/example")

    def test_awin_categories_and_positioning_match_the_product(self):
        cases = (
            ({"network": "awin", "name": "Rewarx Studio AI", "description": "AI product photos without expensive shoots", "tags": ["Software"]}, "AI product photography"),
            ({"network": "awin", "name": "Alison", "description": "Online education and skills training", "tags": ["Software"]}, "Online learning"),
            ({"network": "awin", "name": "eSign", "description": "Sign PDF and DOCX documents on iOS", "tags": ["Software"]}, "Document signing"),
            ({"network": "awin", "name": "BRKOX", "description": "Display frames for LEGO collectors", "tags": ["Software"]}, "Collectibles & display"),
        )
        for item, expected in cases:
            with self.subTest(item=item["name"]):
                self.assertEqual(scout.category_for(item), expected)

    def test_existing_generated_offer_gets_refreshed_without_changing_manual_offer(self):
        generated = {
            "name": "Alison", "category": "Software", "best_for": "Generic", "why_consider": "Generic",
            "use_cases": ["Generic one", "Generic two"],
            "automation": {"discovered_by": "partner-opportunity-engine"},
        }
        manual = {"name": "Manual Tool", "category": "Hand edited"}
        registry = {"offers": [generated, manual]}
        changed = scout.refresh_auto_offers(registry, [{
            "id": "awin:1", "network": "awin", "name": "Alison",
            "description": "Online education and skills training", "tags": ["Software"],
        }])
        self.assertTrue(changed)
        self.assertEqual(generated["category"], "Online learning")
        self.assertEqual(generated["automation"]["network"], "awin")
        self.assertEqual(manual["category"], "Hand edited")


if __name__ == "__main__":
    unittest.main()
