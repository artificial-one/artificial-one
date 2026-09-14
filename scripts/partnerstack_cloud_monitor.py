#!/usr/bin/env python3
"""Read-only PartnerStack Partner API monitor for unattended cloud runs.

Only sanitized aggregate data is persisted. Raw API responses and customer
records are held in memory for the duration of the process and are never
written to disk or printed.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.partnerstack.com/api/v2"
RESEND_EMAILS_URL = "https://api.resend.com/emails"
API_RESOURCES = {
    "partnerships": {"include_offers": "true", "include_archived": "true"},
    "customers": {},
    "transactions": {},
    "rewards": {},
}


class PartnerStackError(RuntimeError):
    """Raised when PartnerStack cannot be read safely."""


def _items_from_payload(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    data = payload.get("data", {})
    if isinstance(data, list):
        return data, False
    if not isinstance(data, dict):
        raise PartnerStackError("PartnerStack returned an unexpected response shape")
    items = data.get("items", [])
    if not isinstance(items, list):
        raise PartnerStackError("PartnerStack returned an unexpected item collection")
    return items, bool(data.get("has_more"))


def fetch_all(resource: str, api_key: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Fetch every page for a read-only Partner API resource."""
    collected: list[dict[str, Any]] = []
    query = dict(params or {})
    query["limit"] = "250"

    while True:
        url = f"{API_BASE}/{resource}?{urlencode(query)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "artificial.one-partner-monitor/1.0",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.load(response)
        except Exception as exc:  # urllib exposes several transport subclasses
            raise PartnerStackError(f"PartnerStack {resource} request failed: {exc}") from exc

        items, has_more = _items_from_payload(payload)
        collected.extend(item for item in items if isinstance(item, dict))
        if not has_more or not items:
            return collected

        cursor = items[-1].get("key")
        if not cursor:
            raise PartnerStackError(f"PartnerStack {resource} pagination had no cursor")
        query["starting_after"] = str(cursor)


