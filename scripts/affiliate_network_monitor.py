#!/usr/bin/env python3
"""Private aggregate dashboard for PartnerStack, Impact and site click data."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from html import escape
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

try:
    from scripts import partnerstack_cloud_monitor as ps
except ImportError:
    import partnerstack_cloud_monitor as ps  # type: ignore


IMPACT_API = "https://api.impact.com/Mediapartners"


class ImpactError(RuntimeError):
    pass


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _impact_request(account_sid: str, auth_token: str, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    import base64
    url = f"{IMPACT_API}/{account_sid}/{path.lstrip('/')}"
    if params:
        url += "?" + urlencode(params)
    credential = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()
    request = Request(url, headers={
        "Accept": "application/json",
        "Authorization": f"Basic {credential}",
        "User-Agent": "artificial.one-affiliate-monitor/1.0",
    }, method="GET")
    try:
        with urlopen(request, timeout=40) as response:
            value = json.load(response)
    except Exception as exc:
        raise ImpactError(f"Impact read failed for {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ImpactError(f"Impact returned an unexpected response for {path}")
    return value


def impact_collection(account_sid: str, auth_token: str, path: str, key: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    query = {"PageSize": "1000", **(params or {})}
    values: list[dict[str, Any]] = []
    page = 1
    while True:
        query["Page"] = str(page)
        payload = _impact_request(account_sid, auth_token, path, query)
        collection = payload.get(key, [])
        if isinstance(collection, dict):
            collection = collection.get(key[:-1], [])
        if not isinstance(collection, list):
            collection = []
        values.extend(item for item in collection if isinstance(item, dict))
        total_pages = int(payload.get("@numpages") or payload.get("@totalpages") or 1)
        if page >= total_pages or not collection:
            return values
        page += 1


def _currency_totals(items: list[dict[str, Any]], field: str, currency_field: str = "Currency") -> dict[str, str]:
    totals: dict[str, Decimal] = {}
    for item in items:
        currency = str(item.get(currency_field) or "USD")
        totals[currency] = totals.get(currency, Decimal("0")) + _decimal(item.get(field))
    return {currency: f"{amount:.2f}" for currency, amount in sorted(totals.items())}


def fetch_impact_snapshot(account_sid: str, auth_token: str) -> dict[str, Any]:
    programs = impact_collection(account_sid, auth_token, "Campaigns", "Campaigns")
    actions = impact_collection(account_sid, auth_token, "Actions", "Actions")
    invoices = impact_collection(account_sid, auth_token, "Invoices", "Invoices")
    statuses = Counter(str(item.get("State") or item.get("Status") or "unknown") for item in actions)
    invoice_statuses: Counter[str] = Counter()
    paid_dates = 0
    for invoice in invoices:
        for line in invoice.get("LineItems", []) if isinstance(invoice.get("LineItems"), list) else []:
            if not isinstance(line, dict):
                continue
            invoice_statuses[str(line.get("Status") or "unknown")] += 1
            if line.get("PaidDate"):
                paid_dates += 1
    program_states = sorted(
        ({"program": str(item.get("CampaignName") or item.get("AdvertiserName") or "Unknown"), "status": str(item.get("ContractStatus") or "unknown"), "id": str(item.get("CampaignId") or "")} for item in programs),
        key=lambda item: item["program"].casefold(),
    )
    return {
        "connected": True,
        "programs": {"count": len(programs), "states": program_states},
        "actions": {
            "count": len(actions),
            "statuses": dict(sorted(statuses.items())),
            "revenue": _currency_totals(actions, "Amount"),
            "commissions": _currency_totals(actions, "Payout"),
        },
        "invoices": {
            "count": len(invoices),
            "totals": _currency_totals(invoices, "TotalAmount"),
            "payment_statuses": dict(sorted(invoice_statuses.items())),
            "paid_line_items": paid_dates,
        },
    }


def _impact_changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    changes: list[str] = []
    for section, field, label in (("programs", "count", "Impact programs"), ("actions", "count", "Impact attributed actions"), ("invoices", "count", "Impact invoices")):
        left = int(before.get(section, {}).get(field) or 0)
        right = int(after.get(section, {}).get(field) or 0)
        if left != right:
            changes.append(f"{label}: {left} -> {right}")
    for section, field, label in (("actions", "revenue", "Impact revenue"), ("actions", "commissions", "Impact commissions"), ("actions", "statuses", "Impact action statuses"), ("invoices", "payment_statuses", "Impact payment statuses")):
        if before.get(section, {}).get(field, {}) != after.get(section, {}).get(field, {}):
            changes.append(f"{label} changed")
    return changes


def _money_map(values: dict[str, Any]) -> str:
    return ", ".join(f"{currency} {amount}" for currency, amount in sorted(values.items())) or "USD 0.00"


def _counts(values: dict[str, Any]) -> str:
    return ", ".join(f"{name}: {count}" for name, count in sorted(values.items())) or "none"


def website_coverage(path: Path = Path("data/appsumo_offers.json")) -> dict[str, int]:
    value = json.loads(path.read_text(encoding="utf-8"))
    offers = value.get("offers", [])
    return {
        "inventory": len(offers),
        "active": sum(item.get("availability") == "active" for item in offers),
        "checking": sum(item.get("availability") in {"unchecked", "checking"} for item in offers),
        "expired": sum(item.get("availability") == "expired" for item in offers),
        "promotable": sum(bool(item.get("availability") != "expired" and item.get("ai_relevant") and item.get("editorial_url")) for item in offers),
    }


def render_dashboard(
    partnerstack: dict[str, Any], impact: dict[str, Any], clicks: dict[str, Any],
    impressions: dict[str, Any], visits: dict[str, Any], route_clicks: dict[str, Any],
    coverage: dict[str, int], changes: list[str], run_url: str,
    route_impressions: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    today = date.today().isoformat()
    ctr = (int(clicks.get("total") or 0) / int(impressions.get("total") or 1) * 100) if int(impressions.get("total") or 0) else 0
    visit_click_rate = (int(clicks.get("total") or 0) / int(visits.get("total") or 1) * 100) if int(visits.get("total") or 0) else 0
    click_total = int(clicks.get("total") or 0)
    route_impressions = route_impressions or {}
    route_view_total = int(route_impressions.get("total") or 0)
    route_click_total = int(route_clicks.get("total") or 0)
    route_ctr = (route_click_total / route_view_total * 100) if route_view_total else 0
    click_goal = 100
    target_ctr = 8.0
    route_ctr_goal = 15.0
    visit_goal = 1250
    click_progress = min(100.0, click_total / click_goal * 100)
    clicks_remaining = max(0, click_goal - click_total)
    ps_rewards = partnerstack.get("rewards", {})
    ps_transactions = partnerstack.get("transactions", {})
    rows = [
        ("Site visits (28d)", str(visits.get("total", 0))),
        ("Internal news/guide route clicks (28d)", str(route_clicks.get("total", 0))),
        ("Internal route impressions (28d)", str(route_view_total)),
        ("Internal route click-through rate", f"{route_ctr:.2f}% (goal {route_ctr_goal:.0f}%)"),
        ("Site affiliate clicks (28d)", str(clicks.get("total", 0))),
        ("Qualified affiliate-click goal (28d)", str(click_goal)),
        ("Progress to click goal", f"{click_total}/{click_goal} ({click_progress:.0f}%)"),
        ("Clicks remaining to goal", str(clicks_remaining)),
        ("Affiliate CTA impressions (28d)", str(impressions.get("total", 0))),
        ("Site CTA click-through rate", f"{ctr:.2f}%"),
        ("Visit-to-affiliate-click rate", f"{visit_click_rate:.2f}%"),
        ("Qualified visit goal (28d)", f"{visit_goal} at {target_ctr:.0f}% affiliate CTR"),
        ("Visits remaining to goal", str(max(0, visit_goal - int(visits.get("total") or 0)))),
        ("Top visit sources", _counts(visits.get("by_source", {}))),
        ("Top visit media", _counts(visits.get("by_medium", {}))),
        ("Top landing pages", _counts(visits.get("by_landing_page", {}))),
        ("Top affiliate-click sources", _counts(clicks.get("by_source", {}))),
        ("PartnerStack programs", str(partnerstack.get("partnerships", {}).get("count", 0))),
        ("PartnerStack signups", str(partnerstack.get("customers", {}).get("count", 0))),
        ("PartnerStack paying customers", str(partnerstack.get("customers", {}).get("paid_count", 0))),
        ("PartnerStack revenue", f"USD {int(ps_transactions.get('amount_usd_cents') or 0) / 100:.2f}"),
        ("PartnerStack commissions", f"USD {int(ps_rewards.get('amount_usd_cents') or 0) / 100:.2f}"),
        ("Impact connected", "yes" if impact.get("connected") else "pending credential setup"),
        ("Impact programs", str(impact.get("programs", {}).get("count", 0))),
        ("Impact attributed actions", str(impact.get("actions", {}).get("count", 0))),
        ("Impact attributed revenue", _money_map(impact.get("actions", {}).get("revenue", {}))),
        ("Impact commissions", _money_map(impact.get("actions", {}).get("commissions", {}))),
        ("Impact invoices", str(impact.get("invoices", {}).get("count", 0))),
        ("Impact payment statuses", _counts(impact.get("invoices", {}).get("payment_statuses", {}))),
        ("AppSumo links in inventory", str(coverage["inventory"])),
        ("AppSumo active", str(coverage["active"])),
        ("AppSumo awaiting confirmation", str(coverage["checking"])),
        ("AppSumo expired/disabled", str(coverage["expired"])),
        ("AppSumo promotable editorial matches", str(coverage["promotable"])),
    ]
    change_lines = changes or ["No meaningful aggregate change."]
    if not impact.get("connected"):
        action = "Complete the one-time Impact API connection; the website inventory and public availability automation can run before that connection is added."
    elif int(impact.get("actions", {}).get("count") or 0) == 0 and click_total > 0 and click_total < click_goal:
        action = f"Drive {clicks_remaining} more qualified affiliate clicks to reach the first 100-click diagnostic sample, concentrating distribution on the guides and calculators already earning clicks. Keep AppSumo brand bidding disabled."
    elif int(impact.get("actions", {}).get("count") or 0) == 0 and click_total >= click_goal:
        action = "The first 100-click diagnostic sample is complete without an Impact action. Review partner-level click concentration, offer-page alignment and CTA promises before sending more traffic."
    elif int(visits.get("total") or 0) > 0 and click_total == 0:
        action = "Visitors are arriving but have not clicked an affiliate CTA. Prioritize related-tool routing and above-the-fold comparison links on the pages receiving visits."
    elif click_total == 0:
        action = "No recent tracked visits or affiliate clicks. Activate a connected distribution channel and continue strengthening discovery of the highest-intent guides."
    else:
        action = "Keep the current automation running; expand only pages whose clicks begin producing attributed actions or commissions."
    text_rows = [f"{label}: {value}" for label, value in rows]
    text = "\n".join(["Artificial.One affiliate network dashboard", f"Date: {today}", "", "CURRENT TOTALS", *text_rows, "", "CHANGES", *(f"- {item}" for item in change_lines), "", "NEXT ACTION", action, "", f"Cloud audit: {run_url}"]) + "\n"
    table = "".join(f"<tr><td style='padding:6px 14px 6px 0;color:#667085'>{escape(label)}</td><td style='padding:6px 0;font-weight:700'>{escape(value)}</td></tr>" for label, value in rows)
    items = "".join(f"<li>{escape(item)}</li>" for item in change_lines)
    html = f"<!doctype html><html><body style='font-family:Arial,sans-serif;color:#101828;max-width:760px;margin:auto;padding:24px'><h1>Affiliate network dashboard</h1><p style='color:#667085'>Artificial.One · {today}</p><h2>Current totals</h2><table>{table}</table><h2>Changes</h2><ul>{items}</ul><h2>Next action</h2><p>{escape(action)}</p><p><a href='{escape(run_url)}'>Open cloud audit</a></p><p style='font-size:12px;color:#667085'>Aggregate data only. No customer identities or raw transaction records are stored or emailed.</p></body></html>"
    return f"Artificial.One affiliate dashboard — {today}", text, html


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path(".affiliate-monitor/baseline.json"))
    parser.add_argument("--email-to", default="")
    parser.add_argument("--email-from", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    partner_key = os.environ.get("PARTNERSTACK_API_KEY", "").strip()
    if not partner_key:
        print("PARTNERSTACK_API_KEY is not configured", file=sys.stderr)
        return 1
    collections = {name: ps.fetch_all(name, partner_key, params) for name, params in ps.API_RESOURCES.items()}
    redis_url = (os.environ.get("UPSTASH_REDIS_REST_URL") or "").strip()
    redis_token = (os.environ.get("UPSTASH_REDIS_REST_TOKEN") or "").strip()
    clicks = ps.fetch_affiliate_events(redis_url, redis_token, "clicks") if redis_url and redis_token else {}
    impressions = ps.fetch_affiliate_events(redis_url, redis_token, "impressions") if redis_url and redis_token else {}
    visits = ps.fetch_affiliate_events(redis_url, redis_token, "visits") if redis_url and redis_token else {}
    route_clicks = ps.fetch_affiliate_events(redis_url, redis_token, "route_clicks") if redis_url and redis_token else {}
    route_impressions = ps.fetch_affiliate_events(redis_url, redis_token, "route_impressions") if redis_url and redis_token else {}
    partnerstack = ps.build_snapshot(collections, affiliate_clicks=clicks, affiliate_impressions=impressions)
    sid = os.environ.get("IMPACT_ACCOUNT_SID", "").strip()
    token = os.environ.get("IMPACT_AUTH_TOKEN", "").strip()
    impact = fetch_impact_snapshot(sid, token) if sid and token else {"connected": False}
    current = {"schema_version": 2, "audited_at": datetime.now(timezone.utc).isoformat(), "partnerstack": partnerstack, "impact": impact, "acquisition": {"visits": visits, "route_clicks": route_clicks, "route_impressions": route_impressions}}
    previous = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline.exists() else {}
    changes = ps.compare_snapshots(previous.get("partnerstack", {}), partnerstack) if previous else []
    if previous and impact.get("connected"):
        changes.extend(_impact_changes(previous.get("impact", {}), impact))
    run_url = f"{os.environ.get('GITHUB_SERVER_URL', '')}/{os.environ.get('GITHUB_REPOSITORY', '')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}".strip("/")
    subject, text_body, html_body = render_dashboard(partnerstack, impact, clicks, impressions, visits, route_clicks, website_coverage(), changes, run_url, route_impressions=route_impressions)
    if args.email_to:
        resend = os.environ.get("RESEND_API_KEY", "").strip()
        if not resend or not args.email_from:
            raise RuntimeError("RESEND_API_KEY and --email-from are required")
        ps.send_resend_email(resend, args.email_from, args.email_to, subject, text_body, html_body)
    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ps._set_output("changed", "true" if changes else "false")
    ps._set_output("impact_connected", "true" if impact.get("connected") else "false")
    print("Affiliate network audit completed; only aggregate data was persisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
