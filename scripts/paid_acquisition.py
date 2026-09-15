#!/usr/bin/env python3
"""Build guarded paid-search plans; never spend without explicit double opt-in."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
POLICY_PATH = ROOT / "data" / "paid_acquisition_policy.json"
PLAN_PATH = ROOT / "data" / "paid_campaign_plan.json"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def generic_keywords(offer: dict[str, Any]) -> list[str]:
    phrases = [str(offer.get("category") or ""), *[str(item) for item in offer.get("use_cases", [])]]
    brand_tokens = set(re.findall(r"[a-z0-9]+", str(offer.get("name") or "").casefold()))
    result: list[str] = []
    for phrase in phrases:
        cleaned = " ".join(token for token in re.findall(r"[a-z0-9]+", phrase.casefold()) if token not in brand_tokens)
        if len(cleaned.split()) >= 2 and cleaned not in result:
            result.append(cleaned[:80])
    return result[:6]


def build_plan() -> dict[str, Any]:
    offers = [item for item in load(OFFERS_PATH).get("offers", []) if item.get("status") == "published"]
    strategy = load(STRATEGY_PATH)
    policy = load(POLICY_PATH)
    ranking = [str(item) for item in strategy.get("ranking", [])]
    positions = {offer_id: index for index, offer_id in enumerate(ranking)}
    rules = policy.get("program_rules", {}) if isinstance(policy.get("program_rules"), dict) else {}
    campaigns = []
    for offer in sorted(offers, key=lambda item: positions.get(str(item["id"]), len(positions)))[:8]:
        offer_id = str(offer["id"])
        allowed = bool(isinstance(rules.get(offer_id), dict) and rules[offer_id].get("paid_search_allowed"))
        campaigns.append({
            "offer_id": offer_id,
            "name": f"AO Generic Intent - {offer['name']}",
            "eligible": allowed,
            "status": "ready" if allowed else "blocked_terms_unverified",
            "landing_url": f"https://artificial.one/partner-offers/{offer['slug']}.html?utm_source=google&utm_medium=cpc&utm_campaign=ao-{offer_id}",
            "keywords": generic_keywords(offer),
            "negative_keywords": [str(offer["name"])],
        })
    return {
        "version": 1,
        "live_enabled": bool(policy.get("live_enabled")),
        "max_daily_budget_cents": int(policy.get("max_daily_budget_cents") or 0),
        "max_cpc_cents": int(policy.get("max_cpc_cents") or 0),
        "stop_loss_cents": int(policy.get("stop_loss_cents") or 0),
        "minimum_clicks_before_decision": int(policy.get("minimum_clicks_before_decision") or 0),
        "conversion_action_verified": bool(policy.get("conversion_action_verified")),
        "target_country_criteria": [str(item) for item in policy.get("target_country_criteria", [])],
        "campaigns": campaigns,
        "safety": "No campaign can launch unless repository policy and PAID_ADS_LIVE both equal true and Google Ads credentials are present.",
    }


def activation_status(plan: dict[str, Any]) -> str:
    required = ("GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN", "GOOGLE_ADS_API_VERSION")
    if not plan.get("live_enabled") or (os.environ.get("PAID_ADS_LIVE") or "").casefold() != "true":
        return "paid acquisition plan refreshed; live spending is disabled"
    if any(not (os.environ.get(name) or "").strip() for name in required):
        return "paid acquisition plan refreshed; Google Ads credentials are incomplete"
    if not any(item.get("eligible") for item in plan.get("campaigns", [])):
        return "paid acquisition plan refreshed; no program has verified paid-search permission"
    if not plan.get("conversion_action_verified"):
        return "paid acquisition plan refreshed; conversion measurement is not verified"
    if not plan.get("target_country_criteria"):
        return "paid acquisition plan refreshed; no target market is authorized"
    return "ready"


def oauth_access_token() -> str:
    body = urlencode({
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    request = Request(
        "https://oauth2.googleapis.com/token", data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST",
    )
    with urlopen(request, timeout=30) as response:
        return str(json.load(response)["access_token"])


def ads_request(path: str, payload: dict[str, Any], token: str) -> dict[str, Any] | list[Any]:
    version = os.environ["GOOGLE_ADS_API_VERSION"].strip()
    customer = re.sub(r"\D", "", os.environ["GOOGLE_ADS_CUSTOMER_ID"])
    headers = {
        "Authorization": f"Bearer {token}",
        "Developer-Token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "Content-Type": "application/json",
    }
    login_customer = re.sub(r"\D", "", os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""))
    if login_customer:
        headers["login-customer-id"] = login_customer
    request = Request(
        f"https://googleads.googleapis.com/{version}/customers/{customer}/{path}",
        data=json.dumps(payload).encode(), headers=headers, method="POST",
    )
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def _resource(result: dict[str, Any] | list[Any]) -> str:
    if not isinstance(result, dict):
        raise RuntimeError("Google Ads mutate returned an unexpected result")
    values = result.get("results", [])
    if not values or not isinstance(values[0], dict) or not values[0].get("resourceName"):
        raise RuntimeError("Google Ads mutate returned no resource name")
    return str(values[0]["resourceName"])


def existing_campaign_metrics(token: str) -> list[dict[str, Any]]:
    result = ads_request(
        "googleAds:searchStream",
        {"query": "SELECT campaign.resource_name, campaign.name, campaign.status, metrics.clicks, metrics.cost_micros, metrics.conversions FROM campaign WHERE campaign.name LIKE 'AO Generic Intent - %' AND segments.date DURING LAST_7_DAYS"},
        token,
    )
    rows: list[dict[str, Any]] = []
    for batch in result if isinstance(result, list) else [result]:
        if isinstance(batch, dict):
            rows.extend(item for item in batch.get("results", []) if isinstance(item, dict))
    return rows


def pause_campaign(resource_name: str, token: str) -> None:
    ads_request(
        "campaigns:mutate",
        {"operations": [{"update": {"resourceName": resource_name, "status": "PAUSED"}, "updateMask": "status"}]},
        token,
    )


def create_campaign(campaign: dict[str, Any], plan: dict[str, Any], token: str) -> None:
    customer = re.sub(r"\D", "", os.environ["GOOGLE_ADS_CUSTOMER_ID"])
    budget = _resource(ads_request("campaignBudgets:mutate", {"operations": [{"create": {
        "name": f"{campaign['name']} Budget", "deliveryMethod": "STANDARD",
        "amountMicros": int(plan["max_daily_budget_cents"]) * 10000, "explicitlyShared": False,
    }}]}, token))
    campaign_resource = _resource(ads_request("campaigns:mutate", {"operations": [{"create": {
        "name": campaign["name"], "status": "ENABLED", "advertisingChannelType": "SEARCH",
        "campaignBudget": budget, "manualCpc": {},
        "containsEuPoliticalAdvertising": "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
        "networkSettings": {"targetGoogleSearch": True, "targetSearchNetwork": False, "targetContentNetwork": False, "targetPartnerSearchNetwork": False},
    }}]}, token))
    criteria = [
        {"create": {"campaign": campaign_resource, "location": {"geoTargetConstant": f"geoTargetConstants/{criterion}"}}}
        for criterion in plan["target_country_criteria"]
    ]
    criteria.append({"create": {"campaign": campaign_resource, "language": {"languageConstant": "languageConstants/1000"}}})
    ads_request("campaignCriteria:mutate", {"operations": criteria}, token)
    ad_group = _resource(ads_request("adGroups:mutate", {"operations": [{"create": {
        "name": f"{campaign['name']} Ad Group", "campaign": campaign_resource,
        "status": "ENABLED", "type": "SEARCH_STANDARD",
        "cpcBidMicros": int(plan["max_cpc_cents"]) * 10000,
    }}]}, token))
    keyword_ops = [
        {"create": {"adGroup": ad_group, "status": "ENABLED", "keyword": {"text": keyword, "matchType": "PHRASE"}}}
        for keyword in campaign["keywords"]
    ]
    keyword_ops.extend(
        {"create": {"adGroup": ad_group, "status": "ENABLED", "negative": True, "keyword": {"text": keyword, "matchType": "PHRASE"}}}
        for keyword in campaign["negative_keywords"]
    )
    ads_request("adGroupCriteria:mutate", {"operations": keyword_ops}, token)
    offer_name = campaign["name"].replace("AO Generic Intent - ", "")[:30]
    ads_request("adGroupAds:mutate", {"operations": [{"create": {
        "adGroup": ad_group, "status": "ENABLED", "ad": {
            "finalUrls": [campaign["landing_url"]],
            "responsiveSearchAd": {
                "headlines": [{"text": f"Compare {offer_name}"[:30]}, {"text": "Review Pricing And Fit"}, {"text": "Independent AI Tool Guide"}],
                "descriptions": [{"text": "Compare use cases, limitations and current pricing before choosing."}, {"text": "Transparent partner disclosure and a practical decision guide."}],
            },
        },
    }}]}, token)
    print(f"created guarded Search campaign {campaign['name']} in customer {customer}")


def run_live(plan: dict[str, Any]) -> str:
    status = activation_status(plan)
    if status != "ready":
        return status
    token = oauth_access_token()
    existing = existing_campaign_metrics(token)
    names = {str(item.get("campaign", {}).get("name") or "") for item in existing}
    paused = 0
    for item in existing:
        campaign = item.get("campaign", {})
        metrics = item.get("metrics", {})
        clicks = int(metrics.get("clicks") or 0)
        cost = int(metrics.get("costMicros") or 0)
        conversions = float(metrics.get("conversions") or 0)
        if clicks >= int(plan["minimum_clicks_before_decision"]) and cost >= int(plan["stop_loss_cents"]) * 10000 and conversions < 1:
            pause_campaign(str(campaign["resourceName"]), token)
            paused += 1
    created = 0
    for campaign in plan.get("campaigns", []):
        if campaign.get("eligible") and campaign["name"] not in names:
            create_campaign(campaign, plan, token)
            created += 1
            break
    return f"paid acquisition active: {created} campaign created, {paused} stopped by guardrails"


if __name__ == "__main__":
    plan = build_plan()
    PLAN_PATH.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    print(run_live(plan))
