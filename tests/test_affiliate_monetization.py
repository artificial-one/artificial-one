import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "monetize_affiliate_links.py"
SPEC = importlib.util.spec_from_file_location("monetize_affiliate_links", MODULE_PATH)
monetize = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(monetize)


class AffiliateMonetizationTests(unittest.TestCase):
    def setUp(self):
        self.offers = {
            "descript": {
                "id": "descript",
                "tracking_url": "https://get.descript.com/new",
                "legacy_urls": ["https://get.descript.com/old"],
            }
        }

    def test_normalizes_legacy_affiliate_anchor(self):
        source = '<a class="button" href="https://get.descript.com/old" rel="noopener">Try it</a>'
        result, found = monetize.normalize_links(source, self.offers)
        self.assertEqual(found, {"descript"})
        self.assertIn('rel="noopener nofollow sponsored"', result)
        self.assertIn('data-affiliate-offer=""', result)
        self.assertIn('data-offer-id="descript"', result)

    def test_ordinary_external_link_is_unchanged(self):
        source = '<a href="https://example.com">Example</a>'
        result, found = monetize.normalize_links(source, self.offers)
        self.assertEqual(result, source)
        self.assertEqual(found, set())

    def test_draft_offers_are_never_selected(self):
        registry = {
            "offers": [
                {"id": "draft", "status": "draft", "tracking_url": "https://example.com/draft"},
                {"id": "live", "status": "published", "tracking_url": "https://example.com/live"},
            ]
        }
        self.assertEqual(set(monetize.published_offers(registry)), {"live"})

    def test_contextual_block_has_disclosure_and_tracking(self):
        rule = {"id": "video", "headline": "Try it", "copy": "Useful copy", "cta_label": "Open"}
        offer = {"id": "descript", "slug": "descript", "tracking_url": "https://get.descript.com/new"}
        result = monetize.render_placement(rule, offer)
        self.assertIn('data-placement="video"', result)
        self.assertIn("We may earn a commission", result)
        self.assertIn('rel="nofollow sponsored noopener"', result)
        self.assertIn("partner-offers/descript.html", result)

    def test_tracking_endpoint_is_added_or_replaced(self):
        page = monetize.ROOT / "reviews.html"
        source = '<html><head><meta name="affiliate-event-endpoint" content=""></head><body></body></html>'
        result = monetize.ensure_tracking_endpoint(source, page)
        self.assertEqual(result.count("affiliate-event-endpoint"), 1)
        self.assertIn('content="/api/affiliate-event"', result)


if __name__ == "__main__":
    unittest.main()
