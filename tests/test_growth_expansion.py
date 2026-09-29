import importlib.util
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


decision = load_module("build_decision_tools")
indexing = load_module("indexing_recovery")
sponsorship = load_module("build_sponsorship")
monitor = load_module("monitor_offer_changes")
search = load_module("search_revenue_engine")


def sample_offer(offer_id="alpha"):
    return {
        "id": offer_id,
        "slug": offer_id,
        "name": offer_id.title(),
        "status": "published",
        "category": "Audio & Video",
        "summary": "A workflow tool for podcast editing.",
        "best_for": "Creators and small teams",
        "tracking_url": f"https://example.com/{offer_id}",
        "cta_label": f"Explore {offer_id.title()}",
        "use_cases": ["Edit podcasts from transcripts"],
        "why_consider": "It supports transcript editing.",
        "watch_out": "Verify current limits.",
    }


class GrowthExpansionTests(unittest.TestCase):
    def test_decision_tools_are_tracked_and_calculators_link_to_root(self):
        pages = decision.planned_pages([sample_offer()])
        self.assertEqual(len(pages), 6)
        stack = pages[decision.ROOT / "ai-stack-builder.html"]
        calculator = pages[decision.ROOT / "calculators" / "voice-production-cost-calculator.html"]
        self.assertIn("WebApplication", stack)
        self.assertIn("data-affiliate-offer", stack)
        self.assertIn('../partner-offers/alpha.html', calculator)
        self.assertIn("Share this calculator", calculator)
        self.assertIn("shared-calculator", calculator)

    def test_sitemap_blocks_are_replaced_without_reordering(self):
        source = '<?xml version="1.0"?><urlset>\n  <!-- before -->\n  <!-- decision-tools:start -->old<!-- decision-tools:end -->\n  <!-- after -->\n</urlset>\n'
        path = decision.ROOT / "decision-tools.html"
        result = decision.update_sitemap(source, [path], "2026-09-15")
        self.assertLess(result.index("before"), result.index("decision-tools:start"))
        self.assertLess(result.index("decision-tools:end"), result.index("after"))
        self.assertEqual(result.count("decision-tools.html"), 1)

    def test_indexnow_payload_uses_public_ownership_key(self):
        self.assertRegex(indexing.INDEXNOW_KEY, r"^[a-z0-9-]{8,128}$")
        updated = indexing.update_sitemap("<urlset>\n</urlset>\n")
        self.assertIn("buyers-guides.html", updated)
        self.assertEqual(updated.count("indexing-recovery:start"), 1)

    def test_google_candidates_include_quality_gated_affiliate_catalogues(self):
        candidates = {path.relative_to(indexing.ROOT).as_posix() for path in indexing.indexing_candidates()}
        self.assertTrue(any(path.startswith("partner-offers/") for path in candidates))
        self.assertTrue(any(path.startswith("news/") for path in candidates))
        self.assertTrue(any(path.startswith("appsumo-guides/") for path in candidates))
        self.assertFalse(any(path.startswith("tools/") for path in candidates))

    def test_priority_sitemap_is_small_and_quality_gated(self):
        candidates = indexing.indexing_candidates()
        accepted, rejected, _incoming = indexing.select_priority_pages(candidates)
        sitemap = indexing.render_priority_sitemap(accepted)
        self.assertIn("partner-offers/foxit-pdf-software.html", sitemap)
        self.assertNotIn("/tools/", sitemap)
        self.assertTrue(any(path.relative_to(indexing.ROOT).as_posix().startswith("appsumo-guides/") for path in accepted))
        self.assertEqual(sitemap.count("<loc>"), len(accepted))
        self.assertTrue(rejected or accepted)

    def test_robots_advertises_google_priority_sitemap(self):
        robots = (indexing.ROOT / "robots.txt").read_text(encoding="utf-8")
        self.assertIn("Sitemap: https://artificial.one/sitemap-priority.xml", robots)
        self.assertNotIn("Sitemap: https://artificial.one/sitemap.xml\n", robots)

    def test_index_issues_publish_paths_only_to_crawl_priority(self):
        public = {"version": 1, "experiments": {}, "crawl_priority": []}
        inspections = [
            {"url": "https://artificial.one/partner-offers/alpha.html", "status": "ISSUE", "detail": "private reason"},
            {"url": "https://artificial.one/about.html", "status": "ISSUE", "detail": "ignored"},
        ]
        actions = search.update_crawl_priority(inspections, public, date(2026, 9, 15))
        self.assertEqual(public["crawl_priority"], ["/partner-offers/alpha.html"])
        self.assertNotIn("private reason", json.dumps(public))
        self.assertEqual(len(actions), 1)

    def test_buyer_hub_highlights_crawl_priority(self):
        page = indexing.ROOT / "partner-offers" / "foxit-pdf-software.html"
        rendered = indexing.render_hub([page], [page])
        self.assertIn("Editor's shortlist", rendered)
        self.assertIn("What are you trying to decide?", rendered)
        self.assertIn('data-guide-search-input', rendered)
        self.assertIn('data-guide-filter="review"', rendered)
        self.assertGreaterEqual(rendered.count("partner-offers/foxit-pdf-software.html"), 2)

    def test_demand_gate_publishes_only_reviewed_concept_id(self):
        original = search.OFFERS_PATH
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "offers.json"
                path.write_text(json.dumps({"offers": [sample_offer()]}), encoding="utf-8")
                search.OFFERS_PATH = path
                public = {"version": 1, "experiments": {}, "demand_pages": []}
                private = {"version": 1}
                rows = [{"keys": ["https://artificial.one/partner-offers/alpha.html", "alpha edit podcasts from transcripts secret"], "impressions": 35}]
                actions = search.update_demand_pages(rows, public, private, date(2026, 9, 15))
                self.assertEqual(public["demand_pages"], ["alpha-use-case-1"])
                self.assertNotIn("secret", json.dumps(public))
                self.assertEqual(len(actions), 1)
                self.assertIn("impressions", json.dumps(private))
        finally:
            search.OFFERS_PATH = original

    def test_offer_monitor_requires_two_matching_change_observations(self):
        original = monitor.fetch_offer
        state = {"version": 1, "offers": {}}
        offer = sample_offer()
        try:
            monitor.fetch_offer = lambda _offer: ("alpha", "https://example.com", "one")
            alerts, _ = monitor.observe([offer], state, date(2026, 9, 13))
            self.assertEqual(alerts, [])
            monitor.fetch_offer = lambda _offer: ("alpha", "https://example.com", "two")
            alerts, _ = monitor.observe([offer], state, date(2026, 9, 14))
            self.assertEqual(alerts, [])
            alerts, _ = monitor.observe([offer], state, date(2026, 9, 15))
            self.assertEqual(len(alerts), 1)
        finally:
            monitor.fetch_offer = original

    def test_sponsorship_intake_is_noindex_and_checkout_defaults_off(self):
        inventory = sponsorship.load_inventory()
        self.assertFalse(inventory["checkout_enabled"])
        self.assertIn('name="robots" content="noindex,nofollow"', sponsorship.render_success())


if __name__ == "__main__":
    unittest.main()
