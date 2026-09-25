#!/usr/bin/env python3
"""Send one business-readable daily report for artificial.one.

The report deliberately hides operational detail. It combines verified public
business activity, current affiliate coverage, aggregate revenue/conversion
metrics and the small set of decisions that cannot legally be automated.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PRAGUE = ZoneInfo("Europe/Prague")
RESEND_URL = "https://api.resend.com/emails"
RESEND_DOMAINS_URL = "https://api.resend.com/domains"
LINKEDIN_VERSION = "202608"
SOCIAL_PLATFORMS = ("linkedin", "bluesky", "x")


def load_json(path: Path, default: Any | None = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {} if default is None else default


def integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def money_map(values: dict[str, Any]) -> str:
    nonzero = [(str(currency), str(amount)) for currency, amount in sorted(values.items()) if float(amount or 0)]
    return ", ".join(f"{currency} {amount}" for currency, amount in nonzero) or "USD 0.00"


def daily_activity(payload: dict[str, Any], report_date: str) -> dict[str, Any]:
    entries = [item for item in payload.get("entries", []) if item.get("date") == report_date]
    kinds = Counter(str(item.get("kind") or "") for item in entries)
    pages_created = [item for item in entries if item.get("kind") == "webpage_created"]
    pages_updated = [item for item in entries if item.get("kind") == "webpage_updated"]
    social = [item for item in entries if item.get("kind") == "social_post_published"]
    commercial = [
        item for item in entries
        if item.get("kind") in {
            "affiliate_offers_added", "appsumo_offers_added",
            "affiliate_offer_changes_detected", "vendor_changes_detected",
        }
    ]
    highlights: list[dict[str, str]] = []
    for group in (commercial, pages_created, social, pages_updated):
        for item in group:
            summary = str(item.get("summary") or "").strip()
            if not summary or any(existing["text"] == summary for existing in highlights):
                continue
            highlights.append({"text": summary, "url": str(item.get("url") or "")})
            if len(highlights) == 5:
                break
        if len(highlights) == 5:
            break
    return {
        "entries": entries,
        "counts": kinds,
        "pages_created": len({item.get("path") for item in pages_created}),
        "pages_updated": len({item.get("path") for item in pages_updated}),
        "social_posts": len(social),
        "highlights": highlights,
    }


def opportunity_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or ""): item
        for item in payload.get("opportunities", [])
        if isinstance(item, dict) and item.get("id")
    }


def owner_actions(
    reconciliation: dict[str, Any], opportunities: dict[str, Any],
    marketplace: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    lookup = opportunity_lookup(opportunities)
    actions: list[dict[str, str]] = []
    labels = {
        "terms_required": "Accept the program terms",
        "external_account_required": "Finish the one-time partner account setup",
    }
    for blocker in reconciliation.get("activation_blockers", []):
        reason = str(blocker.get("reason") or "")
        if reason not in labels:
            continue
        source_id = str(blocker.get("source_id") or "")
        item = lookup.get(source_id, {})
        name = str(item.get("name") or source_id.partition(":")[2].replace("-", " ").title())
        url = str(item.get("application_url") or item.get("terms_url") or "https://dash.partnerstack.com/home")
        actions.append({
            "title": f"{labels[reason]}: {name}",
            "detail": "This requires your acceptance because it creates a legal or account commitment.",
            "url": url,
        })
    for action in (marketplace or {}).get("owner_actions", []):
        if not isinstance(action, dict):
            continue
        actions.append({
            "title": str(action.get("title") or "Review a sponsored-content request"),
            "detail": str(action.get("detail") or "Accepting creates a binding delivery commitment."),
            "url": str(action.get("url") or "https://dash.partnerstack.com/content-marketplace/requests"),
        })
    actions.sort(key=lambda action: action["title"].casefold())
    return actions


def system_work(reconciliation: dict[str, Any], opportunities: dict[str, Any]) -> list[dict[str, str]]:
    """Explain every approved relationship the automation has not published yet."""
    lookup = opportunity_lookup(opportunities)
    work: list[dict[str, str]] = []
    for blocker in reconciliation.get("activation_blockers", []):
        if str(blocker.get("reason") or "") != "active_link_pending":
            continue
        source_id = str(blocker.get("source_id") or "")
        item = lookup.get(source_id, {})
        name = str(item.get("name") or source_id.partition(":")[2].replace("-", " ").title())
        work.append({
            "title": name,
            "detail": (
                "The partnership is approved, but its referral link is not available yet. "
                "The product page will publish automatically as soon as the partner provides the link."
            ),
        })
    return sorted(work, key=lambda item: item["title"].casefold())


def live_affiliate_destinations(partner_offers: dict[str, Any], appsumo: dict[str, Any]) -> int:
    """Count unique, public, AI-relevant destinations—not pages or database rows."""
    urls: set[str] = set()
    for item in partner_offers.get("offers", []):
        if item.get("status") == "published" and str(item.get("tracking_url") or "").startswith("https://"):
            urls.add(str(item["tracking_url"]))
    for item in appsumo.get("offers", []):
        if (
            item.get("availability") != "expired" and item.get("ai_relevant")
            and item.get("editorial_url") and str(item.get("tracking_url") or "").startswith("https://")
        ):
            urls.add(str(item["tracking_url"]))
    return len(urls)


def receipt_urn(receipt: dict[str, Any]) -> str:
    identifier = str(receipt.get("id") or "")
    return identifier.split(":", 1)[1] if ":" in identifier else identifier


def local_receipt_date(receipt: dict[str, Any]) -> date | None:
    parsed = local_receipt_datetime(receipt)
    return parsed.date() if parsed else None


def local_receipt_datetime(receipt: dict[str, Any]) -> datetime | None:
    value = str(receipt.get("published_at") or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(PRAGUE)
    except (ValueError, TypeError):
        return None


def bluesky_metrics(receipts: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    wanted = [receipt_urn(item) for item in receipts if item.get("platform") == "bluesky"]
    if not wanted:
        return {}
    query = "&".join(f"uris={quote(uri, safe='')}" for uri in wanted)
    request = Request(
        f"https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts?{query}",
        headers={"Accept": "application/json", "User-Agent": "artificial.one-daily-report/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            posts = json.load(response).get("posts", [])
    except Exception:
        return {}
    return {
        str(post.get("uri") or ""): {
            "likes": integer(post.get("likeCount")),
            "comments": integer(post.get("replyCount")),
            "reposts": integer(post.get("repostCount")),
            "quotes": integer(post.get("quoteCount")),
        }
        for post in posts if isinstance(post, dict) and post.get("uri")
    }


def linkedin_metrics(receipts: list[dict[str, Any]], token: str, author_urn: str) -> dict[str, dict[str, Any]]:
    """Read organic company-post statistics when LinkedIn has granted reporting access."""
    if not token or not author_urn:
        return {}
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "User-Agent": "artificial.one-daily-report/1.0",
    }
    result: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        if receipt.get("platform") != "linkedin":
            continue
        urn = receipt_urn(receipt)
        url = (
            "https://api.linkedin.com/rest/organizationalEntityShareStatistics"
            f"?q=organizationalEntity&organizationalEntity={quote(author_urn, safe='')}"
            f"&shares=List({quote(urn, safe='')})"
        )
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                elements = json.load(response).get("elements", [])
            totals = elements[0].get("totalShareStatistics", {}) if elements else {}
            result[urn] = {
                "likes": integer(totals.get("likeCount")),
                "comments": integer(totals.get("commentCount")),
                "reposts": integer(totals.get("shareCount")),
                "views": integer(totals.get("impressionCount")),
                "clicks": integer(totals.get("clickCount")),
            }
        except Exception:
            continue
    return result


def social_posts_for_day(
    receipts: dict[str, Any], report_date: date, metrics: dict[str, dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    metrics = metrics or {}
    grouped: dict[str, list[dict[str, Any]]] = {platform: [] for platform in SOCIAL_PLATFORMS}
    for receipt in receipts.get("receipts", []):
        if not isinstance(receipt, dict) or local_receipt_date(receipt) != report_date:
            continue
        platform = str(receipt.get("platform") or "").casefold()
        if platform not in grouped:
            grouped[platform] = []
        urn = receipt_urn(receipt)
        grouped[platform].append({
            "title": str(receipt.get("title") or receipt.get("item_id") or "Artificial.One post"),
            "url": str(receipt.get("url") or ""),
            "published_at": str(receipt.get("published_at") or ""),
            "metrics": metrics.get(urn),
        })
    for posts in grouped.values():
        posts.sort(key=lambda item: item["published_at"])
    return grouped


def social_posts_for_window(
    receipts: dict[str, Any], window_end: datetime,
    metrics: dict[str, dict[str, Any]] | None = None, hours: int = 24,
) -> dict[str, list[dict[str, Any]]]:
    """Group every post from a rolling reporting window."""
    metrics = metrics or {}
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=PRAGUE)
    window_end = window_end.astimezone(PRAGUE)
    window_start = window_end - timedelta(hours=hours)
    grouped: dict[str, list[dict[str, Any]]] = {platform: [] for platform in SOCIAL_PLATFORMS}
    for receipt in receipts.get("receipts", []):
        if not isinstance(receipt, dict):
            continue
        published = local_receipt_datetime(receipt)
        if published is None or published <= window_start or published > window_end:
            continue
        platform = str(receipt.get("platform") or "").casefold()
        grouped.setdefault(platform, [])
        urn = receipt_urn(receipt)
        grouped[platform].append({
            "title": str(receipt.get("title") or receipt.get("item_id") or "Artificial.One post"),
            "url": str(receipt.get("url") or ""),
            "published_at": str(receipt.get("published_at") or ""),
            "metrics": metrics.get(urn),
        })
    for posts in grouped.values():
        posts.sort(key=lambda item: item["published_at"])
    return grouped


def social_performance(root: Path, window_end: datetime) -> dict[str, list[dict[str, Any]]]:
    receipts = load_json(root / "data" / "distribution_receipts.json", {"receipts": []})
    window_start = window_end - timedelta(hours=24)
    recent = [
        item for item in receipts.get("receipts", [])
        if isinstance(item, dict)
        and (published := local_receipt_datetime(item)) is not None
        and window_start < published <= window_end
    ]
    metrics: dict[str, dict[str, Any]] = {}
    metrics.update(bluesky_metrics(recent))
    metrics.update(linkedin_metrics(
        recent,
        os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip(),
        os.environ.get("LINKEDIN_AUTHOR_URN", "").strip(),
    ))
    return social_posts_for_window(receipts, window_end, metrics)


def github_health(token: str, repository: str, now: datetime) -> dict[str, Any]:
    if not token or not repository:
        return {"status": "unknown", "healthy": 0, "attention": 0, "issues": []}
    since = (now.astimezone(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"https://api.github.com/repos/{repository}/actions/runs?per_page=100&created=%3E%3D{quote(since)}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "artificial.one-daily-report/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception:
        return {"status": "unknown", "healthy": 0, "attention": 0, "issues": []}
    latest: dict[str, dict[str, Any]] = {}
    for run in payload.get("workflow_runs", []):
        name = str(run.get("name") or run.get("workflow_id") or "")
        created = str(run.get("created_at") or "")
        if name and (name not in latest or created > str(latest[name].get("created_at") or "")):
            latest[name] = run
    attention = sum(
        str(run.get("status")) == "completed" and str(run.get("conclusion")) not in {"success", "skipped", "neutral"}
        for run in latest.values()
    )
    pending = sum(str(run.get("status")) != "completed" for run in latest.values())
    healthy = len(latest) - attention - pending
    status = "healthy" if attention == 0 else "recovering"
    issues: list[dict[str, str]] = []
    for name, run in sorted(latest.items()):
        if str(run.get("status")) != "completed" or str(run.get("conclusion")) in {"success", "skipped", "neutral"}:
            continue
        failed_work = "The automation run did not complete."
        jobs_url = str(run.get("jobs_url") or "")
        if jobs_url:
            try:
                with urlopen(Request(jobs_url, headers=headers), timeout=30) as response:
                    jobs = json.load(response).get("jobs", [])
                failed_jobs = []
                for job in jobs:
                    failed_steps = [
                        str(step.get("name") or "") for step in job.get("steps", [])
                        if str(step.get("conclusion") or "") not in {"", "success", "skipped", "neutral"}
                    ]
                    if failed_steps:
                        failed_jobs.append(f"{job.get('name') or 'Job'} — {', '.join(failed_steps)}")
                    elif str(job.get("conclusion") or "") not in {"success", "skipped", "neutral"}:
                        failed_jobs.append(str(job.get("name") or "Job failed"))
                if failed_jobs:
                    failed_work = "; ".join(failed_jobs)
            except Exception:
                pass
        issues.append({
            "name": name,
            "url": str(run.get("html_url") or ""),
            "result": str(run.get("conclusion") or "needs another attempt").replace("_", " "),
            "failed_work": failed_work,
        })
    return {"status": status, "healthy": healthy, "attention": attention, "pending": pending, "issues": issues}


def report_model(
    root: Path, snapshot_path: Path, report_date: date, health: dict[str, Any],
    marketplace_status_path: Path | None = None, report_time: datetime | None = None,
    search_snapshot_path: Path | None = None,
) -> dict[str, Any]:
    diary = load_json(root / "data" / "business_activity_diary.json", {"entries": []})
    reconciliation = load_json(root / "data" / "affiliate_source_reconciliation.json", {})
    opportunities = load_json(root / "data" / "partner_opportunities.json", {})
    partner_offers = load_json(root / "data" / "partner_offers.json", {"offers": []})
    appsumo = load_json(root / "data" / "appsumo_offers.json", {"offers": []})
    snapshot = load_json(snapshot_path, {})
    marketplace = load_json(marketplace_status_path, {}) if marketplace_status_path else {}
    search = load_json(search_snapshot_path, {}) if search_snapshot_path else {}
    activity = daily_activity(diary, report_date.isoformat())
    partnerstack = snapshot.get("partnerstack", {})
    impact = snapshot.get("impact", {})
    acquisition = snapshot.get("acquisition", {})
    clicks = partnerstack.get("affiliate_clicks", acquisition.get("clicks", {}))
    visits = acquisition.get("visits", {})
    ps_revenue = integer(partnerstack.get("transactions", {}).get("amount_usd_cents")) / 100
    ps_commission = integer(partnerstack.get("rewards", {}).get("amount_usd_cents")) / 100
    impact_revenue = money_map(impact.get("actions", {}).get("revenue", {}))
    impact_commission = money_map(impact.get("actions", {}).get("commissions", {}))
    summary = reconciliation.get("summary", {})
    published = live_affiliate_destinations(partner_offers, appsumo)
    actions = owner_actions(reconciliation, opportunities, marketplace)
    work_queue = system_work(reconciliation, opportunities)
    report_time = report_time or datetime.combine(report_date, datetime.max.time(), tzinfo=PRAGUE)
    social = social_performance(root, report_time)
    revenue_text = f"USD {ps_revenue:.2f} + {impact_revenue}" if impact_revenue != "USD 0.00" else f"USD {ps_revenue:.2f}"
    commission_text = f"USD {ps_commission:.2f} + {impact_commission}" if impact_commission != "USD 0.00" else f"USD {ps_commission:.2f}"
    return {
        "date": report_date,
        "activity": activity,
        "published_offers": published,
        "visits": integer(visits.get("total")),
        "visit_window_days": integer(visits.get("window_days")) or 28,
        "clicks": integer(clicks.get("total")),
        "click_window_days": integer(clicks.get("window_days")) or 28,
        "signups": integer(partnerstack.get("customers", {}).get("count")),
        "paying_customers": integer(partnerstack.get("customers", {}).get("paid_count")),
        "partnerstack_transactions": integer(partnerstack.get("transactions", {}).get("count")),
        "impact_actions": integer(impact.get("actions", {}).get("count")),
        "revenue": revenue_text,
        "commissions": commission_text,
        "owner_actions": actions,
        "system_work": work_queue,
        "social": social,
        "search": search,
        "blocking_failures": integer(summary.get("blocking_failures")),
        "health": health,
        "content_orders": integer(marketplace.get("orders_total")),
        "content_fulfilling": integer(marketplace.get("fulfilling")),
        "content_completed": integer(marketplace.get("completed")),
    }


def management_summary(model: dict[str, Any]) -> str:
    activity = model["activity"]
    pieces: list[str] = []
    if activity["pages_created"]:
        pieces.append(f"published {activity['pages_created']} new page{'s' if activity['pages_created'] != 1 else ''}")
    if activity["pages_updated"]:
        pieces.append(f"improved {activity['pages_updated']} existing page{'s' if activity['pages_updated'] != 1 else ''}")
    if activity["social_posts"]:
        pieces.append(f"published {activity['social_posts']} social post{'s' if activity['social_posts'] != 1 else ''}")
    completed = ", ".join(pieces) if pieces else "no new public content was released"
    action_count = len(model.get("owner_actions") or [])
    action_note = (
        f" {action_count} decision{'s' if action_count != 1 else ''} {'need' if action_count != 1 else 'needs'} your attention."
        if action_count else " Nothing needs your attention today."
    )
    return (
        f"Today: {completed}. The site has {model['published_offers']} live partner destinations and recorded "
        f"{model['clicks']} affiliate clicks in the last {model.get('click_window_days', 28)} days."
        f"{action_note}"
    )


def metric_card(label: str, value: str, background: str, note: str = "") -> str:
    return (
        f"<td class='metric-cell' width='50%' style='padding:6px;vertical-align:top'><div style='background:{background};"
        "border:1px solid rgba(81,60,133,.08);border-radius:18px;padding:20px;min-height:104px'>"
        f"<div style='font-size:12px;color:#6f6585;font-weight:800;text-transform:uppercase;letter-spacing:.8px'>{escape(label)}</div>"
        f"<div style='font-size:29px;line-height:1;font-weight:900;color:#211a35;margin-top:11px'>{escape(value)}</div>"
        + (f"<div style='font-size:12px;color:#776f87;margin-top:9px;line-height:1.4'>{escape(note)}</div>" if note else "")
        + "</div></td>"
    )


def trend_text(current: float, previous: float, *, lower_is_better: bool = False, percentage_points: bool = False) -> str:
    delta = current - previous
    improved = delta < 0 if lower_is_better else delta > 0
    if percentage_points:
        amount = f"{abs(delta) * 100:.2f} percentage points"
    elif previous:
        amount = f"{abs(delta / previous) * 100:.1f}%"
    elif current:
        amount = "new activity"
    else:
        return "no change"
    if delta == 0:
        return "no change"
    return f"{amount} {'better' if improved else 'lower' if not lower_is_better else 'worse'} than the previous period"


def render_search(search: dict[str, Any]) -> tuple[str, str]:
    if not search:
        return "", "Google visibility data is not available yet."

    period = search.get("period") or {}
    performance = search.get("performance") or {}
    current = performance.get("current") or {}
    indexing = search.get("indexing") or {}
    commercial = search.get("commercial_search") or {}
    clicks = integer(current.get("clicks"))
    impressions = integer(current.get("impressions"))
    ctr = float(current.get("ctr") or 0)
    position = float(current.get("position") or 0)
    indexed = integer(indexing.get("indexed"))
    inspected = integer(indexing.get("inspected"))
    affiliate_pages = integer(indexing.get("affiliate_pages")) or inspected
    index_issues = integer(indexing.get("issues"))
    healthy_percent = (indexed / affiliate_pages * 100) if affiliate_pages else 0

    issue_details = indexing.get("issue_details") or []
    if issue_details:
        issue_html = "".join(
            "<div style='background:#fff8e8;border:1px solid #f3dfae;border-radius:12px;padding:12px 14px;margin-top:8px'>"
            f"<a href='{escape(str(item.get('url') or ''))}' style='color:#5540aa;text-decoration:none;font-weight:800'>"
            f"{escape(str(item.get('url') or 'Affiliate page'))}</a>"
            f"<div style='font-size:12px;color:#7b6653;margin-top:4px'>{escape(str(item.get('detail') or item.get('status') or 'Needs attention'))}</div>"
            "</div>" for item in issue_details
        )
        issue_block = f"<div style='margin-top:18px'><strong style='color:#4a3b2d'>Pages to watch</strong>{issue_html}</div>"
        issue_text = "\n".join(f"- {item.get('url')}: {item.get('detail') or item.get('status')}" for item in issue_details)
    else:
        issue_block = "<div style='margin-top:16px;background:#e9f8f1;border-radius:12px;padding:12px 14px;color:#27614a'><strong>All checked affiliate pages look healthy.</strong></div>"
        issue_text = "- All checked affiliate pages look healthy."

    top_pages = commercial.get("top_pages") or []
    top_html = "".join(
        "<div style='background:#ffffff;border:1px solid #dce8f7;border-radius:12px;padding:12px 14px;margin-top:8px'>"
        f"<a href='https://artificial.one{escape(str(item.get('path') or '/'))}' style='color:#5540aa;text-decoration:none;font-weight:800'>{escape(str(item.get('path') or '/'))}</a>"
        f"<div style='font-size:12px;color:#776f87;margin-top:5px'>{integer(item.get('clicks'))} visits from Google · {integer(item.get('impressions'))} search appearances</div></div>"
        for item in top_pages[:3]
    ) or "<div style='font-size:13px;color:#776f87;margin-top:8px'>Affiliate pages have not appeared in Google results yet.</div>"

    search_console_url = "https://search.google.com/search-console?resource_id=" + quote("https://artificial.one/", safe="")
    html = f'''<tr><td class="section-pad" style="padding:14px 28px"><div style="background:#edf6ff;border:1px solid #dceaf8;border-radius:22px;padding:24px">
      <div style="font-size:11px;font-weight:900;letter-spacing:1.2px;color:#4875a8;text-transform:uppercase">Google visibility</div>
      <h2 style="font-size:22px;color:#211a35;margin:7px 0 5px">Can customers find our affiliate pages?</h2>
      <p style="font-size:13px;color:#6f6880;margin:0 0 16px">Results for {escape(str(period.get('start') or '?'))} &ndash; {escape(str(period.get('end') or '?'))}</p>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
        <td width="33%" style="padding:5px"><div style="background:#ffffff;border-radius:15px;padding:16px"><div style="font-size:24px;font-weight:900;color:#28644d">{indexed}/{affiliate_pages}</div><div style="font-size:12px;color:#706880;margin-top:6px">affiliate pages indexed &middot; {healthy_percent:.0f}%</div></div></td>
        <td width="33%" style="padding:5px"><div style="background:#ffffff;border-radius:15px;padding:16px"><div style="font-size:24px;font-weight:900;color:#5540aa">{impressions}</div><div style="font-size:12px;color:#706880;margin-top:6px">search appearances</div></div></td>
        <td width="33%" style="padding:5px"><div style="background:#ffffff;border-radius:15px;padding:16px"><div style="font-size:24px;font-weight:900;color:#b45b3d">{clicks}</div><div style="font-size:12px;color:#706880;margin-top:6px">visits from Google</div></div></td>
      </tr></table>
      <div style="font-size:12px;color:#6f6880;margin:12px 5px 0">Click-through rate <strong>{ctr * 100:.2f}%</strong> &middot; average search position <strong>{position:.1f}</strong> &middot; <strong>{index_issues}</strong> page{'s' if index_issues != 1 else ''} to watch</div>
      {issue_block}
      <div style="margin-top:18px"><strong style="color:#2e2840">Most visible affiliate pages</strong>{top_html}</div>
      <div style="margin-top:18px"><a href="{search_console_url}" style="display:inline-block;background:#5540aa;color:white;text-decoration:none;font-weight:800;border-radius:12px;padding:11px 16px">Explore Google performance &rarr;</a></div>
    </div></td></tr>'''
    text = "\n".join([
        f"Period: {period.get('start')} to {period.get('end')}",
        f"Google clicks: {clicks}; search appearances: {impressions}; CTR: {ctr * 100:.2f}%; average position: {position:.1f}",
        f"Affiliate pages indexed: {indexed}/{affiliate_pages}; pages to watch: {index_issues}",
        f"Affiliate pages with Google impressions: {integer(commercial.get('pages_with_impressions'))}",
        issue_text,
    ])
    return html, text


def readable_social_metrics(values: dict[str, Any] | None) -> str:
    if values is None:
        return "Open the post to see live engagement"
    labels = (
        ("likes", "likes"), ("comments", "comments"), ("reposts", "reposts/shares"),
        ("quotes", "quotes"), ("views", "views"), ("clicks", "post clicks"),
    )
    return " · ".join(f"{integer(values.get(key))} {label}" for key, label in labels if key in values)


def render_social(social: dict[str, list[dict[str, Any]]]) -> tuple[str, str]:
    names = {"linkedin": "LinkedIn", "bluesky": "Bluesky", "x": "X"}
    colors = {
        "linkedin": ("#eaf3ff", "#2367a7", "in"),
        "bluesky": ("#eaf8ff", "#1673b8", "&#129419;"),
        "x": ("#f0eef8", "#302846", ""),
    }
    platform_html: list[str] = []
    platform_text: list[str] = []
    for platform in SOCIAL_PLATFORMS:
        posts = social.get(platform, [])
        platform_text.append(names[platform])
        background, accent, icon = colors[platform]
        platform_label = f"{icon}&nbsp;&nbsp;{names[platform]}" if icon else names[platform]
        if not posts:
            platform_html.append(
                f"<div style='background:{background};border-radius:15px;padding:14px 16px;margin:0 0 10px'>"
                f"<strong style='color:{accent}'>{platform_label}</strong>"
                "<div style='color:#706880;font-size:12px;margin-top:5px'>No new post in the last 24 hours.</div></div>"
            )
            platform_text.append("- No new post in the last 24 hours.")
            continue
        rows = []
        for post in posts:
            title = escape(post["title"])
            url = escape(post["url"])
            metrics = escape(readable_social_metrics(post.get("metrics")))
            metrics_html = (
                f"<div style='font-size:12px;color:#706880;margin:7px 0 11px'>{metrics}</div>"
                if post.get("metrics") is not None else "<div style='height:8px'></div>"
            )
            rows.append(
                "<div style='background:#fff;border:1px solid #e7e1f2;border-radius:14px;padding:14px 16px;margin-top:10px'>"
                f"<div style='font-size:14px;font-weight:800;color:#28213a;line-height:1.4;overflow-wrap:anywhere;word-break:break-word'>{title}</div>"
                f"{metrics_html}"
                f"<a href='{url}' style='display:inline-block;color:{accent};text-decoration:none;font-size:12px;font-weight:900'>View post &rarr;</a></div>"
            )
            platform_text.append(f"- {post['title']}: {post['url']} — {readable_social_metrics(post.get('metrics'))}")
        platform_html.append(
            f"<div style='background:{background};border-radius:17px;padding:16px 17px;margin:0 0 12px'>"
            f"<strong style='color:{accent}'>{platform_label} &middot; {len(posts)} new</strong>{''.join(rows)}</div>"
        )
    html = (
        '<tr><td class="section-pad" style="padding:14px 28px"><div style="background:#f6f2ff;border:1px solid #e9e1f7;border-radius:22px;padding:24px">'
        '<div style="font-size:11px;font-weight:900;letter-spacing:1.2px;color:#7151bd;text-transform:uppercase">Audience growth</div>'
        '<h2 style="font-size:22px;color:#211a35;margin:7px 0 5px">Social pulse &middot; last 24 hours</h2>'
        '<p style="font-size:13px;color:#706880;margin:0 0 16px">Every new post and its live engagement, in one place.</p>'
        + "".join(platform_html) + "</div></td></tr>"
    )
    return html, "\n".join(platform_text)


def render(model: dict[str, Any]) -> tuple[str, str, str]:
    day = model["date"]
    pretty_date = day.strftime("%d %B %Y")
    subject = f"Artificial.One daily pulse — {pretty_date}"
    action_count = len(model["owner_actions"])
    summary = management_summary(model)
    social_html, social_text = render_social(model.get("social") or {})
    search_html, search_text = render_search(model.get("search") or {})
    highlights = model["activity"]["highlights"]
    if highlights:
        highlight_html = "".join(
            "<div style='background:#ffffff;border:1px solid #e9e2f3;border-radius:14px;padding:14px 16px;margin-top:9px'>"
            "<span style='color:#6e49c6;font-weight:900'>&#10003;</span>&nbsp;&nbsp;" +
            (f"<a href='{escape(item['url'])}' style='color:#302545;text-decoration:none;font-weight:800'>{escape(item['text'])}</a>" if item["url"] else f"<strong style='color:#302545'>{escape(item['text'])}</strong>") +
            "</div>" for item in highlights
        )
        highlights_text = "\n".join(f"- {item['text']}" for item in highlights)
        wins_html = f'''<tr><td class="section-pad" style="padding:14px 28px"><div style="background:#fbf9ff;border:1px solid #ece6f5;border-radius:22px;padding:24px">
          <div style="font-size:11px;font-weight:900;letter-spacing:1.2px;color:#7151bd;text-transform:uppercase">Fresh today</div>
          <h2 style="font-size:22px;color:#211a35;margin:7px 0 10px">What moved forward</h2>{highlight_html}
        </div></td></tr>'''
    else:
        highlights_text = "- No new public content today."
        wins_html = ""

    if action_count:
        shown = model["owner_actions"]
        action_html = "".join(
            "<div style='background:#ffffff;border:1px solid #f2d9b5;border-radius:15px;padding:16px 17px;margin-top:10px'>"
            f"<div style='font-weight:900;color:#53351e;overflow-wrap:anywhere;word-break:break-word'>{escape(action['title'])}</div>"
            f"<div style='font-size:13px;color:#7a6858;margin:6px 0 12px;line-height:1.45;overflow-wrap:anywhere;word-break:break-word'>{escape(action['detail'])}</div>"
            f"<a href='{escape(action['url'])}' style='display:inline-block;background:#ec6f55;color:white;text-decoration:none;"
            "font-weight:900;border-radius:12px;padding:11px 16px'>Review and decide &rarr;</a></div>"
            for action in shown
        )
        action_intro = f"{action_count} decision{'s' if action_count != 1 else ''} for you"
        action_text = "\n".join(f"- {item['title']}: {item['url']}" for item in shown)
        action_section = f'''<tr><td class="section-pad" style="padding:14px 28px"><div style="background:#fff4e5;border:1px solid #f1ddbd;border-radius:22px;padding:24px">
          <div style="display:inline-block;background:#ffe0ca;color:#8c3f25;border-radius:20px;padding:6px 10px;font-size:11px;font-weight:900;text-transform:uppercase;letter-spacing:.8px">Your attention</div>
          <h2 style="font-size:22px;color:#3d2a1d;margin:10px 0 4px">{escape(action_intro)}</h2>
          <p style="font-size:13px;color:#7a6858;margin:0 0 4px">Quick choices that require a person.</p>{action_html}
        </div></td></tr>'''
    else:
        action_intro = "Nothing needs your attention"
        action_text = "- Nothing needs your attention today."
        action_section = '''<tr><td class="section-pad" style="padding:14px 28px"><div style="background:#e9f8f1;border:1px solid #cfeadd;border-radius:18px;padding:16px 19px;color:#28614a"><strong>&#10003; Nothing needs your attention today.</strong></div></td></tr>'''

    work = model.get("system_work") or []
    if work:
        work_rows = "".join(
            "<span style='display:inline-block;background:#ffffff;border:1px solid #dfe7f4;border-radius:20px;"
            f"padding:8px 12px;margin:5px 5px 0 0;font-size:12px;font-weight:800;color:#2c3150'>{escape(item['title'])}</span>"
            for item in work
        )
        work_html = f'''<tr><td class="section-pad" style="padding:14px 28px"><div style="background:#f0f5ff;border:1px solid #dfe8f7;border-radius:22px;padding:24px">
          <div style="font-size:11px;font-weight:900;letter-spacing:1.2px;color:#4e6fa7;text-transform:uppercase">Partner pipeline</div>
          <h2 style="font-size:22px;color:#211a35;margin:7px 0 5px">Approved and waiting for a link</h2>
          <p style="font-size:13px;color:#70758a;margin:0 0 8px">These pages will appear automatically when their referral links become available.</p>{work_rows}
        </div></td></tr>'''
        work_text = (
            "Approved; pages will publish when referral links become available: "
            + ", ".join(item["title"] for item in work)
        )
    else:
        work_html = ""
        work_text = "- None."

    attention_label = f"{action_count} decision{'s' if action_count != 1 else ''}" if action_count else "No action needed"
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>
@media only screen and (max-width:600px){{
  body,table,tbody,tr,td,div,p,h1,h2,a{{box-sizing:border-box!important;max-width:100%!important;overflow-wrap:anywhere!important;word-break:break-word!important}}
  table{{table-layout:fixed!important}}
  img{{max-width:100%!important}}
  .email-shell{{width:100%!important;max-width:100%!important;border-radius:0!important}}
  .outer-pad{{padding:0!important}}
  .hero-pad{{padding:22px 16px!important}}
  .hero-badge{{display:none!important;width:0!important}}
  .hero-logo-cell{{width:58px!important}}
  .hero-logo{{width:50px!important;height:50px!important}}
  .hero-title{{font-size:23px!important}}
  .section-pad{{padding-left:12px!important;padding-right:12px!important}}
  .metric-cell{{display:block!important;width:100%!important;box-sizing:border-box!important}}
  .journey-cell{{display:block!important;width:100%!important;border-left:0!important;border-top:1px solid #e5deec!important;box-sizing:border-box!important}}
}}
</style></head><body style="margin:0;background:#f3f0f8;font-family:Arial,Helvetica,sans-serif;color:#211a35">
<div style="display:none;max-height:0;overflow:hidden;color:transparent">Revenue, traffic, partnerships, Google visibility and social performance &mdash; beautifully brief.</div>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f0f8"><tr><td class="outer-pad" align="center" style="padding:26px 10px">
<table class="email-shell" role="presentation" width="100%" cellspacing="0" cellpadding="0" style="width:100%;max-width:700px;background:#ffffff;border-radius:28px;overflow:hidden;box-shadow:0 18px 50px rgba(57,42,91,.12)">
<tr><td class="hero-pad" style="padding:30px;background-color:#33254e;background-image:linear-gradient(135deg,#33254e 0%,#6651a5 55%,#4c8d86 100%);color:#ffffff">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
    <td class="hero-logo-cell" width="76" valign="middle"><img class="hero-logo" src="https://artificial.one/images/social/artificial-one-logo.png" width="64" height="64" alt="Artificial.One elephant" style="display:block;border-radius:17px;border:2px solid rgba(255,255,255,.25)"></td>
    <td valign="middle"><div style="font-size:12px;font-weight:900;letter-spacing:1.3px;color:#d9f8ad">ARTIFICIAL.ONE</div><h1 class="hero-title" style="margin:5px 0 0;font-size:29px;line-height:1.1">Growth &amp; revenue pulse</h1></td>
    <td class="hero-badge" align="right" valign="middle"><span style="display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.2);border-radius:20px;padding:7px 10px;font-size:11px;font-weight:800">{escape(attention_label)}</span></td>
  </tr></table>
  <div style="font-size:13px;color:#e7e2f2;margin-top:18px">{escape(pretty_date)}</div>
  <p style="font-size:16px;line-height:1.55;margin:10px 0 0;color:#ffffff">{escape(summary)}</p>
</td></tr>
{action_section}
<tr><td class="section-pad" style="padding:14px 22px 4px"><div style="font-size:11px;font-weight:900;letter-spacing:1.2px;color:#7151bd;text-transform:uppercase;margin:0 12px 5px">At a glance</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
    {metric_card('Revenue', model['revenue'], '#eee8ff', 'Confirmed partner sales')}
    {metric_card('Commission earned', model['commissions'], '#fff0dc', 'Recorded by partner networks')}
  </tr><tr>
    {metric_card('Website visits', str(model['visits']), '#e7f8f0', f"Last {model.get('visit_window_days', 28)} days")}
    {metric_card('Affiliate link clicks', str(model['clicks']), '#e8f3ff', f"Last {model.get('click_window_days', 28)} days")}
  </tr></table>
</td></tr>
<tr><td class="section-pad" style="padding:14px 28px"><div style="background:#f8f5fc;border:1px solid #ebe4f2;border-radius:22px;padding:23px">
  <div style="font-size:11px;font-weight:900;letter-spacing:1.2px;color:#7151bd;text-transform:uppercase">Revenue journey</div>
  <h2 style="font-size:22px;color:#211a35;margin:7px 0 16px">From choice to customer</h2>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr>
    <td class="journey-cell" width="25%" align="center" style="padding:8px"><div style="font-size:25px;font-weight:900;color:#5540aa">{model['published_offers']}</div><div style="font-size:11px;color:#706880;margin-top:5px">live partner destinations</div></td>
    <td class="journey-cell" width="25%" align="center" style="padding:8px;border-left:1px solid #e5deec"><div style="font-size:25px;font-weight:900;color:#5540aa">{model['signups']}</div><div style="font-size:11px;color:#706880;margin-top:5px">referred sign-ups</div></td>
    <td class="journey-cell" width="25%" align="center" style="padding:8px;border-left:1px solid #e5deec"><div style="font-size:25px;font-weight:900;color:#28644d">{model['paying_customers']}</div><div style="font-size:11px;color:#706880;margin-top:5px">paying customers</div></td>
    <td class="journey-cell" width="25%" align="center" style="padding:8px;border-left:1px solid #e5deec"><div style="font-size:25px;font-weight:900;color:#b45b3d">{model['impact_actions'] + model.get('partnerstack_transactions', 0)}</div><div style="font-size:11px;color:#706880;margin-top:5px">tracked leads or sales</div></td>
  </tr></table>
</div></td></tr>
{wins_html}
{search_html}
{social_html}
{work_html}
<tr><td align="center" style="background:#29213d;color:#ddd6ea;padding:24px 28px;font-size:12px;line-height:1.6">
  <strong style="color:#ffffff">Artificial.One</strong> &middot; independent AI-tool decisions<br>
  <a href="https://artificial.one/" style="color:#c8ff84;text-decoration:none;font-weight:800">Visit the website &rarr;</a>
</td></tr></table></td></tr></table></body></html>"""

    text = "\n".join([
        "ARTIFICIAL.ONE — DAILY GROWTH & REVENUE PULSE", pretty_date, "", summary, "",
        "AT A GLANCE",
        f"Revenue: {model['revenue']}", f"Commissions: {model['commissions']}",
        f"Site visits (last {model.get('visit_window_days', 28)} days): {model['visits']}",
        f"Affiliate link clicks (last {model.get('click_window_days', 28)} days): {model['clicks']}",
        f"Live partner destinations: {model['published_offers']}",
        f"Referred sign-ups: {model['signups']}",
        f"Paying customers: {model['paying_customers']}",
        f"Tracked leads or sales: {model['impact_actions'] + model.get('partnerstack_transactions', 0)}", "",
        "WHAT MOVED FORWARD", highlights_text, "", "YOUR DECISIONS", action_text, "",
        "GOOGLE VISIBILITY", search_text, "", "SOCIAL PULSE — LAST 24 HOURS", social_text, "",
        "APPROVED PARTNERSHIPS WAITING FOR LINKS", work_text,
    ]) + "\n"
    return subject, text, html


