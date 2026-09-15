import importlib.util
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def module(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(value)
    return value


newsletter = module("publish_newsletter")
distribution = module("distribute_content")
paid = module("paid_acquisition")


class RevenueAccelerationTests(unittest.TestCase):
    def test_newsletter_is_deterministic_and_disclosed(self):
        first = newsletter.build_edition(date(2026, 9, 15))
        second = newsletter.build_edition(date(2026, 9, 15))
        self.assertEqual(first[2], second[2])
        self.assertIn("affiliate", first[1].casefold())
        self.assertIn("utm_source=newsletter", first[1])

    def test_distribution_queue_uses_attributed_site_links(self):
        items = distribution.queue()
        self.assertTrue(items)
        self.assertTrue(all("artificial.one" in item["url"] for item in items))
        self.assertTrue(all("utm_source=distribution" in item["url"] for item in items))

    def test_paid_plan_is_blocked_by_default(self):
        plan = paid.build_plan()
        self.assertFalse(plan["live_enabled"])
        self.assertTrue(all(not campaign["eligible"] for campaign in plan["campaigns"]))
        self.assertIn("disabled", paid.activation_status(plan))

    def test_paid_keywords_do_not_include_brand(self):
        offer = {"name": "ExampleAI", "category": "Marketing tools", "use_cases": ["Create ExampleAI ads"]}
        keywords = paid.generic_keywords(offer)
        self.assertTrue(all("exampleai" not in item for item in keywords))


if __name__ == "__main__":
    unittest.main()
