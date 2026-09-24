#!/usr/bin/env python3
"""Reconcile every connected affiliate source with the public site.

The contract is intentionally network-independent: any connector that emits an
approved relationship and a tracking URL becomes publishable, and CI refuses to
pass until its exact link is present on a generated public page. Approved records
without usable links remain visible as activation blockers instead of disappearing.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from html import escape
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "affiliate_source_reconciliation.json"


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def page_contains_url(path: Path, url: str) -> bool:
    if not path.is_file() or not url:
        return False
    source = path.read_text(encoding="utf-8", errors="replace")
    return url in source or escape(url, quote=True) in source


def offer_indexes(root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    registry = load_json(root / "data" / "partner_offers.json", {"offers": []})
    by_name: dict[str, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for offer in registry.get("offers", []):
        if not isinstance(offer, dict):
            continue
        for value in (offer.get("name"), offer.get("slug"), offer.get("id")):
            if value:
                by_name[normalized(value)] = offer
        if offer.get("id"):
            by_id[str(offer["id"])] = offer
    return by_name, by_id


def opportunity_rows(root: Path) -> list[dict[str, Any]]:
    payload = load_json(root / "data" / "partner_opportunities.json", {"opportunities": []})
    by_name, _ = offer_indexes(root)
    audit = load_json(root / "data" / "partnerstack_program_audit.json", {"programs": []})
    access_by_name = {
        normalized(item.get("name")): str(item.get("access") or "")
        for item in audit.get("programs", []) if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for item in payload.get("opportunities", []):
        if not isinstance(item, dict):
            continue
        approved = bool(item.get("approved") or item.get("authenticated_relationship") or item.get("already_active"))
        offer = by_name.get(normalized(item.get("name"))) or by_name.get(normalized(item.get("slug")))
        tracking_url = str(item.get("tracking_url") or (offer or {}).get("tracking_url") or "")
        explicit = str(item.get("relationship_state") or "")
        access = access_by_name.get(normalized(item.get("name")), "")
        if offer and str(offer.get("status")) == "published":
            state = "published"
        elif access in {"external_account_required", "terms_required"}:
            state = "terms_required" if access == "terms_required" else "active_link_pending"
        elif explicit in {"pending", "terms_required", "active_link_pending", "publishable", "published"}:
            state = explicit
        elif item.get("terms_required") or item.get("state") == "terms_required":
            state = "terms_required"
        elif approved and tracking_url:
            state = "publishable"
        elif approved:
            state = "active_link_pending"
        else:
            state = "pending"
        rows.append({
            "source_id": str(item.get("id") or f"{item.get('network', 'unknown')}:{item.get('slug', '')}"),
            "network": str(item.get("network") or "unknown"),
            "name": str(item.get("name") or item.get("slug") or "Unknown program"),
            "state": state,
            "tracking_url": tracking_url,
            "offer_id": str((offer or {}).get("id") or ""),
            "page": f"partner-offers/{offer['slug']}.html" if offer else "",
            "blocker": access if access in {"external_account_required", "terms_required"} else "",
        })
    return rows


def appsumo_rows(root: Path) -> list[dict[str, Any]]:
    payload = load_json(root / "data" / "appsumo_offers.json", {"offers": []})
    rows: list[dict[str, Any]] = []
    for item in payload.get("offers", []):
        if not isinstance(item, dict) or item.get("availability") != "active" or not item.get("ai_relevant"):
            continue
        tracking_url = str(item.get("tracking_url") or "")
        editorial = str(item.get("editorial_url") or "")
        state = "published" if tracking_url and editorial else ("publishable" if tracking_url else "active_link_pending")
        rows.append({
            "source_id": str(item.get("id") or f"impact-appsumo:{item.get('slug', '')}"),
            "network": "impact-appsumo",
            "name": str(item.get("name") or item.get("slug") or "Unknown AppSumo product"),
            "state": state,
            "tracking_url": tracking_url,
            "offer_id": str(item.get("id") or ""),
            "page": editorial,
        })
    return rows


def reconcile(root: Path) -> dict[str, Any]:
    rows = opportunity_rows(root) + appsumo_rows(root)
    failures: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []
    for row in rows:
        page = root / row["page"] if row["page"] else None
        if row["state"] == "publishable":
            failures.append({"source_id": row["source_id"], "reason": "publishable_relationship_missing_public_offer"})
        elif row["state"] == "published":
            if not row["tracking_url"]:
                failures.append({"source_id": row["source_id"], "reason": "published_offer_missing_tracking_url"})
            elif not page or not page.is_file():
                failures.append({"source_id": row["source_id"], "reason": "published_offer_page_missing"})
            elif not page_contains_url(page, row["tracking_url"]):
                failures.append({"source_id": row["source_id"], "reason": "published_page_has_wrong_or_missing_tracking_url"})
        elif row["state"] in {"terms_required", "active_link_pending"}:
            blockers.append({"source_id": row["source_id"], "reason": row.get("blocker") or row["state"]})

    states = Counter(row["state"] for row in rows)
    networks: dict[str, dict[str, int]] = {}
    for network in sorted({row["network"] for row in rows}):
        network_rows = [row for row in rows if row["network"] == network]
        counts = Counter(row["state"] for row in network_rows)
        networks[network] = {"total": len(network_rows), **dict(sorted(counts.items()))}
    return {
        "version": 1,
        "updated_at": date.today().isoformat(),
        "contract": {
            "states": ["pending", "terms_required", "active_link_pending", "publishable", "published"],
            "rule": "Every approved relationship with a usable tracking URL must have a public page containing that exact URL.",
            "future_sources": "Any connector represented in partner_opportunities.json is reconciled automatically.",
        },
        "summary": {"total": len(rows), **dict(sorted(states.items())), "blocking_failures": len(failures), "activation_blockers": len(blockers)},
        "networks": networks,
        "activation_blockers": blockers,
        "failures": failures,
    }


def main(root: Path, check: bool) -> int:
    payload = reconcile(root)
    desired = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    output = root / "data" / "affiliate_source_reconciliation.json"
    if check:
        current = output.read_text(encoding="utf-8") if output.exists() else ""
        if current != desired:
            print("Affiliate source reconciliation is stale; rebuild it before deployment.")
            return 1
        if payload["failures"]:
            for failure in payload["failures"]:
                print(f"{failure['source_id']}: {failure['reason']}")
            return 1
        print(f"Affiliate reconciliation passed for {payload['summary']['total']} canonical source records.")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(desired, encoding="utf-8")
    print(
        f"Reconciled {payload['summary']['total']} source records: "
        f"{payload['summary'].get('published', 0)} published, "
        f"{payload['summary']['activation_blockers']} activation blockers, "
        f"{payload['summary']['blocking_failures']} publishing failures."
    )
    return 1 if payload["failures"] else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    raise SystemExit(main(args.root, args.check))
