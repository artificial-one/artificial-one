import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts import affiliate_network_monitor as monitor
from scripts import appsumo_impact as appsumo
from scripts import paid_acquisition


ROOT = Path(__file__).resolve().parents[1]


class AppSumoImpactTests(unittest.TestCase):
    def test_workbook_inventory_is_complete_and_public_safe(self):
        registry = json.loads((ROOT / "data" / "appsumo_offers.json").read_text(encoding="utf-8"))
        self.assertEqual(len(registry["offers"]), 184)
        self.assertEqual(len({item["id"] for item in registry["offers"]}), 184)
        self.assertTrue(all(item["tracking_url"].startswith("https://appsumo.8odi.net/") for item in registry["offers"]))
        encoded = json.dumps(registry).casefold()
        self.assertNotIn("auth_token", encoded)
        self.assertNotIn("account_sid", encoded)
        self.assertEqual(registry["policy"]["paid_brand_campaigns"], "prohibited")

    def test_two_inactive_checks_are_required_before_expiry(self):
        registry = {"offers": [{"id": "appsumo-example", "availability": "active", "tracking_url": "https://appsumo.8odi.net/example"}]}
        original = appsumo.check_destination
        appsumo.check_destination = lambda _offer: ("inactive", "https://appsumo.com/")
        try:
            with tempfile.TemporaryDirectory() as directory:
                state = Path(directory) / "availability.json"
                appsumo.refresh_availability(registry, state, workers=1)
                self.assertEqual(registry["offers"][0]["availability"], "checking")
                appsumo.refresh_availability(registry, state, workers=1)
                self.assertEqual(registry["offers"][0]["availability"], "expired")
        finally:
            appsumo.check_destination = original

    def test_transient_network_error_never_expires_offer(self):
        registry = {"offers": [{"id": "appsumo-example", "availability": "active", "tracking_url": "https://appsumo.8odi.net/example"}]}
        original = appsumo.check_destination
        appsumo.check_destination = lambda _offer: ("error", "TimeoutError")
        try:
            with tempfile.TemporaryDirectory() as directory:
                appsumo.refresh_availability(registry, Path(directory) / "state.json", workers=1)
            self.assertEqual(registry["offers"][0]["availability"], "active")
        finally:
            appsumo.check_destination = original

    def test_hub_is_limited_to_relevant_editorial_offers(self):
        registry = {"offers": [
            {"id": "appsumo-good", "name": "Good AI", "category": "AI writing", "tracking_url": "https://appsumo.8odi.net/good", "editorial_url": "blog-good.html", "ai_relevant": True, "availability": "active", "last_checked_at": "2026-09-15", "slug": "good"},
            {"id": "appsumo-expired", "name": "Expired AI", "category": "AI writing", "tracking_url": "https://appsumo.8odi.net/expired", "editorial_url": "blog-expired.html", "ai_relevant": True, "availability": "expired", "last_checked_at": "2026-09-15", "slug": "expired"},
            {"id": "appsumo-no-guide", "name": "No Guide AI", "category": "AI writing", "tracking_url": "https://appsumo.8odi.net/no", "editorial_url": "", "ai_relevant": True, "availability": "active", "last_checked_at": "2026-09-15", "slug": "no-guide"},
        ]}
        page = appsumo.render_hub(registry)
        self.assertIn("Good AI", page)
        self.assertNotIn("Expired AI", page)
        self.assertNotIn("No Guide AI", page)
        self.assertIn("We do not list every promotion", page)
        self.assertIn("AppSumo AI deals available today", page)
        self.assertIn("data-deal-card", page)
        self.assertIn('id="deal-search"', page)
        self.assertIn("Today's checked deal pulse", page)

    def test_deal_pulse_is_deterministic_and_homepage_safe(self):
        registry = {"offers": [
            {"id": f"deal-{index}", "name": f"Deal {index}", "category": "AI tools", "tracking_url": f"https://appsumo.8odi.net/{index}", "editorial_url": f"guide-{index}.html", "ai_relevant": True, "availability": "active", "last_checked_at": "2026-09-15", "slug": f"deal-{index}", "source_status": "new" if index == 0 else "approved"}
            for index in range(5)
        ]}
        first = appsumo.deal_picks(registry, date(2026, 9, 16))
        repeated = appsumo.deal_picks(registry, date(2026, 9, 16))
        self.assertEqual(first, repeated)
        self.assertEqual(len(first), 3)
        self.assertEqual(first[0]["id"], "deal-0")
        source = "<main>\n      {/* Featured Tools */}\n</main>"
        rendered = appsumo.update_homepage(source, registry, date(2026, 9, 16))
        rendered = appsumo.update_homepage(rendered, registry, date(2026, 9, 16))
        self.assertEqual(rendered.count(appsumo.HOMEPAGE_START), 1)
        self.assertIn('data-placement="homepage-deal-pulse"', rendered)
        self.assertIn('rel="nofollow sponsored noopener"', rendered)

    def test_impact_subids_and_runtime_expiry_guard_are_installed(self):
        script = (ROOT / "assets" / "affiliate-tracking.js").read_text(encoding="utf-8")
        self.assertIn('url.searchParams.set("subId1"', script)
        self.assertIn('url.searchParams.set("subId2"', script)
        self.assertIn('url.searchParams.set("subId3"', script)
        self.assertIn('url.searchParams.set("sharedId", "artificial-one")', script)
        self.assertIn("affiliateUnavailable", script)
        self.assertIn('"site_visit"', script)
        self.assertIn('"content_route_click"', script)
        self.assertIn('"content_route_impression"', script)
        endpoint = (ROOT / "api" / "affiliate-event.js").read_text(encoding="utf-8")
        self.assertIn('site_visit: "visits"', endpoint)
        self.assertIn('content_route_click: "route_clicks"', endpoint)
        self.assertIn('content_route_impression: "route_impressions"', endpoint)

    def test_appsumo_is_permanently_blocked_from_paid_search(self):
        policy = {"prohibited_networks": ["impact-appsumo"], "prohibited_brand_terms": ["appsumo"]}
        self.assertTrue(paid_acquisition.prohibited_by_network_policy({"network": "impact-appsumo", "name": "Tool"}, policy))
        self.assertTrue(paid_acquisition.prohibited_by_network_policy({"name": "AppSumo Tool"}, policy))

    def test_impact_snapshot_reduction_has_no_order_identity(self):
        actions = [{"OrderId": "secret-order", "Amount": "99.00", "Payout": "25.00", "Currency": "USD", "State": "PENDING"}]
        invoices = [{"Id": "private-invoice", "TotalAmount": "25.00", "Currency": "USD", "LineItems": [{"Status": "OPEN", "PaidDate": []}]}]
        calls = {"Campaigns": [{"CampaignName": "AppSumo", "CampaignId": "7443", "ContractStatus": "Active"}], "Actions": actions, "Invoices": invoices}
        original = monitor.impact_collection
        monitor.impact_collection = lambda _sid, _token, path, _key, _params=None: calls[path]
        try:
            snapshot = monitor.fetch_impact_snapshot("sid", "token")
        finally:
            monitor.impact_collection = original
        encoded = json.dumps(snapshot)
        self.assertNotIn("secret-order", encoded)
        self.assertNotIn("private-invoice", encoded)
        self.assertEqual(snapshot["actions"]["revenue"], {"USD": "99.00"})
        self.assertEqual(snapshot["actions"]["commissions"], {"USD": "25.00"})
        self.assertEqual(snapshot["invoices"]["payment_statuses"], {"OPEN": 1})

    def test_website_coverage_counts_only_boolean_eligible_rows(self):
        payload = {"offers": [
            {"availability": "active", "ai_relevant": True, "editorial_url": "blog-one.html"},
            {"availability": "expired", "ai_relevant": True, "editorial_url": "blog-two.html"},
            {"availability": "active", "ai_relevant": True, "editorial_url": ""},
        ]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "offers.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            coverage = monitor.website_coverage(path)
        self.assertEqual(coverage["promotable"], 1)

    def test_private_dashboard_reports_first_100_click_goal(self):
        _subject, text, html = monitor.render_dashboard(
            {"rewards": {}, "transactions": {}, "partnerships": {}, "customers": {}},
            {"connected": True, "actions": {"count": 0}, "programs": {}, "invoices": {}},
            {"total": 5}, {"total": 100}, {"total": 20}, {"total": 2},
            {"inventory": 184, "active": 151, "checking": 0, "expired": 33, "promotable": 100},
            [], "https://example.test/run",
        )
        self.assertIn("5/100 (5%)", text)
        self.assertIn("Drive 95 more qualified affiliate clicks", text)
        self.assertIn("Clicks remaining to goal", html)

    def test_private_dashboard_reports_source_and_internal_route_quality(self):
        _subject, text, _html = monitor.render_dashboard(
            {"rewards": {}, "transactions": {}, "partnerships": {}, "customers": {}},
            {"connected": True, "actions": {"count": 0}, "programs": {}, "invoices": {}},
            {"total": 8, "by_source": {"google": 6}}, {"total": 100},
            {"total": 100, "by_source": {"google": 80}, "by_medium": {"organic": 80}, "by_landing_page": {"/buyers-guides.html": 40}},
            {"total": 15},
            {"inventory": 184, "active": 151, "checking": 0, "expired": 33, "promotable": 19},
            [], "https://example.test/run", route_impressions={"total": 100},
        )
        self.assertIn("Internal route click-through rate: 15.00%", text)
        self.assertIn("Top visit sources: google: 80", text)
        self.assertIn("Top landing pages: /buyers-guides.html: 40", text)


if __name__ == "__main__":
    unittest.main()
