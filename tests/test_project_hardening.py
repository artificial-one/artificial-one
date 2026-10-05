import json
from pathlib import Path
import unittest

from scripts.affiliate_catalog import COMMERCIAL_CORE_IDS, is_ai_relevant
from scripts import build_partner_offers, indexing_recovery


ROOT = Path(__file__).resolve().parents[1]


class ProjectHardeningTests(unittest.TestCase):
    def test_commercial_core_has_thirty_live_source_backed_pages(self):
        registry = json.loads((ROOT / "data" / "partner_offers.json").read_text(encoding="utf-8"))
        offers = {item["id"]: item for item in registry["offers"] if item.get("status") == "published"}
        self.assertEqual(30, len(COMMERCIAL_CORE_IDS))
        for offer_id in COMMERCIAL_CORE_IDS:
            self.assertIn(offer_id, offers)
            page = (ROOT / "partner-offers" / f"{offers[offer_id]['slug']}.html").read_text(encoding="utf-8")
            self.assertIn("Your seven-day proof plan", page)
            self.assertIn("Evidence dossier", page)
            self.assertIn("Primary sources", page)

    def test_commercial_core_preserves_behavioral_revenue_order(self):
        registry = json.loads((ROOT / "data" / "partner_offers.json").read_text(encoding="utf-8"))
        core = [
            item
            for item in registry["offers"]
            if item.get("status") == "published" and item["id"] in COMMERCIAL_CORE_IDS
        ]
        self.assertGreaterEqual(len(core), 2)
        deliberately_ranked = [core[1], core[0], *core[2:]]
        rendered = build_partner_offers.render_commercial_core(deliberately_ranked)
        first_marker = f'data-offer-id="{core[1]["id"]}"'
        second_marker = f'data-offer-id="{core[0]["id"]}"'
        self.assertLess(rendered.index(first_marker), rendered.index(second_marker))

    def test_non_ai_commercial_relationships_stay_out_of_ai_sitemap(self):
        registry = json.loads((ROOT / "data" / "partner_offers.json").read_text(encoding="utf-8"))
        non_ai = [item for item in registry["offers"] if item.get("status") == "published" and not is_ai_relevant(item)]
        sitemap = (ROOT / "sitemap-priority.xml").read_text(encoding="utf-8")
        self.assertGreater(len(non_ai), 0)
        for offer in non_ai:
            self.assertNotIn(f"/partner-offers/{offer['slug']}.html", sitemap)
            self.assertTrue((ROOT / "partner-offers" / f"{offer['slug']}.html").exists())

    def test_google_priority_catalogue_is_deliberate_not_every_page(self):
        candidates = indexing_recovery.indexing_candidates()
        self.assertLess(len(candidates), len(list(ROOT.rglob("*.html"))))
        self.assertIn(ROOT / "ai-software-shortlist.html", candidates)

    def test_priority_index_is_capped_and_contains_the_price_tracker(self):
        priority = json.loads((ROOT / "data" / "indexing_priority.json").read_text(encoding="utf-8"))
        self.assertLessEqual(priority["included"], indexing_recovery.PRIORITY_LIMIT)
        self.assertGreaterEqual(priority["included"], 120)
        self.assertIn("ai-software-price-tracker.html", priority["included_paths"])

    def test_deploy_batching_preserves_human_release_deploys(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertEqual("node scripts/vercel-ignore-build.mjs", config["ignoreCommand"])
        script = (ROOT / "scripts" / "vercel-ignore-build.mjs").read_text(encoding="utf-8")
        self.assertIn("[release]", script)
        self.assertIn("[skip ci]", script)

    def test_linkedin_metrics_have_the_verified_organization_fallback(self):
        source = (ROOT / "scripts" / "daily_executive_report.py").read_text(encoding="utf-8")
        self.assertIn("urn:li:organization:145231312", source)
        self.assertIn("persist_private_ledger", source)


if __name__ == "__main__":
    unittest.main()
