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
HUB = ROOT / "appsumo-ai-tools.html"
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
    candidates = [ROOT / f"blog-{slug}.html", ROOT / "tools" / f"{slug}.html"]
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


def promoted_offers(registry: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
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
    return unique[:limit]


def render_hub(registry: dict[str, Any]) -> str:
    offers = promoted_offers(registry)
    cards = []
    for offer in offers:
        status = "Public destination checked" if offer.get("availability") == "active" and offer.get("last_checked_at") else "Approved link; daily monitoring active"
        cards.append(f'''<article class="card"><p class="category">{html.escape(str(offer['category']))}</p><h2>{html.escape(str(offer['name']))}</h2><p>Independent fit guide for {html.escape(str(offer['name']))}. Verify the current price, limits and refund terms at AppSumo before buying.</p><p class="status">{status}</p><div class="actions"><a href="{html.escape(str(offer['editorial_url']))}">Read the guide</a><a class="cta" href="{html.escape(str(offer['tracking_url']))}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-affiliate-network="impact" data-offer-id="{html.escape(str(offer['id']))}" data-placement="appsumo-hub">Check current offer →</a></div></article>''')
    listing = "".join(cards) or '<p class="empty">No AppSumo AI offer currently passes the publication checks. The monitor will restore eligible offers automatically.</p>'
    count = len(offers)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AppSumo AI Tools: Independent Fit Guides | artificial.one</title><meta name="description" content="Independent editorial guides to selected AI software currently available through AppSumo, with daily availability checks."><link rel="canonical" href="https://artificial.one/appsumo-ai-tools.html"><meta name="affiliate-event-endpoint" content="/api/affiliate-event"><style>body{{margin:0;background:#f8fafc;color:#0f172a;font-family:Inter,system-ui,sans-serif}}header,main,footer{{max-width:1120px;margin:auto;padding:24px}}nav{{display:flex;justify-content:space-between;align-items:center}}nav a{{color:#4338ca;font-weight:700;text-decoration:none}}.hero{{padding:72px 24px 44px}}h1{{font-size:clamp(2.5rem,7vw,5rem);line-height:1;margin:.3em 0}}.lead{{max-width:760px;color:#475569;font-size:1.15rem;line-height:1.7}}.notice{{border:1px solid #c7d2fe;background:#eef2ff;padding:18px;border-radius:14px;line-height:1.6}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;padding:28px 0 70px}}.card{{display:flex;flex-direction:column;background:#fff;border:1px solid #e2e8f0;border-radius:18px;padding:24px;box-shadow:0 5px 18px #0f172a0d}}.card h2{{font-size:1.45rem;margin:.3em 0}}.card>p{{color:#64748b;line-height:1.55}}.category{{font-size:.76rem;font-weight:800;text-transform:uppercase;letter-spacing:.08em;color:#4f46e5!important}}.status{{font-size:.8rem;margin-top:auto;padding-top:12px}}.actions{{display:flex;gap:8px;margin-top:14px}}.actions a{{flex:1;text-align:center;border:1px solid #c7d2fe;border-radius:9px;padding:11px;color:#4338ca;font-weight:750;text-decoration:none}}.actions .cta{{background:#4338ca;color:#fff}}footer{{border-top:1px solid #e2e8f0;color:#64748b;font-size:.9rem;line-height:1.6}}@media(max-width:880px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}@media(max-width:600px){{.grid{{grid-template-columns:1fr}}.actions{{flex-direction:column}}}}</style></head><body><header><nav><a href="index.html">artificial.one</a><span><a href="ai-tool-finder.html">Tool finder</a> · <a href="buyers-guides.html">Buyer guides</a></span></nav></header><main><section class="hero"><p class="category">Independent buying research</p><h1>AI software on AppSumo</h1><p class="lead">A limited, use-case-led selection of {count} AI and automation tools with an existing artificial.one editorial guide. We do not list every promotion, publish coupon codes, or accept payment for rankings.</p></section><section class="notice"><strong>Affiliate disclosure:</strong> artificial.one may earn a commission if you buy through a marked link, at no extra cost to you. Availability is checked daily, but AppSumo’s destination is the source of truth for today’s price and terms.</section><section class="grid">{listing}</section></main><footer><p>Selections are editorial and intended for entrepreneurs and businesses evaluating software. No incentivized clicks. AppSumo and product names belong to their owners.</p></footer><script src="assets/affiliate-tracking.js" defer></script></body></html>'''


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


def update_sitemap(source: str) -> str:
    block = f"{SITEMAP_START}\n  <url><loc>https://artificial.one/appsumo-ai-tools.html</loc><lastmod>{date.today().isoformat()}</lastmod><changefreq>daily</changefreq><priority>0.8</priority></url>\n{SITEMAP_END}"
    if SITEMAP_START in source and SITEMAP_END in source:
        return re.sub(re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), block, source, flags=re.S)
    return source.rsplit("</urlset>", 1)[0].rstrip() + "\n" + block + "\n</urlset>\n"


def expected_outputs(live_check: bool = False, state_path: Path = STATE) -> tuple[dict[str, Any], str, str]:
    registry = build_registry(load_json(REGISTRY))
    if live_check:
        refresh_availability(registry, state_path)
    hub = render_hub(registry)
    sitemap = update_sitemap(SITEMAP.read_text(encoding="utf-8"))
    return registry, hub, sitemap


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-check", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--state", type=Path, default=STATE)
    args = parser.parse_args(argv)
    registry, hub, sitemap = expected_outputs(args.live_check, args.state)
    serialized = json.dumps(registry, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    stale = (not REGISTRY.exists() or REGISTRY.read_text(encoding="utf-8") != serialized or not HUB.exists() or HUB.read_text(encoding="utf-8") != hub or SITEMAP.read_text(encoding="utf-8") != sitemap)
    if args.check:
        if stale:
            print("AppSumo/Impact public assets are stale", file=sys.stderr)
            return 1
        print(f"AppSumo/Impact assets are current ({len(registry['offers'])} tracked links).")
        return 0
    REGISTRY.write_text(serialized, encoding="utf-8")
    HUB.write_text(hub, encoding="utf-8")
    SITEMAP.write_text(sitemap, encoding="utf-8")
    changed_pages = instrument_html(registry)
    counts = {status: sum(offer["availability"] == status for offer in registry["offers"]) for status in ("active", "checking", "expired", "unchecked")}
    print(f"Managed {len(registry['offers'])} Impact links; instrumented {changed_pages} pages; availability {counts}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
