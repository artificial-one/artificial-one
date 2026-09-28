import importlib.util
import subprocess
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

    def test_semantic_landmark_normalizer_preserves_existing_layout_classes(self):
        article_page = '<body><nav>Site</nav><article class="reader-card"><h1>Guide</h1></article><footer>End</footer></body>'
        normalized = normalizer.ensure_main_landmark(article_page)
        self.assertIn('<main class="reader-card" id="main-content">', normalized)
        self.assertNotIn("<article", normalized)
        self.assertEqual(normalized, normalizer.ensure_main_landmark(normalized))

        section_page = '<body><nav>Site</nav><header><h1>Tool</h1></header><section>Details</section><footer>End</footer></body>'
        normalized = normalizer.ensure_main_landmark(section_page)
        self.assertLess(normalized.index("</nav>"), normalized.index('<main id="main-content"'))
        self.assertLess(normalized.index("</main>"), normalized.index("<footer>"))

    def test_every_html_page_has_one_primary_content_landmark(self):
        pages = [
            path for path in ROOT.rglob("*.html")
            if ".git" not in path.parts and "node_modules" not in path.parts
        ]
        self.assertGreater(len(pages), 1000)
        missing = []
        duplicates = []
        for path in pages:
            source = path.read_text(encoding="utf-8", errors="ignore").lower()
            # Google verification tokens use an .html suffix but are not
            # documents and intentionally contain no body element.
            if "<body" not in source:
                continue
            landmarks = source.count("<main") + source.count('role="main"') + source.count("role='main'")
            if landmarks == 0:
                missing.append(path.relative_to(ROOT).as_posix())
            elif landmarks > 1:
                duplicates.append(path.relative_to(ROOT).as_posix())
        self.assertEqual([], missing)
        self.assertEqual([], duplicates)

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
        self.assertIn("const canonical = new Map();", source)
        self.assertIn("const unpublishedReviewSlugs = new Set(", source)

    def test_review_card_and_detail_scores_cannot_drift(self):
        result = subprocess.run(
            ["node", str(ROOT / "scripts" / "sync_review_scores.mjs"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_detailed_reviews_use_a_light_reading_surface(self):
        css = (ROOT / "assets" / "legacy-tool-pages.css").read_text(encoding="utf-8")
        self.assertIn("background: #fff !important", css)
        self.assertIn('[data-beehiiv-form="newsletter"] { display: none !important; }', css)
        self.assertIn("body.legacy-tool-page .pros {", css)
        self.assertIn("body.legacy-tool-page .cons {", css)
        self.assertIn("article > header > h1", css)
        self.assertIn("color: #fff !important", css)

    def test_partner_media_is_branded_even_when_remote_capture_is_blank(self):
        css = (ROOT / "assets" / "decision-engine.css").read_text(encoding="utf-8")
        builder = (ROOT / "scripts" / "build_partner_offers.py").read_text(encoding="utf-8")
        self.assertIn('content: attr(data-product)', css)
        self.assertIn(".offer-product-visual > img", css)
        self.assertIn('data-product="{esc(offer[\'name\'])}"', builder)

    def test_legacy_relative_links_are_normalized(self):
        guide = '<html><head></head><body><a href="guides/example.html">Guide</a></body></html>'
        tool = '<html><head></head><body><a href="guides/example.html">Guide</a></body></html>'
        self.assertIn('href="example.html"', normalizer.normalize_guide_page(guide))
        self.assertIn('name="viewport"', normalizer.normalize_guide_page(guide))
        self.assertIn('href="../guides/example.html"', normalizer.normalize_tool_page(tool))

    def test_unstyled_legacy_editorial_pages_receive_a_readable_shell(self):
        source = '<html><head><title>Guide</title></head><body><h1>Guide</h1></body></html>'
        normalized = normalizer.normalize_editorial_page(source)
        self.assertIn("legacy-editorial-pages.css", normalized)
        self.assertIn("legacy-editorial-page", normalized)
        self.assertIn('name="viewport"', normalized)
        self.assertIn("legacy-editorial-header", normalized)

    def test_review_reading_avoids_injected_promotional_clutter(self):
        directory = (ROOT / "reviews.html").read_text(encoding="utf-8")
        detail_css = (ROOT / "assets" / "legacy-tool-pages.css").read_text(encoding="utf-8")
        self.assertIn("#contextual-revenue-route", directory)
        self.assertIn("#affiliate-sticky-recommendation", directory)
        self.assertIn("#contextual-revenue-route", detail_css)
        self.assertIn("#affiliate-sticky-recommendation", detail_css)


if __name__ == "__main__":
    unittest.main()
