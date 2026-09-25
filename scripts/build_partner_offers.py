#!/usr/bin/env python3
"""Validate approved partner offers and build their public static pages."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
SEARCH_STRATEGY_PATH = ROOT / "data" / "search_growth_strategy.json"
SPONSORED_CAMPAIGNS_PATH = ROOT / "data" / "sponsored_campaigns.json"
HUB_PATH = ROOT / "partner-offers.html"
FINDER_PATH = ROOT / "ai-tool-finder.html"
HOME_PATH = ROOT / "index.html"
OFFER_DIRECTORY = ROOT / "partner-offers"
SITEMAP_PATH = ROOT / "sitemap.xml"
GENERATED_MARKER = "<!-- GENERATED: partner-offer-pipeline -->"
SITEMAP_START = "  <!-- partner-offers:start -->"
SITEMAP_END = "  <!-- partner-offers:end -->"
HOME_PICKS_START = "<!-- revenue-picks:start -->"
HOME_PICKS_END = "<!-- revenue-picks:end -->"
HOME_CATALOG_START = "<!-- matcher-catalog:start -->"
HOME_CATALOG_END = "<!-- matcher-catalog:end -->"
ALLOWED_STATUSES = {"draft", "approved", "published", "paused", "expired"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class OfferValidationError(ValueError):
    """Raised when the public offer registry is unsafe or incomplete."""


def is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def parse_iso_date(value: str | None, field: str, offer_id: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise OfferValidationError(
            f"{offer_id}: {field} must be YYYY-MM-DD or null"
        ) from exc


def load_registry(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OfferValidationError(f"Registry not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise OfferValidationError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict) or data.get("version") != 1:
        raise OfferValidationError("Registry must be an object with version: 1")
    if not isinstance(data.get("offers"), list):
        raise OfferValidationError("Registry field 'offers' must be an array")
    if parse_iso_date(data.get("updated_at"), "updated_at", "registry") is None:
        raise OfferValidationError("Registry requires updated_at in YYYY-MM-DD format")
    return data


def validate_registry(data: dict[str, Any]) -> list[dict[str, Any]]:
    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()
    validated: list[dict[str, Any]] = []

    for index, raw_offer in enumerate(data["offers"]):
        if not isinstance(raw_offer, dict):
            raise OfferValidationError(f"Offer #{index + 1} must be an object")

        offer = dict(raw_offer)
        offer_id = str(offer.get("id", "")).strip()
        slug = str(offer.get("slug", "")).strip()
        status = str(offer.get("status", "")).strip()

        if not offer_id or not SLUG_PATTERN.fullmatch(offer_id):
            raise OfferValidationError(
                f"Offer #{index + 1}: id must be a lowercase URL-safe identifier"
            )
        if offer_id in seen_ids:
            raise OfferValidationError(f"Duplicate offer id: {offer_id}")
        seen_ids.add(offer_id)

        if not slug or not SLUG_PATTERN.fullmatch(slug):
            raise OfferValidationError(f"{offer_id}: invalid slug")
        if slug in seen_slugs:
            raise OfferValidationError(f"Duplicate offer slug: {slug}")
        seen_slugs.add(slug)

        if status not in ALLOWED_STATUSES:
            raise OfferValidationError(
                f"{offer_id}: status must be one of {sorted(ALLOWED_STATUSES)}"
            )

        expires_at = parse_iso_date(offer.get("expires_at"), "expires_at", offer_id)
        approved_at = parse_iso_date(offer.get("approved_at"), "approved_at", offer_id)
        verified_at = parse_iso_date(
            offer.get("terms_verified_at"), "terms_verified_at", offer_id
        )

        if status == "published":
            required_text = (
                "name",
                "category",
                "summary",
                "best_for",
                "offer_label",
                "pricing_note",
                "tracking_url",
                "cta_label",
                "why_consider",
                "watch_out",
            )
            missing = [field for field in required_text if not str(offer.get(field, "")).strip()]
            if missing:
                raise OfferValidationError(
                    f"{offer_id}: published offer missing {', '.join(missing)}"
                )
            if not approved_at or not verified_at:
                raise OfferValidationError(
                    f"{offer_id}: published offers require approved_at and terms_verified_at"
                )
            if not is_https_url(str(offer["tracking_url"])):
                raise OfferValidationError(f"{offer_id}: tracking_url must be HTTPS")
            evidence = offer.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise OfferValidationError(
                    f"{offer_id}: published offers require at least one evidence item"
                )
            for item in evidence:
                if not isinstance(item, dict) or not str(item.get("label", "")).strip():
                    raise OfferValidationError(f"{offer_id}: invalid evidence item")
                if not is_https_url(str(item.get("url", ""))):
                    raise OfferValidationError(f"{offer_id}: evidence URLs must be HTTPS")
            use_cases = offer.get("use_cases")
            if (
                not isinstance(use_cases, list)
                or not 2 <= len(use_cases) <= 5
                or any(not isinstance(item, str) or not item.strip() for item in use_cases)
            ):
                raise OfferValidationError(
                    f"{offer_id}: published offers require 2 to 5 non-empty use cases"
                )

        review_url = str(offer.get("review_url", "")).strip()
        review_parts = review_url.replace("\\", "/").split("/")
        if review_url and (
            urlparse(review_url).scheme
            or review_url.startswith(("/", ".."))
            or ".." in review_parts
            or "\\" in review_url
        ):
            raise OfferValidationError(
                f"{offer_id}: review_url must be a safe site-relative path"
            )

        offer["_expires_at"] = expires_at
        validated.append(offer)

    return validated


def public_offers(offers: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    active = []
    for offer in offers:
        if offer["status"] != "published":
            continue
        if offer["_expires_at"] and offer["_expires_at"] < today:
            continue
        active.append(offer)
    return sorted(active, key=lambda item: (not bool(item.get("featured")), item["name"].lower()))


def apply_revenue_strategy(offers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply the public, privacy-safe ordering emitted by the revenue optimizer."""
    try:
        strategy = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return offers
    ranking = strategy.get("ranking", [])
    if not isinstance(ranking, list):
        return offers
    positions = {str(offer_id): index for index, offer_id in enumerate(ranking)}
    return sorted(
        offers,
        key=lambda item: (
            positions.get(str(item["id"]), len(positions)),
            not bool(item.get("featured")),
            str(item["name"]).casefold(),
        ),
    )


