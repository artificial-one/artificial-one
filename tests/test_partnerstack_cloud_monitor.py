import tempfile
import unittest
import json
from pathlib import Path

from scripts.partnerstack_cloud_monitor import (
    _items_from_payload,
    build_snapshot,
    compare_snapshots,
    load_website_coverage,
    reduce_affiliate_click_results,
    render_email_dashboard,
    write_report,
)


class PartnerStackCloudMonitorTests(unittest.TestCase):
    def test_click_store_results_are_reduced_to_aggregates(self):
        result = reduce_affiliate_click_results(
            ["2026-09-14", "2026-09-13"],
            [
                {"result": ["total", "3", "offer:descript", "2", "page:/reviews.html", "3"]},
                {"result": 2},
                {"result": ["total", "4", "offer:descript", "1", "offer:volza", "3"]},
                {"result": 3},
            ],
        )
        self.assertEqual(result["total"], 7)
        self.assertEqual(result["unique_daily_sessions"], 5)
        self.assertEqual(result["by_offer"], {"descript": 3, "volza": 3})

    def test_unwraps_paginated_partner_response(self):
        items, has_more = _items_from_payload(
            {"data": {"items": [{"key": "part_1"}], "has_more": True}}
        )
        self.assertEqual(items, [{"key": "part_1"}])
        self.assertTrue(has_more)

    def test_snapshot_contains_aggregates_but_not_customer_identity(self):
        snapshot = build_snapshot(
            {
                "partnerships": [
                    {"company": {"name": "Volza"}, "approved_status": "approved"}
                ],
                "customers": [
                    {"key": "cus_secret", "email": "private@example.com", "has_paid": True}
                ],
                "transactions": [{"amount_usd": 1250}],
                "rewards": [
                    {"amount": 250, "reward_status": "approved", "payment_status": "available"}
                ],
            },
            audited_at="2026-09-14T09:00:00+00:00",
        )
        encoded = str(snapshot)
        self.assertNotIn("private@example.com", encoded)
        self.assertNotIn("cus_secret", encoded)
        self.assertEqual(snapshot["customers"]["paid_count"], 1)
        self.assertEqual(snapshot["transactions"]["amount_usd_cents"], 1250)
        self.assertEqual(snapshot["rewards"]["amount_usd_cents"], 250)

    def test_detects_funnel_and_partnership_changes(self):
        previous = build_snapshot(
            {
                "partnerships": [{"company": {"name": "Volza"}, "approved_status": "approved"}],
                "customers": [],
                "transactions": [],
                "rewards": [],
            },
            audited_at="before",
        )
        current = build_snapshot(
            {
                "partnerships": [
                    {"company": {"name": "Volza"}, "approved_status": "approved"},
                    {"company": {"name": "Descript"}, "approved_status": "approved"},
                ],
                "customers": [{"has_paid": True}],
                "transactions": [{"amount_usd": 9900}],
                "rewards": [{"amount": 2500, "reward_status": "pending"}],
            },
            audited_at="after",
        )
        changes = compare_snapshots(previous, current)
        rendered = "\n".join(changes)
        self.assertIn("Attributed signups: 0 -> 1", rendered)
        self.assertIn("Attributed revenue: $0.00 -> $99.00", rendered)
        self.assertIn("Commissions: $0.00 -> $25.00", rendered)
        self.assertIn("New partnership: Descript (approved)", rendered)

    def test_timestamp_only_change_is_quiet(self):
        collections = {
            "partnerships": [],
            "customers": [],
            "transactions": [],
            "rewards": [],
        }
        before = build_snapshot(collections, audited_at="before")
        after = build_snapshot(collections, audited_at="after")
        self.assertEqual(compare_snapshots(before, after), [])

    def test_report_contains_no_raw_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            write_report(report, ["Rewards: 0 -> 1"], "https://example.test/run")
            text = report.read_text(encoding="utf-8")
            self.assertIn("Rewards: 0 -> 1", text)
            self.assertIn("review the affected program", text)

    def test_email_dashboard_contains_aggregate_metrics_and_analysis(self):
        current = build_snapshot(
            {
                "partnerships": [{"company": {"name": "Volza"}, "approved_status": "approved"}],
                "customers": [{"key": "cus_private", "email": "private@example.com", "has_paid": True}],
                "transactions": [{"amount_usd": 1250}],
                "rewards": [{"amount": 250, "reward_status": "approved", "payment_status": "available"}],
            },
            audited_at="2026-09-14T09:00:00+00:00",
        )
        subject, text, html = render_email_dashboard(current, [], None, "https://example.test/run")
        combined = subject + text + html
        self.assertIn("Attributed revenue: $12.50", text)
        self.assertIn("Commissions: $2.50", text)
        self.assertIn("Payment statuses: available: 1", text)
        self.assertIn("Baseline initialized", combined)
        self.assertNotIn("private@example.com", combined)
        self.assertNotIn("cus_private", combined)

    def test_email_dashboard_recommends_conversion_follow_up(self):
        previous = build_snapshot({"partnerships": [], "customers": [], "transactions": [], "rewards": []})
        current = build_snapshot(
            {
                "partnerships": [],
                "customers": [{"has_paid": False}],
                "transactions": [],
                "rewards": [],
            }
        )
        _, text, _ = render_email_dashboard(
            current,
            compare_snapshots(previous, current),
            previous,
        )
        self.assertIn("Interest increased without a new paying customer", text)

    def test_website_coverage_is_included_in_email(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = root / "audit.json"
            offers = root / "offers.json"
            placements = root / "placements.json"
            audit.write_text(json.dumps({
                "summary": {"active_programs": 25, "terms_action_required": 0},
                "programs": [
                    {"name": "QuillBot", "website_status": "blocked"},
                    {"name": "Runpod", "website_status": "draft"},
                ],
            }), encoding="utf-8")
            offers.write_text(json.dumps({"offers": [
                {"status": "published"}, {"status": "published"}, {"status": "draft"}
            ]}), encoding="utf-8")
            placements.write_text(json.dumps({"placements": [{"id": "one"}]}), encoding="utf-8")

            coverage = load_website_coverage(audit, offers, placements)
            current = build_snapshot({"partnerships": [], "customers": [], "transactions": [], "rewards": []})
            _, text, html = render_email_dashboard(current, [], None, website_coverage=coverage)

            self.assertIn("Active PartnerStack programs: 25", text)
            self.assertIn("Published partner offers: 2", text)
            self.assertIn("Draft programs: Runpod", text)
            self.assertIn("Blocked programs", html)
            self.assertIn("QuillBot", html)


if __name__ == "__main__":
    unittest.main()
