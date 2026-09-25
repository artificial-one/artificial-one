#!/usr/bin/env python3
"""Build and maintain the public-safe AppSumo/Impact offer layer.

The workbook is the private account export supplied by the site owner. The
generated JSON contains only public product names, destinations and affiliate
links that already appear on the website. Availability is confirmed from the
public AppSumo destination; two consecutive inactive checks are required before
an offer is treated as expired.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import html
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "appsumo-affiliate-links-tracker.xlsx"
REGISTRY = ROOT / "data" / "appsumo_offers.json"
IMPACT_INVENTORY = ROOT / "data" / "appsumo_impact_ads.json"
HUB = ROOT / "appsumo-ai-tools.html"
HOMEPAGE = ROOT / "index.html"
SITEMAP = ROOT / "sitemap.xml"
STATE = ROOT / ".appsumo-monitor" / "availability.json"
TRACKING_RE = re.compile(r"https://appsumo\.8odi\.net/[A-Za-z0-9]+", re.I)
AI_TERMS = {
    "ai", "audio", "automation", "bot", "chat", "code", "content", "copy",
    "design", "email", "image", "llm", "marketing", "meeting", "photo",
    "podcast", "rank", "seo", "social", "speech", "transcript", "video",
    "voice", "write", "writer", "writing",
}
PRIORITY_TERMS = (
    "ai", "seo", "write", "video", "voice", "meeting", "image", "content",
    "automation", "email", "chat",
)
INACTIVE_MARKERS = (
    "this deal is no longer available",
    "this product is no longer available",
    "deal has ended",
    "page not found",
)
SITEMAP_START = "  <!-- appsumo-impact:start -->"
SITEMAP_END = "  <!-- appsumo-impact:end -->"
HOMEPAGE_START = "      {/* APPSUMO_DEAL_PULSE_START */}"
HOMEPAGE_END = "      {/* APPSUMO_DEAL_PULSE_END */}"


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.casefold())).strip("-")


def _column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref.upper())
    value = 0
    for char in letters.group(0) if letters else "A":
        value = value * 26 + ord(char) - 64
    return value - 1


def workbook_rows(path: Path = WORKBOOK) -> list[dict[str, str]]:
    """Read the first XLSX worksheet without adding a spreadsheet dependency."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.parse(archive.open("xl/sharedStrings.xml")).getroot()
            for item in root.findall(".//m:si", ns):
                shared.append("".join(node.text or "" for node in item.findall(".//m:t", ns)))
        sheet_name = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet"))[0]
        sheet = ET.parse(archive.open(sheet_name)).getroot()
        matrix: list[list[str]] = []
        for row in sheet.findall(".//m:row", ns):
            values: dict[int, str] = {}
            for cell in row.findall("m:c", ns):
                index = _column_index(cell.get("r", "A1"))
                value_node = cell.find("m:v", ns)
                value = value_node.text if value_node is not None and value_node.text else ""
                if cell.get("t") == "s" and value:
                    value = shared[int(value)]
                elif cell.get("t") == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//m:t", ns))
                values[index] = value.strip()
            if values:
                matrix.append([values.get(index, "") for index in range(max(values) + 1)])
    if not matrix:
        return []
    headers = [value.strip() or f"Column {index + 1}" for index, value in enumerate(matrix[0])]
    return [
        {header: (row[index].strip() if index < len(row) else "") for index, header in enumerate(headers)}
        for row in matrix[1:]
    ]


def _field(headers: list[str], *needles: str) -> str:
    for header in headers:
        folded = header.casefold()
        if all(needle in folded for needle in needles):
            return header
    return ""


def infer_category(name: str) -> str:
    text = name.casefold()
    groups = (
        (("video", "render", "clip"), "AI video"),
        (("voice", "audio", "podcast", "speech"), "AI audio"),
        (("image", "photo", "design", "graphic", "pixel"), "AI design"),
        (("seo", "rank", "review"), "SEO and growth"),
        (("write", "content", "copy", "blog"), "AI writing"),
        (("email", "social", "marketing", "lead"), "Marketing automation"),
        (("code", "developer", "api", "nocode"), "Development"),
        (("meeting", "calendar", "schedule", "team"), "Productivity"),
    )
    return next((category for terms, category in groups if any(term in text for term in terms)), "Business software")


