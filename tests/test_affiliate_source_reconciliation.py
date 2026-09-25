import json
from pathlib import Path
import tempfile
import unittest

from scripts import affiliate_source_reconciliation as reconciliation


class AffiliateSourceReconciliationTests(unittest.TestCase):
    def make_root(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / "data").mkdir()
        (root / "data/partnerstack_program_audit.json").write_text('{"programs": []}', encoding="utf-8")
        (root / "data/appsumo_offers.json").write_text('{"offers": []}', encoding="utf-8")
        return root

    def test_future_connector_is_covered_without_source_specific_code(self):
        root = self.make_root()
        (root / "data/partner_offers.json").write_text('{"version":1,"offers":[]}', encoding="utf-8")
        (root / "data/partner_opportunities.json").write_text(json.dumps({"opportunities": [{
            "id": "future:one", "network": "future-network", "name": "Future AI",
            "approved": True, "tracking_url": "https://example.com/ref", "relationship_state": "publishable",
        }]}), encoding="utf-8")
        payload = reconciliation.reconcile(root)
        self.assertEqual(payload["networks"]["future-network"]["publishable"], 1)
        self.assertEqual(payload["failures"][0]["reason"], "publishable_relationship_missing_public_offer")

    def test_exact_tracking_url_is_required_on_published_page(self):
        root = self.make_root()
        offer = {"id": "example", "slug": "example-ai", "name": "Example AI", "status": "published", "tracking_url": "https://example.com/right"}
        (root / "data/partner_offers.json").write_text(json.dumps({"version": 1, "offers": [offer]}), encoding="utf-8")
        (root / "data/partner_opportunities.json").write_text(json.dumps({"opportunities": [{
            "id": "source:example", "network": "source", "name": "Example AI", "approved": True,
        }]}), encoding="utf-8")
        (root / "partner-offers").mkdir()
        (root / "partner-offers/example-ai.html").write_text('<a href="https://example.com/wrong">Open</a>', encoding="utf-8")
        payload = reconciliation.reconcile(root)
        self.assertEqual(payload["failures"][0]["reason"], "published_page_has_wrong_or_missing_tracking_url")

    def test_appsumo_active_ai_offer_is_reconciled(self):
        root = self.make_root()
        (root / "data/partner_offers.json").write_text('{"version":1,"offers":[]}', encoding="utf-8")
        (root / "data/partner_opportunities.json").write_text('{"opportunities":[]}', encoding="utf-8")
        (root / "data/appsumo_offers.json").write_text(json.dumps({"offers": [{
            "id": "appsumo:test", "name": "Test AI", "availability": "active", "ai_relevant": True,
            "tracking_url": "https://appsumo.example/ref", "editorial_url": "appsumo-guides/test.html",
        }]}), encoding="utf-8")
        (root / "appsumo-guides").mkdir()
        (root / "appsumo-guides/test.html").write_text('<a href="https://appsumo.example/ref">Open</a>', encoding="utf-8")
        payload = reconciliation.reconcile(root)
        self.assertEqual(payload["networks"]["impact-appsumo"]["published"], 1)
        self.assertEqual(payload["failures"], [])

    def test_partnerstack_company_alias_matches_existing_public_offer(self):
        root = self.make_root()
        offer = {
            "id": "elevenlabs", "slug": "elevenlabs-ai-voice", "name": "ElevenLabs",
            "status": "published", "tracking_url": "https://try.elevenlabs.io/ref",
        }
        (root / "data/partner_offers.json").write_text(
            json.dumps({"version": 1, "offers": [offer]}), encoding="utf-8",
        )
        (root / "data/partner_opportunities.json").write_text(json.dumps({"opportunities": [{
            "id": "partnerstack:elevenlabsinc", "network": "partnerstack",
            "name": "Eleven Labs Inc.", "slug": "elevenlabsinc", "approved": True,
            "relationship_state": "active_link_pending",
        }]}), encoding="utf-8")
        (root / "partner-offers").mkdir()
        (root / "partner-offers/elevenlabs-ai-voice.html").write_text(
            '<a href="https://try.elevenlabs.io/ref">Open</a>', encoding="utf-8",
        )
        payload = reconciliation.reconcile(root)
        self.assertEqual(payload["networks"]["partnerstack"]["published"], 1)
        self.assertEqual(payload["activation_blockers"], [])


if __name__ == "__main__":
    unittest.main()
