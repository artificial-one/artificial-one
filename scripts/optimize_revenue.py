#!/usr/bin/env python3
"""Rank published affiliate offers using privacy-safe conversion signals.

The optimizer runs unattended in GitHub Actions. Raw PartnerStack and Upstash
responses live only in memory; the repository receives only an ordered list of
offer IDs, never customer identities or private account totals.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
from typing import Any

try:
    from scripts.partnerstack_cloud_monitor import (
        PartnerStackError,
        fetch_affiliate_events,
        fetch_all,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/optimize_revenue.py
    from partnerstack_cloud_monitor import (  # type: ignore
        PartnerStackError,
        fetch_affiliate_events,
        fetch_all,
    )


ROOT = Path(__file__).resolve().parents[1]
OFFERS_PATH = ROOT / "data" / "partner_offers.json"
STRATEGY_PATH = ROOT / "data" / "revenue_strategy.json"
WINDOW_DAYS = 28
MONEY_CLUSTER_COUNT = 8


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def published_offers(path: Path = OFFERS_PATH) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        item for item in data.get("offers", [])
        if isinstance(item, dict) and item.get("status") == "published"
    ]


def _company_name(item: dict[str, Any]) -> str:
    company = item.get("company")
    if isinstance(company, dict):
        return str(company.get("name") or company.get("company_name") or "")
    return str(item.get("company_name") or item.get("name") or "")


def _partnership_key(item: dict[str, Any]) -> str:
    partnership = item.get("partnership")
    if isinstance(partnership, dict):
        return str(partnership.get("key") or partnership.get("partnership_key") or "")
    return str(item.get("partnership_key") or item.get("key") or item.get("partner_key") or "")


def _customer_partnership_key(item: dict[str, Any]) -> str:
    partnership = item.get("partnership")
    if isinstance(partnership, dict):
        return str(partnership.get("key") or partnership.get("partnership_key") or "")
    partner = item.get("partner")
    if isinstance(partner, dict):
        nested = partner.get("key") or partner.get("partner_key")
        if nested:
            return str(nested)
    return str(item.get("partnership_key") or item.get("partner_key") or "")


def _customer_key(item: dict[str, Any]) -> str:
    customer = item.get("customer")
    if isinstance(customer, dict):
        return str(customer.get("key") or customer.get("customer_key") or "")
    return str(item.get("customer_key") or item.get("customer") or "")


def offer_program_map(
    offers: list[dict[str, Any]], partnerships: list[dict[str, Any]]
) -> dict[str, str]:
    by_name = {_slug(offer.get("name")): str(offer["id"]) for offer in offers}
    result: dict[str, str] = {}
    for partnership in partnerships:
        name = _slug(_company_name(partnership))
        keys = {
            str(partnership.get(field) or "")
            for field in ("key", "partnership_key", "partner_key")
        }
        keys.discard("")
        offer_id = by_name.get(name)
        if not offer_id:
            # Common dashboard labels add or remove a trailing "AI".
            for offer_name, candidate in by_name.items():
                if name.removesuffix("ai") == offer_name.removesuffix("ai"):
                    offer_id = candidate
                    break
        if offer_id:
            for key in keys:
                result[key] = offer_id
    return result


def partner_signals(
    offers: list[dict[str, Any]], api_key: str
) -> tuple[Counter[str], Counter[str], Counter[str], Counter[str], dict[str, float]]:
    min_created = str(
        int((datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)).timestamp() * 1000)
    )
    partnerships = fetch_all(
        "partnerships", api_key, {"include_offers": "true", "include_archived": "true"}
    )
    customers = fetch_all("customers", api_key, {"min_created": min_created})
    transactions = fetch_all("transactions", api_key, {"min_created": min_created})
    rewards = fetch_all("rewards", api_key, {"min_created": min_created})
    partnership_to_offer = offer_program_map(offers, partnerships)
    economics = partner_economics_map(offers, partnerships)
    customer_to_offer: dict[str, str] = {}
    signups: Counter[str] = Counter()
    paid: Counter[str] = Counter()
    revenue_cents: Counter[str] = Counter()
    commission_cents: Counter[str] = Counter()
    for customer in customers:
        offer_id = partnership_to_offer.get(_customer_partnership_key(customer), "")
        customer_key = str(customer.get("key") or "")
        if offer_id:
            signups[offer_id] += 1
            paid[offer_id] += int(bool(customer.get("has_paid")))
            if customer_key:
                customer_to_offer[customer_key] = offer_id
    for transaction in transactions:
        offer_id = customer_to_offer.get(_customer_key(transaction), "")
        if offer_id:
            revenue_cents[offer_id] += int(transaction.get("amount_usd") or 0)
    for reward in rewards:
        offer_id = customer_to_offer.get(_customer_key(reward), "")
        if offer_id:
            commission_cents[offer_id] += int(reward.get("amount") or 0)
    return signups, paid, revenue_cents, commission_cents, economics


def _economic_scalars(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    result: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            result.extend(_economic_scalars(item, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for item in value:
            result.extend(_economic_scalars(item, prefix))
    else:
        result.append((prefix.casefold(), value))
    return result


def economic_prior(partnership: dict[str, Any]) -> float:
    """Extract a conservative cold-start prior from private program metadata."""
    score = 0.0
    for key, value in _economic_scalars(partnership):
        text = str(value or "").casefold()
        number_match = re.search(r"\d+(?:\.\d+)?", text)
        number = float(number_match.group()) if number_match else 0.0
        if any(term in key for term in ("commission", "reward", "payout")):
            score += min(2.0, math.log1p(number) / 2.5) if number else 0.15
        elif "cookie" in key:
            score += min(0.75, number / 120.0) if number else 0.1
        elif "trial" in key and text not in {"", "false", "none", "0"}:
            score += 0.35
        elif any(term in key for term in ("deep_link", "deeplink", "landing_page")) and text:
            score += 0.2
        elif any(term in key for term in ("conversion", "qualif")) and text:
            score += 0.1
    return min(score, 3.0)


def partner_economics_map(
    offers: list[dict[str, Any]], partnerships: list[dict[str, Any]]
) -> dict[str, float]:
    partnership_to_offer = offer_program_map(offers, partnerships)
    result: dict[str, float] = {}
    for partnership in partnerships:
        keys = [str(partnership.get(field) or "") for field in ("key", "partnership_key", "partner_key")]
        offer_id = next((partnership_to_offer[key] for key in keys if key in partnership_to_offer), "")
        if offer_id:
            result[offer_id] = max(result.get(offer_id, 0.0), economic_prior(partnership))
    return result


def rank_offers(
    offers: list[dict[str, Any]],
    clicks: dict[str, Any] | None = None,
    impressions: dict[str, Any] | None = None,
    signups: Counter[str] | None = None,
    paid: Counter[str] | None = None,
    revenue_cents: Counter[str] | None = None,
    commission_cents: Counter[str] | None = None,
    commercial_priors: dict[str, float] | None = None,
) -> list[str]:
    clicks_by_offer = (clicks or {}).get("by_offer", {})
    impressions_by_offer = (impressions or {}).get("by_offer", {})
    signups = signups or Counter()
    paid = paid or Counter()
    revenue_cents = revenue_cents or Counter()
    commission_cents = commission_cents or Counter()
    commercial_priors = commercial_priors or {}

    def score(offer: dict[str, Any]) -> tuple[float, str]:
        offer_id = str(offer["id"])
        click_count = int(clicks_by_offer.get(offer_id, 0))
        impression_count = int(impressions_by_offer.get(offer_id, 0))
        # Bayesian smoothing prevents a single accidental click from dominating.
        ctr = (click_count + 1.0) / (impression_count + 12.0)
        exploration = 1.0 / math.sqrt(impression_count + 1.0)
        # Expected earnings per visitor/click prevents a high-volume but
        # worthless offer from outranking an offer that actually pays. Small
        # priors keep zero-data programs eligible for exploration.
        commission_per_visitor = (commission_cents[offer_id] + 25.0) / (impression_count + 100.0)
        commission_per_click = (commission_cents[offer_id] + 25.0) / (click_count + 12.0)
        value = (
            (1.25 if offer.get("featured") else 0.0)
            + math.log1p(click_count) * 1.5
            + ctr * 12.0
            + exploration
            + signups[offer_id] * 8.0
            + paid[offer_id] * 24.0
            + math.log1p(revenue_cents[offer_id] / 100.0) * 4.0
            + math.log1p(commission_cents[offer_id] / 100.0) * 6.0
            + math.log1p(commission_per_visitor) * 8.0
            + math.log1p(commission_per_click) * 2.0
            + float(commercial_priors.get(offer_id, 0.0))
        )
        return (-value, str(offer.get("name", offer_id)).casefold())

    return [str(offer["id"]) for offer in sorted(offers, key=score)]


def build_strategy(ranking: list[str]) -> dict[str, Any]:
    return {
        "version": 1,
        "method": "privacy-safe-expected-earnings-ranking",
        "window_days": WINDOW_DAYS,
        "ranking": ranking,
        "featured": ranking[:MONEY_CLUSTER_COUNT],
        "money_clusters": ranking[:MONEY_CLUSTER_COUNT],
        "growth_targets": {
            "window_days": 28,
            "qualified_visits": 1250,
            "affiliate_click_goal": 100,
            "affiliate_ctr_percent": 8,
            "internal_route_ctr_percent": 15,
        },
        "privacy": "Only offer ordering is published; raw traffic and customer data remain private.",
    }


def optimize(output: Path = STRATEGY_PATH) -> bool:
    offers = published_offers()
    clicks: dict[str, Any] = {}
    impressions: dict[str, Any] = {}
    signups: Counter[str] = Counter()
    paid: Counter[str] = Counter()
    revenue_cents: Counter[str] = Counter()
    commission_cents: Counter[str] = Counter()
    commercial_priors: dict[str, float] = {}

    redis_url = (os.environ.get("UPSTASH_REDIS_REST_URL") or "").strip()
    redis_token = (os.environ.get("UPSTASH_REDIS_REST_TOKEN") or "").strip()
    if redis_url and redis_token:
        try:
            clicks = fetch_affiliate_events(redis_url, redis_token, "clicks", WINDOW_DAYS)
            impressions = fetch_affiliate_events(redis_url, redis_token, "impressions", WINDOW_DAYS)
        except PartnerStackError as exc:
            print(f"warning: website performance data unavailable: {exc}")

    partner_key = (os.environ.get("PARTNERSTACK_API_KEY") or "").strip()
    if partner_key:
        try:
            signups, paid, revenue_cents, commission_cents, commercial_priors = partner_signals(offers, partner_key)
        except PartnerStackError as exc:
            print(f"warning: PartnerStack conversion data unavailable: {exc}")

    strategy = build_strategy(
        rank_offers(
            offers,
            clicks,
            impressions,
            signups,
            paid,
            revenue_cents,
            commission_cents,
            commercial_priors,
        )
    )
    desired = json.dumps(strategy, indent=2) + "\n"
    current = output.read_text(encoding="utf-8") if output.exists() else ""
    if desired == current:
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(desired, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    before = STRATEGY_PATH.read_text(encoding="utf-8") if STRATEGY_PATH.exists() else ""
    changed = optimize()
    if args.check and changed:
        STRATEGY_PATH.write_text(before, encoding="utf-8")
        print("Revenue strategy is stale")
        return 1
    print(f"Revenue strategy {'updated' if changed else 'unchanged'}; no private metrics were persisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
