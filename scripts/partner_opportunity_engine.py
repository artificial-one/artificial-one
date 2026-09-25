#!/usr/bin/env python3
"""Discover, screen and onboard affiliate opportunities without accepting contracts.

Discovery and policy classification are unattended. Applications and terms remain
an owner action because they create binding representations. Once PartnerStack
reports an approved partnership and returns a usable tracking link, a conservative
source-backed offer can enter the existing publishing pipeline automatically.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from hashlib import sha256
from html import escape, unescape
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

try:
    from scripts import partnerstack_cloud_monitor as ps
    from scripts import affiliate_network_connectors as network_connectors
except ImportError:
    import partnerstack_cloud_monitor as ps  # type: ignore
    import affiliate_network_connectors as network_connectors  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE_URL = "https://market.partnerstack.com/"
OUTPUT_PATH = ROOT / "data" / "partner_opportunities.json"
QUEUE_PAGE_PATH = ROOT / "partner-opportunities.html"
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
INTELLIGENCE_PATH = ROOT / "data" / "tool_intelligence.json"
RESEND_URL = "https://api.resend.com/emails"
USER_AGENT = "artificial.one-partner-scout/1.1 (+https://artificial.one/)"
APPLICATION_PROFILE = (
    "artificial.one is an AI and business-software discovery and decision-support site. "
    "We publish transparent affiliate disclosures, factual use-case guides, comparisons "
    "and calculators. We do not use incentivized clicks, spam, false claims or trademark bidding."
)
ACTIONABLE_STATES = {"ready_for_owner_application", "policy_review_required", "approved_link_pending", "terms_required"}
RELEVANCE_TERMS = {
    "artificial intelligence": 38, "ai": 26, "software": 18, "saas": 24,
    "automation": 24, "marketing": 20, "sales": 18, "analytics": 20,
    "productivity": 20, "development": 18, "developer": 18, "content": 16,
    "design": 14, "video": 16, "audio": 16, "data": 16, "seo": 20,
    "e-commerce": 12, "customer service": 12, "human resources": 10,
}
POLICY_PATTERNS = {
    "trademark_bidding_restricted": r"(?:no|prohibit(?:ed)?|may not|must not).{0,100}(?:(?:trademark|brand).{0,50}(?:bid|ppc|paid search)|(?:bid|ppc|paid search).{0,50}(?:trademark|brand))",
    "paid_search_restricted": r"(?:no|prohibit(?:ed)?|may not|must not).{0,70}(?:paid search|ppc|search advertising)",
    "coupon_restricted": r"(?:no|prohibit(?:ed)?|may not|must not).{0,70}(?:coupon|voucher|discount code)",
    "email_restricted": r"(?:no|prohibit(?:ed)?|may not|must not).{0,70}(?:email|newsletter|electronic mail)",
    "incentive_restricted": r"(?:no|prohibit(?:ed)?|may not|must not).{0,70}(?:incentiv|cashback|rebate)",
    "content_approval_required": r"(?:prior|written).{0,40}(?:approval|consent).{0,80}(?:content|creative|advertis)",
    "disclosure_required": r"(?:affiliate|material connection).{0,80}(?:disclos|identify)",
}
COOKIE_RE = re.compile(r"\b(\d{1,3})[ -]day(?:s)?\b.{0,40}(?:cookie|referral|attribution)|(?:cookie|referral|attribution).{0,40}\b(\d{1,3})[ -]day", re.I | re.S)
ANCHOR_RE = re.compile(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


class ScoutError(RuntimeError):
    pass


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def fetch_text(url: str, timeout: int = 35) -> str:
    request = Request(url, headers={"Accept": "text/html,application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        content_type = str(response.headers.get("Content-Type") or "")
        if not any(value in content_type.casefold() for value in ("text", "json", "xml", "html")):
            return ""
        return response.read(12_000_000).decode("utf-8", errors="replace")


def clean_text(value: Any, limit: int = 800) -> str:
    text = unescape(TAG_RE.sub(" ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")[:80]


def normalized_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def partnerstack_application_url(slug: str) -> str:
    encoded = quote(slug, safe="")
    return f"https://dash.partnerstack.com/marketplace/all/details/{encoded}?{urlencode({'company': slug, 'gref': 'marketplace'})}"


def https_url(value: Any) -> str:
    raw = unescape(str(value or "").strip())
    if raw.startswith("www."):
        raw = "https://" + raw
    parsed = urlparse(raw)
    return raw if parsed.scheme == "https" and parsed.netloc else ""


def public_reference_url(value: Any) -> str:
    """Keep public references useful without republishing bearer-style parameters."""
    raw = https_url(value)
    if not raw:
        return ""
    parsed = urlparse(raw)
    sensitive = {"access_token", "auth", "key", "secret", "session", "signature", "token"}
    query = [(name, item) for name, item in parse_qsl(parsed.query, keep_blank_values=True) if name.casefold() not in sensitive]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), ""))


def parse_partnerstack_directory(source: str) -> list[dict[str, Any]]:
    marker = "window.__INITIAL_STATE__ = "
    start = source.find(marker)
    if start < 0:
        raise ScoutError("PartnerStack directory did not expose its public initial state")
    state, _ = json.JSONDecoder().raw_decode(source[start + len(marker):].lstrip())
    companies = state.get("company", {}).get("companies", {}) if isinstance(state, dict) else {}
    if not isinstance(companies, dict):
        raise ScoutError("PartnerStack directory returned an unexpected company collection")
    result: list[dict[str, Any]] = []
    for fallback_slug, item in companies.items():
        if not isinstance(item, dict):
            continue
        slug = slugify(str(item.get("slug") or fallback_slug))
        tags = [clean_text(tag.get("name"), 80) for tag in item.get("tags", []) if isinstance(tag, dict)]
        result.append({
            "id": f"partnerstack:{slug}",
            "network": "partnerstack",
            "name": clean_text(item.get("name") or item.get("splitName") or fallback_slug, 120),
            "slug": slug,
            "description": clean_text(item.get("enriched_description") or item.get("description"), 700),
            "offer": clean_text(item.get("offer") or item.get("group_marketplace_config", {}).get("marketplace_offer"), 300),
            "tags": sorted({tag for tag in tags if tag}),
            "application_url": partnerstack_application_url(slug),
            "terms_url": https_url(item.get("tos")),
            "website": https_url(item.get("website")),
            "waitlist": bool(item.get("waitlist")),
            "archived": bool(item.get("archived")),
            "links_enabled": bool(item.get("links_enabled")),
            "materials": bool(item.get("materials")),
            "sub_id_enabled": bool(item.get("sub_id_enabled")),
            "revenue_share": bool(item.get("revenue_share")),
            "review_days": int(item.get("average_application_review_time") or 0),
            "source": MARKETPLACE_URL,
        })
    return result


def source_link_candidates(source_url: str, page: str) -> list[str]:
    values: list[str] = []
    for href, label in ANCHOR_RE.findall(page):
        combined = f"{href} {clean_text(label, 180)}".casefold()
        if not re.search(r"\b(affiliate|affiliates|partner program|referral program|ambassador)\b", combined):
            continue
        candidate = urljoin(source_url, unescape(href.strip()))
        if https_url(candidate) and candidate not in values:
            values.append(candidate)
    return values


def discover_vendor_program(record: dict[str, Any]) -> dict[str, Any] | None:
    links = record.get("links", {}) if isinstance(record.get("links"), dict) else {}
    source = https_url(links.get("source"))
    if not source or bool(record.get("monetization", {}).get("active")):
        return None
    try:
        candidates = source_link_candidates(source, fetch_text(source, 20))
    except Exception:
        return None
    if not candidates:
        return None
    name = clean_text(record.get("name"), 120)
    application = candidates[0]
    network, platform = network_connectors.classify_application_platform(application)
    return {
        "id": f"direct:{slugify(name)}",
        "network": network,
        "platform": platform,
        "name": name,
        "slug": slugify(name),
        "description": clean_text(record.get("summary"), 700),
        "offer": "Direct vendor affiliate or referral program discovered from its official website.",
        "tags": [clean_text(record.get("category"), 80)],
        "application_url": application,
        "terms_url": application,
        "website": source,
        "waitlist": False,
        "archived": False,
        "links_enabled": True,
        "materials": False,
        "sub_id_enabled": False,
        "revenue_share": False,
        "review_days": 0,
        "source": source,
    }


def discover_direct_programs(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    records = [item for item in catalog.get("tools", []) if isinstance(item, dict)]
    result: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(discover_vendor_program, item) for item in records]
        for future in as_completed(futures):
            item = future.result()
            if item:
                result.append(item)
    return sorted(result, key=lambda item: item["name"].casefold())


def relevance_score(item: dict[str, Any]) -> tuple[int, list[str]]:
    haystack = " ".join([str(item.get("name") or ""), str(item.get("description") or ""), " ".join(item.get("tags", []))]).casefold()
    matched: list[str] = []
    relevance = 0
    for term, points in RELEVANCE_TERMS.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", haystack):
            relevance = max(relevance, points)
            matched.append(term)
    score = relevance
    if item.get("offer"):
        score += 15
    if item.get("links_enabled"):
        score += 10
    if item.get("revenue_share"):
        score += 8
    if item.get("sub_id_enabled"):
        score += 5
    if item.get("materials"):
        score += 4
    if any(str(tag).casefold() in {"trusted", "hot"} for tag in item.get("tags", [])):
        score += 5
    if str(item.get("network") or "").startswith("direct-"):
        score += 15
    if item.get("waitlist") or item.get("archived"):
        score -= 100
    return max(0, min(100, score)), sorted(set(matched))


def inspect_policy(url: str) -> dict[str, Any]:
    if not url:
        return {"status": "missing", "signals": {}, "cookie_days": None}
    try:
        text = clean_text(fetch_text(url, 25), 120_000).casefold()
    except Exception:
        return {"status": "unreachable", "signals": {}, "cookie_days": None}
    signals = {name: bool(re.search(pattern, text, re.I | re.S)) for name, pattern in POLICY_PATTERNS.items()}
    cookie = COOKIE_RE.search(text)
    days = int(next(value for value in cookie.groups() if value)) if cookie else None
    return {"status": "reviewed", "signals": signals, "cookie_days": days}


def known_program_names(root: Path) -> set[str]:
    offers = load_json(root / "data/partner_offers.json", {"offers": []})
    audit = load_json(root / "data/partnerstack_program_audit.json", {"programs": []})
    values: list[Any] = []
    for item in offers.get("offers", []):
        if isinstance(item, dict):
            values.extend((item.get("name"), item.get("id"), item.get("slug")))
    for item in audit.get("programs", []):
        if isinstance(item, dict):
            values.extend((item.get("name"), item.get("slug")))
    return {normalized_name(str(value)) for value in values if value}


def partnership_names(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        company = item.get("company") if isinstance(item.get("company"), dict) else {}
        name = str(company.get("name") or item.get("company_name") or item.get("name") or "")
        if name:
            result[normalized_name(name)] = item
        for value in (company.get("slug"), item.get("company_slug"), item.get("slug")):
            if value:
                result[normalized_name(str(value))] = item
    return result


def _nested_value(item: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """Return the first useful value for a small, explicit set of API fields."""
    queue: list[dict[str, Any]] = [item]
    while queue:
        current = queue.pop(0)
        for key in keys:
            value = current.get(key)
            if value not in (None, "", [], {}):
                return value
        queue.extend(value for value in current.values() if isinstance(value, dict))
    return ""


def relationship_terms_required(item: dict[str, Any]) -> bool:
    """Detect an explicit terms gate without guessing from a missing link."""
    explicit = _nested_value(item, ("terms_required", "requires_terms_acceptance", "tos_required"))
    if isinstance(explicit, bool):
        return explicit
    status = clean_text(
        _nested_value(item, ("terms_status", "tos_status", "access_status", "approved_status", "status")), 80
    ).casefold().replace("_", "-")
    return status in {
        "required", "pending", "not-accepted", "terms-required",
        "tos-acceptance-pending", "terms-acceptance-pending",
    }


def merge_authenticated_partnerstack(
    discovered: list[dict[str, Any]], partnerships: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Make the authenticated relationship list authoritative over discovery."""
    by_name: dict[str, dict[str, Any]] = {}
    for item in discovered:
        if item.get("network", "partnerstack") == "partnerstack":
            key = normalized_name(str(item.get("name") or ""))
            if key:
                by_name[key] = item

    for partnership in partnerships:
        company = partnership.get("company") if isinstance(partnership.get("company"), dict) else {}
        name = clean_text(company.get("name") or partnership.get("company_name") or partnership.get("name"), 120)
        if not name:
            continue
        slug = slugify(str(company.get("slug") or partnership.get("company_slug") or partnership.get("slug") or name))
        status = clean_text(partnership.get("approved_status") or partnership.get("status"), 80).casefold()
        fields = {
            "approved": status in {"approved", "active"},
            "authenticated_relationship": True,
            "relationship_status": status or "unknown",
            "terms_required": relationship_terms_required(partnership),
            "partnership_key": clean_text(partnership.get("key") or partnership.get("partnership_key"), 160),
        }
        existing = by_name.get(normalized_name(name))
        if existing:
            existing.update(fields)
            continue

        website = https_url(_nested_value(partnership, ("website", "website_url", "url")))
        terms = https_url(_nested_value(partnership, ("tos", "terms_url", "terms")))
        record = {
            "id": f"partnerstack:{slug}", "network": "partnerstack", "name": name, "slug": slug,
            "description": clean_text(_nested_value(partnership, ("description", "company_description", "program_description")), 700),
            "offer": clean_text(_nested_value(partnership, ("offer", "commission_description")), 300),
            "tags": ["Software"], "application_url": partnerstack_application_url(slug),
            "terms_url": terms, "website": website, "waitlist": False, "archived": False,
            "links_enabled": True, "materials": False, "sub_id_enabled": False,
            "revenue_share": True, "review_days": 0, "source": "https://dash.partnerstack.com/home",
            **fields,
        }
        discovered.append(record)
        by_name[normalized_name(name)] = record
    return discovered


