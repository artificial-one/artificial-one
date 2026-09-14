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
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.partnerstack.com/api/v2"
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


def _set_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path(".partner-metrics/cloud-baseline.json"))
    parser.add_argument("--report", type=Path, default=Path(".partner-metrics/cloud-report.md"))
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

    args.baseline.parent.mkdir(parents=True, exist_ok=True)
    args.baseline.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _set_output("changed", "true" if changes else "false")
    _set_output("initialized", "false" if previous else "true")
    _set_output("report", str(args.report))
    print("PartnerStack cloud audit completed; raw account data was not persisted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