def resend_json(api_key: str, url: str, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "artificial.one-daily-report/1.1",
    }, method="POST" if payload is not None else "GET")
    with urlopen(request, timeout=40) as response:
        if response.status >= 300:
            raise RuntimeError(f"Resend request failed with HTTP {response.status}")
        response_body = response.read().decode("utf-8")
    result = json.loads(response_body or "{}")
    if not isinstance(result, dict):
        raise RuntimeError("Resend returned an unexpected response")
    return result


def verified_sender(api_key: str, requested_sender: str) -> str:
    """Prefer our verified domain instead of Resend's testing-only sender."""
    if "@resend.dev" not in requested_sender.casefold():
        return requested_sender
    try:
        domains = resend_json(api_key, RESEND_DOMAINS_URL).get("data", [])
    except Exception as exc:  # Sending still produces a precise API error if discovery is unavailable.
        print(f"Could not inspect verified sending domains: {type(exc).__name__}")
        return requested_sender
    eligible = [
        str(item.get("name") or "").strip().casefold()
        for item in domains
        if isinstance(item, dict)
        and str(item.get("status") or "").casefold() == "verified"
        and (
            str(item.get("name") or "").strip().casefold() == "artificial.one"
            or str(item.get("name") or "").strip().casefold().endswith(".artificial.one")
        )
    ]
    if not eligible:
        return requested_sender
    domain = sorted(eligible, key=lambda value: (value != "artificial.one", len(value)))[0]
    return f"Artificial.One Daily Brief <reports@{domain}>"