def _existing_editorial(slug: str, tracking_url: str, link_pages: dict[str, str] | None = None) -> str:
    candidates = [
        ROOT / f"blog-{slug}.html",
        ROOT / "tools" / f"{slug}.html",
        ROOT / "appsumo-guides" / f"{slug}.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.relative_to(ROOT).as_posix()
    return (link_pages or {}).get(tracking_url, "")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_registry(previous: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = workbook_rows()
    if not rows:
        raise RuntimeError("The AppSumo tracking-link workbook contains no rows")
    headers = list(rows[0])
    name_key = _field(headers, "product", "name") or headers[0]
    slug_key = _field(headers, "product", "slug")
    link_key = _field(headers, "tracking", "link")
    if not link_key:
        raise RuntimeError("Could not find the generated tracking-link column")
    old = {str(item.get("id")): item for item in (previous or {}).get("offers", [])}
    old_by_tracking = {str(item.get("tracking_url")): item for item in (previous or {}).get("offers", [])}
    slug_counts: dict[str, int] = {}
    link_pages: dict[str, str] = {}
    for path in ROOT.rglob("*.html"):
        if path == HUB or any(part.startswith(".") for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in TRACKING_RE.findall(text):
            link_pages.setdefault(match, path.relative_to(ROOT).as_posix())
    offers: list[dict[str, Any]] = []
    for row in rows:
        name = row.get(name_key, "").strip()
        tracking_match = TRACKING_RE.search(row.get(link_key, ""))
        if not name or not tracking_match:
            continue
        tracking_url = tracking_match.group(0)
        raw_slug = row.get(slug_key, "").strip().rstrip("/").split("/")[-1] if slug_key else ""
        slug = slugify(raw_slug or name)
        slug_counts[slug] = slug_counts.get(slug, 0) + 1
        occurrence = slug_counts[slug]
        offer_id = f"appsumo-{slug}" + (f"-{occurrence}" if occurrence > 1 else "")
        prior = old.get(offer_id) or old_by_tracking.get(tracking_url, {})
        words = set(slugify(name + " " + slug).split("-"))
        ai_relevant = bool(words & AI_TERMS)
        editorial = _existing_editorial(slug, tracking_url, link_pages)
        source_status = str(row.get(_field(headers, "status"), "")).strip().casefold()
        imported_availability = "active" if source_status in {"active", "new"} else "expired" if source_status in {"unavailable", "delete"} else "unchecked"
        product_url_key = _field(headers, "appsumo", "product", "url")
        prior_availability = str(prior.get("availability") or "")
        availability = prior_availability if prior.get("last_checked_at") or prior_availability not in {"", "unchecked"} else imported_availability
        offers.append({
            "id": offer_id,
            "name": name,
            "slug": slug,
            "category": infer_category(name),
            "tracking_url": tracking_url,
            "product_url": row.get(product_url_key, "").strip() if product_url_key else f"https://appsumo.com/products/{slug}/",
            "editorial_url": editorial,
            "ai_relevant": ai_relevant,
            "availability": availability,
            "last_checked_at": prior.get("last_checked_at", ""),
            "source_status": source_status or "unknown",
        })
    imported = load_json(IMPACT_INVENTORY)
    known_slugs = {str(item.get("slug") or "").casefold() for item in offers}
    known_names = {re.sub(r"[^a-z0-9]", "", str(item.get("name") or "").casefold()) for item in offers}
    known_links = {str(item.get("tracking_url") or "") for item in offers}
    for item in imported.get("offers", []):
        if not isinstance(item, dict):
            continue
        tracking = str(item.get("tracking_url") or "")
        slug = slugify(str(item.get("slug") or item.get("name") or ""))
        name_key = re.sub(r"[^a-z0-9]", "", str(item.get("name") or "").casefold())
        if not tracking.startswith("https://") or not slug or tracking in known_links or slug.casefold() in known_slugs or name_key in known_names:
            continue
        prior = old.get(str(item.get("id") or "")) or old_by_tracking.get(tracking, {})
        offers.append({
            "id": str(item.get("id") or f"appsumo-impact-{slug}"),
            "name": str(item.get("name") or slug.replace("-", " ").title()),
            "slug": slug,
            "category": str(item.get("category") or infer_category(str(item.get("name") or slug))),
            "tracking_url": tracking,
            "product_url": str(item.get("product_url") or f"https://appsumo.com/products/{slug}/"),
            "editorial_url": str(item.get("editorial_url") or ""),
            "ai_relevant": bool(item.get("ai_relevant")),
            "availability": str(prior.get("availability") or item.get("availability") or "unchecked"),
            "last_checked_at": str(prior.get("last_checked_at") or ""),
            "source_status": "impact-api",
            "impact_ad_id": str(item.get("impact_ad_id") or ""),
        })
        known_links.add(tracking)
        known_slugs.add(slug.casefold())
        known_names.add(name_key)
    return {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "network": "Impact / AppSumo",
        "campaign_id": "7443",
        "offers": sorted(offers, key=lambda item: item["name"].casefold()),
        "policy": {
            "paid_brand_campaigns": "prohibited",
            "publication_rule": "Only AI-relevant offers with an editorial page and a non-expired public destination are promoted.",
            "expiry_rule": "Two consecutive inactive destination checks disable the affiliate CTA.",
        },
    }


def check_destination(offer: dict[str, Any]) -> tuple[str, str]:
    request = Request(
        str(offer["tracking_url"]),
        headers={"User-Agent": "Mozilla/5.0 (compatible; artificial.one-offer-monitor/1.0)"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            final_url = response.geturl()
            body = response.read(750_000).decode("utf-8", errors="ignore").casefold()
            parsed = urlparse(final_url)
            if response.status >= 400:
                return "inactive", final_url
            if any(marker in body for marker in INACTIVE_MARKERS):
                return "inactive", final_url
            if parsed.netloc.casefold().endswith("appsumo.com") and parsed.path.startswith("/products/"):
                return "active", final_url
            return "inactive", final_url
    except HTTPError as exc:
        return ("inactive" if exc.code in {404, 410} else "error"), str(exc.code)
    except (URLError, TimeoutError, OSError) as exc:
        return "error", type(exc).__name__


def refresh_availability(registry: dict[str, Any], state_path: Path = STATE, workers: int = 12) -> dict[str, Any]:
    state = load_json(state_path)
    previous = state.get("offers", {}) if isinstance(state.get("offers"), dict) else {}
    checked_at = datetime.now(timezone.utc).isoformat()
    results: dict[str, tuple[str, str]] = {}
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(check_destination, offer): offer for offer in registry["offers"]}
        for future in as_completed(futures):
            offer = futures[future]
            results[str(offer["id"])] = future.result()
    next_state: dict[str, Any] = {}
    for offer in registry["offers"]:
        offer_id = str(offer["id"])
        result, final_url = results[offer_id]
        prior = previous.get(offer_id, {}) if isinstance(previous.get(offer_id), dict) else {}
        strikes = int(prior.get("inactive_strikes") or 0)
        if result == "active":
            strikes = 0
            public_status = "active"
        elif result == "inactive":
            strikes = max(strikes, 2) if offer.get("availability") == "expired" else strikes + 1
            public_status = "expired" if strikes >= 2 else "checking"
        else:
            public_status = str(offer.get("availability") or "unchecked")
        offer["availability"] = public_status
        offer["last_checked_at"] = checked_at
        next_state[offer_id] = {
            "inactive_strikes": strikes,
            "last_result": result,
            "last_destination": final_url,
            "checked_at": checked_at,
        }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"version": 1, "offers": next_state}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return registry


def _score(offer: dict[str, Any]) -> tuple[int, str]:
    name = str(offer["name"]).casefold()
    score = sum((len(PRIORITY_TERMS) - index) for index, term in enumerate(PRIORITY_TERMS) if term in name)
    return (-score, name)


def promoted_offers(registry: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    eligible = [
        offer for offer in registry.get("offers", [])
        if offer.get("ai_relevant") and offer.get("editorial_url") and offer.get("availability") != "expired"
    ]
    active = [offer for offer in eligible if offer.get("availability") == "active"]
    pool = active or eligible
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offer in sorted(pool, key=_score):
        key = str(offer.get("slug") or offer.get("name")).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(offer)
    return unique if limit is None else unique[:max(0, limit)]


def deal_picks(registry: dict[str, Any], on_date: date | None = None, limit: int = 3) -> list[dict[str, Any]]:
    """Rotate checked editorial offers so the pulse stays useful without fake urgency."""
    offers = promoted_offers(registry)
    if not offers:
        return []
    day = (on_date or date.today()).toordinal()
    new = [item for item in offers if item.get("source_status") == "new"]
    remaining = [item for item in offers if item not in new]
    start = day % len(remaining) if remaining else 0
    rotated = remaining[start:] + remaining[:start]
    return (new + rotated)[:limit]


def render_homepage_pulse(registry: dict[str, Any], on_date: date | None = None) -> str:
    picks = deal_picks(registry, on_date)
    cards = []
    for offer in picks:
        badge = "Newly listed" if offer.get("source_status") == "new" else "Destination checked"
        cards.append(f'''<article className="rounded-2xl border border-indigo-200 bg-white p-6 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-widest text-indigo-600">{html.escape(badge)}</p>
              <h3 className="mt-2 text-2xl font-black">{html.escape(str(offer['name']))}</h3>
              <p className="mt-3 text-sm leading-6 text-gray-600">Independent fit guide plus a monitored AppSumo destination. Verify today's price, limits and refund terms before buying.</p>
              <div className="mt-5 flex flex-wrap gap-3"><a className="font-bold text-indigo-700 hover:underline" href="{html.escape(str(offer['editorial_url']))}" data-content-route="" data-related-offer-id="{html.escape(str(offer['id']))}" data-placement="homepage-deal-pulse-guide">Read the guide →</a><a className="rounded-lg bg-indigo-600 px-4 py-2 font-bold text-white" href="{html.escape(str(offer['tracking_url']))}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer="" data-affiliate-network="impact" data-offer-id="{html.escape(str(offer['id']))}" data-placement="homepage-deal-pulse">Check current offer</a></div>
            </article>''')
    return f'''{HOMEPAGE_START}
      <section className="bg-indigo-50 py-16" aria-labelledby="live-deal-pulse-title">
        <div className="container mx-auto px-4"><div className="flex flex-col justify-between gap-4 md:flex-row md:items-end"><div><p className="text-sm font-bold uppercase tracking-widest text-indigo-600">Automatically checked daily</p><h2 id="live-deal-pulse-title" className="mt-2 text-3xl font-black md:text-4xl">Live AI deal pulse</h2><p className="mt-3 max-w-2xl text-gray-600">A rotating shortlist of active AppSumo tools with independent fit guides. Availability is monitored; AppSumo remains the source of truth for price and terms.</p></div><a className="font-bold text-indigo-700 hover:underline" href="appsumo-ai-tools.html?utm_source=homepage&amp;utm_medium=deal-pulse&amp;utm_campaign=live-deals" data-content-route="" data-placement="homepage-deal-pulse-all">Browse all checked deals →</a></div><div className="mt-8 grid gap-5 md:grid-cols-3">{''.join(cards)}</div><p className="mt-5 text-xs text-gray-500">Affiliate disclosure: artificial.one may earn a commission from marked links, at no extra cost to you.</p></div>
      </section>
{HOMEPAGE_END}'''


def update_homepage(source: str, registry: dict[str, Any], on_date: date | None = None) -> str:
    block = render_homepage_pulse(registry, on_date)
    if HOMEPAGE_START in source and HOMEPAGE_END in source:
        return re.sub(re.escape(HOMEPAGE_START) + r".*?" + re.escape(HOMEPAGE_END), block, source, flags=re.S)
    marker = "      {/* Featured Tools */}"
    if marker not in source:
        # The decision-engine homepage intentionally omits the legacy deal grid.
        # AppSumo still refreshes its hub, guides and availability data without
        # re-introducing a competing homepage section.
        return source
    return source.replace(marker, block + "\n\n" + marker, 1)


def render_hub(registry: dict[str, Any]) -> str:
    offers = promoted_offers(registry)
    pulse_offers = deal_picks(registry)
    cards = []
    for offer in offers:
        status = "Public destination checked" if offer.get("availability") == "active" and offer.get("last_checked_at") else "Approved link; daily monitoring active"
        search = html.escape(f"{offer['name']} {offer['category']}".casefold(), quote=True)
        category = html.escape(str(offer["category"]), quote=True)
        cards.append(f'''<article class="card" data-deal-card data-category="{category}" data-search="{search}"><p class="category">{html.escape(str(offer['category']))}</p><h2>{html.escape(str(offer['name']))}</h2><p>Independent fit guide for {html.escape(str(offer['name']))}. Verify the current price, limits and refund terms at AppSumo before buying.</p><p class="status">{status}</p><div class="actions"><a href="{html.escape(str(offer['editorial_url']))}">Read the guide</a><a class="cta" href="{html.escape(str(offer['tracking_url']))}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-affiliate-network="impact" data-offer-id="{html.escape(str(offer['id']))}" data-placement="appsumo-hub">Check current offer →</a></div></article>''')
    listing = "".join(cards) or '<p class="empty">No AppSumo AI offer currently passes the publication checks. The monitor will restore eligible offers automatically.</p>'
    count = len(offers)
    checked = max((str(offer.get("last_checked_at") or "")[:10] for offer in offers), default=str(registry.get("updated_at") or date.today().isoformat()))
    categories = sorted({str(offer["category"]) for offer in offers})
    options = "".join(f'<option value="{html.escape(value, quote=True)}">{html.escape(value)}</option>' for value in categories)
    pulse = "".join(f'''<article class="pulse-card"><p class="category">Today's checked pick</p><h2>{html.escape(str(offer['name']))}</h2><p>{html.escape(str(offer['category']))}. Read the independent fit guide, then verify the current offer at AppSumo.</p><div class="actions"><a href="{html.escape(str(offer['editorial_url']))}">Read fit guide</a><a class="cta" href="{html.escape(str(offer['tracking_url']))}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-affiliate-network="impact" data-offer-id="{html.escape(str(offer['id']))}" data-placement="appsumo-deal-pulse">Check offer →</a></div></article>''' for offer in pulse_offers)
    structured = json.dumps({"@context": "https://schema.org", "@type": "ItemList", "name": "AppSumo AI tools available today", "itemListElement": [{"@type": "ListItem", "position": index, "name": offer["name"], "url": f"https://artificial.one/{offer['editorial_url']}"} for index, offer in enumerate(offers, 1)]}).replace("<", "\\u003c")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AppSumo AI Deals Available Today | artificial.one</title><meta name="description" content="Browse independently selected AppSumo AI tools whose public destinations are checked daily, with fit guides and current-offer links."><link rel="canonical" href="https://artificial.one/appsumo-ai-tools.html"><meta name="affiliate-event-endpoint" content="/api/affiliate-event"><script type="application/ld+json">{structured}</script><style>body{{margin:0;background:#f8fafc;color:#0f172a;font-family:Inter,system-ui,sans-serif}}header,main,footer{{max-width:1120px;margin:auto;padding:24px}}nav{{display:flex;justify-content:space-between;align-items:center}}nav a{{color:#4338ca;font-weight:700;text-decoration:none}}.hero{{padding:72px 24px 36px}}h1{{font-size:clamp(2.5rem,7vw,5rem);line-height:1;margin:.3em 0}}.lead{{max-width:760px;color:#475569;font-size:1.15rem;line-height:1.7}}.pulse{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:0 0 28px}}.pulse-card{{background:#111827;color:white;border-radius:18px;padding:22px;box-shadow:0 12px 30px #312e8126}}.pulse-card p{{color:#cbd5e1;line-height:1.55}}.pulse-card .category{{color:#c4b5fd!important}}.notice{{border:1px solid #c7d2fe;background:#eef2ff;padding:18px;border-radius:14px;line-height:1.6}}.filters{{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-top:22px}}.filters input,.filters select{{width:100%;padding:14px;border:1px solid #cbd5e1;border-radius:10px;background:#fff;font:inherit}}.result-count{{color:#475569;font-weight:700}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;padding:18px 0 70px}}.card{{display:flex;flex-direction:column;background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:24px;box-shadow:0 5px 18px #0f172a0d}}.card[hidden]{{display:none}}.card h2{{font-size:1.45rem;margin:.3em 0}}.card>p{{color:#64748b;line-height:1.55}}.category{{font-size:.76rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#4f46e5!important}}.status{{font-size:.8rem;margin-top:auto;padding-top:12px}}.actions{{display:flex;gap:8px;margin-top:14px}}.actions a{{flex:1;text-align:center;border:1px solid #c7d2fe;border-radius:9px;padding:11px;color:#4338ca;font-weight:750;text-decoration:none}}.pulse-card .actions a{{color:#ddd6fe}}.actions .cta,.pulse-card .actions .cta{{background:#4338ca;color:#fff}}footer{{border-top:1px solid #e2e8f0;color:#64748b;font-size:.9rem;line-height:1.6}}@media(max-width:880px){{.pulse,.grid{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:600px){{.filters,.pulse,.grid{{grid-template-columns:1fr}}.actions{{flex-direction:column}}}}</style></head><body><header><nav><a href="index.html">artificial.one</a><span><a href="ai-tool-finder.html">Tool finder</a> · <a href="buyers-guides.html">Buyer guides</a></span></nav></header><main><section class="hero"><p class="category">Checked {html.escape(checked)}</p><h1>AppSumo AI deals available today</h1><p class="lead">A use-case-led selection of {count} AI and automation tools with an artificial.one editorial guide and a currently reachable public AppSumo destination. We do not list every promotion, publish coupon codes, or accept payment for rankings.</p></section><section aria-labelledby="deal-pulse-title"><h2 id="deal-pulse-title">Today's checked deal pulse</h2><p class="lead">Three monitored picks rotate daily so useful offers get discovery without pretending a deadline exists.</p><div class="pulse">{pulse}</div></section><section class="notice"><strong>Affiliate disclosure:</strong> artificial.one may earn a commission if you buy through a marked link, at no extra cost to you. Availability is checked daily, but AppSumo’s destination is the source of truth for today’s price and terms.<div class="filters"><label>Search deals<input id="deal-search" type="search" placeholder="Search by tool or use case"></label><label>Category<select id="deal-category"><option value="">All categories</option>{options}</select></label></div><p id="deal-count" class="result-count">Showing {count} checked tools</p></section><section class="grid">{listing}</section></main><footer><p>Selections are editorial and intended for entrepreneurs and businesses evaluating software. No incentivized clicks. AppSumo and product names belong to their owners.</p></footer><script>(function(){{var search=document.getElementById('deal-search'),category=document.getElementById('deal-category'),cards=[].slice.call(document.querySelectorAll('[data-deal-card]')),count=document.getElementById('deal-count');function update(){{var query=search.value.trim().toLowerCase(),selected=category.value,shown=0;cards.forEach(function(card){{var visible=(!query||card.dataset.search.indexOf(query)>-1)&&(!selected||card.dataset.category===selected);card.hidden=!visible;if(visible)shown++;}});count.textContent='Showing '+shown+' checked tool'+(shown===1?'':'s');}}search.addEventListener('input',update);category.addEventListener('change',update);}})();</script><script src="assets/affiliate-tracking.js" defer></script></body></html>'''


def instrument_html(registry: dict[str, Any]) -> int:
    by_url = {str(offer["tracking_url"]): offer for offer in registry["offers"]}
    changed = 0
    for path in ROOT.rglob("*.html"):
        if any(part.startswith(".") for part in path.relative_to(ROOT).parts) or path == HUB:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "appsumo.8odi.net" not in source:
            continue
        expected = source
        for url, offer in by_url.items():
            if url not in expected:
                continue
            pattern = re.compile(rf"<a\b(?P<attrs>[^>]*href=[\"']{re.escape(url)}(?:\?[^\"']*)?[\"'][^>]*)>", re.I)
            def enrich(match: re.Match[str]) -> str:
                attrs = match.group("attrs")
                additions = []
                if "data-affiliate-offer" not in attrs:
                    additions.append("data-affiliate-offer")
                if "data-affiliate-network" not in attrs:
                    additions.append('data-affiliate-network="impact"')
                if "data-offer-id" not in attrs:
                    additions.append(f'data-offer-id="{offer["id"]}"')
                if "data-placement" not in attrs:
                    additions.append('data-placement="appsumo-editorial"')
                suffix = (" " + " ".join(additions)) if additions else ""
                return f"<a{attrs}{suffix}>"
            expected = pattern.sub(enrich, expected)
        if "data-affiliate-network=\"impact\"" in expected and "affiliate-tracking.js" not in expected:
            depth = len(path.relative_to(ROOT).parts) - 1
            prefix = "../" * depth
            script = f'<script src="{prefix}assets/affiliate-tracking.js" defer></script>'
            expected = re.sub(r"</body\s*>", script + "</body>", expected, count=1, flags=re.I)
        if "data-affiliate-network=\"impact\"" in expected and 'name="affiliate-event-endpoint"' not in expected:
            expected = re.sub(r"</head\s*>", '<meta name="affiliate-event-endpoint" content="/api/affiliate-event"></head>', expected, count=1, flags=re.I)
        if expected != source:
            path.write_text(expected, encoding="utf-8")
            changed += 1
    return changed


def update_sitemap(source: str, registry: dict[str, Any] | None = None) -> str:
    guide_urls = sorted({str(item.get("editorial_url")) for item in (registry or {}).get("offers", []) if str(item.get("editorial_url") or "").startswith("appsumo-guides/")})
    rows = [f"  <url><loc>https://artificial.one/appsumo-ai-tools.html</loc><lastmod>{date.today().isoformat()}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>"]
    rows.extend(f"  <url><loc>https://artificial.one/{html.escape(url)}</loc><lastmod>{date.today().isoformat()}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>" for url in guide_urls)
    block = f"{SITEMAP_START}\n" + "\n".join(rows) + f"\n{SITEMAP_END}"
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), block, source, flags=re.S)
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + block + "\n</urlset>\n"


def expected_outputs(live_check: bool = False, state_path: Path = STATE) -> tuple[dict[str, Any], str, str, str]:
    registry = build_registry(load_json(REGISTRY))
    if live_check:
        refresh_availability(registry, state_path)
    hub = render_hub(registry)
    sitemap = update_sitemap(SITEMAP.read_text(encoding="utf-8"), registry)
    homepage = update_homepage(HOMEPAGE.read_text(encoding="utf-8"), registry)
    return registry, hub, sitemap, homepage


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-check", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--state", type=Path, default=STATE)
    args = parser.parse_args(argv)
    registry, hub, sitemap, homepage = expected_outputs(args.live_check, args.state)
    serialized = json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    stale = (not REGISTRY.exists() or REGISTRY.read_text(encoding="utf-8") != serialized or not HUB.exists() or HUB.read_text(encoding="utf-8") != hub or SITEMAP.read_text(encoding="utf-8") != sitemap or HOMEPAGE.read_text(encoding="utf-8") != homepage)
    if args.check:
        if stale:
            print("AppSumo/Impact public assets are stale", file=sys.stderr)
            return 1
        print(f"AppSumo/Impact assets are current ({len(registry['offers'])} tracked links).")
        return 0
    REGISTRY.write_text(serialized, encoding="utf-8")
    HUB.write_text(hub, encoding="utf-8")
    SITEMAP.write_text(sitemap, encoding="utf-8")
    HOMEPAGE.write_text(homepage, encoding="utf-8")
    changed_pages = instrument_html(registry)
    counts = {status: sum(offer["availability"] == status for offer in registry["offers"]) for status in ("active", "checking", "expired", "unchecked")}
    print(f"Managed {len(registry['offers'])} Impact links; instrumented {changed_pages} pages; availability {counts}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
