import unittest

from scripts import build_business_activity_diary as diary


class BusinessActivityDiaryTests(unittest.TestCase):
    def test_public_page_filter_excludes_internal_and_documentation_pages(self):
        self.assertTrue(diary.public_html("partner-offers/example.html"))
        self.assertTrue(diary.public_html("index.html"))
        self.assertFalse(diary.public_html("partner-opportunities.html"))
        self.assertFalse(diary.public_html("newsletter/latest.html"))
        self.assertFalse(diary.public_html("docs/internal.html"))
        self.assertFalse(diary.public_html("scripts/example.py"))

    def test_new_records_returns_only_business_additions(self):
        before = {"offers": [{"id": "old", "name": "Old"}]}
        after = {"offers": [{"id": "old", "name": "Old"}, {"id": "new", "name": "New"}]}
        self.assertEqual(diary.new_records(before, after, "offers", "id"), [{"id": "new", "name": "New"}])

    def test_document_explains_connected_and_excluded_activity(self):
        payload = {
            "history_begins": "2026-09-15",
            "last_activity_at": "2026-09-22T12:00:00+02:00",
            "entries": [{
                "id": "one", "date": "2026-09-22", "occurred_at": "2026-09-22T12:00:00+02:00",
                "kind": "webpage_created", "summary": "Published webpage: Example",
                "url": "https://artificial.one/example.html",
            }],
        }
        rendered = diary.render_markdown(payload)
        self.assertIn("Published webpage: Example", rendered)
        self.assertIn("Beehiiv newsletter delivery", rendered)
        self.assertIn("Excluded noise", rendered)
        self.assertNotIn("unit tests passed", rendered)


if __name__ == "__main__":
    unittest.main()
