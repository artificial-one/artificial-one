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


if __name__ == "__main__":
    unittest.main()
