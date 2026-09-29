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
            "verified_at": date.today().isoformat(),
            "editorial_url": f"appsumo-guides/{slug}.html" if ai_relevant and tracking else "",
        })
    return sorted(offers, key=lambda item: item["name"].casefold()), created


def buying_playbook(category: str) -> dict[str, Any]:
    """Return category-specific decision questions without inventing product claims."""
    normalized = category.casefold()
    playbooks = (
        (("video",), "creators turning source material into publishable video", "one real source file, the intended output format and your normal editing deadline", ["rendering or export limits", "caption and brand controls", "commercial-use rights for generated media"]),
        (("audio", "voice"), "creators producing speech, podcasts or other audio assets", "a representative recording with the accents, noise and output format you actually use", ["minute or credit allowances", "voice and commercial-use permissions", "export quality and editing control"]),
        (("writing", "content"), "teams producing repeatable written content", "a brief from your real workflow, including tone, references and a difficult revision request", ["word or credit allowances", "fact-checking and citation support", "export, collaboration and brand-voice controls"]),
        (("seo", "growth"), "teams improving discoverability and measurable acquisition", "one existing page and one target query where you already understand the audience", ["data sources and update frequency", "limits on tracked sites or keywords", "whether recommendations can be exported and audited"]),
        (("marketing", "email", "social"), "small teams running repeatable campaigns and follow-up", "one campaign from audience selection through reporting, using non-sensitive sample contacts", ["contact, send or automation limits", "integration and data-export coverage", "consent, deliverability and attribution controls"]),
        (("development", "code"), "builders shipping or maintaining software workflows", "a disposable test project that exercises setup, export and the most important integration", ["API, execution or project limits", "code and data ownership", "deployment, rollback and vendor-lock-in options"]),
        (("productivity", "business"), "operators replacing a recurring manual business task", "one weekly process with a known owner, input, output and time cost", ["seat and workspace limits", "integration and export support", "permissions, audit history and cancellation access"]),
    )
    for needles, audience, trial, checks in playbooks:
        if any(needle in normalized for needle in needles):
            return {"audience": audience, "trial": trial, "checks": checks}
    return {
        "audience": "buyers replacing a clearly defined software workflow",
        "trial": "one realistic task with the same inputs, collaborators and output standard you expect after purchase",
        "checks": ["usage and seat limits", "integration and export support", "support, refund and cancellation terms"],
    }