def partnerstack_links(api_key: str, partnership: dict[str, Any]) -> list[str]:
    identifier = str(partnership.get("key") or partnership.get("partnership_key") or "")
    if not identifier:
        return []
    url = f"{ps.API_BASE}/links/partnership/{quote(identifier)}?limit=250"
    request = Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception:
        return []
    items, _ = ps._items_from_payload(payload)
    result: list[str] = []
    for item in items:
        for key in ("url", "link", "tracking_url", "share_url"):
            value = https_url(item.get(key))
            if value and value not in result:
                result.append(value)
    return result


def category_for(item: dict[str, Any]) -> str:
    if item.get("network") == "awin":
        text = " ".join(
            str(value or "")
            for value in (item.get("name"), item.get("description"), item.get("website"))
        ).casefold()
        category_rules = (
            ("Document signing", ("esign", "sign pdf", "document signing", "electronic signature")),
            ("Online learning", ("online course", "education", "skills training", "career development", "accredited course")),
            ("AI product photography", ("product photo", "product photography", "ai photo", "photo shoot")),
            ("Trade show technology", ("trade show", "exhibitor", "exhibition")),
            ("Collectibles & display", ("lego", "collector", "display frame", "display case")),
            ("AI productivity", ("ai productivity", "ai workflow", "work smarter")),
        )
        for category, needles in category_rules:
            if any(needle in text for needle in needles):
                return category
    ignored = {"affiliates", "publishers", "hot", "trusted"}
    return next((tag for tag in item.get("tags", []) if tag.casefold() not in ignored), "AI & Business Software")


