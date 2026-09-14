import importlib.util
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
        self.assertEqual(summary["active_programs"], 25)
        self.assertEqual(summary["terms_action_required"], 0)
        self.assertEqual(summary["trackable_links_confirmed"], 22)
        self.assertEqual(len(published), 22)
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
            text = page.read_text(encoding="utf-8")
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
            text = page.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
