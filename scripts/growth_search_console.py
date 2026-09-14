#!/usr/bin/env python3
"""Turn Search Console data into a private, revenue-focused growth brief."""

from __future__ import annotations

import argparse
import base64
from datetime import date, timedelta
from html import escape
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SEARCH_API = "https://searchconsole.googleapis.com/webmasters/v3"
RESEND_API = "https://api.resend.com/emails"


class GrowthError(RuntimeError):
    pass


def load_service_account(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise GrowthError("GSC_SERVICE_ACCOUNT_JSON is not configured")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        try:
            value = json.loads(base64.b64decode(raw).decode("utf-8"))
        except Exception as exc:
            raise GrowthError("GSC_SERVICE_ACCOUNT_JSON must be JSON or base64 JSON") from exc
    if not isinstance(value, dict) or not value.get("client_email"):
        raise GrowthError("Search Console service-account credentials are incomplete")
    return value


def authorized_session(service_account_info: dict[str, Any]):
    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2 import service_account
    except ImportError as exc:
        raise GrowthError("Install google-auth before running the growth monitor") from exc
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/webmasters"],
    )
    return AuthorizedSession(credentials)


def query_search_analytics(session, site_url: str, start: date, end: date) -> list[dict[str, Any]]:
    endpoint = f"{SEARCH_API}/sites/{quote(site_url, safe='')}/searchAnalytics/query"
    rows: list[dict[str, Any]] = []
    start_row = 0
    while True:
        payload = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["page", "query"],
            "type": "web",
            "dataState": "final",
            "rowLimit": 25000,
            "startRow": start_row,
        }
        response = session.post(endpoint, json=payload, timeout=45)
        if response.status_code >= 400:
            raise GrowthError(f"Search Console query failed with HTTP {response.status_code}")
        batch = response.json().get("rows", [])
        if not isinstance(batch, list):
            raise GrowthError("Search Console returned an unexpected row collection")
        rows.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 25000:
            return rows
        start_row += len(batch)


def submit_sitemap(session, site_url: str, sitemap_url: str) -> None:
    endpoint = (
        f"{SEARCH_API}/sites/{quote(site_url, safe='')}/sitemaps/"
        f"{quote(sitemap_url, safe='')}"
    )
    response = session.put(endpoint, timeout=30)
    if response.status_code >= 400:
        raise GrowthError(f"Sitemap submission failed with HTTP {response.status_code}")


def affiliate_paths(root: Path = ROOT) -> set[str]:
    paths: set[str] = set()
    for page in root.rglob("*.html"):
        relative = page.relative_to(root).as_posix()
        if relative.startswith((".git/", "node_modules/")):
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        if "data-affiliate-offer" in text or relative.startswith("partner-offers/"):
            paths.add("/" + relative)
    return paths


def target_ctr(position: float) -> float:
    if position <= 3:
        return 0.12
    if position <= 5:
        return 0.08
    if position <= 10:
        return 0.045
    if position <= 20:
        return 0.02
    return 0.01


def build_opportunities(
    rows: list[dict[str, Any]], monetized_paths: set[str], limit: int = 50
) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for row in rows:
        keys = row.get("keys", [])
        if not isinstance(keys, list) or len(keys) < 2:
            continue
        page = str(keys[0])
        query = str(keys[1]).strip()
        impressions = int(float(row.get("impressions") or 0))
        clicks = int(float(row.get("clicks") or 0))
        ctr = float(row.get("ctr") or 0)
        position = float(row.get("position") or 0)
        if impressions < 20 or not 3 <= position <= 20 or not query:
            continue
        path = "/" + page.split("artificial.one/", 1)[-1].split("?", 1)[0].lstrip("/")
        commercial = path in monetized_paths or path.startswith("/partner-offers")
        click_gap = max(0.0, target_ctr(position) - ctr) * impressions
        score = click_gap * (1.75 if commercial else 1.0)
        opportunities.append(
            {
                "query": query[:180],
                "page": page[:500],
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(ctr, 4),
                "position": round(position, 1),
                "commercial": commercial,
                "estimated_click_gap": round(click_gap, 1),
                "score": round(score, 2),
            }
        )
    return sorted(
        opportunities,
        key=lambda item: (-item["score"], -item["impressions"], item["query"]),
    )[:limit]


