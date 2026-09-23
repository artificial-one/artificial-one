import importlib.util
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "x_elephant.py"
SPEC = importlib.util.spec_from_file_location("x_elephant", MODULE_PATH)
x = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(x)


class XElephantTests(unittest.TestCase):
    def test_profile_is_transparently_automated_and_playful(self):
        self.assertIn("🐘", x.PROFILE_DISPLAY_NAME)
        self.assertIn("automated", x.PROFILE_DESCRIPTION.casefold())
        self.assertIn("bot-posted", x.PROFILE_DESCRIPTION.casefold())

    def test_three_daily_posts_are_distinct_and_visual(self):
        day = date(2026, 9, 23)
        posts = [x.build_post(day, slot) for slot in x.POST_SLOTS]
        self.assertEqual(len({item["id"] for item in posts}), 3)
        self.assertEqual(len({item["text"] for item in posts}), 3)
        self.assertTrue(all(item["image"].startswith("https://artificial.one/images/social-cards/") for item in posts))
        self.assertTrue(all(x.x_weighted_length(item["text"]) <= 275 for item in posts))

    def test_only_one_daily_post_contains_a_route(self):
        posts = [x.build_post(date(2026, 9, 23), slot) for slot in x.POST_SLOTS]
        linked = [item for item in posts if item["has_affiliate_or_site_link"]]
        self.assertEqual([item["slot"] for item in linked], ["evening"])
        self.assertIn("utm_source=x", linked[0]["text"])
        self.assertIn("utm_campaign=x-elephant-", linked[0]["text"])

    def test_post_generation_is_deterministic(self):
        first = x.build_post(date(2026, 9, 23), "midday")
        second = x.build_post(date(2026, 9, 23), "midday")
        self.assertEqual(first["text"], second["text"])
        self.assertEqual(first["image"], second["image"])

    def test_oauth_signature_is_stable_for_fixed_nonce_and_time(self):
        header = x.oauth_header(
            "GET", "https://api.x.com/2/users/me?user.fields=username",
            "key", "secret", "token", "token-secret",
            nonce="abc", timestamp="1234567890",
        )
        self.assertTrue(header.startswith("OAuth "))
        self.assertIn('oauth_nonce="abc"', header)
        self.assertIn("oauth_signature=", header)

    def test_ai_replies_are_disabled_without_written_approval(self):
        original = os.environ.get("X_AI_REPLY_APPROVED")
        os.environ.pop("X_AI_REPLY_APPROVED", None)
        try:
            notes = x.process_mentions(x.load_state(Path("missing-state.json")), date(2026, 9, 23))
        finally:
            if original is not None:
                os.environ["X_AI_REPLY_APPROVED"] = original
        self.assertIn("written X approval", notes[0])

    def test_disabled_run_prepares_content_without_needing_credentials(self):
        original = os.environ.get("X_ELEPHANT_ENABLED")
        os.environ["X_ELEPHANT_ENABLED"] = "false"
        try:
            with tempfile.TemporaryDirectory() as folder:
                result = x.run(Path(folder) / "state.json", "morning", date(2026, 9, 23))
        finally:
            if original is None:
                os.environ.pop("X_ELEPHANT_ENABLED", None)
            else:
                os.environ["X_ELEPHANT_ENABLED"] = original
        self.assertIn("waiting for a connected account", result)

    def test_opt_out_and_unsafe_language_filters(self):
        self.assertTrue(x.opts_out("Please do not reply to me"))
        self.assertFalse(x.safe_inbound("Here is NSFW spam"))
        self.assertTrue(x.safe_inbound("Which AI editor should I test?"))

    def test_source_contains_no_automated_like_follow_or_dm_endpoints(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/likes", source)
        self.assertNotIn("/following", source)
        self.assertNotIn("/dm_", source)
        self.assertNotIn("/search/recent", source)


if __name__ == "__main__":
    unittest.main()