def wait_for_delivery(api_key: str, email_id: str, wait_seconds: int = 90) -> str:
    successful = {"delivered", "opened", "clicked"}
    failed = {"bounced", "complained", "suppressed", "failed", "canceled"}
    deadline = time.monotonic() + max(wait_seconds, 0)
    last_event = "accepted"
    while True:
        try:
            details = resend_json(api_key, f"{RESEND_URL}/{quote(email_id, safe='')}")
        except HTTPError as exc:
            if exc.code in {401, 403}:
                print(
                    "Resend accepted the daily report; the configured send-only key "
                    "cannot read delivery events."
                )
                return "accepted_unverified"
            raise
        last_event = str(details.get("last_event") or last_event).casefold()
        if last_event in successful:
            return last_event
        if last_event in failed:
            raise RuntimeError(f"Resend could not deliver the daily report (event: {last_event})")
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Resend accepted the daily report but did not confirm delivery within {wait_seconds} seconds "
                f"(latest event: {last_event})"
            )
        time.sleep(min(5, max(deadline - time.monotonic(), 0)))


def send_email(api_key: str, sender: str, recipient: str, subject: str, text: str, html: str) -> dict[str, str]:
    sender = verified_sender(api_key, sender)
    payload = json.dumps({"from": sender, "to": [recipient], "subject": subject, "text": text, "html": html}).encode()
    request = Request(RESEND_URL, data=payload, headers={
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
        "User-Agent": "artificial.one-daily-report/1.1",
    }, method="POST")
    with urlopen(request, timeout=40) as response:
        if response.status >= 300:
            raise RuntimeError(f"Daily report delivery failed with HTTP {response.status}")
        response_body = response.read().decode("utf-8")
    result = json.loads(response_body or "{}")
    email_id = str(result.get("id") or "").strip()
    if not email_id:
        raise RuntimeError("Resend accepted the report without returning a message ID")
    event = wait_for_delivery(api_key, email_id)
    status_label = "confirmed" if event in {"delivered", "opened", "clicked"} else "recorded"
    print(f"Resend daily report status {status_label}: id={email_id}, event={event}, sender={sender}")
    return {"id": email_id, "event": event, "sender": sender}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=Path(".daily-executive/affiliate-snapshot.json"))
    parser.add_argument("--state", type=Path, default=Path(".daily-executive/state.json"))
    parser.add_argument("--marketplace-status", type=Path, default=Path(".content-marketplace/status.json"))
    parser.add_argument("--search-snapshot", type=Path, default=Path(".search-growth/executive-snapshot.json"))
    parser.add_argument("--email-to", default="")
    parser.add_argument("--email-from", default="Artificial.One Daily Brief <onboarding@resend.dev>")
    parser.add_argument("--date", default="")
    parser.add_argument("--output-html", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    now = datetime.now(PRAGUE)
    report_date = date.fromisoformat(args.date) if args.date else now.date()
    state = load_json(args.state, {})
    if args.email_to and not args.force and state.get("last_sent_date") == report_date.isoformat():
        print(f"Daily executive report already sent for {report_date.isoformat()}.")
        return 0
    health = github_health(os.environ.get("GITHUB_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""), now)
    model = report_model(ROOT, args.snapshot, report_date, health, args.marketplace_status, now, args.search_snapshot)
    subject, text, html = render(model)
    if args.output_html:
        args.output_html.parent.mkdir(parents=True, exist_ok=True)
        args.output_html.write_text(html, encoding="utf-8")
    if args.email_to:
        api_key = os.environ.get("RESEND_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("RESEND_API_KEY is required to send the daily report")
        delivery = send_email(api_key, args.email_from, args.email_to, subject, text, html)
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps({
            "last_sent_date": report_date.isoformat(),
            "last_sent_at": now.isoformat(timespec="seconds"),
            "subject": subject,
            "resend_email_id": delivery["id"],
            "delivery_event": delivery["event"],
            "sender": delivery["sender"],
        }, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared executive report for {report_date.isoformat()}: {subject}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
