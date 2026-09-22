import json
from pathlib import Path
import tempfile
import unittest

from scripts import consolidate_legacy_index as subject


def page(title: str, href: str = "") -> str:
    link = f'<a href="{href}">record</a>' if href else ""
    return f'<!doctype html><html><head><title>{title}</title><link rel="canonical" href="https://artificial.one/{href or "index.html"}"></head><body>{link}</body></html>'


class LegacyIndexConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "data").mkdir()
        (self.root / "tools").mkdir()
        (self.root / "index.html").write_text(page("Home", "tools/weak.html"), encoding="utf-8")
        (self.root / "tools/weak.html").write_text(
            '<html><head><link rel="canonical" href="https://artificial.one/tools/weak.html"></head><body>Weak</body></html>',
            encoding="utf-8",
        )
        (self.root / "tools/sourced.html").write_text(
            '<html><head><link rel="canonical" href="https://artificial.one/tools/sourced.html"></head><body>Sourced</body></html>',
            encoding="utf-8",
        )
        self.records = {
            "tools": [
                {"name": "Weak", "verification": {"status": "legacy-catalog"}, "links": {"profile": "tools/weak.html", "source": ""}, "monetization": {"active": False}},
                {"name": "Sourced", "verification": {"status": "legacy-catalog"}, "links": {"profile": "tools/sourced.html", "source": "https://vendor.example"}, "monetization": {"active": False}},
            ]
        }
        (self.root / "data/tool_intelligence.json").write_text(json.dumps(self.records), encoding="utf-8")
        (self.root / "data/search_growth_strategy.json").write_text('{"observed_pages": []}', encoding="utf-8")
        (self.root / "sitemap.xml").write_text(
            '<urlset><url><loc>https://artificial.one/tools/weak.html</loc></url><url><loc>https://artificial.one/tools/sourced.html</loc></url></urlset>',
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_noindexes_only_high_confidence_legacy_page(self):
        report = subject.run(self.root)
        self.assertEqual(report["summary"]["noindex"], 1)
        self.assertIn(subject.MARKER_START, (self.root / "tools/weak.html").read_text(encoding="utf-8"))
        self.assertNotIn(subject.MARKER_START, (self.root / "tools/sourced.html").read_text(encoding="utf-8"))
        sitemap = (self.root / "sitemap.xml").read_text(encoding="utf-8")
        self.assertNotIn("tools/weak.html", sitemap)
        self.assertIn("tools/sourced.html", sitemap)
        subject.run(self.root, check=True)

    def test_restores_page_after_source_is_added(self):
        subject.run(self.root)
        self.records["tools"][0]["links"]["source"] = "https://vendor.example/weak"
        (self.root / "data/tool_intelligence.json").write_text(json.dumps(self.records), encoding="utf-8")
        report = subject.run(self.root)
        self.assertEqual(report["summary"]["restored"], 1)
        self.assertNotIn(subject.MARKER_START, (self.root / "tools/weak.html").read_text(encoding="utf-8"))
        self.assertIn("tools/weak.html", (self.root / "sitemap.xml").read_text(encoding="utf-8"))

    def test_google_impressions_protect_and_restore_page(self):
        subject.run(self.root)
        (self.root / "data/search_growth_strategy.json").write_text(
            '{"observed_pages": ["/tools/weak.html"]}', encoding="utf-8"
        )
        report = subject.run(self.root)
        self.assertEqual(report["summary"]["restored"], 1)
        self.assertNotIn(subject.MARKER_START, (self.root / "tools/weak.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
