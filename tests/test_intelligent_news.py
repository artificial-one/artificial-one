import unittest
from datetime import datetime, timezone

from scripts import publish_intelligent_news as intelligent


ITEM = {
    "title": "Acme releases an open AI model for document search",
    "url": "https://example.com/acme-model",
    "source": "Example",
    "published_at": "2026-09-27T08:00:00+00:00",
    "display_date": "Sep 27, 2026",
    "category": "Models & LLMs",
    "related": {"title": "Evaluate Pinecone", "url": "partner-offers/pinecone.html", "offer_id": "pinecone"},
}
EVIDENCE = (
    "Acme releases an open AI model for document search. "
    "Acme published the model weights under an Apache license for commercial use. "
    "The company says the model retrieves passages from long business documents. "
    "Independent benchmark results were not included in the announcement. " * 8
)


def good_draft():
    return {
        "headline": "Acme opens its document-search model to commercial builders",
        "summary": "Acme has released model weights for document retrieval under an Apache license. The announcement describes long-document passage retrieval, while leaving independent performance comparisons unanswered for teams considering the model.",
        "facts": [
            {"statement": "The weights are available under an Apache license.", "evidence": "published the model weights under an Apache license for commercial use"},
            {"statement": "Acme positions it for retrieving passages from long documents.", "evidence": "the model retrieves passages from long business documents"},
        ],
        "why_it_matters": "Teams building document search can now inspect and deploy Acme's weights under a commercially permissive license. That creates another build-versus-buy option, but the missing independent benchmarks mean architecture decisions should wait for tests on a team's own documents and retrieval criteria.",
        "elephant_take": "🐘 Acme has put a new document-search model in the room, but the trunk test is still missing: does it retrieve the right passage from your messiest document? Open weights improve inspectability; they do not replace a representative evaluation set.",
        "caveat": "The available source is Acme's announcement, and it includes no independent benchmark comparison. Availability, system requirements and production performance should be verified directly.",
        "who_should_care": ["Developers building retrieval systems", "Teams evaluating self-hosted AI"],
        "what_to_do": ["Test it on representative documents", "Compare retrieval quality and operating cost"],
        "sensitive": False,
    }


class IntelligentNewsTests(unittest.TestCase):
    def test_model_json_parser_uses_final_object_after_an_echoed_prompt(self):
        raw = 'system example {"wrong": true}\nassistant\n<think>private reasoning</think>\n{"approved": true, "score": 91, "issues": []}\nExiting...'
        self.assertEqual(intelligent.parse_model_json(raw)["score"], 91)

    def test_permanent_path_is_stable_and_date_scoped(self):
        self.assertEqual(
            intelligent.permanent_path(ITEM),
            "news/2026/09/27/acme-releases-an-open-ai-model-for-document-search.html",
        )

    def test_quality_gate_requires_exact_source_fragments(self):
        draft = good_draft()
        self.assertEqual(intelligent.validate_draft(ITEM, EVIDENCE, draft), [])
        draft["facts"][0]["evidence"] = "a passage that does not appear in the source at all"
        self.assertIn("a fact has no exact source evidence", intelligent.validate_draft(ITEM, EVIDENCE, draft))

    def test_rendered_page_has_news_schema_source_and_three_decision_routes(self):
        record = {
            "path": intelligent.permanent_path(ITEM),
            "created_at": datetime(2026, 9, 27, tzinfo=timezone.utc).isoformat(),
            "source": ITEM,
            "article": good_draft(),
            "quality": {"approved": True, "score": 92, "issues": []},
            "links": {
                "guide_url": "buyers-guides.html", "guide_title": "Open the practical buyer guide",
                "review_url": "partner-offers/pinecone.html", "review_title": "Evaluate Pinecone",
                "elephant_url": "index.html?task=Explain%20Acme#build", "offer_id": "pinecone",
            },
        }
        page = intelligent.render_article(record)
        self.assertIn('"@type": "NewsArticle"', page)
        self.assertIn("The Elephant take", page)
        self.assertIn("Read the original reporting", page)
        self.assertIn("BUYER GUIDE", page)
        self.assertIn("PARTNER REVIEW", page)
        self.assertIn("ASK THE ELEPHANT", page)
        self.assertIn("locally run open model", page)

    def test_news_sitemap_contains_only_recent_pages(self):
        recent = {
            "path": "news/2026/09/27/recent.html", "created_at": "2026-09-27T08:00:00+00:00",
            "source": ITEM, "article": good_draft(),
        }
        old = {**recent, "path": "news/2026/09/20/old.html", "created_at": "2026-09-20T08:00:00+00:00"}
        value = intelligent.render_news_sitemap([recent, old], datetime(2026, 9, 27, 12, tzinfo=timezone.utc))
        self.assertIn("recent.html", value)
        self.assertNotIn("old.html", value)
        self.assertIn("news:publication", value)


if __name__ == "__main__":
    unittest.main()
