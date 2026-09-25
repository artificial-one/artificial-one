#!/usr/bin/env python3
"""Fulfil accepted PartnerStack Content Marketplace orders.

Pending or negotiating orders are deliberately never accepted here: accepting is
a binding commercial decision. Once the owner accepts an order, this worker
creates public, disclosed deliverables and can submit their live URL for review.
Raw buyer/order data stays in an ignored private state directory.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_BASE = "https://api.partnerstack.com/api/v2"
ORDERS_PATH = "/content-marketplace/orders"
INVENTORY_PATH = ROOT / "data" / "sponsorship_inventory.json"
PUBLIC_PATH = ROOT / "data" / "sponsored_campaigns.json"
HUB_PATH = ROOT / "sponsored.html"
OUTPUT_DIR = ROOT / "sponsored"
SITEMAP_PATH = ROOT / "sitemap.xml"
SITEMAP_START = "  <!-- sponsored-campaigns:start -->"
SITEMAP_END = "  <!-- sponsored-campaigns:end -->"
GENERATED_MARKER = "<!-- GENERATED: content-marketplace-fulfillment -->"
FULFIL_STATUSES = {"accepted", "in_review", "changes_requested", "completed"}
OWNER_STATUSES = {"pending", "negotiating"}


def load_json(path: Path, default: Any | None = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {} if default is None else default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def first(mapping: dict[str, Any], *paths: str, default: Any = "") -> Any:
    for path in paths:
        value: Any = mapping
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value not in (None, "", [], {}):
            return value
    return default


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:72] or "sponsored-campaign"


def safe_https(value: Any) -> str:
    text = str(value or "").strip()
    parsed = urlparse(text)
    return text if parsed.scheme == "https" and parsed.netloc else ""


def list_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("orders", "items", "results", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = list_payload(value)
            if nested:
                return nested
    return []


def request_json(
    api_key: str, path: str, *, method: str = "GET", data: dict[str, Any] | None = None,
    api_base: str = API_BASE,
) -> dict[str, Any] | list[Any]:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = Request(
        f"{api_base.rstrip('/')}{path}", data=body, method=method,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "artificial.one-content-fulfillment/1.0",
        },
    )
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def fetch_orders(api_key: str, api_base: str = API_BASE) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = urlencode({"limit": 250, "offset": offset})
        page = list_payload(request_json(api_key, f"{ORDERS_PATH}?{query}", api_base=api_base))
        result.extend(page)
        if len(page) < 250:
            return result
        offset += len(page)


def inventory_lookup() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    payload = load_json(INVENTORY_PATH, {"packages": []})
    by_name = {
        str(item.get("name") or "").casefold(): item
        for item in payload.get("packages", []) if isinstance(item, dict)
    }
    return by_name, payload


def normalize_order(order: dict[str, Any]) -> dict[str, Any]:
    key = str(first(order, "key", "id", "order_key", "order.key")).strip()
    status = str(first(order, "status", "state", default="unknown")).casefold().strip()
    offer_name = str(first(
        order, "offer.name", "offer.title", "content_offer.name", "content_offer.title",
        "product.name", "title", default="Sponsored AI Tool Evaluation & Placement",
    )).strip()
    brand = str(first(
        order, "brand.name", "buyer.company_name", "buyer.name", "company.name",
        "partnership.company_name", "customer.name", default="Partner product",
    )).strip()
    brief = str(first(
        order, "brief", "requirements", "description", "notes", "campaign.brief",
        "order_details.brief", default="The sponsor has commissioned a clearly disclosed product introduction.",
    )).strip()
    target_url = safe_https(first(
        order, "destination_url", "product_url", "website", "brand.website",
        "company.website", "campaign.url", "url",
    ))
    updated = str(first(order, "updated_at", "modified_at", "created_at", default=""))
    return {
        "key": key,
        "status": status,
        "offer_name": offer_name,
        "brand": brand,
        "brief": brief,
        "target_url": target_url,
        "updated_at": updated,
    }


def order_url(key: str) -> str:
    return f"https://dash.partnerstack.com/content-marketplace/requests/{key}" if key else "https://dash.partnerstack.com/content-marketplace/requests"


def public_campaign(order: dict[str, Any], package: dict[str, Any], prior: dict[str, Any] | None, today: date) -> dict[str, Any]:
    prior = prior or {}
    slug = str(prior.get("slug") or slugify(f"{order['brand']}-{order['key'][-8:]}"))
    deliverables = list(package.get("deliverables") or ["sponsored_page", "tracked_link"])
    first_published = str(prior.get("first_published") or today.isoformat())
    spotlight_until = ""
    if "category_placement" in deliverables:
        spotlight_until = str(prior.get("spotlight_until") or (today + timedelta(days=30)).isoformat())
    social_dates = list(prior.get("social_publish_dates") or [])
    wanted_social = int("social_post" in deliverables) + int("social_followup" in deliverables)
    if wanted_social and not social_dates:
        social_dates = [today.isoformat()]
        if wanted_social > 1:
            social_dates.append((today + timedelta(days=7)).isoformat())
    return {
        "id": f"partnerstack-{order['key']}",
        "order_key": order["key"],
        "slug": slug,
        "status": order["status"],
        "brand": order["brand"],
        "offer_name": order["offer_name"],
        "package_id": str(package.get("id") or "sponsored-evaluation"),
        "brief": order["brief"][:3000],
        "target_url": order["target_url"],
        "first_published": first_published,
        "spotlight_until": spotlight_until,
        "social_publish_dates": social_dates,
        "deliverables": deliverables,
        "page_url": f"https://artificial.one/sponsored/{slug}.html",
        "disclosure": "Sponsored by the featured company. Payment does not buy a positive verdict or alter organic rankings.",
    }


def shell(title: str, description: str, body: str, canonical: str) -> str:
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><meta name="description" content="{escape(description)}"><link rel="canonical" href="{escape(canonical)}">
<link rel="stylesheet" href="/assets/decision-engine.css"></head><body>{GENERATED_MARKER}
<header class="site-header"><nav class="nav container"><a class="brand" href="/"><img src="/images/branding/artificial-one-elephant-mark.png" width="42" height="42" alt=""><strong>artificial.one</strong></a><div class="nav-links"><a href="/ask-elephant.html">Ask Elephant</a><a href="/partner-offers.html">Deals</a><a href="/news.html">What's New</a></div></nav></header>
<main>{body}</main><footer class="site-footer"><div class="container">Artificial.One · Commercial relationships are always disclosed.</div></footer>
<script src="/assets/affiliate-tracking.js" defer></script></body></html>'''


def render_campaign(campaign: dict[str, Any]) -> str:
    cta = ""
    if campaign.get("target_url"):
        cta = (
            f'<a class="btn btn-acid" href="{escape(campaign["target_url"])}" target="_blank" '
            f'rel="nofollow sponsored noopener" data-affiliate-offer data-offer-id="{escape(campaign["id"])}" '
            'data-placement="sponsored-campaign">Visit the sponsor’s product →</a>'
        )
    body = f'''<section class="section"><div class="container narrow">
<p class="eyebrow">Sponsored partner feature</p><h1>{escape(campaign['brand'])}</h1>
<div class="surface content-card"><strong>Commercial disclosure:</strong> {escape(campaign['disclosure'])}</div>
<article class="surface content-card"><h2>What the sponsor wants you to know</h2>
<p>{escape(campaign['brief'])}</p>{cta}
<p class="disclosure">Sponsor-provided description. Verify product capabilities, pricing and terms on the destination before purchasing.</p></article>
<section class="surface content-card"><h2>How Artificial.One handles sponsored work</h2><p>We label paid placements, track outbound interest and keep sponsored placement separate from our independent comparison rankings.</p></section>
</div></section>'''
    return shell(
        f"{campaign['brand']} sponsored feature | Artificial.One",
        f"A clearly disclosed sponsored introduction to {campaign['brand']}.", body, campaign["page_url"],
    )


def render_hub(campaigns: list[dict[str, Any]]) -> str:
    cards = []
    for campaign in campaigns:
        cards.append(f'''<a class="tool-card" href="/sponsored/{escape(campaign['slug'])}.html"><p class="eyebrow">Sponsored</p><h2>{escape(campaign['brand'])}</h2><p>{escape(campaign['brief'][:240])}</p><span class="link-subtle">Open the disclosed feature →</span></a>''')
    listing = "".join(cards) or "<div class='surface content-card'><p>No sponsored campaigns are currently live.</p></div>"
    body = f'''<section class="section"><div class="container"><p class="eyebrow">Commercially transparent</p><h1>Sponsored partner features</h1><p>Paid campaigns are labelled clearly and never alter independent rankings.</p><div class="card-grid">{listing}</div></div></section>'''
    return shell("Sponsored partner features | Artificial.One", "Clearly disclosed paid partner campaigns on Artificial.One.", body, "https://artificial.one/sponsored.html")


def update_sitemap(campaigns: list[dict[str, Any]], today: date) -> None:
    source = SITEMAP_PATH.read_text(encoding="utf-8")
    source = re.sub(rf"\s*{re.escape(SITEMAP_START)}.*?{re.escape(SITEMAP_END)}", "", source, flags=re.DOTALL)
    rows = [SITEMAP_START, "  <url>", "    <loc>https://artificial.one/sponsored.html</loc>", f"    <lastmod>{today.isoformat()}</lastmod>", "    <changefreq>weekly</changefreq>", "    <priority>0.6</priority>", "  </url>"]
    for campaign in campaigns:
        rows.extend(["  <url>", f"    <loc>{escape(campaign['page_url'])}</loc>", f"    <lastmod>{today.isoformat()}</lastmod>", "    <changefreq>weekly</changefreq>", "    <priority>0.7</priority>", "  </url>"])
    rows.append(SITEMAP_END)
    block = "\n".join(rows)
    SITEMAP_PATH.write_text(source.replace("</urlset>", f"{block}\n</urlset>"), encoding="utf-8")


def build_public(campaigns: list[dict[str, Any]], today: date) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    expected = {f"{item['slug']}.html" for item in campaigns}
    for campaign in campaigns:
        (OUTPUT_DIR / f"{campaign['slug']}.html").write_text(render_campaign(campaign), encoding="utf-8")
    for path in OUTPUT_DIR.glob("*.html"):
        if path.name not in expected and GENERATED_MARKER in path.read_text(encoding="utf-8"):
            path.unlink()
    HUB_PATH.write_text(render_hub(campaigns), encoding="utf-8")
    update_sitemap(campaigns, today)


def public_url_is_live(url: str) -> bool:
    try:
        with urlopen(Request(url, method="HEAD", headers={"User-Agent": "artificial.one-content-fulfillment/1.0"}), timeout=20) as response:
            return 200 <= response.status < 400
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return False


def submit_deliverable(api_key: str, order_key: str, url: str, api_base: str = API_BASE) -> None:
    request_json(
        api_key, f"{ORDERS_PATH}/{order_key}/actions", method="POST", api_base=api_base,
        data={
            "action": "submit",
            "deliverables": [{"type": "url", "url": url}],
            "notes": "The disclosed sponsored deliverable is live. Product claims remain sponsor-provided; editorial rankings remain independent.",
        },
    )


def run(api_key: str, state_path: Path, status_path: Path, *, api_base: str = API_BASE, submit: bool = False, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    raw_orders = fetch_orders(api_key, api_base)
    orders = [normalize_order(item) for item in raw_orders]
    orders = [item for item in orders if item["key"]]
    packages, inventory = inventory_lookup()
    prior_public = load_json(PUBLIC_PATH, {"campaigns": []})
    prior_by_key = {str(item.get("order_key")): item for item in prior_public.get("campaigns", [])}
    campaigns: list[dict[str, Any]] = []
    for order in orders:
        if order["status"] not in FULFIL_STATUSES:
            continue
        package = packages.get(order["offer_name"].casefold()) or next(iter(packages.values()), {})
        campaigns.append(public_campaign(order, package, prior_by_key.get(order["key"]), today))
    campaigns.sort(key=lambda item: (item["first_published"], item["brand"].casefold()), reverse=True)
    public_payload = {
        "version": 1,
        "updated_at": today.isoformat(),
        "campaigns": campaigns,
    }
    write_json(PUBLIC_PATH, public_payload)
    build_public(campaigns, today)

    private_state = load_json(state_path, {"submitted": {}})
    submitted = dict(private_state.get("submitted") or {})
    submitted_now: list[str] = []
    if submit:
        for campaign in campaigns:
            if campaign["status"] != "accepted" or submitted.get(campaign["order_key"]):
                continue
            if not public_url_is_live(campaign["page_url"]):
                continue
            submit_deliverable(api_key, campaign["order_key"], campaign["page_url"], api_base)
            submitted[campaign["order_key"]] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            submitted_now.append(campaign["order_key"])

    owner_actions = [
        {
            "title": f"Review {item['brand']} — {item['offer_name']}",
            "detail": "Accept, counter or decline this request in PartnerStack. Acceptance creates a binding commitment.",
            "url": order_url(item["key"]),
            "status": item["status"],
        }
        for item in orders if item["status"] in OWNER_STATUSES
    ]
    status_payload = {
        "version": 1,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "offers_published": len(inventory.get("packages", [])),
        "orders_total": len(orders),
        "owner_actions": owner_actions,
        "fulfilling": sum(item["status"] in FULFIL_STATUSES - {"completed"} for item in orders),
        "completed": sum(item["status"] == "completed" for item in orders),
        "submitted_now": len(submitted_now),
    }
    write_json(status_path, status_payload)
    write_json(state_path, {"version": 1, "submitted": submitted, "orders": orders})
    return status_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=Path(".content-marketplace/state.json"))
    parser.add_argument("--status", type=Path, default=Path(".content-marketplace/status.json"))
    parser.add_argument("--api-base", default=os.environ.get("PARTNERSTACK_API_BASE", API_BASE))
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    api_key = os.environ.get("PARTNERSTACK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PARTNERSTACK_API_KEY is required")
    result = run(api_key, args.state, args.status, api_base=args.api_base, submit=args.submit)
    print(
        f"Content Marketplace: {result['orders_total']} order(s), "
        f"{result['fulfilling']} in fulfilment, {len(result['owner_actions'])} owner action(s), "
        f"{result['submitted_now']} submitted now."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
