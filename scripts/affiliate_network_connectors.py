#!/usr/bin/env python3
"""Optional read-only connectors for additional affiliate networks.

The connector layer deliberately does not create accounts, submit applications,
accept terms, or change payment settings.  Missing credentials are represented as
connection states so the daily scout continues to work before every network is
connected.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from html import unescape
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = "artificial.one-multi-network-scout/1.0 (+https://artificial.one/)"
NETWORKS: dict[str, dict[str, Any]] = {
    "awin": {
        "name": "Awin", "priority": 1,
        "signup_url": "https://ui.awin.com/publisher-signup/en/step1",
        "dashboard_url": "https://ui.awin.com/",
        "credentials": ["AWIN_PUBLISHER_ID", "AWIN_API_TOKEN"],
        "capability": "program discovery and joined-program tracking links",
    },
    "sovrn": {
        "name": "Sovrn Commerce", "priority": 2,
        "signup_url": "https://www.sovrn.com/commerce/",
        "dashboard_url": "https://commerce.sovrn.com/",
        "credentials": ["SOVRN_COMMERCE_API_KEY"],
        "capability": "monetizability checks and automatic fallback links",
    },
    "cj": {
        "name": "CJ Affiliate", "priority": 3,
        "signup_url": "https://signup.cj.com/member/signup/publisher/",
        "dashboard_url": "https://members.cj.com/",
        "credentials": ["CJ_PUBLISHER_CID", "CJ_PERSONAL_ACCESS_TOKEN"],
        "capability": "joined-advertiser discovery",
    },
    "rakuten": {
        "name": "Rakuten Advertising", "priority": 4,
        "signup_url": "https://signup.linkshare.com/publishers/registration/landing",
        "dashboard_url": "https://publisher.rakutenadvertising.com/",
        "credentials": ["RAKUTEN_ACCESS_TOKEN"],
        "capability": "advertiser and partnership discovery",
    },
}

PLATFORM_HOSTS = {
    "rewardful": ("rewardful.com", "Rewardful"),
    "firstpromoter": ("firstpromoter.com", "FirstPromoter"),
    "tolt": ("tolt.io", "Tolt"),
    "reditus": ("reditus.com", "Reditus"),
    "tapfiliate": ("tapfiliate.com", "Tapfiliate"),
    "lemonsqueezy": ("lemonsqueezy.com", "Lemon Squeezy"),
}


def _https(value: Any) -> str:
    raw = unescape(str(value or "").strip())
    if raw.startswith("www."):
        raw = "https://" + raw
    parsed = urlparse(raw)
    return raw if parsed.scheme == "https" and parsed.netloc else ""


def _clean(value: Any, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _safe_error(exc: Exception, env: dict[str, str], network: str) -> str:
    """Make provider failures useful without publishing credential values."""
    message = str(exc)
    for name in NETWORKS[network]["credentials"]:
        secret = env.get(name, "").strip()
        if secret:
            message = message.replace(secret, "[redacted]")
            message = message.replace(quote(secret, safe=""), "[redacted]")
    return _clean(message, 240)


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")[:80]


def classify_application_platform(url: str) -> tuple[str, str]:
    """Return a stable direct-program source and human label from an apply URL."""
    host = (urlparse(url).hostname or "").casefold()
    if host == "getrewardful.com" or host.endswith(".getrewardful.com"):
        return "direct-rewardful", "Rewardful"
    for key, (needle, label) in PLATFORM_HOSTS.items():
        if host == needle or host.endswith("." + needle):
            return f"direct-{key}", label
    return "direct-vendor", "Direct vendor"


def _json_request(url: str, headers: dict[str, str] | None = None) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT, **(headers or {})})
    with urlopen(request, timeout=40) as response:
        return json.load(response)


def _status(env: dict[str, str], key: str) -> dict[str, Any]:
    config = NETWORKS[key]
    missing = [name for name in config["credentials"] if not env.get(name, "").strip()]
    return {
        "network": key, "name": config["name"], "priority": config["priority"],
        "signup_url": config["signup_url"], "dashboard_url": config["dashboard_url"],
        "capability": config["capability"], "connected": not missing,
        "state": "connected" if not missing else "owner_signup_or_credentials_required",
        "missing_credentials": missing,
    }


def _awin(env: dict[str, str]) -> list[dict[str, Any]]:
    publisher = env["AWIN_PUBLISHER_ID"].strip()
    token = env["AWIN_API_TOKEN"].strip()
    url = f"https://api.awin.com/publishers/{quote(publisher)}/programmes?" + urlencode({"accessToken": token, "relationship": "joined"})
    payload = _json_request(url)
    rows = payload if isinstance(payload, list) else payload.get("programmes", [])
    result: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        advertiser = str(row.get("id") or row.get("advertiserId") or "")
        name = _clean(row.get("name") or row.get("advertiserName"), 120)
        website = _https(row.get("displayUrl") or row.get("url") or row.get("website"))
        if not advertiser or not name:
            continue
        tracking = ""
        if website:
            tracking = "https://www.awin1.com/cread.php?" + urlencode({"awinmid": advertiser, "awinaffid": publisher, "ued": website})
        result.append({
            "id": f"awin:{advertiser}", "network": "awin", "name": name,
            "slug": _slug(name), "description": _clean(row.get("description") or f"Awin advertiser programme for {name}."),
            "offer": _clean(row.get("commissionRange") or row.get("commission") or "Joined Awin advertiser programme."),
            "tags": ["Software"], "application_url": NETWORKS["awin"]["dashboard_url"],
            "terms_url": "https://www.awin.com/gb/publisher-terms", "website": website,
            "source": "https://developer.awin.com/apidocs/for-publishers", "approved": True,
            "tracking_url": tracking, "links_enabled": bool(tracking), "revenue_share": True,
            "sub_id_enabled": True, "materials": True, "waitlist": False, "archived": False,
        })
    return result


def _cj(env: dict[str, str]) -> list[dict[str, Any]]:
    cid = env["CJ_PUBLISHER_CID"].strip()
    token = env["CJ_PERSONAL_ACCESS_TOKEN"].strip()
    query = urlencode({"requestor-cid": cid, "advertiser-ids": "joined", "records-per-page": "100", "page-number": "1"})
    request = Request(
        "https://advertiser-lookup.api.cj.com/v3/advertiser-lookup?" + query,
        headers={"Accept": "application/xml", "Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
    )
    with urlopen(request, timeout=40) as response:
        root = ElementTree.fromstring(response.read())
    result: list[dict[str, Any]] = []
    for node in (item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "advertiser"):
        values = {child.tag.rsplit("}", 1)[-1]: _clean(child.text) for child in node}
        advertiser = values.get("advertiser-id", "")
        name = values.get("advertiser-name", "")
        website = _https(values.get("program-url") or values.get("website-url"))
        if advertiser and name:
            result.append({
                "id": f"cj:{advertiser}", "network": "cj", "name": name, "slug": _slug(name),
                "description": _clean(values.get("program-description") or f"Joined CJ advertiser programme for {name}."),
                "offer": _clean(values.get("seven-day-epc") or "Joined CJ advertiser programme."),
                "tags": ["Software"], "application_url": NETWORKS["cj"]["dashboard_url"],
                "terms_url": "https://www.cj.com/legal", "website": website,
                "source": "https://developers.cj.com/", "approved": True, "tracking_url": "",
                "links_enabled": False, "revenue_share": True, "sub_id_enabled": True,
                "materials": True, "waitlist": False, "archived": False,
            })
    return result


def _rakuten_pages(path: str, token: str) -> list[dict[str, Any]]:
    page = 1
    result: list[dict[str, Any]] = []
    while page <= 100:
        separator = "&" if "?" in path else "?"
        payload = _json_request(
            f"https://api.linksynergy.com{path}{separator}{urlencode({'page': page, 'limit': 100})}",
            {"Authorization": f"Bearer {token}"},
        )
        collection = payload.get("advertisers") or payload.get("partnerships") or []
        if not isinstance(collection, list) or not collection:
            break
        result.extend(item for item in collection if isinstance(item, dict))
        metadata = payload.get("_metadata", {}) if isinstance(payload, dict) else {}
        total = int(metadata.get("total") or len(result))
        if len(result) >= total:
            break
        page += 1
    return result


def _rakuten(env: dict[str, str]) -> list[dict[str, Any]]:
    token = env["RAKUTEN_ACCESS_TOKEN"].strip()
    advertisers = _rakuten_pages("/v2/advertisers", token)
    partnerships = _rakuten_pages("/v1/partnerships", token)
    joined: set[str] = set()
    for row in partnerships:
        advertiser = row.get("advertiser") if isinstance(row.get("advertiser"), dict) else {}
        if str(row.get("status") or "").casefold() in {"active", "approved", "joined"}:
            joined.add(str(advertiser.get("id") or ""))
    result: list[dict[str, Any]] = []
    for row in advertisers:
        advertiser = str(row.get("id") or "")
        name = _clean(row.get("name"), 120)
        if not advertiser or not name:
            continue
        features = row.get("features") if isinstance(row.get("features"), dict) else {}
        result.append({
            "id": f"rakuten:{advertiser}", "network": "rakuten", "name": name,
            "slug": _slug(name), "description": f"Rakuten advertiser programme for {name}.",
            "offer": "Active partnership." if advertiser in joined else "Available Rakuten advertiser programme.",
            "tags": ["Technology"], "application_url": NETWORKS["rakuten"]["dashboard_url"],
            "terms_url": "https://rakutenadvertising.com/legal-notices/affiliate-network-policies/",
            "website": _https(row.get("url")), "source": "https://developers.rakutenadvertising.com/guides/advertisers",
            "approved": advertiser in joined, "tracking_url": "", "links_enabled": bool(features.get("deep_links")),
            "revenue_share": True, "sub_id_enabled": True, "materials": bool(features.get("product_feed")),
            "waitlist": False, "archived": False,
        })
    return result


def _sovrn_check(api_key: str, item: dict[str, Any]) -> dict[str, Any] | None:
    website = _https(item.get("website"))
    if not website:
        return None
    url = "https://api.viglink.com/api/link/?" + urlencode({"out": website, "key": api_key, "optimize": "true", "format": "json"})
    payload = _json_request(url)
    if not bool(payload.get("affiliatable")):
        return None
    name = _clean(item.get("name"), 120)
    optimized = _https(payload.get("optimized")) or ("https://sovrn.co?" + urlencode({"key": api_key, "u": website, "cuid": f"artificial-one-{_slug(name)}"}))
    return {
        "id": f"sovrn:{_slug(name)}", "network": "sovrn", "name": name, "slug": _slug(name),
        "description": _clean(item.get("description") or f"{name} can be monetized through Sovrn Commerce."),
        "offer": "Automatically monetizable through Sovrn Commerce.", "tags": list(item.get("tags") or ["Software"]),
        "application_url": NETWORKS["sovrn"]["dashboard_url"], "terms_url": "https://www.sovrn.com/legal/terms-of-service/",
        "website": website, "source": "https://developer.sovrn.com/reference/link", "approved": True,
        "tracking_url": optimized, "estimated_epc": payload.get("eepc"), "links_enabled": True,
        "revenue_share": True, "sub_id_enabled": True, "materials": False, "waitlist": False, "archived": False,
    }


def discover(env: dict[str, str] | None, seed_opportunities: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    env = env or dict(os.environ)
    statuses = {key: _status(env, key) for key in NETWORKS}
    discovered: list[dict[str, Any]] = []
    fetchers = {"awin": _awin, "cj": _cj, "rakuten": _rakuten}
    for key, fetcher in fetchers.items():
        if not statuses[key]["connected"]:
            statuses[key]["records"] = 0
            continue
        try:
            rows = fetcher(env)
            discovered.extend(rows)
            statuses[key]["records"] = len(rows)
        except Exception as exc:
            statuses[key]["state"] = "connected_refresh_failed"
            statuses[key]["error"] = _safe_error(exc, env, key)
            statuses[key]["records"] = 0
    if statuses["sovrn"]["connected"]:
        key = env["SOVRN_COMMERCE_API_KEY"].strip()
        candidates = [item for item in seed_opportunities if item.get("website")][:500]
        with ThreadPoolExecutor(max_workers=12) as executor:
            futures = [executor.submit(_sovrn_check, key, item) for item in candidates]
            for future in as_completed(futures):
                try:
                    item = future.result()
                except Exception:
                    item = None
                if item:
                    discovered.append(item)
        statuses["sovrn"]["records"] = sum(item.get("network") == "sovrn" for item in discovered)
    else:
        statuses["sovrn"]["records"] = 0
    status_payload = {
        "version": 1, "updated_at": date.today().isoformat(),
        "legal_gate": "Account creation, applications and acceptance of binding terms require owner action.",
        "networks": sorted(statuses.values(), key=lambda item: item["priority"]),
    }
    return discovered, status_payload


def write_status(root: Path, payload: dict[str, Any]) -> None:
    path = root / "data" / "affiliate_network_status.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