def positioning_for(name: str, category: str) -> tuple[str, str, list[str]]:
    profiles = {
        "Document signing": (
            "iPhone and iPad users who need to sign and manage PDF or DOCX documents.",
            "mobile document-signing workflows",
            [f"Sign and manage PDF or DOCX documents with {name}", f"Compare {name} with other mobile e-signature apps"],
        ),
        "Online learning": (
            "Learners and teams comparing flexible online courses and career-development resources.",
            "online learning and skills development",
            [f"Evaluate {name} for self-paced skills training", f"Compare {name} with other online-learning platforms"],
        ),
        "AI product photography": (
            "E-commerce teams that need product imagery without a traditional photo shoot.",
            "AI-assisted product photography",
            [f"Create product imagery with {name}", f"Compare {name} with product-photography alternatives"],
        ),
        "Trade show technology": (
            "Exhibitors and B2B teams preparing visual assets for trade shows.",
            "trade-show preparation and visual production",
            [f"Prepare trade-show visuals with {name}", f"Compare {name} with other exhibition-production options"],
        ),
        "Collectibles & display": (
            "Collectors looking for purpose-built display frames and protective cases.",
            "collectible display and protection",
            [f"Evaluate {name} display options for a collection", f"Compare {name} with other display-frame and case options"],
        ),
        "AI productivity": (
            "Professionals comparing AI-assisted tools for everyday workflows.",
            "AI-assisted productivity workflows",
            [f"Evaluate {name} for an AI-assisted workflow", f"Compare {name} with other AI productivity tools"],
        ),
    }
    if category in profiles:
        return profiles[category]
    return (
        f"Teams and professionals evaluating {category.casefold()} for a defined business workflow.",
        f"{category.casefold()} options",
        [f"Evaluate {name} for a relevant business workflow", f"Compare {name} with other {category.casefold()} options"],
    )


