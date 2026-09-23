#!/usr/bin/env python3
"""Select privacy-safe affiliate CTA variants from anonymous aggregate events."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

try:
    from scripts.partnerstack_cloud_monitor import PartnerStackError, fetch_affiliate_events
except ModuleNotFoundError:
    from partnerstack_cloud_monitor import PartnerStackError, fetch_affiliate_events  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "conversion_strategy.json"
MIN_IMPRESSIONS_PER_VARIANT = 100
MIN_RELATIVE_UPLIFT = 0.12
WINDOW_DAYS = 28
VARIANTS = {
    "a": {"message": "Considering this tool? Check the current partner offer.", "cta": "View partner offer"},
    "b": {"message": "See current pricing, limits and partner terms before deciding.", "cta": "Check current offer"},
}
CARD_VARIANTS = {
    "a": {"cta": "See {name} plans"},
    "b": {"cta": "Try {name} on your workflow"},
}


def variant_totals(aggregate: dict[str, Any]) -> dict[str, int]:
    totals = {"a": 0, "b": 0}
    for placement, value in aggregate.get("by_placement", {}).items():
        for variant in totals:
            if str(placement).endswith(f"-cro-{variant}"):
                totals[variant] += int(value or 0)
    return totals


def statistically_preferred(clicks: dict[str, int], impressions: dict[str, int]) -> str | None:
    if any(impressions[key] < MIN_IMPRESSIONS_PER_VARIANT for key in VARIANTS):
        return None
    rates = {key: clicks[key] / max(1, impressions[key]) for key in VARIANTS}
    better = max(rates, key=rates.get)
    worse = "b" if better == "a" else "a"
    if rates[better] < rates[worse] * (1 + MIN_RELATIVE_UPLIFT):
        return None
    pooled = (clicks["a"] + clicks["b"]) / max(1, impressions["a"] + impressions["b"])
    standard_error = math.sqrt(max(1e-12, pooled * (1 - pooled) * (1 / impressions["a"] + 1 / impressions["b"])))
    z_score = (rates[better] - rates[worse]) / standard_error
    return better if z_score >= 1.64 else None


def build_strategy(winner: str | None) -> dict[str, Any]:
    return {
        "version": 1,
        "sticky": {"mode": "winner" if winner else "experiment", "winner": winner, "variants": VARIANTS},
        "cards": {"mode": "winner" if winner else "experiment", "winner": winner, "variants": CARD_VARIANTS},
        "privacy": "Only the selected conversion variant is public; raw interaction totals remain private.",
    }


def optimize(output: Path = OUTPUT) -> bool:
    redis_url = (os.environ.get("UPSTASH_REDIS_REST_URL") or "").strip()
    redis_token = (os.environ.get("UPSTASH_REDIS_REST_TOKEN") or "").strip()
    current: dict[str, Any] = {}
    try:
        current = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    winner = current.get("sticky", {}).get("winner") if isinstance(current.get("sticky"), dict) else None
    if redis_url and redis_token:
        try:
            clicks = variant_totals(fetch_affiliate_events(redis_url, redis_token, "clicks", WINDOW_DAYS))
            impressions = variant_totals(fetch_affiliate_events(redis_url, redis_token, "impressions", WINDOW_DAYS))
            winner = statistically_preferred(clicks, impressions)
        except PartnerStackError as exc:
            print(f"warning: conversion experiment data unavailable: {exc}")
    desired = json.dumps(build_strategy(winner if winner in VARIANTS else None), indent=2) + "\n"
    previous = output.read_text(encoding="utf-8") if output.exists() else ""
    if desired == previous:
        return False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(desired, encoding="utf-8")
    return True


if __name__ == "__main__":
    changed = optimize()
    print(f"Conversion strategy {'updated' if changed else 'unchanged'}; raw events were not persisted.")