def render_guide(offer: dict[str, Any]) -> str:
    name = str(offer["name"])
    description = str(offer["description"])
    category = str(offer["category"])
    tracking = str(offer["tracking_url"])
    product_url = str(offer.get("product_url") or "")
    checked = str(offer.get("verified_at") or date.today().isoformat())[:10]
    playbook = buying_playbook(category)
    canonical = f"https://artificial.one/{offer['editorial_url']}"
    structured = json.dumps({
        "@context": "https://schema.org", "@type": "SoftwareApplication", "name": name,
        "description": description, "applicationCategory": category, "url": canonical,
    }, ensure_ascii=False).replace("<", "\\u003c")
    check_items = "".join(f"<li>{escape(item.capitalize())}.</li>" for item in playbook["checks"])
    source_link = f'<a href="{escape(product_url, quote=True)}" rel="nofollow noopener">AppSumo product listing</a>' if product_url else "AppSumo product listing"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(name)} AppSumo Deal: Fit &amp; Buying Guide | artificial.one</title><meta name="description" content="Independent source-based overview of {escape(name)} on AppSumo, including likely fit, a practical trial plan, buying checks and the current tracked offer."><link rel="canonical" href="{escape(canonical, quote=True)}"><meta name="affiliate-event-endpoint" content="/api/affiliate-event"><script type="application/ld+json">{structured}</script><style>*{{box-sizing:border-box}}body{{margin:0;background:#fff;color:#111827;font-family:Inter,system-ui,sans-serif}}header{{position:sticky;top:0;z-index:10;background:#090914;color:#fff;border-bottom:1px solid #25253a}}header nav,main,footer{{max-width:1080px;margin:auto;padding:20px 24px}}nav{{display:flex;justify-content:space-between;gap:20px}}nav a{{color:#fff;text-decoration:none;font-weight:850}}nav span{{color:#9cff3b}}a{{color:#5b21b6}}.hero{{padding:66px 0 34px}}.eyebrow{{color:#6d28d9;font-size:.78rem;font-weight:900;letter-spacing:.11em;text-transform:uppercase}}h1{{font-size:clamp(2.8rem,7vw,5.7rem);line-height:.94;letter-spacing:-.055em;margin:.2em 0}}h2{{font-size:1.55rem;margin-top:0}}.lead{{max-width:850px;font-size:1.2rem;line-height:1.75;color:#475569}}.grid{{display:grid;grid-template-columns:1.1fr .9fr;gap:22px}}.panel{{background:linear-gradient(145deg,#fff,#f5f3ff);border:1px solid #ddd6fe;border-radius:24px;padding:28px;margin:0 0 22px;box-shadow:0 12px 35px #312e8112}}.panel.dark{{background:#111827;color:#fff;border-color:#312e81}}.panel.dark p,.panel.dark li{{color:#dbeafe}}p,li{{line-height:1.68}}li{{margin:.7em 0}}.cta{{display:inline-block;background:#8b5cf6;color:white;text-decoration:none;font-weight:900;padding:15px 21px;border-radius:12px}}.secondary{{display:inline-block;margin-left:12px;font-weight:800}}.note{{font-size:.9rem;color:#64748b}}.source{{border-top:1px solid #e5e7eb;margin-top:22px;padding-top:18px}}footer{{border-top:1px solid #e5e7eb;color:#64748b}}@media(max-width:760px){{.grid{{grid-template-columns:1fr}}.secondary{{display:block;margin:14px 0 0}}}}</style></head><body><header><nav><a href="../index.html">artificial<span>.</span>one</a><a href="../appsumo-ai-tools.html">Browse all checked deals</a></nav></header><main><section class="hero"><p class="eyebrow">{escape(category)} · source checked {escape(checked)}</p><h1>Is {escape(name)} worth a closer look?</h1><p class="lead">{escape(description)}</p><p class="note">This is a source-based buying guide, not a claim that we personally tested every feature. The live destination remains the source of truth for price, availability and terms.</p></section><section class="grid"><div><article class="panel"><h2>Best fit</h2><p>{escape(name)} is most relevant to {escape(str(playbook['audience']))}. It deserves consideration when its stated purpose maps to a task you already perform and when you can measure whether it saves time, improves output or replaces another recurring software cost.</p></article><article class="panel"><h2>A useful first test</h2><p>Before committing, test {escape(str(playbook['trial']))}. Record setup time, the quality of the first usable result, the manual work still required and whether another person can repeat the workflow. A lifetime offer is valuable only when the workflow survives ordinary day-to-day use.</p></article><article class="panel"><h2>Questions to answer before buying</h2><ul>{check_items}<li>Confirm the current AppSumo license tier, refund window, support route and roadmap.</li><li>Compare the total cost and switching risk with a mature subscription alternative.</li></ul></article></div><aside><article class="panel dark"><h2>Current offer</h2><p>Open the tracked destination to verify today’s price, included limits and availability. No ranking on this page is purchased.</p><a class="cta" href="{escape(tracking, quote=True)}" target="_blank" rel="nofollow sponsored noopener" data-affiliate-offer data-affiliate-network="impact" data-offer-id="{escape(str(offer['id']), quote=True)}" data-placement="appsumo-auto-guide">Check the current {escape(name)} offer →</a><p class="note">Affiliate disclosure: artificial.one may earn a commission if you purchase through this link, at no extra cost to you.</p></article><article class="panel"><h2>Decision rule</h2><p>Shortlist {escape(name)} if the product description matches your real workflow and the trial answers the checks above. Skip it if the attraction is mainly the discount, required integrations are missing, or the useful limits are unclear.</p><p><a href="../ai-tool-alternatives.html">Compare other software options →</a></p><p><a href="../ask-elephant.html">Ask the Elephant for a three-tool shortlist →</a></p><p class="source"><strong>Sources:</strong> {source_link}; Impact campaign asset. Checked {escape(checked)}.</p></article></aside></section></main><footer><p>Independent decision support for software buyers. Product names belong to their owners.</p></footer><script src="../assets/affiliate-tracking.js" defer></script></body></html>'''


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