def auto_offer(item: dict[str, Any], tracking_url: str, today: str) -> dict[str, Any]:
    name = str(item["name"])
    category = category_for(item)
    best_for, comparison_phrase, use_cases = positioning_for(name, category)
    summary = str(item.get("description") or f"A {category.casefold()} product available through an approved affiliate partnership.")
    if len(summary) < 35:
        summary = f"{name} is a {category.casefold()} product available through an approved affiliate partnership."
    website = https_url(item.get("website"))
    terms = https_url(item.get("terms_url"))
    evidence = []
    if website:
        evidence.append({"label": f"{name} product website", "url": website})
    if terms:
        evidence.append({"label": f"{name} partner terms", "url": terms})
    if not evidence:
        reference = https_url(item.get("application_url")) or "https://partnerstack.com/"
        evidence.append({"label": f"{name} authenticated partner record", "url": reference})
    return {
        "id": slugify(name), "slug": f"{slugify(name)}-software", "name": name,
        "status": "published", "category": category, "summary": summary[:500],
        "best_for": best_for,
        "offer_label": f"Explore {name}", "pricing_note": f"Pricing, eligibility and plan limits can change; verify current details with {name}.",
        "tracking_url": tracking_url, "cta_label": f"Explore {name}", "featured": False, "sponsored": True,
        "approved_at": today, "terms_verified_at": today, "expires_at": None,
        "why_consider": f"{name} may fit buyers actively evaluating {comparison_phrase}.",
        "watch_out": "Confirm current pricing, regional availability, plan limits and partner terms before purchasing.",
        "use_cases": use_cases,
        "evidence": evidence,
        "automation": {"source": item["source"], "network": item.get("network", "partnerstack"), "opportunity_id": item.get("id"), "policy_status": item["policy"]["status"], "discovered_by": "partner-opportunity-engine"},
    }


