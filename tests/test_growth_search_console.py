import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "growth_search_console.py"
SPEC = importlib.util.spec_from_file_location("growth_search_console", MODULE_PATH)
growth = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(growth)


class GrowthSearchConsoleTests(unittest.TestCase):
    def test_revenue_pages_receive_priority_weight(self):
        rows = [
            {
                "keys": ["https://artificial.one/reviews.html", "best ai writer"],
                "impressions": 100,
                "clicks": 1,
                "ctr": 0.01,
                "position": 6,
            },
            {
                "keys": ["https://artificial.one/blog.html", "ai news"],
                "impressions": 100,
                "clicks": 1,
                "ctr": 0.01,
                "position": 6,
            },
        ]
        result = growth.build_opportunities(rows, {"/reviews.html"})
        self.assertEqual(result[0]["query"], "best ai writer")
        self.assertTrue(result[0]["commercial"])

    def test_low_impression_rows_are_ignored(self):
        rows = [{
            "keys": ["https://artificial.one/page.html", "tiny query"],
            "impressions": 19,
            "clicks": 0,
            "ctr": 0,
            "position": 8,
        }]
        self.assertEqual(growth.build_opportunities(rows, set()), [])

    def test_base64_service_account_json_is_supported(self):
        import base64
        import json

        encoded = base64.b64encode(
            json.dumps({"client_email": "bot@example.com"}).encode("utf-8")
        ).decode("ascii")
        self.assertEqual(growth.load_service_account(encoded)["client_email"], "bot@example.com")


if __name__ == "__main__":
    unittest.main()
