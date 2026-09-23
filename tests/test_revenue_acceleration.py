import importlib.util
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(value)
    return value


newsletter = module("publish_newsletter")
distribution = module("distribute_content")
paid = module("paid_acquisition")


class RevenueAccelerationTests(unittest.TestCase):
    def test_newsletter_is_deterministic_and_disclosed(self):
        first = newsletter.build_edition(date(2026, 9, 15))
        second = newsletter.build_edition(date(2026, 9, 15))
        self.assertEqual(first[2], second[2])
        self.assertIn("affiliate", first[1].casefold())
        self.assertIn("utm_source=newsletter", first[1])

    def test_distribution_queue_uses_attributed_site_links(self):
        items = distribution.queue(date(2026, 9, 15))
        self.assertTrue(items)
        self.assertTrue(all("artificial.one" in item["url"] for item in items))
        self.assertTrue(all("utm_source=distribution" in item["url"] for item in items))
        self.assertTrue(all(item["image"].startswith("https://artificial.one/images/social-cards/") for item in items))
        self.assertTrue(all(item["image_alt"] for item in items))
        self.assertTrue(all("utm_" not in item["text"] for item in items))

    def test_daily_editorial_is_fresh_deterministic_and_rotates(self):
        first = distribution.queue(date(2026, 9, 14))[0]
        repeated = distribution.queue(date(2026, 9, 14))[0]
        next_day = distribution.queue(date(2026, 9, 15))[0]
        self.assertEqual(first, repeated)
        self.assertNotEqual(first["id"], next_day["id"])
        self.assertNotEqual(first["text"], next_day["text"])
        self.assertIn("utm_content=2026-09-14", first["url"])
        self.assertIn("utm_content=2026-09-15", next_day["url"])
        self.assertEqual(first["image_key"], "daily-editorial")
        self.assertEqual(first["daily"], "true")
        self.assertTrue(first["vertical_image"].endswith("daily-editorial-vertical.jpg"))
        self.assertEqual(len(first["thread"]), 2)
        self.assertTrue(all(0 < len(reply) <= 295 for reply in first["thread"]))

    def test_editorial_calendar_covers_all_seven_content_slots(self):
        kinds = {distribution.queue(date(2026, 9, 14 + offset))[0]["kind"] for offset in range(7)}
        self.assertTrue({"free-tool", "ai-news", "partner-guide", "offer-update"}.issubset(kinds))

    def test_channel_delivery_replaces_generic_source(self):
        item = distribution.queue()[0]
        delivered = distribution.channel_item(item, "bluesky")
        self.assertIn("utm_source=bluesky", delivered["url"])
        self.assertNotIn(delivered["url"], delivered["text"])

    def test_bluesky_post_uses_clickable_visual_card(self):
        item = distribution.channel_item(distribution.queue()[0], "bluesky")
        thumbnail = {"$type": "blob", "ref": {"$link": "example"}, "mimeType": "image/jpeg", "size": 123}
        record = distribution.bluesky_record(item, thumbnail)
        self.assertEqual(record["embed"]["$type"], "app.bsky.embed.external")
        self.assertEqual(record["embed"]["external"]["uri"], item["url"])
        self.assertEqual(record["embed"]["external"]["thumb"], thumbnail)
        self.assertEqual(record["langs"], ["en"])

    def test_bluesky_replies_form_one_rooted_thread(self):
        root = {"uri": "at://did/root", "cid": "root-cid"}
        parent = {"uri": "at://did/parent", "cid": "parent-cid"}
        record = distribution.bluesky_reply_record("Useful context", root, parent)
        self.assertEqual(record["reply"]["root"], root)
        self.assertEqual(record["reply"]["parent"], parent)
        self.assertEqual(record["text"], "Useful context")

    def test_linkedin_post_is_visual_attributed_and_professional(self):
        item = distribution.channel_item(distribution.queue()[0], "linkedin")
        commentary = distribution.linkedin_commentary(item)
        self.assertIn("utm_source=linkedin", commentary)
        self.assertIn("#AITools", commentary)
        self.assertLessEqual(len(commentary), 3000)

    def test_configured_linkedin_author_avoids_profile_lookup(self):
        self.assertEqual(
            distribution.linkedin_author_urn("token", "urn:li:person:123"),
            "urn:li:person:123",
        )

    def test_new_linkedin_channel_does_not_inherit_legacy_sent_state(self):
        legacy = {"version": 2, "sent": ["digest"], "sent_ids": ["daily-id"]}
        self.assertEqual(distribution.channel_state(legacy, "bluesky")["sent_ids"], ["daily-id"])
        self.assertEqual(distribution.channel_state(legacy, "linkedin")["sent_ids"], [])

    def test_linkedin_receipt_is_written_only_after_success(self):
        item = distribution.channel_item(distribution.queue(date(2026, 9, 15))[0], "linkedin")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "receipts.json"
            distribution.append_receipt(path, "linkedin", item, {
                "urn": "urn:li:share:123",
                "url": "https://www.linkedin.com/feed/update/urn:li:share:123/",
            })
            distribution.append_receipt(path, "linkedin", item, {
                "urn": "urn:li:share:123",
                "url": "https://www.linkedin.com/feed/update/urn:li:share:123/",
            })
            receipts = distribution.load(path)["receipts"]
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["platform"], "linkedin")

    def test_friday_editorial_routes_to_checked_appsumo_pulse(self):
        original = distribution.OFFER_ALERTS_PATH
        with tempfile.TemporaryDirectory() as folder:
            empty_alerts = Path(folder) / "alerts.json"
            empty_alerts.write_text('{"alerts":[]}', encoding="utf-8")
            distribution.OFFER_ALERTS_PATH = empty_alerts
            try:
                item = distribution.queue(date(2026, 9, 18))[0]
            finally:
                distribution.OFFER_ALERTS_PATH = original
        self.assertEqual(item["kind"], "offer-update")
        self.assertIn("appsumo-ai-tools.html", item["url"])
        self.assertIn("AppSumo", item["title"])

    def test_connected_channel_activates_without_manual_flag(self):
        original_post = distribution.post_webhook
        original_ping = distribution.ping_websub
        original = {key: os.environ.get(key) for key in ("DISTRIBUTION_SEND_ENABLED", "DISTRIBUTION_WEBHOOK_URL")}
        sent = []
        try:
            os.environ.pop("DISTRIBUTION_SEND_ENABLED", None)
            os.environ["DISTRIBUTION_WEBHOOK_URL"] = "https://example.test/hook"
            distribution.post_webhook = lambda _url, item: sent.append(item)
            distribution.ping_websub = lambda: "WebSub notified"
            with tempfile.TemporaryDirectory() as folder:
                status = distribution.run(Path(folder) / "state.json")
            self.assertIn("distributed one guide", status)
            self.assertEqual(len(sent), 1)
        finally:
            distribution.post_webhook = original_post
            distribution.ping_websub = original_ping
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_daily_editorial_can_publish_only_once_per_date(self):
        original_post = distribution.post_webhook
        original_ping = distribution.ping_websub
        original = {key: os.environ.get(key) for key in ("DISTRIBUTION_SEND_ENABLED", "DISTRIBUTION_WEBHOOK_URL")}
        sent = []
        try:
            os.environ["DISTRIBUTION_SEND_ENABLED"] = "true"
            os.environ["DISTRIBUTION_WEBHOOK_URL"] = "https://example.test/hook"
            distribution.post_webhook = lambda _url, item: sent.append(item)
            distribution.ping_websub = lambda: "WebSub notified"
            with tempfile.TemporaryDirectory() as folder:
                state_path = Path(folder) / "state.json"
                first = distribution.run(state_path, date(2026, 9, 15))
                second = distribution.run(state_path, date(2026, 9, 15))
            self.assertIn("distributed one guide", first)
            self.assertIn("already distributed", second)
            self.assertEqual(len(sent), 1)
        finally:
            distribution.post_webhook = original_post
            distribution.ping_websub = original_ping
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_channels_are_idempotent_independently(self):
        original_linkedin = distribution.post_linkedin
        original_webhook = distribution.post_webhook
        original_ping = distribution.ping_websub
        original_receipts = distribution.RECEIPTS_PATH
        keys = (
            "DISTRIBUTION_SEND_ENABLED", "DISTRIBUTION_WEBHOOK_URL",
            "LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR_URN",
        )
        original = {key: os.environ.get(key) for key in keys}
        delivered = []
        try:
            os.environ["DISTRIBUTION_SEND_ENABLED"] = "true"
            os.environ["DISTRIBUTION_WEBHOOK_URL"] = "https://example.test/hook"
            os.environ.pop("LINKEDIN_ACCESS_TOKEN", None)
            os.environ.pop("LINKEDIN_AUTHOR_URN", None)
            distribution.post_webhook = lambda _url, _item: delivered.append("syndication")
            distribution.post_linkedin = lambda _token, _author, _item: delivered.append("linkedin") or {
                "urn": "urn:li:share:123",
                "url": "https://www.linkedin.com/feed/update/urn:li:share:123/",
            }
            distribution.ping_websub = lambda: "WebSub notified"
            with tempfile.TemporaryDirectory() as folder:
                state_path = Path(folder) / "state.json"
                distribution.RECEIPTS_PATH = Path(folder) / "receipts.json"
                distribution.run(state_path, date(2026, 9, 15))
                os.environ["LINKEDIN_ACCESS_TOKEN"] = "token"
                os.environ["LINKEDIN_AUTHOR_URN"] = "urn:li:person:123"
                distribution.run(state_path, date(2026, 9, 15))
                distribution.run(state_path, date(2026, 9, 15))
                state = distribution.load(state_path)
            self.assertEqual(delivered, ["syndication", "linkedin"])
            self.assertEqual(len(state["channels"]["syndication"]["sent_ids"]), 1)
            self.assertEqual(len(state["channels"]["linkedin"]["sent_ids"]), 1)
        finally:
            distribution.post_linkedin = original_linkedin
            distribution.post_webhook = original_webhook
            distribution.ping_websub = original_ping
            distribution.RECEIPTS_PATH = original_receipts
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_duplicate_cleanup_marks_item_sent_without_publishing(self):
        original_delete = distribution.delete_bluesky_post
        original_ping = distribution.ping_websub
        keys = (
            "DISTRIBUTION_SEND_ENABLED", "BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD",
            "BLUESKY_DELETE_RKEY", "BLUESKY_MARK_SENT_ID",
        )
        original = {key: os.environ.get(key) for key in keys}
        deleted = []
        try:
            os.environ["DISTRIBUTION_SEND_ENABLED"] = "false"
            os.environ["BLUESKY_HANDLE"] = "example.bsky.social"
            os.environ["BLUESKY_APP_PASSWORD"] = "test-only"
            os.environ["BLUESKY_DELETE_RKEY"] = "duplicate-rkey"
            os.environ["BLUESKY_MARK_SENT_ID"] = "ai-stack-builder"
            distribution.delete_bluesky_post = lambda _handle, _password, rkey: deleted.append(rkey) or "deleted"
            distribution.ping_websub = lambda: "WebSub notified"
            with tempfile.TemporaryDirectory() as folder:
                state_path = Path(folder) / "state.json"
                status = distribution.run(state_path)
                state = distribution.load(state_path)
            self.assertEqual(deleted, ["duplicate-rkey"])
            self.assertIn("marked ai-stack-builder as distributed", status)
            self.assertEqual(len(state["channels"]["bluesky"]["sent"]), 1)
        finally:
            distribution.delete_bluesky_post = original_delete
            distribution.ping_websub = original_ping
            for key, value in original.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_rss_advertises_websub_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            original_feed, original_queue = distribution.FEED_PATH, distribution.QUEUE_PATH
            try:
                distribution.FEED_PATH = Path(folder) / "feed.xml"
                distribution.QUEUE_PATH = Path(folder) / "queue.json"
                distribution.write_public_outputs(distribution.queue()[:1])
                feed = distribution.FEED_PATH.read_text(encoding="utf-8")
            finally:
                distribution.FEED_PATH, distribution.QUEUE_PATH = original_feed, original_queue
        self.assertIn('rel="hub"', feed)
        self.assertIn('rel="self"', feed)
        self.assertIn('xmlns:media=', feed)
        self.assertIn('<media:content', feed)

    def test_paid_plan_is_blocked_by_default(self):
        plan = paid.build_plan()
        self.assertFalse(plan["live_enabled"])
        self.assertTrue(all(not campaign["eligible"] for campaign in plan["campaigns"]))
        self.assertIn("disabled", paid.activation_status(plan))

    def test_paid_keywords_do_not_include_brand(self):
        offer = {"name": "ExampleAI", "category": "Marketing tools", "use_cases": ["Create ExampleAI ads"]}
        keywords = paid.generic_keywords(offer)
        self.assertTrue(all("exampleai" not in item for item in keywords))


if __name__ == "__main__":
    unittest.main()
