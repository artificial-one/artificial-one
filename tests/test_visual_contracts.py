import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "normalize_legacy_brand", ROOT / "scripts" / "normalize_legacy_brand.py"
)
normalizer = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(normalizer)


class VisualContractTests(unittest.TestCase):
    def test_hidden_filtered_cards_cannot_be_forced_visible(self):
        css = (ROOT / "assets" / "decision-engine.css").read_text(encoding="utf-8")
        self.assertIn("[hidden] { display: none !important; }", css)

    def test_home_hero_contains_the_full_brand_art(self):
        css = (ROOT / "assets" / "decision-engine.css").read_text(encoding="utf-8")
        self.assertIn(".hero-art img { position: relative", css)
        self.assertIn("aspect-ratio: auto; object-fit: contain", css)
        self.assertIn("min-height: calc(100svh - 74px)", css)
        self.assertIn(".brand img { display: none; }", css)
        self.assertIn(".brand::before", css)
        self.assertIn("artificial-one-elephant-mark.png", css)

    def test_observatory_uses_buyer_language(self):
        builder = (ROOT / "scripts" / "build_elephant_experience.py").read_text(encoding="utf-8")
        self.assertIn("AI tool price &amp; product changes", builder)
        self.assertIn("Check before you subscribe", builder)
        self.assertNotIn("Repeated-source monitoring", builder)

    def test_recipe_cards_have_explicit_dark_surface_contrast(self):
        css = (ROOT / "assets" / "decision-engine.css").read_text(encoding="utf-8")
        self.assertIn(".recipe-card h2 { margin: 13px 0 10px; color: #f8fafc", css)
        self.assertIn(".recipe-card p { min-height: 52px; color: #cbd5e1", css)
        self.assertIn("background: linear-gradient(145deg,#151528,#0e0e1b)", css)

    def test_legacy_tool_normalizer_is_idempotent(self):
        source = '<html><head><title>Tool</title></head><body class="bg-white"><nav>Old</nav></body></html>'
        once = normalizer.normalize_tool_page(source)
        twice = normalizer.normalize_tool_page(once)
        self.assertEqual(once, twice)
        self.assertIn("legacy-tool-page", once)
        self.assertIn("legacy-tool-pages.css", once)
        self.assertIn("affiliate-tracking.js", once)

    def test_every_tool_page_uses_the_current_shell_contract(self):
        pages = list((ROOT / "tools").glob("*.html"))
        self.assertGreater(len(pages), 500)
        for path in pages:
            source = path.read_text(encoding="utf-8")
            self.assertIn("legacy-tool-page", source, path.name)
            self.assertIn("legacy-tool-pages.css", source, path.name)
            self.assertIn("affiliate-tracking.js", source, path.name)

    def test_review_library_is_reader_first_and_progressive(self):
        source = (ROOT / "reviews.html").read_text(encoding="utf-8")
        self.assertIn('name="ai1-clean-editorial" content="true"', source)
        self.assertIn("Reviews that help you <em>decide.</em>", source)
        self.assertIn("data-review-search", source)
        self.assertIn("data-load-more", source)
        self.assertIn("const reviewBatchSize = 24", source)
        self.assertIn("return 'all';", source)

    def test_detailed_reviews_use_a_light_reading_surface(self):
        css = (ROOT / "assets" / "legacy-tool-pages.css").read_text(encoding="utf-8")
        self.assertIn("background: #fff !important", css)
        self.assertIn('[data-beehiiv-form="newsletter"] { display: none !important; }', css)
        self.assertIn("body.legacy-tool-page .pros {", css)
        self.assertIn("body.legacy-tool-page .cons {", css)

    def test_review_reading_avoids_injected_promotional_clutter(self):
        directory = (ROOT / "reviews.html").read_text(encoding="utf-8")
        detail_css = (ROOT / "assets" / "legacy-tool-pages.css").read_text(encoding="utf-8")
        self.assertIn("#contextual-revenue-route", directory)
        self.assertIn("#affiliate-sticky-recommendation", directory)
        self.assertIn("#contextual-revenue-route", detail_css)
        self.assertIn("#affiliate-sticky-recommendation", detail_css)


if __name__ == "__main__":
    unittest.main()
