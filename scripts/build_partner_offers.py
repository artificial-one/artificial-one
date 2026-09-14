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
HUB_PATH = ROOT / "partner-offers.html"
OFFER_DIRECTORY = ROOT / "partner-offers"
SITEMAP_PATH = ROOT / "sitemap.xml"
GENERATED_MARKER = "<!-- GENERATED: partner-offer-pipeline -->"
SITEMAP_START = "  <!-- partner-offers:start -->"
SITEMAP_END = "  <!-- partner-offers:end -->"
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
        r"(?:partners\.html|partner-offers\.html|partner-offers/[^<]+)"
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
    offers = public_offers(validate_registry(registry), date.today())
    lastmod = registry["updated_at"]
    expected: dict[Path, str] = {HUB_PATH: render_hub(offers)}
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
