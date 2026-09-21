import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_search_revenue_pages.py"
SPEC = importlib.util.spec_from_file_location("build_search_revenue_pages", MODULE_PATH)
pages = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pages)


def offer(offer_id, category="Productivity"):
    return {
        "id": offer_id,
        "slug": offer_id,
        "name": offer_id.title(),
        "category": category,
        "summary": "A reviewed workflow tool.",
        "best_for": "Teams choosing software",
        "pricing_note": "Check current pricing.",
        "tracking_url": f"https://example.com/{offer_id}?ref=artificial-one",
        "cta_label": f"Explore {offer_id.title()}",
        "why_consider": "It supports a focused workflow.",
        "watch_out": "Verify the current limits.",
        "use_cases": ["Automate a recurring team workflow"],
    }


class SearchRevenuePageTests(unittest.TestCase):
    def test_generator_covers_alternatives_comparison_and_use_case(self):
        generated = pages.planned_pages([offer("alpha"), offer("beta")])
        names = {path.name for path in generated}
        self.assertIn("alpha-alternatives.html", names)
        self.assertIn("alpha-pricing.html", names)
        self.assertIn("alpha-for-automate-a-recurring-team-workflow.html", names)
        self.assertIn("best-productivity-tools.html", names)
        self.assertIn("alpha-vs-beta.html", names)
        self.assertIn("alpha-value-calculator.html", names)

    def test_priority_pricing_page_uses_reviewed_notes_and_tracked_cta(self):
        html = pages.render_pricing(offer("alpha"))
        self.assertIn("Check current pricing", html)
        self.assertIn("data-affiliate-offer", html)
        self.assertIn('data-placement="pricing-primary"', html)
        self.assertNotIn("$", html)

    def test_pages_have_schema_review_links_and_tracked_ctas(self):
        html = pages.render_comparison(offer("alpha"), offer("beta"))
        self.assertIn('type="application/ld+json"', html)
        self.assertIn("Read review", html)
        self.assertIn("data-affiliate-offer", html)
        self.assertIn('data-placement="comparison-left"', html)

    def test_value_calculator_uses_reviewed_inputs_and_tracked_result(self):
        html = pages.render_value_calculator(offer("alpha"))
        self.assertIn('id="hours-saved"', html)
        self.assertIn('id="roi-value"', html)
        self.assertIn("Verify the current limits", html)
        self.assertIn('data-placement="value-calculator-result"', html)
        self.assertIn("hours saved × hourly value", html)

    def test_context_routes_point_to_guides_and_calculators(self):
        catalog = pages.route_catalog([offer(f"tool-{index}") for index in range(8)])
        self.assertEqual(len(catalog["routes"]), pages.COLD_START_CLUSTER_SIZE)
        self.assertTrue(all(route["url"].startswith("/partner-offers/") for route in catalog["routes"]))
        self.assertTrue(all(route["calculator_url"].startswith("/calculators/") for route in catalog["routes"]))
        self.assertTrue(all(route["strong_keywords"] for route in catalog["routes"]))
        self.assertTrue(all(route["keywords"] for route in catalog["routes"]))

    def test_sitemap_replaces_managed_block(self):
        source = '<?xml version="1.0"?><urlset>\n  <!-- search-revenue:start -->old  <!-- search-revenue:end -->\n</urlset>'
        root = pages.ROOT
        path = root / "search-intent" / "example.html"
        result = pages.update_sitemap(source, [path], "2026-09-15")
        self.assertEqual(result.count("search-revenue:start"), 1)
        self.assertEqual(result.count("example.html"), 1)

    def test_only_obsolete_value_calculators_are_removed_from_shared_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            current = directory / "current-value-calculator.html"
            stale = directory / "stale-value-calculator.html"
            unrelated = directory / "ai-roi-calculator.html"
            for path in (current, stale, unrelated):
                path.write_text("generated", encoding="utf-8")
            self.assertEqual(
                pages.stale_value_calculators({current}, directory),
                {stale},
            )

    def test_search_priority_controls_generated_page_order(self):
        original = pages.SEARCH_STRATEGY_PATH
        with tempfile.TemporaryDirectory() as folder:
            strategy = Path(folder) / "search.json"
            strategy.write_text('{"version":1,"content_priority":["beta"]}', encoding="utf-8")
            pages.SEARCH_STRATEGY_PATH = strategy
            try:
                ordered = pages.apply_search_priority([offer("alpha"), offer("beta")])
            finally:
                pages.SEARCH_STRATEGY_PATH = original
        self.assertEqual([item["id"] for item in ordered], ["beta", "alpha"])

    def test_demand_selected_use_case_uses_reviewed_copy(self):
        original = pages.SEARCH_STRATEGY_PATH
        with tempfile.TemporaryDirectory() as folder:
            strategy = Path(folder) / "search.json"
            strategy.write_text('{"version":1,"demand_pages":["alpha-use-case-1"]}', encoding="utf-8")
            pages.SEARCH_STRATEGY_PATH = strategy
            try:
                generated = pages.planned_pages([offer("alpha"), offer("beta")])
            finally:
                pages.SEARCH_STRATEGY_PATH = original
        names = {path.name for path in generated}
        self.assertIn("alpha-for-automate-a-recurring-team-workflow.html", names)


if __name__ == "__main__":
    unittest.main()
