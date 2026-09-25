import importlib.util
import os
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(value)
    return value


elephant = module("bluesky_elephant")


class BlueskyElephantTests(unittest.TestCase):
    def test_profile_is_explicitly_automated_and_playful(self):
        self.assertIn("automated", elephant.distribution.PROFILE_DESCRIPTION.casefold())
        self.assertIn("elephant", elephant.distribution.PROFILE_DESCRIPTION.casefold())
        self.assertIn("🐘", elephant.distribution.PROFILE_DISPLAY_NAME)

    def test_bonus_is_deterministic_visual_and_attributed(self):
        first = elephant.bluesky_bonus_item(date(2026, 9, 23))
        second = elephant.bluesky_bonus_item(date(2026, 9, 23))
        self.assertEqual(first, second)
        self.assertIsNotNone(first)
        self.assertEqual(first["id"], "bluesky-elephant-2026-09-23")
        self.assertIn("🐘", first["text"])
        self.assertIn("#Bot", first["text"])
        self.assertIn("utm_source=bluesky", first["url"])
        self.assertIn("utm_campaign=bluesky-elephant-", first["url"])
        self.assertTrue(first["image"].endswith(".jpg"))
        self.assertLessEqual(len(first["text"]), 295)

    def test_replies_are_playful_contextual_and_honest(self):
        reply = elephant.direct_reply("Which AI coding tool should I try?", "post-1")
        self.assertIn("🐘", reply)
        self.assertTrue("bot" in reply.casefold() or "automated" in reply.casefold())
        self.assertIn("developer workflow", reply)
        self.assertLessEqual(len(reply), 295)
        self.assertEqual(elephant.direct_reply("Please do not reply, no bots.", "post-2"), "")

    def test_local_ai_reply_is_preferred_and_remembered(self):
        original_generate = elephant.elephant_edge_ai.generate_reply
        original_enabled = os.environ.get("ELEPHANT_EDGE_AI_ENABLED")
        generated = "🐘 My local silicon trunk spotted the real puzzle: which repetitive coding step wastes the most time?"
        elephant.elephant_edge_ai.generate_reply = lambda *_args, **_kwargs: generated
        os.environ["ELEPHANT_EDGE_AI_ENABLED"] = "true"
        state = {"recent_ai_replies": []}
        try:
            reply, used_ai = elephant.elephant_reply(
                "Which AI coding workflow should I automate?", "post-ai", state,
            )
            elephant.remember_ai_reply(state, reply, used_ai)
        finally:
            elephant.elephant_edge_ai.generate_reply = original_generate
            if original_enabled is None:
                os.environ.pop("ELEPHANT_EDGE_AI_ENABLED", None)
            else:
                os.environ["ELEPHANT_EDGE_AI_ENABLED"] = original_enabled
        self.assertTrue(used_ai)
        self.assertEqual(reply, generated)
        self.assertEqual(state["recent_ai_replies"], [generated])

    def test_discovery_requires_recent_relevant_non_promotional_post(self):
        now = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)
        session = {"did": "did:example:self"}
        base = {
            "uri": "at://did:example:other/app.bsky.feed.post/1",
            "cid": "cid-1",
            "author": {"did": "did:example:other", "handle": "human.test", "labels": []},
            "record": {
                "text": "Which AI tools actually help with a repetitive developer workflow?",
                "createdAt": "2026-09-23T10:30:00Z",
            },
        }
        self.assertTrue(elephant.candidate_is_recent_question(base, session, now))
        useful_statement = {
            **base,
            "record": {
                **base["record"],
                "text": "My AI workflow finally removed a repetitive developer task instead of adding another dashboard.",
            },
        }
        self.assertTrue(elephant.candidate_is_recent_question(useful_statement, session, now))
        promo = {**base, "record": {**base["record"], "text": "Which AI tool? Buy now https://spam.test"}}
        self.assertFalse(elephant.candidate_is_recent_question(promo, session, now))
        stale = {**base, "record": {**base["record"], "createdAt": "2026-09-22T10:30:00Z"}}
        self.assertFalse(elephant.candidate_is_recent_question(stale, session, now))

    def test_state_limits_and_opt_outs_survive_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.json"
            state = elephant.load_state(path)
            bucket = elephant.day_bucket(state, date(2026, 9, 23))
            bucket["replied_uris"].extend(["one", "two", "three"])
            state["opt_out_dids"].append("did:example:leave-me-alone")
            elephant.save_state(path, state, date(2026, 9, 23))
            loaded = elephant.load_state(path)
        self.assertEqual(len(elephant.day_bucket(loaded, date(2026, 9, 23))["replied_uris"]), 3)
        self.assertIn("did:example:leave-me-alone", loaded["opt_out_dids"])

    def test_old_notifications_are_not_replied_to(self):
        original_items = elephant.notification_items
        original_post = elephant.distribution.create_bluesky_post
        posted = []
        elephant.notification_items = lambda _session: [{
            "uri": "at://did:example:old/app.bsky.feed.post/1",
            "cid": "old-cid",
            "reason": "mention",
            "indexedAt": "2026-09-01T10:00:00Z",
            "author": {"did": "did:example:old", "handle": "old.test", "labels": []},
            "record": {"text": "Which AI tool should I use?"},
        }]
        elephant.distribution.create_bluesky_post = lambda *_args, **_kwargs: posted.append(True)
        try:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "state.json"
                state = elephant.load_state(path)
                elephant.process_notifications(
                    {"did": "did:example:self", "accessJwt": "token"},
                    path, state, date.today(),
                )
                loaded = elephant.load_state(path)
        finally:
            elephant.notification_items = original_items
            elephant.distribution.create_bluesky_post = original_post
        self.assertEqual(posted, [])
        self.assertIn("at://did:example:old/app.bsky.feed.post/1", loaded["processed_notifications"])

    def test_following_requires_relevance_and_respects_blocks(self):
        author = {
            "did": "did:example:creator",
            "displayName": "AI workflow builder",
            "description": "Developer exploring automation and useful software.",
            "labels": [],
            "viewer": {},
        }
        self.assertTrue(elephant.topical_actor(author))
        self.assertTrue(elephant.healthy_actor(author, "did:example:self", set()))
        blocked = {**author, "viewer": {"blockedBy": True}}
        self.assertFalse(elephant.healthy_actor(blocked, "did:example:self", set()))

    def test_day_limits_are_intentionally_conservative(self):
        self.assertEqual(elephant.MAX_BONUS_POSTS_PER_DAY, 1)
        self.assertEqual(elephant.MAX_REPLIES_PER_DAY, 4)
        self.assertEqual(elephant.MAX_DISCOVERY_REPLIES_PER_DAY, 2)
        self.assertEqual(elephant.MAX_LIKES_PER_DAY, 5)
        self.assertEqual(elephant.MAX_FOLLOWS_PER_DAY, 2)


if __name__ == "__main__":
    unittest.main()
