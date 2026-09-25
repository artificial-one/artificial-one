import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_elephant_experience", ROOT / "scripts" / "build_elephant_experience.py")
experience = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(experience)


class ElephantExperienceTests(unittest.TestCase):
    def test_payload_is_grounded_and_complete(self):
        payload = experience.experience_payload()
        catalog = json.loads((ROOT / "data" / "tool_intelligence.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["stats"]["tools"], len(catalog["tools"]))
        self.assertEqual(payload["stats"]["recipes"], 8)
        self.assertGreater(payload["stats"]["monetized"], 20)
        self.assertNotIn("affiliate", payload["methodology"].casefold().replace("monetization", ""))

    def test_every_recipe_has_steps_and_matched_tools(self):
        payload = experience.experience_payload()
        known = {item["id"] for item in payload["tools"]}
        for recipe in payload["recipes"]:
            self.assertEqual(len(recipe["steps"]), 4)
            self.assertGreaterEqual(len(recipe["tools"]), 3)
            self.assertTrue(set(recipe["tools"]).issubset(known))

    def test_pages_are_deterministic_and_instrumented(self):
        first = experience.outputs()
        second = experience.outputs()
        self.assertEqual(first, second)
        for path, source in first.items():
            if path.suffix != ".html":
                continue
            self.assertIn("decision-engine.css", source, path.name)
            self.assertIn("affiliate-tracking.js", source, path.name)
            self.assertIn("https://artificial.one/", source, path.name)
        self.assertIn("data-elephant-form", first[ROOT / "ask-elephant.html"])
        self.assertIn("data-studio-form", first[ROOT / "ai-stack-studio.html"])
        self.assertIn("data-watch-email-form", first[ROOT / "ai-tool-observatory.html"])

    def test_public_api_excludes_affiliate_destinations(self):
        endpoint = (ROOT / "api" / "tool-catalog.js").read_text(encoding="utf-8")
        self.assertIn("Maximum page size", (ROOT / "scripts" / "build_elephant_experience.py").read_text(encoding="utf-8"))
        self.assertNotIn("affiliate: tool.links", endpoint)
        self.assertIn("Access-Control-Allow-Origin", endpoint)

    def test_watchlist_requires_double_confirmation_and_unsubscribe(self):
        endpoint = (ROOT / "api" / "watchlist-subscribe.js").read_text(encoding="utf-8")
        sender = (ROOT / "scripts" / "send_watchlist_alerts.py").read_text(encoding="utf-8")
        self.assertIn("watch:pending:", endpoint)
        self.assertIn("watch:active:", endpoint)
        self.assertIn('action || "") === "unsubscribe"', endpoint)
        self.assertIn("last_event_id", sender)
        self.assertIn("unsubscribe", sender.casefold())

    def test_sitemap_contains_the_full_experience(self):
        sitemap = experience.outputs()[ROOT / "sitemap.xml"]
        for path in ("ask-elephant.html", "ai-stack-studio.html", "workflow-recipes.html", "ai-tool-observatory.html", "developers.html"):
            self.assertIn(path, sitemap)
        for recipe in experience.RECIPES:
            self.assertIn(f"workflow-recipes/{recipe['id']}.html", sitemap)


if __name__ == "__main__":
    unittest.main()