def search_snippet(offer: dict[str, Any]) -> tuple[str, str]:
    """Return deterministic copy selected by the guarded Search Console loop."""
    path = f"/partner-offers/{offer['slug']}.html"
    try:
        strategy = json.loads(SEARCH_STRATEGY_PATH.read_text(encoding="utf-8"))
        experiment = strategy.get("experiments", {}).get(path, {})
    except (OSError, json.JSONDecodeError, AttributeError):
        experiment = {}
    if isinstance(experiment, dict) and experiment.get("variant") == "commercial":
        return (
            f"{offer['name']} Review: Pricing, Use Cases & Alternatives | artificial.one",
            f"Review {offer['name']} pricing notes, best use cases, limitations and alternatives. Check the current verified partner offer and decide if it fits.",
        )
    return (
        f"{offer['name']}: Use Cases, Fit & Partner Offer | artificial.one",
        f"Evaluate {offer['name']}, who it suits, practical use cases, limitations and the current verified partner offer. Terms checked {offer['terms_verified_at']}.",
    )


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def json_ld(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'<script type="application/ld+json">{payload}</script>'


def shell(
    *,
    title: str,
    description: str,
    canonical_path: str,
    content: str,
    prefix: str = "",
    structured_data: dict[str, Any] | None = None,
    social_image: str = "https://artificial.one/images/og-homepage.jpg",
    social_image_alt: str | None = None,
) -> str:
    canonical = f"https://artificial.one/{canonical_path}"
    image_alt = social_image_alt or title
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{esc(social_image)}">
  <meta property="og:image:alt" content="{esc(image_alt)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="affiliate-event-endpoint" content="/api/affiliate-event">
  <link rel="alternate" type="application/rss+xml" title="artificial.one AI tool guides" href="{prefix}feed.xml">
  {json_ld(structured_data) if structured_data else ""}
  <link rel="preload" href="{prefix}images/social/artificial-one-logo.png" as="image">
  <link rel="stylesheet" href="{prefix}assets/decision-engine.css">
</head>
<body>
  <a class="skip-link" href="#main-content">Skip to content</a>
  {GENERATED_MARKER}
  <header class="site-header">
    <div class="nav-wrap">
      <a class="brand" href="{prefix}index.html"><img src="{prefix}images/social/artificial-one-logo.png" alt="Artificial.One elephant"><span>artificial<span class="brand-dot">.</span>one</span></a>
      <button class="nav-toggle" type="button" aria-expanded="false" aria-label="Open navigation">☰</button>
      <nav class="primary-nav" aria-label="Primary navigation">
        <a href="{prefix}ask-elephant.html">Ask Elephant</a>
        <a href="{prefix}ai-tool-finder.html">Find Tools</a>
        <a href="{prefix}workflow-recipes.html">Recipes</a>
        <a href="{prefix}partner-offers.html">Deals</a>
        <a href="{prefix}news.html">What’s New</a>
        <button class="stack-trigger" type="button" data-open-stack>My Stack</button>
        <details class="more-menu"><summary>Explore ▾</summary><div class="more-links"><a href="{prefix}ai-stack-studio.html">Stack Studio</a><a href="{prefix}ai-tool-observatory.html">Tool Observatory</a><a href="{prefix}ai-tool-finder.html?compare=">Compare</a><a href="{prefix}reviews.html">All reviews</a><a href="{prefix}decision-tools.html">Free tools</a><a href="{prefix}buyers-guides.html">Buyer guides</a><a href="{prefix}developers.html">Public API</a><a href="{prefix}about.html">How we evaluate</a><a href="{prefix}partners.html">For partners</a></div></details>
      </nav>
    </div>
  </header>
  <main id="main-content">{content}</main>
  <footer class="site-footer"><div class="container footer-grid">
    <div><a class="brand" href="{prefix}index.html"><img src="{prefix}images/social/artificial-one-logo.png" alt=""><span>artificial<span class="brand-dot">.</span>one</span></a><p>Independent AI-tool decisions, built around your job—not a wall of logos.</p><p class="disclosure">We may earn a commission from marked links at no extra cost to you. Payment never guarantees a positive verdict.</p></div>
    <div><h4>Decide</h4><a href="{prefix}ask-elephant.html">Ask the Elephant</a><a href="{prefix}ai-stack-studio.html">Stack Studio</a><a href="{prefix}partner-offers.html">Verified deals</a><a href="{prefix}decision-tools.html">Free calculators</a></div>
    <div><h4>Learn</h4><a href="{prefix}workflow-recipes.html">Workflow recipes</a><a href="{prefix}ai-tool-observatory.html">Tool Observatory</a><a href="{prefix}news.html">AI radar</a><a href="{prefix}developers.html">Public API</a><a href="{prefix}about.html">Methodology</a></div>
    <div><h4>Company</h4><a href="{prefix}partners.html">For partners</a><a href="{prefix}privacy.html">Privacy</a><a href="mailto:hello@artificial.one">hello@artificial.one</a></div>
  </div></footer>
  <aside class="stack-panel" data-stack-panel aria-label="My AI Stack"><div class="panel-head"><h2>My AI Stack</h2><button class="close-btn" type="button" data-close-panel aria-label="Close">×</button></div><p>Tools, watched deals and recent decisions saved on this device. No account required.</p><div class="saved-list" data-stack-list></div><div class="panel-actions"><button class="btn btn-secondary btn-small" type="button" data-share-stack>Copy shareable stack</button></div><section class="panel-section"><h3>Deal alerts</h3><div data-watch-alerts><p class="empty compact">The elephant is listening for pricing changes.</p></div></section><section class="panel-section"><h3>Recent comparisons</h3><div data-comparison-history><p class="empty compact">Run a match to build your decision history.</p></div></section></aside>
  <div class="compare-drawer" data-compare-drawer><div class="compare-bar"><strong>Compare</strong><div class="compare-items" data-compare-items></div><button class="btn btn-small" type="button" data-open-compare>Compare now</button><button class="icon-btn" type="button" data-clear-compare aria-label="Clear comparison">×</button></div></div>
  <div class="modal-backdrop" data-compare-modal role="dialog" aria-modal="true" aria-label="Tool comparison"><div class="compare-modal"><div class="panel-head"><h2>Side-by-side decision</h2><button class="close-btn" type="button" data-close-panel aria-label="Close">×</button></div><div class="comparison-grid" data-comparison-grid></div><div class="loop-actions"><button class="btn btn-secondary btn-small" type="button" data-share-compare>Copy share link</button></div></div></div>
  <script src="{prefix}assets/decision-engine.js" defer></script>
  <script src="{prefix}assets/affiliate-tracking.js" defer></script>
</body>
</html>
'''


def public_offer_data(offer: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    palette = ("#8b5cf6", "#9cff3b", "#ff4da6", "#29d3ff", "#ffca58")
    color = palette[sum(ord(char) for char in str(offer["id"])) % len(palette)]
    cta = str(offer.get("cta_label") or f"Check {offer['name']}")
    if cta.casefold().startswith("explore "):
        cta = f"Check {offer['name']} options"
    official_url = next((str(item.get("url")) for item in offer.get("evidence", []) if item.get("url")), str(offer["tracking_url"]))
    host = urlparse(official_url).netloc.removeprefix("www.")
    trial_text = "Free trial availability varies"
    trial_source = " ".join((str(offer.get("cta_label", "")), str(offer.get("offer_label", "")), str(offer.get("pricing_note", "")), str(offer.get("tracking_url", "")))).casefold()
    if any(term in trial_source for term in ("free trial", "start free", "try free", "free plan")):
        trial_text = "Free trial or plan available"
    label = str(offer["offer_label"])
    price_text = label if re.search(r"(?:[$£€]|\bfree\b|\btrial\b|\d+\s*%|\blifetime\b)", label, re.I) else "See current plans"
    use_cases = outcome_use_cases(offer)
    return {
        "id": offer["id"], "slug": offer["slug"], "name": offer["name"],
        "category": offer["category"], "summary": offer["summary"],
        "best": offer["best_for"], "offer": offer["pricing_note"],
        "why": offer["why_consider"], "limit": offer["watch_out"],
        "verified": offer["terms_verified_at"], "featured": bool(offer.get("featured")),
        "useCases": use_cases, "affiliateUrl": offer["tracking_url"],
        "url": f"{prefix}partner-offers/{offer['slug']}.html", "cta": cta, "color": color,
        "price": price_text, "trial": trial_text, "officialUrl": official_url,
        "logoUrl": f"https://www.google.com/s2/favicons?domain={quote(host)}&sz=128",
        "screenshotUrl": f"https://s.wordpress.com/mshots/v1/{quote(official_url, safe='')}?w=1000",
    }


def outcome_use_cases(offer: dict[str, Any]) -> list[str]:
    """Always give a buyer three outcome-oriented paths without inventing product claims."""
    values = [str(item).strip() for item in offer.get("use_cases", []) if str(item).strip()]
    fallbacks = [
        f"Evaluate {offer['name']} against your current workflow",
        f"Compare {offer['name']} with alternatives before buying",
        f"Validate the current plan, limits and total cost",
    ]
    for value in fallbacks:
        if len(values) >= 3:
            break
        if value not in values:
            values.append(value)
    return values[:3]


def catalog_script(offers: list[dict[str, Any]], prefix: str = "") -> str:
    payload = json.dumps([public_offer_data(offer, prefix) for offer in offers], ensure_ascii=False).replace("<", "\\u003c")
    return f'<script id="ai1-offer-data" type="application/json">{payload}</script>'


def offer_card(offer: dict[str, Any], placement: str = "offer-hub") -> str:
    data = public_offer_data(offer)
    mark = "".join(word[:1] for word in str(offer["name"]).split()[:2]).upper()
    search = " ".join([str(offer["name"]), str(offer["category"]), str(offer["best_for"]), *offer["use_cases"]]).casefold()
    return f'''<article class="tool-card" data-tool-card data-id="{esc(offer['id'])}" data-category="{esc(offer['category'])}" data-search="{esc(search)}" data-new-date="{esc(offer['terms_verified_at'])}" style="--brand:{data['color']}">
      <div class="product-visual product-visual-card"><img src="{esc(data['screenshotUrl'])}" alt="{esc(offer['name'])} product website preview" width="1000" height="563" loading="lazy" decoding="async"><span class="product-logo"><img src="{esc(data['logoUrl'])}" alt="{esc(offer['name'])} logo" width="48" height="48" loading="lazy" decoding="async"><b aria-hidden="true">{esc(mark)}</b></span></div>
      <div class="card-top"><span class="new-badge" hidden>New since your last visit</span><span class="fit-score">Verified<small>{esc(offer['terms_verified_at'])}</small></span></div>
      <p class="category">{esc(offer['category'])}</p><h2>{esc(offer['name'])}</h2>
      <p class="summary">{esc(offer['summary'])}</p><p class="reason"><strong>Best for:</strong> {esc(offer['best_for'])}</p><p class="outcome"><strong>Outcome:</strong> {esc(data['useCases'][0])}</p>
      <p class="limitation"><strong>Know first:</strong> {esc(offer['watch_out'])}</p>
      <div class="meta-row"><span class="tag">{esc(data['price'])}</span><span class="tag">{esc(data['trial'])}</span><span class="tag verified">Terms checked</span></div>
      <div class="card-actions"><a class="btn btn-small" href="{esc(offer['tracking_url'])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{esc(offer['id'])}" data-placement="{esc(placement)}">{esc(data['cta'])} →</a><button class="icon-btn compare-add" type="button" data-id="{esc(offer['id'])}" aria-label="Compare {esc(offer['name'])}">⇄</button><button class="icon-btn stack-add" type="button" data-id="{esc(offer['id'])}" aria-label="Save {esc(offer['name'])}">＋</button><a class="details link-subtle" href="partner-offers/{esc(offer['slug'])}.html">Full verdict</a></div>
    </article>'''


def sponsored_spotlight() -> str:
    """Render only paid placements that are currently within their booked window."""
    try:
        payload = json.loads(SPONSORED_CAMPAIGNS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return ""
    today = date.today().isoformat()
    campaigns = [
        item for item in payload.get("campaigns", [])
        if isinstance(item, dict)
        and "category_placement" in (item.get("deliverables") or [])
        and str(item.get("spotlight_until") or "") >= today
    ]
    if not campaigns:
        return ""
    cards = "".join(
        f'''<a class="tool-card sponsored-card" href="sponsored/{esc(item['slug'])}.html">
          <p class="eyebrow">Sponsored spotlight</p><h2>{esc(item['brand'])}</h2>
          <p class="summary">{esc(str(item.get('brief') or '')[:240])}</p>
          <span class="link-subtle">Open the disclosed sponsor feature →</span>
        </a>'''
        for item in campaigns[:3]
    )
    return f'''<section class="surface content-card sponsored-spotlight"><div class="section-head"><div>
      <p class="eyebrow">Paid placement</p><h2>Sponsored partner spotlight</h2>
      <p>Clearly labelled commercial placements. Payment never changes independent rankings.</p>
    </div><a class="link-subtle" href="sponsored.html">All sponsored features →</a></div>
    <div class="card-grid">{cards}</div></section>'''


def render_hub(offers: list[dict[str, Any]]) -> str:
    if offers:
        cards = "\n".join(offer_card(offer) for offer in offers)
        listing = f'<div class="card-grid">{cards}</div>'
        lead = f"{len(offers)} currently verified partner offer{'s' if len(offers) != 1 else ''}."
    else:
        listing = '''<div class="surface empty">
          <h2>The first verified offers are being reviewed</h2>
          <p>We publish an offer only after its terms, destination and audience fit have been checked.</p>
          <a class="link-subtle" href="partners.html">Represent an AI product? Submit an offer →</a>
        </div>'''
        lead = "A curated feed of partner offers, selected for usefulness rather than commission size."

    content = f'''
    <section class="section"><div class="container"><p class="eyebrow">Commercially transparent</p><div class="section-head"><div><h1>Verified AI <span class="gradient-text">deals worth checking</span></h1><p>{lead} Terms, fit and limitations are visible before the click.</p></div></div>
      <div class="surface content-card"><strong>How we earn:</strong> marked links may pay artificial.one a commission. You pay no extra. Payment does not buy a positive verdict or guaranteed placement.</div>
    </div></section>
    <section class="container section-tight">
      {sponsored_spotlight()}
      {listing}
    </section>{catalog_script(offers)}'''
    return shell(
        title="Verified AI Partner Offers | artificial.one",
        description="Curated and independently evaluated offers from AI software partners, with transparent affiliate disclosures and verified terms.",
        canonical_path="partner-offers.html",
        content=content,
        structured_data={
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": "Verified AI partner offers",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index,
                    "name": offer["name"],
                    "url": f"https://artificial.one/partner-offers/{offer['slug']}.html",
                }
                for index, offer in enumerate(offers, start=1)
            ],
        },
    )


def render_finder(offers: list[dict[str, Any]]) -> str:
    categories = sorted({str(offer["category"]) for offer in offers})
    category_buttons = "".join(
        f'<button type="button" data-filter="{esc(category)}">{esc(category)}</button>'
        for category in categories
    )
    cards = "".join(
        f'''<article class="tool" data-category="{esc(offer['category'])}" data-search="{esc(' '.join([str(offer['name']), str(offer['category']), str(offer['best_for']), *offer['use_cases']]).casefold())}" data-rank="{index}">
          <p class="eyebrow">{esc(offer['category'])}</p><h2>{esc(offer['name'])}</h2>
          <p>{esc(offer['summary'])}</p><p class="best"><strong>Best for:</strong> {esc(offer['best_for'])}</p>
          <div class="actions"><a class="details" href="partner-offers/{esc(offer['slug'])}.html">Check fit</a><a class="cta" href="{esc(offer['tracking_url'])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer="" data-offer-id="{esc(offer['id'])}" data-placement="tool-finder">{esc(offer['cta_label'])} →</a></div>
        </article>'''
        for index, offer in enumerate(offers)
    )
    structured = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "AI tool finder",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": index,
                "name": offer["name"],
                "url": f"https://artificial.one/partner-offers/{offer['slug']}.html",
            }
            for index, offer in enumerate(offers, 1)
        ],
    }
    content = f'''
    <section class="finder-hero"><div><p class="eyebrow">Performance-ranked recommendations</p><h1>Find the right AI tool for your job</h1><p>Choose a category or describe what you need. Recommendations are automatically reordered using anonymous impressions, affiliate clicks and attributed conversion signals.</p></div></section>
    <section class="finder"><div class="controls"><label for="tool-search">What do you want to accomplish?</label><input id="tool-search" type="search" placeholder="For example: edit a podcast, build a website, find sales leads"><div class="filters"><button type="button" class="active" data-filter="all">All tools</button>{category_buttons}</div><p id="finder-count" aria-live="polite"></p></div><div id="tool-grid" class="tool-grid">{cards}</div><div id="no-tools" class="empty" hidden>No exact match yet. Try a broader phrase or browse all tools.</div></section>
    <style>.finder-hero{{background:linear-gradient(135deg,#eef2ff,#faf5ff);padding:72px 22px;text-align:center}}.finder-hero>div,.finder{{max-width:1120px;margin:auto}}.finder-hero h1{{font-size:clamp(2.5rem,7vw,4.8rem);line-height:1.02;margin:14px 0}}.finder-hero p{{max-width:780px;margin:0 auto;color:#475569;font-size:1.1rem;line-height:1.7}}.eyebrow{{color:#4f46e5;font-size:.78rem;font-weight:800;letter-spacing:.09em;text-transform:uppercase}}.finder{{padding:44px 22px 80px}}.controls{{background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:24px;margin-bottom:26px}}.controls label{{display:block;font-weight:800;margin-bottom:9px}}.controls input{{width:100%;padding:14px 16px;border:1px solid #cbd5e1;border-radius:11px;font:inherit}}.filters{{display:flex;gap:9px;flex-wrap:wrap;margin-top:16px}}.filters button{{border:1px solid #cbd5e1;background:#fff;border-radius:999px;padding:8px 13px;cursor:pointer}}.filters button.active{{background:#4338ca;color:#fff;border-color:#4338ca}}#finder-count{{color:#64748b;margin:14px 0 0}}.tool-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}.tool{{display:flex;flex-direction:column;background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:23px;box-shadow:0 4px 14px rgba(15,23,42,.05)}}.tool h2{{font-size:1.35rem;margin:6px 0 12px}}.tool>p:not(.eyebrow){{color:#64748b;line-height:1.55}}.tool .best{{font-size:.9rem;margin-top:auto;padding-top:15px}}.actions{{display:flex;gap:10px;margin-top:18px}}.actions a{{flex:1;text-align:center;padding:11px;border-radius:9px;text-decoration:none;font-weight:750}}.details{{border:1px solid #c7d2fe;color:#4338ca}}.cta{{background:#4338ca;color:#fff}}.empty{{text-align:center;padding:40px;color:#64748b}}@media(max-width:900px){{.tool-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:620px){{.tool-grid{{grid-template-columns:1fr}}.actions{{flex-direction:column}}}}</style>
    <script>(function(){{var search=document.getElementById('tool-search'),buttons=[].slice.call(document.querySelectorAll('[data-filter]')),cards=[].slice.call(document.querySelectorAll('.tool')),count=document.getElementById('finder-count'),empty=document.getElementById('no-tools'),filter='all',stop={{a:1,an:1,and:1,build:1,create:1,find:1,for:1,my:1,need:1,the:1,tool:1,use:1,want:1,with:1}};function update(){{var query=search.value.trim().toLowerCase(),tokens=query.split(/\\s+/).filter(function(word){{return word.length>2&&!stop[word];}}),shown=0;cards.forEach(function(card){{var matchCategory=filter==='all'||card.dataset.category===filter;var matchText=!tokens.length||tokens.every(function(word){{return card.dataset.search.indexOf(word)>-1;}});card.hidden=!(matchCategory&&matchText);if(!card.hidden)shown++;}});count.textContent=shown+' matching verified partner tool'+(shown===1?'':'s');empty.hidden=shown!==0;}}buttons.forEach(function(button){{button.addEventListener('click',function(){{filter=button.dataset.filter;buttons.forEach(function(item){{item.classList.toggle('active',item===button);}});update();}});}});search.addEventListener('input',update);update();}})();</script>'''
    return shell(
        title="AI Tool Finder: Match Your Goal to the Right Tool | artificial.one",
        description="Find an AI or business tool matched to your use case, with transparent, performance-ranked partner recommendations.",
        canonical_path="ai-tool-finder.html",
        content=content,
        structured_data=structured,
    )


def render_homepage_picks(offers: list[dict[str, Any]], limit: int = 6) -> str:
    cards = "\n".join(
        f'''              <article className="rounded-2xl border border-slate-700 bg-slate-900 p-7">
                <p className="text-xs font-bold uppercase tracking-widest text-emerald-300">{esc(offer['category'])}</p>
                <h3 className="text-2xl font-bold mt-3">{esc(offer['name'])}</h3>
                <p className="text-slate-300 mt-3">{esc(offer['summary'])}</p>
                <p className="text-sm text-slate-400 mt-5">Best for {esc(offer['best_for'])}</p>
                <a href="partner-offers/{esc(offer['slug'])}.html" className="inline-block mt-6 rounded-lg bg-indigo-600 px-5 py-3 font-semibold hover:bg-indigo-500">Check fit &amp; current offer →</a>
              </article>'''
        for offer in offers[:limit]
    )
    return f"{HOME_PICKS_START}\n{cards}\n              {HOME_PICKS_END}"


def update_homepage_picks(source: str, offers: list[dict[str, Any]]) -> str:
    pattern = re.compile(re.escape(HOME_PICKS_START) + r".*?" + re.escape(HOME_PICKS_END), re.S)
    if not pattern.search(source):
        raise OfferValidationError("Homepage revenue pick markers are missing")
    return pattern.sub(render_homepage_picks(offers), source, count=1)


def related_offers_for(
    offer: dict[str, Any], offers: list[dict[str, Any]], limit: int = 3
) -> list[dict[str, Any]]:
    candidates = [item for item in offers if item["id"] != offer["id"]]
    return sorted(
        candidates,
        key=lambda item: (
            item.get("category") != offer.get("category"),
            not bool(item.get("featured")),
            item["name"].lower(),
        ),
    )[:limit]


def _search_slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.casefold())).strip("-")


def _intent_cluster(category: str) -> str:
    normalized = category.casefold()
    groups = (
        ("growth", ("advert", "conversion", "email", "marketing", "research", "sales", "seo")),
        ("content", ("audio", "design", "presentation", "video", "voice", "web")),
        ("documents", ("document", "pdf", "signature")),
        ("operations", ("automation", "business", "course", "education", "erp", "learning", "practice", "productivity", "tracking", "training")),
        ("data", ("data", "database", "developer")),
    )
    for group, terms in groups:
        if any(term in normalized for term in terms):
            return group
    return normalized


def search_links_for(offer: dict[str, Any], offers: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Link review pages into the deterministic commercial-intent cluster."""
    links: list[tuple[str, str]] = []
    if offer in offers[:8]:
        links.append((f"../search-intent/{offer['slug']}-alternatives.html", f"Best {offer['name']} alternatives"))
    if offer in offers[:6]:
        links.append((f"../search-intent/{offer['slug']}-pricing.html", f"{offer['name']} pricing guide"))
        use_cases = [str(item) for item in offer.get("use_cases", []) if str(item).strip()]
        if use_cases:
            links.append((f"../search-intent/{offer['slug']}-for-{_search_slug(use_cases[0])}.html", f"{offer['name']} for {use_cases[0]}"))
        alternatives = [
            item for item in offers
            if item.get("id") != offer.get("id") and _intent_cluster(str(item.get("category", ""))) == _intent_cluster(str(offer.get("category", "")))
        ]
        if alternatives:
            links.append((f"../search-intent/{offer['slug']}-vs-{alternatives[0]['slug']}.html", f"{offer['name']} vs {alternatives[0]['name']}"))
    members = [item for item in offers if item.get("category") == offer.get("category")]
    if len(members) >= 2:
        category_slug = _search_slug(str(offer["category"]))
        links.append((f"../search-intent/best-{category_slug}-tools.html", f"Best {offer['category']} tools"))
        left, right = members[:2]
        if offer in (left, right):
            links.append((f"../search-intent/{left['slug']}-vs-{right['slug']}.html", f"{left['name']} vs {right['name']}"))
    return links


def render_offer(
    offer: dict[str, Any], related_offers: list[dict[str, Any]] | None = None,
    search_links: list[tuple[str, str]] | None = None,
) -> str:
    title, description = search_snippet(offer)
    review_link = ""
    if offer.get("review_url"):
        review_link = f'<a href="../{esc(offer["review_url"])}" class="font-semibold text-indigo-700 hover:underline">Read the full independent review →</a>'

    evidence = "".join(
        f'<li><a class="text-indigo-700 hover:underline" href="{esc(item["url"])}" target="_blank" rel="noopener">{esc(item["label"])} ↗</a></li>'
        for item in offer["evidence"]
    )
    use_cases = "".join(
        f'<li class="flex gap-3"><span class="mt-1 text-indigo-600" aria-hidden="true">✓</span><span>{esc(item)}</span></li>'
        for item in offer["use_cases"]
    )
    sponsored = "Sponsored commercial relationship" if offer.get("sponsored") else "Affiliate relationship"
    expiry = esc(offer.get("expires_at") or "No fixed end date supplied")
    related_cards = "".join(
        f'''<a href="{esc(item['slug'])}.html" class="block rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-indigo-300 hover:shadow-md">
          <p class="text-xs font-bold uppercase tracking-wide text-indigo-600">{esc(item['category'])}</p>
          <h3 class="mt-2 text-lg font-bold">{esc(item['name'])}</h3>
          <p class="mt-2 text-sm text-slate-600">{esc(item['best_for'])}</p>
          <span class="mt-4 inline-block text-sm font-semibold text-indigo-700">Compare fit →</span>
        </a>'''
        for item in (related_offers or [])
    )
    related_section = ""
    if related_cards:
        related_section = f'''<section class="mx-auto max-w-4xl px-5 pb-6">
      <h2 class="text-2xl font-bold">Compare other tools before deciding</h2>
      <div class="mt-5 grid gap-4 md:grid-cols-3">{related_cards}</div>
    </section>'''
    intent_section = ""
    if search_links:
        intent_links = "".join(
            f'<a class="rounded-full border border-indigo-200 bg-white px-4 py-2 font-semibold text-indigo-700 hover:bg-indigo-50" href="{esc(url)}">{esc(label)} →</a>'
            for url, label in search_links
        )
        intent_section = f'''<section class="mx-auto max-w-4xl px-5 pb-10">
      <h2 class="text-2xl font-bold">Compare before you choose</h2>
      <div class="mt-4 flex flex-wrap gap-3">{intent_links}</div>
    </section>'''
    content = f'''
    <section class="bg-white">
      <div class="mx-auto max-w-4xl px-5 py-16">
        <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">{esc(offer["category"])}</p>
        <h1 class="mt-4 text-4xl font-black md:text-5xl">{esc(offer["name"])} partner offer</h1>
        <p class="mt-6 text-xl text-slate-600">{esc(offer["summary"])}</p>
        <div class="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
          <h2 class="text-sm font-bold uppercase tracking-wide text-emerald-800">Pricing and current offer</h2>
          <p class="mt-2 text-2xl font-bold text-emerald-950">{esc(offer["offer_label"])}</p>
          <p class="mt-2 text-emerald-900">{esc(offer["pricing_note"])}</p>
          <a href="{esc(offer["tracking_url"])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{esc(offer["id"])}" data-placement="offer-page-primary" class="btn-primary mt-6 inline-block rounded-xl px-7 py-4 font-bold text-white">{esc(offer["cta_label"])} →</a>
          <p class="mt-3 text-xs text-emerald-900">Affiliate link. We may earn a commission; your price does not increase.</p>
        </div>
      </div>
    </section>
    <section class="mx-auto grid max-w-4xl gap-6 px-5 py-10 md:grid-cols-2">
      <article class="rounded-2xl border border-slate-200 bg-white p-6">
        <h2 class="text-xl font-bold">Who it is best for</h2><p class="mt-3 text-slate-600">{esc(offer["best_for"])}</p>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-6">
        <h2 class="text-xl font-bold">Commercial disclosure</h2><p class="mt-3 text-slate-600">{sponsored}. The relationship does not change our editorial assessment.</p>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-6 md:col-span-2">
        <h2 class="text-xl font-bold">Why consider {esc(offer["name"])}</h2>
        <p class="mt-3 text-slate-600">{esc(offer["why_consider"])}</p>
        <h3 class="mt-6 font-bold">Practical use cases</h3>
        <ul class="mt-3 grid gap-3 text-slate-700 sm:grid-cols-2">{use_cases}</ul>
      </article>
      <article class="rounded-2xl border border-amber-200 bg-amber-50 p-6 md:col-span-2">
        <h2 class="text-xl font-bold text-amber-950">Before you choose</h2>
        <p class="mt-3 text-amber-900">{esc(offer["watch_out"])}</p>
      </article>
      <article class="rounded-2xl border border-slate-200 bg-white p-6 md:col-span-2">
        <h2 class="text-xl font-bold">Verification record</h2>
        <dl class="mt-4 grid gap-3 text-sm sm:grid-cols-3"><div><dt class="text-slate-500">Terms checked</dt><dd class="font-semibold">{esc(offer["terms_verified_at"])}</dd></div><div><dt class="text-slate-500">Offer expiry</dt><dd class="font-semibold">{expiry}</dd></div><div><dt class="text-slate-500">Editorial approval</dt><dd class="font-semibold">{esc(offer["approved_at"])}</dd></div></dl>
        <h3 class="mt-6 font-bold">Sources</h3><ul class="mt-2 list-inside list-disc space-y-2 text-sm">{evidence}</ul>
      </article>
      <div class="md:col-span-2">{review_link}</div>
    </section>
    <section class="mx-auto max-w-4xl px-5 pb-12">
      <div class="rounded-2xl border border-indigo-200 bg-indigo-50 p-7 text-center">
        <h2 class="text-2xl font-bold">Ready to evaluate {esc(offer['name'])}?</h2>
        <p class="mx-auto mt-3 max-w-2xl text-slate-600">Open the verified partner destination to confirm today’s plans, limits and terms before subscribing.</p>
        <a href="{esc(offer['tracking_url'])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{esc(offer['id'])}" data-placement="offer-page-bottom" class="btn-primary mt-6 inline-block rounded-xl px-7 py-4 font-bold text-white">{esc(offer['cta_label'])} →</a>
        <p class="mt-3 text-xs text-slate-600">Affiliate link. We may earn a commission; your price does not increase.</p>
      </div>
    </section>
{intent_section}{related_section}'''
    return shell(
        title=title,
        description=description,
        canonical_path=f"partner-offers/{offer['slug']}.html",
        content=content,
        prefix="../",
        social_image=f"https://artificial.one/images/social-cards/{offer['id']}.jpg",
        social_image_alt=f"Independent {offer['name']} fit, use-case and pricing guide from Artificial.One",
        structured_data={
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "SoftwareApplication",
                    "name": offer["name"],
                    "applicationCategory": offer["category"],
                    "description": offer["summary"],
                    "url": f"https://artificial.one/partner-offers/{offer['slug']}.html",
                },
                {
                    "@type": "BreadcrumbList",
                    "itemListElement": [
                        {
                            "@type": "ListItem",
                            "position": 1,
                            "name": "Partner offers",
                            "item": "https://artificial.one/partner-offers.html",
                        },
                        {
                            "@type": "ListItem",
                            "position": 2,
                            "name": offer["name"],
                            "item": f"https://artificial.one/partner-offers/{offer['slug']}.html",
                        },
                    ],
                },
            ],
        },
    )


def render_finder(offers: list[dict[str, Any]]) -> str:
    """Render the explainable task-first matcher and the full verified catalog."""
    categories = sorted({str(offer["category"]) for offer in offers})
    category_buttons = "".join(
        f'<button type="button" data-filter="{esc(category)}">{esc(category)}</button>'
        for category in categories
    )
    cards = "".join(offer_card(offer, "tool-finder") for offer in offers)
    content = f'''
    <section class="hero"><div class="container"><p class="eyebrow">AI decision engine</p><h1>Tell us what you need. <span class="gradient-text">We’ll shortlist the AI tools worth paying for.</span></h1><p class="hero-copy">Find the right AI tool for your job. Describe the outcome, get three explainable matches, then compare before you click.</p>
      <form class="matcher" data-matcher-form><label for="finder-task"><strong>What do you want to accomplish?</strong></label><div class="matcher-row"><input id="finder-task" type="search" placeholder="e.g. Turn a webinar into clips and captions"><button class="btn btn-acid" type="submit">Show my best 3</button></div><div class="mission-list"><button class="mission" type="button" data-mission="create" data-prompt="Create video, audio, images or written content">Create</button><button class="mission" type="button" data-mission="sell" data-prompt="Get leads and improve marketing conversion">Sell</button><button class="mission" type="button" data-mission="automate" data-prompt="Automate repetitive business workflows">Automate</button><button class="mission" type="button" data-mission="research" data-prompt="Research markets, documents or data">Research</button><button class="mission" type="button" data-mission="build" data-prompt="Build a website, app or AI workflow">Build</button></div><p class="matcher-note">No sign-up. Scores explain task fit; partner relationships never guarantee placement.</p></form>
      <div class="results" data-matcher-results><div class="results-head"><h2>Your best three</h2><span>Ranked by task fit, evidence and verified availability</span></div><div class="results-grid" data-matcher-results-grid></div></div>
    </div></section>
    <section class="container section-tight"><div class="catalog-controls surface"><label for="tool-search">Or browse every verified tool</label><input id="tool-search" type="search" placeholder="Search by task, category or product"><div class="filters"><button type="button" class="active" data-filter="all">All tools</button>{category_buttons}</div><p id="finder-count" aria-live="polite"></p></div><div id="tool-grid" class="card-grid">{cards}</div><div id="no-tools" class="empty" hidden>No exact match yet. Try a broader phrase or browse all tools.</div></section>{catalog_script(offers)}'''
    return shell(
        title="AI Tool Finder: Match Your Goal to the Right Tool | artificial.one",
        description="Describe the outcome you want and get three explainable AI-tool matches, with verified terms, limitations and transparent partner links.",
        canonical_path="ai-tool-finder.html",
        content=content,
        structured_data={
            "@context": "https://schema.org", "@type": "ItemList", "name": "AI tool finder",
            "itemListElement": [{"@type": "ListItem", "position": index, "name": offer["name"], "url": f"https://artificial.one/partner-offers/{offer['slug']}.html"} for index, offer in enumerate(offers, 1)],
        },
    )


def render_homepage_picks(offers: list[dict[str, Any]], limit: int = 6) -> str:
    cards = "\n".join(offer_card(offer, "homepage-pick") for offer in offers[:limit])
    return f"{HOME_PICKS_START}\n{cards}\n{HOME_PICKS_END}"


def render_homepage_catalog(offers: list[dict[str, Any]]) -> str:
    return f"{HOME_CATALOG_START}\n{catalog_script(offers)}\n{HOME_CATALOG_END}"


def update_homepage_picks(source: str, offers: list[dict[str, Any]]) -> str:
    picks_pattern = re.compile(re.escape(HOME_PICKS_START) + r".*?" + re.escape(HOME_PICKS_END), re.S)
    if not picks_pattern.search(source):
        raise OfferValidationError("Homepage revenue pick markers are missing")
    source = picks_pattern.sub(render_homepage_picks(offers), source, count=1)
    source = re.sub(r"<strong>\d+</strong> verified partner offers", f"<strong>{len(offers)}</strong> verified partner offers", source, count=1)
    catalog_pattern = re.compile(re.escape(HOME_CATALOG_START) + r".*?" + re.escape(HOME_CATALOG_END), re.S)
    if not catalog_pattern.search(source):
        raise OfferValidationError("Homepage matcher catalog markers are missing")
    return catalog_pattern.sub(render_homepage_catalog(offers), source, count=1)


def render_offer(
    offer: dict[str, Any], related_offers: list[dict[str, Any]] | None = None,
    search_links: list[tuple[str, str]] | None = None,
) -> str:
    """Render a reusable decision page designed to answer fit before the affiliate click."""
    title, description = search_snippet(offer)
    data = public_offer_data(offer, "../")
    use_cases = outcome_use_cases(offer)
    use_case_buttons = "".join(
        f'<button class="tab{(" is-active" if index == 0 else "")}" type="button" data-tab data-content="{esc(item)}">Use case {index + 1}</button>'
        for index, item in enumerate(use_cases)
    )
    evidence = "".join(
        f'<li><a class="link-subtle" href="{esc(item["url"])}" target="_blank" rel="noopener">{esc(item["label"])} ↗</a></li>'
        for item in offer["evidence"]
    )
    related = related_offers or []
    related_cards = "".join(offer_card(item, "offer-alternative").replace('href="partner-offers/', 'href="') for item in related[:2])
    intent_links = "".join(
        f'<a href="{esc(url)}">{esc(label)} →</a>' for url, label in (search_links or [])
    )
    review_link = (
        f'<a class="link-subtle" href="../{esc(offer["review_url"])}">Read the full independent review →</a>'
        if offer.get("review_url") else ""
    )
    relationship = "Sponsored commercial relationship" if offer.get("sponsored") else "Affiliate relationship"
    expiry = esc(offer.get("expires_at") or "No fixed end date supplied")
    faq = [
        (f"Who is {offer['name']} best for?", str(offer["best_for"])),
        (f"What should I check before buying {offer['name']}?", str(offer["watch_out"])),
        ("Is this an affiliate link?", "Yes. Artificial.One may earn a commission from qualifying purchases at no extra cost to you. The relationship does not buy a positive verdict."),
    ]
    faq_html = "".join(f'<details><summary>{esc(question)}</summary><p>{esc(answer)}</p></details>' for question, answer in faq)
    content = f'''
    <section class="offer-hero"><div class="container offer-grid"><div><p class="eyebrow">{esc(offer['category'])} · independent fit check</p><div class="offer-product-visual product-visual"><img src="{esc(data['screenshotUrl'])}" alt="{esc(offer['name'])} product website screenshot" width="1000" height="563" loading="lazy" decoding="async"><span class="product-logo"><img src="{esc(data['logoUrl'])}" alt="{esc(offer['name'])} logo" width="56" height="56" decoding="async"><b aria-hidden="true">{esc(offer['name'][:2])}</b></span></div><h1>{esc(offer['name'])}: <span class="gradient-text">is it right for your job?</span></h1><p class="lead">{esc(offer['summary'])}</p><div class="verdict"><strong>One-line verdict</strong><p>{esc(offer['why_consider'])}</p></div><div class="loop-actions"><button class="btn btn-secondary compare-add" type="button" data-id="{esc(offer['id'])}">⇄ Add to comparison</button><button class="btn btn-secondary stack-add" type="button" data-id="{esc(offer['id'])}">＋ Save to My Stack</button><button class="btn btn-secondary" type="button" data-watch-offer="{esc(offer['id'])}">Watch this deal</button></div></div>
      <aside class="surface offer-aside"><p class="eyebrow">Current buying facts</p><h2>{esc(data['price'])}</h2><dl class="buying-facts"><div><dt>Trial</dt><dd>{esc(data['trial'])}</dd></div><div><dt>Last verified</dt><dd>{esc(offer['terms_verified_at'])}</dd></div></dl><p class="price-note">{esc(offer['pricing_note'])}</p><a class="btn btn-acid" href="{esc(offer['tracking_url'])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{esc(offer['id'])}" data-placement="offer-page-primary">{esc(data['cta'])} →</a><p class="verified-line">✓ Product, destination and terms checked {esc(offer['terms_verified_at'])}</p><p class="disclosure">Affiliate link. We may earn a commission; your price does not increase.</p></aside>
    </div></section>
    <section class="container section-tight"><div class="content-grid">
      <article class="surface content-card"><h2>Best for</h2><p>{esc(offer['best_for'])}</p></article>
      <article class="surface content-card warn"><h2>Not ideal when…</h2><p>{esc(offer['watch_out'])}</p></article>
      <article class="surface content-card span-2" data-tabs data-offer-id="{esc(offer['id'])}"><h2>What can you do with it?</h2><div class="tabs">{use_case_buttons}</div><div class="tab-panel" data-tab-panel>{esc(use_cases[0])}</div></article>
      <article class="surface content-card"><h2>Why it makes the shortlist</h2><p>{esc(offer['why_consider'])}</p><h3>Practical strengths</h3><ul><li>Focused fit for the use cases above</li><li>Current partner destination has been checked</li><li>Can be compared and saved without an account</li></ul></article>
      <article class="surface content-card warn"><h2>Limitations</h2><p>{esc(offer['watch_out'])}</p><p>Features, allowances and pricing can change. Confirm the live plan before paying.</p></article>
      <article class="surface content-card span-2"><h2>Will it pay for itself?</h2><p class="disclosure">This calculator is illustrative, not a promise of savings.</p><form class="calculator" data-value-calculator><label>Monthly tool cost ($)<input name="monthly" type="number" min="0" value="30"></label><label>Hours saved monthly<input name="hours" type="number" min="0" value="4"></label><label>Your hour value ($)<input name="value" type="number" min="0" value="25"></label><output class="calc-result" data-calc-output></output></form></article>
      <article class="surface content-card span-2"><h2>Verification &amp; disclosure</h2><p>{relationship}. This does not change our editorial assessment.</p><dl class="trust-grid"><div class="stat"><strong>{esc(offer['terms_verified_at'])}</strong><span>Terms checked</span></div><div class="stat"><strong>{expiry}</strong><span>Offer expiry</span></div><div class="stat"><strong>{esc(offer['approved_at'])}</strong><span>Editorial approval</span></div></dl><h3>Primary sources</h3><ul>{evidence}</ul>{review_link}</article>
      <article class="surface content-card span-2 faq"><h2>Questions before you decide</h2>{faq_html}</article>
    </div></section>
    <section class="container section-tight"><div class="section-head"><div><p class="eyebrow">Keep your options open</p><h2>Two alternatives to compare</h2></div></div><div class="card-grid">{related_cards}</div></section>
    <section class="container section-tight"><div class="surface content-card"><h2>Continue the workflow</h2><div class="related-links">{intent_links}<a href="../ai-tool-finder.html">Run a fresh tool match →</a></div></div></section>
    <section class="narrow section-tight"><div class="surface loop-card"><h2>Ready to evaluate {esc(offer['name'])}?</h2><p>Open the verified destination and confirm today’s plan, limits and terms.</p><a class="btn btn-acid" href="{esc(offer['tracking_url'])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{esc(offer['id'])}" data-placement="offer-page-bottom">{esc(data['cta'])} →</a><p class="disclosure">Affiliate link. We may earn a commission; your price does not increase.</p></div></section>
    <div class="mobile-offer-cta"><a class="btn btn-acid" href="{esc(offer['tracking_url'])}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{esc(offer['id'])}" data-placement="offer-page-mobile">{esc(data['cta'])} →</a></div>
    {catalog_script([offer, *related], '../')}'''
    structured = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "SoftwareApplication", "name": offer["name"], "applicationCategory": offer["category"], "description": offer["summary"], "url": f"https://artificial.one/partner-offers/{offer['slug']}.html"},
            {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Partner offers", "item": "https://artificial.one/partner-offers.html"}, {"@type": "ListItem", "position": 2, "name": offer["name"], "item": f"https://artificial.one/partner-offers/{offer['slug']}.html"}]},
            {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": question, "acceptedAnswer": {"@type": "Answer", "text": answer}} for question, answer in faq]},
        ],
    }
    return shell(
        title=title, description=description,
        canonical_path=f"partner-offers/{offer['slug']}.html", content=content, prefix="../",
        social_image=f"https://artificial.one/images/social-cards/{offer['id']}.jpg",
        social_image_alt=f"Independent {offer['name']} fit, use-case and pricing guide from Artificial.One",
        structured_data=structured,
    )


def sitemap_block(offers: list[dict[str, Any]], lastmod: str) -> str:
    pages = [
        ("https://artificial.one/partners.html", "0.7"),
        ("https://artificial.one/partner-offers.html", "0.8"),
        ("https://artificial.one/ai-tool-finder.html", "0.9"),
    ]
    pages.extend(
        (f"https://artificial.one/partner-offers/{offer['slug']}.html", "0.8")
        for offer in offers
    )
    rows = [SITEMAP_START]
    for url, priority in pages:
        rows.extend(
            [
                "  <url>",
                f"    <loc>{url}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "    <changefreq>weekly</changefreq>",
                f"    <priority>{priority}</priority>",
                "  </url>",
            ]
        )
    rows.append(SITEMAP_END)
    return "\n".join(rows)


def expected_sitemap(current: str, block: str) -> str:
    if SITEMAP_START in current and SITEMAP_END in current:
        pattern = re.compile(
            rf"{re.escape(SITEMAP_START)}.*?{re.escape(SITEMAP_END)}", re.DOTALL
        )
        current = pattern.sub("", current)

    # Other sitemap updaters may drop XML comments and add these pages themselves.
    # Remove any such entries before inserting the single block owned by this builder.
    managed_url = re.compile(
        r"\s*<url>\s*<loc>https://artificial\.one/"
        r"(?:partners\.html|partner-offers\.html|ai-tool-finder\.html|partner-offers/[^<]+)"
        r"</loc>.*?</url>",
        re.DOTALL,
    )
    current = managed_url.sub("", current)
    closing = "</urlset>"
    if closing not in current:
        raise OfferValidationError("sitemap.xml has no closing urlset element")
    # Keep the publisher-owned blocks in a stable order. The search revenue
    # builder appends its block after this one.
    search_marker = "  <!-- search-revenue:start -->"
    if search_marker in current:
        before, after = current.split(search_marker, 1)
        return f"{before.rstrip()}\n{block}\n{search_marker}{after}"
    before_close = current.rsplit(closing, 1)[0].rstrip()
    return f"{before_close}\n{block}\n{closing}\n"


def build(registry_path: Path, check: bool = False) -> int:
    registry = load_registry(registry_path)
    offers = apply_revenue_strategy(public_offers(validate_registry(registry), date.today()))
    lastmod = registry["updated_at"]
    expected: dict[Path, str] = {
        HUB_PATH: render_hub(offers),
        FINDER_PATH: render_finder(offers),
        HOME_PATH: update_homepage_picks(HOME_PATH.read_text(encoding="utf-8"), offers),
    }
    expected.update(
        {
            OFFER_DIRECTORY / f"{offer['slug']}.html": render_offer(
                offer, related_offers_for(offer, offers), search_links_for(offer, offers)
            )
            for offer in offers
        }
    )

    sitemap_current = SITEMAP_PATH.read_text(encoding="utf-8")
    sitemap_expected = expected_sitemap(sitemap_current, sitemap_block(offers, lastmod))

    if check:
        stale = [str(path.relative_to(ROOT)) for path, value in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != value]
        if sitemap_current != sitemap_expected:
            stale.append("sitemap.xml")
        if stale:
            print("Partner offer build is stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"Partner offer build is current ({len(offers)} published offers).")
        return 0

    OFFER_DIRECTORY.mkdir(exist_ok=True)
    for path, value in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    active_names = {f"{offer['slug']}.html" for offer in offers}
    for path in OFFER_DIRECTORY.glob("*.html"):
        if path.name not in active_names and GENERATED_MARKER in path.read_text(encoding="utf-8"):
            path.unlink()

    SITEMAP_PATH.write_text(sitemap_expected, encoding="utf-8")
    print(f"Built partner offer hub and {len(offers)} published offer pages.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--check", action="store_true", help="Fail if generated pages are stale")
    args = parser.parse_args()
    try:
        return build(args.registry.resolve(), check=args.check)
    except OfferValidationError as exc:
        print(f"Partner offer validation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
