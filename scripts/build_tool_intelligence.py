#!/usr/bin/env python3
"""Build the public AI software intelligence database and decision products.

The builder consolidates the legacy catalogue, reviewed partner records and
checked AppSumo inventory without turning every filter combination into a thin
indexable page. Public claims retain their confidence and source provenance.
"""

from __future__ import annotations

import argparse
import csv
from datetime import date
from html import escape, unescape
import io
import json
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlparse

try:
    from scripts.build_partner_offers import esc, shell
except ModuleNotFoundError:
    from build_partner_offers import esc, shell  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
PARTNER_PATH = ROOT / "data" / "partner_offers.json"
APPSUMO_PATH = ROOT / "data" / "appsumo_offers.json"
HISTORY_PATH = ROOT / "data" / "tool_change_history.json"
CATALOG_PATH = ROOT / "data" / "tool_intelligence.json"
CSV_PATH = ROOT / "data" / "ai-tool-intelligence.csv"
EXPLORER_PATH = ROOT / "ai-tool-database.html"
ALTERNATIVES_PATH = ROOT / "ai-tool-alternatives.html"
CHANGES_PATH = ROOT / "ai-tool-changes.html"
HOME_PATH = ROOT / "index.html"
SITEMAP_PATH = ROOT / "sitemap.xml"
HOME_START = "      {/* TOOL_INTELLIGENCE_START */}"
HOME_END = "      {/* TOOL_INTELLIGENCE_END */}"
SITEMAP_START = "  <!-- tool-intelligence:start -->"
SITEMAP_END = "  <!-- tool-intelligence:end -->"

CATEGORIES = (
    "Writing & Content", "Design & Images", "Video & Animation",
    "Coding & Development", "Productivity & Business", "Voice & Audio",
    "Research & Data", "Marketing & Social", "Data & Analytics",
)
GENERIC_NAME_WORDS = {
    "app", "apps", "artificial", "assistant", "cloud", "online", "platform",
    "software", "studio", "tool", "tools", "with", "your",
}
SOURCE_HOST_BLOCKLIST = {
    "artificial.one", "www.artificial.one", "appsumo.8odi.net", "youtube.com",
    "www.youtube.com", "facebook.com", "www.facebook.com", "instagram.com",
    "www.instagram.com", "twitter.com", "x.com", "linkedin.com", "www.linkedin.com",
}
AFFILIATE_HOST_MARKERS = (
    "partnerlinks", "partnerstack", "partners.", "affiliate.", "get.descript.com",
    "try.elevenlabs.io", "try.kartra.com", "try.mrpeasy.com", "start.trainual.com",
)


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(default)
    return value if isinstance(value, dict) else dict(default)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def clean_text(value: str) -> str:
    value = re.sub(r"<(script|style|svg)\b.*?</\1>", " ", value, flags=re.I | re.S)
    value = value.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def first_match(patterns: tuple[str, ...], source: str, flags: int = re.I | re.S) -> str:
    for pattern in patterns:
        match = re.search(pattern, source, flags)
        if match:
            return clean_text(match.group(1))
    return ""


def meta_content(source: str, key: str) -> str:
    patterns = (
        rf'<meta[^>]+(?:name|property)=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']*)',
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:name|property)=["\']{re.escape(key)}["\']',
    )
    return first_match(patterns, source)


def extract_list_after_heading(source: str, heading: str, limit: int = 8) -> list[str]:
    match = re.search(
        rf"<h[2-4][^>]*>[^<]*{heading}.*?</h[2-4]>\s*<ul[^>]*>(.*?)</ul>",
        source, re.I | re.S,
    )
    if not match:
        return []
    result: list[str] = []
    for value in re.findall(r"<li[^>]*>(.*?)</li>", match.group(1), re.I | re.S):
        text = clean_text(value).lstrip("✓✗+- ")
        if 2 <= len(text) <= 180 and text not in result:
            result.append(text)
    return result[:limit]


def inferred_platforms(text: str) -> list[str]:
    mapping = {
        "Web": ("web app", "browser", "cloud", "online"),
        "Windows": ("windows",),
        "macOS": ("macos", "mac os", " mac "),
        "iOS": (" ios ", "iphone", "ipad"),
        "Android": ("android",),
        "API": (" api ", "developer api", "webhook"),
    }
    haystack = f" {text.casefold()} "
    return [name for name, needles in mapping.items() if any(needle in haystack for needle in needles)]


def source_candidate(source: str, name: str) -> str:
    words = [word for word in re.findall(r"[a-z0-9]+", name.casefold()) if len(word) >= 4 and word not in GENERIC_NAME_WORDS]
    for href, rel, label in re.findall(
        r'<a\b[^>]*href=["\'](https://[^"\']+)["\']([^>]*)>(.*?)</a>', source, re.I | re.S
    ):
        url = unescape(href).strip()
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold()
        if not host or host in SOURCE_HOST_BLOCKLIST or any(marker in host for marker in AFFILIATE_HOST_MARKERS):
            continue
        attributes = rel.casefold()
        anchor = clean_text(label).casefold()
        if "sponsored" in attributes or "nofollow" in attributes:
            continue
        if "official" in anchor or "website" in anchor or any(word in host for word in words):
            return url
    return ""


