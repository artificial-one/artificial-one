import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "build_ai_news.py"
SPEC = importlib.util.spec_from_file_location("build_ai_news", MODULE_PATH)
news = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(news)


SOURCE = {
    "name": "Example AI",
    "feed_url": "https://example.com/feed.xml",
    "homepage": "https://example.com/ai",
    "allowed_domains": ["example.com"],
}


class AiNewsPipelineTests(unittest.TestCase):
    def test_relevance_filter_rejects_generic_technology_news(self):
        self.assertTrue(news.is_ai_relevant("New open-weight LLM model launches"))
        self.assertFalse(news.is_ai_relevant("Football features arrive in Search"))

    def test_parses_rss_and_rejects_non_allowlisted_links(self):
        xml = b"""<rss><channel>
          <item><title>New &lt;b&gt;AI&lt;/b&gt; model</title><link>https://example.com/model</link><pubDate>Sun, 13 Sep 2026 10:00:00 GMT</pubDate><description>LLM benchmark</description></item>
          <item><title>Injected</title><link>https://evil.example/news</link><pubDate>Sun, 13 Sep 2026 10:00:00 GMT</pubDate></item>
        </channel></rss>"""
        items = news.parse_feed(xml, SOURCE)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "New AI model")
        self.assertEqual(items[0]["category"], "Models & LLMs")

    def test_parses_atom_alternate_link(self):
        xml = b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry>
          <title>AI research release</title><link rel='alternate' href='https://example.com/research'/>
          <updated>2026-09-13T09:00:00Z</updated><summary>New paper</summary>
        </entry></feed>"""
        items = news.parse_feed(xml, SOURCE)
        self.assertEqual(items[0]["url"], "https://example.com/research")
        self.assertEqual(items[0]["category"], "Research")

    def test_script_json_escapes_markup(self):
        encoded = news.safe_json_for_script([{"title": "</script><script>alert(1)</script>"}])
        self.assertNotIn("<script>", encoded)
        self.assertIn("\\u003c", encoded)

    def test_homepage_markers_are_required_and_replaced(self):
        source = "// AI_NEWS_DATA_START\nconst aiNewsItems = [];\n// AI_NEWS_DATA_END"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "index.html"
            article = root / "news" / "2026" / "09" / "13" / "safe-headline.html"
            article.parent.mkdir(parents=True)
            article.write_text("published", encoding="utf-8")
            path.write_text(source, encoding="utf-8")
            with patch.object(news, "ROOT", root), patch.object(news, "INDEX_PATH", path):
                updated = news.update_homepage([{
                    "title": "Safe headline", "url": "https://example.com/news",
                    "source": "Example AI", "published_at": "2026-09-13T09:00:00+00:00",
                    "display_date": "Sep 13, 2026", "category": "Research",
                    "archive_url": "news/2026/09/13/safe-headline.html",
                }])
        self.assertIn("Safe headline", updated)
        self.assertEqual(updated.count(news.DATA_START), 1)

    def test_news_routes_relevant_story_to_internal_partner_guide(self):
        route = news.related_route(
            {"title": "New AI voice model improves narration", "category": "Models & LLMs"},
            {"elevenlabs": {"name": "ElevenLabs", "slug": "elevenlabs-ai-voice"}},
        )
        self.assertEqual(route["offer_id"], "elevenlabs")
        self.assertEqual(route["url"], "partner-offers/elevenlabs-ai-voice.html")

    def test_news_page_is_reader_first_white_and_free_of_internal_status_banners(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            article = root / "news" / "2026" / "09" / "13" / "ai-voice-update.html"
            article.parent.mkdir(parents=True)
            article.write_text("published", encoding="utf-8")
            item = {
                "title": "AI voice update", "url": "https://example.com/news", "source": "Example AI",
                "published_at": "2026-09-13T09:00:00+00:00", "display_date": "Sep 13, 2026",
                "category": "Models & LLMs", "archive_url": "news/2026/09/13/ai-voice-update.html",
                "related": {"title": "Evaluate ElevenLabs", "url": "partner-offers/elevenlabs.html", "offer_id": "elevenlabs"},
            }
            with patch.object(news, "ROOT", root):
                rendered = news.render_news_page([item], "2026-09-15", [])
        self.assertIn('class="story-link"', rendered)
        self.assertIn('class="lead-story"', rendered)
        self.assertIn('class="news-page"', rendered)
        self.assertIn('images/branding/artificial-one-elephant-mark.png', rendered)
        self.assertNotIn('meta name="affiliate-event-endpoint"', rendered)
        self.assertNotIn('assets/affiliate-tracking.js', rendered)
        self.assertIn('body{margin:0;background:#fff', rendered)
        self.assertIn("The Elephant Wire", rendered)
        self.assertIn("AI news <span>worth knowing.</span>", rendered)
        self.assertIn("data-news-search", rendered)
        self.assertNotIn("Last material update", rendered)
        self.assertNotIn("Sources are allowlisted", rendered)
        self.assertNotIn("EDITOR'S PARTNER PICKS", rendered)
        self.assertNotIn("RELATED DECISION GUIDE", rendered)

    def test_public_news_excludes_external_only_and_missing_briefings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live = root / "news" / "2026" / "09" / "13" / "live.html"
            live.parent.mkdir(parents=True)
            live.write_text("published", encoding="utf-8")
            items = [
                {"title": "External only", "url": "https://example.com/external"},
                {"title": "Missing page", "archive_url": "news/2026/09/13/missing.html"},
                {"title": "Live briefing", "archive_url": "news/2026/09/13/live.html"},
            ]
            with patch.object(news, "ROOT", root):
                published = news.public_news_items(items)
        self.assertEqual([item["title"] for item in published], ["Live briefing"])

    def test_publishable_archive_record_requires_quality_gate_and_live_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            article = root / "news" / "2026" / "09" / "13" / "approved.html"
            article.parent.mkdir(parents=True)
            article.write_text("published", encoding="utf-8")
            record = {
                "path": "news/2026/09/13/approved.html",
                "source": {"url": "https://example.com/source"},
                "quality": {"approved": True, "score": 90, "issues": []},
            }
            with patch.object(news, "ROOT", root):
                self.assertTrue(news.archive_record_is_publishable(record))
                self.assertFalse(news.archive_record_is_publishable({**record, "quality": {"approved": True, "score": 84, "issues": []}}))


if __name__ == "__main__":
    unittest.main()
