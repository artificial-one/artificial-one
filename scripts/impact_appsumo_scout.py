#!/usr/bin/env python3
"""Import every usable AppSumo asset from the active Impact partnership.

Impact treats AppSumo as one joined program. Individual AppSumo products are
ads/assets, so this scout lists the complete campaign inventory, creates a
regular product tracking link when Impact has not supplied one, and builds
conservative source-based guides for AI-relevant products. It never changes a
contract, accepts terms, or touches withdrawal settings.
"""

from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import re
import sys
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

try:
    from scripts import affiliate_network_monitor as impact
    from scripts import appsumo_impact as appsumo
except ImportError:
    import affiliate_network_monitor as impact  # type: ignore
    import appsumo_impact as appsumo  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ID = "7443"
OUTPUT = ROOT / "data" / "appsumo_impact_ads.json"
GUIDE_DIR = ROOT / "appsumo-guides"
TRACKING_ENDPOINT = "https://api.impact.com/Mediapartners/{sid}/Programs/{program}/TrackingLinks"
PRODUCT_PATH = re.compile(r"^/products/([^/]+)/?", re.I)


def clean(value: Any, limit: int = 600) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(value or ""))).strip()[:limit]


def https_url(value: Any) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    return raw if parsed.scheme == "https" and parsed.netloc else ""