def legacy_record(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    raw_name = first_match((r"<h1[^>]*>(.*?)</h1>", r"<title>(.*?)</title>"), source)
    name = re.sub(r"\s+(?:Review|Pricing|Complete Guide).*", "", raw_name, flags=re.I).strip()
    if not name:
        name = path.stem.removesuffix("-review").replace("-", " ").title()
    slug = slugify(name) or path.stem.removesuffix("-review")
    description = meta_content(source, "description") or meta_content(source, "og:description")
    description = re.sub(r"\s*Pricing:\s*.*$", "", description, flags=re.I).strip()
    description = re.sub(r"\s*Rating:\s*\d+(?:\.\d+)?/10\.?", "", description, flags=re.I).strip(" .-")
    if not description or len(description) < 25:
        description = first_match((
            r'<p[^>]+class=["\'][^"\']*(?:text-xl|lead)[^"\']*["\'][^>]*>(.*?)</p>',
            r"<section[^>]*>\s*<p[^>]*>(.*?)</p>",
        ), source)
    description = description[:360].rstrip()
    keywords = meta_content(source, "keywords")
    category = next((item for item in CATEGORIES if item.casefold() in (keywords + " " + source[:12000]).casefold()), "AI Software")
    pricing = first_match((
        r"<strong>\s*Pricing:\s*</strong>\s*([^<]+)",
        r"Pricing:\s*([^<\n]{2,100})",
    ), source)
    pricing = re.sub(r"\s+", " ", pricing)[:120].strip(" .")
    best_for = first_match((
        r"Best For.*?</h[2-4]>.*?<strong>(.*?)</strong>",
        rf"{re.escape(name)}\s+is\s+best\s+for:\s*<strong>(.*?)</strong>",
    ), source)
    features = extract_list_after_heading(source, "Pros") or extract_list_after_heading(source, "Key Features")
    page = path.relative_to(ROOT).as_posix()
    canonical = meta_content(source, "canonical")
    if not canonical:
        canonical = first_match((r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',), source)
    source_url = source_candidate(source, name)
    combined = " ".join([description, best_for, *features])
    return {
        "id": slug,
        "name": name,
        "slug": slug,
        "category": category,
        "summary": description or f"Catalogue record for {name}.",
        "best_for": best_for,
        "features": features,
        "platforms": inferred_platforms(combined),
        "pricing": {
            "label": pricing,
            "has_free_plan": bool(re.search(r"\bfree\b", pricing, re.I)),
            "confidence": "legacy-unverified" if pricing else "unknown",
            "verified_at": None,
        },
        "links": {
            "profile": page,
            "partner_guide": "",
            "affiliate": "",
            "source": source_url,
        },
        "verification": {
            "status": "legacy-catalog",
            "last_checked": None,
            "source_count": 1 if source_url else 0,
        },
        "monetization": {"active": False, "network": "", "offer_id": ""},
        "search_text": " ".join([name, category, description, best_for, *features]).casefold(),
    }


def name_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def reviewed_source(offer: dict[str, Any]) -> str:
    evidence = [item for item in offer.get("evidence", []) if isinstance(item, dict)]
    selected = next((item for item in evidence if "product" in str(item.get("label") or "").casefold()), None)
    selected = selected or (evidence[0] if evidence else {})
    url = str(selected.get("url") or "")
    return url if urlparse(url).scheme == "https" else ""


def network_for(url: str) -> str:
    host = (urlparse(url).hostname or "").casefold()
    if "8odi.net" in host:
        return "impact-appsumo"
    if any(value in host for value in ("partnerstack", "partners.", "get.", "try.")):
        return "partnerstack"
    return "affiliate-partner" if url else ""


def merge_partner(records: dict[str, dict[str, Any]], offer: dict[str, Any]) -> None:
    key = name_key(str(offer["name"]))
    record = next((item for item in records.values() if name_key(str(item["name"])) == key), None)
    if record is None:
        slug = slugify(str(offer["name"]))
        record = {
            "id": slug, "name": str(offer["name"]), "slug": slug,
            "category": str(offer["category"]), "summary": str(offer["summary"]),
            "best_for": str(offer["best_for"]), "features": [], "platforms": [],
            "pricing": {"label": "", "has_free_plan": False, "confidence": "unknown", "verified_at": None},
            "links": {"profile": "", "partner_guide": "", "affiliate": "", "source": ""},
            "verification": {"status": "legacy-catalog", "last_checked": None, "source_count": 0},
            "monetization": {"active": False, "network": "", "offer_id": ""}, "search_text": "",
        }
        records[slug] = record
    record.update({
        "category": str(offer["category"]),
        "summary": str(offer["summary"]),
        "best_for": str(offer["best_for"]),
        "features": list(dict.fromkeys([*map(str, offer.get("use_cases", [])), *record.get("features", [])]))[:8],
    })
    source = reviewed_source(offer)
    record["platforms"] = inferred_platforms(" ".join([record["summary"], record["best_for"], *record["features"]]))
    record["pricing"] = {
        "label": str(offer["pricing_note"]),
        "has_free_plan": bool(re.search(r"\bfree\b", str(offer["pricing_note"]), re.I)),
        "confidence": "reviewed-source-note",
        "verified_at": str(offer["terms_verified_at"]),
    }
    record["links"].update({
        "profile": f"partner-offers/{offer['slug']}.html",
        "partner_guide": f"partner-offers/{offer['slug']}.html",
        "affiliate": str(offer["tracking_url"]),
        "source": source,
    })
    record["verification"] = {
        "status": "reviewed",
        "last_checked": str(offer["terms_verified_at"]),
        "source_count": len(offer.get("evidence", [])),
    }
    record["monetization"] = {"active": True, "network": network_for(str(offer["tracking_url"])), "offer_id": str(offer["id"])}


def merge_appsumo(records: dict[str, dict[str, Any]], offer: dict[str, Any]) -> None:
    if not offer.get("ai_relevant") or offer.get("availability") == "expired":
        return
    key = name_key(str(offer["name"]))
    record = next((item for item in records.values() if name_key(str(item["name"])) == key), None)
    if record is None:
        slug = slugify(str(offer["name"]))
        record = {
            "id": slug, "name": str(offer["name"]), "slug": slug,
            "category": str(offer.get("category") or "AI Software"),
            "summary": f"AI-relevant AppSumo catalogue record for {offer['name']}; verify current features and terms on the destination.",
            "best_for": "Buyers evaluating a currently available AI or automation offer.",
            "features": [], "platforms": [],
            "pricing": {"label": "Check current AppSumo price and terms", "has_free_plan": False, "confidence": "destination-only", "verified_at": None},
            "links": {"profile": str(offer.get("editorial_url") or "appsumo-ai-tools.html"), "partner_guide": str(offer.get("editorial_url") or ""), "affiliate": "", "source": ""},
            "verification": {"status": "legacy-catalog", "last_checked": None, "source_count": 0},
            "monetization": {"active": False, "network": "", "offer_id": ""}, "search_text": "",
        }
        records[slug] = record
    if record["verification"]["status"] != "reviewed":
        record["verification"] = {
            "status": "destination-checked",
            "last_checked": str(offer.get("last_checked_at") or "")[:10] or None,
            "source_count": 1,
        }
    record["links"]["affiliate"] = str(offer["tracking_url"])
    record["links"]["partner_guide"] = str(offer.get("editorial_url") or record["links"].get("partner_guide") or "")
    if not record["links"].get("profile"):
        record["links"]["profile"] = record["links"]["partner_guide"] or "appsumo-ai-tools.html"
    record["monetization"] = {"active": True, "network": "impact-appsumo", "offer_id": str(offer["id"])}


def build_catalog() -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[Path]] = {}
    for path in sorted(TOOLS_DIR.glob("*.html")):
        grouped.setdefault(path.stem.removesuffix("-review"), []).append(path)
    for paths in grouped.values():
        preferred = next((path for path in paths if not path.stem.endswith("-review")), paths[0])
        record = legacy_record(preferred)
        candidate = record["id"]
        suffix = 2
        while candidate in records and name_key(records[candidate]["name"]) != name_key(record["name"]):
            candidate = f"{record['id']}-{suffix}"
            suffix += 1
        record["id"] = candidate
        records[candidate] = record

    partners = load_json(PARTNER_PATH, {"offers": []})
    for offer in partners.get("offers", []):
        if isinstance(offer, dict) and offer.get("status") == "published":
            merge_partner(records, offer)
    appsumo = load_json(APPSUMO_PATH, {"offers": []})
    for offer in appsumo.get("offers", []):
        if isinstance(offer, dict):
            merge_appsumo(records, offer)

    tools = []
    for record in records.values():
        record["search_text"] = " ".join([
            str(record["name"]), str(record["category"]), str(record["summary"]),
            str(record["best_for"]), *map(str, record["features"]), *map(str, record["platforms"]),
        ]).casefold()
        tools.append(record)
    status_order = {"reviewed": 0, "destination-checked": 1, "legacy-catalog": 2}
    tools.sort(key=lambda item: (status_order.get(item["verification"]["status"], 9), item["name"].casefold()))
    return {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "methodology": {
            "entity_rule": "Duplicate legacy review URLs are consolidated into one named software entity.",
            "verification_rule": "Reviewed means evidence-backed partner data; destination-checked means the public offer destination responded; legacy records remain explicitly unverified.",
            "pricing_rule": "Legacy price labels are discovery metadata only and must be verified on the vendor source before purchase.",
            "filter_rule": "Explorer filters are client-side and canonicalize to one crawlable page rather than creating indexable URL combinations.",
        },
        "stats": {
            "tools": len(tools),
            "reviewed": sum(item["verification"]["status"] == "reviewed" for item in tools),
            "destination_checked": sum(item["verification"]["status"] == "destination-checked" for item in tools),
            "source_monitored": sum(bool(item["links"].get("source")) for item in tools),
            "monetized": sum(bool(item["monetization"]["active"]) for item in tools),
        },
        "tools": tools,
    }


def verification_label(status: str) -> str:
    return {"reviewed": "Evidence reviewed", "destination-checked": "Destination checked"}.get(status, "Catalogue record")


def card(record: dict[str, Any]) -> str:
    pricing = record["pricing"]
    price = str(pricing.get("label") or "Pricing not recorded")
    if pricing.get("confidence") == "legacy-unverified":
        price += " · verify current terms"
    links = record["links"]
    detail = str(links.get("profile") or "reviews.html")
    affiliate = str(links.get("affiliate") or "")
    affiliate_cta = ""
    if affiliate:
        offer_id = str(record["monetization"].get("offer_id") or record["id"])
        affiliate_cta = f'<a class="rounded-lg bg-indigo-600 px-4 py-2 text-center font-bold text-white" href="{esc(affiliate)}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer="" data-affiliate-network="{esc(record["monetization"]["network"])}" data-offer-id="{esc(offer_id)}" data-placement="intelligence-explorer">Check current offer</a>'
    return f'''<article class="tool-card flex flex-col rounded-2xl border border-slate-200 bg-white p-5" data-tool-card data-id="{esc(record['id'])}" data-category="{esc(record['category'])}" data-status="{esc(record['verification']['status'])}" data-free="{'true' if pricing.get('has_free_plan') else 'false'}" data-search="{esc(record['search_text'])}">
      <div class="flex items-center justify-between gap-3"><span class="text-xs font-bold uppercase tracking-wider text-indigo-700">{esc(record['category'])}</span><span class="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">{esc(verification_label(record['verification']['status']))}</span></div>
      <h2 class="mt-4 text-2xl font-black">{esc(record['name'])}</h2><p class="mt-2 flex-1 text-sm leading-6 text-slate-600">{esc(record['summary'])}</p>
      <p class="mt-4 text-sm"><strong>Best for:</strong> {esc(record['best_for'] or 'Evaluate against your workflow requirements.')}</p><p class="mt-3 text-sm text-slate-500">{esc(price)}</p>
      <div class="mt-5 flex flex-wrap gap-3"><a class="rounded-lg border border-indigo-200 px-4 py-2 text-center font-bold text-indigo-700" href="{esc(detail)}" data-content-route="" data-related-offer-id="{esc(record['id'])}" data-placement="intelligence-profile">View record</a>{affiliate_cta}</div>
    </article>'''


def render_explorer(catalog: dict[str, Any]) -> str:
    tools = list(catalog["tools"])
    categories = sorted({str(item["category"]) for item in tools})
    options = "".join(f'<option value="{esc(item)}">{esc(item)}</option>' for item in categories)
    cards = "".join(card(item) for item in tools)
    stats = catalog["stats"]
    content = f'''<section class="bg-white"><div class="mx-auto max-w-6xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Open software intelligence</p><h1 class="mt-4 text-4xl font-black md:text-6xl">AI Tool Intelligence Database</h1><p class="mt-5 max-w-3xl text-lg leading-8 text-slate-600">Search {stats['tools']} consolidated software records by use case, category, free-plan signal and evidence status. Every record shows what is reviewed, what was merely destination-checked and what still needs vendor verification.</p><div class="mt-8 grid gap-3 sm:grid-cols-4"><p class="rounded-xl bg-slate-100 p-4"><strong class="block text-2xl">{stats['tools']}</strong><span class="text-sm text-slate-600">software entities</span></p><p class="rounded-xl bg-slate-100 p-4"><strong class="block text-2xl">{stats['reviewed']}</strong><span class="text-sm text-slate-600">evidence reviewed</span></p><p class="rounded-xl bg-slate-100 p-4"><strong class="block text-2xl">{stats['source_monitored']}</strong><span class="text-sm text-slate-600">vendor sources mapped</span></p><p class="rounded-xl bg-slate-100 p-4"><strong class="block text-2xl">{stats['monetized']}</strong><span class="text-sm text-slate-600">commission-eligible</span></p></div><div class="mt-7 flex flex-wrap gap-4 text-sm font-bold text-indigo-700"><a href="ai-tool-alternatives.html">Open migration wizard →</a><a href="ai-tool-changes.html">See confirmed changes →</a><a href="data/ai-tool-intelligence.csv" download>Download the dataset →</a><a href="data/tool_intelligence.json">Open JSON API →</a></div></div></section>
    <section class="mx-auto max-w-6xl px-5 py-10"><div class="rounded-2xl border border-slate-200 bg-white p-5"><div class="grid gap-4 md:grid-cols-4"><label class="font-bold md:col-span-2">Search by tool, job or feature<input id="intel-search" type="search" class="mt-2 w-full rounded-lg border border-slate-300 p-3" placeholder="Example: podcast editing or vector search"></label><label class="font-bold">Category<select id="intel-category" class="mt-2 w-full rounded-lg border border-slate-300 p-3"><option value="">All categories</option>{options}</select></label><label class="font-bold">Evidence<select id="intel-status" class="mt-2 w-full rounded-lg border border-slate-300 p-3"><option value="">All records</option><option value="reviewed">Evidence reviewed</option><option value="destination-checked">Destination checked</option><option value="legacy-catalog">Legacy catalogue</option></select></label></div><label class="mt-4 flex items-center gap-2 text-sm font-bold"><input id="intel-free" type="checkbox"> Has a recorded free-plan signal</label><p id="intel-count" class="mt-4 text-sm text-slate-500" aria-live="polite"></p></div><div id="intel-grid" class="mt-7 grid gap-5 md:grid-cols-2 lg:grid-cols-3">{cards}</div><div class="mt-8 text-center"><button id="intel-more" class="rounded-lg border border-indigo-300 px-6 py-3 font-bold text-indigo-700" type="button">Show more tools</button></div><p class="mt-8 text-xs leading-6 text-slate-500">Pricing labels marked as legacy are discovery metadata, not current quotes. Verify final price, plan limits and commercial-use terms on the source before purchasing. Affiliate links are marked and may earn artificial.one a commission at no extra cost to you.</p></section>
    <script>(function(){{var cards=[].slice.call(document.querySelectorAll('[data-tool-card]')),search=document.getElementById('intel-search'),category=document.getElementById('intel-category'),status=document.getElementById('intel-status'),free=document.getElementById('intel-free'),count=document.getElementById('intel-count'),more=document.getElementById('intel-more'),limit=30;function apply(reset){{if(reset)limit=30;var tokens=search.value.trim().toLowerCase().split(/\\s+/).filter(Boolean),matches=cards.filter(function(card){{return(!category.value||card.dataset.category===category.value)&&(!status.value||card.dataset.status===status.value)&&(!free.checked||card.dataset.free==='true')&&tokens.every(function(token){{return card.dataset.search.indexOf(token)>-1;}});}});cards.forEach(function(card){{card.hidden=true;}});matches.slice(0,limit).forEach(function(card){{card.hidden=false;}});count.textContent=matches.length+' matching software record'+(matches.length===1?'':'s');more.hidden=matches.length<=limit;}}[search,category,status,free].forEach(function(control){{control.addEventListener(control===search?'input':'change',function(){{apply(true);}});}});more.addEventListener('click',function(){{limit+=30;apply(false);}});apply(true);}})();</script>'''
    structured = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": "Artificial.One AI Tool Intelligence Database",
        "description": "A normalized catalogue of AI and business software with evidence status, pricing signals and decision links.",
        "url": "https://artificial.one/ai-tool-database.html",
        "dateModified": catalog["updated_at"],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": "https://artificial.one/data/tool_intelligence.json"},
            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": "https://artificial.one/data/ai-tool-intelligence.csv"},
        ],
    }
    return shell(title="AI Tool Database: Prices, Free Plans & Verified Sources | artificial.one", description=f"Search {stats['tools']} consolidated AI and business software records by use case, category, free-plan signal and verification status.", canonical_path="ai-tool-database.html", content=content, structured_data=structured, social_image="https://artificial.one/images/social-cards/ai-tool-database.jpg", social_image_alt="Search the Artificial.One AI Tool Intelligence Database")


