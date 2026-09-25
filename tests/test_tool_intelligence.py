import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


intelligence = load_module("build_tool_intelligence", ROOT / "scripts" / "build_tool_intelligence.py")
monitor = load_module("monitor_tool_intelligence", ROOT / "scripts" / "monitor_tool_intelligence.py")


class ToolIntelligenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = intelligence.build_catalog()
        cls.by_id = {item["id"]: item for item in cls.catalog["tools"]}

    def test_catalog_normalizes_legacy_pages_into_unique_entities(self):
        tools = self.catalog["tools"]
        self.assertGreaterEqual(len(tools), 350)
        self.assertEqual(len({item["id"] for item in tools}), len(tools))
        self.assertEqual(len({item["name"].casefold() for item in tools}), len(tools))
        self.assertEqual(sum(item["id"] == "adobe-firefly" for item in tools), 1)

    def test_evidence_labels_and_pricing_are_honest(self):
        reviewed = [item for item in self.catalog["tools"] if item["verification"]["status"] == "reviewed"]
        legacy = [item for item in self.catalog["tools"] if item["verification"]["status"] == "legacy-catalog"]
        self.assertGreaterEqual(len(reviewed), 20)
        self.assertTrue(all(item["links"]["affiliate"].startswith("https://") for item in reviewed))
        self.assertTrue(all(item["pricing"]["confidence"] == "legacy-unverified" for item in legacy))

    def test_explorer_is_crawlable_downloadable_and_commercial(self):
        html = intelligence.render_explorer(self.catalog)
        self.assertIn('id="intel-search"', html)
        self.assertIn('id="intel-category"', html)
        self.assertIn("data/tool_intelligence.json", html)
        self.assertIn("data/ai-tool-intelligence.csv", html)
        self.assertIn('"@type":"Dataset"', html)
        self.assertIn("data-affiliate-offer", html)
        self.assertIn("Affiliate links are marked", html)

    def test_migration_wizard_explains_scoring_and_escapes_dynamic_content(self):
        html = intelligence.render_alternatives(self.catalog)
        self.assertIn("Migration checklist", html)
        self.assertIn("two-point tie-break", html)
        self.assertIn("URLSearchParams", html)
        self.assertIn("function h(value)", html)
        self.assertIn("safeUrl", html)

    def test_homepage_and_sitemap_updates_are_idempotent(self):
        home = "<main>\n      {/* Featured Tools */}\n</main>"
        once = intelligence.update_homepage(home, self.catalog)
        twice = intelligence.update_homepage(once, self.catalog)
        self.assertEqual(once, twice)
        self.assertEqual(once.count("TOOL_INTELLIGENCE_START"), 1)
        sitemap = '<?xml version="1.0"?><urlset>\n</urlset>\n'
        first_map = intelligence.update_sitemap(sitemap, "2026-09-16")
        second_map = intelligence.update_sitemap(first_map, "2026-09-16")
        self.assertEqual(first_map, second_map)
        self.assertEqual(first_map.count("tool-intelligence:start"), 1)
        self.assertEqual(first_map.count("ai-tool-database.html"), 1)

    def test_compact_decision_engine_homepage_skips_legacy_database_block(self):
        source = '<main><section data-home-picks></section></main>'
        self.assertEqual(intelligence.update_homepage(source, self.catalog), source)

    def test_change_monitor_requires_same_changed_signal_twice(self):
        tool = {
            "id": "sample",
            "name": "Sample",
            "links": {"source": "https://example.com/pricing"},
        }
        state = {"version": 1, "tools": {}}
        history = {"version": 1, "events": [], "coverage": {}}
        observations = [
            ("sample", tool["links"]["source"], "old", "Pricing is ten dollars per month."),
            ("sample", tool["links"]["source"], "new", "Pricing is twenty dollars per month."),
            ("sample", tool["links"]["source"], "new", "Pricing is twenty dollars per month."),
        ]
        with patch.object(monitor, "fetch_source", side_effect=observations):
            first, _ = monitor.observe([tool], state, history, date(2026, 9, 14), batch_size=1, workers=1)
            second, _ = monitor.observe([tool], state, history, date(2026, 9, 15), batch_size=1, workers=1)
            third, _ = monitor.observe([tool], state, history, date(2026, 9, 16), batch_size=1, workers=1)
        self.assertEqual(first, [])
        self.assertEqual(second, [])
        self.assertEqual(len(third), 1)
        self.assertEqual(third[0]["kind"], "pricing or plan")
        self.assertNotIn("twenty dollars", json.dumps(third[0]))
        self.assertNotIn("signal", third[0])

    def test_generated_catalog_matches_current_build(self):
        generated = json.loads(intelligence.CATALOG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(generated["stats"], self.catalog["stats"])
        self.assertEqual(generated["methodology"], self.catalog["methodology"])


if __name__ == "__main__":
    unittest.main()