def product_slug(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    if host != "appsumo.com" and not host.endswith(".appsumo.com"):
        return ""
    match = PRODUCT_PATH.match(parsed.path)
    return appsumo.slugify(match.group(1)) if match else ""


def display_name(ad: dict[str, Any], slug: str) -> str:
    name = clean(ad.get("Name"), 140)
    name = re.sub(r"\s+(?:text link|banner|coupon|deal)$", "", name, flags=re.I).strip(" -|")
    return name if name and name.casefold() not in {"appsumo", "default link"} else slug.replace("-", " ").title()


def relevant(name: str, slug: str, description: str) -> bool:
    words = set(appsumo.slugify(f"{name} {slug} {description}").split("-"))
    return bool(words & appsumo.AI_TERMS)


def create_tracking_link(sid: str, token: str, ad_id: str, landing: str) -> str:
    query = urlencode({"Type": "Regular", "AdId": ad_id, "DeepLink": landing})
    url = TRACKING_ENDPOINT.format(sid=sid, program=CAMPAIGN_ID) + "?" + query
    credential = base64.b64encode(f"{sid}:{token}".encode()).decode()
    request = Request(url, data=b"", headers={
        "Accept": "application/json",
        "Authorization": f"Basic {credential}",
        "User-Agent": "artificial.one-appsumo-scout/1.0",
    }, method="POST")
    with urlopen(request, timeout=40) as response:
        payload = json.load(response)
    return https_url(payload.get("TrackingURL") or payload.get("TrackingUrl"))


def policy_summary(contracts: list[dict[str, Any]]) -> dict[str, Any]:
    contract = next((item for item in contracts if str(item.get("CampaignId") or item.get("ProgramId") or "") == CAMPAIGN_ID), {})
    terms = contract.get("Terms") if isinstance(contract.get("Terms"), dict) else {}
    special = " ".join(clean(item.get("TermsContent"), 4000) for item in terms.get("SpecialTermsList", []) if isinstance(item, dict)).casefold()
    return {
        "contract_status": clean(contract.get("Status") or contract.get("ContractStatus") or "unknown", 40),
        "paid_brand_campaigns": "prohibited",
        "coupon_restriction_detected": bool(re.search(r"(?:no|prohibit|may not|must not).{0,80}coupon", special)),
        "email_restriction_detected": bool(re.search(r"(?:no|prohibit|may not|must not).{0,80}(?:email|newsletter)", special)),
        "incentive_restriction_detected": bool(re.search(r"(?:no|prohibit|may not|must not).{0,80}(?:incentiv|cashback|rebate)", special)),
    }


def normalize_ads(ads: list[dict[str, Any]], sid: str, token: str) -> tuple[list[dict[str, Any]], int]:
    candidates: dict[str, list[dict[str, Any]]] = {}
    for ad in ads:
        landing = https_url(ad.get("LandingPageUrl"))
        slug = product_slug(landing)
        if not slug:
            continue
        candidates.setdefault(slug, []).append(ad)

    offers: list[dict[str, Any]] = []
    created = 0
    for slug, group in candidates.items():
        def rank(ad: dict[str, Any]) -> tuple[int, int, int, int]:
            state = str(ad.get("DealState") or "").upper()
            return (
                1 if state == "ACTIVE" else 0,
                1 if https_url(ad.get("TrackingLink")) else 0,
                1 if str(ad.get("Type") or "").upper() == "TEXT_LINK" else 0,
                len(clean(ad.get("Description"), 2000)),
            )
        ad = max(group, key=rank)
        landing = https_url(ad.get("LandingPageUrl"))
        name = display_name(ad, slug)
        description = clean(ad.get("Description") or ad.get("DealDescription"), 700)
        tracking = https_url(ad.get("TrackingLink"))
        ad_id = str(ad.get("Id") or "")
        if not tracking and ad_id:
            try:
                tracking = create_tracking_link(sid, token, ad_id, landing)
                created += bool(tracking)
            except Exception as exc:
                print(f"Could not create tracking link for {name}: {exc}", file=sys.stderr)
        state = str(ad.get("DealState") or "ACTIVE").upper()
        ai_relevant = relevant(name, slug, description)
        offers.append({
            "id": f"impact-ad-{ad.get('Id') or slug}",
            "impact_ad_id": ad_id,
            "name": name,
            "slug": slug,
            "description": description or f"AppSumo product asset for {name}.",
            "category": appsumo.infer_category(name + " " + description),
            "tracking_url": tracking,
            "product_url": landing,
            "creative_url": https_url(ad.get("CreativeUrl")),
            "allow_deep_linking": bool(ad.get("AllowDeepLinking")),
            "ai_relevant": ai_relevant,
            "availability": "expired" if state == "EXPIRED" else "active",
            "deal_state": state,
            "source_status": "impact-api",
            "editorial_url": f"appsumo-guides/{slug}.html" if ai_relevant and tracking else "",
        })
    return sorted(offers, key=lambda item: item["name"].casefold()), created


def render_guide(offer: dict[str, Any]) -> str:
    name = str(offer["name"])
    description = str(offer["description"])
    category = str(offer["category"])
    tracking = str(offer["tracking_url"])
    canonical = f"https://artificial.one/{offer['editorial_url']}"
    structured = json.dumps({
        "@context": "https://schema.org", "@type": "SoftwareApplication", "name": name,
        "description": description, "applicationCategory": category, "url": canonical,
    }, ensure_ascii=False).replace("<", "\\u003c")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(name)} AppSumo Deal: Fit &amp; Buying Guide | artificial.one</title><meta name="description" content="Independent source-based overview of {escape(name)} on AppSumo, including likely fit, buying checks and the current tracked offer."><link rel="canonical" href="{escape(canonical, quote=True)}"><meta name="affiliate-event-endpoint" content="/api/affiliate-event"><script type="application/ld+json">{structured}</script><style>body{{margin:0;background:#f8fafc;color:#0f172a;font-family:Inter,system-ui,sans-serif}}header,main,footer{{max-width:920px;margin:auto;padding:24px}}nav{{display:flex;justify-content:space-between}}a{{color:#4338ca}}.hero{{padding:72px 0 36px}}h1{{font-size:clamp(2.5rem,7vw,4.8rem);line-height:1;margin:.25em 0}}.lead{{font-size:1.15rem;line-height:1.7;color:#475569}}.panel{{background:white;border:1px solid #e2e8f0;border-radius:18px;padding:26px;margin:22px 0}}li{{margin:.8em 0;line-height:1.55}}.cta{{display:inline-block;background:#4338ca;color:white;text-decoration:none;font-weight:800;padding:14px 20px;border-radius:10px}}.note{{font-size:.9rem;color:#64748b}}footer{{border-top:1px solid #e2e8f0;color:#64748b}}</style></head><body><header><nav><a href="../index.html"><strong>artificial.one</strong></a><a href="../appsumo-ai-tools.html">AppSumo AI deals</a></nav></header><main><section class="hero"><p><strong>{escape(category)}</strong> · Automatically monitored</p><h1>{escape(name)} on AppSumo</h1><p class="lead">{escape(description)}</p><p class="note">Source-based overview—not a claim of hands-on testing. Verify the current price, limits, support and refund terms on AppSumo.</p></section><section class="panel"><h2>Who should consider it?</h2><p>Buyers actively evaluating {escape(category.casefold())} who have a defined workflow and can validate the product against real inputs during AppSumo’s current evaluation period.</p></section><section class="panel"><h2>Check before buying</h2><ul><li>Confirm that the current plan includes the features and usage volume you need.</li><li>Review integrations, data-export options and any AI usage or credit limits.</li><li>Check the current AppSumo price, license tiers, refund terms and product roadmap.</li><li>Compare the lifetime cost with an established subscription alternative.</li></ul><a class="cta" href="{escape(tracking, quote=True)}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-affiliate-network="impact" data-offer-id="{escape(str(offer['id']), quote=True)}" data-placement="appsumo-auto-guide">Check the current {escape(name)} offer →</a><p class="note">Affiliate disclosure: artificial.one may earn a commission if you purchase through this link, at no additional cost to you.</p></section></main><footer><p>Availability is checked automatically. AppSumo remains the source of truth for pricing and terms.</p></footer><script src="../assets/affiliate-tracking.js" defer></script></body></html>'''


def write_guides(offers: list[dict[str, Any]], root: Path = ROOT) -> int:
    count = 0
    for offer in offers:
        relative = str(offer.get("editorial_url") or "")
        if not relative:
            continue
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        desired = render_guide(offer)
        if not path.exists() or path.read_text(encoding="utf-8") != desired:
            path.write_text(desired, encoding="utf-8")
            count += 1
    return count


def write_outputs(**values: Any) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    with Path(output).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")


def run(root: Path = ROOT) -> dict[str, Any]:
    sid = os.environ.get("IMPACT_ACCOUNT_SID", "").strip()
    token = os.environ.get("IMPACT_AUTH_TOKEN", "").strip()
    if not sid or not token:
        raise RuntimeError("IMPACT_ACCOUNT_SID and IMPACT_AUTH_TOKEN are required")
    print("Reading every AppSumo asset exposed by the active Impact partnership…", flush=True)
    try:
        ads = impact.impact_collection(sid, token, "Ads", "Ads", {"CampaignId": CAMPAIGN_ID})
    except RuntimeError as exc:
        if "403" not in str(exc):
            raise
        # Keep the mature workbook-backed catalog and the rest of the daily
        # revenue monitor running while a scoped token awaits Ads read access.
        print("Impact token lacks Ads read scope; preserving the existing AppSumo catalog.", file=sys.stderr)
        write_outputs(products=0, new_items=0, links_created=0, guides_written=0, permission_required=True)
        return {"permission_required": True, "reason": "impact_ads_scope"}
    try:
        contracts = impact.impact_collection(sid, token, "Contracts", "Contracts")
    except RuntimeError as exc:
        print(f"Impact contract summary unavailable; continuing without contract text: {exc}", file=sys.stderr)
        contracts = []
    offers, created = normalize_ads(ads, sid, token)
    previous = appsumo.load_json(root / "data/appsumo_impact_ads.json")
    payload = {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "network": "Impact / AppSumo",
        "campaign_id": CAMPAIGN_ID,
        "policy": policy_summary(contracts),
        "summary": {
            "ads_received": len(ads), "products": len(offers),
            "trackable": sum(bool(item["tracking_url"]) for item in offers),
            "ai_relevant": sum(bool(item["ai_relevant"]) for item in offers),
            "active": sum(item["availability"] == "active" for item in offers),
            "tracking_links_created": created,
        },
        "offers": offers,
    }
    path = root / "data/appsumo_impact_ads.json"
    desired = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != desired:
        path.write_text(desired, encoding="utf-8")
    guides = write_guides(offers, root)
    previous_ids = {str(item.get("id")) for item in previous.get("offers", []) if isinstance(item, dict)}
    new_items = sum(str(item.get("id")) not in previous_ids for item in offers)
    write_outputs(products=len(offers), new_items=new_items, links_created=created, guides_written=guides, permission_required=False)
    print(f"AppSumo scout retained {len(offers)} products without a quota; {created} missing tracking links created; {guides} guides written.")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        run()
    except Exception as exc:
        print(f"AppSumo Impact scout failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
