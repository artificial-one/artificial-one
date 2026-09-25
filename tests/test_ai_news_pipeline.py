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
            path = Path(directory) / "index.html"
            path.write_text(source, encoding="utf-8")
            with patch.object(news, "INDEX_PATH", path):
                updated = news.update_homepage([{
                    "title": "Safe headline", "url": "https://example.com/news",
                    "source": "Example AI", "published_at": "2026-09-13T09:00:00+00:00",
                    "display_date": "Sep 13, 2026", "category": "Research",
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

    def test_news_page_places_internal_decision_link_before_source(self):
        item = {
            "title": "AI voice update", "url": "https://example.com/news", "source": "Example AI",
            "published_at": "2026-09-13T09:00:00+00:00", "display_date": "Sep 13, 2026",
            "category": "Models & LLMs", "related": {"title": "Evaluate ElevenLabs", "url": "partner-offers/elevenlabs.html", "offer_id": "elevenlabs"},
        }
        rendered = news.render_news_page([item], "2026-09-15", [])
        self.assertIn("data-content-route", rendered)
        self.assertIn('class="story-link"', rendered)
        self.assertIn('class="story-visual"', rendered)
        self.assertIn('class="news-page"', rendered)
        self.assertIn('images/branding/artificial-one-elephant-mark.png', rendered)
        self.assertIn('meta name="affiliate-event-endpoint" content="/api/affiliate-event"', rendered)
        self.assertIn('script src="assets/affiliate-tracking.js" defer', rendered)
        self.assertIn('.card h2{font-size:1.25rem;line-height:1.35;margin:13px 0;color:#0f172a}', rendered)
        self.assertIn('.pick strong{font-size:1.15rem;margin:8px 0;color:#0f172a}', rendered)


if __name__ == "__main__":
    unittest.main()