def refresh_auto_offers(registry: dict[str, Any], opportunities: list[dict[str, Any]]) -> bool:
    """Refresh search positioning for generated offers without touching manual copy."""
    by_name = {normalized_name(str(item.get("name") or "")): item for item in opportunities}
    changed = False
    for offer in registry.get("offers", []):
        if not isinstance(offer, dict) or offer.get("automation", {}).get("discovered_by") != "partner-opportunity-engine":
            continue
        item = by_name.get(normalized_name(str(offer.get("name") or "")))
        if not item:
            continue
        name = str(offer["name"])
        category = category_for(item)
        best_for, comparison_phrase, use_cases = positioning_for(name, category)
        replacements = {
            "category": category,
            "best_for": best_for,
            "why_consider": f"{name} may fit buyers actively evaluating {comparison_phrase}.",
            "use_cases": use_cases,
        }
        for key, value in replacements.items():
            if offer.get(key) != value:
                offer[key] = value
                changed = True
        automation = offer.setdefault("automation", {})
        for key, value in (("network", item.get("network", "partnerstack")), ("opportunity_id", item.get("id"))):
            if automation.get(key) != value:
                automation[key] = value
                changed = True
    return changed


def merge_auto_offers(root: Path, opportunities: list[dict[str, Any]], partnerships: dict[str, dict[str, Any]], api_key: str) -> list[str]:
    registry = load_json(root / "data/partner_offers.json", {"version": 1, "offers": []})
    audit_path = root / "data/partnerstack_program_audit.json"
    audit = load_json(audit_path, {"version": 1, "programs": [], "summary": {}})
    registry_changed = refresh_auto_offers(registry, opportunities)
    existing = {normalized_name(str(item.get("name") or "")) for item in registry.get("offers", []) if isinstance(item, dict)}
    added: list[str] = []
    for item in opportunities:
        key = normalized_name(str(item["name"]))
        # Records created by the original engine predate the explicit network
        # field and are PartnerStack records by definition.
        is_partnerstack = item.get("network", "partnerstack") == "partnerstack"
        partnership = partnerships.get(key) or partnerships.get(normalized_name(str(item.get("slug") or ""))) if is_partnerstack else None
        approved = (
            str((partnership or {}).get("approved_status") or (partnership or {}).get("status") or "").casefold() in {"approved", "active"}
            if is_partnerstack else bool(item.get("approved"))
        )
        if key in existing:
            if approved:
                item["relationship_state"] = "published"
            continue
        if not approved:
            continue
        if item.get("terms_required"):
            item["relationship_state"] = "terms_required"
            item["state"] = "terms_required"
            continue
        authenticated = bool(item.get("authenticated_relationship")) or not is_partnerstack
        if not authenticated and item.get("policy", {}).get("status") != "reviewed":
            continue
        links = partnerstack_links(api_key, partnership) if is_partnerstack and partnership else [https_url(item.get("tracking_url"))]
        links = [link for link in links if link]
        if not links:
            item["state"] = "approved_link_pending"
            item["relationship_state"] = "active_link_pending"
            continue
        item["tracking_url"] = links[0]
        item["relationship_state"] = "publishable"
        registry.setdefault("offers", []).append(auto_offer(item, links[0], date.today().isoformat()))
        existing.add(key)
        added.append(str(item["name"]))
        item["state"] = "active_auto_onboarded"
        item["relationship_state"] = "published"
    if added or registry_changed:
        registry["updated_at"] = date.today().isoformat()
        (root / "data/partner_offers.json").write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if added:
        known_audit = {normalized_name(str(row.get("name") or "")) for row in audit.get("programs", []) if isinstance(row, dict)}
        for item in opportunities:
            if str(item["name"]) not in added or normalized_name(str(item["name"])) in known_audit:
                continue
            audit.setdefault("programs", []).append({
                "name": item["name"], "slug": item["slug"], "category": category_for(item),
                "access": "usable", "website_status": "published", "source": f"partner-opportunity-engine:{item.get('network', 'unknown')}",
            })
        programs = [row for row in audit.get("programs", []) if isinstance(row, dict)]
        audit["audited_at"] = date.today().isoformat()
        audit["summary"] = {
            "active_programs": len(programs),
            "terms_action_required": sum(row.get("access") == "terms_required" for row in programs),
            "trackable_links_confirmed": sum(row.get("website_status") == "published" for row in programs),
            "external_account_required": sum(row.get("access") == "external_account_required" for row in programs),
            "no_usable_link": sum(row.get("website_status") == "blocked" for row in programs),
        }
        audit_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return added


