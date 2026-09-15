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
        items = distribution.queue()
        self.assertTrue(items)
        self.assertTrue(all("artificial.one" in item["url"] for item in items))
        self.assertTrue(all("utm_source=distribution" in item["url"] for item in items))
        self.assertTrue(all(item["image"].startswith("https://artificial.one/images/social-cards/") for item in items))
        self.assertTrue(all(item["image_alt"] for item in items))
        self.assertTrue(all("utm_" not in item["text"] for item in items))

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
