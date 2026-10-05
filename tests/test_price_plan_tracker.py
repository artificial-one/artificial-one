import unittest

from scripts import build_price_plan_tracker as tracker


class PricePlanTrackerTests(unittest.TestCase):
    def test_tracker_covers_commercial_core_without_invented_fields(self):
        records = tracker.tracker_records()
        self.assertEqual(len(records), 30)
        self.assertTrue(all(item["terms_checked"] for item in records))
        self.assertTrue(all(item["evidence_sources"] >= 1 for item in records))
        self.assertTrue(all(item["guide_url"].startswith("partner-offers/") for item in records))

    def test_tracker_page_is_searchable_and_downloadable(self):
        page = tracker.render_page(tracker.tracker_records())
        self.assertIn("data-tracker-search", page)
        self.assertIn("ai-software-price-tracker.csv", page)
        self.assertIn("Open evidence dossier", page)


if __name__ == "__main__":
    unittest.main()