def prepare_opportunities(discovered: list[dict[str, Any]], root: Path, active: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    known = known_program_names(root)
    deduped: dict[str, dict[str, Any]] = {}
    for item in discovered:
        key = normalized_name(str(item.get("name") or ""))
        if not key:
            continue
        if key in deduped:
            current = deduped[key]
            current_value = (bool(current.get("approved")), bool(current.get("tracking_url")))
            candidate_value = (bool(item.get("approved")), bool(item.get("tracking_url")))
            if candidate_value <= current_value:
                continue
        score, matches = relevance_score(item)
        item["score"] = score
        item["relevance_matches"] = matches
        slug_key = normalized_name(str(item.get("slug") or ""))
        partnership = active.get(key) or active.get(slug_key)
        partner_status = str((partnership or {}).get("approved_status") or (partnership or {}).get("status") or "").casefold()
        registered = key in known or slug_key in known
        approved = partner_status in {"approved", "active"} or bool(item.get("approved"))
        item["already_active"] = registered or approved
        if registered:
            item["relationship_state"] = "published"
        elif item.get("terms_required"):
            item["relationship_state"] = "terms_required"
        elif approved and item.get("tracking_url"):
            item["relationship_state"] = "publishable"
        elif approved:
            item["relationship_state"] = "active_link_pending"
        else:
            item["relationship_state"] = "pending"
        if registered:
            item["state"] = "existing_active"
        elif item.get("terms_required"):
            item["state"] = "terms_required"
        elif approved:
            item["state"] = "policy_review_pending"
        elif partner_status == "pending":
            item["state"] = "application_pending"
        elif partner_status == "declined":
            item["state"] = "application_declined"
        elif item.get("waitlist"):
            item["state"] = "waitlist"
        elif score >= 35:
            item["state"] = "policy_review_pending"
        else:
            item["state"] = "not_qualified"
        deduped[key] = item

    policy_targets = [item for item in deduped.values() if item["state"] == "policy_review_pending"]
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(inspect_policy, str(item.get("terms_url") or item.get("application_url") or "")): item for item in policy_targets}
        for future in as_completed(futures):
            item = futures[future]
            item["policy"] = future.result()
            if item["policy"]["status"] == "reviewed":
                item["state"] = "approved_ready_for_auto_onboarding" if item.get("approved") else "ready_for_owner_application"
            elif item.get("authenticated_relationship") and item.get("approved"):
                item["state"] = "approved_ready_for_auto_onboarding"
            else:
                item["state"] = "policy_review_required"
    for item in deduped.values():
        item.setdefault("policy", {"status": "not_reviewed", "signals": {}, "cookie_days": None})
        if item.get("network") == "partnerstack" and item.get("slug"):
            item["application_url"] = partnerstack_application_url(str(item["slug"]))
        item["application_url"] = public_reference_url(item.get("application_url"))
        item["terms_url"] = public_reference_url(item.get("terms_url"))
        item["website"] = public_reference_url(item.get("website"))
        item["source"] = public_reference_url(item.get("source"))
    return sorted(deduped.values(), key=lambda item: (-int(item["score"]), str(item["name"]).casefold()))


