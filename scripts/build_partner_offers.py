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
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
HUB_PATH = ROOT / "partner-offers.html"
FINDER_PATH = ROOT / "ai-tool-finder.html"
HOME_PATH = ROOT / "index.html"
OFFER_DIRECTORY = ROOT / "partner-offers"
SITEMAP_PATH = ROOT / "sitemap.xml"
GENERATED_MARKER = "<!-- GENERATED: partner-offer-pipeline -->"
SITEMAP_START = "  <!-- partner-offers:start -->"
SITEMAP_END = "  <!-- partner-offers:end -->"
HOME_PICKS_START = "{/* revenue-picks:start */}"
HOME_PICKS_END = "{/* revenue-picks:end */}"
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
) -> str:
    canonical = f"https://artificial.one/{canonical_path}"
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
  <meta property="og:image" content="https://artificial.one/images/og-homepage.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="affiliate-event-endpoint" content="/api/affiliate-event">
  {json_ld(structured_data) if structured_data else ""}
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .gradient-text {{ background: linear-gradient(135deg,#4f46e5,#9333ea,#db2777); -webkit-background-clip:text; color:transparent; }}
    .btn-primary {{ background:linear-gradient(135deg,#4f46e5,#9333ea); transition:.2s ease; }}
    .btn-primary:hover {{ transform:translateY(-2px); box-shadow:0 12px 28px rgba(79,70,229,.25); }}
  </style>
</head>
<body class="bg-slate-50 text-slate-900">
  {GENERATED_MARKER}
  <header class="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
    <div class="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
      <a href="{prefix}index.html"><img src="{prefix}artificial-one-logo-large.svg" alt="artificial.one" class="h-14"></a>
      <nav class="flex items-center gap-5 text-sm font-semibold">
        <a href="{prefix}reviews.html" class="text-slate-600 hover:text-indigo-600">Reviews</a>
        <a href="{prefix}ai-tool-finder.html" class="text-indigo-700">Tool finder</a>
        <a href="{prefix}partner-offers.html" class="text-indigo-700">Partner offers</a>
        <a href="{prefix}partners.html" class="rounded-lg border border-indigo-200 px-4 py-2 text-indigo-700 hover:bg-indigo-50">For partners</a>
      </nav>
    </div>
  </header>
  <main>{content}</main>
  <footer class="mt-16 border-t border-slate-200 bg-white">
    <div class="mx-auto max-w-6xl px-5 py-10 text-sm text-slate-600">
      <p class="font-semibold text-slate-800">artificial.one</p>
      <p class="mt-2">We may earn a commission when you buy through marked partner links, at no extra cost to you. Commercial relationships never guarantee a positive review.</p>
      <div class="mt-4 flex flex-wrap gap-4"><a class="text-indigo-700" href="{prefix}about.html">About</a><a class="text-indigo-700" href="{prefix}partners.html">Work with us</a><a class="text-indigo-700" href="mailto:hello@artificial.one">Contact</a></div>
    </div>
  </footer>
  <script src="{prefix}assets/affiliate-tracking.js" defer></script>
</body>
</html>
'''


def offer_card(offer: dict[str, Any]) -> str:
    badge = "Featured" if offer.get("featured") else esc(offer["category"])
    return f'''
      <article class="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-center justify-between gap-3"><span class="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-indigo-700">{badge}</span><span class="text-xs text-slate-500">Terms checked {esc(offer["terms_verified_at"])}</span></div>
        <h2 class="mt-5 text-2xl font-bold">{esc(offer["name"])}</h2>
        <p class="mt-3 flex-1 text-slate-600">{esc(offer["summary"])}</p>
        <p class="mt-5 text-sm font-semibold text-emerald-700">{esc(offer["offer_label"])}</p>
        <p class="mt-1 text-sm text-slate-500">{esc(offer["pricing_note"])}</p>
        <a href="partner-offers/{esc(offer['slug'])}.html" class="mt-6 font-semibold text-indigo-700 hover:underline">See our offer analysis →</a>
      </article>'''


def render_hub(offers: list[dict[str, Any]]) -> str:
    if offers:
        cards = "\n".join(offer_card(offer) for offer in offers)
        listing = f'<div class="mt-10 grid gap-6 md:grid-cols-2 lg:grid-cols-3">{cards}</div>'
        lead = f"{len(offers)} currently verified partner offer{'s' if len(offers) != 1 else ''}."
    else:
        listing = '''<div class="mt-10 rounded-2xl border border-dashed border-indigo-300 bg-indigo-50 p-10 text-center">
          <h2 class="text-2xl font-bold">The first verified offers are being reviewed</h2>
          <p class="mx-auto mt-3 max-w-2xl text-slate-600">We publish an offer only after its terms, destination and audience fit have been checked. Join the newsletter or return soon for the first release.</p>
          <a href="partners.html" class="mt-6 inline-block font-semibold text-indigo-700 hover:underline">Represent an AI product? Submit an offer →</a>
        </div>'''
        lead = "A curated feed of partner offers, selected for usefulness rather than commission size."

    content = f'''
    <section class="bg-white">
      <div class="mx-auto max-w-6xl px-5 py-20 text-center">
        <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Commercially transparent</p>
        <h1 class="mt-4 text-4xl font-black md:text-6xl">Verified AI <span class="gradient-text">partner offers</span></h1>
        <p class="mx-auto mt-6 max-w-3xl text-lg text-slate-600">{lead} Every listing identifies sponsored links and shows when terms were last checked.</p>
      </div>
    </section>
    <section class="mx-auto max-w-6xl px-5 py-12">
      <div class="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950"><strong>How we earn:</strong> marked links may pay artificial.one a commission. You pay no extra. Payment does not buy a positive verdict or guaranteed placement.</div>
      {listing}
    </section>'''
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


def render_homepage_picks(offers: list[dict[str, Any]], limit: int = 4) -> str:
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


def render_offer(
    offer: dict[str, Any], related_offers: list[dict[str, Any]] | None = None
) -> str:
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
    content = f'''
    <section class="bg-white">
      <div class="mx-auto max-w-4xl px-5 py-16">
        <p class="text-sm font-bold uppercase tracking-widest text-indigo-600">{esc(offer["category"])}</p>
        <h1 class="mt-4 text-4xl font-black md:text-5xl">{esc(offer["name"])} partner offer</h1>
        <p class="mt-6 text-xl text-slate-600">{esc(offer["summary"])}</p>
        <div class="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-6">
          <p class="text-sm font-bold uppercase tracking-wide text-emerald-800">Current offer</p>
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
    {related_section}'''
    return shell(
        title=f"{offer['name']}: Use Cases, Fit & Partner Offer | artificial.one",
        description=f"Evaluate {offer['name']}, who it suits, practical use cases, limitations and the current verified partner offer. Terms checked {offer['terms_verified_at']}.",
        canonical_path=f"partner-offers/{offer['slug']}.html",
        content=content,
        prefix="../",
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
                offer, related_offers_for(offer, offers)
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
