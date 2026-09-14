import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_partner_offers.py"
SPEC = importlib.util.spec_from_file_location("build_partner_offers", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pipeline)


def published_offer(**overrides):
    offer = {
        "id": "useful-ai",
        "slug": "useful-ai",
        "name": "Useful AI",
        "status": "published",
        "category": "Productivity",
        "summary": "A useful product.",
        "best_for": "Small teams",
        "offer_label": "20% off",
        "pricing_note": "Verify current pricing",
        "tracking_url": "https://example.com/?ref=artificial-one",
        "review_url": "tools/useful-ai-review.html",
        "cta_label": "View offer",
        "featured": True,
        "sponsored": True,
        "approved_at": "2026-09-14",
        "terms_verified_at": "2026-09-14",
        "expires_at": "2026-12-31",
        "why_consider": "It combines related tasks in one workflow.",
        "watch_out": "Verify that the current plan limits match your needs.",
        "use_cases": ["Draft a document", "Summarize a meeting"],
        "evidence": [{"label": "Offer terms", "url": "https://example.com/terms"}],
    }
    offer.update(overrides)
    return offer


class PartnerOfferPipelineTests(unittest.TestCase):
    def test_drafts_do_not_publish(self):
        data = {"version": 1, "updated_at": "2026-09-14", "offers": [published_offer(status="draft")]}
        offers = pipeline.validate_registry(data)
        self.assertEqual(pipeline.public_offers(offers, date(2026, 9, 14)), [])

    def test_valid_published_offer_renders_safe_commercial_link(self):
        data = {"version": 1, "updated_at": "2026-09-14", "offers": [published_offer()]}
        offers = pipeline.public_offers(pipeline.validate_registry(data), date(2026, 9, 14))
        page = pipeline.render_offer(offers[0])
        self.assertIn('rel="nofollow sponsored noopener"', page)
        self.assertIn('data-offer-id="useful-ai"', page)
        self.assertIn('data-placement="offer-page-bottom"', page)
        self.assertIn("Use Cases, Fit &amp; Partner Offer", page)
        self.assertIn('type="application/ld+json"', page)

    def test_related_offers_prioritize_same_category(self):
        primary = published_offer()
        same = published_offer(id="same", slug="same", name="Same", featured=False)
        other = published_offer(
            id="other", slug="other", name="Other", category="Audio", featured=True
        )
        related = pipeline.related_offers_for(primary, [primary, other, same])
        self.assertEqual([item["id"] for item in related], ["same", "other"])

    def test_revenue_strategy_controls_offer_order(self):
        first = published_offer(id="first", slug="first", name="First")
        second = published_offer(id="second", slug="second", name="Second")
        original = pipeline.STRATEGY_PATH
        with tempfile.TemporaryDirectory() as folder:
            strategy = Path(folder) / "strategy.json"
            strategy.write_text('{"version":1,"ranking":["second","first"]}', encoding="utf-8")
            pipeline.STRATEGY_PATH = strategy
            try:
                ordered = pipeline.apply_revenue_strategy([first, second])
            finally:
                pipeline.STRATEGY_PATH = original
        self.assertEqual([item["id"] for item in ordered], ["second", "first"])

    def test_finder_contains_direct_tracked_cta(self):
        page = pipeline.render_finder([published_offer()])
        self.assertIn("What do you want to accomplish?", page)
        self.assertIn('data-placement="tool-finder"', page)
        self.assertIn('data-offer-id="useful-ai"', page)
        self.assertIn("affiliate-tracking.js", page)

    def test_review_page_links_to_search_intent_cluster(self):
        first = published_offer(id="first", slug="first", name="First")
        second = published_offer(id="second", slug="second", name="Second")
        links = pipeline.search_links_for(first, [first, second])
        page = pipeline.render_offer(first, [], links)
        self.assertIn("../search-intent/first-alternatives.html", page)
        self.assertIn("../search-intent/best-productivity-tools.html", page)
        self.assertIn("../search-intent/first-vs-second.html", page)

    def test_published_offer_requires_approval(self):
        data = {"version": 1, "updated_at": "2026-09-14", "offers": [published_offer(approved_at=None)]}
        with self.assertRaises(pipeline.OfferValidationError):
            pipeline.validate_registry(data)

    def test_published_offer_requires_concrete_use_cases(self):
        data = {
            "version": 1,
            "updated_at": "2026-09-14",
            "offers": [published_offer(use_cases=["Only one"])],
        }
        with self.assertRaises(pipeline.OfferValidationError):
            pipeline.validate_registry(data)

    def test_duplicate_slug_is_rejected(self):
        second = published_offer(id="other-ai")
        data = {"version": 1, "updated_at": "2026-09-14", "offers": [published_offer(), second]}
        with self.assertRaises(pipeline.OfferValidationError):
            pipeline.validate_registry(data)

    def test_expired_offer_is_not_public(self):
        data = {"version": 1, "updated_at": "2026-09-14", "offers": [published_offer(expires_at="2026-09-13")]}
        offers = pipeline.validate_registry(data)
        self.assertEqual(pipeline.public_offers(offers, date(2026, 9, 14)), [])

    def test_registry_content_is_html_escaped(self):
        dangerous = published_offer(name='<script>alert("x")</script>')
        data = {"version": 1, "updated_at": "2026-09-14", "offers": [dangerous]}
        offer = pipeline.public_offers(pipeline.validate_registry(data), date(2026, 9, 14))[0]
        page = pipeline.render_offer(offer)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertIn("&lt;script&gt;", page)

    def test_review_path_cannot_escape_site(self):
        unsafe = published_offer(review_url="tools/../../private.txt")
        data = {"version": 1, "updated_at": "2026-09-14", "offers": [unsafe]}
        with self.assertRaises(pipeline.OfferValidationError):
            pipeline.validate_registry(data)

    def test_registry_requires_updated_date(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "offers.json"
            path.write_text('{"version": 1, "offers": []}', encoding="utf-8")
            with self.assertRaises(pipeline.OfferValidationError):
                pipeline.load_registry(path)

    def test_sitemap_sync_deduplicates_managed_pages(self):
        current = """<?xml version=\"1.0\"?><urlset>
  <url><loc>https://artificial.one/partners.html</loc><priority>0.5</priority></url>
  <url><loc>https://artificial.one/about.html</loc><priority>0.5</priority></url>
</urlset>"""
        block = pipeline.sitemap_block([], "2026-09-14")
        result = pipeline.expected_sitemap(current, block)
        self.assertEqual(result.count("https://artificial.one/partners.html"), 1)
        self.assertEqual(result.count("https://artificial.one/partner-offers.html"), 1)
        self.assertEqual(result.count("https://artificial.one/about.html"), 1)


if __name__ == "__main__":
    unittest.main()
