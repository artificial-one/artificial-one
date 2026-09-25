import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.daily_executive_report import (
    daily_activity, live_affiliate_destinations, owner_actions, render,
    social_posts_for_day, social_posts_for_window, system_work, verified_sender,
    wait_for_delivery, PRAGUE,
)


class DailyExecutiveReportTests(unittest.TestCase):
    def test_verified_sender_prefers_artificial_one_domain(self):
        with patch("scripts.daily_executive_report.resend_json", return_value={"data": [
            {"name": "other.example", "status": "verified"},
            {"name": "artificial.one", "status": "verified"},
        ]}):
            sender = verified_sender("secret", "Artificial.One <onboarding@resend.dev>")
        self.assertEqual(sender, "Artificial.One Daily Brief <reports@artificial.one>")

    def test_delivery_wait_requires_real_delivery_event(self):
        with patch("scripts.daily_executive_report.resend_json", side_effect=[
            {"last_event": "sent"}, {"last_event": "delivered"},
        ]), patch("scripts.daily_executive_report.time.sleep"):
            self.assertEqual(wait_for_delivery("secret", "email-id", wait_seconds=90), "delivered")

    def test_delivery_wait_rejects_bounce(self):
        with patch("scripts.daily_executive_report.resend_json", return_value={"last_event": "bounced"}):
            with self.assertRaisesRegex(RuntimeError, "bounced"):
                wait_for_delivery("secret", "email-id", wait_seconds=0)

    def test_delivery_wait_tolerates_send_only_api_key(self):
        error = HTTPError("https://api.resend.com/emails/id", 401, "Unauthorized", None, None)
        with patch("scripts.daily_executive_report.resend_json", side_effect=error):
            self.assertEqual(
                wait_for_delivery("secret", "email-id", wait_seconds=0),
                "accepted_unverified",
            )

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
            "impact_actions": 0, "paying_customers": 0, "partnerstack_transactions": 0, "revenue": "USD 0.00",
            "commissions": "USD 0.00", "owner_actions": [], "system_queue": 8,
            "blocking_failures": 0, "health": {"status": "healthy", "healthy": 10, "attention": 0},
            "social": {},
        }
        subject, text, html = render(model)
        self.assertIn("daily business brief", subject)
        self.assertIn("No action required", text)
        self.assertIn("#f4f1fb", html)
        self.assertIn("senior-management", html)
        self.assertNotIn("workflow run", text.casefold())
        self.assertNotIn("cache", text.casefold())
        self.assertIn("last 28 days", text)
        self.assertIn("PartnerStack referred sign-ups (since tracking began)", text)
        self.assertIn("inventory and traffic", html)
        self.assertIn("Impact tracked lead or sale events", text)
        self.assertNotIn("attributed actions", text)
        self.assertNotIn("monetized offers under coverage", text)
        self.assertNotIn("All catalogues stayed current", text)
        self.assertIn("GOOGLE SEARCH AND INDEXING", text)

    def test_report_explains_google_indexing_with_period_and_issues(self):
        model = {
            "date": date(2026, 9, 25),
            "activity": {"pages_created": 0, "pages_updated": 0, "social_posts": 0, "highlights": []},
            "published_offers": 2, "visits": 50, "clicks": 4, "signups": 0,
            "impact_actions": 0, "paying_customers": 0, "partnerstack_transactions": 0,
            "revenue": "USD 0.00", "commissions": "USD 0.00", "owner_actions": [],
            "system_work": [], "health": {"status": "healthy", "healthy": 10, "attention": 0, "issues": []},
            "social": {},
            "search": {
                "period": {"start": "2026-08-25", "end": "2026-09-21", "data_lag_days": 3},
                "performance": {
                    "current": {"clicks": 12, "impressions": 600, "ctr": .02, "position": 8.4},
                    "previous": {"clicks": 6, "impressions": 400, "ctr": .015, "position": 10.2},
                },
                "sitemap": {"counts_available": True, "submitted": 120, "indexed": 87, "errors": 0, "warnings": 1},
                "indexing": {"affiliate_pages": 40, "indexed": 38, "inspected": 40, "issues": 2, "complete": True, "newly_indexed": ["one"], "lost_indexing": [], "issue_details": [
                    {"url": "https://artificial.one/partner-offers/broken.html", "detail": "Crawled - currently not indexed"}
                ]},
                "commercial_search": {"pages_with_impressions": 9, "top_pages": []},
            },
        }
        _, text, html = render(model)
        self.assertIn("Sitemap indexed/submitted: 87 / 120", text)
        self.assertIn("Affiliate pages checked: 40/40", text)
        self.assertIn("Are our affiliate pages indexed and healthy?", html)
        self.assertIn("2026-08-25 to 2026-09-21", html)
        self.assertIn("Crawled - currently not indexed", html)
        self.assertIn("Open Google Search Console", html)

    def test_every_owner_decision_is_rendered_without_grouping(self):
        actions = [
            {"title": f"Decision {index}", "detail": "Accept terms", "url": f"https://example.com/{index}"}
            for index in range(9)
        ]
        model = {
            "date": date(2026, 9, 25),
            "activity": {"pages_created": 0, "pages_updated": 0, "social_posts": 0, "highlights": []},
            "published_offers": 2, "visits": 50, "clicks": 4, "signups": 1,
            "impact_actions": 0, "paying_customers": 0, "partnerstack_transactions": 0, "revenue": "USD 0.00",
            "commissions": "USD 0.00", "owner_actions": actions, "system_work": [],
            "health": {"status": "healthy", "healthy": 10, "attention": 0, "issues": []},
            "social": {},
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
        work = system_work(reconciliation, opportunities)
        self.assertEqual([item["title"] for item in work], ["One", "Two"])
        self.assertIn("07:41 Prague time", work[0]["detail"])
        self.assertIn("no guaranteed completion date", work[0]["detail"].casefold())

    def test_social_section_lists_every_post_for_report_day_with_links_and_metrics(self):
        receipts = {"receipts": [
            {
                "id": "bluesky:at://did:example/app.bsky.feed.post/one",
                "platform": "bluesky", "title": "Blue post",
                "published_at": "2026-09-25T08:00:00Z", "url": "https://bsky.app/post/one",
            },
            {
                "id": "linkedin:urn:li:share:123", "platform": "linkedin", "title": "Linked post",
                "published_at": "2026-09-25T09:00:00Z", "url": "https://linkedin.example/123",
            },
            {
                "id": "linkedin:urn:li:share:old", "platform": "linkedin", "title": "Old",
                "published_at": "2026-09-24T09:00:00Z", "url": "https://linkedin.example/old",
            },
        ]}
        metrics = {
            "at://did:example/app.bsky.feed.post/one": {"likes": 4, "comments": 2, "reposts": 1},
            "urn:li:share:123": {"likes": 7, "comments": 3, "reposts": 2, "views": 80},
        }
        result = social_posts_for_day(receipts, date(2026, 9, 25), metrics)
        self.assertEqual([item["title"] for item in result["linkedin"]], ["Linked post"])
        self.assertEqual(result["linkedin"][0]["metrics"]["views"], 80)
        self.assertEqual(result["bluesky"][0]["url"], "https://bsky.app/post/one")

    def test_social_rolling_window_includes_previous_calendar_day(self):
        receipts = {"receipts": [
            {
                "id": "linkedin:urn:li:share:recent", "platform": "linkedin", "title": "Recent",
                "published_at": "2026-09-24T20:00:00Z", "url": "https://linkedin.example/recent",
            },
            {
                "id": "linkedin:urn:li:share:old", "platform": "linkedin", "title": "Old",
                "published_at": "2026-09-23T20:00:00Z", "url": "https://linkedin.example/old",
            },
        ]}
        result = social_posts_for_window(
            receipts, datetime(2026, 9, 25, 3, 0, tzinfo=PRAGUE), {},
        )
        self.assertEqual([item["title"] for item in result["linkedin"]], ["Recent"])


if __name__ == "__main__":
    unittest.main()
