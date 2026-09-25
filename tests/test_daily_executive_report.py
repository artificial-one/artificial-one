import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.daily_executive_report import daily_activity, live_affiliate_destinations, owner_actions, render, system_work


class DailyExecutiveReportTests(unittest.TestCase):
    def test_daily_activity_contains_only_requested_day(self):
        payload = {"entries": [
            {"date": "2026-09-25", "kind": "webpage_created", "path": "one.html", "summary": "Published One"},
            {"date": "2026-09-24", "kind": "webpage_created", "path": "old.html", "summary": "Published Old"},
            {"date": "2026-09-25", "kind": "social_post_published", "summary": "Published LinkedIn post"},
        ]}
        result = daily_activity(payload, "2026-09-25")
        self.assertEqual(result["pages_created"], 1)
        self.assertEqual(result["social_posts"], 1)
        self.assertNotIn("Old", str(result))

    def test_owner_actions_exclude_machine_managed_link_queue(self):
        reconciliation = {"activation_blockers": [
            {"source_id": "partnerstack:legal", "reason": "terms_required"},
            {"source_id": "partnerstack:link", "reason": "active_link_pending"},
        ]}
        opportunities = {"opportunities": [
            {"id": "partnerstack:legal", "name": "Legal Tool", "application_url": "https://example.com/legal"},
            {"id": "partnerstack:link", "name": "Link Tool", "application_url": "https://example.com/link"},
        ]}
        actions = owner_actions(reconciliation, opportunities)
        self.assertEqual(len(actions), 1)
        self.assertIn("Legal Tool", actions[0]["title"])

    def test_report_is_management_readable_and_pastel(self):
        model = {
            "date": date(2026, 9, 25),
            "activity": {"pages_created": 2, "pages_updated": 3, "social_posts": 1, "highlights": []},
            "published_offers": 277, "visits": 50, "clicks": 4, "signups": 1,
            "impact_actions": 0, "paying_customers": 0, "revenue": "USD 0.00",
            "commissions": "USD 0.00", "owner_actions": [], "system_queue": 8,
            "blocking_failures": 0, "health": {"status": "healthy", "healthy": 10, "attention": 0},
        }
        subject, text, html = render(model)
        self.assertIn("daily business brief", subject)
        self.assertIn("No action required", text)
        self.assertIn("#f4f1fb", html)
        self.assertIn("senior-management", html)
        self.assertNotIn("workflow run", text.casefold())
        self.assertNotIn("cache", text.casefold())
        self.assertIn("last 28 days", text)
        self.assertIn("sign-ups or purchase events", text)
        self.assertNotIn("attributed actions", text)
        self.assertNotIn("monetized offers under coverage", text)
        self.assertNotIn("All catalogues stayed current", text)

    def test_every_owner_decision_is_rendered_without_grouping(self):
        actions = [
            {"title": f"Decision {index}", "detail": "Accept terms", "url": f"https://example.com/{index}"}
            for index in range(9)
        ]
        model = {
            "date": date(2026, 9, 25),
            "activity": {"pages_created": 0, "pages_updated": 0, "social_posts": 0, "highlights": []},
            "published_offers": 2, "visits": 50, "clicks": 4, "signups": 1,
            "impact_actions": 0, "paying_customers": 0, "revenue": "USD 0.00",
            "commissions": "USD 0.00", "owner_actions": actions, "system_work": [],
            "health": {"status": "healthy", "healthy": 10, "attention": 0, "issues": []},
        }
        _, text, html = render(model)
        self.assertIn("Decision 8", html)
        self.assertIn("Decision 8", text)
        self.assertNotIn("similar term decisions", html)
        self.assertNotIn("You will never be asked", html)

    def test_live_destination_count_is_unique_and_ai_relevant(self):
        partners = {"offers": [
            {"status": "published", "tracking_url": "https://example.com/a"},
            {"status": "published", "tracking_url": "https://example.com/a"},
        ]}
        appsumo = {"offers": [
            {"availability": "active", "ai_relevant": True, "editorial_url": "guide.html", "tracking_url": "https://example.com/b"},
            {"availability": "active", "ai_relevant": False, "editorial_url": "other.html", "tracking_url": "https://example.com/c"},
        ]}
        self.assertEqual(live_affiliate_destinations(partners, appsumo), 2)

    def test_machine_work_names_every_pending_approved_program(self):
        reconciliation = {"activation_blockers": [
            {"source_id": "partnerstack:one", "reason": "active_link_pending"},
            {"source_id": "partnerstack:two", "reason": "active_link_pending"},
        ]}
        opportunities = {"opportunities": [
            {"id": "partnerstack:one", "name": "One"},
            {"id": "partnerstack:two", "name": "Two"},
        ]}
        self.assertEqual([item["title"] for item in system_work(reconciliation, opportunities)], ["One", "Two"])


if __name__ == "__main__":
    unittest.main()
