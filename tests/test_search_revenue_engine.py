import importlib.util
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "search_revenue_engine.py"
SPEC = importlib.util.spec_from_file_location("search_revenue_engine", MODULE_PATH)
engine = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(engine)


def row(path="/partner-offers/useful.html", impressions=100, clicks=1, position=7):
    return {
        "keys": [f"https://www.artificial.one{path}", "useful ai pricing"],
        "impressions": impressions,
        "clicks": clicks,
        "ctr": clicks / impressions,
        "position": position,
    }


class FakeResponse:
    status_code = 200

    def json(self):
        return {
            "inspectionResult": {
                "indexStatusResult": {
                    "verdict": "PASS",
                    "robotsTxtState": "ALLOWED",
                    "indexingState": "INDEXING_ALLOWED",
                    "pageFetchState": "SUCCESSFUL",
                    "googleCanonical": "https://artificial.one/partner-offers/useful.html",
                    "userCanonical": "https://www.artificial.one/partner-offers/useful.html",
                    "lastCrawlTime": "2026-09-14T00:00:00Z",
                },
                "richResultsResult": {"verdict": "PASS"},
            }
        }


class FakeSession:
    def post(self, *_args, **_kwargs):
        return FakeResponse()


class SearchRevenueEngineTests(unittest.TestCase):
    def test_revenue_weight_changes_priority(self):
        rows = [
            row("/partner-offers/useful.html"),
            row("/partner-offers/other.html"),
        ]
        result = engine.revenue_weighted_opportunities(
            rows,
            {"/partner-offers/useful.html", "/partner-offers/other.html"},
            {"/partner-offers/other.html": 2.5},
        )
        self.assertIn("/partner-offers/other.html", result[0]["page"])

    def test_experiment_requires_minimum_impressions(self):
        public = engine.load_public_strategy(Path("missing.json"))
        private = {"version": 1, "experiments": {}}
        opportunities = [{"page": "https://www.artificial.one/partner-offers/useful.html"}]
        actions = engine.update_experiments(
            [row(impressions=79)], opportunities,
            {"/partner-offers/useful.html": 2.0}, public, private, date(2026, 9, 15)
        )
        self.assertEqual(actions, [])
        self.assertEqual(public["experiments"], {})

    def test_experiment_starts_and_public_output_has_no_metrics(self):
        public = engine.load_public_strategy(Path("missing.json"))
        private = {"version": 1, "experiments": {}}
        opportunities = [{"page": "https://www.artificial.one/partner-offers/useful.html"}]
        actions = engine.update_experiments(
            [row()], opportunities,
            {"/partner-offers/useful.html": 2.0}, public, private, date(2026, 9, 15)
        )
        self.assertEqual(len(actions), 1)
        experiment = public["experiments"]["/partner-offers/useful.html"]
        self.assertEqual(experiment, {"variant": "commercial", "status": "running"})
        self.assertNotIn("ctr", str(public))
        self.assertIn("baseline_ctr", private["experiments"]["/partner-offers/useful.html"])

    def test_material_decline_reverts_after_guard_window(self):
        path = "/partner-offers/useful.html"
        started = date(2026, 9, 15) - timedelta(days=15)
        public = {"version": 1, "experiments": {path: {"variant": "commercial", "status": "running"}}}
        private = {"version": 1, "experiments": {path: {
            "status": "running", "started_on": started.isoformat(),
            "baseline_ctr": 0.05, "baseline_position": 6.0,
        }}}
        actions = engine.update_experiments(
            [row(clicks=1, impressions=100, position=9)], [], {path: 2.0},
            public, private, date(2026, 9, 15)
        )
        self.assertTrue(any("Reverted" in item for item in actions))
        self.assertEqual(public["experiments"][path]["variant"], "control")

    def test_inspection_accepts_www_to_apex_canonical(self):
        result = engine.inspect_urls(
            FakeSession(), "https://www.artificial.one/",
            ["https://www.artificial.one/partner-offers/useful.html"]
        )
        self.assertEqual(result[0]["status"], "PASS")

    def test_private_state_is_written_outside_public_strategy(self):
        with tempfile.TemporaryDirectory() as folder:
            public_path = Path(folder) / "public.json"
            self.assertTrue(engine.write_if_changed(public_path, {"version": 1}))
            self.assertFalse(engine.write_if_changed(public_path, {"version": 1}))

    def test_content_priority_exposes_ids_not_queries_or_metrics(self):
        original = engine.OFFERS_PATH
        try:
            with tempfile.TemporaryDirectory() as folder:
                registry = Path(folder) / "offers.json"
                registry.write_text('{"offers":[{"id":"useful","slug":"useful","status":"published"}]}', encoding="utf-8")
                engine.OFFERS_PATH = registry
                public = {"version": 1, "experiments": {}, "content_priority": []}
                private = {"version": 1}
                actions = engine.update_content_priority(
                    [{"page": "https://www.artificial.one/partner-offers/useful.html", "query": "private query", "impressions": 100}],
                    public, private, date(2026, 9, 15)
                )
                self.assertEqual(public["content_priority"], ["useful"])
                self.assertNotIn("private query", str(public))
                self.assertEqual(len(actions), 1)
        finally:
            engine.OFFERS_PATH = original


if __name__ == "__main__":
    unittest.main()