def _integer(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _company_name(item: dict[str, Any]) -> str:
    company = item.get("company")
    if isinstance(company, dict):
        name = company.get("name")
        if name:
            return str(name)
    return str(item.get("company_name") or item.get("name") or "Unknown program")


def _partnership_status(item: dict[str, Any]) -> str:
    return str(item.get("approved_status") or item.get("status") or "unknown")


def build_snapshot(collections: dict[str, list[dict[str, Any]]], audited_at: str | None = None) -> dict[str, Any]:
    """Reduce API data to non-PII aggregates suitable for a cloud cache."""
    partnerships = collections.get("partnerships", [])
    customers = collections.get("customers", [])
    transactions = collections.get("transactions", [])
    rewards = collections.get("rewards", [])

    partnership_states = sorted(
        (
            {
            "program": _company_name(item),
            "status": _partnership_status(item),
            }
            for item in partnerships
        ),
        key=lambda item: (item["program"].casefold(), item["status"].casefold()),
    )
    reward_statuses = Counter(
        str(item.get("reward_status") or item.get("status") or "unknown") for item in rewards
    )
    payment_statuses = Counter(str(item.get("payment_status") or "unknown") for item in rewards)

    return {
        "schema_version": 1,
        "audited_at": audited_at or datetime.now(timezone.utc).isoformat(),
        "partnerships": {
            "count": len(partnerships),
            "states": partnership_states,
        },
        "customers": {
            "count": len(customers),
            "paid_count": sum(bool(item.get("has_paid")) for item in customers),
        },
        "transactions": {
            "count": len(transactions),
            "amount_usd_cents": sum(_integer(item.get("amount_usd")) for item in transactions),
        },
        "rewards": {
            "count": len(rewards),
            "amount_usd_cents": sum(_integer(item.get("amount")) for item in rewards),
            "statuses": dict(sorted(reward_statuses.items())),
            "payment_statuses": dict(sorted(payment_statuses.items())),
        },
    }


def _money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def compare_snapshots(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Return user-readable material changes without customer-level data."""
    changes: list[str] = []
    fields = (
        ("customers", "count", "Attributed signups", str),
        ("customers", "paid_count", "Paying customers", str),
        ("transactions", "count", "Transactions", str),
        ("transactions", "amount_usd_cents", "Attributed revenue", _money),
        ("rewards", "count", "Rewards", str),
        ("rewards", "amount_usd_cents", "Commissions", _money),
    )
    for section, field, label, formatter in fields:
        before = _integer(previous.get(section, {}).get(field))
        after = _integer(current.get(section, {}).get(field))
        if before != after:
            changes.append(f"{label}: {formatter(before)} -> {formatter(after)}")

    before_states = {
        str(item.get("program")): str(item.get("status"))
        for item in previous.get("partnerships", {}).get("states", [])
    }
    after_states = {
        str(item.get("program")): str(item.get("status"))
        for item in current.get("partnerships", {}).get("states", [])
    }
    for program in sorted(after_states.keys() - before_states.keys()):
        changes.append(f"New partnership: {program} ({after_states[program]})")
    for program in sorted(before_states.keys() - after_states.keys()):
        changes.append(f"Partnership removed or archived: {program}")
    for program in sorted(before_states.keys() & after_states.keys()):
        if before_states[program] != after_states[program]:
            changes.append(
                f"Partnership status changed: {program} "
                f"({before_states[program]} -> {after_states[program]})"
            )

    for section, label in (("statuses", "Reward status"), ("payment_statuses", "Payment status")):
        before = previous.get("rewards", {}).get(section, {})
        after = current.get("rewards", {}).get(section, {})
        if before != after:
            changes.append(f"{label} totals changed")
    return changes


def write_report(path: Path, changes: Iterable[str], run_url: str = "") -> None:
    lines = ["## PartnerStack cloud monitor", ""]
    change_list = list(changes)
    if change_list:
        lines.append("Meaningful aggregate changes were detected:")
        lines.append("")
        lines.extend(f"- {change}" for change in change_list)
        lines.extend(
            [
                "",
                "Recommended next step: review the affected program in PartnerStack before changing public content.",
            ]
        )
    else:
        lines.append("No meaningful aggregate change was detected.")
    if run_url:
        lines.extend(["", f"Workflow run: {run_url}"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _status_summary(values: dict[str, Any]) -> str:
    if not values:
        return "None"
    return ", ".join(f"{name}: {_integer(count)}" for name, count in sorted(values.items()))


def _recommendation(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    changes: list[str],
) -> str:
    if previous is None:
        return "Baseline initialized. Confirm that the priority offers and their public tracking links match the current publishing plan."

    before_customers = previous.get("customers", {})
    after_customers = current.get("customers", {})
    signup_delta = _integer(after_customers.get("count")) - _integer(before_customers.get("count"))
    paid_delta = _integer(after_customers.get("paid_count")) - _integer(before_customers.get("paid_count"))
    commission_delta = _integer(current.get("rewards", {}).get("amount_usd_cents")) - _integer(
        previous.get("rewards", {}).get("amount_usd_cents")
    )

    if paid_delta > 0 or commission_delta > 0:
        return "Conversions improved. Identify the converting offer and expand the content or call-to-action that generated it."
    if signup_delta > 0 and paid_delta <= 0:
        return "Interest increased without a new paying customer. Review offer-to-landing-page alignment and the next-step call to action."
    if any(change.startswith("New partnership:") for change in changes):
        return "Review the new program's audience fit, economics and promotion restrictions before adding it to public content."
    if any("Payment status" in change or "Reward status" in change for change in changes):
        return "Review the changed reward or payment state in PartnerStack and act only if the dashboard requires account action."
    if changes:
        return "Review the affected metric or partnership in PartnerStack before changing public content."
    return "No action is needed today. Keep the current offer and publishing plan unchanged."


def render_email_dashboard(
    current: dict[str, Any],
    changes: list[str],
    previous: dict[str, Any] | None,
    run_url: str = "",
) -> tuple[str, str, str]:
    """Return subject, plain text and HTML using aggregate, non-PII data only."""
    audited_at = str(current.get("audited_at") or "")
    report_date = audited_at[:10] or datetime.now(timezone.utc).date().isoformat()
    subject = f"Artificial.One PartnerStack dashboard — {report_date}"
    partnerships = current.get("partnerships", {})
    customers = current.get("customers", {})
    transactions = current.get("transactions", {})
    rewards = current.get("rewards", {})
    partnership_states = partnerships.get("states", [])
    partnership_lines = [
        f"{item.get('program', 'Unknown program')}: {item.get('status', 'unknown')}"
        for item in partnership_states
    ] or ["None"]
    change_lines = changes or (["Baseline initialized; future emails will show daily changes."] if previous is None else ["No meaningful change."])
    recommendation = _recommendation(previous, current, changes)

    metric_lines = [
        f"Partnerships: {_integer(partnerships.get('count'))}",
        f"Attributed signups: {_integer(customers.get('count'))}",
        f"Paying customers: {_integer(customers.get('paid_count'))}",
        f"Transactions: {_integer(transactions.get('count'))}",
        f"Attributed revenue: {_money(_integer(transactions.get('amount_usd_cents')))}",
        f"Rewards: {_integer(rewards.get('count'))}",
        f"Commissions: {_money(_integer(rewards.get('amount_usd_cents')))}",
        f"Reward statuses: {_status_summary(rewards.get('statuses', {}))}",
        f"Payment statuses: {_status_summary(rewards.get('payment_statuses', {}))}",
    ]
    text_lines = [
        "Artificial.One PartnerStack dashboard",
        f"Audited: {audited_at}",
        "",
        "CURRENT TOTALS",
        *metric_lines,
        "",
        "PARTNERSHIPS",
        *(f"- {line}" for line in partnership_lines),
        "",
        "CHANGES SINCE PREVIOUS AUDIT",
        *(f"- {line}" for line in change_lines),
        "",
        "ANALYSIS / NEXT ACTION",
        recommendation,
    ]
    if run_url:
        text_lines.extend(["", f"Cloud audit: {run_url}"])
    text_body = "\n".join(text_lines) + "\n"

    metric_rows = "".join(
        f"<tr><td style='padding:6px 12px 6px 0;color:#667085'>{escape(line.split(':', 1)[0])}</td>"
        f"<td style='padding:6px 0;font-weight:600'>{escape(line.split(':', 1)[1].strip())}</td></tr>"
        for line in metric_lines
    )
    partnership_items = "".join(f"<li>{escape(line)}</li>" for line in partnership_lines)
    change_items = "".join(f"<li>{escape(line)}</li>" for line in change_lines)
    run_link = f"<p><a href='{escape(run_url)}'>Open cloud audit</a></p>" if run_url else ""
    html_body = f"""<!doctype html>
<html><body style="font-family:Arial,sans-serif;color:#101828;line-height:1.5;max-width:680px;margin:auto;padding:24px">
<h1 style="font-size:24px;margin-bottom:4px">PartnerStack daily dashboard</h1>
<p style="color:#667085;margin-top:0">Artificial.One · {escape(audited_at)}</p>
<h2 style="font-size:18px">Current totals</h2><table>{metric_rows}</table>
<h2 style="font-size:18px">Partnerships</h2><ul>{partnership_items}</ul>
<h2 style="font-size:18px">Changes since previous audit</h2><ul>{change_items}</ul>
<h2 style="font-size:18px">Analysis / next action</h2><p>{escape(recommendation)}</p>
{run_link}<p style="color:#667085;font-size:12px">This automated email contains aggregate data only. No customer identities are stored or sent.</p>
</body></html>"""
    return subject, text_body, html_body


def send_resend_email(
    api_key: str,
    sender: str,
    recipient: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    payload = json.dumps(
        {
            "from": sender,
            "to": [recipient],
            "subject": subject,
            "text": text_body,
            "html": html_body,
        }
    ).encode("utf-8")
    request = Request(
        RESEND_EMAILS_URL,
        data=payload,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "artificial.one-partner-monitor/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise PartnerStackError(f"Resend rejected the dashboard email with HTTP {response.status}")
            json.load(response)
    except PartnerStackError:
        raise
    except Exception as exc:
        raise PartnerStackError(f"Private dashboard email delivery failed: {exc}") from exc


def _set_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path(".partner-metrics/cloud-baseline.json"))
    parser.add_argument("--report", type=Path, default=Path(".partner-metrics/cloud-report.md"))
    parser.add_argument("--email-to", default="")
    parser.add_argument("--email-from", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    api_key = os.environ.get("PARTNERSTACK_API_KEY", "").strip()
    if not api_key:
        print("PARTNERSTACK_API_KEY is not configured", file=sys.stderr)
        return 1

    collections = {
        resource: fetch_all(resource, api_key, params)
        for resource, params in API_RESOURCES.items()
    }
    current = build_snapshot(collections)
    previous = None
    if args.baseline.exists():
        previous = json.loads(args.baseline.read_text(encoding="utf-8"))

    changes = compare_snapshots(previous, current) if previous else []
    run_url = ""
    if os.environ.get("GITHUB_SERVER_URL") and os.environ.get("GITHUB_REPOSITORY"):
        run_url = (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
        )
    write_report(args.report, changes, run_url)

    if args.email_to:
        resend_api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not resend_api_key:
            raise PartnerStackError("RESEND_API_KEY is not configured")
        if not args.email_from:
            raise PartnerStackError("--email-from is required when --email-to is used")
        subject, text_body, html_body = render_email_dashboard(current, changes, previous, run_url)
        send_resend_email(
            resend_api_key,
            args.email_from,
            args.email_to,
            subject,
            text_body,
            html_body,
        )

    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _set_output("changed", "true" if changes else "false")
    _set_output("initialized", "false" if previous else "true")
    _set_output("report", str(args.report))
    print("PartnerStack cloud audit completed; raw account data was not persisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
