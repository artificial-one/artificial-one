import importlib.util
import html
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "monetize_affiliate_links.py"
SPEC = importlib.util.spec_from_file_location("monetize_affiliate_links_output", MODULE_PATH)
monetize = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(monetize)


class AffiliateSiteOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads((ROOT / "data" / "partner_offers.json").read_text(encoding="utf-8"))
        cls.audit = json.loads((ROOT / "data" / "partnerstack_program_audit.json").read_text(encoding="utf-8"))
        cls.placements = json.loads((ROOT / "data" / "affiliate_placements.json").read_text(encoding="utf-8"))

    def test_confirmed_portfolio_counts_are_consistent(self):
        published = [offer for offer in self.registry["offers"] if offer["status"] == "published"]
        drafts = [offer for offer in self.registry["offers"] if offer["status"] == "draft"]
        summary = self.audit["summary"]
        self.assertEqual(summary["active_programs"], len(self.audit["programs"]))
        self.assertEqual(summary["terms_action_required"], 0)
        self.assertEqual(summary["trackable_links_confirmed"], len(published))
        self.assertEqual([offer["id"] for offer in drafts], ["runpod"])
        self.assertEqual(
            sum(program["website_status"] == "blocked" for program in self.audit["programs"]),
            2,
        )

    def test_every_published_offer_has_a_generated_tracked_page(self):
        for offer in self.registry["offers"]:
            if offer["status"] != "published":
                continue
            page = ROOT / "partner-offers" / f"{offer['slug']}.html"
            text = html.unescape(page.read_text(encoding="utf-8"))
            self.assertIn(offer["tracking_url"], text, offer["id"])
            self.assertIn(f'data-offer-id="{offer["id"]}"', text, offer["id"])
            self.assertIn("affiliate-tracking.js", text, offer["id"])

    def test_contextual_campaign_targets_are_instrumented(self):
        offers = monetize.published_offers(self.registry)
        expected_by_page = {}
        for rule in self.placements["placements"]:
            for page in monetize.selected_pages(rule):
                expected_by_page.setdefault(page, rule)
        for page, rule in expected_by_page.items():
            text = html.unescape(page.read_text(encoding="utf-8"))
            offer_id = rule["offer_id"]
            self.assertIn("affiliate-tracking.js", text, page.as_posix())
            self.assertIn(f'data-offer-id="{offer_id}"', text, page.as_posix())
            acceptable_urls = [
                offers[offer_id]["tracking_url"],
                *offers[offer_id].get("legacy_urls", []),
            ]
            self.assertTrue(
                any(url in text for url in acceptable_urls),
                page.as_posix(),
            )

    def test_managed_blocks_never_land_inside_script_tags(self):
        for page in ROOT.rglob("*.html"):
            text = page.read_text(encoding="utf-8", errors="ignore")
            markers = [match.start() for match in re.finditer(r"<!-- affiliate-placement:", text)]
            if not markers:
                continue
            script_spans = [match.span() for match in re.finditer(r"<script\b[^>]*>.*?</script\s*>", text, re.I | re.S)]
            for marker in markers:
                self.assertFalse(
                    any(start <= marker < end for start, end in script_spans),
                    f"Managed block is inside a script in {page.relative_to(ROOT)}",
                )

    def test_dynamic_reviews_links_are_attributed(self):
        text = (ROOT / "reviews.html").read_text(encoding="utf-8")
        self.assertIn('"https://get.descript.com/951y7htioj6v": "descript"', text)
        self.assertIn('"https://try.elevenlabs.io/v5gy7s0nd0ty": "elevenlabs"', text)
        self.assertIn('data-placement="reviews-directory"', text)
        self.assertIn('src="assets/affiliate-tracking.js"', text)

    def test_ai_tool_finder_is_generated_and_tracked(self):
        text = (ROOT / "ai-tool-finder.html").read_text(encoding="utf-8")
        self.assertIn("Find the right AI tool for your job", text)
        self.assertIn('data-placement="tool-finder"', text)
        self.assertIn("affiliate-tracking.js", text)
        for offer in self.registry["offers"]:
            if offer["status"] == "published":
                self.assertIn(f'data-offer-id="{offer["id"]}"', text)

    def test_tracking_adds_subids_and_impression_measurement(self):
        text = (ROOT / "assets" / "affiliate-tracking.js").read_text(encoding="utf-8")
        self.assertIn('url.searchParams.set("sid1"', text)
        self.assertIn('url.searchParams.set("sid2"', text)
        self.assertIn('url.searchParams.set("sid3"', text)
        self.assertIn("affiliate_impression", text)

    def test_homepage_does_not_show_the_sticky_partner_banner(self):
        text = (ROOT / "assets" / "affiliate-tracking.js").read_text(encoding="utf-8")
        homepage_guard = 'if (/^\\/(?:index\\.html)?$/.test(window.location.pathname)) return;'
        self.assertEqual(text.count(homepage_guard), 2)

    def test_shared_navigation_does_not_restore_the_removed_how_it_works_link(self):
        text = (ROOT / "assets" / "affiliate-tracking.js").read_text(encoding="utf-8")
        generator = (ROOT / "scripts" / "build_partner_offers.py").read_text(encoding="utf-8")
        self.assertNotIn('/#how-it-works', text)
        self.assertNotIn('index.html#how-it-works', generator)

    def test_monetized_cards_open_their_existing_affiliate_link(self):
        text = (ROOT / "assets" / "affiliate-tracking.js").read_text(encoding="utf-8")
        self.assertIn("function enableAffiliateCardNavigation()", text)
        self.assertIn('a[data-affiliate-offer]', text)
        self.assertIn(".plan-card", text)
        self.assertIn("link.click();", text)
        self.assertIn("event.target.closest(\"a,button,input,select,textarea,label,summary,[role='button']\")", text)
        self.assertGreaterEqual(text.count("enableAffiliateCardNavigation();"), 3)

    def test_decision_engine_homepage_is_prebuilt_and_instrumented(self):
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        engine = (ROOT / "assets" / "decision-engine.js").read_text(encoding="utf-8")
        self.assertNotIn("cdn.tailwindcss.com", homepage)
        self.assertNotIn("babel.min.js", homepage)
        self.assertIn("Build my AI setup", homepage)
        self.assertIn("data-setup-builder", homepage)
        self.assertIn("data-setup-plan", homepage)
        self.assertIn("matcher-catalog:start", homepage)
        self.assertNotIn('href="#how-it-works"', homepage)
        self.assertNotIn('class="container section how-it-works"', homepage)
        self.assertNotIn('class="container section plan-explainer"', homepage)
        self.assertNotIn('class="container section final-cta"', homepage)
        self.assertNotIn('class="container faq-strip"', homepage)
        for event in (
            "matcher_start", "matcher_complete", "setup_plan_complete", "setup_plan_shared", "recommendation_impression",
            "compare_add", "stack_save", "stack_share", "watchlist_add", "email_opt_in",
        ):
            self.assertIn(event, engine)
        endpoint = (ROOT / "api" / "affiliate-event.js").read_text(encoding="utf-8")
        self.assertIn('matcher_complete: "matcher_completions"', endpoint)
        self.assertIn('setup_plan_complete: "setup_plan_completions"', endpoint)
        self.assertIn('watchlist_add: "watchlist_adds"', endpoint)
        self.assertIn('web_vital: "web_vitals"', endpoint)

    def test_homepage_exposes_complete_decision_and_return_loop(self):
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        engine = (ROOT / "assets" / "decision-engine.js").read_text(encoding="utf-8")
        self.assertIn("Start → add → scale", homepage)
        self.assertIn("data-plan-budget", homepage)
        self.assertIn("data-share-plan", homepage)
        self.assertIn("data-share-stack", homepage)
        self.assertIn("Recommended winner", engine)
        self.assertIn("Start here", engine)
        self.assertIn("Compare first", engine)
        self.assertIn("Keep", engine)
        self.assertIn("offer_change_alerts.json", engine)

    def test_homepage_has_one_primary_product_action(self):
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        header = homepage.split("</header>", 1)[0]
        self.assertIn("Build my AI setup", header)
        for competing_action in ("How it works", "Find Tools", "Recipes", "Deals", "What’s New", "My Stack", "Explore"):
            self.assertNotIn(competing_action, header)

    def test_homepage_command_center_is_complete_and_footerless(self):
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        engine = (ROOT / "assets" / "decision-engine.js").read_text(encoding="utf-8")
        tracking = (ROOT / "assets" / "affiliate-tracking.js").read_text(encoding="utf-8")
        header = homepage.split("</header>", 1)[0]
        for destination in ("reviews.html", "buyers-guides.html", "news.html", "about.html", "partners.html", "privacy.html", "mailto:hello@artificial.one"):
            self.assertIn(destination, header)
        self.assertNotIn('class="site-footer"', homepage)
        self.assertIn("data-home-news-track", homepage)
        self.assertIn("data-home-tool-search", homepage)
        self.assertIn("data-home-tool-results", homepage)
        self.assertIn("initHomeNewsTicker", engine)
        self.assertIn("initHomeToolSearch", engine)
        self.assertIn("initHomeWorkspaceTabs", engine)
        self.assertIn("var visibleLimit = query ? 4 : 3", engine)
        self.assertIn('!document.body.classList.contains("home-page")', tracking)

    def test_imported_offer_copy_is_buyer_facing(self):
        serialized = json.dumps(self.registry).casefold()
        for phrase in ("earn up to 50%", "affiliate support", "affiliate terms model", "strong fit for affiliates"):
            self.assertNotIn(phrase, serialized)


if __name__ == "__main__":
    unittest.main()