def public_payload(opportunities: list[dict[str, Any]], previous: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in opportunities:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    material = json.dumps(opportunities, sort_keys=True, ensure_ascii=False)
    previous_material = json.dumps(previous.get("opportunities", []), sort_keys=True, ensure_ascii=False)
    updated = str(previous.get("updated_at") or date.today().isoformat()) if material == previous_material else date.today().isoformat()
    return {
        "version": 1,
        "updated_at": updated,
        "method": "uncapped-public-marketplace-and-vendor-site-discovery",
        "legal_gate": "Applications, factual certifications and acceptance of program terms require owner action.",
        "application_profile": APPLICATION_PROFILE,
        "summary": {"total": len(opportunities), **dict(sorted(counts.items()))},
        "opportunities": opportunities,
    }


def changed_signature(payload: dict[str, Any]) -> str:
    compact = [{"id": item["id"], "state": item["state"], "score": item["score"], "policy": item["policy"]} for item in payload["opportunities"]]
    return sha256(json.dumps(compact, sort_keys=True).encode()).hexdigest()


def render_queue_page(payload: dict[str, Any]) -> str:
    cards: list[str] = []
    for item in payload["opportunities"]:
        restrictions = ", ".join(name.replace("_", " ") for name, value in item["policy"]["signals"].items() if value) or "No automated restriction signal; read the source terms."
        cards.append(
            f'''<article data-card data-state="{escape(item['state'])}" data-network="{escape(item['network'])}" data-search="{escape((item['name']+' '+item.get('description','')+' '+' '.join(item.get('tags',[]))).casefold())}" class="card"><p class="eyebrow">{escape(item['network'])} · score {item['score']}/100</p><h2>{escape(item['name'])}</h2><p>{escape(item.get('offer') or item.get('description') or 'Public offer details were not stated.')}</p><p><strong>State:</strong> {escape(item['state'].replace('_',' '))}</p><p class="policy"><strong>Policy signals:</strong> {escape(restrictions)}</p><a href="{escape(item['application_url'], quote=True)}" rel="nofollow noopener" target="_blank">Open this program in {escape(str(item.get('platform') or item['network']).replace('-', ' ').title())} →</a></article>'''
        )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Partner opportunity queue | artificial.one</title><style>body{{margin:0;background:#f8fafc;color:#0f172a;font-family:Inter,system-ui,sans-serif}}main{{max-width:1120px;margin:auto;padding:40px 20px}}h1{{font-size:clamp(2.2rem,6vw,4.5rem);line-height:1;margin:.2em 0}}.lead{{max-width:780px;color:#475569;line-height:1.6}}.controls{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px;margin:28px 0}}input,select{{padding:13px;border:1px solid #cbd5e1;border-radius:10px;background:white;font:inherit}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.card{{display:flex;flex-direction:column;border:1px solid #e2e8f0;border-radius:16px;background:white;padding:20px;box-shadow:0 5px 18px #0f172a0a}}.card h2{{margin:.25em 0}}.card p{{color:#475569;line-height:1.5}}.card a{{margin-top:auto;color:#4338ca;font-weight:800}}.eyebrow{{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:#4f46e5!important;font-weight:800}}.policy{{font-size:.85rem}}@media(max-width:800px){{.grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:560px){{.controls,.grid{{grid-template-columns:1fr}}}}</style></head><body><main><p class="eyebrow">Owner review queue · updated {escape(payload['updated_at'])}</p><h1>Affiliate opportunities</h1><p class="lead">All discovered candidates are retained—there is no weekly application quota. This page is excluded from search. Review the source program and its binding terms before applying; the automation never accepts contracts, certifies business facts or supplies tax and banking details.</p><p><strong>{payload['summary'].get('ready_for_owner_application',0)}</strong> ready for owner review · <strong>{payload['summary'].get('terms_required',0)}</strong> need terms accepted · <strong>{payload['summary'].get('approved_link_pending',0)}</strong> need a usable link · <strong>{payload['summary'].get('application_pending',0)}</strong> pending</p><section class="controls"><input id="q" type="search" placeholder="Search programs"><select id="state"><option value="">All states</option>{''.join(f'<option>{escape(value)}</option>' for value in sorted({item['state'] for item in payload['opportunities']}))}</select><select id="network"><option value="">All networks</option>{''.join(f'<option>{escape(value)}</option>' for value in sorted({item['network'] for item in payload['opportunities']}))}</select></section><p id="count"></p><section class="grid">{''.join(cards)}</section></main><script>(function(){{var q=document.getElementById('q'),s=document.getElementById('state'),n=document.getElementById('network'),cards=[].slice.call(document.querySelectorAll('[data-card]')),count=document.getElementById('count');function apply(){{var text=q.value.trim().toLowerCase(),shown=0;cards.forEach(function(card){{var visible=(!text||card.dataset.search.indexOf(text)>-1)&&(!s.value||card.dataset.state===s.value)&&(!n.value||card.dataset.network===n.value);card.hidden=!visible;if(visible)shown++;}});count.textContent=shown+' opportunities shown';}}[q,s,n].forEach(function(control){{control.addEventListener(control===q?'input':'change',apply);}});apply();}})();</script></body></html>'''


def render_email(payload: dict[str, Any], added: list[str], run_url: str) -> tuple[str, str, str]:
    actionable = [item for item in payload["opportunities"] if item["state"] in ACTIONABLE_STATES]
    lines = ["Artificial.One partner opportunity scout", "", f"Actionable opportunities: {len(actionable)}", f"Automatically onboarded: {len(added)}", "", "Applications and binding terms require owner action.", ""]
    queue_url = "https://artificial.one/partner-opportunities.html"
    lines.extend([f"Review the complete uncapped queue: {queue_url}", f"Cloud run: {run_url}"])
    subject = f"Artificial.One partner opportunities — {len(actionable)} require review"
    html = f"<!doctype html><html><body style='font-family:Arial,sans-serif;max-width:760px;margin:auto;padding:24px'><h1>Partner opportunity scout</h1><p>Every qualifying candidate is retained; no weekly quota is applied. Applications and contract acceptance remain an owner action.</p><p><strong>{len(actionable)}</strong> actionable · <strong>{len(added)}</strong> automatically onboarded</p><p><a href='{queue_url}' style='display:inline-block;background:#4f46e5;color:white;padding:12px 18px;border-radius:9px;text-decoration:none;font-weight:700'>Open the complete opportunity queue</a></p><p><a href='{escape(run_url)}'>Open cloud run</a></p></body></html>"
    return subject, "\n".join(lines), html


def send_email(api_key: str, to: str, sender: str, subject: str, text: str, html: str) -> None:
    body = json.dumps({"from": sender, "to": [to], "subject": subject, "text": text, "html": html}).encode()
    request = Request(
        RESEND_URL,
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "artificial.one-partner-scout/1.0",
        },
        method="POST",
    )
    with urlopen(request, timeout=35) as response:
        if response.status >= 300:
            raise ScoutError(f"Resend returned HTTP {response.status}")


def run(
    root: Path,
    state_path: Path,
    email_to: str = "",
    email_from: str = "",
    force_email: bool = False,
) -> dict[str, Any]:
    print("Fetching PartnerStack's public marketplace…", flush=True)
    try:
        discovered = parse_partnerstack_directory(fetch_text(MARKETPLACE_URL))
    except Exception as exc:
        previous_inventory = load_json(root / "data/partner_opportunities.json", {"opportunities": []})
        discovered = [
            item for item in previous_inventory.get("opportunities", [])
            if isinstance(item, dict) and item.get("network") == "partnerstack"
        ]
        if not discovered:
            raise ScoutError(f"PartnerStack marketplace fetch failed and no safe baseline exists: {exc}") from exc
        print(f"Marketplace refresh unavailable ({exc}); retaining {len(discovered)} known PartnerStack opportunities.", file=sys.stderr, flush=True)
    print("Scanning the verified catalog for direct-vendor programs…", flush=True)
    discovered.extend(discover_direct_programs(load_json(root / "data/tool_intelligence.json", {"tools": []})))
    print("Reading optional Awin, CJ, Sovrn and Rakuten connectors…", flush=True)
    network_items, network_status = network_connectors.discover(dict(os.environ), discovered)
    discovered.extend(network_items)
    network_connectors.write_status(root, network_status)
    api_key = os.environ.get("PARTNERSTACK_API_KEY", "").strip()
    partnerships: list[dict[str, Any]] = []
    if api_key:
        print("Reading current PartnerStack partnership states…", flush=True)
        try:
            partnerships = ps.fetch_all("partnerships", api_key, {"include_offers": "true", "include_archived": "true"})
        except Exception as exc:
            print(f"Partnership status refresh unavailable ({exc}); continuing from the published registry.", file=sys.stderr, flush=True)
    discovered = merge_authenticated_partnerstack(discovered, partnerships)
    active = partnership_names(partnerships)
    print(f"Screening {len(discovered)} discovered opportunities and their policies…", flush=True)
    opportunities = prepare_opportunities(discovered, root, active)
    added = merge_auto_offers(root, opportunities, active, api_key)
    previous = load_json(root / "data/partner_opportunities.json", {})
    payload = public_payload(opportunities, previous)
    output = root / "data/partner_opportunities.json"
    desired = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if not output.exists() or output.read_text(encoding="utf-8") != desired:
        output.write_text(desired, encoding="utf-8")
    queue_page = root / "partner-opportunities.html"
    queue_page.write_text(render_queue_page(payload), encoding="utf-8")

    state = load_json(state_path, {"version": 1})
    signature = changed_signature(payload)
    changed = signature != state.get("signature") or bool(added)
    run_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com") + "/" + os.environ.get("GITHUB_REPOSITORY", "artificial-one/artificial-one") + "/actions/runs/" + os.environ.get("GITHUB_RUN_ID", "manual")
    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    email_error = ""
    if (changed or force_email) and email_to and email_from and resend_key:
        try:
            send_email(resend_key, email_to, email_from, *render_email(payload, added, run_url))
            print(f"Meaningful-change email delivered to {email_to}.", flush=True)
        except Exception as exc:
            email_error = str(exc)
            print(f"Opportunity email delivery deferred ({exc}); discovery and publishing will continue.", file=sys.stderr, flush=True)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    saved_signature = state.get("signature") if email_error else signature
    saved_state = {"version": 1, "signature": saved_signature, "checked_at": datetime.now(timezone.utc).isoformat()}
    if email_error:
        saved_state["last_email_error"] = email_error
    state_path.write_text(json.dumps(saved_state, indent=2) + "\n", encoding="utf-8")
    output_file = os.environ.get("GITHUB_OUTPUT", "")
    if output_file:
        actionable = sum(item["state"] in ACTIONABLE_STATES for item in opportunities)
        with Path(output_file).open("a", encoding="utf-8") as handle:
            handle.write(f"changed={'true' if changed else 'false'}\nactionable={actionable}\nonboarded={len(added)}\nemail_delivered={'false' if email_error else 'true'}\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=ROOT / ".partner-scout/state.json")
    parser.add_argument("--email-to", default="")
    parser.add_argument("--email-from", default="Artificial.One Partner Scout <onboarding@resend.dev>")
    parser.add_argument("--force-email", action="store_true", help="Send the current report even when the inventory is unchanged.")
    args = parser.parse_args()
    try:
        result = run(ROOT, args.state, args.email_to, args.email_from, args.force_email)
        print(f"Partner scout evaluated {result['summary']['total']} opportunities with no application quota.")
    except (ScoutError, OSError, ValueError) as exc:
        print(f"Partner scout failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