def compact_tool(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"], "name": record["name"], "category": record["category"],
        "summary": record["summary"], "best_for": record["best_for"],
        "features": record["features"], "platforms": record["platforms"],
        "free": bool(record["pricing"].get("has_free_plan")),
        "price": str(record["pricing"].get("label") or "Pricing not recorded"),
        "status": record["verification"]["status"], "links": record["links"],
        "monetization": record["monetization"],
    }


def render_alternatives(catalog: dict[str, Any]) -> str:
    tools = list(catalog["tools"])
    options = "".join(f'<option value="{esc(item["id"])}">{esc(item["name"])}</option>' for item in tools)
    payload = json.dumps([compact_tool(item) for item in tools], ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    content = rf'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Interactive migration planner</p><h1 class="mt-4 text-4xl font-black md:text-6xl">Find an AI tool alternative—and plan the switch</h1><p class="mt-5 max-w-3xl text-lg leading-8 text-slate-600">Choose what you use now, why you want to leave and what matters most. The wizard scores known catalogue attributes and explains every recommendation.</p></div></section><section class="mx-auto max-w-5xl px-5 py-10"><div class="grid gap-5 rounded-2xl border border-slate-200 bg-white p-6 md:grid-cols-3"><label class="font-bold">Current tool<select id="migration-from" class="mt-2 w-full rounded-lg border border-slate-300 p-3"><option value="">Choose a tool</option>{options}</select></label><label class="font-bold">Reason for switching<select id="migration-reason" class="mt-2 w-full rounded-lg border border-slate-300 p-3"><option value="cost">Reduce cost</option><option value="features">Need different features</option><option value="complexity">Simpler workflow</option><option value="platform">Platform or API fit</option></select></label><label class="font-bold">Top priority<select id="migration-priority" class="mt-2 w-full rounded-lg border border-slate-300 p-3"><option value="fit">Closest workflow fit</option><option value="verified">Strongest evidence</option><option value="free">Recorded free plan</option><option value="api">API availability</option></select></label><div class="md:col-span-3"><button id="migration-run" type="button" class="rounded-lg bg-indigo-600 px-6 py-3 font-bold text-white">Build migration shortlist</button></div></div><div id="migration-summary" class="mt-7" aria-live="polite"></div><div id="migration-results" class="mt-5 grid gap-5 md:grid-cols-3"></div><section id="migration-checklist" class="mt-8 rounded-2xl border border-slate-200 bg-white p-6" hidden><h2 class="text-2xl font-black">Migration checklist</h2><ol class="mt-4 list-decimal space-y-2 pl-5 text-slate-700"><li>Export data, templates, prompts and team configuration from the current tool.</li><li>Confirm the replacement supports the required formats, integrations and commercial-use rights.</li><li>Run one real workflow in parallel before cancelling the current subscription.</li><li>Document gaps, retrain collaborators and retain a rollback copy.</li><li>Verify current pricing and limits on the vendor source before purchasing.</li></ol></section><p class="mt-6 text-xs leading-6 text-slate-500">Recommendations use recorded category, feature, platform, free-plan and evidence attributes. Commission eligibility contributes only a two-point tie-break and never overrides workflow fit. Legacy data remains explicitly unverified.</p></section>
    <script>const migrationTools={payload};(function(){{var from=document.getElementById('migration-from'),reason=document.getElementById('migration-reason'),priority=document.getElementById('migration-priority'),run=document.getElementById('migration-run'),results=document.getElementById('migration-results'),summary=document.getElementById('migration-summary'),checklist=document.getElementById('migration-checklist');function h(value){{return String(value||'').replace(/[&<>"']/g,function(char){{return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char];}});}}function safeUrl(value,fallback){{var url=String(value||'');return (/^https:\/\//i.test(url)||/^[a-z0-9][a-z0-9._\/-]*\.html(?:[?#].*)?$/i.test(url))?h(url):fallback;}}function words(tool){{return new Set(([tool.summary,tool.best_for].concat(tool.features||[])).join(' ').toLowerCase().match(/[a-z0-9]+/g)||[]);}}function overlap(a,b){{var aw=words(a),bw=words(b),count=0;aw.forEach(function(word){{if(word.length>4&&bw.has(word))count++;}});return Math.min(30,count*3);}}function score(base,item){{var value=(base.category===item.category?45:0)+overlap(base,item);if(priority.value==='verified')value+=item.status==='reviewed'?25:item.status==='destination-checked'?10:0;if(priority.value==='free'&&item.free)value+=25;if(priority.value==='api'&&(item.platforms||[]).indexOf('API')>-1)value+=25;if(priority.value==='fit')value+=overlap(base,item);if(reason.value==='cost'&&item.free)value+=20;if(reason.value==='platform'&&(item.platforms||[]).length)value+=10;if(reason.value==='features')value+=Math.min(15,(item.features||[]).length*2);if(reason.value==='complexity'&&item.category===base.category)value+=8;if(item.monetization&&item.monetization.active)value+=2;return value;}}function rationale(base,item){{var parts=[];if(item.category===base.category)parts.push('same '+item.category+' category');var shared=overlap(base,item);if(shared)parts.push('shared workflow language');if(item.free)parts.push('recorded free-plan signal');if(item.status==='reviewed')parts.push('evidence-reviewed record');if((item.platforms||[]).indexOf('API')>-1)parts.push('API signal');return parts.slice(0,3).join(' · ')||'broader catalogue alternative';}}function render(){{var base=migrationTools.find(function(item){{return item.id===from.value;}});if(!base){{summary.innerHTML='<p class="rounded-xl bg-amber-50 p-4 text-amber-900">Choose the tool you currently use.</p>';results.innerHTML='';checklist.hidden=true;return;}}var ranked=migrationTools.filter(function(item){{return item.id!==base.id;}}).map(function(item){{return{{item:item,score:score(base,item)}};}}).sort(function(a,b){{return b.score-a.score||a.item.name.localeCompare(b.item.name);}}).slice(0,3);summary.innerHTML='<h2 class="text-3xl font-black">Best recorded alternatives to '+h(base.name)+'</h2><p class="mt-2 text-slate-600">Shortlisted for '+h(reason.options[reason.selectedIndex].text.toLowerCase())+' with '+h(priority.options[priority.selectedIndex].text.toLowerCase())+'.</p>';results.innerHTML=ranked.map(function(row,index){{var item=row.item,affiliate=item.links.affiliate&&/^https:\/\//i.test(item.links.affiliate)?'<a class="mt-3 block rounded-lg bg-indigo-600 px-4 py-2 text-center font-bold text-white" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-affiliate-network="'+h(item.monetization.network)+'" data-offer-id="'+h(item.monetization.offer_id||item.id)+'" data-placement="migration-wizard" href="'+safeUrl(item.links.affiliate,'#')+'">Check current offer</a>':'';return '<article class="rounded-2xl border border-slate-200 bg-white p-5"><p class="text-xs font-bold uppercase tracking-widest text-indigo-600">Option '+(index+1)+' · score '+row.score+'</p><h3 class="mt-2 text-2xl font-black">'+h(item.name)+'</h3><p class="mt-3 text-sm leading-6 text-slate-600">'+h(item.summary)+'</p><p class="mt-4 text-xs text-slate-500">'+h(rationale(base,item))+'</p><a class="mt-4 block font-bold text-indigo-700" data-content-route data-related-offer-id="'+h(item.id)+'" data-placement="migration-profile" href="'+safeUrl(item.links.profile,'reviews.html')+'">Review the record →</a>'+affiliate+'</article>';}}).join('');checklist.hidden=false;var params=new URLSearchParams({{from:from.value,reason:reason.value,priority:priority.value}});history.replaceState(null,'','?'+params.toString());}}run.addEventListener('click',render);var params=new URLSearchParams(location.search);if(params.get('from')){{from.value=params.get('from');reason.value=params.get('reason')||'cost';priority.value=params.get('priority')||'fit';render();}}}})();</script>'''
    return shell(title="AI Tool Alternatives & Migration Wizard | artificial.one", description="Find alternatives to your current AI tool using transparent category, feature, platform, free-plan and evidence signals, then follow a practical migration checklist.", canonical_path="ai-tool-alternatives.html", content=content, structured_data={"@context": "https://schema.org", "@type": "WebApplication", "name": "AI Tool Alternatives and Migration Wizard", "applicationCategory": "BusinessApplication", "isAccessibleForFree": True}, social_image="https://artificial.one/images/social-cards/ai-tool-alternatives.jpg", social_image_alt="Find AI tool alternatives with the Artificial.One migration wizard")


def default_history() -> dict[str, Any]:
    return {"version": 1, "updated_at": date.today().isoformat(), "method": "two-consecutive-observation vendor-source monitor", "coverage": {"tracked_sources": 0, "successful_checks": 0}, "events": []}


def render_changes(catalog: dict[str, Any], history: dict[str, Any]) -> str:
    by_id = {str(item["id"]): item for item in catalog["tools"]}
    events = [item for item in history.get("events", []) if isinstance(item, dict)]
    cards = []
    for event in events[:60]:
        tool = by_id.get(str(event.get("tool_id") or ""), {})
        name = str(tool.get("name") or event.get("tool_name") or "AI tool")
        profile = str(tool.get("links", {}).get("profile") or "ai-tool-database.html")
        cards.append(f'''<article class="rounded-2xl border border-slate-200 bg-white p-6"><p class="text-xs font-bold uppercase tracking-widest text-indigo-600">{esc(event.get('kind', 'product'))} change · {esc(event.get('detected_on'))}</p><h2 class="mt-2 text-2xl font-black">{esc(name)}</h2><p class="mt-3 text-slate-600">{esc(event.get('message'))}</p><div class="mt-5 flex flex-wrap gap-4"><a class="font-bold text-indigo-700" href="{esc(profile)}">Open tool record</a><a class="font-bold text-slate-700" href="{esc(event.get('source_url'))}" target="_blank" rel="noopener">Verify with vendor</a></div></article>''')
    if not cards:
        cards.append('<div class="rounded-2xl border border-slate-200 bg-white p-8"><h2 class="text-2xl font-black">Monitoring history starts now</h2><p class="mt-3 text-slate-600">No vendor change has yet passed the two-consecutive-observation rule. Initial snapshots never become public “changes.”</p></div>')
    coverage = history.get("coverage", {})
    tracked_sources = coverage.get("tracked_sources") or catalog["stats"]["source_monitored"]
    content = f'''<section class="bg-white"><div class="mx-auto max-w-5xl px-5 py-16"><p class="text-sm font-bold uppercase tracking-widest text-indigo-600">Repeated-source verification</p><h1 class="mt-4 text-4xl font-black md:text-6xl">AI pricing and feature change history</h1><p class="mt-5 max-w-3xl text-lg leading-8 text-slate-600">A public timeline of confirmed changes from mapped vendor sources. A changed page must produce the same new signal twice before an event is published.</p><div class="mt-7 flex flex-wrap gap-5 text-sm"><span><strong>{esc(tracked_sources)}</strong> mapped sources</span><span><strong>{esc(coverage.get('successful_checks', 0))}</strong> successful checks in the latest batch</span><a class="font-bold text-indigo-700" href="ai-tool-database.html">Search the full database →</a></div></div></section><section class="mx-auto grid max-w-5xl gap-5 px-5 py-10 md:grid-cols-2">{''.join(cards)}</section><section class="mx-auto max-w-5xl px-5 pb-10"><p class="text-xs leading-6 text-slate-500">The monitor stores only fingerprints privately. Public events contain the tool, date, broad change type and source URL—not scraped vendor copy. Always verify current terms with the vendor.</p></section>'''
    return shell(title="AI Tool Pricing & Feature Change History | artificial.one", description="Track confirmed AI software pricing, plan, availability and feature changes using repeated observations from mapped vendor sources.", canonical_path="ai-tool-changes.html", content=content, structured_data={"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI tool pricing and feature change history", "dateModified": history.get("updated_at")})


def render_home_block(catalog: dict[str, Any]) -> str:
    stats = catalog["stats"]
    return f'''{HOME_START}
      <section className="bg-slate-950 py-16 text-white" aria-labelledby="intelligence-title"><div className="container mx-auto px-4"><p className="text-sm font-bold uppercase tracking-widest text-indigo-300">Live software intelligence</p><h2 id="intelligence-title" className="mt-3 text-3xl font-black md:text-5xl">Search {stats['tools']} normalized AI tool records</h2><p className="mt-4 max-w-3xl text-slate-300">Compare evidence status, recorded pricing signals, free plans and workflow fit—then use the migration wizard or follow confirmed vendor changes.</p><div className="mt-7 flex flex-wrap gap-3"><a className="rounded-lg bg-indigo-500 px-5 py-3 font-bold text-white" href="ai-tool-database.html?utm_source=homepage&amp;utm_medium=intelligence&amp;utm_campaign=database" data-content-route="" data-placement="homepage-intelligence">Search the database</a><a className="rounded-lg border border-slate-600 px-5 py-3 font-bold text-white" href="ai-tool-alternatives.html?utm_source=homepage&amp;utm_medium=intelligence&amp;utm_campaign=migration" data-content-route="" data-placement="homepage-migration">Plan a tool migration</a><a className="px-2 py-3 font-bold text-indigo-200" href="ai-tool-changes.html?utm_source=homepage&amp;utm_medium=intelligence&amp;utm_campaign=change-history" data-content-route="" data-placement="homepage-change-history">Follow tool changes →</a></div></div></section>
{HOME_END}'''


def update_homepage(source: str, catalog: dict[str, Any]) -> str:
    block = render_home_block(catalog)
    if HOME_START in source and HOME_END in source:
        return re.sub(re.escape(HOME_START) + r".*?" + re.escape(HOME_END), block, source, flags=re.S)
    marker = "      {/* APPSUMO_DEAL_PULSE_START */}"
    if marker not in source:
        marker = "      {/* Featured Tools */}"
    if marker not in source:
        # The compact decision-engine homepage routes to the database through
        # navigation and contextual recommendations instead of a legacy block.
        return source
    return source.replace(marker, block + "\n\n" + marker, 1)


def update_sitemap(source: str, updated_at: str) -> str:
    rows = [SITEMAP_START]
    for path, priority, frequency in (
        ("ai-tool-database.html", "0.95", "daily"),
        ("ai-tool-alternatives.html", "0.9", "weekly"),
        ("ai-tool-changes.html", "0.85", "daily"),
    ):
        rows.extend(["  <url>", f"    <loc>https://artificial.one/{path}</loc>", f"    <lastmod>{updated_at}</lastmod>", f"    <changefreq>{frequency}</changefreq>", f"    <priority>{priority}</priority>", "  </url>"])
    rows.append(SITEMAP_END)
    block = "\n".join(rows)
    source = re.sub(r"\s*" + re.escape(SITEMAP_START) + r".*?" + re.escape(SITEMAP_END), "", source, flags=re.S)
    source = re.sub(r"\s*<url>\s*<loc>https://artificial\.one/(?:ai-tool-database|ai-tool-alternatives|ai-tool-changes)\.html</loc>.*?</url>", "", source, flags=re.S)
    if "</urlset>" not in source:
        raise ValueError("sitemap.xml has no closing urlset")
    before = source.rsplit("</urlset>", 1)[0].rstrip()
    return before + "\n" + block + "\n</urlset>\n"


def render_csv(catalog: dict[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["id", "name", "category", "summary", "best_for", "pricing_label", "free_plan_signal", "verification_status", "last_checked", "profile_url", "source_url", "monetized"])
    for item in catalog["tools"]:
        writer.writerow([
            item["id"], item["name"], item["category"], item["summary"], item["best_for"],
            item["pricing"]["label"], str(bool(item["pricing"]["has_free_plan"])).lower(),
            item["verification"]["status"], item["verification"]["last_checked"] or "",
            "https://artificial.one/" + str(item["links"]["profile"]).lstrip("/"),
            item["links"]["source"], str(bool(item["monetization"]["active"])).lower(),
        ])
    return output.getvalue()


def outputs() -> dict[Path, str]:
    catalog = build_catalog()
    history = load_json(HISTORY_PATH, default_history())
    serialized = json.dumps(catalog, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return {
        CATALOG_PATH: serialized,
        CSV_PATH: render_csv(catalog),
        EXPLORER_PATH: render_explorer(catalog),
        ALTERNATIVES_PATH: render_alternatives(catalog),
        CHANGES_PATH: render_changes(catalog, history),
        HOME_PATH: update_homepage(HOME_PATH.read_text(encoding="utf-8"), catalog),
        SITEMAP_PATH: update_sitemap(SITEMAP_PATH.read_text(encoding="utf-8"), str(catalog["updated_at"])),
    }


def build(check: bool = False) -> int:
    if not HISTORY_PATH.exists() and not check:
        HISTORY_PATH.write_text(json.dumps(default_history(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    expected = outputs()
    stale = [str(path.relative_to(ROOT)) for path, value in expected.items() if not path.exists() or path.read_text(encoding="utf-8") != value]
    if check:
        if stale:
            print("Tool intelligence build is stale: " + ", ".join(stale), file=sys.stderr)
            return 1
        catalog = json.loads(expected[CATALOG_PATH])
        print(f"Tool intelligence build is current ({catalog['stats']['tools']} normalized records).")
        return 0
    for path, value in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8", newline="")
    catalog = json.loads(expected[CATALOG_PATH])
    print(f"Built AI Tool Intelligence Database with {catalog['stats']['tools']} normalized records.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raise SystemExit(build(args.check))