def render_email(opportunities: list[dict[str, Any]], start: date, end: date) -> tuple[str, str, str]:
    commercial = [item for item in opportunities if item["commercial"]]
    subject = f"Artificial.One growth opportunities — {end.isoformat()}"
    intro = (
        f"Search Console analysis for {start.isoformat()} through {end.isoformat()}. "
        f"Found {len(opportunities)} priority query/page opportunities; "
        f"{len(commercial)} already lead to monetized pages."
    )
    lines = [subject, "", intro, "", "TOP OPPORTUNITIES"]
    for item in opportunities[:20]:
        label = "REVENUE PAGE" if item["commercial"] else "AUDIENCE PAGE"
        lines.append(
            f"- [{label}] {item['query']} — position {item['position']}, "
            f"{item['impressions']} impressions, {item['clicks']} clicks, "
            f"estimated gap {item['estimated_click_gap']} clicks\n  {item['page']}"
        )
    if not opportunities:
        lines.append("- No query/page pair met the current opportunity threshold.")
    lines.extend(
        [
            "",
            "AUTOMATED ACTION",
            "The sitemap was resubmitted. The ranking queue will be re-evaluated on the next scheduled run.",
            "No customer identities or raw Search Console export are stored or emailed.",
        ]
    )

    rows = "".join(
        "<tr>"
        f"<td style='padding:8px;border-bottom:1px solid #e5e7eb'>{escape(item['query'])}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #e5e7eb'>{item['position']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #e5e7eb'>{item['impressions']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #e5e7eb'>{item['estimated_click_gap']}</td>"
        f"<td style='padding:8px;border-bottom:1px solid #e5e7eb'>{'Revenue' if item['commercial'] else 'Audience'}</td>"
        "</tr>"
        for item in opportunities[:20]
    )
    if not rows:
        rows = "<tr><td colspan='5' style='padding:12px'>No opportunity met the current threshold.</td></tr>"
    html = f"""<!doctype html><html><body style="font-family:Arial,sans-serif;color:#101828;line-height:1.5;max-width:760px;margin:auto;padding:24px">
<h1 style="font-size:24px;margin-bottom:4px">Artificial.One growth dashboard</h1>
<p style="color:#667085">{escape(intro)}</p>
<table style="border-collapse:collapse;width:100%;font-size:13px"><thead><tr><th align="left">Query</th><th>Position</th><th>Impressions</th><th>Click gap</th><th>Path</th></tr></thead><tbody>{rows}</tbody></table>
<h2 style="font-size:18px;margin-top:24px">Automated action</h2><p>The sitemap was resubmitted and this revenue-weighted ranking queue will be recalculated automatically.</p>
<p style="color:#667085;font-size:12px">Aggregate search performance only. No customer identities or raw export are retained.</p>
</body></html>"""
    return subject, "\n".join(lines) + "\n", html


def send_email(api_key: str, sender: str, recipient: str, subject: str, text: str, html: str) -> None:
    payload = json.dumps(
        {"from": sender, "to": [recipient], "subject": subject, "text": text, "html": html}
    ).encode("utf-8")
    request = Request(
        RESEND_API,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "artificial.one-growth-monitor/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise GrowthError(f"Resend returned HTTP {response.status}")
    except GrowthError:
        raise
    except Exception as exc:
        raise GrowthError(f"Growth email delivery failed: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site",
        default=os.environ.get("GSC_SITE_URL") or "sc-domain:artificial.one",
    )
    parser.add_argument("--sitemap", default="https://artificial.one/sitemap.xml")
    parser.add_argument("--email-to", default="hello@artificial.one")
    parser.add_argument("--email-from", default="Artificial.One Growth <onboarding@resend.dev>")
    parser.add_argument("--days", type=int, default=28)
    args = parser.parse_args()

    try:
        info = load_service_account(os.environ.get("GSC_SERVICE_ACCOUNT_JSON", ""))
        session = authorized_session(info)
        end = date.today() - timedelta(days=3)
        start = end - timedelta(days=max(1, args.days) - 1)
        rows = query_search_analytics(session, args.site, start, end)
        opportunities = build_opportunities(rows, affiliate_paths())
        submit_sitemap(session, args.site, args.sitemap)
        resend_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not resend_key:
            raise GrowthError("RESEND_API_KEY is not configured")
        subject, text, html = render_email(opportunities, start, end)
        send_email(resend_key, args.email_from, args.email_to, subject, text, html)
        print(
            f"Analyzed {len(rows)} Search Console rows; "
            f"emailed {len(opportunities)} sanitized opportunities."
        )
        return 0
    except GrowthError as exc:
        print(f"Growth monitor failed: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
