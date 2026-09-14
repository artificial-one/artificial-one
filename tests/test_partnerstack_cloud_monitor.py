import tempfile
import unittest
from pathlib import Path

from scripts.partnerstack_cloud_monitor import (
    _items_from_payload,
    build_snapshot,
    compare_snapshots,
    write_report,
)


class PartnerStackCloudMonitorTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
